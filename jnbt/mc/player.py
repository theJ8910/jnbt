#This module contains functions for working with player save data

import urllib.request
import json
from time import time

from jnbt import tag

#Player saves are stored in three locations:
#    * For singleplayer worlds, in the world's level.dat.
#    * For multiplayer worlds before Minecraft 1.7.6 (April 9, 2014), player saves are stored by username (e.g. theJ89.dat) in <world>/players/.
#    * For multiplayer worlds since Minecraft 1.7.6, player saves are stored by UUID (with dashes, e.g. 1e20fcf5-690e-481b-b0f4-3cc86789a3be.dat) in <world>/playerdata/.
#
#For singleplayer worlds, the player's save may be present in both the level.dat and the players / playerdata directory.
#The game will prefer to load the player's save from level.dat, however if this data is missing, it will attempt to load it from players / playerdata instead.
#
#Unfortunately, a player's last known name / uuid doesn't seem to be stored in the player save or cached locally anywhere else.
#In the case of singleplayer worlds, determining the identity of the singleplayer may not always be possible.
#Luckily though, in the multiplayer case, since we have either a name or uuid from the filename, we can request the one we don't have from the Mojang API.
#This module implements uuidToUsername and usernameToUUID for these purposes.
#
#References:
#   http://minecraft.gamepedia.com/Level_format
#   http://minecraft.gamepedia.com/Player.dat_format

def uuidToUsername( uuid ):
    """
    Look up a player's name given their uuid.
    uuid is expected to be a UUID string without dashes.
    """
    #Note: See documentation on Mojang API: http://wiki.vg/Mojang_API
    with urllib.request.urlopen( "https://sessionserver.mojang.com/session/minecraft/profile/" + uuid ) as res:
        if res.status == 200:
            return json.loads( res.read().decode() )["name"]
        else:
            raise Exception( "Mojang API returned HTTP {:d}".format( res.status ) )

def usernameToUUID( username ):
    """
    Look up a player's UUID given their name.
    The returned uuid will be a UUID string without dashes.
    """
    with urllib.request.urlopen( "https://api.mojang.com/users/profiles/minecraft/{}?at={:d}".format( username, int( time() ) ) ) as res:
        if res.status == 200:
            return json.loads( res.read().decode() )["id"]
        else:
            raise Exception( "Mojang API returned HTTP {:d}".format( res.status ) )


class Player:
    """
    Represents a player.
    """
    __slots__ = ( "path", "_nbt", "_name", "_uuid" )
    def __init__( self, path=None, nbt=None, name=None, uuid=None ):
        """
        Constructor. All parameters are optional and default to None.

        path is a path (as a string) to the player's save data and is expected to be a gzip-compressed NBT file.
            If nbt is None or not given, the first time the nbt attribute is accessed it will be initialized by reading the file at this path.
        nbt should be an NBTDocument containing the player's save data.
        name should be the player's name as a string (e.g. "theJ89").
        uuid should be the player's uuid as a string, lowercase, without dashes (e.g. "1e20fcf5690e481bb0f43cc86789a3be").
        """
        self.path  = path
        self._nbt  = nbt
        self._name = name
        self._uuid = uuid

    def getNBT( self ):
        """
        Returns the player's save data.
        If we don't have the save data but we do have a path to a file where we can read it from, this will read and cache the save data from that file.
        Otherwise, None is returned.
        """
        nbt = self._nbt
        if nbt is None:
            path = self.path
            if path is not None:
                self._nbt = nbt = tag.read( path )
        return nbt
    nbt = property( getNBT )

    def getName( self ):
        """
        Returns the player's name.
        If we don't have the name but do have the UUID, this will fetch and cache the player's name through the Mojang API.
        Otherwise, None is returned.
        """
        name = self._name
        if name is None:
            uuid = self._uuid
            if uuid is not None:
                self._name = name = uuidToUsername( uuid )
        return name
    name = property( getName )

    def getUUID( self ):
        """
        Returns the player's UUID.
        If we don't have the UUID but do have the name, this will fetch and cache the player's UUID through the Mojang API.
        Otherwise, None is returned.
        """
        uuid = self._uuid
        if uuid is None:
            name = self._name
            if name is not None:
                self._uuid = uuid = usernameToUUID( name )
        return uuid
    uuid = property( getUUID )

    def __repr__( self ):
        args = []

        v = self.path
        if v is not None:
            args.append( "path="+repr( v ) )

        v = self._name
        if v is not None:
            args.append( "name="+repr( v ) )

        v = self._uuid
        if v is not None:
            args.append( "uuid="+repr( v ) )

        return "Player({})".format( ", ".join( args ) )