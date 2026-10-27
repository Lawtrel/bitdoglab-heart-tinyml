"""Selecao de dispositivo e teste real; nao produz resultados cientificos."""
import time
import numpy as np
from .common import write_json, provenance


def configure(tf, requested="auto"):
    if requested not in ("auto", "cpu", "gpu"):
        raise ValueError("Dispositivo deve ser auto, cpu ou gpu.")
    gpus = tf.config.list_physical_devices("GPU")
    if requested == "gpu" and not gpus:
        raise RuntimeError("GPU solicitada, mas TensorFlow nao detectou GPU. Treino cancelado.")
    if requested == "cpu":
        tf.config.set_visible_devices([], "GPU")
    else:
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
    tf.config.experimental.enable_tensor_float_32_execution(False)
    selected = "/GPU:0" if requested != "cpu" and gpus else "/CPU:0"
    return {"requested": requested, "selected": selected,
            "tensorflow": tf.__version__, "build": tf.sysconfig.get_build_info(),
            "physical_gpus": [tf.config.experimental.get_device_details(g) | {"name": g.name}
                              for g in gpus]}


def cnn_probe(tf, device):
    """Executa convolucoes, gradientes e Adam da mesma CNN com dados artificiais."""
    from .learning import build_model
    tf.keras.utils.set_random_seed(42)
    rng = np.random.default_rng(42)
    x = rng.normal(size=(32, 186, 24, 1)).astype(np.float32)
    y = np.arange(32, dtype=np.int32) % 2
    previous = tf.config.get_soft_device_placement()
    try:
        # O teste nao pode mascarar kernels ausentes usando a CPU.
        tf.config.set_soft_device_placement(False)
        with tf.device(device):
            model = build_model(tf)
            optimizer = tf.keras.optimizers.Adam(0.001)
            inputs, labels = tf.constant(x), tf.constant(y)
            durations, losses = [], []
            for step in range(6):
                start = time.perf_counter()
                with tf.GradientTape() as tape:
                    prediction = model(inputs, training=True)
                    loss = tf.reduce_mean(tf.keras.losses.sparse_categorical_crossentropy(labels, prediction))
                gradients = tape.gradient(loss, model.trainable_variables)
                optimizer.apply_gradients(zip(gradients, model.trainable_variables))
                value = float(loss.numpy())  # Sincroniza a GPU antes de medir tempo.
                if not np.isfinite(value):
                    raise RuntimeError("Loss nao finito no teste da CNN.")
                losses.append(value)
                if step:  # Primeira iteracao aquece kernels/alocacoes.
                    durations.append((time.perf_counter() - start) * 1000)
            if device.startswith("/GPU") and "GPU:" not in prediction.device.upper():
                raise RuntimeError("CNN nao executou no dispositivo GPU esperado.")
            return {"prediction_device": prediction.device, "steps": 6, "batch_size": 32,
                    "losses": losses, "median_step_ms": float(np.median(durations)),
                    "timing_scope": "eager CNN forward+backward+Adam; synthetic; warmup excluded"}
    finally:
        tf.config.set_soft_device_placement(previous)


def gpu_check(output):
    from .learning import tensorflow
    report = {"kind": "synthetic_environment_check_not_research_results", "status": "failed"}
    try:
        tf = tensorflow()
        report["runtime"] = configure(tf, "gpu")
        tf.config.experimental.enable_op_determinism()
        report["cnn"] = cnn_probe(tf, "/GPU:0")
        report["status"] = "cnn_gpu_check_passed"
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        report["provenance"] = provenance()
        write_json(output, report)
    print(f"CNN executada na GPU. Relatorio: {output}")
