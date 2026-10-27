"""Metricas por paciente; nunca usa janelas como unidades independentes."""
from collections import defaultdict
import numpy as np
from .common import finite_probabilities, write_csv, write_json


def aggregate(probabilities, metadata):
    probs = finite_probabilities(probabilities)
    if len(probs) != len(metadata):
        raise ValueError("Quantidade de predicoes difere das janelas.")
    recordings, patients = defaultdict(list), {}
    for p, row in zip(probs, metadata):
        key = (str(row["patient_id"]), str(row["recording_id"]))
        recordings[key].append(float(p))
        patient = str(row["patient_id"])
        label = int(row["label"])
        if patient in patients and patients[patient] != label:
            raise ValueError("Paciente com rotulos inconsistentes.")
        patients[patient] = label
    grouped = defaultdict(list)
    for (patient, _), scores in recordings.items():
        grouped[patient].append(float(np.mean(scores)))
    ids = sorted(grouped)
    return ids, np.array([patients[g] for g in ids], dtype=int), np.array([max(grouped[g]) for g in ids])


def _ratio(n, d):
    return None if d == 0 else float(n / d)


def binary_metrics(y, probabilities, threshold):
    raw_y = np.asarray(y)
    if not np.all(np.isin(raw_y, [0, 1])):
        raise ValueError("Rotulos devem ser 0 ou 1.")
    y = raw_y.astype(int)
    p = finite_probabilities(probabilities)
    if y.shape != p.shape or y.size == 0 or not set(y.tolist()) <= {0, 1}:
        raise ValueError("Rotulos binarios e predicoes devem ter formato identico e nao vazio.")
    if not np.isfinite(threshold):
        raise ValueError("Limiar nao finito.")
    pred = p >= threshold
    tp = int(np.sum((y == 1) & pred))
    tn = int(np.sum((y == 0) & ~pred))
    fp = int(np.sum((y == 0) & pred))
    fn = int(np.sum((y == 1) & ~pred))
    f1 = _ratio(2 * tp, 2 * tp + fp + fn)
    f1_absent = _ratio(2 * tn, 2 * tn + fp + fn)
    return {"f1": f1, "recall": _ratio(tp, tp+fn), "precision": _ratio(tp, tp+fp),
            "accuracy": (tp+tn)/len(y), "specificity": _ratio(tn, tn+fp),
            "macro_f1": None if f1 is None or f1_absent is None else (f1+f1_absent)/2,
            "tp": tp, "tn": tn, "fp": fp, "fn": fn,
            "support_present": tp+fn, "support_absent": tn+fp,
            "threshold": float(threshold), "patients": len(y),
            "undefined_metrics": [k for k, v in {"f1": f1, "f1_absent": f1_absent,
                "precision": _ratio(tp,tp+fp), "recall": _ratio(tp,tp+fn),
                "specificity": _ratio(tn,tn+fp)}.items() if v is None]}


def select_threshold(y, p):
    p = finite_probabilities(p)
    if set(np.asarray(y).tolist()) != {0, 1}:
        raise ValueError("Validacao precisa conter as duas classes.")
    # Inclui predicao totalmente negativa; >= e a regra compartilhada com C++.
    candidates = np.unique(np.r_[0.0, p, np.nextafter(1.0, 2.0)])
    best, rank = None, None
    for threshold in candidates:
        m = binary_metrics(y, p, threshold)
        score = (m["f1"] if m["f1"] is not None else -1,
                 m["recall"] if m["recall"] is not None else -1, -float(threshold))
        if rank is None or score > rank:
            best, rank = m, score
    return best


def bootstrap(y, p, threshold, replicates=2000, seed=2026):
    """Bootstrap ordinario por pessoa; replicas com classe ausente sao contadas."""
    y, p = np.asarray(y), finite_probabilities(p)
    rng = np.random.default_rng(seed)
    values = defaultdict(list)
    invalid = CounterLike()
    for _ in range(replicates):
        ix = rng.integers(0, len(y), len(y))
        m = binary_metrics(y[ix], p[ix], threshold)
        for name in ("f1", "recall", "precision", "accuracy", "specificity", "macro_f1"):
            if m[name] is None:
                invalid[name] += 1
            else:
                values[name].append(m[name])
    result = {}
    for name in ("f1", "recall", "precision", "accuracy", "specificity", "macro_f1"):
        result[name] = {"ci95": np.percentile(values[name], [2.5, 97.5]).tolist() if values[name] else None,
                        "valid_replicates": len(values[name]), "invalid_replicates": invalid[name]}
    return {"method": "ordinary_patient_bootstrap_percentile", "replicates": replicates,
            "seed": seed, "intervals": result}


class CounterLike(defaultdict):
    def __init__(self):
        super().__init__(int)


def write_report(out, name, ids, y, p, threshold, c):
    m = binary_metrics(y, p, threshold)
    m["bootstrap"] = bootstrap(y, p, threshold, c["bootstrap_replicates"], c["bootstrap_seed"])
    m["unit"] = "patient"
    write_json(out / f"{name}_metrics.json", m)
    write_csv(out / f"{name}_patients.csv",
              [{"patient_id": g, "label": int(t), "prob_present": float(v),
                "prediction": int(v >= threshold)} for g, t, v in zip(ids, y, p)])
    write_csv(out / f"{name}_confusion.csv", [
        {"actual": "Absent", "predicted_absent": m["tn"], "predicted_present": m["fp"]},
        {"actual": "Present", "predicted_absent": m["fn"], "predicted_present": m["tp"]}])
    # Figura vetorial simples, sem dependencia grafica; nada e simulado.
    cells = [[m["tn"], m["fp"]], [m["fn"], m["tp"]]]
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="440" height="300" viewBox="0 0 440 300">',
             '<rect width="440" height="300" fill="white"/>',
             '<g font-family="sans-serif" font-size="15" fill="#173d46">',
             '<text x="150" y="25">Predicted Absent</text><text x="285" y="25">Present</text>',
             '<text x="12" y="95">Actual Absent</text><text x="12" y="205">Present</text>']
    for i in range(2):
        for j in range(2):
            x, yy = 145+135*j, 45+110*i
            fill = "#dbece8" if i == j else "#f4dddd"
            parts += [f'<rect x="{x}" y="{yy}" width="125" height="100" fill="{fill}"/>',
                      f'<text x="{x+55}" y="{yy+57}" text-anchor="middle">{cells[i][j]}</text>']
    parts += ['</g></svg>']
    (out / f"{name}_confusion.svg").write_text("\n".join(parts), encoding="utf-8")
    return m
