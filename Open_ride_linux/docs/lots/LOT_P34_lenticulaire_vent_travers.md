# Lot P34 – Roue lenticulaire et vent de travers

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série P : pénalité de la roue lenticulaire par vent de travers (question V-Q13), à partir du vent de travers déjà calculé pour l'abri | Python | P2, AS3, V3 | Petite | Prêt (version 3.0) |

Question V-Q13 (plan V, validée le 27 octobre) : la lenticulaire est pénalisée par sa masse en montée seulement, et la pénalité au vent de travers « attend un lot de la série P ». Ce lot n'existait pas ; relevé le 8 novembre. Le vent de travers est déjà calculé pour la bordure (AS3, `draft.py`).

## 1. Objectif

Donner à la roue lenticulaire un vrai compromis : rapide par vent calme, moins efficace par fort vent de travers.

## 2. À lire

`docs/2.0/PLAN_SERIE_V.md` §5 (V-Q13) ; `core/src/openride_core/equipment.py` (effets bornés de V3) ; `core/src/openride_core/draft.py` (composante de travers, AS3) ; `core/src/openride_core/wind.py`.

## 3. Travail demandé

- Effet sur le CdA de la lenticulaire selon la composante de travers (gain réduit puis annulé au-delà d'un seuil), borné comme les autres effets de V3 (CdA −6 % au plus).
- « Temps gagné » affiché au Garage (V5) recalculé avec le vent du parcours.
- Aucun effet sur la puissance enregistrée (invariant A7).

## 4. Critères d'acceptation

1. Sans vent, résultats identiques à aujourd'hui (test).
2. Par vent de travers fort, la lenticulaire ne fait pas mieux que la roue à hauts profils (test).

## 5. Fichiers touchés

`core/src/openride_core/equipment.py`, `core/src/openride_core/data/progression.toml` (`wheels_disc`), tests.
