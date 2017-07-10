#This module contains code common to both the mcr and mca formats.

import os
import os.path
import zlib
import re
from io import BytesIO

from jnbt           import tag
from jnbt.shared    import scandir, read as _r, readUnsignedByte as _rub, readUnsignedInt as _rui, readUnsignedInts as _ruis
from jnbt.mc.data   import _blockIDtoName
from jnbt.mc.player import Player

#Regular expression that matches player save files in <world>/playerdata; i.e. filenames of the form "{8}-{4}-{4}-{4}-{12}.dat", where {n} is a grouping of bytes that makes up the player's UUID, expressed as n hex digits.
RE_PLAYERDATA_FILE = re.compile( "^([0-9a-f]{8})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{12})\.dat$", re.IGNORECASE )
#Regular expression that matches player save files in <world>/players; i.e. filenames of the form "{name}.dat", where name is the player's name
RE_PLAYERS_FILE    = re.compile( "^(.+)\.dat$", re.IGNORECASE )

#Compression types
COMPRESSION_NONE = 0
COMPRESSION_GZIP = 1
COMPRESSION_ZLIB = 2

#Level format enums
#We only support region and anvil but others are listed in case I want to support those in the future
LVLFMT_CLASSIC = 0
LVLFMT_INDEV   = 1
LVLFMT_ALPHA   = 2
LVLFMT_REGION  = 3
LVLFMT_ANVIL   = 4

#Maps LVLFMT_* enums to names
LVLFMT_TO_NAME = (
    "classic",
    "indev",
    "alpha",
    "region",
    "anvil"
)

#A world can have several dimensions.
#A dimension can have several regions.
#A region can have several chunks.
#A chunk has 16 sections (overall 16x256x16 blocks).
#Each section has 16x16x16 blocks.

#There are two Region formats:
#    .mcr: Minecraft Region (Minecraft Beta 1.3 - Minecraft 1.1)
#    .mca: Minecraft Anvil (Minecraft 1.2.1+)
#Region and Anvil are similar to one another but have a few notable differences.

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

#Returns the nibble (a 4-bit value in the range [0,15]) in the given byte array, b, at the given index, i.
#Note: i is a nibble index, not a byte index. A single byte stores two nibbles, so for a byte array with 2048 bytes, there are 4096 nibbles.
#This function assumes little-endian ordering of nibbles within the bytes they're stored in:
#    Byte index:        0        1
#                   uuuullll uuuullll  ...
#    Nibble index:    1   0    3   2
def _n( b, i ):
    #Note: bytearray has unsigned bytes in range [0,255]
    return ( b[i//2] & 0x0F ) if (i & 1) == 0 else ( b[i//2] >> 4 )




class _BaseWorld:
    """
    Represents an entire Minecraft world.
    A world consists of several dimensions (such as the Overworld, Nether, and The End), and global metadata (level.dat, player saves, etc).
    """
    __slots__ = ( "path", "_dimensions", "_leveldata", "_blockIDtoName", "_blockNameToID", "_players" )

    #Subclasses should override these
    formatid = None
    format   = None
    _clsDimension = None

    def __init__( self, path ):
        """
        Constructor.
        path is the path to the world's directory.
        """
        self.path           = path
        self._dimensions    = None
        self._leveldata     = None
        self._blockIDtoName = None
        self._blockNameToID = None
        self._players       = None

    def iterDimensions( self ):
        """Iterates over every dimension in this world."""
        path = self.path
        if not os.path.isdir( path ):
            return

        #DIM0 is the overworld; its directory is the world directory.
        clsDimension = self._clsDimension
        yield clsDimension( path, self, 0 )

        #For non-overworld dimensions, scan the world directory for directories named "DIM{id}", where id is the dimension's ID (e.g. DIM-1, DIM1, etc).
        #TODO: This won't catch all dimension folders; unfortunately, some mods don't follow this naming scheme (e.g. Dimensional Doors, The Tropics, etc).
        #A better implementation would select directories that contain a "region" directory, which in turn contains at least one .mca/.mcr file.
        #The only problem with this approach is that the dimension's ID isn't necessarily derivable from the name of its directory (e.g. The Tropics uses "TROPICS" as the directory name for its dimension).
        #We'd probably need to read that information from a data dump, which would need to be separately generated in-game by a mod.
        for entry in scandir( path ):
            if entry.is_dir():
                name = entry.name.upper()
                if name.startswith( "DIM" ):
                    try:
                        #Parse dimension ID from folder name
                        i = int( name[3:] )
                    except ValueError:
                        pass
                    else:
                        #Ignore the "DIM0" directory if it exists;
                        #This is typically created by mods that wrongly assume the overworld's directory.
                        if i != 0:
                            yield clsDimension( entry.path, self, i )

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

    def iterPlayers( self, playerdata=True, players=True ):
        """
        Iterates over every player who has played in this world.
        playerdata is an optional boolean that defaults to True.
            If this is True, we will iterate over player save files in the playerdata/ directory if it exists.
            Otherwise this directory will be skipped.
        players is an optional boolean that defaults to True.
            If this is True, we will iterate over player save files in the player/ directory if it exists.
            Otherwise this directory will be skipped.
        """
        #NOTE: The same player may be iterated over multiple times (e.g. converted worlds).
        #      Ideally the same player should only be iterated over once, but there may not be a reliable way of determining if two files represent the same player.

        #Search <world>/playerdata/
        if playerdata:
            path = os.path.join( self.path, "playerdata" )
            if os.path.isdir( path ):
                for entry in scandir( path ):
                    match = RE_PLAYERDATA_FILE.fullmatch( entry.name )
                    if match:
                        yield Player( entry.path, uuid="".join( match.groups() ) )
        #Search <world>/players/
        if players:
            path = os.path.join( self.path, "players" )
            if os.path.isdir( path ):
                for entry in scandir( path ):
                    match = RE_PLAYERS_FILE.fullmatch( entry.name )
                    if match:
                        yield Player( entry.path, name=match.group(1) )

    def getDimension( self, id ):
        """
        Return the dimension with the given ID, or None if this dimension doesn't exist.
        id is expected to be an int.

        If you're getting a vanilla dimension, you can use the jnbt.DIM_* enums for more readable code:
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
        d = self._clsDimension( path, self, id )
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
            path = os.path.join( self.path, "level.dat" )
            if os.path.isfile( path ):
                self._leveldata = ld = tag.read( path )
            else:
                return None
        return ld
    leveldata = property( getLevelData )

    def getBlockName( self, id ):
        """
        Returns the internal name of a block with the given id or None if this cannot be determined.
        None may be returned if the world lacks block information, or if a block with that ID couldn't be found in the block information.

        This function may be expensive the first time it is called because it must load the world's leveldata and create id<->name dictionaries.
        """
        bIDtoN = self._blockIDtoName
        if bIDtoN is None:
            bIDtoN = {}
            bNtoID = {}

            #Load the level.dat for this world.
            #If this is a modded world, we can get names for blocks and items from FML.ItemData
            tag = self.getLevelData()
            if tag is None:
                return None
            tag = tag.rget("FML", "ItemData")
            if tag is None:
                return None
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
        return bIDtoN.get( id )

    def getSPPlayer( self ):
        """Returns the singleplayer player, or None if the world isn't a singleplayer world."""
        spnbt=self.getLevelData().rget( "Data", "Player" )
        if spnbt is not None:
            return Player( nbt=spnbt )

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

    #Handles iter( world ). Equivalent to world.iterDimensions().
    #Allows use of this class in a for loop like so:
    #   for dimension in world:
    #       ...
    __iter__ = iterDimensions

    #Handles world[id]. Equivalent to world.getDimension( id ).
    __getitem__ = getDimension

    def __repr__( self ):
        return "World('{}')".format( self.path )




class _BaseDimension:
    """
    Represents a dimension.
    A dimension consists of a sparsely populated, practically infinite grid of regions.
    """
    __slots__ = ( "id", "path", "world", "_regions" )

    #Subclasses should override these
    formatid     = None
    format       = None
    _clsRegion   = None
    _reFilename  = None
    _fmtFilename = None

    def __init__( self, path, world, id=None ):
        """
        Constructor.
        path is the path to the dimension's directory.
        world is the World this dimension is a part of.
        id is the dimension's id
        """
        self.path     = path
        self.world    = world
        self.id       = id
        self._regions = None

    def iterRegions( self ):
        """Iterates over every region in this dimension."""
        path = os.path.join( self.path, "region" )
        if not os.path.isdir( path ):
            return

        reFilename = self._reFilename
        clsRegion  = self._clsRegion

        for entry in scandir( path ):
            if entry.is_file():
                match = reFilename.fullmatch( entry.name )
                if match:
                    yield clsRegion(
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
        #If so, create a new Region object, cache it, then return it.
        path = os.path.join( self.path, "region", self._fmtFilename.format( rx, rz ) )
        if os.path.isfile( path ):
            regions[ rx, rz ] = r = self._clsRegion( rx, rz, path, self )
            return r
        else:
            return None

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

    #Handles iter( dimension ). Equivalent to dimension.iterRegions().
    #Allows use of this class in a for loop like so:
    #    for region in dimension:
    #        ...
    __iter__ = iterRegions

    def __repr__( self ):
        return "Dimension('{}',id={})".format( self.path, self.id )




class _BaseRegion:
    __slots__ = ( "x", "z", "path", "dimension", "_chunks", "_length" )

    #Subclasses should override these
    formatid  = None
    format    = None
    _clsChunk = None

    def __init__( self, rx, rz, path, dimension ):
        """
        Constructor.
        rx and rz are the region coordinates.
        path is the path to the region's file.
        dimension is a reference to the dimension this region is a part of.
        """
        #Region x and z coordinates
        self.x = rx
        self.z = rz

        self.path = path
        self.dimension = dimension

        self._chunks = None  #Cached chunks
        self._length = None  #Number of chunks in this region

    def getWorld( self ):
        """Return the world this region belongs to."""
        r = self.dimension
        if r is not None:
            return r.world
    world = property( getWorld )

    def _readChunks( self, file ):
        """
        Reads chunks from the given readable file-like object, file.
        Returns a _clsChunk list sorted by offset in ascending order.
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

            c = self._clsChunk(
                32 * self.x + x,
                32 * self.z + z,
                x,
                z,
                offset,
                allocsize,
                timestamps[ i ],
                None,
                None,
                None,
                self
            )

            i2c[i] = c

        #Return a list of chunks sorted by offset (so we're always reading in a forward direction)
        return sorted( i2c.values(), key=lambda c: c.offset )

    def iterChunks( self, content=True ):
        """
        Iterates over every chunk in this region.
        See help( jnbt.Region.getChunk ) for information on content.
        """
        with open( self.path, "rb" ) as file:
            chunks = self._readChunks( file )

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

            offset    = 4096 * ( ( loc & 0xFFFFFF00 ) >> 8 )
            allocsize = 4096 * ( ( loc & 0x000000FF )      )

            #Read timestamp
            file.seek( 4096 + i4, os.SEEK_SET )
            timestamp = _rui( file )

            #Read chunk header
            c = self._clsChunk(
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
        chunks = self._chunks
        if chunks is None:
            chunks = {}
            for c in self.iterChunks():
                chunks[c.x,c.z] = c
            self._chunks = chunks
        return chunks

    def __len__( self ):
        """
        Returns the number of chunks in this region.
        Returns an int in the range [0, 1024].
        """
        l = self._length
        if l is None:
            l = 0
            with open( self.path, "rb" ) as file:
                locations  = _ruis( file, 1024 )
                for location in locations:
                    if location != 0:
                        l += 1
            self._length = l
        return l

    def __getitem__( self, index ):
        """Handles region[x,z]. Equivalent to region.getChunk( x, z )."""
        return self.getChunk( *index )

    #Handles iter( region ). Equivalent to region.iterChunks().
    #Allows use of this class in a for loop like so:
    #    for chunk in region:
    #        ...
    __iter__ = iterChunks

    def __repr__( self ):
        return "Region({:d}, {:d}, '{}')".format( self.x, self.z, self.path )




#Base chunk class.
#Chunks are (typically zlib compressed) NBT documents stored in region files.
#Each chunk stores detailed information about a small area of the world.
#This includes block, lighting, and heightmap data, but also non-block data such as save data for entities and tile entities within their bounds.
class _BaseChunk:
    __slots__ = ( "x", "z", "lx", "lz", "offset", "allocsize", "timestamp", "size", "compression", "nbt", "region", "_tileEntities" )

    #Subclasses should override this
    formatid = None
    format   = None

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
        tileEntities = self._tileEntities
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
        raise NotImplementedError()

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
        raise NotImplementedError()

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

    #Handles iter( chunk ). Equivalent to chunk.iterBlocks().
    #Allows use of this class in a for loop like so:
    #    for block in chunk:
    #        ...
    __iter__ = iterBlocks

    def __getitem__( self, index ):
        """Handles chunk[x,y,z]. Equivalent to chunk.getBlock( x, y, z )."""
        return self.getBlock( *index )

    def __repr__( self ):
        return "Chunk({:d}, {:d})".format( self.x, self.z )




class _BaseBlock:
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
    __slots__ = ( "chunk", "_d", "_i" )

    #Subclasses should override these
    formatid = None
    format   = None

    def __init__( self, chunk = None, data = None, index = None ):
        self.chunk = chunk  #Chunk containing this block
        self._d    = data   #Data relating to the section containing this block
        self._i    = index  #Index of this block within the section

    def getPos( self ):
        raise NotImplementedError()
    pos = property( getPos )

    def getX( self ):
        raise NotImplementedError()
    x = property( getX )

    def getY( self ):
        raise NotImplementedError()
    y = property( getY )

    def getZ( self ):
        raise NotImplementedError()
    z = property( getZ )

    def getID( self ):
        raise NotImplementedError()
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
        return _n( self._d[1], self._i )
    meta = property( getMeta )

    def getBlockLight( self ):
        return _n( self._d[2], self._i )
    blockLight = property( getBlockLight )

    def getSkyLight( self ):
        return _n( self._d[3], self._i )
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
        return "Block({:d},{:d},{:d},{:d},{:d})".format( *self.pos, self.id, self.meta )