# Makefile for Laning and Zierer interpreter
# fedorkow, nov 7, 2024
#

L-and-Z.wwsim.log: L-and-Z.acore L-and-Z.petRA
	wwsim -c 1000 -t L-and-Z.acore


L-and-Z.petRA: Sample-L-and-Z-Code.txt
	ww-ASCII-to-Flexo -i Sample-L-and-Z-Code.txt -o L-and-Z.petRA

L-and-Z.acore: L-and-Z.ww
	wwasm -D L-and-Z.ww
	echo Back Up Source
	cp L-and-Z.ww L-and-Z.ww.bak

