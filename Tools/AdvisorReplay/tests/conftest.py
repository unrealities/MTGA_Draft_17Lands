import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

# The harness scripts, and the app they replay.
sys.path[:0] = [os.path.dirname(HERE), ROOT]
