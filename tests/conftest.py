import os
import sys

# The local Anaconda environment may have optional pandas accelerator wheels
# compiled against a different NumPy ABI. Pandas works without them, so keep test
# imports on the pure-Python path.
os.environ.setdefault("PANDAS_USE_NUMEXPR", "0")
os.environ.setdefault("PANDAS_USE_BOTTLENECK", "0")
sys.modules.setdefault("numexpr", None)
sys.modules.setdefault("bottleneck", None)
