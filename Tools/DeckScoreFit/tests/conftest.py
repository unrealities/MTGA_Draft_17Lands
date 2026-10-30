import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

# The tool's scripts, and the app whose features they compute.
sys.path[:0] = [os.path.dirname(HERE), ROOT]
