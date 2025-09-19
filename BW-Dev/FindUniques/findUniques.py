#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Sep 19 11:52:33 2025

@author: brian
"""
import os
import filecmp

allFiles = []
filesToIgnore = []
uniqueFiles = []

# first, make a list of all the rea files
topDirList = ["../../Recovered-Tapes/Translated-Files/Magnetic-Tapes/", "../../Recovered-Tapes/Translated-Files/Paper-Tapes/"]
for topDir in topDirList:
    dirList = os.listdir(topDir)
    for dir in dirList:
        dirName = topDir + dir
        if (os.path.isdir(dirName)):
            fileList = os.listdir(dirName)
            for file in fileList:
                if (not file.startswith(".")):
                    fileName = dirName + "/" + file
                    allFiles.append(fileName)

# then check them against each other
for file1 in allFiles:
    foundAMatchForFile1Already = 0
    if (file1 not in filesToIgnore):
        for file2 in allFiles:
            if (file2 not in filesToIgnore):
                if (filecmp.cmp(file1, file2, shallow = False)):
                    # file2 is a dupe of file 1
                    if (foundAMatchForFile1Already == 0):
                        # it's the first time file1 has matched; so save it
                        uniqueFiles.append(file1);
                        foundAMatchForFile1Already = 1
                        print(file1)
                        # but file 2 is a dupe so ignore it
                        filesToIgnore.append(file2);
                    else:
                        # we've already found a match for file1
                        filesToIgnore.append(file2)

with open("uniqueFileNames.txt", 'w') as f:
    for line in uniqueFiles:
        f.write(f"{line}\n")
                