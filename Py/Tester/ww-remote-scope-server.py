import socket
import wwinfra
from graphics import GraphicsError

"""

  LAS 8/9/26 This file gathers up the major pieces of code used for
  the Remote Scope experiment, which was largely successful, but not
  (yet) very useful.

  Note this file is just a repository for the code and doesn't run
  as-is. To get it going again, put the client classes in wwinfra, add
  the intercept calls to ww_draw fcns as shown, define args in the sim
  for control, and restore this file to server-only.

  The first section shows args added to the sim to specify use of the
  remote scope.

  The next section, of routines from graphics output, shows where we
  intercept the calls to send to the remote server.

  The next section is a set of classes to enable the client side,
  e.g.,implements the "send" method used in the ww_draw calls.

  The final section is the server itself, based on good-old socket
  bind/listen/accept.

"""

    parser.add_argument("--RemoteScope", help="Display graphical output on the remote scope server (default localhost)", action="store_true")
    parser.add_argument("--RemoteScopeOnly", help="Don't bring up scope on local machine too", action="store_true")
    parser.add_argument("--RemoteScopeServer", help="Remote scope server machine name or IP addr (default localhost)", type=str)

    if (args.RemoteScope or
        args.RemoteScopeServer is not None or
        args.RemoteScopeOnly):
        cb.remote_scope = wwinfra.RemoteScope (args.RemoteScopeServer)

    if args.RemoteScopeOnly:
        cb.remote_scope_only = True




    def ww_draw_char(self, ww_x, ww_y, mask, expand, scope=None):
        if scope is None:
            scope = self.cb.SCOPE_MAIN
        if self.cb.ana_scope:
            self.cb.ana_scope.drawChar(ww_x, ww_y, mask, expand, self, scope=scope)
        else:
            if self.cb.remote_scope is not None:
                cmd = "C %d %d %d %d E " % (ww_x, ww_y, mask, expand)
                self.cb.remote_scope.send (cmd)
            if not self.cb.remote_scope_only:
                x0, y0 = self.ww_to_xwin_coords(ww_x, ww_y)
                obj = XwinCrtObject(x0, y0, 0, 0, 'C', mask, expand = expand)
                self.screen_brightness[obj] = self.BRIGHT
        pass

    def ww_draw_line(self, ww_x0, ww_y0, ww_xd, ww_yd, scope=None):
        if scope is None:
            scope = self.cb.SCOPE_MAIN
        self.cb.log.info("ww_draw_line: pt=(%d,%d) len=(%d,%d), scope=%d" % (ww_x0, ww_y0, ww_xd, ww_yd, scope)) 
        if self.cb.ana_scope:
                self.cb.ana_scope.drawVector(ww_x0, ww_y0, ww_xd>>2, ww_yd>>2, scope=scope)
        else:
            if self.cb.remote_scope is not None:
                cmd = "L %d %d %d %d E " % (ww_x0, ww_y0, ww_xd, ww_yd)
                self.cb.remote_scope.send (cmd)
            if not self.cb.remote_scope_only:
                ww_x1 = ww_x0 + ww_xd
                ww_y1 = ww_y0 + ww_yd
                x0, y0 = self.ww_to_xwin_coords(ww_x0, ww_y0)
                x1, y1 = self.ww_to_xwin_coords(ww_x1, ww_y1)
                obj = XwinCrtObject(x0, y0, x1, y1, 'L', 0)
                self.screen_brightness[obj] = self.BRIGHT
        pass
    
    def ww_draw_point(self, ww_x, ww_y, color=(0.0, 1.0, 0.0), scope=None, light_gun=False):  # default color is green
        if scope is None:
            scope = self.cb.SCOPE_MAIN
        self.cb.log.info("ww_draw_point: x=%d, y=%d, scope=%d, gun_enable=%d" % (ww_x, ww_y, scope, light_gun)) 
        if self.cb.ana_scope:
            self.cb.ana_scope.drawPoint(ww_x, ww_y, scope=scope)
            if light_gun:
                self.last_pen_point = True  # remember the point was seen; not sure this really matters...
        else:
            red = color[0]
            green = color[1]
            blue = color[2]
            if self.cb.remote_scope is not None:
                cmd = "D %d %d %f %f %f E " % (ww_x, ww_y, red, green, blue)
                self.cb.remote_scope.send (cmd)
            if not self.cb.remote_scope_only:
                x0, y0 = self.ww_to_xwin_coords(ww_x, ww_y)
                obj = XwinCrtObject(x0, y0, 0, 0, 'D', 0)
                obj.red = red
                obj.green = green
                obj.blue = blue
                self.screen_brightness[obj] = self.BRIGHT
                if light_gun:
                    self.last_pen_point = obj  # remember the point so it can be undrawn later
        pass

    def ww_highlight_point(self):
        if self.last_pen_point is not None:
            if not self.cb.remote_scope_only:
                x0 = self.last_pen_point.x0
                y0 = self.last_pen_point.y0
                c = self.gfx.Circle(self.gfx.Point(x0, y0), 5)  # the last arg is the circle dimension
                c.setFill("Red")
                c.draw(self.win)
                self.last_pen_point = None
            if self.cb.remote_scope is not None:
                cmd = "H E "
                self.cb.remote_scope.send (cmd)
        pass


# These two classes support remote scope clients

class RemoteUtility:
    def __init__ (self):
        self.bufferLim: int = 512
        # The example on the net used port 65432. Avoid using that port and
        # instead use the next highest prime number. This is both arbitrary and
        # capricious.
        self.port = 65437
        pass
    
class RemoteScope (RemoteUtility):
    def __init__ (self, host: str):
        super().__init__()
        self.buffer: str = "R E "
        if host is None:
            host = socket.gethostname()
        s = socket.socket (socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect ((host, self.port))
        except OSError as e:
            print ("Error connecting to remote scope server: %s" % e)
            sys.exit (-1)
        self.remote_scope_socket = s
        self.sendBuffer()
        pass
    # public
    def send (self, msg: str):
        if len (self.buffer) + len (msg) > self.bufferLim:
            self.sendBuffer()
        self.buffer += msg
        pass
    # public
    def update (self):
        self.send ("U E ")
        self.sendBuffer()
        pass
    # private
    def sendBuffer (self):
        try:
            self.remote_scope_socket.sendall (bytes (self.buffer, "utf-8"))
            self.buffer = ""
        except OSError as e:
            print ("Error sending data to remote scope server: %s" % e)
            sys.exit (-1)
        pass




# This and the Server class support a remote scpe server

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
