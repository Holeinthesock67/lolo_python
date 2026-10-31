# Lot Y7 – Essai du moteur de rendu Mobile pour le préréglage `low` (mesure seule)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Essai du moteur Mobile pour `low` (mesure seule, décision du propriétaire) | GDScript | Y2 | Petite | Oui (mesure) ; issue #363 |

## 1. Objectif

Série Y (fin de projet, `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` §4, technique T13). Tous les préréglages tournent avec le moteur Forward+. Le moteur Mobile de Godot n'a pas de pré-passe de profondeur et peut être plus rapide sur une scène simple, mais il n'a ni SSAO, ni SSIL, ni brouillard volumétrique, ni TAA, ni FSR, et certains shaders peuvent s'y rendre autrement. Décision du propriétaire du 27 octobre (§0, question 8) : **essai mesuré maintenu, décision après la mesure**.

Ce lot ne change rien par défaut : il mesure `low` en Mobile contre `low` en Forward+, compare les images, et rend un rapport avec une recommandation.

## 2. À lire

1. `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` §4 (T13) ; documentation de Godot « Renderers » (tableau des fonctions par moteur) et « Occlusion culling ».
2. `docs/OUTILS_DE_TEST.md` (banc simulé, sonde X13) ; cahier Y13 (PR #446) §5 (effets de `low`).
3. Code : `engine/tests/sim_bench.py`, `engine/tests/visual_check.py`, `engine/scripts/engine_args.gd`, `render_quality.gd`, les shaders de `engine/shaders/` ; `core/src/openride_core/launcher.py` (lancement de l'engine).

## 3. Prérequis

Y2 livré (le moteur Mobile s'est amélioré en 4.6 : désaturation et précision HDR) ; Y4 et Y6 utiles (base de mesure de `low` stable).

## 4. Travail demandé

- **Lancement en Mobile pour l'essai** : option `--renderer=mobile` de `sim_bench.py` et de `visual_check.py`, qui passe `--rendering-method mobile` à Godot ; aucun changement du lanceur ni de `project.godot`.
- **Mesure** sur le PC cible, PC au calme : banc simulé `montee_descente`, mondes `village` et OSM, `low` en Forward+ puis en Mobile, avec la sonde X13 (images/s médianes, p99, temps CPU et GPU, appels de dessin, VRAM).
- **Images** : `visual_check.py --native` en Mobile ; liste des scènes qui diffèrent de plus du seuil, avec la cause (shader du terrain E2, arbres, eau, faune, néon du Cyber-Rogue, brume de P17, particules) ; captures côte à côte.
- **Rapport** `docs/ESSAI_MOTEUR_MOBILE.md` : tableau des mesures, images, défauts à corriger si on adoptait Mobile, et recommandation (garder Forward+, ou passer `low` en Mobile avec la liste des corrections, qui feraient alors un lot à part).

## 5. Fichiers concernés

- **Modifiés :** `engine/tests/sim_bench.py`, `engine/tests/visual_check.py` (option d'essai seulement), `engine/tests/README.md`, `docs/OUTILS_DE_TEST.md` ; `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `docs/ESSAI_MOTEUR_MOBILE.md`.
- **Interdits :** `engine/project.godot`, le lanceur, les préréglages, les shaders (aucune correction dans ce lot).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `sim_bench.py --renderer=mobile` et `visual_check.py --renderer=mobile` lancent bien le moteur Mobile (vérifié dans le journal de Godot) ; sans l'option, rien ne change.
2. Rapport complet : mesures des deux moteurs sur les deux mondes, liste des différences d'image, recommandation.

**Sur le PC cible (le propriétaire) :** lancer les deux mesures (environ 10 min), regarder les captures ; **décider** de garder Forward+ ou de prévoir le passage de `low` en Mobile.

## 8. Hors périmètre

- Passage effectif de `low` en Mobile et corrections des shaders : lot à part, seulement si le propriétaire le décide.
- Moteur Compatibility (utilisé seulement par les tests sans carte graphique).
