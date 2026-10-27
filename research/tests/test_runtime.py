"""A exigencia de GPU nao pode cair silenciosamente para CPU."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from pcg.runtime import configure, gpu_check


def fake_tf(gpus):
    config = Mock()
    config.list_physical_devices.return_value = gpus
    config.experimental.get_device_details.return_value = {"device_name": "test GPU"}
    return SimpleNamespace(config=config, __version__="test",
                           sysconfig=SimpleNamespace(get_build_info=lambda: {}))


class RuntimeTests(unittest.TestCase):
    def test_gpu_required_fails_without_device(self):
        tf = fake_tf([])
        with self.assertRaisesRegex(RuntimeError, "Treino cancelado"):
            configure(tf, "gpu")
        tf.config.experimental.set_memory_growth.assert_not_called()

    def test_cpu_explicit_hides_available_gpu(self):
        tf = fake_tf([SimpleNamespace(name="GPU:0")])
        self.assertEqual(configure(tf, "cpu")["selected"], "/CPU:0")
        tf.config.set_visible_devices.assert_called_once_with([], "GPU")
        tf.config.experimental.set_memory_growth.assert_not_called()

    def test_gpu_failure_is_saved_and_not_swallowed(self):
        with patch("pcg.learning.tensorflow", side_effect=RuntimeError("missing kernel")), \
             patch("pcg.runtime.write_json") as save:
            with self.assertRaisesRegex(RuntimeError, "missing kernel"):
                gpu_check("unused.json")
            report = save.call_args.args[1]
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["error"], "missing kernel")
