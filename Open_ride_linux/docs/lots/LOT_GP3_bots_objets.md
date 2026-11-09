# Lot GP3 – Bots : usage des objets, garde et esquive

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : bots qui prennent, gardent et lancent les objets, esquive selon le niveau et le chaos, sans élastique physique | Python | GP1 | Moyenne | Livré le 8 novembre (PR #776, version 4.0) |

Série GP (mode « Grand Prix des objets », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_GP.md`.

## 1. Objectif

Donner aux bots les règles du §6 du plan : quand lancer chaque objet, quand le garder comme bouclier, quand changer de voie pour esquiver.

## 2. À lire

`docs/4.0/PLAN_SERIE_GP.md` §6 ; `core/src/openride_core/bots.py` (`ProfileBot`) ; `core/src/openride_core/grandprix/` (GP1).

## 3. Travail demandé

- Règles d'usage par objet, délai tiré entre 0,5 et 3 s (graine de la séance).
- Garde du bidon ou de la musette en tête tant qu'aucune boîte n'approche.
- Esquive à moins de 40 m : 30, 50 ou 75 % selon le chaos, plus ou moins 10 points selon le niveau du bot.
- Aucun ralentissement d'un bot à cause de l'écart avec le joueur.

## 4. Critères d'acceptation

1. Tests de chaque règle d'usage (positifs et négatifs : pas de musette guidée sans cible, pas de vent contraire en tête).
2. Sur 200 courses simulées, taux d'esquive mesuré à ± 5 points de la consigne.
3. Test : la puissance d'un bot ne dépend jamais de la position du joueur.

## 5. Livraison (8 novembre 2026)

- Module pur `core/src/openride_core/grandprix/brain.py` (`BotBrain`), appelé par `GrandPrixMode.step` après les boîtes et avant le pas des objets. Les règles sont lues sur la fiche de l'objet (cible et forme), pas sur son nom : un objet ajouté à la table suit la règle de sa famille.
- Usage : objet pour soi (coup de fouet, super-forme, voiture d'équipe, furtif) et nuage d'orage (seulement avec un premier devant) tout de suite ; bidon avec un coureur à moins de 30 m derrière ; musette avec une cible sur sa voie à moins de 150 m ; musette guidée avec une cible à moins de sa portée de verrouillage (200 m) ; sonnette contre un projectile à moins de 30 m derrière qui arrive, ou le nuage qui vise le bot ; vent contraire avec au moins deux coureurs devant. Délai tiré entre 0,5 et 3 s à chaque objet reçu, avec un générateur propre aux bots dérivé de la graine de la séance (le tirage des boîtes ne change pas).
- Garde : le bot en tête garde bidon et musette (les boucliers de la parade) tant qu'aucune rangée de boîtes n'est à moins de 150 m.
- Esquive : une décision par objet sur sa voie à moins de 40 m devant (pas les siens), réussie avec 30, 50 ou 75 % selon le chaos, ± 10 points entre 50 et 150 % de la FTP (niveau du bot, `levels` du mode, donné par la séance) ; vers la voie voisine libre la plus proche. La séance suit la voie forcée de chaque bot comme celle du cycliste (placement AS2 au centre de la voie, puis automatique après 20 s sans objet en vue). Ligne de journal `gp` `dodge`.
- `GrandPrixMode(bots=...)` : coureurs menés par le cerveau (tous sauf le cycliste par défaut) ; les tests des règles d'objets du lot GP1 passent `bots=()`.
- Pas d'élastique : le cerveau n'appelle que `use` et `set_lane`.
- Tests : `core/tests/test_grandprix_bots.py` (chaque règle dans les deux sens ; taux d'esquive sur 200 courses par chaos et par niveau, à ± 5 points, et tout objet non esquivé touche ; puissance des bots identique, au bit près, avec un cycliste à 0 W ou à 40 W parti 200 m derrière le peloton, objets coupés). Les relais et attaques des bots (lot Y10) restent ceux du mode, hors de ce lot.
