# Lot X30 – Tableau de recette 1.0

## 1. Objectif

Les 25 lignes de la recette 1.0 (cahier O8) se cochent dans un fichier Markdown, sans lien vers les journaux des outils qui les mesurent.

## 2. À lire

`docs/lots/LOT_O8_recette_1_0.md` (tableau des lignes), `docs/SUIVI_AVANCEMENT.md` §3, dossiers de sortie des outils (`~/OpenRide/recettes/`, `sim_bench/`, `trainer_steps/`, `click_recette/`, `boutons_click/`, `recettes_install/`, `fc_recette/`).

## 3. Travail demandé

- **`scripts/tableau_recette.py`** : lit le tableau d'O8, associe à chaque ligne l'outil qui la mesure (table dans le script : ligne → outil, dossier, champ du verdict) et cherche le dernier rapport de cet outil dans `~/OpenRide/` ; écrit `~/OpenRide/recette_1_0/tableau.html` : ligne, critère, dernier résultat (OK/ÉCHEC/à faire), date, lien vers le rapport, case « vu par le propriétaire » et note (localStorage, export JSON), PR de correction si elle est notée.
- `--json` pour les sessions qui corrigent.

## 4. Fichiers

- **Nouveaux :** `scripts/tableau_recette.py`, `core/tests/test_tableau_recette.py` (O8 lu, rapports fabriqués dans un HOME temporaire).
- **Modifiés :** `docs/OUTILS_DE_TEST.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 5. Critères d'acceptation

1. Les 25 lignes d'O8 sont lues ; une ligne sans outil est marquée « à la main ».
2. Un rapport OK fabriqué apparaît avec sa date et son lien.

## 6. Hors périmètre

Publier la 1.0 (O8).
