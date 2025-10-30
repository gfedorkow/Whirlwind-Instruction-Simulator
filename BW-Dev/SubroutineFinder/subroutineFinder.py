#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 24 15:37:13 2025

@author: brian
"""

import os


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
				
				