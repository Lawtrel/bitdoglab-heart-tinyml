"""Decoder WAV PCM16 e conversão didática, independente da interface."""
import io
import wave
import numpy as np
from ..domain.errors import InputError
from ..domain.models import AudioWindow

SAMPLE_RATE = 4000
WINDOW_SAMPLES = 12000

def _resample(samples: np.ndarray, rate: int, first: int, origin: int) -> np.ndarray:
    """Sinc janelado com antialias; exclusivo da demonstração acústica.

    O estudo original usa scipy.signal.resample_poly. Esta implementação
    mantém a conversão da demo anterior, sem alterar o protocolo científico.
    """
    radius = max(32, int(np.ceil(32 * rate / SAMPLE_RATE)))
    cutoff = 0.94 * SAMPLE_RATE / rate
    output = np.zeros(WINDOW_SAMPLES, np.float64)
    offsets = np.arange(-radius + 1, radius + 1)
    for chunk in range(0, WINDOW_SAMPLES, 256):
        positions = first - origin + np.arange(chunk, min(chunk + 256, WINDOW_SAMPLES)) * rate / SAMPLE_RATE
        indices = np.floor(positions).astype(int)[:, None] + offsets
        delta = positions[:, None] - indices
        window = np.where(np.abs(delta) < radius, 0.5 + 0.5 * np.cos(np.pi * delta / radius), 0)
        kernel = cutoff * np.sinc(cutoff * delta) * window
        kernel /= np.maximum(kernel.sum(axis=1, keepdims=True), 1e-12)
        valid = (indices >= 0) & (indices < len(samples))
        values = samples[np.clip(indices, 0, len(samples) - 1)] * valid
        output[chunk:chunk + len(positions)] = (kernel * values).sum(axis=1)
    return np.rint(output).clip(-32768, 32767).astype("<i2")

class WavDecoder:
    """Adapter do contrato AudioDecoder para WAV sem compressão."""

    def decode(self, blob: bytes, start: float = 0.0) -> AudioWindow:
        try:
            return self._decode(blob, start)
        except (ValueError, wave.Error, EOFError, OverflowError) as error:
            raise InputError(str(error) or "Arquivo WAV inválido.") from error

    def _decode(self, blob: bytes, start: float) -> AudioWindow:
        if not np.isfinite(start) or start < 0:
            raise ValueError("O início precisa ser um número finito e positivo ou zero.")
        with wave.open(io.BytesIO(blob), "rb") as source:
            rate = source.getframerate()
            channels = source.getnchannels()
            frames = source.getnframes()
            if source.getsampwidth() != 2 or source.getcomptype() != "NONE" or channels not in (1, 2):
                raise ValueError("Use WAV PCM16 mono ou estéreo. MP3 e WAV float não são aceitos.")
            if not 4000 <= rate <= 96000:
                raise ValueError("Use uma taxa de amostragem entre 4 e 96 kHz.")
            first = int(round(start * rate))
            if first >= frames:
                raise ValueError("O início está além do fim do áudio.")
            radius = max(32, int(np.ceil(32 * rate / SAMPLE_RATE)))
            origin = max(0, first - radius)
            end = min(frames, first + 3 * rate + radius)
            source.setpos(origin)
            raw = np.frombuffer(source.readframes(end - origin), "<i2").reshape(-1, channels)
        samples = raw.astype(np.float64).mean(axis=1)
        if rate == SAMPLE_RATE:
            pcm = np.rint(samples[first - origin:first - origin + WINDOW_SAMPLES]).clip(-32768, 32767).astype("<i2")
            pcm = np.pad(pcm, (0, WINDOW_SAMPLES - len(pcm)))
        else:
            pcm = _resample(samples, rate, first, origin)
        converted = rate != SAMPLE_RATE or channels != 1
        metadata = {
            "source_rate": rate, "source_channels": channels,
            "start_seconds": first / rate, "duration_seconds": frames / rate,
            "padded": first + 3 * rate > frames, "converted": converted,
            "conversion": "Conversão didática mono/sinc para 4 kHz, fora do protocolo científico" if converted else "PCM16 canônico",
        }
        return AudioWindow(pcm, metadata)

    def encode(self, audio: AudioWindow) -> bytes:
        result = io.BytesIO()
        with wave.open(result, "wb") as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(SAMPLE_RATE)
            target.writeframes(audio.pcm.astype("<i2").tobytes())
        return result.getvalue()
