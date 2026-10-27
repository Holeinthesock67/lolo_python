# Lot T16 – Écarts en temps de passage avec le bot devant et le bot derrière

## 1. Objectif

Demande du propriétaire du 25 octobre (plan de la série T §3.4) : donner en permanence l'écart avec les deux voisins immédiats, par exemple « ▲ Grimpeur +8,4 s » et « ▼ Diesel −3,1 s ». Ce lot calcule dans le core, une fois par trame, l'écart en **temps de passage** de chaque bot (`gap_s`) et les identifiants des deux voisins (`bot_ahead`, `bot_behind`). L'affichage est le lot T15 ; l'ajout des champs à la trame `state` vient avec le contrat T1.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_T.md` §3.4 (paragraphe « Écart avec le bot devant et le bot derrière ») et §3.5 (champs `gap_s`, `bot_ahead`, `bot_behind`).
2. `docs/lots/LOT_N9_bots_core.md`, `docs/lots/LOT_O7_affichage_bots.md` (estimation distance ÷ vitesse).
3. Code : `core/src/openride_core/bots.py`, `core/src/openride_core/physics.py` (`RiderPhysics.s` cumulée).

## 3. Prérequis

N9 (livré, PR #175). Aucun contrat pour le module ; branchement dans `session.py` et `IpcState` avec T1 (IPC v1.4).

## 4. Travail demandé

Nouveau module `core/src/openride_core/gaps.py` :

- `GapTracker(length_m, loop)` garde les passages (`s`, `t`) de chaque coureur sur les 5 dernières minutes, au plus 10 par seconde ; `step(t, (s, v) du cycliste, {id: (s, v)} des bots)` note les positions puis rend un `GapReport`.
- **Bot devant :** temps écoulé depuis son passage au point où se trouve le cycliste (écart positif). **Bot derrière :** temps écoulé depuis le passage du cycliste au point où se trouve le bot (écart négatif).
- **Repli :** sans passage dans l'historique (départ, ou écart de plus de 5 min), distance ÷ vitesse du coureur qui doit couvrir la distance (le cycliste pour un bot devant, le bot pour un bot derrière), vitesse plancher 1 m/s ; `estimated` le signale.
- **Voisins :** `bot_ahead` est le plus proche devant, `bot_behind` le plus proche derrière (ou à égalité) ; `None` s'il n'y en a pas (la ligne disparaît du HUD).
- **Boucle :** le voisin est cherché sur le tour en cours, c'est-à-dire sur le circuit : l'écart de position est ramené dans ]−L/2, L/2]. Un bot qui a un tour d'avance et roule 50 m derrière le cycliste est donc « derrière, 50 m » ; l'écart en temps utilise l'historique dans les distances cumulées du bot.
- Coût : moins de 0,2 ms par trame avec 5 bots.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/gaps.py`, `core/tests/test_gaps.py`, ce cahier.
- **Interdits :** `bots.py`, `session.py`, `ipc_server.py`, le contrat IPC, l'engine.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `python -m pytest -q` passe en entier dans `core/`.
2. Vitesses égales à 10 m/s : bot 100 m devant = +10 s, bot 50 m derrière = −5 s, à 0,02 s près, sans repli.
3. Au départ : repli distance ÷ vitesse signalé ; plancher de 1 m/s.
4. Bot devant entré dans une montée (2 m/s) pendant que le cycliste roule à 10 m/s : écart stable à 10 s, alors que distance ÷ vitesse du bot donnerait plus du double.
5. Voisins : les plus proches devant et derrière, lignes absentes sans bot.
6. Boucle : voisin cherché sur le circuit ; écart en temps juste avec un tour d'avance.
7. Écart de plus de 5 min : repli, écart juste à 0,5 s près à vitesse constante.
8. Coût : moins de 0,2 ms par trame avec 5 bots et 60 s d'historique.

## 8. Hors périmètre

- Champs `gap_s`, `bot_ahead`, `bot_behind` de `state` et tests de taille (T1 puis branchement) ; affichage (T15).
- Profils de bots (T12) : le module ne dépend que des positions.

## 9. Livraison (26 octobre 2026)

- Module pur et 8 tests, sans changement de `session.py` ni du contrat ; branchement avec T1. Ligne de suivi : ce cahier.
