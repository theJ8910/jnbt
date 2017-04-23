import unittest

import jnbt

from jnbt.shared import s4array

expected = (
    ( "start",                                            ),
    ( "name",          jnbt.TAG_COMPOUND,   "Example!"    ),
    ( "startCompound",                                    ),
    ( "name",          jnbt.TAG_BYTE,       "byte"        ),
    ( "byte",          -3                                 ),
    ( "name",          jnbt.TAG_SHORT,      "short"       ),
    ( "short",         -500                               ),
    ( "name",          jnbt.TAG_INT,        "int"         ),
    ( "int",           -1234567                           ),
    ( "name",          jnbt.TAG_LONG,       "long"        ),
    ( "long",          -12345678910111213                 ),
    ( "name",          jnbt.TAG_FLOAT,      "float"       ),
    ( "float",         52.358924865722656                 ),
    ( "name",          jnbt.TAG_DOUBLE,     "double"      ),
    ( "double",        123.456789101112                   ),
    ( "name",          jnbt.TAG_STRING,     "string"      ),
    ( "string",        "This is a string!"                ),
    ( "name",          jnbt.TAG_COMPOUND,   "compound"    ),
    ( "startCompound",                                    ),
    ( "name",          jnbt.TAG_STRING,     "name"        ),
    ( "string",        "Jeff"                             ),
    ( "name",          jnbt.TAG_INT,        "id"          ),
    ( "int",           5                                  ),
    ( "endCompound",                                      ),
    ( "name",          jnbt.TAG_LIST,       "list"        ),
    ( "startList",     jnbt.TAG_STRING,     5             ),
    ( "string",        "Hey!"                             ),
    ( "string",        "Check"                            ),
    ( "string",        "out"                              ),
    ( "string",        "these"                            ),
    ( "string",        "strings!"                         ),
    ( "endList",                                          ),
    ( "name",          jnbt.TAG_LIST,       "list2"       ),
    ( "startList",     jnbt.TAG_FLOAT,      4             ),
    ( "float",         10.2                               ),
    ( "float",         15.6                               ),
    ( "float",         17.1                               ),
    ( "float",         -1.12                              ),
    ( "endList",                                          ),
    ( "name",           jnbt.TAG_BYTE_ARRAY, "bytearray"  ),
    ( "startByteArray", 4                                 ),
    ( "bytes",          b"\x00\x01\x02\x03"               ),
    ( "endByteArray",                                     ),
    ( "name",           jnbt.TAG_BYTE_ARRAY, "bytearray2" ),
    ( "startByteArray", 4                                 ),
    ( "bytes",          b"\x04\x05\x06\x07"               ),
    ( "endByteArray",                                     ),
    ( "name",           jnbt.TAG_INT_ARRAY,  "intarray"   ),
    ( "startIntArray",  4                                 ),
    ( "ints",           s4array( ( 5, 6, 7, 8 ) )         ),
    ( "endIntArray",                                      ),
    ( "name",           jnbt.TAG_INT_ARRAY, "intarray2"   ),
    ( "startIntArray",  4                                 ),
    ( "ints",           s4array( ( 9, 10, 11, 12 ) )      ),
    ( "endIntArray",                                      ),
    ( "endCompound",                                      ),
    ( "end",                                              )
)
class TestNBTHandler( jnbt.NBTHandler ):
    def __init__( self ):
        self._i = 0
    def _check( self, *args ):
        i = self._i
        if i >= len( expected ) or expected[i] != args:
            #print( "Mismatch: Expected {}, got {}".format( expected[i], args ) )
            return self.stop()
        self._i = i + 1
    def _checkFloat( self, *args ):
        i = self._i
        if i >= len( expected ):
            return self.stop()

        expected_args = expected[i]
        if expected_args[0] != args[0] or abs( expected_args[1] - args[1] ) >= 0.001:
            return self.stop()
        self._i = i + 1

    def name( self, tagType, name ):
        self._check( "name", tagType, name )
    def start( self ):
        self._check( "start" )
    def end( self ):
        self._check( "end" )
        if self._i != len( expected ):
            self.stop()
    def byte( self, value ):
        self._check( "byte", value )
    def short( self, value ):
        self._check( "short", value )
    def int( self, value ):
        self._check( "int", value )
    def long( self, value ):
        self._check( "long", value )
    def float( self, value ):
        self._checkFloat( "float", value )
    def double( self, value ):
        self._checkFloat( "double", value )
    def startByteArray( self, length ):
        self._check( "startByteArray", length )
    def bytes( self, values ):
        self._check( "bytes", values )
    def endByteArray( self ):
        self._check( "endByteArray" )
    def string( self, value ):
        self._check( "string", value )
    def startList( self, tagType, length ):
        self._check( "startList", tagType, length )
    def endList( self ):
        self._check( "endList" )
    def startCompound( self ):
        self._check( "startCompound" )
    def endCompound( self ):
        self._check( "endCompound" )
    def startIntArray( self, length ):
        self._check( "startIntArray", length )
    def ints( self, values ):
        self._check( "ints", values )
    def endIntArray( self ):
        self._check( "endIntArray" )


class TestJNBT( unittest.TestCase ):
    def test_parse( self):
        for source, compression in ( ( "raw.nbt", None ), ( "gzip.nbt", "gzip" ), ( "zlib.nbt", "zlib" ) ):
            self.assertTrue( jnbt.parse( source, TestNBTHandler(), compression ) )
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
            w.intarray( "intarray", ( 5, 6, 7, 8 ) )
            w.startIntArray( "intarray2", 4 )
            w.ints( (  9, 10 ) )
            w.ints( ( 11, 12 ) )
            w.endIntArray()
            w.end()

if __name__ == "__main__":
    unittest.main()