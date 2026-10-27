"""Casos de uso. Sem detalhes de HTTP, interpretador ou porta serial."""
import base64
from datetime import datetime, timezone
from ..domain.errors import BoardError
from ..domain.models import InferenceOutput
from ..domain.ports import AudioDecoder, BoardGateway, Predictor

class AnalysisService:
    def __init__(self, predictor: Predictor, decoder: AudioDecoder, board: BoardGateway):
        self.predictor = predictor
        self.decoder = decoder
        self.board = board

    @staticmethod
    def present(result: InferenceOutput) -> dict:
        return {
            "score": result.score, "threshold": result.threshold,
            "prediction": "COM SOPRO" if result.label == "Present" else "SEM SOPRO",
            "preprocessing_ms": result.preprocessing_ms,
            "inference_ms": result.inference_ms, "processing_ms": result.processing_ms,
            "waveform": result.waveform.round(6).tolist(), "mfe": result.mfe.round(5).tolist(),
            "pcm_sha256": result.pcm_sha256, "model_sha256": result.model_sha256,
            "scope": "Janela de demonstração. Não é diagnóstico nem métrica por paciente.",
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }

    def analyze(self, blob: bytes, start: float = 0.0, compare: bool = False, port: str = "auto") -> dict:
        audio = self.decoder.decode(blob, start)
        response = self.present(self.predictor.predict(audio))
        response["audio"] = base64.b64encode(self.decoder.encode(audio)).decode()
        response["input"] = audio.metadata
        if compare:
            try:
                response["board"] = self.board.infer(audio, port)
            except BoardError as error:
                # Preserva o resultado real do PC quando somente a USB falha.
                response["board_error"] = str(error)
        return response

    def capture(self, port: str = "auto") -> dict:
        capture = self.board.capture(port)
        response = {
            "capture": {**capture.metadata, "quality_ok": capture.quality_ok, "reason": capture.reason},
            "audio": base64.b64encode(self.decoder.encode(capture.audio)).decode(),
            "input": capture.audio.metadata,
        }
        if capture.quality_ok:
            response.update(self.present(self.predictor.predict(capture.audio)))
            response["board"] = capture.result
        return response
