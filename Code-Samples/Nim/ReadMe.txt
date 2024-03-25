Game of Nim - recovered code

g fedorkow, feb 21, 2024, Mar 25, 2024

See DCL-113 for instructions on how to work this game of "Generalized Nim"
http://www.bitsavers.org/pdf/mit/whirlwind/DCL-series/DCL-113_Generalized_Nim_Playing_Routine_Dec55.pdf
The "control panel" (i.e., wwsim -p) is required, as user-intent is signalled via (emulated) switches.

To start the game, type:
  guyfe@fedorkow-srfc-5 ~/WW/GitHub/Code-Samples/Nim
  $ wwsim -q -p --Auto nim-fb.acore

The project_exec file will set up the game with 4, 3, 2, 1, 0, 0, 0, 1 tokens in the eight buckets.  It should allow up
to seven tokens to be removed at a time, from one bucket.
  So far (Mar 25, 2024), the setup works flawlessly, but the game algorithm doesn't seem to behave according to the rules.


nim-fc.ww gives a part of the program in source format from a CHM tape...  This version does the initialization
but does not appear to include the game algorithm.


