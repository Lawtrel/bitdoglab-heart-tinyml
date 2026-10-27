"""Extrai medidas do build real, sem confundir .uf2/debug/arena com flash/RAM."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pcg.common import sha256, write_json, provenance
from pcg.learning import verify_export

p = argparse.ArgumentParser()
p.add_argument("--run", type=Path, required=True)
p.add_argument("--build", type=Path, required=True)
p.add_argument("--sdk", type=Path, required=True)
p.add_argument("--tflm", type=Path, required=True)
p.add_argument("--board", required=True)
a = p.parse_args()
ex = verify_export(a.run)
elf, binary, uf2 = [a.build / ("pcg_bitdoglab" + suffix) for suffix in (".elf", ".bin", ".uf2")]
for artifact in (elf, binary, uf2):
    if not artifact.is_file():
        raise FileNotFoundError(f"Build incompleto: {artifact}")
size_text = subprocess.check_output(["arm-none-eabi-size", "-B", str(elf)], text=True)
(a.build/"size-output.txt").write_text(size_text, encoding="utf-8")
values = size_text.splitlines()[-1].split()
text, data, bss = map(int, values[:3])
def commit(path):
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
report = {"status": "built_not_deployed", "model_sha256": ex["model_sha256"],
    "model_bytes": ex["model_bytes"], "firmware_flash_image_bytes": binary.stat().st_size,
    "elf_text_bytes": text, "elf_data_bytes": data, "elf_bss_bytes": bss,
    "elf_data_plus_bss_bytes": data+bss, "total_peak_ram_bytes": None,
    "stack_high_water_bytes": None,
    "note": "data+bss ja inclui arena/buffers estaticos; nao some a arena novamente. "
            "Pico de RAM e watermark de pilha exigem instrumentacao adicional no hardware.",
    "board": a.board, "pico_sdk_commit": commit(a.sdk), "pico_tflmicro_commit": commit(a.tflm),
    "compiler": subprocess.check_output(["arm-none-eabi-gcc", "--version"], text=True).splitlines()[0],
    "artifacts": {x.name: sha256(x) for x in (elf, binary, uf2)}, "provenance": provenance()}
write_json(a.build/"resource-report.json", report)
print(json.dumps(report, indent=2))
