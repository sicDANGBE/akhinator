# Akinator Lite — livrable bootstrapable

Objectif : mini “Akinator” (oui / non / passer) avec **algo isolé** + **bench de qualité externe**.

## Démarrer (local)

```bash
cd akinator-lite
python -m venv .venv
source .venv/bin/activate
pip install -r server/requirements.txt
uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
```

Ouvrir : http://localhost:8000

## Démarrer (Docker)

```bash
docker build -t akinator-lite .
docker run --rm -p 8000:8000 akinator-lite
```

## Contrat algorithmique

Le serveur n’appelle **qu’un seul point d’entrée** :

- `server/algo/decision.py`
- fonction: `decide_next_action(context) -> dict`

Le calcul de qualité est **en dehors** de ce middleware (aucune dépendance depuis l’algo).

## Dossier "solutions"

Trois implémentations prêtes à copier/coller dans `server/algo/decision.py` :

- `solutions/decision_balanced_strict.py` : split équilibré strict
- `solutions/decision_information_gain.py` : information gain (recommandé)
- `solutions/decision_minimax.py` : minimax (pire cas)

## Mesure de qualité

Benchmark / score sur 20 + itérations :

```bash
python -m server.quality_report
python -m server.quality_report --algo solutions/decision_information_gain.py
```

Le bench simule un joueur “parfait” (répond selon le vrai item).
