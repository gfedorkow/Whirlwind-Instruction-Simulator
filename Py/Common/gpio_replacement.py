
class gpioClass:
    def __init__(self):
        self.BCM = 0
        self.OUT = 0
        self.IN = 0
        self.PUD_UP = 0
        print("gpio init")

    def setmode(self, mode):
        print("set gpio mode")

    def setup(self, pin_gpio_LED1, pindir, pull_up_down=0):
        print("pin setup")

    def output(self, pin, val):
        print("output val=0o%o to pin %d" % (val, pin))

    def input(self, pin):
        print("input from pin %d" % pin)

