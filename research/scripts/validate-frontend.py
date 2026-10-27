"""Compila o front-end C++ desktop e compara com NumPy em sinais conhecidos."""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pcg.common import ROOT, config, write_json
from pcg.embedded import write_frontend_header
from pcg.features import extract

p = argparse.ArgumentParser()
p.add_argument("--compiler", default=shutil.which("g++") or shutil.which("clang++"))
p.add_argument("--out", type=Path)
a = p.parse_args()
if not a.compiler:
    p.exit(2, "Compilador C++ desktop ausente. Esta verificacao NAO foi executada.\n")
c = config()
report = {"test_only_synthetic_signals": True, "compiler": a.compiler, "entries": []}
temp_base = ROOT/"work"/"frontend-validation"
temp_base.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="pcg-frontend-", dir=temp_base) as temp:
    temp = Path(temp)
    write_frontend_header(temp/"frontend_config.h", np.zeros(24), np.ones(24), c)
    exe = temp/("frontend.exe" if sys.platform == "win32" else "frontend")
    subprocess.run([a.compiler, "-std=c++17", "-O2", "-I", str(temp), "-I", str(ROOT/"firmware"),
        str(ROOT/"firmware"/"frontend.cpp"), str(ROOT/"firmware"/"frontend_desktop.cpp"),
        "-o", str(exe)], check=True)
    rng = np.random.default_rng(2026)
    t = np.arange(12000)/4000
    signals = {"silence": np.zeros(12000), "dc": np.full(12000, 0.15),
               "noise": rng.normal(0, .1, 12000),
               "tone150_plus_noise": .3*np.sin(2*np.pi*150*t)+rng.normal(0,.01,12000),
               "tone800_plus_noise": .3*np.sin(2*np.pi*800*t)+rng.normal(0,.01,12000)}
    for name, x in signals.items():
        pcm = np.clip(np.rint(x*32768), -32768, 32767).astype("<i2")
        expected = extract(pcm.astype(np.float32)/32768, c)
        result = subprocess.run([str(exe)], input=pcm.tobytes(), capture_output=True, check=True)
        actual = np.frombuffer(result.stdout, dtype="<f4").reshape(186,24)
        maximum = float(np.max(np.abs(expected-actual)))
        report["entries"].append({"signal": name, "max_absolute_log_mfe_error": maximum})
    report["passed"] = all(r["max_absolute_log_mfe_error"] <= 0.005 for r in report["entries"])
if a.out:
    write_json(a.out, report)
print(report)
if not report["passed"]:
    raise SystemExit(1)
