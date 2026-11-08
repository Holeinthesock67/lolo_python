# OpenRide Linux – Spécification générale, versions 1.0 à 5.0

26 octobre 2026, complétée le 8 novembre 2026 (versions 4.0 et 5.0, modes de jeu, réglages, vent, jour et nuit, saisons, contrat IPC jusqu'à la révision 1.8 et révisions réservées). Ce document rassemble en une seule spécification la SRS de la 1.0 et les plans des versions 2.0 à 5.0. Il ne remplace aucun document détaillé : il dit **ce que chaque version doit faire**, **où en est chaque exigence** et **quel document fait foi** pour le détail.

## 1. Comment lire ce document

**Documents qui font foi pour le détail**

| Sujet | Document |
| --- | --- |
| Exigences de la 1.0 (matériel, physique, ERG, compilateur, rendu, FIT, configuration) | [SRS_v1.1.md](SRS_v1.1.md) |
| Messages entre le core et l'engine | [contracts/ipc_v1.md](contracts/ipc_v1.md) et ses schémas dans `docs/contracts/ipc/` |
| Format des parcours `.world` et des thèmes | [contracts/world_format_v1.md](contracts/world_format_v1.md) et ses schémas dans `docs/contracts/world/` |
| Découpage en lots, état de chaque lot | [lots/00_INDEX.md](lots/00_INDEX.md) |
| Plans de la 2.0 | [2.0/README.md](2.0/README.md) : séries R, T, V et W ; série P dans l'index des lots |
| Plan de la 3.0 | [3.0/README.md](3.0/README.md) : série U, peloton, écran de démarrage |
| Plans de la 4.0 | [4.0/README.md](4.0/README.md) : séries TT, GP et VD, Click gauche |
| Plans de la 5.0 | [5.0/README.md](5.0/README.md) : séries CT, WF, CO et BC, mondes demo, installeur |
| Feuille de route et décisions datées du propriétaire | `/mnt/project-files/feuille-de-route/PLAN_APRES_2_0.md` (hors dépôt) |

En cas de désaccord entre ce document et un document détaillé, le document détaillé fait foi et l'écart est une erreur à corriger ici. Les écarts déjà connus sont listés au §9.

**Versions**

- **1.0 :** séries de lots A à O et Q (dernière série avant la publication : O, recette O8 et étiquette `v1.0.0`).
- **1.x :** mises à jour après la 1.0, sans changement de version majeure : lots N17 et N18 (demi-tour et bots réglés au menu, décision D11 du 27 octobre) et série P (décor vivant, vent, aspiration) y est rangée, sauf le jour, la nuit, les saisons et les packs de textures (P7, P18, P19, P20), reportés à la 2.0 par décision du propriétaire du 25 octobre.
- **2.0 :** séries R (Cyber-Rogue), T (segments, bonus, bots à profil), V (progression) et W (monde ouvert), plus P7, P18, P19 et P20.
- **3.0 :** série U (biomes, textures régionales, saisons par biome) et option « gravel » ; écran de démarrage, peloton d'environ 12 bots (PL1) et Dernier survivant à 11 adversaires (DS8) ; FIT accepté par Garmin Connect et GoldenCheetah (X56) ; vent d'après la météo locale, reporté de la 2.0.
- **4.0 :** séries TT (bonus tactiques), GP (Grand Prix des objets) et VD (vélodrome) ; Click gauche ; constructions et faune par biome (U23) ; panneaux d'approche refaits ; résistance calculée à basse vitesse (RC4, RC5).
- **5.0 :** séries CT (Course tactique), WF (trainer en Wi-Fi), CO (séance conseillée) et BC (badges et cartes) ; séance `.zwo` complète au Click ; essais de gain de performance GPU ; rendu et bots améliorés en fin de projet ; mondes demo nettoyés ; installeur en un seul fichier, en dernier.
- **Socle :** lots sans version (A à M, Q, S, X, Z, RC, Y) qui servent toutes les versions.

**Statuts**

| Statut | Sens |
| --- | --- |
| Livré | Code et documentation sur `main` |
| En revue | Pull request ouverte, pas encore fusionnée |
| Spécifié | Cahier de lot sur `main`, travail pas commencé |
| Planifié | Décrit dans un plan de série seulement, sans cahier sur `main` |
| À trancher | Décision du propriétaire attendue (§9) |

**Identifiants.** Chaque exigence porte un identifiant `<version>-<domaine>-<n>` (par exemple `2.0-JEU-3`). Les identifiants ne sont jamais réutilisés : une exigence abandonnée garde son numéro avec le statut « Abandonnée ».

## 2. Périmètre par version

| Thème | 1.0 | 1.x | 2.0 | 3.0 |
| --- | --- | --- | --- | --- |
| Rouler sur une trace GPX, FIT ou TCX, pente au trainer | Oui | | | |
| Entraînements ERG (`.zwo`, `.erg`, `.mrc`), test de FTP, plans | Oui | | | |
| Rendu : route, terrain, ciel, arbres, bâtiments, eau, sons, HUD | Oui | | | |
| Menus au Click, appairage, réglages, bilan, lanceur sans terminal | Oui | | | |
| Bots à puissance constante et fantôme | Oui (core ; affichage O7 facultatif) | | Bots à profil (T) | |
| Vent physique, aspiration, décor vivant | | Oui (P) | Vent d'après la météo locale | |
| Jour, nuit, saisons, packs de textures par niveau | | | Oui (P7, P18 à P20) | Saisons par biome (U) |
| Sprints, montées chronométrées, records, bonus, maillots | | | Oui (T) | |
| Mode de jeu Cyber-Rogue | | | Oui (R) | |
| Progression : expérience, pièces, équipement, avatar | | | Oui (V) | |
| Monde ouvert généré en direct, cache local | | | Oui (W) | Chemins de terre (« gravel ») |
| Biomes, variantes régionales, mer et côtes | | | | Oui (U) |

| Thème | 4.0 | 5.0 |
| --- | --- | --- |
| Bonus tactiques (Plume, Casque, Puissance, Enclume, Aspiration +, Échappée, Rouleau compresseur) | Oui (TT) | Payés par les relais (CT6) |
| Mode « Grand Prix des objets » | Oui (GP) | |
| Vélodrome couvert, épreuves de piste | Oui (VD) | |
| Boîtier gauche du Click sous Zwift | Oui (K9) | |
| Constructions et faune propres à chaque biome | Oui (U23) | |
| Panneaux d'approche plus grands et plus travaillés | Oui | |
| Mode « Course tactique » | | Oui (CT) |
| Trainer en Wi-Fi (Direct Connect), mode de mesures rapides | | Oui (WF, si la mesure WF1 le justifie) |
| Séance conseillée au menu, suggestion de la montre Garmin | | Oui (CO) |
| Badges et cartes à collectionner | | Oui (BC) |
| Mondes demo nettoyés et nommés, puis installeur en un seul fichier | | Oui (O37, J9) |

**Toujours hors périmètre**, toutes versions : multijoueur, envoi vers Strava ou un autre service en ligne, compte en ligne, achats en argent réel (les pièces de la série V se gagnent en roulant), ANT+ direct (une ceinture ANT+ n'arrive que par le pont cardio du trainer, SRS §4.1).

**Changements de périmètre par rapport à la SRS v1.1 §1** (décisions du propriétaire) :

- les bots, « optionnels en fin de feuille de route », sont livrés dans le core dès la 1.0 (lot N9) ;
- l'avatar et le vélo 3D, hors périmètre de la v1, entrent en 2.0 (série V, lots V6 et V7) ;
- la « boutique » refusée en v1 devient en 2.0 un Garage local où l'on dépense des pièces gagnées en roulant (V3b), sans argent réel ni service en ligne.

### 2.1 Modes de jeu

Le core annonce les modes qu'il sait jouer dans `hello_ack.config.modes` ; l'accueil n'affiche que ceux que l'engine sait aussi montrer (1.0-UI-2). **Règle sans exception (8 novembre) :** un mode n'est annoncé, et ses réglages ne sont envoyés au menu, qu'une fois le lot de son entrée à l'accueil fusionné (cas du Grand Prix : GP9). Le mode d'une séance est l'argument `mode` de `start`.

| Mode | Valeur | Pilotage du trainer | Version | Plan | Statut |
| --- | --- | --- | --- | --- | --- |
| Parcours (classique) | `ride` | SIM, résistance calculée ou ERG de session libre | 1.0 | SRS | Livré |
| Entraînement ERG | `erg` | ERG | 1.0 | SRS §6 | Livré |
| Monde ouvert | `open_world` | SIM ou ERG | 2.0 | [PLAN_SERIE_W.md](2.0/PLAN_SERIE_W.md) | Livré ; recette W16 à faire |
| Cyber-Rogue | `rogue` | Frein par décalage de pente (SIM) | 2.0 | [PLAN_SERIE_R.md](2.0/PLAN_SERIE_R.md) | Livré ; recette R14 à faire |
| « What the fuck » | `wtf` | SIM seulement, pente bornée −6 / +10 % | 2.0 | [PLAN_SERIE_WTF.md](2.0/PLAN_SERIE_WTF.md) | Livré ; recette WTF8 à faire |
| Dernier survivant | `survivor` | SIM | 2.0 (11 adversaires en 3.0) | [PLAN_SERIE_DS.md](2.0/PLAN_SERIE_DS.md) | Livré ; recette DS9 à faire |
| Grand Prix des objets | `grandprix` | SIM seulement | 4.0 | [PLAN_SERIE_GP.md](4.0/PLAN_SERIE_GP.md) | Core livré (GP1 à GP3) ; entrée de l'accueil GP9 à faire |
| Vélodrome | épreuves passées par `list_mode_options` et `set_mode_option` | SIM | 4.0 | [PLAN_SERIE_VD.md](4.0/PLAN_SERIE_VD.md) | En revue (PR #746, #769) |
| Course tactique | `tactical` | SIM seulement | 5.0 | [PLAN_SERIE_CT.md](5.0/PLAN_SERIE_CT.md) | CT0 livré, CT9 maquettes validées ; reste CT1 à CT8, CT10 à CT12 |

Les options d'un mode (règles du WTF, objets du Grand Prix, épreuves de piste) passent par les commandes génériques `list_mode_options` et `set_mode_option` (révision 1.7), jamais par une commande propre au mode.

## 3. Architecture et invariants

Ces règles valent pour toutes les versions. Une série qui voudrait en changer une le dit dans son plan et passe par une décision du propriétaire.

| # | Invariant | Origine |
| --- | --- | --- |
| A1 | Le core est le maître de la séance : physique, pilotage du trainer, journal, FIT. L'engine n'affiche que ce qu'il reçoit | SRS §3 |
| A2 | Les règles de jeu (segments, bonus, W'bal, combat, expérience, navigation du monde ouvert) vivent dans le core, en modules purs testés en pytest | Décision R-Q1, reprise par T, V et W |
| A3 | Aucun calcul lourd dans la boucle à 50 Hz du core ; la compilation et la génération du monde tournent dans leur propre processus | SRS §7, plan W §3.5 |
| A4 | Le contrat IPC n'évolue que par ajouts compatibles tant que `v` vaut 1 ; chaque ajout prend une révision (§6.1) | `docs/contracts/ipc_v1.md` §8 |
| A5 | Le format `.world` évolue par couches facultatives ; l'engine ignore une couche absente et un parcours ancien reste lisible | `docs/contracts/world_format_v1.md` §10 |
| A6 | Le journal de séance est écrit en continu et la séance survit à un plantage de l'engine ou du core | SRS §9, lot N8 |
| A7 | La puissance enregistrée (journal, FIT, bilan, historique) est toujours la puissance mesurée ; bonus, équipement, vent et aspiration ne changent que la vitesse virtuelle | Plans T §3.3 et V §2.2 |
| A8 | Aucune donnée personnelle dans le dépôt (noms, coordonnées précises du domicile, adresses Bluetooth réelles, traces réelles) ; elles restent sous `~/OpenRide/` | Règle du propriétaire du 24 octobre |
| A9 | Textures et modèles sous licence libre (CC0) téléchargés en packs, jamais dans le dépôt ; le dépôt garde des couleurs unies | Décision U-Q3, lot P20 |

**Programmes**

| Programme | Rôle | Depuis |
| --- | --- | --- |
| openride-core | Bluetooth, physique, ERG, braquets, bots, journal, FIT, serveur IPC ; en 2.0 aussi règles de jeu et navigation du monde ouvert | 1.0 |
| openride-compiler | Trace vers `.world`, caches d'altitude et d'OSM ; en 3.0 aussi classification des biomes | 1.0 |
| openride-engine (Godot) | Rendu, HUD, menus, sons | 1.0 |
| openride (lanceur) | Lance et surveille le core et l'engine | 1.0 (lot K6) |
| openride-worldgen | Télécharge, met en cache et génère le monde ouvert pendant la séance, piloté par le core | 2.0 (lots W1 et W8) |

**Réseau.** La règle de la 1.0 est simple : une fois le parcours compilé, tout fonctionne sans Internet (SRS §12). La 2.0 l'assouplit à deux endroits, encadrés ainsi :

- **R-NET-1 :** la boucle du core n'attend jamais le réseau ; une séance ne se bloque ni ne s'arrête faute de connexion.
- **R-NET-2 :** seuls le compilateur, le lanceur et `openride-worldgen` téléchargent, avec un cache local et un repli hors ligne.
- **R-NET-3 :** les usages en ligne de la 2.0 sont la météo locale au lancement (vent, décision P1 n° 1, repli sans vent) et les cartes et le relief du monde ouvert (W, repli sur le cache).

Règle adoptée par le propriétaire le 26 octobre (point C4 du §9).

## 4. Exigences de la 1.0

Le détail est dans la [SRS v1.1](SRS_v1.1.md) ; ce tableau en donne l'état. Les numéros de section renvoient à la SRS.

| Id | Exigence | Réf. | Lots | Statut |
| --- | --- | --- | --- | --- |
| 1.0-MAT-1 | Pilotage FTMS du trainer en SIM et en ERG, une procédure à la fois, reprise du contrôle | §4.1 | C, M1, audit FTMS | Livré |
| 1.0-MAT-2 | Cardio : pont du trainer ou ceinture Bluetooth, fréquence figée écartée | §4.1 | M2, Q5 | Livré (M2 ; Q5, PR #195) |
| 1.0-MAT-3 | Zwift Click V2 (deux boîtiers), B lu comme « − », boîtier gauche redémarré quand Zwift le verrouille | §4.2 | K8, Q6 | Livré (K8 ; Q6, PR #193 ; redémarrage `0x18`, PR #595, #607, #609 : − et flèches du gauche reçus sur le PC le 30 octobre) |
| 1.0-MAT-4 | Bluetooth simulé et mode mock : tout se développe sans le vélo | §12 | H3, M5, M6 | Livré |
| 1.0-PHY-1 | Physique à 50 Hz par bilan d'énergie, 250 W à plat ≈ 10,2 m/s | §5 | — | Livré |
| 1.0-PHY-2 | 24 braquets virtuels de 0,65 à 2,00, pente effective bornée | §4.3 | — | Livré |
| 1.0-PHY-3 | Coefficient de difficulté, 50 % par défaut, réglable en séance | §5, §11 | Q1 | Livré |
| 1.0-PHY-4 | Rampe de pente distincte à la montée et à la descente | §5 | Q4 | Livré (PR #194) |
| 1.0-ERG-1 | Lecteur `.zwo`, cibles lissées, biais au Click, saut de bloc, pause | §6 | F, L6 | Livré |
| 1.0-ERG-2 | Formats `.erg` et `.mrc` de GoldenCheetah | — | O9 | Livré |
| 1.0-ERG-3 | Test de FTP, plans sur plusieurs semaines, menu Entraînement | — | O10 à O12 | O10, O11 et O12 livrés (O12 : core PR #395, écrans de l'engine PR #396) |
| 1.0-ERG-4 | Bandeau ERG à l'écran, histogramme, bip à T − 3 s | §6 | N7 | Livré |
| 1.0-ERG-5 | Boutons de l'ERG selon le plan commun (§7.1) : ± court biais ± 2 %, ± long biais ± 10 %, Z bloc suivant, Y pause | §4.4 | O17 | Livré (O17) ; essai complet au Click reporté en 5.0 avec la séance `.zwo` (5.0-ERG-1) |
| 1.0-ERG-6 | ERG dans une session libre depuis l'écran de pause : SIM, ERG libre (puissance cible) ou ERG à cadence verrouillée (cadence ± 10 % depuis l'essai du 1er novembre, puissance adaptée) ; ± = biais de la cible (puissance, ou cadence en ERG cadence), Z = bonus comme en SIM | — | O18 | Livré (PR #550) ; plage ± 10 % choisie après l'essai sur le vélo du 1er novembre |
| 1.0-CMP-1 | Compilateur GPX vers `.world` : route, terrain, OSM, caches | §7 | B1, B2, I3, I4 | Livré |
| 1.0-CMP-2 | Traces FIT et TCX, archives Garmin, compilation au lancement | §7 | M7, N11, O5 | Livré |
| 1.0-CMP-3 | Bibliothèque de parcours et pack de cols célèbres | — | O15, O16 | Livré (O15, O16 ; pack corrigé par la PR #740, 16 cols sur 16 hors ligne) ; première construction du pack sur le PC à faire |
| 1.0-RND-1 | Route, terrain triplanaire, ciel, arbres, HUD avec profil | §8 | E1 à E3 | Livré ; recette visuelle E3/E4 validée par le propriétaire le 1er novembre |
| 1.0-RND-2 | Bâtiments, forêts, eau et sons du parcours | §8 | E4 | Livré |
| 1.0-RND-3 | Préréglages de qualité, au moins 30 images/s en `low` sur la GTX 1060 | §8, §12 | L4, O1, S1 | Livré (L4, O1, brouillard Y1, PR #381) ; S1 : essai sur la GTX 1060 à faire |
| 1.0-RND-4 | Pentes lisibles à l'écran (caméra et relief exagéré) | — | Q2 | Livré (PR #191 ; facteur par défaut à choisir sur la GTX 1060) |
| 1.0-RND-5 | Thèmes et packs de thèmes | §10 | H7, I5, N10 | Livré |
| 1.0-UI-1 | Menus au Click : parcours, entraînements, appareils, bilan | §4.5 | N1 à N6, N13 | Livré |
| 1.0-UI-2 | Menu principal et sous-menu ERG ; l'entrée qui choisit le parcours s'appelle « Parcours » (« Monde ouvert » est réservé à la série W) et l'accueil n'affiche que les modes annoncés par le core (`hello_ack.config.modes`, révision 1.3) | — | N15, N16 | Livré (N15, « Parcours », décision D10 ; N16, PR #249 et #288) |
| 1.0-UI-3 | Réglages depuis le menu (FTP, masse, difficulté, braquet, qualité, thème, mode d'affichage) | §11 | O3, O4 | Livré (O3, O4, mode d'affichage) |
| 1.0-UI-4 | Courbes de la séance façon GoldenCheetah | — | O13, O14 | Livré (O13, O14) |
| 1.0-UI-5 | Bots à l'écran (facultatif pour la 1.0) | — | O7 | Livré (O7, PR #407 ; bots dessinés comme l'avatar, Y18) |
| 1.0-REC-1 | Journal JSONL continu, FIT minimal, reprise après plantage | §9 | N8 | Livré |
| 1.0-REC-2 | Bilan (NP, IF, TSS), historique des séances | — | K7, L7 | Livré |
| 1.0-BOT-1 | Bots à puissance constante et fantôme d'une séance passée | §13 | N9 | Livré |
| 1.0-INS-1 | Lanceur unique, lancement sans terminal, raccourci de bureau | — | K6, L8, N14 | Livré |
| 1.0-INS-2 | Numéro de version unique, notes de version, guide d'utilisation | — | O2, O6 | Livré (O2, O6) |
| 1.0-INS-3 | Recette 1.0 sur le matériel et publication `v1.0.0` | — | O8 | Livré : `v1.0.0` et `v1.0.1` publiées le 1er novembre ; lignes 5 et 14 (séance `.zwo`) reportées en 5.0, ligne 21 (FIT) faite en 3.0 (X56), ligne 7 (ceinture Bluetooth) sans objet |

**Exigences non fonctionnelles de la 1.0** (SRS §12) : délai trainer vers écran sous 100 ms hors rendu ; boucle stable sur 3 h ; 30 images/s au moins en `low` sur la GTX 1060 ; aucune perte de séance si l'engine plante ; hors ligne une fois le parcours compilé ; seuils de passage à Rust de la SRS §14.1.

## 5. Exigences des versions suivantes

### 5.1 Mises à jour 1.x : décor vivant, vent et aspiration (série P), réglages de séance au menu (lots N17 et N18)

Détail : paragraphe « Série P » de [lots/00_INDEX.md](lots/00_INDEX.md) et cahiers [P1](lots/LOT_P1_contrat_vent_decor.md) à [P21](lots/LOT_P21_passants_villages.md). Tous les lots attendent la publication de la 1.0.

| Id | Exigence | Lots | Statut |
| --- | --- | --- | --- |
| 1.x-VNT-1 | Vent physique dans le core : rafales, composante de face, vitesse virtuelle ; en SIM, supplément de pente plafonné à 4 points (réglable) ; en ERG, vitesse seulement ; coupé par défaut en 1.x | P1, P2 | Livré (P1, P2) |
| 1.x-VNT-2 | Aspiration derrière les bots (courbe exponentielle, effet de file, vent de travers) ; le fantôme n'abrite pas | P3 | Livré (P3) |
| 1.x-VNT-3 | Indicateur du vent au HUD (favorable, défavorable, neutre ; intensité de 0 à 4) et de l'abri | P4, P16 | Livré (P4, P16) |
| 1.x-DEC-1 | Arbres et herbe au vent, nuages, météo légère | P5, P6, P8 | Livré (P5, P6, P8) |
| 1.x-DEC-2 | Sons d'ambiance et du vélo (vent selon la vitesse dans l'air, roue libre, « clac » à la reprise) | P9, P10 | Livré (P9, P10) |
| 1.x-DEC-3 | Animaux, éoliennes, drapeaux, véhicules, bord de route, spectateurs, passants | P11 à P15, P21 | Livré (P11 à P15, P21) |
| 1.x-UI-1 | Demi-tour sur la route depuis l'écran de pause (« Faire demi-tour »), puis aussi par Y maintenu en roulant (demande du propriétaire du 8 novembre) | N17 | En PR (8 novembre : commande `u_turn` et champ `dir`, révision 1.9 ; Y maintenu, événement `Y_LONG`, révision 1.11) |
| 1.x-UI-2 | Bots réglés depuis les menus : nombre, puissance de chacun, fantôme, dans les réglages et l'écran de pause | N18 | En revue (PR #789) ; écran Prêt déjà livré par O35 et PL1 |
| 1.x-DEC-4 | Intégration et recette : au moins 55 images/s en `low` sur la GTX 1060, p99 sous 25 ms, tout se coupe par préréglage | P16, P17 | Livré ; RECETTE_P16 validée le 27 octobre sauf vent de travers, vent de dos et décor vivant coupé ; RECETTE_P17 jamais passée |

### 5.2 Version 2.0

**Ambiance et rendu (fin de la série P)**

| Id | Exigence | Lots | Statut |
| --- | --- | --- | --- |
| 2.0-DEC-1 | Jour et nuit : heure, coucher de soleil, nuit étoilée | P7, P19 | En revue (P7 et P18 réunis, PR #781) ; P19 commencé ; réglage `render.day_night` séparé, coupé par défaut (demande du propriétaire du 8 novembre) |
| 2.0-DEC-2 | Quatre saisons (feuillages, neige, vergers en fleurs), inversées dans l'hémisphère sud | P18, P19 | En revue (PR #781) ; réglage `render.seasons` séparé de celui du jour et de la nuit, coupé par défaut |
| 2.0-DEC-3 | Packs de textures à plusieurs niveaux, choisis selon le préréglage et la mémoire vidéo | P20 | Livré (P20, PR #621) ; réglage « Textures du décor » |
| 2.0-VNT-1 | Vent activé par défaut d'après la météo locale, repli sans vent hors ligne (règle R-NET-3) | P1 (décision n° 1) | **Non fait** (oubli relevé le 8 novembre) : reporté en 3.0 (3.0-VNT-1, lot P33, mode `local`, coupé par défaut) |

**Mode Cyber-Rogue (série R)** — détail : [PLAN_SERIE_R.md](2.0/PLAN_SERIE_R.md) et [GDD_CYBER_ROGUE.md](2.0/GDD_CYBER_ROGUE.md)

| Id | Exigence | Lots | Statut |
| --- | --- | --- | --- |
| 2.0-ROG-1 | Mesure du délai du frein avant de caler les fenêtres de jeu | R0 | Outil livré (X5, PR #245) ; essai R0 sur le vélo à faire |
| 2.0-ROG-2 | Frein par décalage centré : pente de l'ennemi + (vitesse − 6) × 1 point, bornée à −10 / +16 % | R5, R8 | Livré (R5, R8) |
| 2.0-ROG-3 | W'bal (W' 20 kJ par défaut, réglable, estimé depuis l'historique) et postures de cadence | R2, R16 | Livré (R2, R16) |
| 2.0-ROG-4 | Salles générées à graine, Firewall à X % de FTP, combat, run en couloirs avec deck, reliques et boss | R3 à R7 | Livré (R3 à R7, branchés par R8) |
| 2.0-ROG-5 | Run composée à partir d'un objectif (VO2max, seuil, endurance) et d'une durée choisis au menu | R15 | Livré (R15) |
| 2.0-ROG-6 | Châssis permanents à bonus de jeu, vies achetées avec les pièces de la série V | R9 | Livré (R9) |
| 2.0-ROG-7 | Scène néon séparée de la scène classique, HUD diégétique, ennemis géométriques, menu ; direction artistique et catalogue graphique générés par le code | R10 à R13, R17 | Livré (R10 à R13, R17) ; contrôle à l'écran avec la recette R14 |
| 2.0-ROG-8 | Recette : run complète, 60 images/s, ressenti des boutons | R14 | À faire : recette R14 (séance S10 de 10 min, `recettes-physiques/PLAN_SESSIONS_10MIN.md`) |

Les cahiers R0 à R17 sont sur `main` ; le contrat de la série est dans le lot T1 (contrat 1.4 commun aux séries R, T et V).

**Mode classique enrichi (série T)** — détail : [PLAN_SERIE_T.md](2.0/PLAN_SERIE_T.md)

| Id | Exigence | Lots | Statut |
| --- | --- | --- | --- |
| 2.0-SEG-1 | Montées détectées automatiquement (500 m, 3 %, 30 m de gain ; catégorie 4 à HC) et sprints déclarés ou proposés, couche `segments` du `.world` | T1 à T3 | Livré (T1, T2, T3, branché dans la séance par T7) |
| 2.0-SEG-2 | Chronométrage interpolé à 0,02 s près, pause Y qui annule, coupure subie qui suspend, boucles et aller-retour | T4 | Livré, module pur (T4, PR #251) |
| 2.0-SEG-3 | Records « avec » et « sans bonus » séparés, classement local avec bots et fantôme | T5, T10 | Livré (T5, T10, PR #414) |
| 2.0-BON-1 | Bonus légèreté (masse × 0,90), aéro (CdA × 0,75), puissance (× 1,10), 15 s, activés par Z, désactivés en ERG, sans effet sur la résistance du trainer | T6, T7 | Livré (T6, T7) |
| 2.0-BOT-1 | Bots à profil (grimpeur, sprinteur, puncheur, diesel) avec CP, W' et masse, calibrés par simulation du parcours à 90, 100 ou 110 % de la FTP ou à un niveau libre | T12, T13 | Livré (T12, PR #487 ; T13, PR #488) ; tactique des bots Y10 (PR #728) |
| 2.0-BOT-2 | Maillots vert et à pois attribués pendant la séance aux points, bots compris | T14 | Livré, module pur (T14, PR #328) |
| 2.0-BOT-3 | Écart en temps de passage avec le bot devant et le bot derrière | T16 | Livré, module pur (T16, PR #275) |
| 2.0-HUD-1 | Lignes, arches et panneaux en 3D ; HUD segment, bonus et bots dans le coin supérieur droit | T8, T9, T15 | Livré (T8, PR #408 ; T9, PR #409 ; T15, PR #453) |
| 2.0-SEG-4 | Recette : un sprint, une montée réelle, chaque bonus, une course contre 4 bots | T11 | En partie : §1 de la recette T11 faite le 7 novembre ; course contre 4 bots (§8) à faire |

**Progression (série V)** — détail : [PLAN_SERIE_V.md](2.0/PLAN_SERIE_V.md)

| Id | Exigence | Lots | Statut |
| --- | --- | --- | --- |
| 2.0-PRG-1 | Une seule progression pour tous les modes, recalculée depuis le journal des séances du jeu (pas les traces importées) ; 50 niveaux | V2, V4 | Livré et branché sur la séance (V2, V4, V11) |
| 2.0-PRG-2 | Pièces gagnées en roulant, dépensées au Garage et pour les vies du Cyber-Rogue | V3b | Livré (V3b, PR #281) |
| 2.0-PRG-3 | Équipement à effets bornés (−3 % de masse, −6 % de CdA au plus), compromis par terrain, temps gagné affiché | V3, V5 | Livré (V3 ; V5, PR #496) |
| 2.0-PRG-4 | Avatar généré par le code, pédalage synchronisé sur la cadence, menu Garage | V6 à V8 | Livré (V6 à V8 ; avatar détaillé Y16) |
| 2.0-PRG-5 | Fin de séance : expérience, pièces, niveau, déblocages | V9 | Livré (V9 ; barre de niveau corrigée par la PR #764) ; recette V10 à faire |

Les cahiers V2 à V11 sont sur `main` et les questions V-Q1 à V-Q13 sont tranchées ; le contrat de la série est dans le lot T1.

**Profils de joueurs et profil d'essai (série MJ)** — détail : [PLAN_SERIE_MJ.md](2.0/PLAN_SERIE_MJ.md)

| Id | Exigence | Lots | Statut |
| --- | --- | --- | --- |
| 2.0-PRF-1 | Un profil = un dossier `~/OpenRide/Profils/<id>/` (réglages du joueur, équipement, records, plan, séances) ; le reste est à la machine | MJ1, MJ4 | Livré (MJ1, MJ4) |
| 2.0-PRF-2 | Profil d'essai `_essai` : séances simulées comptées, jamais par défaut, signalé « ESSAI », « Session simulée » du menu dessus ; le vrai profil n'est jamais modifié (garde-fou d'empreinte) | MJ2, MJ3, MJ8 | Livré (MJ2, MJ3, MJ8) |
| 2.0-PRF-3 | Choix du profil « Qui roule ? » après la connexion des appareils, seulement avec au moins deux profils ; création, nom, renommage et suppression au menu (Click, clavier, souris) ; huit profils au plus | MJ6 à MJ8 | Livré (MJ6 à MJ8) |
| 2.0-PRF-4 | Migration du profil actuel vers `principal` sans perte (contrôle X39), séances simulées et rejouées rangées dans `_essai` | MJ5, MJ10 | Livré (MJ5) ; recette MJ10 sur le PC à faire |

**Monde ouvert (série W)** — détail : [PLAN_SERIE_W.md](2.0/PLAN_SERIE_W.md)

| Id | Exigence | Lots | Statut |
| --- | --- | --- | --- |
| 2.0-MON-1 | Départ choisi sur un globe ou par recherche de lieu, puis sur une carte régionale | W11 | Livré (W11, PR #426) |
| 2.0-MON-2 | Monde généré en direct par `openride-worldgen` ; au moins 3 km de route engagée devant le cycliste ; choix au carrefour jusqu'à 30 m avant, sinon le navigateur choisit | W1, W4 à W9 | Livré (W1, W4 à W9) |
| 2.0-MON-3 | Cache local de 5 Go par défaut, éviction des moins récemment utilisés, régions épinglées ; rien n'est retéléchargé au retour au même endroit | W2 | Livré (W2, PR #285) |
| 2.0-MON-4 | Cartes : tuiles vectorielles mondiales au fil de la balade et préchargées autour des lieux de départ habituels ; extrait régional facultatif ; Overpass jamais pendant la séance | W3, W13 | Livré (W3, W13) |
| 2.0-MON-5 | Monde ouvert autorisé en ERG ; balade, destination ou boucle de X km ; balade enregistrable comme parcours | W6, W14 | Livré (W6 ; W14, PR #418) |
| 2.0-MON-6 | Recette : une heure sans pause d'attente, 55 images/s, gigue de la physique sous 5 ms | W16 | À faire : recette W16 (1 h, à redécouper en trois séances de 20 min) |

**Autres modes et ajouts de la 2.0** (exigences rédigées le 8 novembre d'après les plans et les lots livrés)

| Id | Exigence | Lots | Statut |
| --- | --- | --- | --- |
| 2.0-WTF-1 | Mode « What the fuck » : gags physiques (gravité, monde à l'envers, route qui s'effondre, tempête), Katamari, peloton délirant, chef et plats, chaque règle coupable au menu ; SIM seulement, pente envoyée bornée | WTF1 à WTF7 | Livré ; recette WTF8 à faire |
| 2.0-DS-1 | Mode « Dernier survivant » : arches à écart réglable, dernier du groupe éliminé, bots tacticiens, HUD et bilan | DS1 à DS7 | Livré (PR #705) ; recette DS9 à faire |
| 2.0-ABR-1 | Aspiration plus fine : bots qui s'abritent entre eux, zone latérale et placement, bordure par vent de travers, groupes, abri ressenti (watts économisés), abri des véhicules et des cyclistes du décor | AS1 à AS7 | Livré (#649, #704) ; essais sur le vélo à faire ; véhicules superposés corrigés en PR #775 |
| 2.0-ERG-1 | Test de FTP par rampe, FTP provisoire au HUD, Z pour passer l'échauffement, résultat rangé dans le profil | O10, PR #709 | Livré, validé sur le vélo le 4 novembre |
| 2.0-HIS-1 | Historique des séances au menu | O28 | Livré (PR #666) |
| 2.0-DEC-4 | Personnages du bord de route remodelés et plus variés | Y21 | Livré (PR #715) |

### 5.3 Version 3.0

Détail : [PLAN_SERIE_U.md](3.0/PLAN_SERIE_U.md). Toutes les questions U-Q1 à U-Q5, U-G1 et U-G2 sont tranchées (25 octobre). Cahiers des lots U0 à U22 rédigés le 27 octobre ([index des lots](lots/00_INDEX.md)) ; les questions U-Q6 à U-Q13 nées de cette rédaction (§11 du plan) sont toutes validées le 27 octobre.

| Id | Exigence | Lots | Statut |
| --- | --- | --- | --- |
| 3.0-BIO-1 | Seize biomes ; au plus quatre par tuile de terrain (trois en `low`) ; biome automatique d'après les données réelles et forçage au compilateur et au menu | U1, U2, U16, U19 | En partie : U1, U16 et U19 livrés ; classification automatique U2 en revue (PR #734) |
| 3.0-BIO-2 | Occupation du sol ESA WorldCover téléchargée par le compilateur et mise en cache | U2 | En revue (U2, PR #734) |
| 3.0-BIO-3 | Variantes régionales de roches, terres et bâtiments à grosse maille | U4, U14 | U4 en revue (PR #785, brouillon) ; U14 attend U4 |
| 3.0-BIO-4 | Mer, côtes et plages | U3, U9 | U3 en revue (PR #790) ; U9 attend U3 |
| 3.0-BIO-5 | Saisons propres à chaque biome (saison sèche et saison des pluies, désert, polaire) | U13 | Bloqué : U13 attend P18 (PR #781), puis P19 |
| 3.0-BIO-6 | Végétation, sons, faune et atmosphère par biome | U7, U8, U10 à U12 | Livré : U7, U8, U10 et U12 ; sons U11 en revue (PR #787) |
| 3.0-BIO-7 | Thème 2.0 en pack de biomes, thèmes 1.x toujours lisibles ; textures CC0 en packs, bibliothèque de 5 Go | U1, U15 | Livré (U1, U15) |
| 3.0-BIO-8 | Budget : 1 Go de mémoire vidéo au plus pour le décor, 55 images/s en `low` ; premier jalon : prairie, forêt tempérée, vignobles et cultures, haute montagne, méditerranéen, littoral | U6, U17, U18, U19 | U6, U17 et U19 livrés ; U18 : partie PC faite (PR #729), étape 1 après U2, étape gravel à refaire en « Chemins réels » ; cultures et forêt encore au-dessus des budgets, essais de gain reportés en 5.0 (5.0-RND-1) |
| 3.0-GRV-1 | Option « gravel » coupée par défaut : chemins de terre ouverts au monde ouvert ; résistance au roulement 2 à 3 fois celle du bitume, en supplément de pente sous le même plafond que le vent ; en ERG, vitesse seulement ; surface réelle d'OSM (« Chemins réels ») ou imposée à tout le parcours (« Gravier », « Terre », « Chemin compact ») pour rouler en gravel sur une trace revêtue (décision U-Q8 du 27 octobre) ; ruban de terre ou de gravier | U1, U16, U20, U21, U22 | Livré (U16, U20, U21, U22) ; essai gravel sur le vélo noté 5/5 le 7 novembre, analyse à refaire avec « Chemins réels » |
| 3.0-ECR-1 | Écran de démarrage « Start your engines » plus stylé (demande du 4 novembre, maquette A) | Y, PR #714 | Livré |
| 3.0-PEL-1 | Peloton d'environ 12 coureurs : 11 bots et un fantôme, trame `state` sous 4 096 octets, bots enfermés qui lèvent le pied, bots détaillés plafonnés par qualité, ligne « Peloton » au menu | PL1 | Livré (PR #716, révision IPC 1.6) |
| 3.0-DS-1 | Dernier survivant jusqu'à 11 adversaires | DS8 | Livré (PR #735) |
| 3.0-FIT-1 | FIT importé sans erreur dans Garmin Connect et GoldenCheetah (ligne 21 de la recette 1.0) | X56 | Livré, validé le 7 novembre |
| 3.0-VNT-1 | Vent d'après la météo locale (Open-Meteo) au lancement, coupé par défaut et activé au menu (décisions du 8 novembre), lu par un processus annexe, repli sans vent hors ligne, le core n'attend jamais le réseau (reprend 2.0-VNT-1, règle R-NET-3) | P33 | Spécifié (cahier rédigé le 8 novembre) |
| 3.0-VNT-2 | Lenticulaire et vent de travers : pénalité de la roue lenticulaire par vent de travers (question V-Q13), vent de travers déjà calculé pour l'abri (AS3) | P34 | En revue |

### 5.4 Version 4.0

Détail : [4.0/README.md](4.0/README.md). Code de la 4.0 déjà fusionné sur `main` avant la publication de la 3.0 (GP1 à GP3, GP6, U23 étape 1) : il reste caché tant que son entrée au menu n'est pas livrée (§2.1).

| Id | Exigence | Lots | Statut |
| --- | --- | --- | --- |
| 4.0-BON-1 | Bonus tactiques : un seul modèle de bonus dans `powerups.py`, tirage selon le contexte et refus motivé ; Plume, Casque, Puissance, Enclume, Aspiration +, Échappée, Rouleau compresseur ; réglage `powerups.mode` à trois choix ; tous coupés en ERG, ERG de session libre compris | TT1 à TT8 | Spécifié (cahiers rédigés le 8 novembre) |
| 4.0-GP-1 | Grand Prix des objets : treize objets propres à OpenRide, chacun désactivable, boîtes de ravitaillement, tirage selon le retard, effets sur la vitesse virtuelle seulement, bots qui prennent et lancent les objets, jusqu'à 11 bots | GP1 à GP11 | GP1, GP2, GP3 et GP6 livrés ; GP5 en revue (PR #779) ; reste GP4, GP7 à GP11 |
| 4.0-VD-1 | Vélodrome couvert : piste de 250 m en bois à virages relevés, salle et tribunes, épreuves de piste (poursuite, kilomètre, scratch, points, élimination, keirin, omnium, heure…), bots du peloton sur la piste | VD0 à VD12 | VD0 livré (PR #725) ; VD1 à VD5 en revue (PR #746) ; VD6, VD7, VD9 et VD10 en revue (PR #769) |
| 4.0-CLK-1 | Boîtier gauche du Click fiable quand Zwift tourne sur un autre appareil, essai sur le vélo (décision du 28 octobre) | K9 | Essayé le 8 novembre : le maintien sans redémarrage ne tient pas sous firmware 1.2.0, le redémarrage `0x18` reste (environ 4 s par minute) |
| 4.0-BIO-1 | Constructions et faune propres à chaque biome (demande du 6 novembre) | U23 | Étape 1 livrée (PR #748) ; étape 2 en revue (PR #771) |
| 4.0-DEC-1 | Panneaux d'approche plus grands (+25 %) et plus travaillés (demande du 6 novembre) | panneaux, PR #773 | En revue : captures validées le 8 novembre, banc GPU à faire |
| 4.0-RES-1 | Résistance calculée sans trou à basse vitesse, sans pompage à basse cadence | RC4, RC5 | RC4 livré (PR #718, recette 4/5 le 7 novembre) ; RC5 en revue (PR #766) |

### 5.5 Version 5.0

Détail : [5.0/README.md](5.0/README.md).

| Id | Exigence | Lots | Statut |
| --- | --- | --- | --- |
| 5.0-CT-1 | Course tactique : réserve W′ symétrique et Burnout, sillage et catapulte, parade et rétro-radar, crédits gagnés en tête et capacités, virages et Apex, circuits générés ; charte cartoon | CT0 à CT12 | CT0 livré (PR #743) ; CT9 maquettes validées le 29 octobre ; reste CT1 à CT8, CT10 à CT12 |
| 5.0-WF-1 | Trainer en Wi-Fi (Direct Connect) et mode de mesures rapides ; mesure WF1 d'abord, pilote WF2 à WF6 seulement si elle le justifie (gain attendu sous 5 %) | WF0 à WF6 | Planifié (plan seul, cahiers après WF1) |
| 5.0-CO-1 | Séance conseillée au menu selon les courses et le besoin (aérobie léger, aérobie intense, anaérobie), suggestion de la montre Garmin, séances de jeu calibrées | CO0 à CO9 | CO0 et CO1 livrés (PR #747) ; CO3 à CO6 et CO9 en revue (PR #770) ; reste CO2, CO7, CO8 |
| 5.0-BC-1 | Badges et cartes à collectionner, recalculés depuis le journal, visuels générés hors dépôt | BC0 à BC7 | BC0 à BC4 livrés (BC2 : PR #758, révision IPC 1.8) ; BC5 et BC6 en revue (PR #783) ; reste BC7 |
| 5.0-ERG-1 | Séance `.zwo` complète en ERG au Click : cibles, biais ± 2 % et ± 10 %, bip à T − 3 s, Z, Y, courbes lisibles (lignes 5 et 14 de la recette 1.0) | F, O17, O14 | Code livré ; recette à faire en un bloc de 10 min |
| 5.0-RND-1 | Essais de gain de performance GPU (cultures, forêt, alpin : effets d'écran, prépasse de profondeur) jusqu'à tenir les budgets du §8 | Y, [HISTORIQUE_ESSAIS_GRAPHIQUES.md](HISTORIQUE_ESSAIS_GRAPHIQUES.md) §5 | Planifié (décision du 8 novembre) |
| 5.0-RND-2 | Graphisme et comportement des bots améliorés en toute fin de projet, sous les budgets GPU (série Y restante : Y3, Y4, Y7, Y9, Y12) | Y | Spécifié |
| 5.0-DEM-1 | Mondes demo gardés dans le jeu de base, nettoyés des artefacts de test et renommés en parcours explicites (demande du 5 novembre), **avant** l'installeur | O37 | Spécifié (cahier rédigé le 8 novembre) |
| 5.0-INS-1 | Installation simple sur Linux, idéalement un seul fichier exécutable, avec une notice si ce n'est pas un fichier unique ; en tout dernier (demandes du 31 octobre et du 5 novembre) | J4, J9 | Spécifié (J9 rédigé le 8 novembre ; J4 en cours) |

## 6. Contrats

### 6.1 Révisions du contrat IPC

Le champ `v` reste 1 : tous les ajouts sont compatibles. Chaque révision est notée dans le journal des changements de [ipc_v1.md](contracts/ipc_v1.md).

| Révision | Contenu | Lots | Version | Statut |
| --- | --- | --- | --- | --- |
| 1.0 | État à 30 Hz, commandes, heartbeat, pannes | C, D | 1.0 | Livré |
| 1.1 | Listes des parcours et entraînements, `devices`, bilan enrichi, reprise après plantage | N1 | 1.0 | Livré |
| 1.2 | `set_difficulty`, `difficulty_pct` ; appairage depuis le menu (`scan_devices`, `pair_devices`…). Fermée : plus aucun ajout | Q1, N13 | 1.0 | Livré |
| 1.3 | Révision de la sortie de la 1.0 : champs `wind` et `draft` de `state`, `state` à 4 096 octets, `rev` et `modes` (P1, livrés) ; réglages (`list_settings`, `set_setting`, message `settings`), précisions de X25, `bad_args`, imports d'entraînements (`list_imports`, `create_workout`, `import_workout`), `PLUS_UNCLEAR` et `MINUS_UNCLEAR` ; événements de tous les boutons du Click (`A_SHORT`, `A_LONG`, `Z_SHORT`, `Z_LONG`, `Y_SHORT`, `LEFT_SHORT`, `RIGHT_SHORT`, `UP_SHORT`, `DOWN_SHORT`, plan de boutons du §7.1) ; demi-tour et bots réglés au menu s'ils fusionnent avant l'étiquette `v1.0.0`. Se ferme à l'étiquette `v1.0.0` | P1, O3, O4, X25, #288, N16, #287 | 1.0 (P1 sert la 1.x) | P1, X25, O3, O4, l'audit IPC (#288), N16 (#249), événements des boutons (#287) et contrat d'O12 (#395) livrés |
| 1.4 | (Les événements des boutons sont déjà en 1.3.) Mode `ROGUE` et valeur `"rogue"` de `modes` ; champs `segment`, `powerup`, `jerseys`, `bot_ahead`, `bot_behind` et objet `rogue` de `state` ; champs des bots à profil ; `summary.segments` et `summary.rogue` ; messages `segment_result`, `room`, `loot`, `garage`, `progression`, `xp_result` ; commandes `start_run`, `rogue_resync`, `list_garage`, `equip`, `buy`, `set_avatar` ; `hello_ack.config.rogue` et `progression` | T1 | 2.0 | Contrat validé par le propriétaire et fusionné le 27 octobre (lot T1, PR #392, un seul lot de contrat, décision D4) ; branché depuis (R8, T7, V11), le core annonce désormais `rev` « 1.5 » |
| 1.5 | Monde ouvert : `start_open_world`, `choose_branch`, champ `open_world`, `world_status` et messages de la carte ; limite unique de 4 096 octets pour tout message hors messages en parties (décision du propriétaire du 27 octobre) ; puis, dans l'ordre des fusions : champ `group` et réglages des volumes et des images/s (24 réglages au plus), bots à profil dans `start.bots` et leur `level_pct` (T12, T13), ERG d'une session libre (`set_ride_mode`, `erg.kind` et champs `cadence_*`, O18) ; profils de joueurs : `list_profiles`, `select_profile`, `create_profile`, `rename_profile`, `delete_profile`, message `profiles`, `hello_ack.config.profile`, `hello_ack` renvoyé après un changement de profil, codes `profile_invalid` et `name_invalid` (MJ6) ; contenus installables : `list_contents`, `install_content`, message `contents`, codes `content_invalid` et `content_failed` (O25) ; watts économisés à l'abri `draft_w` dans `state`, `summary.draft_time_s` et `summary.draft_kj` (AS5) ; et tous les ajouts compatibles du 28 octobre au 3 novembre notés au journal d'ipc_v1.md (AS2, AS6, AS7, WTF2, DS2, MJ6, O23 à O36, O28, test de FTP) | W1, T12, T13, O18, MJ6, O25, AS5 | 2.0 (O18 sert la 1.0) | Livré : W1 (PR #282), T12 (#487), T13 (#488), O18 (#550), `devices.trainer.busy` (#540), `set_setting` en séance (#552) ; le core et l'engine annoncent `rev` « 1.5 » |
| 1.6 | Peloton d'environ 12 bots : jusqu'à 12 éléments dans `bots` (`state`, `start`, `last_choices`), liste allégée au-delà de 5 bots | PL1 | 3.0 | Livré (PR #716, 6 novembre) |
| 1.7 | Mode `grandprix` (argument `mode` de `start`, `hello_ack.config.modes`), objet `gp` de `state`, champs `item` et `fx` des bots, `summary.gp`, message `gp_hit` ; commandes génériques `list_mode_options` et `set_mode_option`, message `mode_options`. Fermée | GP2 | 4.0 | Livré (7 novembre) |
| 1.8 | Collection de cartes : commandes `list_collection` et `collection_seen`, message `collection`, objet facultatif `summary.collection` | BC2 | 5.0 | Livré (PR #758, 8 novembre) ; le core annonce `rev` « 1.8 » |
| 1.9 | Demi-tour depuis la pause : commande `u_turn` (en `PAUSED` seulement, sinon `busy`), champ facultatif `dir` de `state` (`-1` à rebours, absent vaut `1`), `grade` dans le sens roulé | N17 | 1.x | En PR (lot N17, 8 novembre) ; 1.9 et non 1.8, réservée à la collection de cartes (lot BC2, PR #758) ; le core annonce `rev` « 1.9 » |
| 1.11 | Demi-tour en roulant : événement `input` `Y_LONG` (Y maintenu 0,9 s ou plus, sans zone floue) ; pendant `RUNNING`, demi-tour sans arrêt aux conditions de `u_turn`, sinon pause | N17 (suite) | 1.x | En PR (8 novembre) ; 1.10 prise par #788 |
| (1.5) | Série U : clés facultatives `biome` et `gravel` de `hello_ack.config`, aucun nouveau message (le menu passe par `set_setting`) | U1, U16 | 3.0 | Livré : prévu pour la 1.6, avancé dans la 1.5 avec le lot U16 (PR #639, journal d'ipc_v1.md du 31 octobre) |

**Ajouts fusionnés le 29 octobre** (notés au journal de [ipc_v1.md](contracts/ipc_v1.md)) : champ facultatif `busy` de `devices.trainer` (PR #540, Control Point occupé par un autre appareil, liaison gardée) ; `set_setting` accepté pendant la séance pour les réglages `applies` = `now` (PR #552, matrice X42) ; réglage `render.draft_gauge` (jauge d'abri). Sans changement IPC : champ facultatif `reason` des lignes `event` du journal de séance (PR #542) et plus aucun bloc `freeride` en ERG (lot O19, consigne jamais sous 50 W). Aucun ajout du contrat n'est en revue au 29 octobre au soir.

**Révisions réservées par des PR ouvertes (8 novembre au matin).** La règle reste « première révision libre au moment de la fusion » : ces numéros sont provisoires et chaque PR prend, à sa fusion, le numéro qui suit la dernière révision de `main`.

| Révision réservée | Contenu | Lot, PR | Écart à corriger à la fusion |
| --- | --- | --- | --- |
| 1.9 | Commande `u_turn` et champ `dir` de `state` (demi-tour depuis la pause) | N17, PR #791 | **Même numéro que la PR #789** : la seconde fusionnée prend 1.10 |
| 1.9 | Commande `set_bots` (bots changés en pause), ligne `bots` du journal | N18, PR #789 | Idem |
| 1.10 | Bilan en tuiles et profil du segment | N20, PR #788 | Prend la révision qui suit N17 et N18 |
| 1.11 | Demi-tour sur Y maintenu en roulant | suite de N17, PR #792 (brouillon) | Idem |
| (1.7) | Objet `track` de `state` (épreuves de piste) | VD6, PR #769 | **La 1.7 est fermée** (GP2) : la PR doit prendre la révision libre suivante |
| — | Commande `get_coach`, message `coach` | CO3, PR #770 | Le contrat doit annoncer sa révision à la fusion |


Règles de numérotation (décision du propriétaire du 27 octobre, « au plus propre », audit de cohérence) : les révisions se suivent dans l'ordre des fusions, si bien qu'un programme qui annonce `rev` « 1.3 » connaît tout ce qui est noté 1.2 et 1.3. Une révision fermée ne reçoit plus d'ajout : la 1.2 est fermée depuis la fusion de la 1.3 ; la 1.3 reste ouverte jusqu'à l'étiquette `v1.0.0` et reçoit tous les ajouts de la 1.0 qui fusionnent avant elle ; la 1.4 est celle des séries R, T et V, en un seul lot de contrat, T1 (décisions D2 de l'audit IPC et D4 de l'audit de cohérence) ; les événements de tous les boutons sont déjà dans la 1.3, une seule fois ; W1 prend la 1.5. Un ajout fait après la 1.0 hors de ces séries prend la première révision libre à sa fusion. Numérotation 1.4 et 1.5 confirmée par le propriétaire le 26 octobre (décision D2 de l'audit IPC). L'ancienne proposition N13 = 1.3, P1 = 1.4, R/T = 1.5 est périmée.

### 6.2 Format `.world` et thèmes

| Ajout | Lot | Version | Statut |
| --- | --- | --- | --- |
| Couches route, terrain, bâtiments, végétation, points d'intérêt, eau | B1, B2, I3, I4 | 1.0 | Livré |
| Points d'intérêt `wind_turbine` et `flag` ; thème 1.2 (nuages, météo, ambiance, faune, saison, heure) | P1 | 1.x | Livré |
| Niveaux de textures dans le thème | P20 | 2.0 | Livré (PR #621) |
| Couche `segments` (format 1.3, `segments.json`) | T1, T3 | 2.0 | Format écrit (T1) ; écrite par le compilateur et le parcours de démonstration (T3) |
| Monde vivant : `live`, origine sur grille UTM, route par parties, couches par carré, `junctions.json` | W1 | 2.0 | Livré (PR #282) |
| Couche `biome`, variante régionale, eau `sea`, couche `coast` ; colonne `surface` de la route et classe `g` du monde ouvert ; thème 2.0 en pack de biomes | U1 | 3.0 | Format livré le 28 octobre (U1) ; couches remplies par U2 (PR #734), U3 (PR #790) et U4 (PR #785) |
| Colonne `bank_deg` de `route.json`, surface `wood`, couche `venue` (vélodrome, format 1.7) | VD1 | 4.0 | En revue (PR #746) |

### 6.3 Configuration et réglages du menu

Toutes les valeurs ajustables sont dans `~/OpenRide/config.toml` (SRS §11). **Règle (lot X53) :** chaque clé est soit réglée par le menu « Réglages » ou un autre écran, soit rangée avec sa raison dans `config.py` (`EXPERT_KEYS`, `DEV_KEYS`, ou `PENDING_KEYS` avec le lot qui la reliera au menu) ; `core/tests/test_options_menus.py` le vérifie. Au 8 novembre, `PENDING_KEYS` est vide. Les réglages du menu sont définis dans `core/src/openride_core/settings.py` et rangés en six sous-écrans (`GROUPS`) :

| Sous-écran | Réglages (clé de `config.toml`) |
| --- | --- |
| Cycliste | FTP, poids, FC max (`rider.*`) ; poids du vélo (`bike.mass_kg`) |
| Séance | Difficulté (`trainer.difficulty_pct`), braquet de départ, bonus (`powerups.mode`), niveau des bots (`bots.level_pct`), gravel (`gravel.mode`), pilotage du trainer (`trainer.control` : `sim`, défaut revenu le 2 novembre en 1.0.2, ou `resistance`, résistance calculée), départ au pédalage (`depart.mode`, `depart.cadence_rpm`), placement dans la roue (`ride.auto_draft`), abri derrière les véhicules (`ride.vehicle_draft`), options du Dernier survivant (`survivor.*`) et du Grand Prix (`grandprix.*`, à cacher jusqu'à GP9, §2.1) |
| Graphisme | Qualité (`render.quality`, `low` par défaut), textures du décor, thème, courbes de la séance, mode d'affichage, images/s, jauge d'abri, vue de caméra, biome du décor, décor vivant, relief exagéré (`render.*`) ; à venir : jour et nuit (`render.day_night`), saisons (`render.seasons`), deux réglages séparés, coupés par défaut (P19) |
| Son | Volume général, vent et roue libre, ambiance, bips et événements, bruitages et musique du Cyber-Rogue (`audio.*`) |
| Vent | Mode, force, direction, rafales, plafond, ressenti (`wind.*`, voir ci-dessous) |
| Avancé | Téléchargement des cartes et cache du monde ouvert (`open_world.*`), place pour les thèmes, progression et Garage (lot O27) |

**Vent (état de `main` au 8 novembre).** `[wind] mode` vaut `off` par défaut ; les autres valeurs sont `fixed` (force et direction fixes), `gusty` (rafales d'amplitude `gust_pct`) et `theme` (vent du thème 1.2) ; le lot P33 ajoute `local` (météo du jour, ci-dessous). En SIM, le vent devient un supplément de pente plafonné à `max_grade_offset_pct` (4 points par défaut, plafond commun avec le gravel) ; avec `feel = "ftms"`, il passe par le champ vent de la commande FTMS 0x11 ; en ERG, il ne change que la vitesse virtuelle. Le mode WTF « tempête » et l'objet « vent contraire » du Grand Prix ajoutent leur vent ; le Cyber-Rogue n'en a pas. Le décor vivant prend le vent du thème (8 km/h) quand le core n'en envoie pas ; le HUD n'affiche le vent que s'il est actif. Météo du jour (lot P33, 3.0-VNT-1, en revue) : avec `local`, le lanceur lit chez Open-Meteo, dans un fil à part et en 5 s au plus, le vent à 10 m au départ de chaque parcours installé (positions arrondies à 0,1°, environ 10 km), le ramène à hauteur de cycliste (× 0,6) et l'écrit dans `~/.cache/openride/meteo_vent.json` ; une lecture sert 3 h. Le core lit ce fichier au choix du parcours et au départ, jamais le réseau ; sans lecture de moins de 3 h, la séance est identique à `off`, avec une ligne au journal et l'état de la lecture dans la légende du réglage Vent.

**Jour, nuit et saisons (P7, P18, P19).** Modèles et shaders en revue (PR #781) ; aucun effet à l'écran avant P19. Réglages décidés le 8 novembre : `render.day_night` (`off`, `theme`, `real`, `accelerated`) et `render.seasons` (`off`, `date`, `spring`, `summer`, `autumn`, `winter`), chacun coupable seul, coupés par défaut jusqu'aux bancs dans les trois qualités et à la validation des captures. Les saisons par biome (U13, 3.0) viennent ensuite.

Sections réservées aux experts (sans menu, raison dans `EXPERT_KEYS`) : modèle physique (`bike.cda_m2`, `crr`), réglages fins du trainer, boîte de vitesses virtuelle, seuils d'appui du Click, génération du monde ouvert, facteurs du gravel, seuils de la danseuse de l'avatar, valeurs du Cyber-Rogue, durées du départ.

## 7. Boutons du Click et vues de caméra

### 7.1 Une même famille d'action par bouton, partout

Demande du propriétaire du 26 octobre (point C7) : chaque bouton garde le même **type** d'action d'un mode à l'autre, pour qu'on n'ait jamais à se demander « ici, Y fait quoi ? ». Plan validé le 26 octobre, puis réécrit le 27 octobre sans aucune exception, menus compris (principe du propriétaire : « on évite les exceptions »). **Ce tableau est la seule référence** : la SRS, les plans et les cahiers y renvoient au lieu de le recopier.

Boîtier droit : +, A, B, Y, Z ; boîtier gauche : −, flèches. Les deux boîtiers répondent ; Zwift verrouille le gauche environ une minute après la connexion et OpenRide le redémarre alors tout seul, d'où environ 4 s sans boutons à gauche chaque minute (SRS §4.2). B double donc toujours « − », et rien d'indispensable n'est mis sur le seul boîtier gauche : les flèches sont des raccourcis. Appui court : moins de 0,5 s ; appui long : 0,9 s ou plus ; entre les deux, rien ne se passe et l'écran le dit (`PLUS_UNCLEAR`, `MINUS_UNCLEAR`).

| Bouton | Famille | Menus | Classique SIM | ERG | Cyber-Rogue | Monde ouvert | Grand Prix des objets |
| --- | --- | --- | --- | --- | --- | --- | --- |
| + / B (ou −), court | Déplacer ou doser, petit pas | Élément suivant, précédent | Braquet ± 1 | Biais ± 2 % | Vitesse du frein ± 1 | Comme le mode roulé (SIM ou ERG) | Braquet ± 1 |
| + / B (ou −), long | Déplacer ou doser, grand pas | Cinq éléments plus loin, plus haut (bornés à la liste) | Braquet ± 10 | Biais ± 10 % | Vitesse du frein ± 3 | Comme le mode roulé | Braquet ± 10 |
| Y court | Interrompre et revenir | Écran précédent ; sur l'écran de pause, reprendre | Pause et reprise | Pause et reprise | Pause et reprise | Pause et reprise | Pause et reprise |
| Y long | Interrompre et revenir : revenir sur ses pas | Comme Y court | Demi-tour sans s'arrêter (sinon pause) | Demi-tour sans s'arrêter (sinon pause) | Pause et reprise, comme Y court | Pause et reprise, comme Y court | Pause et reprise, comme Y court |
| Z court | Action du mode | Aucune (un menu n'est pas un mode) | Bonus (T) | Bloc suivant | Attaque | Bonus (T) | Utiliser l'objet en réserve |
| Z long | Action spéciale du mode | Aucune | Repère « décrochage » au journal | Repère « décrochage » au journal | Carte ou relique active (T1) | Repère « décrochage » au journal | Repère « décrochage » au journal |
| A court | Choisir : option suivante du choix affiché | Élément suivant | Vue de caméra suivante | Vue de caméra suivante | Couloir ou carte suivant | Branche suivante au carrefour, sinon vue suivante | Voie suivante quand le choix de voie est affiché, sinon vue suivante |
| A long | Valider le choix affiché | Valider l'élément | Revenir à la vue par défaut | Revenir à la vue par défaut | Valider le couloir ou la carte | Valider la branche, sinon revenir à la vue par défaut | Revenir au placement automatique, sinon à la vue par défaut |
| Flèches gauche, droite (boîtier gauche) | Choisir, raccourci | Élément précédent, suivant | Aucune | Aucune | Couloir ou carte précédent, suivant | Branche à gauche, à droite | Voie à gauche, à droite |
| Flèches haut, bas (boîtier gauche) | Vue, raccourci | Aucune (pas de vue dans un menu) | Vue suivante, précédente | idem | idem | idem | idem |

Règles communes, valables partout :

- **A agit sur le choix affiché.** Un menu, un carrefour, une liste de couloirs ou de cartes sont des choix : A court passe à l'option suivante, A long valide. Sans choix affiché (en roulant), le choix est celui de la vue de caméra.
- **Y revient en arrière** : pause en séance, écran précédent dans un menu, reprise depuis l'écran de pause.
- **Y maintenu (8 novembre, demande du propriétaire, contrat IPC 1.11)** : en roulant sur un parcours (classique SIM, ERG), demi-tour sans s'arrêter, aux mêmes conditions que la ligne « Faire demi-tour » de l'écran de pause (lot N17) : même position, sens inversé, vitesse gardée, et l'écran affiche « Demi-tour ». Là où le demi-tour n'existe pas (départ d'un parcours en ligne, Cyber-Rogue, monde ouvert, Dernier survivant, Grand Prix), Y maintenu vaut Y court. Y n'a pas de zone floue : un appui de moins de 0,9 s est un Y court, pour qu'une pause ne se perde jamais.
- **Z n'a que l'action du mode** ; il ne fait rien dans un menu.
- **Pas de roue libre en ERG** (choix du propriétaire du 29 octobre, lot O19) : la consigne ERG ne descend jamais sous 50 W, biais compris, et un bloc FreeRide d'un `.zwo` devient un palier à 50 W. Les boutons gardent donc la colonne ERG d'un bout à l'autre de l'entraînement. Le test de FTP se fait par la rampe seule.
- **ERG d'une session libre (lot O18)** : choisi sur l'écran de pause, il garde la colonne ERG, sauf Z, qui reste le bonus de la colonne SIM (pas de blocs) ; en ERG à cadence verrouillée, le biais s'applique à la cadence cible.
- **Fin d'un entraînement (1er novembre)** : après le dernier bloc, la séance continue en parcours libre ; le bandeau invite à « Y puis A maintenu pour terminer et enregistrer », et Y ouvre la pause avec le focus sur « Terminer et enregistrer » (Y garde son rôle, A long valide comme partout). Champ `workout_done` de `state` (contrat IPC 1.5).
- **Repère « décrochage » (lot X47, séance du 29 octobre)** : en roulant, hors Cyber-Rogue, Z long (Maj+Z au clavier) écrit `{"kind": "event", "event": "decrochage"}` au journal quand le cycliste sent le trainer décrocher, et l'écran le confirme. L'outil `decrochages` (lot X44) met ce repère face aux chutes de puissance mesurées. Rien d'autre ne change : ni braquet, ni consigne, ni chronomètre.
- **Le grand pas vaut dix petits pas en séance** et cinq éléments dans un menu.
- **Clavier (décision D6 du 27 octobre) :** il double le Click touche pour touche, avec les mêmes seuils d'appui (court sous 0,5 s, long à 0,9 s ou plus, zone floue entre les deux), en menu comme en séance ; une touche n'a jamais d'autre rôle que celui de son bouton. Pas de bouton pour la difficulté (décision Q1).

| Bouton du Click | Touche | L'appui long aussi par | Remarque |
| --- | --- | --- | --- |
| + | + (ou =, + du pavé numérique) | Page haut | — |
| − ou B | − (− du pavé numérique) | Page bas | B n'a pas de touche propre : il double « − » |
| A | A | Maj+A, Entrée | Entrée vaut donc « valider » partout |
| Y | Y | Maj+Y | Échap vaut Y court |
| Z | Z | Maj+Z | — |
| Flèches du boîtier gauche | Flèches du clavier | — | Haut et bas changent de vue en séance ; ils ne font plus le braquet |

Les lettres sont lues comme imprimées sur la touche (AZERTY comme QWERTY). Les synonymes (Page haut, Page bas, Maj+lettre, Entrée, Échap) servent aux claviers où l'appui long est malcommode et au fournisseur clavier du terminal (mode mock), qui ne sait pas mesurer la durée d'un appui. Les anciennes touches P et Espace (pause) et la navigation de menu propre au clavier disparaissent.

Changements à reporter, tous dans des lots identifiés :

| Où | Avant | Après | Lot |
| --- | --- | --- | --- |
| Menus (SRS §4.5, PR #287) | + long : valider ; − long : revenir ; puis A = valider et Z = retour (PR #287) | Tableau ci-dessus : ± déplacent, A court élément suivant, A long valide, Y revient, Z ne fait rien | PR #287, à réécrire avant fusion ; elle ajoute aussi les événements de tous les boutons à la 1.3 |
| ERG (1.0, SRS §4.4) | + long : bloc suivant ; − long : pause ERG à 0 % | ± long : biais ± 10 % ; Z : bloc suivant ; Y : pause de la séance (déjà là) | O17 (fait) |
| Cyber-Rogue (plan R) | Y : attaque ; A long : pause | Z : attaque ; Y : pause | T1 (fait dans le cahier) |
| Monde ouvert (W-Q1) | A court : faire défiler les branches | Inchangé, plus A long : valider la branche | W1 |
| Classique (plan T) | A libre | A : vues de caméra | V12 (§7.2) |
| Clavier (engine `key_map.gd`, fournisseur du terminal) | Flèches haut et bas = braquet, Page haut et bas = appuis longs, P, Espace et Échap = pause, Entrée et Échap = valider et revenir dans les menus | Tableau du clavier ci-dessus ; en séance, la touche suit le chemin du Click (core, puis relais à l'engine) | O17 (fait) |

- **Modes de la 2.0 à la 5.0 :** le WTF, le Dernier survivant et le vélodrome suivent la colonne « Classique SIM » ; dans le WTF, Z court refuse aussi le plat du chef (action du mode). La Course tactique (CT1) et les bonus tactiques (TT1) ajoutent leur colonne ici avant tout code, sans nouvelle famille d'action.

Conséquence : avec ce plan, le Cyber-Rogue n'a plus à être exclu du monde ouvert (point C7 levé).

### 7.2 Vues de caméra

Demande du propriétaire du 26 octobre (point C6) : la caméra unique de la SRS §8 devient un choix de vues.

| Id | Exigence | Lots | Statut |
| --- | --- | --- | --- |
| 2.0-CAM-1 | Quatre vues : subjective (celle de la 1.0, avatar masqué), suivi proche derrière l'avatar, suivi éloigné en hauteur (bots, carrefours, peloton), latérale façon retransmission | V12 (après V6) | Livré (V12, 28 octobre) ; banc par vue à faire |
| 2.0-CAM-2 | Changement de vue au Click (A court et flèches haut et bas ; A long revient à la vue par défaut, §7.1) et au clavier, transition douce de moins d'une demi-seconde ; la dernière vue est retenue dans `[render] camera` | V12 ; clavier O17 | Livré (V12, O17) |
| 2.0-CAM-3 | Vue par défaut : subjective tant que l'avatar n'existe pas, suivi proche ensuite ; le Cyber-Rogue garde ses effets de champ de vision et de tremblement dans chaque vue | V6, R11 | Livré (V6, V12, R11) |
| 2.0-CAM-4 | Lisibilité des pentes (lot Q2 : caméra inclinée, relief exagéré) appliquée à toutes les vues | Q2 | Livré en vue subjective (Q2, PR #191) ; à vérifier dans les autres vues avec le banc par vue |
| 2.0-CAM-5 | Budget : aucune vue ne fait passer sous 55 images/s en `low` ; les vues éloignées utilisent les mêmes préréglages de distance que la vue subjective ; le tri de ce qui est dessiné suit la caméra active | V12, S1, P16 | À mesurer : banc par vue en `low`, `medium` et `high` |

## 8. Exigences non fonctionnelles par version

| Exigence | 1.0 | 1.x et 2.0 | 3.0 | 4.0 et 5.0 |
| --- | --- | --- | --- | --- |
| Images par seconde en `low` sur la GTX 1060 | 30 au moins | 55 en moyenne, p99 sous 25 ms (P16, P17) ; 60 dans le Cyber-Rogue (R14) | 55 avec les biomes (U18) | idem, vélodrome et Grand Prix compris |
| Temps GPU par image sur la GTX 1060 (`low` / `medium` / `high`) | — | 8 / 13 / 16 ms (budgets relevés par le propriétaire le 8 novembre, décision de la PR #732 ; avant : 6 / 12 / 14) | idem | idem |
| Mémoire vidéo du décor | — | Niveaux de textures selon la mémoire (P20) | 1 Go au plus | idem |
| Gigue de la boucle physique | p99 du pas sous 5 ms (SRS §14.1) | Sous 5 ms pendant la génération du monde (W16) | idem | idem |
| Disque | Caches d'altitude et d'OSM | Cache du monde : 5 Go par défaut | Bibliothèque de textures : 5 Go | idem |
| Réseau | Hors ligne après compilation | R-NET-1 à R-NET-3 (§3) | Téléchargement de WorldCover par le compilateur ; météo locale au lancement (3.0-VNT-1) | Wi-Fi local du trainer (WF), jamais Internet pendant la séance |

## 9. Contradictions et points à trancher

Écarts relevés en rassemblant les documents. Les points C1 à C3 et C9 sont des corrections à appliquer dans les documents détaillés ; C4 à C8 et C10 demandent une décision du propriétaire ; C4 à C7 sont tranchées (26 octobre).

| # | Écart | Où | Proposition |
| --- | --- | --- | --- |
| C1 | Numéros de l'IPC : le cahier P1, l'index et les plans R, T et V disent encore « P = v1.2, R/T/V = v1.3 », alors que la 1.2 est prise par Q1 et N13 | `docs/lots/LOT_P1_contrat_vent_decor.md`, `docs/2.0/README.md`, plans R, T, V | Appliquer 1.3 = P, 1.4 = R/T/V, 1.5 = W ; déjà fait pour R dans la PR #244, à faire pour P1, T et V |
| C2 | Le README de la 2.0 dit « rien de ceci n'est commencé » alors que des lots T, V et W sont en revue | `docs/2.0/README.md` | **Corrigé le 27 octobre** : le README de la 2.0 dit ce qui est fusionné (modules purs T et V, contrat T1, W0) |
| C3 | La SRS §4.2 donne « aucune action » au bouton Y, alors que N6 en a fait la pause (corrigé dans cette PR, §4.2 et §4.4 de la SRS ; même correction pour le défaut de 100 % du coefficient de difficulté au §5, passé à 50 % par Q1) | `docs/SRS_v1.1.md` | Fait |
| C4 | Règle « hors ligne » : la SRS §12 et la décision U-Q2 (« jamais la séance ») contre la météo locale de P1 et le téléchargement des cartes pendant la balade (W-Q4) | SRS §12, plan U §7, cahier P1, plan W §4 | **Décidé le 26 octobre :** R-NET-1 à R-NET-3 (§3), le core n'attend jamais le réseau, seuls les processus annexes téléchargent |
| C5 | Place de la série P : « après la 1.0 » dans l'index, sans numéro de version, alors que le README de la 2.0 la traite comme le premier contrat de la 2.0 | Index, `docs/2.0/README.md` | **Décidé le 26 octobre :** P1 à P6, P8 à P17 et P21 en mises à jour 1.x ; P7, P18 à P20 en 2.0 |
| C6 | Caméra : la SRS §8 dit « ni avatar ni vélo, caméra subjective » ; la série V ajoute un avatar visible (question V-Q11 ouverte) | SRS §8, plan V §2.3 | **Décidé le 26 octobre :** la spécification change, plusieurs vues de caméra (§7.2) ; V-Q11 se règle par 2.0-CAM-3 |
| C7 | Bouton A : libre en classique (T), branches du carrefour en monde ouvert (W-Q1), pause en Cyber-Rogue (proposé, R1). Sans conflit tant que ces modes ne se combinent pas ; à vérifier pour le Cyber-Rogue en monde ouvert, que rien n'exclut | Plans R, T, W | **Décidé le 26 octobre :** plan de boutons commun à tous les modes (§7.1) |
| C8 | Programmes : la SRS §3 annonce trois programmes ; le lot W1 en ajoute un quatrième (`openride-worldgen`) | SRS §3, PR #282 | Accepter, noté au §3 |
| C9 | L'état « Livré » de Q1 et Q3 n'est pas reporté dans l'index des lots, alors que leur code est sur `main` (révision 1.2 de l'IPC, clé `trace_ftms`) | `docs/lots/00_INDEX.md` | À corriger par la série Q (tenue par une autre IA) |
| C10 | Taille de la trame `state` : le contrat promettait 1 400 octets, alors qu'une trame réaliste en faisait déjà environ 1 520 | `docs/contracts/ipc_v1.md`, audit IPC (PR #288) | **Réglé :** limite de `state` portée à 4 096 octets dans la révision 1.3 (P1, décision D1 de l'audit IPC) ; arrondi des flottants dans la PR #288 |
| C11 | Premier jalon de la série U : la décision U-Q5 y met le littoral, mais l'ordre conseillé du plan §8 renvoyait la côte et la mer (U3, U9) après le jalon | `docs/3.0/PLAN_SERIE_U.md` §8 | La décision du propriétaire l'emporte : U3 et U9 entrent dans le premier jalon (corrigé dans le plan et validé par le propriétaire (U-Q13) le 27 octobre) |
| C12 | Audit de cohérence du 27 octobre ([AUDIT_COHERENCE_2026-10-27.md](AUDIT_COHERENCE_2026-10-27.md)) : ajouts « 1.2 » faits après la 1.3, exception de Z dans les menus, boutons ERG sans lot, demi-tour et bots sans série | Rapport §2 | **Décidé le 27 octobre :** révisions dans l'ordre des fusions (§6.1) ; plan de boutons sans exception, menus compris (§7.1) ; lot O17 ; lots N17 et N18 ; « Parcours » dans N15 ; issues V1, V5 à V11 et T1. un seul contrat 1.4 (lot T1, qui remplace R1 et V1) ; lot V12 des quatre vues de caméra, V6 sans caméra, tri de S1 selon la caméra active ; clavier touche pour touche (§7.1, lot O17). D7 et D8 sans objet (séries Q et X fusionnées) |
| C13 | Révisions IPC : deux PR ouvertes réservent la 1.9 (N17 #791, N18 #789) et la PR #769 du vélodrome ajoute à la 1.7, déjà fermée | §6.1 | Appliquer la règle « première révision libre à la fusion » : chaque PR renumérote au moment de sa fusion |
| C14 | Réglages du Grand Prix (4.0) envoyés au menu et mode `grandprix` annoncé alors que l'accueil n'a pas son entrée (GP9) | `settings.py`, `ipc_server.py` | Règle du §2.1 : rien d'un mode avant son entrée au menu ; fil « Masquer les réglages Grand Prix avant la 3.0 » (8 novembre) |
| C15 | Code de la 4.0 et de la 5.0 fusionné sur `main` avant la publication de la 3.0, alors que la feuille de route dit « une version à la fois » | Feuille de route, §5.4 et §5.5 | Accepté tant que ce code reste caché (C14) ; les notes de la 3.0 ne l'annoncent pas |

## 10. Tenue de ce document

- Chaque PR qui livre ou ajoute une exigence met à jour sa ligne ici (statut, lots) en même temps que l'index des lots.
- Un nouveau plan de série ajoute ses exigences au §5 avec le statut « Planifié ».
- Les tests de cohérence de la documentation (`core/tests/test_docs_coherence.py`) vérifient les liens et les chemins cités de ce document.

| Date | Changement |
| --- | --- |
| 26 octobre 2026 | Première version : SRS v1.1, série P, plans R, T, V, W et U rassemblés ; révisions IPC 1.0 à 1.5 ; contradictions C1 à C10 ; numérotation alignée sur l'audit IPC (PR #288) |
| 26 octobre 2026 | Décisions C4, C5 et C6 ; vues de caméra (§7.2) ; plan de boutons commun (§7.1), validé le même jour |
| 27 octobre 2026 | Série U : cahiers U0 à U22, lots de l'option « gravel » (U20 à U22), révision 1.6 provisoire de l'IPC, écart C11 |
| 27 octobre 2026 | Audit de cohérence (C12) : révisions 1.2 et 1.3 (§6.1), plan de boutons réécrit sans exception (§7.1), exigences 1.0-ERG-5, 1.x-UI-1 et 1.x-UI-2, C10 réglé |
| 27 octobre 2026 | Statuts remis à l'état de `main` après les fusions du jour (séries O, P, Q, T, V, W0, Y1, contrat 1.4) ; cahiers R, U, V et W sur `main` notés « Spécifié » ; C2 corrigé |
| 29 octobre 2026 | Révision 1.5 de l'IPC remise à l'état de `main` (W1, T12, T13, O18 livrés), ajouts du 29 octobre notés (#540, #552, `render.draft_gauge`, O19) ; 1.0-ERG-6 (O18) livré ; statuts « en revue » d'O12 et de la série W remplacés par l'état des PR, toutes fusionnées |
| 8 novembre 2026 | Complétée à la demande du propriétaire : versions 4.0 et 5.0 (§1, §2, §5.4, §5.5), modes de jeu (§2.1), autres ajouts de la 2.0 et de la 3.0, statuts remis à l'état de `main` 3fc651a1, révisions IPC 1.6 à 1.8 et révisions réservées (§6.1), réglages du menu, vent, jour, nuit et saisons (§6.3), boutons des nouveaux modes (§7.1), budgets GPU 8 / 13 / 16 ms (§8), écarts C13 à C15 |
| 8 novembre 2026 | Y maintenu en roulant : demi-tour sans arrêt (§7.1, ligne « Y long », clavier Maj+Y), révision 1.11 de l'IPC (§6.1), exigence 1.x-UI-1 complétée |
