"""Regenerate current paper figures, optionally including archived drafts."""
import argparse
import subprocess
import sys
from pathlib import Path

base = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--include-archive', action='store_true', help='Also regenerate superseded drafts.')
args = parser.parse_args()
scripts = sorted(base.glob('plot_*.py'))
if args.include_archive:
    scripts += sorted((base / 'archive').glob('*.py'))
for script in scripts:
    print(f'Rendering {script.name}', flush=True)
    subprocess.run([sys.executable, str(script)], check=True)
