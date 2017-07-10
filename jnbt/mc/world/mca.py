#This module contains code for working with the MCA (Anvil) format.
#Anvil was introduced in Minecraft 12w07a (February 15, 2012) and is still used by modern versions of Minecraft at the time of writing.
#
#An MCA-formatted chunk consists of a sparsely populated column of up to 16 sections (i.e. 1x16x1 sections). Each section contains 16x16x16 blocks.
#Geometrically, an MCA-formatted chunk is a 16x256x16 block column containing a total of 65536 blocks.
#All arrays are one-dimensional. Block data is indexed in YZX order (i.e. (0,0,0) would be index 1, (0,1,0) would be index 2, etc.)
#
#Read more about the format here:
#    http://minecraft.gamepedia.com/Anvil_file_format
#    http://minecraft.gamepedia.com/Chunk_format

import re

from jnbt.mc.world.base import LVLFMT_ANVIL, _BaseWorld, _BaseDimension, _BaseRegion, _BaseChunk, _BaseBlock, _n

#Regular expressions that matches Anvil filenames; i.e. filenames of the form "r.{x}.{z}.mca" (where x and z are region coordinates)
RE_FILENAME  = re.compile( "^r\.(-?\d+)\.(-?\d+)\.mca$", re.IGNORECASE )
FMT_FILENAME = "r.{:d}.{:d}.mca"
NAME         = "anvil"

def _getBlockIDWithAdd( index, blocks, add ):
    return blocks[index] + ( _n( add, index ) << 8 )

def _getBlockIDWithoutAdd( index, blocks, add ):
    return blocks[index]

class World( _BaseWorld ):
    __slots__ = ()
    formatid = LVLFMT_ANVIL
    format   = NAME
    #_clsDimension = (outside of class)

class Dimension( _BaseDimension ):
    """Represents an MCA dimension."""
    __slots__ = ()
    formatid  = LVLFMT_ANVIL
    format    = NAME
    #_clsRegion = (outside of class)
    _reFilename = RE_FILENAME
    _fmtFilename = FMT_FILENAME
World._clsDimension = Dimension

class Region( _BaseRegion ):
    """
    Represents an MCA region.
    A region consists of a sparsely populated 32x32 grid of chunks.
    Overall, an MCA region encompasses a 512x256x512 block area.
    """
    __slots__ = ()
    formatid  = LVLFMT_ANVIL
    format    = NAME
    #_clsChunk = (outside of class)
Dimension._clsRegion = Region

class Chunk( _BaseChunk ):
    """Represents an MCA-formatted chunk."""
    __slots__ = ()
    formatid = LVLFMT_ANVIL
    format   = NAME
    def iterBlocks( self ):
        #Reuse the same Block() instance to avoid performance penalty of repeated Block#__init__() calls.
        block = Block( self )
        for section in self.nbt["Level"]["Sections"]:
            baseY = 16 * int( section["Y"] )
            add = section.get("Add")
            sectionData = (
                section["Blocks"],                                      #0
                section["Data"],                                        #1
                section["BlockLight"],                                  #2
                section["SkyLight"],                                    #3
                baseY,                                                  #4
                add,                                                    #5
                _getBlockIDWithAdd if add else _getBlockIDWithoutAdd,   #6
            )
            block._d = sectionData
            for i in range( 4096 ):
                block._i = i
                yield block
    def getBlock( self, x, y, z ):
        for section in self.nbt["Level"]["Sections"]:
            baseY = 16 * int( section["Y"] )
            if y >= baseY and y < baseY + 16:
                add = section.get("Add")
                sectionData = (
                    section["Blocks"],
                    section["Data"],
                    section["BlockLight"],
                    section["SkyLight"],
                    baseY,
                    add,
                    _getBlockIDWithAdd if add else _getBlockIDWithoutAdd,
                )
                return Block( self, sectionData, 256*(y-baseY) + 16*z + x )
        return None
    __iter__ = iterBlocks
Region._clsChunk = Chunk

class Block( _BaseBlock ):
    formatid = LVLFMT_ANVIL
    format   = NAME
    def getPos( self ):
        y, index = divmod( self._i, 256 )
        z, x = divmod( index, 16 )
        c = self.chunk
        return (
            16 * c.x   + x,
            self._d[4] + y,
            16 * c.z   + z
        )
    pos = property( getPos )

    def getX( self ):
        return 16 * self.chunk.x + ( self._i & 15 )
    x = property( getX )

    def getY( self ):
        return self._d[4] + ( self._i // 256 )
    y = property( getY )

    def getZ( self ):
        return 16 * self.chunk.z + ( ( self._i & 255 ) // 16 )
    z = property( getZ )

    def getID( self ):
        d = self._d
        return d[6]( self._i, d[0], d[5] )
    id = property( getID )