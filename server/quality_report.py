from __future__ import annotations

import argparse
import json
from pathlib import Path

from server.quality import evaluate_algo, load_decider_from_path

def main() -> int:
    p = argparse.ArgumentParser(description="Akinator Lite — rapport qualité")
    p.add_argument("--kb", default=str(Path(__file__).with_name("kb.json")), help="Path to kb.json")
    p.add_argument("--algo", default=str(Path(__file__).parent / "algo" / "decision.py"), help="Path to decision.py")
    p.add_argument("--theme", default=None, help="Theme key (optional)")
    p.add_argument("--difficulty", default=None, choices=["easy","medium","hard"], help="Difficulty (optional)")
    args = p.parse_args()

    kb = json.loads(Path(args.kb).read_text(encoding="utf-8"))
    decider = load_decider_from_path(args.algo)

    themes = [t["key"] for t in kb.get("themes", [])] if kb.get("themes") else sorted({x for it in kb["items"] for x in it.get("themes", [])})
    diffs = ["easy","medium","hard"]

    if args.theme:
        themes = [args.theme]
    if args.difficulty:
        diffs = [args.difficulty]

    print(f"KB:   {args.kb}")
    print(f"ALGO: {args.algo}")
    print("")

    for d in diffs:
        print(f"=== difficulty: {d} ===")
        for t in themes:
            st = evaluate_algo(kb, t, d, decider)
            print(f"- theme={st.theme:8} items={st.items:2d} avg={st.avg_iters:5.2f} p90={st.p90_iters:2d} max={st.max_iters:2d} score={st.score_20:5.2f}/20")
        print("")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
