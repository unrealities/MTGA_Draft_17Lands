import ctypes
import os

os.environ['DISPLAY'] = ':1'  # make sure DISPLAY is set

# Initialize Xlib threads
xcb = ctypes.CDLL('libX11.so')
xcb.XInitThreads()

import tkinter as tk

root = tk.Tk()
root.title("Test Tkinter")

label = tk.Label(root, text="Hello, Tkinter on DISPLAY :1")
label.pack(padx=20, pady=20)

root.mainloop()

