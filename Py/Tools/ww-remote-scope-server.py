import socket
import wwinfra
from graphics import GraphicsError

class Tokenizer:
    # handleTokenFcn (token: str) -> None
    def __init__ (self, handleTokenFcn):
        self.handleTokenFcn = handleTokenFcn
        self.state = 0
        self.token = ""
    def isWhitespace (self, c) -> bool:
        return c == ' ' or c == '\t'
    def handleChar (self, cInt: int):
        c: str = chr (cInt)
        if self.state == 0:
            if self.isWhitespace (c):
                pass
            elif c == '"':
                self.state = 1
            else:
                self.state = 3
                self.token = self.token + c
        elif self.state == 1:
            if c == '\\':
                self.state = 2
            elif c == '"':
                self.state = 0
                self.handleTokenFcn (self.token)
                self.token = ""
            else:
                self.token = self.token + c
        elif self.state == 2:
                self.token = self.token + c
                self.state = 1
        elif self.state == 3:
            if self.isWhitespace (c):
                self.state = 0
                self.handleTokenFcn (self.token)
                self.token = ""
            else:
                self.token = self.token + c
        else:
            print ("Unexpected state %d in Tokenizer" % self.state)
            exit (-1)

class Server (wwinfra.RemoteUtility):
    def __init__ (self):
        super().__init__()
        self.cb = wwinfra.ConstWWbitClass (get_screen_size = True)
        self.cb.this_is_remote_scope = True
        self.cb.use_x_win = True
        self.cb.log = wwinfra.LogFactory().getLog (quiet=True, no_warn=True)
        self.crt = wwinfra.XwinCrt (self.cb)
        self.cm = wwinfra.CorememClass (self.cb)
        self.tz = Tokenizer (self.handleToken)
        self.cmd: [int|str] = []
        pass
    def handleToken (self, token: str):
        if token == "E":
            self.doScopeCmd (self.cmd)
            self.cmd = []
        else:
            self.cmd.append (token)
        pass
    def doScopeCmd (self, cmd: []):
        op = cmd[0]
        if op == "L":
            x0 = int (cmd[1])
            y0 = int (cmd[2])
            xd = int (cmd[3])
            yd = int (cmd[4])
            self.crt.ww_draw_line (x0, y0, xd, yd)
        elif op == "D":         # "D" for "Dot" -- the convention used in XwinCrtObject
            x =   int (cmd[1])
            y =   int (cmd[2])
            r = float (cmd[3])
            g = float (cmd[4])
            b = float (cmd[5])
            self.crt.ww_draw_point (x, y, color = (r, g, b))
        elif op == "C":
            x       = int (cmd[1])
            y       = int (cmd[2])
            mask    = int (cmd[3])
            expand  = float (cmd[4])
            self.crt.ww_draw_char (x, y, mask, expand)
        elif op == "H":
            self.crt.ww_highlight_point()
        elif op == "U":
            self.crt.ww_scope_update (self.cm, self.cb)
        elif op == "R":
            self.crt.ww_scope_reset()
        pass
    def recv (self, msg: bytes):
        for c in msg:
            self.tz.handleChar (c)
        pass
    def run (self):
        while True:
            try:
                with socket.socket (socket.AF_INET, socket.SOCK_STREAM) as s:
                    host: str = socket.gethostname()
                    port = self.port
                    print ("Scope server running on %s, port %d" % (host, port))
                    s.bind ((host, port))
                    while True:
                        s.listen()
                        conn, addr = s.accept()
                        with conn:
                            print ("%s has connected to the scope server" % addr[0])
                            while True:
                                data = conn.recv (self.bufferLim)
                                if not data:
                                    print ("Scope server connection closed")
                                    break
                                self.recv (data)
            except GraphicsError:
                break
            except ConnectionResetError:
                self.cmd = []
                pass
        pass

def main ():
    Server().run()

main()
