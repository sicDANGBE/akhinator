# Tutoriel pseudo‑code — `decide_next_action(context: dict) -> dict`

Objectif : te donner une **trame pédagogique** (pseudo‑code, pas du Python exécutable) pour implémenter / améliorer l’algorithme dans **un seul point d’entrée**.

---

## 0) Contrat d’entrée / sortie

### Entrée : `context`

Le serveur fournit tout ce qu’il faut pour décider :

* `kb`: dataset chargé (`features` + `items`)
* `history`: événements passés (questions posées, réponses, feedback)
* `candidates`: liste d’IDs candidats encore possibles
* `asked`: liste des features déjà posées (sérialisée)
* `difficulty`: `easy | medium | hard` (déjà appliquée côté serveur via filtrage des features)
* `step`: compteur d’itérations
* `last_guess_id` (optionnel): dernier item proposé

### Sortie : **une seule action**

* Question : `{"type": "question", "question_key": "has_wheels"}`
* Guess : `{"type": "guess", "item_id": "bike", "confidence": 0.86}`
* Done : `{"type": "done", "message": "Plus de candidats"}`

---

## 1) Début obligatoire : déconstruire le `context`

> Pseudo‑code proche de Python, mais volontairement « non exécutable ».

```text
function decide_next_action(context: dict) -> dict:

  # --- Déconstruction du contexte (toujours en premier) ---
  kb         := context.get("kb") or {}
  features   := kb.get("features") or []      # liste de features autorisées (déjà filtrées)
  items      := kb.get("items") or []         # liste complète d'items

  history    := context.get("history") or []
  candidates := context.get("candidates") or []
  asked      := set(context.get("asked") or [])

  difficulty := context.get("difficulty")     # info, mais features déjà filtrées
  step       := int(context.get("step") or 0)
  last_guess := context.get("last_guess_id")  # optionnel

  # Accès rapide aux attributs d'un item
  items_by_id := { item.id -> item } construit à partir de `items`

  # --- Gardes (cas limites) ---
  if candidates est vide:
      return {type:"done", message:"Plus de candidats"}

  if taille(candidates) == 1:
      return {type:"guess", item_id:candidates[0], confidence:1.0}
```

---

## 2) Normaliser les réponses déjà données

On veut une structure simple : `answers[feature_key] = True|False|None`.

```text
  answers := extract_answers(history)

  # extract_answers(history):
  #   answers := {}
  #   for event in history:
  #       if event.type == "answer":
  #           key := event.key
  #           value := event.value
  #           if value == "yes":  answers[key] = True
  #           if value == "no":   answers[key] = False
  #           if value == "skip": answers[key] = None
  #   return answers
```

> Note : on ignore les événements autres que `answer`.

---

## 3) Choisir entre **question** et **guess**

Tu as deux sous‑problèmes :

1. **Quel est le meilleur candidat actuel ?** (et à quel point il est probable)
2. **Est-ce qu’on guess maintenant ?** (policy)

### 3.1 Estimer le meilleur candidat + une confiance

Tu peux faire simple au départ :

* score = proportion de réponses « compatibles »
* `None` (unknown) ne doit pas éliminer, donc score partiel

```text
  (best_id, confidence) := best_candidate_and_confidence(candidates, items_by_id, answers)

  # best_candidate_and_confidence(...):
  #   answered_keys := liste des features où answers[key] est True/False
  #   best_id := candidates[0]
  #   best_score := -inf
  #
  #   for cid in candidates:
  #       attrs := items_by_id[cid].attrs
  #       score := 0
  #       for key in answered_keys:
  #           want := answers[key]        # True/False
  #           have := attrs.get(key)      # True/False/None
  #
  #           if have == None: score += 0.5      # inconnu = demi‑point
  #           else if have == want: score += 1.0
  #           else: score += 0
  #
  #       score := score / max(1, len(answered_keys))
  #
  #       if score > best_score:
  #           best_score := score
  #           best_id := cid
  #
  #   # Confiance = best_score * facteur(taille candidats)
  #   cand_factor := 1 / max(1, len(candidates))
  #   confidence := clamp( best_score * (0.25 + 2.0*cand_factor), 0, 1 )
  #   return (best_id, confidence)
```

### 3.2 Policy de guessing (quand proposer un item)

Objectif : éviter de guess trop tôt et éviter la boucle sur le même guess.

```text
  # Politique simple:
  # - si très peu de candidats, guess
  # - si confiance haute et pas le même guess qu'avant, guess

  if len(candidates) <= 2 and step >= 1:
      return {type:"guess", item_id:best_id, confidence:confidence}

  if confidence >= 0.80 and step >= 2 and best_id != last_guess:
      return {type:"guess", item_id:best_id, confidence:confidence}
```

> Variantes utiles :

* seuil dynamique : plus `step` est grand, plus tu peux baisser le seuil
* guess “progressif” : ne guess que si `best_score` est suffisamment supérieur au 2e meilleur

---

## 4) Sélection de la prochaine question

Tu dois choisir une feature **non posée** qui réduit l’incertitude.

```text
  feature_keys := [f.key for f in features]
  available := [k for k in feature_keys si k not in asked]

  if available est vide:
      return {type:"guess", item_id:best_id, confidence:confidence}
```

Ensuite, tu as **plusieurs stratégies**. Je t’en propose 3 (toutes fonctionnent). Choisis-en une.

---

# Solution 1 — Split équilibré (baseline, simple)

Idée : une bonne question sépare les candidats en deux groupes (True / False) et a peu de `None`.

### Pseudo‑code

```text
  q := select_question_balanced(available, candidates, items_by_id)

  if q == None:
      return {type:"guess", item_id:best_id, confidence:confidence}

  return {type:"question", question_key:q}
```

### Détail du score

```text
function select_question_balanced(feature_keys, candidates, items_by_id) -> feature_key|None:

  total := len(candidates)
  best_key := None
  best_score := +inf

  for key in feature_keys:
      t := 0 ; f := 0 ; n := 0

      for cid in candidates:
          v := items_by_id[cid].attrs.get(key)
          if v == True:  t += 1
          else if v == False: f += 1
          else: n += 1

      # "strict": il faut du monde des deux côtés
      if t == 0 or f == 0:
          continue

      known := t + f
      imbalance := abs(t - f) / known
      unknown_ratio := n / total

      score := imbalance + 0.7 * unknown_ratio

      if score < best_score:
          best_score := score
          best_key := key

  return best_key
```

**Pourquoi ça marche ?**

* `imbalance` proche de 0 ⇒ split ~50/50 ⇒ tu réduis la recherche vite.
* `unknown_ratio` faible ⇒ la question a de la donnée ⇒ moins de réponses “skip” utiles.

---

# Solution 2 — Information Gain (entropie) (recommandée)

Idée : choisir la question qui maximise la réduction d’entropie **en moyenne**.

### Intuition

* Avant : incertitude ~ `log2(N)` avec N candidats
* Après : incertitude = somme pondérée par la proba des réponses (yes/no/skip)
* `None` signifie “inconnu” : si l’utilisateur répond yes ou no, les `None` restent en jeu.

### Pseudo‑code

```text
  q := select_question_information_gain(available, candidates, items_by_id)

  if q == None:
      return {type:"guess", item_id:best_id, confidence:confidence}

  return {type:"question", question_key:q}
```

### Détail

```text
function select_question_information_gain(feature_keys, candidates, items_by_id) -> feature_key|None:

  total := len(candidates)
  if total <= 1: return None

  H_before := log2(total)
  best_key := None
  best_ig_adj := -inf

  for key in feature_keys:
      t := 0 ; f := 0 ; n := 0
      for cid in candidates:
          v := items_by_id[cid].attrs.get(key)
          if v == True:  t += 1
          else if v == False: f += 1
          else: n += 1

      if t == 0 and f == 0:
          continue

      p_yes := t / total
      p_no  := f / total
      p_skip:= n / total

      # Si l'utilisateur répond yes : on garde True + None
      size_yes := t + n
      # Si l'utilisateur répond no : on garde False + None
      size_no  := f + n
      # Si l'utilisateur skip : on garde tout
      size_skip := total

      H_after := p_yes*log2(size_yes) + p_no*log2(size_no) + p_skip*log2(size_skip)

      IG := H_before - H_after

      # Ajustement : pénaliser les features trop "unknown"
      IG_adj := IG - 0.10 * p_skip

      if IG_adj > best_ig_adj:
          best_ig_adj := IG_adj
          best_key := key

  # Option: si le gain est trop faible, abandonner (guess)
  if best_key == None: return None
  if best_ig_adj <= 0.05: return None

  return best_key
```

**Pourquoi c’est souvent meilleur ?**

* Le critère IG cible directement la réduction de recherche “en moyenne”.
* Tu obtiens généralement moins de questions qu’un split équilibré naïf.

---

# Solution 3 — Minimax (réduction du pire cas)

Idée : choisir la question qui minimise le **pire** nombre de candidats restants après réponse.

### Pseudo‑code

```text
  q := select_question_minimax(available, candidates, items_by_id)

  if q == None:
      return {type:"guess", item_id:best_id, confidence:confidence}

  return {type:"question", question_key:q}
```

### Détail

```text
function select_question_minimax(feature_keys, candidates, items_by_id) -> feature_key|None:

  total := len(candidates)
  best_key := None
  best_worst := +inf

  for key in feature_keys:
      t := 0 ; f := 0 ; n := 0

      for cid in candidates:
          v := items_by_id[cid].attrs.get(key)
          if v == True:  t += 1
          else if v == False: f += 1
          else: n += 1

      if t == 0 and f == 0:
          continue

      # unknown reste dans les deux branches
      size_yes := t + n
      size_no  := f + n
      size_skip := total

      worst := max(size_yes, size_no, size_skip)

      if worst < best_worst:
          best_worst := worst
          best_key := key

  # Si ça ne réduit jamais rien, autant guess
  if best_key == None: return None
  if best_worst >= total: return None

  return best_key
```

**Pourquoi ça marche ?**

* Ça évite les questions “pièges” qui ne réduisent presque rien dans le pire cas.
* Très utile si tu cherches à limiter le `max_iters` (pire partie).

---

## 5) Assemblage final (choisir UNE des solutions)

Tu choisis une stratégie de question (Solution 1/2/3) et tu la branches ici :

```text
function decide_next_action(context: dict) -> dict:

  # 1) Déconstruction du context
  ... (cf section 1) ...

  # 2) Gardes
  ...

  # 3) Normalisation des réponses
  answers := extract_answers(history)

  # 4) Meilleur candidat + confiance
  (best_id, confidence) := best_candidate_and_confidence(...)

  # 5) Policy guess
  if should_guess(candidates, step, confidence, best_id, last_guess):
      return {type:"guess", item_id:best_id, confidence:confidence}

  # 6) Features dispo
  available := features non posées
  if available vide:
      return {type:"guess", item_id:best_id, confidence:confidence}

  # 7) Choix question (UNE méthode)
  q := select_question_information_gain(...)   # OU balanced(...) OU minimax(...)

  if q == None:
      return {type:"guess", item_id:best_id, confidence:confidence}

  return {type:"question", question_key:q}
```

---

## 6) Notes importantes sur `None` (unknown) et `skip`

* `None` dans la KB veut dire : “on ne sait pas” (pas “False”).
* Si l’utilisateur répond **yes** ou **no**, tu gardes les candidats `None` (par prudence).
* Si l’utilisateur répond **skip**, le serveur ne filtre pas les candidats.

Conséquence : une bonne question est une feature avec :

* beaucoup de valeurs connues (`True/False`)
* un split utile

---

## 7) Extension facile : confidence plus robuste

Au lieu d’un score brut, compare le meilleur au second :

```text
best_score, second_score := top2(scores)
margin := best_score - second_score

confidence := clamp( 0.5*best_score + 0.5*margin + 0.2*(1/len(candidates)), 0, 1 )

if confidence > seuil:
   guess
```

Ça réduit les guesses précoces lorsque plusieurs candidats sont très proches.
