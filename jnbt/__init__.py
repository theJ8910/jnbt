"""
JNBT is a library for reading and writing Named Binary Tag (NBT) data for Python 3.
It features both DOM and SAX-style parsing and writing, as well as utilities to read world data (e.g. world save directories and Minecraft Anvil regions).
"""

#NBT Tag Types, Exceptions
from jnbt.shared import (
    TAG_END, TAG_BYTE, TAG_SHORT, TAG_INT, TAG_LONG, TAG_FLOAT, TAG_DOUBLE, TAG_BYTE_ARRAY, TAG_STRING, TAG_LIST, TAG_COMPOUND, TAG_INT_ARRAY,
    TAG_COUNT,
    NBTFormatError, WrongTagError, DuplicateNameError, UnknownTagTypeError, OutOfBoundsError
)

#read, NBTDocument and TAG_* Classes
from jnbt.tag import read, NBTDocument, TAG_Byte, TAG_Short, TAG_Int, TAG_Long, TAG_Float, TAG_Double, TAG_Byte_Array, TAG_String, TAG_List, TAG_Compound, TAG_Int_Array

#Classes and functions to interact with Minecraft worlds
from jnbt.world import DIM_NETHER, DIM_OVERWORLD, DIM_END, World, Dimension, Region, Chunk, Block, setMinecraftDir, getMinecraftPath

#NBT Parsers + Handlers
from jnbt.parse import parse
from jnbt.handler import AbstractNBTHandler, PrintNBTHandler

#NBT Writer
from jnbt.writer import writer, NBTWriter


#Export everything we imported above
__all__ = [
    "TAG_END", "TAG_BYTE", "TAG_SHORT", "TAG_INT", "TAG_LONG", "TAG_FLOAT", "TAG_DOUBLE", "TAG_BYTE_ARRAY", "TAG_STRING", "TAG_LIST", "TAG_COMPOUND", "TAG_INT_ARRAY",
    "TAG_COUNT",
    "NBTFormatError", "WrongTagError", "DuplicateNameError", "UnknownTagTypeError", "OutOfBoundsError",
    "read", "NBTDocument", "TAG_Byte", "TAG_Short", "TAG_Int", "TAG_Long", "TAG_Float", "TAG_Double", "TAG_Byte_Array", "TAG_String", "TAG_List", "TAG_Compound", "TAG_Int_Array",
    "DIM_NETHER", "DIM_OVERWORLD", "DIM_END", "World", "Dimension", "Region", "Chunk", "Block", "setMinecraftDir", "getMinecraftPath",
    "parse",
    "AbstractNBTHandler", "PrintNBTHandler",
    "writer", "NBTWriter"
]