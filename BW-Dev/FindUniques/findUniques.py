#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Sep 19 11:52:33 2025

@author: brian
"""
import os
import filecmp
import shelve

allFiles = []
uniqueFiles = []

if (not os.path.isfile("/Users/brian/Desktop/wwTemp/fileData.shlf.db")):
    i = 0
    # first, make a list of all the real files
    # set up a list of tuples:
    #  fileName, flag
    #   flag = 0 -> this file is not a duplicate of another (or hasn't been checked yet)
    #   flag = 1 -> this file is a duplicate of another file
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
                        getMd5 = os.popen("grep -v \"%File:\" " + fileName + " | md5")
                        md5 = getMd5.read()
                        getMd5.close()
                        data = {"fn" : fileName, "md5" : md5, "dup" : 0}
                        allFiles.append(data)
                        print(i)
                        i = i + 1
    # save the result
    shelf = shelve.open("/Users/brian/Desktop/wwTemp/fileData.shlf")
    shelf["allFiles"] = allFiles
    shelf.close()
else:
    shelf = shelve.open("/Users/brian/Desktop/wwTemp/fileData.shlf")
    allFiles = shelf["allFiles"]
    shelf.close()
    print("loaded saved file data")

# loop over them to find duplicates
with open("duplicateInfo.csv", 'w') as f:
    for i in range(len(allFiles)):
        # see if the probe file is a duplicate; ignore if it is
        if (allFiles[i]["dup"] == 0):
            # it isn't, so save the name and look for duplicates
            uniqueFiles.append(allFiles[i]["fn"])
            # check for identical md5 sums
            for j in range(i + 1, len(allFiles)):
                if (allFiles[j]["dup"] == 0):
                    # create a cleaned copy for comparison
                    print("comparing " + str(i) + " and " + str(j))
                    # do the comparison of the md5's first
                    if (allFiles[i]['md5'] == allFiles[j]['md5']):
                        # to be sure, check the actual cleaned of metadata files
                        os.system("grep -v \"%File:\" " + allFiles[i]["fn"] + " > ~/Desktop/wwTemp/temp1")
                        os.system("grep -v \"%File:\" " + allFiles[j]["fn"] + " > ~/Desktop/wwTemp/temp2")
                        command = "diff ~/Desktop/wwTemp/temp1 ~/Desktop/wwTemp/temp2"
                        process = os.popen(command)
                        result = process.read()
                        process.close()
                        if(result == ""):
                            # if [j] is a duplicate of [i]; mark both as duplicates
                            f.write(allFiles[i]['fn'] + "," + allFiles[j]['fn'] + "\n")
                            allFiles[i]["dup"] = 1
                            allFiles[j]["dup"] = 1
f.close()
                
# save the result
with open("uniqueFileNames.txt", 'w') as f:
    for line in uniqueFiles:
        f.write(f"{line}\n")
      


