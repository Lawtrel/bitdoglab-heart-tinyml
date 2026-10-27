"""Gravação explícita: valida UF2 e identidade da unidade antes de copiar."""
from pathlib import Path
import argparse
import re
import shutil
from verify_uf2 import verify

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("uf2", type=Path)
    parser.add_argument("--drive", type=Path, required=True, help="Unidade RPI-RP2 em BOOTSEL")
    args = parser.parse_args()
    result = verify(args.uf2)
    drive = args.drive.resolve()
    identity = (drive / "INFO_UF2.TXT").read_text(encoding="utf-8")
    if not re.search(r"^Board-ID:\s*RPI-RP2\s*$", identity, re.MULTILINE):
        parser.error("Unidade não identificada como RP2040. Nada foi gravado.")
    print("Substituindo o programa da placa pelo UF2 verificado…")
    shutil.copyfile(args.uf2, drive / "pcg_bitdoglab.uf2")
    print("UF2 copiado: " + result["uf2_sha256"])
    print("Confirme a execução na placa. A cópia não comprova funcionamento físico.")

if __name__ == "__main__":
    main()
