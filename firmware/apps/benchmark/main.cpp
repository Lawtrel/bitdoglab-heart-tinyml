// Replay digital USB. Microfone/OLED ficam para uma etapa posterior.
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
#include <cmath>
#include <cstdio>
#include <cstdint>
namespace {
alignas(16) uint8_t arena[pcg::kArenaBytes];
int16_t pcm[pcg::kWindowSamples];
tflite::MicroInterpreter* interpreter = nullptr;
TfLiteTensor* input = nullptr;
TfLiteTensor* output = nullptr;
bool ready = false;
uint64_t allocation_us = 0;
uint32_t Crc32(const uint8_t* data, size_t size) {
  uint32_t crc = 0xffffffffu;
  for (size_t i = 0; i < size; ++i) {
    crc ^= data[i];
    for (int bit = 0; bit < 8; ++bit) crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
  }
  return ~crc;
}
bool ReadBytes(uint8_t* dst, size_t n) {
  const uint64_t deadline = time_us_64() + 30000000u;
  for (size_t i = 0; i < n; ++i) {
    int value;
    do {
      value = getchar_timeout_us(1000);
      if (time_us_64() > deadline) return false;
    } while (value == PICO_ERROR_TIMEOUT);
    dst[i] = static_cast<uint8_t>(value);
  }
  return true;
}
uint32_t Little32(const uint8_t* b) {
  return uint32_t(b[0]) | (uint32_t(b[1])<<8) | (uint32_t(b[2])<<16) | (uint32_t(b[3])<<24);
}
void Error(uint32_t seq, const char* reason) {
  printf("{\"type\":\"error\",\"seq\":%lu,\"reason\":\"%s\"}\n",
         static_cast<unsigned long>(seq), reason);
  stdio_flush();
}
void Hello(uint32_t seq) {
  printf("{\"type\":\"hello\",\"seq\":%lu,\"ready\":%s,"
         "\"model_sha256\":\"%s\",\"clock_hz\":%lu,\"arena_capacity_bytes\":%u,"
         "\"arena_used_bytes\":%u,\"pcm_buffer_bytes\":%u,\"allocation_us\":%llu,"
         "\"stack_high_water_bytes\":null,\"total_peak_ram_bytes\":null,"
         "\"mode\":\"digital_pcm16_4000hz\"}\n",
         static_cast<unsigned long>(seq), ready ? "true" : "false", pcg::kModelSha256,
         static_cast<unsigned long>(clock_get_hz(clk_sys)), static_cast<unsigned>(sizeof(arena)),
         ready ? static_cast<unsigned>(interpreter->arena_used_bytes()) : 0u,
         static_cast<unsigned>(sizeof(pcm)), static_cast<unsigned long long>(allocation_us));
  stdio_flush();
}
bool SetupModel() {
  tflite::InitializeTarget();
  const tflite::Model* model = tflite::GetModel(g_model);
  if (model->version() != TFLITE_SCHEMA_VERSION) return false;
  static tflite::MicroMutableOpResolver<6> resolver;
  if (resolver.AddConv2D() != kTfLiteOk || resolver.AddMaxPool2D() != kTfLiteOk ||
      resolver.AddMean() != kTfLiteOk || resolver.AddFullyConnected() != kTfLiteOk ||
      resolver.AddSoftmax() != kTfLiteOk || resolver.AddReshape() != kTfLiteOk) return false;
  static tflite::MicroInterpreter instance(model, resolver, arena, sizeof(arena));
  interpreter = &instance;
  const uint64_t start = time_us_64();
  if (interpreter->AllocateTensors() != kTfLiteOk) return false;
  allocation_us = time_us_64() - start;
  input = interpreter->input(0); output = interpreter->output(0);
  if (input->type != kTfLiteInt8 || output->type != kTfLiteInt8 ||
      input->bytes != pcg::kFeatureCount || output->bytes != 2) return false;
  if (std::fabs(input->params.scale - pcg::kInputScale) > 1e-9f ||
      input->params.zero_point != pcg::kInputZero ||
      std::fabs(output->params.scale - pcg::kOutputScale) > 1e-9f ||
      output->params.zero_point != pcg::kOutputZero) return false;
  return true;
}
}
int main() {
  if (!set_sys_clock_khz(133000, true)) return 2;
  stdio_init_all();
  stdio_set_translate_crlf(&stdio_usb, false);
  // Nenhuma chamada inicia Wi-Fi ou core1 neste aplicativo.
  ready = SetupModel();
  for (;;) {
    // PCG1 + uint32 seq + uint8 modo + uint32 nbytes + uint32 CRC32.
    const char magic[] = "PCG1";
    int matched = 0;
    while (matched != 4) {
      const int ch = getchar_timeout_us(1000);
      if (ch == PICO_ERROR_TIMEOUT) continue;
      matched = (ch == magic[matched]) ? matched + 1 : (ch == 'P' ? 1 : 0);
    }
    uint8_t header[13];
    if (!ReadBytes(header, sizeof(header))) continue;
    const uint32_t seq = Little32(header);
    const uint8_t mode = header[4];
    const uint32_t length = Little32(header+5), expected_crc = Little32(header+9);
    if (mode == 0 && length == 0) { Hello(seq); continue; }
    if ((mode != 1 && mode != 2) || length != sizeof(pcm)) {
      Error(seq, "invalid_header"); continue;
    }
    if (!ReadBytes(reinterpret_cast<uint8_t*>(pcm), sizeof(pcm))) {
      Error(seq, "payload_timeout"); continue;
    }
    if (Crc32(reinterpret_cast<uint8_t*>(pcm), sizeof(pcm)) != expected_crc) {
      Error(seq, "payload_crc_mismatch"); continue;
    }
    if (!ready) { Error(seq, "model_not_ready"); continue; }
    const uint64_t start = time_us_64();
    pcg::ExtractFeatures(pcm, input->data.int8, pcg::kInputScale, pcg::kInputZero);
    const uint64_t pre_end = time_us_64();
    const uint32_t feature_crc = Crc32(reinterpret_cast<uint8_t*>(input->data.int8), pcg::kFeatureCount);
    if (mode == 2) {
      printf("{\"type\":\"features\",\"seq\":%lu,\"bytes\":%d,\"crc32\":%lu}\n",
          static_cast<unsigned long>(seq), pcg::kFeatureCount, static_cast<unsigned long>(feature_crc));
      // Saida binaria direta: stdio_flush() nao esvazia o FILE* da newlib.
      // Nao usar fwrite aqui: o ultimo bloco pode permanecer no buffer libc.
      stdio_put_string(reinterpret_cast<const char*>(input->data.int8),
                       pcg::kFeatureCount, false, false);
      stdio_flush();
      continue;
    }
    const uint64_t invoke_start = time_us_64();
    const TfLiteStatus status = interpreter->Invoke();
    const uint64_t finish = time_us_64();
    if (status != kTfLiteOk) { Error(seq, "invoke_failed"); continue; }
    const float p = (static_cast<int>(output->data.int8[1])-pcg::kOutputZero) * pcg::kOutputScale;
    printf("{\"type\":\"result\",\"seq\":%lu,\"prob_present\":%.9g,"
           "\"preprocessing_us\":%llu,\"inference_us\":%llu,\"processing_us\":%llu,"
           "\"feature_crc32\":%lu}\n",
           static_cast<unsigned long>(seq), static_cast<double>(p),
           static_cast<unsigned long long>(pre_end-start),
           static_cast<unsigned long long>(finish-invoke_start),
           static_cast<unsigned long long>((pre_end-start)+(finish-invoke_start)),
           static_cast<unsigned long>(feature_crc));
    // CRC, transferencia e formatacao nao entram nos tempos de processamento.
    stdio_flush();
  }
}
