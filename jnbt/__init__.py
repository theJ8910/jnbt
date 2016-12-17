"""
JNBT is a library for reading and writing Named Binary Tag (NBT) data for Python 3.
It features both DOM and SAX-style parsing and writing, as well as utilities to read world data (e.g. world save directories and Minecraft Anvil regions).

Modifying an NBT file:
    doc = jnbt.read( "filename.nbt" )
    
    for tag in doc["inventory"]:
        if tag["id"] == 501:
            tag["id"] = 1024

    doc.write( "filename.nbt" )

Finding iron ore in the overworld:
    path  = jnbt.getMinecraftPath( "saves", "New World" )
    world = jnbt.World( path )
    
    overworld = world[ jnbt.DIM_OVERWORLD ]
    for block in overworld.iterBlocks():
        if block.id == 15:
            print( block.x, block.y, block.z )
"""

#Useful links:
#    http://web.archive.org/web/20110723210920/http://www.minecraft.net/docs/NBT.txt
#    http://minecraft.gamepedia.com/NBT_Format
#    http://wiki.vg/Nbt
#
#    http://minecraft.gamepedia.com/Level_Format
#    http://minecraft.gamepedia.com/Region_file_format
#    http://minecraft.gamepedia.com/Anvil_file_format
#    http://minecraft.gamepedia.com/Chunk_format
#    http://wiki.vg/Region_Files
#    http://wiki.vg/Map_Format

#NBT Tag Types, Exceptions
from .shared import (
    TAG_END, TAG_BYTE, TAG_SHORT, TAG_INT, TAG_LONG, TAG_FLOAT, TAG_DOUBLE, TAG_BYTE_ARRAY, TAG_STRING, TAG_LIST, TAG_COMPOUND, TAG_INT_ARRAY,
    TAG_COUNT,
    NBTFormatError, WrongTagError, DuplicateNameError, UnknownTagTypeError, OutOfBoundsError
)

#read, NBTDocument and TAG_* Classes
from .tag import read, NBTDocument, TAG_Byte, TAG_Short, TAG_Int, TAG_Long, TAG_Float, TAG_Double, TAG_Byte_Array, TAG_String, TAG_List, TAG_Compound, TAG_Int_Array

#Classes and functions to interact with Minecraft worlds
from .world import DIM_NETHER, DIM_OVERWORLD, DIM_END, World, Dimension, Region, Chunk, Block, setMinecraftDir, getMinecraftPath

#NBT Parsers + Handlers
from .parse import treeparse, parse
from .handler import AbstractNBTHandler, PrintNBTHandler, TreeNBTHandler

#NBT Writers
from .writer import NBTWriter
from .safewriter import SafeNBTWriter

#Export everything we imported above
__all__ = [
    "TAG_END", "TAG_BYTE", "TAG_SHORT", "TAG_INT", "TAG_LONG", "TAG_FLOAT", "TAG_DOUBLE", "TAG_BYTE_ARRAY", "TAG_STRING", "TAG_LIST", "TAG_COMPOUND", "TAG_INT_ARRAY",
    "TAG_COUNT",
    "NBTFormatError", "WrongTagError", "DuplicateNameError", "UnknownTagTypeError", "OutOfBoundsError",
    "read", "NBTDocument", "TAG_Byte", "TAG_Short", "TAG_Int", "TAG_Long", "TAG_Float", "TAG_Double", "TAG_Byte_Array", "TAG_String", "TAG_List", "TAG_Compound", "TAG_Int_Array",
    "DIM_NETHER", "DIM_OVERWORLD", "DIM_END", "World", "Dimension", "Region", "Chunk", "Block", "setMinecraftDir", "getMinecraftPath",
    "treeparse", "parse",
    "AbstractNBTHandler", "PrintNBTHandler", "TreeNBTHandler",
    "NBTWriter",
    "SafeNBTWriter"
]