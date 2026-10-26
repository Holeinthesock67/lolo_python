# OpenRide 2.0 – GDD du mode « Cyber-Rogue Cycliste 3D »

Retranscription du document de conception remis par le propriétaire le 25 octobre 2026 (PDF de 7 pages, « GDD & Spécifications – Cyber-Rogue Cycliste 3D (Godot) »). Le texte suit l'original ; les décisions prises ensuite, qui l'emportent sur lui là où elles diffèrent, sont dans [PLAN_SERIE_R.md](PLAN_SERIE_R.md) §2 ; les corrections chiffrées du 26 octobre sont signalées ci-dessous par « Correction ».

## Partie 1 – Vision et philosophie

### 1.1 Constat : sortir du piège du « Zwift-like »

Une simulation cycliste en monde ouvert classique, développée en solo ou en petite équipe, mène à une impasse de production : 90 % du temps part dans la modélisation d'environnements statiques, pour un résultat qui paraîtra toujours vide face aux serveurs massivement multijoueurs.

Le projet prend le contre-pied de la contemplation : transformer l'entraînement sur home trainer en jeu d'action tactique de type rogue-lite (inspirations : Hades, Slay the Spire, Thumper et les films de motos lumineuses), où les jambes sont le moteur, la cadence est la posture et les boutons au guidon sont la manette de combat.

### 1.2 Piliers du gameplay

- **Équité physiologique (indexation sur la FTP) :** cibles de puissance, vitesse des menaces et points de vie des ennemis sont en pourcentage de la FTP. Débutant et athlète confirmé vivent la même intensité dramatique.
- **Synergie jambes + pouces :** l'effort produit les ressources (énergie, vitesse, posture) ; les 5 boutons au guidon changent de braquet virtuel, parent, déclenchent les compétences et choisissent les récompenses.
- **L'intention d'entraînement dicte le jeu :** le joueur choisit au départ son biome selon la filière travaillée (endurance zone 2, seuil ou sweet spot, PMA ou anaérobie). Le donjon se génère autour de cette contrainte, pour éviter les séances « fourre-tout ».
- **Zéro latence physiologique (pas de cardio actif) :** la fréquence cardiaque a 20 à 45 s d'inertie et dérive avec la chaleur ; elle ne déclenche rien en temps réel. Le jeu repose sur la puissance instantanée, la cadence et la réserve anaérobie W'bal.
- **Pas de « game over » qui coupe la séance :** une défaite dégrade le butin (perte d'or, reliques corrompues, boss qui s'enfuit sans récompense), suivie d'une courte récupération forcée, puis la séance continue.

### 1.3 Direction artistique : néon vectoriel (« le Grid »)

Le mode partage le socle technique Godot 3D de la simulation classique, avec une esthétique néon et synthwave :

- **Lisible à 180 bpm :** fond noir ou bleu nuit, contrastes extrêmes grâce au glow de Godot.
- **Peu d'assets 3D :** ni végétation ni textures photoréalistes ; grilles, shaders procéduraux, particules GPU, entités géométriques ou mécaniques (trains blindés, motos lumineuses, drones monolithiques).
- **Route diégétique (ruban tactique 3D) :** la piste suspendue dans le vide sert d'interface ; ses couleurs et son inclinaison sur 200 m devant le joueur annoncent chaque effort.

## Partie 2 – Spécifications fonctionnelles et game design

### 2.1 Modèle physique : mode hybride et braquet virtuel

Ni ERG pur (trop passif, « spirale de la mort » en cas de fatigue), ni pente libre (on pourrait tricher en moulinant). Un mode hybride :

1. **Résistance par la pente et le braquet virtuel :** la chaîne reste sur un pignon central. Le trainer reçoit une consigne calculée en continu (formule du GDD : frein = pente envoyée par l'ennemi + facteur du rapport virtuel de 1 à 12 ; **remplacée par la décision Q2**). Monter les vitesses durcit le frein et augmente le multiplicateur de dégâts et d'avancement par watt ; les descendre soulage pour mouliner dans les fortes pentes.
2. **Pression temporelle, le « Firewall » (mur de décompilation) :** un mur poursuit le joueur sur la piste. Sa vitesse est calée sur le pourcentage de FTP de la salle (par exemple 88 % en salle Seuil). Si l'effort baisse, il rattrape le joueur et entame bouclier et butin.

### 2.2 Les 5 boutons

Boîtier droit du Click : +, B, Y, Z, A actifs ; le bouton − n'est pas utilisé.

| Bouton | En combat (salles) | En récupération (menus, portes, butin) | Rôle tactique |
| --- | --- | --- | --- |
| + | Vitesse virtuelle +1 (plus de résistance) | Naviguer à droite | Engager, relancer en descente |
| B | Vitesse virtuelle −1 (moins de résistance) | Naviguer à gauche | Soulager, anticiper un mur |
| Y | Compétence offensive (burst) : consomme l'adrénaline quand la roue touche une cible [Y] | Valider (carte ou porte) | Attaque lourde, brise-armure |
| Z | Parade, bouclier ou aspiration : timing quand la roue traverse une zone [Z] | Relancer le tirage (coûte de l'or) | Défense active, accrocher la roue |
| A | Disjoncteur : purge d'urgence (−4 vitesses d'un coup) ou compétence de carte | Afficher le deck et les métriques | Joker de survie, surcharge volontaire |

### 2.3 La cadence comme posture de combat

À puissance égale :

- **Roc (< 70 rpm, force) :** armure +30 %, génération de mana ralentie.
- **Fluide (80 à 95 rpm, neutre) :** équilibre, meilleure régénération de W'bal.
- **Véloce (> 100 rpm, vélocité) :** plus de coups critiques, recharge de Y plus rapide, armure réduite.

**Correction (26 octobre) :** Fluide couvre tout de 70 à 100 rpm, avec une hystérésis de 3 rpm et un maintien de 1,5 s avant de changer de posture ; la meilleure régénération de W'bal reste réservée à 80 à 95 rpm (lot R2).

### 2.4 Ruban tactique et « Perfect Shift »

La piste affiche les événements 10 à 15 s à l'avance :

- **Couleur du sol selon la pente :** cyan de −3 à +1 % (monter les vitesses pour ne pas pédaler dans le vide), jaune ou orange de 2 à 6 % (faux-plat), magenta au-delà de 7 % (mur, rétrograder avec B).
- **Perfect Shift (arches dorées) :** juste avant une rupture de pente, une arche laser est posée. Changer de braquet (+ ou B) dans une fenêtre de 1,5 s au passage lisse la transition sur le trainer et donne +10 % d'adrénaline.

**Correction (26 octobre) :** couleurs sans trou : bleu sous −3 %, cyan jusqu'à 1,5 %, jaune jusqu'à 4 %, orange jusqu'à 6,5 %, magenta au-delà (lot R10). La fenêtre de 1,5 s et l'avance des arches sont réglées après la mesure du frein (lot R0).

### 2.5 Bestiaire (salles de 3 à 5 min)

| Archétype | Forme 3D | Profil de pente | Mécanique | Filière |
| --- | --- | --- | --- | --- |
| Le Diesel (Mainframe) | Train blindé crachant un souffle réacteur | Rampe constante de 3 à 4 % sans répit | Tunnels de cadence (ex. 90 rpm ± 3) : la régularité charge des éclairs, attaque avec Y | Seuil, régularité |
| Le Puncheur (Intercepteur) | Moto lumineuse laissant un mur d'énergie | Dents de scie : 15 s à 9 %, puis cuvettes à −2 % | Perfect Draft [Z] : zone bleue 2 s avant l'attaque ; Z en haussant les watts accroche l'aspiration (la bosse coûte moitié) | PMA, micro-intervalles 15/30, 30/30 |
| Le Grimpeur (Architecte) | Drone pyramidal qui soulève la route | Escalier : paliers chaque minute, 4 puis 7 puis 10 % | Rochers d'armure [Y] : charger la jauge en posture Roc (< 70 rpm ; **correction** : le GDD disait < 75) et frapper les balises | Force sous-maximale, tolérance lactique |
| Le Sprinteur (Berserker) | Chasseur furtif ultra-rapide | Plat à 0 %, mais le Firewall accélère par salves | Pavés de boost : vitesses 10 à 12 et sprint > 140 % FTP sur les flèches | Explosivité, capacité anaérobie |
| Le Saboteur (Glitch) | Essaim de cubes corrompus | Pente variable de 2 à 5 % | Piratage : bloque +/B ou force un pignon ; compenser à la cadence jusqu'à la balise de purge [A] | Adaptabilité neuromusculaire |

### 2.6 Deckbuilding et cassette (butin)

Pendant les 2 min de récupération entre les salles (pente 0 %, zone 1 à 2), choisir 1 carte parmi 3 (B et + pour naviguer, Y pour valider, Z pour relancer) :

1. **Terraformeurs (modifient la piste) :**
   - Rouleau compresseur : écrête les murs rouges (10 % limité à 6 %, mais 3 s plus long).
   - Tremplin cinétique : boost gratuit au fond de chaque descente bleue si un gros braquet (+) est engagé dans le creux.
2. **Pignons spéciaux (cassette virtuelle de 12 vitesses) :**
   - Overdrive (remplace la 12) : +40 % de frein, dégâts doublés pendant 8 s, puis retour automatique en 6.
   - Soin (remplace la 1) : au-delà de 95 rpm en 1, bouclier régénéré 2 fois plus vite.
   - Maudit (remplace la 10) : +35 % de dégâts tant que la 10 est engagée, mais Z désactivé (rétrograder en 9 pour parer).
   - Shifter électronique pro : fenêtre de Perfect Shift doublée (1,5 à 3 s), bouclier soigné à chaque réussite.
3. **Modules d'action (Y, Z, A) :**
   - Siphon d'aspiration : un draft réussi avec Z remplit 50 % de la jauge Y.
   - Inversion polaire (A) : une fois par salle, une montée devient une descente équivalente pendant 8 s.

### 2.7 Structure d'une run de 45 min et boss final

- **00:00 à 08:00, échauffement :** calibrage des vitesses, choix du biome, tirage de la relique de départ.
- **08:00 à 30:00, donjon :** 3 ou 4 salles à embranchements, combats de 3 à 5 min et couloirs de récupération de 2 min (portes gauche ou droite, cartes).
- **30:00 à 40:00, boss « la Chimère centrale », 3 phases :**
  1. Blindage (3 min) : montée constante à 5 % ; stabiliser l'effort et détruire les verrous d'armure avec Y.
  2. Furie tactique (4 min) : montagnes russes 8 / 0 / 10 % et ondes de choc [Z] ; coordination +, B, Z et jambes.
  3. Exécution (90 s) : route à 0 % mais écarlate, Firewall à 120 % FTP ; plus gros pignons et réserve vidée pour achever le boss.
- **40:00 à 45:00, retour au calme :** pente 0 %, coffres de fin de séance, déblocage de châssis permanents.

**Correction (26 octobre) :** 4 salles de 3 à 5 min et 4 couloirs de 2 min ne tiennent pas entre 08:00 et 30:00 (jusqu'à 28 min). Le calendrier de 45 min retenu : 4 salles de 3,5 min en moyenne et 4 couloirs de 2 min, puis un boss de 10 min (3 + 4 + 1,5 min de combat et 1,5 min de transitions). Les calendriers de 30, 60 et 90 min sont dans le lot R15.

## Partie 3 – Intégration Godot 3D

### 3.1 Interface diégétique

- **Hologramme de roue arrière :** rapport engagé (01 à 12), watts en % de FTP et cadence, dans l'axe du regard.
- **Arcs au sol :** deux demi-cercles autour du vélo pour le bouclier (Z, gauche, bleu) et l'adrénaline (Y, droite, orange).
- **Caméra :** champ de vision de 75 à 95° pendant les sprints ou l'activation de Y, léger tremblement aux impacts et aux Perfect Shifts.

### 3.2 Architecture modulaire (coexistence avec la simulation classique)

Le GDD propose des autoloads Godot partagés (`SensorManager`, `InputController`, `PlayerPhysiology`) et un générateur de salle (`TrackGenerator` en `Path3D` et `CSGPolygon3D` ou maillage procédural, points générés depuis le motif de l'ennemi, arches instanciées). **Décision Q1 :** ces règles vivent dans le core ; voir le plan.
