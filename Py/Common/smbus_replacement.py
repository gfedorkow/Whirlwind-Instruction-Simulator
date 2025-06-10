
class SMBus:
    def __init__(self, bus_number):
        print("init SMBUS")

    def write_i2c_block_data(self, i2c_addr, ISSI_COMMANDREGISTER, msg):
        msg_text = ""
        for m in msg:
            msg_text += "0x%x " % m
        print("write_i2c_block_data: i2c_addr 0x%x, Command=0x%x, msg_len=0d%d, msg=%s" %
              (i2c_addr, ISSI_COMMANDREGISTER, len(msg), msg_text))

    def write_byte_data(self, i2c_addr, cmd, val):
        print("write byte data")

    def read_byte_data(self, i2c_addr, command):
        print("read byte data")
        return 0
