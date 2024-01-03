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
code=~/WW/Code-Samples
base=~/WW/Py/Shell
while true
do $base/select.py
   rc=$?
   echo rc=$rc
   pwd
   p="continue"
   case $rc in
      0) continue;;
      1) p="python $base/vecIF.py";;
      2) p="python $base/tictactoe.py";;
      3) p="wwsim $code/Bounce/Bounce-Tape-with-Hole/fb131-0-2690_bounce-annotated.acore --Ana -q";;
      4) p="wwsim $code/Bounce/r-196-bounce-example/bounce.acore --Ana -q";;
      5) p="wwsim $code/Mad-Game/mad-game.acore --Ana -q";;
      6) p="wwsim $code/Blackjack/bjack.acore --Ana -q";;
      7) p="wwsim $code/Diags/crt-test-68_001_fbl00-0-50.tcore --Ana -q";;
      8) p="wwsim $code/Vibrating-String/fb131-97-setup-and-run-Annotated.acore --Ana -q";;
      9) p="wwsim $code/Vibrating-String/fc131-204-2-merged-annotated.acore --Ana -q";;
     10) p="wwsim $code/Lorenz/lorenz.acore --NoAlarm --Ana -q";;
     11) cd $code/Track-While-Scan-D-Israel/; p="wwsim annotated-track-while-scan.acore -D -r --CrtF 5 --NoToggl --Ana -c 0 -q";;
     12) cd $code/Vector-Clock; p="wwsim vector-clock.acore --Ana -q";;
     13) cd $code/Vector-Clock; p="wwsim vector-clock-gf.acore --Ana -q";;
     14) p="wwsim $code/Number-Display/number-display-annotated.acore --Ana -q";;
     15) exit;;
    127) exit;;
      *) continue;;
   esac
   echo "prog=$p"
   sh -c "$p"
done
                        
                        
