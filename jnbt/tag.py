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
    NBTFormatError, WrongTagError, DuplicateNameError, OutOfBoundsError,
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

def _assertTagList( i, t ):
    """Assert that all entries in the given iterable, i, are TAG_* objects with the given tagType, t."""
    for v in i:
        if v.tagType != t:
            raise WrongTagError( t, v.tagType )

def _makeTagAppender( methodname, tagclass ):
    """Returns a method that creates tags of the given class and appends them to a TAG_List."""
    def appender( self, *args, **kwargs ):
        t = tagclass( *args, **kwargs )
        self.append( t )
        return t
    #Override appender.__name__ so help( tagclass ) shows this as "methodname( self, value)" instead of "methodname = appender( self, value )"
    appender.__name__ = methodname
    appender.__doc__ = \
        """
        Appends a new {} to the end of this TAG_List, passing the given arguments to the tag's constructor.
        Returns the new tag.
        """.format( tagclass.__name__ )
    return appender

def _makeTagSetter( methodname, tagclass ):
    """Returns a method that creates tags of the given class and adds or replaces a tag in a TAG_Compound with the given name."""
    def setter( self, *args, **kwargs ):
        #Note: We do this to force name to be a positional-only argument.
        #This allows us to pass a keyword argument called "name" to the constructor of whatever tag we're constructing.
        l = len( args )
        if l < 1:
            raise TypeError( "{} takes at least 1 positional argument but {:d} were given".format( methodname, l ) )
        name, *args = args
        t = tagclass( *args, **kwargs )
        self[name] = t
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

def _makeTagSetDefault( methodname, tagclass ):
    """
    Returns a TAG_Compound method that functions similarly to setdefault(), but for a specific type of tag.
    If the TAG_Compound contains an existing tag with that name and type, the function returns the existing tag.
    If the TAG_Compound contains an existing tag with that name of a different type, the function raises a WrongTagError.
    If the TAG_Compound does not contain an existing tag with that name, the function creates a new tag using the arguments provided to it.
    """
    def setdefault( self, *args, **kwargs ):
        l = len( args )
        if l < 1:
            raise TypeError( "{} takes at least 1 positional argument but {:d} were given".format( methodname, l ) )
        name, *args = args
        t = self.get( name )
        if t is None:
            t = tagclass( *args, **kwargs )
            self[name] = t
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

def _makeIntPrimitiveClass( classname, tt, vmin, vmax, r, w, **kwargs ):
    """Returns an NBT class that stores a primitive like byte, short, int, or long."""
    class _IntPrimitiveTag( _BaseIntTag ):
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

def _leafRget( self, index, default=None ):
    l = len( self )
    if index >= l or index < 0:
        return default
    return self[index]

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
        raise NotImplementedError()

    def _p( self, name, depth, maxdepth, maxlen, fn ):
        """
        Recursive step of print().
        name is a str inserted after the tag type indicating the name/index of that tag within its parent. For example:
            "" for no name
            "(5)" for a TAG_List entry with index 5
            "(\"example\")" for a TAG_Compound entry with name "example"
        depth is the current recursive depth.
        See help( tag.print  for a description of maxdepth, maxlen, and fn.
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
    This class implements a constructor that asserts that the given value is within these bounds, and throws a ValueError if they are not.
    """
    isNumeric  = True
    isIntegral = True

    value = property( int, doc="Read-only property. Converts this tag to an int." )

    __slots__ = ()

    #min > max here so if a subclass forgets to set these the constructor will always fail
    min =  1
    max = -1
    def __init__( self, value=None ):
        #Note: self is set by int's __new__ prior to calling __init__.
        #self is guaranteed to be an int, unlike value. The only reason the value parameter is here is so __init__ won't raise errors.
        if self < self.min or self > self.max:
            raise OutOfBoundsError( self, self.min, self.max )
    def __repr__( self ):
        return "{}({})".format( self.__class__.__name__, super().__repr__() )
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

    value = property( float, doc="Read-only property. Converts this tag to a float" )

    __slots__ = ()
    
    def __repr__( self ):
        return "TAG_Float({})".format( super().__repr__() )
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

    value = property( float, doc="Read-only property. Converts this tag to a float" )

    __slots__ = ()

    def __repr__( self ):
        return "TAG_Double({})".format( super().__repr__() )
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
        return "TAG_Byte_Array"+super().__repr__()[9:]
    rget = _leafRget
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
        return TAG_String( super().__add__( value ) )

    def __imul__( self, value ):
        #Note: str doesn't have __imul__
        return TAG_String( super().__imul__( value ) )

    def __repr__( self ):
        return "TAG_String({})".format( super().__repr__() )
    
    rget = _leafRget

    def _p( self, name, depth, maxdepth, maxlen, fn ):
        fn( "{}TAG_String{}: {:s}".format( "    "*depth, name, self ) )
    def _r( i ):
        return TAG_String( _rst( i ) )
    _w = _wst

class TAG_Int_Array( array, _BaseTag ):
    """
    Represents a TAG_Int_Array.
    TAG_Compound is a signed 4-byte int array subclass and generally works the same way and in the same places any other sequence (tuple, list, array etc) would.

    A TAG_Int_Array may not contain more than 2147483647 integers (8 GiB), however this is not enforced.
    Because this is an array of signed 4-byte integers, its values are limited to a signed 4-byte integer's range: [-2147483648, 2147483647].
    """
    tagType    = TAG_INT_ARRAY
    isIntArray = True
    isSequence = True

    __slots__ = ()

    #array implements __new__ rather than __init__
    def __new__( cls, *args, **kwargs ):
        return array.__new__( cls, SIGNED_INT_TYPE, *args, **kwargs )

    def __repr__( self ):
        if len( self ) > 0:
            return "TAG_Int_Array({})".format( super().__repr__()[11:-1] )
        else:
            return "TAG_Int_Array()"

    rget = _leafRget

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

    def __init__( self, tags=() ):
        """
        TAG_List constructor.
        Initializes a new list, optionally with a given sequence of tags.
        If tags is given, it must be a sequence (e.g. tuple, list) of TAG_* objects (e.g. TAG_Byte, TAG_Compound, etc). All tags must be of the same type.
        """
        #Determine tag type and ensure all given tags are of the same type
        if len( tags ) > 0:
            it = iter( tags )
            tt = next( it ).tagType
            _assertTagList( it, tt )
            self.listTagType = tt
            super().__init__( tags )
        #Empty list; use default tagType TAG_END
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

    def __iadd__( self, value ):
        if len( value ) == 0:
            return self
        
        #Ensure the tags we're adding match our list tagType.
        #If the list is empty, use the tag type from the first tag we're adding.
        tt = self.listTagType
        it = iter( value )
        if tt == TAG_END:
            tt = next( it ).tagType
        _assertTagList( it, tt )

        super().__iadd__( self, value )
                
        return self

    def __imul__( self, value ):
        if value == 0:
            self.listTagType = TAG_END
        super().__imul__( value )
        return self

    def __setitem__( self, key, value ):
        #Add, remove, or replace tags in a slice, e.g. list[1:4] = [1,2,3]
        if isinstance( key, slice ):
            ml = len( self )
            sl = len( range( *key.indices( ml ) ) )

            #Replacing the entire list's contents
            if ml == sl:
                #Replacing with a non-empty list; determine new list tagType.
                if len( value ) > 0:
                    it = iter( value )
                    tt = next( it ).tagType
                    _assertTagList( it, tt )
                    self.listTagType = tt
                #Replacing with an empty list; new list tagtype is default TAG_END.
                else:
                    self.listTagType = TAG_END
            #Replacing only some of the list contents; ensure that the replacement tags match the existing tags' tagType.
            else:
                _assertTagList( value, self.listTagType )
        #Replace an existing tag, e.g. list[1] = TAG_Int( 5 ). Ensure replacement tag has the same tagtype.
        elif value.tagType != self.listTagType:
            raise WrongTagError( self.listTagType, value.tagType )

        super().__setitem__( key, value )

    #TODO: need __getitem__ that returns TAG_List for slices

    def __delitem__( self, key ):
        super().__delitem__( key )
        if len( self ) == 0:
            self.listTagType = TAG_END

    def __repr__( self ):
        if len( self ) > 0:
            return "TAG_List({})".format( super().__repr__() )
        else:
            return "TAG_List()"

    def append( self, value ):
        tt = value.tagType
        if len( self ) == 0:
            self.listTagType = tt
        elif tt != self.listTagType:
            raise WrongTagError( self.listTagType, tt )
        super().append( value )

    def clear( self ):
        super().clear()
        self.listTagType = TAG_END

    def copy( self ):
        l = list.__new__( TAG_List )
        l.listTagType = self.listTagType
        super( TAG_List, l ).__iadd__( self )
        return l

    def extend( self, iterable ):
        self.__iadd__( self, iterable )

    def insert( self, index, value ):
        tt = value.tagType
        if len( self ) == 0:
            self.listTagType = tt
        elif tt != self.listTagType:
            raise WrongTagError( self.listTagType, tt )
        super().insert( index, obj )

    def pop( self, *args, **kwargs ):
        v = super().pop( *args, **kwargs )
        if len( self ) == 0:
            self.listTagType = TAG_END
        return v

    def remove( self, value ):
        super().remove( value )
        if len( self ) == 0:
            self.listTagType = TAG_END

    def rget( self, *args, default=None ):
        l = len( args )
        if l == 0:
            raise TypeError( "rget() takes at least 1 argument but 0 were given." )
        else:
            i = args[0]
            if i >= len( self ) or i < 0:
                return default
            
            if l == 1:
                return self[i]
            else:
                return self[i].rget( *args[1:], default=default )

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

        key must be a str. If it isn't, TypeError is raised.
        To insert or replace a tag with the given key, value must be a TAG_*. For example:
            comp["str"]  = jnbt.TAG_String( "Example!" )
            comp["byte"] = jnbt.TAG_Byte( 5 )

        For convenience, non TAG_* values may also be used, but only to change the value of an existing tag (due to possible ambiguity). If no such tag exists, NameError is raised.
        value must be something valid to pass to that tag's constructor. For example:
            comp["str"] = "Another example!"
            comp["byte"] = -5
        If you need to insert non-TAG_* values, use the tag setter methods instead (e.g. comp.byte(key, value) ).
        """
        #Ensure key is a str and value is a TAG_*
        if not isinstance( key, str ):
            raise TypeError( "Attempted to set a non-str key on TAG_Compound." )

        #If value is a non TAG_*, cast it to the type of the existing tag with the given name.
        if not hasattr( value, "tagType" ):
            #Raise NameError if there is no previous tag
            prev = self.get( key )
            if prev is None:
                raise NameError( "There is no tag with the name \"{}\" in this TAG_Compound.".format( key ) )
            value = prev.__class__( value )

        super().__setitem__( key, value )

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
        Returns the arugments provided to the write() method when called without arguments.
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
TAG_List.list          = _makeTagAppender( "list",     TAG_List     )
TAG_List.compound      = _makeTagAppender( "compound", TAG_Compound )
TAG_Compound.compound  = _makeTagSetter(   "compound", TAG_Compound )
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