# Lot N14 – Lancement sans terminal : premier démarrage, erreurs affichées, mise à jour depuis l'icône

## 1. Objectif

Demande du propriétaire du 25 octobre : pouvoir lancer le jeu sans passer par des lignes de commande. La série N couvre déjà l'essentiel :

| Besoin | Lot |
| --- | --- |
| Icône et entrée de menu du bureau | L8 (livré) : `scripts/install-desktop.sh` |
| Choisir parcours et entraînement, rouler, bilan, quitter, sans `--autostart` | N6 (avec N2 à N5) |
| Nouvelles traces GPX compilées au lancement | N11 |
| Trouver et enregistrer le trainer et le Click | N12 et N13 |
| Séance reprise après un plantage du core | N8 |

Ce lot comble ce qui manque encore pour qu'aucun terminal ne soit nécessaire **après l'installation** :
- **Premier démarrage :** une configuration locale par défaut est créée, et le menu propose la section « Appareils ».
- **Erreurs :** un problème au lancement s'affiche dans une fenêtre et non dans un terminal.
- **Mise à jour :** une deuxième entrée de menu met OpenRide à jour.

L'installation elle-même reste une seule commande, à taper une fois et documentée.

## 2. À lire

1. `docs/lots/00_INDEX.md`, cahiers L8, K6, M8, N6, N11 et N13.
2. Code : `core/src/openride_core/launcher.py` (`Supervisor`, `DEFAULT_CORE_ARGS`, journal du lanceur), `core/src/openride_core/config.py` (`load`, valeurs par défaut), `scripts/install-desktop.sh`, `scripts/desktop/openride.desktop.in`.

## 3. Prérequis

N11 fusionné (même fichier `launcher.py`). À faire avant N6, qui change seulement le défaut `--autostart`.

## 4. Travail demandé

- **Premier démarrage :** si `~/OpenRide/config.toml` n'existe pas, le lanceur le crée à partir d'un modèle commenté (`scripts/config.example.toml`, nouveau, sans aucune valeur réelle), crée `~/OpenRide/GPX/` et `~/OpenRide/Workouts/`, puis passe `--first-run` au core pour que le menu (N13) ouvre la section « Appareils ». En attendant N13, il affiche « Configurez vos appareils : openride-core devices --save » dans la fenêtre d'information.
- **Fenêtre d'erreur :** quand le lanceur s'arrête sur une erreur (Godot introuvable, port IPC occupé, configuration invalide, trainer réservé par une autre application, plantages répétés du core), il montre un message court et l'emplacement du journal. Il utilise `zenity --error` s'il existe, sinon `kdialog`, sinon `notify-send`, sinon le journal seul. La fonction d'affichage est injectable pour les tests. Le message dit quoi faire, par exemple « Fermez l'application Zwift ou lancez OpenRide → Libérer le trainer ».
- **Entrées de bureau supplémentaires,** installées par `install-desktop.sh` et retirées par `--uninstall` :
  - `OpenRide – Libérer le trainer` lance `openride-core release-trainer`, avec le résultat en notification ;
  - `OpenRide – Mettre à jour` lance le nouveau script `scripts/update.sh`. Ce script fait `git pull --ff-only` puis `pip install -c constraints.txt -e core -e compiler` dans le venv. Il refuse si le dépôt a des modifications locales ou n'avance pas en avance rapide, et ne fait jamais de `reset` ni de poussée. Le résultat est affiché en notification.
- **Installation en une commande :** `scripts/install.sh` crée le venv, installe le core et le compilateur, vérifie Godot 4.3 (chemin demandé une fois et gardé dans `~/OpenRide/config.toml`), puis appelle `install-desktop.sh`. Il peut être relancé sans dommage. Le README décrit cette seule commande.
- **Quitter :** l'entrée « Quitter » du menu ferme proprement l'engine et le core, et libère le trainer. Le lanceur ne laisse aucun processus derrière lui. C'est déjà prévu par K6 : à vérifier et à tester ici.

## 5. Fichiers concernés

- **Nouveaux :** `scripts/install.sh`, `scripts/update.sh`, `scripts/config.example.toml`, `scripts/desktop/openride-release.desktop.in`, `scripts/desktop/openride-update.desktop.in`, `core/tests/test_launch_no_terminal.py`.
- **Modifiés :** `core/src/openride_core/launcher.py`, `core/src/openride_core/__main__.py` (option `--first-run`, transmise sans effet tant que N13 n'est pas fait), `scripts/install-desktop.sh`, `core/tests/test_desktop_entry.py`, `README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** l'engine, le contrat IPC, `~/OpenRide/config.toml` réel pendant les tests (dossier `HOME` temporaire).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Avec un `HOME` vide : le premier lancement (moteur et core factices) crée la configuration à partir du modèle et les deux dossiers, et transmet `--first-run`. Le deuxième lancement ne transmet plus `--first-run` et ne touche pas la configuration.
3. Les cinq erreurs du §4 donnent chacune un message précis à la fonction d'affichage factice, et le lanceur sort avec un code non nul.
4. `install-desktop.sh` installe trois entrées valides (`desktop-file-validate` si présent) ; `--uninstall` les retire toutes.
5. `update.sh` sur un dépôt de test refuse proprement s'il y a des modifications locales ou si le dépôt n'avance pas en avance rapide, et réussit sinon.
6. `install.sh` lancé deux fois de suite dans un `HOME` temporaire donne le même résultat, avec Godot factice.
7. Aucune valeur réelle (adresse, nom d'appareil, chemin personnel) dans les fichiers ajoutés.

**Sur le PC cible (le propriétaire) :** depuis l'icône seulement, lancer OpenRide, rouler, quitter. Ensuite, lancer « Mettre à jour », puis « Libérer le trainer » pendant que le trainer est occupé, sans ouvrir de terminal.

## 8. Hors périmètre

- Paquet `.deb` ou Flatpak, et démarrage automatique à l'ouverture de session.
- Réglages (FTP, thème, qualité) depuis le menu : lot à rédiger si le propriétaire le souhaite.
