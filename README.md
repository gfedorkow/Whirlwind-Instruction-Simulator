# Whirlwind
Software Recovery from 1950's MIT Whirlwind I computer development.

This project contains files that make up an instruction-set simulator for the MIT Whirlwind I computer, first brought on line end of 1949.
The project includes some files recovered from paper tape and magnetic tape, from 1949 to 1959.
Original media is stored in the Computer History Museum archive.

## Usage
Run `python wwasm/wwasm.py program.ww` to generate the assembled `.acore` file.
Run `python wwsim/wwsim.py program.acore` to run the simulator.

`Win-Binary/wwsim.exe` and `MacOS-Binary/wwsim` are prepackaged executables for the `wwsim.py` script bundled with all dependencies.

To regenerate the executable run `pyinstaller wwsim/wwsim.py --clean -F -p wwsim --hidden-import graphics`.

## References
- [Report R-196: Programming For Whirlwind I (1951)](http://www.bitsavers.org/pdf/mit/whirlwind/R-series/R-196_Programming_for_Whirlwind_I_Jun51.pdf)
- [Whirlwind Programming Manual (1958)](http://www.bitsavers.org/pdf/mit/whirlwind/M-series/2M-0277_Whirlwind_Programming_Manual_Oct58.pdf)
- [Making Electrons Count Film](https://teachingexcellence.mit.edu/from-the-vault/making-electrons-count-c-1950)
