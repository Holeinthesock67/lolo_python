# Protocole de test à effectuer (26 octobre 2026, remis à jour le 27 octobre)

Un seul protocole, pas à pas, pour valider sur le PC cible et sur le vélo l'état d'OpenRide après les fusions des 26 et 27 octobre. Il ne remplace pas les listes existantes, il les ordonne et renvoie vers elles :

- [RECETTE_E3_E4.md](RECETTE_E3_E4.md) : ciel, brouillard, arbres, bâtiments, eau, sons (rendu) ;
- [RECETTE_P16.md](RECETTE_P16.md) et [RECETTE_P17.md](RECETTE_P17.md) : vent, nuages, sons d'ambiance, puis décor complet (mises à jour 1.x, bloc J) ;
- [lots/LOT_O8_recette_1_0.md](lots/LOT_O8_recette_1_0.md) §4 : les 25 lignes de la recette 1.0 (cité « O8 ligne n ») ;
- l'essai de 1 h 09 du 25 octobre (circuit `essai-69`, coupures provoquées) : à refaire tel quel s'il faut revalider les coupures ;
- [OUTILS_DE_TEST.md](OUTILS_DE_TEST.md) : la liste de tous les outils et de leurs options.

Version à cocher en ligne : la page « Protocole de test OpenRide » publiée avec ce document (les cases restent cochées dans le navigateur). Ici, cocher en remplaçant `[ ]` par `[x]`.

## 0. Avant de commencer

### 0.1 Code à tester

Depuis le 27 octobre, tout ce que ce protocole teste est sur `main`, sauf deux essais qui attendent leur PR :

| Essai | PR en revue |
| --- | --- |
| A3, mise à jour avec le jeu ouvert | #391 (remplace #290, fermée) |
| J3, écrans Plans, Test de FTP et bibliothèque (O12) | #396 |

Les autres blocs se font sur `main`, à jour. Une fois une de ces PR fusionnée, son essai se fait aussi sur `main`.

### 0.2 Mettre le PC à jour

Depuis le dépôt du PC (`~/Games/lolo_python`), sans modification locale (`git status` propre) :

```bash
cd ~/Games/lolo_python && git switch main && git pull --ff-only
# Pour un essai qui attend sa PR (§0.1) :
git fetch origin && git switch -C recette --track origin/<branche de la PR>
# … essai …
git switch main                                  # retour à main à la fin
```

Le core et le compilateur sont installés en mode éditable, et Godot lit `engine/` du dépôt : l'icône **OpenRide** lance donc le code de la branche en cours, sans réinstaller.

### 0.3 Notes et journaux

- Noter chaque écart sans s'arrêter : `echo "$(date +%T) C2 flèche haut descend" >> ~/OpenRide/Logs/recette_notes.txt`.
- Journal du lanceur (core, Godot préfixé `[engine]`) : `~/OpenRide/Logs/openride_<date>.log`, lien `~/run_trainer.log`.
- Séances : `~/OpenRide/Activities/` (FIT et `.jsonl`). Mise à jour : `~/OpenRide/Logs/update.log`.
- Rapports des outils : `~/OpenRide/recettes/`, `recettes_install/`, `trainer_steps/`, `click_recette/`, `boutons_click/`, `sim_bench/`.
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
| G. Trainer et Click (outils X5, X8, test des boutons) | vélo (G3 : bureau, Click en main) | 60 min |
| H. Performance et endurance (X13, X16) | PC seul, fenêtre visible | 75 min (sans surveiller) |
| J. Lots du 27 octobre | vélo (J2, J5, J6, J7) et bureau | 3 h environ, sur plusieurs jours |
| I. Clôture | bureau | 10 min |

Les blocs A, F et H se font sans pédaler ; D, E et G le même jour, échauffé. Le bloc H tourne pendant que tu fais autre chose, mais Godot ouvre une fenêtre.

### 0.5 Essais guidés : rien à chronométrer

Sur le vélo, tu n'as pas à lire ce document ni à chronométrer :

- **Dans le jeu** (D1, E0) : `python -m openride_core.tools.seance_guidee` écrit deux parcours d'essai, `recette-velo` (séance libre en SIM, 25 min) et `recette-erg` (ERG, 13 min, entraînement « Recette ERG guidée »), avec leurs consignes. Chaque consigne s'affiche dans le bandeau avec un bip, au bon moment de la séance. Quand il faut du matériel (retirer la ceinture, sprint, fin de séance), un préavis « Dans 1 min, prépare … » arrive une minute avant. À chaque consigne, le journal du lanceur note le temps, la puissance, la cadence, la FC, le braquet et la pente envoyée (lignes `[essai]`).
- **Dans les outils de test** (X4, X5, X8, X16, test des boutons G3) : un écran de guidage en grand (consigne, compte à rebours, bip au début et à la fin de chaque étape, relevés horodatés dans `guide.jsonl`) et une option `--materiel` qui donne la liste du matériel et la durée avant de commencer. Il est sur `main` depuis la [PR #300](https://github.com/Holeinthesock67/lolo_python/pull/300) : `python -m openride_core.tools.guide materiel` donne le matériel de tous les essais, à lire la veille ; `python -m openride_core.tools.guide bips` sert à régler le volume avant de monter sur le vélo ; `--muet` coupe les bips et `--sans-attente` enchaîne sans pause. Agrandir la police du terminal (Ctrl + +) pour le lire depuis le vélo.

`python -m openride_core.tools.seance_guidee --materiel` affiche ce qu'il faut préparer, sans rien écrire ; `--retirer` efface les parcours d'essai.

### 0.6 Matériel à préparer, par jour

| Jour | Matériel | Préavis dans l'essai |
| --- | --- | --- |
| Vélo (D, E, G) | Vélo sur le HomeTrainer, Bluetooth du PC allumé, aucune autre application reliée au trainer ; les deux boîtiers du Click réveillés, pile CR2032 de secours ; ceinture humidifiée ; bidon, serviette ; écran visible depuis le vélo, son audible ; FTP et poids à jour dans les réglages | 1 min avant de retirer la ceinture, avant le sprint, avant la pause ERG et avant chaque fin de séance |
| X5 (G1) | Le même vélo, un braquet moyen gardé tout l'essai, 5 min d'échauffement avant | Paliers annoncés par l'outil |
| X8 (G2) | Les deux boîtiers, piles chargées, jeu fermé ; vélo conseillé | Rappel d'appui toutes les 5 min |
| Boutons (G3) | Les deux boîtiers, piles chargées, jeu fermé, son du PC allumé | Bip au début de chaque appui demandé |
| X16, X13 (H) | Rien (trainer simulé) ; PC sans mise en veille, sur la GTX 1060 | Bip au départ et à la fin |

---

## A. PC, installation et mise à jour

### A1. Recette du PC en une commande (X4) et état du GPU

- **Prérequis :** `core/.venv` à jour (`pip install -c constraints.txt -e "core[dev]" -e "compiler[dev]"`), `GODOT` défini.
- **Étapes :**
  1. `nvidia-smi` : le pilote NVIDIA est chargé, la GTX 1060 est listée, aucun processus fantôme.
  2. `glxinfo -B | grep -E "renderer|version"` : rendu par la GTX 1060 (pas `llvmpipe`).
  3. `lscpu | grep -E "Model name|MHz"` et `free -h` : relever CPU et mémoire libre.
  4. `cd Open_ride_linux && python3 scripts/recette_pc.py` (25 min environ, rien à faire).
- **Attendu :** `resume.txt` avec chaque étape OK (core, compilateur, engine, bout en bout, tests graphiques, confidentialité) ; `test_tree_renderer` compris (87 ms relevés sur ce PC le 27 octobre après O1, seuil 170 ms).
- [ ] GPU et pilote corrects
- [ ] `recette_pc.py` : toutes les étapes OK
- **Journaux :** `~/OpenRide/recettes/<date>_<heure>/` (`resume.txt`, un journal par étape, `perf.csv`).
- **Si échec :** relancer seulement l'étape en cause (`--seulement engine`) pour confirmer, puis donner le dossier. `llvmpipe` au point 2 : pilote NVIDIA à réinstaller, ne pas continuer les blocs D à H.

### A2. Icône et lancement sans terminal

- **Étapes :** ouvrir le menu des applications, chercher « OpenRide » : trois entrées (OpenRide, Libérer le trainer, Mettre à jour) avec l'icône. Lancer **OpenRide** par l'icône.
- **Attendu :** pas de terminal ; compilation des nouvelles traces avec notification si besoin ; écran « Connexion des appareils ».
- [ ] Trois entrées avec l'icône, lancement sans terminal
- **Si échec :** `scripts/install-desktop.sh` puis réessayer ; une fenêtre d'erreur donne le chemin du journal.

### A3. Mise à jour avec le jeu ouvert (PR #391, en revue)

- **Code :** la branche de la PR #391 (§0.2), suivie avec `--track`, donc « Mettre à jour » peut tirer.
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

### A4. Numéro de version (O2)

- **Étapes :** `openride --version`, `openride-core --version`, `openride-compiler --version` ; lancer OpenRide puis lire la première ligne du journal du lanceur.
- **Attendu :** « openride 0.9.0 », « openride-core 0.9.0 », « openride-compiler 0.9.0 » ; journal : `[openride] OpenRide 0.9.0`.
- [ ] Même numéro partout
- **Si échec :** noter la sortie exacte.

### A5. Installation sur un système propre (X29), facultatif

- **Étapes :** `python3 scripts/recette_install.py --mode home` (15 min environ ; le mode `docker` demande Docker). À la main, si tu as le temps : `sudo adduser essai`, puis depuis ce compte `scripts/install.sh` et lancement par l'icône (O8 ligne 1).
- **Attendu :** clone, installation, commandes, `config.toml`, raccourcis valides, premier démarrage sur trainer simulé, mise à jour qui garde les données octet pour octet.
- [ ] `recette_install.py` OK
- [ ] Second compte (facultatif)
- **Journaux :** `~/OpenRide/recettes_install/<date>/`.

---

## B. Appareils et ceinture

### B1. Écran « Connexion des appareils » (N13)

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

- **Étapes :**
  1. Ceinture portée et humidifiée, HomeTrainer allumé. `bluetoothctl`, puis `scan on` pendant 20 s, puis `scan off`, `quit`.
  2. `openride-core devices` : rôle « ceinture » ?
  3. Pendant une séance (bloc D), lire la FC au HUD, puis retirer la ceinture 30 s.
- **Attendu :** la ceinture n'apparaît ni dans `bluetoothctl` ni comme ceinture dans `devices` (elle n'émet qu'en ANT+) ; la FC au HUD arrive par le relais du trainer ; ceinture retirée, la FC relayée se fige puis, au bout de 15 s (`[trainer] hr_relay_freeze_s`, lot Q5), est écrite comme absente au journal et au HUD ; `hr = "none"` dans `config.toml` est le bon réglage.
- [ ] Absente du scan Bluetooth
- [ ] FC relayée par le trainer visible au HUD
- [ ] FC figée ceinture retirée, puis absente au bout de 15 s
- **Si échec :** si la ceinture apparaît dans le scan, noter son nom (pas son adresse) : ce serait un autre modèle.

---

## C. Menus et réglages

Commandes de référence (plan des boutons, spécification générale §7.1, PR #287) : + / − courts pour l'élément suivant ou précédent, + / − longs pour sauter de cinq ; A court pour l'élément suivant, A long pour valider ; Y pour revenir (sur l'écran de pause : reprendre) ; flèches gauche et droite du Click comme − et + ; Z ne fait rien dans un menu. Clavier en attendant O17 : flèches bas et haut, Page suivante et Page précédente, Tab (A court), Entrée (A long, valider), Échap (Y).

### C1. Menus au Click et au clavier

- **Étapes :** parcourir l'accueil, la liste des parcours, la liste des entraînements, revenir, au Click puis au clavier.
- **Attendu :** tout est pilotable au Click seul ; Y revient toujours d'un écran ; aide des commandes lisible.
- [ ] Menus au Click seul
- [ ] Menus au clavier

### C2. Menu principal (N15)

- **Étapes :** sur l'accueil, choisir « Parcours : … », un parcours, puis « Session libre », puis revenir et choisir « Session ERG ».
- **Attendu :** six entrées (Parcours, Session libre, Session ERG, Session simulée, Réglages, Quitter ; décision D10 : « Monde ouvert » est réservé à la série W) ; le parcours choisi s'affiche sur l'accueil ; « Session libre » mène à « Prêt : session libre » ; « Session ERG » mène à la liste des entraînements ; sans parcours choisi, la liste des parcours passe d'abord ; « Quitter » demande confirmation.
- [ ] Accueil à six entrées, parcours affiché
- [ ] Écran « Prêt » correct pour libre et ERG
- **Si échec :** noter l'écran et la touche ; journal du lanceur, lignes `[engine]`.

### C3. Réglages (O3/O4)

- **Étapes :** Réglages → FTP : + / − puis A long pour enregistrer ; refaire avec Y pour annuler ; changer la qualité et le thème ; lire la ligne « OpenRide X.Y.Z » en bas ; quitter et relancer OpenRide.
- **Attendu :** FTP, poids, difficulté, braquet de départ, qualité et thème modifiables ; la valeur enregistrée est écrite dans `~/OpenRide/config.toml` et retrouvée après relance ; l'annulation ne change rien ; qualité et thème s'appliquent tout de suite au décor ; réglages refusés pendant une séance.
- [ ] Modifier, enregistrer, annuler
- [ ] Valeurs gardées après relance (O8 critère « FTP utilisée par l'ERG » : voir E3)
- [ ] Qualité et thème appliqués tout de suite

### C4. Curseur de difficulté sur l'écran de pause (Q1, O4)

- **Étapes :** en séance libre (bloc D), Y pour la pause, déplacer le curseur de difficulté de 50 % à 40 %, reprendre.
- **Attendu :** curseur de 0 à 100 % par pas de 10 % ; le journal du core note `Difficulté : 50 % -> 40 %` ; `config.toml` n'est pas modifié ; défaut 50 %.
- [ ] Curseur de pause actif, journal correct, `config.toml` inchangé

### C5. Flèches, souris, A et Z du Click (plan des boutons, PR #287)

- **Étapes :** dans les menus : flèche bas, flèche haut ; clic gauche sur un élément, clic droit, molette ; bouton A puis Z du Click (appui court et long) ; un appui sur + d'environ 0,7 s (ni court ni long) ; en séance, flèche haut.
- **Attendu :** bas = élément suivant, haut = précédent ; clic gauche valide, clic droit revient, molette choisit ; A court passe à l'élément suivant, A long valide ; Z ne fait rien dans un menu ; A et Z sans effet en séance libre (Z servira en ERG avec O17) ; l'appui ambigu est expliqué dans le bandeau ; aide des commandes visible dans tous les menus, « Y reprendre » sur la pause, rappel des commandes au départ ; en séance, haut reste « braquet plus dur ».
- [ ] Flèches dans le bon sens
- [ ] Souris
- [ ] A et Z du Click
- [ ] Appui ambigu expliqué, aide visible

---

## D. Séances SIM et session simulée

### D1. Séance libre guidée de 25 min en SIM (O8 ligne 4)

- **Prérequis :** matériel du jour vélo (0.6) ; `python -m openride_core.tools.seance_guidee` lancé une fois (20 s).
- **Étapes :** OpenRide par l'icône → « Parcours » → `recette-velo` → « Session libre » → « Démarrer », puis suivre les consignes du bandeau : échauffement 5 min, 10 appuis sur +, 10 sur − (ou B du boîtier droit si le − se tait), appuis longs, A et Z, pause par Y avec le curseur de difficulté, ceinture retirée 30 s puis remise, un changement de braquet par minute en montée, roue libre, sprint de 10 s, retour au calme, puis Y → « Terminer et enregistrer ».
- **Attendu :** chaque consigne arrive avec un bip, les préavis une minute avant ; braquets nets et perceptibles, un bip par appui, braquet borné de 1 à 24 ; pause et reprise par Y ; FC figée ceinture retirée, puis repartie (B2) ; à la fin : consigne annulée, trainer rendu, FIT écrit, bilan affiché.
- [ ] Consignes et préavis à l'heure, avec bip
- [ ] Braquets perceptibles, appuis tous reçus
- [ ] Pause et reprise par Y
- [ ] Arrêt propre, FIT et bilan
- **Journaux :** lignes `[essai]` du journal du lanceur (`grep "\[essai\]" ~/run_trainer.log`) ; `python -m openride_core.tools.log_report` (dernier journal), `openride-core summary`, mesures `Perf` du journal.
- **Si échec :** pour un boîtier muet, noter l'heure (problème du boîtier gauche, essai du lot Q6 en J5) et continuer avec B. Aucune consigne à l'écran : vérifier `~/OpenRide/Essais/recette-velo.consignes.json` et la ligne `[essai] … consignes chargées` du journal.

### D2. Session simulée et retour au matériel réel (N15)

- **Étapes :** accueil → « Session simulée » → confirmer ; démarrer une courte séance libre ; revenir à l'accueil → « Revenir au matériel réel ».
- **Attendu :** l'engine se ferme et revient seul (code 65) ; accueil « OpenRide — session simulée » ; la séance roule sans pédaler (trainer, Click et ceinture simulés) et le vrai trainer ne bouge pas ; « Revenir au matériel réel » relance sur le vrai matériel (code 64) et l'écran de connexion réapparaît.
- [ ] Passage en session simulée
- [ ] Séance simulée sans toucher au vrai trainer
- [ ] Retour au matériel réel
- **Journaux :** journal du lanceur (`--trainer sim --input sim --hr sim --sim-scenario nominal` au relancement du core).

### D3. Trainer libéré après la séance (O8 ligne 11)

- **Étapes :** après D1, quitter OpenRide, ouvrir une autre application de vélo et s'y connecter au HomeTrainer.
- **Attendu :** connexion immédiate. Sinon « OpenRide – Libérer le trainer » doit suffire.
- [ ] Autre application connectée sans manipulation

### D4. Nouvelle séance après le bilan

- **Étapes :** après le bilan, « Nouvelle séance ».
- **Attendu :** le parcours choisi est rechargé, écran « Prêt », séance qui démarre.
- [ ] Nouvelle séance sans relancer OpenRide

---

## E. ERG

Rappel des commandes en ERG (état de `main`) : appui court + / − = intensité ± 2 % ; appui long + = bloc suivant ; appui long − = pause ERG ; Y = pause de la séance. Le lot O17 passera aux gestes définitifs (± long = biais ± 10 %, Z = bloc suivant) : son essai est en J7.

### E0. Séance ERG guidée de 13 min

- **Prérequis :** D1 faite (ou `seance_guidee` lancé), FTP à jour.
- **Étapes :** « Parcours » → `recette-erg` → « Session ERG » → « Recette ERG guidée » → « Démarrer », puis suivre les consignes : intensité + 2 % puis − 2 % au Click, écoute du bip avant le changement de bloc, pause de 10 s en récupération, deuxième effort, retour au calme, bilan.
- **Attendu :** bandeau ERG avec tous les blocs, cible tenue, biais affiché au bandeau et au bilan, bip à T − 3 s à chaque changement de bloc, trainer relâché pendant la pause, cible et écart par bloc au bilan.
- [ ] Biais ± 2 % visible et au bilan
- [ ] Bip à T − 3 s, cible tenue
- [ ] Pause en ERG et reprise
- **Journaux :** lignes `[essai]` (puissance et cible au moment de chaque consigne), `openride-core summary`.

### E1. Créer un entraînement court au Click (N16)

- **Étapes :** Session ERG → « Créer un entraînement (intervalles) » : échauffement 2 min, 2 répétitions, effort 1 min à 100 %, récupération 1 min à 50 %, retour au calme 1 min ; « Enregistrer et choisir » ; démarrer et rouler jusqu'au bout (environ 8 min).
- **Attendu :** fichier `intervalles_2x60s_100.zwo` dans `~/OpenRide/Workouts/`, ligne « Créé : … », focus sur le nouvel entraînement ; en séance : bandeau ERG avec tous les blocs du début à la fin, histogramme, bip à T − 3 s avant chaque changement de bloc, cible tenue par le trainer, biais ± 2 % au Click affiché.
- [ ] Création et choix au Click
- [ ] Bandeau et histogramme complets
- [ ] Bip à T − 3 s à chaque bloc
- [ ] Cible tenue, biais ± 2 % visible
- **Journaux :** `openride-core summary` (cible et écart par bloc, biais).

### E2. Importer un exercice (N16)

- **Prérequis :** un fichier `.zwo`, `.erg` ou `.mrc` dans `~/Téléchargements` (par exemple une copie de `core/workouts/tempo_2x15.erg`, ou un export GoldenCheetah, qui reste sur le PC).
- **Étapes :** Session ERG → « Importer un fichier » → choisir le fichier ; refaire l'import du même fichier.
- **Attendu :** fichiers proposés du plus récent au plus ancien avec leur dossier ; copie dans `~/OpenRide/Workouts/`, « Importé : … » ; second import du même fichier : marqué « déjà importé », pas de doublon ; un fichier différent du même nom prend le suffixe `_2`.
- [ ] Import et choix
- [ ] Pas de doublon ni d'écrasement

### E3. `sweet_spot_3x10` complet (O8 ligne 5)

- **Étapes :** choisir `sweet_spot_3x10` (60 min : échauffement 10 min, 3 × 10 min à 90 % de la FTP, récupérations 5 min à 55 %, retour au calme 5 min) et le rouler en entier, ou au moins jusqu'à la fin du premier effort (20 min).
- **Attendu :** cibles calculées sur la FTP des réglages ; cibles tenues ; biais ± 2 % ; bips ; bandeau lisible à 2 m.
- [ ] Séance complète (ou 20 min) sans défaut
- **Journaux :** `openride-core summary`, `log_report`.

### E4. Entraînement choisi après une séance terminée (PR #291)

- **Étapes :** finir une séance libre courte (2 min), puis depuis le bilan choisir un entraînement ERG et démarrer.
- **Attendu :** la séance part en ERG avec le bandeau (avant la correction, elle repartait en SIM sans bandeau).
- [ ] ERG pris en compte après une première séance

---

## F. Fichiers, plans et courbes (sans pédaler)

### F1. FIT de séance dans Garmin Connect et GoldenCheetah (O8 ligne 21)

- **Étapes :** importer le FIT de D1 ou E1 (`~/OpenRide/Activities/`) dans Garmin Connect, puis dans GoldenCheetah.
- **Attendu :** import sans erreur, puissance, cadence et FC présentes.
- [ ] Garmin Connect
- [ ] GoldenCheetah

### F2. Traces Garmin déposées dans le dossier (O5)

- **Étapes :** copier dans `~/OpenRide/GPX/` une sortie exportée de Garmin Connect telle quelle (`.fit`, `.tcx`, `.fit.gz` ou `.zip`) ; lancer OpenRide par l'icône ; en plus, copier une archive `.zip` vide.
- **Attendu :** compilation au lancement avec notification ; le parcours apparaît dans la liste et se roule ; l'archive vide est refusée avec un message sans empêcher les autres ; deux fichiers de même nom (`col.gpx`, `col.fit`) : un seul compilé, l'autre signalé.
- [ ] Sortie Garmin compilée et roulée
- [ ] Archive invalide refusée proprement
- **Journaux :** journal du lanceur (compilation), `openride-compiler list`.
- **Rappel :** ces traces restent sur le PC, jamais dans le dépôt.

### F3. Plans d'entraînement (O11)

- **Étapes :** `openride-core plan install`, `plan list`, `plan show reprise_4_semaines`, `plan start reprise_4_semaines`, `plan today` ; après une séance de l'entraînement du jour roulée à 80 % ou plus, `plan today` et `openride-core history --weeks 2`.
- **Attendu :** deux plans installés sans rien écraser ; durée et TSS par semaine ; séance du jour indiquée ; une fois roulée, elle compte (pourcentage fait), et `history` mentionne le plan. Le choix du plan depuis le menu est l'essai J3 (O12).
- [ ] Installation et affichage des plans
- [ ] Séance du jour comptée

### F4. Modèle des courbes (O13)

- **Étapes :** `UNIT=test_workout_chart_model engine/tests/run_engine_tests.sh`.
- **Attendu :** tous les tests passent ; le temps de calcul de la géométrie d'une longue séance reste faible. L'affichage à l'écran viendra avec O14 : rien à voir en séance pour l'instant.
- [ ] Tests du modèle OK

---

## G. Trainer et Click (outils de test X5 et X8)

### G1. Banc de latence du trainer par paliers (X5)

- **Prérequis :** OpenRide fermé, aucune autre application reliée au trainer, 5 min d'échauffement, un braquet moyen gardé tout l'essai, cadence tenue à 85 tr/min. Tout est chronométré par l'outil.
- **Étapes :** essai à blanc `python -m openride_core.tools.trainer_steps --trainer sim --mode sim --fast` ; puis sur le vélo `python -m openride_core.tools.trainer_steps --mode sim` (4 min environ), puis `--mode erg --cadence 85` (3 min environ).
- **Attendu :** pour chaque palier : délai consigne → écriture → accusé 0x80, t10, t63, t90, stabilisation, dépassement ; délai stable de 1 à 2 s (à noter s'il dépasse 3 s) ; trainer relâché à la fin.
- [ ] Essai à blanc OK
- [ ] Mode SIM sur le vélo
- [ ] Mode ERG (facultatif)
- **Journaux :** `~/OpenRide/trainer_steps/<date>_<heure>/` (`rapport.html`, `steps.csv`).
- **Si échec :** `--analyse DOSSIER` refait l'analyse ; donner le dossier.

### G2. Recette guidée du Click, 30 min (X8, O8 ligne 6)

- **Prérequis :** les deux boîtiers, piles chargées (une CR2032 de secours), jeu fermé.
- **Étapes :** essai à blanc `python -m openride_core.tools.click_recette --sim` ; puis `python -m openride_core.tools.click_recette --minutes 30 --rappel 5`, en pédalant ou non : appuyer sur chaque bouton demandé, puis un appui à chaque rappel.
- **Attendu :** chaque bouton (+, − du boîtier gauche, B et Y du boîtier droit, appuis longs) coché avec le bon boîtier ; sur 30 min, silences, coupures et reprises de chaque boîtier relevés. Défaut connu : le boîtier gauche peut se taire 35 à 60 s après la connexion (B du boîtier droit sert de « − ») ; l'outil dira à quelle minute.
- [ ] Essai à blanc OK
- [ ] Tous les boutons reconnus
- [ ] 30 min : aucune coupure non reprise (sinon heure du silence notée)
- **Journaux :** `~/OpenRide/click_recette/<date>/` (`rapport.txt`, `notifications.csv`).

### G3. Test guidé des boutons du Click, 5 min (plan des boutons, spécification générale §7.1)

- **Prérequis :** les deux boîtiers, piles chargées, jeu fermé, son du PC allumé (`python -m openride_core.tools.guide bips` pour régler le volume). Pas besoin de pédaler.
- **Étapes :** essai à blanc `python -m openride_core.tools.boutons_click --sim` (3 min, sans matériel : un cycliste simulé fait les appuis, on regarde seulement) ; puis `python -m openride_core.tools.boutons_click`. Réveiller les deux boîtiers, puis faire les 17 appuis demandés un par un : boîtier gauche d'abord (flèches gauche, droite, haut, bas ; puis − court, long, moyen d'environ 0,7 s), sans traîner : il se tait environ 70 s après sa connexion (essai du 27 octobre, firmware 1.0.2 avant mise à jour ; l'outil l'annonce « bridé » et saute ses étapes), puis le droit (+ court, long, moyen ; B court et long ; A court et long ; Y ; Z court et long). Chaque étape commence par un bip et passe seule à la suivante 4 s après l'appui reconnu, le temps de lire l'encadré (`--lecture` pour changer) ; 30 s au plus pour appuyer (`--delai`).
- **Attendu :** chaque appui reçu s'affiche dans un encadré, vert si c'est celui demandé, jaune sinon : événement décodé (`A_LONG`…), touche et boîtier, puis l'action de l'appui dans chaque mode (menus, SIM, ERG, Cyber-Rogue, monde ouvert) telle que l'écrit le tableau §7.1 ; un bip d'appui (court : une note, long : deux notes montantes, ni court ni long : une note grave) ; un verdict à la fin, « 17/17 appuis reconnus ». L'encadré montre le plan cible : en ERG, ± long et Z ne font le biais ± 10 % et le bloc suivant qu'avec O17 (J7).
- [ ] Essai à blanc OK
- [ ] Boîtier gauche : 7 appuis reconnus (sinon minute du silence notée, voir J5)
- [ ] Boîtier droit : 10 appuis reconnus
- **Journaux :** `~/OpenRide/boutons_click/<date>/` (`rapport.txt`, `rapport.json`, `guide.jsonl`).
- **Si échec :** garder le dossier ; `-v` affiche le journal du Click.

---

## H. Performance et endurance (PC seul, fenêtre visible)

### H1. Sonde de performance du moteur (X13)

- **Étapes :** `python3 engine/tests/sim_bench.py --native --probe --scenario erg_village --duration 300` ; en plus, une vraie séance avec la sonde : `OPENRIDE_PERF_PROBE=~/OpenRide/sonde/moteur.csv openride` puis, dans un second terminal, `python3 engine/tests/perf_probe.py watch`.
- **Attendu :** une ligne par seconde (temps d'image p50 et p99, CPU et GPU, appels de dessin, mémoire vidéo, nvidia-smi) ; en qualité basse sur le village : 30 images/s au moins (O8 ligne 17) ; GPU, pas de CPU saturé.
- [ ] Sonde en séance simulée
- [ ] Sonde en vraie séance
- [ ] 30 images/s ou plus en qualité basse
- **Journaux :** dossier du banc (`sonde.csv`, `sonde.txt`, `rapport.html`).

### H2. Endurance d'une heure (X16, O8 ligne 18)

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

## J. Lots fusionnés le 27 octobre

Ces essais s'ajoutent aux blocs A à H ; chacun dit s'il se fait sur le vélo. Les traces et les résultats réels restent sur le PC.

### J1. Arbres en qualité haute (O1, O8 ligne 19)

- **Étapes :** `UNIT=test_tree_renderer engine/tests/run_engine_tests.sh` ; puis Réglages → qualité `high`, une séance de 10 min sur un parcours boisé (`essai-69` ou un parcours OSM).
- **Attendu :** préparation d'une tuile sous 170 ms (87 ms relevés le 27 octobre) ; aucun à-coup à l'arrivée des tuiles d'arbres.
- [ ] Test des arbres sous le seuil
- [ ] Séance en `high` sans à-coup

### J2. Test de FTP par rampe (O10, O8 ligne 12), sur le vélo

- **Prérequis :** reposé, FTP actuelle dans les réglages ; un parcours en boucle (un parcours avec arrivée termine la séance).
- **Étapes :** `openride-core run --autostart --route <boucle> --ftp-test ramp` ; paliers d'une minute jusqu'à ne plus tenir ; puis `openride-core ftp-test` et, si le résultat convient, `openride-core ftp-test --accept`.
- **Attendu :** fin détectée seule (cadence sous 50 tr/min 5 s, ou puissance sous 80 % de la cible 10 s), retour au calme de 5 min à 100 W ; FTP proposée = 75 % de la meilleure minute ; après `--accept`, la nouvelle FTP est dans `~/OpenRide/config.toml` (copie `.bak`).
- [ ] Fin de rampe détectée
- [ ] FTP proposée puis acceptée

### J3. Plans, test de FTP et bibliothèque au menu (O12, PR #396 en revue ; O8 lignes 12, 13 et 15)

- **Code :** la branche de la PR #396 (§0.2), ou `main` après sa fusion.
- **Étapes :** au menu, ouvrir les plans, démarrer un plan et lancer la séance du jour ; ouvrir « Test de FTP » ; trier et filtrer la bibliothèque de parcours ; après J2, accepter la FTP proposée depuis le menu.
- **Attendu :** tout se fait au Click, sans terminal ; la séance du jour est comptée dans le plan (`openride-core plan today`) ; la FTP acceptée au menu est écrite dans `config.toml`.
- [ ] Plan et séance du jour au menu
- [ ] Test de FTP et acceptation au menu
- [ ] Bibliothèque triée et filtrée

### J4. Pack « Cols célèbres » (O16), avec réseau

- **Étapes :** `openride-compiler route-pack-build cols_celebres --install` (plusieurs minutes, OpenStreetMap et altitudes) ; `openride-compiler route-pack-list` ; rouler un col au choix.
- **Attendu :** chaque col construit est contrôlé à ± 5 % (longueur et dénivelé de la recette) ; une trace hors tolérance est refusée avec un message qui nomme le col et le point de passage à corriger ; les cols acceptés apparaissent dans la bibliothèque.
- [ ] Pack construit, écarts notés
- [ ] Un col roulé

### J5. Boîtier gauche du Click (Q6), sur le vélo

- **Étapes :** dans `~/OpenRide/config.toml`, `[drivers] click_trace_raw = true`, séance de 10 min ; puis `click_rehandshake_s = 30` et une autre séance de 10 min.
- **Attendu :** le journal dit à quelle minute le boîtier gauche se tait ; avec la reprise, dire s'il revient.
- [ ] Silence du boîtier gauche daté
- [ ] Reprise essayée (revient ou non)

### J6. Horizon et pentes à l'écran (Y1, Q2), sur le vélo

- **Étapes :** `essai-69` en qualité `medium` puis `low` ; puis `[render] visual_grade_scale` à 1,0, 1,3 et 1,5 (une montée à chaque fois).
- **Attendu :** brouillard opaque à 6 km en `medium` et 4 km en `low`, rien qui surgit au loin ; lignes `[perf-rendu]` au moins aussi bonnes que le 25 octobre (59,4 images/s, p99 22 ms en `low`) ; choisir le facteur de relief par défaut.
- [ ] Horizon accepté en `medium` et `low`
- [ ] Facteur de relief choisi : …

### J7. Boutons de l'ERG définitifs (O17, après sa livraison), sur le vélo

- **Étapes :** séance ERG courte, au Click puis au clavier : ± longs, Z, Y.
- **Attendu :** ± long = biais ± 10 % (borné à 80 % et 120 %), Z = bloc suivant, Y = pause ; ± court = biais ± 2 % comme avant.
- [ ] Gestes du plan commun au Click
- [ ] Mêmes gestes au clavier

### J8. Décor vivant (P16 puis P17, mises à jour 1.x)

- **Étapes :** [RECETTE_P16.md](RECETTE_P16.md) (vent, nuages, sons), puis [RECETTE_P17.md](RECETTE_P17.md) (météo, animaux, véhicules, bord de route, foule, abri).
- [ ] Recette P16
- [ ] Recette P17

### J9. Mesures du monde ouvert (W0), avec réseau, sans pédaler

- **Étapes :** les deux commandes `openride-compiler world-measure` du cahier [W0](lots/LOT_W0_mesures_monde_ouvert.md) §7.
- **Attendu :** `rapport.md` et `rapport.json` écrits ; leurs chiffres servent au lot W1.
- [ ] Deux mesures faites, dossier donné

---

## I. Clôture

- [ ] `git switch main && git pull --ff-only` : retour sur `main`.
- [ ] `python3 Open_ride_linux/scripts/privacy/privacy_scan.py --all` : aucune donnée interdite dans le dépôt.
- [ ] `~/OpenRide/Logs/recette_notes.txt` relu.
- [ ] Message dans le fil : blocs faits, cases non cochées. Je lis les journaux sur le PC et ouvre un correctif ou une ligne de suivi par défaut.

Toutes les PR citées par la première version de ce protocole sont fusionnées depuis le 27 octobre, sauf la mise à jour avec le jeu ouvert (#391, qui remplace #290).
