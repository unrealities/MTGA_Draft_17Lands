#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "numpy==2.0.0",
#     "pillow==10.4.0",
#     "pydantic==2.8.2",
#     "pynput==1.7.6",
#     "pytest==8.2.0",
#     "requests==2.32.3",
# ]
# ///
"""! @brief Magic the Gathering draft application that utilizes 17Lands data"""

# Initialize X11 threading
import ctypes
ctypes.cdll.LoadLibrary("libX11.so").XInitThreads()

# Imports
from src.overlay import start_overlay

def main():
    start_overlay()

if __name__ == "__main__":
    main()
