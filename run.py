#!/usr/bin/env python3
"""CLI.

  python run.py facts                         # build data/factsheets/*.json (deterministic)
  python run.py draft  --model PATH.gguf      # one model over all sheets -> outputs/<model>/
  python run.py eval   --model A.gguf --model B.gguf   # drafts + summary + stress test -> reports/
  python run.py stub                          # CI path: stub generator, no model download
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from vcomm.facts import write_all, build_all  # noqa: E402
from vcomm.evaluate import run_model, stress_test  # noqa: E402
from vcomm.generate import StubGenerator  # noqa: E402

REPORTS, OUTPUTS = ROOT / "reports", ROOT / "outputs"


def tag(path: str) -> str:
    return Path(path).stem


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["facts", "draft", "eval", "stub"])
    ap.add_argument("--model", action="append", default=[])
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--only", default=None, help="substring filter on sheet id")
    a = ap.parse_args()

    sheets = write_all(ROOT / "data" / "factsheets")
    if a.only:
        sheets = [s for s in sheets if a.only in s.id]
    print(f"{len(sheets)} fact sheets")
    if a.cmd == "facts":
        return
    if a.cmd == "stub":
        gen = StubGenerator({s.id: s for s in sheets})
        summ = run_model(sheets, gen, ROOT / "build" / "stub", a.attempts)
        print(json.dumps(summ, indent=2))
        assert summ["llm_final"] == len(sheets), "stub drafts should all validate"
        return

    from vcomm.generate import LlamaCppGenerator
    summaries = []
    for m in a.model:
        gen = LlamaCppGenerator(m)
        summ = run_model(sheets, gen, OUTPUTS / tag(m), a.attempts)
        summaries.append(summ)
        (REPORTS / f"summary_{tag(m)}.json").parent.mkdir(exist_ok=True)
        (REPORTS / f"summary_{tag(m)}.json").write_text(json.dumps(summ, indent=2) + "\n")
        del gen
    if a.cmd == "eval":
        S = {s.id: s for s in build_all()}
        texts = []
        for m in a.model:
            for p in sorted((OUTPUTS / tag(m)).glob("*.json")):
                r = json.loads(p.read_text())
                if r["source"] == "llm":
                    texts.append((r["sheet_id"], r["final_text"]))
        st = stress_test(S, texts)
        (REPORTS / "validator_stress_test.json").write_text(json.dumps(st, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps(st, indent=2)[:3000])


if __name__ == "__main__":
    main()
