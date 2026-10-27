import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from .common import config, provenance


def doctor():
    print(json.dumps({"python": sys.version.split()[0], "packages": {
        name: importlib.util.find_spec(name) is not None
        for name in ("numpy", "scipy", "tensorflow", "serial")},
        "tools": {name: shutil.which(name) for name in (
            "cmake", "ninja", "arm-none-eabi-gcc", "arm-none-eabi-size", "git", "g++", "clang++")},
        "status": "environment_check_not_an_experiment"}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="CirCor -> CNN -> INT8 -> BitDogLab RP2040")
    parser.add_argument("--config", type=Path, help="Configuracao de novo experimento")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Confere dependencias sem instalar nada")
    p = commands.add_parser("gpu-check", help="Treina CNN artificial na GPU e registra compatibilidade")
    p.add_argument("--out", type=Path, default=Path("runs/gpu-check.json"))
    p = commands.add_parser("download", help="Baixa CirCor 1.0.3 e valida SHA256")
    p.add_argument("--dest", type=Path, default=Path("data/circor-1.0.3"))
    p.add_argument("--workers", type=int, default=4)
    p = commands.add_parser("inventory", help="Audita Murmur/Additional ID/duplicatas")
    p.add_argument("data", type=Path)
    p.add_argument("--out", type=Path, required=True)
    for name, description in (("split", "Congela split por paciente"),
                              ("prepare", "Extrai MFE e ajusta normalizacao no treino"),
                              ("train", "Treina tres seeds e seleciona por validacao")):
        p = commands.add_parser(name, help=description)
        p.add_argument("source", type=Path)
        p.add_argument("--out", type=Path, required=True)
        if name == "train":
            p.add_argument("--device", choices=("auto", "cpu", "gpu"), default="auto")
    for name in ("export", "evaluate"):
        p = commands.add_parser(name)
        p.add_argument("run", type=Path)
        p.add_argument("--prepared", type=Path, help="Local dos dados preparados se foram movidos")
    p = commands.add_parser("collect", help="Mede placa real por replay USB")
    p.add_argument("run", type=Path)
    p.add_argument("--port", required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--prepared", type=Path)
    p.add_argument("--evaluate-test", action="store_true")
    p.add_argument("--benchmark-windows", type=int, default=100)
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            doctor()
        elif args.command == "gpu-check":
            from .runtime import gpu_check
            gpu_check(args.out)
        elif args.command == "download":
            from .data import download
            download(args.dest, args.workers)
        elif args.command == "inventory":
            from .data import inventory
            inventory(args.data, args.out)
        elif args.command == "split":
            from .data import make_split
            make_split(args.source, args.out, config(args.config))
        elif args.command == "prepare":
            from .features import prepare
            from .common import read_json
            frozen = read_json(args.source)["config"]
            if args.config and config(args.config) != frozen:
                raise ValueError("Configuracao difere do split congelado; crie outro split.")
            prepare(args.source, args.out, frozen)
        elif args.command == "train":
            from .learning import train
            train(args.source, args.out, args.device)
        elif args.command == "export":
            from .learning import export
            export(args.run, args.prepared)
        elif args.command == "evaluate":
            from .learning import evaluate
            evaluate(args.run, args.prepared)
        elif args.command == "collect":
            from .board import collect
            collect(args.run, args.port, args.out, args.prepared, args.evaluate_test, args.benchmark_windows)
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        parser.exit(1, f"ERRO: {exc}\n")


if __name__ == "__main__":
    main()
