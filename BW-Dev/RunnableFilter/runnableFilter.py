#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 24 15:37:13 2025

@author: brian
"""

import os

runnableFiles = []
nonRunnableFiles = []
fcFileCount = 0

with open('uniqueFileNames.txt', 'r') as f:
	for fileName in f:
		# .fc files are not readable by the disasm
		if (not ".fc" in fileName):
			command = "python3 ../../Py/Disassembler/wwdisasm.py -o - " + fileName
			
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
				print(fileName + " will run")
				runnableFiles.append(fileName)
			else:
				print(fileName + " won't run")
				nonRunnableFiles.append(fileName)
		else:
			fcFileCount = fcFileCount + 1
			
with open('runnableFiles.txt', 'w') as f:
	for fileName in runnableFiles:
		f.write(fileName)

with open('nonRunnableFiles.txt', 'w') as f:
	for fileName in nonRunnableFiles:
		f.write(fileName)
	
print(str(len(runnableFiles)) + " runnable files\n")
print(str(len(nonRunnableFiles)) + " non-runnable files\n")
print(str(fcFileCount) + " .fc files \n")