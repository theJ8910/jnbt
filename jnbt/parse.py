from .shared import (
    NBTFormatError, readInts as _ris,
    _NT, _TL, _B, _S, _I, _L, _F, _D,
    TAG_END, TAG_BYTE, TAG_SHORT, TAG_INT, TAG_LONG, TAG_FLOAT, TAG_DOUBLE, TAG_BYTE_ARRAY, TAG_STRING, TAG_LIST, TAG_COMPOUND, TAG_INT_ARRAY,
    TAG_COUNT
)

def _read( input, n ):
    """
    Reads n bytes from input (a file-like object).
    Raises an EOFError if the end-of-file is encountered before n bytes can be read.
    """
    b = input.read( n )
    if len( b ) != n:
        raise EOFError( "End of file reached prematurely!" )
    return b

def parse( input, handler ):
    """
    Provides SAX-like NBT parsing.

    As NBT tags are parsed from input, parse calls the corresponding methods on the given handler (e.g. string(), short()).
    These methods can then react to these tags being read as necessary.
    handler is expected to implement the methods defined in AbstractNBTHandler.

    There are two primary advantages to parse() over treeparse():
        1. Data is usable as soon as it is read (i.e. you don't have to wait for the entire input source to be read)
        2. Typically lower memory requirements due to parse() discarding the data it has read after handler has interacted with it

    parse() does have disadvantages, however. One such disadvantage is that tasks that require data to be accessed out-of-order are typically harder / more awkward to program.

    input is expected to be a file-like object containing uncompressed NBT data.
    """
    #Read root tag type and name length at same time
    tagType, length = _NT.unpack( _read( input, 3 ) )

    #Check that tagType and name length are valid.
    if tagType != TAG_COMPOUND:
        raise NBTFormatError( "Root tag is expected to be a {}, but is a {} instead.".format( describeTag( TAG_COMPOUND ), describeTag( tagType ) ) )
    if length < 0:
        raise NBTFormatError( "Invalid length for name string: {:d}.".format( length ) )

    #Call .name() on handler, passing tagType and length.
    handler.name( tagType, _read( input, length ).decode() )
    handler.start()
    parseTagCompound( input, handler )
    handler.end()
def parseTagByte( input, handler ):
    """
    Reads a TAG_Byte from input as a python int.
    Calls handler.byte() and passes the value as an argument.
    """
    handler.byte( _B.unpack( _read( input, 1 ) )[0] )
def parseTagShort( input, handler ):
    """
    Reads a TAG_Short from input as a python int.
    Calls handler.short() and passes the value as an argument.
    """
    handler.short( _S.unpack( _read( input, 2 ) )[0] )

def parseTagInt( input, handler ):
    """
    Reads a TAG_Int from input as a python int.
    Calls handler.int() and passes the value as an argument.
    """
    handler.int( _I.unpack( _read( input, 4 ) )[0] )

def parseTagLong( input, handler ):
    """
    Reads a TAG_Long from input as a python int.
    Calls handler.long() and passes the value as an argument.
    """
    handler.long( _L.unpack( _read( input, 8 ) )[0] )

def parseTagFloat( input, handler ):
    """
    Reads a TAG_Float from input as a python float (i.e. a float)
    Calls handler.float() and passes the value as an argument.
    """
    handler.float( _F.unpack( _read( input, 4 ) )[0] )

def parseTagDouble( input, handler ):
    """
    Reads a TAG_Double from input as a python float (i.e. a double)
    Calls handler.double() and passes the value as an argument.
    """
    handler.double( _D.unpack( _read( input, 8 ) )[0] )

def parseTagByteArray( input, handler ):
    """
    Reads a TAG_Byte_Array from input.
    Calls handler.startByteArray(), passing the length of the array.
    Repeatedly reads up to 4KB from the array and calls handler.bytes(), passing the bytes that were read as an argument.
    Finally, calls handler.endByteArray().
    """
    length = _I.unpack( _read( input, 4 ) )[0]

    #Check that length is valid.
    if length < 0:
        raise NBTFormatError( "Invalid length for TAG_Byte_Array: {:d}".format( length ) )

    handler.startByteArray( length )
    
    #Read at most 4096 bytes at a time
    if length > 0:
        while length > 4096:
            handler.bytes( _read( input, 4096 ) )
            length -= 4096
        handler.bytes( _read( input, length ) )

    handler.endByteArray()

def parseTagString( input, handler ):
    """
    Reads a TAG_String from input as a UTF-8 encoded string.
    Calls handler.string() and passes the value as an argument.
    """
    length = _S.unpack( _read( input, 2 ) )[0]
    if length < 0:
        raise NBTFormatError( "Invalid string length encountered while parsing TAG_String: {:d}.".format( length ) )
    handler.string( _read( input, length ).decode() )

def parseTagList( input, handler ):
    """
    Reads a TAG_List from input.
    Calls handler.startList(), passing the tag type and number of items in the list.
    For each entry in the list, calls the appropriate parse*() function (e.g. parseInt) to read the payload of the tag.
    Finally, calls handler.endList().
    """
    tagType, length = _TL.unpack( _read( input, 5 ) )
    if tagType < 0 or tagType >= TAG_COUNT:
        raise NBTFormatError( "Invalid tag type encountered while parsing TAG_List: {}.".format( describeTag( tagType ) ) )
    parser = TAG_PARSERS[ tagType ]

    handler.startList( tagType, length )
    for i in range( length ):
        parser( input, handler )
    handler.endList()

def parseTagCompound( input, handler ):
    """
    Reads a TAG_Compound from input.
    Calls handler.startCompound().
    For each entry in the TAG_Compound:
        1. Reads the type and name of the entry from input and calls handler.name()
        2. Calls an appropriate parse*() function (e.g. parseInt) to read the payload of the tag
    Finally, calls handler.endCompound().
    """
    handler.startCompound()
    
    #Read first named tag header
    tagType = _B.unpack( _read( input, 1 ) )[0]
    while tagType != TAG_END:
        #Check that tagType is valid.
        if tagType < 0 or tagType >= TAG_COUNT:
            raise NBTFormatError( "Unknown tag type {:d}.".format( tagType ) )
        #Now that we know the named tag isn't TAG_End, read the length of the name and check that it's valid.
        length = _S.unpack( _read( input, 2 ) )[0]
        if length < 0:
            raise NBTFormatError( "Invalid length for name string: {:d}.".format( length ) )

        #Call .name() on handler, passing tagType and length.
        handler.name( tagType, _read( input, length ).decode() )
        
        #Call appropriate parse() function for the type of tag we're reading
        TAG_PARSERS[ tagType ]( input, handler )

        #Read next named tag header
        tagType = _B.unpack( _read( input, 1 ) )[0]

    handler.endCompound()

def parseTagIntArray( input, handler ):
    """
    Reads a TAG_Int_Array from input.
    Calls handler.startIntArray(), passing the length of the array.
    Repeatedly reads up to 4KB (1024 integers) from input and calls handler.ints(), passing the ints that were read as an argument.
    Finally, calls handler.endIntArray().
    """
    #Note: length refers to the number of integers in the array, NOT the number of bytes.
    #Since each integer is 4 bytes each, multiply this number by 4 to get the number of bytes.
    length = _I.unpack( _read( input, 4 ) )[0]

    #Check that length is valid.
    if length < 0:
        raise NBTFormatError( "Invalid length for TAG_Int_Array: {:d}".format( length ) )

    handler.startIntArray( length )

    #Read at most 1024 ints (4096 bytes) at a time
    if length > 0:
        while length > 1024:
            handler.ints( _ris( input, 1024 ) )
            length -= 1024
        handler.ints( _ris( input, length ) )

    handler.endIntArray()

#List of functions (indexed by tag type) that parse the payloads for their respective tags.
#I'd prefer to put this at the top with the rest of the constants, but the parse functions aren't declared until the bottom of the file.
TAG_PARSERS = (
    None,
    parseTagByte,
    parseTagShort,
    parseTagInt,
    parseTagLong,
    parseTagFloat,
    parseTagDouble,
    parseTagByteArray,
    parseTagString,
    parseTagList,
    parseTagCompound,
    parseTagIntArray
)