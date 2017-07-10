jnbt
=========

jnbt is a Named Binary Tag (NBT) library for Python 3.

NBT is a data-interchange format similar to JSON. The most notable difference between the two is that NBT is stored as binary rather than text. NBT is used in Minecraft for many things requiring long-term storage, such as chunks, player data, and world metadata.

jnbt implements both DOM-style and SAX-style interfaces for reading and writing NBT files, as well as limited support for reading Minecraft world saves.

Table of Contents
-----------------
* [DOM-style Interface](#dom-style-interface)
* [SAX-style Interface](#sax-style-interface)
* [Reading Minecraft Worlds](#reading-minecraft-worlds)
* [Documentation](#documentation)
* [Installation](#installation)
* [Additional Resources](#additional-resources)

DOM-style Interface
-------------------
jnbt's DOM-style interface allows you to read, write, and build NBT documents, represented as a tree of NBT tags.

Modifying a player's inventory:
```python
import jnbt

#Read the file
doc = jnbt.read( "filename.nbt" )

#Change coal to diamonds
for item in doc["Inventory"]:
    if item["id"] == 263 and item["Damage"] == 0:
        item["id"] = 264

#Save changes
doc.write()
```

Building and saving an NBT document:
```python
import jnbt

doc = jnbt.NBTDocument()

#Add a TAG_Byte to doc.
doc.byte( "my_byte", 10 )

#Add a TAG_List to doc and add TAG_Strings to it.
doc.list( "my_list", [ "This", "is", "an", "example." ] )

#Add a TAG_Compound to doc and add tags to it.
comp = doc.compound( "my_compound" )
comp.string( "name", "Sheep" )
comp.long( "id", 1234567890 )

#Save it
doc.write( "somefile.nbt" )
```

SAX-style Interface
-------------------
jnbt's SAX-style interface reads/writes NBT documents in a streaming fashion, potentially allowing for a lower memory footprint where this is a concern.

Write NBT to a file without building a tree in memory:
```python
import jnbt

with jnbt.writer( "somefile.nbt" ) as writer:
    writer.start()
    
    writer.byte( "my_byte", 10 )
    
    writer.startList( "my_list", jnbt.TAG_STRING, 4 )
    writer.string( "This" )
    writer.string( "is" )
    writer.string( "an" )
    writer.string( "example." )
    writer.endList()

    writer.startCompound( "my_compound" )
    writer.string( "name", "Sheep" )
    writer.long( "id", 1234567890 )
    writer.endCompound()

    writer.end()
```

Print strings as they're read:
```python
import jnbt

class MyHandler( jnbt.NBTHandler ):
    def string( self, value ):
        print( value )

jnbt.parse( "somefile.nbt", MyHandler() )
```

Reading Minecraft Worlds
------------------------
jnbt can read Minecraft worlds, but cannot modify them at this time.
Currently, both Region and Anvil formats are supported.

Specifically, jnbt understands the structure of Minecraft world directories and represents it programmatically. You can find and read level and player data, dimensions, regions, chunk and block data in Minecraft worlds.

Finding iron ore in the overworld:
```python
import jnbt

#Open the world at <your minecraft directory>/saves/New World
world = jnbt.getWorld( "New World" )

overworld = world[ jnbt.DIM_OVERWORLD ]
for block in overworld.iterBlocks():
    if block.name == "minecraft:iron_ore":
        print( block.x, block.y, block.z )
```

Documentation
-------------
Beyond this README file, jnbt does not currently have online documentation. However, almost every function, class, and method has documentation in the form of docstrings.

You can read these by exploring the source code, or with the "help" function in the Python interpreter:
```
>>> import jnbt
>>> help( jnbt.read )
...
```

Installation
------------
If you have git installed locally, the following command can be used to install or update jnbt:

`pip install git+https://github.com/theJ8910/jnbt.git`

Otherwise, you can download jnbt [here](https://github.com/theJ8910/jnbt/archive/dev.zip) and run the following command:

`pip install dev.zip`

Additional Resources
-------------------
These resources were used in the development of jnbt and may help you to better understand NBT and how Minecraft utilizes it:

http://web.archive.org/web/20110723210920/http://www.minecraft.net/docs/NBT.txt

http://minecraft.gamepedia.com/NBT_Format

http://wiki.vg/Nbt


http://minecraft.gamepedia.com/Level_Format

http://minecraft.gamepedia.com/Region_file_format

http://minecraft.gamepedia.com/Anvil_file_format

http://minecraft.gamepedia.com/Chunk_format

http://minecraft.gamepedia.com/index.php?title=Chunk_format&oldid=249962

http://minecraft.gamepedia.com/Player.dat_format

http://wiki.vg/Region_Files

http://wiki.vg/Map_Format