"""
JNBT's tag module provides a DOM-style interface for reading, writing, building, modifying and inspecting NBT documents.

NBTDocument, several TAG_* classes and the read() function are implemented here.
"""
import gzip
import zlib
import itertools

from collections import OrderedDict
from array import array
from io import BytesIO, StringIO

from jnbt.shared import (
    NBTFormatError, WrongTagError, ConversionError, DuplicateNameError, OutOfBoundsError,
    INF,
    TAG_END, TAG_BYTE, TAG_SHORT, TAG_INT, TAG_LONG, TAG_FLOAT, TAG_DOUBLE, TAG_BYTE_ARRAY, TAG_STRING, TAG_LIST, TAG_COMPOUND, TAG_INT_ARRAY,
    TAG_NAMES, TAG_COUNT, SIGNED_INT_TYPE,

    writeTagName        as _wtn,  writeByte         as _wb,   writeShort          as _ws,
    writeInt            as _wi,   writeLong         as _wl,   writeFloat          as _wf,
    writeDouble         as _wd,   writeString       as _wst,  writeTagListHeader  as _wlh,

    writeByteArray      as _wba,  writeIntArray     as _wia,

    readTagName         as _rtn,  readByte          as _rb,   readShort           as _rs,
    readInt             as _ri,   readLong          as _rl,   readFloat           as _rf,
    readDouble          as _rd,   readString        as _rst,  readTagListHeader   as _rlh,

    readArrayHeader     as _rah,  read              as _r,    readExpectedTagName as _retn,

    tagListString       as _tls,
    assertValidTagType  as _avtt, byteswapMaybe     as _bm,   copyReturnIntArray  as _cria
)

#Base class methods called at various locations
_int_repr       = int.__repr__
_float_repr     = float.__repr__
_bytearray_repr = bytearray.__repr__
_str_add        = str.__add__
_str_mul        = str.__mul__
_str_repr       = str.__repr__
_array_new      = array.__new__
_array_repr     = array.__repr__
_list_append    = list.append
_list_clear     = list.clear
_list_insert    = list.insert
_list_pop       = list.pop
_list_remove    = list.remove
_list_init      = list.__init__
_list_new       = list.__new__
_list_setitem   = list.__setitem__
_list_delitem   = list.__delitem__
_list_iadd      = list.__iadd__
_list_imul      = list.__imul__
_list_repr      = list.__repr__
_od_setitem     = OrderedDict.__setitem__

#Generator that converts values in the given iterable, i, to a deduced tag class if necessary.
#The tag class is deduced by inspecting the first value of the iterable, f, in this order:
#   1. If f is a tag, f's class.
#   2. The tag class mapped to f's Python type.
#If the type cannot be deduced, raises a CoversionError.
#Additionally, the deduced tag class's constructor may also raise exceptions during conversion.
def _TL_init_v2t( i ):
    i = iter( i )
    #Note: Python 3.7 compatibility (see PEP 380).
    #Since Python 3.7, throwing StopIteration inside of a generator no longer silently terminates it; now it's converted to a RuntimeError instead.
    #Previously, next() would throw a StopIteration when i was empty which would terminate the generator.
    #But now to achieve the same effect, we need to explicitly catch StopIteration and return.
    try:
        f = next( i )
    except StopIteration:
        return

    #First value is a tag.
    if hasattr( f, "tagType" ):
        c = f.__class__
        yield f
    #First value isn't a tag. Try converting the value to its corresponding tag class.
    else:
        c = _TAGMAP.get( f.__class__ )
        #If this isn't possible, ConversionError is raised.
        if c is None:
            raise ConversionError( f )
        yield c( f )

    #Convert values in i to the chosen tag class.
    yield from _TL_v2t( i, c )

#Generator that converts values in the given iterable, i, to a deduced tag class if necessary.
#This variant involves t, the tagType of elements stored in a TAG_List, in the type deduction process.
#The tag class is deduced by inspecting the first value of the iterable, f, in this order:
#   1. If f is a tag, f's class.
#   2. If the TAG_List is non-empty, the class of tags stored by the list (e.g. TAG_Int).
#   3. The tag class mapped to f's Python type.
#If the type cannot be deduced, raises a CoversionError.
#Additionally, the deduced tag class's constructor may also raise exceptions during conversion.
def _TL_suggest_v2t( i, t ):
    i = iter( i )
    try:
        f = next( i )
    except StopIteration:
        return

    #First value is a tag.
    if hasattr( f, "tagType" ):
        c = f.__class__
        yield f
    #First value isn't a tag. Try converting the value to the type of tags currently stored by the list, t.
    elif t != TAG_END:
        c = _TAGCLASS[t]
        yield c(f)
    #The list is empty. Try converting the value to its corresponding tag class.
    else:
        c = _TAGMAP.get( f.__class__ )
        #If this isn't possible, ConversionError is raised.
        if c is None:
            raise ConversionError( f )
        yield c(f)

    #Convert values in i to the chosen tag class.
    yield from _TL_v2t( i, c )

#Generator that converts values in the given iterable, i, to the given tag class, c, if necessary.
#Conversions are performed by doing c( v ), where v is the value to be converted.
#Note: c's constructor may raise exceptions during conversion.
def _TL_v2t( i, c ):
    for v in i:
        yield v if v.__class__ == c else c( v )

#Returns a method that creates tags of the given class and appends them to a TAG_List.
def _makeTagAppender( methodname, tagclass ):
    tt = tagclass.tagType
    def appender( self, *args, **kwargs ):
        l = len( self )
        if l != 0 and tt != self.listTagType:
            raise WrongTagError( self.listTagType, tt )

        #Wait until after we've successfully constructed a tag and added it to the list before we change the list tag type
        t = tagclass( *args, **kwargs )
        _list_append( self, t )
        if l == 0:
            self.listTagType = tt
        return t
    #Override appender.__name__ so help( tagclass ) shows this as "methodname( self, value )" instead of "methodname = appender( self, value )"
    appender.__name__ = methodname
    appender.__doc__ = \
        """
        Appends a new {} to the end of this TAG_List, passing the given arguments to the tag's constructor.
        Returns the new tag.
        """.format( tagclass.__name__ )
    return appender

#Returns a method that creates tags of the given class and inserts them into a TAG_List.
def _makeTagInserter( methodname, tagclass ):
    tt = tagclass.tagType
    def inserter( self, *args, **kwargs ):
        l = len( args )
        if l < 1:
            raise TypeError( "{} takes at least 1 positional argument but {:d} were given".format( methodname, l ) )
        pos, *args = args

        l = len( self )
        if l != 0 and tt != self.listTagType:
            raise WrongTagError( self.listTagType, tt )

        t = tagclass( *args, **kwargs )
        _list_insert( self, pos, t )
        if l == 0:
            self.listTagType = tt
        return t
    inserter.__name__ = methodname
    inserter.__doc__ = \
        """
        {0:}(self, pos, *args, **kwargs) -> {1:}

        Inserts a new {1:} before the given index in this TAG_List, passing the given arguments to the tag's constructor.
        Returns the new tag.
        """.format( methodname, tagclass.__name__ )
    return inserter

#Returns a method that creates tags of the given class and adds or replaces a tag in a TAG_Compound with the given name.
def _makeTagSetter( methodname, tagclass ):
    def setter( self, *args, **kwargs ):
        #Note: We do this to force name to be a positional-only argument.
        #This allows us to pass a keyword argument called "name" to the constructor of whatever tag we're constructing.
        l = len( args )
        if l < 1:
            raise TypeError( "{} takes at least 1 positional argument but {:d} were given".format( methodname, l ) )
        name, *args = args

        if not isinstance( name, str ):
            raise TypeError( "Attempted to set a non-str key on TAG_Compound." )
        t = tagclass( *args, **kwargs )

        #Since we know what the tagtype is, avoid extra cost of calling TAG_Compound.__setitem__. Use base class OrderedDict.__setitem__ instead.
        _od_setitem( self, name, t )
        return t
    #Override setter.__name__ so help( tagclass ) shows this as "methodname( self, name, value)" instead of "methodname = setter( self, name, value )"
    setter.__name__ = methodname
    setter.__doc__ = \
        """
        {0:}(self, name, *args, **kwargs) -> {1:}

        Creates a new {1:}, passing the given arguments to the tag's constructor.
        Sets self[name] to the new tag, then returns the new tag.
        """.format( methodname, tagclass.__name__ )
    return setter

#Returns a TAG_Compound method that functions similarly to setdefault(), but for a specific type of tag.
def _makeTagSetDefault( methodname, tagclass ):
    def setdefault( self, *args, **kwargs ):
        l = len( args )
        if l < 1:
            raise TypeError( "{} takes at least 1 positional argument but {:d} were given".format( methodname, l ) )
        name, *args = args
        t = self.get( name )
        if t is None:
            if not isinstance( name, str ):
                raise TypeError( "Attempted to set a non-str key on TAG_Compound." )
            t = tagclass( *args, **kwargs )
            _od_setitem( self, name, t )
        elif t.tagType != tagclass.tagType:
            raise WrongTagError( tagclass.tagType, t.tagType );
        return t
    setdefault.__name__ = methodname
    setdefault.__doc__ = \
        """
        {0:}(self, name, *args, **kwargs) -> {1:}

        If a tag with the given name exists, returns the existing tag. Raises a WrongTagError if the existing tag isn't a {1:}.
        Otherwise, creates a new {1:}, passing the given arguments to the tag's constructor,
        sets self[name] to the new tag, then returns the new tag.
        """.format( methodname, tagclass.__name__ )
    return setdefault

#Returns an NBT class that stores a primitive like byte, short, int, or long.
def _makeIntPrimitiveClass( classname, tt, vmin, vmax, r, w, **kwargs ):
    class _IntPrimitiveTag( _BaseIntTag ):
        def __init__( self, value=None ):
            #Note: self is set by int's __new__ prior to calling __init__.
            #self is guaranteed to be an int, unlike value. The only reason the value parameter is here is so __init__ won't raise errors.
            if self < vmin or self > vmax:
                raise OutOfBoundsError( self, vmin, vmax )
        tagType = tt
        min = vmin
        max = vmax
        _w  = w
    def _r( i ):
        return _IntPrimitiveTag( r( i ) )
    _IntPrimitiveTag._r = _r
    for n,v in kwargs.items():
        setattr( _IntPrimitiveTag, n, v )

    _IntPrimitiveTag.__name__ = classname
    _IntPrimitiveTag.__doc__ = \
        """
        Represents a {0:}.
        {0:} is an int subclass and generally works the same way and in the same places as an int would.
        """.format( classname )
    return _IntPrimitiveTag

#rget() implementation for TAG_String, TAG_Byte_Array, and TAG_Int_Array.
#If more than 1 positional argument is provided to this function, default is returned.
#This is because these aforementioned tag types contain leaves (non-container values) and indexing a leaf is guaranteed to fail.
def _rget_leaf( self, *args, default=None ):
    l = len( args )
    if l == 0:
        raise TypeError( "rget() takes at least 1 argument but 0 were given." )
    elif l == 1:
        i = args[0]
        if not isinstance( i, int ) or i >= len(self) or i < 0:
            return default
        return self[i]
    else:
        return default

class _BaseTag:
    """Base class for all jnbt tag classes."""
    tagType     = -1

    #Simple means to check if a tag is a specific tagType
    isByte      = False
    isShort     = False
    isInt       = False
    isLong      = False
    isString    = False
    isFloat     = False
    isDouble    = False
    isByteArray = False
    isList      = False
    isCompound  = False
    isIntArray  = False

    #Simple means to check properties of the tag
    isNumeric   = False #True for TAG_Byte, TAG_Short, TAG_Int, TAG_Long, TAG_Float, TAG_Double
    isIntegral  = False #True for TAG_Byte, TAG_Short, TAG_Int, TAG_Long,
    isReal      = False #True for TAG_Float, TAG_Double
    isSequence  = False #True for TAG_String, TAG_Byte_Array, TAG_List, TAG_Int_Array

    __slots__ = ()

    def print( self, maxdepth=INF, maxlen=INF, fn=print ):
        """
        Recursively pretty-print the tag and its children.
        maxdepth is the maximum recursive depth to pretty-print.
            0 prints only this tag,
            1 prints this tag and its children,
            2 prints this tag, its children, and their children, and so on.
            math.inf is the default and prints the entire tree.
        maxlen is the maximum number of tags per TAG_List / TAG_Compound to print.
            For example, 64 would print only the first 64 entries in a list, and print a single ... for the remaining entries.
            math.inf is the default and prints every tag in a list / compound.
        fn is the callable that will be used to print a line of text, and defaults to the built-in print function.
            fn should take a str as its first argument.
            fn's return value (if any) is ignored.

        Examples:
        >>> ex.print()
        TAG_Compound( "example" ): 2 entries {
            TAG_String( "str" ): Example string
            TAG_List( "floats" ): 2 TAG_Floats [
                TAG_Float: 5.10
                TAG_Float: -1.2
            ]
        }

        >>> ex.print( 0 )
        TAG_Compound( "example" ): 2 entries { ... }

        >>> ex.print( 1 )
        TAG_Compound( "example" ): 2 entries {
           TAG_String( "str" ): Example string
           TAG_List( "floats" ): 2 TAG_Floats [ ... ]
        }
        """
        return self._p( "", 0, maxdepth, maxlen, fn )
    def sprint( self, maxdepth=INF, maxlen=INF ):
        """
        Recursively pretty-print the tag and its children to a string and return it.
        See help( tag.print ) for a description of maxdepth and maxlen and example usage.
        """
        with StringIO() as out:
            self.print( maxdepth, maxlen, lambda x: out.write( x + "\n" ) )
            return out.getvalue()

    def rget( self, *args, default=None ):
        """
        Recursive get.

        Gets the tag inside of this tag whose name or index is the first argument.
        If there is no such tag, returns default (which is None by default).
        If there is such a tag and len( args ) > 1, recursively calls rget() on the found tag with the remaining arguments.
        Otherwise, returns the found tag.

        Example:
            #Throws an exception if "FML" is not in leveldata:
            itemdata = leveldata["FML"]["ItemData"]

            #Does the same thing, but returns None instead of throwing an exception:
            itemdata = leveldata.rget( "FML", "ItemData" )
        """ 
        if len( args ) == 0:
            raise TypeError( "rget() takes at least 1 argument but 0 were given." )
        return default

    def _p( self, name, depth, maxdepth, maxlen, fn ):
        """
        Recursive step of print().
        name is a str inserted after the tag type indicating the name/index of that tag within its parent. For example:
            "" for no name
            "(5)" for a TAG_List entry with index 5
            "(\"example\")" for a TAG_Compound entry with name "example"
        depth is the current recursive depth.
        See help( tag.print ) for a description of maxdepth, maxlen, and fn.
        """
        raise NotImplementedError()
    def _w( self, o ):
        """Write this tag to the given writable file-like object, o."""
        raise NotImplementedError()
    def _r( i ):
        """Read this tag from the given readable file-like object, i."""
        raise NotImplementedError()

class _BaseIntTag( int, _BaseTag ):
    """
    Base class for all primitive integer tags (TAG_Byte, TAG_Short, TAG_Int, TAG_Long).
    Defines two static members min and max that represent the bounds (inclusive) of the range of values that can be represented by that primitive.
    This class implements a constructor that asserts that the given value is within these bounds, and raises an OutOfBoundsError if they are not.
    """
    isNumeric  = True
    isIntegral = True

    value = property( int, doc="Read-only property. Converts this tag to an int." )

    __slots__ = ()

    min =  1
    max = -1

    #TODO: __iadd__, __isub__, __imul__, __idiv__, etc.
    def __repr__( self ):
        return "{}({})".format( self.__class__.__name__, _int_repr( self ) )
    def _p( self, name, depth, maxdepth, maxlen, fn ):
        fn( "{}{}{}: {:d}".format( "    "*depth, self.__class__.__name__, name, self ) )

TAG_Byte  = _makeIntPrimitiveClass( "TAG_Byte",  TAG_BYTE,                  -128,                 127, _rb, _wb, isByte  = True )
TAG_Short = _makeIntPrimitiveClass( "TAG_Short", TAG_SHORT,               -32768,               32767, _rs, _ws, isShort = True )
TAG_Int   = _makeIntPrimitiveClass( "TAG_Int",   TAG_INT,            -2147483648,          2147483647, _ri, _wi, isInt   = True )
TAG_Long  = _makeIntPrimitiveClass( "TAG_Long",  TAG_LONG,  -9223372036854775808, 9223372036854775807, _rl, _wl, isLong  = True )

class TAG_Float( float, _BaseTag ):
    """
    Represents a TAG_Float.
    TAG_Float is a float subclass and generally works the same way and in the same places as a float would.
    """
    tagType   = TAG_FLOAT
    isFloat   = True
    isNumeric = True
    isReal    = True

    value = property( float, doc="Read-only property. Converts this tag to a float." )

    __slots__ = ()

    #TODO: __iadd__, __isub__, __imul__, __idiv__, etc.
    def __repr__( self ):
        return "TAG_Float({})".format( _float_repr( self ) )
    def _p( self, name, depth, maxdepth, maxlen, fn ):
        fn( "{}TAG_Float{}: {:.17g}".format( "    "*depth, name, self ) )
    def _r( i ):
        return TAG_Float( _rf( i ) )
    _w = _wf

class TAG_Double( float, _BaseTag ):
    """
    Represents a TAG_Double.
    TAG_Double is a float subclass and generally works the same way and in the same places as a float would.
    """
    tagType   = TAG_DOUBLE
    isDouble  = True
    isNumeric = True
    isReal    = True

    value = property( float, doc="Read-only property. Converts this tag to a float." )

    __slots__ = ()

    #TODO: __iadd__, __isub__, __imul__, __idiv__, etc.
    def __repr__( self ):
        return "TAG_Double({})".format( _float_repr( self ) )
    def _p( self, name, depth, maxdepth, maxlen, fn ):
        fn( "{}TAG_Double{}: {:.17g}".format( "    "*depth, name, self ) )
    def _r( i ):
        return TAG_Double( _rd( i ) )
    _w = _wd

class TAG_Byte_Array( bytearray, _BaseTag ):
    """
    Represents a TAG_Byte_Array.
    TAG_Byte_Array is a bytearray subclass and generally works the same way and in the same places a bytearray would.

    A TAG_Byte_Array may not contain more than 2147483647 bytes (2 GB), however this is not enforced.
    Values in a byte array are limited to the range [0,255].
    This is a Python convention; the NBT specification doesn't specify the format of bytes within a TAG_Byte_Array.
    Here are some conversion formulas to go from signed bytes [-128,127] to unsigned bytes [0,255] and vice-versa:
        ubyte = sbyte if sbyte >   0 else 256 + sbyte  #Signed byte to unsigned byte
        sbyte = ubyte if ubyte < 128 else ubyte - 256  #Unsigned byte to signed byte
    """
    tagType     = TAG_BYTE_ARRAY
    isByteArray = True
    isSequence  = True

    __slots__ = ()

    def __repr__( self ):
        return "TAG_Byte_Array"+_bytearray_repr( self )[9:]
    rget = _rget_leaf
    def _p( self, name, depth, maxdepth, maxlen, fn ):
        l = len( self )
        fn( "{}TAG_Byte_Array{}: [{:d} byte{}]".format( "    "*depth, name, l, "s" if l != 1 else "" ) )
    def _r( i ):
        l = _rah( i )
        return TAG_Byte_Array( _r( i, l ) )
    _w = _wba

class TAG_String( str, _BaseTag ):
    """
    Represents a TAG_String.
    TAG_String is a str subclass and generally works the same way and in the same places as a str would.

    A TAG_String can be no longer than 32767 bytes (when UTF-8 encoded).
    Note: If your string consists only of ASCII characters, the length of the string in characters (len(s)) is the same as its length in bytes (len(s.encode())).
    """
    tagType    = TAG_STRING
    isString   = True
    isSequence = True

    value = property( str, doc="Read-only property. Converts this tag to a str." )

    __slots__ = ()

    def __init__( self, *args, **kwargs ):
        #It sucks, but at the moment is the fastest correct way to get the encoded string length that Python has to offer:
        l = len( self.encode() )
        if l > 32767:
            raise OutOfBoundsError( l, 0, 32767 )

    #Note: TAG_String overrides methods that modify it in place to return TAG_String, but all other methods return str.
    def __iadd__( self, value ):
        #Note: str doesn't have __iadd__
        return TAG_String( _str_add( self, value ) )

    def __imul__( self, value ):
        #Note: str doesn't have __imul__
        return TAG_String( _str_mul( self, value ) )

    def __repr__( self ):
        return "TAG_String({})".format( _str_repr( self ) )

    rget = _rget_leaf

    def _p( self, name, depth, maxdepth, maxlen, fn ):
        fn( "{}TAG_String{}: {:s}".format( "    "*depth, name, self ) )
    def _r( i ):
        return TAG_String( _rst( i ) )
    _w = _wst

class TAG_Int_Array( array, _BaseTag ):
    """
    Represents a TAG_Int_Array.
    TAG_Int_Array is a signed 4-byte int array subclass and generally works the same way and in the same places any other sequence (tuple, list, array etc) would.

    A TAG_Int_Array may not contain more than 2147483647 integers (8 GiB), however this is not enforced.
    Because this is an array of signed 4-byte integers, its values are limited to a signed 4-byte integer's range: [-2147483648, 2147483647].
    """
    tagType    = TAG_INT_ARRAY
    isIntArray = True
    isSequence = True

    __slots__ = ()

    #array implements __new__ rather than __init__
    def __new__( cls, *args, **kwargs ):
        return _array_new( cls, SIGNED_INT_TYPE, *args, **kwargs )

    def __repr__( self ):
        if len( self ) > 0:
            return "TAG_Int_Array({})".format( _array_repr( self )[11:-1] )
        else:
            return "TAG_Int_Array()"

    rget = _rget_leaf

    def _p( self, name, depth, maxdepth, maxlen, fn ):
        l = len( self )
        fn( "{}TAG_Int_Array{}: [{:d} int{}]".format( "    "*depth, name, l, "s" if l != 1 else "" ) )
    def _r( i ):
        tag = TAG_Int_Array()
        l = _rah( i )
        if l > 0:
            tag.fromfile( i, l )
            _bm( tag )
        return tag
    def _w( self, o ):
        _wia( _cria( self ), o )

class TAG_List( list, _BaseTag ):
    """
    Represents a TAG_List.
    TAG_List is a list subclass and generally works the same way and in the same places as a list would.

    A TAG_List may not contain more than 2147483647 entries, however this is not enforced.
    """
    tagType    = TAG_LIST
    isList     = True
    isSequence = True

    __slots__ = "listTagType"

    def __init__( self, iterable=(), listTagType=None ):
        """
        TAG_List constructor.
        Initializes a new TAG_List, optionally with a given iterable.

        iterable is an optional parameter that determines the initial contents of the list. Defaults to an empty tuple.
            Like the name suggests, if given it should be something that can be iterated over (e.g. list, tuple, generator, etc).
            iterable's values can be tags (e.g. TAG_String( "Example" ) ) or non-tag values that can be converted to tags (e.g. "Example").
            All tags in a list must be of the same type. If necessary, iterable's values will be converted to the appropriate type of tag for the list.
        listTagType is an optional parameter specifying the type of tags stored by this list.
            This can be None (the default) or a tag class.
            If this is None, the list's tagType is deduced by inspecting the first value of the iterable (if any).
            Typically this parameter is only needed in cases where you're making lists of int/float based tags:
                jnbt.TAG_Byte
                jnbt.TAG_Short
                jnbt.TAG_Int
                jnbt.TAG_Long
                jnbt.TAG_Float
                jnbt.TAG_Double

        Examples:
            #List of strings
            ls = jnbt.TAG_List( ( "Check", "out", "these", "strings!" ) )

            #Numbers 0-9 as a list of TAG_Int
            ls = jnbt.TAG_List( range(10), jnbt.TAG_Int )

            #List of coordinates as TAG_Double
            ls = jnbt.TAG_List( ( 100.21, 60, -500.852 ), jnbt.TAG_Double )
        """
        if listTagType is None:
            _list_init( self, _TL_init_v2t( iterable ) )
        else:
            _avtt( listTagType.tagType )
            _list_init( self, _TL_v2t( iterable, listTagType ) )

        if len( self ) > 0:
            self.listTagType = self[0].tagType
        else:
            self.listTagType = TAG_END

    byte      = _makeTagAppender( "byte",      TAG_Byte       )
    short     = _makeTagAppender( "short",     TAG_Short      )
    int       = _makeTagAppender( "int",       TAG_Int        )
    long      = _makeTagAppender( "long",      TAG_Long       )
    float     = _makeTagAppender( "float",     TAG_Float      )
    double    = _makeTagAppender( "double",    TAG_Double     )
    bytearray = _makeTagAppender( "bytearray", TAG_Byte_Array )
    string    = _makeTagAppender( "string",    TAG_String     )
    #list     = (outside of class)
    #compound = (outside of class)
    intarray  = _makeTagAppender( "intarray",  TAG_Int_Array  )

    insert_byte      = _makeTagInserter( "insert_byte",      TAG_Byte       )
    insert_short     = _makeTagInserter( "insert_short",     TAG_Short      )
    insert_int       = _makeTagInserter( "insert_int",       TAG_Int        )
    insert_long      = _makeTagInserter( "insert_long",      TAG_Long       )
    insert_float     = _makeTagInserter( "insert_float",     TAG_Float      )
    insert_double    = _makeTagInserter( "insert_double",    TAG_Double     )
    insert_bytearray = _makeTagInserter( "insert_bytearray", TAG_Byte_Array )
    insert_string    = _makeTagInserter( "insert_string",    TAG_String     )
    #insert_list     = (outside of class)
    #insert_compound = (outside of class)
    insert_intarray  = _makeTagInserter( "insert_intarray",  TAG_Int_Array  )

    def __iadd__( self, value ):
        if len( self ) > 0:
            _list_iadd( self, _TL_v2t( value, _TAGCLASS[ self.listTagType ] ) )
        else:
            _list_iadd( self, _TL_init_v2t( value ) )
            if len( self ) > 0:
                self.listTagType = self[0].tagType

        return self

    def __imul__( self, value ):
        if value == 0:
            self.listTagType = TAG_END
        _list_imul( self, value )
        return self

    def __setitem__( self, key, value ):
        """
        Handle self[key] = value.

        If key is an int, value should be a single value. For example:
            list[0] = jnbt.TAG_String( "Example" )
            list[1] = "Another Example"
        If key is a slice, value should be an iterable (list, tuple, generator, etc) of values. For example:
            list[:]   = ( TAG_Int(5), 6, 7, 8 )
            list[2:4] = ()
        If key isn't an int or a slice, TypeError is raised.

        If they aren't already, differing tags and non-tag values will be converted to a singular tag class.
        If only part of the list is being replaced:
            Given values will be converted to the type of tags currently stored by the list.
        If the entire list is being replaced:
            Given values will be converted to the tag type of the first/only value.
            If the first value isn't a tag, values will be converted to the type of tags currently stored by the list.
            If the list is empty, then values are converted to the tag class mapped to the first/only value's Python type.
            If all of these attempts fail, a ConversionError is raised.
        If a conversion is performed, the tag constructor may raise an exception.
        """
        ml = len( self )
        #Add, remove, or replace tags in a slice, e.g. list[1:4] = (1,2,3)
        if isinstance( key, slice ):
            sl = len( range( *key.indices( ml ) ) )

            #Replace the entire list's contents. This may possibly change the list tagType.
            if ml == sl:
                _list_setitem( self, key, _TL_suggest_v2t( value, self.listTagType ) )
                self.listTagType = self[0].tagType if len( self ) > 0 else TAG_END
            #Replace some of the list's contents, values must be converted to existing tagType if different
            else:
                _list_setitem( self, key, _TL_v2t( value, _TAGCLASS[ self.listTagType ] ) )
        #Replace a single tag...
        elif isinstance( key, int ):
            #Replace an existing tag with another tag, e.g. list[1] = TAG_Int( 5 )
            #Change the list tagType if we're replacing our only tag.
            if ml == 1:
                t = getattr( value, "tagType", None )
                if t is None:
                    value = _TAGCLASS[self.listTagType]( value )
                else:
                    self.listTagType = t
            #If we have several tags, the replacement tag needs to match the tagType of the rest of the tags.
            #Attempt a conversion if value is a tag of a different type or a non-tag.
            elif ml > 0:
                ltt = self.listTagType
                if getattr( value, "tagType", None ) != ltt:
                    value = _TAGCLASS[ ltt ]( value )
            _list_setitem( self, key, value )
        #Invalid key, let list.__setitem__ throw a TypeError
        else:
            _list_setitem( self, key, None )

    #TODO: need __getitem__ that returns TAG_List for slices

    def __delitem__( self, key ):
        _list_delitem( self, key )
        if len( self ) == 0:
            self.listTagType = TAG_END

    def __repr__( self ):
        if len( self ) > 0:
            return "TAG_List({})".format( _list_repr( self ) )
        else:
            return "TAG_List()"

    def append( self, value ):
        _list_append( self, self._a( value ) )

    def clear( self ):
        _list_clear( self )
        self.listTagType = TAG_END

    def copy( self ):
        l = _list_new( TAG_List )
        l.listTagType = self.listTagType
        super( TAG_List, l ).__iadd__( self )
        return l

    def extend( self, iterable ):
        self.__iadd__( iterable )

    def insert( self, index, value ):
        _list_insert( self, index, self._a( value ) )

    def pop( self, *args, **kwargs ):
        v = _list_pop( self, *args, **kwargs )
        if len( self ) == 0:
            self.listTagType = TAG_END
        return v

    def remove( self, value ):
        _list_remove( self, value )
        if len( self ) == 0:
            self.listTagType = TAG_END

    def rget( self, *args, default=None ):
        l = len( args )
        if l == 0:
            raise TypeError( "rget() takes at least 1 argument but 0 were given." )
        else:
            i = args[0]
            if not isinstance( i, int ) or i >= len( self ) or i < 0:
                return default

            if l == 1:
                return self[i]
            else:
                return self[i].rget( *args[1:], default=default )

    #Called by append() and insert().
    #Changes the list tagType and/or converts the value to a TAG_* of the appropriate type if necessary.
    #Returns the (possibly converted) value.
    def _a( self, value ):
        ltt = self.listTagType
        t = getattr( value, "tagType", None )
        #List is empty
        if ltt == TAG_END:
            #value isn't a tag
            if t is None:
                t = _TAGMAP.get( value.__class__ )
                #No mapped conversion for this type
                if t is None:
                    raise ConversionError( value )
                value = t( value )
                t = t.tagType
            #Update the list tagType
            self.listTagType = t
        #List is non-empty, value isn't a tag or is a tag of the wrong type
        elif t != ltt:
            value = _TAGCLASS[ltt]( value )
        return value

    def _p( self, name, depth, maxdepth, maxlen, fn ):
        l = len( self )
        indent = "    "*depth
        line = "{}TAG_List{}: {} [".format( indent, name, _tls( l, self.listTagType ) )

        if l == 0:
            fn( line + "]" )
        elif depth < maxdepth and maxlen != 0:
            fn( line )

            depth = depth + 1
            i = 0
            if maxlen < l:
                for t in itertools.islice( self, maxlen ):
                    t._p( "({:d})".format( i ), depth, maxdepth, maxlen, fn )
                    i += 1
                fn( indent + "    ..." )
            else:
                for t in self:
                    t._p( "({:d})".format( i ), depth, maxdepth, maxlen, fn )
                    i += 1

            fn( indent + "]" )
        else:
            fn( line + " ... ]" )

    def _r( i ):
        t, l = _rlh( i )
        c = _TAGCLASS[ t ]

        tag = TAG_List()
        tag.listTagType = t
        a = super( TAG_List, tag ).append

        for _ in range( l ):
            a( c._r( i ) )

        return tag

    def _w( self, o ):
        _wlh( self.listTagType, len( self ), o )
        for t in self:
            t._w( o )


class TAG_Compound( OrderedDict, _BaseTag ):
    """
    Represents a TAG_Compound.
    TAG_Compound is an OrderedDict subclass and generally works the same way and in the same places any other mapping (dict, etc.) would, with one major exception:
    The keys and values of a TAG_Compound are restricted to str and TAG_* objects (e.g. TAG_Byte, TAG_Compound, etc) respectively.

    A TAG_Compound can be initialized in the same ways a normal dict / OrderedDict can:
        * TAG_Compound( { k: v, ... } ):  From another mapping (e.g. dict, OrderedDict, etc).
        * TAG_Compound( [ (k,v), ... ] ): With an iterable of pairs (where pair = an iterable containing a key and value, in that order)
        * TAG_Compound( name=v, ... ):    With keyword arguments. Can be combined with either of the previous two choices.
    Note: Both k and name are used as keys in the resulting map, but the difference is that k is an expression, while name is a string literal.
    """
    tagType = TAG_COMPOUND
    isCompound = True

    __slots__ = ()

    def __setitem__( self, key, value ):
        """
        Handle self[key] = value.

        Note: Consider using the tag setter methods instead. They're unambiguous and often more compact. For example:
            comp.string( "str", "Example!" )
            comp.byte( "byte", 5 )

        key must be a str. If it isn't, TypeError is raised.

        value can be a tag or a non-tag.
        If a non-tag is provided, it is converted to a tag according to the following rules:
            If a tag with the given name already exists, value is converted to the existing tag's type.
            If no such tag exists, value is converted to the tag class mapped to the value's Python type.
            If both of these attempts fail, a ConversionError is raised.
        If a conversion is performed, the tag constructor may raise an exception.

        Examples:
            comp["str"]  = jnbt.TAG_String( "Example!" )
            comp["byte"] = jnbt.TAG_Byte( 5 )

            comp["str"] = "Another example!"
            comp["byte"] = -5
        """
        #Ensure key is a str and value is a tag
        if not isinstance( key, str ):
            raise TypeError( "Attempted to set a non-str key on TAG_Compound." )

        #If value is a non tag, attempt to convert it to a tag.
        if not hasattr( value, "tagType" ):
            #If there is an existing tag with the given name, convert the value to the existing tag's type.
            temp = self.get( key )
            if temp is None:
                #Otherwise, see if we can determine the tag class from the python type.
                temp = _TAGMAP.get( value.__class__ )
                if temp is None:
                    raise ConversionError( value )
                value = temp( value )
            else:
                value = temp.__class__( value )

        _od_setitem( self, key, value )

    #Note: No __repr__ override necessary, OrderedDict inserts the correct classname for us

    byte      = _makeTagSetter( "byte",      TAG_Byte       )
    short     = _makeTagSetter( "short",     TAG_Short      )
    int       = _makeTagSetter( "int",       TAG_Int        )
    long      = _makeTagSetter( "long",      TAG_Long       )
    float     = _makeTagSetter( "float",     TAG_Float      )
    double    = _makeTagSetter( "double",    TAG_Double     )
    bytearray = _makeTagSetter( "bytearray", TAG_Byte_Array )
    string    = _makeTagSetter( "string",    TAG_String     )
    list      = _makeTagSetter( "list",      TAG_List       )
    #compound = (outside of class)
    intarray  = _makeTagSetter( "intarray",  TAG_Int_Array  )

    setdefault_byte      = _makeTagSetDefault( "setdefault_byte",      TAG_Byte       )
    setdefault_short     = _makeTagSetDefault( "setdefault_short",     TAG_Short      )
    setdefault_int       = _makeTagSetDefault( "setdefault_int",       TAG_Int        )
    setdefault_long      = _makeTagSetDefault( "setdefault_long",      TAG_Long       )
    setdefault_float     = _makeTagSetDefault( "setdefault_float",     TAG_Float      )
    setdefault_double    = _makeTagSetDefault( "setdefault_double",    TAG_Double     )
    setdefault_bytearray = _makeTagSetDefault( "setdefault_bytearray", TAG_Byte_Array )
    setdefault_string    = _makeTagSetDefault( "setdefault_string",    TAG_String     )
    setdefault_list      = _makeTagSetDefault( "setdefault_list",      TAG_List       )
    #setdefault_compound = (outside of class)
    setdefault_intarray  = _makeTagSetDefault( "setdefault_intarray",  TAG_Int_Array  )

    def copy( self ):
        return TAG_Compound( self )

    def rget( self, *args, default=None ):
        l = len( args )
        if l == 0:
            raise TypeError( "rget() takes at least 1 argument but 0 were given." )
        elif l == 1:
            return self.get( args[0], default )
        else:
            tag = self.get( args[0] )
            if tag is None:
                return default
            return tag.rget( *args[1:], default=default )

    def _p( self, name, depth, maxdepth, maxlen, fn ):
        l = len( self )
        indent = "    "*depth
        line = "{}TAG_Compound{}: {} {{".format( indent, name, "{:d} entr{}".format( l, "ies" if l != 1 else "y" ) )
        if l == 0:
            fn( line + "}" )
        elif depth < maxdepth and maxlen != 0:
            fn( line )
            depth = depth + 1
            if maxlen < l:
                for n,t in itertools.islice( self.items(), maxlen ):
                    t._p( "(\"{}\")".format( n ), depth, maxdepth, maxlen, fn )
                fn( indent + "    ..." )
            else:
                for n,t in self.items():
                    t._p( "(\"{}\")".format( n ), depth, maxdepth, maxlen, fn )
            fn( indent + "}" )
        else:
            fn( line + " ... }" )

    def _r( i ):
        tag = TAG_Compound()
        si = super( TAG_Compound, tag ).__setitem__

        tt = _rb( i )
        while tt != TAG_END:
            #Check that the tagType is valid.
            _avtt( tt )

            #Now that we know the tag isn't TAG_END, read the name and check that there isn't already a tag with that name
            name = _rst( i )
            if name in tag:
                raise DuplicateNameError( name )

            si( name, _TAGCLASS[tt]._r( i ) )
            tt = _rb( i )

        return tag

    def _w( self, o ):
        for n,t in self.items():
            _wtn( t.tagType, n, o )
            t._w( o )
        o.write( b"\0" )

class NBTDocument( TAG_Compound ):
    """
    Represents an NBT document.

    An NBTDocument is a named TAG_Compound that serves as the root tag of the NBT tree.
    Although NBTDocuments can be named, more often than not the name is simply the empty string, "".
    """
    __slots__ = ()

    def __init__( self, *args, **kwargs ):
        """
        NBTDocument()             -> new empty NBTDocument with name ""
        NBTDocument(name)         -> new empty NBTDocument with the given name
        NBTDocument(<init>)       -> new NBTDocument with name "", initialized with the given initializers
        NBTDocument(name, <init>) -> new NBTDocument with the given name, initialized with the given initializers

        NBTDocument constructor.

        name is expected to be a str.
        <init> is a single positional argument and/or several named arguments that determine the NBTDocument's initial contents.
        See help( jnbt.TAG_Compound ) for more information on valid initializers.
        """
        l = len( args )
        if l == 0:
            self.name = ""
            super().__init__( **kwargs )
        elif l == 2:
            self.name = args[0]
            super().__init__( args[1], **kwargs )
        elif l == 1:
            arg = args[0]
            if isinstance( arg, str ):
                self.name = arg
                super().__init__( **kwargs )
            else:
                self.name = ""
                super().__init__( arg, **kwargs )
        else:
            raise TypeError( "__init__() takes at most 2 positional arguments but {:d} were given".format( l ) )

        self.target      = None
        self.compression = None

    def setWriteArguments( self, target, compression ):
        """
        Sets the arguments provided to the write() method when called without arguments.
        For documents returned by jnbt.read(), these arguments are set automatically.
        """
        self.target      = target
        self.compression = compression

    def getWriteArguments( self ):
        """
        Returns the arguments provided to the write() method when called without arguments.
        Returns (None, None) if these argments are not set.
        """
        return self.target, self.compression

    def print( self, maxdepth=INF, maxlen=INF, fn=print ):
        self._p( "(\"{}\")".format( self.name ), 0, maxdepth, maxlen, fn )

    def _writeImpl( self, target, compression="gzip" ):
        """
        Implementation of NBTDocument#write() that takes a fixed number of parameters.
        See help( NBTDocument.write ) for further documentation.
        """
        is_zlib = False
        if isinstance( target, str ):
            if compression is None:
                file = open( target, "wb" )
            elif compression == "gzip":
                file = gzip.open( target, "wb" )
            #For zlib compressed files we write raw NBT to a BytesIO, then later zlib compress this data to the target file.
            elif compression == "zlib":
                file = BytesIO()
                is_zlib = True
            else:
                raise ValueError( "Unknown compression type \"{}\".".format( compression ) )

            with file:
                self._w( file )
                if is_zlib:
                    with open( target, "wb" ) as hardfile:
                        hardfile.write( zlib.compress( file.getbuffer() ) )
        else:
            self._w( target )

    def write( self, *args, **kwargs ):
        """
        document.write()
        document.write( target, compression="gzip" )

        Writes an NBTDocument to a file.
        When called without arguments, writes changes to the document back to the file it was read from.
        Specifically, calling write() without arguments is equivalent to calling write() with self.target and self.compression substituted for the target and compression parameters, respectively.

        target can be the path of the file to write to (as a str), or a writable file-like object.
        compression is an optional parameter that can be None, "gzip", or "zlib". Defaults to "gzip".
            If target is a writable file-like object, this parameter is ignored; bytes will be written to the file as if compression were None.
        """
        la = len( args ) + len( kwargs )
        if la == 0:
            if self.target is None:
                raise TypeError( "Unknown write target. Call doc.write() with arguments, or provide the write target in jnbt.read() or doc.setWriteArguments()." )
            return self._writeImpl( self.target, self.compression )
        else:
            return self._writeImpl( *args, **kwargs )

    def _r( i ):
        name = _retn( i, TAG_COMPOUND )
        tag = TAG_Compound._r( i )
        tag.name = name
        tag.__class__ = NBTDocument
        return tag

    def _w( self, o ):
        _wtn( TAG_COMPOUND, self.name, o )
        super()._w( o )

    def __repr__( self ):
        parts = []
        name, other = self.name, super().__repr__()[12:-1]
        if len( name ) > 0:
            parts.append( "'{}'".format( name ) )
        if len( other ) > 0:
            parts.append( other )
        return "NBTDocument({})".format( ", ".join( parts ) )

#Note: Have to set create these methods here because the target classes don't exist until this point:
TAG_List.list                    = _makeTagAppender(   "list",                TAG_List     )
TAG_List.compound                = _makeTagAppender(   "compound",            TAG_Compound )
TAG_List.insert_list             = _makeTagInserter(   "insert_list",         TAG_List     )
TAG_List.insert_compound         = _makeTagInserter(   "insert_compound",     TAG_Compound )
TAG_Compound.compound            = _makeTagSetter(     "compound",            TAG_Compound )
TAG_Compound.setdefault_compound = _makeTagSetDefault( "setdefault_compound", TAG_Compound )

#Tuple of tag classes indexed by tagType.
#Do _TAGCLASS[tagType] to get the class for the tag with that tagType.
_TAGCLASS = (
    None,           #TAG_END
    TAG_Byte,       #TAG_BYTE
    TAG_Short,      #TAG_SHORT
    TAG_Int,        #TAG_INT
    TAG_Long,       #TAG_LONG
    TAG_Float,      #TAG_FLOAT
    TAG_Double,     #TAG_DOUBLE
    TAG_Byte_Array, #TAG_BYTE_ARRAY
    TAG_String,     #TAG_STRING
    TAG_List,       #TAG_LIST
    TAG_Compound,   #TAG_COMPOUND
    TAG_Int_Array   #TAG_INT_ARRAY
)

#Mapping of python types -> tag classes.
#NBT doesn't have a boolean type. Instead, a TAG_Byte with a value of 0 for False and 1 for True is usually used instead.
#Therefore, we map the python bool type to TAG_Byte.
#Tag type deduction is not possible for the int and float python types because it would be ambiguous;
#int could be deduced as TAG_Byte, TAG_Short, TAG_Int, or TAG_Long,
#and float could be deduced as TAG_Float or TAG_Double.
_TAGMAP = {
    bool:        TAG_Byte,
    bytes:       TAG_Byte_Array,
    bytearray:   TAG_Byte_Array,
    memoryview:  TAG_Byte_Array,
    str:         TAG_String,
    list:        TAG_List,
    tuple:       TAG_List,
    dict:        TAG_Compound,
    OrderedDict: TAG_Compound,
    array:       TAG_Int_Array
}

def read( source, compression="gzip", target=None, create=False ):
    """
    Parses an NBT file from source and returns an NBTDocument.
    Returns None if source is empty.

    source can be the path of the file to read from (as a str), or a readable file-like object containing uncompressed NBT data.
    compression is an optional parameter that can be None, "gzip", or "zlib". Defaults to "gzip".
    target is an optional parameter that determines the file that will be written to when calling doc.write() on the returned document without arguments.
        This parameter can be None, the path of a file to write to (as a str), or a writable file-like object. Defaults to None.
        If target is None, jnbt can determine the write target automatically from the given source, but only if source is a str or an object with a "name" attribute, such as a file.
        Otherwise, the write target will be set to None.
    create is an optional parameter that determines what happens if source is a str and the file at that path cannot be found. If source is not a str, this parameter is ignored.
        If create is True, returns a new blank NBTDocument(). Otherwise, raises FileNotFoundError.
        Defaults to False.
    """
    if isinstance( source, str ):
        if target is None:
            target = source
        try:
            if compression is None:
                file = open( source, "rb" )
            elif compression == "gzip":
                file = gzip.open( source, "rb" )
            elif compression == "zlib":
                with open( source, "rb" ) as hardfile:
                    file = BytesIO( zlib.decompress( hardfile.read() ) )
            else:
                raise ValueError( "Unknown compression type \"{}\".".format( compression ) )
            with file:
                doc = NBTDocument._r( file )
        except FileNotFoundError:
            if create is True:
                doc = NBTDocument()
            else:
                raise
        doc.setWriteArguments( target, compression )
        return doc
    else:
        doc = NBTDocument._r( source )
        if target is None:
            target = getattr( source, "name", None )
        doc.setWriteArguments( target, None )
        return doc