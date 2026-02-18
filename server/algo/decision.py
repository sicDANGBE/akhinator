from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# -----------------------------------------------------------------------------
# Middleware algorithmique (isolé)
# -----------------------------------------------------------------------------
# Entrée unique : decide_next_action(context)
# Sorties possibles:
#   {"type":"question", "question_key": "<feature_key>"}
#   {"type":"guess", "item_id": "<item_id>", "confidence": 0..1}
#   {"type":"done", "message": "..."}
#
# Le serveur construit le contexte (candidats, historique, features autorisées)
# et applique lui-même les effets de bord (marquer "asked", stocker history, etc.)
# -----------------------------------------------------------------------------

def decide_next_action(context: dict) -> dict:
    """Décide quoi faire au prochain tour.

    Stratégie de base:
      - Estime le meilleur candidat (score heuristique sur réponses connues)
      - Si confiance suffisante ou peu de candidats: propose un guess
      - Sinon, pose une question qui sépare au mieux les candidats
    """
    kb: Dict[str, Any] = context.get("kb", {}) or {}
    features: List[Dict[str, Any]] = kb.get("features", []) or []
    items: List[Dict[str, Any]] = kb.get("items", []) or []

    history: List[Dict[str, Any]] = context.get("history", []) or []
    candidates: List[str] = context.get("candidates", []) or []
    asked = set(context.get("asked", []) or [])

    step: int = int(context.get("step", 0) or 0)
    last_guess_id: Optional[str] = context.get("last_guess_id")

    items_by_id: Dict[str, Dict[str, Any]] = {it.get("id"): it for it in items if it.get("id")}


    return {""}
