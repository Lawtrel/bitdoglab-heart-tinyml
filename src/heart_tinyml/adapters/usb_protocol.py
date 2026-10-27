"""Framing PCG1, sequenciamento, leitura parcial e integridade CRC32."""
import binascii
from enum import IntEnum
import json
import math
import struct
import time
from ..domain.errors import ProtocolError

class Mode(IntEnum):
    HELLO = 0
    INFER = 1
    CAPTURE = 3

class ProtocolClient:
    def __init__(self, port, timeout: float = 20.0, clock=time.monotonic):
        self.port = port
        self.timeout = timeout
        self.clock = clock
        self.sequence = 0

    def read_exact(self, length: int, deadline: float) -> bytes:
        result = bytearray()
        while len(result) < length:
            if self.clock() >= deadline:
                raise ProtocolError("Tempo limite durante a transferência USB.")
            chunk = self.port.read(length - len(result))
            if not chunk:
                raise ProtocolError(f"USB interrompida: {len(result)}/{length} bytes.")
            result.extend(chunk)
        return bytes(result)

    def request(self, mode: Mode, payload: bytes = b""):
        self.sequence += 1
        frame = struct.pack("<4sIBII", b"PCG1", self.sequence, int(mode),
                            len(payload), binascii.crc32(payload) & 0xffffffff) + payload
        if self.port.write(frame) != len(frame):
            raise ProtocolError("Escrita USB incompleta.")
        deadline = self.clock() + self.timeout
        expected = {Mode.HELLO: "hello", Mode.INFER: "result", Mode.CAPTURE: "capture"}[mode]
        while self.clock() < deadline:
            line = self.port.readline(8192)
            if not line:
                continue
            try:
                result = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                continue
            if not isinstance(result, dict) or result.get("seq") != self.sequence:
                continue
            if result.get("type") == "error":
                raise ProtocolError("Placa: " + str(result.get("reason", "erro")))
            if result.get("type") != expected:
                raise ProtocolError("Tipo de resposta USB incompatível.")
            if mode == Mode.CAPTURE:
                if result.get("bytes") != 24000:
                    raise ProtocolError("Comprimento da captura incompatível.")
                raw = self.read_exact(24000, deadline)
                if binascii.crc32(raw) & 0xffffffff != result.get("crc32"):
                    raise ProtocolError("O CRC da captura não confere.")
                return result, raw
            return result
        raise ProtocolError("A placa não respondeu. Grave o firmware demo e feche monitores seriais.")

def validate_inference(result: dict) -> dict:
    try:
        values = [float(result[key]) for key in
                  ("prob_present", "preprocessing_us", "inference_us", "processing_us")]
        if not all(math.isfinite(v) for v in values) or not 0 <= values[0] <= 1 or min(values[1:]) < 0:
            raise ValueError
        if abs(values[1] + values[2] - values[3]) > 2:
            raise ValueError
    except (KeyError, TypeError, ValueError) as error:
        raise ProtocolError("Escores ou tempos inválidos na resposta da placa.") from error
    return result
