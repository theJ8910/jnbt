import unittest
from array import array

import jnbt

class TestJNBT( unittest.TestCase ):
    def test_NBTWriter( self ):
        with jnbt.writer( "write_test.nbt", None ) as w:
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
            w.list( "list", jnbt.TAG_STRING, ( "Hey!", "Check", "out", "these", "strings!" ) )
            w.startList( "list2", jnbt.TAG_FLOAT, 4 )
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

if __name__ == "__main__":
    unittest.main()