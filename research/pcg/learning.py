import os
import shutil
from pathlib import Path
from collections import Counter
import numpy as np
from .common import (fresh_directory, read_json, write_json, write_csv, sha256,
                     object_hash, provenance)
from .metrics import aggregate, select_threshold, write_report


def tensorflow():
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    try:
        import tensorflow as tf
    except ImportError as exc:
        raise RuntimeError("TensorFlow nao instalado. Execute scripts/setup.ps1 ou instale requirements.txt.") from exc
    # Cada comando CLI abre um processo: export/evaluate tambem precisam da
    # mesma precisao do treino, onde runtime.configure ja desabilitava TF32.
    tf.config.experimental.enable_tensor_float_32_execution(False)
    return tf


def load_prepared(folder):
    folder = Path(folder)
    info = read_json(folder / "preparation.json")
    path = folder / "features.npz"
    if sha256(path) != info["features_sha256"]:
        raise ValueError("Features alteradas apos a preparacao.")
    metadata = read_json(folder / "windows.json")
    with np.load(path, allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in archive.files}
    if len(metadata) != len(arrays["x"]):
        raise ValueError("Metadados e features nao correspondem.")
    expected = [(r["patient_id"], r["recording_id"], r["label"], r["split"]) for r in metadata]
    actual = list(zip(arrays["patient"].tolist(), arrays["recording"].tolist(),
                      arrays["y"].tolist(), arrays["split"].tolist()))
    if expected != actual:
        raise ValueError("Metadados de janelas alterados.")
    return info, arrays, metadata


def sample_weights(metadata):
    counts = Counter(str(r["patient_id"]) for r in metadata)
    labels = {str(r["patient_id"]): int(r["label"]) for r in metadata}
    class_patients = Counter(labels.values())
    if set(class_patients) != {0, 1}:
        raise ValueError("Treino precisa conter ambas as classes.")
    weights = np.array([1.0 / (class_patients[int(r["label"])] * counts[str(r["patient_id"])])
                        for r in metadata], np.float32)
    return weights / weights.mean()


def build_model(tf):
    return tf.keras.Sequential([
        tf.keras.layers.Input(shape=(186, 24, 1)),
        tf.keras.layers.Conv2D(8, (3, 3), padding="same", activation="relu"),
        tf.keras.layers.MaxPooling2D((2, 2)),
        tf.keras.layers.Conv2D(16, (3, 3), padding="same", activation="relu"),
        tf.keras.layers.MaxPooling2D((2, 2)),
        tf.keras.layers.GlobalAveragePooling2D(),
        tf.keras.layers.Dense(2, activation="softmax")
    ], name="pcg_cnn")


def train(prepared, output, device="auto"):
    tf = tensorflow()
    from .runtime import configure, cnn_probe
    runtime = configure(tf, device)
    tf.config.experimental.enable_op_determinism()
    if runtime["selected"].startswith("/GPU"):
        # Falha antes de abrir o experimento se faltam kernels para esta placa.
        runtime["cnn_probe"] = cnn_probe(tf, runtime["selected"])
    info, data, metadata = load_prepared(prepared)
    c = info["config"]
    out = fresh_directory(output)
    train_ix = np.where(data["split"] == "train")[0]
    val_ix = np.where(data["split"] == "validation")[0]
    train_meta = [metadata[i] for i in train_ix]
    val_meta = [metadata[i] for i in val_ix]
    weights = sample_weights(train_meta)
    if not len(val_ix) or set(data["y"][val_ix].tolist()) != {0, 1}:
        raise ValueError("Validacao precisa conter ambas as classes.")
    records = []
    tf.config.experimental.enable_op_determinism()
    for seed in c["training_seeds"]:
        tf.keras.backend.clear_session()
        tf.keras.utils.set_random_seed(seed)
        with tf.device(runtime["selected"]):
            model = build_model(tf)
            model.compile(optimizer=tf.keras.optimizers.Adam(c["learning_rate"]),
                          loss=tf.keras.losses.SparseCategoricalCrossentropy(), jit_compile=False)
        seed_dir = out / f"seed_{seed}"
        seed_dir.mkdir()

        class PatientValidation(tf.keras.callbacks.Callback):
            def __init__(self):
                super().__init__()
                self.best = -1.0
                self.wait = 0
                self.history = []

            def on_epoch_end(self, epoch, logs=None):
                probabilities = self.model.predict(data["x"][val_ix], batch_size=c["batch_size"], verbose=0)[:, 1]
                _, labels, probs = aggregate(probabilities, val_meta)
                m = select_threshold(labels, probs)
                row = {"epoch": epoch+1, "loss": float((logs or {})["loss"]),
                       "validation_patient_f1": m["f1"], "validation_recall": m["recall"],
                       "threshold": m["threshold"]}
                self.history.append(row)
                if m["f1"] > self.best:
                    self.best, self.wait = m["f1"], 0
                    self.model.save(seed_dir / "best.keras")
                    write_json(seed_dir / "validation_selection.json", m | {"epoch": epoch+1})
                else:
                    self.wait += 1
                print(f"seed={seed} epoch={epoch+1} patient_val_f1={m['f1']:.4f}", flush=True)
                if self.wait >= c["patience"]:
                    self.model.stop_training = True

        callback = PatientValidation()
        with tf.device(runtime["selected"]):
            model.fit(data["x"][train_ix], data["y"][train_ix], sample_weight=weights,
                      batch_size=c["batch_size"], epochs=c["epochs"], shuffle=True,
                      callbacks=[callback], verbose=2)
        write_csv(seed_dir / "history.csv", callback.history)
        selection = read_json(seed_dir / "validation_selection.json")
        records.append(selection | {"seed": seed, "parameters": model.count_params()})
    # Escolha exclusivamente pela validacao; nenhuma predicao de teste aqui.
    selected = max(records, key=lambda r: (r["f1"], r["recall"], -r["seed"]))
    shutil.copyfile(out / f"seed_{selected['seed']}" / "best.keras", out / "float.keras")
    write_json(out / "training.json", {"status": "trained_not_tested", "config": c,
        "prepared_dir": str(Path(prepared).resolve()), "preparation_sha256": sha256(Path(prepared)/"preparation.json"),
        "windows_sha256": sha256(Path(prepared)/"windows.json"), "seeds": records,
        "selected": selected, "float_model_sha256": sha256(out / "float.keras"),
        "runtime": runtime, "provenance": provenance()})
    print(f"Treinamento concluido. Seed escolhida pela validacao: {selected['seed']}")


def check_run(run, prepared=None):
    run = Path(run)
    training = read_json(run / "training.json")
    if sha256(run / "float.keras") != training["float_model_sha256"]:
        raise ValueError("Modelo floating-point alterado.")
    prepared = Path(prepared or training["prepared_dir"])
    for name, key in (("preparation.json", "preparation_sha256"), ("windows.json", "windows_sha256")):
        if sha256(prepared / name) != training[key]:
            raise ValueError(f"{name} mudou depois do treino.")
    info, data, metadata = load_prepared(prepared)
    return training, info, data, metadata


def lite_interpreter(tf, path):
    interpreter = tf.lite.Interpreter(model_path=str(path), num_threads=1)
    interpreter.allocate_tensors()
    return interpreter


def lite_probabilities(interpreter, features):
    from .features import quantize
    inp = interpreter.get_input_details()[0]
    out = interpreter.get_output_details()[0]
    scale, zero = inp["quantization"]
    out_scale, out_zero = out["quantization"]
    result = []
    for x in features:
        interpreter.set_tensor(inp["index"], quantize(x[None], scale, zero))
        interpreter.invoke()
        value = (interpreter.get_tensor(out["index"])[0, 1].item() - out_zero) * out_scale
        result.append(value)
    return np.asarray(result)


def freeze_inference(tf, model):
    # API interna do proprio TensorFlow, usada tambem pelo conversor: versao fixada
    # nos requirements. Remove ReadVariableOp/VarHandleOp antes da calibracao INT8.
    from tensorflow.python.framework.convert_to_constants import convert_variables_to_constants_v2

    @tf.function(input_signature=[tf.TensorSpec([1, 186, 24, 1], tf.float32, name="features")])
    def inference(features):
        return model(features, training=False)

    with tf.device("/CPU:0"):
        frozen = convert_variables_to_constants_v2(inference.get_concrete_function())
    graph = frozen.graph.as_graph_def()
    nodes = list(graph.node)
    for function in graph.library.function:
        nodes.extend(function.node_def)
    resources = [n.name for n in nodes if n.op in ("ReadVariableOp", "VarHandleOp", "AssignVariableOp")]
    if resources or any(t.dtype == tf.resource for t in frozen.inputs):
        raise ValueError(f"Grafo de inferencia ainda contem variaveis: {resources}")
    return frozen



def check_frozen_predictions(tf, model, frozen, features, indices, output):
    """Compara apenas amostras de treino, no mesmo dispositivo e em float32."""
    check = {"status": "started", "partition": "train", "device": "/CPU:0",
             "rtol": 1e-5, "atol": 1e-5,
             "tf32_enabled": bool(tf.config.experimental.tensor_float_32_execution_enabled()),
             "samples": [], "max_abs_error": 0.0}
    try:
        for index in list(indices)[:8]:
            with tf.device("/CPU:0"):
                inputs = tf.constant(features[index:index+1], dtype=tf.float32)
                expected_tensor = model(inputs, training=False)
                actual_tensor = tf.nest.flatten(frozen(inputs))[0]
                expected, actual = expected_tensor.numpy(), actual_tensor.numpy()
            devices = {"reference_device": expected_tensor.device,
                       "frozen_device": actual_tensor.device}
            if any("CPU:" not in value.upper() for value in devices.values()):
                raise RuntimeError(f"Comparacao de congelamento fora da CPU: {devices}")
            error = float(np.max(np.abs(actual - expected)))
            check["samples"].append({"index": int(index), "max_abs_error": error, **devices})
            check["max_abs_error"] = max(check["max_abs_error"], error)
            np.testing.assert_allclose(actual, expected, rtol=check["rtol"], atol=check["atol"],
                                       err_msg="Congelamento alterou previsoes mesmo em CPU/float32.")
        check["status"] = "passed"
    except Exception as exc:
        check["status"] = "failed"
        check["error"] = str(exc)
        raise
    finally:
        write_json(output, check)
    return check


def export(run, prepared=None):
    from .embedded import write_generated
    tf = tensorflow()
    run = Path(run)
    if (run / "evaluation_receipt.json").exists():
        raise ValueError("Teste ja aberto. Nao altere exportacao/limiares; crie outro experimento declarado.")
    if (run / "export.json").exists():
        raise FileExistsError("Exportacao ja congelada. Use outro run para revisar o experimento.")
    training, info, data, metadata = check_run(run, prepared)
    c = info["config"]
    with tf.device("/CPU:0"):
        model = tf.keras.models.load_model(run / "float.keras", compile=False)
        frozen = freeze_inference(tf, model)
    shape = [1, 186, 24, 1]
    # Assinatura fixa e pesos constantes: nenhuma variavel de recurso no RP2040.
    (run / "inference_frozen.pb").write_bytes(frozen.graph.as_graph_def().SerializeToString())
    train_ix = np.where(data["split"] == "train")[0]
    rng = np.random.default_rng(c["split_seed"])
    calibration = rng.choice(train_ix, size=min(c["calibration_windows"], len(train_ix)), replace=False)
    freezing_check = check_frozen_predictions(
        tf, model, frozen, data["x"], calibration, run / "freezing_check.json")
    max_freezing_error = freezing_check["max_abs_error"]
    # Entrada ja congelada: evita preservar recursos do SavedModel na calibracao.
    converter = tf.lite.TFLiteConverter.from_concrete_functions([frozen])
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = lambda: ([data["x"][i:i+1]] for i in calibration)
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8
    (run / "model_int8.tflite").write_bytes(converter.convert())
    interpreter = lite_interpreter(tf, run / "model_int8.tflite")
    inp, out = interpreter.get_input_details()[0], interpreter.get_output_details()[0]
    if inp["dtype"] != np.int8 or out["dtype"] != np.int8 or inp["shape"].tolist() != shape:
        raise ValueError("Conversao nao gerou entrada/saida INT8 no formato esperado.")
    tensors = interpreter.get_tensor_details()
    floating = [d["name"] for d in tensors if np.issubdtype(d["dtype"], np.floating)]
    if floating:
        raise ValueError(f"Tensores floating-point no modelo quantizado: {floating}")
    # API diagnostica do Interpreter: lista exata dos operadores convertidos.
    ops = sorted({v["op_name"] for v in interpreter._get_ops_details()} - {"DELEGATE"})
    supported = {"CONV_2D", "MAX_POOL_2D", "MEAN", "FULLY_CONNECTED", "SOFTMAX", "RESHAPE"}
    if not set(ops) <= supported:
        raise ValueError(f"Operadores nao cobertos pelo resolver do firmware: {set(ops)-supported}")
    val_ix = np.where(data["split"] == "validation")[0]
    val_meta = [metadata[i] for i in val_ix]
    ids, y, p = aggregate(lite_probabilities(interpreter, data["x"][val_ix]), val_meta)
    selected = select_threshold(y, p)
    export_info = {"status": "int8_exported_not_deployed", "model_sha256": sha256(run/"model_int8.tflite"),
        "conversion_source": "frozen_concrete_function", "freezing_max_abs_error": max_freezing_error,
        "freezing_comparison_device": "/CPU:0", "tf32_enabled": False,
        "freezing_check_sha256": sha256(run/"freezing_check.json"),
        "frozen_graph_sha256": sha256(run/"inference_frozen.pb"),
        "model_bytes": (run/"model_int8.tflite").stat().st_size, "operators": ops,
        "input_scale": float(inp["quantization"][0]), "input_zero_point": int(inp["quantization"][1]),
        "output_scale": float(out["quantization"][0]), "output_zero_point": int(out["quantization"][1]),
        "threshold": selected["threshold"], "validation_patient_metrics": selected,
        "calibration_indices": calibration.tolist(), "calibration_partition": "train",
        "float_threshold": training["selected"]["threshold"], "config_hash": object_hash(c),
        "training_sha256": sha256(run/"training.json"), "provenance": provenance()}
    write_generated(run / "generated", run/"model_int8.tflite", export_info, data["mean"], data["std"], c)
    export_info["generated_hashes"] = {p.name: sha256(p) for p in (run/"generated").glob("*") if p.is_file()}
    write_json(run / "export.json", export_info)
    print(f"Modelo INT8: {export_info['model_bytes']} bytes; operadores {ops}. Nao executado no RP2040.")


def verify_export(run):
    run = Path(run)
    ex = read_json(run / "export.json")
    if sha256(run/"model_int8.tflite") != ex["model_sha256"]:
        raise ValueError("Modelo INT8 alterado depois da selecao.")
    if sha256(run/"training.json") != ex["training_sha256"]:
        raise ValueError("Treinamento alterado depois da exportacao.")
    for name, digest in ex["generated_hashes"].items():
        if sha256(run/"generated"/name) != digest:
            raise ValueError(f"Artefato embarcado alterado: {name}")
    return ex


def evaluate(run, prepared=None):
    tf = tensorflow()
    run = Path(run)
    if (run / "evaluation_receipt.json").exists():
        raise FileExistsError("Teste ja avaliado neste run. Consulte reports/; nao selecione pelo teste.")
    training, info, data, metadata = check_run(run, prepared)
    ex = verify_export(run)
    report_dir = fresh_directory(run / "reports")
    # Recibo antes de abrir as predicoes: marca inclusive tentativas interrompidas.
    write_json(run/"evaluation_receipt.json", {"status": "started_test_opened",
        "export_sha256": sha256(run/"export.json"), "model_sha256": ex["model_sha256"],
        "config_hash": info["config_hash"], "provenance": provenance()})
    ix = np.where(data["split"] == "test")[0]
    meta = [metadata[i] for i in ix]
    float_model = tf.keras.models.load_model(run / "float.keras")
    float_windows = float_model.predict(data["x"][ix], verbose=0)[:, 1]
    int8_windows = lite_probabilities(lite_interpreter(tf, run/"model_int8.tflite"), data["x"][ix])
    ids, y, float_p = aggregate(float_windows, meta)
    _, _, int8_p = aggregate(int8_windows, meta)
    train_people = {r["patient_id"]: int(r["label"]) for r in metadata if r["split"] == "train"}
    n_present = sum(train_people.values())
    majority = int(n_present > len(train_people)/2)  # empate -> Absent
    results = []
    for name, p, threshold in (("majority_baseline", np.full(len(y), majority), 0.5),
                               ("float_cnn", float_p, ex["float_threshold"]),
                               ("int8_host", int8_p, ex["threshold"])):
        m = write_report(report_dir, name, ids, y, p, threshold, info["config"])
        results.append({"model": name, **{k: m[k] for k in (
            "f1", "recall", "precision", "accuracy", "specificity", "macro_f1", "patients")}})
    write_csv(report_dir/"summary.csv", results)
    write_csv(report_dir/"test_windows.csv", [
        r | {"float_probability": float(p), "int8_probability": float(q)}
        for r, p, q in zip(meta, float_windows, int8_windows)])
    receipt = read_json(run/"evaluation_receipt.json")
    write_json(run/"evaluation_receipt.json", receipt | {"status": "complete",
        "report_hashes": {p.name: sha256(p) for p in report_dir.iterdir() if p.is_file()}})
    print(f"Metricas reais de teste gravadas em {report_dir}. Metricas da placa continuam pendentes.")
