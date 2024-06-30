#include <Wire.h>
#include <Adafruit_GFX.h>
#include "Adafruit_IS31FL3731guy.h"
#include <LibPrintf.h>


// If you're using the full breakout...
Adafruit_IS31FL3731guy ledmatrix = Adafruit_IS31FL3731guy();
// If you're using the FeatherWing version
//Adafruit_IS31FL3731_Wing ledmatrix = Adafruit_IS31FL3731_Wing();


#define BUILDV_LEN 60
struct status_display_struct {
  char     buildv[BUILDV_LEN+1];
  uint8_t  chatty;
} StatusDisplay;

#define NPONGS 9
struct pingpong_struct {
  int16_t delay_count;
  int16_t delay_preset;
  int8_t  incr;
  uint16_t invert;
  int8_t  val;
  uint8_t  chan;
} pingpong_state[NPONGS];



void setup() {
  Serial.begin(9600);
  Serial.println("ISSI swirl test");
  delay(1500);

  if (! ledmatrix.begin()) {
    Serial.println("IS31 not found");
    while (1);
  }
  Serial.println("IS31 found!");


  int count = 0;
  for(uint8_t x=0; x<16; x++) {
    Serial.print("Row ");
    Serial.println(x);
    for(uint8_t y=0; y<9; y++) {
      ledmatrix.drawPixel(x, y, 16);
    }
    delay(80);
  }
  int i;
  struct pingpong_struct *pp;
  pp = &pingpong_state[0];
  for (i = 0; i < NPONGS; i++) {
    pp->delay_count = 0;
    pp->delay_preset = i;
    pp->val = 0;
    pp->incr = 1;
    pp->invert = 0;
    pp->chan = i;
    pp++;
  }
  Serial.println("Init Done");

#ifdef OLD
  while(1) {
    delay(500);
    ledmatrix.setLEDBytesguy(0, 0x55, 0xcc);
    delay(500);
    ledmatrix.setLEDBytesguy(0, 0xAA, 0x33);
  }
#endif
}

void loop_rand() {

  int count = 0;
  for(uint8_t x=0; x<16; x++) {
    Serial.print("Row ");
    Serial.println(x);
    for(uint8_t y=0; y<9; y++) {
      ledmatrix.drawPixel(x, y, random()%64);
    }
    delay(80);
  }
}

void display_one_register(uint8_t reg_num, uint16_t val) {
  int i, x, y, c_on, c_off;

  c_on = 16;
  c_off = 0;

  y = reg_num;
  for (i=0; i<16; i++) {
    if (val & (1 << i)) {
      ledmatrix.drawPixel(i, y, c_on);
      } 
    else {
      ledmatrix.drawPixel(i, y, c_off);
    }
  }
}


uint16_t pingpong( struct pingpong_struct *pp){
  
  if (pp->delay_count-- <= 0) {
    pp->delay_count = pp->delay_preset;

    pp->val += pp->incr;
    if (pp->val < 0) {
      pp->val = 1;
      pp->incr = 1;
    }
    if (pp->val > 15) {
      pp->val = 14;
      pp->incr = -1;
      pp->invert = ~(pp->invert);
    }
  }
  return((1 << pp->val) ^ pp->invert);
}

void loop() {
  static uint8_t count = 0;
  uint16_t led_cmd_buf[10];
  uint16_t *led_bit_map;
  uint16_t ping_buf[NPONGS];

  int i;
  struct pingpong_struct *pp;

  led_cmd_buf[0] = 0xDEAD;
  led_bit_map = &led_cmd_buf[1];

  led_bit_map[i] = count;
  pp = &pingpong_state[0];
  for (i = 1; i < NPONGS; i++) {
    led_bit_map[i] = pingpong(pp++);
  }

#ifdef OLD
  // display_one_register(1, count);
  if (count & 1) {
    led_bit_map[0] = 0x5533;
    led_bit_map[8] = 0xAACC;
  }
  else {
    led_bit_map[0] = 0xAACC;
    led_bit_map[8] = 0x5533;
  }
#endif

  //printf("LEDBuf cmd=%x, bit_map[0]=%x\n", led_bit_map[-1], led_bit_map[0]);
  ledmatrix.setLEDBufguy(0, 9, led_bit_map);
  //printf("done LEDBuf\n");

  //Serial.print("Still Here: ");

  Serial.println(count++);
  delay(30);
  // Do nothing -- image doesn't change

}

#ifdef ORIGINAL_SWIRL
// The lookup table to make the brightness changes be more visible
uint8_t sweep[] = {1, 2, 3, 4, 6, 8, 10, 15, 20, 30, 40, 60, 60, 40, 30, 20, 15, 10, 8, 6, 4, 3, 2, 1};

void loop() {
  // animate over all the pixels, and set the brightness from the sweep table
  for (uint8_t incr = 0; incr < 24; incr++)
    for (uint8_t x = 0; x < 16; x++)
      for (uint8_t y = 0; y < 9; y++)
        ledmatrix.drawPixel(x, y, sweep[(x+y+incr)%24]);
  delay(20);
}
#endif
