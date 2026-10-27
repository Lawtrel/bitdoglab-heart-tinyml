from pathlib import Path
import numpy as np
from .features import coefficients


def _floats(array):
    def literal(x):
        s = format(float(x), ".9g")
        if "." not in s and "e" not in s.lower():
            s += ".0"
        return s + "f"
    return ", ".join(literal(x) for x in np.asarray(array).ravel())


def write_frontend_header(path, mean, std, c):
    hann, bank = coefficients(c)
    angles = 2*np.pi*np.arange(64)/128
    text = """#pragma once
// Gerado pelo treinamento. Mesmos coeficientes do Python; nao editar a mao.
namespace pcg {
inline constexpr int kSampleRate = 4000, kWindowSamples = 12000;
inline constexpr int kFft = 128, kFrameHop = 64, kFrames = 186, kBands = 24;
inline constexpr int kFeatureCount = kFrames * kBands;
"""
    for name, arr in (("kHann", hann), ("kMel", bank), ("kMean", mean), ("kStd", std),
                      ("kTwiddleReal", np.cos(angles)), ("kTwiddleImag", -np.sin(angles))):
        text += f"inline constexpr float {name}[{np.asarray(arr).size}] = {{{_floats(arr)}}};\n"
    text += f"inline constexpr float kLogFloor = {_floats([c['log_floor']])};\n}}\n"
    Path(path).write_text(text, encoding="utf-8")


def write_generated(folder, model_path, ex, mean, std, c):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    model = Path(model_path).read_bytes()
    (folder/"model_data.h").write_text(
        "#pragma once\n#include <cstddef>\nextern const unsigned char g_model[];\n"
        "extern const unsigned int g_model_len;\n", encoding="utf-8")
    lines = [", ".join(f"0x{b:02x}" for b in model[i:i+16]) for i in range(0, len(model), 16)]
    (folder/"model_data.cpp").write_text('#include "model_data.h"\n'
        'alignas(16) const unsigned char g_model[] = {\n' + ",\n".join(lines) +
        f"\n}};\nconst unsigned int g_model_len = {len(model)};\n", encoding="utf-8")
    text = '#pragma once\n#include <cstddef>\nnamespace pcg {\n'
    for name, key in (("kInputScale", "input_scale"), ("kOutputScale", "output_scale"),
                       ("kThreshold", "threshold")):
        text += f"inline constexpr float {name} = {_floats([ex[key]])};\n"
    text += f"inline constexpr int kInputZero = {ex['input_zero_point']}, kOutputZero = {ex['output_zero_point']};\n"
    text += f"inline constexpr std::size_t kArenaBytes = {c['tensor_arena_bytes']};\n"
    text += f'inline constexpr char kModelSha256[] = "{ex["model_sha256"]}";\n'
    text += '}\n'
    (folder/"model_config.h").write_text(text, encoding="utf-8")
    write_frontend_header(folder/"frontend_config.h", mean, std, c)
