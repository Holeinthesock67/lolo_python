# Notes de version d'OpenRide Linux

Toutes les évolutions notables, version par version, au format [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).
Le numéro unique se trouve dans le fichier `VERSION` ; `scripts/bump-version.sh X.Y.Z` le change partout (lot O2).

## 0.9.0 – Non publiée

Première version complète avant la 1.0 : tout ce que contient `main` au 26 octobre 2026.

### Séance sur le home trainer
- Pilote FTMS du HomeTrainer : mode SIM (pente) et ERG (puissance), reconnexion, renvoi des erreurs ATT, relâche du trainer à la fermeture et `openride-core release-trainer`.
- Physique à 50 Hz, 24 braquets virtuels, pente anticipée et lissée, difficulté réglable pendant la séance (50 % par défaut).
- Entraînements ERG `.zwo`, `.erg` et `.mrc` (GoldenCheetah), biais ± 2 % (appui court) et ± 10 % (appui long), bloc suivant par Z et pause par Y au Click, bip avant chaque bloc (lot O17 : même plan de boutons que les autres modes).
- ERG dans une session libre, choisi sur l'écran de pause : ERG à puissance cible, ou ERG à cadence verrouillée (± 15 % autour de la cadence cible, puissance adaptée progressivement), et retour en SIM (lot O18).
- Aucune roue libre en ERG : consigne jamais sous 50 W, bloc FreeRide d'un `.zwo` roulé à 50 W ; test de FTP par la rampe seule, le test de 20 minutes est retiré (lot O19).
- Bots à puissance constante et fantôme d'une séance passée ; reprise d'une séance après un plantage du core.
- Ceinture cardio Bluetooth facultative.

### Zwift Click et appareils
- Zwift Click V2 (paire de boîtiers) et Zwift Cog, appuis courts et longs ; le clavier double le Click touche pour touche, mêmes durées d'appui (lot O17).
- Inventaire des appareils (`openride-core devices`), appairage depuis la ligne de commande et depuis le menu.
- Recherche de l'écran Appareils : plus d'échec « org.bluez.Error.InProgress » quand le trainer ou le Click se reconnectent ; message lisible si le Bluetooth est occupé ou éteint.

### Parcours
- Compilateur `openride-compiler` : traces GPX, FIT et TCX vers `.world`, relief Copernicus GLO-30, couches OpenStreetMap (bâtiments, végétation, points d'intérêt, eau).
- Compilation des nouvelles traces au lancement, packs de thèmes (`theme-list`, `theme-install`).

### Affichage (Godot 4.3)
- Route et terrain par tronçons, shader triplanaire, ciel, arbres, bâtiments, eau et sons.
- HUD, bandeau et histogramme ERG, menus au Click (parcours, entraînements, pause, fin de séance, appareils).

### Lancement et outils
- Lanceur unique `openride`, raccourcis de bureau, installation en une commande, erreurs dans une fenêtre.
- Journal de séance JSONL, export FIT, `summary`, `history`, analyse du journal (`log_report`).
- Bluetooth simulé, rejeu de séances, banc d'essai simulé, tests graphiques et intégration continue.
- Tests isolés du dossier personnel : HOME temporaire, aucune fenêtre, échec d'un test qui écrit hors de son dossier temporaire, une seule suite à la fois.
