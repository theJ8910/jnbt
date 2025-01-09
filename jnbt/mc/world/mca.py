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
RE_FILENAME  = re.compile( "^r\\.(-?\\d+)\\.(-?\\d+)\\.mca$", re.IGNORECASE )
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

#TODO: MC 1.13 kept the anvil format, but uses a different chunk format.
#The iterBlocks / getBlock methods here will FAIL on 1.13 or newer worlds.
#Specifically, Blocks, Add, and Data were removed, and Palette and BlockStates was added.
#Palette is a TAG_List containing every unique block state in the chunk, as TAG_Compounds.
#Each TAG_Compound contains two keys:
#    Name (the block ID as a TAG_String)
#    Properties (a TAG_Compound, optional.)
#        This entry maps one or more block state properties names (e.g. "minecraft:redstone_ore" has the "lit" property) to its respective value,
#        stored as a TAG_String (e.g. "false").
#BlockStates is a TAG_Long_Array of variable size, enough to store 4096 (16x16x16) Palette indices.
#    I find it easier to think of this as an array of indices (where each index is "N" bits large), rather than an array of longs.
#    Each long in this array provides 64 bits of space in which the indices can be stored.
#    If we need N bits to represent the largest index in Palette, then we need a TAG_Long_Array containing ceil( ( 4096 * N ) / 64 ) longs to store this many entries.
#    N can be 4 at a minimum (in which case Palette will contain 16 or fewer entries and BlockStates will contain 256 longs),
#    and 12 at a maximum (in which case Palette will contain 4096 entries and BlockStates will contain 1024 longs).
#    If N doesn't evenly divide 64 (e.g. N=5), then the bits for an index may span two longs.
#    Indices are ordered within the array in an YZX order as they were before (e.g. the first index = (0,0,0), the second index = (1,0,0), the 16th index = (0,0,1), the 256th index = (0,1,0), etc).
#    The actual block state for these coordinates is determined by the block state stored in Palette at the particular index.
#
#I need to:
#    1. Write code to handle the new chunk format
#    2. Pin down exactly which Minecraft version the change happened in, so we can easily determine which code to use.
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
