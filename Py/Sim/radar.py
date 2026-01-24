# Radar Station Simulation
# This module is used to generate radar signals to be used with David Israel's track-and-scan,
# described in M-1343
# The program expects to receive data in the form of one-word messages, which might contain
# either a range or an azimuth reading (i.e., polar coordinates)
# This module also emulates the 1950 version of the Light Gun
# The program was done before the 'new i/o system', so radar and light gun were both
# wired in through flip-flop registers
#
# Guy Fedorkow, Feb 5, 2021


# #####################
import numpy as np
import sys
import os
import wwinfra
import time
# from wwsim import CpuClass

# There can be a source file that contains subroutines that might be called by exec statements specific
#   to the particular project under simulation.  If the file exists in the current working dir, import it.
if os.path.exists("project_exec.py"):
    sys.path.append('.')
    from project_exec import *

def breakp(reason=""):
    print("Breakpoint %s" % reason)

# My WW Radar works in degrees, with angle=zero being North
# increasing angle is counter-clockwise
# Python works in radians, with zero along the positive x-axis
def cart2pol(x, y):
    rho = np.sqrt(x**2 + y**2)
    phi = np.arctan2(y, x)
    angle = phi * 360.0 / (2 * np.pi) - 90.0
    if angle < 0:
        angle += 360.0
    return(rho, angle)

def pol2cart(rho, angle):  # radius in miles, angle in degrees
    phi = (angle + 90.0) * 2 * np.pi / 360.0
    x = rho * np.cos(phi)
    y = rho * np.sin(phi)
    return(x, y)


# ######################

class AircraftClass:
    def __init__(self, name, xi, yi, heading, v_mph, autoclick_revolutions, autoclick_type):
        self.name = name
        self.log = wwinfra.LogFactory().getLog ()
        self.v_mph = v_mph   # real-world velocity in MPH
        self.heading = heading  # real-world heading in degrees
        self.distance_scale = 128.0  # represents 128 real world miles
        self.xi = xi  # initial x pos in miles
        self.yi = yi  # initial y pos in miles
        # I want to be able to update the heading during a run.  But to avoid accumulation of errors, I
        # think it's safer to extrapolate straight-line from the last heading change.
        self.last_heading_change_x = xi  # remember where the craft was last so we can extrapolate the position
        self.last_heading_change_y = yi
        self.last_heading_change_time = 0
        self.last_heading = None
        self.last_x = xi  # these two are for debug only
        self.last_y = yi

        # These two params are so that the simulator can identify Target and Interceptor itself
        # That's easy with the mouse, but hard to get it predictable
        self.autoclick_revolutions = autoclick_revolutions
        self.autoclick_type = autoclick_type
        self.shot_down = False   # set this to True to remove the aircraft from the simulation


    def get_current_position(self, current_time, radial = True):  # current_time in seconds
        # heading is given as degrees from North, counting up clockwise, i.e., flying west is 270 degree heading
        (vx, vy) = pol2cart(self.v_mph/3600.0, -self.heading)  #convert mph to miles per second
        delta_t = current_time - self.last_heading_change_time
        x = self.last_heading_change_x + delta_t * vx
        y = self.last_heading_change_y + delta_t * vy
        self.last_x = x
        self.last_y = y
        rng, angle = cart2pol(x, y)
        if radial == True:
            return rng, angle
        else:
            return x, y


    def change_heading(self, current_time, heading, msg="null-msg", vmph = None):
        # figure out where we are, and reset the positions for the next linear segment
        x, y = self.get_current_position(current_time, radial = False)
        self.last_heading_change_x = x  # remember where the craft was last, so we can extrapolate the position
        self.last_heading_change_y = y
        self.last_heading_change_time = current_time
        self.last_heading = self.heading
        self.heading = heading
        if heading != self.last_heading:
            self.log.info ("py_radar Aircraft %s: change heading to %d; msg=%s" % (self.name, heading, msg))


# I've added a "screen widget" to steer the target aircraft during the sim.  This class is activated
# by that widget.
# It's expected to have functions to read the current value, or increment or decrement the value.
class RadarAdjustHeadingWidgetClass:
    def __init__(self):
        self.target = None

    def register(self, target):
        self.target = target
    def rd(self):
        if self.target is None:
            return None
        else:
            return int(self.target.heading)

    def incr(self, val):
        if self.target is None:
            return
        else:
            self.target.heading += val
            if self.target.heading >= 360.0:
                self.target.heading -= 360.0
            if self.target.heading < 0.0:
                self.target.heading += 360.0



# Initialize the radar system.
# The flag autoclick_enable comes from the command line and indicates if the radar sim should use pre-programmed
# mouse clicks to indicate Target and Interceptor, oor if we should wait for the Real User to Click the Buttons.
#  Autoclick allows perfectly-repeatable simulation runs as a (substantial) aid to debug.
class RadarClass:
    def __init__(self, target_list, cb, cpu, autoclick_enable):
        self.log = wwinfra.LogFactory().getLog ()
        self.azimuth_steps = 256
        self.rng_list = []   # list of radar reflections at the current azimuth
        self.current_azimuth = 0
        self.last_azimuth = -1
        self.slots_into_rotation = 0  # count how many transmission slots we are into the antenna rotation

        self.target_list = target_list
        self.elapsed_time = 0
        self.antenna_revolutions = 0
        self.azimuth_next = True   # We (roughly) alternate sending Range and Azimuth

        self.autoclick_enable = autoclick_enable
        self.mouse_clicked_once_for_autostart = False

        # This program is the only one that uses the older Light Gun interface linked in through
        # one of the Flip Flop registers.  To avoid messing with the rest of the sim for this
        # unusual mode, I added a callback to come to this class when that FF is accessed, and "emulate"
        # the toggle switch register interface here.  So this var remembers the state of that one FF Reg.
        self.light_gun_ff_reg = 0   # zero in the light-gun flip flop is "no reading"
        self.cpu = cpu       # keep this around to check the mouse
        self.cb = cb
        self.crt = None      # pick up the CRT handle when the radar axis is drawn in draw_axis
        self.exit_alarm = False   # this is a flag back to the main sim loop to exit in case of a Red X

        self.radar_time_increment = 1.0/50.0  # 20 msec per word from the remote radar station
        time_per_reading = 0.02    # a number is transmitted over the phone link every 20 msec
        self.time_per_revolution = 15  # seconds
        self.readings_per_rotation = int(self.time_per_revolution / self.radar_time_increment)  #  that's a long way of saying "750"
        self.last_aircraft_name_sent = None

        self.adjust_target_heading = RadarAdjustHeadingWidgetClass()

        project_register_radar(self)


    # the radar antenna rotates a full turn in 15 seconds.  There are 750 20-msec opportunities to send
    # a reading every rotation, approximately half of which would be Azimuth (angle of antenna with respect
    # to due north, rotating counter clockwise).  So the same azimuth is reported just about 1.5 times on
    # average.  The exact number doesn't matter, as long as the result is about 750 samples.
    # This routine uses float-to-int conversion to figure the next azimuth, while keeping the average
    # number about right.


    # this routine returns the radial coords of all the current aircraft at the given time increment
    def where_are_they_now(self, current_time, radial = True):  # time in seconds
        ret = []
        for tgt in self.target_list:
            if tgt.shot_down == True:
                continue
            rng, angle = tgt.get_current_position(current_time, radial=radial)
            if rng < 128:
                ret.append((tgt.name, rng, angle))
        return ret

    # called by the simulation when it reads the radar register
    # this action controls timing of the simulation; a word from the radar unit would be sent
    # every 20 msec, providing a time base.
    def get_next_radar(self):

        self.current_azimuth = int(round((self.slots_into_rotation / self.readings_per_rotation * 256)))
        if self.slots_into_rotation == 0:
            new_rotation = True
        else:
            new_rotation = False
        # There are 750 slots in a rotation, but only 256 different azimuth values.
        # Send a new azimuth each time we've gone about three 20 msec slots and we're on to the next value
        if self.azimuth_next and (self.current_azimuth != self.last_azimuth):
            craft_list = self.where_are_they_now(self.elapsed_time)
            self.rng_list = []
            for craft in craft_list:
                # heading is given as degrees from North, counting up clockwise
                # craft = [name   start x/y   heading  mph  auto-click-time Target-or-Interceptor]
                azi = int(round(craft[2] * 256.0 / 360.0))   # Heading
                if azi == self.current_azimuth:
                    self.rng_list.append((craft[0], craft[1]))  # append nametag and range to list
            # Holy Cow -- Israel's code only works if he gets some 'noise' range readings...  the code doesn't
            # notice that it's out of the scan sector until it gets a non-zero range return from an untracked
            # plane, or from clutter.  So here's a fake reading from due-north...
            # And it appears that it doesn't work unless the clutter is clearly outside the zone of both the tracked
            # aircraft!
            if self.current_azimuth == 0 and len(self.rng_list) == 0:
                self.rng_list.append(("Geo_North_marker", 120.0))
            if self.current_azimuth == 128 and len(self.rng_list) == 0:
                self.rng_list.append(("Geo_South_marker", 120.0))   # note Azimuth is measured in 1/256ths of a revolution
            azi_code = (self.current_azimuth | 0o400) << 6   # convert to phone line coding
            ret = (azi_code, "Radar Return: azimuth %d" % (self.current_azimuth), new_rotation)
            self.azimuth_next = False  # given the automatic 256 of 750 azimuth slots, this flag is probably not needed...
            self.last_azimuth = self.current_azimuth

            # This call shows the current radar Azimuth on the LCD screen
            # It was originally added to help debug the problem caused by lack of clutter
            # I disabled the function Oct 5, 2023, as it didn't seem to be adding much value
            if self.current_azimuth % 4 == 0:
                self.draw_radar_scan(self.current_azimuth)

        # if we didn't create an Azimuth slot, then it has to be a range slot
        # Most azimuth readings will have a null range, since most antenna angles don't see a target, and even
        # those that do, we only send the target once.
        else:  # There might be one range at this azi, or possibly more at the same azi
            if len(self.rng_list) > 0:
                (tgt_name, tgt_rng) = self.rng_list[0]
                del self.rng_list[0]
            else:
                tgt_name = "null"
                tgt_rng = 0  # zero range is the way to say "nothing" (I guess if the attacker is that close, you've lost)
            # after sending the current azimuth, then send one or more range readings
            # See M-1343 pg 13 for the picture of how the signals are encoded going into FF4.
            # Send Range; Note special case; if the next range is the same azi, don't send the azimuth again

            # Prepare the line-coded range response
            if tgt_rng > 127:   # not sure if this can happen, but don't wrap the Range response
                tgt_rng = 127
            rng_code = (int(round(tgt_rng)) << 1) << 6
            # compute pilot-friendly angle of where the radar antenna *was* pointing
            angle_degrees = (self.current_azimuth -1) * 360.0/256.0
            if angle_degrees > 180:
                angle_degrees -= 360
            (x, y) = pol2cart(tgt_rng, angle_degrees)
            ret = (rng_code, "Radar Return: %s rng=%d azi=%d (%d degrees) (x,y)=(%3.1f, %3.1f) miles at t=%3.2f seconds" %
                   (tgt_name, tgt_rng, self.current_azimuth, angle_degrees, x, y, self.elapsed_time), new_rotation)
            if tgt_name != "null":
                self.last_aircraft_name_sent = tgt_name
                # print("aircraft tgt_name=%s" % tgt_name)
            self.mouse_autoclick(tgt_name)  # check to see if we should AutoClick on this antenna revolution

            # yeah, ok, if the two targets are at the same spot, we'll send two identical Range readings
            # This couldn't actually happen (there's only one echo) but I don't think the WW program will care.
            # The Interceptor flight crew will be too busy celebrating.
            if len(self.rng_list) == 0:
                self.azimuth_next = True

        self.elapsed_time += self.radar_time_increment
        self.slots_into_rotation += 1
        if self.slots_into_rotation >= self.readings_per_rotation:
            self.slots_into_rotation = 0
            self.antenna_revolutions += 1
        return ret


    def mouse_check_callback(self, addr, write_val):
        ret = None
        ff_gun = 0
        if write_val is not None:
            # print("mouse check callback Write %02o to @%02o" % (write_val, addr))
            self.light_gun_ff_reg = write_val
        else:  # must be a read of the ff reg
            # print("mouse check callback Read @%02o, return 0o%02o" % (addr, ret))
            if self.cpu.scope.crt is not None:
                (exit_alarm, gun_reading) = self.cpu.scope.rd(None, None)
                if exit_alarm != self.cb.NO_ALARM:
                    self.exit_alarm = exit_alarm
                if gun_reading != 0:
                    # 2M-0277 describes in detail how multiple light guns work.  But the air defense
                    # demo came long before the standard interface.  In this case, I'm coding the first two
                    # light guns as one with the Target switch, one with the Interceptor switch set.
                    if gun_reading & 0o20000:
                        ff_gun = 0o100000
                    elif gun_reading & 0o40000:
                        ff_gun = 0o177777
                    else:
                        self.log.info ("** Unexpected Light Gun Value 0o%o ***" % gun_reading)
                    self.light_gun_ff_reg = ff_gun
            ret = self.light_gun_ff_reg
            self.log.info ("** light_gun_ff_reg=0o%o, ff_gun=0o%o, ret=0o%o" % (self.light_gun_ff_reg, ff_gun, ret))
        return ret

    # autoclick means that we simulate a light-gun hit automatically a certain number of
    # revolutions after start of sim.
    # This allows tests to run repeatedly and with no manual intervention.  (which got old
    # after the first 1,000 times...)
    def mouse_autoclick(self, tgt_name):
        # This Pause was inserted Apr 21, 2021 to allow me to make a video demo
        #  When it hits this pause, the screen is displayed, so I can "share" it with
        # zoom and record the rest of the session
        # This 'feature' can only work with the xwin display, so I bypass the check if we're
        # using the analog display mode.
        if self.autoclick_enable == False:
            return   # don't even try
        if self.mouse_clicked_once_for_autostart == False and self.cpu.scope.crt and \
                self.cpu.scope.crt.win and self.antenna_revolutions == 1 and self.current_azimuth == 10:
            # Uncomment these two lines to make the sim wait for a mouse click before starting
            # self.log.info ("wait for mouse")
            # self.cpu.scope.crt.win.getMouse()
            self.log.info ("let's go!")
            self.mouse_clicked_once_for_autostart = True

        for tgt in self.target_list:
            if self.antenna_revolutions > 0 and \
                self.antenna_revolutions == tgt.autoclick_revolutions and tgt_name == tgt.name:
                click_type = tgt.autoclick_type
                self.log.info ("  *** Autoclick Aircraft %s, type %s, revolution %d, elapsed time=%3.2f" %
                      (tgt.name, click_type, self.antenna_revolutions, self.elapsed_time))
                if click_type == 'T':
                    self.light_gun_ff_reg = 0o177777
                elif click_type == 'I':
                    self.light_gun_ff_reg = 0o100000
                else:
                    self.log.info ("  Autoclick: Invalid Type: %s, aircraft %s", (click_type, tgt_name))


    def draw_axis(self, crt):
        self.crt = crt  # keep this around to draw debug markings on the 'radar' screen
        axis_color = crt.gfx.color_rgb(80, 0, 80)
        xaxis = crt.gfx.Line(crt.gfx.Point(0, crt.WIN_MAX_COORD / 2),
                              crt.gfx.Point(crt.WIN_MAX_COORD, crt.WIN_MAX_COORD / 2))
        xaxis.setOutline(axis_color)
        xaxis.setWidth(1)
        xaxis.draw(crt.win)

        yaxis = crt.gfx.Line(crt.gfx.Point(crt.WIN_MAX_COORD / 2, 0),
                              crt.gfx.Point(crt.WIN_MAX_COORD / 2, crt.WIN_MAX_COORD))
        yaxis.setOutline(axis_color)
        yaxis.setWidth(1)
        yaxis.draw(crt.win)

        rings = 5
        radial_axis = [None] * rings
        for i in range(0, rings):
            # draw concentric circles every 25 miles
            diameter = 25 / 128 * i * ((crt.WIN_MAX_COORD / 2))
            radial_axis[i] = crt.gfx.Circle(crt.gfx.Point(crt.WIN_MAX_COORD / 2, crt.WIN_MAX_COORD / 2), diameter)
            radial_axis[i].setOutline(axis_color)
            radial_axis[i].setWidth(1)
            radial_axis[i].draw(crt.win)


    # This routine shows debug information around the (circular) edge of the radar screen, e.g., where the
    # antenna is pointing, who's in the Scan zone, etc
    def draw_radar_scan(self, azimuth):
        return  # disabled for now

        if self.crt is None or self.cb.analog_display:
            return

        # show the antenna angle
        (x, y) = pol2cart((self.crt.WIN_MAX_COORD - 10)/2 , (azimuth/256.0) * 365.0)  # radius in miles, angle in degrees
        ww_x = self.crt.WIN_MAX_COORD/2 + x
        ww_y = self.crt.WIN_MAX_COORD/2 - y  # remember that the Y Axis is upside down
#        self.crt.ww_draw_point(ww_x, ww_y, color=(0.0, 1.0, 0.0), light_gun=False)
        color = self.crt.gfx.color_rgb(255, 255, 255)
        c = self.crt.gfx.Circle(self.crt.gfx.Point(ww_x, ww_y), 5)  # was 5 # the last arg is the circle dimension
        c.setFill(color)
        c.draw(self.crt.win)
        self.crt.gfx.update()
        # breakp("")


def main():

    crt = False            # set this True to see the picture on the CRT
    report_tracks = False  # print out or display the tracks; otherwise format as radar data words

    target_list = [AircraftClass('A', 30.0, -36.0, 0.0, 400.0, 3, 'T'),
                   AircraftClass('B', 100.0, -10.0, 90.0, 450.0, 6, 'I')]
    radar = RadarClass(target_list, None, None)

    if not report_tracks:
        while radar.elapsed_time < 1550.0:
            (code, string) = radar.get_next_radar()
            if string is None:
                break
            radar.log.info (string)

    else:
        print("oops; exit")
        exit(1)
#        cb = wwinfra.ConstWWbitClass()
#        CoreMem = wwinfra.CorememClass(cb)
#        cpu = CpuClass(cb, CoreMem)  # instantiating this class instantiates all the I/O device classes as well
#        cb.cpu = cpu
#        cpu.cpu_switches = wwinfra.WWSwitchClass()
#        cb.log = wwinfra.LogClass(sys.argv[0], quiet=False)
#        cb.dbwgt = wwinfra.ScreenDebugWidgetClass(CoreMem)
#
#        while True:
#
#
#            xy_tracks = radar.track(1.0)  # get current positions, advance time one second
#            polar_list = radar.xy_to_range_azi(xy_tracks)
#            polar_sorted = sorted(polar_list, key=lambda tgt: tgt[2])  # sort by azimuth
#            if len(xy_tracks) == 0:
#                break
#            report = ''
#            for t in polar_sorted:
#                # name = t[0]
#                x = 0  # t[1]
#                y = 0  # t[2]
#                (name, rng, azi) = t
#                report += "%s: xy=(%f, %f) rng_az=(%d, %d) " % (name, x, y, rng, azi)
#                # i broke the xy display when I sorted the polar list by azimuth
#                if crt:
#                    cpu._AC = int(x * 512) << 6
#                    cpu.qh_inst(0, 0o40, '', '')
#                    cpu._AC = int(y * 512) << 6
#                    cpu.qd_inst(0, 0o40, '', '')
#                    cpu.scope.crt.ww_scope_update(CoreMem, cb.dbwgt)
#
#            print("t=%d: %s" % (radar.elapsed_time, report))
#        if crt:
#            time.sleep(20)


if __name__ == "__main__":
    main()
