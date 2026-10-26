# Protocole de test à effectuer (26 octobre 2026)

Un seul protocole, pas à pas, pour valider sur le PC cible et sur le vélo l'état d'OpenRide après les fusions et les PR du 26 octobre. Il ne remplace pas les listes existantes, il les ordonne et renvoie vers elles :

- [RECETTE_E3_E4.md](RECETTE_E3_E4.md) : ciel, brouillard, arbres, bâtiments, eau, sons (rendu) ;
- [lots/LOT_O8_recette_1_0.md](lots/LOT_O8_recette_1_0.md) §4 : les 25 lignes de la recette 1.0 (cité « O8 ligne n ») ;
- l'essai de 1 h 09 du 25 octobre (circuit `essai-69`, coupures provoquées) : à refaire tel quel s'il faut revalider les coupures ;
- [OUTILS_DE_TEST.md](OUTILS_DE_TEST.md) : la liste de tous les outils et de leurs options.

Version à cocher en ligne : la page « Protocole de test OpenRide » publiée avec ce document (les cases restent cochées dans le navigateur). Ici, cocher en remplaçant `[ ]` par `[x]`.

## 0. Avant de commencer

### 0.1 Ce qui est fusionné et ce qui ne l'est pas

Le 26 octobre au soir, `main` contient la série N (dont N13, écran « Connexion des appareils »), le banc simulé et la SRS « ceinture ANT+ seule ». **Tout le reste est encore en PR.** Chaque test indique sur quel code il se fait :

| Code à tester | Branche | PR | Tests |
| --- | --- | --- | --- |
| `main` | `main` | – | A2, B1, B2, C1, D3, F1 |
| Séances guidées sur le vélo, consignes au temps de séance | `claude/project-thread-66gfit` | #297 (ce protocole) | D1, E0 |
| Mise à jour, jeu ouvert | `claude/update-game-running` | #290 | A3 |
| Version unique | `lot-o2-version` | #235 | A4 |
| Menu principal, réglages, sous-menu ERG (pile) | `claude/project-thread-shezfp-erg` | #230 → #248 → #249 | C2, C3, C4, D2, D4, E1, E2 |
| Flèches, souris, A et Z du Click | `claude/fleches-souris-click` | #287 | C5 |
| Entraînement choisi après une séance | `claude/erg-apres-seance` | #291 | E4 |
| Traces Garmin déposées | `lot-o5-traces-garmin` | #252 | F2 |
| Plans d'entraînement | `lot-o11-plans` | #289 | F3 |
| Modèle des courbes | `lot-o13-modele-courbes` | #277 | F4 |
| Outils de test X1 → X29 (pile) | `claude/project-thread-6d8wpm-x29` | #232 → … → #296 | A1, A5, G1, G2, H1, H2 |

Ces branches partent toutes de `main` et ne se gênent pas entre elles, sauf dans `README.md` et `SUIVI_AVANCEMENT.md` (nombres de tests) : on les teste **une par une**. Une fois une PR fusionnée, son test se fait sur `main`.

### 0.2 Passer d'une branche à l'autre

Depuis le dépôt du PC (`~/Games/lolo_python`), sans modification locale (`git status` propre) :

```bash
cd ~/Games/lolo_python && git fetch origin
git switch -C recette --track origin/<branche>   # exemple : origin/lot-o2-version
# … tests …
git switch main && git pull --ff-only            # retour à main à la fin
```

Le core et le compilateur sont installés en mode éditable, et Godot lit `engine/` du dépôt : l'icône **OpenRide** lance donc le code de la branche en cours, sans réinstaller. Seule exception : une branche qui ajoute une dépendance Python (aucune ici).

### 0.3 Notes et journaux

- Noter chaque écart sans s'arrêter : `echo "$(date +%T) C2 flèche haut descend" >> ~/OpenRide/Logs/recette_notes.txt`.
- Journal du lanceur (core, Godot préfixé `[engine]`) : `~/OpenRide/Logs/openride_<date>.log`, lien `~/run_trainer.log`.
- Séances : `~/OpenRide/Activities/` (FIT et `.jsonl`). Mise à jour : `~/OpenRide/Logs/update.log`.
- Rapports des outils : `~/OpenRide/recettes/`, `recettes_install/`, `trainer_steps/`, `click_recette/`, `sim_bench/`.
- Après un test raté : garder le dossier, ne pas relancer tout de suite, noter l'heure, puis le dire dans le fil. Je lis les journaux sur le PC ; les adresses Bluetooth et les traces réelles restent sur le PC.

### 0.4 Ordre conseillé et durées

| Bloc | Où | Durée |
| --- | --- | --- |
| A. PC, installation et mise à jour | bureau, sans pédaler | 45 min (dont 25 sans surveiller) |
| B. Appareils et ceinture | bureau, matériel allumé | 15 min |
| C. Menus et réglages | bureau, Click en main | 30 min |
| D. Séances SIM et session simulée | vélo | 40 min (dont 25 guidées) |
| E. ERG | vélo | 45 min (dont 13 guidées ; + 60 min pour le `sweet_spot_3x10` complet) |
| F. Fichiers, plans, courbes | bureau | 20 min |
| G. Trainer et Click (outils X5, X8) | vélo | 55 min |
| H. Performance et endurance (X13, X16) | PC seul, fenêtre visible | 75 min (sans surveiller) |
| I. Clôture | bureau | 10 min |

Les blocs A, F et H se font sans pédaler ; D, E et G le même jour, échauffé. Le bloc H tourne pendant que tu fais autre chose, mais Godot ouvre une fenêtre.

### 0.5 Essais guidés : rien à chronométrer

Sur le vélo, tu n'as pas à lire ce document ni à chronométrer :

- **Dans le jeu** (D1, E0) : `python -m openride_core.tools.seance_guidee` écrit deux parcours d'essai, `recette-velo` (séance libre en SIM, 25 min) et `recette-erg` (ERG, 13 min, entraînement « Recette ERG guidée »), avec leurs consignes. Chaque consigne s'affiche dans le bandeau avec un bip, au bon moment de la séance. Quand il faut du matériel (retirer la ceinture, sprint, fin de séance), un préavis « Dans 1 min, prépare … » arrive une minute avant. À chaque consigne, le journal du lanceur note le temps, la puissance, la cadence, la FC, le braquet et la pente envoyée (lignes `[essai]`).
- **Dans les outils de test** (X4, X5, X8, X16) : un écran de guidage en grand (consigne, compte à rebours, bip au début et à la fin de chaque étape, relevés horodatés dans `guide.jsonl`) et une option `--materiel` qui donne la liste du matériel et la durée avant de commencer. Il arrive dans une PR du fil des outils de test ; d'ici là, les outils marchent comme décrit en G et H, avec un bip du terminal.

`python -m openride_core.tools.seance_guidee --materiel` affiche ce qu'il faut préparer, sans rien écrire ; `--retirer` efface les parcours d'essai.

### 0.6 Matériel à préparer, par jour

| Jour | Matériel | Préavis dans l'essai |
| --- | --- | --- |
| Vélo (D, E, G) | Vélo sur le HomeTrainer, Bluetooth du PC allumé, aucune autre application reliée au trainer ; les deux boîtiers du Click réveillés, pile CR2032 de secours ; ceinture humidifiée ; bidon, serviette ; écran visible depuis le vélo, son audible ; FTP et poids à jour dans les réglages | 1 min avant de retirer la ceinture, avant le sprint, avant la pause ERG et avant chaque fin de séance |
| X5 (G1) | Le même vélo, un braquet moyen gardé tout l'essai, 5 min d'échauffement avant | Paliers annoncés par l'outil |
| X8 (G2) | Les deux boîtiers, piles chargées, jeu fermé ; vélo conseillé | Rappel d'appui toutes les 5 min |
| X16, X13 (H) | Rien (trainer simulé) ; PC sans mise en veille, sur la GTX 1060 | Bip au départ et à la fin |

---

## A. PC, installation et mise à jour

### A1. Recette du PC en une commande (X4) et état du GPU

- **Code :** `claude/project-thread-6d8wpm-x29` (PR #237, dans la pile X).
- **Prérequis :** `core/.venv` à jour (`pip install -c constraints.txt -e "core[dev]" -e "compiler[dev]"`), `GODOT` défini.
- **Étapes :**
  1. `nvidia-smi` : le pilote NVIDIA est chargé, la GTX 1060 est listée, aucun processus fantôme.
  2. `glxinfo -B | grep -E "renderer|version"` : rendu par la GTX 1060 (pas `llvmpipe`).
  3. `lscpu | grep -E "Model name|MHz"` et `free -h` : relever CPU et mémoire libre.
  4. `cd Open_ride_linux && python3 scripts/recette_pc.py` (25 min environ, rien à faire).
- **Attendu :** `resume.txt` avec chaque étape OK (core, compilateur, engine, bout en bout, tests graphiques, confidentialité) ; la seule exception connue est le budget de temps de `test_tree_renderer` (environ 210 ms pour 150 ms), signalé `(DÉPASSÉ)` sans faire échouer l'étape.
- [ ] GPU et pilote corrects
- [ ] `recette_pc.py` : toutes les étapes OK
- **Journaux :** `~/OpenRide/recettes/<date>_<heure>/` (`resume.txt`, un journal par étape, `perf.csv`).
- **Si échec :** relancer seulement l'étape en cause (`--seulement engine`) pour confirmer, puis donner le dossier. `llvmpipe` au point 2 : pilote NVIDIA à réinstaller, ne pas continuer les blocs D à H.

### A2. Icône et lancement sans terminal

- **Code :** `main`.
- **Étapes :** ouvrir le menu des applications, chercher « OpenRide » : trois entrées (OpenRide, Libérer le trainer, Mettre à jour) avec l'icône. Lancer **OpenRide** par l'icône.
- **Attendu :** pas de terminal ; compilation des nouvelles traces avec notification si besoin ; écran « Connexion des appareils ».
- [ ] Trois entrées avec l'icône, lancement sans terminal
- **Si échec :** `scripts/install-desktop.sh` puis réessayer ; une fenêtre d'erreur donne le chemin du journal.

### A3. Mise à jour avec le jeu ouvert (PR #290)

- **Code :** `claude/update-game-running` (suivie avec `--track`, donc « Mettre à jour » peut tirer).
- **Étapes :**
  1. Lancer OpenRide par l'icône, rester sur le menu.
  2. Lancer « OpenRide – Mettre à jour » par l'icône.
  3. Choisir « Réessayer » (jeu toujours ouvert), puis « Fermer le jeu ».
  4. Lancer une seconde fois « Mettre à jour » pendant la première (si elle est encore ouverte), puis lancer OpenRide pendant la mise à jour.
- **Attendu :** au point 2, rien n'est touché et une fenêtre propose « Fermer le jeu / Réessayer / Annuler » ; « Réessayer » repropose la même fenêtre ; « Fermer le jeu » arrête proprement (trainer relâché) puis met à jour ; résultat dans une fenêtre, pas de terminal. Au point 4 : seconde mise à jour refusée, le lanceur refuse de démarrer tant que le verrou `~/OpenRide/.update.lock` existe. Parcours, séances et `config.toml` inchangés (O8 ligne 2).
- [ ] Jeu ouvert détecté, fenêtre à trois choix
- [ ] Fermeture propre puis mise à jour réussie
- [ ] Verrou : seconde mise à jour et lancement refusés
- [ ] Données conservées
- **Journaux :** `~/OpenRide/Logs/update.log`.
- **Si échec :** copier le contenu de la fenêtre ; vérifier qu'aucun `~/OpenRide/.update.lock` ne reste après la fin (sinon le noter et le supprimer à la main).

### A4. Numéro de version (O2, PR #235)

- **Code :** `lot-o2-version`.
- **Étapes :** `openride --version`, `openride-core --version`, `openride-compiler --version` ; lancer OpenRide puis lire la première ligne du journal du lanceur.
- **Attendu :** « openride 0.9.0 », « openride-core 0.9.0 », « openride-compiler 0.9.0 » ; journal : `[openride] OpenRide 0.9.0`.
- [ ] Même numéro partout
- **Si échec :** noter la sortie exacte.

### A5. Installation sur un système propre (X29, PR #296), facultatif

- **Code :** `claude/project-thread-6d8wpm-x29`.
- **Étapes :** `python3 scripts/recette_install.py --mode home` (15 min environ ; le mode `docker` demande Docker). À la main, si tu as le temps : `sudo adduser essai`, puis depuis ce compte `scripts/install.sh` et lancement par l'icône (O8 ligne 1).
- **Attendu :** clone, installation, commandes, `config.toml`, raccourcis valides, premier démarrage sur trainer simulé, mise à jour qui garde les données octet pour octet.
- [ ] `recette_install.py` OK
- [ ] Second compte (facultatif)
- **Journaux :** `~/OpenRide/recettes_install/<date>/`.

---

## B. Appareils et ceinture

### B1. Écran « Connexion des appareils » (N13)

- **Code :** `main`.
- **Prérequis :** HomeTrainer allumé, les deux boîtiers du Click réveillés (un appui sur chacun), ceinture portée.
- **Étapes :**
  1. Lancer OpenRide par l'icône.
  2. Relancer avec un seul boîtier du Click réveillé.
  3. Réglages → « Appareils : rechercher et appairer » : recherche, « Click : identifier le bouton + » (appuyer sur + du vrai boîtier), « Enregistrer », « Relancer OpenRide maintenant ».
- **Attendu :** au point 1, passage seul au menu 2 s après que tout est relié ; au point 2, « Passer » nomme ce qui manque (« un seul boîtier du Click ») ; au point 3, le bon boîtier devient « + », la confirmation nomme les changements, `~/OpenRide/config.toml` est réécrit (copie `config.toml.bak`) et la relance reconnecte tout sans quitter à la main (O8 ligne 3).
- [ ] Passage automatique quand tout est relié
- [ ] « Passer » avec un seul boîtier
- [ ] Appairage, identification du +, relance
- [ ] Lisible à 2 m
- **Journaux :** journal du lanceur (lignes du core sur la recherche et la relance, code 64).
- **Si échec :** `openride-core devices` dans un terminal pour comparer ce que voit BlueZ ; ne pas copier les adresses dans le fil.

### B2. Ceinture HRM-Tri : ANT+ seulement

- **Code :** `main` (SRS « ceinture ANT+ seule », PR #196).
- **Étapes :**
  1. Ceinture portée et humidifiée, HomeTrainer allumé. `bluetoothctl`, puis `scan on` pendant 20 s, puis `scan off`, `quit`.
  2. `openride-core devices` : rôle « ceinture » ?
  3. Pendant une séance (bloc D), lire la FC au HUD, puis retirer la ceinture 30 s.
- **Attendu :** la ceinture n'apparaît ni dans `bluetoothctl` ni comme ceinture dans `devices` (elle n'émet qu'en ANT+) ; la FC au HUD arrive par le relais du trainer ; ceinture retirée, la FC reste figée au lieu de tomber à 0 (comportement attendu, l'exclusion de la FC figée est le lot Q5, PR #195, mené à part) ; `hr = "none"` dans `config.toml` est le bon réglage.
- [ ] Absente du scan Bluetooth
- [ ] FC relayée par le trainer visible au HUD
- [ ] FC figée ceinture retirée (noter la durée)
- **Si échec :** si la ceinture apparaît dans le scan, noter son nom (pas son adresse) : ce serait un autre modèle.

---

## C. Menus et réglages

Commandes de référence : Click + / − pour choisir, appui long + pour valider, appui long − pour revenir, Y (boîtier droit) pour la pause ; clavier : flèches, Entrée, Échap ; P, Espace ou Échap pour la pause en séance.

### C1. Menus au Click et au clavier (état de `main`)

- **Code :** `main`.
- **Étapes :** parcourir l'accueil, la liste des parcours, la liste des entraînements, revenir, au Click puis au clavier.
- **Attendu :** tout est pilotable au Click seul ; appui long − revient toujours d'un écran ; aide des commandes lisible. Défaut connu sur `main` : la flèche haut descend dans les menus (corrigé par C5).
- [ ] Menus au Click seul
- [ ] Menus au clavier

### C2. Menu principal (N15, PR #230)

- **Code :** `claude/project-thread-shezfp-erg` (contient #230, #248 et #249).
- **Étapes :** sur l'accueil, choisir « Monde : … », un parcours, puis « Session libre », puis revenir et choisir « Session ERG ».
- **Attendu :** six entrées (Monde, Session libre, Session ERG, Session simulée, Réglages, Quitter) ; le monde choisi s'affiche sur l'accueil ; « Session libre » mène à « Prêt : session libre — monde » ; « Session ERG » mène à la liste des entraînements ; sans monde choisi, la liste des parcours passe d'abord ; « Quitter » demande confirmation.
- [ ] Accueil à six entrées, monde affiché
- [ ] Écran « Prêt » correct pour libre et ERG
- **Si échec :** noter l'écran et la touche ; journal du lanceur, lignes `[engine]`.

### C3. Réglages (O3/O4, PR #248)

- **Code :** `claude/project-thread-shezfp-erg`.
- **Étapes :** Réglages → FTP : + / − puis appui long + pour enregistrer ; refaire avec appui long − pour annuler ; changer la qualité et le thème ; quitter et relancer OpenRide.
- **Attendu :** FTP, poids, difficulté, braquet de départ, qualité et thème modifiables ; la valeur enregistrée est écrite dans `~/OpenRide/config.toml` et retrouvée après relance ; l'annulation ne change rien ; qualité et thème s'appliquent tout de suite au décor ; réglages refusés pendant une séance.
- [ ] Modifier, enregistrer, annuler
- [ ] Valeurs gardées après relance (O8 critère « FTP utilisée par l'ERG » : voir E3)
- [ ] Qualité et thème appliqués tout de suite

### C4. Curseur de difficulté sur l'écran de pause (Q1 + PR #248)

- **Code :** `claude/project-thread-shezfp-erg`.
- **Étapes :** en séance libre (bloc D), Y pour la pause, déplacer le curseur de difficulté de 50 % à 40 %, reprendre.
- **Attendu :** curseur de 0 à 100 % par pas de 10 % ; le journal du core note `Difficulté : 50 % -> 40 %` ; `config.toml` n'est pas modifié ; défaut 50 %.
- [ ] Curseur de pause actif, journal correct, `config.toml` inchangé

### C5. Flèches, souris, A et Z du Click (PR #287)

- **Code :** `claude/fleches-souris-click`.
- **Étapes :** dans les menus : flèche bas, flèche haut ; clic gauche sur un élément, clic droit, molette ; bouton A puis Z du Click (appui court et long) ; un appui sur + d'environ 0,7 s (ni court ni long) ; en séance, flèche haut.
- **Attendu :** bas = élément suivant, haut = précédent ; clic gauche valide, clic droit revient, molette choisit ; A valide et Z revient quelle que soit la durée de l'appui, sans effet en séance ; l'appui ambigu est expliqué dans le bandeau ; aide des commandes visible dans tous les menus, « Y reprendre » sur la pause, rappel des commandes au départ ; en séance, haut reste « braquet plus dur ».
- [ ] Flèches dans le bon sens
- [ ] Souris
- [ ] A et Z du Click
- [ ] Appui ambigu expliqué, aide visible

---

## D. Séances SIM et session simulée

### D1. Séance libre guidée de 25 min en SIM (O8 ligne 4)

- **Code :** `main` après la fusion de #297 (consignes au temps de séance). Les consignes du curseur de difficulté (#248) et des boutons A et Z (#287) ne servent qu'une fois ces PR fusionnées.
- **Prérequis :** matériel du jour vélo (0.6) ; `python -m openride_core.tools.seance_guidee` lancé une fois (20 s).
- **Étapes :** OpenRide par l'icône → « Monde » → `recette-velo` → « Session libre » → « Démarrer », puis suivre les consignes du bandeau : échauffement 5 min, 10 appuis sur +, 10 sur − (ou B du boîtier droit si le − se tait), appuis longs, A et Z, pause par Y avec le curseur de difficulté, ceinture retirée 30 s puis remise, un changement de braquet par minute en montée, roue libre, sprint de 10 s, retour au calme, puis Y → « Terminer et enregistrer ».
- **Attendu :** chaque consigne arrive avec un bip, les préavis une minute avant ; braquets nets et perceptibles, un bip par appui, braquet borné de 1 à 24 ; pause et reprise par Y ; FC figée ceinture retirée, puis repartie (B2) ; à la fin : consigne annulée, trainer rendu, FIT écrit, bilan affiché.
- [ ] Consignes et préavis à l'heure, avec bip
- [ ] Braquets perceptibles, appuis tous reçus
- [ ] Pause et reprise par Y
- [ ] Arrêt propre, FIT et bilan
- **Journaux :** lignes `[essai]` du journal du lanceur (`grep "\[essai\]" ~/run_trainer.log`) ; `python -m openride_core.tools.log_report` (dernier journal), `openride-core summary`, mesures `Perf` du journal.
- **Si échec :** pour un boîtier muet, noter l'heure (problème Q6 connu, lot mené à part) et continuer avec B. Aucune consigne à l'écran : vérifier `~/OpenRide/Essais/recette-velo.consignes.json` et la ligne `[essai] … consignes chargées` du journal.

### D2. Session simulée et retour au matériel réel (N15, PR #230)

- **Code :** `claude/project-thread-shezfp-erg`.
- **Étapes :** accueil → « Session simulée » → confirmer ; démarrer une courte séance libre ; revenir à l'accueil → « Revenir au matériel réel ».
- **Attendu :** l'engine se ferme et revient seul (code 65) ; accueil « OpenRide — session simulée » ; la séance roule sans pédaler (trainer, Click et ceinture simulés) et le vrai trainer ne bouge pas ; « Revenir au matériel réel » relance sur le vrai matériel (code 64) et l'écran de connexion réapparaît.
- [ ] Passage en session simulée
- [ ] Séance simulée sans toucher au vrai trainer
- [ ] Retour au matériel réel
- **Journaux :** journal du lanceur (`--trainer sim --input sim --hr sim --sim-scenario nominal` au relancement du core).

### D3. Trainer libéré après la séance (O8 ligne 11)

- **Code :** `main`.
- **Étapes :** après D1, quitter OpenRide, ouvrir une autre application de vélo et s'y connecter au HomeTrainer.
- **Attendu :** connexion immédiate. Sinon « OpenRide – Libérer le trainer » doit suffire.
- [ ] Autre application connectée sans manipulation

### D4. Nouvelle séance après le bilan

- **Code :** `claude/project-thread-shezfp-erg`.
- **Étapes :** après le bilan, « Nouvelle séance ».
- **Attendu :** le monde choisi est rechargé, écran « Prêt », séance qui démarre.
- [ ] Nouvelle séance sans relancer OpenRide

---

## E. ERG

Rappel des commandes en ERG : appui court + / − = intensité ± 2 % ; Y = pause.

### E0. Séance ERG guidée de 13 min

- **Code :** `main` après la fusion de #297.
- **Prérequis :** D1 faite (ou `seance_guidee` lancé), FTP à jour.
- **Étapes :** « Monde » → `recette-erg` → « Session ERG » → « Recette ERG guidée » → « Démarrer », puis suivre les consignes : intensité + 2 % puis − 2 % au Click, écoute du bip avant le changement de bloc, pause de 10 s en récupération, deuxième effort, retour au calme, bilan.
- **Attendu :** bandeau ERG avec tous les blocs, cible tenue, biais affiché au bandeau et au bilan, bip à T − 3 s à chaque changement de bloc, trainer relâché pendant la pause, cible et écart par bloc au bilan.
- [ ] Biais ± 2 % visible et au bilan
- [ ] Bip à T − 3 s, cible tenue
- [ ] Pause en ERG et reprise
- **Journaux :** lignes `[essai]` (puissance et cible au moment de chaque consigne), `openride-core summary`.

### E1. Créer un entraînement court au Click (N16, PR #249)

- **Code :** `claude/project-thread-shezfp-erg`.
- **Étapes :** Session ERG → « Créer un entraînement (intervalles) » : échauffement 2 min, 2 répétitions, effort 1 min à 100 %, récupération 1 min à 50 %, retour au calme 1 min ; « Enregistrer et choisir » ; démarrer et rouler jusqu'au bout (environ 8 min).
- **Attendu :** fichier `intervalles_2x60s_100.zwo` dans `~/OpenRide/Workouts/`, ligne « Créé : … », focus sur le nouvel entraînement ; en séance : bandeau ERG avec tous les blocs du début à la fin, histogramme, bip à T − 3 s avant chaque changement de bloc, cible tenue par le trainer, biais ± 2 % au Click affiché.
- [ ] Création et choix au Click
- [ ] Bandeau et histogramme complets
- [ ] Bip à T − 3 s à chaque bloc
- [ ] Cible tenue, biais ± 2 % visible
- **Journaux :** `openride-core summary` (cible et écart par bloc, biais).

### E2. Importer un exercice (N16, PR #249)

- **Code :** `claude/project-thread-shezfp-erg`.
- **Prérequis :** un fichier `.zwo`, `.erg` ou `.mrc` dans `~/Téléchargements` (par exemple une copie de `core/workouts/tempo_2x15.erg`, ou un export GoldenCheetah, qui reste sur le PC).
- **Étapes :** Session ERG → « Importer un fichier » → choisir le fichier ; refaire l'import du même fichier.
- **Attendu :** fichiers proposés du plus récent au plus ancien avec leur dossier ; copie dans `~/OpenRide/Workouts/`, « Importé : … » ; second import du même fichier : marqué « déjà importé », pas de doublon ; un fichier différent du même nom prend le suffixe `_2`.
- [ ] Import et choix
- [ ] Pas de doublon ni d'écrasement

### E3. `sweet_spot_3x10` complet (O8 ligne 5)

- **Code :** `main`, ou la branche des menus pour vérifier aussi la FTP réglée en C3.
- **Étapes :** choisir `sweet_spot_3x10` (60 min : échauffement 10 min, 3 × 10 min à 90 % de la FTP, récupérations 5 min à 55 %, retour au calme 5 min) et le rouler en entier, ou au moins jusqu'à la fin du premier effort (20 min).
- **Attendu :** cibles calculées sur la FTP des réglages ; cibles tenues ; biais ± 2 % ; bips ; bandeau lisible à 2 m.
- [ ] Séance complète (ou 20 min) sans défaut
- **Journaux :** `openride-core summary`, `log_report`.

### E4. Entraînement choisi après une séance terminée (PR #291)

- **Code :** `claude/erg-apres-seance`.
- **Étapes :** finir une séance libre courte (2 min), puis depuis le bilan choisir un entraînement ERG et démarrer.
- **Attendu :** la séance part en ERG avec le bandeau (avant la correction, elle repartait en SIM sans bandeau).
- [ ] ERG pris en compte après une première séance

---

## F. Fichiers, plans et courbes (sans pédaler)

### F1. FIT de séance dans Garmin Connect et GoldenCheetah (O8 ligne 21)

- **Code :** `main`.
- **Étapes :** importer le FIT de D1 ou E1 (`~/OpenRide/Activities/`) dans Garmin Connect, puis dans GoldenCheetah.
- **Attendu :** import sans erreur, puissance, cadence et FC présentes.
- [ ] Garmin Connect
- [ ] GoldenCheetah

### F2. Traces Garmin déposées dans le dossier (O5, PR #252)

- **Code :** `lot-o5-traces-garmin`.
- **Étapes :** copier dans `~/OpenRide/GPX/` une sortie exportée de Garmin Connect telle quelle (`.fit`, `.tcx`, `.fit.gz` ou `.zip`) ; lancer OpenRide par l'icône ; en plus, copier une archive `.zip` vide.
- **Attendu :** compilation au lancement avec notification ; le parcours apparaît dans la liste et se roule ; l'archive vide est refusée avec un message sans empêcher les autres ; deux fichiers de même nom (`col.gpx`, `col.fit`) : un seul compilé, l'autre signalé.
- [ ] Sortie Garmin compilée et roulée
- [ ] Archive invalide refusée proprement
- **Journaux :** journal du lanceur (compilation), `openride-compiler list`.
- **Rappel :** ces traces restent sur le PC, jamais dans le dépôt.

### F3. Plans d'entraînement (O11, PR #289)

- **Code :** `lot-o11-plans`.
- **Étapes :** `openride-core plan install`, `plan list`, `plan show reprise_4_semaines`, `plan start reprise_4_semaines`, `plan today` ; après une séance de l'entraînement du jour roulée à 80 % ou plus, `plan today` et `openride-core history --weeks 2`.
- **Attendu :** deux plans installés sans rien écraser ; durée et TSS par semaine ; séance du jour indiquée ; une fois roulée, elle compte (pourcentage fait), et `history` mentionne le plan. Le choix du plan depuis le menu viendra avec O12.
- [ ] Installation et affichage des plans
- [ ] Séance du jour comptée

### F4. Modèle des courbes (O13, PR #277)

- **Code :** `lot-o13-modele-courbes`.
- **Étapes :** `UNIT=test_workout_chart_model engine/tests/run_engine_tests.sh`.
- **Attendu :** tous les tests passent ; le temps de calcul de la géométrie d'une longue séance reste faible. L'affichage à l'écran viendra avec O14 : rien à voir en séance pour l'instant.
- [ ] Tests du modèle OK

---

## G. Trainer et Click (outils de test X5 et X8)

### G1. Banc de latence du trainer par paliers (X5, PR #245)

- **Code :** `claude/project-thread-6d8wpm-x29`.
- **Prérequis :** OpenRide fermé, aucune autre application reliée au trainer, 5 min d'échauffement, un braquet moyen gardé tout l'essai, cadence tenue à 85 tr/min. Tout est chronométré par l'outil.
- **Étapes :** essai à blanc `python -m openride_core.tools.trainer_steps --trainer sim --mode sim --fast` ; puis sur le vélo `python -m openride_core.tools.trainer_steps --mode sim` (4 min environ), puis `--mode erg --cadence 85` (3 min environ).
- **Attendu :** pour chaque palier : délai consigne → écriture → accusé 0x80, t10, t63, t90, stabilisation, dépassement ; délai stable de 1 à 2 s (à noter s'il dépasse 3 s) ; trainer relâché à la fin.
- [ ] Essai à blanc OK
- [ ] Mode SIM sur le vélo
- [ ] Mode ERG (facultatif)
- **Journaux :** `~/OpenRide/trainer_steps/<date>_<heure>/` (`rapport.html`, `steps.csv`).
- **Si échec :** `--analyse DOSSIER` refait l'analyse ; donner le dossier.

### G2. Recette guidée du Click, 30 min (X8, PR #295, O8 ligne 6)

- **Code :** `claude/project-thread-6d8wpm-x29`.
- **Prérequis :** les deux boîtiers, piles chargées (une CR2032 de secours), jeu fermé.
- **Étapes :** essai à blanc `python -m openride_core.tools.click_recette --sim` ; puis `python -m openride_core.tools.click_recette --minutes 30 --rappel 5`, en pédalant ou non : appuyer sur chaque bouton demandé, puis un appui à chaque rappel.
- **Attendu :** chaque bouton (+, − du boîtier gauche, B et Y du boîtier droit, appuis longs) coché avec le bon boîtier ; sur 30 min, silences, coupures et reprises de chaque boîtier relevés. Défaut connu : le boîtier gauche peut se taire 35 à 60 s après la connexion (B du boîtier droit sert de « − ») ; l'outil dira à quelle minute.
- [ ] Essai à blanc OK
- [ ] Tous les boutons reconnus
- [ ] 30 min : aucune coupure non reprise (sinon heure du silence notée)
- **Journaux :** `~/OpenRide/click_recette/<date>/` (`rapport.txt`, `notifications.csv`).

---

## H. Performance et endurance (PC seul, fenêtre visible)

### H1. Sonde de performance du moteur (X13, PR #280)

- **Code :** `claude/project-thread-6d8wpm-x29`.
- **Étapes :** `python3 engine/tests/sim_bench.py --native --probe --scenario erg_village --duration 300` ; en plus, une vraie séance avec la sonde : `OPENRIDE_PERF_PROBE=~/OpenRide/sonde/moteur.csv openride` puis, dans un second terminal, `python3 engine/tests/perf_probe.py watch`.
- **Attendu :** une ligne par seconde (temps d'image p50 et p99, CPU et GPU, appels de dessin, mémoire vidéo, nvidia-smi) ; en qualité basse sur le village : 30 images/s au moins (O8 ligne 17) ; GPU, pas de CPU saturé.
- [ ] Sonde en séance simulée
- [ ] Sonde en vraie séance
- [ ] 30 images/s ou plus en qualité basse
- **Journaux :** dossier du banc (`sonde.csv`, `sonde.txt`, `rapport.html`).

### H2. Endurance d'une heure (X16, PR #294, O8 ligne 18)

- **Code :** `claude/project-thread-6d8wpm-x29`.
- **Prérequis :** PC sans mise en veille, rien d'autre de lourd ouvert.
- **Étapes :** `python3 engine/tests/sim_bench.py --native --scenario endurance --probe` (1 h 05, bip au départ et à la fin, ne pas fermer la fenêtre).
- **Attendu :** engine vivant jusqu'à la fin, aucune erreur Godot ni exception du core ; médiane ≥ 30 images/s, baisse < 10 % entre début et fin, 6 saccades au plus ; mémoire : moins de 100 Mo/h pour Godot, 20 Mo/h pour le core (une marche d'environ 5 Mo à chaque rechargement du parcours a été vue dans le cloud : à surveiller), 50 Mo/h pour la mémoire vidéo de Godot.
- [ ] Une heure sans plantage
- [ ] Images/s et saccades dans les seuils
- [ ] Mémoire dans les seuils
- **Journaux :** `~/OpenRide/sim_bench/<date>/endurance/` (`rapport.html`, `sonde.txt`).
- **Si échec :** ne pas relancer ; donner le dossier.

Le rendu détaillé (ciel, arbres, bâtiments, eau, sons) reste dans [RECETTE_E3_E4.md](RECETTE_E3_E4.md) : à faire lors d'une séance sur un parcours OSM.

---

## I. Clôture

- [ ] `git switch main && git pull --ff-only` : retour sur `main`.
- [ ] `python3 Open_ride_linux/scripts/privacy/privacy_scan.py --all` (branche X29) : aucune donnée interdite dans le dépôt.
- [ ] `~/OpenRide/Logs/recette_notes.txt` relu.
- [ ] Message dans le fil : blocs faits, cases non cochées. Je lis les journaux sur le PC et ouvre un correctif ou une ligne de suivi par défaut.

Ordre de fusion conseillé : #297 d'abord (il porte les séances guidées), puis, si tout passe, #290 et #291 (petits correctifs), puis la pile des menus #230 → #248 → #249, puis #287 (conflit de nombres de tests seulement), puis O2, O5, O11, O13, puis la pile X.
