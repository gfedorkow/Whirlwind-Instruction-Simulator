





















from screeninfo import get_monitors
from vpython import *

# scene.visible = False # while preparing the scene

title = "Click and drag the mouse in the 3D canvas to insert and drag a small sphere."
scene.title = title
scene.range = 10 # 3

scene.width = 1500
scene.height = 1000

"""
for i in range (0, 100):
    arrow (pos=vector(-1,-1.3 - .2*i,0), color=color.orange)
"""

"""
b = box (pos = vector(0,0,0), width = .5, length = 1.5, height = 1.5, color = color.gray (.3))
con  = cone (pos=vector(0,+0.3,2), axis=vector(0,-0.3,-2), radius = .5, color=color.gray (.5))
coff = cone (pos=vector(0,-0.3,2), axis=vector(0,+0.3,-2), radius = .5, color=color.gray (.5))
e = extrusion (path=[vector(0,0,.25), vector(0,0,.75)],
               shape=shapes.circle (radius=.5, thickness=0.4), color=color.gray (.5))
toggleoff = compound ([b,coff,e])
toggleon = compound ([b,con,e])
toggleon.visible = False
"""

"""
ring(pos=vector(-0.6,-1.3,0), size=vector(0.2,1,1), color=color.green)
sph = sphere(pos=vector(1,1,1), radius=0.1, color=color.red)

Lshaft = 1 # length of gyroscope shaft
Rshaft = 0.03 # radius of gyroscope shaft
Rrotor = 0.4 # radius of gyroscope rotor
Drotor = 0.1 # thickness of gyroscope rotor
a = vector(1,0,0)
shaft = cylinder(axis=Lshaft*a, radius=Rshaft, color=vector(0.85,0.85,0.85))
rotor = cylinder(pos=0.5*a*(Lshaft-Drotor), opacity=0.2,
                 axis=Drotor*a, radius=Rrotor, color=vector(0.5,0.5,0.5))
stripe = box(pos=rotor.pos+0.5*vector(Drotor,0,0),
              size=vector(0.03*Rrotor,2*Rrotor,0.03*Rrotor), color=color.black)
gyro = compound([rotor, shaft, stripe])
"""

x = arrow (pos = vector(0,0,0), axis = vector(1,0,0))
xt = text (pos = vector(1,0,0), text = "x")
y = arrow (pos = vector(0,0,0), axis = vector(0,1,0))
yt = text (pos = vector(0,1,0), text = "y")
z = arrow (pos = vector(0,0,0), axis = vector(0,0,1))
zt = text (pos = vector(0,0,1), text = "z")
compound ((x, xt, y, yt, z, zt))

# A text obj by itself causes exceptions on selction, but works ok when
# embedded in a compound.
crap = compound ([text (pos = vector(1,4,0), text = "If it isn't Scottish it's crap!")])

class ObjPair:
    def __init__ (self, pos: vector):
        self.isOn = False
        self.pos = pos
        self.objOff = None
        self.objOn = None
        self.alsoToggle = None
    def isHit (self, obj) -> bool:
        return obj == self.objOn or obj == self.objOff
    def toggle (self) -> compound:
        curObj = self.objOff if not self.isOn else self.objOn
        otherObj = self.objOff if self.isOn else self.objOn
        otherObj.pos = curObj.pos
        curObj.visible = False
        otherObj.visible = True
        self.isOn = not self.isOn
        if self.alsoToggle is not None:
            self.alsoToggle.toggle()
        return otherObj
    # Rotate around the y-direction axis 
    def rotateY (self, angle):
        self.objOff.rotate (angle = angle,
                            axis = vector (0,1,0))
        self.objOn.rotate (angle = angle,
                           axis = vector (0,1,0))
        pass
    def setPos (self, pos: vector):
        self.objOff.pos = pos
        self.objOn.pos = pos

class ObjPairs:
    def __init__ (self):
        self.pairs: [ObjPair] = []
        pass
    def addPair (self, pair: ObjPair):
        self.pairs.append (pair)
    def findHit (self, obj) -> []:
        for p in self.pairs:
            if p.isHit (obj):
                return p
        return None

class LampPair (ObjPair):
    def __init__ (self, pos: vector):
        super().__init__ (pos)
        b = box (pos = vector (0, 0, 0), width = .5, length = 1.5, height = 1.5, color = color.gray (.3))
        e = extrusion (path=[vector(0,0,0.25), vector(0,0,0.75)],
        shape=shapes.circle (radius=0.5, thickness=0.4), color=color.gray (0.5))
        hshape = shapes.arc(angle1=0, angle2=0.999*pi/2, radius=0.3, thickness=0.01, pos=[-0.5,0] )
        hpath = paths.circle(radius=0.5)
        hemion = extrusion (shape=hshape, path=hpath, color=color.red)
        hemion.emissive = True
        hemion.opacity = 1.0
        hemion.rotate (angle = pi/2)
        hemion.pos = vector (0, 0, .85)
        hemioff = extrusion (shape=hshape, path=hpath, color=color.green)
        hemioff.emissive = True
        hemioff.opacity = 1.0
        hemioff.rotate (angle = pi/2)
        hemioff.pos = vector (0, 0, .85)
        self.objOff = compound ([b, e, hemioff])
        self.objOff.pos = pos
        self.objOff.visible = True
        self.objOn = compound ([b, e, hemion])
        self.objOn.pos = pos
        self.objOn.visible = False

class TogglePair (ObjPair):
    def __init__ (self, pos: vector):
        super().__init__ (pos)
        b = box (pos = pos, width = .5, length = 1.5, height = 1.5, color = color.gray (.3))
        hshape = shapes.arc (angle1=0, angle2=0.999*pi/2, radius=0.3, thickness=0.01, pos=[-0.5,0])
        hpath = paths.circle(radius=0.5)
        swcone = cone (pos = vector (0, 0, 0), axis=vector(0,0,2), radius = .3, color=color.gray (.4))
        swhemi = extrusion (shape=hshape, path=hpath, color=color.gray (.4))
        swhemi.rotate (angle = -pi/2)
        swhemi.pos = vector (0, 0, -0.15)
        swhandle = compound ([swcone, swhemi])
        swhandle.visible = False
        swhandle.rotate (angle = pi)
        swhon = swhandle.clone()
        swhon.rotate (angle = -pi/8)
        swhon.pos = pos + vector (0, 0, 0.75)
        swhoff = swhandle.clone()
        swhoff.rotate (angle = pi/8)
        swhoff.pos = pos + vector (0, 0, 0.75)
        e = extrusion (path=[pos+vector(0,0,0.25), pos+vector(0,0,0.75)],
            shape=shapes.circle (radius=0.5, thickness=0.4), color=color.gray (0.5))
        self.objOff = compound ([b,swhoff,e])
        self.objOn = compound ([b,swhon,e])
        self.objOn.visible = False

objPairs = ObjPairs()

class TogglePairs:
    def __init__ (self, n: int):
        for i in range (0, n):
            pos = vector (1.5*i, 0, 0)
            objPairs.addPair (TogglePair (pos))
        pass

class LampPairs:
    def __init__ (self, n: int):
        for i in range (0, n):
            pos = vector (1.5*i, 2, 0)
            objPairs.addPair (LampPair (pos))
        pass

class ToggleLampPairs:
    def __init__ (self, rowSize: int, colSize: int):
        dirs = [
            vector (1, 0, 0),
            vector (0, 0, -1),
            vector (-1, 0, 0),
            vector (0, 0, 1)
            ]
        pos0 = vector (-5, -5, 0)
        pos = pos0
        rot = 0
        for s in range (0, 4):
            dir = dirs[s]
            colpos = vector (pos.x, pos0.y, pos.z)
            for i in range (0, colSize):
                pos = colpos + vector (0, -5*i, 0)
                # pos = pos.x,pos0.y,0
                # pos = vector(dot(colpos,vector(1,0,0)),dot(pos0,vector(0,1,0)),dot(pos,vector(0,0,1))) + vector (0, -5*i, 0)
                for j in range (0, rowSize):
                    pos = pos + 1.6*dir
                    # p = pos + vector (0, -4.6, 0)
                    lp = LampPair (pos)
                    lp.rotateY (rot)
                    tp = TogglePair (vector (0, 0, 0))
                    tp.rotateY (rot)
                    tp.setPos (pos+vector(0,-2,0))
                    tp.alsoToggle = lp
                    objPairs.addPair (tp)
                    objPairs.addPair (lp)
            rot += pi/2
            pos = pos + 1.6*dir
        pass

# TogglePairs (10)
# LampPairs (10)

ToggleLampPairs (4,2)

# scene.visible = True # finished preparing the scene

class Handler:
    def __init__ (self):
        self.drag = True
        self.s = None
        screens = get_monitors()
        for s in screens:
            print ("LAS86", s.width, s.height)
    def grab (self, evt):
        global scene
        scene.title = 'Toggle switches.'
        self.drag = True
        if self.s is None:
            self.s = scene.mouse.pick
            if self.s is not None:
                tpHit = objPairs.findHit (self.s)
                if tpHit is not None:
                    self.s = tpHit.toggle()
    def move (self, evt):
        global scene
        if self.drag and self.s is not None:
            self.s.pos = scene.mouse.pos
            pass
    def drop (self, evt):
        global scene
        scene.title = title
        if self.s is not None:
            # self.s.color = color.cyan
            pass
        self.drag = False
        self.s = None
    def processEvent (self, e):
        if e.event == "mousedown":
            self.grab (e)
        elif e.event == "mouseup":
            self.drop (e)
        elif e.event == "mousemove":
            self.move (e)
        else:
            pass

h = Handler()

# scene.bind('mousedown',h.grab)
# scene.bind('mousemove',h.move)
# scene.bind('mouseup',h.drop)

scene.bind('mousedown',h.processEvent)
scene.bind('mousemove',h.processEvent)
scene.bind('mouseup',h.processEvent)

while True:
    rate(10)
    # scene.waitfor ("mousedown mouseup mousemove")
