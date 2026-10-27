"""Leitura validada dos recursos congelados e das evidências publicáveis."""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import numpy as np
from ..domain.errors import IntegrityError
from ..domain.models import FROZEN_MODEL_SHA256, FROZEN_THRESHOLD

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

@dataclass(frozen=True)
class ModelBundle:
    path: Path
    manifest: dict
    mean: np.ndarray
    std: np.ndarray

class FrozenModelRepository:
    def __init__(self, assets: Path):
        self.folder = assets / "model"

    def load(self) -> ModelBundle:
        manifest = read_json(self.folder / "manifest.json")
        # Nomes fixos evitam referências fora da pasta de recursos.
        path = self.folder / "model_int8.tflite"
        normalization = self.folder / "normalization.json"
        if manifest["model_sha256"] != FROZEN_MODEL_SHA256 or sha256(path) != FROZEN_MODEL_SHA256:
            raise IntegrityError("O modelo mudou. Restaure os recursos congelados.")
        if sha256(normalization) != manifest["normalization_sha256"]:
            raise IntegrityError("A normalização mudou. Não execute com coeficientes alterados.")
        if manifest["threshold"] != FROZEN_THRESHOLD:
            raise IntegrityError("O limiar difere do experimento congelado.")
        config = manifest["frontend"]
        expected = (4000, 12000, 128, 64, 24, 30.0, 1800.0, 1e-6)
        actual = tuple(config[k] for k in ("sample_rate", "window_samples", "fft_size", "frame_hop", "mel_bands", "low_hz", "high_hz", "log_floor"))
        if actual != expected:
            raise IntegrityError("Configuração MFE incompatível com o modelo.")
        raw = read_json(normalization)
        mean, std = (np.asarray(raw[k], np.float32) for k in ("mean", "std"))
        if mean.shape != (24,) or std.shape != (24,) or not np.isfinite(mean).all() or not np.isfinite(std).all() or np.any(std <= 0):
            raise IntegrityError("Coeficientes de normalização inválidos.")
        return ModelBundle(path, manifest, mean, std)

class EvidenceRepository:
    def __init__(self, assets: Path):
        self.assets = assets

    def classification(self) -> dict:
        return read_json(self.assets / "evidence/classification.json")

    def benchmark(self) -> dict:
        return read_json(self.assets / "evidence/benchmark.json")

    def fresh_benchmark(self) -> dict:
        return read_json(self.assets / "evidence/fresh_benchmark.json")

    def catalog(self) -> dict:
        return read_json(self.assets / "audio/catalog.json")

    def sample(self, number: int) -> bytes:
        examples = self.catalog()["examples"]
        sample = next((item for item in examples if item["number"] == number), None)
        if sample is None:
            raise FileNotFoundError("Exemplo inexistente")
        # O nome e construido a partir do numero validado, nunca do pedido HTTP.
        blob = (self.assets / "audio" / f"exemplo-{number}.wav").read_bytes()
        if hashlib.sha256(blob).hexdigest() != sample["wav_sha256"]:
            raise IntegrityError("O audio de exemplo mudou. Restaure o arquivo original.")
        return blob
