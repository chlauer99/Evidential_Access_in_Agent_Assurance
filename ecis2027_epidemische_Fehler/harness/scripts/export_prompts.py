"""Write the paper's prompts, verbatim, from the harness source code to harness/prompts/.

The scripts remain the source of truth (their in-code strings produced the paper); this makes every prompt
inspectable as a file. tests/test_prompts.py checks that the files and the code agree byte for byte.
  python harness/scripts/export_prompts.py
"""
import json, runpy, sys
from pathlib import Path

H = Path(__file__).resolve().parent.parent
MH = H / "mab_harness"
P = H / "prompts"


def collect():
    ra = runpy.run_path(str(MH / "run_agents.py"), run_name="ra")
    jr = runpy.run_path(str(MH / "judge_runs.py"), run_name="jr")
    ja_src = (MH / "judge_agentic.py").read_text(encoding="utf-8")
    ns = {}
    exec(ja_src[ja_src.find("ACCESS = "):ja_src.find("def _val")], ns)
    pr = runpy.run_path(str(MH / "probes.py"), run_name="pr")
    cue = json.loads((H.parent / "data" / "raw" / "cue_deepseekv32" / "run_config.json").read_text(encoding="utf-8"))["context_suffix"]
    spec_header = "\nAPI SPECIFICATION GIVEN TO THE AGENT (the hospital's FHIR function catalogue)\n"
    out = {
        "agent_prompt.txt": ra["PROMPT"],
        "judge_system.txt": jr["SYSTEM"],
        "judge_user_template.txt": jr["USER"],
        "judge_checklist.txt": jr["VERIFY_CHECKS"],
        "judge_spec_header.txt": spec_header,
        "judge_record_access_block.txt": ns["ACCESS"],
        "probe_system.txt": pr["SYSTEM"],
        "cue_sentence.txt": cue,
        "post_ack.txt": ra["ACK"],
    }
    for k, v in pr["TEMPLATES"].items():
        out[f"probe_template_{k}.txt"] = v
    return out


if __name__ == "__main__":
    P.mkdir(exist_ok=True)
    for name, text in collect().items():
        (P / name).write_bytes(text.encode("utf-8"))
        print("wrote prompts/" + name, len(text), "chars")
