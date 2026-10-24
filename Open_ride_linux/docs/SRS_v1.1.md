# OpenRide Linux – SRS v1.1

21 octobre 2026 ; mises à jour du 23 octobre 2026 (alignement sur le code et les essais sur le vélo ; §14.1, seuils de passage à Rust)

## 1. Objectifs et périmètre

OpenRide est un simulateur de cyclisme indoor 3D à usage personnel, natif Linux, plus léger que Zwift. La v1 doit être simple, stable et extensible par couches, sans jamais casser ce qui existe déjà.

**Matériel de référence :** JetBlack Victory (FTMS et pont cardio), Zwift Cog 14 dents, Zwift Click, PC de bureau MSI sous Ubuntu avec carte graphique GTX 1060.

**Dans la v1**

- Parcours libre depuis un fichier GPX, avec la pente restituée au home trainer (mode SIM).
- 24 vitesses virtuelles pilotées par le Zwift Click.
- Entraînements structurés `.zwo` (mode ERG), avec le paysage qui défile.
- Rendu 3D stylisé : route, terrain, ciel, arbres, HUD.
- Enregistrement de la séance et export FIT minimal, pour GoldenCheetah et Garmin Connect.

**Hors périmètre (décidé le 21 octobre 2026)**

- Upload Strava ou tout service en ligne.
- Avatar, vélo 3D, personnalisation de l'apparence.
- Multijoueur, boutique, ANT+.
- Bots IA : optionnels, en fin de feuille de route (§13).

**Principe directeur :** toute fonction ajoutée plus tard (bâtiments, thèmes, audio, bots) s'ajoute comme une couche ou un module, sans modifier les parcours déjà compilés ni le contrat entre les programmes.

## 2. Décisions de conception et changements depuis la v1.0

La v1.1 garde le découplage matériel/rendu et le modèle 1D sur rail, et corrige les points suivants.

| Sujet | v1.0 | v1.1 | Raison |
| --- | --- | --- | --- |
| Processus | 2 (démon, moteur) | 3 : core, compiler, engine | La compilation GPX bloquerait le Bluetooth si elle tournait dans le démon |
| Physique | Dans Godot | Dans le core Python | Source de vérité unique ; l'enregistrement survit à un plantage du rendu ; testable sans Godot |
| IPC | Trame JSON sans version | Versionné, numéro de séquence, heartbeat | Détecter les pertes et les incompatibilités |
| Intégration de la vitesse | P/v avec seuil v_min | Bilan d'énergie cinétique | Stable à l'arrêt, plus de contournement |
| Braquets | R1 = 0,55, R24 = 1,85 | R1 = 0,40, R24 = 3,00, étagement calculé | Rapport 7,5 : un braquet doit se sentir sur le plat (essai Victory du 24 octobre) |
| Zwift Click | Appuis longs actifs en SIM | Appuis longs : ± 3 vitesses en SIM (essai du 22 octobre), saut de bloc et pause en ERG | Changer vite de braquet en côte ; actions dédiées en ERG |
| Route | B-spline | Polyligne à 10 m lissée | Une B-spline ne passe pas par les points du tracé |
| Altitude | API à points | Tuiles raster avec cache | Pas de limite de débit, parcours longs possibles |
| Fichier de parcours | Un fichier `.world` | Un dossier `.world` en couches | Ajouter une couche sans réécrire le reste |
| Rendu | Tout dès la v1 | MVP puis couches | Bâtiments, audio et effets viennent après |
| Export FIT | Compatible Strava | Minimal, sans upload | Strava abandonné |
| Enregistrement | FIT en fin de séance | Journal continu puis FIT | Pas de perte de séance en cas de plantage |
| Développement | Matériel obligatoire | Mode mock | Développer sans être sur le vélo |
| Avatar, vélo | Sous-entendus | Supprimés | Hors périmètre |

## 3. Architecture système

Trois programmes indépendants ; seul le core parle au matériel et c'est lui qui fait foi pour la séance. L'engine n'affiche que ce qu'il reçoit.

| Bloc | Technologie | Rôle | Quand |
| --- | --- | --- | --- |
| openride-core | Python 3.11+, asyncio, bleak | BLE (trainer, Click), physique, ERG, braquets, bots, journal, FIT, serveur IPC | Pendant la séance |
| openride-compiler | Python, ligne de commande | GPX vers `.world` : lissage, altitude, OSM, caches | À la demande, hors séance |
| openride-engine | Godot 4.3+, GDScript | Rendu 3D, HUD, menus, audio, interpolation | Pendant la séance |

**Flux pendant une séance**

1. Le trainer envoie puissance, cadence et fréquence cardiaque au core en BLE.
2. Le core fait avancer la position `s` sur la route (physique à 50 Hz) et envoie l'état à l'engine à 30 Hz.
3. Le core pilote le trainer (pente effective ou puissance cible) en lisant la pente un peu en avance sur la route.
4. L'engine renvoie au core des commandes d'interface (choisir un parcours, pause, fin) et un heartbeat.
5. Le core écrit un journal à 1 Hz et produit le FIT à la fin.

Le core lit directement la couche route du `.world` : il a besoin de la pente et des coordonnées, pas du terrain.

**États de sécurité**

- Plus de heartbeat de l'engine pendant 2 s : le core met la séance en pause (pente 0 %, enregistrement suspendu) et reprend sur demande quand l'engine revient.
- Plus de données du trainer pendant 3 s : pause, tentative de reconnexion, bandeau d'alerte dans l'engine.
- Le détail des messages et des pannes est dans le Contrat IPC v1.

## 4. Module Core

Le core isole chaque dépendance matérielle derrière une interface (§10) : le reste du code ne sait pas si le trainer est réel ou simulé.

### 4.1 Pilote trainer (FTMS)

- À la connexion : lecture de Fitness Machine Feature (0x2ACC) et de la plage de puissance (0x2AD8), abonnement à Indoor Bike Data (0x2AD2).
- Avant toute commande : Request Control (0x00) puis Start/Resume (0x07) ; les réponses du Control Point (0x2AD9) sont vérifiées.
- Le Control Point traite une procédure à la fois (FTMS v1.0 §4.16.3) : chaque commande attend l'indication de réponse (0x80) avant la suivante, au plus 1 s. Fitness Machine Status (0x2ADA) est écouté : « Control Permission Lost » (0xFF) déclenche une reprise du contrôle. Une consigne ERG ou SIM que Fitness Machine Feature n'annonce pas n'est pas envoyée (ajout du 24 octobre 2026, audit FTMS).
- **Mode SIM :** Set Indoor Bike Simulation Parameters (0x11) avec pente (résolution 0,01 %), Crr, Cw et vent nul. La pente est limitée à −10 % / +16 %, envoyée dès qu'elle varie d'au moins 0,1 point, au plus toutes les 0,2 s, et renvoyée au moins toutes les 2 s (réglages validés sur le Victory le 22 octobre 2026).
- **Mode ERG :** Set Target Power (0x05), en watts entiers, bornée par la plage annoncée par le trainer.
- La cardio vient du pont cardio du Victory si sa caractéristique est exposée (à vérifier au sprint 0), sinon d'une ceinture connectée séparément.
- Fréquence des données **mesurée** sur le Victory (22 octobre 2026) : environ 1 Hz au repos et en mode puissance, environ 8 Hz en mode pente. Le core ne suppose donc aucune cadence fixe : la dernière puissance reçue est maintenue entre deux notifications et lissée dans le temps (filtre exponentiel, constante de temps 0,7 s, clé `power_smooth_tau_s`) ; une moyenne glissante sur 3 s est calculée à part pour l'affichage. La physique ne dépend pas de la cadence de réception.
- Plage de puissance annoncée par le Victory : 0 à 1 000 W, par pas de 1 W. Une fréquence cardiaque de 0 bpm signifie « pas de mesure » et est traitée comme `null`.
- États : `CONNECTED`, `RECONNECTING`, `LOST`, avec reconnexion automatique à délai croissant.

### 4.2 Zwift Click

- Connexion BLE, handshake propriétaire, notifications des boutons + et − (référence : projet ouvert jat255/zwift_click_handling, à valider au sprint 0). Le Click n'accepte qu'un client à la fois : l'application Zwift et le téléphone doivent être déconnectés.
- **Format mesuré (22 octobre 2026) :** le Click testé (handshake `RideOn` sans chiffrement) envoie en continu, à environ 10 Hz, un message de type `0x23` dont le champ 1 est un tableau de bits ; un bit à 0 signifie « appuyé » (bit 12 = +, bit 8 = −). Le niveau de batterie arrive dans un message `0x19` toutes les 5 s. L'ancien format `0x37` reste pris en charge. La durée d'un appui est connue à 0,1 s près.
- Événements normalisés : `PLUS_SHORT`, `MINUS_SHORT`, `PLUS_LONG`, `MINUS_LONG`. Appui court : moins de 500 ms ; appui long : 900 ms ou plus ; entre les deux : ignoré. Seuil abaissé de 1 200 à 900 ms le 22 octobre 2026 après essai sur le vélo (appuis longs naturels : 0,7 à 1,1 s).
- Repli : un fournisseur clavier (flèches, touches +/−) produit les mêmes événements.

### 4.3 Braquets virtuels

La chaîne reste sur le pignon fixe du Zwift Cog ; le braquet n'agit que sur la résistance ressentie, donc sur la cadence pour une puissance donnée. La vitesse virtuelle est calculée avec la puissance mesurée et la pente réelle du terrain, jamais avec le braquet.

- Index `k` de 1 à 24, 12 au lancement.
- Rapport géométrique entre R_min = 0,40 et R_max = 3,00 (rapport 7,5, soit environ 9,2 % par clic) ; R_12 vaut alors environ 1,05, ce qui est accepté comme « neutre ».
- Pente envoyée au trainer :

```latex
G_{eff} = (G_{terrain} + G_{base}) \cdot R_k - G_{base}
```

- G_base = 2 % (résistance de base sur le plat, équivalent du roulement et de l'air). Essayé à 4 % le 24 octobre : en petit braquet, une montée de 3 % devenait une descente pour le trainer. Le résultat ne change jamais de signe par rapport au terrain (une montée reste au moins plate, une descente aussi), puis il est limité à −10 % / +16 %.
- R_min, R_max, G_base et le nombre de vitesses sont dans la configuration (§11) : la formule est heuristique et se règle au ressenti.

### 4.4 Actions du Click en v1

| Action | Mode SIM | Mode ERG |
| --- | --- | --- |
| Appui court + / − | Braquet k + 1 / k − 1 | Biais d'intensité ± 2 % (plage 80 % à 120 %) |
| Appui long + | Braquet + 10, borné à 24 (`long_press_gears`) | Passer au bloc suivant |
| Appui long − | Braquet − 10, borné à 1 (`long_press_gears`) | Pause / reprise ERG (pente 0 %) |

Le demi-tour sur la route et le réglage des bots sont reportés (§14).

### 4.5 Navigation dans les menus

Hors séance, le core transmet les événements du Click à l'engine : appui court ± pour défiler, appui long + pour valider, appui long − pour revenir. Le clavier fait de même.

## 5. Physique

La physique tourne dans le core, à 50 Hz (pas de 20 ms). Le vélo suit une coordonnée unique `s` (distance en mètres le long de la route) ; position 3D, cap et tangage sont lus dans la couche route du `.world`. Aucune collision n'est simulée.

**Bilan d'énergie.** La vitesse est déduite de l'énergie cinétique, ce qui reste stable à l'arrêt sans seuil sur P/v :

```latex
\frac{d}{dt}\left(\tfrac{1}{2} m v^2\right) = \eta P - F_{res}(v)\, v
```

```latex
F_{res}(v) = \tfrac{1}{2}\rho\, C_dA\,(1-\alpha_{draft})\,(v+v_{vent})\,|v+v_{vent}| + m g\,(\sin\theta + C_{rr}\cos\theta)
```

- La pente du terrain est `grade_pct` (positif en montée) ; θ = arctan(grade_pct / 100).
- Amorçage : l'énergie est ramenée à celle d'une vitesse plancher de 0,5 m/s quand la puissance est positive ou que la gravité entraîne le vélo (descente). En montée à puissance nulle, la vitesse retombe à 0 et le vélo ne recule pas.
- La vitesse peut être plafonnée (80 m/s) pour éviter les valeurs aberrantes.
- Le coefficient d'aspiration `alpha_draft` vaut 0 sans bot ; il n'intervient qu'avec les bots (de 0 à 0,45 selon la distance derrière un bot).

**Paramètres par défaut** (modifiables, §11)

| Paramètre | Valeur | Remarque |
| --- | --- | --- |
| Masse totale m | 84 kg | Coureur 75 kg + vélo 9 kg, à régler |
| CdA | 0,32 m² | Position de route |
| Crr | 0,004 | Pneus route sur home trainer virtuel |
| Rendement η | 0,97 | Transmission |
| Densité de l'air ρ | 1,225·e^(−h/8400) kg/m³ | h = altitude en mètres |
| Vent | 0 m/s | |

**Anticipation de latence.** Pour compenser la réponse du trainer (0,5 à 1,0 s), la pente envoyée est lue sur la route à `s_anticipée = s + v · tau` avec tau = 0,8 s par défaut.

**Lissage de la pente envoyée au trainer**

- Variation limitée à 2 points de pourcentage par seconde.
- Coefficient de difficulté (100 % par défaut) : la pente envoyée est multipliée par ce coefficient, alors que la vitesse virtuelle utilise toujours la pente réelle. Mettre 50 % adoucit les cols sans fausser la vitesse affichée.

**Fin de parcours.** La séance s'arrête à la fin de la route (`s` = longueur) ; un parcours marqué en boucle dans le `.world` reboucle sans coupure.

**Contrôle.** Cas de référence : 250 W à plat, CdA 0,32 m², 84 kg, air à 1,225 kg/m³ doivent donner environ 10,2 m/s (36,7 km/h) à ± 3 %.

## 6. Entraînements structurés ERG (.zwo)

Les fichiers `.zwo` (XML ouvert) placés dans `~/OpenRide/Workouts/` sont lus par le core. Même en ERG, le paysage défile : la physique du §5 continue d'utiliser la puissance mesurée sur la route choisie.

| Bloc | Balises lues | Comportement |
| --- | --- | --- |
| Warmup, Cooldown, Ramp | Duration, PowerLow, PowerHigh | Rampe linéaire entre les deux puissances |
| SteadyState | Duration, Power | Puissance constante |
| IntervalsT | Repeat, OnDuration, OffDuration, OnPower, OffPower | Alternance travail / récupération |
| FreeRide | Duration | Pas de cible : le core repasse en mode SIM le temps du bloc |

- Les puissances du fichier sont des fractions de la FTP (0,75 = 75 %). Cible en watts = FTP × fraction × biais, arrondie au watt ; le biais (80 % à 120 %) se règle au Click.
- Les changements de cible sont lissés sur 2 s pour ne pas brusquer le trainer.
- Balises inconnues (cadence, messages texte) : ignorées avec un avertissement dans les journaux.
- Un fichier invalide n'arrête rien : il apparaît dans le menu avec l'erreur, sans être sélectionnable.
- Le menu affiche la durée totale et le profil des blocs de chaque entraînement.

**HUD de l'entraînement :** bandeau inférieur avec l'histogramme des blocs, le compte à rebours du bloc en cours, la puissance lissée sur 3 s, la cible et le biais ; un bip retentit 3 s avant chaque changement de bloc. Le saut de bloc et la pause se font par appui long sur le Click (§4.4).

## 7. Compilateur de parcours

Le compilateur transforme un `.gpx` déposé dans `~/OpenRide/GPX/` en dossier `.world` (format décrit dans le document « Format .world v1 »). Il tourne dans son propre processus, jamais dans la boucle du core.

**Étapes**

1. **Lecture du GPX :** suppression des points en double et des arrêts ; une trace de moins de 500 m est refusée avec un message clair.
2. **Ré-échantillonnage** tous les 10 m de distance horizontale.
3. **Altitude lissée :** filtre de Savitzky-Golay (fenêtre de 11 points, ordre 2, soit environ 110 m). Si le GPX n'a pas d'altitude, ou une altitude jugée aberrante, elle est prise dans le MNT.
4. **Pente et cap** calculés sur l'altitude lissée ; pente limitée à ± 25 %, le nombre de points limités est noté dans le manifeste.
5. **Terrain :** altitudes issues du MNT, creusées autour de la route pour que le ruban ne flotte pas ni ne s'enterre (fondu entre la route et le MNT de 4 m à 25 m du ruban).
6. **OpenStreetMap** (couches optionnelles) : bâtiments, forêts, eau, points d'intérêt, par segments le long du parcours.
7. **Écriture atomique** du dossier `.world` (dossier temporaire puis renommage) et validation.

**Sources d'altitude (interface ElevationProvider)**

- Par défaut : Copernicus GLO-30 (30 m, libre, mondial), lu en tuiles GeoTIFF avec `rasterio`.
- En France : RGE ALTI de l'IGN (résolution plus fine) quand il est disponible.
- OpenTopoData : en dernier recours seulement, son service public est limité en débit.

**Deux étages de cache**

- Cache brut, réutilisable entre parcours : `~/.cache/openride/dem/` (tuiles) et `~/.cache/openride/osm/` (réponses Overpass).
- Cache compilé : `~/.local/share/openride/routes/<nom>.world/`, régénérable à tout moment depuis le cache brut, sans nouveau téléchargement.

**Durées.** Le premier calcul d'un long parcours prend quelques minutes selon le réseau et le serveur Overpass ; les requêtes sont découpées, avec délais d'attente et reprises. Le chargement d'un parcours déjà compilé vise moins de 2 s.

**Utilisation**

- En ligne de commande : `openride-compiler build col.gpx --layers route,terrain` ; `add-layer` ajoute une couche à un `.world` existant ; `verify` le contrôle.
- Depuis le menu : un parcours non compilé affiche « à compiler » et le core lance le compilateur en tâche de fond, sans bloquer le Bluetooth.

**Cas particuliers :** un tracé dont le départ et l'arrivée sont distants de moins de 50 m est marqué en boucle ; l'aller-retour est une option explicite ; le bord du terrain proche est masqué par un terrain lointain en basse résolution (§5 du document .world).

## 8. Moteur de rendu Godot

L'engine reçoit l'état du core, charge les couches du `.world` qui existent et ignore les autres. Il n'a ni avatar ni vélo : la caméra est subjective et suit la position `s`.

**MVP visuel (sprint 3)**

- Ruban de route et terrain générés par tronçons de 1 km, avec le shader triplanaire du §8.1.
- Ciel physique avec soleil fixe, arbres instanciés (`MultiMeshInstance3D`) avec une densité issue d'un bruit sous la limite des arbres.
- HUD de base : puissance (lissée 3 s), cadence, fréquence cardiaque, vitesse, distance, pente, braquet `k/24`, temps, profil d'altitude avec la position.

**Modules ajoutés ensuite :** bâtiments extrudés, forêts OSM, brouillard volumétrique, SSAO, LUT colorimétrique, ambiances sonores spatialisées, bots.

**Fluidité.** Le core envoie `s` et `v` à 30 Hz ; l'engine interpole et extrapole la position à la cadence de rendu, pour éviter la saccade d'une position à 20 ou 30 Hz.

**Performance**

- Trois préréglages de qualité (bas, moyen, haut) dans la configuration : distance de vue, densité de végétation, SSAO, brouillard, MSAA.
- Le brouillard volumétrique n'existe qu'avec le moteur de rendu Forward+ ; sur GPU intégré, le préréglage bas utilise le moteur Mobile ou Compatibility.
- La génération des maillages se fait dans des threads (`WorkerThreadPool`), par tronçon, en avance sur la caméra ; elle peut aussi être précalculée plus tard.
- Objectif : 30 images par seconde au minimum sur le PC cible en préréglage bas.

**Bâtiments (module ultérieur) :** triangulation par `Geometry2D.triangulate_polygon` (pas de bibliothèque Earcut externe) ; les polygones OSM avec trous (multipolygones) sont traités à part ; toits plats d'abord, toits à deux pans ensuite ; hauteurs tirées de `height` et `building:levels`, sinon d'une valeur aléatoire stable.

**Audio (module ultérieur) :** vent proportionnel à la vitesse, bruit de roue libre à 0 W, sources 3D sur les points d'intérêt.

### 8.1 Shader triplanaire

- Projection sans coordonnées UV, échelle exprimée en mètres.
- Pente inférieure à 22° : prairie, avec variation par bruit ; supérieure : roche, avec facettes marquées.
- Neige au-dessus d'une altitude seuil (2 200 m par défaut).
- Les couleurs, textures, seuils et échelles viennent du thème actif (§10) : changer de textures ne demande aucune modification du code ni du `.world`.

## 9. Enregistrement de séance et export FIT

Le core enregistre la séance tout seul, sans dépendre de l'engine, et la convertit en FIT à la fin. Aucun envoi vers un service en ligne.

**Journal continu**

- Un fichier JSONL par séance dans `~/OpenRide/Activities/.journal/`, une ligne par seconde, vidée (`flush`) à chaque ligne et synchronisée sur disque (`fsync`) toutes les 5 s.
- Champs : temps, latitude, longitude, altitude, distance, vitesse, puissance, cadence, fréquence cardiaque, pente, mode, braquet, bloc d'entraînement.
- Après un plantage, la commande `openride-core recover` transforme le dernier journal en FIT.

**Export FIT** (bibliothèque `fit-tool`) vers `~/OpenRide/Activities/AAAA-MM-JJ_HH-MM_parcours.fit`

- Messages : `file_id`, `event` (début, fin, pauses), `record` à 1 Hz (`timestamp`, `position_lat`, `position_long`, `distance`, `altitude`, `speed`, `power`, `cadence`, `heart_rate`), `lap`, `session` (sport cycling, sub_sport virtual_activity, totaux et moyennes) et `activity`.
- Latitude et longitude sont converties en semicercles (degrés × 2³¹ / 180).
- Pendant une pause, le temps chronométré est arrêté par un événement.
- Critère d'acceptation : le fichier s'ouvre sans erreur dans GoldenCheetah et dans Garmin Connect.

## 10. Modularité : interfaces, couches, thèmes

L'évolution dans le temps repose sur trois mécanismes : des interfaces remplaçables, un parcours en couches facultatives et des thèmes qui ne changent que le rendu.

**Interfaces du core**

| Interface | Implémentations v1 | Extensions possibles |
| --- | --- | --- |
| TrainerDriver | FtmsDriver, MockDriver | ANT+, autre trainer |
| InputProvider | ZwiftClickProvider, KeyboardProvider | Manette, téléphone |
| ElevationProvider | Copernicus GLO-30, IGN RGE ALTI | OpenTopoData, autre MNT |
| WorkoutSource | Lecteur `.zwo` | Autres formats |
| Exporter | FitExporter | Autres formats de fichier |

**Couches du `.world`** (détail dans « Format .world v1 »)

| Couche | Statut | Sprint |
| --- | --- | --- |
| route | Obligatoire | 2 |
| terrain (proche et lointain) | Facultative, présente dès la v1 | 2 |
| vegetation | Facultative | 3 (densité par bruit), 5 (OSM) |
| buildings | Facultative | 5 |
| poi et eau | Facultative | 6 |

L'engine ignore toute couche absente ; une couche se régénère seule avec `add-layer` sans toucher aux autres.

**Thèmes et textures**

- Un thème est un dossier `~/OpenRide/Themes/<nom>/` avec un `theme.json` et des textures (herbe, roche, neige, route), des palettes de bâtiments, les paramètres du ciel et du brouillard.
- Le thème est choisi au lancement dans la configuration : changer de thème ne demande ni recompilation ni modification du code.
- Toute texture manquante est remplacée par une couleur unie : un thème peut être démarré avec un seul fichier.
- Un thème ne touche jamais au coureur ; le format est décrit dans « Format .world v1 », section Thèmes.

**Dépôt de code.** Un seul dépôt avec `docs/contracts/` contenant cette SRS, le Contrat IPC v1, le format `.world` et leurs schémas JSON. Ces documents sont fournis à l'IA au début de chaque session de développement ; des tests de contrat vérifient que chaque programme les respecte.

## 11. Configuration et arborescence

Toutes les valeurs ajustables sont dans un seul fichier `~/OpenRide/config.toml`, lu au démarrage par le core et par l'engine.

```toml
[rider]
ftp_w = 250
mass_kg = 75

[bike]
mass_kg = 9
cda_m2 = 0.32
crr = 0.004
drivetrain_efficiency = 0.97

[trainer]
device_name = "Victory"      # fragment du nom annoncé (« Victory 9908 »)
latency_tau_s = 0.8
difficulty_pct = 100
grade_min_pct = -10
grade_max_pct = 16
power_smooth_tau_s = 0.7
grade_rate_pct_per_s = 2.0   # limite de variation due au relief (pas aux braquets)

[gearing]
n_gears = 24
start_gear = 12
ratio_min = 0.40
ratio_max = 3.00
g_base_pct = 2.0
long_press_gears = 10

[drivers]
trainer = "mock"             # "ftms" ou "mock"
input = "keyboard"           # "click", "keyboard" ou "none"
trainer_address = ""         # adresse MAC facultative
click_address = ""
click_short_max_s = 0.5
click_long_min_s = 0.9
mock_replay = ""             # chemin facultatif d'un journal (.jsonl) ou d'un .fit à rejouer en mode mock

[render]
quality = "low"      # low, medium, high
theme = "default"

[ipc]
port_state = 5005
port_commands = 5006
```

Les valeurs ci-dessus sont des exemples de départ (FTP et masses à adapter).

**Arborescence**

```text
~/OpenRide/
  config.toml
  GPX/                 traces à compiler
  Workouts/            entraînements .zwo
  Themes/<nom>/        theme.json et textures
  Activities/          fichiers .fit
    .journal/          journaux JSONL de séance
~/.local/share/openride/routes/<nom>.world/   parcours compilés (dossier)
~/.cache/openride/dem/                        tuiles d'altitude brutes
~/.cache/openride/osm/                        réponses OpenStreetMap brutes
```

Le `.world` est désormais un dossier, et non un fichier unique comme dans la v1.0.

## 12. Exigences non fonctionnelles, mode mock, tests

**Exigences**

- Délai entre une notification du trainer et son effet à l'écran : moins de 100 ms hors rendu.
- Boucle de physique stable à 50 Hz, sans dérive sur une séance de 3 h.
- Engine : 30 images par seconde au minimum en préréglage bas sur le PC cible ; pas de fuite de mémoire visible sur 3 h.
- Un plantage de l'engine ne fait perdre aucune donnée de séance.
- Fonctionnement sans connexion Internet une fois le parcours compilé.
- Journaux lisibles (niveau, horodatage) pour chaque programme.

**Mode mock.** `MockDriver` remplace le trainer : puissance constante, profil en rampe, pilotage au clavier ou rejeu d'un FIT ou d'un journal, avec simulation de déconnexion. Avec le clavier comme `InputProvider`, toute l'application se développe et se teste sans le vélo.

**Tests**

| Domaine | Test |
| --- | --- |
| Physique | 250 W à plat ≈ 10,2 m/s ± 3 % ; stabilité à l'arrêt ; pas de recul en montée à 0 W ; descente à 0 W accélère |
| Braquets | Rapports strictement croissants de k = 1 à 24 ; R_12 ≈ 1,05 ; pente effective bornée |
| ERG | Calcul des cibles à partir d'un `.zwo` de référence ; lissage de 2 s ; saut de bloc |
| IPC | Chaque trame d'exemple valide son schéma JSON ; comportement sur perte et désordre |
| Compilateur | Pente et longueur d'un GPX de référence ; relance sans nouveau téléchargement |
| FIT | Relecture par bibliothèque, puis ouverture manuelle dans GoldenCheetah et Garmin Connect |
| Route | Mêmes valeurs en Python et en GDScript pour les vecteurs de test d'interpolation |

## 13. Plan de développement par sprints

Le MVP utilisable est atteint à la fin du sprint 3 : pédaler sur une trace GPX avec terrain, ciel et HUD, résistance pilotée, FIT en fin de séance.

| Sprint | Contenu | Critère d'acceptation |
| --- | --- | --- |
| 0. Spikes | Connexion BLE réelle au Victory (lecture, commandes 0x11 et 0x05) et au Click ; FIT minimal ; Godot affiche une polyligne avec des données factices | Les faits vérifiés (capacités du Victory, fréquences réelles, handshake du Click) sont notés dans `docs/spikes.md` ; le FIT s'ouvre dans GoldenCheetah |
| 1. Core et mock | BLE, braquets, physique, serveur IPC, journal, FIT, MockDriver, tests | 10 min avec MockDriver produisent un journal et un FIT valides ; 10 min sur le vrai trainer avec des braquets perceptibles |
| 2. Compilateur minimal | GPX vers `.world` (route et terrain), caches | Un GPX de 30 km compile ; pente maximale à ± 1 point près de celle de Garmin Connect ; la relance n'utilise pas le réseau |
| 3. Moteur minimal | Route, terrain, ciel, arbres, HUD, caméra interpolée | 30 images par seconde sur le PC cible ; 1 h sans plantage ; mouvement sans saccade visible |
| 4. ERG et ZWO | Lecteur, rampes lissées, biais, saut de bloc, bandeau | Un `.zwo` standard s'exécute en entier ; cibles atteintes ; bip à T − 3 s |
| 5. Couches OSM | Bâtiments puis forêts, préréglages de qualité | Traversée d'un village sans trous ni artefacts ; 30 images par seconde en préréglage bas |
| 6. Thèmes, audio, POI | Thèmes avec textures, ambiances sonores, points d'intérêt, eau | Changer de thème modifie le rendu sans recompiler |
| 7. Bots (optionnel) | Bots à puissance constante, fantôme d'un ancien FIT, modèle CP / W' en dernier | À définir au moment de lancer ce sprint |

## 14. Évolutions futures et risques ouverts

**Évolutions envisagées** (aucune n'est dans la v1)

- Bots : puissance constante, puis fantôme d'un ancien FIT, puis modèle CP / W' pour les courses.
- Demi-tour sur la route et réglage des bots par appui long en mode SIM.
- Brouillard volumétrique, SSAO, LUT colorimétrique, toits à deux pans.
- Couverture du sol (ESA WorldCover) pour la végétation en montagne, où OSM est lacunaire.
- Téléphone comme télécommande, ANT+.

**Risques ouverts**

| Risque | Conséquence | Parade |
| --- | --- | --- |
| Capacités FTMS réelles du Victory inconnues (pont cardio, fréquences) | Commandes ou cardio inutilisables | Sprint 0 avec un outil de diagnostic BLE |
| Protocole du Zwift Click rétro-ingénié | Boutons inutilisables après une mise à jour | InputProvider isolé, repli clavier |
| Performances sur GPU intégré | Moins de 30 images par seconde | Préréglages de qualité, threads, moteur Mobile |
| OSM lacunaire en montagne | Paysage vide | Densité d'arbres par bruit, couverture du sol plus tard |
| Ressenti des braquets | Résistance peu naturelle | Paramètres en configuration, réglage à l'usage |
| Lenteur d'Overpass | Compilation longue | Segments, délais d'attente, cache brut |
| Dérive entre documents | Modules incompatibles | Contrats versionnés et tests de contrat |

### 14.1 Seuils de passage à Rust

Le core reste en Python tant que les mesures de performance restent sous les seuils ci-dessous. Le core les écrit dans son journal toutes les 60 s (ligne `Perf`, `session.py`), sur la fenêtre écoulée depuis le relevé précédent.

| Mesure | Définition | Seuil | Mesuré le 22 octobre (PC cible) |
| --- | --- | --- | --- |
| Durée du pas de physique, p99 | Temps d'un tour de boucle : IPC, entrées, physique, envoi de la consigne | 5 ms (le quart du pas de 20 ms à 50 Hz) | p50 0,2 ms (p99 à 7 ms avant que le `fsync` du journal ne soit espacé) |
| Retard de boucle, p99 | Écart entre l'heure prévue d'un tour et son heure réelle | 20 ms (un pas de physique entier) | max de 3 à 19 ms |
| CPU du processus core | Temps processeur / temps écoulé | 15 % d'un cœur | 3 à 4 % |

**Règle de décision**

- Un dépassement isolé (gel du système, swap, démarrage) ne compte pas. Le seuil est atteint quand **trois relevés `Perf` consécutifs** le dépassent pendant une séance réelle, sur le PC cible.
- Le retard **maximal** est relevé pour information, sans seuil : un pic isolé est absorbé par `MAX_STEP_S` (pas borné à 0,1 s) et par l'extrapolation de l'engine.
- Avant Rust, chercher d'abord la cause en Python (entrée-sortie bloquante dans la boucle, `fsync`, journalisation excessive), comme pour le `fsync` du journal corrigé le 22 octobre.
- Si Rust devient nécessaire, seuls les modules purs sont concernés (`physics.py`, puis `gearing.py`), derrière la même interface, avec les mêmes tests.

Les essais du 22 octobre restent loin de ces seuils (`docs/SUIVI_AVANCEMENT.md` §2).
