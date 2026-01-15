
# install-kit copies a bunch of base files needed to install the WW Sim on a new RasPi
# 
# Guy Fedorkow, Dec 24, 2025

GPATH=~/History-of-Computing/Whirlwind/GitHub/Shell-Scripts

cd $GPATH/pi-kit 
cp .bashrc .vimrc  .viminfo  .nanorc .bash_profile .gitconfig  ~

mkdir -p ~/bin
cd  $GPATH/pi-kit/bin
cp auto-ping  no-blank  pinger.sh  run-ww  wwasm  ww-shell  wwsim  ~/bin


cd  $GPATH/pi-kit/
cp -r  config-ww ~/config-ww

mkdir -p  ~/History-of-Computing/Whirlwind/GitHub/.git
mkdir -p  ~/History-of-Computing/Whirlwind/Hardware/Micro-Whirlwind/GitHub/.git


cp $GPATH/pi-kit/History-of-Computing/Whirlwind/GitHub/.git/config    ~/History-of-Computing/Whirlwind/GitHub/.git/

cp $GPATH/pi-kit/History-of-Computing/Whirlwind/Hardware/Micro-Whirlwind/GitHub/.git/config   ~/History-of-Computing/Whirlwind/Hardware/Micro-Whirlwind/GitHub/.git/


# Set up the ww-demo user and group
sudo adduser ww-demo  --firstuid 1000 --firstgid 1000
sudo chmod 755 /home/guyfe /home/ww-demo

cd $GPATH/pi-kit/ww-demo
sudo cp -p .bashrc .vimrc  .nanorc .bash_profile /home/ww-demo
sudo cp -p -r bin /home/ww-demo/ 
