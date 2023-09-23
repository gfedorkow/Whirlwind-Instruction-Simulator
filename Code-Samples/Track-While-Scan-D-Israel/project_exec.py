# project-specific python
# These project-specific files would usually contain functions called by .exec statements
# embedded in ww source code.


import wwinfra
import numpy as np
import math


def breakp():
    print("breakpoint")


def deg_to_rad(deg):
    return deg / 360.0 * (2 * np.pi)


Radar = None
Interceptor = None
Target = None


def project_register_radar(radar_arg):
    global Radar
    Radar = radar_arg


# this one returns the identity of the airplane being tracked based on the value
# of a state variable at location 0d241 in the WW code.
def which_plane(cm):  # figure out which plane we're scanning at the moment
    state = cm.rd(241)
    if state == 0o163777:
        ret = "Target"
    elif state == 0o14000:
        ret = "Interceptor"
    else:
        ret = "??"
    return ret


# When the simulator identifies a radar return as the Interceptor, we want to record which aircraft
# that is, so later we can start to steer the interceptor towards the target.
# Called from .exec when the sim initiates tracking of the last echo return
def record_initiation(cm, cb):
    global Radar
    global Interceptor, Target

    # which_plane returns a string to say whether the WW code is considering Target or Interceptor
    # The radar station knows which plane it last saw, so we can search the aircraft structs to find
    # the one we're Initiating
    # from there, we can set Globals inside project_exec to remember which is which
    state = which_plane(cm)
    which_tgt = None
    nametag = Radar.last_aircraft_name_sent
    for tgt in Radar.targets:
        if tgt.name == nametag:
            which_tgt = tgt
    if which_tgt is None:
        cb.log.warning("Not sure why we didn't find an airplane in record_initiation()")
    if state == "Interceptor":
        Interceptor = which_tgt
    if state == "Target":
        Target = which_tgt
        if cb.DebugWidgetPyVars.TargetHeading is not None:
            cb.DebugWidgetPyVars.TargetHeading.register(which_tgt)

    msg = "Initiate %s" % state
    cb.dbwgt.add_screen_print(2, msg)


def add_overflow_check(cpu, cm, addr_a, addr_b):
    a = cpu._AC
    b = cm.rd(addr_b)
    (wsum, _sam_out, alarm) = cpu.ww_add(a, b, 0)
    if True:  # alarm != 0:
        print("overflow check: a=0o%02o, b=0o%02o, sum=0o%o, alarm=%0d, addr_b=0d%d" % (a, b, wsum, alarm, addr_b))
#         dump_tracking_state(cm, cpu.decif)


# Undo the ones-complement
def py_int(ww_int):
    if ww_int & 0o100000:
        py_intv = -(ww_int ^ 0o177777)
    else:
        py_intv = ww_int
    return py_intv

# =======================================
# --------------------------------
# Intercept Solver
# Added May 25, 2023


# https://gist.github.com/LyleScott/e36e08bfb23b1f87af68c9051f985302
# Rotate X,Y (2D) coordinates around a point or origin in Python
def rotate_origin_only(xy, radians):
    """Only rotate a point around the origin (0, 0)."""
    x, y = xy
    xx = x * math.cos(radians) + y * math.sin(radians)
    yy = -x * math.sin(radians) + y * math.cos(radians)
    return xx, yy


# https://math.stackexchange.com/questions/2165564/is-there-a-way-to-solve-an-equation-with-both-sine-and-cosine-in-it

# https://en.wikipedia.org/wiki/Heading_(navigation)
# Heading is typically based on cardinal directions, so 0° (or 360°) indicates a direction toward
#   true north, 90° true east, 180° true south, and 270° true west.[1]


class GeometryClass:
    def __init__(self, xpos_t=30, ypos_t=-10, xpos_i=61, ypos_i=00, velo_i=250):
        self.V_interceptor = velo_i
        # self.Theta_target = 45 / 180 * np.pi
        self.X_interceptor_position = xpos_i
        self.Y_interceptor_position = ypos_i
        self.X_target_initial_position = xpos_t
        self.Y_target_initial_position = ypos_t

        self.dx = self.X_target_initial_position - self.X_interceptor_position
        self.dy = self.Y_target_initial_position - self.Y_interceptor_position

    # the following routine solves the intercept problem but, due to guy's limited abilities
    # with trigonometric function, doesn't do it for a wide enough range of initial conditions.
    # def solve_for_Theta_intercept_guy(self, Theta_target):
    #     s = self
    #     # sin(Theta_interceptor = sin(Theta_target) * V_target / V_intercept
    #     sin_Theta_interceptor = np.sin(Theta_target / 180 * np.pi) * s.V_target / s.V_interceptor
    #     # print("sin_Theta_i = %f" % sin_Theta_intercept)
    #     Theta_interceptor = np.arcsin(sin_Theta_interceptor) * 180 / np.pi
    #
    #     x_interceptor_velocity = np.cos(Theta_interceptor / 180 * np.pi) * s.V_interceptor
    #     x_target_velocity = np.cos(Theta_target / 180 * np.pi) * s.V_target
    #
    #     # D Isreal tagged Time to Intercept with the label Tau
    #     Tau = (self.X_target_initial_position - self.X_interceptor_position) / (
    #                 x_target_velocity - x_interceptor_velocity)
    #
    #     x_t_collision_point = self.X_target_initial_position + Tau * x_target_velocity
    #     x_i_collision_point = self.X_interceptor_position + Tau * x_interceptor_velocity
    #     if abs(x_t_collision_point - x_t_collision_point) > 0.0001:
    #         print("mismatch: x_t_collision_point=%4.5f, x_i_collision_point=%4.5f" % \
    #               (x_t_collision_point, x_i_collision_point))
    #
    #     print(
    #         "Solution #2: Theta_t %6.2f --> Theta_i=%6.2f, V_tx=%6.2f, V_ix=%6.2f, Tau=%4.3f, \
    #         x_t_collision_point=%4.2f" % \
    #         (Theta_target, Theta_interceptor, x_target_velocity, x_interceptor_velocity, Tau, x_t_collision_point))
    #     return (Theta_interceptor, Tau)

    def plot_intercept(self, Theta_interceptor, Tau):
        s = self
        x_interceptor_velocity = np.cos(Theta_interceptor / 180 * np.pi) * s.V_interceptor
        y_interceptor_velocity = np.sin(Theta_interceptor / 180 * np.pi) * s.V_interceptor

        print("t, x, y")
        for i in range(0, 75):
            t = i / 100
            x_offset = t * -x_interceptor_velocity
            y_offset = t * y_interceptor_velocity
            print("%4.2f, %4.2f, %4.2f" % (t, s.X_interceptor_position + x_offset, y_offset + s.Y_interceptor_position))

    # Here's an iterative approach to this problem patterened from M-1343
    # This step solves for 'Tau', time-to-intercept, without figuring the interceptor heading
    def solve_for_Tau(self, xvelo_t, yvelo_t):
        s = self
        diff = 0
        # s.x_target_velocity = np.cos((Theta_target / 180) * np.pi) * self.V_target
        # s.y_target_velocity = np.sin((Theta_target / 180) * np.pi) * self.V_target
        s.x_target_velocity = xvelo_t
        s.y_target_velocity = yvelo_t
        Tau_inverse = 0.1  # initial value doesn't matter, but it keeps PyCharm from complaining
        for i in range(1, 500):
            Tau_inverse = i / 10  # This is 1/Tau
            diff = (s.dx * Tau_inverse + s.x_target_velocity) ** 2.0 + (s.dy * Tau_inverse + s.y_target_velocity) \
                ** 2.0 - s.V_interceptor ** 2
            # print("  Iteration i=%d, Tau=%4.2f, diff= %4.2f" % (i, 1 / Tau_inverse, diff))
            if diff >= 0:
                break
        return 1.0 / Tau_inverse

    def solve_for_Theta_I(self, Tau):
        s = self
        # I think the WW equation 14 (approximation of arctan) only works for angles
        # between -90 and +90, i.e, headings 0 to 180
        # But the following implements Equation 13 with NumPy ArcTan()
        Theta_I_ww = self.velocity_to_Theta((s.dx / Tau + s.x_target_velocity), (s.dy / Tau + s.y_target_velocity))
        return Theta_I_ww

    # take X and Y velocity readings and return the implied angle relative to
    #   the +x-axis, in degrees (i.e., not heading)
    def velocity_to_Theta(self, velo_x, velo_y):
        # huh, there must be a cleaner way to avoid a divide by zero...
        # I can trap on a divide exception, but I'm not sure if the value returned by atan is any
        # good if the input is "almost infinite"
        try:
            angle = velo_y / velo_x
        except ArithmeticError:
            if velo_y >= 0:
                angle = 90
            else:
                angle = -90
        theta = np.arctan(angle) * (180 / np.pi)
        if velo_x < 0:
            theta += 180
        return theta


class SmootherStateClass:
    def __init__(self):
        # smoothing variables corresponding to aircraft 0 and 1
        # (where 0 is normally the target, 1 is normally the interceptor, assuming Autoclick)
        self.X_posn_smoothed = [0, 0]
        self.Y_posn_smoothed = [0, 0]
        self.X_velo_smoothed = [0, 0]
        self.Y_velo_smoothed = [0, 0]
        self.was_tracking = [False, False]

    # emulate the operation of the smoother function.  In the Real Code, the position averaging seems to work
    # with no problem, but the velocity average is Like Totally All Over the Place
    # azimuth is used to make sure we only run the smoother once per revolution
    def run_smoother(self, csv, azi=None, is_tracking=None, heading=False):
        if csv & heading:
            return "py_x_posn_smoo_t, py_y_posn_smoo_t, py_x_velo_smoo_t, py_y_velo_smoo_t, \
py_x_posn_smoo_i, py_y_posn_smoo_i, py_x_velo_smoo_i, py_y_velo_smoo_i"
        ret = ""
        rloc = Radar.where_are_they_now(Radar.elapsed_time, radial=False)
        g = 1.0/16.0  # constants from doc Page 37 of M-1343
        h = 5.0/16.0
        for i in range(0, len(rloc)):
            craft = rloc[i][0]
            rdr_x = rloc[i][1]  # radar reports in miles, but the WW program operates in 256ths
            rdr_y = rloc[i][2]  # This calculation is self-contained, so it's in floating-point miles
            # the following in M-1343 are Equations 4-9
            if azi == 1 and is_tracking[i]:  # run smoothing once per antenna revolution
                # initialize the position when we first start tracking
                if not self.was_tracking[i]:
                    self.X_posn_smoothed[i] = rdr_x
                    self.Y_posn_smoothed[i] = rdr_y
                    self.was_tracking[i] = True

                predicted_x_pos = self.X_posn_smoothed[i]  # + self.X_velo_smoothed[i]
                diff_x = rdr_x - predicted_x_pos
                next_X_velo_smoothed = self.X_velo_smoothed[i] + g * diff_x
                next_X_posn_smoothed = self.X_posn_smoothed[i] + next_X_velo_smoothed + h * diff_x
                self.X_posn_smoothed[i] = next_X_posn_smoothed
                self.X_velo_smoothed[i] = next_X_velo_smoothed
                # and again for Y
                predicted_y_pos = self.Y_posn_smoothed[i]  # + self.Y_velo_smoothed[i]
                diff_y = rdr_y - predicted_y_pos
                next_Y_velo_smoothed = self.Y_velo_smoothed[i] + g * diff_y
                next_Y_posn_smoothed = self.Y_posn_smoothed[i] + next_Y_velo_smoothed + h * diff_y
                self.Y_posn_smoothed[i] = next_Y_posn_smoothed
                self.Y_velo_smoothed[i] = next_Y_velo_smoothed

            if not csv:
                print("  PySmoother, Craft %s: radar=(%4.2f, %4.2f), posn_smoo=(%4.2f, %4.2f), velo_smoo=(%4.2f, %4.2f)" %
                  (craft, rdr_x, rdr_y, self.X_posn_smoothed[i], self.Y_posn_smoothed[i],
                   self.X_velo_smoothed[i], self.Y_velo_smoothed[i]))
            if csv:
                ret += " %4.2f, %4.2f, %4.2f, %4.2f, " % (self.X_posn_smoothed[i], self.Y_posn_smoothed[i],
                   self.X_velo_smoothed[i], self.Y_velo_smoothed[i])
        return ret


# call this with the flight params to compute the next Interceptor heading
# The approach used here emulates what M-1343 does
def paper_solution(csv, xpos_t, ypos_t, xpos_i, ypos_i, xvelo_t, yvelo_t, xvelo_i, yvelo_i, velo_i):
    if (xvelo_t == 0 and yvelo_t == 0) or (xvelo_i == 0 and yvelo_i == 0):
        ret = "Paper Solution: Zero Velocity; no solution"
        interceptor_heading = 0
        py_smooth_str = '0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,'
    else:
        g = GeometryClass(xpos_t, ypos_t, xpos_i, ypos_i, velo_i)
    #    target_theta = g.velocity_to_Theta(xvelo_t, yvelo_t)
        tau = g.solve_for_Tau(xvelo_t, yvelo_t)
        theta_i = g.solve_for_Theta_I(tau)
        interceptor_heading = 90 - theta_i
        if interceptor_heading < 0:
            interceptor_heading += 360
        ret = "Py solution: Tau=%4.2f, interceptor_heading = %4.1f" % (tau, interceptor_heading)
    return ret, interceptor_heading


#=======================================

First = True  # state variable to get a header printed on the first pass of dump_state/csv
SmootherState = SmootherStateClass()

def dump_long_tracking_state(cm, decif, rl, long, last_py_heading, py_smoother):
    global First
    global Radar
    global SmootherState

    # ad-hoc reverse symbol table
    labels = {251: "x_smoo",
              252: "y_smoo",
              253: "y_velo",
              254: "x_velo",
              255: "x_diff",
              256: "y_diff",
              257: "srch_i",
              258: "srch_r",
              259: " @259 "}
    more_state = {
        29: "Tau_inv",
        281: "dx",
        282: "dy",
        30: "Veloc_i",
        280: "vel_i_sq",
    }
    if True:  # long == 'csv':  # this format is meant to be imported to Excel
        # Essentially, we're dumping "everything" so I can analyze the results in a spreadsheet.
        # the following routine by default returns Range and Azimuth, but if radial=False, you get (x, y)
        rloc = Radar.where_are_they_now(Radar.elapsed_time, radial=False)
        if First:
            prt = "CSV, Time, Py_Heading, WW_Heading, craft_t, rdr_x_t, rdr_y_t, craft_i, rdr_x_i, rdr_y_i, "
            for addr in labels:
                prt += "%s0(@%d), %s1(@%d), " % (labels[addr], addr, labels[addr], addr + 10)
            for addr in more_state:
                prt += "%s(@%d), " % (more_state[addr], addr)
            g = GeometryClass(0, 0, 0, 0, 0)
            prt += SmootherState.run_smoother(True, azi=None, heading=True)
            print(prt)
            First = False
        # print the actual data
        heading = cm.rd(rl("FF_angle"))
        lights, ww_heading = octal_to_bin(heading)

        prt = "CSV, "
        prt += "%4.2f, %4.2f, %d, " % (Radar.elapsed_time, last_py_heading, ww_heading)
        for i in range(0, len(rloc)):
            prt += "%s, %4.2f, %4.2f, " % (rloc[i][0], rloc[i][1], rloc[i][2])
        for addr in labels:
            prt += "%s, %s, " % (decif(cm.rd(addr), decimal_0d=False), decif(cm.rd(addr + 10), decimal_0d=False))
        for addr in more_state:
            prt += "%s, " % (decif(cm.rd(addr), decimal_0d=False))
        prt += py_smoother
        print(prt)

    else:  # this format is meant for engineers to read...
        for addr in labels:
            print("     %s0(@%d)=%-8s  %s1(@%d)=%s" %
                  (labels[addr], addr, decif(cm.rd(addr)), labels[addr], addr + 10, decif(cm.rd(addr + 10))))
        prt = '    '
        for addr in more_state:
            prt += "%s(@%d)=%-5s  " % (more_state[addr], addr, decif(cm.rd(addr)))
        print(prt)

        g = (py_int(cm.rd(rl("dy"))) * py_int(cm.rd(rl("Tau_inv"))) / 256 + py_int(cm.rd(rl("y_velo0")))) * 32
        gsq = (g ** 2) // (2 ** 15)
        h = (py_int(cm.rd(rl("dx"))) * py_int(cm.rd(rl("Tau_inv"))) / 256 + py_int(cm.rd(rl("x_velo0")))) * 32
        hsq = (h ** 2) // (2 ** 15)
        print("g=%d <--> @275=%d; g**2=%d <--> @283=%d;  h=%d <--> @278=%d; h**2=%d <--> @??=?? " %
              (g, py_int(cm.rd(275)), gsq, py_int(cm.rd(283)), h, py_int(cm.rd(278)), hsq))
        print("pc=@168: g**2 + h**2 - vI**2 = %d" % (gsq + hsq - py_int(cm.rd(rl("vel_I_sq")))))


LastPyHeading = 0  # remember the pencil-and-paper pythonic heading
LastPyResultStr = ''

# cm is the core mem pointer.
# 'deci' is a routine that converts native to decimal numbers, assuming ww conventions.
#  I'm passing it in here since it's a local routine in the py_exec function.
# Set long = 'csv' to output the tracking stats for Excel
def dump_tracking_state(cm, decif, rl, long=True):
    global LastPyHeading
    global LastPyResultStr
    global SmootherState

    xpos_t = py_int(cm.rd(rl("x_smoo0"))) / 256.0
    ypos_t = py_int(cm.rd(rl("y_smoo0"))) / 256.0
    xpos_i = py_int(cm.rd(rl("x_smoo1"))) / 256.0
    ypos_i = py_int(cm.rd(rl("y_smoo1"))) / 256.0
    xvelo_t = py_int(cm.rd(rl("x_velo0"))) * 250.0 / 350.0
    yvelo_t = py_int(cm.rd(rl("y_velo0"))) * 250.0 / 350.0
    xvelo_i = py_int(cm.rd(rl("x_velo1"))) * 250.0 / 350.0
    yvelo_i = py_int(cm.rd(rl("y_velo1"))) * 250.0 / 350.0

    azi = Radar.current_azimuth
    is_tracking = ((xpos_t != 0 or ypos_t != 0), (xpos_i != 0 or ypos_i != 0))


    csv = long

    LastPyResultStr, LastPyHeading = paper_solution(csv, xpos_t, ypos_t, xpos_i, ypos_i,
                                                    xvelo_t, yvelo_t, xvelo_i, yvelo_i, 250)

    if long:
        py_smooth_str = SmootherState.run_smoother(csv, azi=azi, is_tracking=is_tracking, heading=False)
        dump_long_tracking_state(cm, decif, rl, long, LastPyHeading, py_smooth_str)

    print(LastPyResultStr)


# call this after the alleged arctan calculation to see if we can correlate the answers
def check_heading(cm, decif, rl):
    global LastPyHeading
    global LastPyResultStr
    ww_heading = py_int(cm.rd(275))
    # lights, heading_from_lights = octal_to_bin(ww_heading)
    # off_by = ww_heading - heading_from_lights
    print("Compare Headings: Py_Predict=%3.2f, WW_heading=0d%d" %
          (LastPyHeading, ww_heading))

# Convert an octal int into a Track-and-Scan BCD kinda number
# e.g. FF_angle=0o 14520; . ..XX . .X.X . X... .
# the number is supposed to represent degrees of compass heading, i.e., 0-360
# with no more weird secret scaling factors, so the operator can read the number
# into a phone to the pilot to say which way to fly.
# Note that the three BCD digits are not adjacent
# For checking, I'm also converting the alleged BCD reference back into a
# python number.
def octal_to_bin(octal):
    spaces_list = (1, 5, 6, 10, 11, 15)
    bcd_digit_value = (1600, 800, 400, 200, 100, 0, 80, 40, 20, 10, 0, 8, 4, 2, 1, 0)
    ascii_binary = ''
    py_int = 0
    num = octal
    for i in range(0,16):
        if i in spaces_list:
            ascii_binary += ' '
        the_bit = num & 0o100000
        if the_bit:
            ascii_binary += 'X'
        else:
            ascii_binary += '.'
        if the_bit:
            py_int += bcd_digit_value[i]
        num <<= 1
    bcd = "%d degree" % py_int
    return (ascii_binary + '  ' + bcd), py_int


# This function reads the Flip-Flop Register lights showing the heading for the Interceptor
# spelled out in BCD, converts that back to a binary int, and displays that along with the
# Python-calculated interceptor heading
def print_ff_heading(cm, decif, rl, cb):
    global LastPyHeading
    global Interceptor

    heading = cm.rd(rl("FF_angle"))
    lights, py_int = octal_to_bin(heading)
    off_by = py_int - LastPyHeading

    heading_change = False
    heading_summary = ""
    for tgt in Radar.targets:
        if tgt.last_heading is None:
            tgt.last_heading = tgt.heading
            heading_change = True   # This ensures that the heading will print below on the first time through
        if tgt.heading != tgt.last_heading:
            heading_change = True
        heading_summary += "%s=%d,%d deg, " % (tgt.name, tgt.heading, tgt.last_heading)
    # This section could surely be simplified; I made a couple of dumb versioning mistakes
    # while modifying it, and haven't gone back to unwind all the experiments.
    # In particular, I'm sure it should be able to call change_heading only when there's a change in heading!
    if Interceptor:
        Interceptor.change_heading(Radar.elapsed_time, py_int)
    if Target:
        Target.change_heading(Radar.elapsed_time, Target.heading)
    if heading_change:
        msg = "WW-Heading %s, PyHeading=%d, off_by %d, hdgs:%s at t=%4.2f" % \
              (lights, LastPyHeading, off_by, heading_summary, Radar.elapsed_time)
        cb.dbwgt.add_screen_print(1, msg)
        print(msg)


# def main():
#     g = GeometryClass()
#     #    print("V_interceptor=%4.2f, V_target=%4.2f, interceptor_position=(%4.1f, %4.1f), \
#     #        target_position=(%4.1f, %4.1f)" % \
#     #        (g.V_interceptor, g.V_target,        g.X_interceptor_position,
#     #        g.Y_interceptor_position,        g.X_target_initial_position,
#     #        g.Y_target_initial_position))
#
#     for Target_heading in range(0, 360, 10):
#         print()
#         Tau = g.solve_for_Tau(90 - Target_heading)
#         Theta_I = g.solve_for_Theta_I(Tau)
#         Interceptor_heading = 90 - Theta_I
#         print(
#             "M-1343: Target_heading=%d, Interceptor_heading=%d, Tau=%4.2f" % (Target_heading, Interceptor_heading, Tau))
#
#         # (Theta_I, Tau) = g.solve_for_Theta_intercept_guy(Target_heading - 270)
#     #    g.plot_intercept(Theta_I, Tau)


#-----------------------------
#older solver

# initial pass at this works only for orthogonal paths
def old_paper_solution(xpos_t, ypos_t, xpos_i, ypos_i, xvelo_t, yvelo_t, xvelo_i, yvelo_i, velo_i):

    measured_velo_i = np.sqrt(xvelo_i**2 * yvelo_i**2)
    smallest_diff = 99999999999.0
    perfectest_angle = None
    # Tau is Time to Intercept.  It can be infinite, but there are fewer exceptions if it's just "large"
    perfectest_Tau = None
    for i in range(0, 360):
        angle = i - 180
        try:
            Tau_x = (xpos_i - xpos_t) / (xvelo_t - velo_i*np.cos(deg_to_rad(angle)))
            Tau_y = (ypos_i - ypos_t) / (yvelo_t - velo_i*np.sin(deg_to_rad(angle)))
        except ZeroDivisionError:
            Tau_x = 990
            Tau_y = 9900
        if Tau_x > 990:
            Tau_x = 990
        if Tau_y > 9900:
            Tau_y = 9900
        diff = abs(Tau_x - Tau_y)
        if diff < smallest_diff and (Tau_x >= 0 or Tau_y >= 0):  # find the smallest diff with positive time
            smallest_diff = diff
            perfectest_angle = angle
            perfectest_Tau = Tau_x
        # print("angle %d, tgt=(%3.1f, %3.1f), int=(%3.1f, %3.1f): Tau_x=%3.1f min, Tau_y=%3.1f min; diff %3.3f" %
        #       (angle, xpos_t, ypos_t, xpos_i, ypos_i, Tau_x*60.0, Tau_y*60.0, diff))

    heading = 90 - perfectest_angle
    if heading < 0:
        heading += 360
    ret = "final angle %3d; Heading %3d, Tau_x=%3.1f min, measured_velo_i=%3.1f" % \
          (perfectest_angle, heading, perfectest_Tau*60.0, measured_velo_i)
    return ret, heading


def main():
    print("There is no Main!")


if __name__ == "__main__":
    main()

