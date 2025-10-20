#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 24 15:37:13 2025

@author: brian
"""

import os

runnableFiles = []
noJumpToFiles = []
nonRunnableFiles = []
fcFiles = []

with open('uniqueFileNames.txt', 'r') as f:
	for fileName in f:
		# .fc files are not readable by the disasm
		if (not ".fc" in fileName):
			fileName = fileName.rstrip()
			
			# first, see if the .xcore file has a JumpTo line in it 
			# since the disassembler adds a default JumpTo 0o040 to all files
			# if there's a real '%JumpTo' then log that address
			jumpToAddr = 0
			with open(fileName) as file:
				for line in file:
					if ('JumpTo' in line):
						jumpToAddr = int(line.split("%JumpTo")[1], 8)
						
			if (jumpToAddr != 0):
				#there's a real jump to address; now see if it's runnable
				command = "python3 ../../Py/Disassembler/wwdisasm.py -o - " + fileName + "\n"
				
				process = os.popen(command)
				result = process.read()
				process.close();
				
				addressesWithData = []
				for line in result.splitlines():
					if (line.startswith("@")):
						addrString = line.split(":")[0].replace("@", "")
						addressesWithData.append(int(addrString, 8))
						
				if jumpToAddr in addressesWithData:
					print(fileName + " will run")
					runnableFiles.append(fileName)
				else:
					nonRunnableFiles.append(fileName)
			else:
				noJumpToFiles.append(fileName)
		else:
			fcFiles.append(fileName)
			
with open('runnableFiles.txt', 'w') as f:
	for fileName in runnableFiles:
		f.write(fileName + '\n')

with open('nonRunnableFiles.txt', 'w') as f:
	for fileName in nonRunnableFiles:
		f.write(fileName + '\n')
		
with open('noJumpToFiles.txt', 'w') as f:
	for fileName in noJumpToFiles:
		f.write(fileName + '\n')

with open('fcFiles.txt', 'w') as f:
	for fileName in fcFiles:
		f.write(fileName + '\n')
	
print(str(len(runnableFiles)) + " runnable files\n")
print(str(len(nonRunnableFiles)) + " non-runnable files\n")
print(str(len(noJumpToFiles)) + " files without a JumpTo in the .xcore\n")
print(str(len(fcFiles)) + " .fc files \n")