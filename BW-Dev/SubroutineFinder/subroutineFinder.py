#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Oct 30 2025
find possible subroutines
	ta to address X
	@X cp or sp 0000
@author: brian
"""

import os

with open('subroutineCounts.csv', 'w') as out:
	with open('uniqueFileNames.txt', 'r') as f:
		for fileName in f:
			# .fc files are not readable by the disasm
			if (not ".fc" in fileName):
				fileName = fileName.rstrip()
				
				# try to run it
				command = "python3 ../../Py/Disassembler/wwdisasm.py -o - " + fileName + "\n"
				process = os.popen(command)
				result = process.read()
				process.close();
				result = result.splitlines()
				
				# first pass, find all the ta instructions
				taInstructionTargetAddresses = []
				for line in result:
					if 'transfer address' in line:
						part1 = line.split('ta')[1].strip()
						addressString = part1.split()[0]
						numPart = ''
						if 'o' in addressString:
							numPart = addressString.split('o')[1]
						if 'w' in addressString:
							numPart = addressString.replace('w', '')
						if 'i' in addressString:
							numPart = addressString.replace('i', '')
						if (numPart != ''):
							taInstructionTargetAddresses.append(int(numPart,8))
				
				# do a second pass to see if any of these write to a cp or sp 0000
				# only do the second pass if some ta's were found
				numSubCalls = 0
				if (len(taInstructionTargetAddresses) != 0):
					for line in result:
						if line.startswith('@'):
							address = int(line.split(':')[0].replace('@',''), 8)
							# the TA writes to here - see if it's cp or sp
							if address in taInstructionTargetAddresses:
								if ('conditional program' in line) or ('sub-program' in line):
									numSubCalls = numSubCalls + 1
				
				if (numSubCalls != 0):
					out.write(f'\"{fileName}\", {numSubCalls}\n')
					
						
				
				