from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

def decide_next_action(context: dict) -> dict:
    """Variant: minimax — réduit le pire cas (taille max après réponse)."""
    kb: Dict[str, Any] = context.get("kb", {}) or {}
    features: List[Dict[str, Any]] = kb.get("features", []) or []
    items: List[Dict[str, Any]] = kb.get("items", []) or []

    history: List[Dict[str, Any]] = context.get("history", []) or []
    candidates: List[str] = context.get("candidates", []) or []
    asked = set(context.get("asked", []) or [])

    step: int = int(context.get("step", 0) or 0)
    last_guess_id: Optional[str] = context.get("last_guess_id")

    items_by_id: Dict[str, Dict[str, Any]] = {it.get("id"): it for it in items if it.get("id")}

    if not candidates:
        return {"type": "done", "message": "Plus de candidats"}
    if len(candidates) == 1:
        return {"type": "guess", "item_id": candidates[0], "confidence": 1.0}

    answers = _extract_answers(history)
    best_id, confidence = _best_candidate_and_confidence(candidates, items_by_id, answers)

    if len(candidates) <= 2 and step >= 2:
        return {"type": "guess", "item_id": best_id, "confidence": float(confidence)}
    if confidence >= 0.90 and step >= 3 and best_id != last_guess_id:
        return {"type": "guess", "item_id": best_id, "confidence": float(confidence)}

    feature_keys = [f.get("key") for f in features if f.get("key")]
    available = [k for k in feature_keys if k not in asked]
    if not available:
        return {"type": "guess", "item_id": best_id, "confidence": float(confidence)}

    q = _select_best_question_minimax(available, candidates, items_by_id)
    if q is None:
        return {"type": "guess", "item_id": best_id, "confidence": float(confidence)}
    return {"type": "question", "question_key": q}

def _extract_answers(history: List[Dict[str, Any]]) -> Dict[str, Optional[bool]]:
    out: Dict[str, Optional[bool]] = {}
    for ev in history:
        if ev.get("type") != "answer":
            continue
        k = ev.get("key")
        v = ev.get("value")
        if not k:
            continue
        if v in (True, False):
            out[k] = v
        elif v == "yes":
            out[k] = True
        elif v == "no":
            out[k] = False
        elif v == "skip":
            out[k] = None
    return out

def _best_candidate_and_confidence(
    candidates: List[str],
    items_by_id: Dict[str, Dict[str, Any]],
    answers: Dict[str, Optional[bool]],
) -> Tuple[str, float]:
    answered_keys = [k for k, v in answers.items() if v is True or v is False]
    answered_n = len(answered_keys)

    best_id = candidates[0]
    best_score = -1.0

    for cid in candidates:
        attrs = (items_by_id.get(cid, {}).get("attrs", {}) or {})
        score = 0.0
        for k in answered_keys:
            want = answers[k]
            have = attrs.get(k, None)
            if have is None:
                score += 0.5
            elif have is want:
                score += 1.0
        score = (score / answered_n) if answered_n > 0 else 0.5
        if score > best_score:
            best_score = score
            best_id = cid

    cand_factor = 1.0 / max(1, len(candidates))
    conf = best_score * (0.20 + 2.2 * cand_factor)
    return best_id, max(0.0, min(1.0, float(conf)))

def _select_best_question_minimax(
    feature_keys: List[str],
    candidates: List[str],
    items_by_id: Dict[str, Dict[str, Any]],
) -> Optional[str]:
    total = len(candidates)
    best_k = None
    best_score = 1e18

    for k in feature_keys:
        t = f = n = 0
        for cid in candidates:
            v = (items_by_id.get(cid, {}).get("attrs", {}) or {}).get(k, None)
            if v is True:
                t += 1
            elif v is False:
                f += 1
            else:
                n += 1

        if t == 0 and f == 0:
            continue

        size_yes = t + n
        size_no = f + n
        worst = max(size_yes, size_no, total if n > 0 else 0)

        imbalance = abs(t - f) / float(max(1, t + f))
        unknown_ratio = n / float(max(1, total))
        score = worst + 0.5 * unknown_ratio * total + 0.2 * imbalance * total

        if score < best_score:
            best_score = score
            best_k = k

    if best_k is None:
        return None
    # Si aucune question ne réduit le pire cas => guess.
    if best_score >= total:
        return None
    return best_k
