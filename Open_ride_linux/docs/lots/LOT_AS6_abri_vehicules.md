# Lot AS6 – Abri derrière les véhicules et aspiration au dépassement

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série AS : circulation calculée par le core, abri derrière un véhicule lent (activé par défaut, réglable), aspiration au dépassement | Python + GDScript | AS2 | Grande | Prêt (version 2.0) |

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
