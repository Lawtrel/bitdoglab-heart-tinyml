#!/usr/bin/env bash
set -euo pipefail
bundle="$(realpath -- "$1")"
out="$(realpath -- "$2")"
training_root="${PCG_TRAINING_ROOT:-$HOME/projects/bitdoglab-tinyml}"
if [[ ! -x "$training_root/.venv-gpu-wsl/bin/python" ]]; then
  echo 'Ambiente GPU existente nao encontrado. Defina PCG_TRAINING_ROOT com a pasta do projeto no Arch.' >&2; exit 1
fi
cd -- "$training_root"
source scripts/gpu-env.sh
native_root="$HOME/projects/heart-tinyml-benchmarks/$(basename -- "$out")"
mkdir -p -- "$native_root"
cp -a -- "$bundle/." "$native_root/"
export PYTHONPATH="$native_root/source"
mkdir -p -- "$native_root/reports"
trap 'cp -a -- "$native_root/reports/." "$out/" 2>/dev/null || true' EXIT
for mode in cpu_float gpu_float cpu_float_lite cpu_int8; do
  echo "INFERENCE BENCHMARK: $mode; batch=1; 100 janelas x 3; sem training"
  "$gpu_python" -u "$native_root/benchmark_validation.py" --bundle "$native_root" --mode "$mode" --out "$native_root/reports"
  cp -a -- "$native_root/reports/." "$out/"
done
echo 'ARCH_BENCHMARK_CONCLUIDO'
