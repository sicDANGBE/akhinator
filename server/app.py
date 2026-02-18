from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from server.models import (
    StartRequest,
    AnswerRequest,
    GuessFeedbackRequest,
    ApiTurnResponse,
    ApiQuestion,
    ApiGuess,
    ApiDone,
    MetaResponse,
    WordsResponse,
)
from server.algo.decision import decide_next_action

BASE_DIR = Path(__file__).resolve().parent
KB_PATH = BASE_DIR / "kb.json"
STATIC_DIR = BASE_DIR / "static"

KB: Dict[str, Any] = json.loads(KB_PATH.read_text(encoding="utf-8"))
ITEMS_BY_ID: Dict[str, Dict[str, Any]] = {it["id"]: it for it in KB["items"]}
FEATURES_IN_ORDER: List[str] = [f["key"] for f in KB["features"]]
FEATURE_QUESTION_BY_KEY: Dict[str, str] = {f["key"]: f["question"] for f in KB["features"]}

def themes_from_kb() -> List[Dict[str, Any]]:
    counts: Dict[str, int] = {}
    for it in KB.get("items", []):
        for t in it.get("themes", []):
            counts[t] = counts.get(t, 0) + 1
    out = []
    for t in KB.get("themes", []):
        key = t["key"]
        out.append({"key": key, "label": t.get("label", key), "count": counts.get(key, 0)})
    return out

def allowed_feature_keys_for_difficulty(difficulty: str) -> List[str]:
    if difficulty == "hard":
        return FEATURES_IN_ORDER[:8]
    if difficulty == "medium":
        return FEATURES_IN_ORDER[:12]
    return FEATURES_IN_ORDER[:]

def build_algo_kb_subset(allowed_feature_keys: List[str]) -> Dict[str, Any]:
    allowed = set(allowed_feature_keys)
    return {
        "features": [f for f in KB["features"] if f["key"] in allowed],
        "items": KB["items"],
    }

def filter_candidates_by_theme(theme: str) -> List[str]:
    return [it["id"] for it in KB["items"] if theme in it.get("themes", [])]

def update_candidates_on_answer(candidates: List[str], question_key: str, answer: str) -> List[str]:
    # Fonction de filtrage : on conserve les items compatibles.
    # - yes/no: garde les items dont l'attribut est (True/False) OU inconnu (None)
    # - skip: ne filtre pas
    if answer == "skip":
        return candidates
    want = True if answer == "yes" else False
    out: List[str] = []
    for cid in candidates:
        attrs = (ITEMS_BY_ID.get(cid, {}).get("attrs", {}) or {})
        v = attrs.get(question_key, None)
        if v is None or v is want:
            out.append(cid)
    return out

@dataclass
class GameState:
    game_id: str
    theme: str
    difficulty: str
    allowed_feature_keys: List[str]
    candidates: List[str]
    asked: Set[str]
    history: List[Dict[str, Any]]
    step: int
    current_question_key: Optional[str] = None
    last_guess_id: Optional[str] = None
    done: bool = False
    done_message: Optional[str] = None

GAMES: Dict[str, GameState] = {}
GAMES_LOCK = Lock()

def to_api_turn_response(state: GameState, action: Dict[str, Any]) -> ApiTurnResponse:
    question_obj = None
    guess_obj = None
    done_obj = None

    if action["type"] == "question":
        qk = action["question_key"]
        question_obj = ApiQuestion(key=qk, text=FEATURE_QUESTION_BY_KEY.get(qk, qk))
    elif action["type"] == "guess":
        gid = action["item_id"]
        item = ITEMS_BY_ID.get(gid)
        label = item["label"] if item else gid
        guess_obj = ApiGuess(id=gid, label=label, confidence=float(action.get("confidence", 0.0)))
    elif action["type"] == "done":
        done_obj = ApiDone(message=str(action.get("message", "Terminé")))

    return ApiTurnResponse(
        game_id=state.game_id,
        action=action,
        question=question_obj,
        guess=guess_obj,
        done=done_obj,
        candidates_left=len(state.candidates),
        step=state.step,
        asked_count=len(state.asked),
        theme=state.theme,
        difficulty=state.difficulty,  # type: ignore[arg-type]
    )

def call_algo(state: GameState) -> Dict[str, Any]:
    # Construction du contexte et appel de l'algo.
    # Les effets de bord sont appliqués ici (pas dans l'algo).
    algo_kb = build_algo_kb_subset(state.allowed_feature_keys)
    ctx = {
        "kb": algo_kb,
        "history": state.history,
        "candidates": state.candidates,
        "asked": sorted(list(state.asked)),
        "difficulty": state.difficulty,
        "step": state.step,
        "last_guess_id": state.last_guess_id,
    }

    action = decide_next_action(ctx)

    if action.get("type") == "question":
        qk = action.get("question_key")
        if not qk:
            return {"type": "done", "message": "Action invalide: question_key manquant"}
        state.current_question_key = qk
        state.asked.add(qk)
        state.history.append({"type": "question", "key": qk})
        return {"type": "question", "question_key": qk}

    if action.get("type") == "guess":
        gid = action.get("item_id")
        if not gid:
            return {"type": "done", "message": "Action invalide: item_id manquant"}
        state.last_guess_id = gid
        state.current_question_key = None
        return {"type": "guess", "item_id": gid, "confidence": float(action.get("confidence", 0.0))}

    if action.get("type") == "done":
        state.done = True
        state.done_message = str(action.get("message", "Terminé"))
        state.current_question_key = None
        return {"type": "done", "message": state.done_message}

    state.done = True
    state.done_message = "Action inconnue"
    return {"type": "done", "message": state.done_message}

app = FastAPI(title="Akinator Lite", version="2.0.0")

@app.get("/api/meta", response_model=MetaResponse)
def api_meta():
    return MetaResponse(
        themes=themes_from_kb(),
        difficulties=["easy", "medium", "hard"],
        items_count=len(KB["items"]),
        features_count=len(KB["features"]),
    )

@app.get("/api/words", response_model=WordsResponse)
def api_words(theme: str = Query(...), difficulty: str = Query("easy")):
    words = [{"id": it["id"], "label": it["label"], "themes": it.get("themes", [])} for it in KB["items"] if theme in it.get("themes", [])]
    return WordsResponse(theme=theme, difficulty=difficulty, words=words)  # type: ignore[arg-type]

@app.post("/api/start", response_model=ApiTurnResponse)
def api_start(req: StartRequest):
    candidates = filter_candidates_by_theme(req.theme)
    if not candidates:
        raise HTTPException(status_code=400, detail=f"Aucun mot pour le thème '{req.theme}'")

    state = GameState(
        game_id=uuid.uuid4().hex,
        theme=req.theme,
        difficulty=req.difficulty,
        allowed_feature_keys=allowed_feature_keys_for_difficulty(req.difficulty),
        candidates=candidates,
        asked=set(),
        history=[],
        step=0,
    )

    with GAMES_LOCK:
        GAMES[state.game_id] = state

    action = call_algo(state)
    return to_api_turn_response(state, action)

@app.post("/api/answer", response_model=ApiTurnResponse)
def api_answer(game_id: str = Query(...), req: AnswerRequest = ...):
    with GAMES_LOCK:
        state = GAMES.get(game_id)
    if not state:
        raise HTTPException(status_code=404, detail="game_id inconnu")
    if state.done:
        return to_api_turn_response(state, {"type": "done", "message": state.done_message or "Terminé"})

    state.history.append({"type": "answer", "key": req.question_key, "value": req.answer})
    state.candidates = update_candidates_on_answer(state.candidates, req.question_key, req.answer)
    state.step += 1

    if not state.candidates:
        state.done = True
        state.done_message = "Plus de candidats"
        return to_api_turn_response(state, {"type": "done", "message": state.done_message})

    action = call_algo(state)
    return to_api_turn_response(state, action)

@app.post("/api/guess_feedback", response_model=ApiTurnResponse)
def api_guess_feedback(game_id: str = Query(...), req: GuessFeedbackRequest = ...):
    with GAMES_LOCK:
        state = GAMES.get(game_id)
    if not state:
        raise HTTPException(status_code=404, detail="game_id inconnu")
    if state.done:
        return to_api_turn_response(state, {"type": "done", "message": state.done_message or "Terminé"})

    state.history.append({"type": "guess_feedback", "item_id": req.guess_id, "correct": req.correct})

    if req.correct:
        state.done = True
        state.done_message = f"Bravo ! Mot trouvé : {ITEMS_BY_ID.get(req.guess_id, {}).get('label', req.guess_id)}"
        return to_api_turn_response(state, {"type": "done", "message": state.done_message})

    state.candidates = [c for c in state.candidates if c != req.guess_id]
    state.last_guess_id = req.guess_id
    state.step += 1

    if not state.candidates:
        state.done = True
        state.done_message = "Plus de candidats après élimination"
        return to_api_turn_response(state, {"type": "done", "message": state.done_message})

    action = call_algo(state)
    return to_api_turn_response(state, action)

@app.get("/api/state")
def api_state(game_id: str = Query(...)):
    with GAMES_LOCK:
        state = GAMES.get(game_id)
    if not state:
        raise HTTPException(status_code=404, detail="game_id inconnu")
    d = asdict(state)
    d["asked"] = sorted(list(state.asked))
    return d

# Static UI (HTML)
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
