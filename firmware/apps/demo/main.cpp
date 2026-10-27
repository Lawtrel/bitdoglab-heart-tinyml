// V3 didatica separada: A/B e PCM USB. Nao altera o experimento cientifico.
#include "pico/stdlib.h"
#include "pico/stdio_usb.h"
#include "hardware/clocks.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/system_setup.h"
#include "tensorflow/lite/schema/schema_generated.h"
#include "frontend.h"
#include "frontend_config.h"
#include "model_data.h"
#include "model_config.h"
#include "demo_samples.h"
#include "presentation_ui.h"
#include "microphone.h"
#include <cstdio>
#include <cmath>
namespace {
alignas(16) uint8_t arena[pcg::kArenaBytes];
int16_t pcm[pcg::kWindowSamples];
tflite::MicroInterpreter* net=nullptr;TfLiteTensor* input=nullptr;TfLiteTensor* output=nullptr;
struct Result {float score=0;uint64_t pre=0,infer=0;bool ok=false;};
void Fatal(const char* s){demo::Clear();demo::Line(2,s);demo::Show();present::ErrorSound();while(true)sleep_ms(100);}
uint32_t Crc(const uint8_t* p,size_t n){uint32_t c=0xffffffffu;for(size_t i=0;i<n;i++){c^=p[i];for(int j=0;j<8;j++)c=(c>>1)^(0xedb88320u&(0u-(c&1u)));}return ~c;}
uint32_t U32(const uint8_t* p){return uint32_t(p[0])|(uint32_t(p[1])<<8)|(uint32_t(p[2])<<16)|(uint32_t(p[3])<<24);}
bool Read(uint8_t* p,size_t n){uint64_t end=time_us_64()+5000000u;for(size_t i=0;i<n;i++){int v;do{v=getchar_timeout_us(1000);if(time_us_64()>end)return false;}while(v==PICO_ERROR_TIMEOUT);p[i]=uint8_t(v);}return true;}
void Error(uint32_t seq,const char* why){printf("{\"type\":\"error\",\"seq\":%lu,\"reason\":\"%s\"}\n",(unsigned long)seq,why);stdio_flush();}
void Hello(uint32_t seq){printf("{\"type\":\"hello\",\"seq\":%lu,\"ready\":true,\"app\":\"tinyml_aula_v3\",\"model_sha256\":\"%s\",\"clock_hz\":%lu}\n",(unsigned long)seq,pcg::kModelSha256,(unsigned long)clock_get_hz(clk_sys));stdio_flush();}
Result Infer(){Result r;auto t=time_us_64();pcg::ExtractFeatures(pcm,input->data.int8,pcg::kInputScale,pcg::kInputZero);r.pre=time_us_64()-t;t=time_us_64();auto s=net->Invoke();r.infer=time_us_64()-t;r.ok=s==kTfLiteOk;if(r.ok)r.score=(int(output->data.int8[1])-pcg::kOutputZero)*pcg::kOutputScale;return r;}
void Fields(const Result& r){printf("\"prob_present\":%.9g,\"preprocessing_us\":%llu,\"inference_us\":%llu,\"processing_us\":%llu",double(r.score),(unsigned long long)r.pre,(unsigned long long)r.infer,(unsigned long long)(r.pre+r.infer));}
void ShowDigital(const Result& r,bool from_usb,unsigned sample){
 present::Result(false,sample,r.score,r.score>=pcg::kThreshold);
 if(from_usb){demo::Line(0,"AUDIO DO PC (USB)");demo::Line(1,"JANELA DE 3 SEGUNDOS");demo::Show();}
}
void BusyUsb(){demo::Clear();demo::Line(0,"AUDIO DO PC (USB)");present::Big(3,"ANALISANDO");demo::Color(false,false,true);demo::Show();}
microphone::Stats Capture(){present::Tone(1000,80);present::Silence();sleep_ms(400);present::Busy(true,0);return microphone::Capture(pcm,pcg::kWindowSamples);}
const char* Quality(const microphone::Stats& s){if(!s.complete)return "captura_interrompida";if(s.clipped_fraction>0.01f)return "saturado";if(s.rms_adc<4.0f)return "som_baixo";return "ok";}
void Reject(const microphone::Stats& s){if(!s.complete)present::Reject("FALHOU","CAPTURA INTERROMPIDA");else if(s.clipped_fraction>0.01f)present::Reject("SATURADO","REDUZA O VOLUME");else present::Reject("SOM BAIXO","APROXIME A FONTE");}
void Usb(uint32_t seq,unsigned mode,uint32_t length,uint32_t crc){
 if(mode==0&&length==0){Hello(seq);return;}
 if(mode==3&&length==0){
   auto stats=Capture();if(!stats.complete){Error(seq,"captura_interrompida");return;}
   const bool good=stats.clipped_fraction<=0.01f&&stats.rms_adc>=4.0f;Result r;
   if(good){present::Big(3,"ANALISANDO");demo::Show();r=Infer();if(!r.ok){Error(seq,"invoke_failed");return;}}
   uint32_t checksum=Crc(reinterpret_cast<uint8_t*>(pcm),sizeof(pcm));
   printf("{\"type\":\"capture\",\"seq\":%lu,\"bytes\":%u,\"crc32\":%lu,\"quality_ok\":%s,\"reason\":\"%s\",\"rms_adc\":%.6g,\"clipped_fraction\":%.6g,\"capture_us\":%llu,\"result\":",(unsigned long)seq,unsigned(sizeof(pcm)),(unsigned long)checksum,good?"true":"false",Quality(stats),double(stats.rms_adc),double(stats.clipped_fraction),(unsigned long long)stats.capture_us);
   if(good){printf("{");Fields(r);printf("}");}else printf("null");printf("}\n");
   // Saida direta, sem o ultimo bloco retido no FILE* da newlib.
   stdio_put_string(reinterpret_cast<const char*>(pcm),sizeof(pcm),false,false);stdio_flush();
   if(good)present::Result(true,0,r.score,r.score>=pcg::kThreshold);else Reject(stats);return;
 }
 if(mode!=1||length!=sizeof(pcm)){Error(seq,"invalid_header");return;}
 if(!Read(reinterpret_cast<uint8_t*>(pcm),sizeof(pcm))){Error(seq,"payload_timeout");return;}
 if(Crc(reinterpret_cast<uint8_t*>(pcm),sizeof(pcm))!=crc){Error(seq,"payload_crc_mismatch");return;}
 BusyUsb();auto r=Infer();if(!r.ok){Error(seq,"invoke_failed");return;}
 printf("{\"type\":\"result\",\"seq\":%lu,",(unsigned long)seq);Fields(r);printf("}\n");stdio_flush();ShowDigital(r,true,0);
}
}
int main(){
 if(!set_sys_clock_khz(133000,true))return 2;stdio_init_all();stdio_set_translate_crlf(&stdio_usb,false);sleep_ms(300);demo::Init();present::Silence();
 tflite::InitializeTarget();auto* m=tflite::GetModel(g_model);if(m->version()!=TFLITE_SCHEMA_VERSION)Fatal("ERRO NO MODELO");
 static tflite::MicroMutableOpResolver<5> ops;
 if(ops.AddConv2D()!=kTfLiteOk||ops.AddMaxPool2D()!=kTfLiteOk||ops.AddMean()!=kTfLiteOk||ops.AddFullyConnected()!=kTfLiteOk||ops.AddSoftmax()!=kTfLiteOk)Fatal("ERRO NOS OPERADORES");
 static tflite::MicroInterpreter interpreter(m,ops,arena,sizeof(arena));net=&interpreter;if(net->AllocateTensors()!=kTfLiteOk)Fatal("MEMORIA INSUFICIENTE");input=net->input(0);output=net->output(0);
 if(input->type!=kTfLiteInt8||output->type!=kTfLiteInt8||input->bytes!=pcg::kFeatureCount||output->bytes!=2||std::fabs(input->params.scale-pcg::kInputScale)>1e-9f||input->params.zero_point!=pcg::kInputZero||std::fabs(output->params.scale-pcg::kOutputScale)>1e-9f||output->params.zero_point!=pcg::kOutputZero)Fatal("MODELO INCOMPATIVEL");
 present::Home();present::Tone(700,80);sleep_ms(80);present::Tone(1000,80);unsigned sample=0;bool old_a=true,old_b=true;int matched=0;uint64_t prefix_time=0;
 for(;;){
   int ch=getchar_timeout_us(0);if(ch!=PICO_ERROR_TIMEOUT){
     if(time_us_64()-prefix_time>2000000u)matched=0;prefix_time=time_us_64();const char* magic="PCG1";matched=(ch==magic[matched])?matched+1:(ch=='P'?1:0);
     if(matched==4){matched=0;uint8_t h[13];if(Read(h,sizeof(h)))Usb(U32(h),h[4],U32(h+5),U32(h+9));else Error(0,"header_timeout");}
   }
   const bool a=gpio_get(5),b=gpio_get(6);bool ra=old_a&&!a,rb=old_b&&!b;old_a=a;old_b=b;
   if(ra||rb){const bool mic=rb&&!ra;if(mic){auto s=Capture();if(!s.complete||s.rms_adc<4.0f||s.clipped_fraction>0.01f){Reject(s);}else{present::Big(3,"ANALISANDO");demo::Show();auto r=Infer();if(!r.ok)Fatal("ERRO NA INFERENCIA");present::Result(true,0,r.score,r.score>=pcg::kThreshold);}}
     else{present::Tone(1000,40);present::Busy(false,sample);memcpy(pcm,demo::kSamples[sample],sizeof(pcm));auto r=Infer();if(!r.ok)Fatal("ERRO NA INFERENCIA");ShowDigital(r,false,sample);sample=(sample+1)%2;}
     while(!gpio_get(5)||!gpio_get(6))sleep_ms(25);sleep_ms(40);old_a=old_b=true;
   }
   if(ch==PICO_ERROR_TIMEOUT)sleep_ms(1);
 }
}
