import concurrent.futures
import math
import re
import time
import urllib.request
import wave
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
import numpy as np
from .common import fresh_directory, read_json, write_json, write_csv, sha256, object_hash, provenance

DATA_URL = "https://physionet.org/files/circor-heart-sound/1.0.3/"


def _safe_relative(name):
    p = PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts or "\\" in name or ":" in name:
        raise ValueError(f"Caminho remoto invalido: {name}")
    return p


def download(dest, workers=4):
    """Baixa a versao fixa, verifica cada arquivo pelo SHA256 oficial e retoma."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(DATA_URL + "SHA256SUMS.txt", headers={"User-Agent": "PCG-research/0.1"})
    checksum_text = urllib.request.urlopen(req, timeout=60).read().decode()
    checks = []
    for line in checksum_text.splitlines():
        match = re.match(r"^([0-9a-fA-F]{64})\s+\*?(.+)$", line)
        if not match:
            continue
        expected, name = match.groups()
        name = name.removeprefix("./")
        rel = _safe_relative(name)
        # Segmentacoes .tsv nao sao usadas neste baseline; WAVs e metadados bastam.
        if rel.suffix in (".wav", ".txt", ".hea", ".csv"):
            checks.append((name, expected.lower()))
    if not checks:
        raise ValueError("Manifesto oficial vazio ou formato inesperado.")
    (dest / "SHA256SUMS.txt").write_text(checksum_text, encoding="utf-8")

    def fetch(item):
        name, expected = item
        target = dest.joinpath(*_safe_relative(name).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and sha256(target) == expected:
            return
        for attempt in range(3):
            try:
                part = target.with_name(target.name + ".part")
                request = urllib.request.Request(DATA_URL + name, headers={"User-Agent": "PCG-research/0.1"})
                with urllib.request.urlopen(request, timeout=90) as src, part.open("wb") as dst:
                    for chunk in iter(lambda: src.read(1024 * 1024), b""):
                        dst.write(chunk)
                if sha256(part) != expected:
                    raise ValueError(f"Checksum incorreto: {name}")
                part.replace(target)
                return
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch, item) for item in checks]
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            future.result()
            if i % 100 == 0 or i == len(futures):
                print(f"{i}/{len(futures)} arquivos verificados", flush=True)
    # A licenca e o manifesto permanecem junto aos dados; nada e enviado a servicos.
    if not (dest / "LICENSE.txt").exists():
        request = urllib.request.Request(DATA_URL + "LICENSE.txt")
        (dest / "LICENSE.txt").write_bytes(urllib.request.urlopen(request, timeout=60).read())
    write_json(dest / "download_receipt.json", {"source": DATA_URL, "version": "1.0.3",
        "verified_files": len(checks), "checksum_manifest_sha256": sha256(dest / "SHA256SUMS.txt"),
        "provenance": provenance()})


class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        self.parent[max(a, b)] = min(a, b)


def parse_header(path):
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    first = lines[0].split()
    if len(first) < 3 or not first[0].isdigit():
        raise ValueError("Cabecalho de paciente invalido")
    encounter_id, count = first[0], int(first[1])
    fields = {}
    for line in lines:
        if line.startswith("#") and ":" in line:
            k, value = line[1:].split(":", 1)
            fields[k.strip()] = value.strip()
    recordings = []
    for line in lines[1:1 + count]:
        tokens = line.split()
        if len(tokens) < 3 or not tokens[2].endswith(".wav"):
            raise ValueError("Linha de gravacao invalida")
        name = tokens[2]
        if Path(name).name != name or not re.fullmatch(r"[A-Za-z0-9_.-]+\.wav", name):
            raise ValueError("Nome WAV inseguro")
        recordings.append((tokens[0], name))
    additional = fields.get("Additional ID", "").strip()
    if additional.lower() in ("", "nan", "none"):
        additional = None
    elif not re.fullmatch(r"\d+", additional):
        raise ValueError(f"Additional ID inesperado: {additional}")
    return encounter_id, fields, recordings, additional


def inventory(root, output):
    root = Path(root).resolve()
    headers = []
    for p in sorted(root.rglob("*.txt")):
        # Apenas cabecalhos numericos de sujeitos; ignora LICENSE/RECORDS.
        if p.stem.isdigit():
            headers.append(p)
    if not headers:
        raise ValueError("Nenhum cabecalho de paciente encontrado. Aponte para a pasta do CirCor.")
    uf, encounters, errors = UnionFind(), {}, []
    source_headers = {}
    for path in headers:
        try:
            encounter, fields, recordings, additional = parse_header(path)
            if encounter in encounters:
                raise ValueError(f"ID duplicado de cabecalho: {encounter}")
            uf.find(encounter)
            if additional:
                uf.union(encounter, additional)
            encounters[encounter] = (path, fields, recordings, additional)
            source_headers[path.relative_to(root).as_posix()] = sha256(path)
        except (ValueError, IndexError) as exc:
            errors.append({"header": str(path.relative_to(root)), "reason": str(exc)})
    # Metadados malformados nao sao descartados silenciosamente: impedem dividir.
    if errors:
        raise ValueError(f"Corrija cabecalhos malformados antes do split: {errors[:5]}")
    rows, excluded, seen_hash = [], [], {}
    for encounter, (header, fields, recs, additional) in encounters.items():
        label = {"Present": 1, "Absent": 0}.get(fields.get("Murmur"))
        if label is None:
            excluded.append({"encounter_id": encounter, "reason": "unknown_or_missing_murmur",
                             "recordings": len(recs)})
        for location, name in recs:
            path = header.parent / name
            try:
                with wave.open(str(path), "rb") as wav:
                    if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getnframes() == 0:
                        raise ValueError("Formato precisa ser mono PCM16 nao vazio")
                    rate, frames = wav.getframerate(), wav.getnframes()
                digest = sha256(path)
                if digest in seen_hash:
                    # Unir grupos com WAV identico evita vazamento por duplicatas.
                    uf.union(encounter, seen_hash[digest])
                seen_hash[digest] = encounter
                if label is not None:
                    rows.append({"encounter_id": encounter, "recording_id": path.stem,
                        "path": path.relative_to(root).as_posix(), "location": location,
                        "label": label, "sha256": digest, "sample_rate": rate,
                        "samples": frames, "seconds": frames / rate,
                        "audible_locations": fields.get("Murmur locations", "")})
            except (OSError, EOFError, wave.Error, ValueError) as exc:
                if label is not None:
                    excluded.append({"encounter_id": encounter, "recording_id": path.stem,
                                     "reason": "unreadable_or_invalid_wav", "detail": str(exc)})
    labels_by_group = defaultdict(set)
    for row in rows:
        row["patient_id"] = uf.find(row["encounter_id"])
        labels_by_group[row["patient_id"]].add(row["label"])
    conflicts = {g for g, labels in labels_by_group.items() if len(labels) != 1}
    unique, included_hashes = [], set()
    for row in rows:
        if row["patient_id"] in conflicts:
            excluded.append({"encounter_id": row["encounter_id"], "recording_id": row["recording_id"],
                             "reason": "conflicting_labels_in_linked_patient"})
        elif row["sha256"] in included_hashes:
            excluded.append({"encounter_id": row["encounter_id"], "recording_id": row["recording_id"],
                             "reason": "exact_duplicate_wav"})
        else:
            included_hashes.add(row["sha256"])
            unique.append(row)
    if not unique:
        raise ValueError("Nenhuma gravacao elegivel apos auditoria.")
    report = {"dataset": "CirCor DigiScope 1.0.3", "data_root": str(root),
        "recordings": unique, "excluded": excluded, "source_headers": source_headers,
        "linkage": "Additional ID plus exact-WAV SHA256; unannotated identity cannot be proven",
        "linked_encounters": sum(bool(v[3]) for v in encounters.values()),
        "dangling_additional_ids": sorted({v[3] for v in encounters.values() if v[3] and v[3] not in encounters}),
        "conflicting_groups_excluded": sorted(conflicts), "provenance": provenance()}
    write_json(output, report)
    print(f"Inventario: {len(unique)} gravacoes elegiveis; {len(excluded)} exclusoes registradas.")


def make_split(inventory_path, out, c):
    inv = read_json(inventory_path)
    out = fresh_directory(out)
    patients = {}
    for r in inv["recordings"]:
        if r["patient_id"] in patients and patients[r["patient_id"]] != r["label"]:
            raise ValueError("Paciente com rotulos conflitantes.")
        patients[r["patient_id"]] = r["label"]
    assignment = {}
    rng = np.random.default_rng(c["split_seed"])
    for label in (0, 1):
        groups = np.array(sorted(g for g, y in patients.items() if y == label))
        if len(groups) < 3:
            raise ValueError("Cada classe precisa ter pelo menos tres pacientes para treino/val/teste.")
        rng.shuffle(groups)
        n_val = max(1, round(len(groups) * c["validation_fraction"]))
        n_test = max(1, round(len(groups) * c["test_fraction"]))
        if n_val + n_test >= len(groups):
            raise ValueError("Coorte pequena demais para as proporcoes escolhidas.")
        for name, subset in (("validation", groups[:n_val]), ("test", groups[n_val:n_val+n_test]),
                             ("train", groups[n_val+n_test:])):
            assignment.update({str(g): name for g in subset})
    rows = [r | {"split": assignment[r["patient_id"]]} for r in inv["recordings"]]
    audit_disjoint(rows)
    manifest = inv | {"recordings": rows, "assignment": assignment, "config": c,
                      "config_hash": object_hash(c), "inventory_sha256": sha256(inventory_path),
                      "status": "split_frozen_before_segmentation"}
    write_json(out / "manifest.json", manifest)
    write_csv(out / "split_manifest.csv", rows)
    counts = {s: {"patients": Counter(str(patients[g]) for g in assignment if assignment[g] == s),
                  "recordings": sum(r["split"] == s for r in rows)}
              for s in ("train", "validation", "test")}
    write_json(out / "split_counts.json", counts)
    print(f"Split congelado em {out}; grupos e hashes disjuntos.")


def audit_disjoint(rows):
    for field in ("patient_id", "encounter_id", "sha256", "recording_id"):
        partitions = defaultdict(set)
        for row in rows:
            partitions[row[field]].add(row["split"])
        leaked = [key for key, parts in partitions.items() if len(parts) != 1]
        if leaked:
            raise ValueError(f"Vazamento por {field}: {leaked[:5]}")
