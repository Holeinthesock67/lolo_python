# Notes de version d'OpenRide Linux

Toutes les évolutions notables, version par version, au format [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).
Le numéro unique se trouve dans le fichier `VERSION` ; `scripts/bump-version.sh X.Y.Z` le change partout (lot O2).

## 1.0.1 – 2026-11-01

Corrections, et trois petites options de menu mises de côté pendant le gel de la 1.0.

### Séance
- Départ au pédalage (lot O36) : après « Démarrer », l'écran « START YOUR ENGINES » attend le décor du départ, le trainer puis 3 secondes de pédalage à 30 tr/min avant de lancer chrono, distance, ERG et bots ; Y annule. Réglages › Séance : **Départ** (au pédalage ou immédiat) et **Cadence de départ**. Une run Cyber-Rogue n'attend pas de décor.
- Quatre bots et le fantôme ensemble (lot O35) : l'écran Prêt propose « Bot 1 » à « Bot 4 », chaque ligne apparaissant dès que la précédente est choisie ; les derniers choix reprennent jusqu'à quatre bots.

### Menus
- QWKcode saisi au clavier (lot O21) : « Saisir du QWKcode (clavier) » dans la liste des entraînements ERG.
- Texte des bots lisible sur ciel clair : orange, bleu du fantôme et gris éclaircis, contraste d'au moins 3:1.

### Ménage
- Fichiers `.uid` des vitrines `vitrine_amorces` et `vitrine_vehicules_pente` ajoutés.

## 1.0.0 – 2026-11-01

Première version publiée : tout ce que contient `main` au 1er novembre 2026. État de la recette : `docs/lots/LOT_O8_recette_1_0.md` §7.

### Séance sur le home trainer
- Pilote FTMS du HomeTrainer : mode SIM (pente) et ERG (puissance), reconnexion, renvoi des erreurs ATT, relâche du trainer à la fermeture et `openride-core release-trainer`.
- Physique à 50 Hz, 24 braquets virtuels, pente anticipée et lissée, difficulté réglable pendant la séance (50 % par défaut).
- Entraînements ERG `.zwo`, `.erg` et `.mrc` (GoldenCheetah), biais ± 2 % (appui court) et ± 10 % (appui long), bloc suivant par Z et pause par Y au Click, bip avant chaque bloc (lot O17 : même plan de boutons que les autres modes).
- ERG dans une session libre, choisi sur l'écran de pause : ERG à puissance cible, ou ERG à cadence verrouillée (± 10 % autour de la cadence cible, puissance adaptée progressivement, puissance gardée à la reprise après une pause), et retour en SIM (lot O18).
- Pilotage du trainer en « résistance calculée » par défaut : OpenRide calcule la force de la route et règle le frein du trainer, sans trou de résistance après un sprint ; le mode SIM du trainer reste au choix dans Réglages › Séance (lot RC).
- Aucune roue libre en ERG : consigne jamais sous 50 W, bloc FreeRide d'un `.zwo` roulé à 50 W ; test de FTP par la rampe seule, le test de 20 minutes est retiré (lot O19).
- Fin d'un entraînement ERG ou de la séance du jour d'un plan : le bandeau du haut invite à « Y puis A maintenu pour terminer et enregistrer », et la pause s'ouvre directement sur « Terminer et enregistrer » (champ `workout_done` de `state`, constat du vélo du 1er novembre).
- Bots à puissance constante et fantôme d'une séance passée ; reprise d'une séance après un plantage du core.
- Ceinture cardio Bluetooth facultative.

### Zwift Click et appareils
- Zwift Click V2 (paire de boîtiers) et Zwift Cog, appuis courts et longs ; le clavier double le Click touche pour touche, mêmes durées d'appui (lot O17).
- Inventaire des appareils (`openride-core devices`), appairage depuis la ligne de commande et depuis le menu.
- Monde ouvert : la recherche d'un lieu se fait aussi au Click, avec la grille de lettres du nom d'un profil (Z sur le globe), sans clavier (lot O31).
- Réglages : sous-écran **Avancé** (monde ouvert sans téléchargement, plafonds du cache et des thèmes installés, progression et Garage) ; tout interrupteur s'affiche oui / non ; la liste des réglages part en plusieurs datagrammes si besoin (lot O27).
- Réglages : décor vivant et relief exagéré dans Graphisme (pris au lancement suivant, avec « Relancer OpenRide maintenant »), ressenti du vent dans Vent ; mode du vent et thème par défaut affichés en français (lot O26).
- Écran Appareils : la ceinture choisie est vraiment utilisée (avant, elle était enregistrée sans être activée) ; « aucun » oublie le trainer ou la ceinture, « Oublier le Click » retire les deux boîtiers (lot O24).
- Recherche de l'écran Appareils : plus d'échec « org.bluez.Error.InProgress » quand le trainer ou le Click se reconnectent ; message lisible si le Bluetooth est occupé ou éteint.

### Parcours
- Compilateur `openride-compiler` : traces GPX, FIT et TCX vers `.world`, relief Copernicus GLO-30, couches OpenStreetMap (bâtiments, végétation, points d'intérêt, eau).
- Compilation des nouvelles traces au lancement, packs de thèmes (`theme-list`, `theme-install`).

### Affichage (Godot 4.7)
- Route et terrain par tronçons, shader triplanaire, ciel, arbres, bâtiments, eau et sons.
- La chaussée ne commence plus au milieu de l'herbe : sur un parcours ouvert, elle continue 100 m avant le départ et 200 m après l'arrivée, posée sur le terrain, sans arbre dessus ; distance et fiches du parcours inchangées.
- HUD, bandeau et histogramme ERG, menus au Click (parcours, entraînements, pause, fin de séance, appareils).

### Lancement et outils
- Lanceur unique `openride`, raccourcis de bureau, installation en une commande, erreurs dans une fenêtre.
- Journal de séance JSONL, export FIT, `summary`, `history`, analyse du journal (`log_report`).
- Bluetooth simulé, rejeu de séances, banc d'essai simulé, tests graphiques et intégration continue.
- Tests isolés du dossier personnel : HOME temporaire, aucune fenêtre, échec d'un test qui écrit hors de son dossier temporaire, une seule suite à la fois.
