#pragma once
// UI: letras grandes e tons usados apenas como sinais de interface.
#include "display.h"
#include <cstdio>
#include "hardware/pwm.h"
#include "hardware/clocks.h"
namespace present {
constexpr unsigned kBuzzerPin=21;
inline void Silence() {
  const uint slice=pwm_gpio_to_slice_num(kBuzzerPin);pwm_set_enabled(slice,false);
  gpio_init(kBuzzerPin);gpio_set_dir(kBuzzerPin,GPIO_OUT);gpio_put(kBuzzerPin,0);
}
inline void Tone(unsigned hz,unsigned ms) {
  gpio_set_function(kBuzzerPin,GPIO_FUNC_PWM);
  const uint slice=pwm_gpio_to_slice_num(kBuzzerPin);
  const float div=125.0f;
  const uint16_t wrap=static_cast<uint16_t>(clock_get_hz(clk_sys)/(div*hz)-1);
  auto config=pwm_get_default_config();pwm_config_set_clkdiv(&config,div);pwm_config_set_wrap(&config,wrap);
  pwm_init(slice,&config,false);pwm_set_gpio_level(kBuzzerPin,(wrap+1)/4);pwm_set_enabled(slice,true);
  sleep_ms(ms);Silence();
}
inline void ResultSound(bool present) {
  if(present) {for(int i=0;i<3;++i) {Tone(1800,100);sleep_ms(100);}}
  else Tone(850,220);
}
inline void ErrorSound() {Tone(350,220);sleep_ms(100);Tone(350,220);}
inline bool Big(int row,const char* text) {
  if(row<0 || row>6 || strlen(text)>10) return false;
  memset(demo::screen+row*128,0,256);
  int cursor=0;
  for(;*text;++text,cursor+=12) {
    unsigned ch=static_cast<unsigned char>(*text);if(ch<32||ch>126)ch='?';
    for(int x=0;x<6;++x) for(int y=0;y<8;++y) if(kFont6x8[ch-32][x]&(1u<<y)) {
      for(int dx=0;dx<2;++dx) for(int dy=0;dy<2;++dy) {
        int px=cursor+x*2+dx,py=row*8+y*2+dy;
        demo::screen[(py/8)*128+px] |= uint8_t(1u<<(py%8));
      }
    }
  }
  return true;
}
inline void Home() {
  demo::Clear();Big(0,"TINYML");demo::Line(3,"SONS DO CORACAO");demo::Line(4,"PC: COMPARACAO USB");
  demo::Line(5,"A: EXEMPLOS GRAVADOS");demo::Line(6,"B: MICROFONE (TESTE)");demo::Line(7,"NAO E DIAGNOSTICO");
  demo::Color(false,false,true);demo::Show();
}
inline void Busy(bool mic,unsigned sample) {
  demo::Clear();demo::Line(0,mic?"MICROFONE":"EXEMPLO GRAVADO");
  if(mic) {demo::Line(1,"EXPERIMENTAL");Big(3,"OUVINDO");demo::Line(5,"GRAVANDO 3 SEGUNDOS");}
  else {char line[24];snprintf(line,sizeof(line),"TRECHO %u/2",sample+1);demo::Line(1,line);Big(3,"ANALISANDO");}
  demo::Color(false,false,true);demo::Show();
}
inline void Result(bool mic,unsigned sample,float score,bool detected) {
  demo::Clear();demo::Line(0,mic?"MICROFONE":"EXEMPLO GRAVADO");
  char text[24];if(mic)demo::Line(1,"EXPERIMENTAL");else {snprintf(text,sizeof(text),"TRECHO %u/2",sample+1);demo::Line(1,text);}
  Big(3,mic?(detected?"COM SOPRO?":"SEM SOPRO?"):(detected?"COM SOPRO":"SEM SOPRO"));
  snprintf(text,sizeof(text),"ESCORE: %.3f",static_cast<double>(score));demo::Line(5,text);
  demo::Line(6,mic?"TESTE SEM VALIDACAO":(detected?"VERMELHO: 3 BIPES":"VERDE: 1 BIPE"));
  demo::Line(7,"A EXEMPLOS B MICRO");
  // Microfone permanece azul: a saida experimental nao e um alarme validado.
  demo::Color(mic?false:detected,mic?false:!detected,mic);demo::Show();
  if(mic) {Tone(650,70);sleep_ms(100);Tone(650,70);} else ResultSound(detected);
}
inline void Reject(const char* cause,const char* instruction) {
  demo::Clear();demo::Line(0,"MICROFONE - TESTE");Big(2,cause);demo::Line(5,instruction);demo::Line(6,"B: TENTAR NOVAMENTE");demo::Line(7,"A: EXEMPLOS");
  demo::Color(true,true,false);demo::Show();ErrorSound();
}
}

