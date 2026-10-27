#pragma once
#include "pico/stdlib.h"
#include "hardware/adc.h"
#include "hardware/dma.h"
#include "hardware/clocks.h"
#include <cmath>
#include <cstdint>
namespace microphone {
struct Stats {float rms_adc=0,clipped_fraction=0,mean_adc=0;uint64_t capture_us=0;bool complete=false;};
constexpr int16_t ToPcm(unsigned raw) {return static_cast<int16_t>((static_cast<int>(raw)-2048)*16);}
static_assert(ToPcm(0)==-32768 && ToPcm(2048)==0 && ToPcm(4095)==32752,"ADC/PCM mapping");
inline Stats Capture(int16_t* pcm,unsigned count) {
  Stats stats;adc_init();adc_gpio_init(28);adc_select_input(2);adc_set_round_robin(0);adc_run(false);adc_fifo_drain();
  // RP2040 ADC: periodo = 1 + divisor; ADC clock read from SDK (normally 48 MHz).
  adc_set_clkdiv(static_cast<float>(clock_get_hz(clk_adc))/4000.0f-1.0f);
  adc_fifo_setup(true,true,1,false,false);
  const int channel=dma_claim_unused_channel(false);if(channel<0)return stats;
  auto config=dma_channel_get_default_config(channel);channel_config_set_transfer_data_size(&config,DMA_SIZE_16);
  channel_config_set_read_increment(&config,false);channel_config_set_write_increment(&config,true);channel_config_set_dreq(&config,DREQ_ADC);
  dma_channel_configure(channel,&config,pcm,&adc_hw->fifo,count,false);
  const uint64_t started=time_us_64();dma_start_channel_mask(1u<<channel);adc_run(true);
  while(dma_channel_is_busy(channel) && time_us_64()-started<5000000u) sleep_us(100);
  stats.capture_us=time_us_64()-started;stats.complete=!dma_channel_is_busy(channel);adc_run(false);
  if(!stats.complete)dma_channel_abort(channel);
  adc_fifo_drain();adc_fifo_setup(false,false,1,false,false);dma_channel_unclaim(channel);
  if(!stats.complete)return stats;
  int64_t sum=0,square=0;unsigned clipped=0;
  for(unsigned i=0;i<count;++i) {unsigned raw=static_cast<uint16_t>(pcm[i])&0xfffu;sum+=raw;square+=int64_t(raw)*raw;if(raw<=8||raw>=4087)++clipped;pcm[i]=ToPcm(raw);}
  const double mean=static_cast<double>(sum)/count;
  const double variance=static_cast<double>(square)/count-mean*mean;
  stats.mean_adc=static_cast<float>(mean);stats.rms_adc=static_cast<float>(std::sqrt(variance>0?variance:0));stats.clipped_fraction=static_cast<float>(clipped)/count;
  return stats;
}
}

