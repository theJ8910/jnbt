from .writer import _NBTWriterBase

from .shared import (
    NBTFormatError, WrongTagError, DuplicateNameError, describeTag,
    TAG_END, TAG_BYTE, TAG_SHORT, TAG_INT, TAG_LONG, TAG_FLOAT, TAG_DOUBLE, TAG_BYTE_ARRAY, TAG_STRING, TAG_LIST, TAG_COMPOUND, TAG_INT_ARRAY,
    TAG_COUNT
)

#import with parentheses doesn't support renaming
from .shared import writeTagName       as _wtn, writeByte      as _wb,  writeShort    as _ws
from .shared import writeInt           as _wi,  writeLong      as _wl,  writeFloat    as _wf
from .shared import writeDouble        as _wd,  writeByteArray as _wba, writeString   as _wst
from .shared import writeTagListHeader as _wlh, writeTagList   as _wlp, writeIntArray as _wia
from .shared import writeInts          as _wis

from .shared import convertToIntArray  as _ctia, assertValidTagType as _avtt

class _SafeNBTWriterBase( _NBTWriterBase ):
    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )
        #A boolean indicating if the root TAG_Compound has been started yet.
        self._r = False

        #For TAG_List, TAG_Byte_Array, and TAG_Int_Array, the number of tags/bytes/ints written so far.
        self._a = None
        #For TAG_List, TAG_Byte_Array, and TAG_Int_Array, the number of tags/bytes/ints expected to be written.
        self._b = None
        #For TAG_List, the tag type of the list.
        #For TAG_Compound, the set of names that have been written so far.
        self._c = None
    def _pushC( self ):
        """Push a new TAG_Compound context to the stack."""
        self._s.append( ( self.__class__, self._c ) ) 
        self.__class__ = _SafeNBTWriterCompound
        self._c = set()
    def _pushL( self, tagType, length ):
        """Push a new TAG_List context to the stack."""
        self._s.append( ( self.__class__, self._a, self._b, self._c ) )
        self.__class__ = _SafeNBTWriterList
        self._a = 0
        self._b = length
        self._c = tagType
    def _pushI( self, b ):
        """Push a new TAG_Int_Array context to the stack."""
        self._s.append( ( self.__class__, self._a, self._b ) )
        self.__class__ = _SafeNBTWriterIntArray
        self._a = 0
        self._b = b
    def _pushB( self, b ):
        """Push a new TAG_Byte_Array context to the stack."""
        self._s.append( ( self.__class__, self._a, self._b ) )
        self.__class__ = _SafeNBTWriterByteArray
        self._a = 0
        self._b = b

    def __enter__( self ):
        return self

    def __exit__( self, exc_type, exc_value, traceback ):
        """Automatically closes the writable file-like object after exiting a with block."""
        self._o.close()

class _SafeNBTWriterCompound( _SafeNBTWriterBase ):
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
        if length < 0:
            raise NBTFormatError( "TAG_Byte_Array has negative length!" )
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
        if tagType < 0 or tagType >= TAG_COUNT:
            raise NBTFormatError( "TAG_List given invalid tag type." )
        self._ac( name )
        o = self._o
        _wtn( TAG_LIST, name, o )
        _wlp( tagType, values, o )
    def startList( self, name, tagType, length ):
        if length < 0:
            raise NBTFormatError( "TAG_List has negative length!" )
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
        values = _ctia( values )
        o = self._o
        _wtn( TAG_INT_ARRAY, name, o )
        _wia( values, o )

    def startIntArray( self, name, length ):
        if length < 0:
            raise NBTFormatError( "TAG_Int_Array has negative length!" )
        self._ac( name )
        o = self._o
        _wtn( TAG_INT_ARRAY, name, o )
        _wi( length, o )
        self._pushI( length )

class _SafeNBTWriterList( _SafeNBTWriterBase ):
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
        if length < 0:
            raise NBTFormatError( "TAG_Byte_Array has negative length!" )
        self._al( TAG_BYTE_ARRAY )
        _wi( length, self._o )
        self._pushB( length )
    def string( self, value ):
        self._al( TAG_STRING )
        _wst( value, self._o )
    
    def list( self, tagType, values ):
        if tagType < 0 or tagType >= TAG_COUNT:
            raise NBTFormatError( "TAG_List given invalid tag type." )
        self._al( TAG_LIST )
        _wlp( tagType, values, self._o )

    def startList( self, tagType, length ):
        if length < 0:
            raise NBTFormatError( "TAG_List has negative length!" )
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
        _wia( _ctia( values ), self._o )

    def startIntArray( self, length ):
        if length < 0:
            raise NBTFormatError( "TAG_Int_Array has negative length!" )
        self._al( TAG_INT_ARRAY )
        _wi( length, self._o )
        self._pushI( length )
    

class _SafeNBTWriterByteArray( _SafeNBTWriterBase ):
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

class _SafeNBTWriterIntArray( _SafeNBTWriterBase ):
    def ints( self, values ):
        a = self._a + len( values )
        b = self._b
        if a > b:
            raise NBTFormatError( "More than {:d} ints were written.".format( b ) )
        self._a = a
        
        _wis( _ctia( values ), self._o )

    def endIntArray( self ):
        a = self._a
        b = self._b
        if a != b:
            raise NBTFormatError( "Expected {:d} ints, but only {:d} ints were written.".format( b, a ) )
        self.__class__, self._a, self._b = self._s.pop()

class _SafeNBTWriterRootCompound( _SafeNBTWriterCompound ):
    def end( self ):
        self._o.write( b"\0" )
        self.__class__ = SafeNBTWriter
    def endCompound( self ):
        raise NBTFormatError( "You must call .end() instead of .endCompound() to end the root TAG_Compound." )

class SafeNBTWriter( _SafeNBTWriterBase ):
    """
    This is a "safe" version of NBTWriter that performs sanity checks and throws NBTFormatError exceptions when writing NBT incorrectly.
    May be somewhat slower than NBTWriter, but can be useful during development and debugging.
    """
    def start( self, name="" ):
        if self._r is True:
            raise NBTFormatError( "The root TAG_Compound has already been created." )
        self._r = True

        _wtn( TAG_COMPOUND, name, self._o )
        
        self.__class__ = _SafeNBTWriterRootCompound
        self._c = set()