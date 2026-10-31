# Lot N4 – Modèle de l'écran de fin de séance (sans affichage)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Modèle de l'écran de fin de séance, sans affichage | GDScript | K1, K5 (livrés) | Petite | **Livré le 25 octobre** (issue #103, PR #161) |

## 1. Objectif

Quand `session_state` passe à `FINISHED`, l'engine doit afficher un bilan lisible et proposer la suite (nouvelle séance, quitter). Ce lot écrit le **modèle de vue** de cet écran, sans affichage : textes, unités, arrondis, cas des champs absents, et l'écran de menu associé. L'affichage viendra avec N6.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/contracts/ipc_v1.md` §3 (`summary`) et §7.
2. `docs/lots/LOT_N1_contrat_ipc_v1_1.md` §4.3 (champs facultatifs du bilan enrichi, **proposés**).
3. Code : `engine/scripts/hud_view_model.gd` et `engine/scripts/erg_view_model.gd` (style des modèles sans nœud), `engine/scripts/menu_model.gd`, `core/src/openride_core/tools/session_summary.py` (définitions et format texte de `openride-core summary`).

## 3. Prérequis

Aucun. Le modèle lit les champs v1 de `summary` (`duration_s`, `distance_m`, `avg_power_w`, `fit_path`), présents sur `main`. Les champs enrichis du lot N1 sont lus **s'ils sont présents**, sous les noms du §4.3 de N1 ; si N1 les renomme avant fusion, la recette adapte les noms (une constante par champ, en tête du script).

## 4. Travail demandé

Nouveau `engine/scripts/summary_view_model.gd` (`extends RefCounted`, sans `class_name`) :

- `lines(summary: Dictionary, mode: String, ftp_w: int) -> Array` : lignes `{label, value, unit}` dans un ordre fixe : durée (`h:mm:ss`), distance (km, deux décimales), puissance moyenne, puissance normalisée, IF, TSS, dénivelé, cadence, FC moyenne, puissance max ; une ligne absente quand le champ manque ou vaut `null` (jamais « null » ni « 0 » inventé).
- `blocks(summary) -> Array` : en ERG, une ligne par bloc avec l'écart à la cible en W et en % (couleur : vert à ± 5 %, orange au-delà, rouge au-delà de 10 %).
- `fit_line(summary) -> String` : « Séance enregistrée : NOM.fit » ou « Séance non enregistrée » si `fit_path` vaut `null`, avec le nom du fichier seul (pas le chemin complet).
- `menu_screen() -> Dictionary` : écran au format de `menu_model.gd` avec « Nouvelle séance », « Voir le bilan détaillé » (blocs), « Quitter » (avec confirmation, règle de K5).
- Textes en français, nombres au format français (virgule décimale), comme `openride-core summary`.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/summary_view_model.gd`, `engine/tests/unit/test_summary_view_model.gd`.
- **Modifiés :** `engine/tests/README.md` (une ligne), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, scènes, `menu_model.gd`, contrat IPC.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Bilan v1 seul (4 champs) : 3 lignes et la ligne du FIT, aucune ligne vide ni « null ».
3. Bilan enrichi complet : 10 lignes dans l'ordre fixé ; 3 723 s affichées « 1:02:03 » ; 12 345 m affichés « 12,35 km ».
4. ERG avec 3 blocs à + 2 %, − 7 % et + 12 % de la cible : couleurs vert, orange, rouge.
5. `fit_path` à `null` : « Séance non enregistrée » ; chemin absolu : seul le nom du fichier apparaît.
6. L'écran de menu passe dans `menu_model.gd` : « Quitter » demande confirmation.
7. Aucun nœud créé (`Performance.OBJECT_NODE_COUNT`).

## 8. Hors périmètre

- Affichage de l'écran (N6).
- Calcul des valeurs (core, N2).

## 9. Livraison (25 octobre 2026, PR #161)

- Code et tests fusionnés sur `main` par la PR #161 (issue #103 fermée) ; détail dans la description de la PR et dans `docs/SUIVI_AVANCEMENT.md`.
