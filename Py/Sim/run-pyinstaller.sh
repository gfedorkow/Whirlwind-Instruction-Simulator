#!/bin/bash

# Run PyInstaller to create a 'portable' Windows image of the WW simulator
# g fedorkow, Aug 15, 2022
# Use '--onefile' to create a single installation file instead of a directory
#   (and to put upwith slower startup time and less help in debug)

# https://pyinstaller.org/en/stable/index.html

pyinstaller -p . wwsim.py --hidden-import=graphics --clean --onefile
