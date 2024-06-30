
# Test program to run IS31FL3731 LED Multiplexer
# Derived from Adafruit 
# Guy Fedorkow, Jun 2024

# https://pypi.org/project/smbus2/
import smbus2


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

    def writeRegister8(self, bus, register, command, val):
           # Create our 12-bit number representing relative voltage
        msg = [register, command, val]

        bus.write_byte_data(register, command, val)
        # Write out I2C command: address, reg_write_dac, msg[0], msg[1]
        # bus.write_i2c_block_data(register, command, msg)


    def displayFrame(self, frame):
        self.writeRegister8(ISSI_BANK_FUNCTIONREG, ISSI_REG_PICTUREFRAME, frame);
    

    def set_intensity(val):
       pass

    def init(self):
        _frame = 0;
        # shutdown
        self.writeRegister8(ISSI_BANK_FUNCTIONREG, ISSI_REG_SHUTDOWN, 0x00);
        delay(10);

        # out of shutdown
        self.writeRegister8(ISSI_BANK_FUNCTIONREG, ISSI_REG_SHUTDOWN, 0x01);
        # picture mode
        self.writeRegister8(ISSI_BANK_FUNCTIONREG, ISSI_REG_CONFIG,
                 ISSI_REG_CONFIG_PICTUREMODE);

        self.displayFrame(_frame);

        # all LEDs to the same brightness, and turn them all off
        self.set_brightness(0x16)

        for frame in range(0, 8): 
            for i in range(0, 0x12):
                self.writeRegister8(frame, i, 0xff)   # each 8 LEDs on (off)

class I2C:
    def __init__(self, channel = 1):
        # I2C channel 1 is connected to the GPIO pins
        # Initialize I2C (SMBus)
        bus = smbus2.SMBus(channel)
        #_i2c_dev->setSpeed(400000);
        bus.setSpeed(400000)



def main():
    bus = I2C(channel = 1)

    is31 = IS31FL3731(bus)


main()