# Lot AS6 – Abri derrière les véhicules et aspiration au dépassement

Série AS, version 2.0. Demande du propriétaire du 29 octobre 2026 (« abri derrière véhicules ou groupes à intégrer ») ; décision du même jour : **abri derrière un véhicule lent activé par défaut, désactivable dans le menu**.

## 1. Objectif

Les véhicules du décor (P13, P25) n'ont aucun effet sur la physique : ils sont tirés par l'engine seul (`traffic_model.gd`), et le core ne les connaît pas. Ce lot rend la circulation physique :

- un véhicule lent devant (tracteur, utilitaire en côte) abrite le cycliste qui le suit ;
- un véhicule qui double donne un bref coup d'aspiration.

Comme la physique ne doit jamais dépendre de l'affichage (préréglage de qualité, budget de véhicules), **le core devient l'autorité de la circulation proche du cycliste** et l'envoie à l'engine.

## 2. À lire

`docs/lots/LOT_P13_vehicules.md`, `LOT_P25_vehicules_au_sol.md`, `LOT_P3_aspiration_bots.md`, `LOT_AS2_zone_laterale_placement.md` ; code `engine/scripts/traffic_model.gd` (tirage par cases, sortes `KINDS`, dépassements), `living_decor.gd`, `core/src/openride_core/draft.py`, `session.py`.

## 3. Prérequis

AS2 livré (position latérale, voie de droite). Contrat de la 2.0 ouvert.

## 4. Travail demandé

- **Circulation dans le core.** Nouveau module pur `traffic.py`, portage de `traffic_model.gd` : même découpage en cases, mêmes sortes et parts, même graine de séance, mêmes règles de dépassement et de croisement. Le budget de véhicules ne dépend plus du préréglage pour les véhicules à moins de 150 m du cycliste. Le préréglage ne règle plus que les véhicules lointains, purement décoratifs, que l'engine garde.
- **Nouveau cas : véhicule lent devant.** Les tracteurs (et les utilitaires dans une montée de plus de 6 %) peuvent rouler dans le même sens que le cycliste, sur la voie de droite, plus lentement que lui. Le cycliste les rattrape : il peut rester derrière ou doubler (placement d'AS2).
- **Abri derrière un véhicule.** Même forme que la courbe de P3, mais avec une portée et une valeur propres à chaque sorte : par exemple voiture 0,45 à 3 m et portée 20 m, camion et autocar 0,60 et portée 30 m, tracteur 0,50 et portée 20 m, moto 0,15 et portée 8 m. Ces valeurs sont des points de départ à recaler sur les mesures publiées (Blocken et coll. 2016, véhicules d'accompagnement), avec les sources en tête du module. Le facteur latéral d'AS2 utilise la demi-largeur du véhicule. Plafond 0,60.
- **Réglage.** `[ride] vehicle_draft = true` par défaut, « Abri derrière les véhicules » dans Séance. Coupé : aucun abri derrière un véhicule lent.
- **Aspiration au dépassement.** Toujours active, même réglage coupé. Un véhicule qui double à moins de 2,5 m sur le côté donne une baisse de la résistance qui monte et retombe en 1 à 2 s : jusqu'à 0,15 pour une voiture, 0,30 pour un camion ou un autocar. Le pic se produit quand l'arrière du véhicule passe à la hauteur du cycliste.
- **Contrat.** Liste `vehicles` dans `state` : au plus 4 véhicules à moins de 150 m, `{id, kind, color, s, dir, v, lane_m}`. Elle est envoyée à 10 Hz pour tenir dans la limite de 4 096 octets de la trame, puis extrapolée par l'engine comme les bots. L'engine affiche ces véhicules au lieu de les tirer lui-même près du cycliste.
- **Abri et jauge.** `draft_bot` peut désigner un véhicule (`veh:<id>`). La jauge d'abri se pose alors au-dessus du véhicule.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/traffic.py`, `core/tests/test_traffic.py`.
- **Modifiés :** `draft.py`, `session.py`, `config.py`, `settings.py` et leurs tests ; `engine/scripts/traffic_model.gd` (véhicules lointains seulement), le rendu des véhicules, `main.gd`, `draft_gauge.gd` (ancrage sur un véhicule), `settings_view_model.gd`, `engine/tests/fake_core.py`, `visual_check.py` ; `docs/contracts/ipc_v1.md` et schéma `state` ; `docs/SRS_v1.1.md` (§5) ; `docs/GUIDE_UTILISATION.md`.

## 6. Modifications de contrat autorisées

Liste facultative `vehicles` dans `state` ; `draft_bot` peut valoir `veh:<id>` ; réglage `ride.vehicle_draft`. Révision de la 2.0.

## 7. Critères d'acceptation

1. `pytest` et tests de l'engine sans écran passent ; `visual_check.py` et banc sim en low, medium **et** high : mêmes véhicules proches dans les trois qualités (même liste `vehicles`).
2. `traffic.py` et l'ancien `traffic_model.gd` : mêmes véhicules (sorte, case, sens) sur 20 km de parcours de démonstration avec la même graine.
3. Tracteur à 25 km/h, cycliste à 3 m derrière, placement activé : abri entre 0,35 et 0,50 ; réglage coupé : 0.
4. Camion qui double à 1,8 m : pic de baisse de résistance entre 0,2 et 0,3, retour à 0 en moins de 2 s ; aucun effet à plus de 2,5 m.
5. Trame `state` avec 4 véhicules et 5 bots : sous 4 096 octets.
6. Coût du core : moins de 0,2 ms par pas avec 4 véhicules.
7. Captures en low, medium et high : tracteur devant, jauge au-dessus.

**Sur le vélo (le propriétaire) :** suivre un tracteur en montée, puis le doubler ; se faire doubler par un camion.

## 8. Hors périmètre

Véhicules qui réagissent au cycliste (klaxon, freinage), règles de sécurité routière.

## 9. Livraison (31 octobre 2026, PR empilée sur AS2)

- **Core.** `traffic.py` : portage de `traffic_model.gd` (cases de 250 m, mêmes sortes et parts, même tirage `hash3`, graine 0 comme l'engine, villages de la couche `poi` par tronçons de 1 km, limite de neige du thème), budget fixe de 8 véhicules (celui du préréglage high) quel que soit le préréglage. Liste `vehicles` : les 4 plus proches à moins de 150 m, une trame sur trois. Pas de circulation sans décor vivant (`[render] living`), puisque l'engine n'en affiche pas.
- **Véhicule lent devant.** Tracteur, ou utilitaire dans une montée de plus de 6 % (18 à 26 km/h), tiré dans le même sens et plus lent que le cycliste : posé 150 à 300 m devant, voie de droite. Il garde sa ligne face aux coureurs qui le doublent (ce sont eux qui s'écartent) et ne double jamais un coureur. Une fois doublé, il suit les règles des autres véhicules, sans jamais s'engager à doubler plus vite qu'il ne roule.
- **Placement (AS2).** `draft.Lane` gagne `half_width` et `length` (ceux d'un vélo par défaut, rien ne change entre vélos) : un véhicule du même sens est un coureur que l'on suit dans sa ligne, que l'on double à 1 m de sa carrosserie et que l'on longe comme un vélo ; on commence à le doubler assez tôt pour avoir fini de se décaler (`SIDE_EXTRA_MARGIN`). Les bots aussi l'évitent. Les véhicules évitent le cycliste à sa vraie place (`lane_m`).
- **Abri et aspiration.** Courbe et constantes en tête de `traffic.py` plutôt que dans `draft.py`, pour ne pas toucher le fichier qu'AS3 et AS5 modifient en même temps ; `draft.py` ne gagne que les deux champs de `Lane`. Le plus fort de l'abri des bots et de celui des véhicules s'applique ; l'aspiration s'ajoute sans lissage, total plafonné à 0,60 (`draft` de la trame compris, jauge et pastille à 100 % au-delà de 0,45).
- **Engine.** `traffic_model.gd` : `sync_core` reprend la liste `vehicles` une fois par trame (`seq`), remplace ses véhicules de même `id`, retire ceux à moins de 140 m absents de la liste, extrapole ceux du core entre deux listes ; un véhicule qui sort de la liste reste au décor. Le budget du préréglage ne compte plus que le décor lointain. Les véhicules lents ne viennent que du core : les cyclistes du décor de l'engine ne savent pas les doubler (AS7). Jauge d'abri au-dessus d'un véhicule (`living_decor.vehicle_anchor`, juste au-dessus du toit).
- **Vecteurs partagés.** `python -m openride_core.tools.traffic_vectors` écrit `engine/tests/data/traffic_slots_vectors.json` (parcours d'essai de 20 km, six graines, trois villages, une rampe à 10 %, un col enneigé) ; `test_traffic.py` et `test_traffic_model.gd` y trouvent les mêmes 47 véhicules (case, sorte, couleur, sens, vitesse).
- **Hors de ce lot.** Les bots ne s'abritent pas derrière les véhicules ; les cyclistes du décor ne sont pas encore des obstacles pour la circulation du core (AS7).

### Mesures du 31 octobre (cloud)

| Critère | Valeur |
| --- | --- |
| 2 : mêmes véhicules que l'engine sur 20 km | 47 sur 47, six graines (Godot 4.7.2 sans écran) |
| 3 : tracteur à 25 km/h, 3 m derrière, placement activé | abri 0,45 dans sa ligne (0,45 aussi à 1,2 m de l'axe, derrière la carrosserie) ; réglage coupé : 0 |
| 4 : camion qui double à 1,8 m | pic 0,24 quand l'arrière passe le cycliste, retour sous 0,005 en moins d'une seconde ; rien à 2,6 m |
| 5 : trame la plus lourde, 4 véhicules et 5 bots | 2 841 octets avec `devices`, 2 734 sans (limite 4 096) |
| 6 : coût du core, 4 véhicules et 5 bots | 0,011 ms par pas (borne 0,2 ms) |

Restent sur le PC (fil de fusion) : `visual_check.py` et banc sim en low, medium et high (scènes `abri_tracteur` et `abri_tracteur_parti`), captures à montrer au propriétaire avant la fusion ; sur le vélo : suivre un tracteur en montée, le doubler, se faire doubler par un camion.
