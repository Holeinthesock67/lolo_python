# Lot X30 – Tableau de recette 1.0

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : Tableau de recette 1.0 relié aux rapports des outils | Python | O8 | Petite | **Livré le 28 octobre** (branche `claude/project-thread-818r6t-x30`) ; issue #228 |

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

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x30`).

- **`scripts/tableau_recette.py`** lit le §4 d'O8 : numéro, critère (sans la mention de l'outil), ligne bloquante (en gras), groupe.
- **Table `OUTILS`** (ligne → commande, dossier de `~/OpenRide/`) :
  - lignes 1 et 2 → `recette_install` (`docker`, `home`) ;
  - 5 → `boutons_click` ;
  - 6 → `click_recette` ;
  - 7 → `fc_recette` ;
  - 17 → `sim_bench` ;
  - 18 → `sim_bench` avec le scénario `endurance` ;
  - 19 → étape `engine` de `recette_pc` ;
  - 20 → `menu_bench`.
  - Les lignes 10, 21 et 22 ont un outil qui n'écrit rien (`log_report --latence`, `fit-check`, `compare-garmin`) : elles sont « à la main », avec la commande.
  - Les autres lignes sont « à la main » sans outil.
- **Résultat d'un rapport**, dans l'ordre : ligne `verdict` de `guide.jsonl` (tous les outils guidés) ; `resume.json` (`ok`, ou l'étape nommée) ; `rapport.json` ; `resultats.json` (aucun échec) ; `resume_<mode>.txt`. Le dernier dossier `<date>_<heure>` fait foi.
- **`tableau.html`** (`~/OpenRide/recette_1_0/`) : une rangée par ligne avec le résultat, la date, le lien `file://` vers le rapport, la case « vu », la note et la PR. Ces trois champs sont gardés dans `localStorage` (lecture et écriture protégées) et exportables en JSON. `--json` donne le tableau sur la sortie standard.
- **Tests** `core/tests/test_tableau_recette.py` (4 tests) : O8 lu (25 lignes), HOME vide, rapports fabriqués (dernier rapport, étape de la recette du PC, scénario d'endurance, banc des menus, installation), page et JSON.
- **Docs** : `docs/OUTILS_DE_TEST.md`, `SUIVI_AVANCEMENT.md`.
