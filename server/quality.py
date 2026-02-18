from __future__ import annotations

import importlib.util
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

DecideFn = Callable[[dict], dict]

def load_decider_from_path(path: str) -> DecideFn:
    p = Path(path)
    spec = importlib.util.spec_from_file_location(p.stem, p)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import module from: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    fn = getattr(mod, "decide_next_action", None)
    if not callable(fn):
        raise RuntimeError(f"No callable decide_next_action in: {path}")
    return fn

def allowed_feature_keys_for_difficulty(feature_keys_in_order: List[str], difficulty: str) -> List[str]:
    if difficulty == "hard":
        return feature_keys_in_order[:8]
    if difficulty == "medium":
        return feature_keys_in_order[:12]
    return feature_keys_in_order[:]

def filter_candidates_by_theme(kb: Dict[str, Any], theme: str) -> List[str]:
    return [it["id"] for it in kb["items"] if theme in it.get("themes", [])]

def update_candidates_on_answer(items_by_id: Dict[str, Any], candidates: List[str], question_key: str, answer: str) -> List[str]:
    if answer == "skip":
        return candidates
    want = True if answer == "yes" else False
    out: List[str] = []
    for cid in candidates:
        attrs = (items_by_id.get(cid, {}) or {}).get("attrs", {}) or {}
        v = attrs.get(question_key, None)
        if v is None or v is want:
            out.append(cid)
    return out

def simulate_game_for_target(
    kb: Dict[str, Any],
    theme: str,
    difficulty: str,
    decide_next_action: DecideFn,
    target_id: str,
    max_steps: int = 80,
) -> Tuple[bool, int]:
    items_by_id = {it["id"]: it for it in kb["items"]}
    feature_keys_in_order = [f["key"] for f in kb["features"]]
    allowed = set(allowed_feature_keys_for_difficulty(feature_keys_in_order, difficulty))

    candidates = filter_candidates_by_theme(kb, theme)
    asked = set()
    history: List[Dict[str, Any]] = []
    step = 0
    last_guess_id: Optional[str] = None

    target = items_by_id[target_id]
    target_attrs = target.get("attrs", {}) or {}

    for _ in range(max_steps):
        algo_kb = {"features": [f for f in kb["features"] if f["key"] in allowed], "items": kb["items"]}
        ctx = {
            "kb": algo_kb,
            "history": history,
            "candidates": candidates,
            "asked": sorted(list(asked)),
            "difficulty": difficulty,
            "step": step,
            "last_guess_id": last_guess_id,
        }
        action = decide_next_action(ctx)

        if action.get("type") == "done":
            return False, step

        if action.get("type") == "question":
            qk = action.get("question_key")
            if not qk:
                return False, step

            asked.add(qk)
            history.append({"type": "question", "key": qk})

            v = target_attrs.get(qk, None)
            if v is True:
                ans = "yes"
            elif v is False:
                ans = "no"
            else:
                ans = "skip"

            history.append({"type": "answer", "key": qk, "value": ans})
            candidates = update_candidates_on_answer(items_by_id, candidates, qk, ans)
            step += 1

            if not candidates:
                return False, step
            continue

        if action.get("type") == "guess":
            gid = action.get("item_id")
            if not gid:
                return False, step

            if gid == target_id:
                history.append({"type": "guess_feedback", "item_id": gid, "correct": True})
                return True, step

            history.append({"type": "guess_feedback", "item_id": gid, "correct": False})
            candidates = [c for c in candidates if c != gid]
            last_guess_id = gid
            step += 1

            if not candidates:
                return False, step
            continue

        return False, step

    return False, step

@dataclass
class QualityStats:
    theme: str
    difficulty: str
    items: int
    avg_iters: float
    p90_iters: int
    max_iters: int
    score_20: float

def compute_score_20(kb: Dict[str, Any], theme: str, iters: int) -> float:
    n = len(filter_candidates_by_theme(kb, theme))
    if n <= 1:
        return 20.0
    ideal = math.log2(n)
    ratio = ideal / max(1, iters)
    return max(0.0, min(1.0, ratio)) * 20.0

def evaluate_algo(kb: Dict[str, Any], theme: str, difficulty: str, decide_next_action: DecideFn) -> QualityStats:
    ids = filter_candidates_by_theme(kb, theme)
    iters_list: List[int] = []
    for tid in ids:
        ok, iters = simulate_game_for_target(kb, theme, difficulty, decide_next_action, tid)
        iters_list.append(iters if ok else max(iters, 1))

    iters_sorted = sorted(iters_list)
    items = len(iters_list)
    avg = sum(iters_list) / max(1, items)
    p90 = iters_sorted[int(math.ceil(0.90 * items)) - 1] if items else 0
    mx = iters_sorted[-1] if items else 0

    scores = [compute_score_20(kb, theme, i) for i in iters_list]
    score = sum(scores) / max(1, len(scores))

    return QualityStats(theme=theme, difficulty=difficulty, items=items, avg_iters=avg, p90_iters=int(p90), max_iters=int(mx), score_20=float(score))
