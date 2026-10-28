# OpenRide 2.0 – Sprints, montées chronométrées et bonus (série T)

25 octobre 2026. Demande du propriétaire : ajouter au mode classique, comme dans Zwift, des zones de sprint, des montées chronométrées et des bonus (légèreté, aérodynamique, puissance), puis des bots à profil (grimpeur, sprinteur, puncheur, diesel) équilibrés sur la FTP du joueur. Ce plan les découpe en lots. **La série T commence après la 1.0.** Les cahiers des lots seront rédigés au démarrage de la série et ajoutés à `docs/lots/00_INDEX.md`.

## 1. En résumé

Presque tout tient dans le core, sans toucher au pilotage du trainer :

- **Segments :** un segment est un intervalle `[s_début, s_fin]` de la route. Il est détecté automatiquement sur le profil (montées) ou déclaré à la main (sprints), puis rangé dans une nouvelle couche facultative `segments` du `.world`.
- **Chronométrage :** le core chronomètre chaque passage à 50 Hz, avec l'heure de franchissement interpolée. Il compare au record personnel et publie l'écart en direct.
- **Bots à profil :** grimpeur, sprinteur, puncheur et diesel, équilibrés sur ta FTP, avec maillots vert et à pois (§3.4).
- **Bonus :** ils modifient pendant quelques secondes les paramètres de `core/src/openride_core/physics.py` (masse, CdA, puissance prise en compte) et n'agissent que sur la vitesse virtuelle, comme dans Zwift. Ils s'activent avec le bouton Z du Click, libre en mode classique (Y y met en pause depuis le lot N6).

Ce plan réutilise ce que la série R a déjà prévu : règles du jeu dans le core, boutons Y, Z et A dans le contrat, données d'équilibrage dans un fichier modifiable. Il s'articule aussi avec la série P (décor vivant), qui ajoute le vent physique (P2) et l'aspiration derrière les bots (P3).

## 2. Ce qui se réutilise

| Besoin | Existant | Où |
| --- | --- | --- |
| Position, pente, altitude le long de la route | Lecture du `.world` et interpolation | `core/src/openride_core/route.py` |
| Ajout d'une couche sans recompiler la route | `add-layer` du compilateur, versions par couche | `docs/contracts/world_format_v1.md` §2 et §10 |
| Masse, CdA, rendement, terme d'aspiration | `PhysicsParams`, `alpha_draft` | `core/src/openride_core/physics.py` |
| Bots et fantôme à chronométrer aussi | Lot N9 | `docs/lots/LOT_N9_bots_core.md` |
| Historique des séances | Lecture des séances passées | `core/src/openride_core/tools/history.py` |
| Bouton Z décodé | `KEYPAD_BITS` du boîtier droit | `core/src/openride_core/zwift_click.py` |
| Bandeaux et HUD | Modèle du HUD, bandeau | `engine/scripts/hud_view_model.gd`, `engine/scripts/banner.gd` |

## 3. Choix de conception proposés

### 3.1 Segments

- **Montées (détection automatique) :** au moins 500 m, une pente moyenne d'au moins 3 % et un gain d'au moins 30 m. Les montées voisines séparées par moins de 200 m de replat sont fusionnées. Une catégorie de 4 à HC est calculée à partir du produit longueur × pente.
- **Segments manuels :** sprints ou montées déclarés dans un petit fichier à côté du GPX (début et fin en km) ; ils s'ajoutent aux segments automatiques ou les remplacent.
- **Sprints :** déclarés à la main, ou proposés automatiquement sur un tronçon de 200 à 500 m entre −1 et +2 %, au plus un tous les 10 km.
- **Parcours de démonstration :** un sprint et une montée, pour tester sans trace réelle.
- **Boucles et aller-retour :** un segment se chronomètre à chaque passage ; sur un aller-retour, il ne compte que dans le sens où il a été défini.

### 3.2 Chronométrage et records

- L'heure d'entrée et de sortie est interpolée entre deux pas de 50 Hz : la précision est d'environ 0,02 s.
- Une pause pendant un segment l'annule ; une pause `trainer_lost` aussi.
- Chaque passage garde : temps, puissance moyenne, W/kg, vitesse moyenne, bonus utilisés. Les records « avec bonus » et « sans bonus » sont tenus séparément (décision T-Q1).
- Les records personnels par parcours et par segment sont dans `~/OpenRide/`, recalculables depuis le journal des séances.
- En direct : distance jusqu'au prochain segment, chrono, écart au record (« −3,2 s »), puis le résultat à l'arrivée.
- Classement local du passage : toi, tes records passés, les bots et le fantôme (N9).

### 3.3 Bonus

| Bonus | Effet proposé | Durée |
| --- | --- | --- |
| Légèreté | Masse totale × 0,90 | 15 s |
| Aérodynamique | CdA × 0,75 | 15 s |
| Puissance | Puissance prise en compte par la physique × 1,10 | 15 s |

- **Obtention :** un bonus au hasard à la fin de chaque segment, et sous une arche tous les 5 km. Un seul bonus en réserve ; un nouveau remplace l'ancien.
- **Activation :** bouton Z du Click, appui court (touche du clavier en secours). Pas d'activation automatique.
- **Boutons du mode classique :** ceux du plan commun, seule référence ([spécification générale](../SPECIFICATION_GENERALE.md) §7.1) : + et B changent de braquet (appui long : 10 braquets), Y met en pause, Z active le bonus, A change de vue de caméra (A long : vue par défaut).
- **Valeurs :** dans un fichier de données modifiable, comme la table d'équilibrage de la série R.
- **Résistance au trainer :** inchangée par les bonus, comme dans Zwift. Seule exception, voulue : le supplément de pente dû au vent et à l'aspiration (série P, `feel = "grade"`) se calcule avec le CdA courant, donc le bonus aéro l'allège aussi, sans deuxième calcul : P2 et P3 calculent ce supplément à chaque pas avec les `PhysicsParams` courants (CdA et masse).
- **Fichiers :** la puissance du FIT et du journal reste la puissance mesurée. La vitesse et la distance restent les valeurs virtuelles, comme aujourd'hui. Les bonus utilisés vont au journal.
- **ERG :** les segments sont chronométrés, les bonus sont désactivés (entraînement structuré).

### 3.4 Bots à profil (demande du 25 octobre)

Les bots de N9 roulent à puissance constante. En 2.0, chaque bot a un profil physiologique et une stratégie simple, pour qu'on puisse choisir comment le battre.

| Profil | Masse | Puissance tenable (CP) | Réserve W' | Comportement | Maillot visé |
| --- | --- | --- | --- | --- | --- |
| Grimpeur | Légère (≈ 60 kg) | Haute en W/kg | Faible | Accélère dans les montées, souffre sur le plat | À pois |
| Sprinteur | Lourde (≈ 80 kg) | Moyenne | Grosse, pic sur 10 s | Reste à l'abri, lance le sprint dans les 200 derniers mètres | Vert |
| Puncheur | Moyenne | Moyenne | Moyenne, fort sur 1 à 3 min | Relance dans les bosses courtes | — |
| Diesel | Moyenne | Un peu plus haute | Presque nulle | Régulier, ne répond pas aux attaques | — |

- **Profils retenus le 27 octobre (§6) :** Grimpeur, Rouleur, Sprinteur et Diesel ; le Rouleur (fort sur le plat) remplace le Puncheur du tableau ci-dessus (cahier T12).
- **Modèle :** même réserve W'bal que la série R (lot R2), un seul module pour le joueur et les bots.
- **Équilibrage :** niveau choisi au départ (90, 100 ou 110 % de la FTP du joueur, ou valeur libre dans les options). Avant le départ, le core simule le parcours et ajuste la CP de chaque bot pour qu'il finisse dans le même temps qu'un cycliste qui roule à ce niveau. Le profil change l'endroit où le bot est fort, pas son niveau global.
- **Stratégie :** règles simples tirées des segments (montée, sprint) et de la réserve restante ; pas d'intelligence artificielle.
- **Maillots :** le vert et le maillot à pois vont, pendant la séance, à qui a le plus de points sur les segments de sprint et de montée, bots compris.
- **HUD :** pour chaque bot, maillot, profil, FTP en W et en W/kg, écart en secondes, jauge de réserve W'.
- **Écart avec le bot devant et le bot derrière (demande du 25 octobre) :** un encart permanent donne les deux voisins immédiats, par exemple « ▲ Grimpeur +8,4 s » et « ▼ Diesel −3,1 s », même quand d'autres bots sont plus loin.
    - **Calcul en temps de passage, comme en course :** pour le bot devant, l'écart est le temps écoulé depuis son passage au point où tu te trouves ; pour le bot derrière, c'est le temps écoulé depuis ton propre passage au point où il se trouve. Le core garde pour cela les passages (`s`, `t`) de chaque coureur sur les dernières minutes.
    - **Pourquoi pas distance ÷ vitesse :** l'estimation du lot O7 (1.0) suffit pour un bot à puissance constante, mais elle saute dans les montées et quand la vitesse change vite ; le temps de passage reste stable et c'est ce qu'affichent les retransmissions.
    - **Cas limites :** au départ, avant que le bot devant ait un passage enregistré, l'écart retombe sur l'estimation distance ÷ vitesse ; en boucle, le voisin est cherché sur le tour en cours ; sans bot devant (ou derrière), la ligne disparaît.
    - Le calcul se fait dans le core, une fois par trame, et l'engine affiche la valeur reçue (règle « le core est le maître »).
- **Aspiration :** les bots abritent le joueur comme dans P3 ; l'aspiration entre bots reste hors périmètre.
- **Bonus :** les bots n'en prennent pas.

### 3.5 Contrat

Les ajouts suivent ceux de la série P, qui prend la version 1.3 du contrat IPC (lot P1 ; la 1.2 est prise par Q1, N13 et O4). La série T, comme la série R, passe donc en **v1.4**, par ajouts compatibles :

- **Format `.world` 1.x :** couche facultative `segments` (`segments.json` : identifiant, nom, type `sprint` ou `climb`, `s_start`, `s_end`, longueur, pente moyenne, gain, catégorie, source `auto` ou `manual`). L'engine la lit lui-même, comme les autres couches.
- **Trame `state` :** champ facultatif `segment` (segment en cours ou prochain, distance, chrono, écart au record) et champ `powerup` (bonus en réserve, bonus actif, temps restant). Chaque élément de `bots` gagne `profile`, `cp_w`, `mass_kg`, `wbal_pct`, `jersey` et `gap_s` (écart en temps de passage, positif si le bot est devant). La trame gagne `bot_ahead` et `bot_behind` (identifiants des deux voisins immédiats, ou `null`). Les 5 bots au plus de N9 tiennent toujours dans la limite de 4 096 octets de `state` (révision 1.3) avec ces champs, à vérifier par les tests de taille de `core/tests/test_contract_ipc.py`.
- **Message `segment_result` :** temps, record battu ou non, classement du passage.
- **Événements `input` Z et A :** ajoutés à la révision 1.3 avec tous les boutons du Click (spécification générale §6.1 et §7.1) ; T1 les utilise sans les redéfinir.

## 4. Risques

| # | Risque | Parade |
| --- | --- | --- |
| 1 | Profil bruité : faux départs de montée sur une trace GPS | Détection sur la pente lissée déjà utilisée par la route, seuils en constantes, vecteurs de test |
| 2 | Records faussés par les bonus | Records « avec bonus » et « sans bonus » séparés (décision T-Q1) |
| 3 | Bonus puissance perçu comme une triche dans l'historique (NP, TSS) | Bilan calculé sur la puissance mesurée, jamais sur la puissance bonifiée |
| 4 | Conflit de version du contrat avec les séries P et R | Ordre fixé : P1 en v1.3, puis R et T en v1.4 (la v1.2 est prise par Q1, N13 et O4) |
| 6 | Bots à profil trop forts ou trop faibles selon le parcours | Calibrage par simulation du parcours avant le départ, vérifié par une matrice de parcours types (plat, vallonné, col) |
| 5 | HUD chargé (vent, abri, ERG, segment, bonus) | Blocs segment et bonus dans le coin supérieur droit, hors de la colonne HUD de gauche ; le lot P16 laisse cette zone libre |

## 5. Lots de la série T

| Lot | Contenu | Dépend de | Type |
| --- | --- | --- | --- |
| T1 | Contrat IPC 1.4 commun aux séries R, T et V ([cahier](../lots/LOT_T1_contrat_1_4.md)) ; partie T : couche `segments` du `.world`, champs `segment`, `powerup` et `jerseys`, message `segment_result` | P1, PR #287 | Interne (décision) |
| T2 | Détection automatique des montées et des sprints (module pur, vecteurs de test) | — | Délégable |
| T3 | Compilateur : couche `segments` par `add-layer`, sprints déclarés à la main, segments du parcours de démonstration | T1, T2 | Délégable |
| T4 | Chronométrage dans le core : franchissements interpolés, pauses, boucles et aller-retour, journal | T1, T2 | Délégable |
| T5 | Records personnels et classement local (historique, bots, fantôme) | T4, N9 | Délégable |
| T6 | Bonus : types, obtention, activation par Z, effets sur `PhysicsParams`, fichier de valeurs, désactivés en ERG | T1 | Délégable |
| T7 | Branchement de la série T dans la séance du core ([cahier](../lots/LOT_T7_branchement_seance.md)) : segments, records, bonus et bouton Z, supplément vent et aspiration calculé avec le CdA courant, maillots, écarts, champs de la révision 1.4 (élargi le 27 octobre : le plan n'avait aucun lot de branchement, comme R8 pour la série R et V11 pour la série V) | T1 à T6, T14, T16, P2, P3 | Interne |
| T8 | Engine : lignes de départ et d'arrivée en 3D, arches de bonus, panneaux « Sprint » et « Montée » | T1 | Interne (rendu) |
| T9 | Engine : HUD segment (approche, chrono, écart au record, résultat) et HUD bonus (icône, compte à rebours), coin supérieur droit | T1, P16 | Interne |
| T10 | Menu : records par parcours, option bonus | T5, N6 | Interne |
| T11 | Recette sur ton PC et ton vélo : un sprint, une montée réelle, chaque bonus, une course contre 4 bots à profil | T3 à T10, T12 à T15, T17 | Propriétaire |
| T12 | Bots à profil : CP, W', masse, pic sur 10 s, stratégie par segment (grimpeur, sprinteur, puncheur, diesel) | N9, R2, T2 | Délégable |
| T13 | Équilibrage des bots : niveau 90, 100 ou 110 % de la FTP, calibrage par simulation du parcours | T12 | Délégable |
| T14 | Points et maillots de la séance (vert, à pois), bots compris | T4, T12 | Délégable |
| T15 | Engine : HUD des bots (maillot, profil, FTP en W et W/kg, écart, jauge W') et encart des deux voisins (devant, derrière) | O7, T9, T16 | Interne |
| T16 | Écarts en temps de passage : historique des passages, `gap_s`, `bot_ahead`, `bot_behind`, repli distance ÷ vitesse, boucles | T1, N9 | Délégable |
| T17 | Engine : jingles des événements du parcours, sommet d'une montée, fin de sprint, arche de bonus, fin de séance ([cahier](../lots/LOT_T17_jingles_evenements.md), demande du 27 octobre) | T8, T9 | Interne (son) |

Ordre conseillé : T1 après P1, puis T2, T4 et T6 en parallèle ; T3, T5, T7 et T12 ensuite, puis T13, T14 et T16 ; enfin l'engine (T8 à T10, T15) et la recette T11. Les numéros T ne se confondent pas avec les constats d'audit, et les lots R non plus (les constats « R3 » et « S2 » du lot M9 sont sans rapport).

## 6. Questions pour le propriétaire

- [x] **T-Q1 Records (oui, 25 octobre) :** séparer « avec bonus » et « sans bonus » ? (Recommandé : oui.)
- [x] **T-Q2 ERG (oui, 25 octobre) :** bonus désactivés en ERG, segments chronométrés quand même ? (Recommandé : oui.)
- [x] **T-Q3 Ressenti (oui, 25 octobre) :** les bonus ne changent pas la résistance du trainer, hors vent et aspiration ? (Recommandé : oui, comme Zwift.)
- [x] **T-Q4 Valeurs (25 octobre : un bonus tous les 5 km et à chaque segment, valeurs proposées gardées) :** légèreté −10 % de masse, aéro −25 % de CdA, puissance +10 %, 15 s chacun, un bonus par segment et tous les 5 km ? (Recommandé : oui, modifiable dans le fichier de données.)
- [x] **T-Q5 Maillots (oui, 25 octobre) :** maillots vert et à pois attribués pendant la séance aux points, bots compris, plutôt qu'au détenteur d'un record ? (Recommandé : oui.)
- [x] **T-Q6 Niveaux des bots (oui, avec réglage libre en option, 25 octobre) :** 90, 100 et 110 % de ta FTP suffisent-ils, ou faut-il un réglage libre ? (Recommandé : les trois niveaux, plus un réglage libre dans les options.)

### Décisions du 27 octobre (lots non encore rédigés)

Le propriétaire a validé le 27 octobre les propositions suivantes ; elles servent de base aux cahiers à venir.

- **T1, contrat 1.4 :** rédigé après P1 (1.3). `segments.json` est la liste rendue par `Segment.to_dict()` (`segments.py`, lot T2) ; `state` gagne les champs `segment`, `powerup` et `segment_result` ; les événements de boutons `Z_SHORT`, `Z_LONG`, `A_SHORT` et `A_LONG` existent déjà depuis la révision 1.3.
- **T3, segments manuels :** fichier `<parcours>.segments.toml` posé à côté du GPX (type, km de début, km de fin, nom). Le parcours de démonstration garde les segments détectés automatiquement, sans segment manuel.
- **T5, records :** fichier `~/OpenRide/records.json`, par parcours et par segment, avec les 10 meilleurs temps et leur date. Le fantôme compte au classement comme ton meilleur temps, pas comme un coureur de plus. Le journal gagne un événement `powerup` (type, début, durée), sans changement des champs existants.
- **T8, T9, T10 et T15 :** pas de maquette préalable ; le rendu, le HUD et le menu sont codés puis validés ensemble à la recette.
- **T12 et T13, profils de bots** (CP en W/kg, W′), ajustés par la difficulté : Grimpeur 4,0 et 15 kJ, Rouleur 3,6 et 20 kJ, Sprinteur 3,3 et 25 kJ avec un pic de 12 W/kg sur 10 s, Diesel 3,8 et 10 kJ. Ces lots attendent le modèle W′bal de R2.
- **T14, barème de points :** montées HC 20, 15, 10, 6, 4 ; 1re catégorie 10, 8, 6, 4, 2 ; 2e 5, 3, 2, 1 ; 3e 2, 1 ; 4e 1. Sprints 15, 10, 6, 4, 2. Maillot à pois pour les montées, maillot vert pour les sprints.
