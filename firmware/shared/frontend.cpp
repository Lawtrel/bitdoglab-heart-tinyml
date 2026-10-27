#include "frontend.h"
#include "frontend_config.h"
#include <algorithm>
#include <cmath>
#include <cstdint>
namespace pcg {
void ExtractFeatures(const int16_t* pcm, int8_t* quantized, float scale, int zero,
                     float* normalized) {
  int64_t sum = 0;
  for (int i = 0; i < kWindowSamples; ++i) sum += pcm[i];
  const float mean = static_cast<float>(static_cast<double>(sum) /
      (static_cast<double>(kWindowSamples) * 32768.0));
  float re[kFft], im[kFft], power[kFft / 2 + 1];
  for (int frame = 0; frame < kFrames; ++frame) {
    for (int i = 0; i < kFft; ++i) {
      re[i] = (pcm[frame * kFrameHop + i] / 32768.0f - mean) * kHann[i];
      im[i] = 0;
    }
    // FFT radix-2 nao normalizada. Uma frame por vez para economizar RAM.
    for (int i = 1, j = 0; i < kFft; ++i) {
      int bit = kFft >> 1;
      for (; j & bit; bit >>= 1) j ^= bit;
      j ^= bit;
      if (i < j) { std::swap(re[i], re[j]); std::swap(im[i], im[j]); }
    }
    for (int len = 2; len <= kFft; len <<= 1)
      for (int start = 0; start < kFft; start += len)
        for (int j = 0; j < len / 2; ++j) {
          const int w = j * kFft / len, a = start + j, b = a + len / 2;
          const float tr = kTwiddleReal[w] * re[b] - kTwiddleImag[w] * im[b];
          const float ti = kTwiddleReal[w] * im[b] + kTwiddleImag[w] * re[b];
          re[b] = re[a] - tr; im[b] = im[a] - ti;
          re[a] += tr; im[a] += ti;
        }
    for (int k = 0; k <= kFft / 2; ++k) power[k] = re[k]*re[k] + im[k]*im[k];
    for (int band = 0; band < kBands; ++band) {
      float energy = 0;
      for (int k = 0; k <= kFft / 2; ++k)
        energy += power[k] * kMel[band * (kFft/2 + 1) + k];
      const float value = (std::log(std::max(energy, kLogFloor)) - kMean[band]) / kStd[band];
      const int index = frame * kBands + band;
      if (normalized) normalized[index] = value;
      const float q = std::round(value / scale) + static_cast<float>(zero);
      quantized[index] = static_cast<int8_t>(std::max(-128.0f, std::min(127.0f, q)));
    }
  }
}
}
