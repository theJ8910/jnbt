"""
JNBT's world module contains classes and functions for interacting with Minecraft saves.

Note: This module is still under development, and as such is subject to breaking changes!
"""
import os
import os.path
import sys
import re
import json
import urllib.request
import zlib
from io import BytesIO
from collections import OrderedDict
from array import array

from . import tag
from .shared import read as _r, readUnsignedByte as _rub, readUnsignedInt as _rui, readUnsignedInts as _ruis

#Regular expressions that matches Region / Anvil filenames; i.e. filenames of the form "r.{x}.{z}.mc(a|r)" (where x and z are region coordinates)
MCR_RE = re.compile( "^r\.(-?\d+)\.(-?\d+)\.mcr$", re.IGNORECASE )
MCA_RE = re.compile( "^r\.(-?\d+)\.(-?\d+)\.mca$", re.IGNORECASE )
#Regular expression that matches player data filenames; i.e. filenames of the form "{8}-{4}-{4}-{4}-{12}.dat", where {n} is a grouping of bytes that makes up the player's UUID, expressed as n hex digits.
PD_RE  = re.compile( "^([0-9a-f]{8})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{12})\.dat$", re.IGNORECASE )




#Dimension IDs for the Overworld, Nether, and End
DIM_NETHER    = -1
DIM_OVERWORLD =  0
DIM_END       =  1

#Compression types
COMPRESSION_NONE = 0
COMPRESSION_GZIP = 1
COMPRESSION_ZLIB = 2




#Path to the Minecraft installation directory
_mcPath = None
_blockIDtoName = {
      0: "minecraft:air",
      1: "minecraft:stone",
      2: "minecraft:grass",
      3: "minecraft:dirt",
      4: "minecraft:cobblestone",
      5: "minecraft:planks",
      6: "minecraft:sapling",
      7: "minecraft:bedrock",
      8: "minecraft:flowing_water",
      9: "minecraft:water",
     10: "minecraft:flowing_lava",
     11: "minecraft:lava",
     12: "minecraft:sand",
     13: "minecraft:gravel",
     14: "minecraft:gold_ore",
     15: "minecraft:iron_ore",
     16: "minecraft:coal_ore",
     17: "minecraft:log",
     18: "minecraft:leaves",
     19: "minecraft:sponge",
     20: "minecraft:glass",
     21: "minecraft:lapis_ore",
     22: "minecraft:lapis_block",
     23: "minecraft:dispenser",
     24: "minecraft:sandstone",
     25: "minecraft:noteblock",
     26: "minecraft:bed",
     27: "minecraft:golden_rail",
     28: "minecraft:detector_rail",
     29: "minecraft:sticky_piston",
     30: "minecraft:web",
     31: "minecraft:tallgrass",
     32: "minecraft:deadbush",
     33: "minecraft:piston",
     34: "minecraft:piston_head",
     35: "minecraft:wool",
     36: "minecraft:piston_extension",
     37: "minecraft:yellow_flower",
     38: "minecraft:red_flower",
     39: "minecraft:brown_mushroom",
     40: "minecraft:red_mushroom",
     41: "minecraft:gold_block",
     42: "minecraft:iron_block",
     43: "minecraft:double_stone_slab",
     44: "minecraft:stone_slab",
     45: "minecraft:brick_block",
     46: "minecraft:tnt",
     47: "minecraft:bookshelf",
     48: "minecraft:mossy_cobblestone",
     49: "minecraft:obsidian",
     50: "minecraft:torch",
     51: "minecraft:fire",
     52: "minecraft:mob_spawner",
     53: "minecraft:oak_stairs",
     54: "minecraft:chest",
     55: "minecraft:redstone_wire",
     56: "minecraft:diamond_ore",
     57: "minecraft:diamond_block",
     58: "minecraft:crafting_table",
     59: "minecraft:wheat",
     60: "minecraft:farmland",
     61: "minecraft:furnace",
     62: "minecraft:lit_furnace",
     63: "minecraft:standing_sign",
     64: "minecraft:wooden_door",
     65: "minecraft:ladder",
     66: "minecraft:rail",
     67: "minecraft:stone_stairs",
     68: "minecraft:wall_sign",
     69: "minecraft:lever",
     70: "minecraft:stone_pressure_plate",
     71: "minecraft:iron_door",
     72: "minecraft:wooden_pressure_plate",
     73: "minecraft:redstone_ore",
     74: "minecraft:lit_redstone_ore",
     75: "minecraft:unlit_redstone_torch",
     76: "minecraft:redstone_torch",
     77: "minecraft:stone_button",
     78: "minecraft:snow_layer",
     79: "minecraft:ice",
     80: "minecraft:snow",
     81: "minecraft:cactus",
     82: "minecraft:clay",
     83: "minecraft:reeds",
     84: "minecraft:jukebox",
     85: "minecraft:fence",
     86: "minecraft:pumpkin",
     87: "minecraft:netherrack",
     88: "minecraft:soul_sand",
     89: "minecraft:glowstone",
     90: "minecraft:portal",
     91: "minecraft:lit_pumpkin",
     92: "minecraft:cake",
     93: "minecraft:unpowered_repeater",
     94: "minecraft:powered_repeater",
     95: "minecraft:stained_glass",
     96: "minecraft:trapdoor",
     97: "minecraft:monster_egg",
     98: "minecraft:stonebrick",
     99: "minecraft:brown_mushroom_block",
    100: "minecraft:red_mushroom_block",
    101: "minecraft:iron_bars",
    102: "minecraft:glass_pane",
    103: "minecraft:melon_block",
    104: "minecraft:pumpkin_stem",
    105: "minecraft:melon_stem",
    106: "minecraft:vine",
    107: "minecraft:fence_gate",
    108: "minecraft:brick_stairs",
    109: "minecraft:stone_brick_stairs",
    110: "minecraft:mycelium",
    111: "minecraft:waterlily",
    112: "minecraft:nether_brick",
    113: "minecraft:nether_brick_fence",
    114: "minecraft:nether_brick_stairs",
    115: "minecraft:nether_wart",
    116: "minecraft:enchanting_table",
    117: "minecraft:brewing_stand",
    118: "minecraft:cauldron",
    119: "minecraft:end_portal",
    120: "minecraft:end_portal_frame",
    121: "minecraft:end_stone",
    122: "minecraft:dragon_egg",
    123: "minecraft:redstone_lamp",
    124: "minecraft:lit_redstone_lamp",
    125: "minecraft:double_wooden_slab",
    126: "minecraft:wooden_slab",
    127: "minecraft:cocoa",
    128: "minecraft:sandstone_stairs",
    129: "minecraft:emerald_ore",
    130: "minecraft:ender_chest",
    131: "minecraft:tripwire_hook",
    132: "minecraft:tripwire",
    133: "minecraft:emerald_block",
    134: "minecraft:spruce_stairs",
    135: "minecraft:birch_stairs",
    136: "minecraft:jungle_stairs",
    137: "minecraft:command_block",
    138: "minecraft:beacon",
    139: "minecraft:cobblestone_wall",
    140: "minecraft:flower_pot",
    141: "minecraft:carrots",
    142: "minecraft:potatoes",
    143: "minecraft:wooden_button",
    144: "minecraft:skull",
    145: "minecraft:anvil",
    146: "minecraft:trapped_chest",
    147: "minecraft:light_weighted_pressure_plate",
    148: "minecraft:heavy_weighted_pressure_plate",
    149: "minecraft:unpowered_comparator",
    150: "minecraft:powered_comparator",
    151: "minecraft:daylight_detector",
    152: "minecraft:redstone_block",
    153: "minecraft:quartz_ore",
    154: "minecraft:hopper",
    155: "minecraft:quartz_block",
    156: "minecraft:quartz_stairs",
    157: "minecraft:activator_rail",
    158: "minecraft:dropper",
    159: "minecraft:stained_hardened_clay",
    160: "minecraft:stained_glass_pane",
    161: "minecraft:leaves2",
    162: "minecraft:log2",
    163: "minecraft:acacia_stairs",
    164: "minecraft:dark_oak_stairs",
    170: "minecraft:hay_block",
    171: "minecraft:carpet",
    172: "minecraft:hardened_clay",
    173: "minecraft:coal_block",
    174: "minecraft:packed_ice",
    175: "minecraft:double_plant"
}
_blockNameToID = dict( reversed( item ) for item in _blockIDtoName.items() )

#A world can have several dimensions.
#A dimension can have several regions.
#A region can have several chunks.
#A chunk has 16 sections (overall 16x256x16 blocks).
#Each section has 16x16x16 blocks.

#There are two Region formats:
#    .mcr: Minecraft Region (Minecraft Beta 1.3 - Minecraft 1.1)
#    .mca: Minecraft Anvil (Minecraft 1.2.1+)
#Region and Anvil are similar to one another but have a few notable differences.
#We currently support Minecraft Anvil.

#Region files are divided into 4KiB blocks called sectors.
#Region files start with an 8 KiB large header.
#The first 4 KiB consists of 1024 locations.
#Each location describes where within the region file a particular chunk can be found. Each location is 4 bytes long, and consists of two parts:
#    * Offset:
#      3-byte, big-endian unsigned(?) integer
#      The offset of the chunk within the file, in sectors.
#    * Size:
#      1-byte unsigned(?) integer
#      The size of the chunk, in sectors.
#If a location's offset and size are both 0, the chunk has not been generated yet.
#The remaining 4 KiB consists of 1024 timestamps.
#Each timestamp is a 4-byte, big-endian unsigned(?) integer recording the time a particular chunk last updated (in seconds since the unix epoch).
#This can be used to get a human readable date/time:
#    str( datetime.fromtimestamp( timestamp ) )
#The index of chunk with chunk coordinates (x,z) can be calculated with the following formula:
#    i=(x%32)+(z%32)*32.
#Conversely, the chunk coordinates (x,z) of a chunk with index i can be calculated like so, where rx and rz are the region coordinates of this region:
#    z,x = divmod(i,32)
#    x += rx * 32
#    z += rz * 32
#The offset of chunk i's location is calculated like so:
#    loff = i*4
#Similarly, for the timestamp:
#    toff = 4096+i*4
#Chunks are stored as compressed NBT files.
#At the start of each chunk is a 5 byte header consisting of two parts:
#    * Size:
#      4-byte, big-endian unsigned(?) integer
#      The size of the compressed file, in bytes.
#    * Compression:
#      1-byte unsigned(?) integer
#      How the chunk is compressed. 1 = gzip, 2 = zlib.
#      See COMPRESSION_* enums above.

#Unfortunately a given player's last known name doesn't seem to be cached anywhere.
#Here we can request it from the Mojang API:
def uuidToUsername( uuid ):
    """
    Look up a player's name given their uuid.
    uuid is expected to be a UUID string without dashes.
    """
    #Note: See documentation on Mojang API: http://wiki.vg/Mojang_API
    with urllib.request.urlopen( "https://sessionserver.mojang.com/session/minecraft/profile/" + uuid ) as res:
        return json.loads( res.read().decode() )["name"]

def setMinecraftDir( path ):
    """
    Sets the path returned by getMinecraftPath().
    """
    global _mcPath
    _mcPath = path

def getDefaultMinecraftDir():
    """
    Return the default Minecraft directory for this operating system.
    Raise an Exception if the operating system is not supported.
    JNBT supports Windows, Linux, and Mac OS X.
    """
    name = sys.platform
    if   name == "win32":
        return os.path.join( os.environ["appdata"], ".minecraft" )
    elif name == "linux":
        return os.path.expanduser( os.path.join( "~", ".minecraft" ) )
    elif name == "darwin": #Mac OS X
        return os.path.expanduser( os.path.join( "~", "Library", "Application Support", "minecraft" ) )
    else:
        raise Exception( "Cannot find .minecraft directory; unsupported operating system." )

def getMinecraftPath( *args ):
    """
    Return the path to the Minecraft installation directory.
    If this path has not manually been set with setMinecraftDir(), sets it to the default installation path for the current operating system.

    If any positional arguments are given, returns the path resulting from joining the Minecraft installation directory and the given arguments.
    For example, on Windows:
        jnbt.getMinecraftPath( "saves", "New World" )
        "C:\\Users\\<your username>\\AppData\\Roaming\\.minecraft\\saves\\New World"
    """
    if _mcPath == None:
        setMinecraftDir( getDefaultMinecraftDir() )
    return os.path.join( _mcPath, *args )

def nibble( ba, idx ):
    """
    Returns the nibble (a 4-bit value in the range [0,15]) in the given byte array, ba, at the given index, idx.
    Note: idx is a nibble index, not a byte index. A single byte stores two nibbles, so for a byte array with 2048 bytes, there are 4096 nibbles.
    This function assumes little-endian ordering of nibbles within the bytes they're stored in:
        Byte index:        0        1
                       uuuullll uuuullll  ...
        Nibble index:    1   0    3   2
    """
    #Note: bytearray has unsigned bytes in range [0,255]
    return ( ba[idx//2] & 0x0F ) if (idx & 1) == 0 else ( ba[idx//2] >> 4 )

def _readChunks( file, region ):
    """
    Reads chunks from the given readable file-like object, file.
    Returns a Chunk list sorted by offset in ascending order.
    """

    #Map of regional index -> chunk
    i2c = {}

    #Read locations and timestamps
    locations  = _ruis( file, 1024 )
    timestamps = _ruis( file, 1024 )

    for i in range( 1024 ):
        loc = locations[i]
        
        if loc == 0:
            continue

        offset    = 4096 * ( ( loc & 0xFFFFFF00 ) >> 8 )
        allocsize = 4096 * ( ( loc & 0x000000FF )      )

        z,x = divmod( i, 32 )
        
        c = Chunk(
            32 * region.x + x,
            32 * region.z + z,
            x,
            z,
            offset,
            allocsize,
            timestamps[ i ],
            None,
            None,
            None,
            region
        )

        i2c[i] = c

    #Return a list of chunks sorted by offset (so we're always reading in a forward direction)
    return sorted( i2c.values(), key=lambda c: c.offset )

def _getBlockIDWithAdd( index, blocks, add ):
    return blocks[index] + ( nibble( add, index ) << 8 )
def _getBlockIDWithoutAdd( index, blocks, add ):
    return blocks[index]

class World:
    """
    Represents an entire Minecraft world.
    A world consists of several dimensions (such as the Overworld, Nether, and The End), and global metadata (level.dat, player saves, etc).
    """
    __slots__ = ( "path", "_dimensions", "_leveldata", "_blockIDtoName", "_blockNameToID", "_players" )

    def __init__( self, path ):
        """
        Constructor.
        path is the path to the world's directory.
        """
        self.path           = os.path.abspath( path )
        self._dimensions    = None
        self._leveldata     = None
        self._blockIDtoName = None
        self._blockNameToID = None
        self._players       = None

    def iterDimensions( self ):
        """Iterates over every dimension in this world."""
        #DIM0 is the overworld; its directory is the world directory.
        path = self.path
        if not os.path.isdir( path ):
            return

        yield Dimension( 0, path, self )

        for entry in os.scandir( path ):
            if entry.is_dir():
                name = entry.name.upper()
                if name.startswith( "DIM" ):
                    try:
                        #Parse dimension ID from folder name
                        i = int( name[3:] )
                    except ValueError:
                        pass
                    else:
                        #Ignore directories in the world directory called "DIM0".
                        #This is typically created by mods that wrongly assume the overworld's directory.
                        if i != 0:
                            yield Dimension( i, entry.path, self )

    def iterRegions( self ):
        """Iterates over every region in every dimension in this world."""
        for dimension in self.iterDimensions():
            yield from dimension.iterRegions()

    def iterChunks( self, content=True ):
        """
        Iterates over every chunk in every region in every dimension in this world.
        See help( jnbt.Region.getChunk ) for information on content.
        """
        for dimension in self.iterDimensions():
            yield from dimension.iterChunks( content )

    def iterBlocks( self ):
        """Iterates over every block in every chunk in every region in every dimension in this world."""
        for dimension in self.iterDimensions():
            yield from dimension.iterBlocks()

    def iterPlayers( self ):
        """Iterates over every player who has played in this world."""
        path = os.path.join( self.path, "playerdata" )
        if not os.path.isdir( path ):
            return
        for entry in os.scandir( path ):
            match = PD_RE.fullmatch( entry.name )
            if match:
                yield Player( "".join( match.groups() ), tag.read( entry.path ) )

    def getDimension( self, id ):
        """
        Return the dimension with the given ID, or None if this dimension doesn't exist.
        id is expected to be an int.

        If you're getting a vanilla dimension, can use the jnbt.DIM_* enums for more readable code:
            world.getDimension( jnbt.DIM_OVERWORLD )
        """
        #Return the cached Dimension object, if any
        dims = self._dimensions
        if dims is None:
            self._dimensions = dims = {}
        else:
            d = dims.get( id )
            if d is not None:
                return d

        #Check if this world has a dimension with this id
        path = os.path.join( self.path, "DIM{:d}".format( id ) ) if id != 0 else self.path
        if not os.path.isdir( path ):
            return None

        #Create a new Dimension object, cache it, then return it
        d = Dimension( id, path, self )
        dims[id] = d
        return d

    def getDimensions( self ):
        """
        Return a dictionary of dimensions in this world keyed by dimension ID.
        """
        dimensions = self._dimensions
        if dimensions is None:
            dimensions = {}
        
            for d in self.iterDimensions():
                dimensions[d.id] = d

            self._dimensions = dimensions
        return dimensions
    dimensions = property( getDimensions )

    def getLevelData( self ):
        """Return this world's level.dat as a NBTDocument."""
        ld = self._leveldata
        if ld is None:
            ld = tag.read( os.path.join( self.path, "level.dat" ) )
            self._leveldata = ld
        return ld
    leveldata = property( getLevelData )

    def getBlockName( self, id ):
        """
        Returns the internal name of a block with the given id, or None if this world does not contain block information.

        This function may be expensive the first time it is called because it must load the world's leveldata and create id<->name dictionaries.
        """
        bIDtoN = self._blockIDtoName
        if bIDtoN is None:
            bIDtoN = {}
            bNtoID = {}

            #Load the level.dat for this world.
            #If this is a modded world, we can get names for blocks and items from FML.ItemData
            tag = self.getLevelData()
            if tag is not None:
                tag = tag.rget("FML", "ItemData")
                if tag is not None:
                    for entry in tag:
                        #Key is the internal name of the block/item, prepended with "\x01" for blocks and "\x02" for items
                        key = str( entry["K"] )
                        if key.startswith( "\x01" ):
                            key = key[1:]
                            value = int( entry["V"] )
                            bIDtoN[ value ] = key
                            bNtoID[ key   ] = value

            self._blockIDtoName = bIDtoN
            self._blockNameToID = bNtoID
        return bIDtoN[ id ]

    def getPlayers( self ):
        """Return a dictionary of playerdata (sorted by uuid) for all players that have played on this world."""
        players = self._players
        if players is None:
            players = {}
            for p in self.iterPlayers():
                players[ p.uuid ] = p
            self._players = players
        return players
    players = property( getPlayers )

    def __getitem__( self, index ):
        """Handles world[id]. Equivalent to world.getDimension( id )."""
        return self.getDimension( index )

    def __repr__( self ):
        return "World('{}')".format( self.path )

class Dimension:
    """
    Represents a dimension.
    A dimension consists of a sparsely populated, practically infinite grid of regions.
    """
    __slots__ = ( "id", "path", "world", "_regions" )

    def __init__( self, id, path, world ):
        """
        Constructor.
        path is the path to the dimension's directory.
        """
        self.id       = id
        self.path     = path
        self.world    = world
        self._regions = None

    def iterRegions( self ):
        """Iterates over every region in this dimension."""
        path = os.path.join( self.path, "region" )
        if not os.path.isdir( path ):
            return
        for entry in os.scandir( path ):
            if entry.is_file():
                match = MCA_RE.fullmatch( entry.name )
                if match:
                    yield Region(
                        int( match.group( 1 ) ),
                        int( match.group( 2 ) ),
                        entry.path,
                        self
                    )

    def iterChunks( self, content=True ):
        """
        Iterates over every chunk in every region in this dimension.
        See help( jnbt.Region.getChunk ) for information on content.
        """
        for region in self.iterRegions():
            yield from region.iterChunks( content )

    def iterBlocks( self ):
        """Iterates over every block in every chunk in every region in this dimension."""
        for region in self.iterRegions():
            yield from region.iterBlocks()

    def getRegion( self, rx, rz ):
        """
        Returns the region in this dimension with the given region coordinates, (rx, rz).
        Returns None if there is no region with these coordinates.
        """
        #Return the cached region object, if any
        regions = self._regions
        if regions is None:
            self._regions = regions = {}
        else:
            r = self._regions.get( ( rx, rz ) )
            if r is not None:
                return r

        #Check if the world has a region with this ID
        path = os.path.join( self.path, "region", "r.{:d}.{:d}.mca".format( rx, rz ) )
        if not os.path.isfile( path ):
            return None

        #Create a new Region object, cache it, then return it
        r = Region( rx, rz, path, self )
        regions[ rx, rz ] = r
        return r

    def getChunk( self, cx, cz, content=True ):
        """
        Returns the chunk in this dimension with the given chunk coordinates, (cx, cz).
        Returns None if there is no chunk with these coordinates.
        See help( jnbt.Region.getChunk ) for information on content.
        """
        rx, cx = divmod( cx, 32 )
        rz, cz = divmod( cz, 32 )
        region = self.getRegion( rx, rz )
        if region is None:
            return None
        return region.getChunk( cx, cz, content )

    def getBlock( self, x, y, z ):
        """
        Returns the block in this dimension at the given block coordinates, (x, y, z).
        Returns None if there is no block at these coordinates.
        """
        cx,  x = divmod(  x, 16 )
        cz,  z = divmod(  z, 16 )
        rx, cx = divmod( cx, 32 )
        rz, cz = divmod( cz, 32 )
        region = self.getRegion( rx, rz )
        if region is None:
            return None
        chunk = region.getChunk( cx, cz )
        if chunk is None:
            return None
        return chunk.getBlock( x, y, z )

    def getBiome( self, x, z ):
        """
        Returns the biome ID in this dimension at the given block coordinates, (x, z).
        Returns None if there is no chunk at these coordinates.
        """
        cx,  x = divmod(  x, 16 )
        cz,  z = divmod(  z, 16 )
        rx, cx = divmod( cx, 32 )
        rz, cz = divmod( cz, 32 )
        region = self.getRegion( rx, rz )
        if region is None:
            return None
        chunk = region.getChunk( cx, cz )
        if chunk is None:
            return None
        return chunk.getBiome( x, z )

    def getRegions( self ):
        """Returns a dictionary of regions keyed by region coordinates."""
        regions = self._regions
        if regions is None:
            regions = {}
            for r in self.iterRegions():
                regions[r.x, r.z] = r
            self._regions = regions
        return regions
    regions = property( getRegions )

    def __getitem__( self, index ):
        """Handles dimension[x,z]. Equivalent to dimension.getRegion( x, z )."""
        return self.getRegion( *index )

    def __repr__( self ):
        return "Dimension({:d},'{}')".format( self.id, self.path )




class Region:
    """
    Represents a region.
    A region consists of a sparsely populated 32x32 grid of chunks.
    Overall, a region encompasses a 512x256x512 block area.
    """
    __slots__ = ( "x", "z", "path", "dimension", "_chunks" )

    def __init__( self, rx, rz, path, dimension ):
        """
        Constructor.
        rx and rz are the region coordinates.
        path is the path to the region's Minecraft Anvil (mca) file.
        dimension is a reference to the dimension this region is a part of.
        """
        #Region x and z coordinates
        self.x = rx
        self.z = rz

        self.path = path
        self.dimension = dimension

        self._chunks = None  #Cached chunks

    def getWorld( self ):
        """Return the world this region belongs to."""
        r = self.dimension
        if r is not None:
            return r.world
    world = property( getWorld )

    def iterChunks( self, content=True ):
        """
        Iterates over every chunk in this region.
        See help( jnbt.Region.getChunk ) for information on content.
        """
        with open( self.path, "rb" ) as file:
            chunks = _readChunks( file, self )

            if content:
                for c in chunks:
                    c._read( file )
                    yield c
            else:
                yield from chunks

    def iterBlocks( self ):
        """Iterates over every block in every chunk in this region."""
        for chunk in self.iterChunks():
            yield from chunk.iterBlocks()

    def getChunk( self, cx, cz, content=True ):
        """
        Returns the chunk with the given chunk coordinates relative to this region, (cx, cz).
        Returns None if there is no chunk with these coordinates.
        cx and cz are expected to be in the range [0,31].
        If content is True, read the chunk contents into an NBTDocument and include it in the returned Chunk.
            Reading chunk contents is an expensive operation, so if you don't plan to use them, give False for this argument.
            Defaults to True.
        """
        chunks = self._chunks
        if chunks is None:
            self._chunks = chunks = {}
        else:
            c = chunks.get( ( cx, cz ) )
            if c is not None:
                if content and c.nbt is None:
                    with open( self.path, "rb" ) as file:
                        c._read( file )
                return c
        
        #Read, cache, and return the chunk
        with open( self.path, "rb" ) as file:
            i4 = 4*(cx + 32*cz)

            #Read location
            file.seek( i4, os.SEEK_SET )
            loc = _rui( file )
            if loc == 0:
                return None

            offset     = 4096 * ( ( loc & 0xFFFFFF00 ) >> 8 )
            allocsize = 4096 * ( ( loc & 0x000000FF )      )

            #Read timestamp
            file.seek( 4096 + i4, os.SEEK_SET )
            timestamp = _rui( file )

            #Read chunk header
            c = Chunk(
                32 * self.x + cx,
                32 * self.z + cz,
                cx,
                cz,
                offset,
                allocsize,
                timestamp,
                None,
                None,
                None,
                self
            )
            if content:
                c._read( file )
            
        chunks[ cx, cz ] = c
        return c

    def getChunks( self, content=True ):
        """
        Returns a dictionary of chunks in this region keyed by chunk coordinates relative to this region, (cx, cz).
        cx and cz will be in the range [0,31].
        See help( jnbt.Region.getChunk ) for information on content.
        """
        pass

    def __getitem__( self, index ):
        """Handles region[x,z]. Equivalent to region.getChunk( x, z )."""
        return self.getChunk( *index )

    def __repr__( self ):
        return "Region({:d}, {:d}, '{}')".format( self.x, self.z, self.path )

class Chunk:
    """
    Represents a chunk.
    Chunks are (typically zlib compressed) NBT documents stored within Minecraft Anvil (.mca) regions.
    A chunk consists of a sparsely populated column of up to 16 sections (i.e. 1x16x1 sections).
    Each section contains 16x16x16 blocks. Overall, each chunk contains 16x256x16 blocks.
    Chunks also contain non-block data related to the chunk, for example save data for entities and tile entities within their bounds.
    """
    __slots__ = ( "x", "z", "lx", "lz", "offset", "allocsize", "timestamp", "size", "compression", "nbt", "region", "_tileEntities" )

    def __init__( self, cx=None, cz=None, lx=None, lz=None, offset=None, allocsize=None, timestamp=None, size=None, compression=None, nbt=None, region=None ):
        """
        Constructor.
        cx and cz are absolute chunk coordinates.
        region is a reference to the region this chunk is a part of.
        """
        self.x           = cx           #Absolute chunk X/Z coordinates
        self.z           = cz
        self.lx          = lx           #Region-local chunk X/Z coordinates
        self.lz          = lz
        self.offset      = offset       #Chunk header starts at this offset in bytes
        self.allocsize   = allocsize    #Allocated space for chunk in bytes
        self.timestamp   = timestamp    #Timestamp (seconds since unix epoch)
        self.size        = size         #Size of compressed chunk contents in bytes
        self.compression = compression  #Compression type (1=gzip, 2=zlib)
        self.nbt         = nbt          #An NBTDocument containing the contents of the chunk.
        self.region      = region       #Reference to the region this chunk is a part of

        self._tileEntities = None

    def getDimension( self ):
        """Returns the dimension this chunk belongs to."""
        r = self.region
        if r is not None:
            return r.dimension
    dimension = property( getDimension )

    def getWorld( self ):
        """Returns the world this chunk belongs to."""
        r = self.region
        if r is not None:
            r = r.dimension
            if r is not None:
                return r.world
    world = property( getWorld )

    def getTileEntities( self ):
        """
        Returns a dictionary of all tile entities in this chunk.
        Each key will be a tuple of absolute block coordinates, (x,y,z).
        Each value will be a TAG_Compound containing the named tags: x, y, z, id.
        """
        tileEntities = self.tileEntities
        if tileEntities is None:
            tileEntities = self._initTileEntities()
        return tileEntities
    tileEntities = property( getTileEntities )

    def getTileEntity( self, x, y, z ):
        """
        Returns the tile entity at the given block coordinates, (x, y, z).
        Returns None if there is no tile entity at these coordinates
        """
        tileEntities = self._tileEntities
        if tileEntities is None:
            tileEntities = self._initTileEntities()
        return tileEntities.get( ( x, y, z ) )

    def iterBlocks( self ):
        """
        Generator that iterates over every block in this chunk.
        For each block, yields a Block() describing it.
        """
        #Reuse the same Block() instance to avoid performance penalty of repeated Block#__init__() calls.
        block = Block( self )
        for section in self.nbt["Level"]["Sections"]:
            baseY = 16 * int( section["Y"] )
            add = section.get("Add")
            sectionData = (
                baseY,
                section["Blocks"],
                add,
                _getBlockIDWithAdd if add else _getBlockIDWithoutAdd,
                section["Data"],
                section["BlockLight"],
                section["SkyLight"]
            )
            block._s = sectionData
            for i in range( 1024 ):
                block._i = i
                yield block

    def getBiome( self, x, z ):
        """
        Returns the biome ID at block coordinates ( x, z ) relative to the chunk.
        x and z are expected to be in the range [0,15].
        """
        return self.nbt["Level"]["Biomes"][16 * z + x]

    def getBlock( self, x, y, z ):
        """
        Returns data about the block at block coordinates (x, y, z) relative to the chunk.
        x and z are expected to be in the range [0,15].
        y is expected to be in the range [0,255].
        Returns a Block() describing the block at that position.
        """
        for section in self.nbt["Level"]["Sections"]:
            baseY = 16 * int( section["Y"] )
            if y >= baseY and y < baseY + 16:
                add = section.get("Add")
                sectionData = (
                    baseY,
                    section["Blocks"],
                    add,
                    _getBlockIDWithAdd if add else _getBlockIDWithoutAdd,
                    section["Data"],
                    section["BlockLight"],
                    section["SkyLight"]
                )
                return Block( self, sectionData, 256*(y-baseY) + 16*z + x )
        return None

    def _read( self, file ):
        """Read chunk contents from the given readable file-like object, file."""
        #Read chunk header
        file.seek( self.offset, os.SEEK_SET )
        
        size        = _rui( file ) - 1
        compression = _rub( file )

        if compression == 2:
            #TODO: Don't read entire file into memory; use zlib decompression objects
            source = BytesIO( zlib.decompress( _r( file, size ) ) )
        elif compression == 1:
            source = gzip.GzipFile( fileobj=file )
        else:
            raise NBTFormatError( "Unrecognized compression type: {:d}.".format( compression ) )

        #Read chunk data
        nbt = tag.read( source, None )

        self.size        = size
        self.compression = compression
        self.nbt         = nbt

    def _free( self ):
        """Clear loaded chunk contents."""
        self.nbt = None

    def _initTileEntities( self ):
        te = {}
        for tag in self.nbt["Level"]["TileEntities"]:
            te[int(tag["x"]),int(tag["y"]),int(tag["z"])] = tag
        self._tileEntities = te
        return te

    def __getitem__( self, index ):
        """Handles chunk[x,y,z]. Equivalent to chunk.getBlock( x, y, z )."""
        return self.getBlock( *index )

    def __repr__( self ):
        return "Chunk({:d}, {:d})".format( self.x, self.z )

class Block:
    """
    Contains detailed information about a particular block in the world.
    Block has several attributes:
    * x,y, and z store the position of the block in absolute block coordinates.
    * id is the numeric ID of the block, an int in the range [0, 4095].
    * name is the internal name of the block, a string such as "minecraft:iron_ore".
      The block name is determined by looking up the block ID in the leveldata for the world this block belongs to (if it exists).
      Otherwise, we look it up in our built-in block ID -> internal name dictionary.
      Failing both of these things, name will be None.
    * meta is the metadata value of the block. For blocks with variations like wool, metadata indicates the particular variation. For all other blocks, this is usually 0.
    * blockLight and skyLight indicate how much light from light-emitting blocks and the sky (respectively) are reaching this block space. Both are ints in the range [0, 15].
    * light is the sum of blockLight and skyLight, clamped to the range [0, 15].
    * tileEntity is the TAG_Compound for this block's tile entity, or None if this block is not a tile entity
    * chunk, region, dimension, and world are references to the chunk, region, dimension, and world that contains this block.
    """
    __slots__ = ( "chunk", "_s", "_i" )

    def __init__( self, chunk = None, sectionData = None, index = None ):
        self.chunk = chunk       #Chunk containing this block
        self._s    = sectionData #Data relating to the section containing this block
        self._i    = index       #Index of this block within the section
    
    def getPos( self ):
        y, index = divmod( self._i, 256 )
        z, x = divmod( index, 16 )
        c = self.chunk
        pos = (
            16 * c.x   + x,
            self._s[0] + y,
            16 * c.z   + z
        )
        return pos
    pos = property( getPos )

    def getX( self ):
        return 16 * self.chunk.x + ( self._i & 15 )
    x = property( getX )
    
    def getY( self ):
        return self._s[0] + ( self._i // 256 )
    y = property( getY )

    def getZ( self ):
        return 16 * self.chunk.z + ( ( self._i & 255 ) // 16 )
    z = property( getZ )

    def getID( self ):
        s = self._s
        return s[3]( self._i, s[1], s[2] )
    id = property( getID )

    def getName( self ):
        """
        Return the name of the block, or None if not recognized.
        e.g. "minecraft:iron_ore"
        """
        #Get name from leveldata if possible
        r = self.getWorld()
        if r is not None:
            r = r.getBlockName( self.id )
            if r is not None:
                return r
        #Get name from built-in Minecraft mappings if possible
        return _blockIDtoName.get( self.id )
    name  = property( getName )

    def getMeta( self ):
        return nibble( self._s[4], self._i )
    meta = property( getMeta )

    def getBlockLight( self ):
        return nibble( self._s[5], self._i )
    blockLight = property( getBlockLight )

    def getSkyLight( self ):
        return nibble( self._s[6], self._i )
    skyLight = property( getSkyLight )

    def getLight( self ):
        """Return the light level at this block's position."""
        return min( 15, self.blockLight + self.skyLight )
    light = property( getLight )

    def getTileEntity( self ):
        return self.chunk.getTileEntity( *self.getPos() )
    tileEntity = property( getTileEntity )

    def getRegion( self ):
        """Returns the region this block is a part of."""
        r = self.chunk
        if r is not None:
            return r.region
    region = property( getRegion )

    def getDimension( self ):
        """Returns the dimension this block is a part of."""
        r = self.chunk
        if r is not None:
            r = r.region
            if r is not None:
                return r.dimension
    dimension = property( getDimension )

    def getWorld( self ):
        """Returns the world this block is a part of."""
        r = self.chunk
        if r is not None:
            r = r.region
            if r is not None:
                r = r.dimension
                if r is not None:
                    return r.world
    world = property( getWorld )

    def __repr__( self ):
        return "Block({:d},{:d},{:d},{:d},{:d})".format( self.x, self.y, self.z, self.id, self.meta )

class Player:
    """
    Represents a player.
    uuid is the player's uuid.
    nbt is the player's save file.
    """
    slots = ( "uuid", "nbt", "_name" )
    def __init__( self, uuid, name=None, nbt=None ):
        self.uuid  = uuid
        self.nbt   = nbt
        self._name = name

    def getName( self ):
        """
        Returns the player's name.
        If we don't already have it, this will fetch the player's name through the Mojang API.
        """
        name = self._name
        if name is None:
            name = uuidToUsername( self.uuid )
            self._name = name
        return name
    name = property( getName )

    def __repr__( self ):
        return "Player('{}')".format( self.uuid )

class FileSlice:
    """Wrapper around a file that restricts reads/writes to the range described by the given offset/length"""
    def __init__( self, file, offset, length ):
        self.file = file
        self._o = offset
        self._l = length
        self._p = 0
    def read( self, size=-1 ):
        self.file.read( size )
    def write( self ):
        self.file.write()