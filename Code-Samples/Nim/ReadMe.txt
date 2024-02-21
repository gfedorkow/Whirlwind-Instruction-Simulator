Game of Nim - recovered code

g fedorkow, feb 21, 2024

See DCL-113 for instructions on how to work this game of "Generalized Nim"
The "control panel" (i.e., wwsim -p) is required, as user-intent is signalled via (emulated) switches.

Compiled from CS-II source from tape fc-131_102766757_fc131-247-12

The code is partly working; initialization of the game works, the first user-move works, but the second user move causes a jump to an undefined label, resulting in a sudden halt.
  Still debugging...
  
In the mean time, the 'real' source (and the debug framework) is still in a local repository


