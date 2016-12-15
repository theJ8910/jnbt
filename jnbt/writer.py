from collections import deque

from .shared import (
    NBTFormatError, describeTag,
    TAG_END, TAG_BYTE, TAG_SHORT, TAG_INT, TAG_LONG, TAG_FLOAT, TAG_DOUBLE, TAG_BYTE_ARRAY, TAG_STRING, TAG_LIST, TAG_COMPOUND, TAG_INT_ARRAY,
    TAG_COUNT
)

#import with parentheses doesn't support renaming
from .shared import writeTagName       as _wtn, writeByte      as _wb,  writeShort    as _ws
from .shared import writeInt           as _wi,  writeLong      as _wl,  writeFloat    as _wf
from .shared import writeDouble        as _wd,  writeByteArray as _wba, writeString   as _wst
from .shared import writeTagListHeader as _wlh, writeTagList   as _wlp, writeIntArray as _wia
from .shared import writeInts          as _wis

from .shared import convertToIntArray  as _ctia

class _NBTWriterBase:
    """
    Base class for all other NBTWriter states.
    Implements methods to save/restore NBTWriter contexts and default NBTWriter methods.
    """
    def __init__( self, output ):
        """
        Constructor for NBTWriter.
        output is expected to be a writable file-like object.
        """
        self._o = output
        self._s = deque()
    
    def _push( self, c ):
        """Push the current context to the stack."""
        self._s.append( self.__class__ )
        self.__class__ = c

    def _pop( self ):
        """Pop the current context from the stack."""
        self.__class__ = self._s.pop()

    def __enter__( self ):
        return self

    def __exit__( self, exc_type, exc_value, traceback ):
        """Automatically closes the file-like object after exiting a with block."""
        self._o.close()

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
    def byte( self, name, value ):
        o = self._o
        _wtn( TAG_BYTE, name, o )
        _wb( value, o )
    def short( self, name, value ):
        o = self._o
        _wtn( TAG_SHORT, name, o )
        _ws( value, o )
    def int( self, name, value ):
        o = self._o
        _wtn( TAG_INT, name, o )
        _wi( value, o )
    def long( self, name, value ):
        o = self._o
        _wtn( TAG_LONG, name, o )
        _wl( value, o )
    def float( self, name, value ):
        o = self._o
        _wtn( TAG_FLOAT, name, o )
        _wf( value, o )
    def double( self, name, value ):
        o = self._o
        _wtn( TAG_DOUBLE, name, o )
        _wd( value, o )

    def bytearray( self, name, values ):
        o = self._o
        _wtn( TAG_BYTE_ARRAY, name, o )
        _wba( values, o )
    def startByteArray( self, name, length ):
        o = self._o
        _wtn( TAG_BYTE_ARRAY, name, o )
        _wi( length, o )
        self._push( _NBTWriterByteArray )

    def string( self, name, value ):
        o = self._o
        _wtn( TAG_STRING, name, o )
        _wst( value, o )

    def list( self, name, tagType, values ):
        o = self._o
        _wtn( TAG_LIST, name, o )
        _wlp( tagType, values, o )
    def startList( self, name, tagType, length ):
        o = self._o
        _wtn( TAG_LIST, name, o )
        _wlh( tagType, length, o )
        self._push( _NBTWriterList )

    def startCompound( self, name ):
        _wtn( TAG_COMPOUND, name, self._o )
        self._push( _NBTWriterCompound )

    def endCompound( self ):
        self._o.write( b"\0" )
        self._pop()

    def intarray( self, name, values ):
        values = _ctia( values )
        o = self._o
        _wtn( TAG_INT_ARRAY, name, o )
        _wia( values, o )
    def startIntArray( self, name, length ):
        o = self._o
        _wtn( TAG_INT_ARRAY, name, o )
        _wi( length, o )
        self._push( _NBTWriterIntArray )

class _NBTWriterList( _NBTWriterBase ):
    """
    Context while writing a TAG_List.
    Methods in this class do not take names as arguments.
    """
    def byte( self, value ):
        _wb( value, self._o )
    def short( self, value ):
        _ws( value, self._o )
    def int( self, value ):
        _wi( value, self._o )
    def long( self, value ):
        _wl( value, self._o )
    def float( self, value ):
        _wf( value, self._o )
    def double( self, value ):
        _wd( value, self._o )

    def bytearray( self, values ):
        _wba( values, self._o )

    def startByteArray( self, length ):
        _wi( length, self._o )
        self._push( _NBTWriterByteArray )
    def string( self, value ):
        _wst( value, self._o )
    
    def list( self, tagType, values ):
        _wlp( tagType, values, self._o )

    def startList( self, tagType, length ):
        _wlh( tagType, length, self._o )
        self._push( _NBTWriterList )
    def endList( self ):
        self._pop()

    def startCompound( self ):
        self._push( _NBTWriterCompound )

    def intarray( self, values ):
        _wia( _ctia( values ), self._o )

    def startIntArray( self, length ):
        _wi( length, self._o )
        self._push( _NBTWriterIntArray )

class _NBTWriterByteArray( _NBTWriterBase ):
    """Context while writing a TAG_Byte_Array."""
    def bytes( self, values ):
        self._o.write( values )
    def endByteArray( self ):
        self._pop()

class _NBTWriterIntArray( _NBTWriterBase ):
    """Context while writing a TAG_Int_Array."""
    def ints( self, values ):
        _wis( _ctia( values ), self._o )
    def endIntArray( self ):
        self._pop()

class _NBTWriterRootCompound( _NBTWriterCompound ):
    def end( self ):
        self._o.write( b"\0" )
        self._pop()
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
        _wtn( TAG_COMPOUND, name, self._o )
        self._push( _NBTWriterRootCompound )