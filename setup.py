from setuptools import setup, Command

class Codegen( Command ):
    user_options = [
        ( "unsafe", None, "Generate an unsafe variant of NBTWriter" )
    ]
    boolean_options = [ "unsafe" ]
    def initialize_options( self ):
        self.unsafe = None
    def finalize_options( self ):
        self.safe = ( self.unsafe != True )
        del self.unsafe
    def run( self ):
        with open( "template/writer.py", "r" ) as fin:
            with open( "jnbt/writer.py", "w", newline="\n" ) as fout:
                echo = True
                line = fin.readline()
                while line != "":
                    ls = line.strip()
                    if   ls == "#if safe":
                        echo = self.safe
                    elif ls == "#else":
                        echo = not self.safe
                    elif ls == "#end":
                        echo = True
                    elif echo:
                        fout.write( line )
                    line = fin.readline()

setup(
    name        = "jnbt",
    version     = "1.0.17",
    author      = "theJ89",
    description = "theJ89's NBT Library",
    packages    = [ "jnbt" ],
    zip_safe    = True,
    cmdclass = {
        "codegen": Codegen
    }
)