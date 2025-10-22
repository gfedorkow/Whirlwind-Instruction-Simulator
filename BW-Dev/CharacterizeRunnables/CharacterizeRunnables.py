#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 24 15:37:13 2025

@author: brian
"""

import os

i = 0 
with open("RunnableFileResults.csv", 'w') as outFile:
	outFile.write("FileName,NumLinesInResult,LastUsefulLine,DisplayCount,LightGunEnableCount,LightGunCheckCount,FlexowriterCount,BranchTargetCount,AvgBranchTargetHits\n")
	with open('runnableFiles.txt', 'r') as f:
		for fileName in f:
			fileName = fileName.rstrip()
			
			command = "python3 ../../Py/Sim/wwsim.py -c 10000 " + fileName + "\n"
			process = os.popen(command)
			result = process.read()
			process.close();
			result = result.splitlines()
			
			# get how long it ran for
			numLinesInResult = len(result)
			# get the last line in the log that has info on the run
			lastUsefulLine = result[len(result) - 3]
			
			# scan for interesting things
			displayCount = 0
			flexowriterCount = 0
			lightGunEnableCount = 0
			lightGunCheckCount = 0
			branchTargetLog = {}
			
			for line in result:
				if ("DisplayScope" in line):
					displayCount = displayCount + 1
				if ("gun_enable=1" in line):
					lightGunEnableCount = lightGunEnableCount + 1
				if ("ww_check_light_gun" in line):
					lightGunCheckCount = lightGunCheckCount + 1
				if ("Flexowriter" in line):
					flexowriterCount = flexowriterCount + 1
				if ("branch" in line):
					destAddr = int(line.split(" to ")[1],8)
					if (not destAddr in branchTargetLog):
						branchTargetLog[destAddr] = 0
					branchTargetLog[destAddr] = branchTargetLog[destAddr] + 1
			
			# add result to file
			outFile.write("\"" + fileName + "\",")
			outFile.write(str(numLinesInResult) + ",")
			outFile.write("\"" + lastUsefulLine.rstrip() + "\",")
			outFile.write(str(displayCount) + ",")
			outFile.write(str(lightGunEnableCount) + ",")
			outFile.write(str(lightGunCheckCount) + ",")
			outFile.write(str(flexowriterCount) + ",")
			outFile.write(str(len(branchTargetLog)) + ",")
			totalHits = 0
			for dest in sorted(branchTargetLog):
				totalHits = totalHits + branchTargetLog[dest]
			if (len(branchTargetLog) > 0):
				avg = totalHits/len(branchTargetLog)
				outFile.write(str(round(avg, 1)) + "\n")
			else:
				outFile.write("-\n")

