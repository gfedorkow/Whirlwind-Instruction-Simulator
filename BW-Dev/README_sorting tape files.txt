Description of the various files I used to preliminarily characterize the tape files
in the archives. I present them roughly in order of how they should be used.

************

FindUniques/findUniques.py
this uses an md5 hash to see if the contents of two tape files are identical 
(not counting the line in the file with the name: grep -v \"%File:\" )
it iterates over all the files in
/Recovered-Tapes/Translated-Files/Magnetic-Tapes/
/Recovered-Tapes/Translated-Files/Paper-Tapes/
and creates a file "uniqueFileNames.txt" with all the unique files

when run in 9/2025, there were:
- 13762 files in the archives
- 11,799 unique files
- 1,983 duplicates
*********

RunnableFilter/runnableFilter.py
takes uniqueFileNames.txt and iterates over all these files
for each:
	- if it is a .fc file => "fcFiles.txt" (436 found)
	- else:
		- open the tape file
		- if it contains a "jumpTo"
			- disassemble it 
				- if there's code at the jumpTo target => "runnableFiles.txt" (258 found)
				- else => "nonRunnableFiles.txt" (723 found)
		- else => "noJumpToFiles.txt" (10,362 found)
***********

CharacterizeRunnables/characterizeRunnbles.py
takes runnableFiles.txt and, for each
runs them for 10,000 cycles and scans the output for:
- “NumLinesInResult” - just a count of the number of lines of text that came out of wwsim.py. 
	I’m thinking that longer logs corresponds to more interesting run.
- “LastUsefulLine” - the third-to-last line of the sim run often contained something vaguely 
	indicative of what was going on (the last 2 lines just say that the cycle count was exceeded)
- “DisplayCount” - the number of lines in the sim run output that contained the text “DisplayScope”. 
	Hopefully, an indication of display activity.
- “LightGunEnableCount” - the number of lines in the sim run output that contained the text 
	“gun_enable=1”. This turned out to be less useful than I’d hoped.
- “LightGunCHeckCount” - the number of lines in the sim run output that contained the text 
	“ww_check_light_gun”. Hopefully an indication of the use of the light gun.
- “FlexowriterCount” - the number of lines in the sim run output that contained the text 
	“Flexowriter”. Hopefully an indication of printed output.
- some logging of the branches - to get an idea of the complexity of the run
	each time there was a branch, I kept track of the destination and added 1 to a count of 
		times a branch landed there
	“BranchTargetCount” = the number of different branch target addresses referenced in 
		the sim run output
	“AvgBranchTargetHits” = the average number of hits over all the branch target addresses 
		referenced in the sim run output

results in "runnableFileResults.csv"
*************

SubroutineFinder/subroutineFinder.py
takes all the files in "uniqueFileNames.txt"
disassemble each and look for
	ta to address X
	@X cp or sp 0000
count these up and report in "subroutineCounts.csv"
************