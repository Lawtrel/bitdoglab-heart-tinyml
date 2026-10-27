"""Front-end definido explicitamente; C++ implementa os mesmos coeficientes."""
import math
import wave
from pathlib import Path
import numpy as np


def load_audio(path, target_rate=4000):
    with wave.open(str(path), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getcomptype() != "NONE":
            raise ValueError(f"WAV precisa ser mono PCM16 sem compressao: {path}")
        rate = wav.getframerate()
        raw = wav.readframes(wav.getnframes())
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if not len(samples):
        raise ValueError(f"Audio vazio: {path}")
    if rate != target_rate:
        try:
            from scipy.signal import resample_poly
        except ImportError as exc:
            raise RuntimeError("Reamostragem requer scipy; instale requirements.txt.") from exc
        divisor = math.gcd(rate, target_rate)
        samples = resample_poly(samples, target_rate // divisor, rate // divisor).astype(np.float32)
        # PCM16 canonico tambem apos reamostragem, identico ao transporte USB.
        samples = np.clip(np.rint(samples * 32768), -32768, 32767).astype("<i2").astype(np.float32) / 32768.0
    return samples


def windows(samples, c):
    """Remove DC por janela, inclusive no firmware; padding antes da media."""
    size, hop = c["window_samples"], c["hop_samples"]
    if len(samples) < size:
        samples = np.pad(samples, (0, size - len(samples)))
    for start in range(0, len(samples) - size + 1, hop):
        # Para replay, o PCM nao e alterado; a remocao DC ocorre em extract().
        yield start, samples[start:start + size].copy()


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


def prepare(manifest_path, out, c):
    from .common import fresh_directory, read_json, write_json, sha256, object_hash, provenance
    m = read_json(manifest_path)
    rows = m["recordings"]
    if not rows:
        raise ValueError("Manifesto sem gravacoes.")
    out = fresh_directory(out)
    features, metadata = [], []
    coeffs = coefficients(c)
    for row in rows:
        path = Path(m["data_root"]) / row["path"]
        if sha256(path) != row["sha256"]:
            raise ValueError(f"Arquivo alterado apos inventario: {path}")
        for start, samples in windows(load_audio(path, c["sample_rate"]), c):
            features.append(extract(samples, c, coeffs))
            metadata.append({k: row[k] for k in ("patient_id", "encounter_id", "recording_id", "label", "split")}
                            | {"start": start, "path": row["path"]})
    x = np.stack(features)
    split = np.array([r["split"] for r in metadata])
    train = x[split == "train"]
    if len(train) == 0:
        raise ValueError("Treino vazio.")
    mean = train.mean(axis=(0, 1), dtype=np.float64).astype(np.float32)
    std = np.maximum(train.std(axis=(0, 1), dtype=np.float64), c["std_floor"]).astype(np.float32)
    normalized = ((x - mean) / std)[..., None].astype(np.float32)
    if not np.isfinite(normalized).all():
        raise ValueError("Features nao finitas.")
    np.savez(out / "features.npz", x=normalized, y=np.array([r["label"] for r in metadata], np.int32),
             split=split, patient=np.array([r["patient_id"] for r in metadata]),
             recording=np.array([r["recording_id"] for r in metadata]), mean=mean, std=std)
    write_json(out / "windows.json", metadata)
    write_json(out / "preparation.json", {"config": c, "config_hash": object_hash(c),
        "manifest_sha256": sha256(manifest_path), "manifest": m,
        "features_sha256": sha256(out / "features.npz"), "provenance": provenance(),
        "normalization_source": "train_only", "window_count": len(x),
        "feature_shape": list(normalized.shape), "status": "features_prepared_no_model"})
    print(f"Features: {normalized.shape}; normalizacao calculada apenas no treino.")
