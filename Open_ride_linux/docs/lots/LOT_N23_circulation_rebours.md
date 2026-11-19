# Lot N23 – Circulation et cyclistes du décor à rebours

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| 1.x série N : voitures, camions, tracteurs et cyclistes du décor après un demi-tour | Python, GDScript | N17 | Moyenne | **Livré le 15 novembre** (PR #890), **version 1.x** |

## 1. Objectif

Audit du décor dans les deux sens (8 novembre, points 11 et 12) : la circulation (`traffic.py`, `traffic_model.gd`)
et les cyclistes du décor (`road_cyclists.py`, `road_cyclists_model.gd`) ne tiraient de nouvelles cases que quand le
cycliste avançait vers les s croissants. Après un demi-tour (N17), ceux déjà là s'en allaient et la route restait
vide jusqu'à la fin de la séance.

## 2. Travail fait

Pas de seconde logique « à rebours » : les deux modèles restent écrits pour un cycliste qui avance, et roulent après
un demi-tour sur le parcours retourné (principe du projet : pas d'exception, un seul chemin).

- `core/.../route_mirror.py` et `engine/scripts/route_mirror.gd` (jumeaux) : parcours lu dans l'autre sens,
  abscisse u = L − s, même tracé, cap + 180°, pente et tangage opposés. Les cases tirées sont les mêmes au core et à
  l'engine, qui retournent le même parcours.
- `Traffic.set_direction` / `RoadCyclists.set_direction` (et leurs jumeaux de l'engine) : au demi-tour, chacun garde
  sa place (abscisse, sens et écart à l'axe convertis). Une voiture qui suivait le cycliste vient en face, celle qui
  l'avait croisé roule devant lui ; un groupe de cyclistes qui allait dans son sens vient en face, un groupe d'en
  face qui l'avait croisé roule devant lui (`ahead`), un groupe d'en face pas encore croisé, désormais dans son dos,
  quitte la route. Les bots, qui gardent le sens du parcours, sont vus en face.
- Montées du décor à rebours (plus de cyclistes en montée) : aucune tant que les montées du retour ne sont pas
  détectées (lot N24), rendues au demi-tour suivant.
- `session.py` : circulation et cyclistes tenus dans ce repère, listes `vehicles` et `riders` de l'état toujours dans
  le repère du parcours (protocole inchangé), abri et aspiration toujours coupés à rebours (N17).
- Placement du cycliste à rebours (AS2) : il se place parmi les véhicules et les cyclistes du décor de son sens,
  dans le repère de la circulation, et double le tracteur lent devant lui (banc cloud du 14/11 : 4 contacts
  « tractor / cycliste » sans ce placement). Les bots, en face, n'en font pas partie.
- `living_decor.gd` : lit `dir` de l'état, convertit les listes du core et les places des bots ; `road_users` et
  `vehicle_places` restent dans le repère du parcours ; contacts comptés dans le repère de la circulation.
- Banc simulé : scénario `circulation_rebours` (village, demi-tour par Y maintenu à 60 s, passages forcés du banc
  toutes les 20 s).

## 3. Critères d'acceptation

1. Tests du core (`test_decor_rebours.py`, `test_traffic.py`, `test_road_cyclists.py`, `test_u_turn.py`) et de
   l'engine (`test_decor_rebours.gd`, `test_traffic_model.gd`, `test_road_cyclists_*.gd`, `test_living_decor.gd`) au vert.
2. Captures du banc `circulation_rebours` en low, medium et high, après le demi-tour, validées par le propriétaire.
3. Banc GPU sur le PC en low, medium et high : attendu neutre (même budget de véhicules et de cyclistes).

## Livraison

Fusionné dans `main` : PR #890 (15 novembre). Statut relevé par la mise à jour de la documentation du 19 novembre 2026.
