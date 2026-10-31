# Lot AS3 – Vent de travers et bordure

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série AS : vent de travers, zone abritée décalée sous le vent, bordure limitée par la voie | Python | AS2, P2 | Moyenne | Prêt (version 2.0) |

Série AS, version 2.0 (décision du propriétaire du 29 octobre 2026).

## 1. Objectif

Par vent de travers, la zone abritée glisse sous le vent : on s'abrite en diagonale derrière le coureur, pas dans sa roue. Aujourd'hui, P3 retire simplement jusqu'à la moitié de l'abri à 45°. Avec la position latérale d'AS2, ce lot déplace la zone au lieu de la réduire. Le placement automatique cherche la diagonale. Dans un groupe, la largeur de la voie limite l'éventail : ceux qui n'y tiennent pas restent exposés. C'est la bordure.

## 2. À lire

`docs/lots/LOT_P2_vent_physique_core.md`, `LOT_P3_aspiration_bots.md`, `LOT_AS2_zone_laterale_placement.md` ; code `draft.py`, `wind.py`, `session.py`.

## 3. Prérequis

AS2 livré. Vent actif (`[wind] mode` autre que `off`).

## 4. Travail demandé

- **Zone décalée.** Le centre de la zone abritée se décale sous le vent de `gap × tan(lacet)`, où le lacet est l'angle du vent apparent (P2). Il est borné à 1,5 m. `lateral_factor` d'AS2 s'applique autour de ce centre.
- **Perte résiduelle.** La réduction de P3 (−50 % à 45°) devient −20 % à 45° pour un coureur bien placé en diagonale : une partie de l'abri reste perdue par le tourbillon du vent de travers.
- **Placement.** Le placement automatique vise le centre décalé, borné par la voie de droite (P32). Si la diagonale sortirait de la voie, le coureur reste au bord et reçoit l'abri que donne sa position réelle.
- **Éventail.** Derrière un groupe, chaque coureur vise la diagonale du coureur devant lui. L'éventail s'arrête au bord de la voie, et les suivants se mettent en file au bord, exposés.
- **Indicateur.** La jauge d'abri continue de suivre `draft_bot`. Le HUD n'ajoute rien.

## 5. Fichiers concernés

`core/src/openride_core/draft.py`, `session.py`, `core/tests/test_draft.py`, `docs/SRS_v1.1.md` (§5), `docs/SUIVI_AVANCEMENT.md`. Interdits : l'engine (le placement passe déjà par `lane_m`), le contrat.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest` passe en entier.
2. Vent nul ou de face : résultats identiques à AS2.
3. Vent de travers à 45° venant de gauche, coureur à 2 m derrière : centre de la zone décalé vers la droite d'environ 2 m, borné à 1,5 m. Coureur placé là : abri d'au moins 0,8 × l'abri sans vent.
4. Coureur resté dans la roue par vent de travers à 45° : abri au plus 0,4 × l'abri sans vent.
5. Groupe de 5 bots par vent de travers fort : au plus 2 à 3 coureurs dans l'éventail (selon la largeur de voie), les autres reçoivent moins de 0,15.

**Sur le vélo (le propriétaire) :** vent de travers « fort » derrière 3 bots : l'avatar se place en diagonale et l'abri revient en partie.

## 8. Hors périmètre

Bordure sur une route large à plusieurs voies, vent tournant au fil du parcours (déjà géré par P2 au niveau du vent).
