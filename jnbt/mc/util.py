import os
import os.path
import sys

#Path to the Minecraft installation directory
_mcPath = None

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