# Lot X36 – Pré-vol avant une séance vélo

## 1. Objectif

Règle du propriétaire (28 octobre) : une séance vélo tient en 20 minutes de pédalage. Tout ce qui se vérifie sans pédaler doit l'être avant, en une commande, avec un verdict « prêt à rouler » (proposition du fil des fusions).

## 2. À lire

`scripts/recette_pc.py`, `engine/tests/run_engine_tests.sh` (variable `UNIT`), `core/src/openride_core/tools/guide.py`, `/mnt/project-files/plans/SEANCE_VELO_T11_J7_P27.md` (préparation).

## 3. Travail demandé

- **`scripts/pre_vol.py --seance NOM`** (séances décrites dans `scripts/pre_vol_seances.toml` : `t11_j7`, `p27`, `erg`, `recette_1_0`) :
  1. `git` : branche, à jour avec `origin`, rien de non commité ;
  2. tests ciblés : pytest avec la marque `recette_sans_velo` (tests listés pour la séance) et `run_engine_tests.sh` avec les `UNIT` de la séance ;
  3. séance simulée de la séance (scénarios X33 quand ils existent) en `--rapide` ;
  4. matériel et fichiers : `config.toml` sauvegardé (`config.toml.<séance>`), parcours compilés présents, fichiers temporaires (`powerups.toml`) posés ou retirés ;
  5. Bluetooth allumé, trainer et Click visibles (`openride-core devices --rapide`, sauté avec `--sans-bluetooth`) ;
  6. verdict : **PRÊT À ROULER** ou la liste de ce qui bloque, avec bip (guide).
- Journal dans `~/OpenRide/pre_vol/<date>_<heure>/`.
- Durée cible : moins de 10 minutes.

## 4. Fichiers

- **Nouveaux :** `scripts/pre_vol.py`, `scripts/pre_vol_seances.toml`, `core/tests/test_pre_vol.py`.
- **Modifiés :** `core/pyproject.toml` (marque `recette_sans_velo`), tests marqués, `docs/OUTILS_DE_TEST.md`, `docs/PROTOCOLE_TEST_2026-10-26.md` (§0), ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 5. Critères d'acceptation

1. Chaque étape testée avec des commandes simulées (OK, échec, sautée).
2. `pre_vol.py --seance t11_j7 --sans-bluetooth --sans-engine` tourne au cloud.

## 6. Hors périmètre

La séance elle-même.
