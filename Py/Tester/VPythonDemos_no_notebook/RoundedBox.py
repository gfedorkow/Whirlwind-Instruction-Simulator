from vpython import *
scene.visible = False
L = 1     # length of cube
R = 0.2   # radius of end sphere
C = L-2*R # length of cylinder and of square

def rounded_box(**kw):
    # Create a box with rounded corners whose radius R = Lmin*radius,
    #   where Lmin is the shortest of length, height, and wideth.
    #   Default R = 0.2*Dmin
    if 'size' in kw:
        size = kw['size']
        del kw['size']
    else:
        size = vec(1,1,1)
    L = size.x
    H = size.y
    W = size.z
    if 'length' in kw:
        L = kw['length']
        del kw['length']
    if 'height' in kw:
        H = kw['height']
        del kw['height']
    if 'width' in kw:
        W = kw['width']
        del kw['width']
    Lmin = min(L,H,W)
    if 'radius' in kw:
        R = kw['radius']*Lmin
        del kw['radius']
    else:
        R = 0.2*Lmin
    Cx = L-2*R # cylinder lengths
    Cy = H-2*R
    Cz = W-2*R
    
    # Make a path that goes around the box, with 4 straight sections and 4 curved sections
    p = [vec(-Cx/2,Cy/2,W/2)] # start at left end of upper front section
    p.extend( paths.arc(pos=vec(Cx/2,Cy/2,Cz/2), radius=R, angle1=-pi/2, angle2=0) )
    p.extend( paths.arc(pos=vec(Cx/2,Cy/2,-Cz/2), radius=R, angle1=0, angle2=pi/2) )
    p.extend( paths.arc(pos=vec(-Cx/2,Cy/2,-Cz/2), radius=R, angle1=pi/2, angle2=pi) )
    p.extend( paths.arc(pos=vec(-Cx/2,Cy/2,Cz/2), radius=R, angle1=pi, angle2=3*pi/2) )
    
    # Extrude a quarter-circle arc along the path p
    top = extrusion(path=p, shape=shapes.arc(pos=[-R,0], radius=R, angle1=0, angle2=pi/2))
    bottom = top.clone()
    bottom.rotate(angle=pi, axis=vec(1,0,0), origin=vec(0,0,0))
    
    # Make 4 vertical members linking the corners of the top and bottom
    vert1 = extrusion(path=[vec(Cx/2,-Cy/2,Cz/2), vec(Cx/2,Cy/2,Cz/2)], # right front
            shape=shapes.arc(radius=R, angle1=pi/2, angle2=pi))
    vert2 = vert1.clone(pos=vert1.pos+vec(0,0,-Cz-R)) # right back
    vert2.rotate(angle=pi/2, axis=vec(0,1,0))
    vert3 = vert2.clone(pos=vert2.pos+vec(-Cx-R,0,0)) # left back
    vert3.rotate(angle=pi/2, axis=vec(0,1,0))
    vert4 = vert1.clone(pos=vert1.pos+vec(-Cx-R,0,0)) # left front
    vert4.rotate(angle=-pi/2, axis=vec(0,1,0))
    
    # Make a quad for the top of the box
    v0 = vertex(pos=vec(-Cx/2,H/2,Cz/2), normal=vec(0,1,0))
    v1 = vertex(pos=vec(Cx/2,H/2,Cz/2), normal=vec(0,1,0))
    v2 = vertex(pos=vec(Cx/2,H/2,-Cz/2), normal=vec(0,1,0))
    v3 = vertex(pos=vec(-Cx/2,H/2,-Cz/2), normal=vec(0,1,0))
    q = compound( [quad(vs=[v0,v1,v2,v3])] ) # compound the quad; cannot clone a quad
    q1 = q.clone()
    q1.rotate(angle=pi, axis=vec(1,0,0), origin=vec(0,0,0)) # bottom quad
    q2 = q.clone()
    q2.rotate(angle=pi/2, axis=vec(1,0,0), origin=vec(0,0,0)) # front quad
    q3 = q.clone()
    q3.rotate(angle=-pi/2, axis=vec(1,0,0), origin=vec(0,0,0)) # back quad
    
    # Make a quad for the right side of the box
    v0 = vertex(pos=vec(L/2,Cy/2,Cz/2), normal=vec(1,0,0))
    v1 = vertex(pos=vec(L/2,-Cy/2,Cz/2), normal=vec(1,0,0))
    v2 = vertex(pos=vec(L/2,-Cy/2,-Cz/2), normal=vec(1,0,0))
    v3 = vertex(pos=vec(L/2,Cy/2,-Cz/2), normal=vec(1,0,0))
    q4 = compound( [quad(vs=[v0,v1,v2,v3])] ) # right side quad
    q5 = q4.clone()
    q5.rotate(angle=pi, axis=vec(0,1,0), origin=vec(0,0,0)) # left side quad
    c = compound([top, bottom, vert1, vert2, vert3, vert4, q, q1, q2, q3, q4, q5])
    if 'axis' in kw:
        c.axis = L*norm(kw['axis'])
        del kw['axis']
    for a in kw:
        setattr(c, a, kw[a])
    return c

rb = rounded_box(size=vec(2,1,1), color=color.cyan)
scene.visible = True
scene.pause('Click to change the axis')
rb.axis = vec(3,1,0)
