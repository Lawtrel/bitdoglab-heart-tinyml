"""Composition root: implementações concretas reunidas em um único lugar."""
from dataclasses import dataclass
import importlib.metadata
import platform
import os
from .adapters.audio import WavDecoder
from .adapters.inference import LiteRTPredictor
from .adapters.repositories import EvidenceRepository, FrozenModelRepository
from .adapters.serial_board import SerialBoardAdapter
from .application.service import AnalysisService
from .config import AppConfig

@dataclass
class Application:
    service: AnalysisService
    evidence: EvidenceRepository
    config: AppConfig

def create_application(config: AppConfig) -> Application:
    model = FrozenModelRepository(config.assets).load()
    service = AnalysisService(LiteRTPredictor(model), WavDecoder(), SerialBoardAdapter())
    return Application(service, EvidenceRepository(config.assets), config)

def provenance() -> dict:
    import numpy as np
    return {
        "platform": platform.platform(), "processor": platform.processor(),
        "python": platform.python_version(), "numpy": np.__version__,
        "litert": importlib.metadata.version("ai-edge-litert"),
        "runtime": "LiteRT BUILTIN_REF, CPU, uma thread", "gpu_used": False,
        "logical_cpus": os.cpu_count(),
    }
