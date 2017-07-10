"""
JNBT's world module contains classes and functions for interacting with Minecraft saves.

Note: This module is still under development, and as such is subject to breaking changes!
"""
import os.path

from jnbt.shared        import scandir
from jnbt.mc.util       import getMinecraftPath
from jnbt.mc.world.base import LVLFMT_REGION, LVLFMT_ANVIL
from jnbt.mc.world.mcr import World as MCRWorld, Dimension as MCRDimension, Region as MCRRegion, RE_FILENAME as RE_FILENAME_MCR
from jnbt.mc.world.mca import World as MCAWorld, Dimension as MCADimension, Region as MCARegion, RE_FILENAME as RE_FILENAME_MCA

#Dimension IDs for the Overworld, Nether, and End
DIM_NETHER    = -1
DIM_OVERWORLD =  0
DIM_END       =  1

#These tuples map LVLFMT_* enums to World, Dimension, and Region classes for each format
LVLFMT_TO_WORLD = (
    None,     #Classic
    None,     #Indev
    None,     #Alpha
    MCRWorld, #Region
    MCAWorld  #Anvil
)

LVLFMT_TO_DIMENSION = (
    None,         #Classic
    None,         #Indev
    None,         #Alpha
    MCRDimension, #Region
    MCADimension  #Anvil
)

LVLFMT_TO_REGION = (
    None,      #Classic
    None,      #Indev
    None,      #Alpha
    MCRRegion, #Region
    MCARegion, #Anvil
)

#Attempts to determine what kind of level format the world / dimension / region / etc. uses by examining file extensions in the given path
#Returns a LVLFMT_* enum.
#If the format cannot be determined for any reason, raises an Exception.
def _getLevelFormat( path ):
    #Given a directory, visit bottommost folders first because they're most likely to contain our region files
    if os.path.isdir( path ):
        haveMCR = False
        for dirpath, dirs, files in os.walk( path, False ):
            if os.path.basename( dirpath ).lower() == "region":
                for file in files:
                    #Found an .mca file. Since this is the newest format, we can quickly conclude this is an .mca world.
                    if RE_FILENAME_MCA.fullmatch( file ):
                        return LVLFMT_ANVIL
                    #No .mca yet, but we found an .mcr. This doesn't necessarily mean this is an .mcr world though, because .mcr files aren't deleted when the world is converted to .mca.
                    elif RE_FILENAME_MCR.fullmatch( file ):
                        haveMCR = True
        #Didn't find any .mca files, did we find any .mcr?
        if haveMCR:
            return LVLFMT_REGION
    #We were given a file
    elif os.path.isfile( path ):
        if RE_FILENAME_MCA.fullmatch( path ):
            return LVLFMT_ANVIL
        elif RE_FILENAME_MCR.fullmatch( path ):
            return LVLFMT_REGION
    raise Exception( "Unrecognized world format." )

#Like os.path.dirname but returns None if path is the root of the file system
def _getParentDirectory( path ):
    parent = os.path.dirname( path )
    return None if parent == path else parent

#Given an absolute path to a world directory or a file/directory contained within a world directory,
#returns the path to the world directory. Returns None if the path is not contained within a valid world directory.
def _getWorldDirectory( path ):
    while True:
        if os.path.isfile( os.path.join( path, "level.dat" ) ):
            return path
        path = _getParentDirectory( path )
        if path is None:
            return None

#Given a dimension directory path, returns the dimension's ID if the directory's name is of the form "DIM{n}" (where n is the ID#).
#Otherwise, returns None.
def _getDimensionIDFromPath( path ):
    name = os.path.basename( path ).upper()
    if name.startswith( "DIM" ):
        try:
            return int( name[3:] )
        except ValueError:
            pass

#Given an absolute path to a region file, return the path to its containing dimension's directory.
#Returns None if the given file was not contained in a valid dimension directory.
def _getRegionDimension( path ):
    #A region's path typically takes this form:
    #   <dimension>/region/<region_file>
    #With that in mind, we can work upwards through the hierarchy, checking if the file is in a directory called "region":
    path = _getParentDirectory( path )
    if path is None or os.path.basename( path ).lower() != "region":
        return None
    #And if so, returning its parent directory, if any:
    return _getParentDirectory( path )

def getWorld( name="New World", savedir=None ):
    """
    Returns a World with the given name that exists in the given directory, savedir.
    Basically this:
        w = jnbt.getWorld( "My World" )
    Is a convenient shorthand for this:
        w = jnbt.World( jnbt.getMinecraftPath( "saves", "My World" ) )

    name is an optional parameter that defaults to "New World".
        If given, this should be the name of the directory for the world you want to read.
        Note: the world's directory name may differ from the world's display name under some circumstances.
    savedir is optional parameter that defaults to "<your minecraft directory>/saves".
        If given, this should be a path (as a string) to a directory containing your world(s).
    """
    if savedir is None:
        savedir = getMinecraftPath( "saves" )
    return World( os.path.join( savedir, name ) )

def iterWorlds( savedir=None ):
    """
    Iterates over every Minecraft world in the given directory, savedir.
    savedir is optional parameter that defaults to "<your minecraft directory>/saves".
        If given, this should be a path (as a string) to a directory containing your world(s).
    """
    if savedir is None:
        savedir = getMinecraftPath( "saves" )
    for entry in scandir( savedir ):
        if entry.is_dir():
            path = entry.path
            if os.path.isfile( os.path.join( path, "level.dat" ) ):
                yield World( path )

def World( path ):
    """
    Returns a World object of the appropriate type for the given path.
    Raises an exception if the level format cannot be determined.
    """
    path = os.path.abspath( path )
    if not os.path.isdir( path ):
        raise Exception( "\"{}\" does not exist or is not a directory.".format( path ) )

    #Determine world format (.mcr or .mca) and return the appropriate type of World object
    fmt = _getLevelFormat( path )
    if fmt is None:
        raise Exception( "Unrecognized world format." )
    return LVLFMT_TO_WORLD[fmt]( path )

def Dimension( path ):
    """
    Returns a Dimension object of the appropriate type for the given path.
    The given path is expected to be a directory.
    Raises an exception if the level format cannot be determined.
    """
    path = os.path.abspath( path )
    if not os.path.isdir( path ):
        raise Exception( "\"{}\" does not exist or is not a directory.".format( path ) )

    #Create a World for this Dimension if possible
    worldpath = _getWorldDirectory( path )
    if worldpath is None:
        fmt = _getLevelFormat( path )
        id = _getDimensionIDFromPath( path )
        world = None
    else:
        #Dimension folder may exist but have no region files.
        #If we have a world directory, determine the world (and by extension the dimension's) format from the world.
        fmt = _getLevelFormat( worldpath )
        id = 0 if path == worldpath else _getDimensionIDFromPath( path )
        world = LVLFMT_TO_WORLD[ fmt ]( worldpath )
    return LVLFMT_TO_DIMENSION[ fmt ]( path, world, id )

def Region( path ):
    """
    Returns a Region object of the appropriate type for the given path.
    Raises an exception if the level format cannot be determined.
    """
    path = os.path.abspath( path )
    if not os.path.isfile( path ):
        raise Exception( "\"{}\" does not exist or is not a file.".format( path ) )

    #Determine level format
    name = os.path.basename( path )
    match = RE_FILENAME_MCA.fullmatch( name )
    if match:
        clsWorld     = MCAWorld
        clsDimension = MCADimension
        clsRegion    = MCARegion
    else:
        match = RE_FILENAME_MCR.fullmatch( name )
        if match:
            clsWorld     = MCRWorld
            clsDimension = MCRDimension
            clsRegion    = MCRRegion
        else:
            raise Exception( "Unrecognized world format." )

    #Create a World and Dimension for this region if possible
    dimpath = _getRegionDimension( path )
    if dimpath is None:
        dimension = None
    else:
        worldpath = _getWorldDirectory( dimpath )
        if worldpath is None:
            id = _getDimensionIDFromPath( dimpath )
            world = None
        else:
            id = 0 if dimpath == worldpath else _getDimensionIDFromPath( dimpath )
            world = clsWorld( worldpath )
        dimension = clsDimension( dimpath, world, id )

    #Return the region object
    return clsRegion(
        int( match.group( 1 ) ),
        int( match.group( 2 ) ),
        path,
        dimension
    )