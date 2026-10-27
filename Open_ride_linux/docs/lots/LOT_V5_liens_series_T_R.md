# Lot V5 – Liens avec les séries T et R : segments, maillots, runs, records et bots

## 1. Objectif

Brancher la progression sur les jeux des séries T (segments, records, maillots, bots à profil) et R (runs Cyber-Rogue) : les événements de ces séries rapportent expérience et pièces, l'équipement est noté avec chaque passage de segment, et le calibrage des bots tient compte de l'équipement.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_V.md` §2.1, §2.2 (« Records », « Bots à profil ») ; `docs/2.0/PLAN_SERIE_T.md` §3.1 à §3.4 ; `docs/2.0/PLAN_SERIE_R.md` (R9) et `docs/2.0/GDD_CYBER_ROGUE.md` §2.7 (boss).
2. Code livré par T4 (passages au journal), T5 (records), T13 (calibrage), T14 (maillots), R9 (runs et vies), et `progression.py`, `equipment.py`, `coins.py` (V2, V3, V3b).

## 3. Prérequis

V2, V3, V3b et V11 fusionnés ; T4, T5, T13 et T14 fusionnés ; R9 pour la partie Cyber-Rogue (la partie T peut être livrée seule, la partie R ensuite dans une deuxième PR du même lot).

## 4. Travail demandé

- **Événements depuis le journal :** `session_facts` (V2) lit les lignes écrites par T4, T14 et la série R (forme fixée par ces lots) et remplit `events` : `segment` (identifiant, type, record personnel battu, catégorie de montée), `jersey` (`kom` ou `sprint`), `rogue_run` (minutes, boss vaincus). Les gains et les compteurs de défis de V2 et V3b s'en servent sans autre changement.
- **Défis :** « premier col HC » (passage d'un segment de montée de catégorie HC, T2), « premier maillot à pois » (T14), « premier boss » (R).
- **Records et équipement :** chaque passage enregistré par T5 garde l'équipement utilisé (`loadout` de l'en-tête du journal, écrit par V11) ; un record reste un record, l'équipement est affiché à côté (T10) ; le message `segment_result` reçoit `equipment_gain_s` calculé par `equipment_time_gain` sur le segment (V3).
- **Bots à profil (T13) :** le calibrage avant le départ simule le cycliste avec ses `PhysicsParams` équipés (`apply_equipment`), pour que le niveau choisi reste juste.
- **Cyber-Rogue :** l'équipement de la série V ne s'applique pas dans ce mode (les châssis de R9 en tiennent lieu, proposition à confirmer avec la série R) ; une run rapporte expérience et pièces selon le plan.

## 5. Fichiers concernés

`progression.py`, `coins.py`, les modules de T5, T13 et R9 (lignes d'appel seulement), leurs tests, `docs/SUIVI_AVANCEMENT.md`. Interdits : l'engine.

## 6. Modifications de contrat autorisées

Champ `equipment_gain_s` de `segment_result`, s'il n'a pas été ajouté par V1 ou T1.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Journal synthétique avec deux segments (dont un record) et un maillot à pois : 50 + 100 + 200 points de plus qu'une séance sans événement, pièces 5 + 5 + 20, défi « maillot à pois » réussi.
3. Calibrage d'un bot au même niveau avec et sans équipement aéro sur un parcours plat : temps d'arrivée du bot identique à celui du cycliste simulé équipé (à 1 % près).
4. Passage de segment : équipement noté dans le record, `equipment_gain_s` nul avec l'équipement de départ.

## 8. Hors périmètre

Affichage des records (T10) et du bilan (V9) ; règles du jeu des séries T et R.
