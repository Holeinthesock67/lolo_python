# Lot H4 – Endurance simulée : séance de 3 h en temps accéléré

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Endurance simulée : séance de 3 h en temps accéléré (audit F7) | Python | — | Petite | **Livré le 23 octobre** (PR #14) |

## 1. Objectif

Vérifier automatiquement les exigences de durée de la SRS §12 sans pédaler 3 h :
- boucle de physique sans dérive sur une séance de 3 h ;
- mémoire du core stable ;
- journal et FIT valides et cohérents en fin de séance ;
- trame `state` toujours sous la limite de taille du contrat (constat F7 de l'audit).

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/SRS_v1.1.md` §5 (physique), §9 (journal, FIT), §12 (exigences).
3. `docs/contracts/ipc_v1.md` (taille maximale d'une trame).
4. `docs/AUDIT_2026-10-23.md`, constat F7.
5. Code : `core/src/openride_core/session.py` (`CoreSession._step`) ; `core/tests/test_workout.py` (fonctions `make_session` et `run`, qui font avancer la séance en temps accéléré sans boucle asyncio).

## 3. Prérequis

Aucun. Partir de `main` à jour.

## 4. Travail demandé

Nouveau fichier `core/tests/test_endurance.py`. Tests marqués `@pytest.mark.slow`, déclarés dans `core/pyproject.toml` (`[tool.pytest.ini_options] markers`). Ils tournent par défaut ; `pytest -m "not slow"` permet de les sauter.

**Scénarios :**

1. **3 h en SIM** : parcours en boucle synthétique de 10 km (écrit avec les aides de test existantes de `test_route.py` ou `test_workout.py`), `MockDriver` en rampe, pas de 0,02 s (50 Hz réels), 540 000 pas.
   - Temps de séance final : 10 800 s à 0,1 s près.
   - Distance cohérente avec la vitesse moyenne (écart < 0,5 %).
   - Énergie : vitesse jamais négative, jamais `NaN`, jamais au-delà du plafond de `physics.py`.
2. **Mémoire** : `tracemalloc` entre la 30e minute et la fin ; la croissance doit rester sous un seuil justifié (ordre de grandeur : ce que pèsent les enregistrements gardés en mémoire par `SessionRecorder`, soit environ 10 800 lignes ; aucune autre structure ne doit croître).
3. **Journal et FIT** : à la fin (`end_session` avec `save: True`, `fit_export.ACTIVITIES_DIR` redirigé vers `tmp_path`), 10 800 enregistrements à ± 1, horodatages strictement croissants ; le FIT relu par `iter_records` contient autant de `record` et une `session` de 3 h de temps chronométré.
4. **Pauses** : la même séance avec 5 pauses de 2 min réparties : le temps chronométré exclut les pauses, et le FIT contient les événements correspondants.
5. **Taille de la trame `state`** (F7) : pendant la séance, avec un entraînement ERG chargé (objet `erg` rempli), la trame sérialisée reste sous la limite du contrat ; la plus grande taille observée est affichée dans la sortie du test.

**Durée** : chaque scénario doit tenir en moins de 60 s sur un PC ordinaire. Si ce n'est pas possible à 50 Hz, le dire dans le rapport et proposer un pas plus grand pour le scénario concerné, sans toucher au code de production.

## 5. Fichiers concernés

- **Nouveau :** `core/tests/test_endurance.py`.
- **Modifiés :** `core/pyproject.toml` (marqueur `slow` uniquement), `docs/AUDIT_2026-10-23.md` (suivi de F7), `docs/SUIVI_AVANCEMENT.md` (une ligne).

Si un défaut est trouvé dans le code de production (dérive, fuite), **s'arrêter et le signaler** au lieu de corriger.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Les 5 scénarios du §4 ont un test, et `cd core && pytest -q` passe en entier.
2. `pytest -m "not slow"` saute ces tests et passe.
3. La durée de chaque test lent est donnée dans le rapport (`pytest --durations=10`).
4. Le rapport donne la croissance mémoire mesurée et la taille maximale de trame observée.

## 8. Hors périmètre

- Endurance de l'engine Godot (fuite de mémoire de rendu) : demande le PC cible.
- Endurance Bluetooth réelle.


## 9. Livraison (23 octobre 2026)

Branche `lot-h4-endurance-simulee` (PR #14), fusionnée dans `main`. Les 4 critères d'acceptation du §7 sont tenus (5 tests `@pytest.mark.slow` dans `core/tests/test_endurance.py`, code de production inchangé) :
- **Durées (`pytest --durations=10`) :**
  - `test_endurance_sim_3h_physics_and_drift` (540 000 pas à 50 Hz) : 10,56 s ;
  - `test_endurance_state_frame_size_under_limit` (3 h avec ERG actif, audit F7) : 13,22 s ;
  - `test_endurance_journal_and_fit_3h` (10 801 relevés, FIT relu par `iter_records`) : 21,11 s ;
  - `test_endurance_with_five_pauses` (5 pauses de 2 min, 12 événements timer dans le FIT) : 22,10 s ;
  - `test_endurance_memory_stability` (`tracemalloc` entre 30 min et 3 h) : 51,45 s.
- **Mesures relevées :**
  - Croissance mémoire entre 30 min et 3 h : **+5 843,9 Ko** pour **+9 001 lignes** dans `SessionRecorder.lines` (665 octets/ligne, aucune autre structure ne croît) ;
  - Taille maximale de la trame `state` observée sur 3 h avec objet `erg` complet : **704 octets** (limite du contrat : 1 400 octets).
- **Choix technique documenté (§4) :** sous `tracemalloc`, chaque allocation Python est tracée (~8× plus lent, 99 s à 50 Hz). Le scénario 2 utilise un pas `dt = 0,04 s` (25 Hz, 270 000 pas) qui produit les mêmes 10 800 relevés à 1 Hz en 51,5 s (< 60 s).
