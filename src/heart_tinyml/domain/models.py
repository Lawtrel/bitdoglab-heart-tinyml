"""Objetos de domínio independentes de HTTP, LiteRT e USB."""
from dataclasses import dataclass, field
from typing import Any
import numpy as np

FROZEN_MODEL_SHA256 = "3b7e258e26ca124d9e973ba8b4ac5744c87c3ed1d41f501192d2ca7a0b185454"
FROZEN_THRESHOLD = 0.7346754807692307
WINDOW_SAMPLES = 12000

@dataclass(frozen=True)
class AudioWindow:
    pcm: np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class InferenceOutput:
    score: float
    threshold: float
    preprocessing_ms: float
    inference_ms: float
    waveform: np.ndarray
    mfe: np.ndarray
    pcm_sha256: str
    model_sha256: str

    @property
    def label(self) -> str:
        return "Present" if self.score >= self.threshold else "Absent"

    @property
    def processing_ms(self) -> float:
        return self.preprocessing_ms + self.inference_ms

@dataclass(frozen=True)
class BoardCapture:
    audio: AudioWindow
    quality_ok: bool
    reason: str
    metadata: dict[str, Any]
    result: dict[str, Any] | None
