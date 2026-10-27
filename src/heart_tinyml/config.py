"""Configuração portátil: nenhum caminho deste computador é obrigatório."""
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

@dataclass(frozen=True)
class AppConfig:
    assets: Path
    port: int = 8766
    open_browser: bool = True
    max_body_bytes: int = 30_000_000

    @classmethod
    def default(cls, **kwargs):
        return cls(assets=Path(str(files("heart_tinyml").joinpath("resources"))), **kwargs)
