"""MFE e quantização compatíveis com o front-end congelado do estudo."""

import numpy as np


def coefficients(c):
    n = c["fft_size"]
    # Hann periodica (denominador N), sem centralizacao/padding do STFT.
    hann = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n) / n)).astype(np.float32)
    hz_to_mel = lambda hz: 2595.0 * np.log10(1 + hz / 700.0)
    points = np.linspace(hz_to_mel(c["low_hz"]), hz_to_mel(c["high_hz"]), c["mel_bands"] + 2)
    hz = 700.0 * (10 ** (points / 2595.0) - 1)
    freq = np.arange(n // 2 + 1) * c["sample_rate"] / n
    bank = np.empty((c["mel_bands"], len(freq)), dtype=np.float32)
    for b in range(c["mel_bands"]):
        bank[b] = np.maximum(0, np.minimum((freq - hz[b]) / (hz[b+1] - hz[b]),
                                         (hz[b+2] - freq) / (hz[b+2] - hz[b+1])))
        if not np.any(bank[b] > 0):
            raise ValueError(f"Filtro mel vazio: {b}")
    return hann, bank


def extract(samples, c, coeffs=None):
    if np.shape(samples) != (c["window_samples"],):
        raise ValueError("Janela deve ter exatamente 12000 amostras.")
    hann, bank = coeffs or coefficients(c)
    x = np.asarray(samples, np.float32)
    x = x - np.float32(np.mean(x, dtype=np.float64))
    frames = np.lib.stride_tricks.sliding_window_view(x, c["fft_size"])[::c["frame_hop"]]
    spectrum = np.fft.rfft(frames * hann, axis=1)
    # FFT nao normalizada; sem duplicar potencia dos bins positivos.
    power = (spectrum.real ** 2 + spectrum.imag ** 2).astype(np.float32)
    energy = power @ bank.T
    return np.log(np.maximum(energy, c["log_floor"])).astype(np.float32)


def quantize(x, scale, zero):
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("Escala INT8 invalida.")
    # Arredondamento half-away-from-zero, igual ao std::round do C++.
    raw = np.asarray(x, np.float64) / scale
    rounded = np.copysign(np.floor(np.abs(raw) + 0.5), raw)
    return np.clip(rounded + zero, -128, 127).astype(np.int8)


