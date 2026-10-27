import io
import json
import shutil
import tempfile
import unittest
import wave
import numpy as np
from heart_tinyml.config import AppConfig
from heart_tinyml.adapters.audio import WavDecoder
from heart_tinyml.adapters.inference import LiteRTPredictor
from heart_tinyml.adapters.repositories import FrozenModelRepository, EvidenceRepository
from heart_tinyml.domain.errors import InputError, IntegrityError

class ModelAndAudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = AppConfig.default().assets
        cls.decoder = WavDecoder()
        cls.predictor = LiteRTPredictor(FrozenModelRepository(cls.assets).load())

    def test_frozen_examples_keep_their_original_scores(self):
        for sample, score in ((1, 0.56640625), (2, 0.8984375)):
            with self.subTest(sample=sample):
                blob = (self.assets / "audio" / f"exemplo-{sample}.wav").read_bytes()
                audio = self.decoder.decode(blob)
                result = self.predictor.predict(audio)
                self.assertEqual(result.score, score)
                self.assertEqual(result.mfe.shape, (24, 186))
                self.assertEqual(result.waveform.shape, (600,))
                self.assertEqual(self.decoder.decode(self.decoder.encode(audio)).pcm.tobytes(), audio.pcm.tobytes())

    def test_invalid_wav_and_invalid_offsets_are_rejected(self):
        blob = (self.assets / "audio/exemplo-1.wav").read_bytes()
        for value in (-1, float("nan"), float("inf"), 900):
            with self.subTest(offset=value), self.assertRaises(InputError):
                self.decoder.decode(blob, value)
        with self.assertRaises(InputError):
            self.decoder.decode(b"not a WAV")

    def test_short_audio_is_padded_explicitly(self):
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(4000)
            target.writeframes(np.ones(100, dtype="<i2").tobytes())
        result = self.decoder.decode(buffer.getvalue())
        self.assertTrue(result.metadata["padded"])
        np.testing.assert_array_equal(result.pcm[:100], 1)
        np.testing.assert_array_equal(result.pcm[100:], 0)

    def test_resampling_suppresses_out_of_band_aliasing(self):
        levels = []
        for frequency in (500, 5000):
            signal = (np.sin(2 * np.pi * frequency * np.arange(132300) / 44100) * 12000).astype("<i2")
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as target:
                target.setnchannels(1)
                target.setsampwidth(2)
                target.setframerate(44100)
                target.writeframes(signal.tobytes())
            audio = self.decoder.decode(buffer.getvalue())
            self.assertTrue(audio.metadata["converted"])
            levels.append(float(np.std(audio.pcm[200:-200])))
        self.assertGreater(levels[0], 8000)
        self.assertLess(levels[1], 10)

    def test_tampered_model_normalization_and_threshold_fail_closed(self):
        for target in ("model_int8.tflite", "normalization.json", "manifest.json"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                folder = __import__("pathlib").Path(tmp)
                shutil.copytree(self.assets / "model", folder / "model")
                path = folder / "model" / target
                if target == "manifest.json":
                    content = json.loads(path.read_text())
                    content["threshold"] = 0.5
                    path.write_text(json.dumps(content))
                else:
                    path.write_bytes(path.read_bytes() + b"changed")
                with self.assertRaises(IntegrityError):
                    FrozenModelRepository(folder).load()

    def test_six_catalogued_examples_are_intact_and_reproducible(self):
        evidence = EvidenceRepository(self.assets)
        catalog = evidence.catalog()
        self.assertEqual(len(catalog["examples"]), 6)
        self.assertEqual({item["split"] for item in catalog["examples"]}, {"validation"})
        self.assertEqual(len({item["patient_group"] for item in catalog["examples"]}), 6)
        for item in catalog["examples"]:
            raw = evidence.sample(item["number"])
            output = self.predictor.predict(self.decoder.decode(raw))
            self.assertEqual(output.score, item["reference_score"])
        with self.assertRaises(FileNotFoundError):
            evidence.sample(99)
