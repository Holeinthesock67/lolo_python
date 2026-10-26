# Lot N9 – Bots côté core : puissance constante et fantôme d'une séance passée

## 1. Objectif

Premier pas du sprint 7 de la SRS (optionnel) : rouler avec un partenaire virtuel. Ce lot calcule dans le core la position de bots à **puissance constante** et d'un **fantôme** rejouant une séance passée (`.fit` ou `.jsonl`) sur le même parcours, et les publie dans le champ `bots` de la trame `state`, déjà annoncé par le contrat. L'affichage (silhouette, écart en secondes) viendra dans un lot interne.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/contracts/ipc_v1.md` §3 (champ `bots`) et le §4.4 du lot N1 (forme proposée `{id, name, s, v, kind}`).
2. `docs/SRS_v1.1.md` §5 (physique) et §13 (sprint 7), §14.
3. Code : `core/src/openride_core/physics.py`, `core/src/openride_core/route.py` (pente à `s`, boucles), `core/src/openride_core/replay.py` (lecture `.fit` et `.jsonl`), `core/src/openride_core/session.py`, `core/src/openride_core/__main__.py`.

## 3. Prérequis

- PR #91, lots M3 et M4 (PR #92 et #90) : fusionnés le 24 octobre, partir de `main` à jour (ils ont modifié `session.py` et `__main__.py`).
- Lot N1 (livré le 24 octobre) : la forme de `bots` est fixée par le contrat v1.1 §3 (au plus 5 éléments, `id` de 8 caractères et `name` de 16 au plus) ; le schéma la décrit déjà.

## 4. Travail demandé

- Nouveau module `bots.py` :
  - `ConstantPowerBot(power_w, mass_kg, …)` : même modèle physique que le cycliste (`physics.py`), même pente du parcours à sa position, pas de braquet (pente réelle) ; boucle et aller-retour gérés comme pour le cycliste ;
  - `GhostBot(path)` : position en fonction du temps chronométré de la séance enregistrée (distance cumulée), interpolée ; arrêté en bout de séance enregistrée ; refus clair si le fichier n'a pas de distance ;
  - avance des bots au pas de 50 Hz seulement pendant `RUNNING` (figés en pause, comme le chronomètre).
- `openride-core run --bot W` (répétable, au plus 4) et `--ghost FICHIER` (un seul) ; noms « Bot 200 W » et « Fantôme du JJ/MM ».
- Champ `bots` dans `state` uniquement s'il y a des bots (absent sinon : trames inchangées).
- Le journal reste celui du cycliste : les bots n'y sont pas écrits (pas de changement de format).

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/bots.py`, `core/tests/test_bots.py`.
- **Modifiés :** `session.py`, `ipc_server.py` (`IpcState`), `__main__.py`, `README.md` et `CLAUDE.md` (options citées), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `physics.py` (lecture seule ; une fonction manquante se signale), l'engine.

## 6. Modifications de contrat autorisées

Aucune : la propriété `bots` est décrite dans le contrat v1.1 et dans `state.schema.json` (lot N1).

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Parcours plat : un bot de 200 W et un cycliste simulé à 200 W, même masse : écart de position inférieur à 1 m après 10 min simulées.
3. Montée à 8 % : un bot de 300 W va plus vite qu'un bot de 200 W, dans le rapport attendu par `physics.py` (à 2 % près).
4. Fantôme d'un `.fit` de test : à t = 600 s, position égale à la distance du FIT à t = 600 s (à 5 m près) ; `.jsonl` et `.fit` de la même séance donnent les mêmes positions.
5. Pause de 60 s : bots figés, `t` des bots inchangé.
6. Sans bot : trame `state` identique à aujourd'hui (aucune clé `bots`) ; avec 4 bots : trame validée par le schéma.
7. Coût : 4 bots ajoutent moins de 0,2 ms au pas de physique p99 (mesure dans le test, PC de développement).

## 8. Hors périmètre

- Affichage des bots dans l'engine (lot interne à rédiger).
- Modèle CP / W', réglage des bots au Click, courses.

## 9. Livraison (25 octobre 2026, PR #175)

- Code et tests fusionnés sur `main` par la PR #175 (issue #106 fermée) ; détail dans la description de la PR et dans `docs/SUIVI_AVANCEMENT.md`.
