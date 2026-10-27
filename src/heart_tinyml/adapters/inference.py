"""Adapter para LiteRT: a aplicação depende do contrato Predictor."""
import hashlib
import threading
import time
import numpy as np
from ..domain.models import AudioWindow, InferenceOutput
from ..domain.errors import InputError, IntegrityError
from ..signal import coefficients, extract, quantize
from .repositories import ModelBundle

class LiteRTPredictor:
    def __init__(self, bundle: ModelBundle):
        from ai_edge_litert.interpreter import Interpreter, OpResolverType
        self.bundle = bundle
        self.config = bundle.manifest["frontend"]
        self.coefficients = coefficients(self.config)
        self.runtime = Interpreter(model_path=str(bundle.path), num_threads=1,
            experimental_op_resolver_type=OpResolverType.BUILTIN_REF)
        self.runtime.allocate_tensors()
        self.input = self.runtime.get_input_details()[0]
        self.output = self.runtime.get_output_details()[0]
        if tuple(self.input["shape"]) != (1, 186, 24, 1) or self.input["dtype"] != np.int8:
            raise IntegrityError("Entrada do modelo incompatível.")
        self.lock = threading.Lock()
        self.predict(AudioWindow(np.zeros(12000, dtype=np.int16)))

    def predict(self, audio: AudioWindow) -> InferenceOutput:
        pcm = audio.pcm
        if pcm.shape != (12000,) or pcm.dtype != np.int16:
            raise InputError("O áudio precisa ter 12000 amostras PCM16.")
        with self.lock:
            begin = time.perf_counter_ns()
            mfe = extract(pcm.astype(np.float32) / 32768, self.config, self.coefficients)
            normalized = ((mfe - self.bundle.mean) / self.bundle.std)[..., None]
            scale, zero = self.input["quantization"]
            features = quantize(normalized, scale, zero)
            prepared = time.perf_counter_ns()
            self.runtime.set_tensor(self.input["index"], features[None])
            invoke = time.perf_counter_ns()
            self.runtime.invoke()
            finished = time.perf_counter_ns()
            scale, zero = self.output["quantization"]
            score = float((int(self.runtime.get_tensor(self.output["index"])[0, 1]) - zero) * scale)
        return InferenceOutput(
            score=score, threshold=self.bundle.manifest["threshold"],
            preprocessing_ms=(prepared - begin) / 1e6,
            inference_ms=(finished - invoke) / 1e6,
            waveform=(pcm.astype(float) / 32768).reshape(600, 20).mean(axis=1),
            mfe=mfe.T, pcm_sha256=hashlib.sha256(pcm.astype("<i2").tobytes()).hexdigest(),
            model_sha256=self.bundle.manifest["model_sha256"],
        )
