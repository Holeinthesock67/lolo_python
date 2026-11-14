# Notes de version d'OpenRide Linux

Toutes les évolutions notables, version par version, au format [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).
Le numéro unique se trouve dans le fichier `VERSION` ; `scripts/bump-version.sh X.Y.Z` le change partout (lot O2).

## Non publié

### Pack « Cols célèbres » livré avec le jeu (lot PK1)
- Le pack des cols célèbres fait partie du jeu de base : construit une fois (`scripts/build_pack_base.sh`), livré déjà compilé dans le paquet, il s'installe au premier démarrage avec les contenus de départ, sans réseau et sans rien écraser.
- Écran « Réglages › Contenus » : sans réseau ni confirmation quand le paquet porte le pack ; crédits OpenStreetMap (ODbL), Copernicus et WorldCover sur la ligne du pack et au §10 du guide d'utilisation.
- Liste des parcours : un parcours dont la fiche (`<trace>.toml`) porte un nom s'affiche sous ce nom (« Abra Málaga », « Alpe d'Huez ») au lieu de son identifiant (« abra-malaga ») ; l'identifiant ne change pas.
### Nettoyage après l'import de fichiers (lot NT2)
- `_on_command_failed` (main.gd) ne cite plus `list_imports`, retirée en révision 1.15 : les listes sans bandeau « sans réponse du core » sont celles que le client IPC relance (`IpcClient.LIST_COMMANDS`), testées par `test_list_commands.gd`.

### Grand Prix : plus de frôlements entre coureurs (lot GP12)
- Un coureur sur une voie imposée (esquive, flèches) double et s'écarte comme les autres au lieu de rouler dans la roue d'un plus lent de sa voie.
- Un objet (coup de fouet, super-forme, glissade du coureur de devant) ne pousse plus personne dans la roue devant : on freine roue contre roue, cycliste compris (vitesse virtuelle seulement, la pente envoyée ne change pas).
### Un circuit en boucle livré avec le jeu (lot O38)
- Nouveau parcours de démonstration « Circuit des Prés » : une boucle de 3 km dans les prés, départ au hameau, montées et descentes jusqu'à 5 %, une courbe en S serrée, étang et verger au milieu. Le Grand Prix des objets et toute course en tours s'y jouent sans trace personnelle.
- Ajouté à la prochaine installation des contenus de départ ; aucun autre parcours n'est réécrit. Trace, relief et décor sont entièrement inventés (aucune donnée réelle).
### Biomes sur le « Col du lacet » (lot W17 bis)
- Le parcours de démonstration « Col du lacet » reçoit une couche biome synthétique : de grandes taches de forêt tempérée (hêtres, chênes, quelques épicéas) à plus de 60 m de la route, entre des alpages au look habituel du col (biome `alpine` : sapins, herbe et roche d'avant la couche biome). La route passe toujours en alpage : vue dégagée et ciel visible comme avant.
- Générateur `openride-fake-world` 0.4.0 : une démonstration déjà installée est remplacée au prochain lancement, couche biome comprise.
### Nouveau biome : hauts plateaux (lot HP1, 6.0)
- Biome « hauts plateaux » (Altiplano, Tibet, Ladakh) : herbe jaune d'ichu en touffes, sol ocre, roche brun-rouge, air sec et très clair, lacs bleu profond ; lamas, vigognes et yacks ; maisons basses d'adobe à toit de paille.
- Le compilateur le pose seul sur le terrain ouvert au-dessus de 3 300 à 3 800 m sous 40° de latitude, sur les parcours comme dans le monde ouvert ; neige et glaciers restent alpins, les Alpes ne changent pas.
- Pack « Cols célèbres » : Ticlio (Pérou, 4 818 m).
- Construction des cols : une route en lacets qui sort de la zone chargée autour des points est cherchée dans une zone plus large ; un refus dit quel tronçon manque et si une route non revêtue passerait.
- Choix « hauts plateaux » dans « Biome du décor ».

### Canyons, fjords, îles volcaniques et rizières (lot U25, 6.0, partie 1)
- Quatre paysages célèbres s'ajoutent comme variantes des biomes existants, pas comme biomes : canyons rouges du plateau du Colorado, fjords de Norvège (côte ouest, Nordland, Lofoten), îles volcaniques de l'Atlantique (Canaries, Madère, Açores) et rizières d'Asie du Sud-Est. Le compilateur et le monde ouvert les posent avec la même table à grosse maille que les variantes régionales.
- Arbres du paysage : bouleaux et épicéas des fjords (sans palmiers ni pins parasols sur la côte, limite des arbres à 700–900 m), pinède canarienne et laurisylve sur les îles volcaniques, palmiers dans les rizières (sans vignes), pins et genévriers épars dans les canyons. Les fjords ont des maisons de bois peint (toit `bois_peint`).
- Sol du paysage : herbe verte et gneiss sombre au bord des fjords (au lieu du sable jaune de la côte), sable et grès rouges des canyons, cendres et basalte des îles, rizières vert vif.
- Un parcours compilé avant ce lot reste valide ; il faut le recompiler (`add-layer <parcours>.world biome`) pour voir les paysages. Strates des canyons, terrasses en eau des rizières et cascades des fjords viendront avec la partie 2.
- Format `.world` : membre facultatif `landscape` de la variante, toit `bois_peint` ; thème 2.0 : section `landscapes`. `--variant GROUND,ROOFS[,LANDSCAPE]` impose un paysage.
### Mode WTF lisible et objets reconnaissables (lot WTF9)
- Sous le nom de chaque gag, une ligne « À toi : … » dit quoi faire (puissance à tenir, Z court pour refuser le plat du chef, rien à faire pour les caméras). Le bandeau grossit un instant à chaque nouveau gag.
- Au premier passage de chaque gag et de chaque règle permanente (Katamari, cadence, peloton), une légende s'affiche 7 s à droite : ce qui se passe, ce que tu fais. Elle revient à la séance suivante.
- La carte du Katamari annonce le prochain objet, sa distance et s'il sera ramassé ou fera « boing ».
- Objets redessinés : la boule du Katamari est couverte d'objets collés (plus de boule rose unie) ; pomme, panneau, voiture, maison et église ont leur forme (plus de cubes de couleur) et sont posés sur la ligne de la boule ; la route qui s'effondre montre une lèvre de bitume déchiquetée, des fissures et des plaques qui basculent ; les plats du chef sont reconnaissables (spaghetti, gelée, accordéon, soufflé, piment).
- Le rose venait des couleurs choisies, pas d'un shader manquant : aucun matériau ni shader n'est chargé depuis un fichier dans la scène WTF.

### Import d'entraînements retiré du menu ERG
- La ligne « Importer un fichier » du sous-menu ERG est retirée (décision du propriétaire du 12 novembre). Un `.zwo`, `.erg`, `.mrc` ou `.qwk` se dépose directement dans `~/OpenRide/Workouts/` ; les entraînements livrés, « Créer un entraînement » et la saisie QWKcode ne changent pas.
- Contrat IPC, révision 1.15 : `list_imports` et `import_workout` répondent `error` `workout_invalid` (un engine plus ancien reste conforme) ; le message `imports` n'est plus envoyé.

### Parcours de démonstration nommés (lot O37)
- Les quatre parcours de démonstration livrés portent un vrai nom au menu : « Col du lacet » (ex-`demo`), « Tour des six paysages », « Route de la côte » et « Montée alpine ». Le tour en partie non revêtu (`demo-biomes-gravel`) quitte le jeu de base : le gravel étant coupé par défaut, il ressemblait au tour asphalté ; il reste pour les recettes. Les villages, belvédères et étangs ont des noms de lieux inventés au lieu de « Port Fictif » ou « Col Fictif » (panneau du sommet).
- Les démonstrations déjà installées sont remplacées au prochain lancement (l'ancien tour gravel est enlevé) ; un parcours du joueur n'est jamais touché.
- Le générateur des parcours des biomes est passé des tests de l'engine au compilateur : un jeu installé sans les tests les produit. Les bancs et les recettes gardent les noms techniques avec `--recette`.

### Le cycliste prend mieux les virages (lot CY1)
- Le vélo du joueur et des bots regarde où il va : il ne tourne plus 20 m avant un virage serré et ne roule plus en crabe (jusqu'à 29° dans un angle droit dessiné avec peu de points).
- Il se penche dans les virages selon sa vitesse (au plus 30°), et se redresse en ligne droite ou à l'arrêt. Sur la piste du vélodrome, il reste perpendiculaire à la piste dans les virages relevés.
- Sa trajectoire est lissée : il coupe légèrement les angles droits au lieu de faire un écart.
- La caméra suit le cap du vélo (lissé) au lieu de tourner 20 m avant le virage.

### Boîtier gauche du Click sans redémarrage, à l'essai (lot K9)
- `[drivers] click_reset_locked` devient un choix : `"reset"` (défaut, comme avant), `"keep"` ou `"off"` ; les anciens `true` et `false` sont toujours lus.
- `"keep"` essaie de garder le boîtier gauche déverrouillé (activation complète et réponse `ff 04 00`) et ne le redémarre que si Zwift le verrouille quand même. Essai sur le vélo du 8 novembre : sans effet sous le firmware 1.2.0 (verrou toujours vers 50 s), `"reset"` reste donc le défaut.
- Journal : durée de chaque fenêtre de boutons du boîtier gauche ; `click_recette --verrou keep --attente-rappel 8` compte les appuis perdus par tranche de 10 min.

### Mer, côte et plages dans les parcours compilés (lot U3)
- Un parcours compilé avec la couche eau reçoit la mer, tirée des lignes de côte d'OpenStreetMap et refermée sur le bord du terrain, îles comprises.
- Nouvelle couche `coast` (`--layers …,coast` ou `add-layer coast`) : le rivage (falaise, sable, galets ou roche) et les plages qui touchent la côte, pour la mer animée de la 3.0 (U9).
- Un parcours loin de la mer ne change pas.
- Tracteurs des champs loin de la route : leur sol est lu sur le terrain lointain, et la recherche de la route la plus proche ne parcourt plus des milliers de cases vides. Les tronçons de la Côte d'Opale bordés de grands champs se préparaient en 20 s, ce qui retardait le terrain proche et les arbres (à-coups au premier essai).
- Rangs des tracteurs dans les grands champs (plusieurs km, milliers de points) calculés sans relire tous les côtés du champ.
- La pleine mer est écrite en grands rectangles et non plus carré de 1 km par carré (214 aires deviennent une cinquantaine).

### Rendu plus léger (étude du 5 et 6 novembre)
- Medium et high : MSAA 2× et ombres du soleil en 2048 ; high sans lumière indirecte d'écran (SSIL) et filtrage anisotrope 8×. Tour des six biomes sur la GTX 1060 : environ −2,4 ms par image en medium et −4 ms en high.
- Feuillage et herbe éclairés plus simplement (sans reflet spéculaire), arbres lointains sans vent, halo à trois niveaux.
- Montagnes du fond qui ne sont plus noires en medium et high : la brume volumétrique prend la lumière du ciel.
- Ciel : nuages calculés en demi-résolution et retirés du calcul de la lumière ambiante, carte de rayonnement mise à jour par morceaux (−0,4 à −0,5 ms).
- Le globe du menu « Monde ouvert » n'est plus dessiné pendant la sortie.
- Image moins claire et plus contrastée : brume éclairée à moitié par le ciel et étalonnage en S (ombres plus denses), au même coût.
- Route qui disparaissait sous l'herbe dans les longues montées (forêt, montagne) : le terrain lointain est de nouveau creusé sous la chaussée avec le relief exagéré.
- Parcours demo : le sol ne recouvre plus la chaussée au km 1,74, là où la pente passe de 1 % à 3,5 %. Le terrain de démonstration reçoit le même garde-fou que les parcours compilés et la démo du dossier des parcours est remplacée au prochain lancement.

### Dernier survivant à 11 adversaires (lot DS8)
- Jusqu'à 11 adversaires (au lieu de 4) grâce au peloton : une arche par adversaire, donc un parcours d'au moins 11 km à 1 km d'écart, ou une boucle, ou le monde ouvert. Sur un parcours trop court, l'écran Prêt propose les réglages qui tiennent.
- Un bot éliminé laisse passer le coureur à sa hauteur avant de se ranger sur le bas-côté (au lieu de lui couper la route).
- Liste des coureurs du HUD : nom et écart en secondes de chaque bot, même des plus loin (la trame du peloton ne les envoie pas à chaque fois).

### Séances dans Garmin Connect et GoldenCheetah (lot X56)
- Le FIT de chaque séance donne les calories, le travail, le dénivelé positif et négatif, la puissance normalisée et la cadence maximale, pour la séance et pour chaque tour ; l'appareil s'appelle « OpenRide » avec la version du jeu.
- `openride-core fit-check` contrôle en plus ce que Garmin Connect et GoldenCheetah exigent à l'import (en-tête, tours et séance datés, heure locale).

### Outils de test
- Bancs de fluidité : la périodicité des à-coups se compte en passages distincts et non plus en images. Deux paquets d'images lentes éloignés (bots, décor, arrêt à l'arrivée) ne forment plus une fausse période ; la saccade de 40 m du 4 novembre reste détectée (lot X57).

### Bots et abri (série AS)
- Cyclistes du décor dessinés comme les bots (même cycliste, mêmes niveaux de détail), avec leurs propres maillots, unis ou de club, de couleurs qu'aucun bot ne porte, sans dossard (lot AS7, retour d'essai du 4 novembre).

## 2.0.0 – 2026-11-04

Un nouveau mode de course, le Dernier survivant, des bots qui roulent en groupe de façon plus réaliste, le gravier et le désert, et un rendu des essais identique à celui du jeu.

### Nouveau mode : Dernier survivant (série DS)
- Une arche d'élimination tous les 1, 2 ou 3 km : le dernier à la passer est éliminé, jusqu'au vainqueur.
- Réglages sur l'écran Prêt : adversaires, écart des arches, niveau des bots, écart de niveau, et ce qui se passe une fois éliminé (continuer à rouler ou terminer). Quand « Lancer » est grisé, l'écran dit pourquoi et quoi changer.
- Bloc SURVIVANT du HUD : prochaine arche, rang, écart au dernier, et le coureur de devant avec son écart en secondes et les watts qu'il faut pour le rejoindre avant l'arche.
- Portiques d'élimination, bots éliminés rangés sur le bas-côté, bandeaux, jingles et lignes du bilan.

### Bots et abri (série AS)
- Abri de groupe, vent de travers, abri derrière les véhicules et les cyclistes du décor.
- Placement dans la roue, dépassement toujours par la gauche du paquet.
- Va-et-vient des bots 4 fois moindres. La caméra suit le cycliste sans retard quand les images ralentissent, et les bots sont placés avant le décor de l'image : à-coups entre bots et cycliste 2 à 3 fois plus faibles en low, medium et high.

### Monde et rendu
- Gravier et désert (lot U16) : routes en gravier gris-brun et biome du décor au choix dans le menu, désert sec avec touffes et cailloux.
- Couleurs : le jeu affiche les couleurs du thème telles qu'elles sont écrites (sRGB), plus sombre et plus saturé là où il était délavé.
- Démo intégrée : elle a maintenant son terrain, et la route ne flotte plus au-dessus du sol. Un talus sous les bords de la route la porte là où le terrain est raide.
- Plus d'à-coup tous les 40 m sur un parcours sans terrain : la recherche du point de route le plus proche passe par une grille, et la pose de l'herbe est limitée à 1,5 ms par image.

### Entraînement
- Test de FTP : FTP provisoire au bandeau ERG pendant la rampe (75 % de la meilleure minute roulée), rappel « Z = passer l'échauffement » au départ, et message qui cite le bon fichier (profil.toml) quand la FTP est acceptée.

### Outils de test
- Les essais rendent en Forward+, comme le jeu.
- Garde-fou « à-coups » aux bancs de fluidité : images lentes par minute, périodicité en distance, et départ (bloc `hitches` de `perf_targets.json`).
- Contrôle route/sol dans les deux sens (route enfoncée ou route qui flotte), sur la démo intégrée, les parcours compilés et le monde ouvert simulé.
- La difficulté ne change que la pente envoyée au trainer, jamais la vitesse (test ajouté).
- Banc des menus : deux courses corrigées (focus des profils, écran de connexion des appareils).
- Test graphique de l'avatar : avance du pédalier lue dans l'engine.

### Connu, pour plus tard
- La bannière « Montée 1 · 4e catégorie » se voit en transparence derrière le titre de certains menus.
- Le boîtier gauche du Click se relance toutes les 52 s environ (verrou Zwift), avec environ 4 s d'absence ; le boîtier droit n'est pas touché.
- Une image lente au départ et deux dans les premières tuiles d'arbres (lot Y20).
- Sur la démo compilée, le GPU dépasse de peu son budget en medium (12,0 ms pour 12) et en high (14,2 ms pour 14).

## 1.0.2 – 2026-11-02

Le SIM du trainer redevient le pilotage par défaut. Cette version contient aussi les premiers morceaux de la 2.0 fusionnés depuis la 1.0.1.

### Séance
- **Pilotage du trainer : « SIM du trainer » par défaut** (choix du propriétaire du 2 novembre). En « résistance calculée », le défaut de la 1.0.0 et de la 1.0.1, le pédalage tournait dans le vide au départ et à basse vitesse sur le plat (21 à 31 W à 80 tr/min, essai vélo du 2 novembre). La résistance calculée reste dans Réglages › Séance, à l'essai, en attendant sa correction.
- Test de FTP : + et − sont bloqués pendant les paliers de la rampe, avec un rappel à l'écran (Z arrête le test).
- Départ d'une run Cyber-Rogue : la scène du mode se prépare sous l'écran « START YOUR ENGINES », et le pédalage ne compte qu'ensuite. Il n'y a plus de gel de 3 s juste après le départ. Les ennemis et le HUD du mode y sont aussi préparés, contre la dernière image lente (150 à 190 ms) au départ.

### Décor et son
- Oiseaux par phrases : un chant de 1,5 à 3,5 s toutes les 9 s environ, au lieu d'un gazouillis continu.
- Portiques et panneaux du parcours préparés au chargement : plus d'à-coup au premier passage d'une arche.
- Sons et musique du Cyber-Rogue fabriqués hors du fil principal.

### Nouveautés de la 2.0 déjà incluses
- Historique dans le menu : séances, bilan, cumul par semaine, tests de FTP (lot O28).
- Mode WTF : gags en 3D (tornade de vaches, fromage, cuisine géante, Lune…), préparés sous l'écran de départ (lots WTF5, WTF6, Y20).

### Outils de test
- Endurance : un essai de moins d'une heure a droit au seuil d'une heure de saccades (lot Y19).

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
