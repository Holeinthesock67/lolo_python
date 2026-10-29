# Lot Y2 – Migration de Godot 4.3 vers 4.7.x

## 1. Objectif

Décision du propriétaire du 27 octobre (`docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` §0, question 5) : migrer directement vers Godot 4.7.x au début de la phase finale, **avant** les autres optimisations de la série Y, pour que leurs mesures partent de la bonne base. La migration apporte sans travail les ubershaders et la précompilation des pipelines (moins de saccades à la première apparition d'un objet, 4.4), l'interpolation physique en 3D (4.4), des LOD générés plus propres et un SSR plus rapide (4.6), un tampon de constantes par passe (4.7), et rend possibles le SMAA (4.5) et la tonalité AgX (4.4).

Le lot change de version, il n'ajoute aucune fonction : à la fin, le jeu fait la même chose qu'avant, au moins aussi vite, avec une image recettée par le propriétaire.

## 2. À lire

1. `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` §3 (apports et points de vigilance) et §5 (saccades) ; notes de version de Godot 4.4 à 4.7 et guides de mise à jour (« Upgrading from Godot 4.3 to 4.4 », puis 4.5, 4.6 et 4.7) de la documentation officielle.
2. `docs/OUTILS_DE_TEST.md` (banc simulé, sonde X13, seuils X2), `docs/ESSAI_GRAPHIQUE_E2.md` (recette visuelle), le cahier Y13 de la PR #446 (qualité d'image par préréglage, §7.3 : réglages à recaler après la migration).
3. Fichiers qui nomment la version : `engine/project.godot` (`config/features`), `scripts/install.sh`, `scripts/config.example.toml`, `scripts/recette_pc.py`, `scripts/recette_install.py`, `scripts/recette_install/check_install.sh`, `core/src/openride_core/config.py` (`[engine] godot`), `engine/tests/run_engine_tests.sh`, `run_visual_tests.sh`, `run_e2e.sh`, `e2e_check.py`, `.github/workflows/openride.yml` (à la racine du dépôt), `core/tests/test_recette_install.py`, `core/tests/test_launch_no_terminal.py`, `README.md`, `CLAUDE.md`, `docs/GUIDE_UTILISATION.md`.

## 3. Prérequis

Y1 livré, X2 et X13 (seuils et sonde) livrés. Phase finale ouverte par le propriétaire (« fin de projet » : les autres séries prévues avant sont fusionnées). Le jour du lot, choisir le dernier correctif 4.7.x stable publié et noter son numéro exact dans ce cahier.

## 4. Travail demandé

1. **Mesure de départ sur Godot 4.3**, sur le PC cible, PC au calme : `python3 engine/tests/sim_bench.py --native --probe` en `medium` puis en `low`, mondes `village` et OSM, scénario `montee_descente` ; garder `sonde.csv` et les lignes `[perf-rendu]`. Captures de `visual_check.py --native` en `low`, `medium` et `high`.
2. **Ouverture du projet en 4.7.x** : import sans écran (`--headless --import`), puis correction de chaque erreur et avertissement nouveau des scripts GDScript (types plus stricts, fonctions renommées ou retirées entre 4.4 et 4.7) ; aucun avertissement de plus qu'en 4.3 dans `run_engine_tests.sh`. Les fichiers `.uid` créés par l'éditeur depuis 4.4 sont versionnés. `config/features` passe à « 4.7 ». Le moteur de rendu reste Forward+ ; la physique reste celle de Godot (Jolt n'est pas imposé aux projets existants, ne pas l'activer ici).
3. **Outils et installation** : chaque fichier du §2.3 nomme 4.7 au lieu de 4.3 (chemin par défaut `Godot_v4.7…-stable_linux.x86_64`, vérification de version dans `install.sh` qui accepte `4.7*` et refuse 4.3 avec un message qui dit quoi télécharger) ; intégration continue : cache et téléchargement de la version retenue.
4. **Rendu à recaler** (aucune nouveauté, seulement retrouver l'image d'avant) : glow mélangé avant la tonalité depuis 4.6 (régler l'intensité pour retrouver l'aspect d'avant), shaders du terrain (E2), des arbres, de l'eau, de la faune et du néon du Cyber-Rogue (R17) relus, `MultiMesh` et `visibility_range` vérifiés. Ce qui relève du choix d'image (AgX, SMAA, glow nouveau) est fait ensuite par l'étape du cahier Y13 §7.3, pas ici.
5. **Mesure d'arrivée** : mêmes commandes qu'au point 1 ; tableau avant et après dans ce cahier (images/s médianes, p99, temps CPU et GPU, appels de dessin, VRAM). Captures avant et après côte à côte pour la recette du propriétaire.
6. **Retour arrière** : tant que le propriétaire n'a pas recetté, garder Godot 4.3 installé sur le PC (`[engine] godot` de `config.toml` peut y pointer) ; le lot ne supprime aucun binaire.

## 5. Fichiers concernés

- **Modifiés :** les fichiers du §2.3, les scripts `.gd` et les shaders qui ne passent plus en 4.7, `engine/tests/README.md`, `docs/OUTILS_DE_TEST.md`, `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Nouveaux :** fichiers `.uid` de l'éditeur.
- **Interdits :** le core (sauf le texte du chemin par défaut de Godot dans `config.py`), le compilateur, les contrats, toute fonction nouvelle.

## 6. Modifications de contrat autorisées

Aucune. Le prérequis d'installation change (Godot 4.7.x au lieu de 4.3) : le guide d'utilisation et le README le disent.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh`, `run_e2e.sh` et `visual_check.py --native` passent en entier avec Godot 4.7.x, sur le PC et dans l'intégration continue ; `pytest -q` du core et du compilateur passent.
2. Aucun avertissement GDScript de plus qu'en 4.3.
3. Banc simulé en `medium` et en `low` : images/s médianes égales ou meilleures, p99 égal ou meilleur à 1 ms près ; seuils X2 tenus.
4. `install.sh` sur un PC propre avec Godot 4.7.x : installation complète ; avec Godot 4.3 : refus clair.

**Sur le PC cible (le propriétaire) :** `essai-69` de 20 min en `medium` ; regarder les captures avant et après ; dire si l'image est acceptable (le glow et les couleurs peuvent avoir un peu bougé). La fusion attend cet accord.

## 8. Hors périmètre

- Nouveaux réglages d'image (AgX, SMAA, glow) : cahier Y13 §7.3 ; ombres : Y4 ; arbres lointains : Y5.
- Moteur Mobile : Y7 ; Jolt ; export en paquet autonome de Godot (J4).

## 9. Réalisation (29 octobre)

Version retenue : **Godot 4.7.2-stable** (dernier correctif publié ; 4.7.3 n'existe pas le 29 octobre). Godot 4.3 reste installé sur le PC cible pour le retour arrière (§4.6).

- **Import** (`--headless --import`) : aucune erreur ni avertissement ; les 280 fichiers `.uid` créés par l'éditeur sont versionnés ; `config/features` passe à « 4.7 ».
- **Outils et installation** : chemins par défaut, CI (cache et téléchargement de 4.7.2), `install.sh` (accepte `4.7*`, refuse 4.3 en donnant le lien de 4.7.2, testé dans `test_launch_no_terminal.py`), README, CLAUDE.md, guide, outils de test.
- **Corrections dues à 4.7** :
  - filtre des journaux : Godot 4.7 écrit « ObjectDB instances were leaked » (toléré comme avant) ;
  - ciel nuageux (`sky_clouds.gdshader`) : le `ProceduralSkyMaterial` de 4.7 calcule le dégradé sur les cosinus ; notre copie reprend la nouvelle formule et les mêmes conversions de réglages que le moteur (écart 0/255 avec le ciel du moteur en couverture 0) ;
  - FXAA demandé seulement en Forward+ (le moteur Compatibility l'avertit désormais), comme l'occlusion et la brume ;
  - `WorkoutChartModel.nice_ticks` : plus de `-0.0` (4.7 compare les tableaux bit à bit) ;
  - test des traînées : fond uni non teinté par le brouillard (`fog_sky_affect = 0`).
  - réglages chiffrés : depuis 4.4, `str()` d'un flottant entier garde « .0 » (« FTP — 250.0 W » relevé par le banc des menus en CI) ; `SettingsViewModel.number_text` rend « 250 » comme avant ; banc des menus 16/16 en 4.7.2.
- **Résultats dans le cloud** : `run_engine_tests.sh` 126/126, `run_e2e.sh` OK, `pytest` core 1601 et compilateur 420. Captures Forward+ (`visual_check.py --native`, lavapipe, 1280×720) : image quasi identique ; couleurs un peu plus froides en 4.7 (rouge −4 à −15, bleu +5 à +10 sur 255, moyenne du bas de l'image), y compris en `low` sans glow : l'écart vient de la lumière ambiante du nouveau ciel, pas du glow. Réglages du glow inchangés (Soft Light ; l'étape 4 d'Y13 le recale avec AgX).
- **Reste** : mesure avant et après sur le PC cible (§4.1 et §4.5) et recette du propriétaire.
