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
| [E1](LOT_E1_rendu_route_terrain.md) | Rendu 3D : ruban de route et terrain par tronçons | GDScript | A (livré), D ; tuiles du format (B2 ou générateur fourni) | Grande | **Livré le 24 octobre** (PR #7 ; essai sur la GTX 1060 à faire) |
| [F](LOT_F_erg_zwo.md) | Entraînements ERG : lecteur `.zwo` et pilotage ERG dans le core | Python | C (livré) | Moyenne | **Livré le 23 octobre** (essai ERG sur le Victory à faire) |
| [H1](LOT_H1_integration_continue.md) | Intégration continue GitHub Actions et fichier de contraintes (audit F6) | YAML | — | Petite | **Livré le 23 octobre** (PR #11) |
| [H2](LOT_H2_tests_ble.md) | Tests de la recherche Bluetooth sans matériel (audit F8) | Python | — | Petite | **Livré le 23 octobre** (PR #12, couverture 100 %) |
| [H3](LOT_H3_rejeu_mock.md) | Rejeu d'une séance réelle (JSONL ou FIT) dans le simulateur | Python | — | Petite | **Livré le 23 octobre** (PR #13) |
| [H4](LOT_H4_endurance_simulee.md) | Endurance simulée : séance de 3 h en temps accéléré (audit F7) | Python | — | Petite | **Livré le 23 octobre** (PR #14) |
| [H5](LOT_H5_validation_fit.md) | Validation des FIT par le SDK officiel Garmin | Python | — | Petite | **Livré le 23 octobre** (PR #15) |
| [H6](LOT_H6_analyse_journal.md) | Analyseur du journal de séance (`run_victory.log`) | Python | — | Petite | **Livré le 23 octobre** (PR #16) |
| [H7](LOT_H7_schema_themes.md) | Schéma, validateur et thème par défaut (prépare E2) | Python + JSON | — | Petite | **Livré le 23 octobre** (PR #17) |
| [H8](LOT_H8_outils_entrainements.md) | Outils et bibliothèque d'entraînements `.zwo` | Python | F (livré) | Petite | **Livré le 23 octobre** (PR #18) |
| [I1](LOT_I1_coherence_doc_code.md) | Tests de cohérence entre la documentation et le code | Python | — | Petite | **Livré le 23 octobre** (PR #20) |
| [I2](LOT_I2_catalogue_parcours.md) | Catalogue de parcours : `build-all` et `list` | Python | B2 (livré) | Petite | **Livré le 23 octobre** (PR #21) |
| [I3](LOT_I3_osm_batiments_forets.md) | Compilateur : couches OSM bâtiments et végétation | Python | B2 (livré) | Moyenne | **Livré le 23 octobre** (PR #22) |
| [I4](LOT_I4_osm_poi_eau.md) | Compilateur : couches points d'intérêt et eau | Python | I3 | Petite | **Livré le 23 octobre** (PR #23) |
| [I5](LOT_I5_chargeur_themes_godot.md) | Chargeur de thèmes en GDScript (sans shader) | GDScript | H7 (livré), E1 fusionné | Petite | **Livré le 23 octobre** (PR #24) |
| [I6](LOT_I6_logique_erg_godot.md) | Logique de l'entraînement ERG côté Godot (bandeau, bip, histogramme, sans affichage) | GDScript | F (livré), E1 fusionné | Petite | **Livré le 23 octobre** (PR #25) |
| [J1](LOT_J1_lancement_parcours_entrainement.md) | Lancer une séance sur un parcours et un entraînement choisis (`run --route`, `--workout`) | Python | — | Petite | **Livré le 24 octobre** (fait directement, issue #49) |
| [J2](LOT_J2_ipc_messages_malformes.md) | Robustesse du serveur IPC face aux messages malformés | Python | — | Petite | **Livré le 23 octobre** (fait directement) |
| [J3](LOT_J3_configuration_validee.md) | Configuration validée (types, bornes) et erreurs lisibles | Python | — | Petite | **Livré le 23 octobre** (fait directement) |
| [J4](LOT_J4_paquetage_autonome.md) | Paquets installables hors du dépôt (dépendance `jsonschema`, ressources embarquées) | Python | — | Petite | Oui (dépendance `jsonschema` faite ; reste les ressources embarquées) |
| [J5](LOT_J5_integration_continue_v2.md) | Intégration continue : chaque état de `main` testé, exécution hebdomadaire, actions à jour | YAML | — | Petite | Oui (concurrence, hebdomadaire, `pip check` et actions faits ; reste JUnit) |
| [J6](LOT_J6_parite_catalogue.md) | Une seule logique de catalogue des parcours (core et repli du compilateur) | Python | — | Petite | **Livré le 23 octobre** (fait directement) |
| [J7](LOT_J7_coherence_doc_etendue.md) | Cohérence de la documentation, deuxième passe (caractères, liens, nombres de tests) | Python | — | Petite | **Livré le 23 octobre** (fait directement) |
| [J8](LOT_J8_bout_en_bout_sans_ecran.md) | Essai de bout en bout sans écran : vrai core et vrai engine | Bash + Python | J5 (`openride.yml`) | Moyenne | **Livré le 23 octobre** (fait directement) |
| [K6](LOT_K6_lanceur_unique.md) | Lanceur unique `openride` : core et Godot supervisés, arrêt propre | Python | — | Petite | **Livré le 23 octobre** (fait directement ; cahier rédigé le 24 octobre) |
| [K7](LOT_K7_bilan_seance.md) | Bilan de séance `openride-core summary` (NP, IF, TSS, zones) | Python | — | Petite | **Livré le 23 octobre** (fait directement ; cahier rédigé le 24 octobre) |
| [K1](LOT_K1_tests_godot_par_decouverte.md) | Tests Godot sans écran lancés par découverte (`engine/tests/unit/`) | Bash + GDScript | E1 fusionné | Petite | **Livré le 24 octobre** (PR #38) |
| [K2](LOT_K2_modele_hud_profil.md) | Modèle de vue du HUD et profil d'altitude, sans affichage (prépare E3) | GDScript | K1 | Petite | **Livré le 24 octobre** (PR #39) |
| [K3](LOT_K3_placement_vegetation.md) | Placement déterministe de la végétation, sans affichage (prépare E3 et E4) | GDScript | K1 | Petite | **Livré le 24 octobre** (PR #40) |
| [K4](LOT_K4_lecture_couches_osm_godot.md) | Lecture des couches OSM dans l'engine, sans affichage (prépare E4) | GDScript + Python | K1, I3, I4 (livrés) | Moyenne | **Livré le 24 octobre** (PR #41) |
| [K5](LOT_K5_navigation_menus.md) | Navigation des menus au Click, machine à états sans affichage (prépare G) | GDScript | K1 | Petite | **Livré le 24 octobre** (PR #42) |
| [K8](LOT_K8_diagnostic_click.md) | Diagnostic des déconnexions du Zwift Click (journal et analyseur) | Python | — | Petite | **Livré le 24 octobre** (PR #34 ; séance de 20 min avec le Click à faire) |
| [L1](LOT_L1_maillage_batiments.md) | Maillage des bâtiments extrudés, sans affichage (prépare E4) | GDScript | K1 (livré) | Petite | **Livré le 24 octobre** (PR #64, issue #53) |
| [L2](LOT_L2_maillage_eau.md) | Maillage de l'eau : rivières en ruban et lacs avec îles, sans affichage | GDScript | K1 (livré) | Petite | **Livré le 24 octobre** (PR #65, issue #54) |
| [L3](LOT_L3_parametres_rendu_theme.md) | Paramètres de rendu tirés du thème et fonction de référence du mélange herbe, roche, neige (prépare E2) | GDScript | K1, I5 (livrés) | Petite | **Livré le 24 octobre** (PR #66, issue #55) |
| [L4](LOT_L4_prereglages_qualite.md) | Préréglages de qualité et thème transmis du lanceur à l'engine | GDScript + Python | K1, K6 (livrés) | Petite | **Livré le 24 octobre** (PR #67, issue #56) |
| [L5](LOT_L5_modele_sonore.md) | Modèle sonore sans affichage : vent, roue libre, points d'intérêt | GDScript | K1 (livré) | Petite | **Livré le 24 octobre** (PR #68, issue #57) |
| [L6](LOT_L6_cible_erg_journal.md) | Cible ERG enregistrée dans le journal de séance | Python | — | Petite | **Livré le 24 octobre** (PR #69, issue #58) |
| [L7](LOT_L7_historique_seances.md) | Historique des séances : `openride-core history` | Python | — | Petite | **Livré le 24 octobre** (PR #70, issue #59) |
| [L8](LOT_L8_raccourci_bureau.md) | Raccourci de bureau : fichier `.desktop`, icône, script d'installation | Bash | — | Petite | **Livré le 24 octobre** (PR #71, issue #60) |
| [M1](LOT_M1_erreur_att_renvoi.md) | Erreur d'écriture du Control Point (ATT 0x80) : renvoyer la commande au lieu de reconnecter | Python | — | Petite | **Livré le 24 octobre** (issue #78) |
| [M2](LOT_M2_ceinture_cardio_reelle.md) | Ceinture cardio réelle : mesure complète, contact, choix de l'appareil, batterie | Python | — | Petite | **Livré le 24 octobre** (issue #79) |
| [M3](LOT_M3_inventaire_appareils.md) | Inventaire des appareils Bluetooth : `openride-core devices` | Python | — | Petite | **Livré le 24 octobre** (issue #80) |
| [M4](LOT_M4_journal_biais_coupures.md) | Journal de séance : biais ERG et coupures des appareils | Python | — | Petite | **Livré le 24 octobre** (issue #81) |
| [M5](LOT_M5_scenario_depuis_journal.md) | Rejouer une panne réelle : scénario de simulation tiré de `run_victory.log` | Python | — | Petite | **Livré le 24 octobre** (issue #82) |
| [M6](LOT_M6_matrice_scenarios_simules.md) | Recette sans matériel : chaque scénario simulé joué en séance complète | Python | — | Petite | **Livré le 24 octobre** (issue #83) |
| [M7](LOT_M7_compilateur_fit_tcx.md) | Compilateur : parcours depuis un fichier FIT ou TCX | Python | — | Petite | **Livré le 24 octobre** (issue #84) |
| [M8](LOT_M8_journal_lanceur.md) | Journal du lanceur sans terminal (sortie de Godot, rotation) | Python | — | Petite | **Livré le 24 octobre** (issue #85) |
| [M9](LOT_M9_dette_r3_s2.md) | Petite dette des vérifications du 24 octobre (R3 et S2) | Python | — | Petite | Oui (issue #86) |
| [E2](LOT_E2_shader_triplanaire_theme.md) | Shader triplanaire et application du thème (terrain, route, soleil) | GDScript + shader Godot | E1, I5, L3 (livrés) | Moyenne | **Livré le 24 octobre** (PR #75, corrigée après revue ; essai sur la GTX 1060 à faire) |
| [E3](LOT_E3_ciel_arbres_hud.md) | Ciel physique, brouillard, arbres par bruit, HUD final avec profil d'altitude | GDScript + shader Godot | E2 (PR #75), K2, K3, L3, L4 (livrés) | Grande | Non : interne (contrôle visuel sur la GTX 1060), cahier rédigé le 24 octobre |
| [E4](LOT_E4_osm_eau_sons.md) | Bâtiments, forêts OSM, eau et sons du parcours | GDScript | E3, K3, K4, L1, L2, L5 (livrés sauf E3) | Grande | Non : interne (contrôle visuel et sonore), cahier rédigé le 24 octobre |

**Restent en interne** (matériel nécessaire) :
- stabilité du Zwift Click (déconnexions spontanées) ;
- essais sur le vélo ;
- validation des fichiers FIT dans GoldenCheetah et Garmin Connect.

**À rédiger plus tard** (contrôle visuel ou décision de Laurent nécessaire) :
- F2 : affichage du bandeau ERG, de l'histogramme et son du bip (s'appuie sur I6) ;
- G : contrat IPC v1.1 (listes de parcours et d'entraînements, état des appareils), affichage des menus pilotés au Click et écran de fin de séance (s'appuie sur I2, K5, K6 et K7).

Leur forme dépendra des choix faits dans E1 et D.

**Ordre conseillé :** A, A2, B1, B2, C, D, F, H1 à H8 et I1 à I6 sont livrés (23 octobre). E1 est livré (PR #7, fusionnée le 24 octobre) ; reste l'essai sur le PC cible. I5 et I6 ont été fusionnés **avant** E1, contrairement à l'ordre prévu ; le conflit qui en résultait dans `engine/tests/` est résolu sur la branche d'E1 (les trois étapes rendu, thèmes et ERG s'enchaînent). Série J (audit J du 23 octobre au soir) : J2, J3, J6, J7 et J8 sont livrés, J4 et J5 en partie ; J1 et le reste de J4 et J5 peuvent démarrer en parallèle. J1 est le plus utile pour les essais sur le vélo (parcours compilés et essai ERG).

**Série K (23 octobre au soir) :** tous les lots sont livrés le 24 octobre (K6 et K7 faits directement le 23). K2 à K5 déposent leur test dans `engine/tests/unit/` (découverte par `run_engine_tests.sh`, lot K1). Les lots K préparent E3 (K2, K3), E4 (K3, K4) et G (K5, K6, K7) sans les remplacer : le rendu, l'affichage et le contrat IPC v1.1 restent internes.

**Série M (24 octobre, après le Bluetooth simulé de la PR #74) :** neuf lots Python, tous délégables et testés sans matériel grâce au simulateur (`docs/SIMULATION_BLE.md`). Aucun ne touche l'engine, réservé à E2, E3 et E4. Fichiers partagés : `__main__.py` (M3 seul) ; `ble_sim.py` et `sim_scenarios.py` (M2 seul ; M1, M5 et M6 les lisent) ; `test_ble_sim.py` (M1 seul ; M4 et M6 ont leur propre fichier de tests) ; `compiler/pyproject.toml` (M7 `dependencies`, M9 extra `dev`) ; `docs/SIMULATION_BLE.md` (M1, M2, M5, M6, sections différentes). M6 ne vérifie que des invariants vrais avant et après M1. Les noms « M1 » à « M9 » du tableau des constats de l'audit du 23 octobre (`docs/AUDIT_2026-10-23.md` §3) n'ont aucun rapport avec ces lots.

**Série L (24 octobre) :** tous les lots L1 à L8 sont livrés le 24 octobre (PR #64 à #71). L1 à L5 (GDScript, sans affichage) déposent leur test dans `engine/tests/unit/` ; L4 modifie aussi `engine_args.gd` et `launcher.py` ; L6 à L8 enrichissent le journal (cible ERG), le core (`history`) et le bureau (`.desktop`).

**Lots H, I, J, K, L et M (23 et 24 octobre) :** ces séries sont faites pour une IA externe : recette entièrement automatique, sans essai sur le matériel. Aucun lot des séries I, J, K, L et M ne touche `main.gd` ni les scripts de rendu d'E1. Fichiers partagés dans la série J : `.github/workflows/openride.yml` (J5 puis J8) ; J1 touche `__main__.py`, déjà modifié par J3 (livré) ; `docs/SUIVI_AVANCEMENT.md` est commun à tous (une ligne chacun, à fusionner à la main).

**Lots H, détail :** petits lots hors du chemin critique, recettés uniquement par des tests automatiques, sans essai sur le matériel. Ils peuvent être confiés en parallèle : aucun ne partage de fichier de code avec un autre (seuls `docs/SUIVI_AVANCEMENT.md` et parfois `README.md` sont communs, à fusionner à la main). H3 est le seul à toucher `config.py`, `session.py` et `__main__.py` ; H5 et H4 touchent tous deux `core/pyproject.toml` (sections différentes).

Les lots livrés gardent leur cahier des charges, complété d'une section « Livraison » qui liste les écarts assumés.

```text
A ──► B1 ──► B2 ──┬──► E1 ──┬──► I5 ──► E2
│                 │          └──► I6 ──► F2
└──► D ───────────┘
B2 ──► I2 ──► G       B2 ──► I3 ──► I4 ;  I3 ──► E4
C ──► F ──► H8        H1 à H8, I1 : indépendants
J4, J5 : indépendants (J1, J2, J3, J6, J7, J8 livrés)
K6, K7, K8 : indépendants (livrés)
E1 ──► K1 ──► K2, K3, K4, K5 (livrés ; préparent E3, E4 et G)
E2 ──► E3 ──► E4 ;  K2, K3, L3, L4 ──► E3 ;  K4, L1, L2, L5 ──► E4
K1 ──► L1, L2, L3, L4, L5 ;  L6, L7, L8 : indépendants
M1 à M9 : indépendants (simulateur Bluetooth de la PR #74)
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
- Le matériel (Victory, Click) n'est pas disponible pour l'IA. Tout ce qui dépend du matériel se teste avec les doublures existantes (`MockDriver`, faux clients BLE dans `core/tests/test_drivers_session.py`). Les essais réels sont listés dans le rapport pour le propriétaire.

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

## 5. Partage des lots par issues GitHub

Depuis le 24 octobre, chaque lot ouvert a une issue GitHub, rattachée à l'issue de suivi [#48](https://github.com/Holeinthesock67/lolo_python/issues/48). Étiquettes : `lot`, `délégable` (recette automatique, sans matériel), `série J`, `série L` ou `série M`, langage (`python`, `gdscript`, `ci`) et `bloqué` tant qu'un prérequis n'est pas sur `main`.

1. Choisir une issue ouverte sans l'étiquette `bloqué`, sans assigné ni commentaire « Je prends ce lot ».
2. Commenter « Je prends ce lot » sur l'issue, pour que deux IA ne fassent pas le même lot.
3. Suivre le message du §4, puis écrire `Closes #<numéro de l'issue>` dans la description de la pull request : l'issue se ferme à la fusion.
4. Le propriétaire fusionne ; l'IA ne fusionne pas.

Un nouveau lot reçoit son issue au moment où son cahier est ajouté à l'index.
