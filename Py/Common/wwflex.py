import os
import sys
import argparse
import datetime
import time
import math
from enum import Enum
import graphics as gfx
from tkinter import TclError
import wwinfra 

#
# Flexowriter support library
# main program provides test path
#
# Public classes are FlasciiToFlex, FlexToFlascii, FlexToComment, and FlexToFlexoWin.
#

# Use this class multiple-inheritance-style to hold common utilities

class AsciiFlexBase:
    def __init__ (self):
        self.cb = wwinfra.ConstWWbitClass (get_screen_size=True)
    def error (self, msg: str):
        # self.cb.log.error (msg)
        print ("Error!", msg)
    def isDigit (self, c) -> bool:
        return c >= '0' and c <= '9'

# The Flascii language, i.e., a format for specifying all the possible flex
# codes. In summary:
#
#        - Most printable ascii characters map to a unique flex code with a
#          shift bit.
#
#        - Newline, tab, and backspace also map to unique flex codes, and the
#          shift bit is ignored.
#
#        - "Upper case numbers" -- flex's name for superscript numbers -- are
#          supported as ^n. ^ has no flex code. When encountered, the
#          next contiguous set of digits will be superscripted, or
#          upcased in flex parlance. We'll make the resonable
#          assumption that any non-digit encountered returns to lower
#          case. So "^1 2" will produce a super 1 and a normal 2, but
#          "^12" will super both the 1 and the 2.
#
#        - Flex characters such as "stop" will be denoted "<stop>". See the
#          table below for all the formats.


# This level just gets tokens; they're checked at the next level up.

FlasciiTokenType = Enum ("FlasciiTokenType",
                         ["Character",
                          "Super",
                          "Bracketed",
                          "EndOfString"])

class FlasciiToken:
    def __init__ (self, type: FlasciiTokenType, data: str):
        self.type: FlasciiTokenType = type
        self.data = data

class FlasciiTokenizer (AsciiFlexBase):
    def __init__ (self, str):
        self.pos = 0
        self.state = 0
        self.str = str
        self.slen = len (str)
        # self.cb = theConstWWbitClass
        self.endOfString = "<EndOfString>"
        self.endOfStringTok = FlasciiToken (FlasciiTokenType.EndOfString, "")
    def getToken (self) -> FlasciiToken:
        data = ""
        while self.pos <= self.slen:
            if self.pos < self.slen:
                c = self.str[self.pos]
            else:
                c = self.endOfString
            # print (c, self.state, self.pos) # LAS
            if self.state == 0:
                if c == '^':
                    self.state = 1
                    self.pos += 1
                elif c == '<':
                    self.state = 3
                    self.pos += 1
                elif c == self.endOfString:
                    return self.endOfStringTok
                else:
                    self.state = 0
                    self.pos += 1
                    return FlasciiToken (FlasciiTokenType.Character, c)
            elif self.state == 1:
                if self.isDigit (c):
                    self.state = 2
                    self.pos += 1
                    data += c
                elif c == "-":
                    self.state = 2
                    self.pos += 1
                    data += c
                else:
                    self.state = 0
                    return FlasciiToken (FlasciiTokenType.Super, data)
            elif self.state == 2:
                if self.isDigit (c):
                    self.state = 2
                    self.pos += 1
                    data += c
                else:
                    self.state = 0
                    return FlasciiToken (FlasciiTokenType.Super, data)
            elif self.state == 3:
                if c == '>':
                    self.state = 0
                    self.pos += 1
                    return FlasciiToken (FlasciiTokenType.Bracketed, '<' + data + '>')
                elif c == self.endOfString:
                    self.error ("Unterminated bracketed op %s" % '<' + data )
                    return self.endOfStringTok
                else:
                    self.state = 3
                    self.pos += 1
                    data += c
            else:
                print ("Internal error: Unexpected state %d in FlasciiTokenizer" % self.state)
                exit(1)
        return self.endOfStringTok

class AsciiFlex (AsciiFlexBase):
    def __init__ (self):
        # self.cb = theConstWWbitClass
        self.curCodeTable: dict = None
        self.upperCodeTable: dict = {}          # ascii to flex
        self.lowerCodeTable: dict = {}
        self.upperAsciiTable: dict = {}         # flex to ascii
        self.lowerAsciiTable: dict = {}
        self.readableAsciiTable: dict = {}      # Flex to ascii, but sparse (for -r)
        self.buildTables()
    def buildTables (self):
        for e in AsciiFlexCodes.codes:
            readable = ""
            unprintable = ""
            if len (e) == 3:
                (flexCode, lcAscii, ucAscii) = e
            else:
                (flexCode, lcAscii, ucAscii, readable) = e                
            self.lowerCodeTable[lcAscii] = flexCode
            self.upperCodeTable[ucAscii] = flexCode
            self.upperAsciiTable[flexCode] = ucAscii
            self.lowerAsciiTable[flexCode] = lcAscii
            if readable != "":
                self.readableAsciiTable[flexCode] = readable
        self.curCodeTable = self.lowerCodeTable
        pass
    # These return true if a shift was in fact required
    def checkShiftUp (self) -> bool:
        if self.curCodeTable != self.upperCodeTable:
            self.curCodeTable = self.upperCodeTable
            return True
        else:
            return False
    def checkShiftDown (self) -> bool:
        if self.curCodeTable != self.lowerCodeTable:
            self.curCodeTable = self.lowerCodeTable
            return True
        else:
            return False

# Provide a string, then use getFlex to get the resulting list of flex codes.
# If addStopCode is True, add the <stop> char to the end of the resulting set
# of flex codes.

class FlasciiToFlex (AsciiFlex):
    def __init__ (self, asciiIn: str, addStopCode: bool = False):
        super().__init__()
        self.addStopCode = addStopCode
        self.asciiIn = asciiIn + ("<stop>" if self.addStopCode else "")
        self.flexOut = []
    def checkShiftUp (self):
        if super().checkShiftUp():
            self.flexOut.append (self.curCodeTable["<shift up>"])
    def checkShiftDown (self):
        if super().checkShiftDown():
            self.flexOut.append (self.curCodeTable["<shift dn>"])
    def getFlex (self) -> [int]:
        tokenizer = FlasciiTokenizer (self.asciiIn)
        while True:
            tok: FlasciiToken = tokenizer.getToken()
            if tok.type == FlasciiTokenType.Character:
                if tok.data in self.lowerCodeTable:
                    self.checkShiftDown()
                elif tok.data in self.upperCodeTable:
                    self.checkShiftUp()
                else:
                    self.error ("No flex code for %s" % tok.data)
                if tok.data in self.curCodeTable:
                    self.flexOut.append (self.curCodeTable[tok.data])
            elif tok.type == FlasciiTokenType.Super:
                self.checkShiftUp()
                for c in tok.data:
                    self.flexOut.append (self.curCodeTable[c])
                self.checkShiftDown()
            elif tok.type == FlasciiTokenType.Bracketed:
                if tok.data in self.curCodeTable:
                    self.flexOut.append (self.curCodeTable[tok.data])
                else:
                    self.error ("Unknown bracketed op %s" % tok.data)
            elif tok.type == FlasciiTokenType.EndOfString:
                return self.flexOut
        pass

# Base class for conversions from Flex to other forms. All conversions need to
# use a stateful model.
#
# These classes are init'ed either bare or with a list of flex codes. If bare
# then each call to addCode adds to the set of be converted. If a list is
# passed then all the codes for that list are added upon creation. More may be
# added if desired, but a typical use is to conver a block at once, i.e., it's
# just a function. Both styles are useful. In any case to get the final string
# getXXX is called.

class FlexToSomething (AsciiFlex):
    def __init__ (self):
        super().__init__()
        self.upcase: bool = False
        self.colorRed: bool = False
        self.asciiOut = ""
    def addCodes (self, flexCodes: [int]):
        for code in flexCodes:
            self.addCode (code)
        return self
    def addCode (self, flexCode: int):
        # Subclass def
        pass

# Convert Flex code-by-code (via addCode), building up a string in the Flascii
# format. Get the resulting string with getFlascii.
#
# We assume that initially we're in a downshifted and uncolored state.

class FlexToFlascii (FlexToSomething):
    def __init__ (self):
        super().__init__()
        self.state = 0
    def accumAndSetColor (self, ascii: str):
        if ascii == "<color>":
            self.colorRed = not self.colorRed
        self.asciiOut += ascii
    def checkValidCode (self, flexCode):
        if flexCode not in self.lowerAsciiTable:
            self.accumAndSetColor ("<invalid flex %d>" % flexCode)
            return False
        else:
            return True
    def addCode (self, flexCode: int):
        if self.checkValidCode (flexCode):
            if self.state == 0:
                ascii = self.lowerAsciiTable[flexCode]
                if ascii == "<shift up>":
                    self.state = 1
                elif ascii == "<shift dn>":
                    self.state = 0
                else:
                    self.accumAndSetColor (ascii)
            elif self.state == 1:
                ascii = self.upperAsciiTable[flexCode]
                if self.isDigit (ascii) or ascii == "-":
                    self.asciiOut += "^" + ascii
                    self.state = 2
                elif ascii == "<shift dn>":
                    self.state = 0
                elif ascii == "<shift up>":
                    self.state = 1
                else:
                    self.accumAndSetColor (ascii)
                    self.state = 1
            elif self.state == 2:
                ascii = self.upperAsciiTable[flexCode]
                if self.isDigit (ascii) or ascii == "-":
                    self.asciiOut += ascii
                    self.state = 2
                elif ascii == "<shift dn>":
                    self.state = 0
                elif ascii == "<shift up>":
                    self.state = 2
                else:
                    self.accumAndSetColor (ascii)
                    self.state = 1
            else:
                print ("Internal error: Unexpected state %d in FlexToFlascii" % self.state)
                exit (1)
        pass
    def getFlascii (self) -> str:
        return self.asciiOut


# make_filename_safe     tab, bs -> ' ', else any ctl char -> ''. Used in decode_556_file, to get ww_file.title
#                        Also used in decode_a_flexo_byte in read_7ch, but in commented-out code
# ^--- ortho ---v
# show_unprintable       Used in decode_ww_loader_format to get ww_file.title
# v--Can be used with either of the above
# ascii_only             Replaces <del> and <color> with the empty string. Option to wwutd when making .fc files

    
# Convert from Flex to .fc format. This will emit Ansi escape codes for color,
# rather than <color>, otherwise same as Flascii.
#
# The utility of asciiOnly is not clear except to eliminate the Ansi color
# escape sequences.

class FlexToFc (FlexToFlascii):
    def __init__ (self, asciiOnly = False):
        super().__init__()
        self.asciiOnly = asciiOnly
    def accumAndSetColor (self, ascii: str):
        if ascii == "<color>":
            self.colorRed = not self.colorRed
            if not self.asciiOnly:
                if self.colorRed:
                    self.asciiOut += "\033[1;31m"
                else:
                    self.asciiOut += "\033[0m"
        elif ascii == "<del>" and self.asciiOnly:
            pass
        else:
            self.asciiOut += ascii

# Used to satisfy show_unprintable

class FlexToCsyntaxFlascii (FlexToFc):
    def __init__ (self):
        super().__init__()
        self.dict = {'\n': '\\n', '\t': '\\t'}
    def accumAndSetColor (self, ascii: str):
        if ascii in self.dict:
            ascii = self.dict[ascii]
        self.asciiOut += ascii

# Used to satisfy make_filename_safe

class FlexToFilenameSafeFlascii (FlexToFc):
    def __init__ (self):
        super().__init__()
        self.dict = {'\n': '', '\t': ' ', '\b': ' '}
    def accumAndSetColor (self, ascii: str):
        if ascii in self.dict:
            ascii = self.dict[ascii]
        elif len (ascii) > 0 and ascii[0] == '<':    # [Guy's original comment] if we're making a file name, ignore all the control functions in the table above
            ascii = ''
        self.asciiOut += ascii

# Produce the "readable" set of lines for the -r option to ww-ASCII-to-Flexo.py

class FlexToComment (FlexToSomething):
    def __init__ (self):
        super().__init__()
    def addCode (self, flexCode: int):
        if self.upcase:
            ascii = self.upperAsciiTable[flexCode]
        else:
            ascii = self.lowerAsciiTable[flexCode]
        readableAscii = self.readableAsciiTable[flexCode] if flexCode in self.readableAsciiTable else ""
        if ascii == "<shift up>":
            self.upcase = True
        elif ascii == "<shift dn>":
            self.upcase = False
        elif ascii == "<color>":
            self.colorRed = not self.colorRed
        if readableAscii != "":
            ascii = readableAscii
        self.asciiOut += "; %06o %s\n" % (flexCode, ascii)
        pass
    def getComment (self) -> str:
        return self.asciiOut

# Creates a FlexoWin, and each incoming call to addCode(flexCode) prints any
# printable code to that FlexoWin.
    
class FlexToFlexoWin (FlexToSomething):
    def __init__ (self):
        super().__init__()
        self.flexoWin = FlexoWin()
    def addCode (self, flexCode: int):
        if self.upcase:
            ct = self.upperAsciiTable
        else:
            ct = self.lowerAsciiTable
        ascii = ct[flexCode] if flexCode in ct else ''
        if ascii == "<shift up>":
            self.upcase = True
        elif ascii == "<shift dn>":
            self.upcase = False
        elif ascii == "<color>":
            self.colorRed = not self.colorRed
        elif self.isDigit (ascii) or ascii == "-":
            if self.upcase:
                self.flexoWin.writeChar (ascii, super = True, colorRed = self.colorRed)
            else:
                self.flexoWin.writeChar (ascii, super = False, colorRed = self.colorRed)
        elif ascii in ["<stop>", "<nullify>"]:
            # Just ignore these, not sure there is behavior worth emulating
            pass
        else:
            self.flexoWin.writeChar (ascii, super = False, colorRed = self.colorRed)

#
# This table is based on 2M-0277, Table 1, Page 106
#    

class AsciiFlexCodes:
    codes = [
        #
        #                                    
        # code    lc           uc            ww-ASCII-to-flexo.py -r
        #
        [0o2,    'e',          'E'],
        [0o3,    '8',          '8'],
        [0o5,    '|',          '_'],
        [0o6,    'a',          'A'],
        [0o7,    '3',          '3'],
        [0o10,   ' ',          ' ',          'sp'],       # Space
        [0o11,   '=',          ':'],
        [0o12,   's',          'S'],
        [0o13,   '4',          '4'],
        [0o14,   'i',          'I'],
        [0o15,   '+',          '/'],
        [0o16,   'u',          'U'],
        [0o17,   '2',          '2'],
        [0o20,   '<color>',    '<color>',    'color'],
        [0o21,   '.',          ')'],
        [0o22,   'd',          'D'],
        [0o23,   '5',          '5'],
        [0o24,   'r',          'R'],
        [0o25,   '1',          '1'],
        [0o26,   'j',          'J'],
        [0o27,   '7',          '7'],
        [0o30,   'n',          'N'],
        [0o31,   ',',          '('],
        [0o32,   'f',          'F'],
        [0o33,   '6',          '6'],
        [0o34,   'c',          'C'],
        [0o35,   '-',          '-'],                      # Upper case '-' is for superscripts, e.g. for negative exponents
        [0o36,   'k',          'K'],
        [0o40,   't',          'T'],
        [0o42,   'z',          'Z'],
        [0o43,   '\b',         '\b',         'bs'],       # Backspace
        [0o44,   'l',          'L'],
        [0o45,   '\t',         '\t',         'tab'],      # Tab
        [0o46,   'w',          'W'],
        [0o50,   'h',          'H'],
        [0o51,   '\n',         '\n',         'cr'],       # Newline
        [0o52,   'y',          'Y'],
        [0o54,   'p',          'P'],
        [0o56,   'q',          'Q'],
        [0o60,   'o',          'O'],
        [0o61,   '<stop>',     '<stop>',     'stop'],
        [0o62,   'b',          'B'],
        [0o64,   'g',          'G'],
        [0o66,   '9',          '9'],
        [0o70,   'm',          'M'],
        [0o71,   '<shift up>', '<shift up>', 'shift up'], 
        [0o72,   'x',          'X'],
        [0o74,   'v',          'V'],
        [0o75,   '<shift dn>', '<shift dn>', 'shift dn'],
        [0o76,   '0',          '0'],
        [0o77,   '<del>',      '<del>',      'del']
        ]
    def __init__ (self):
        self.codeSet = [codeInfo[0] for codeInfo in self.codes]
    def isValidCode (self, flexCode: int) -> bool:
        return flexCode in self.codeSet


# Check noxwin option!!!!!

# From 2M-027, page 46:
# Printer Response Times
# 
# The approximate times required for the printer to carry out various
# processes are listed below:
# 
# Print any alphanumerical character or symbol, space, color change,
# upper and lower case shifts:
#       125 milliseconds
# Back space:
#       180 milliseconds
# Tabulation and carriage return:
#       200 to 900 milliseconds

class FlexoWin (AsciiFlexBase):
    def __init__(self):
        super().__init__()
        self.crTime = 50e-3         # Set these based on the times above for "authentic" timing
        self.charTime = 10e-3
        (self.screen_h, self.screen_v, self.gfx_scale_factor) = self.cb.get_display_size()
        # The factors used to size the window are based on LAS's desktop monitor.
        self.h = math.floor ((1000/3840) * self.screen_h)
        self.v = math.floor ((1500/2160) * self.screen_v)
        self.win = gfx.GraphWin ("Flexowriter", self.h, self.v)
        self.win.setBackground ("cornsilk")     # A color that really looks old-fashioned
        imageName = os.path.normpath (os.environ["PYTHONPATH"] + "/" + "flexowriter-scaled-cropped.gif")
        
        # Here we try each filename format, after os-norm, first using the
        # normed format, and if that fails, trying forward-slash-based
        # pathnames. There is something funny about Tcl or Cygwin or both,
        # where on Cygwin it only accepts Unix pathnames, so Windows-based
        # pathnames produce file-not-found. So the norm is Windows-based, but
        # tk wants Unix. Note could use os.exists but that accepts Windows
        # format and says yes the file exists (but Tcl thinks it doesn't) so we
        # really need to intercept the Tcl error. Also note that since this is
        # a system file clean error messages and such are not needed.

        try:
            self.image = gfx.Image (gfx.Point (0, 0), [imageName])
        except TclError as e:
            imageName = imageName.replace ("\\", "/")
            self.image = gfx.Image (gfx.Point (0, 0), [imageName])
            
        self.imageH = self.image.getWidth()
        self.imageV = self.image.getHeight()
        self.image = gfx.Image (gfx.Point (self.h/2, self.v - self.imageV/2), [imageName])
        self.image.draw (self.win)
        self.textX = self.h/3
        self.charX = self.textX
        self.textY = self.v - self.imageV/2 - 250
        self.texts = []
        pass

    def newText (self, c: str, charX: int, charY: int, super: bool, colorRed: bool) -> gfx.Text:
        if super:
            charY -= 5
        text = gfx.Text (gfx.Point (charX, charY), c)
        text.setFace ("courier")
        text.setTextColor ("red" if colorRed else "black")
        text.setSize (12 if super else 15)
        return text

    # This does not accept direct flex code, leaving that logic to the
    # AsciiFlex classes. Accepted here is an ascii char, and modifiers for
    # superscript and color

    def writeChar (self, c: str, super: bool = False, colorRed: bool = False):
        if c in ["\n", "\\n"]:      # Accept the real ascii char or printed rep
            for i in range (0, len (self.texts)):
                self.texts[i].move (0, -25)
            self.charX = self.textX
            time.sleep (self.crTime)
        else:
            charY = self.textY
            t = self.newText (c, self.charX, charY, super, colorRed)
            self.texts.append (t)
            self.charX += 12
            time.sleep (self.charTime)
            t.draw (self.win)

# Test area
    
testText1 = "\
ABC\n\
def\n\
<stop>\n\
x^42\n\
<nullify>\n\
<shift up>abc<shift dn>\n\
<color>\n\
<yyy>\n\
<xxx\n"

testText2 = "\
m=~1,\n\
z=0,\n\
1 Dz=0,\n\
7 p=xd|^0/c+p|^0,\n\
<color>\
8 q=.0001p,\n\
u=10000/c|^10+c|^11q+c|^12q^2+c|^13q^3,\n\
<color>\
q|^1=F^3 ^4(a),\n\
\n\n\n\n"

# The test in Tests/flex runs this without -w, so the virtual flexowriter
# window will pop up, display the text, and then be gone.

def main ():
    parser = wwinfra.StdArgs().getParser (".")
    parser.add_argument ("-w", "--Wait", help="Wait for input before exiting, to allow viewing of the virual flexowriter window", action="store_true")
    cmdArgs = parser.parse_args()
    text = testText2
    a = FlasciiToFlex (text)
    f = a.getFlex()
    print (text, f)
    
    b = FlexToFlascii()
    for c in f:
        b.addCode (c)
    sys.stdout.write (b.getFlascii())
    sys.stdout.write (FlexToComment().addCodes(f).getComment())

    fc = FlexToFc()
    for c in f:
        fc.addCode (c)
    sys.stdout.write (fc.getFlascii())
    
    w = FlexToFlexoWin()
    for c in f:
        w.addCode (c)
    if cmdArgs.Wait:
        input ("Press return to exit: ")

if __name__ == "__main__":
    main()
