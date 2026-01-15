
# mk-kit copies a bunch of base files needed to install the WW Sim on a new RasPi
# The kit assumes that we're starting with a working system...
# Guy Fedorkow, Dec 24, 2025

GPATH=~/History-of-Computing/Whirlwind/GitHub/Shell-Scripts

cd ~ 
cp .basrc .vimrc  .viminfo  .nanorc .bash_profile .gitconfig  $GPATH/pi-kit

cd ~/bin
cp auto-ping  no-blank  pinger.sh  run-ww  wwasm  ww-shell  wwsim  $GPATH/pi-kit/bin

cd
cp -r  ~/config-ww $GPATH/pi-kit/config-ww

cp ~/History-of-Computing/Whirlwind/GitHub/.git/config  $GPATH/pi-kit/History-of-Computing/Whirlwind/GitHub/.git/

cp ~/History-of-Computing/Whirlwind/Hardware/Micro-Whirlwind/GitHub/.git/config  $GPATH/pi-kit/History-of-Computing/Whirlwind/Hardware/Micro-Whirlwind/GitHub/.git/

sudo cp -p -r /home/ww-demo $GPATH/pi-kit/
