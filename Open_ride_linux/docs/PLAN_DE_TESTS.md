# OpenRide Linux – Plan de tests

Version du 29 octobre 2026 au soir. Ce document dit **quoi tester, où, comment le lancer et ce qu'on doit obtenir**. Le catalogue des commandes et de leurs options reste [OUTILS_DE_TEST.md](OUTILS_DE_TEST.md) ; le pas à pas des essais sur le PC et sur le vélo reste [PROTOCOLE_TEST_2026-10-26.md](PROTOCOLE_TEST_2026-10-26.md) ; la liste de ce qui reste à essayer sur le matériel est le §3 de [SUIVI_AVANCEMENT.md](SUIVI_AVANCEMENT.md). Toutes les commandes se lancent depuis `Open_ride_linux/`, `GODOT` désigne l'exécutable Godot 4.3.

## 1. Règles communes

- **Trois lieux d'exécution.** *Cloud* : la CI GitHub (`.github/workflows/openride.yml`) passe chaque PR et chaque envoi sur `main` ; c'est elle qui dit si une PR est verte. *PC cible* : tout ce qui demande la GTX 1060, le Bluetooth réel ou une fenêtre (`--native`), dans l'ordre de la file des mesures du PC (un seul usage à la fois, étapes de 10 minutes au plus, `config.toml` sauvegardé puis restauré). *Vélo* : le ressenti et le matériel, par étapes de 10 minutes au plus, précédées du pré-vol (§4.2).
- **Une suite à la fois.** pytest, `scripts/recette_pc.py`, `scripts/pre_vol.py`, `sim_bench.py`, `menu_bench.py` et `e2e_check.py` prennent le même verrou ; une deuxième suite attend la première, pour ne pas fausser les mesures.
- **Isolation.** Les suites pytest tournent dans un HOME temporaire (`scripts/isolation_tests.py`) ; un test qui écrit hors de son `tmp_path` échoue en nommant le fichier. Les bancs travaillent aussi dans un HOME temporaire et vérifient que le vrai `~/OpenRide` n'a pas bougé.
- **Aucun seuil de temps en dur** dans un test : il passe par `engine/tests/perf_budgets.json` (budget du PC et seuil de la CI) et `PerfBudget.check` ; `OPENRIDE_PERF=strict` fait échouer un dépassement.
- **Essai graphique = captures.** Tout essai de qualité graphique rend ses captures et ses chiffres (images/s, p99, GPU) au propriétaire, et la qualité réellement appliquée est contrôlée (§3.7).
- **Données privées.** Aucun nom, aucune position précise, aucune adresse Bluetooth réelle, aucun réglage personnel ni aucune trace réelle dans un test ou un rapport versionné (scanner du §3.11).
- **Résultat attendu partout :** code de sortie 0, aucune ligne `[ÉCHEC]`, aucune erreur ni avertissement Godot hors tolérances connues, aucun nombre de tests écrit en dur dans la doc (`python3 scripts/recompte_tests.py --verifier`).

## 2. Niveaux de test

| Niveau | Périmètre | Commande | Lieu | Durée | Réussite |
| --- | --- | --- | --- | --- | --- |
| Core | Physique, braquets, FTMS, Click, ceinture, séance, ERG, journal, FIT, IPC, réglages, séries R, T, V, W | `(cd core && pytest -q)` | Cloud (3.11, 3.14), PC | ~3 min | 0 échec ; `-m "not slow"` en ~20 s |
| Compilateur | GPX, FIT, TCX, route, terrain, OSM, thèmes, biomes, monde ouvert | `(cd compiler && pytest -q)` | Cloud, PC | ~1 min | 0 échec, sans réseau |
| Contrats | Schémas JSON, exemples du §7 d'`ipc_v1.md`, taille des trames, vecteurs de route | dans les suites core ; `python -m openride_core.tools.route_vectors --check` ; `python -m openride_core.ipc_budget` | Cloud | < 1 min | Exemples valides, pire trame sous 4 096 octets |
| Bluetooth simulé | Vrais pilotes devant un trainer, un Click et une ceinture simulés, pannes | `core/tests/test_ble_sim.py`, `core/tests/test_sim_matrix.py` ; `scripts/openride-dev.sh --trainer sim --input sim --hr sim --sim-scenario NOM` | Cloud, PC | ~1 min | Reprises sans reconnexion inutile, pauses attendues |
| Engine | Tests unitaires GDScript (découverte), rendus Xvfb, couches OSM, rendu par tronçons, ERG, 8 scénarios IPC face au faux core | `engine/tests/run_engine_tests.sh` | Cloud, PC | ~3 min | Toutes les lignes `[OK]`, aucune erreur Godot |
| Bout en bout | Vrai core (`mock`) et vrai engine | `engine/tests/run_e2e.sh` | Cloud, PC | ~10 s | 9 vérifications OK (§3.6) |
| Menus | Tous les menus au Click simulé, au clavier et à la souris | `python3 engine/tests/menu_bench.py` | Cloud (`--rotation`), PC (trois voies) | 10 à 25 min | Chaque scénario OK sur chaque voie |
| Graphique | Scène principale, HUD, lisibilité, débordements, qualité appliquée | `engine/tests/run_visual_tests.sh`, `engine/tests/hud_galerie.py` | PC | ~2 min | Contrôles OK, captures rendues |
| Banc simulé | Séances complètes sur Bluetooth simulé dans la vraie scène, captures et images/s | `python3 engine/tests/sim_bench.py --scenario NOM [--native --probe]` | PC (file des mesures) | 2 à 60 min | Contrôles OK ; images/s et p99 dans les budgets |
| Vitrines | Rendu, biomes, sols, comparés à une référence | `engine/tests/vitrine_rendu.gd`, `engine/tests/vitrine_biomes.gd`, `engine/tests/vitrine_sols.gd` | PC | 1 à 5 min | Pas de sol surexposé ; écarts sous `--max-diff` |
| Confidentialité | Données interdites dans les fichiers et les commits | `scripts/privacy/privacy_scan.py` | Cloud (chaque PR), crochet pre-commit | < 10 s | Aucune donnée trouvée |
| Recette PC | Toutes les suites d'un coup, comparées au passage précédent | `python3 scripts/recette_pc.py` | PC | ~40 min | Toutes les étapes OK |
| Pré-vol | Tout ce qui se vérifie sans pédaler avant une séance | `python3 scripts/pre_vol.py --seance NOM` | PC | ~3 min | « PRÊT À ROULER » |
| Vélo | Ressenti, matériel réel, recettes guidées | outils du §4.3 | Vélo | 10 min par étape | Cases cochées dans le protocole |

## 3. Détail par niveau

### 3.1 Core (`core/tests/`)

Périmètre : tout le code Python du core, sans matériel. Familles principales :

| Famille | Fichiers (exemples) | Ce qui est vérifié |
| --- | --- | --- |
| Physique et braquets | `core/tests/test_physics.py`, `core/tests/test_gearing_config.py` | Vitesse d'équilibre, pente effective bornée, plage des 24 braquets, difficulté |
| Trainer FTMS | `core/tests/test_ftms_spec.py`, `core/tests/test_ble_sim.py` | Conformité FTMS v1.0, Control Point, erreurs ATT 0x80 et 0xFE, relâche à l'arrêt |
| Séance | `core/tests/test_session_serie_t.py`, `core/tests/test_free_erg.py`, `core/tests/test_rogue_session.py` | États, pauses, ERG, ERG d'une session libre (O18), segments, Cyber-Rogue |
| IPC | `core/tests/test_contract_ipc.py` | Chaque trame émise valide contre son schéma, exemples du contrat, révisions 1.1 à 1.5, limite de 4 096 octets |
| Réglages | `core/tests/test_settings_persistance.py` | Chaque réglage de la liste écrit puis relu après relance (X37) |
| Documentation | `core/tests/test_docs_coherence.py` | Liens, chemins cités, modules de CLAUDE.md, nombres de tests, raccourcis du guide, statut des lots |

Marques : `slow` (séances simulées de 3 h, `pytest -m "not slow"` pour les sauter) et `recette_sans_velo` (étapes des recettes T11 et J7 faites sans vélo, `pytest -m recette_sans_velo`, lancées par le pré-vol).

Résultat attendu : `N passed` avec N égal au nombre du README, quelques `skipped` (tests réseau ou dépendances facultatives absentes), aucun `failed`.

### 3.2 Compilateur (`compiler/tests/`)

Périmètre : GPX, FIT et TCX vers `.world`, terrain, couches OpenStreetMap à partir de réponses Overpass enregistrées, thèmes, biomes, monde ouvert, bibliothèque et packs de parcours. Sans réseau ; `-m network` ajoute Copernicus. Attendu : 0 échec.

### 3.3 Contrats

- **IPC** : chaque schéma de `docs/contracts/ipc/` est valide ; chaque bloc JSON du §7 de [ipc_v1.md](contracts/ipc_v1.md) se lit ; les exemples (SIM, ERG, ERG cadence d'une session libre, commandes, `devices`, listes, révision 1.4, `set_ride_mode`) passent le schéma (`core/tests/test_contract_ipc.py`). Un changement de contrat se fait par ajout compatible avec une ligne au journal (§8 du contrat), le schéma et, si besoin, un exemple au §7 testé.
- **Taille** : `python -m openride_core.ipc_budget` donne la pire trame `state` de chaque révision face à sa limite ; attendu : marge positive à 4 096 octets.
- **Route** : `python -m openride_core.tools.route_vectors --check` ; les mêmes vecteurs sont relus par l'engine (`test_route_vectors.gd`).

### 3.4 Bluetooth simulé

Scénarios intégrés et attendus (détail dans [SIMULATION_BLE.md](SIMULATION_BLE.md)) :

| Scénario | Attendu |
| --- | --- |
| `nominal` | Tout connecté en 1 s, aucune pause |
| `demo` | Appuis courts et longs du Click reçus, effort variable suivi |
| `reveil_tardif` | Séance qui démarre quand le trainer apparaît, appuis perdus sur un boîtier endormi, rien d'autre |
| `erreur_0x80` | Renvoi 0,25 s plus tard, liaison gardée, pas de « Reconnexion au trainer » |
| `connexions_retardees` | Échecs de connexion repris sans intervention |
| `coupures` | Chaque coupure suivie de `down` puis `up` au journal ; pause `trainer_lost` pendant le silence du trainer, reprise ensuite |
| `controle_refuse` | Séance en `ERROR` après deux reprises |
| `rafale_0x80` | Rafale de braquets sur un Control Point lent : écritures refusées en 0x80 reprises, liaison gardée, aucune pause |
| `montre_garmin` | Écritures refusées pendant que la montre tient le trainer : consignes reportées, `devices.trainer.busy` vrai, bandeau, aucune pause |

Une panne vue sur le vélo se rejoue : `python -m openride_core.tools.log_scenario -o ~/panne.json`, puis `--sim-scenario ~/panne.json`.

### 3.5 Engine sans écran (`engine/tests/run_engine_tests.sh`)

Étapes : tests unitaires de `engine/tests/unit/` (un fichier par sujet : HUD, menus, ERG, réglages, clavier, thème, décor, biomes…), couches OSM, rendu par tronçons, coutures du sol multi-biome, ERG face au faux core (bips à T − 3 s), 8 scénarios IPC face à `engine/tests/fake_core.py` (hello, renvois toutes les 200 ms, abandon à 3 s, core muet 1,5 s, `shutdown`, trames en désordre, `error`, heartbeats à 2 Hz), puis contrôle de la sortie de Godot. Détail des vérifications : [engine/tests/README.md](../engine/tests/README.md).

- `UNIT=test_free_erg_menu engine/tests/run_engine_tests.sh` ne lance qu'un test unitaire.
- `OPENRIDE_PERF=strict PERF_CSV=~/OpenRide/perf/tests.csv engine/tests/run_engine_tests.sh` : passage dédié aux budgets de temps.
- Attendu : une ligne `<nom> : N vérifications, 0 échecs` par fichier, code 0.

### 3.6 Bout en bout (`engine/tests/run_e2e.sh`)

Vrai core sur trainer `mock` et vrai engine, HOME temporaire. Attendu : `hello_ack` en moins de 3 s ; au moins 25 trames `state` par seconde ; `input_event` relayé (bip) ; engine arrêté puis `PAUSED (engine_lost)` en moins de 3 s ; braquet de 12 à 13 ; même longueur de parcours vue par le core et l'engine ; `FINISHED` avec un bilan conforme au schéma ; FIT écrit ; aucune erreur Godot, core sorti avec le code 0, vrai HOME inchangé, moins de 60 s au total.

### 3.7 Tests graphiques

- **Scène principale** : `engine/tests/run_visual_tests.sh [--native]` lance `visual_check.py` face au faux core : captures du HUD, bandeau, menus, bilans (`bilan_complet`, `bilan_complet_detaille`), ERG (cible longue, palier de 50 W), contrôles de lisibilité (chiffres d'au moins 28 px ramenés à 1080 lignes, contraste 4,5:1 pour les valeurs et 3:1 pour les libellés) et de débordement (panneaux dans l'écran, sans chevauchement, textes dans leur colonne). Rapport dans `~/OpenRide/visual_tests/`.
- **Galerie des cas du HUD** : `python3 engine/tests/hud_galerie.py [--configs 1024x600:medium,1920x1080:high] [--native]` capture chaque cas (SIM, zones de puissance, vent et abri, bots avec segment et bonus, ERG avec cible courte, cible longue et palier de 50 W, courbes réduites et complètes, courbes en SIM, valeurs extrêmes) ; attendu : braquet et profil cachés en ERG, rien ne déborde, `planche_<config>.png` et `rapport.html` à montrer au propriétaire.
- **Qualité appliquée (X32)** : chaque banc vérifie dans le journal de l'engine que la capture a été rendue dans la qualité demandée (`engine/tests/quality_guard.py`) ; sinon ÉCHEC « qualité demandée medium, appliquée low ».
- **Couleurs du thème (X38)** : `test_theme_colors.gd` refuse toute couleur écrite en dur dans les scripts d'interface.

### 3.8 Banc des menus (`engine/tests/menu_bench.py`)

Vrai core sur Bluetooth simulé, démarré sans `--autostart` comme depuis l'icône, et vraie scène. Chaque scénario de `engine/tests/menu_scenarios/` se joue par trois voies : Click simulé, clavier, souris. Les vérifications lisent l'état des menus (écran, focus, éléments), `config.toml`, les journaux et les fichiers écrits.

| Scénario | Attendu |
| --- | --- |
| `connexion_auto` | L'écran « Connexion des appareils » passe seul à l'accueil |
| `appareils` | Un seul boîtier : « Passer » ; recherche, enregistrement confirmé dans `config.toml` |
| `sessions` | Parcours, session libre, pause, fin enregistrée, bilan ; session ERG ; session simulée |
| `reglages` | Sous-écrans, FTP + 15 W écrite, Y annule, qualité appliquée et écrite |
| `erg` | Entraînement créé (fichier écrit), import depuis les Téléchargements |
| `erg_libre` | Session libre, pause, Mode SIM → ERG (Puissance cible + 25 W), ERG cadence (Cadence cible), reprise, retour SIM, fin enregistrée ; lignes du journal « Mode de la séance : … » |
| `pause` | Y reprend, curseur de difficulté, « Abandonner » confirmé sans FIT |
| `quitter` | Focus sur Non ; Oui ferme l'engine avec le code 0 |
| `plans_ftp` | Plan démarré puis arrêté ; test de FTP par rampe jusqu'à « Prêt » |
| `records` | Table des records, segment sans temps désactivé |
| `garage` | Équipement et avatar enregistrés dans `profile.json` |
| `monde_ouvert` | Globe, recherche, Échap (Click et clavier) |
| `cyber_rogue` | Objectif, durée, avertissement, run composée jusqu'à « Prêt » |
| `clavier_synonymes` | Touches synonymes ; appui ambigu de 0,7 s ignoré |
| `souris_gestes` | Clic, molette, clic droit ; clic hors des éléments sans effet |
| `persistance` | Réglages de quatre sous-écrans et difficulté de la pause relus après relance |

Lancement : `python3 engine/tests/menu_bench.py --scenario erg_libre --voies clavier` (un cas), `--native` (fenêtre visible), `--captures ecrans` (capture de chaque écran vérifié). Rapport : `rapport.html`, `resultats.json`, `resume.txt`, journaux par passage, capture à chaque échec. Code 0 si tout passe, 1 sinon, 2 si Godot ou `xvfb-run` manque.

### 3.9 Banc simulé (`engine/tests/sim_bench.py`)

Séance complète sur Bluetooth simulé dans la vraie scène, captures régulières et à chaque événement, rapport HTML (courbes, captures, `summary`, `log_report`, images/s).

| Scénario | Attendu |
| --- | --- |
| `montee_descente` | 14 min de village : braquets au Click, pente envoyée qui suit le profil |
| `difficulte` | À 350 W en montée, pente envoyée à 50 % puis 100 % de difficulté dans le bon rapport |
| `erg_village` | ERG de 5 min 30 : consignes au trainer, bandeau ERG, biais au Click, appui long, coupure du « + » |
| `coupures_village` | Chaque coupure `down` puis `up`, pause et reprise visibles |
| `ceinture` | Ceinture préférée à la montre, contact perdu puis retrouvé, batterie faible signalée |
| `click_sommeil` | Boîtier « − » qui se rendort, appuis perdus sans effet de bord |
| `decor_vivant_2` | Décor vivant P27 sur le monde OSM ; ≥ 55 i/s en `low`, p99 < 25 ms |
| `rendu_invisible` | Tri du visible coupé puis activé (`--culling`), captures comparables par `compare_captures.py` |
| `endurance` | Une heure en fenêtre : images/s stables, mémoire sans dérive |
| `serie_t` | Recette T11 §1 à §3 sans vélo (X33) : segment, résultats de la montée et du sprint, arches, Z, jingles, records |
| `erg_boutons` | Essai J7 sans vélo (X33) : chaque appui du Click puis chaque touche du clavier a l'effet du plan (biais, bloc suivant, pause), aucun bonus en ERG |
| `course_bots` | Recette T11 §8 sans vélo (X33) : 4 bots à profil calibrés au journal, encart des bots et écarts à l'écran |

Contrôles communs : démarrage, parcours chargé, captures, aucune erreur Godot ni exception du core, journal et FIT écrits, fin de séance, vrai HOME inchangé, qualité appliquée égale à la demande.

### 3.10 Vitrines de rendu

`vitrine_rendu.gd` (route, herbe, personnages, animaux par préréglage), `vitrine_biomes.gd` (16 biomes × 4 vues) et `vitrine_sols.gd` (huit paires de biomes) produisent des PNG et un CSV (triangles, appels de dessin, objets). Avec `--compare REF`, comparaison image par image à une série de référence (`compare_captures.py`, images des écarts, seuil `--max-diff`) ; sol surexposé au-delà de 5 % de pixels saturés : échec. Ces vitrines servent d'avant/après à toute retouche graphique ; les planches sont montrées au propriétaire.

### 3.11 Confidentialité

`python3 Open_ride_linux/scripts/privacy/privacy_scan.py --all` (depuis la racine du dépôt) avant une étiquette de version ; `--commits origin/main..HEAD` pour une branche ; le crochet pre-commit refuse un commit fautif. La liste des mots interdits reste hors du dépôt.

## 4. Recettes sur le PC et sur le vélo

### 4.1 Recette du PC en une commande (X4)

`python3 scripts/recette_pc.py` enchaîne core, compilateur, engine, bout en bout, tests graphiques, banc des menus, séances simulées de T11 et J7 (`serie_t`, `erg_boutons`, `course_bots`, lot Z2) et confidentialité ; journal par étape dans `~/OpenRide/recettes/<date>_<heure>/` avec `resume.txt`, `resume.json` et `perf.csv`, comparés au passage précédent. `--rapide` saute les tests lents, les tests graphiques, le banc des menus et les séances simulées ; `--seulement core,engine` restreint.

### 4.2 Pré-vol avant une séance sur le vélo (X36)

`python3 scripts/pre_vol.py --seance t11_j7` (ou `p27`, `erg`, `recette_1_0`, `--liste`) vérifie git, les tests `recette_sans_velo`, les tests Godot de la séance, les parcours compilés, les fichiers posés ou mis de côté et la présence du trainer et du Click en Bluetooth. Verdict « PRÊT À ROULER » (code 0) ou la liste de ce qui bloque (code 1). Les séances sont dans `scripts/pre_vol_seances.toml`.

### 4.3 Outils guidés sur le matériel

| Outil | Essai | Attendu |
| --- | --- | --- |
| `python -m openride_core.tools.trainer_steps --mode sim\|erg` | Latence du trainer par paliers (X5) | Délai d'accusé, t63, t90 et stabilisation dans `rapport.html` |
| `python -m openride_core.tools.click_recette --minutes 30` | Click sur 30 min (X8) | Aucun silence non signalé |
| `python -m openride_core.tools.fc_recette` | Fréquence cardiaque (X9) | Retrait, absence, valeur figée et retour détectés |
| `python -m openride_core.tools.boutons_click` | 17 appuis du plan des boutons | Chaque appui reconnu avec son action et un bip |
| `python -m openride_core.tools.seance_guidee` | Séances guidées sur le trainer | Consignes suivies, journal complet |
| `openride-core session-report` | Analyse d'une séance réelle (X12) | Rapport par section, en local |

## 5. Changements récents : comment les tester

État de `main` au 29 octobre 2026 au soir.

| Changement | Tests automatiques | Lancement | Reste à faire |
| --- | --- | --- | --- |
| ERG d'une session libre et ERG à cadence verrouillée (O18, PR #550) | `core/tests/test_free_erg.py` (départ, biais, plage ± 15 % et sens, bornes et 10 W/s, pas d'oscillation, bascule dans la séance, refus `busy` et `bad_args`, journal et reprise, trainer simulé qui suit) ; `engine/tests/unit/test_free_erg_menu.gd` ; scénario `erg_libre` du banc des menus ; exemples du contrat (§3.3) | `(cd core && pytest -q tests/test_free_erg.py)` ; `UNIT=test_free_erg_menu engine/tests/run_engine_tests.sh` ; `python3 engine/tests/menu_bench.py --scenario erg_libre` | Essai de 10 min sur le vélo : bascule au Click, au clavier et à la souris, ressenti de la plage de 15 % (10 % en option), ERG libre à 50 W |
| Aucune roue libre en ERG (O19, PR #569) : consigne jamais sous 50 W, bloc FreeRide = palier de 50 W, test de FTP par la rampe seule | Tests du core sur le plancher de 50 W ; scène `erg_palier_50w` de `visual_check.py` et de la galerie du HUD | `(cd core && pytest -q)` ; `engine/tests/run_visual_tests.sh` | Ressenti sur le vélo avec un `.zwo` qui contient un FreeRide |
| HUD ERG et bilan de fin de séance sans débordement (PR #549, suite X22) | Scènes `erg_cible_longue`, `bilan_complet`, `bilan_complet_detaille` ; contrôle « textes dans leur colonne » | `engine/tests/run_visual_tests.sh --native` ; `python3 engine/tests/hud_galerie.py --native` | Captures à 1024×600 et 1920×1080 montrées au propriétaire |
| Control Point occupé sans décrochage (PR #540) | Scénarios `rafale_0x80` et `montre_garmin` (§3.4), tests du pilote dans `core/tests/test_ble_sim.py` | `scripts/openride-dev.sh --trainer sim --input sim --sim-scenario montre_garmin --autostart` | Bloc vélo avec la montre Garmin allumée |
| Coupure subie qui suspend la montée au lieu de l'annuler (PR #542) | `core/tests/test_segment_timing.py`, `core/tests/test_session_serie_t.py` | `(cd core && pytest -q tests/test_segment_timing.py tests/test_session_serie_t.py)` | — |
| Braquets SIM resserrés à 0,65–2,00 (PR #547) | `core/tests/test_gearing_config.py` | `(cd core && pytest -q tests/test_gearing_config.py)` | Ressenti des petits braquets sur le vélo |
| Séance simulée série T et boutons de l'ERG (X33, PR #534) | Scénarios `serie_t`, `erg_boutons`, `course_bots` (§3.9) | `python3 engine/tests/sim_bench.py --scenario erg_boutons` | Ne laisse au vélo que le ressenti de T11 et J7 |
| Matrice des boutons et des réglages (X42, PR #552) | `python -m openride_core.tools.matrice_boutons --partie tout` ; `core/tests/test_matrice_boutons.py` | idem | — |
| Cyber-Rogue de bout en bout (X40, #546) et banc visuel (X41, #548) | `python -m openride_core.tools.rogue_bout_en_bout --objective tous` ; `python3 engine/tests/rogue_bench.py --godot GODOT` | idem | Planche `rapport.html` montrée au propriétaire |
| Lisibilité du HUD (X22), persistance des réglages (X37), couleurs du thème (X38), qualité appliquée (X32), hygiène des suites (X34) | §3.7, §3.8, `core/tests/test_settings_persistance.py`, `scripts/recompte_tests.py` | voir les sections citées | Remesures medium et high par la file du PC |
| Autres outils X fusionnés le 29 octobre (X3, X10, X11, X14, X15, X17, X19, X20, X21, X24, X26, X27, X28, X30, X31, X35) | Chacun décrit dans [OUTILS_DE_TEST.md](OUTILS_DE_TEST.md) avec sa commande | voir le catalogue | Premier passage sur le PC pour ceux qui mesurent le matériel |

## 6. En revue : PR ouvertes au 29 octobre 2026 au soir

Rien de ce tableau n'est sur `main`. À la fusion, chaque PR met à jour le catalogue ([OUTILS_DE_TEST.md](OUTILS_DE_TEST.md)) et, pour l'IPC, le journal du contrat ; la ligne disparaît d'ici.

| PR | Contenu | Ce qu'il faudra tester |
| --- | --- | --- |
| #580 | Trainer : frein lâché détecté, contrôle repris, trace fine des mesures | Scénario simulé du frein lâché, puis un bloc vélo |
| #582 | SIM : Cw envoyé au trainer corrigé (ρ × CdA, sans le ½) | Tests de la physique et de FTMS ; ressenti sur le plat |
| #578 | Trace FTMS : mesures annoncées par le trainer toutes les 2 s | Lecture de la trace dans le journal |
| #583 | Banc du trainer X43 : paliers SIM à puissance cible, plafond, relances courtes, vitesse du volant | Passage du banc sur le vélo (file du PC) |
| #581 | Terrain lointain enfoncé juste ce qu'il faut sous le proche (coutures des flancs, relief × 2,5) | Captures dans les trois qualités, montrées au propriétaire |
| #572, #574, #575, #577 | Série MJ : profils, profil d'essai `_essai`, campagne simulée accélérée | Tests du core de chaque lot ; séances simulées comptées à part |
| #559 | Y13 étape 4 : rendu des tons AgX et filtrage anisotrope par préréglage | Captures et images/s par préréglage, après #557 |
| #557 | Y2 : migration de Godot 4.3 vers 4.7.2 | Toutes les suites de l'engine, les bancs et la recette du PC sous 4.7 |
| #507 | Robot des menus : Click, clavier et souris simulés de bout en bout | Recoupe le banc des menus (§3.8) |
| #322 | Zwift Click : comparaison avant et après la mise à jour du firmware | Essai du boîtier gauche, reporté à la 4.0 |

## 7. Mesures de performance

- **Où :** sur le PC cible seulement, en fenêtre (`--native`), par la file des mesures ; sous Xvfb le rendu est logiciel et les images/s ne valent rien.
- **Sonde (X13) :** `python3 engine/tests/sim_bench.py --native --probe --scenario NOM --quality low|medium|high` ; pendant une vraie séance, `OPENRIDE_PERF_PROBE` puis `python3 engine/tests/perf_probe.py watch`, et `perf_probe.py report --quality Q`.
- **Objectifs :** au moins 55 images/s en `low` et p99 de la durée d'image sous 25 ms ; en `medium`, environ 10,8 ms de GPU à 1680×1050 sur la GTX 1060 (mesure Y13 du 28 octobre).
- **Endurance (X16) :** `sim_bench.py --native --scenario endurance` : une heure, images/s et mémoire sans dérive.
- **Budgets de temps des tests :** `engine/tests/perf_budgets.json` (budget du PC, seuil de la CI), remplaçables par machine dans `~/OpenRide/perf_budgets.json`.
- **Comparer avant et après :** `compare_captures.py AVANT APRES --out ECARTS` pour les images ; pour les chiffres, `fps.csv` et `sonde.csv` des deux bancs.
- Toujours vérifier la ligne de qualité appliquée (§3.7) : avant la PR #481, les bancs medium et high mesuraient du `low`.

## 8. Écrire un test

| Cas | Où et comment | Règles |
| --- | --- | --- |
| Test du core | `core/tests/test_<sujet>.py`, fonctions `test_…` ; séance réelle sans matériel avec les fabriques de `test_contract_ipc.py` ou le Bluetooth simulé | `tmp_path` seulement ; marque `slow` au-delà de quelques secondes ; marque `recette_sans_velo` pour une étape de recette faite sans vélo |
| Test unitaire Godot | `engine/tests/unit/test_<sujet>.gd`, `extends SceneTree`, une ligne `[OK]` ou `[ÉCHEC]` par vérification puis `<nom> : N vérifications, M échecs`, code 0 ou 1 | Découvert sans modifier le script ; ni réseau ni fichier hors de `res://` et `user://` ; une mesure de temps passe par `PerfBudget` |
| Scénario de menus | `engine/tests/menu_scenarios/<nom>.json` : `description`, `voies`, `config`, `fichiers`, `etapes` ; étapes `ecran`, `choisir`, `appui`, `elements`, `contient`, `edition`, `journal` + `motif`, `config`, `fichier`, `relancer`, `capture` (liste complète en tête de `menu_bench.py`) | Identifiants stables des menus, jamais des textes traduits seuls ; chaque attente a un délai |
| Scénario du banc simulé | `engine/tests/sim_bench_scenarios/<nom>.json` : format de [SIMULATION_BLE.md](SIMULATION_BLE.md) plus une section `bench` (`world`, `workout`, `duration_s`, `every_s`, `difficulty_pct`) | Événements datés ; vérifications nommées dans le rapport |
| Scénario Bluetooth | JSON de [SIMULATION_BLE.md](SIMULATION_BLE.md) (`trainer`, `click`, `hr`, `events`) | Une section absente retire l'appareil |
| Scène graphique | Fonction de scène de `engine/tests/visual_check.py` (capture, `check_texts`, `check_layout`) | Rendue dans la qualité demandée |
| Changement de contrat | Schéma de `docs/contracts/ipc/`, ligne au journal du contrat, exemple au §7 et test dans `test_contract_ipc.py` | Ajout compatible seulement ; tableau des révisions de la [spécification générale](SPECIFICATION_GENERALE.md#61-révisions-du-contrat-ipc) |

Après l'ajout : `python3 scripts/recompte_tests.py` (nombre de tests de chaque suite, rien à réécrire), puis `(cd core && pytest -q tests/test_docs_coherence.py)` (liens, chemins cités, lots).

## 9. Couverture au 29 octobre face à l'audit du 28 octobre

L'audit de couverture du 28 octobre relevait sept trous. État sur `main` le 29 octobre au soir :

| Trou relevé le 28 octobre | État le 29 octobre |
| --- | --- |
| Qualité effective non vérifiée dans les bancs | **Comblé** : garde-fou X32 dans `sim_bench`, `visual_check`, `perf_probe` |
| Pas de séance simulée série T et boutons de l'ERG | **Comblé** : scénarios `serie_t`, `erg_boutons`, `course_bots` (X33) et matrice des boutons X42 |
| Menus au clavier et à la souris, persistance, écrans 2.0, banc hors CI | **Comblé** : banc des menus à trois voies, 16 scénarios, en CI (`--rotation`) et dans la recette du PC ; persistance X37 |
| Pas de référence visuelle ni de détection d'apparition | **Comblé** : régression visuelle v2 (X20), comparaison des vitrines (`--compare`), outils d'apparition livrés avec S1 (X18) |
| Pas de référence de performance ni d'alerte | **Comblé** : référence et comparateur avant/après (X14), coût par image (X19) |
| Analyse des séances sur le vélo à la main | **Comblé** : `openride-core session-report` (X12), `openride-core fit-check` (X11) |
| Outils jamais validés sur le PC : X4, X5, X8, X16 | En cours : paliers du trainer (X5) passés sur le PC le 29 octobre ; X4, X8 et X16 toujours à faire (§3 de [SUIVI_AVANCEMENT.md](SUIVI_AVANCEMENT.md)) |

Restent sans outil sur `main` : trainer simulé réaliste (X6) et latence Click → écran (X7) ; le banc du trainer X43 est en revue (#583).
