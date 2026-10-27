"""Regressao: comparar congelamento na CPU sem afrouxar a tolerancia."""
from contextlib import contextmanager
from types import SimpleNamespace
from pathlib import Path
import tempfile
import unittest
import numpy as np
from pcg.common import ROOT, read_json
from pcg.learning import check_frozen_predictions


class PrecisionTests(unittest.TestCase):
    def environment(self, difference=0.0, device="CPU:0"):
        state = {"active": False, "calls": 0}

        @contextmanager
        def scope(selected):
            self.assertEqual(selected, "/CPU:0")
            state["active"] = True
            try:
                yield
            finally:
                state["active"] = False

        class Tensor:
            def __init__(self, value, placement="CPU:0"):
                self.value, self.device = np.array(value, np.float32), placement
            def numpy(self):
                return self.value

        def model(inputs, training):
            self.assertTrue(state["active"])
            self.assertFalse(training)
            state["calls"] += 1
            return Tensor([[0.899053, 0.100947]])

        def frozen(inputs):
            self.assertTrue(state["active"])
            state["calls"] += 1
            return [Tensor([[0.899053 + difference, 0.100947 - difference]], device)]

        tf = SimpleNamespace(device=scope, float32=np.float32,
            constant=lambda x, dtype: Tensor(x),
            nest=SimpleNamespace(flatten=lambda x: x),
            config=SimpleNamespace(experimental=SimpleNamespace(
                tensor_float_32_execution_enabled=lambda: False)))
        return tf, model, frozen, state

    def run_check(self, difference=0.0, device="CPU:0"):
        base = ROOT/"work"/"precision-tests"
        base.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name)/"precision.json"
        tf, model, frozen, state = self.environment(difference, device)
        return output, tf, model, frozen, state

    def test_reference_and_frozen_both_called_on_cpu(self):
        output, tf, model, frozen, state = self.run_check()
        report = check_frozen_predictions(tf, model, frozen, np.zeros((1,2), np.float32), [0], output)
        self.assertEqual(state["calls"], 2)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["rtol"], 1e-5)
        self.assertEqual(report["atol"], 1e-5)

    def test_genuine_drift_still_fails_with_diagnostic(self):
        output, tf, model, frozen, _ = self.run_check(5.06e-5)
        with self.assertRaises(AssertionError):
            check_frozen_predictions(tf, model, frozen, np.zeros((1,2), np.float32), [0], output)
        report = read_json(output)
        self.assertEqual(report["status"], "failed")
        self.assertGreater(report["max_abs_error"], 5e-5)
        self.assertEqual(report["rtol"], 1e-5)

    def test_wrong_device_is_not_accepted(self):
        output, tf, model, frozen, _ = self.run_check(device="GPU:0")
        with self.assertRaisesRegex(RuntimeError, "fora da CPU"):
            check_frozen_predictions(tf, model, frozen, np.zeros((1,2), np.float32), [0], output)
        self.assertEqual(read_json(output)["status"], "failed")
