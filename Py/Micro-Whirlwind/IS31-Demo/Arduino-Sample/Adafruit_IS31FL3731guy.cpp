#include "Adafruit_IS31FL3731guy.h"
#include <LibPrintf.h>




#ifndef _swap_int16_t
#define _swap_int16_t(a, b)                                                    \
  {                                                                            \
    int16_t t = a;                                                             \
    a = b;                                                                     \
    b = t;                                                                     \
  }
#endif

/**************************************************************************/
/*!
    @brief Constructor for breakout version
    @param width Desired width of led display
    @param height Desired height of led display
*/
/**************************************************************************/

Adafruit_IS31FL3731guy::Adafruit_IS31FL3731guy(uint8_t width, uint8_t height)
    : Adafruit_GFX(width, height) {}

/**************************************************************************/
/*!
    @brief Constructor for FeatherWing version (15x7 LEDs)
*/
/**************************************************************************/
Adafruit_IS31FL3731guy_Wing::Adafruit_IS31FL3731guy_Wing(void)
    : Adafruit_IS31FL3731guy(15, 7) {}

/**************************************************************************/
/*!
    @brief Initialize hardware and clear display
    @param addr The I2C address we expect to find the chip at
    @param theWire The TwoWire I2C bus device to use, defaults to &Wire
    @returns True on success, false if chip isnt found
*/
/**************************************************************************/
bool Adafruit_IS31FL3731guy::begin(uint8_t addr, TwoWire *theWire) {
  if (_i2c_dev) {
    delete _i2c_dev;
  }
  _i2c_dev = new Adafruit_I2CDevice(addr, theWire);

  if (!_i2c_dev->begin()) {
    return false;
  }

  _i2c_dev->setSpeed(400000);
  _frame = 0;

  // shutdown
  writeRegister8(ISSI_BANK_FUNCTIONREG, ISSI_REG_SHUTDOWN, 0x00);

  delay(10);

  // out of shutdown
  writeRegister8(ISSI_BANK_FUNCTIONREG, ISSI_REG_SHUTDOWN, 0x01);

  // picture mode
  writeRegister8(ISSI_BANK_FUNCTIONREG, ISSI_REG_CONFIG,
                 ISSI_REG_CONFIG_PICTUREMODE);

  displayFrame(_frame);

  // all LEDs on & 0 PWM
  clear(); // set each led to 0 PWM

  for (uint8_t f = 0; f < 8; f++) {
    for (uint8_t i = 0; i <= 0x11; i++)
      writeRegister8(f, i, 0xff); // each 8 LEDs on
  }

  return true;
}

/**************************************************************************/
/*!
    @brief Sets all LEDs on & 0 PWM for current frame.
*/
/**************************************************************************/
void Adafruit_IS31FL3731guy::clear(void) {
  selectBank(_frame);
  uint8_t erasebuf[25];

  memset(erasebuf, 0, 25);

  for (uint8_t i = 0; i < 6; i++) {
    erasebuf[0] = 0x24 + i * 24;
    _i2c_dev->write(erasebuf, 25);
  }
}

/**************************************************************************/
/*!
    @brief Low level accesssor - sets a 8-bit PWM pixel value to a bank location
    does not handle rotation, x/y or any rearrangements!
    @param lednum The offset into the bank that corresponds to the LED
    @param bank The bank/frame we will set the data in
    @param pwm brightnes, from 0 (off) to 255 (max on)
*/
/**************************************************************************/
void Adafruit_IS31FL3731guy::setLEDPWM(uint8_t lednum, uint8_t pwm, uint8_t bank) {
  if (lednum >= 144)
    return;
  writeRegister8(bank, 0x24 + lednum, pwm);
}


/*
  Set the on/off status for sixteen LEDs
*/
void Adafruit_IS31FL3731guy::setLEDBytesguy(uint8_t reg, uint8_t bits_l, uint8_t bits_r) {
  uint8_t erasebuf[25];

  if (reg >= 18)
    return;
  //writeRegister8(_frame, lednum/8, bits);

  // memset(erasebuf, 0, 25);
  erasebuf[0] = 0;
  erasebuf[1] = bits_r;
  erasebuf[2] = bits_l;
  _i2c_dev->write(erasebuf, 3);

}

/*
  Set the on/off status for a set of sixteen-bit LED registers
  'reg' says which of 9 rows of 16 LEDs is the first to be written
  Be Careful!
  I'm assuming that the word ahead of the first register can be overwritten!
*/
void Adafruit_IS31FL3731guy::setLEDBufguy(uint8_t reg, uint8_t count, uint16_t *words) {
  uint8_t *byte_buf;
  uint8_t len;
  uint8_t i;

  byte_buf = (uint8_t *) words;

#ifdef DEBUG
  printf("cmd=%x ", byte_buf[-1]);
  printf("reg=%d, count=%d", reg, count);
  for (i = 0; i < 9; i++) printf(" r[%d]=0x%x", i, words[i]);
  printf("\n");
#endif

  if (reg+count > 9)
    return;
  
  byte_buf[-1] = reg * 2;
  len = 2* count + 1;
  _i2c_dev->write(&byte_buf[-1], len);

}


/**************************************************************************/
/*!
    @brief Adafruit GFX low level accesssor - sets a 8-bit PWM pixel value
    handles rotation and pixel arrangement, unlike setLEDPWM
    @param x The x position, starting with 0 for left-most side
    @param y The y position, starting with 0 for top-most side
    @param color Despite being a 16-bit value, takes 0 (off) to 255 (max on)
*/
/**************************************************************************/
void Adafruit_IS31FL3731guy::drawPixel(int16_t x, int16_t y, uint16_t color) {
  // check rotation, move pixel around if necessary
  switch (getRotation()) {
  case 1:
    _swap_int16_t(x, y);
    x = 16 - x - 1;
    break;
  case 2:
    x = 16 - x - 1;
    y = 9 - y - 1;
    break;
  case 3:
    _swap_int16_t(x, y);
    y = 9 - y - 1;
    break;
  }

  if ((x < 0) || (x >= 16))
    return;
  if ((y < 0) || (y >= 9))
    return;
  if (color > 255)
    color = 255; // PWM 8bit max

  setLEDPWM(x + y * 16, color, _frame);
  return;
}

/**************************************************************************/
/*!
    @brief Set's this object's frame tracker (does not talk to the chip)
    @param frame Ranges from 0 - 7 for the 8 frames
*/
/**************************************************************************/
void Adafruit_IS31FL3731guy::setFrame(uint8_t frame) { _frame = frame; }

/**************************************************************************/
/*!
    @brief Have the chip set the display to the contents of a frame
    @param frame Ranges from 0 - 7 for the 8 frames
*/
/**************************************************************************/
void Adafruit_IS31FL3731guy::displayFrame(uint8_t frame) {
  if (frame > 7)
    frame = 0;
  writeRegister8(ISSI_BANK_FUNCTIONREG, ISSI_REG_PICTUREFRAME, frame);
}

/**************************************************************************/
/*!
    @brief Switch to a given bank in the chip memory for future reads
    @param bank The IS31 bank to switch to
    @returns False if I2C command failed to be ack'd
*/
/**************************************************************************/
bool Adafruit_IS31FL3731guy::selectBank(uint8_t bank) {
  uint8_t cmd[2] = {ISSI_COMMANDREGISTER, bank};
  return _i2c_dev->write(cmd, 2);
}



/**************************************************************************/
/*!
    @brief Write one byte to a register located in a given bank
    @param bank The IS31 bank to write the register location
    @param reg the offset into the bank to write
    @param data The byte value
    @returns False if I2C command failed to be ack'd
*/
/**************************************************************************/
bool Adafruit_IS31FL3731guy::writeRegister8(uint8_t bank, uint8_t reg,
                                         uint8_t data) {
  selectBank(bank);

  uint8_t cmd[2] = {reg, data};
  return _i2c_dev->write(cmd, 2);
}

/**************************************************************************/
/*!
    @brief  Read one byte from a register located in a given bank
    @param   bank The IS31 bank to read the register location
    @param   reg the offset into the bank to read
    @return 1 byte value
*/
/**************************************************************************/
uint8_t Adafruit_IS31FL3731guy::readRegister8(uint8_t bank, uint8_t reg) {
  uint8_t val = 0xFF;

  selectBank(bank);

  _i2c_dev->write_then_read(&reg, 1, &val, 1);

  return val;
}
