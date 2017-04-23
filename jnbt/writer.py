import gzip
import zlib

from collections import deque
from io import BytesIO
from types import MethodType

from jnbt.shared import (
    NBTFormatError, describeTag,
    WrongTagError, DuplicateNameError,
    TAG_END, TAG_BYTE, TAG_SHORT, TAG_INT, TAG_LONG, TAG_FLOAT, TAG_DOUBLE, TAG_BYTE_ARRAY, TAG_STRING, TAG_LIST, TAG_COMPOUND, TAG_INT_ARRAY,
    TAG_COUNT,

    writeTagName       as _wtn, writeByte      as _wb,  writeShort    as _ws,
    writeInt           as _wi,  writeLong      as _wl,  writeFloat    as _wf,
    writeDouble        as _wd,  writeByteArray as _wba, writeString   as _wst,
    writeTagListHeader as _wlh, writeTagList   as _wlp, writeIntArray as _wia,
    writeInts          as _wis,

    convertCopyReturnIntArray as _ccria,
    assertValidTagType as _avtt,
)

def writer( target, compression="gzip" ):
    """
    Returns an NBTWriter that writes to the file indicated by target.

    target can be the path of the file to write to (as a str), or a writable file-like object.
    compression is an optional parameter that can be None, "gzip", or "zlib". Defaults to "gzip".
        If target is a writable file-like object, this parameter is ignored; bytes will be written to the file as if compression were None.
    """
    if isinstance( target, str ):
        close = None
        if compression is None:
            file = open( target, "wb" )
        elif compression == "gzip":
            file = gzip.open( target, "wb" )
        #For zlib compressed files we write raw NBT to a BytesIO, then later zlib compress this data to the target file.
        elif compression == "zlib":
            file = BytesIO()
            def _close_finalize_zlib( self ):
                with file, open( target, "wb" ) as hardfile:
                    hardfile.write( zlib.compress( file.getbuffer() ) )
            close = _close_finalize_zlib
        else:
            raise ValueError( "Unknown compression type \"{}\".".format( compression ) )
        w = NBTWriter( file )
        if close is not None:
            w.close = MethodType( close, w )
    else:
        w = NBTWriter( target )
    return w

class _NBTWriterBase:
    """
    Base class for all other NBTWriter states.
    Implements a context stack and default NBTWriter methods.
    """
    def __init__( self, output ):
        """
        Constructor for NBTWriter.
        output is expected to be a writable file-like object.
        """
        self._o = output
        self._s = deque()
        #A boolean indicating if the root TAG_Compound has been started yet.
        self._r = False

        #For TAG_List, TAG_Byte_Array, and TAG_Int_Array, the number of tags/bytes/ints written so far.
        self._a = None
        #For TAG_List, TAG_Byte_Array, and TAG_Int_Array, the number of tags/bytes/ints expected to be written.
        self._b = None
        #For TAG_List, the tag type of the list.
        #For TAG_Compound, the set of names that have been written so far.
        self._c = None
    def close( self ):
        self._o.close()
    def _pushC( self ):
        """Push a new TAG_Compound context to the stack."""
        self._s.append( ( self.__class__, self._c ) )
        self.__class__ = _NBTWriterCompound
        self._c = set()
    def _pushL( self, tagType, length ):
        """Push a new TAG_List context to the stack."""
        self._s.append( ( self.__class__, self._a, self._b, self._c ) )
        self.__class__ = _NBTWriterList
        self._a = 0
        self._b = length
        self._c = tagType
    def _pushI( self, b ):
        """Push a new TAG_Int_Array context to the stack."""
        self._s.append( ( self.__class__, self._a, self._b ) )
        self.__class__ = _NBTWriterIntArray
        self._a = 0
        self._b = b
    def _pushB( self, b ):
        """Push a new TAG_Byte_Array context to the stack."""
        self._s.append( ( self.__class__, self._a, self._b ) )
        self.__class__ = _NBTWriterByteArray
        self._a = 0
        self._b = b

    def __enter__( self ):
        return self

    def __exit__( self, exc_type, exc_value, traceback ):
        """Automatically closes the writable file-like object after exiting a with block."""
        self.close()

    #Default implementations for NBTWriter methods.
    #These raise NBTFormatErrors to indicate that calling these methods in the current context is inappropriate.
    def start( self, *args, **kwargs ):
        """
        Start the root TAG_Compound.

        After calling .start() and writing tags, the .end() method must be called to finish writing the root TAG_Compound.
        """
        raise NBTFormatError( "The root TAG_Compound cannot be created here." )
    def end( self, *args, **kwargs ):
        """
        Finish writing the root TAG_Compound.

        This method may only be called in tandem with a prior call to .start().
        """
        raise NBTFormatError( "Attempted to end the root TAG_Compound, but the current tag is not the root TAG_Compound!" )
    """NBTWriter instances become _NBTWriterCompound while writing a (non-root) TAG_Compound."""
    def byte( self, *args, **kwargs ):
        """
        Write a TAG_Byte with the given value.

        value is expected to be an int in the range [-128, 127]. 
        """
        raise NBTFormatError( "A TAG_Byte cannot be created here." )
    def short( self, *args, **kwargs ):
        """
        Write a TAG_Short with the given value.

        value is expected to be an int in the range [-32768, 32767].
        """
        raise NBTFormatError( "A TAG_Short cannot be created here." )
    def int( self, *args, **kwargs ):
        """
        Write a TAG_Int with the given value.

        value is expected to be a number in the range [-2147483648, 2147483647].
        """
        raise NBTFormatError( "A TAG_Int cannot be created here." )
    def long( self, *args, **kwargs ):
        """
        Write a TAG_Long with the given value.

        value is expected to be a number in the range [-9223372036854775808, 9223372036854775807].
        """
        raise NBTFormatError( "A TAG_Long cannot be created here." )
    def float( self, *args, **kwargs ):
        """
        Write a TAG_Float with the given value.

        value is expected to be a float.
        """
        raise NBTFormatError( "A TAG_Float cannot be created here." )
    def double( self, *args, **kwargs ):
        """
        Write a TAG_Double with the given value.

        value is expected to be a float.
        """
        raise NBTFormatError( "A TAG_Double cannot be created here." )

    def bytearray( self, *args, **kwargs ):
        """
        Write a TAG_Byte_Array consisting of the given bytes-like object, values.

        values is expected to be a bytes-like object containing integers in the range [0,255].
        len(values) is expected to be in the range [0, 2147483647].
        """
        raise NBTFormatError( "A TAG_Byte_Array cannot be created here." )
    def startByteArray( self, *args, **kwargs ):
        """
        Start writing a TAG_Byte_Array that will contain length elements.

        length is expected to be an int in the range [0, 2147483647].

        After calling the .startByteArray( length ) method, a total of length bytes must be written via calls to the .bytes() method.
        Finally, the .endByteArray() method must be called to finish writing the byte array.

        Example:
            writer.startByteArray( "mybytes", 16 )
            writer.bytes( b"\\x00\\x01\\x02\\x03\\x04\\x05\\x06\\x07" )
            writer.bytes( b"\\x08\\x09\\x0A\\x0B\\x0C\\x0D\\x0E\\x0F" )
            writer.endByteArray()
        """
        raise NBTFormatError( "A TAG_Byte_Array cannot be created here." )
    def bytes( self, *args, **kwargs ):
        """
        Write the bytes-like object values to the current TAG_Byte_Array.

        This method may only be called between calls to the .startByteArray() and .endByteArray() methods.
        """
        raise NBTFormatError( "Attempted to write bytes, but current tag is not a TAG_Byte_Array." )
    def endByteArray( self, *args, **kwargs ):
        """
        Finish writing a TAG_Byte_Array.
        This method may only be called in tandem with a prior call to .startByteArray().
        """
        raise NBTFormatError( "Attempted to end a TAG_Byte_Array, but the current tag is not a TAG_Byte_Array." )

    def string( self, *args, **kwargs ):
        """
        Write a TAG_String.

        value is expected to be a UTF-8 str.
        len( value ) is expected to be in the range [0, 32767].
        """
        raise NBTFormatError( "A TAG_String cannot be created here." )

    def list( self, *args, **kwargs ):
        """
        Write a TAG_List containing the values stored in values.

        tagType is expected to be a valid numerical tag type (e.g. jnbt.TAG_FLOAT, jnbt.TAG_BYTE_ARRAY) identifying the tags that will be written to the list.
        len(values) is expected to be in the range [0, 2147483647].
        All values in values are expected to be the python type corresponding to tagType (e.g. if tagType is jnbt.TAG_DOUBLE, we expect each value to be a float).
        If values is empty, tagType should preferably be jnbt.TAG_END.
        Otherwise, tagType can be any type except for jnbt.TAG_LIST or jnbt.TAG_COMPOUND.
        Automatically writing these types would require inferring the types of the tags they store, which is not possible in our implementation because several
        tags map to the same python type (e.g. TAG_Float, TAG_Double -> float).
        In other words, it would be ambiguous. To write a list containing these types, use startList()/endList() instead.
        """
        raise NBTFormatError( "A TAG_List cannot be created here." )
    def startList( self, *args, **kwargs ):
        """
        Start writing a TAG_List.

        tagType is expected to be a valid numerical tag type (e.g. jnbt.TAG_FLOAT, jnbt.TAG_BYTE_ARRAY) identifying the tags that will be written to the list.
        length is expected to be an int in the range [0, 2147483647].

        After calling the .startList( length ) method, a total of length tags must be written via calls to the appropriate methods (e.g. .float() for jnbt.TAG_FLOAT,
        .start/endCompound() for jnbt.TAG_COMPOUND, etc).
        Finally, the .endList() method must be called to finish writing the int array.

        Example:
            writer.startList( "mylist", jnbt.TAG_COMPOUND, 3 )
            
            writer.startCompound()
            writer.string( "name", "Sheep" )
            writer.int( "health", 10 )
            writer.endCompound()
            
            writer.startCompound()
            writer.string( "name", "Villager" )
            writer.int( "health", 20 )
            writer.endCompound()

            writer.startCompound()
            writer.string( "name", "Zombie" )
            writer.int( "health", 30 )
            writer.endCompound()

            writer.endList()
        """
        raise NBTFormatError( "A TAG_List cannot be created here." )
    def endList( self, *args, **kwargs ):
        """
        Finish writing a TAG_List.

        This method may only be called in tandem with a prior call to .startList().
        """
        raise NBTFormatError( "Attempted to end a TAG_List, but the current tag is not a TAG_List." )

    def startCompound( self, *args, **kwargs ):
        """
        Start writing a TAG_Compound.

        After calling .startCompound() and writing tags, the .endCompound() method must be called to finish writing the TAG_Compound.
        """
        raise NBTFormatError( "A TAG_Compound cannot be created here." )
    def endCompound( self, *args, **kwargs ):
        """
        Finish writing a TAG_Compound.

        This method may only be called in tandem with a prior call to .startCompound().
        """
        raise NBTFormatError( "Attempted to end a TAG_Compound, but the current tag is not a TAG_Compound." )

    def intarray( self, *args, **kwargs ):
        """
        Write a TAG_Int_Array consisting of the given values.

        values is expected to be a sequence (tuple, list, etc) of integers in the range [-2147483648, 2147483647].
        """
        raise NBTFormatError( "A TAG_Int_Array cannot be created here." )
    def startIntArray( self, *args, **kwargs ):
        """
        Start writing a TAG_Int_Array that will contain length elements.

        length is expected to be an int in the range [0, 2147483647].

        After calling the .startIntArray( length ) method, a total of length integers must be written via calls to the .ints() method.
        Finally, the .endIntArray() method must be called to finish writing the int array.

        Example:
            writer.startIntArray( "my_ints", 16 )
            writer.ints( ( 0, 1,  2,  3,  4,  5,  6,  7 ) )
            writer.ints( ( 8, 9, 10, 11, 12, 13, 14, 15 ) )
            writer.endIntArray()
        """
        raise NBTFormatError( "A TAG_Int_Array cannot be created here." )
    def ints( self, *args, **kwargs ):
        """
        Write the given values to the current TAG_Int_Array.

        values is expected to be a sequence (tuple, list, etc) of integers in the range [-2147483648, 2147483647].

        This method may only be called between calls to the .startIntArray() and .endIntArray() methods.
        """
        raise NBTFormatError( "Attempted to write ints, but the current tag is not a TAG_Int_Array." )
    def endIntArray( self, *args, **kwargs ):
        """
        Finish writing a TAG_Int_Array.

        This method may only be called in tandem with a prior call to .startIntArray().
        """
        raise NBTFormatError( "Attempted to end a TAG_Int_Array, but the current tag is not a TAG_Int_Array." )

class _NBTWriterCompound( _NBTWriterBase ):
    """
    Context while writing a (non-root) TAG_Compound.
    Methods in this class take a name as a first argument.
    """
    def _ac( self, name ):
        """
        Asserts that a tag with this name has not already been written.
        If so, raises a DuplicateNameError.
        Otherwise, adds the name to the set of written names.
        """
        c = self._c
        if name in c:
            raise DuplicateNameError( name )
        c.add( name )
    def byte( self, name, value ):
        self._ac( name )
        o = self._o
        _wtn( TAG_BYTE, name, o )
        _wb( value, o )
    def short( self, name, value ):
        self._ac( name )
        o = self._o
        _wtn( TAG_SHORT, name, o )
        _ws( value, o )
    def int( self, name, value ):
        self._ac( name )
        o = self._o
        _wtn( TAG_INT, name, o )
        _wi( value, o )
    def long( self, name, value ):
        self._ac( name )
        o = self._o
        _wtn( TAG_LONG, name, o )
        _wl( value, o )
    def float( self, name, value ):
        self._ac( name )
        o = self._o
        _wtn( TAG_FLOAT, name, o )
        _wf( value, o )
    def double( self, name, value ):
        self._ac( name )
        o = self._o
        _wtn( TAG_DOUBLE, name, o )
        _wd( value, o )

    def bytearray( self, name, values ):
        self._ac( name )
        o = self._o
        _wtn( TAG_BYTE_ARRAY, name, o )
        _wba( values, o )
    def startByteArray( self, name, length ):
        if length < 0 or length > 2147483647:
            raise OutOfBoundsError( length, 0, 2147483647 )
        self._ac( name )
        o = self._o
        _wtn( TAG_BYTE_ARRAY, name, o )
        _wi( length, o )
        self._pushB( length )

    def string( self, name, value ):
        self._ac( name )
        o = self._o
        _wtn( TAG_STRING, name, o )
        _wst( value, o )

    def list( self, name, tagType, values ):
        _avtt( tagType )
        self._ac( name )
        o = self._o
        _wtn( TAG_LIST, name, o )
        _wlp( tagType, values, o )
    def startList( self, name, tagType, length ):
        if length < 0 or length > 2147483647:
            raise OutOfBoundsError( length, 0, 2147483647 )
        _avtt( tagType )
        self._ac( name )
        o = self._o
        _wtn( TAG_LIST, name, o )
        _wlh( tagType, length, o )
        self._pushL( tagType, length )

    def startCompound( self, name ):
        self._ac( name )
        _wtn( TAG_COMPOUND, name, self._o )
        self._pushC()

    def endCompound( self ):
        self._o.write( b"\0" )
        self.__class__, self._c = self._s.pop()

    def intarray( self, name, values ):
        self._ac( name )
        values = _ccria( values )
        o = self._o
        _wtn( TAG_INT_ARRAY, name, o )
        _wia( values, o )

    def startIntArray( self, name, length ):
        if length < 0 or length > 2147483647:
            raise OutOfBoundsError( length, 0, 2147483647 )
        self._ac( name )
        o = self._o
        _wtn( TAG_INT_ARRAY, name, o )
        _wi( length, o )
        self._pushI( length )

class _NBTWriterList( _NBTWriterBase ):
    """
    Context while writing a TAG_List.
    Methods in this class do not take names as arguments.
    """
    def _al( self, tagType ):
        """
        Asserts that the tagType of the element matches the list's tagType.
        Adds 1 to the count of tags written so far and asserts that the list length hasn't been exceeded.
        """
        c = self._c
        if tagType != c:
            raise WrongTagError( c, tagType )
        a = self._a + 1
        b = self._b
        if a > b:
            raise NBTFormatError( "More than {:d} tags were written.".format( b ) )
        self._a = a
    def byte( self, value ):
        self._al( TAG_BYTE )
        _wb( value, self._o )
    def short( self, value ):
        self._al( TAG_SHORT )
        _ws( value, self._o )
    def int( self, value ):
        self._al( TAG_INT )
        _wi( value, self._o )
    def long( self, value ):
        self._al( TAG_LONG )
        _wl( value, self._o )
    def float( self, value ):
        self._al( TAG_FLOAT )
        _wf( value, self._o )
    def double( self, value ):
        self._al( TAG_DOUBLE )
        _wd( value, self._o )

    def bytearray( self, values ):
        self._al( TAG_BYTE_ARRAY )
        _wba( values, self._o )

    def startByteArray( self, length ):
        if length < 0 or length > 2147483647:
            raise OutOfBoundsError( length, 0, 2147483647 )
        self._al( TAG_BYTE_ARRAY )
        _wi( length, self._o )
        self._pushB( length )
    def string( self, value ):
        self._al( TAG_STRING )
        _wst( value, self._o )
    
    def list( self, tagType, values ):
        _avtt( tagType )
        self._al( TAG_LIST )
        _wlp( tagType, values, self._o )

    def startList( self, tagType, length ):
        if length < 0 or length > 2147483647:
            raise OutOfBoundsError( length, 0, 2147483647 )
        _avtt( tagType )
        self._al( TAG_LIST )
        _wlh( tagType, length, self._o )
        self._pushL( tagType, length )
    def endList( self ):
        a = self._a
        b = self._b
        if a != b:
            raise NBTFormatError( "Expected {:d} tags, but only {:d} tags were written.".format( b, a ) )
        self.__class__, self._a, self._b, self._c = self._s.pop()

    def startCompound( self ):
        self._al( TAG_COMPOUND )
        self._pushC()

    def intarray( self, values ):
        self._al( TAG_INT_ARRAY )
        _wia( _ccria( values ), self._o )

    def startIntArray( self, length ):
        if length < 0 or length > 2147483647:
            raise OutOfBoundsError( length, 0, 2147483647 )
        self._al( TAG_INT_ARRAY )
        _wi( length, self._o )
        self._pushI( length )

class _NBTWriterByteArray( _NBTWriterBase ):
    """Context while writing a TAG_Byte_Array."""
    def bytes( self, values ):
        a = self._a + len( values )
        b = self._b
        if a > b:
            raise NBTFormatError( "More than {:d} bytes were written.".format( b ) )
        self._a = a
        self._o.write( values )
    def endByteArray( self ):
        a = self._a
        b = self._b
        if a != b:
            raise NBTFormatError( "Expected {:d} bytes, but only {:d} bytes were written.".format( b, a ) )
        self.__class__, self._a, self._b = self._s.pop()

class _NBTWriterIntArray( _NBTWriterBase ):
    """Context while writing a TAG_Int_Array."""
    def ints( self, values ):
        a = self._a + len( values )
        b = self._b
        if a > b:
            raise NBTFormatError( "More than {:d} ints were written.".format( b ) )
        self._a = a
        _wis( _ccria( values ), self._o )

    def endIntArray( self ):
        a = self._a
        b = self._b
        if a != b:
            raise NBTFormatError( "Expected {:d} ints, but only {:d} ints were written.".format( b, a ) )
        self.__class__, self._a, self._b = self._s.pop()

class _NBTWriterRootCompound( _NBTWriterCompound ):
    """Context while writing the root TAG_Compound."""
    def end( self ):
        self._o.write( b"\0" )
        self.__class__ = NBTWriter
    def endCompound( self ):
        raise NBTFormatError( "You must call .end() instead of .endCompound() to end the root TAG_Compound." )

class NBTWriter( _NBTWriterBase ):
    """
    A class for writing NBT data to a writable file-like object.
    You can write NBT files with this class by calling methods of this class in the appropriate order.
    Example:
        with jnbt.NBTWriter( gzip.open( "somefile.nbt", "wb" ) ) as writer:
            writer.start()
            
            writer.byte( "my_byte", 10 )
            
            writer.startList( "my_list", jnbt.TAG_STRING, 4 )
            writer.string( "This" )
            writer.string( "is" )
            writer.string( "an" )
            writer.string( "example." )
            writer.endList()

            writer.startCompound( "my_compound" )
            writer.string( "name", "Sheep" )
            writer.long( "id", 1234567890 )
            writer.endCompound()

            writer.end()
    """
    def start( self, name="" ):
        if self._r is True:
            raise NBTFormatError( "The root TAG_Compound has already been created." )
        self._r = True
        _wtn( TAG_COMPOUND, name, self._o )
        self.__class__ = _NBTWriterRootCompound
        self._c = set()
