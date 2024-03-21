# Copyright 2024 Guy C. Fedorkow
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
# associated documentation files (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge, publish, distribute,
# sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#   The above copyright notice and this permission notice shall be included in all copies or
# substantial portions of the Software.
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
# BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


# Whirlwind Control Panel
# This module does "buttons and lights" for guy's MIT Whirlwind Simulator
# The file also contains a test framework
# guy fedorkow, jan 31, 2024

from graphics import *


# ###########################################

class BboxClass:   # Bounding Box for buttons
    def __init__(self, x, y, x_size, y_size):
        self.min_x = x
        self.min_y = y
        self.max_x = x + x_size
        self.max_y = y + y_size

    def in_bbox(self, x, y):
        return x > self.min_x and x < self.max_x and y > self.min_y and y < self.max_y


class OneToggleClass:  # make a toggle switch
    def __init__(self, win, x, y, radius, name=None, initial_value = 0,
                 on_color="blue", off_color="black", outline_color="white"):
        self.win = win
        self.current_state = initial_value
        self.name = name
        self.on_color = on_color
        self.off_color = off_color
        self.outline_color = outline_color
        self.rect = Rectangle(Point(x-radius, y-2*radius), Point(x+radius, y+radius))
        if name is not None:
            self.tag = Text(Point(x, y+2*radius+compensate_justification(name)), name)
            self.tag.setTextAngle(-90)
            self.tag.setFill("white")
            self.tag.setFace("helvetica")
            self.tag.draw(win)
        self.rect.setOutline(outline_color)
        self.rect.setWidth(2)
        self.draw_toggle(initial_value, initialize=True)
        self.bbox = BboxClass(x - radius, y - 2* radius, 2 * radius, 2 * radius)
        return

    # call this method to draw a toggle switch with either the 'on' or 'off' fill color
    # If the button has previously been initialized, it must be "undrawn".
    # If it's been initialized, note that we short-circuit the process if the new value
    # would be the same as what's already there.
    def draw_toggle(self, val, initialize=False):
        if not initialize:
            if val == self.current_state:
                return
            self.rect.undraw()

        if val is None:  # if we're not setting the switch to something, just reverse its polarity
            val = ~ self.current_state & 1

        if val:
            fill_color = self.on_color
            self.current_state = 1
        else:
            fill_color = self.off_color
            self.current_state = 0
        self.rect.setFill(fill_color)
        self.rect.draw(self.win)

    def test_for_hit(self, x, y):
        if x > self.bbox.min_x and x < self.bbox.max_x and y > self.bbox.min_y and y < self.bbox.max_y:
            return True
        return False


class OneButtonClass:
    def __init__(self, win, x, y, radius, name=None, initial_value=0, on_color="blue", off_color="black", outline_color="white"):
        self.win = win
        self.current_state = initial_value
        self.on_color = on_color
        self.off_color = off_color
        self.outline_color = outline_color
        self.circle = Circle(Point(x, y), radius)  # circle method takes radius, not diameter
        self.circle.setOutline(outline_color)
        self.circle.setWidth(2)
        self.draw_button(initial_value, initialize=True)
        self.bbox = BboxClass(x - radius, y - radius, 2 * radius, 2 * radius)
        if name is not None:
            self.tag = Text(Point(x, y+2*radius+compensate_justification(name)), name)
            self.tag.setTextAngle(-90)
            self.tag.setFill("white")
            self.tag.draw(win)
        return

    # call this method to draw a button with either the 'on' or 'off' fill color
    # If the button has previously been initialized, it must be "undrawn".
    # If it's been initialized, note that we short-circuit the process if the new value
    # would be the same as what's already there.
    def draw_button(self, val, initialize=False):
        if not initialize:
            if val == self.current_state:
                return
            self.circle.undraw()
        if val:
            fill_color = self.on_color
            self.current_state = 1
        else:
            fill_color = self.off_color
            self.current_state = 0
        self.circle.setFill(fill_color)
        self.circle.draw(self.win)

    def test_for_hit(self, x, y):
        if x > self.bbox.min_x and x < self.bbox.max_x and y > self.bbox.min_y and y < self.bbox.max_y:
            return True
        return False


class OneLampClass:
    def __init__(self, win, x, y, radius, on_color="orange", off_color="black", initial_value=0):
        self.on_color = on_color
        self.off_color = off_color
        self.current_state = 0
        if initial_value:
            color = self.on_color
            self.current_state = 1
        self.lamp = OneButtonClass(win, x, y, radius, on_color=on_color, off_color=off_color,
                                   outline_color=on_color, initial_value=initial_value)

    def set_lamp(self, new_state):
        new_state &= 1  # only look at the LSB
        # this short-circuit is probably un-needed; it's done at the next layer down too
        if self.current_state == new_state:
            return
        if (new_state):
            self.lamp.draw_button(1)
        else:
            self.lamp.draw_button(0)
        self.current_state = new_state


class LampVectorClass:
    def __init__(self, panel, n_lamp, x=0, y=0, x_step=0, y_step=0, diameter=0, name="Lamp Register", initial_value=0):
        self.n_lamp = n_lamp
        self.name = name
        self.value = initial_value
        self.x = x
        self.y = y
        self.x_step = x_step
        self.y_step = y_step
        self.lamp_vector = []
        for i in range(0, n_lamp):
            val = (initial_value >> (15 - i)) & 1
            self.lamp_vector.append(OneLampClass(panel.win, x + i * x_step, y + i * y_step,
                                                 diameter/2, on_color="orange", initial_value=val))
            if x_step and ((i % 3) == 0) and (i < n_lamp -1):  # mark off the Octal digits with a vertical line
                ln = Line(Point(x + i * x_step + x_step / 2, y - x_step / 2), Point(x + i * x_step + x_step / 2, y + x_step / 2)) # aLine = Line(Point(1,3), Point(7,4))
                ln.setOutline("white")
                ln.setWidth(2)
                ln.draw(panel.win)

    def set_lamp_register(self, value):
        self.value = value
        for i in range(0, self.n_lamp):
            self.lamp_vector[i].set_lamp(value >> (15 - i))


# This object creates one set of "Radio buttons", i.e., a one-of-N selector switch,
# Or, a set of buttons that make up a single multi-bit register
class ButtonVectorClass:
    # x and y coords correspond to the center of the first button; subsequent buttons are
    # drawn at x + n*x_step, etc
    def __init__(self, win, n_button, name, x, y, x_step, y_step, diameter, radio=True, initial_value=0o125252):
        self.win = win
        self.name = name
        self.radio = radio
        self.n_button = n_button
        self.x = x
        self.y = y
        self.x_step = x_step
        self.y_step = y_step
        self.radius = diameter / 2
        self.current_selection = 0
        self.off_color = "black"
        self.on_color = "blue"
        self.button_obj = []
        self.button_x = []
        self.button_y = []
        self.current_pressed_button = None  # rename to current_pressed_radio_button
        self.current_register_value = initial_value
        if self.x_step == 0:
            self.bbox = BboxClass(x - self.radius, y - self.radius, y_step, y_step * n_button)
        elif self.y_step == 0:
            self.bbox = BboxClass(x - self.radius, y - self.radius, x_step * n_button, x_step)
        else:
            print("fatal in ButtonVectorClass: only x_step or y_step, not both")
            exit(1)

        # now draw the initial set of buttons
        for i in range(0, self.n_button):
            val = 0
            if self.radio:
                if i == initial_value:
                    val = 1
                    self.current_pressed_button = i
            else:
                if initial_value & (1 << (self.n_button - i - 1)):
                    val = 1
            b = OneButtonClass(self.win, self.x + i * self.x_step, self.y + i * self.y_step, self.radius,
                               initial_value=val, on_color=self.on_color, off_color=self.off_color)
            self.button_obj.append(b)
        if self.radio == False:
            self.current_register_value = initial_value

    def test_button_vector_hit(self, x, y):
        ret = None
        if self.bbox.in_bbox(x, y):
            if self.x_step == 0:
                ret = int((y - self.bbox.min_y) // self.y_step)
            if self.y_step == 0:
                ret = int((x - self.bbox.min_x) // self.x_step)
        if ret is not None:
            print("Button hit: class %s, button %d" % (self.name, self.n_button - 1 - ret))
        return ret

    # New Button is an offset in the vector 0..n_buttons
    # if it's a radio button, we turn off the old one and turn on the new one
    # Otherwise, we flip the bit and update the overall register value
    def flip_a_button(self, new_button, set_val=None):
        b_offset = self.n_button - new_button - 1
        if self.radio:
            b = self.button_obj[self.current_pressed_button]
            b.draw_button(0)

            b = self.button_obj[b_offset]
            b.draw_button(1)
            self.current_pressed_button = b_offset
        elif set_val is None:  # this is a button-click; if it's not a radio, then we just flip that one bit
            b = self.button_obj[new_button]
            bit = self.current_register_value & (1 << b_offset)
            if bit:   # the switch is on; turn it off
                new_state = 0
                self.current_register_value &= ~(1 << b_offset)
            else:     # the switch is off; turn it on
                new_state = 1
                self.current_register_value |= (1 << b_offset)
            b.draw_button(new_state)
        else:
            b = self.button_obj[new_button]
            #current_bit = (self.current_register_value >> b_offset) & 1
            #if current_bit != b.current_state:
            b.draw_button(set_val)

    def set_button_vector(self, value):
        if self.radio:
            self.flip_a_button(value, set_val=value)
        else:
            for i in range(0, self.n_button):
                val = (value >> i) & 1
                self.flip_a_button(self.n_button -1 - i, set_val=val)
        self.current_register_value = value

    def read_button_vector(self):
        if self.radio:
            return self.n_button - 1 - self.current_pressed_button
        else:
            return self.current_register_value


class ActivateButtonClass:
    def __init__(self, one_ir, x=0, y=0):
        self.button = OneButtonClass(one_ir.win, x, y, one_ir.diameter/2, on_color="white")
        self.lamp = OneLampClass(one_ir.win, x, y - one_ir.y_step, one_ir.diameter/2)

    def test_activate_hit(self, x, y):
        return self.button.bbox.in_bbox(x, y)

    def read_bit(self):
        if self.lamp.current_state:
            ret = 1
        else:
            ret = 0
        return(ret)

    def write_bit(self, val):
        self.lamp.current_state = val


class OneInterventionRegisterClass:
    def __init__(self, win, x, y, name, initial_value=0o52525):
        # Instantiate a set of radio buttons to make a 16-bit Manual Intervention Register
        # Note that the first column of buttons represents only the MSB, so is just two buttons
        # Note that the array of buttons places rbc[0] at the top of the array, while the label on
        # the button marks the bottom button as have value Zero.
        self.win = win
        self.name = name
        self.rbc = []
        self.y_step = 20
        self.x_step = 20
        self.diameter = self.x_step * 16/20
        self.rbc.append(ButtonVectorClass(win, 2, "%s-0" % name, x, y + 6 * self.x_step, 0, self.y_step, self.diameter,
                                          initial_value=(1 - (initial_value >> 15))))

        # the remaining five columns each have eight octal-coded buttons
        for i in range(1, 6):
            rbc = ButtonVectorClass(win, 8, "%s%d" % (name, i), x + i * 20, y, 0, 20, 16,
                                    initial_value=(7 - ((initial_value >> (15 - i*3)) & 7)))
            self.rbc.append(rbc)

        self.activate = ActivateButtonClass(self, x=x, y=y + 2 * self.y_step)
        nametag = Text(Point(x + 3*self.x_step, y + 8 * self.y_step), self.name)
        nametag.setTextColor("white")
        nametag.draw(self.win)

    # This routine looks at a mouse click and figures if it hit any radio buttons
    # If so, it updates the display and stored value of the button array.
    # We don't return anything here; Whirlwind doesn't know when an Intervention button is pushed, it
    # just knows the value when the instruction to read the switch register is executed.
    def test_radio_hit(self, x, y):
        for i in range(0, 6):
            bn = self.rbc[i].test_button_vector_hit(x, y)
            if bn is not None:
                self.rbc[i].flip_a_button(self.rbc[i].n_button - 1 - bn)
        act = self.activate.button.bbox.in_bbox(x, y)
        if act:
            self.activate.lamp.set_lamp(True)
            # print("hit %s Activate button" % self.name)


    def read_register(self):
        ret = 0
        for i in range(0, 6):
            ret |= (self.rbc[i].read_button_vector() << ((5 - i) * 3))
        return(ret)

    def set_register(self, value):
        for i in range(0, 6):
            val = (value >> ((5 - i) * 3)) & 7
            self.rbc[i].set_button_vector(val)
        return


class DualInterventionRegisterClass:
    def __init__(self, win, x=0, y=0, left_init=0, right_init=0, folded=False):
        self.left_ir = OneInterventionRegisterClass(win, x, y, "LMIR", initial_value=left_init)
        self.right_ir = OneInterventionRegisterClass(win, x + 150, y, "RMIR", initial_value=right_init)

    def test_ir_hit(self, x, y):
        self.left_ir.test_radio_hit(x, y)
        self.right_ir.test_radio_hit(x, y)

    def read_left_register(self):
        val = self.left_ir.read_register()
        return val

    def read_right_register(self):
        val = self.right_ir.read_register()
        return val

    def set_right_register(self, value):
        self.right_ir.set_register(value)

    def set_left_register(self, value):
        self.left_ir.set_register(value)

class CPURregClass:
    def __init__(self, panel, name='?', x=0, y=0, initial_value=0, pc_special=False):
        self.win = panel.win
        self.name = name
        self.y_step = 0               # this says it's a horizontal vector of buttons
        self.x_step = panel.x_step
        self.diameter = panel.diameter
        self.lamp_vector = LampVectorClass(self, 16, x=x, y=y, x_step= self.x_step, y_step=0,
                                           diameter=panel.diameter, initial_value=initial_value,
                                           name=self.name)
        nametag = Text(Point(x + 16*self.x_step + 10, y), self.name)
        nametag.setTextColor("white")
        nametag.draw(panel.win)

    # write the reg value, setting the lights
    def write_cpu_register(self, value):
        self.lamp_vector.set_lamp_register(value)



class FFRregClass:
    def __init__(self, panel, addr=2, x=0, y=0, initial_value=1):
        self.win = panel.win
        self.addr = addr
        self.name = "FF%02o" % addr
        self.y_step = 0               # this says it's a horizontal vector of buttons
        self.x_step = panel.x_step
        self.diameter = panel.diameter
        self.lamp_vector = LampVectorClass(self, 16, x=x, y=y, x_step= self.x_step, y_step=0,
                                           diameter=panel.diameter, initial_value=0o123,
                                           name=self.name)
        nametag = Text(Point(x + 16*self.x_step + 20, y + panel.y_step / 2), self.name)
        nametag.setTextColor("white")
        nametag.draw(panel.win)

        self.bbox = BboxClass(x - panel.x_step / 2, (y + panel.y_step) - panel.y_step / 2,
                              16 * panel.x_step + panel.x_step / 2, panel.y_step + panel.y_step / 2)
        self.rbc = ButtonVectorClass(self.win, 16, "%s-0" % self.name, x, y + panel.y_step, self.x_step, 0, self.diameter,
                                     radio=False, initial_value=initial_value)

    # on mouse hit, we test to see if it hit any of the buttons used to initialize the FF
    # values.  If so, the buttons are updated, but the value of the FF Reg is not changed.  (That
    # only happens with reset_ff_reg() below.)
    def test_for_ff_hit(self, x, y):
        ret = None
        if self.bbox.in_bbox(x, y):
            if self.x_step == 0:
                ret = int((y - self.bbox.min_y) // self.y_step)
            if self.y_step == 0:
                ret = int((x - self.bbox.min_x) // self.x_step)
        if ret is not None:
            if True:  #  self.cb.TraceQuiet is False:  (no accecss to cb here...)
                print("Button hit: class %s, button %d" % (self.name, ret))
            if ret is not None:
                self.rbc.flip_a_button(ret)
        return ret

    # read the current volatile setting for a flip-flop register
    def read_ff_register(self):
        return self.lamp_vector.value

    # write the ff reg value, especially setting the lights
    def write_ff_register(self, value):
        self.lamp_vector.set_lamp_register(value)

    def read_switch_register(self):
        return self.rbc.current_register_value

    # this entry point sets the value of the _switches_, not the FF display lamps
    def set_switch_register(self, value):
        self.rbc.set_button_vector((value))

    # This entry point copies whatever is in the FF switch register into the active FF register itself
    # This is done indirectly by calling a function that updates the core-mem image directly from the
    # switch register in the control panel, ignoring whatever the default values from the .core file
    # might have been.
    # The args to this function are the pointer to the update function and the name of the corresponding
    # FF register.  Note that there's a name transformation here...  the name space in the control panel
    # and the .core file are slightly different, linked by the address offset of the FF Register
    def reset_register(self, function, log, info_string):
        val = self.rbc.current_register_value
        # self.lamp_vector.set_lamp_register(val)
        function(self.addr, val)
        if log:
            log.info(info_string % (self.addr, self.addr, val))


class ControlButtonAndLight:
    def __init__(self, panel, x, y,  y_step, switch_name, lamp_name, toggle=False):
        self.switch_name = switch_name
        self.lamp_name = lamp_name
        self.toggle = toggle
        self.button_object = None
        if lamp_name is not None:
            self.lamp_object = OneLampClass(panel.win, x, y,
                                        y_step/3, on_color="orange", initial_value=False)
        if toggle == False:
            self.button_object =  OneButtonClass(panel.win, x, y + y_step, y_step/3, name=switch_name, on_color="white")
        else:
            self.button_object = OneToggleClass(panel.win, x, y + y_step, y_step/3, name=switch_name, on_color="white")

    def test_for_hit(self, x, y):
        return self.button_object.test_for_hit(x, y)

# CPU Control provides the buttons and lights for starting and stopping the processor
# Including
#  Start at 40
#  Continue
#  Single Step
#  Stop
#  Alarm

class CPUControlClass:
    def __init__(self, panel, x=0, y=0, x_step=20, y_step=20):
        toggle_sw_def = ["Stop on CK", "Stop on SI-1"]
        lights_def =   ["Alarm",        "Stop",  None,        "Run",      None,          None,             None, None]
        buttons_def =  ["Clear Alarm", "Stop", "Start Over", "Restart", "Start at 40", "Order-by-Order", "Examine",
                                                                                                            "Read In"]
        self.control = []   # list of control panel objects indexed by x axis location
        self.dispatch = {}  # list of control panel objects indexed by switch name

        xi = x
        for i in range(0, len(toggle_sw_def)):
            ts = ControlButtonAndLight(panel, xi, y,  y_step, toggle_sw_def[i], None, toggle=True)
            self.control.append(ts)
            self.dispatch[toggle_sw_def[i]] = ts
            xi += x_step
        for i in range(0, len(buttons_def)):
            pb = ControlButtonAndLight(panel, xi, y,  y_step, buttons_def[i], lights_def[i], toggle=False)
            self.control.append(pb)
            self.dispatch[buttons_def[i]] = pb
            xi += x_step

    def test_for_hit(self, x, y, cb):
        for cbl in self.control:
            hit = cbl.test_for_hit(x, y)
            if hit:
                print("Hit switch %s" % cbl.switch_name)
                self.local_state_machine(cbl)
                self.sim_state_machine(cbl, cb)

    # this small routine manages local interactions in the buttons and lights
    def local_state_machine(self, cbl):
        sw = cbl.switch_name
        # reverse the state of a toggle switch if there was a hit
        if sw == "Stop on CK" or sw == "Stop on SI-1":
            self.dispatch[sw].button_object.draw_toggle(None)
            return

    # This state machine is used to control the flow of execution for the simulator
    def sim_state_machine(self, cbl, cb):
        sw = cbl.switch_name
        if sw == "Stop":
            cb.sim_state = cb.SIM_STATE_STOP
            # self.dispatch["Stop"].lamp_object.set_lamp(True)
            # self.dispatch["Start at 40"].lamp_object.set_lamp(False)
            return
        if sw == "Restart":   # don't mess with the PC, just pick up from the last address
            cb.sim_state = cb.SIM_STATE_RUN
            return

        if sw == "Start at 40":
            cb.sim_state = cb.SIM_STATE_RUN
            cb.cpu.PC = 0o40
            return

        if sw == "Order-by-Order":  # don't mess with the PC, just pick up from the last address
            cb.sim_state = cb.SIM_STATE_SINGLE_STEP
            return

    def set_cpu_state_lamps(self, cb, sim_state, alarm_state):
        run = sim_state != cb.SIM_STATE_STOP
        self.dispatch["Restart"].lamp_object.set_lamp(run)
        self.dispatch["Stop"].lamp_object.set_lamp(~run)

class PanelClass:
    def __init__(self, left_init=0, right_init=0):
        self.scale = 1.0
        self.PANEL_X_SIZE = 512
        self.PANEL_Y_SIZE = 800
        self.XBOX = 20
        self.win = GraphWin("Control Panel Layout", self.PANEL_X_SIZE, self.PANEL_Y_SIZE)
        self.win.setBackground("Gray30")

        self.y_step = 20
        self.x_step = 20
        self.diameter = self.x_step * 16/20
        y_start = 70

        message_panel = Text(Point(self.PANEL_X_SIZE / 2, 20), "Whirlwind Control Panel")
        message_panel.setTextColor("pink")
        message_panel.draw(self.win)

        # I've put a mouse zone in the top right corner to Exit the program, i.e., to synthesize a Whirlwind
        # alarm that causes the interpreter to exit.  Mark the spot with a red X
        xline = Line(Point(self.PANEL_X_SIZE - self.XBOX, self.XBOX),
                     Point(self.PANEL_X_SIZE, 0))
        xline.setOutline("Red")
        xline.setWidth(2)
        xline.draw(self.win)
        xline = Line(Point(self.PANEL_X_SIZE - self.XBOX, 0),
                     Point(self.PANEL_X_SIZE, self.XBOX))
        xline.setOutline("Red")
        xline.setWidth(2)
        xline.draw(self.win)

        self.dual_ir = DualInterventionRegisterClass(self.win, x=50, y=50, left_init=left_init, right_init=right_init)

        row = 9
        self.ffreg = []
        # self.ffreg.append(FFRregClass(self, addr=1, x=30, y=y_start+row*self.y_step))
        # row += 3
        self.ffreg.append(FFRregClass(self, addr=2, x=30, y=y_start+row*self.y_step))
        row += 3
        self.ffreg.append(FFRregClass(self, addr=3, x=30, y=y_start+row*self.y_step))
        row += 3
        self.ffreg.append(FFRregClass(self, addr=4, x=30, y=y_start+row*self.y_step))
        row += 3
        self.ffreg.append(FFRregClass(self, addr=5, x=30, y=y_start+row*self.y_step))
        row += 3
        self.ffreg.append(FFRregClass(self, addr=6, x=30, y=y_start+row*self.y_step))
        row += 3

        self.cpu_reg_acc = CPURregClass(self, "ACC", x=30, y=y_start + row * self.y_step, initial_value=0)
        row += 1
        self.cpu_reg_breg = CPURregClass(self, "BR", x=30, y=y_start + row * self.y_step, initial_value=0)
        row += 1
        self.cpu_reg_areg = CPURregClass(self, "AR", x=30, y=y_start + row * self.y_step, initial_value=0)
        row += 1
        self.cpu_reg_pc = CPURregClass(self, "PC", x=30, y=y_start+row*self.y_step, initial_value=0, pc_special=True)
        row += 2

        self.cpu_control = CPUControlClass(self, x=30, y=y_start+row*self.y_step, x_step=self.x_step, y_step=self.y_step)

        # the first element in the dict is the switch Read entry point, the second is the one to set the switches
        self.dispatch = {"LMIR":[self.dual_ir.read_left_register, self.dual_ir.set_left_register],
                    "RMIR": [self.dual_ir.read_right_register, self.dual_ir.set_right_register],
                    "ActivationReg0": [self.activate_reg_read, self.activate_reg_write],
                    # "FF01": [self.ffreg[0].read_ff_register, self.ffreg[0].write_ff_register],
                    # "FF01Sw": [self.ffreg[0].read_switch_register, self.ffreg[0].set_switch_register],
                    "FF02": [self.ffreg[0].read_ff_register, self.ffreg[0].write_ff_register],
                    "FF02Sw": [self.ffreg[0].read_switch_register, self.ffreg[0].set_switch_register],
                    "FF03": [self.ffreg[1].read_ff_register, self.ffreg[1].write_ff_register],
                    "FF03Sw": [self.ffreg[1].read_switch_register, self.ffreg[1].set_switch_register],
                    "FF04": [self.ffreg[2].read_ff_register, self.ffreg[2].write_ff_register],
                    "FF04Sw": [self.ffreg[2].read_switch_register, self.ffreg[2].set_switch_register],
                    "FF05": [self.ffreg[3].read_ff_register, self.ffreg[3].write_ff_register],
                    "FF05Sw": [self.ffreg[3].read_switch_register, self.ffreg[3].set_switch_register],
                    "FF06": [self.ffreg[4].read_ff_register, self.ffreg[4].write_ff_register],
                    "FF06Sw": [self.ffreg[4].read_switch_register, self.ffreg[4].set_switch_register],
                    }


    # Check the mouse, and update any buttons.  The only return from this call should be True or False to say
    # whether the Exit box was clicked or not.
    # As a side effect, the simulator run state in cb is updated
    def update_panel(self, cb, pc, bank, acc, alarm_state=0, standalone=False):
        if not standalone:
            cpu = cb.cpu
            self.cpu_reg_acc.write_cpu_register(cpu._AC)
            self.cpu_reg_areg.write_cpu_register(cpu._AReg)
            self.cpu_reg_breg.write_cpu_register(cpu._BReg)
            self.cpu_reg_pc.write_cpu_register(cpu.PC + (bank << 12))

        pt = self.win.checkMouse()
        if pt[0]:
            # print("Panel mouse x=%d, y=%d" % (pt[0].x, pt[0].y))

            self.dual_ir.test_ir_hit(pt[0].x, pt[0].y)
            # print("Left Intervention Register set to  0o%06o" % self.dual_ir.read_register("left_ir"))
            # print("Right Intervention Register set to 0o%06o" % self.dual_ir.read_register("right_ir"))
            # print("FF0 Register set to 0o%06o" % self.ffreg[0].read_register("FF0"))

            for ff in self.ffreg:
                ff.test_for_ff_hit(pt[0].x, pt[0].y)

            self.cpu_control.test_for_hit(pt[0].x, pt[0].y, cb)

            # This test checks for hit of the Red X in the top right corner
            if pt[0].x > self.PANEL_X_SIZE - self.XBOX and pt[0].y < self.XBOX:
                return False

        # update all the blinkenlights
        if not standalone:
            self.cpu_control.set_cpu_state_lamps(cb, cb.sim_state, alarm_state)
        return True

    # read a register from the switches and lights panel.
    # It would normally be called with a string giving the name.  Inside the simulator
    # sometimes it's easier to find a number for the flip-flop registers
    def read_register(self, which_one):
        if type(which_one) is int:
            which_one = "FF%02oSw" % which_one
        if which_one not in self.dispatch:
            print("Panel.read_register: unknown register %s" % which_one)
            exit()
        # element zero in the dispatch is the Read entry; element one is the Set entry
        return self.dispatch[which_one][0]()

    # write a register to the switches and lights panel.
    # It would normally be called with a string giving the name.  Inside the simulator
    # sometimes it's easier to find a number for the flip-flop registers
    def write_register(self, which_one, value):
        if type(which_one) is int:
            which_one = "FF%02o" % which_one
        if which_one not in self.dispatch:
            print("Panel.write_register: unknown register %s" % which_one)
            exit()
        # element zero in the dispatch is the Read entry; element one is the Set entry
        return self.dispatch[which_one][1](value)

    # call this entry point to initialize the value of a switch register.  Invoked by the
    # routine that reads Core files and parses %Switch directives
    #def set_switches(self, name, val):
    #    if name not in self.dispatch:
    #        print("Panel.set_register: unknown register %s", name)
    #        exit()
    #    # element zero in the dispatch is the Read entry; element one is the Set entry
    #    return self.dispatch[name][1](val)


    # assemble all the known activate bits into a single word
    def activate_reg_read(self):
        ret = 0
        left_activate = self.dual_ir.left_ir.activate.read_bit()
        if left_activate:
            self.dual_ir.left_ir.activate.lamp.set_lamp(False)

        right_activate = self.dual_ir.right_ir.activate.read_bit()
        if right_activate:
            self.dual_ir.right_ir.activate.lamp.set_lamp(False)

        # I _think_ Upper/Lower (i.e. left/right) Activate buttons return the top two bits or ActReg0
        ret = left_activate << 15 | (right_activate << 14)
        return ret

    def activate_reg_write(self, val):
        fn = [self.dual_ir.left_ir.activate.write_bit, self.dual_ir.right_ir.activate.write_bit]
        lamp = [self.dual_ir.left_ir.activate.lamp.set_lamp, self.dual_ir.right_ir.activate.lamp.set_lamp]
        shift = [15, 14]

        for i in range(0, len(fn)):
            bit = (val >> shift[i]) & 1  # pick up the bit for each Activate, one at a time
            if bit:
                fn[i](1)        # "push" the activate button
                lamp[i](True)   # turn on the light associated with the button

    def reset_ff_registers(self, function, log=None, info_str=''):

        for ff in self.ffreg:
            ff.reset_register(function, log, info_str)

def compensate_justification(txt, font=9):
    count = len(txt)
    offset = count * (font / 3)
    return offset

# ########################## Framework ###########################
def main():
    crt_win = GraphWin("Control Panel Layout", 512, 512)
    crt_win.setBackground("Gray10")


    x = 30
    y = 100
    txt = "Hello GraphWin CRT!"
    message_crt = Text(Point(x, y + compensate_justification(txt)), txt)
    message_crt.setTextColor("yellow")
    message_crt.setTextAngle("-90")
    message_crt.draw(crt_win)
    # rect = Rectangle(Point(x - 6, y - 4*len(txt)), Point(x + 6, y + 4*len(txt)))
    rect = Rectangle(Point(x - 6, y - 6), Point(x + 6, y + 6))
    rect.setOutline("white")
    rect.setWidth(2)
    rect.draw(crt_win)


#    m = crt_win
#    return self.tk.getint(self.tk.call(
#        self._w, 'create', itemType,
#        *(args + self._options(cnf, kw))))
#    ret = m.tk.call(
#        m._w, 'create', 'text', '100.0', '70.0', '-angle', '-90', '-justify', 'left',
#        '-fill', 'green', '-text', 'Hello TK CRT!', '-font', 'helvetica 12 normal')
#        *(args + self._options(cnf, kw))))

    panel = PanelClass(left_init=0o123456, right_init=0o012345)

    panel.write_register("FF02Sw", 0x5050)

    x = 30
    incr = 10
    i = 0
    while True:
        # scroll a message back and forth on what should be the "crt"
        message = Text(Point(x, 40), "Main CRT Win: x=%d" % x)
        message.setTextColor("pink")
        message.draw(crt_win)
        time.sleep(0.40)
        message.undraw()
        x += incr
        if (x > 200):
            incr = -10
        if (x < 30):
            incr = +10

        if (i % 7) == 0:
            act_val = panel.read_register("ActivationReg0")
            print("LMIR=0o%06o, RMIR=0o%06o, FF02=0o%06o, ActivateReg0=0o%o" %
                  (panel.read_register("LMIR"), panel.read_register("RMIR"), panel.read_register("FF02"),
                   act_val))
            panel.reset_ff_registers(panel.write_register)
        i += 1

        pt = crt_win.checkMouse() # watch for mouse clicks in the CRT window
        if pt[0]:
            print("CRT mouse x=%d, y=%d" % (pt[0].x, pt[0].y))
            if pt[0].x < 40 and pt[0].y < 40:  # test for exit
                break

        # second
        if panel.update_panel(None, None, None, None, standalone=True) == False: # watch for mouse clicks on the panel
            break

        #  not sure how to regulate which window gets the key clicks, but in this case, it's the Panel
        # Might be the most-recent window created
        key = panel.win.checkKey()
        if key != '':
            print("key 1: %s, 0x%x" % (key, ord(key[0])))


    # all done
    crt_win.close()    # Close window when done
    panel.win.close()    # Close window when done

if __name__ == "__main__":
    main()

