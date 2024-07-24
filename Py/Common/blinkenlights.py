

# Classes to run the hardware I/O devices to make up the Micro-Whirlwind

# Guy Fedorkow, Jun 2024

# https://pypi.org/project/smbus2/
import smbus2  # also contains i2c support
import time


IS31_1_ADDR = 0x74
TCA8414_1_ADDR = 0x34
Debug_I2C = False

class BlinkenLights:
    def __init__(self, sim_state_machine_arg=None):
        self.sim_state_machine = sim_state_machine_arg
        print("I2C init: ")
        # bus = I2Cclass(channel = 1)
        self.i2c_bus = smbus2.SMBus(1)
        print("  done")

        self.is31_1 = IS31FL3731(self.i2c_bus, IS31_1_ADDR)
        self.is31_1.init_IS31()
        print("  IS31 init done")

        self.tca84 = TCA8414(self.i2c_bus, TCA8414_1_ADDR)
        self.tca84.init_tca8414(3, 2)  # scan 3 rows, 2 columns
        self.tca84.init_gp_out()
        # flush the internal buffer
        self.tca84.flush()
        print("  TCA8414 init done")


    def check_buttons(self):
        # Official Button Names, as per Python-based Control Panel
        #buttons_def =  ["Clear Alarm", "Stop", "Start Over", "Restart", "Start at 40", "Order-by-Order", "Examine",
        #                                                                                                    "Read In"]
        buttons_def = [["Restart", "Start Over", "Examine"], ["Stop", "Single", "Clear"]]
        button_press = None
        if self.tca84.available() > 0:
            key = self.tca84.getEvent()
            pressed = key & 0x80
            if pressed:     # I'm ignoring "released" events
                key &= 0x7F
                key -= 1
                row = key // 10
                col = key % 10
                button_press = buttons_def[row][col]
                print("Pressed %s: row=%d, col=%d" % (button_press, row, col))
        return button_press

    def set_cpu_state_lamps(self, cb, sim_state, alarm_state):
        # ad-hoc; key scan GPIO-3 has two bits driving LEDs, for Run and Alarm
        leds = 0
        if sim_state != cb.SIM_STATE_STOP:
            leds |= 1   # green
        if alarm_state:     # Zero is No Alarm
            leds |= 2   # red
        self.tca84.set_gp_out(leds)


    def update_panel(self, cb, bank, alarm_state=0, standalone=False, init_PC=None):
        cpu = cb.cpu
        lights = [0] * 9
        lights[0] = ~cpu.PC
        lights[1] = cpu.PC
        lights[2] = ~cpu._AC
        lights[3] = cpu._AC
        lights[4] = cpu._BReg
        lights[5] = cpu._AReg
        lights[6] = cpu.cm.mem_addr_reg
        lights[7] = cpu.cm.rd(0x02, skip_mar=True)   # Fixed to FF2 for now; 'skip_mar' says to _not_ update the MAR/PAR with this read

        par = cpu.cm.mem_data_reg
        if par:  # make sure we're not sending None to the PAR lights register
            lights[7] = par
        else:
            lights[7] = 0
        self.is31_1.write_16bit_led_rows(0, lights)

        if not standalone:
            self.set_cpu_state_lamps(cb, cb.sim_state, alarm_state)
            bn = self.check_buttons()
            if bn:
                self.sim_state_machine(bn, cb)


# =============== TCA8414 Keypad Scanner ==================================

class TCA8414:
    def __init__(self, bus, i2c_addr):
        self.bus = bus
        self.i2c_addr = i2c_addr
        self.TCA8418_REG_CFG = 0x01  # < Configuration register
        self.TCA8418_REG_INT_STAT = 0x02  # < Interrupt status
        self.TCA8418_REG_KEY_LCK_EC = 0x03  # < Key lock and event counter
        self.TCA8418_REG_KEY_EVENT_A = 0x04  # < Key event register A
        self.TCA8418_REG_KEY_EVENT_B = 0x05  # < Key event register B
        self.TCA8418_REG_KEY_EVENT_C = 0x06  # < Key event register C
        self.TCA8418_REG_KEY_EVENT_D = 0x07  # < Key event register D
        self.TCA8418_REG_KEY_EVENT_E = 0x08  # < Key event register E
        self.TCA8418_REG_KEY_EVENT_F = 0x09  # < Key event register F
        self.TCA8418_REG_KEY_EVENT_G = 0x0A  # < Key event register G
        self.TCA8418_REG_KEY_EVENT_H = 0x0B  # < Key event register H
        self.TCA8418_REG_KEY_EVENT_I = 0x0C  # < Key event register I
        self.TCA8418_REG_KEY_EVENT_J = 0x0D  # < Key event register J
        self.TCA8418_REG_KP_LCK_TIMER = 0x0E  # < Keypad lock1 to lock2 timer
        self.TCA8418_REG_UNLOCK_1 = 0x0F  # < Unlock register 1
        self.TCA8418_REG_UNLOCK_2 = 0x10  # < Unlock register 2
        self.TCA8418_REG_GPIO_INT_STAT_1 = 0x11  # < GPIO interrupt status 1
        self.TCA8418_REG_GPIO_INT_STAT_2 = 0x12  # < GPIO interrupt status 2
        self.TCA8418_REG_GPIO_INT_STAT_3 = 0x13  # < GPIO interrupt status 3
        self.TCA8418_REG_GPIO_DAT_STAT_1 = 0x14  # < GPIO data status 1
        self.TCA8418_REG_GPIO_DAT_STAT_2 = 0x15  # < GPIO data status 2
        self.TCA8418_REG_GPIO_DAT_STAT_3 = 0x16  # < GPIO data status 3
        self.TCA8418_REG_GPIO_DAT_OUT_1 = 0x17  # < GPIO data out 1
        self.TCA8418_REG_GPIO_DAT_OUT_2 = 0x18  # < GPIO data out 2
        self.TCA8418_REG_GPIO_DAT_OUT_3 = 0x19  # < GPIO data out 3
        self.TCA8418_REG_GPIO_INT_EN_1 = 0x1A  # < GPIO interrupt enable 1
        self.TCA8418_REG_GPIO_INT_EN_2 = 0x1B  # < GPIO interrupt enable 2
        self.TCA8418_REG_GPIO_INT_EN_3 = 0x1C  # < GPIO interrupt enable 3
        self.TCA8418_REG_KP_GPIO_1 = 0x1D  # < Keypad/GPIO select 1
        self.TCA8418_REG_KP_GPIO_2 = 0x1E  # < Keypad/GPIO select 2
        self.TCA8418_REG_KP_GPIO_3 = 0x1F  # < Keypad/GPIO select 3
        self.TCA8418_REG_GPI_EM_1 = 0x20  # < GPI event mode 1
        self.TCA8418_REG_GPI_EM_2 = 0x21  # < GPI event mode 2
        self.TCA8418_REG_GPI_EM_3 = 0x22  # < GPI event mode 3
        self.TCA8418_REG_GPIO_DIR_1 = 0x23  # < GPIO data direction 1
        self.TCA8418_REG_GPIO_DIR_2 = 0x24  # < GPIO data direction 2
        self.TCA8418_REG_GPIO_DIR_3 = 0x25  # < GPIO data direction 3
        self.TCA8418_REG_GPIO_INT_LVL_1 = 0x26  # < GPIO edge/level detect 1
        self.TCA8418_REG_GPIO_INT_LVL_2 = 0x27  # < GPIO edge/level detect 2
        self.TCA8418_REG_GPIO_INT_LVL_3 = 0x28  # < GPIO edge/level detect 3
        self.TCA8418_REG_DEBOUNCE_DIS_1 = 0x29  # < Debounce disable 1
        self.TCA8418_REG_DEBOUNCE_DIS_2 = 0x2A  # < Debounce disable 2
        self.TCA8418_REG_DEBOUNCE_DIS_3 = 0x2B  # < Debounce disable 3
        self.TCA8418_REG_GPIO_PULL_1 = 0x2C  # < GPIO pull-up disable 1
        self.TCA8418_REG_GPIO_PULL_2 = 0x2D  # < GPIO pull-up disable 2
        self.TCA8418_REG_GPIO_PULL_3 = 0x2E  # < GPIO pull-up disable 3
        # #define TCA8418_REG_RESERVED          0x2F

        # FIELDS CONFIG REGISTER  1

        self.TCA8418_REG_CFG_AI = 0x80  # < Auto-increment for read/write
        self.TCA8418_REG_CFG_GPI_E_CGF = 0x40  # < Event mode config
        self.TCA8418_REG_CFG_OVR_FLOW_M = 0x20  # < Overflow mode enable
        self.TCA8418_REG_CFG_INT_CFG = 0x10  # < Interrupt config
        self.TCA8418_REG_CFG_OVR_FLOW_IEN = 0x08  # < Overflow interrupt enable
        self.TCA8418_REG_CFG_K_LCK_IEN = 0x04  # < Keypad lock interrupt enable
        self.TCA8418_REG_CFG_GPI_IEN = 0x02  # < GPI interrupt enable
        self.TCA8418_REG_CFG_KE_IEN = 0x01  # < Key events interrupt enable

        # FIELDS INT_STAT REGISTER  2
        self.TCA8418_REG_STAT_CAD_INT = 0x10  # < Ctrl-alt-del seq status
        self.TCA8418_REG_STAT_OVR_FLOW_INT = 0x08  # < Overflow interrupt status
        self.TCA8418_REG_STAT_K_LCK_INT = 0x04  # < Key lock interrupt status
        self.TCA8418_REG_STAT_GPI_INT = 0x02  # < GPI interrupt status
        self.TCA8418_REG_STAT_K_INT = 0x01  # < Key events interrupt status

        # FIELDS  KEY_LCK_EC REGISTER 3
        self.TCA8418_REG_LCK_EC_K_LCK_EN = 0x40  # < Key lock enable
        self.TCA8418_REG_LCK_EC_LCK_2 = 0x20  # < Keypad lock status 2
        self.TCA8418_REG_LCK_EC_LCK_1 = 0x10  # < Keypad lock status 1
        self.TCA8418_REG_LCK_EC_KLEC_3 = 0x08  # < Key event count bit 3
        self.TCA8418_REG_LCK_EC_KLEC_2 = 0x04  # < Key event count bit 2
        self.TCA8418_REG_LCK_EC_KLEC_1 = 0x02  # < Key event count bit 1
        self.TCA8418_REG_LCK_EC_KLEC_0 = 0x01  # < Key event count bit 0

    def writeRegister(self, command, val):
        if Debug_I2C: print("writeRegister: cmd=%x val=%x" % (command, val))
        self.bus.write_byte_data(self.i2c_addr, command, val)

    def readRegister(self, command):
        val = self.bus.read_byte_data(self.i2c_addr, command)
        if Debug_I2C: print("readRegister: cmd=%x val=%x" % (command, val))
        return val

    def i2c_reg_test(self):
        val = 0x55
        self.writeRegister(self.TCA8418_REG_GPIO_DIR_1, val)
        nval = self.readRegister(self.TCA8418_REG_GPIO_DIR_1)
        print(" Reg %x: val=%x, read=%x" % (self.TCA8418_REG_GPIO_DIR_1, val, nval))

    def init_tca8414(self, rows, columns):

        #  GPIO
        #  set default all GIO pins to INPUT
        self.writeRegister(self.TCA8418_REG_GPIO_DIR_1, 0x00)
        self.writeRegister(self.TCA8418_REG_GPIO_DIR_2, 0x00)
        self.writeRegister(self.TCA8418_REG_GPIO_DIR_3, 0x00)

        #  add all pins to key events
        self.writeRegister(self.TCA8418_REG_GPI_EM_1, 0xFF)
        self.writeRegister(self.TCA8418_REG_GPI_EM_2, 0xFF)
        self.writeRegister(self.TCA8418_REG_GPI_EM_3, 0x00)

        #  set all pins to FALLING interrupts
        self.writeRegister(self.TCA8418_REG_GPIO_INT_LVL_1, 0x00)
        self.writeRegister(self.TCA8418_REG_GPIO_INT_LVL_2, 0x00)
        self.writeRegister(self.TCA8418_REG_GPIO_INT_LVL_3, 0x00)

        #  add all pins to interrupts
        self.writeRegister(self.TCA8418_REG_GPIO_INT_EN_1, 0xFF)
        self.writeRegister(self.TCA8418_REG_GPIO_INT_EN_2, 0xFF)
        self.writeRegister(self.TCA8418_REG_GPIO_INT_EN_3, 0xFF)

        self.matrix(rows, columns)

    """ from: /**
     *  @file Adafruit_TCA8418.cpp
     *
     * 	I2C Driver for the Adafruit TCA8418 Keypad Matrix / GPIO Expander Breakout
     *
     * 	This is a library for the Adafruit TCA8418 breakout:
     * 	https://www.adafruit.com/product/XXXX
     *

    /**
     * @brief configures the size of the keypad matrix.
     *
     * @param [in] rows    number of rows, should be <= 8
     * @param [in] columns number of columns, should be <= 10
     * @return true is rows and columns have valid values.
     *
     * @details will always use the lowest pins for rows and columns.
     *          0..rows-1  and  0..columns-1
     */
    """

    def matrix(self, rows, columns):
        if (rows > 8) or (columns > 10):
            return False

        # skip zero size matrix
        if (rows != 0) and (columns != 0):
            # setup the keypad matrix.
            mask = 0x00
            for r in range(0, rows):
                mask <<= 1
                mask |= 1
            self.writeRegister(self.TCA8418_REG_KP_GPIO_1, mask)

            mask = 0x00
            for c in range(0, 8):  # (int c = 0; c < columns && c < 8; c++) {
                if c >= columns:
                    mask <<= 1
                    mask |= 1
            self.writeRegister(self.TCA8418_REG_KP_GPIO_2, mask)

            mask = 0
            if columns > 8:
                if columns == 9:
                    mask = 0x01;
                else:
                    mask = 0x03;
            self.writeRegister(self.TCA8418_REG_KP_GPIO_3, mask);
        return True

    # hack -- config two pins as output to blink an LED
    def init_gp_out(self):
        # column 8 and 9 pins
        self.writeRegister(self.TCA8418_REG_GPIO_DIR_3, 0x3)

    def set_gp_out(self, val):
        self.writeRegister(self.TCA8418_REG_GPIO_DAT_OUT_3, val)

    """ ... from Adafruit
    /**
     * @brief flushes the internal buffer of key events
     *        and cleans the GPIO status registers.
     *
     * @return number of keys flushed.
     */    """

    def flush(self):
        count = 0
        while self.getEvent() != 0:
            count += 1
        #  flush gpio events
        self.readRegister(self.TCA8418_REG_GPIO_INT_STAT_1)
        self.readRegister(self.TCA8418_REG_GPIO_INT_STAT_2)
        self.readRegister(self.TCA8418_REG_GPIO_INT_STAT_3)
        #  //  clear INT_STAT register
        self.writeRegister(self.TCA8418_REG_INT_STAT, 3)
        return count

    """
    /**
     * @brief gets first event from the internal buffer
     *
     * @return key event or 0 if none available
     *
     * @details
     *     key event 0x00        no event
     *               0x01..0x50  key  press
     *               0x81..0xD0  key  release
     *               0x5B..0x72  GPIO press
     *               0xDB..0xF2  GPIO release
     */
    """

    def getEvent(self):
        return self.readRegister(self.TCA8418_REG_KEY_EVENT_A)

    """
    /**
     * @brief checks if key events are available in the internal buffer
     *
     * @return number of key events in the buffer
     */
    """

    def available(self):
        eventCount = self.readRegister(self.TCA8418_REG_KEY_LCK_EC)
        eventCount &= 0x0F  # //  lower 4 bits only
        return eventCount



# =============== IS31FL3731 LED Mux ==================================
    # This class was derived from an Adafruit example
class IS31FL3731:
    def __init__(self, bus, i2c_addr):
        self.bus = bus
        self.i2c_addr = i2c_addr
        # converted from Adafruit library
        self.ISSI_REG_CONFIG = 0x00
        self.ISSI_REG_CONFIG_PICTUREMODE = 0x00
        self.ISSI_REG_CONFIG_AUTOPLAYMODE = 0x08
        self.ISSI_REG_CONFIG_AUDIOPLAYMODE = 0x18
        self.ISSI_CONF_PICTUREMODE = 0x00
        self.ISSI_CONF_AUTOFRAMEMODE = 0x04
        self.ISSI_CONF_AUDIOMODE = 0x08
        self.ISSI_REG_PICTUREFRAME = 0x01
        self.ISSI_REG_SHUTDOWN = 0x0A
        self.ISSI_REG_AUDIOSYNC = 0x06
        self.ISSI_COMMANDREGISTER = 0xFD
        self.ISSI_BANK_FUNCTIONREG = 0x0B  # helpfully called 'page nine'

    # this routine is used to transmit an easy-to-recognize pattern on
    # the I2C bus, for watching with a logic analyzer.  It doesn't make
    # the display do anything...
    def i2c_bus_test(self):
        msg = [2]
        self.bus.write_i2c_block_data(self.i2c_addr, 1, msg)
        msg = [4]
        self.bus.write_i2c_block_data(self.i2c_addr, 3, msg)
        msg = [6, 7]
        self.bus.write_i2c_block_data(self.i2c_addr, 5, msg)
        msg = [0xa, 0xb, 0xc]
        self.bus.write_i2c_block_data(self.i2c_addr, 9, msg)


    # write an IS31 control register.  Start by selecting "Page 9", the one that
    # has control registers instead of pixels.
    def writeRegister8(self, register, command, val=None):
        print("writeRegister: reg=%x, cmd=%x " % (register, command), "val=", val)
        msg = [register]
        self.bus.write_i2c_block_data(self.i2c_addr, self.ISSI_COMMANDREGISTER, msg)

        if val is not None:
            msg = [val]
        else:
            msg = []
        self.bus.write_i2c_block_data(self.i2c_addr, command, msg)


    def writeMultiRegister(self, register, val_list):
        #print("writeMultiRegister: reg=%x, " % (register), "val=", val_list)
        self.bus.write_i2c_block_data(self.i2c_addr, self.ISSI_COMMANDREGISTER, [0])
        self.bus.write_i2c_block_data(self.i2c_addr, register, val_list)


    def selectFrame(self, frame):
        msg = [frame]
        self.bus.write_i2c_block_data(self.i2c_addr, self.ISSI_COMMANDREGISTER, msg)

    def displayFrame(self, frame):
        self.writeRegister8(self.ISSI_BANK_FUNCTIONREG, self.ISSI_REG_PICTUREFRAME, val=frame);

    def set_brightness(self, bright):
        #for (uint8_t i = 0; i < 6; i++) {
        #  erasebuf[0] = 0x24 + i * 24;
        #  _i2c_dev->write(erasebuf, 25);
        #}
        IS31_LEDS = 192
        I2C_BLOCK = 24
        val = [bright] * I2C_BLOCK

        print("set brightness to %x" % bright)
        for i in range(0, IS31_LEDS // I2C_BLOCK):
            self.writeMultiRegister(i*I2C_BLOCK + 0x24, val)   # each 8 LEDs on (off)
        onoff = [0x5C] * (IS31_LEDS // 8)  # 8 bits per byte of on/off status
        print("set on-status to ", onoff)
        # for i in range(0, 18):
        self.writeMultiRegister(0, onoff)   # each 8 LEDs on (off)

    def write_16bit_led_rows(self, row, int_list):
        byte_list = []
        for val in int_list:
            byte_list.append(val & 0xff)
            byte_list.append(val >> 8)
        #self.writeMultiRegister(row * 2, byte_list)   # 16 bits in two bytes
        self.bus.write_i2c_block_data(self.i2c_addr, row, byte_list)


    def init_IS31(self):
        _frame = 0
        # shutdown
        print("Shutdown")
        self.writeRegister8(self.ISSI_BANK_FUNCTIONREG, self.ISSI_REG_SHUTDOWN, val=0x00)
        time.sleep(0.01)

        # out of shutdown
        print("unShutdown")
        self.writeRegister8(self.ISSI_BANK_FUNCTIONREG, self.ISSI_REG_SHUTDOWN, val=0x01)
        #time.sleep(1)

        # picture mode
        print("picture mode")
        self.writeRegister8(self.ISSI_BANK_FUNCTIONREG, self.ISSI_REG_CONFIG,
                 val=self.ISSI_REG_CONFIG_PICTUREMODE)

        #time.sleep(1)
        print("display frame")
        self.displayFrame(_frame)

        #time.sleep(1)
        print("set brightness")
        # all LEDs to the same brightness, and turn them all off
        self.set_brightness(0x16)


#class I2Cclass:
    #def __init__(self, channel = 1):
        # I2C channel 1 is connected to the GPIO pins
        # Initialize I2C (SMBus)
        #bus = smbus2.SMBus(channel)
        #_i2c_dev->setSpeed(400000);
        # bus.setSpeed(400000)

# --------------------
# the remainder of this file gives a standalone test program that exercises
# the hardware (currently the IS31 LED driver)
# July 7, 2024

class PingPongStruct():
    def __init__(self, i):
        print("pong_struct preset = ", i)

        self.delay_count = 0
        self.delay_preset = i
        self.incr = 1
        self.invert = 0
        self.val = 0

    def pingpong(self):
        self.delay_count -= 1
        if self.delay_count < 0:
            self.delay_count = self.delay_preset

            self.val += self.incr
            if self.val < 0:
                self.val = 1
                self.incr = 1
                self.invert = 0

            if self.val > 15:
                self.val = 14
                self.incr = -1
                self.invert = ~self.invert

        return((1 << self.val) ^ self.invert)


_NPONGS = 9
def _init_pongs():
    pp = []
    for i in range(0, _NPONGS):
        pp.append(PingPongStruct(i))
    return pp


# --------------------
def main():
    print("I2C init: ")
    # bus = I2Cclass(channel = 1)
    bus = smbus2.SMBus(1)
    print("  done")

    is31 = IS31FL3731(bus, IS31_1_ADDR)
    print("I2C Test")
    # is31.i2c_reg_test()
    is31.init_IS31()
    print("  IS31 init done")

    tca84 = TCA8414(bus, TCA8414_1_ADDR)
    print("TCA8414 Test")
    tca84.i2c_reg_test()
    tca84.init_tca8414(3, 2)  # scan 3 rows, 2 columns
    tca84.init_gp_out()
    # flush the internal buffer
    tca84.flush()

    print("  TCA8414 init done")

    pp = _init_pongs()
    int_val = [0] * _NPONGS
    is31.selectFrame(0)   # do this once, so it doesn't have to be done with each write of the LEDs
    while True:
        for j in range(0, _NPONGS):
            int_val[j] = pp[j].pingpong()
        is31.write_16bit_led_rows(0, int_val)
        time.sleep(.03)

    input("CR to Shutdown")
    is31.writeRegister8(ISSI_BANK_FUNCTIONREG, ISSI_REG_SHUTDOWN, val=0x00)
    time.sleep(1)

    for i in range(0, 10000):
        tca84.set_gp_out(i & 0x3)
        if tca84.available() > 0:
            key = tca84.getEvent()
            pressed = key & 0x80
            key &= 0x7F
            key -= 1
            row = key // 10
            col = key % 10
            push_str = "Released"
            if pressed:
                push_str = "Pressed "
            print("%s: row=%d, col=%d" % (push_str, row, col))

        time.sleep(0.3)


if __name__ == "__main__":
    main()
