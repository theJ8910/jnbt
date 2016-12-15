import sys
import os
import gzip
import traceback
import pdb
import functools
from array import array
from collections import OrderedDict
from pathlib import Path

import jnbt as nbt1
import nbt.nbt as nbt2

def main( argv ):
    try:
        #Read and compare test.nbt (note: uncompressed)
        with open( "test.nbt", "rb" ) as file:
            d1 = nbt1.treeparse( file )
        with open( "test.nbt", "rb" ) as file:
            d2 = nbt2.NBTFile( buffer=file )
        compare( d1, d2 )
        print( "d1 = d2 for test.nbt" )

        #Read and compare bigtest.nbt (note: gzip compressed)
        with gzip.open( "bigtest.nbt" ) as file:
            d1 = nbt1.treeparse( file )
        d2 = nbt2.NBTFile( "bigtest.nbt" )
        compare( d1, d2 )
        print( "d1 = d2 for bigtest.nbt" )

        #Read and compare level.dat
        p = str( Path( os.environ["appdata"], ".minecraft", "saves", "New World", "level.dat" ) )
        with gzip.open( p ) as file:
            d1 = nbt1.treeparse( file )
        d2 = nbt2.NBTFile( p )
        compare( d1, d2 )
        print( "d1 = d2 for level.dat" )

        print( "Testing nbt1.NBTWriter" )
        writeTest1()
        print( "Testing nbt1.SafeNBTWriter" )
        writeTest2()
        print( "Testing nbt2.NBTFile" )
        writeTest3()

        return 0
    except:
        traceback.print_exc()
        pdb.post_mortem(sys.exc_info()[2])
        return 1

def writeTest( Writer ):
    with Writer( open( "write_test.nbt", "wb" ) ) as w:
        w.start( "Example!" )
        w.byte( "byte", -3 )
        w.short( "short", -500 )
        w.int( "int", -1234567 )
        w.long( "long", -12345678910111213 )
        w.float( "float", 52.358924865722656 )
        w.double( "double", 123.456789101112 )
        w.string( "string", "This is a string!" )
        w.startCompound( "compound" )
        w.string( "name", "Jeff" )
        w.int( "id", 5 )
        w.endCompound()
        w.list( "list", nbt1.TAG_STRING, ( "Hey!", "Check", "out", "these", "strings!" ) )
        w.startList( "list2", nbt1.TAG_FLOAT, 4 )
        w.float( 10.2 )
        w.float( 15.6 )
        w.float( 17.1 )
        w.float( -1.12 )
        w.endList()
        w.bytearray( "bytearray", b"\x00\x01\x02\x03" )
        w.startByteArray( "bytearray2", 4 )
        w.bytes( b"\x04\x05" )
        w.bytes( b"\x06\x07" )
        w.endByteArray()
        w.intarray( "intarray", array( "i", ( 5,6,7,8 ) ) )
        w.startIntArray( "intarray2", 4 )
        w.ints( array( "i", ( 9, 10 ) ) )
        w.ints( array( "i", ( 11, 12 ) ) )
        w.endIntArray()
        w.end()

writeTest1 = functools.partial( writeTest, nbt1.NBTWriter )
writeTest2 = functools.partial( writeTest, nbt1.SafeNBTWriter )

def writeTest3():
    with open( "write_test.nbt", "wb" ) as file:
        f               = nbt2.NBTFile()

        f["byte"]       = nbt2.TAG_Byte( -3 )
        f["short"]      = nbt2.TAG_Short( -500 )
        f["int"]        = nbt2.TAG_Int( -1234567 )
        f["long"]       = nbt2.TAG_Long( -12345678910111213 )
        f["float"]      = nbt2.TAG_Float( 52.358924865722656 )
        f["double"]     = nbt2.TAG_Double( 123.456789101112 )
        f["string"]     = nbt2.TAG_String( "This is a string!" )
        
        c               = nbt2.TAG_Compound()
        c["name"]       = nbt2.TAG_String( "Jeff" )
        c["id"]         = nbt2.TAG_Int( 5 )
        f["compound"]   = c

        l               = nbt2.TAG_List( nbt2.TAG_String )
        l.append( nbt2.TAG_String( "Hey!" ) )
        l.append( nbt2.TAG_String( "Check" ) )
        l.append( nbt2.TAG_String( "out" ) )
        l.append( nbt2.TAG_String( "these" ) )
        l.append( nbt2.TAG_String( "strings!" ) )
        f["list"]       = l

        l               = nbt2.TAG_List( nbt2.TAG_Float )
        l.append( nbt2.TAG_Float( 10.2 ) )
        l.append( nbt2.TAG_Float( 15.6 ) )
        l.append( nbt2.TAG_Float( 17.1 ) )
        l.append( nbt2.TAG_Float( -1.12 ) )
        f["list2"]      = l

        b               = nbt2.TAG_Byte_Array()
        b.value         = bytearray( b"\x00\x01\x02\x03" )
        f["bytearray"]  = b

        b               = nbt2.TAG_Byte_Array()
        b.value         = bytearray( b"\x04\x05\x06\x07" )
        f["bytearray2"] = b

        i               = nbt2.TAG_Int_Array()
        i.value         = [ 5,6,7,8 ]
        f["intarray"]   = i

        i               = nbt2.TAG_Int_Array()
        i.value         = [ 9, 10, 11, 12 ]
        f["intarray2"]  = i

        f.write_file( buffer=file )

def compare( d1, d2 ):
    if type( d1 ) is not tuple:
        raise Exception( "nbt1 document root isn't a tuple!" )
    if type( d2 ) is not nbt2.NBTFile:
        raise Exception( "nbt2 document root isn't an NBTFile!" )
    if d1[0] != d2.name:
        raise Exception( "Document root names don't match!" )
    compareTagCompound( d1[1], d2 )

def compareTagCompound( t1, t2 ):
    if type( t1 ) is not OrderedDict:
        raise Exception( "t1 isn't an OrderedDict!" )
    t2t = type( t2 )
    if t2t is not nbt2.TAG_Compound and t2t is not nbt2.NBTFile:
        raise Exception( "t2 is neither a TAG_Compound nor an NBTFile!" )
    mismatch = set( t1.keys() ) ^ set( t2.keys() )
    if len( mismatch ) > 0:
        raise Exception( "TAG_Compound key sets differ!" )
    for k,v1 in t1.items():
        v2 = t2[k]

        c = COMPARATORS[ v2.id ]

        if c is not None:
            c( v1, v2 )
        else:
            raise Exception( "Unknown tag type" )

def compareTagList( t1, t2 ):
    if type( t1 ) is not list:
        raise Exception( "t1 isn't a list!" )
    if type( t2 ) is not nbt2.TAG_List:
        raise Exception( "t2 isn't a TAG_List!" )
    l = len( t1 )
    if l != len( t2 ):
        raise Exception( "List lengths don't match!" )

    c = COMPARATORS[ t2.tagID ]
    for i in range( l ):
        c( t1[i], t2[i] )

def compareTagIntArray( t1, t2 ):
    t2v = t2.value
    l = len( t1 )
    if l != len( t2v ):
        raise Exception( "t1 and t2 are different sizes!" )
    #We need a custom function for compareTagIntArray because nbt1 (ours) uses array to represent this tag, but nbt2 uses list
    for i1,i2 in zip( t1, t2v ):
        if i1 != i2:
            raise Exception( "An integer in t1 and t2 have different values!" )

def comparator( type1, type2 ):
    name1 = type1.__name__
    err1 = "t1 isn't {} {}!".format( "an" if name1[0].lower() in "aeiou" else "a", name1 )
    name2 = type2.__name__
    err2 = "t2 isn't {} {}!".format( "an" if name2[0].lower() in "aeiou" else "a", name2 )
    def compare( t1, t2 ):
        if type( t1 ) is not type1:
            raise Exception( err1 )
        if type( t2 ) is not type2:
            raise Exception( err2 )
        if t1 != t2.value:
            raise Exception( "Tag values don't match!" )
    return compare

COMPARATORS = (
    None,                                         #TAG_End
    comparator( int,       nbt2.TAG_Byte       ), #TAG_Byte
    comparator( int,       nbt2.TAG_Short      ), #TAG_Short
    comparator( int,       nbt2.TAG_Int        ), #TAG_Int
    comparator( int,       nbt2.TAG_Long       ), #TAG_Long
    comparator( float,     nbt2.TAG_Float      ), #TAG_Float
    comparator( float,     nbt2.TAG_Double     ), #TAG_Double
    comparator( bytearray, nbt2.TAG_Byte_Array ), #TAG_Byte_Array
    comparator( str,       nbt2.TAG_String     ), #TAG_String
    compareTagList,                               #TAG_List
    compareTagCompound,                           #TAG_Compound
    compareTagIntArray                            #TAG_Int_Array
)

if __name__ == "__main__":
    sys.exit( main( sys.argv ) )