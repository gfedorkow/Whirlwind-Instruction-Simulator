#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 24 15:37:13 2025

@author: brian
"""

import os

#this one won't run
#command = "python3 ../../Py/Disassembler/wwdisasm.py -o - ../../Recovered-Tapes/Translated-Files/Magnetic-Tapes/04/t04_gs041.tcore"

# this one will
command = "python3 ../../Py/Disassembler/wwdisasm.py -o - ../../Recovered-Tapes/Translated-Files/Paper-Tapes/2018_01/102766760_fb2353_polynomial_gs001_FB#131-0-2691.tcore"

process = os.popen(command)
result = process.read()
process.close();

addressesWithData = []
jumpToAddr = ""
for line in result.splitlines():
	if (line.startswith("@")):
		addrString = line.split(":")[0].replace("@", "")
		addressesWithData.append(int(addrString, 8))
	if (".JumpTo" in line):
		jumpToAddr = int(line.split(".JumpTo")[1], 8)
		

if jumpToAddr in addressesWithData:
	print("will run")
else:
	print("won't run")
	
	