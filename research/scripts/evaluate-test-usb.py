"""Avaliacao completa e retomavel do mesmo teste congelado no RP2040."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from pcg.board_test import run
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--model',type=Path,required=True)
p.add_argument('--data-root',type=Path,required=True)
p.add_argument('--benchmark',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
p.add_argument('--port',default='auto')
p.add_argument('--prepare-only',action='store_true')
a=p.parse_args()
run(a.model,a.data_root,a.benchmark,a.out,a.port,a.prepare_only)
