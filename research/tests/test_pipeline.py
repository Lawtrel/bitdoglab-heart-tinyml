import binascii
import importlib.util
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
import wave
import numpy as np
from pcg.common import config, read_json, write_json
from pcg.data import inventory, make_split, audit_disjoint
from pcg.features import extract, coefficients, windows, prepare, quantize
from pcg.learning import sample_weights, load_prepared
from pcg.metrics import aggregate, binary_metrics, select_threshold, bootstrap, write_report
from pcg.board import packet, transact


def temp_workspace():
    base = Path(os.environ.get("PCG_TEST_TMP", Path(__file__).resolve().parents[1]/"work"/"tests"))
    base.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.TemporaryDirectory(dir=base, prefix="pcg-test-")
    assert Path(temporary.name).resolve().is_relative_to(base.resolve())
    return temporary


def fixture(root):
    """Dados artificiais APENAS para testes de software; nunca resultados do artigo."""
    root.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(3)
    def subject(identifier, label, additional=None, tone=150):
        header = (f"{identifier} 1 4000\nAV {identifier}_AV.hea {identifier}_AV.wav {identifier}_AV.tsv\n"
                  f"#Murmur: {label}\n#Outcome: Abnormal\n#Additional ID: {additional or 'nan'}\n")
        (root/f"{identifier}.txt").write_text(header, encoding="utf-8")
        t = np.arange(12000) / 4000
        audio = 0.1*np.sin(2*np.pi*t*tone) + rng.normal(0, .01, len(t))
        pcm = np.clip(np.rint(audio*32768), -32768, 32767).astype("<i2")
        with wave.open(str(root/f"{identifier}_AV.wav"), "wb") as f:
            f.setnchannels(1); f.setsampwidth(2); f.setframerate(4000)
            f.writeframes(pcm.tobytes())
    for i in range(16):
        subject(str(100+i), "Present" if i >= 8 else "Absent", tone=150+10*i)
    subject("200", "Absent", additional="100")
    subject("300", "Unknown")
    return subject


class SoftwareTests(unittest.TestCase):
    def test_realistic_inventory_linkage_unknown_and_split(self):
        with temp_workspace() as tmp:
            root = Path(tmp)
            fixture(root/"data")
            inventory(root/"data", root/"inventory.json")
            inv = read_json(root/"inventory.json")
            self.assertEqual(len(inv["recordings"]), 17)
            self.assertEqual({r["label"] for r in inv["recordings"]}, {0,1})
            linked = [r for r in inv["recordings"] if r["encounter_id"] in ("100","200")]
            self.assertEqual(len({r["patient_id"] for r in linked}), 1)
            self.assertTrue(any(e["reason"] == "unknown_or_missing_murmur" for e in inv["excluded"]))
            make_split(root/"inventory.json", root/"split-a", config())
            make_split(root/"inventory.json", root/"split-b", config())
            a = read_json(root/"split-a"/"manifest.json")
            b = read_json(root/"split-b"/"manifest.json")
            self.assertEqual(a["assignment"], b["assignment"])
            audit_disjoint(a["recordings"])
            for split in ("train","validation","test"):
                self.assertEqual({r["label"] for r in a["recordings"] if r["split"] == split}, {0,1})
            prepare(root/"split-a"/"manifest.json", root/"prepared", config())
            info, arrays, meta = load_prepared(root/"prepared")
            self.assertEqual(arrays["x"].shape, (17,186,24,1))
            self.assertEqual(info["normalization_source"], "train_only")
            train_x = arrays["x"][arrays["split"] == "train"]
            np.testing.assert_allclose(train_x.mean(axis=(0,1,3)), 0, atol=1e-5)
            # Alterar um WAV quebra o manifesto e impede preparar novos dados.
            wav = root/"data"/"100_AV.wav"
            wav.write_bytes(wav.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "alterado"):
                prepare(root/"split-a"/"manifest.json", root/"tampered", config())

    def test_duplicates_grouped_and_conflicting_patients_excluded(self):
        with temp_workspace() as tmp:
            root = Path(tmp)
            subject = fixture(root/"data")
            # WAV identico sob outro ID deve unir os grupos, nao vazar.
            (root/"data"/"101_AV.wav").write_bytes((root/"data"/"100_AV.wav").read_bytes())
            subject("500", "Present", additional="102")
            inventory(root/"data", root/"inv.json")
            inv = read_json(root/"inv.json")
            reasons = [r["reason"] for r in inv["excluded"]]
            self.assertIn("exact_duplicate_wav", reasons)
            self.assertIn("conflicting_labels_in_linked_patient", reasons)
            self.assertFalse(any(r["encounter_id"] in ("102","500") for r in inv["recordings"]))

    def test_leakage_fails_for_identical_hash(self):
        rows = [{"patient_id":"a","encounter_id":"1","recording_id":"a","sha256":"same","split":"train"},
                {"patient_id":"b","encounter_id":"2","recording_id":"b","sha256":"same","split":"test"}]
        with self.assertRaisesRegex(ValueError, "sha256"):
            audit_disjoint(rows)

    def test_feature_shape_silence_dc_and_windows(self):
        c = config()
        silence = extract(np.zeros(12000,np.float32), c)
        dc = extract(np.full(12000,.125,np.float32), c)
        self.assertEqual(silence.shape, (186,24))
        self.assertTrue(np.isfinite(silence).all())
        np.testing.assert_allclose(silence, np.log(c["log_floor"]), atol=1e-5)
        np.testing.assert_allclose(silence, dc)
        self.assertEqual(len(list(windows(np.zeros(15000),c))),1)
        self.assertEqual(len(list(windows(np.zeros(18000),c))),2)
        self.assertEqual(len(list(windows(np.zeros(30),c))),1)
        hann, bank = coefficients(c)
        self.assertEqual(hann[0], 0)
        self.assertTrue((bank.sum(axis=1)>0).all())

    def test_normalization_does_not_fit_held_out_values(self):
        # Confere a formula sobre o treino real do fixture, nao so media global.
        with temp_workspace() as tmp:
            root = Path(tmp); fixture(root/"data")
            inventory(root/"data",root/"inv.json")
            make_split(root/"inv.json",root/"split",config())
            manifest = read_json(root/"split"/"manifest.json")
            # Recalcula a estatistica usando apenas as linhas de treino congeladas.
            from pcg.features import load_audio
            expected_train = []
            for row in manifest["recordings"]:
                p = root/"data"/Path(row["path"])
                if row["split"] == "train":
                    expected_train.append(extract(load_audio(p),config()))
            prepare(root/"split"/"manifest.json",root/"prepared",config())
            _, arrays, _ = load_prepared(root/"prepared")
            np.testing.assert_allclose(arrays["mean"],np.stack(expected_train).mean(axis=(0,1)),atol=1e-4)
            all_mean = []
            for row in manifest["recordings"]:
                all_mean.append(extract(load_audio(root/"data"/row["path"]),config()))
            self.assertGreater(float(np.max(np.abs(arrays["mean"]-np.stack(all_mean).mean(axis=(0,1))))),1e-5)

    def test_patient_weights_balance_windows_and_classes(self):
        rows = [{"patient_id":"a","label":0}]*10+[{"patient_id":"b","label":0}]+[{"patient_id":"c","label":1}]*4
        w = sample_weights(rows)
        self.assertAlmostEqual(float(w[:10].sum()),float(w[10]),places=5)
        self.assertAlmostEqual(float(w[:11].sum()),float(w[11:].sum()),places=5)

    def test_aggregation_recording_mean_then_patient_max(self):
        meta = [{"patient_id":"a","recording_id":"r1","label":1}]*3 + [
            {"patient_id":"a","recording_id":"r2","label":1},
            {"patient_id":"b","recording_id":"r3","label":0}]
        ids,y,p = aggregate([0,0,0,.8,.1],meta)
        self.assertEqual(ids,["a","b"])
        np.testing.assert_allclose(p,[.8,.1])
        np.testing.assert_array_equal(y,[1,0])

    def test_metrics_confusion_undefined_and_serializable(self):
        m = binary_metrics([0,0,1,1],[.1,.9,.8,.7],.75)
        self.assertEqual([m[k] for k in ("tp","tn","fp","fn")],[1,1,1,1])
        self.assertEqual(m["f1"],.5)
        n = binary_metrics([0,1],[0,0],.5)
        self.assertIsNone(n["precision"])
        self.assertEqual(n["f1"],0)
        with self.assertRaises(ValueError):
            binary_metrics([0,.5],[.1,.2],.5)
        with self.assertRaises(ValueError):
            binary_metrics([0,1],[np.nan,.2],.5)
        json.dumps(n,allow_nan=False)

    def test_threshold_selection_and_bootstrap(self):
        y,p = np.array([0,0,1,1]),np.array([.1,.4,.6,.8])
        selected = select_threshold(y,p)
        self.assertEqual(selected["f1"],1)
        self.assertAlmostEqual(selected["threshold"],.6)
        a = bootstrap(y,p,.6,replicates=30,seed=42)
        self.assertEqual(a,bootstrap(y,p,.6,replicates=30,seed=42))
        with temp_workspace() as tmp:
            write_report(Path(tmp),"test_only",list("abcd"),y,p,.6,
                         config() | {"bootstrap_replicates":30})
            self.assertTrue((Path(tmp)/"test_only_confusion.svg").exists())

    def test_quantization_rounding_and_saturation(self):
        np.testing.assert_array_equal(quantize(np.array([-100,-.1875,-.0625,.0625,.1875,100]),.125,0),
                                      [-128,-2,-1,1,2,127])

    def test_usb_framing_and_binary_crc(self):
        payload = b"\x00\n\xffP"
        frame = packet(7,1,payload)
        magic,seq,mode,length,crc = struct.unpack("<4sIBII",frame[:17])
        self.assertEqual((magic,seq,mode,length),(b"PCG1",7,1,4))
        self.assertEqual(crc,binascii.crc32(payload)&0xffffffff)
        class FakeSerial:
            def __init__(self, raw):
                self.raw=raw
            def write(self, data):
                self.sent=data
            def flush(self):
                pass
            def readline(self):
                head, self.raw=self.raw.split(b"\n",1)
                return head+b"\n"
            def read(self,n):
                chunk,self.raw=self.raw[:n],self.raw[n:]
                return chunk
        raw=np.zeros(4464,np.int8).tobytes()
        header=json.dumps({"type":"features","seq":1,"bytes":len(raw),"crc32":binascii.crc32(raw)}).encode()+b"\n"
        response,features=transact(FakeSerial(header+raw),1,2,payload)
        self.assertEqual(features.shape,(4464,))


@unittest.skipUnless(os.environ.get("PCG_RUN_TF_TEST") == "1" and importlib.util.find_spec("tensorflow"),
                     "Integracao TensorFlow exige dependencia e PCG_RUN_TF_TEST=1; nao validada sem isso.")
class TensorFlowIntegration(unittest.TestCase):
    def test_tiny_training_export_evaluation(self):
        from pcg.learning import train, export, evaluate
        with temp_workspace() as tmp:
            root=Path(tmp); fixture(root/"SYNTHETIC_TEST_ONLY")
            c=config() | {"training_seeds":[42],"epochs":1,"patience":1,"bootstrap_replicates":20}
            inventory(root/"SYNTHETIC_TEST_ONLY",root/"inventory.json")
            make_split(root/"inventory.json",root/"split",c)
            prepare(root/"split"/"manifest.json",root/"prepared",c)
            train(root/"prepared",root/"model")
            export(root/"model")
            ex = read_json(root/"model"/"export.json")
            self.assertEqual(ex["conversion_source"], "frozen_concrete_function")
            self.assertLessEqual(ex["freezing_max_abs_error"], 2e-5)
            self.assertNotIn("READ_VARIABLE", ex["operators"])
            evaluate(root/"model")
            self.assertEqual(read_json(root/"model"/"evaluation_receipt.json")["status"],"complete")
            self.assertTrue((root/"model"/"generated"/"model_data.cpp").exists())
            with self.assertRaises(FileExistsError):
                evaluate(root/"model")


if __name__ == "__main__":
    unittest.main()
