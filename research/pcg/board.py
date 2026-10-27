"""Replay USB real. Sem placa conectada nao ha metricas embarcadas."""
import binascii
import json
import struct
import time
from pathlib import Path
import numpy as np
from .common import fresh_directory, write_json, write_csv, sha256, provenance, read_json
from .features import load_audio, extract, quantize
from .learning import check_run, verify_export, tensorflow, lite_probabilities
from .metrics import aggregate, write_report


def packet(seq, mode, payload=b""):
    return struct.pack("<4sIBII", b"PCG1", seq, mode, len(payload),
                       binascii.crc32(payload) & 0xffffffff) + payload


def read_exact(port, length):
    data = bytearray()
    while len(data) < length:
        chunk = port.read(length-len(data))
        if not chunk:
            raise TimeoutError(f"Timeout lendo dados binarios da placa: {len(data)}/{length} bytes recebidos.")
        data.extend(chunk)
    return bytes(data)


def transact(port, seq, mode, payload=b"", *, flush_output=True):
    frame = packet(seq, mode, payload)
    written = port.write(frame)
    if written is not None and written != len(frame):
        raise TimeoutError("Pacote USB escrito parcialmente.")
    # O teste longo usa a resposta como ACK. FlushFileBuffers do Windows pode
    # bloquear sem write_timeout quando o dispositivo desconecta.
    if flush_output:
        port.flush()
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        line = port.readline()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            continue  # mensagens de diagnostico do runtime nao sao resultados
        if not isinstance(obj, dict) or obj.get("seq") != seq:
            continue
        if obj.get("type") == "error":
            raise RuntimeError(f"Placa recusou a entrada: {obj['reason']}")
        if mode == 2:
            if obj.get("type") != "features" or obj.get("bytes") != 186*24:
                raise ValueError("Resposta de features invalida.")
            raw = read_exact(port, obj["bytes"])
            if binascii.crc32(raw) & 0xffffffff != obj["crc32"]:
                raise ValueError("CRC da resposta binaria incorreto.")
            return obj, np.frombuffer(raw, dtype=np.int8)
        expected = "hello" if mode == 0 else "result"
        if obj.get("type") != expected:
            raise ValueError("Tipo inesperado de resposta USB.")
        return obj
    raise TimeoutError("Sem resposta valida da placa; confira porta e firmware.")


def _payload(meta, manifest, c, cache):
    path = Path(manifest["data_root"]) / meta["path"]
    if str(path) not in cache:
        expected = next(r["sha256"] for r in manifest["recordings"] if r["path"] == meta["path"])
        if sha256(path) != expected:
            raise ValueError(f"WAV alterado depois do split: {path}")
        cache.clear()  # uma gravacao em memoria por vez
        cache[str(path)] = load_audio(path, c["sample_rate"])
    x = cache[str(path)]
    if len(x) < c["window_samples"]:
        x = np.pad(x, (0, c["window_samples"]-len(x)))
    window = x[meta["start"]:meta["start"]+c["window_samples"]]
    pcm = np.clip(np.rint(window*32768), -32768, 32767).astype("<i2")
    return pcm.tobytes(), pcm.astype(np.float32) / 32768


def collect(run, port_name, output, prepared=None, evaluate_test=False, benchmark_windows=100):
    if benchmark_windows < 100:
        raise ValueError("Protocolo exige pelo menos 100 janelas cronometradas.")
    try:
        import serial
    except ImportError as exc:
        raise RuntimeError("Instale pyserial (scripts/setup.ps1).") from exc
    training, info, data, metadata = check_run(run, prepared)
    run = Path(run)
    ex, c = verify_export(run), info["config"]
    if evaluate_test:
        receipt = run/"evaluation_receipt.json"
        if not receipt.exists() or read_json(receipt).get("status") != "complete":
            raise ValueError("Primeiro conclua pcg evaluate no mesmo teste congelado.")
        if read_json(receipt)["export_sha256"] != sha256(run/"export.json"):
            raise ValueError("Exportacao/limiares foram alterados depois da avaliacao de teste.")
    out = fresh_directory(output)
    tf = tensorflow()
    # Paridade com kernels inteiros de referencia; o teste host original
    # AUTO/XNNPACK continua congelado e nao e recalculado aqui.
    interpreter = tf.lite.Interpreter(model_path=str(run/"model_int8.tflite"), num_threads=1,
        experimental_op_resolver_type=tf.lite.experimental.OpResolverType.BUILTIN_REF)
    interpreter.allocate_tensors()
    cache, seq = {}, 0
    val_ix = np.where(data["split"] == "validation")[0]
    if not len(val_ix):
        raise ValueError("Sem validacao para benchmark.")
    raw_log = out/"usb_log.jsonl"
    # Cria evidencia antes de iniciar; uma falha nao vira metrica zero.
    write_json(out/"session.json", {"status": "started", "kind": "real_board", "host_parity_resolver": "BUILTIN_REF",
        "model_sha256": ex["model_sha256"], "test_requested": evaluate_test,
        "preparation_sha256": training["preparation_sha256"], "provenance": provenance()})
    with serial.Serial(port_name, 115200, timeout=60, write_timeout=60) as port, raw_log.open("w", encoding="utf-8") as log:
        port.dtr = True
        port.reset_input_buffer()
        hello = transact(port, seq, 0)
        if not hello.get("ready") or hello.get("model_sha256") != ex["model_sha256"]:
            raise ValueError("Firmware sem modelo pronto ou hash diferente do modelo selecionado.")
        if hello.get("clock_hz") != 133000000:
            raise ValueError("Clock diferente dos 133 MHz planejados.")
        write_json(out/"board_info.json", hello)
        log.write(json.dumps(hello)+"\n")
        parity = []
        # Compara features e saida do modelo em ate dez entradas de validacao.
        for i in val_ix[:10]:
            payload, pcm = _payload(metadata[i], info["manifest"], c, cache)
            feature = ((extract(pcm, c)-data["mean"]) / data["std"])[..., None]
            expected = quantize(feature, ex["input_scale"], ex["input_zero_point"]).ravel()
            seq += 1
            _, observed = transact(port, seq, 2, payload)
            diff = np.abs(expected.astype(int)-observed.astype(int))
            seq += 1
            result = transact(port, seq, 1, payload)
            host = lite_probabilities(interpreter, feature[None])[0]
            parity.append({"window_index": int(i), "max_int8_feature_difference": int(diff.max()),
                "different_feature_elements": int(np.count_nonzero(diff)),
                "host_probability": float(host), "board_probability": result["prob_present"],
                "absolute_probability_difference": float(abs(host-result["prob_present"]))})
            log.write(json.dumps(result)+"\n")
        passed = all(r["max_int8_feature_difference"] <= 1 and
                     r["absolute_probability_difference"] <= 2*ex["output_scale"]+1e-7 for r in parity)
        write_json(out/"parity.json", {"passed": passed, "entries": parity,
            "acceptance": "max input INT8 difference <=1; output vs BUILTIN_REF <=2 quantization steps"})
        if not passed:
            raise ValueError("Paridade Python/placa falhou. Corrija o front-end/runtime antes das metricas.")
        times = []
        # Dez warmups adicionais; os tempos deles nao entram no resumo.
        for number in range(10 + benchmark_windows):
            i = val_ix[number % len(val_ix)]
            payload, _ = _payload(metadata[i], info["manifest"], c, cache)
            seq += 1
            row = transact(port, seq, 1, payload) | {"window_index": int(i), "warmup": number < 10}
            log.write(json.dumps(row)+"\n")
            log.flush()
            if number >= 10:
                times.append(row)
        write_csv(out/"timing_windows.csv", times)
        timing = {}
        for key in ("preprocessing_us", "inference_us", "processing_us"):
            values = np.asarray([r[key] for r in times], dtype=float)
            if not np.isfinite(values).all() or np.any(values < 0):
                raise ValueError("Tempo reportado invalido.")
            timing[key] = dict(zip(("median", "p95", "maximum"),
                                  np.percentile(values, [50, 95, 100]).tolist()))
        write_json(out/"timing_summary.json", {"measured_windows": len(times), "warmup_windows": 10,
            "times": timing, "unit": "microseconds", "acquisition_window_seconds": 3,
            "window_hop_seconds": 1.5, "excludes": ["USB_transfer", "CRC", "OLED", "acquisition"],
            "board": hello})
        if evaluate_test:
            if not (run/"evaluation_receipt.json").exists():
                raise ValueError("Primeiro execute pcg evaluate; compare placa com o mesmo teste congelado.")
            test_ix = np.where(data["split"] == "test")[0]
            predictions, test_meta, host_probabilities = [], [], []
            for i in test_ix:
                payload, pcm = _payload(metadata[i], info["manifest"], c, cache)
                seq += 1
                row = transact(port, seq, 1, payload)
                log.write(json.dumps(row | {"window_index": int(i)})+"\n")
                log.flush()
                predictions.append(row["prob_present"])
                test_meta.append(metadata[i])
                host_probabilities.append(lite_probabilities(interpreter, data["x"][i:i+1])[0])
            ids, y, p = aggregate(predictions, test_meta)
            write_report(out, "int8_rp2040", ids, y, p, ex["threshold"], c)
            _, _, host_p = aggregate(host_probabilities, test_meta)
            write_json(out/"host_board_agreement.json", {
                "host_comparison_resolver": "BUILTIN_REF; original AUTO/XNNPACK test report preserved",
                "patient_prediction_agreement": float(np.mean((p >= ex["threshold"]) == (host_p >= ex["threshold"]))),
                "mean_absolute_patient_score_difference": float(np.mean(np.abs(p-host_p))),
                "patients": len(ids)})
            write_csv(out/"board_test_windows.csv", [
                r | {"board_probability": float(p), "host_probability": float(q)}
                for r, p, q in zip(test_meta, predictions, host_probabilities)])
    write_json(out/"session.json", {"status": "complete", "kind": "real_board", "host_parity_resolver": "BUILTIN_REF",
        "model_sha256": ex["model_sha256"], "test_evaluated": evaluate_test,
        "provenance": provenance(), "files": {p.name: sha256(p) for p in out.iterdir()
                                             if p.is_file() and p.name != "session.json"}})
    print(f"Medidas reais da placa em {out}")
