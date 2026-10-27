#pragma once
#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include "font6x8.h"
#include <cstdint>
#include <cstring>
#include <initializer_list>
namespace demo {
inline uint8_t screen[1024];
inline bool oled=false;
inline uint8_t address=0x3c;
inline int sda=-1;
inline bool Send(const uint8_t* p, size_t n) {
  return i2c_write_timeout_us(i2c1,address,p,n,false,5000)==static_cast<int>(n);
}
inline void Clear() { memset(screen,0,sizeof(screen)); }
inline void Line(int row, const char* text) {
  if(row<0 || row>7) return;
  memset(screen+row*128,0,128);
  for(int x=0; *text && x+6<=128; ++text,x+=6) {
    unsigned ch=static_cast<unsigned char>(*text);if(ch<32||ch>126)ch='?';
    memcpy(screen+row*128+x,kFont6x8[ch-32],6);
  }
}
inline void Show() {
  if(!oled) return;
  const uint8_t cmd[]={0x00,0x21,0,127,0x22,0,7};
  if(!Send(cmd,sizeof(cmd))) { oled=false;return; }
  for(int i=0;i<1024;i+=32) {
    uint8_t packet[33];packet[0]=0x40;memcpy(packet+1,screen+i,32);
    if(!Send(packet,sizeof(packet))) {oled=false;return;}
  }
}
inline void Color(bool red,bool green,bool blue) {
  gpio_put(13,red);gpio_put(11,green);gpio_put(12,blue);
}
inline void Init() {
  for(int pin:{13,11,12}) {gpio_init(pin);gpio_set_dir(pin,GPIO_OUT);gpio_put(pin,0);}
  for(int pin:{5,6}) {gpio_init(pin);gpio_set_dir(pin,GPIO_IN);gpio_pull_up(pin);}
  // V6/EmbarcaTech commonly uses 14/15; current V7 examples use 2/3.
  // Probe both supported I2C1 mappings with finite timeouts; no external dependency.
  const int pairs[2][2]={{14,15},{2,3}};
  for(const auto& pair:pairs) {
    i2c_init(i2c1,400000);
    gpio_set_function(pair[0],GPIO_FUNC_I2C);gpio_set_function(pair[1],GPIO_FUNC_I2C);
    gpio_pull_up(pair[0]);gpio_pull_up(pair[1]);
    for(uint8_t candidate:{uint8_t(0x3c),uint8_t(0x3d)}) {
      address=candidate;const uint8_t probe[]={0x00,0xae};
      if(Send(probe,sizeof(probe))) {oled=true;sda=pair[0];break;}
    }
    if(oled) break;
    i2c_deinit(i2c1);gpio_init(pair[0]);gpio_init(pair[1]);
  }
  if(oled) {
    const uint8_t setup[]={0x00,0xae,0xd5,0x80,0xa8,0x3f,0xd3,0x00,0x40,0x8d,0x14,0x20,0x00,0xa1,0xc8,0xda,0x12,0x81,0x7f,0xd9,0xf1,0xdb,0x40,0xa4,0xa6,0x2e,0xaf};
    oled=Send(setup,sizeof(setup));
  }
  Clear();Line(0,"BITDOGLAB / TINYML");Line(2,"DEMO PCG");Line(4,oled?"OLED OK":"OLED AUSENTE");Line(7,"NAO E DIAGNOSTICO");Show();
}
}

