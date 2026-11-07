# Lot GP1 – Règles des objets dans le core

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : catalogue des objets, effets dans la table de TT2, objets sur la route, projectiles, contacts et tirage selon le retard | Python | TT2, AS2, T12, T13 | Grande | En PR (7 novembre, version 4.0 proposée), avant TT2 ; core seul, sans séance ni affichage |

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

## 5. Livraison (7 novembre)

Modules : `core/src/openride_core/route_objects.py` (générique) et le paquet `core/src/openride_core/grandprix/` (`effects.py`, `items.py`, `boxes.py`, `draw.py`, `mode.py`) ; tests : `core/tests/test_grandprix.py`. Rien n'est branché dans la séance (lot GP2) : le mode n'est ni annoncé ni lançable.

Lectures retenues là où le plan laissait un choix :

- **TT2 n'est pas encore écrit.** Les six effets (`kick`, `slip`, `speed_floor`, `cap`, `immune`, `wind`) et la marque `breakaway` sont des lignes de données (`EffectSpec` : effet, facteur, durée) dans `grandprix/effects.py`, chaque objet étant décrit par une cible (`self`, `ahead`, `leader`, `near`, `behind`) et une forme (`instant`, `duration`, `dropped`, `projectile`) : aucun objet n'a de branche de code à lui. TT2 déplacera ces lignes dans la table unique de `powerups.py` sans les réécrire ; `powerups.py` n'est pas touché ici.
- **Lignes doubles du tirage** (« Bidon, trois bidons ») : trois quarts pour l'objet simple, un quart pour l'objet triple ; les sommes par ligne sont celles du §4.2.
- **Chaos** : la force est l'écart à 1 d'un facteur (ou la valeur du vent) multipliée par 0,7, 1 ou 1,3 ; les durées ne changent pas ; la fréquence est l'écart des rangées divisé par le même nombre.
- **Voies** : trois voies sur la chaussée de droite de l'AS2 (0,3 à 2,6 m), limites à 1,07 et 1,83 m ; le cycliste sans placement (1,2 m) est au centre, un bot seul (2,1 m) à droite. Centres publiés pour le placement forcé de GP2 : 0,68, 1,45 et 2,22 m.
- **Nuage d'orage** : vole à la vitesse du lanceur plus 30 m/s vers le premier du moment, puis attend 1 s au-dessus de lui (`warn`) avant l'averse ; la sonnette du premier dans cette seconde le chasse.
- **Musette guidée** : verrouillée sur le premier coureur devant à moins de 200 m, sinon lancée tout droit ; portée 600 m, 40 s.
- **Furtif** : vol de l'objet et marque `breakaway` de 10 s ; l'abri retiré aux suiveurs et les bots aveugles viennent avec GP4 (après TT4).
- **Esquivés** (bilan) : coups arrêtés par l'invincibilité, la parade, les 2 s après un coup, la reprise après une pause, ou la sonnette qui chasse un nuage.
- **Trame `gp`** : `fx` regroupé par objet (`[["star", 5.2]]`, comme l'exemple du §8.1) ; `obj` donne l'objet dessiné (`musette`, jamais `musette_x3`) ; identifiants d'objets repris de 1 à 99 (32 objets au plus) ; rangées au mètre. Pire trame d'une course de 30 km : moins de 500 octets (test).
- **`loss_s`** de `gp_hit` : perte estimée en secondes, positive, calculée comme les chiffres du §3 (même physique, 60 s après le coup) à la vitesse d'équilibre et la pente du moment.
