#
# This shell file runs a dispatcher that posts a menu on the Analog Scope and
# waits for a Light Gun hit to trigger a demo program to run.  When the demo 
# program terminates, it returns to this dispatcher menu.
# Written by Rainer Glaschich at HNF, Oct 2023
# Integrated by guy, Dec 2023
#
# This code only runs on the Rasp Pi with Analog scope, as some of the programs are
# Python scripts that directly call the analog driver.
#
code=~/WW/GitHub/Code-Samples
base=~/WW/GitHub/Py/Shell
while true
do $base/scope-select.py
   rc=$?
   echo rc=$rc
   pwd
   p="continue"
   case $rc in
      0) exit;;
      1) p="python Py/Common/random-lines.py";;
      2) p="python $base/tictactoe.py";;
      3) p="wwsim $code/ --Ana -q";;
      4) p="wwsim $code/Tic-Tac-Toe/tic-tac-toe.acore --Ana -q";;
      5) p="wwsim $code/Bounce/Bounce-Tape-with-Hole/fb131-0-2690_bounce-annotated.acore --Ana -q";;
      6) p="wwsim $code/Mad-Game/mad-game.acore --Ana -q";;
      7) p="wwsim $code/Blackjack/bjack.acore --Ana -q";;
      8) p="wwsim $code/Diags/crt-test-68_001_fbl00-0-50.tcore --Ana -q";;
      9) p="wwsim $code/Vibrating-String/v97-closed-end.acore --Ana -q";;
     10) p="wwsim $code/Vibrating-String/v204-open-end.acore --Ana -q";;
     11) p="wwsim $code/Nim/nim-fb.acore --Ana -q";;
     12) p="wwsim $code/Number-Display/number-display-annotated.acore --Ana -q";;
     13) cd $code/Track-While-Scan-D-Israel/; p="wwsim annotated-track-while-scan.acore -D -r --CrtF 15 --NoToggl --Ana -c 0 -q --NoAlarmStop";;
     14) cd $code/Vector-Clock; p="wwsim vector-clock.acore --Ana -q";;
     15) p="wwsim $code/Lorenz/lorenz.acore --NoAlarm --Ana -q";;
    127) exit;;
      *) continue;;
   esac
   echo "prog=$p"
   sh -c "$p"
done
                        
                        
