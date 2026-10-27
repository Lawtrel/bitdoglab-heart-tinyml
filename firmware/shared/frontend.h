#pragma once
#include <cstdint>
namespace pcg {
// PCM16 mono 4 kHz. Float opcional somente para validacao desktop.
void ExtractFeatures(const int16_t* pcm, int8_t* quantized, float scale, int zero,
                     float* normalized = nullptr);
}
