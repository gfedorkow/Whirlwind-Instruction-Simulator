#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 24 15:37:13 2025

@author: brian
"""

import os

command = "python3 ../../Py/Disassembler/wwdisasm.py -o - ../../Recovered-Tapes/Translated-Files/Magnetic-Tapes/132/t132_pt2_good_gs007.ocore"
process = os.popen(command)
result = process.read()
process.close();

print(result)