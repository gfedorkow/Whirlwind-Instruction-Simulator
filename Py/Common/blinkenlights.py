
# =Test program to run IS31FL3731 LED Multiplexer
# Derived from Adafruit 
# Guy Fedorkow, Jun 2024

# https://pypi.org/project/smbus2/
import smbus2
import time

IS31_1_ADDR = 0x74

# converted from Adafruit library
ISSI_REG_CONFIG = 0x00
ISSI_REG_CONFIG_PICTUREMODE = 0x00
ISSI_REG_CONFIG_AUTOPLAYMODE = 0x08
ISSI_REG_CONFIG_AUDIOPLAYMODE = 0x18
ISSI_CONF_PICTUREMODE = 0x00
ISSI_CONF_AUTOFRAMEMODE = 0x04
ISSI_CONF_AUDIOMODE = 0x08
ISSI_REG_PICTUREFRAME = 0x01
ISSI_REG_SHUTDOWN = 0x0A
ISSI_REG_AUDIOSYNC = 0x06
ISSI_COMMANDREGISTER = 0xFD
ISSI_BANK_FUNCTIONREG = 0x0B  # helpfully called 'page nine'

class IS31FL3731:
    def __init__(self, bus):
        self.bus = bus

    # this routine is used to transmit an easy-to-recognize pattern on
    # the I2C bus, for watching with a logic analyzer.  It doesn't make
    # the display do anything...
    def i2c_bus_test(self):
        msg = [2]
        self.bus.write_i2c_block_data(IS31_1_ADDR, 1, msg)
        msg = [4]
        self.bus.write_i2c_block_data(IS31_1_ADDR, 3, msg)
        msg = [6, 7]
        self.bus.write_i2c_block_data(IS31_1_ADDR, 5, msg)
        msg = [0xa, 0xb, 0xc]
        self.bus.write_i2c_block_data(IS31_1_ADDR, 9, msg)


    # write an IS31 control register.  Start by selecting "Page 9", the one that
    # has control registers instead of pixels.
    def writeRegister8(self, register, command, val=None):
        print("writeRegister: reg=%x, cmd=%x " % (register, command), "val=", val)
        msg = [register]
        self.bus.write_i2c_block_data(IS31_1_ADDR, ISSI_COMMANDREGISTER, msg)

        if val is not None:
            msg = [val]
        else:
            msg = []
        self.bus.write_i2c_block_data(IS31_1_ADDR, command, msg)


    def writeMultiRegister(self, register, val_list):
        #print("writeMultiRegister: reg=%x, " % (register), "val=", val_list)
        self.bus.write_i2c_block_data(IS31_1_ADDR, ISSI_COMMANDREGISTER, [0])
        self.bus.write_i2c_block_data(IS31_1_ADDR, register, val_list)


    def selectFrame(self, frame):
        msg = [frame]
        self.bus.write_i2c_block_data(IS31_1_ADDR, ISSI_COMMANDREGISTER, msg)

    def displayFrame(self, frame):
        self.writeRegister8(ISSI_BANK_FUNCTIONREG, ISSI_REG_PICTUREFRAME, val=frame);

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
        self.bus.write_i2c_block_data(IS31_1_ADDR, row, byte_list)


    def init(self):
        _frame = 0;
        # shutdown
        print("Shutdown")
        self.writeRegister8(ISSI_BANK_FUNCTIONREG, ISSI_REG_SHUTDOWN, val=0x00);
        time.sleep(0.01);

        # out of shutdown
        print("unShutdown")
        self.writeRegister8(ISSI_BANK_FUNCTIONREG, ISSI_REG_SHUTDOWN, val=0x01);
        #time.sleep(1)

        # picture mode
        print("picture mode")
        self.writeRegister8(ISSI_BANK_FUNCTIONREG, ISSI_REG_CONFIG,
                 val=ISSI_REG_CONFIG_PICTUREMODE);

        #time.sleep(1)
        print("display frame")
        self.displayFrame(_frame);

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

_NPONGS = 9
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

    is31 = IS31FL3731(bus)
    print("I2C Test")
    # is31.i2c_reg_test()
    is31.init()
    print("  IS31 init done")

    pp = _init_pongs()
    int_val = [0] * _NPONGS
    is31.selectFrame(0)   # do this once, so it doesn't have to be done with each write of the LEDs
    while True:
        for j in range(0, _NPONGS):
            int_val[j] = pp[j].pingpong()
        is31.write_16bit_led_rows(0, int_val)
        time.sleep(.03)

    input("CR to Shutdown")
    is31.writeRegister8(ISSI_BANK_FUNCTIONREG, ISSI_REG_SHUTDOWN, val=0x00);
    time.sleep(1)


if __name__ == "__main__":
    main()
