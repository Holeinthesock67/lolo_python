# OpenRide Linux – Spécification générale, versions 1.0, 2.0 et 3.0

26 octobre 2026. Ce document rassemble en une seule spécification la SRS de la 1.0 et les plans des versions 2.0 et 3.0. Il ne remplace aucun document détaillé : il dit **ce que chaque version doit faire**, **où en est chaque exigence** et **quel document fait foi** pour le détail.

## 1. Comment lire ce document

**Documents qui font foi pour le détail**

| Sujet | Document |
| --- | --- |
| Exigences de la 1.0 (matériel, physique, ERG, compilateur, rendu, FIT, configuration) | [SRS_v1.1.md](SRS_v1.1.md) |
| Messages entre le core et l'engine | [contracts/ipc_v1.md](contracts/ipc_v1.md) et ses schémas dans `docs/contracts/ipc/` |
| Format des parcours `.world` et des thèmes | [contracts/world_format_v1.md](contracts/world_format_v1.md) et ses schémas dans `docs/contracts/world/` |
| Découpage en lots, état de chaque lot | [lots/00_INDEX.md](lots/00_INDEX.md) |
| Plans de la 2.0 | [2.0/README.md](2.0/README.md) : séries R, T, V et W ; série P dans l'index des lots |
| Plan de la 3.0 | [3.0/PLAN_SERIE_U.md](3.0/PLAN_SERIE_U.md) |

En cas de désaccord entre ce document et un document détaillé, le document détaillé fait foi et l'écart est une erreur à corriger ici. Les écarts déjà connus sont listés au §9.

**Versions**

- **1.0 :** séries de lots A à O et Q (dernière série avant la publication : O, recette O8 et étiquette `v1.0.0`).
- **1.x :** mises à jour après la 1.0, sans changement de version majeure : lots N17 et N18 (demi-tour et bots réglés au menu, décision D11 du 27 octobre) et série P (décor vivant, vent, aspiration) y est rangée, sauf le jour, la nuit, les saisons et les packs de textures (P7, P18, P19, P20), reportés à la 2.0 par décision du propriétaire du 25 octobre.
- **2.0 :** séries R (Cyber-Rogue), T (segments, bonus, bots à profil), V (progression) et W (monde ouvert), plus P7, P18, P19 et P20.
- **3.0 :** série U (biomes, textures régionales, saisons par biome) et option « gravel ».

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

**Toujours hors périmètre**, toutes versions : multijoueur, envoi vers Strava ou un autre service en ligne, compte en ligne, achats en argent réel (les pièces de la série V se gagnent en roulant), ANT+ direct (une ceinture ANT+ n'arrive que par le pont cardio du trainer, SRS §4.1).

**Changements de périmètre par rapport à la SRS v1.1 §1** (décisions du propriétaire) :

- les bots, « optionnels en fin de feuille de route », sont livrés dans le core dès la 1.0 (lot N9) ;
- l'avatar et le vélo 3D, hors périmètre de la v1, entrent en 2.0 (série V, lots V6 et V7) ;
- la « boutique » refusée en v1 devient en 2.0 un Garage local où l'on dépense des pièces gagnées en roulant (V3b), sans argent réel ni service en ligne.

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
| 1.0-MAT-3 | Zwift Click V2 (deux boîtiers), B lu comme « − », boîtier gauche bridé | §4.2 | K8, Q6 | Livré (K8 ; Q6, PR #193 ; essai du boîtier gauche sur le PC à faire) |
| 1.0-MAT-4 | Bluetooth simulé et mode mock : tout se développe sans le vélo | §12 | H3, M5, M6 | Livré |
| 1.0-PHY-1 | Physique à 50 Hz par bilan d'énergie, 250 W à plat ≈ 10,2 m/s | §5 | — | Livré |
| 1.0-PHY-2 | 24 braquets virtuels de 0,40 à 3,00, pente effective bornée | §4.3 | — | Livré |
| 1.0-PHY-3 | Coefficient de difficulté, 50 % par défaut, réglable en séance | §5, §11 | Q1 | Livré |
| 1.0-PHY-4 | Rampe de pente distincte à la montée et à la descente | §5 | Q4 | Livré (PR #194) |
| 1.0-ERG-1 | Lecteur `.zwo`, cibles lissées, biais au Click, saut de bloc, pause | §6 | F, L6 | Livré |
| 1.0-ERG-2 | Formats `.erg` et `.mrc` de GoldenCheetah | — | O9 | Livré |
| 1.0-ERG-3 | Test de FTP, plans sur plusieurs semaines, menu Entraînement | — | O10 à O12 | O10 et O11 livrés ; O12 : core livré (PR #395), écrans de l'engine en revue (PR #396) |
| 1.0-ERG-4 | Bandeau ERG à l'écran, histogramme, bip à T − 3 s | §6 | N7 | Livré |
| 1.0-ERG-5 | Boutons de l'ERG selon le plan commun (§7.1) : ± court biais ± 2 %, ± long biais ± 10 %, Z bloc suivant, Y pause | §4.4 | O17 | Livré, essai sur le PC à faire (décision D3 du 27 octobre, issue #367) |
| 1.0-CMP-1 | Compilateur GPX vers `.world` : route, terrain, OSM, caches | §7 | B1, B2, I3, I4 | Livré |
| 1.0-CMP-2 | Traces FIT et TCX, archives Garmin, compilation au lancement | §7 | M7, N11, O5 | Livré |
| 1.0-CMP-3 | Bibliothèque de parcours et pack de cols célèbres | — | O15, O16 | Livré (pack O16 à construire une première fois sur le PC) |
| 1.0-RND-1 | Route, terrain triplanaire, ciel, arbres, HUD avec profil | §8 | E1 à E3 | Livré (recette visuelle sur la GTX 1060 à faire, `docs/RECETTE_E3_E4.md`) |
| 1.0-RND-2 | Bâtiments, forêts, eau et sons du parcours | §8 | E4 | Livré |
| 1.0-RND-3 | Préréglages de qualité, au moins 30 images/s en `low` sur la GTX 1060 | §8, §12 | L4, O1, S1 | Livré (L4, O1 ; brouillard par préréglage Y1, PR #381) ; S1 spécifié |
| 1.0-RND-4 | Pentes lisibles à l'écran (caméra et relief exagéré) | — | Q2 | Livré (PR #191 ; facteur par défaut à choisir sur la GTX 1060) |
| 1.0-RND-5 | Thèmes et packs de thèmes | §10 | H7, I5, N10 | Livré |
| 1.0-UI-1 | Menus au Click : parcours, entraînements, appareils, bilan | §4.5 | N1 à N6, N13 | Livré |
| 1.0-UI-2 | Menu principal et sous-menu ERG ; l'entrée qui choisit le parcours s'appelle « Parcours » (« Monde ouvert » est réservé à la série W) et l'accueil n'affiche que les modes annoncés par le core (`hello_ack.config.modes`, révision 1.3) | — | N15, N16 | Livré (N15, « Parcours », décision D10 ; N16, PR #249 et #288) |
| 1.0-UI-3 | Réglages depuis le menu (FTP, masse, difficulté, braquet, qualité, thème, mode d'affichage) | §11 | O3, O4 | Livré ; mode d'affichage livré le 27 octobre, mesures sur le PC à faire (protocole J10) |
| 1.0-UI-4 | Courbes de la séance façon GoldenCheetah | — | O13, O14 | O13 livré ; O14 spécifié |
| 1.0-UI-5 | Bots à l'écran (facultatif pour la 1.0) | — | O7 | Spécifié |
| 1.0-REC-1 | Journal JSONL continu, FIT minimal, reprise après plantage | §9 | N8 | Livré |
| 1.0-REC-2 | Bilan (NP, IF, TSS), historique des séances | — | K7, L7 | Livré |
| 1.0-BOT-1 | Bots à puissance constante et fantôme d'une séance passée | §13 | N9 | Livré |
| 1.0-INS-1 | Lanceur unique, lancement sans terminal, raccourci de bureau | — | K6, L8, N14 | Livré |
| 1.0-INS-2 | Numéro de version unique, notes de version, guide d'utilisation | — | O2, O6 | O2 livré ; O6 spécifié |
| 1.0-INS-3 | Recette 1.0 sur le matériel et publication `v1.0.0` | — | O8 | Spécifié |

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
| 1.x-UI-1 | Demi-tour sur la route depuis l'écran de pause (« Faire demi-tour »), sans geste du Click | N17 | Spécifié (décision D11 du 27 octobre) |
| 1.x-UI-2 | Bots réglés depuis les menus : nombre, puissance de chacun, fantôme, dans les réglages et l'écran de pause | N18 | Spécifié (décision D11 du 27 octobre) |
| 1.x-DEC-4 | Intégration et recette : au moins 55 images/s en `low` sur la GTX 1060, p99 sous 25 ms, tout se coupe par préréglage | P16, P17 | Livré ; recettes sur la GTX 1060 à faire (`docs/RECETTE_P16.md`, `docs/RECETTE_P17.md`) |

### 5.2 Version 2.0

**Ambiance et rendu (fin de la série P)**

| Id | Exigence | Lots | Statut |
| --- | --- | --- | --- |
| 2.0-DEC-1 | Jour et nuit : heure, coucher de soleil, nuit étoilée | P7, P19 | Spécifié |
| 2.0-DEC-2 | Quatre saisons (feuillages, neige, vergers en fleurs), inversées dans l'hémisphère sud | P18, P19 | Spécifié |
| 2.0-DEC-3 | Packs de textures à plusieurs niveaux, choisis selon le préréglage et la mémoire vidéo | P20 | Spécifié ; méthode des images générées livrée (PR #231) |
| 2.0-VNT-1 | Vent activé par défaut d'après la météo locale, repli sans vent hors ligne (règle R-NET-3) | P1 (décision n° 1) | Spécifié |

**Mode Cyber-Rogue (série R)** — détail : [PLAN_SERIE_R.md](2.0/PLAN_SERIE_R.md) et [GDD_CYBER_ROGUE.md](2.0/GDD_CYBER_ROGUE.md)

| Id | Exigence | Lots | Statut |
| --- | --- | --- | --- |
| 2.0-ROG-1 | Mesure du délai du frein avant de caler les fenêtres de jeu | R0 | Spécifié (outil X5 livré, PR #245 ; essai sur le vélo à faire) |
| 2.0-ROG-2 | Frein par décalage centré : pente de l'ennemi + (vitesse − 6) × 1 point, bornée à −10 / +16 % | R5, R8 | Spécifié |
| 2.0-ROG-3 | W'bal (W' 20 kJ par défaut, réglable, estimé depuis l'historique) et postures de cadence | R2, R16 | Spécifié |
| 2.0-ROG-4 | Salles générées à graine, Firewall à X % de FTP, combat, run en couloirs avec deck, reliques et boss | R3 à R7 | Spécifié |
| 2.0-ROG-5 | Run composée à partir d'un objectif (VO2max, seuil, endurance) et d'une durée choisis au menu | R15 | Spécifié |
| 2.0-ROG-6 | Châssis permanents à bonus de jeu, vies achetées avec les pièces de la série V | R9 | Spécifié |
| 2.0-ROG-7 | Scène néon séparée de la scène classique, HUD diégétique, ennemis géométriques, menu ; direction artistique et catalogue graphique générés par le code | R10 à R13, R17 | Spécifié |
| 2.0-ROG-8 | Recette : run complète, 60 images/s, ressenti des boutons | R14 | Spécifié |

Les cahiers R0 à R17 sont sur `main` ; le contrat de la série est dans le lot T1 (contrat 1.4 commun aux séries R, T et V).

**Mode classique enrichi (série T)** — détail : [PLAN_SERIE_T.md](2.0/PLAN_SERIE_T.md)

| Id | Exigence | Lots | Statut |
| --- | --- | --- | --- |
| 2.0-SEG-1 | Montées détectées automatiquement (500 m, 3 %, 30 m de gain ; catégorie 4 à HC) et sprints déclarés ou proposés, couche `segments` du `.world` | T1 à T3 | Livré (T1, PR #392 ; T2, PR #247 ; T3, PR #394) ; branchement dans la séance par T7 |
| 2.0-SEG-2 | Chronométrage interpolé à 0,02 s près, pause Y qui annule, coupure subie qui suspend, boucles et aller-retour | T4 | Livré, module pur (T4, PR #251) |
| 2.0-SEG-3 | Records « avec » et « sans bonus » séparés, classement local avec bots et fantôme | T5, T10 | T5 livré, module pur (PR #326) ; T10 spécifié |
| 2.0-BON-1 | Bonus légèreté (masse × 0,90), aéro (CdA × 0,75), puissance (× 1,10), 15 s, activés par Z, désactivés en ERG, sans effet sur la résistance du trainer | T6, T7 | T6 livré, module pur (PR #262) ; T7 spécifié |
| 2.0-BOT-1 | Bots à profil (grimpeur, sprinteur, puncheur, diesel) avec CP, W' et masse, calibrés par simulation du parcours à 90, 100 ou 110 % de la FTP ou à un niveau libre | T12, T13 | Planifié |
| 2.0-BOT-2 | Maillots vert et à pois attribués pendant la séance aux points, bots compris | T14 | Livré, module pur (T14, PR #328) |
| 2.0-BOT-3 | Écart en temps de passage avec le bot devant et le bot derrière | T16 | Livré, module pur (T16, PR #275) |
| 2.0-HUD-1 | Lignes, arches et panneaux en 3D ; HUD segment, bonus et bots dans le coin supérieur droit | T8, T9, T15 | Spécifié |
| 2.0-SEG-4 | Recette : un sprint, une montée réelle, chaque bonus, une course contre 4 bots | T11 | Spécifié |

**Progression (série V)** — détail : [PLAN_SERIE_V.md](2.0/PLAN_SERIE_V.md)

| Id | Exigence | Lots | Statut |
| --- | --- | --- | --- |
| 2.0-PRG-1 | Une seule progression pour tous les modes, recalculée depuis le journal des séances du jeu (pas les traces importées) ; 50 niveaux | V2, V4 | Livré, pas encore branché sur la séance (V2, PR #273 ; V4, PR #276) |
| 2.0-PRG-2 | Pièces gagnées en roulant, dépensées au Garage et pour les vies du Cyber-Rogue | V3b | Livré (V3b, PR #281) |
| 2.0-PRG-3 | Équipement à effets bornés (−3 % de masse, −6 % de CdA au plus), compromis par terrain, temps gagné affiché | V3, V5 | V3 livré (PR #278) ; V5 spécifié |
| 2.0-PRG-4 | Avatar généré par le code, pédalage synchronisé sur la cadence, menu Garage | V6 à V8 | Spécifié |
| 2.0-PRG-5 | Fin de séance : expérience, pièces, niveau, déblocages | V9 | Spécifié |

Les cahiers V2 à V11 sont sur `main` et les questions V-Q1 à V-Q13 sont tranchées ; le contrat de la série est dans le lot T1.

**Monde ouvert (série W)** — détail : [PLAN_SERIE_W.md](2.0/PLAN_SERIE_W.md)

| Id | Exigence | Lots | Statut |
| --- | --- | --- | --- |
| 2.0-MON-1 | Départ choisi sur un globe ou par recherche de lieu, puis sur une carte régionale | W11 | Spécifié |
| 2.0-MON-2 | Monde généré en direct par `openride-worldgen` ; au moins 3 km de route engagée devant le cycliste ; choix au carrefour jusqu'à 30 m avant, sinon le navigateur choisit | W1, W4 à W9 | W0 livré (PR #279) ; W1 en revue (PR #282) ; W4 à W8 en revue (PR #303, #304, #309, #310, #313) ; W9 spécifié |
| 2.0-MON-3 | Cache local de 5 Go par défaut, éviction des moins récemment utilisés, régions épinglées ; rien n'est retéléchargé au retour au même endroit | W2 | En revue (PR #285) |
| 2.0-MON-4 | Cartes : tuiles vectorielles mondiales au fil de la balade et préchargées autour des lieux de départ habituels ; extrait régional facultatif ; Overpass jamais pendant la séance | W3, W13 | W3 et W13 en revue (PR #302, #318) |
| 2.0-MON-5 | Monde ouvert autorisé en ERG ; balade, destination ou boucle de X km ; balade enregistrable comme parcours | W6, W14 | W6 en revue (PR #309) ; W14 spécifié |
| 2.0-MON-6 | Recette : une heure sans pause d'attente, 55 images/s, gigue de la physique sous 5 ms | W16 | Spécifié |

### 5.3 Version 3.0

Détail : [PLAN_SERIE_U.md](3.0/PLAN_SERIE_U.md). Toutes les questions U-Q1 à U-Q5, U-G1 et U-G2 sont tranchées (25 octobre). Cahiers des lots U0 à U22 rédigés le 27 octobre ([index des lots](lots/00_INDEX.md)) ; les questions U-Q6 à U-Q13 nées de cette rédaction (§11 du plan) sont toutes validées le 27 octobre.

| Id | Exigence | Lots | Statut |
| --- | --- | --- | --- |
| 3.0-BIO-1 | Seize biomes ; au plus quatre par tuile de terrain (trois en `low`) ; biome automatique d'après les données réelles et forçage au compilateur et au menu | U1, U2, U16, U19 | Spécifié |
| 3.0-BIO-2 | Occupation du sol ESA WorldCover téléchargée par le compilateur et mise en cache | U2 | Spécifié |
| 3.0-BIO-3 | Variantes régionales de roches, terres et bâtiments à grosse maille | U4, U14 | Spécifié |
| 3.0-BIO-4 | Mer, côtes et plages | U3, U9 | Spécifié |
| 3.0-BIO-5 | Saisons propres à chaque biome (saison sèche et saison des pluies, désert, polaire) | U13 | Spécifié |
| 3.0-BIO-6 | Végétation, sons, faune et atmosphère par biome | U7, U8, U10 à U12 | Spécifié |
| 3.0-BIO-7 | Thème 2.0 en pack de biomes, thèmes 1.x toujours lisibles ; textures CC0 en packs, bibliothèque de 5 Go | U1, U15 | Spécifié |
| 3.0-BIO-8 | Budget : 1 Go de mémoire vidéo au plus pour le décor, 55 images/s en `low` ; premier jalon : prairie, forêt tempérée, vignobles et cultures, haute montagne, méditerranéen, littoral | U6, U17, U18, U19 | Spécifié |
| 3.0-GRV-1 | Option « gravel » coupée par défaut : chemins de terre ouverts au monde ouvert ; résistance au roulement 2 à 3 fois celle du bitume, en supplément de pente sous le même plafond que le vent ; en ERG, vitesse seulement ; surface réelle d'OSM (« Chemins réels ») ou imposée à tout le parcours (« Gravier », « Terre », « Chemin compact ») pour rouler en gravel sur une trace revêtue (décision U-Q8 du 27 octobre) ; ruban de terre ou de gravier | U1, U16, U20, U21, U22 | Spécifié |

## 6. Contrats

### 6.1 Révisions du contrat IPC

Le champ `v` reste 1 : tous les ajouts sont compatibles. Chaque révision est notée dans le journal des changements de [ipc_v1.md](contracts/ipc_v1.md).

| Révision | Contenu | Lots | Version | Statut |
| --- | --- | --- | --- | --- |
| 1.0 | État à 30 Hz, commandes, heartbeat, pannes | C, D | 1.0 | Livré |
| 1.1 | Listes des parcours et entraînements, `devices`, bilan enrichi, reprise après plantage | N1 | 1.0 | Livré |
| 1.2 | `set_difficulty`, `difficulty_pct` ; appairage depuis le menu (`scan_devices`, `pair_devices`…). Fermée : plus aucun ajout | Q1, N13 | 1.0 | Livré |
| 1.3 | Révision de la sortie de la 1.0 : champs `wind` et `draft` de `state`, `state` à 4 096 octets, `rev` et `modes` (P1, livrés) ; réglages (`list_settings`, `set_setting`, message `settings`), précisions de X25, `bad_args`, imports d'entraînements (`list_imports`, `create_workout`, `import_workout`), `PLUS_UNCLEAR` et `MINUS_UNCLEAR` ; événements de tous les boutons du Click (`A_SHORT`, `A_LONG`, `Z_SHORT`, `Z_LONG`, `Y_SHORT`, `LEFT_SHORT`, `RIGHT_SHORT`, `UP_SHORT`, `DOWN_SHORT`, plan de boutons du §7.1) ; demi-tour et bots réglés au menu s'ils fusionnent avant l'étiquette `v1.0.0`. Se ferme à l'étiquette `v1.0.0` | P1, O3, O4, X25, #288, N16, #287 | 1.0 (P1 sert la 1.x) | P1, X25, O3, O4, l'audit IPC (#288), N16 (#249), événements des boutons (#287) et contrat d'O12 (#395) livrés |
| 1.4 | (Les événements des boutons sont déjà en 1.3.) Mode `ROGUE` et valeur `"rogue"` de `modes` ; champs `segment`, `powerup`, `jerseys`, `bot_ahead`, `bot_behind` et objet `rogue` de `state` ; champs des bots à profil ; `summary.segments` et `summary.rogue` ; messages `segment_result`, `room`, `loot`, `garage`, `progression`, `xp_result` ; commandes `start_run`, `rogue_resync`, `list_garage`, `equip`, `buy`, `set_avatar` ; `hello_ack.config.rogue` et `progression` | T1 | 2.0 | Contrat validé par le propriétaire et fusionné le 27 octobre (lot T1, PR #392, un seul lot de contrat, décision D4) ; le core annonce encore `rev` « 1.3 » jusqu'au branchement (R8, T7, V11) |
| 1.5 | Monde ouvert : `start_open_world`, `choose_branch`, champ `open_world`, `world_status` et messages de la carte ; limite unique de 4 096 octets pour tout message hors messages en parties (décision du propriétaire du 27 octobre) | W1 | 2.0 | En revue (PR #282) |
| 1.6 | Série U : clés facultatives `biome` et `gravel` de `hello_ack.config`, aucun nouveau message (le menu passe par `set_setting`) | U1, U16 | 3.0 | Spécifié (cahier U1) ; numéro provisoire : la série U prend la première révision libre à sa fusion (§6.1) |

Règles de numérotation (décision du propriétaire du 27 octobre, « au plus propre », audit de cohérence) : les révisions se suivent dans l'ordre des fusions, si bien qu'un programme qui annonce `rev` « 1.3 » connaît tout ce qui est noté 1.2 et 1.3. Une révision fermée ne reçoit plus d'ajout : la 1.2 est fermée depuis la fusion de la 1.3 ; la 1.3 reste ouverte jusqu'à l'étiquette `v1.0.0` et reçoit tous les ajouts de la 1.0 qui fusionnent avant elle ; la 1.4 est celle des séries R, T et V, en un seul lot de contrat, T1 (décisions D2 de l'audit IPC et D4 de l'audit de cohérence) ; les événements de tous les boutons sont déjà dans la 1.3, une seule fois ; W1 prend la 1.5. Un ajout fait après la 1.0 hors de ces séries prend la première révision libre à sa fusion. Numérotation 1.4 et 1.5 confirmée par le propriétaire le 26 octobre (décision D2 de l'audit IPC). L'ancienne proposition N13 = 1.3, P1 = 1.4, R/T = 1.5 est périmée.

### 6.2 Format `.world` et thèmes

| Ajout | Lot | Version | Statut |
| --- | --- | --- | --- |
| Couches route, terrain, bâtiments, végétation, points d'intérêt, eau | B1, B2, I3, I4 | 1.0 | Livré |
| Points d'intérêt `wind_turbine` et `flag` ; thème 1.2 (nuages, météo, ambiance, faune, saison, heure) | P1 | 1.x | Spécifié |
| Niveaux de textures dans le thème | P20 | 2.0 | Spécifié |
| Couche `segments` (format 1.3, `segments.json`) | T1, T3 | 2.0 | Format écrit (T1) ; écrite par le compilateur et le parcours de démonstration (T3) |
| Monde vivant : `live`, origine sur grille UTM, route par parties, couches par carré, `junctions.json` | W1 | 2.0 | En revue (PR #282) |
| Couche `biome`, variante régionale, eau `sea`, couche `coast` ; colonne `surface` de la route et classe `g` du monde ouvert ; thème 2.0 en pack de biomes | U1 | 3.0 | Spécifié (cahier U1 ; mineur libre suivant celui de W1) |

### 6.3 Configuration

Les sections de `~/OpenRide/config.toml` de la 1.0 sont dans la SRS §11. Ajouts prévus : `[wind]` (P1), `[render] living` et `texture_level` (P4, P20), `[open_world]` avec `cache_dir` et `cache_max_gb` (W2), `[render] camera` (V12, livré) ; `[render] biome` et `theme_library_gb`, section `[gravel]` (U1, U15) ; sections `[rogue]` (`w_prime_j`, `cp_w`, rampe de pente en run) et `[avatar]` (seuils de la danseuse), fixées par le contrat 1.4 (T1, SRS §11).

## 7. Boutons du Click et vues de caméra

### 7.1 Une même famille d'action par bouton, partout

Demande du propriétaire du 26 octobre (point C7) : chaque bouton garde le même **type** d'action d'un mode à l'autre, pour qu'on n'ait jamais à se demander « ici, Y fait quoi ? ». Plan validé le 26 octobre, puis réécrit le 27 octobre sans aucune exception, menus compris (principe du propriétaire : « on évite les exceptions »). **Ce tableau est la seule référence** : la SRS, les plans et les cahiers y renvoient au lieu de le recopier.

Boîtier droit : +, A, B, Y, Z ; boîtier gauche : −, flèches (bridé sans déblocage Zwift, SRS §4.2). B double toujours « − », et rien d'indispensable n'est mis sur le seul boîtier gauche. Appui court : moins de 0,5 s ; appui long : 0,9 s ou plus ; entre les deux, rien ne se passe et l'écran le dit (`PLUS_UNCLEAR`, `MINUS_UNCLEAR`).

| Bouton | Famille | Menus | Classique SIM | ERG | Cyber-Rogue | Monde ouvert |
| --- | --- | --- | --- | --- | --- | --- |
| + / B (ou −), court | Déplacer ou doser, petit pas | Élément suivant, précédent | Braquet ± 1 | Biais ± 2 % | Vitesse du frein ± 1 | Comme le mode roulé (SIM ou ERG) |
| + / B (ou −), long | Déplacer ou doser, grand pas | Cinq éléments plus loin, plus haut (bornés à la liste) | Braquet ± 10 | Biais ± 10 % | Vitesse du frein ± 3 | Comme le mode roulé |
| Y court | Interrompre et revenir | Écran précédent ; sur l'écran de pause, reprendre | Pause et reprise | Pause et reprise | Pause et reprise | Pause et reprise |
| Z court | Action du mode | Aucune (un menu n'est pas un mode) | Bonus (T) | Bloc suivant | Attaque | Bonus (T) |
| Z long | Action spéciale du mode | Aucune | Aucune | Aucune | Carte ou relique active (T1) | Aucune |
| A court | Choisir : option suivante du choix affiché | Élément suivant | Vue de caméra suivante | Vue de caméra suivante | Couloir ou carte suivant | Branche suivante au carrefour, sinon vue suivante |
| A long | Valider le choix affiché | Valider l'élément | Revenir à la vue par défaut | Revenir à la vue par défaut | Valider le couloir ou la carte | Valider la branche, sinon revenir à la vue par défaut |
| Flèches gauche, droite (boîtier gauche) | Choisir, raccourci | Élément précédent, suivant | Aucune | Aucune | Couloir ou carte précédent, suivant | Branche à gauche, à droite |
| Flèches haut, bas (boîtier gauche) | Vue, raccourci | Aucune (pas de vue dans un menu) | Vue suivante, précédente | idem | idem | idem |

Règles communes, valables partout :

- **A agit sur le choix affiché.** Un menu, un carrefour, une liste de couloirs ou de cartes sont des choix : A court passe à l'option suivante, A long valide. Sans choix affiché (en roulant), le choix est celui de la vue de caméra.
- **Y revient en arrière** : pause en séance, écran précédent dans un menu, reprise depuis l'écran de pause.
- **Z n'a que l'action du mode** ; il ne fait rien dans un menu.
- **Le grand pas vaut dix petits pas en séance** et cinq éléments dans un menu.
- **Clavier (décision D6 du 27 octobre) :** il double le Click touche pour touche, avec les mêmes seuils d'appui (court sous 0,5 s, long à 0,9 s ou plus, zone floue entre les deux), en menu comme en séance ; une touche n'a jamais d'autre rôle que celui de son bouton. Pas de bouton pour la difficulté (décision Q1).

| Bouton du Click | Touche | L'appui long aussi par | Remarque |
| --- | --- | --- | --- |
| + | + (ou =, + du pavé numérique) | Page haut | — |
| − ou B | − (− du pavé numérique) | Page bas | B n'a pas de touche propre : il double « − » |
| A | A | Maj+A, Entrée | Entrée vaut donc « valider » partout |
| Y | Y | — | Échap vaut Y court |
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

Conséquence : avec ce plan, le Cyber-Rogue n'a plus à être exclu du monde ouvert (point C7 levé).

### 7.2 Vues de caméra

Demande du propriétaire du 26 octobre (point C6) : la caméra unique de la SRS §8 devient un choix de vues.

| Id | Exigence | Lots | Statut |
| --- | --- | --- | --- |
| 2.0-CAM-1 | Quatre vues : subjective (celle de la 1.0, avatar masqué), suivi proche derrière l'avatar, suivi éloigné en hauteur (bots, carrefours, peloton), latérale façon retransmission | V12 (après V6) | Spécifié |
| 2.0-CAM-2 | Changement de vue au Click (A court et flèches haut et bas ; A long revient à la vue par défaut, §7.1) et au clavier, transition douce de moins d'une demi-seconde ; la dernière vue est retenue dans `[render] camera` | V12 ; clavier O17 | Spécifié |
| 2.0-CAM-3 | Vue par défaut : subjective tant que l'avatar n'existe pas, suivi proche ensuite ; le Cyber-Rogue garde ses effets de champ de vision et de tremblement dans chaque vue | V6, R11 | Spécifié |
| 2.0-CAM-4 | Lisibilité des pentes (lot Q2 : caméra inclinée, relief exagéré) appliquée à toutes les vues | Q2 | Spécifié (Q2 livré en vue subjective, PR #191) |
| 2.0-CAM-5 | Budget : aucune vue ne fait passer sous 55 images/s en `low` ; les vues éloignées utilisent les mêmes préréglages de distance que la vue subjective ; le tri de ce qui est dessiné suit la caméra active | V12, S1, P16 | Spécifié |

## 8. Exigences non fonctionnelles par version

| Exigence | 1.0 | 1.x et 2.0 | 3.0 |
| --- | --- | --- | --- |
| Images par seconde en `low` sur la GTX 1060 | 30 au moins | 55 en moyenne, p99 sous 25 ms (P16, P17) ; 60 dans le Cyber-Rogue (R14) | 55 avec les biomes (U18) |
| Mémoire vidéo du décor | — | Niveaux de textures selon la mémoire (P20) | 1 Go au plus |
| Gigue de la boucle physique | p99 du pas sous 5 ms (SRS §14.1) | Sous 5 ms pendant la génération du monde (W16) | idem |
| Disque | Caches d'altitude et d'OSM | Cache du monde : 5 Go par défaut | Bibliothèque de textures : 5 Go |
| Réseau | Hors ligne après compilation | R-NET-1 à R-NET-3 (§3) | Téléchargement de WorldCover par le compilateur |

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
