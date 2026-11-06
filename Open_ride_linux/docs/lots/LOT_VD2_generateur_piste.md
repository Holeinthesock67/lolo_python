# Lot VD2 – Générateur de pistes

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série VD : générateur de pistes dans le core (droites, clothoïdes, virages relevés), sans GPX ni compilateur | Python | VD1 | Moyenne | Prêt (version 4.0) |

Série VD (modèle « Vélodrome », demande du propriétaire du 5 novembre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_VD.md`. Plan validé par le propriétaire le 6 novembre (lot VD0).

## 1. Objectif

Écrire en module pur le générateur des pistes du §3, qui produit un `.world` en boucle avec `bank_deg`, sa couche `venue` et sans terrain.

## 2. À lire

§3 du plan ; `core/src/openride_core/demo_world.py` (parcours synthétiques écrits par le core) ; `core/src/openride_core/route.py`.

## 3. Travail demandé

- Module `velodrome.py` : table des pistes (§3.3), résolution des longueurs de droites et de clothoïdes pour tomber sur la longueur exacte à la ligne de mesure, point tous les 10 m (1 m conseillé dans les virages si le format le permet, sinon 10 m et Catmull-Rom), relèvement continu.
- Écriture atomique dans le dossier des parcours, date de création fixe (reproductible octet pour octet), fiche `stats` et `library` (nom, description, étiquette `velodrome`).
- Sous-commande `openride-core velodromes [--out DOSSIER]`, appelée aussi au premier lancement comme les parcours de démonstration.

## 4. Critères d'acceptation

1. Longueur à ± 0,05 m, bouclage exact (premier point = dernier), courbure et relèvement continus (sauts sous 0,5° par point).
2. Pente nulle partout (`grade_pct` = 0 à 1e-6 près).
3. Deux écritures successives identiques octet pour octet.
4. Tests positifs et négatifs (longueur impossible, relèvement hors de 0 à 50°).

## 5. Fichiers touchés

- `core/src/openride_core/velodrome.py` (nouveau), son test, `__main__.py` (sous-commande).

Tout lot qui change l'affichage est mesuré en `low`, `medium` et `high` (budgets GPU : 6, 12 et 14 ms) et ses captures sont validées par le propriétaire avant la fusion.
