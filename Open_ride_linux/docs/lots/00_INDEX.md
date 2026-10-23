# Lots de travail sous-traitables – index et règles communes

23 octobre 2026. Ces cahiers des charges permettent de confier une partie d'OpenRide à une autre IA (ou à un développeur) sans le contexte des conversations précédentes. Chaque lot est **autonome** : il dit quoi lire, quoi produire, quels fichiers toucher et comment la livraison sera recettée.

## 1. Liste des lots

| Lot | Titre | Langage | Dépend de | Taille | Prêt à confier |
| --- | --- | --- | --- | --- | --- |
| [A](LOT_A_route.md) | Lecteur `.world` et interpolation de route partagés core/engine | Python + GDScript | — | Moyenne | **Livré le 23 octobre** |
| [A2](LOT_A2_trace_demo.md) | Tracé de démonstration sans recouvrement (lacet) | Python | A (livré) | Petite | **Livré le 23 octobre** |
| [B1](LOT_B1_compilateur_route.md) | Compilateur : GPX vers `.world` (couche route) | Python | Aucune (A, livré, sert à la vérification croisée) | Moyenne | **Livré le 23 octobre** (fusionné ; 53 tests revérifiés le 23 octobre) |
| [B2](LOT_B2_compilateur_terrain.md) | Compilateur : couche terrain (MNT Copernicus, tuiles) | Python | B1 | Grande | **Livré le 23 octobre** |
| [C](LOT_C_core_conformite.md) | Mise en conformité du core avec le contrat IPC (défauts de l'audit) | Python | — | Petite | **Livré le 23 octobre** |
| [D](LOT_D_engine_ipc.md) | Mise en conformité de l'engine avec le contrat IPC | GDScript | A (livré) | Moyenne | **Livré le 23 octobre** (tests sans écran 8/8 revérifiés) |
| [E1](LOT_E1_rendu_route_terrain.md) | Rendu 3D : ruban de route et terrain par tronçons | GDScript | A (livré), D ; tuiles du format (B2 ou générateur fourni) | Grande | Oui (A et D livrés) |
| [F](LOT_F_erg_zwo.md) | Entraînements ERG : lecteur `.zwo` et pilotage ERG dans le core | Python | C (livré) | Moyenne | **Livré le 23 octobre** (essai ERG sur le HomeTrainer à faire) |
| [H1](LOT_H1_integration_continue.md) | Intégration continue GitHub Actions et fichier de contraintes (audit F6) | YAML | — | Petite | **Livré le 23 octobre** (PR #11) |
| [H2](LOT_H2_tests_ble.md) | Tests de la recherche Bluetooth sans matériel (audit F8) | Python | — | Petite | **Livré le 23 octobre** (PR #12, couverture 100 %) |
| [H3](LOT_H3_rejeu_mock.md) | Rejeu d'une séance réelle (JSONL ou FIT) dans le simulateur | Python | — | Petite | **Livré le 23 octobre** (PR #13) |
| [H4](LOT_H4_endurance_simulee.md) | Endurance simulée : séance de 3 h en temps accéléré (audit F7) | Python | — | Petite | **Livré le 23 octobre** (PR #14) |
| [H5](LOT_H5_validation_fit.md) | Validation des FIT par le SDK officiel Garmin | Python | — | Petite | **Livré le 23 octobre** (PR #15) |
| [H6](LOT_H6_analyse_journal.md) | Analyseur du journal de séance (`run_trainer.log`) | Python | — | Petite | **Livré le 23 octobre** (PR #16) |
| [H7](LOT_H7_schema_themes.md) | Schéma, validateur et thème par défaut (prépare E2) | Python + JSON | — | Petite | **Livré le 23 octobre** (PR #17) |
| [H8](LOT_H8_outils_entrainements.md) | Outils et bibliothèque d'entraînements `.zwo` | Python | F (livré) | Petite | **Livré le 23 octobre** (PR #18) |
| [I1](LOT_I1_coherence_doc_code.md) | Tests de cohérence entre la documentation et le code | Python | — | Petite | **Livré le 23 octobre** (PR #20) |
| [I2](LOT_I2_catalogue_parcours.md) | Catalogue de parcours : `build-all` et `list` | Python | B2 (livré) | Petite | **Livré le 23 octobre** (PR #21) |
| [I3](LOT_I3_osm_batiments_forets.md) | Compilateur : couches OSM bâtiments et végétation | Python | B2 (livré) | Moyenne | **Livré le 23 octobre** (PR #22) |
| [I4](LOT_I4_osm_poi_eau.md) | Compilateur : couches points d'intérêt et eau | Python | I3 | Petite | **Livré le 23 octobre** (PR #23) |
| [I5](LOT_I5_chargeur_themes_godot.md) | Chargeur de thèmes en GDScript (sans shader) | GDScript | H7 (livré), E1 fusionné | Petite | **Livré le 23 octobre** (PR #24) |
| [I6](LOT_I6_logique_erg_godot.md) | Logique de l'entraînement ERG côté Godot (bandeau, bip, histogramme, sans affichage) | GDScript | F (livré), E1 fusionné | Petite | **Livré le 23 octobre** (PR #25) |
| [J1](LOT_J1_lancement_parcours_entrainement.md) | Lancer une séance sur un parcours et un entraînement choisis (`run --route`, `--workout`) | Python | — | Petite | Oui |
| [J2](LOT_J2_ipc_messages_malformes.md) | Robustesse du serveur IPC face aux messages malformés | Python | — | Petite | **Livré le 23 octobre** (fait directement) |
| [J3](LOT_J3_configuration_validee.md) | Configuration validée (types, bornes) et erreurs lisibles | Python | — | Petite | **Livré le 23 octobre** (fait directement) |
| [J4](LOT_J4_paquetage_autonome.md) | Paquets installables hors du dépôt (dépendance `jsonschema`, ressources embarquées) | Python | — | Petite | Oui (dépendance `jsonschema` faite ; reste les ressources embarquées) |
| [J5](LOT_J5_integration_continue_v2.md) | Intégration continue : chaque état de `main` testé, exécution hebdomadaire, actions à jour | YAML | — | Petite | Oui (concurrence, hebdomadaire, `pip check` et actions faits ; reste JUnit) |
| [J6](LOT_J6_parite_catalogue.md) | Une seule logique de catalogue des parcours (core et repli du compilateur) | Python | — | Petite | Oui |
| [J7](LOT_J7_coherence_doc_etendue.md) | Cohérence de la documentation, deuxième passe (caractères, liens, nombres de tests) | Python | — | Petite | Oui |
| [J8](LOT_J8_bout_en_bout_sans_ecran.md) | Essai de bout en bout sans écran : vrai core et vrai engine | Bash + Python | J5 (`openride.yml`) | Moyenne | Après J5 |
| [K1](LOT_K1_tests_godot_par_decouverte.md) | Tests Godot sans écran lancés par découverte (`engine/tests/unit/`) | Bash + GDScript | E1 fusionné | Petite | Après la fusion de la PR #7 |
| [K2](LOT_K2_modele_hud_profil.md) | Modèle de vue du HUD et profil d'altitude, sans affichage (prépare E3) | GDScript | K1 | Petite | Après K1 |
| [K3](LOT_K3_placement_vegetation.md) | Placement déterministe de la végétation, sans affichage (prépare E3 et E4) | GDScript | K1 | Petite | Après K1 |
| [K4](LOT_K4_lecture_couches_osm_godot.md) | Lecture des couches OSM dans l'engine, sans affichage (prépare E4) | GDScript + Python | K1, I3, I4 (livrés) | Moyenne | Après K1 |
| [K5](LOT_K5_navigation_menus.md) | Navigation des menus au Click, machine à états sans affichage (prépare G) | GDScript | K1 | Petite | Après K1 |
| [K6](LOT_K6_lanceur_supervision.md) | Lanceur unique `openride` et supervision du core et de l'engine | Python | — | Moyenne | Oui |
| [K7](LOT_K7_bilan_seance.md) | Bilan d'une séance : `openride-core summary` (NP, IF, TSS, zones, records) | Python | — | Petite | Oui |
| [K8](LOT_K8_diagnostic_click.md) | Diagnostic des déconnexions du Zwift Click (journal et analyseur) | Python | — | Petite | Oui |

**Restent en interne** (matériel nécessaire) :
- stabilité du Zwift Click (déconnexions spontanées) ;
- essais sur le vélo ;
- validation des fichiers FIT dans GoldenCheetah et Garmin Connect.

**À rédiger plus tard** (contrôle visuel ou décision du propriétaire nécessaire) :
- E2 : shader triplanaire et application du thème (s'appuie sur I5) ;
- E3 : ciel, végétation par bruit, HUD final avec profil d'altitude (s'appuie sur K2 et K3) ;
- E4 : rendu des bâtiments, des forêts, de l'eau et sons des points d'intérêt (s'appuie sur I3, I4, K3 et K4) ;
- F2 : affichage du bandeau ERG, de l'histogramme et son du bip (s'appuie sur I6) ;
- G : contrat IPC v1.1 (listes de parcours et d'entraînements, état des appareils), affichage des menus pilotés au Click et écran de fin de séance (s'appuie sur I2, K5, K6 et K7).

Leur forme dépendra des choix faits dans E1 et D.

**Ordre conseillé :** A, A2, B1, B2, C, D, F, H1 à H8 et I1 à I6 sont livrés (23 octobre). E1 est fait et attend l'essai sur le PC cible (PR #7). I5 et I6 ont été fusionnés **avant** E1, contrairement à l'ordre prévu ; le conflit qui en résultait dans `engine/tests/` est résolu sur la branche d'E1 (les trois étapes rendu, thèmes et ERG s'enchaînent). Série J (audit J du 23 octobre au soir) : J2 et J3 sont livrés, J4 et J5 en partie ; J1, le reste de J4 et J5, J6 et J7 peuvent démarrer en parallèle, J8 après J5. J1 est le plus utile pour les essais sur le vélo (parcours compilés et essai ERG). Le conflit de la PR #7 avec `main` a été résolu sur sa branche le 23 octobre au soir.

**Série K (23 octobre au soir) :** K6, K7 et K8 (Python) peuvent démarrer tout de suite, en parallèle de J1 et des lots J restants. K1 attend la fusion de la PR #7 (E1), puis K2 à K5 (GDScript, sans affichage) peuvent partir en parallèle : chacun dépose son test dans `engine/tests/unit/` et ne touche plus `run_engine_tests.sh` (sauf K4, une étape de génération de données). J1, K7 et K6 modifient `__main__.py` ou `pyproject.toml` du core : fusionner l'un après l'autre. Les lots K préparent E3 (K2, K3), E4 (K3, K4) et G (K5, K6, K7) sans les remplacer : le rendu, l'affichage et le contrat IPC v1.1 restent internes.

**Lots H, I, J et K (23 octobre) :** ces séries sont faites pour une IA externe : recette entièrement automatique, sans essai sur le matériel. Aucun lot des séries I, J et K ne touche `main.gd` ni les scripts de rendu d'E1. Fichiers partagés dans la série J : `.github/workflows/openride.yml` (J5 puis J8) ; J1 touche `__main__.py`, déjà modifié par J3 (livré) ; `docs/SUIVI_AVANCEMENT.md` est commun à tous (une ligne chacun, à fusionner à la main).

**Lots H, détail :** petits lots hors du chemin critique, recettés uniquement par des tests automatiques, sans essai sur le matériel. Ils peuvent être confiés en parallèle : aucun ne partage de fichier de code avec un autre (seuls `docs/SUIVI_AVANCEMENT.md` et parfois `README.md` sont communs, à fusionner à la main). H3 est le seul à toucher `config.py`, `session.py` et `__main__.py` ; H5 et H4 touchent tous deux `core/pyproject.toml` (sections différentes).

Les lots livrés gardent leur cahier des charges, complété d'une section « Livraison » qui liste les écarts assumés.

```text
A ──► B1 ──► B2 ──┬──► E1 ──┬──► I5 ──► E2
│                 │          └──► I6 ──► F2
└──► D ───────────┘
B2 ──► I2 ──► G       B2 ──► I3 ──► I4 ;  I3 ──► E4
C ──► F ──► H8        H1 à H8, I1 : indépendants
J5 ──► J8             J1, J4, J6, J7 : indépendants (J2, J3 livrés)
E1 ──► K1 ──┬──► K2 ──► E3        K3 ──► E3, E4      K4 ──► E4
            ├──► K3              K5, K6, K7 ──► G
            ├──► K4              K6, K7, K8 : indépendants
            └──► K5
```

## 2. Prérequis côté propriétaire du projet (avant de confier un lot)

1. Partir de `main` à jour (fusions du 23 octobre faites).
2. Donner à l'IA un accès en écriture au dépôt `Holeinthesock67/lolo_python`, ou lui remettre une copie et récupérer un correctif.
3. Lui transmettre le texte du lot et les documents listés dans sa section « À lire ».

## 3. Règles communes à tous les lots

**Documents qui font loi.** `docs/SRS_v1.1.md`, `docs/contracts/ipc_v1.md`, `docs/contracts/world_format_v1.md` et les schémas JSON de `docs/contracts/`.
- Un lot ne modifie un contrat que si sa section « Modifications de contrat autorisées » le prévoit.
- Si le travail révèle qu'un contrat est faux ou incomplet, l'IA **s'arrête et le signale** dans son rapport, au lieu de l'interpréter.

**Dépôt.**
- Le projet est dans le dossier `Open_ride_linux/` du dépôt `lolo_python`, qui contient d'autres projets sans rapport : ne rien toucher en dehors de `Open_ride_linux/`.
- Chaque lot se fait sur une branche `lot-<id>-<sujet>` partant de `main` à jour. Une demande de fusion (pull request) par lot.
- Ne modifier que les fichiers listés dans « Fichiers concernés ». Un fichier supplémentaire indispensable est signalé et justifié dans le rapport.

**Code.**
- **Python :**
  - version 3.11 minimum, et le code doit aussi tourner en 3.14 (version du PC cible) ;
  - typage avec annotations et dataclasses comme dans le code existant ;
  - aucune entrée-sortie bloquante dans la boucle du core.
- **GDScript :**
  - Godot 4.3 ;
  - pas de `class_name` pour les scripts dont dépend la scène principale : l'engine est lancé sans passer par l'éditeur, et Godot ne connaît alors pas les `class_name`. Utiliser `preload`.
- **Langue :** commentaires, docstrings et messages de journal en français ; identifiants en anglais.
- **Dépendances :** toute nouvelle dépendance est déclarée dans le `pyproject.toml` concerné et justifiée dans le rapport. Pas de bibliothèque pour ce que la bibliothèque standard ou une dépendance existante fait déjà.
- **Hors ligne :** aucun accès réseau à l'exécution, sauf dans le lot B2, qui télécharge des tuiles d'altitude dans un cache.

**Tests.**
- Chaque critère d'acceptation vérifiable par machine a son test automatique.
- `pytest` passe en entier (tests existants compris) dans `Open_ride_linux/core/` et, s'il existe, dans `Open_ride_linux/compiler/`.
- Côté Godot, les tests se lancent sans écran : `godot --headless --path engine ...` (Godot 4.3 officiel, téléchargeable sur GitHub).
- Le matériel (HomeTrainer, Click) n'est pas disponible pour l'IA. Tout ce qui dépend du matériel se teste avec les doublures existantes (`MockDriver`, faux clients BLE dans `core/tests/test_drivers_session.py`). Les essais réels sont listés dans le rapport pour le propriétaire.

**Livraison.** La demande de fusion contient :
1. le résumé de ce qui a été fait ;
2. la liste des critères d'acceptation, cochés, avec la commande qui les prouve ;
3. la sortie des tests ;
4. les écarts ou questions ouvertes ;
5. les essais à faire sur le matériel, s'il y en a.

**Recette.** Le propriétaire (ou Claude) relit la demande, relance les tests, vérifie les critères et fait les essais réels. Un critère non tenu renvoie le lot.

## 4. Modèle de message pour confier un lot

```text
Tu travailles sur OpenRide Linux, dépôt GitHub Holeinthesock67/lolo_python, dossier Open_ride_linux/.
Lis d'abord docs/lots/00_INDEX.md (règles communes), puis docs/lots/LOT_<X>_....md (ton lot), puis
les documents listés dans sa section « À lire ». Respecte strictement les fichiers autorisés et les
contrats. Crée la branche lot-<x>-<sujet> depuis main, fais le travail, fais passer tous les tests,
puis ouvre une pull request avec la liste des critères d'acceptation cochés et la sortie des tests.
Si un contrat te semble faux ou incomplet, arrête-toi et pose la question au lieu d'improviser.
```
