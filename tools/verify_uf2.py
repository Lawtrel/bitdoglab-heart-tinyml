"""Verifica a imagem UF2 RP2040 e o modelo congelado, sem abrir hardware."""
from pathlib import Path
import argparse
import hashlib
import json
import struct

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "src/heart_tinyml/resources/model/model_int8.tflite"
MODEL_SHA = "3b7e258e26ca124d9e973ba8b4ac5744c87c3ed1d41f501192d2ca7a0b185454"

def verify(path: Path) -> dict:
    raw = path.read_bytes()
    if not raw or len(raw) % 512:
        raise ValueError("UF2 vazio ou com tamanho inválido")
    model = MODEL.read_bytes()
    if hashlib.sha256(model).hexdigest() != MODEL_SHA:
        raise ValueError("Modelo do repositório alterado")
    blocks = {}
    for offset in range(0, len(raw), 512):
        block = raw[offset:offset + 512]
        first, second, flags, address, length, index, total, family = struct.unpack_from("<8I", block)
        if (first, second, struct.unpack_from("<I", block, 508)[0]) != (0x0A324655, 0x9E5D5157, 0x0AB16F30):
            raise ValueError("Assinatura UF2 inválida")
        if flags != 0x2000 or family != 0xE48BFF56 or length != 256:
            raise ValueError("Esperada imagem UF2 RP2040")
        if total != len(raw) // 512 or index in blocks or address != 0x10000000 + index * 256:
            raise ValueError("Blocos ausentes, duplicados ou endereços inesperados")
        blocks[index] = block[32:32 + length]
    if sorted(blocks) != list(range(len(blocks))):
        raise ValueError("Sequência de blocos incompleta")
    image = b"".join(blocks[index] for index in range(len(blocks)))
    if image.count(model) != 1:
        raise ValueError("Modelo congelado ausente ou duplicado no firmware")
    return {"status": "uf2_verified_not_runtime_tested", "uf2_sha256": hashlib.sha256(raw).hexdigest(),
            "model_sha256": MODEL_SHA, "blocks": len(blocks), "family": "RP2040"}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("uf2", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.uf2), indent=2))

if __name__ == "__main__":
    main()
