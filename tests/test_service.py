import unittest
from unittest.mock import Mock
import numpy as np
from heart_tinyml.application.service import AnalysisService
from heart_tinyml.domain.models import AudioWindow, InferenceOutput, BoardCapture
from heart_tinyml.domain.errors import BoardError

def prediction():
    return InferenceOutput(0.8, 0.7346754807692307, 1.0, 2.0,
                           np.zeros(600), np.zeros((24, 186)), "pcm", "model")

class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.audio = AudioWindow(np.zeros(12000, np.int16), {"converted": False})
        self.predictor = Mock()
        self.predictor.predict.return_value = prediction()
        self.decoder = Mock()
        self.decoder.decode.return_value = self.audio
        self.decoder.encode.return_value = b"WAV"
        self.board = Mock()
        self.service = AnalysisService(self.predictor, self.decoder, self.board)

    def test_pc_only_never_opens_the_device(self):
        result = self.service.analyze(b"input")
        self.assertEqual(result["prediction"], "COM SOPRO")
        self.assertEqual(result["processing_ms"], 3)
        self.board.infer.assert_not_called()

    def test_comparison_uses_exactly_the_decoded_window(self):
        self.board.infer.return_value = {"prob_present": 0.8}
        result = self.service.analyze(b"input", compare=True)
        self.board.infer.assert_called_once_with(self.audio, "auto")
        self.assertIn("board", result)

    def test_board_failure_keeps_the_real_pc_result(self):
        self.board.infer.side_effect = BoardError("disconnected")
        result = self.service.analyze(b"input", compare=True)
        self.assertEqual(result["score"], 0.8)
        self.assertEqual(result["board_error"], "disconnected")
        self.assertNotIn("board", result)

    def test_rejected_capture_never_runs_classifier(self):
        self.board.capture.return_value = BoardCapture(self.audio, False, "saturado", {}, None)
        result = self.service.capture()
        self.predictor.predict.assert_not_called()
        self.assertNotIn("score", result)
        self.assertFalse(result["capture"]["quality_ok"])
