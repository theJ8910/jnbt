import os
import sys
import math
from struct import calcsize, Struct
from array import array

#Tag Types
#A TAG_End is a nameless tag that terminates TAG_Compound and is the default tagType for an empty TAG_List.
#It has no payload, and its named tag header is simply b"\0" because it is nameless (and therefore lacks any name-related entries).
TAG_END        = 0
TAG_BYTE       = 1  #A TAG_Byte payload stores a 1-byte signed integer.
TAG_SHORT      = 2  #A TAG_Short payload stores a 2-byte big-endian signed integer.
TAG_INT        = 3  #A TAG_Int payload stores a 4-byte big-endian signed integer.
TAG_LONG       = 4  #A TAG_Long payload stores an 8-byte big-endian signed integer.
TAG_FLOAT      = 5  #A TAG_Float payload stores a big-endian float (a 4-byte IEEE 754-2008, aka binary32).
TAG_DOUBLE     = 6  #A TAG_Double payload stores a big-endian double (an 8-byte IEEE 754-2008, aka binary64).
TAG_BYTE_ARRAY = 7  #A TAG_Byte_Array stores bytes of an unspecified format. The payload consists of the length of the array (a 4-byte big-endian signed integer), followed by exactly that many bytes.
TAG_STRING     = 8  #A TAG_String stores a UTF-8 encoded string. It starts with the length of the encoded string _in bytes_ (a 2-byte big-endian signed integer), followed by the encoded bytes.
TAG_LIST       = 9  #A TAG_List stores several tags of the same type. The payload consists of a single byte encoding the tagType, followed by the length of the list (a 4-byte big-endian signed integer), followed by that many payloads of the specified tag.
TAG_COMPOUND   = 10 #A TAG_Compound stored several uniquely-named tags of any type. The payload consists of several pairs of named tag headers + tag payloads and is terminated by a TAG_End (null byte).
TAG_INT_ARRAY  = 11 #A TAG_Int_Array's payload consists of the length of the array (a 4-byte big-endian signed integer) followed by that many 4-byte big-endian signed integers.

#Internal names of tags (indexed by tag type) as defined by the NBT specification
TAG_NAMES = (
    "TAG_End",
    "TAG_Byte",
    "TAG_Short",
    "TAG_Int",
    "TAG_Long",
    "TAG_Float",
    "TAG_Double",
    "TAG_Byte_Array",
    "TAG_String",
    "TAG_List",
    "TAG_Compound",
    "TAG_Int_Array"
)

#Total number of tags supported by this version of the library.
TAG_COUNT = len( TAG_NAMES )

#Datatypes for signed and unsigned 4-byte integers
#Unfortunately, we have to select these at runtime because these datatypes are free to vary in size from system to system.
#We /need/ a 4-byte integer type: select one here, or fail if one is not available.
if calcsize( "i" ) == 4:
    SIGNED_INT_TYPE   = "i"
    UNSIGNED_INT_TYPE = "I"
elif calcsize( "l" ) == 4:
    SIGNED_INT_TYPE   = "l"
    UNSIGNED_INT_TYPE = "L"
else:
    raise OSError( "No 4-byte datatype available." )

#math.inf only exists in Python 3.5+
try:
    INF = math.inf
except AttributeError:
    INF = float( "inf" )

#os.scandir/os.DirEntry only exists in Python 3.5+
try:
    scandir = os.scandir
except AttributeError:
    #Implement the same interface as os.scandir() but with pre-Python 3.5 stuff
    class _DirEntryShim:
        name = ""
        path = ""
        def inode( self ):
            return os.lstat( self.path ).st_ino
        def is_dir( self ):
            return os.path.isdir( self.path )
        def is_file( self ):
            return os.path.isfile( self.path )
        def is_symlink( self ):
            return os.path.islink( self.path )
        def stat( self, follow_symlinks=True ):
            if follow_symlinks:
                return os.stat( self.path )
            else:
                return os.lstat( self.path )
    def listdir_to_scandir_shim( path="." ):
        entries = os.listdir( path )
        de = _DirEntryShim()
        for entry in entries:
            de.name = entry
            de.path = os.path.join( path, entry )
            yield de
    scandir = listdir_to_scandir_shim

#Structs
_NT = Struct( ">bh"                   )     #Named tag info
_TL = Struct( ">b" + SIGNED_INT_TYPE  )     #Tag list info
_B  = Struct( ">b"                    )     #Signed byte (1 byte)
_S  = Struct( ">h"                    )     #Signed big-endian short (2 bytes)
_I  = Struct( ">" + SIGNED_INT_TYPE   )     #Signed big-endian int (4 bytes)
_L  = Struct( ">q"                    )     #Signed big-endian long (8 bytes)
_F  = Struct( ">f"                    )     #Big-endian float (4 bytes)
_D  = Struct( ">d"                    )     #Big-endian double (8 bytes)
_UI = Struct( ">" + UNSIGNED_INT_TYPE )     #Unsigned big-endian int (4 bytes)

class NBTFormatError( Exception ):
    """This exception is raised when parsing, writing, or modifying data that violates the NBT specification."""
    pass

class WrongTagError( NBTFormatError ):
    """
    WrongTagError( expected, given )

    This exception is raised when the root tag of an NBT document is not a TAG_Compound, or when the wrong type of tag is written to a TAG_List.
    According to the NBT specification, TAG_Lists are only permitted to contain tags of a single type.
    """
    def __str__( self ):
        return "Expected {}, but received {} instead.".format( describeTag( self.args[0] ), describeTag( self.args[1] ) )

class ConversionError( NBTFormatError ):
    """
    ConversionError( value )

    This exception is raised when failing to find a tag class to convert a non-tag value to.
    This indicates the tag class to convert to couldn't be determined from the context, and there isn't a mapping from value's Python type to a tag class.
    This often happens when value is an int or float; these types don't have tag mappings because there are multiple possible conversions.
    In other words, the type to convert to would be ambiguous:
        * int could be converted TAG_Byte, TAG_Short, TAG_Int, or TAG_Long.
        * float could be converted TAG_Float or TAG_Double.
    If you run into this problem, you can fix it by manually specifying the tag type you want to convert to.
    e.g.
        doc["myNumber"] = 5             #Raises an exception if myNumber doesn't exist. Instead of this...
        doc["myNumber"] = TAG_Int( 5 )  #...try this
        doc.int( "myNumber", 5 )        #...or better yet, this

        ls = doc.list( "myList", [ 10, 11, 12 ] )            #Instead of this...
        ls = doc.list( "myList", [ TAG_Int( 10 ), 11, 12 ] ) #...try this
        ls = doc.list( "myList", [ 10, 11, 12 ], TAG_Int )   #...or better yet, this
    """
    def __str__( self ):
        return "Unable to convert value of type \"{}\" to a tag.".format( self.args[0].__class__.__name__ )

class DuplicateNameError( NBTFormatError ):
    """
    DuplicateNameError( name )

    This exception is raised when multiple tags with the same name are parsed from or written to the same TAG_Compound.
    """
    def __str__( self ):
        return "There is already a tag with the name \"{}\" in this TAG_Compound.".format( self.args[0] )

class UnknownTagTypeError( NBTFormatError ):
    """
    UnknownTagTypeError( tagType )

    This exception is raised when a tag with an invalid or unrecognized type is parsed or written.
    See "Tag Types" above for valid tag types.
    """
    def __str__( self ):
        return "Unknown or unsupported tag type: {:d}".format( self.args[0] )

class OutOfBoundsError( NBTFormatError ):
    """
    OutOfBoundsError( value, min, max )

    This exception is raised when parsing or writing a value that is outside of the valid range for that type.
    This error can be raised for integral types (byte, short, int, long) if the type cannot represent the value,
    or for tag names and sequence types (string, list, bytearray, intarray) if the length is negative or too long to be represented.
    """
    def __str__( self ):
        return "Value {:d} is outside of expected range [{:d},{:d}].".format( *self.args )

def describeTag( tagType ):
    """
    Returns a short description of a tag with the given tagType, including the internal name and numeric type (e.g. TAG_Compound (10) ).
    tagType is expected to be a number.
    If tagType does not represent a valid tag, returns "Unknown (<tagType>)".
    """
    if tagType <= 0 or tagType >= TAG_COUNT:
        return "Unknown ({:d})".format( tagType )
    return "{} ({:d})".format( TAG_NAMES[tagType], tagType )

#_tns
def tagNameString( name ):
    """Return "" if name is None, otherwise return name surrounded by parentheses and double quotes."""
    return "" if name is None else "(\"{}\")".format( name )

#_tls
def tagListString( length, tagType ):
    """
    Returns a str summarizing the contents of a TAG_List with the given length and tagType.
    Return "0 entries" if length == 0.
    Otherwise, return "<length> <name of tag>(s)".
    """
    if length == 0:
        return "0 entries"
    return "{:d} {:s}{}".format( length, TAG_NAMES[tagType], "s" if length != 1 else "" )

#_avtt
def assertValidTagType( tagType ):
    """Raises UnknownTagTypeError if the given tagType is unrecognized"""
    if tagType < 0 or tagType >= TAG_COUNT:
        raise UnknownTagTypeError( tagType )

#_r
def read( i, n ):
    """
    Reads n bytes from i (a readable file-like object).
    Raises an EOFError if the end-of-file is encountered before n bytes can be read.
    """
    b = i.read( n )
    if len( b ) != n:
        raise EOFError( "End of file reached prematurely!" )
    return b

def readinto( i, b ):
    """
    Reads len(b) bytes from i (a readable file-like object) into b, a buffer.
    Raises an EOFError if the end-of-file is encountered before len(b) bytes can be read.
    """
    l = input.readinto( b )
    if l != len( b ):
        raise EOFError( "End of file reached prematurely!" )
    return b

#_rtn
def readTagName( i ):
    """
    Reads a named tag header.
    Returns a tuple, ( tagType, name ).
    tagType is the numerical ID of the tag directly following this header.
    name is the name of the tag.
    """
    tagType, length = _NT.unpack( read( i, 3 ) )
    if length < 0:
        raise OutOfBoundsError( length, 0, 32768 )
    return ( tagType, read( i, length ).decode() )

#_retn
def readExpectedTagName( i, expected ):
    """
    Reads a named tag header and asserts that the tagType we read matches the given tagType, expected.
    Raises an NBTFormatError if the tagTypes don't match, or if the length of the name is invalid.
    Returns the name of the tag.
    """
    tagType, length = _NT.unpack( read( i, 3 ) )
    if tagType != expected:
        raise WrongTagError( expected, tagType )
    if length < 0:
        raise OutOfBoundsError( length, 0, 32768 )
    return read( i, length ).decode()

#_wtn
def writeTagName( tagType, name, o ):
    """
    Writes a named tag header.
    tagType is the numerical ID of the tag directly following this header.
    name is the name of the tag.
    """
    b = name.encode()
    o.write( _NT.pack( tagType, len( b ) ) )
    o.write( b )

#_rb
def readByte( i ):
    """
    Reads a TAG_Byte payload.
    i is a file-like object to read bytes from.
    """
    return _B.unpack( read( i, 1 ) )[0]
#_wb
def writeByte( v, o ):
    """Writes a TAG_Byte payload."""
    o.write( _B.pack( v ) )

def readShort( i ):
    """Reads a TAG_Short payload."""
    return _S.unpack( read( i, 2 ) )[0]
#_ws
def writeShort( v, o ):
    """Writes a TAG_Short payload."""
    o.write( _S.pack( v ) )

#_ri
def readInt( i ):
    """Reads a TAG_Int payload."""
    return _I.unpack( read( i, 4 ) )[0]
#_wi
def writeInt( v, o ):
    """Writes a TAG_Int payload."""
    o.write( _I.pack( v ) )

#_rl
def readLong( i ):
    """Reads a TAG_Long payload."""
    return _L.unpack( read( i, 8 ) )[0]
#_wl
def writeLong( v, o ):
    """Writes a TAG_Long payload."""
    o.write( _L.pack( v ) )

#_rf
def readFloat( i ):
    """Reads a TAG_Float payload."""
    return _F.unpack( read( i, 4 ) )[0]
#_wf
def writeFloat( v, o ):
    """Writes a TAG_Float payload."""
    o.write( _F.pack( v ) )

#_rd
def readDouble( i ):
    """Reads a TAG_Double payload."""
    return _D.unpack( read( i, 8 ) )[0]
#_wd
def writeDouble( v, o ):
    """Writes a TAG_Double payload."""
    o.write( _D.pack( v ) )

#_wba
def writeByteArray( v, o ):
    """Writes a TAG_Byte_Array payload."""
    o.write( _I.pack( len( v ) ) )
    o.write( v )

#_rst
def readString( i ):
    """Reads a TAG_String payload."""
    l = _S.unpack( read( i, 2 ) )[0]
    if l < 0:
        raise OutOfBoundsError( l, 0, 32768 )
    return read( i, l ).decode()

#_wst
def writeString( v, o ):
    """Writes a TAG_String payload."""
    v = v.encode()
    length = len( v )
    #Reraise struct.error as OutOfBoundsError if v is too large.
    #Note: len(v) cannot be negative here
    try:
        o.write( _S.pack( length ) )
    except struct.error as e:
        raise OutOfBoundsError( length, 0, 32768 ) from e
    o.write( v )

#_rlh
def readTagListHeader( i ):
    """
    Reads a TAG_List header.

    Returns a tuple ( tagType, length ).
    tagType is the numerical ID of the tags contained in this list.
    length is how many tags are stored in the list.

    Raises UnknownTagTypeError if tagType is unknown.
    Raises OutOfBoundsError if the length of the list is negative.
    """
    p = _TL.unpack( read( i, 5 ) )
    assertValidTagType( p[0] )
    if p[1] < 0:
        raise OutOfBoundsError( 0, 2147483647 );
    return p

#_wlh
def writeTagListHeader( t, l, o ):
    """Writes a TAG_List header."""
    o.write( _TL.pack( t, l ) )

#_wlp
def writeTagList( t, v, o ):
    """Writes a TAG_List payload."""
    writeTagListHeader( t, len( v ), o )
    w = _WRITERS[ t ]
    for x in v:
        w( x, o )

#_wia
def writeIntArray( v, o ):
    """Writes a TAG_Int_Array payload."""
    o.write( _I.pack( len( v ) ) )
    writeInts( v, o )

#_rah
def readArrayHeader( i ):
    """
    Reads a TAG_Byte_Array or TAG_Int_Array header.
    Returns the length (in bytes and ints, respectively) of the array.
    If the length is negative, raises an OutOfBoundsError.
    """
    l = _I.unpack( read( i, 4 ) )[0]
    if l < 0:
        raise OutOfBoundsError( l, 0, 2147483647 )
    return l

#_rub
def readUnsignedByte( i ):
    """Reads an unsigned byte from i."""
    return read( i, 1 )[0] #note: no struct unpacking necessary; bytes() uses unsigned bytes

#_rui
def readUnsignedInt( i ):
    return _UI.unpack( read( i, 4 ) )[0]


#write* methods indexed by tagType
_WRITERS = (
    None,           #TAG_End
    writeByte,      #TAG_Byte
    writeShort,     #TAG_Short
    writeInt,       #TAG_Int
    writeLong,      #TAG_Long
    writeFloat,     #TAG_Float
    writeDouble,    #TAG_Double
    writeByteArray, #TAG_Byte_Array
    writeString,    #TAG_String
    None,           #TAG_List
    None,           #TAG_Compound
    writeIntArray   #TAG_Int_Array
)

#Compile platform-dependent functions during loadtime to avoid runtime lookup costs.

#We may use either "i" or "l" as an array datatype depending on the system.
#array assumes native-endianness in the data it reads to populate itself.
#Therefore, to properly read integers with big-endian ordering on little-endian systems
#we must reverse the endianness with byteswap().
exec(
"""
#_ris
def readInts( i, n ):
    \"\"\"
    Reads n signed, big-endian, 4-byte integers from i (a readable file-like object) into an array and returns it.
    \"\"\"
    a = array( "{SIGNED_INT_TYPE}" )
    a.fromfile( i, n )
    {BYTESWAP}
    return a

#_ruis
def readUnsignedInts( i, n ):
    \"\"\"
    Reads n unsigned, big-endian, 4-byte integers from i (a readable file-like object) into an array and returns it.
    \"\"\"
    a = array( "{UNSIGNED_INT_TYPE}" )
    a.fromfile( i, n )
    {BYTESWAP}
    return a
#_wis
def writeInts( a, o ):
    \"\"\"
    Writes signed, big-endian, 4-byte integers stored in the given array, a, to the given writable file-like object, o.
    \"\"\"
    {BYTESWAP}
    a.tofile( o )

#_cria
def copyReturnIntArray( a ):
    \"\"\"
    Takes an array of signed 4-byte integers.
    If this is a big-endian system, returns it.
    If this is a little-endian system, returns a copy of it.
    \"\"\"
    {COPY}
    return a
#_ccria
def convertCopyReturnIntArray( a ):
    \"\"\"
    Takes an iterable, a.
    If a is an array of signed 4-byte integers:
        ...and this is a big-endian system, returns the array.
        ...and this is a little-endian system, returns a copy of the array.
    Otherwise, converts a to a signed 4-byte integer array and returns the array.
    \"\"\"
    if isinstance( a, array ) and a.typecode == "{SIGNED_INT_TYPE}":
        {COPY}
        return a
    else:
        return array( "{SIGNED_INT_TYPE}", a )
#_bm
def byteswapMaybe( a ):
    \"\"\"
    Byteswap the given array if on a little-endian system. Otherwise, do nothing.
    This should be done after reading big-endian data to convert it to native-endian,
    or before writing native-endian data to convert it to big-endian.
    \"\"\"
    {BYTESWAP}

#_ctia
def convertToIntArray( v ):
    \"\"\"Converts the given iterable of ints, v, to an array of signed 4-byte integers if it isn't one already.\"\"\"
    if isinstance( v, array ) and v.typecode == "{SIGNED_INT_TYPE}":
        return v
    return array( "{SIGNED_INT_TYPE}", v )

def assertIntArray( a ):
    \"\"\"Asserts that a is an array of signed 4-byte integers. Raises TypeError if it is not.\"\"\"
    if type( a ) is not array:
        raise TypeError( "Wrong type for values: expected array(\\"{SIGNED_INT_TYPE}\\")" )
    if a.typecode != SIGNED_INT_TYPE:
        raise TypeError( "Wrong array typecode for values: expected \\"{SIGNED_INT_TYPE}\\", got \\"{{}}\\"".format( a.typecode ) )

def s4array( *args ):
    \"\"\"
    s4array([initializer]) -> array("{SIGNED_INT_TYPE}" [, initializer])

    Returns an array.array of signed 4-byte integers, optionally initialized with a given initializer.
    \"\"\"
    return array( "{SIGNED_INT_TYPE}", *args )

def u4array( *args ):
    \"\"\"
    u4array([initializer]) -> array("{UNSIGNED_INT_TYPE}" [, initializer])

    Returns an array.array of unsigned 4-byte integers, optionally initialized with a given initializer.
    \"\"\"
    return array( "{UNSIGNED_INT_TYPE}", *args )
""".format(
        SIGNED_INT_TYPE  = SIGNED_INT_TYPE,
        UNSIGNED_INT_TYPE= UNSIGNED_INT_TYPE,
        BYTESWAP         = "a.byteswap()" if sys.byteorder == "little" else "",
        COPY             = "a = array(\"" + SIGNED_INT_TYPE + "\", a)" if sys.byteorder == "little" else ""
    )
)