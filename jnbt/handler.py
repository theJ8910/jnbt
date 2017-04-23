from jnbt.shared import TAG_NAMES, tagNameString as _tns, tagListString as _tls
from jnbt.parse  import _StopParsingNBT

class NBTHandler:
    """
    Base NBT Event Handler.
    As an NBT file is parsed, functions in the given handler are called.
    This class provides default method implementations and documentation for handlers that inherit from it.
    """
    def name( self, tagType, name ):
        """
        Called when a named tag header is read.
        tagType is the numerical ID of the tag directly following this header.
        name is the name assigned to the tag.
        """
        pass
    def start( self ):
        """
        Called before we start parsing the root TAG_Compound of the NBT file, but after the name of the root has been parsed
        so that the handler can know in advance what the name of the root element is.
        """
        pass
    def end( self ):
        """
        Called after we have finished parsing the root TAG_Compound.
        This should be the last method to be called on a handler if the entire file was successfully parsed.
        """
        pass
    def byte( self, value ):
        """
        Called when a TAG_Byte is parsed.

        value will be an int in the range [-128, 127].
        """
        pass
    def short( self, value ):
        """
        Called when a TAG_Short is parsed.

        value will be an int in the range [-32768, 32767].
        """
        pass
    def int( self, value ):
        """
        Called when a TAG_Int is parsed.

        value will be an int in the range [-2147483648, 2147483647].
        """
        pass
    def long( self, value ):
        """
        Called when a TAG_Long is parsed.

        value will be an int in the range [-9223372036854775808, 9223372036854775807]
        """
        pass
    def float( self, value ):
        """
        Called when a TAG_Float is parsed.

        value will be a float.
        """
        pass
    def double( self, value ):
        """
        Called when a TAG_Double is parsed.

        value will be a float.
        """
        pass
    def startByteArray( self, length ):
        """
        Called when the start of a TAG_Byte_Array is parsed.

        length indicates how many bytes are stored in the current TAG_Byte_Array. It will be an int in the range [0, 2147483647].
        """
        pass
    def bytes( self, values ):
        """
        Called when the parser reads one or more bytes from the current TAG_Byte_Array.

        values will be a bytes() containing integers in the range [0,255].
        Note: The NBT specification considers the bytes stored in a TAG_Byte_Array to be of "unspecified format",
        meaning that the format of the data varies on a case-by-case basis (e.g. you may be intended to interpret it as an array of signed bytes, chunk data, etc).
        """
        pass
    def endByteArray( self ):
        """
        Called when the end of a TAG_Byte_Array is parsed.
        """
        pass
    def string( self, value ):
        """
        Called when a TAG_String is parsed.

        value will be a UTF-8 str.
        len( value ) will be in the range [0, 32767].
        """
        pass
    def startList( self, tagType, length ):
        """
        Called when the start of a TAG_List is parsed.

        tagType is the numerical tag type (e.g. jnbt.TAG_FLOAT) of tags stored in this TAG_List.
        length indicates how many tags are stored by this list. It will be an int in the range [0, 2147483647].
        """
        pass
    def endList( self ):
        """
        Called when the end of a TAG_List is parsed.
        """
        pass
    def startCompound( self ):
        """
        Called when the start of a TAG_Compound is parsed.

        A TAG_Compound stores named entries of varying types.
        """
        pass
    def endCompound( self ):
        """
        Called when the end of a TAG_Compound is parsed.
        """
        pass
    def startIntArray( self, length ):
        """
        Called when the start of a TAG_Int_Array is parsed.

        length indicates how many integers are stored in the current TAG_Int_Array. It will be an int in the range [0, 2147483647].
        """
        pass
    def ints( self, values ):
        """
        Called when the parser reads one or more integers from the current TAG_Int_Array.

        values will be an array of signed 4-byte integers.

        Depending on how many integers are in the TAG_Int_Array and how the parser is configured, the parser may call this method several times until all the integers in the array are read.
        """
        pass
    def endIntArray( self ):
        """
        Called when the end of a TAG_Int_Array is parsed.
        """
        pass

    def stop( self ):
        """Call this method if you want to stop parsing prematurely."""
        raise _StopParsingNBT()

class PrintNBTHandler( NBTHandler ):
    """
    NBT Event Handler that prints a tree of NBT tags as they are fed through it.
    """
    def __init__( self ):
        self._n  = None  #Name for current entry
        self._i  = 0     #Current indent level
        self._is = ""    #Current indent string (cached for efficiency)
    def setIndent( self, indent ):
        """Sets the indent level (where 0 is no indent, 1 is four spaces of indent, 2 is eight, and so on)."""
        self._i  = indent
        self._is = "    " * indent
    def name( self, tagType, name ):
        self._n = name
    def byte( self, value ):
        print( "{}TAG_Byte{}: {:d}".format( self._is, _tns( self._n ), value ) )
    def short( self, value ):
        print( "{}TAG_Short{}: {:d}".format( self._is, _tns( self._n ), value ) )
    def int( self, value ):
        print( "{}TAG_Int{}: {:d}".format( self._is, _tns( self._n ), value ) )
    def long( self, value ):
        print( "{}TAG_Long{}: {:d}".format( self._is, _tns( self._n ), value ) )
    def float( self, value ):
        print( "{}TAG_Float{}: {:g}".format( self._is, _tns( self._n ), value ) )
    def double( self, value ):
        print( "{}TAG_Double{}: {:g}".format( self._is, _tns( self._n ), value ) )
    def startByteArray( self, length ):
        print( "{}TAG_Byte_Array{}: [{:d} byte{}]".format( self._is, _tns( self._n ), length, "s" if length != 1 else "" ) )
    def string( self, value ):
        print( "{}TAG_String{}: {:s}".format( self._is, _tns( self._n ), value ) )
    def startList( self, tagType, length ):
        print( "{}TAG_List{}: {} [".format( self._is, _tns( self._n ), _tls( length, tagType ) ) )
        self._n = None
        self.setIndent( self._i + 1 )
    def endList( self ):
        self.setIndent( self._i - 1 )
        print( self._is + "]" )
    def startCompound( self ):
        print( "{}TAG_Compound{}: {{".format( self._is, _tns( self._n ) ) )
        self.setIndent( self._i + 1 )
    def endCompound( self ):
        self.setIndent( self._i - 1 )
        print( self._is + "}" )
    def startIntArray( self, length ):
        print( "{}TAG_Int_Array{}: [{:d} int{}]".format( self._is, _tns( self._n ), length, "s" if length != 1 else "" ) )