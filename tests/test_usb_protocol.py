import binascii
import io
import json
import struct
import unittest
from heart_tinyml.adapters.usb_protocol import Mode, ProtocolClient, validate_inference
from heart_tinyml.domain.errors import ProtocolError

class FakePort:
    def __init__(self, raw=b"", bad_crc=False):
        self.raw = raw
        self.buffer = io.BytesIO(raw)
        self.bad_crc = bad_crc
        self.sequence = None
        self.packet = None

    def write(self, frame):
        self.packet = frame
        self.sequence = struct.unpack_from("<I", frame, 4)[0]
        return len(frame)

    def readline(self, maximum=8192):
        response = {"type": "capture", "seq": self.sequence, "bytes": len(self.raw),
                    "crc32": (binascii.crc32(self.raw) & 0xffffffff) ^ int(self.bad_crc)}
        return json.dumps(response).encode() + b"\n"

    def read(self, amount):
        return self.buffer.read(min(amount, 997))

class ProtocolTests(unittest.TestCase):
    def test_partial_usb_reads_are_reassembled_and_crc_checked(self):
        raw = bytes(range(240)) * 100
        port = FakePort(raw)
        metadata, observed = ProtocolClient(port).request(Mode.CAPTURE)
        self.assertEqual(observed, raw)
        magic, sequence, mode, length, crc = struct.unpack("<4sIBII", port.packet)
        self.assertEqual((magic, sequence, mode, length, crc), (b"PCG1", 1, 3, 0, 0))

    def test_corrupt_and_truncated_captures_are_rejected(self):
        with self.assertRaises(ProtocolError):
            ProtocolClient(FakePort(b"0" * 24000, bad_crc=True)).request(Mode.CAPTURE)
        port = FakePort(b"0" * 24000)
        port.buffer = io.BytesIO(b"0" * 1000)
        with self.assertRaises(ProtocolError):
            ProtocolClient(port).request(Mode.CAPTURE)

    def test_invalid_result_values_cannot_become_measurements(self):
        valid = dict(prob_present=0.5, preprocessing_us=100, inference_us=20, processing_us=120)
        self.assertEqual(validate_inference(valid), valid)
        for patch in ({"prob_present": float("nan")}, {"prob_present": 2},
                      {"inference_us": -1}, {"processing_us": 999}):
            with self.subTest(patch=patch), self.assertRaises(ProtocolError):
                validate_inference(valid | patch)
