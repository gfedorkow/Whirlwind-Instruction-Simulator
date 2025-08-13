


ww-octal-to-7ch Everett-Tape-manual-read.txt

# the -o option doesn't seem to work right -- it puts the file in the wrong directory
ww-octal-to-7ch -x ../Everett-tape-Dec23-21/optical-reader-dec23-21-v3a.txt -o optical-reader-dec23-21-v3a.7ch

cp ../Everett-tape-Dec23-21/optical-reader-dec23-21-v3a.7ch .

cat Everett-Tape-manual-read.7ch optical-reader-dec23-21-v3a.7ch > Everett-tape-merged.7ch

# add -Min 0; wwutd seems to be failing to output .petrA files, but not saying so
wwutd Everett-tape-merged.7ch
