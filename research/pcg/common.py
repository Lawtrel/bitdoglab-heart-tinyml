import csv
import hashlib
import json
import platform
from pathlib import Path
from datetime import datetime, timezone
import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                    encoding="utf-8")


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def object_hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, allow_nan=False).encode()).hexdigest()


def config(path=None):
    c = read_json(path or ROOT / "config.json")
    if (c["sample_rate"], c["window_samples"], c["fft_size"], c["frame_hop"], c["mel_bands"]) != (
            4000, 12000, 128, 64, 24):
        raise ValueError("Esta versao compartilha front-end fixo 4000/12000/128/64/24 com C++. "
                         "Para altera-lo, atualize e valide ambos antes de novo experimento.")
    for key in ("hop_samples", "batch_size", "epochs", "patience", "bootstrap_replicates",
                "calibration_windows", "tensor_arena_bytes"):
        if not isinstance(c[key], int) or c[key] <= 0:
            raise ValueError(f"{key} precisa ser inteiro positivo.")
    fractions = [c[k] for k in ("train_fraction", "validation_fraction", "test_fraction")]
    if not all(0 < v < 1 for v in fractions) or abs(sum(fractions)-1) > 1e-9:
        raise ValueError("Proporcoes de treino/validacao/teste devem somar um.")
    seeds = c["training_seeds"]
    if not seeds or len(set(seeds)) != len(seeds) or not all(isinstance(s, int) for s in seeds):
        raise ValueError("Seeds de treino devem ser inteiras, distintas e nao vazias.")
    if not 0 <= c["low_hz"] < c["high_hz"] < c["sample_rate"]/2:
        raise ValueError("Faixa mel invalida.")
    return c


def write_csv(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    fields = fields or (list(rows[0]) if rows else [])
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def provenance():
    import importlib.metadata
    packages = {}
    for name in ("numpy", "scipy", "tensorflow", "pyserial"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {"utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
            "platform": platform.system(), "packages": packages,
            "source_hash": object_hash({str(p.relative_to(ROOT)): sha256(p)
                                       for p in sorted((ROOT / "pcg").glob("*.py"))})}


def fresh_directory(path):
    path = Path(path)
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(f"Pasta nao vazia: {path}. Use um nome novo para preservar resultados.")
    path.mkdir(parents=True, exist_ok=True)
    return path


def finite_probabilities(values):
    values = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(values)) or np.any((values < 0) | (values > 1)):
        raise ValueError("Probabilidades devem ser finitas e pertencer a [0,1].")
    return values
