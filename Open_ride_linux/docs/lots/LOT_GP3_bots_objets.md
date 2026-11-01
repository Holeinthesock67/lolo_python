# Lot GP3 – Bots : usage des objets, garde et esquive

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : bots qui prennent, gardent et lancent les objets, esquive selon le niveau et le chaos, sans élastique physique | Python | GP1 | Moyenne | Prêt (version 4.0 proposée) |

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
