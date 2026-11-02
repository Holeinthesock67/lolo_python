# Lot GP1 – Règles des objets dans le core

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : catalogue des objets, effets dans la table de TT2, objets sur la route, projectiles, contacts et tirage selon le retard | Python | TT2, AS2, T12, T13 | Grande | Prêt (version 4.0 proposée) |

Série GP (mode « Grand Prix des objets », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_GP.md`.

## 1. Objectif

Écrire en modules purs (aucune entrée-sortie dans la boucle) tout ce que le mode calcule : les treize objets, leurs effets sur la vitesse virtuelle, les objets posés et les projectiles, les contacts par voie, les boîtes de ravitaillement et le tirage selon le retard sur le premier.

## 2. À lire

`docs/4.0/PLAN_SERIE_GP.md` §2 à §5 et §7 ; `core/src/openride_core/powerups.py` réécrit par TT2 (modèle unique d'effets) ; `core/src/openride_core/draft.py` et `lane_m` d'AS2 ; `core/src/openride_core/physics.py` (`RiderPhysics`, `steady_speed`) ; `core/src/openride_core/wtf/mode.py` (forme d'un mode en module pur).

## 3. Travail demandé

- Effets ajoutés à la table de TT2, sans cas particulier : `kick` (v × facteur), `speed_floor` (v ≥ facteur × v_éq), `cap` (v ≤ facteur × v_éq), `slip` (v × facteur), `immune`, `wind` (vent virtuel), chacun avec une cible (soi, devant, premier, coureurs proches) et une forme (immédiat, durée, objet posé, projectile).
- Module générique `route_objects.py` : objets avec `s`, voie, durée de vie, vitesse ; contact par voie ; 32 objets au plus (les plus vieux bidons disparaissent).
- Paquet `grandprix/` : `items.py` (catalogue, fichier `~/OpenRide/grandprix.toml` borné objet par objet), `boxes.py` (rangées, roulette de 2 s, réserve unique), `draw.py` (poids du §4.2, objets inutiles exclus, objets désactivés retirés), `mode.py` (`GrandPrixMode` : `start`, `step`, `use(rider)`, `set_lane(rider, lane)`, `frame()`, `due_results(t)`, `summary()`, `take_journal()`).
- Règles communes : 2 s sans nouveau coup après un coup reçu ; parade automatique de la musette guidée par un bidon ou une musette en réserve ; un seul nuage d'orage en vol ; rien pendant une pause ni une coupure, ni pendant 3 s après la reprise.
- Chaos doux, normal, fou : forces et fréquences × 0,7, × 1, × 1,3.

## 4. Critères d'acceptation

1. Tests positifs et négatifs pour chaque objet du §3 du plan, dont les chiffres du tableau à ± 10 % (cycliste de 84 kg à 250 W, plat, 6 %, −4 %).
2. Tirage : 10 000 tirages par tranche de retard, fréquences à ± 2 points des poids ; aucun objet inutile ni désactivé.
3. Course simulée de 4 et de 11 bots : trame `gp` sous 500 octets, aucun objet au-delà de 32, même graine, même course.
4. Aucune fonction du module ne renvoie de pente : test qui le vérifie (la pente envoyée ne dépend pas des objets).
