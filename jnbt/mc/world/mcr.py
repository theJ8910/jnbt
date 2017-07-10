#This module contains code for working with the MCR ("McRegion" or simply "Region") format.
#Region was used by Minecraft from Beta 1.3 (February 22, 2011) to Snapshot 12w06a (February 14, 2012).

#Geometrically, an MCR-formatted chunk is a 16x128x16 block column containing a total of 32768 blocks.
#All arrays are one-dimensional. For all arrays but HeightMap, block data is indexed in XZY order (i.e. (0,0,0) would be index 0, (0,1,0) would be index 1, etc.)
#HeightMap is ordered in ZX order (i.e. (0,0) would be index 0, (1,0) would be index 1, etc.)
#
#Read more about the format here:
#    http://minecraft.gamepedia.com/Region_file_format
#    http://minecraft.gamepedia.com/index.php?title=Chunk_format&oldid=249962

import re

from jnbt.mc.world.base import LVLFMT_REGION, _BaseWorld, _BaseDimension, _BaseRegion, _BaseChunk, _BaseBlock

#Regular expressions that matches McRegion filenames; i.e. filenames of the form "r.{x}.{z}.mcr" (where x and z are region coordinates)
RE_FILENAME  = re.compile( "^r\.(-?\d+)\.(-?\d+)\.mcr$", re.IGNORECASE )
FMT_FILENAME = "r.{:d}.{:d}.mcr"
NAME         = "region"

class World( _BaseWorld ):
    __slots__ = ()
    formatid = LVLFMT_REGION
    format   = NAME
    #_clsDimension = (outside of class)

class Dimension( _BaseDimension ):
    __slots__ = ()
    formatid = LVLFMT_REGION
    format   = NAME
    #_clsRegion = (outside of class)
    _reFilename = RE_FILENAME
    _fmtFilename = FMT_FILENAME
World._clsDimension = Dimension

class Region( _BaseRegion ):
    """
    Represents an MCR region.
    A region consists of a sparsely populated 32x32 grid of chunks.
    Overall, an MCR region encompasses a 512x128x512 block area.
    """
    __slots__ = ()
    formatid = LVLFMT_REGION
    format   = NAME
    #_clsChunk = (outside of class)
Dimension._clsRegion = Region

class Chunk( _BaseChunk ):
    """Represents an MCR-formatted chunk."""
    __slots__ = ()
    formatid = LVLFMT_REGION
    format   = NAME
    def iterBlocks( self ):
        #Reuse the same Block() instance to avoid performance penalty of repeated Block#__init__() calls.
        block = Block( self )
        level = self.nbt["Level"]
        data = (
            level["Blocks"],        #0
            level["Data"],          #1
            level["BlockLight"],    #2
            level["SkyLight"]       #3
        )
        block._d = data
        for i in range( 32768 ):
            block._i = i
            yield block
    def getBlock( self, x, y, z ):
        level = self.nbt["Level"]
        data = (
            level["Blocks"],
            level["Data"],
            level["BlockLight"],
            level["SkyLight"]
        )
        return Block( self, data, 2048*x + 128*z + y )
    __iter__ = iterBlocks
Region._clsChunk = Chunk

class Block( _BaseBlock ):
    formatid = LVLFMT_REGION
    format   = NAME
    def getPos( self ):
        x, index = divmod( self._i, 2048 )
        z, y = divmod( index, 128 )
        c = self.chunk
        return (
            16 * c.x + x,
                       y,
            16 * c.z + z
        )
    pos = property( getPos )

    def getX( self ):
        return 16 * self.chunk.x + self._i // 2048
    x = property( getX )

    def getY( self ):
        return ( self._i & 127 )
    y = property( getY )

    def getZ( self ):
        return 16 * self.chunk.z + ( ( self._i & 2047 ) // 128 )
    z = property( getZ )

    def getID( self ):
        return self._d[0][ self._i ]
    id = property( getID )