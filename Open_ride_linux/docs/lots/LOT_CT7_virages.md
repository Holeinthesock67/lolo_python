# Lot CT7 – Virages : vitesse critique, freinage automatique et Apex

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CT : virages : vitesse critique, freinage automatique et Apex | Python | AS2, CT2 | Moyenne | Prêt (version 5.0) |

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`.

## 1. Objectif

Donner un sens aux virages sans pénaliser les épingles de montée : au-dessus de la vitesse critique, la vitesse est ramenée à cette vitesse (classique et Course tactique) ; dans la Course tactique seulement, couper l'effort en entrée puis relancer au point de corde donne une relance (Apex).

## 2. À lire

1. `docs/5.0/PLAN_SERIE_CT.md` (décisions du propriétaire du 29 octobre), `docs/SPECIFICATION_GENERALE.md` §6.1 et §7.1, `docs/contracts/ipc_v1.md`.
2. Code `route.py` (cap `heading_deg`), `physics.py`, `session.py` ; contrat `world_format_v1.md` (route).

## 3. Prérequis

AS2 (trajectoire visible) et CT2 livrés.

## 4. Travail demandé

- **Courbure** : rayon calculé par le core depuis le cap de la route sur une fenêtre de 10 m, lissé, mis en cache au chargement du parcours.
- **Vitesse critique** : `√(μ g R)`, μ = 0,8 sur bitume sec (0,5 sur gravier si la série U est là).
- **Au-dessus** (classique et Course tactique) : la vitesse virtuelle est ramenée à la vitesse critique (freinage automatique), sans autre pénalité. Pas d'effet en montée : à 10 ou 15 km/h on reste sous la vitesse critique d'une épingle (25 à 32 km/h pour 10 m de rayon).
- **Apex** (Course tactique) : fenêtre ouverte quand le virage approche à moins de 50 m et que la vitesse dépasse 80 % de la vitesse critique ; effort sous 20 % de la FTP pendant 2 s en entrée, puis hausse d'au moins `apex_jump_pct` de la FTP au point de corde : puissance prise en compte × 1,2 pendant 3 s. Une Apex toutes les 30 s au plus.
- **Dérive** : pleine puissance au-dessus de la vitesse critique : la vitesse est ramenée à 85 % de la vitesse critique au lieu de 100 %.
- Bots : mêmes règles, erreurs de CT3.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/tactical/virages.py`, `core/src/openride_core/curvature.py` (calcul de la courbure, partagé), tests correspondants.
- **Modifiés :** `route.py` (cache), `session.py`, ce cahier, `00_INDEX.md`.
- **Interdits :** l'engine.

## 6. Modifications de contrat autorisées

Aucune : les champs viennent du lot CT1. Dans le classique, aucun champ ajouté.

## 7. Critères d'acceptation

1. `pytest -q` passe ; courbure sous 50 ms pour un parcours de 100 km au chargement.
2. Épingle de 10 m de rayon : à 40 km/h la vitesse tombe à environ 32 km/h ; à 12 km/h (montée), aucun effet.
3. Apex réussie : relance de 3 s ; pédaler à fond au-dessus de la vitesse critique : 85 % de la vitesse critique.
4. Classique : seul le freinage automatique existe.

## 8. Hors périmètre

Trajectoire dessinée à l'écran (CT10).
