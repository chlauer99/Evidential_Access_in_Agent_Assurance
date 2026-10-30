"""Check that harness/prompts/*.txt equal the prompts in the harness code (byte for byte)."""
import runpy, sys
from pathlib import Path

H = Path(__file__).resolve().parent.parent
ex = runpy.run_path(str(H / "scripts" / "export_prompts.py"), run_name="ex")
bad = 0
for name, text in ex["collect"]().items():
    f = H / "prompts" / name
    ok = f.exists() and f.read_bytes() == text.encode("utf-8")
    bad += not ok
    print(("PASS " if ok else "FAIL ") + name)
sys.exit(1 if bad else 0)
