# Lot W20 – Montées, sprints et records du monde ouvert

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Montées et sprints du monde ouvert détectés en roulant, records d'une balade à l'autre | Python | W9, T2, T4, T5, T7, W19 | Moyenne | En revue (13 novembre) |

## 1. Objectif

Demande du propriétaire du 13 novembre (« fais des lots pour compléter les incohérences et manques » du monde ouvert). Le plan W (§ « branchement des séries de la 2.0 ») annonçait des montées détectées automatiquement sur la route engagée. Elles n'avaient jamais été faites, et le mode classique avait trois défauts en monde ouvert :

1. **Segments périmés :** la séance gardait les segments du dernier parcours chargé (`self._segments` n'était pas remis à zéro). Ils étaient chronométrés à des distances qui ne correspondaient à rien sur la route du monde ouvert.
2. **Aucune montée ni aucun sprint** du monde ouvert lui-même.
3. **Records perdus d'une balade à l'autre :** ils étaient rangés sous `ow:<id>`, un identifiant propre à chaque séance.

## 2. Travail fait

- **`core/src/openride_core/open_world_segments.py`** (nouveau, pur sauf le petit index) :
  - `LiveSegments.update` cherche montées et sprints avec les règles de `segments.py` (T2), sur la route connue, de 3 km derrière le cycliste au bout de la route engagée.
  - Un segment n'est retenu que s'il commence devant le cycliste et finit au moins 1 km avant le bout connu. Une montée qui touche ce bout pourrait encore s'allonger. Un segment retenu n'est plus jamais redessiné.
  - Un segment pas encore fini est retiré si un choix de branche déplace son début ou sa fin de plus de 5 m.
  - Sprints : au plus un tous les 10 km sur la séance.
- **Records d'une balade à l'autre :**
  - Les records du monde ouvert sont rangés sous le parcours commun `ow`.
  - Un segment dont le début et la fin sont à moins de 60 m d'un segment déjà vu, de même type, reprend son identifiant et son nom.
  - L'index est `segments_monde_ouvert.json`, à côté de `records.json` du profil. Il est écrit avec les records, hors de la boucle à 50 Hz.
  - Noms : « Montée n°K (4e cat.) », « Sprint n°K ».
- **Mode classique** (`classic.py`, `segment_timing.py`) :
  - `ClassicRace.open_ended` : longueur sans fin pour les chronomètres.
  - `add_segments` et `drop_segments` : un passage en cours d'un segment retiré est annulé, raison `route`.
- **Séance** (`session.py`) :
  - Segments vidés quand le monde ouvert est prêt.
  - Recherche toutes les 2 s (`OW_SEGMENTS_PERIOD_S`) sur la route connue.
  - Les segments trouvés passent au mode classique : HUD de segment, `segment_result`, records, maillots.

## 3. Contrats

Aucune modification. Les identifiants (`owc…`, `ows…`, 13 caractères) et les noms respectent les longueurs de `state.segment.id` et de `segment_result`.

## 4. Critères d'acceptation

1. `pytest` passe dans `core/` (nouveaux tests `test_open_world_segments.py`, et trois essais W20 dans `test_open_world_session.py` avec la doublure `--hills 6`).
2. Après un parcours chargé, le monde ouvert démarre sans segment.
3. Une montée trouvée en roulant est chronométrée : `segment_result` envoyé, record rangé sous `ow`.
4. Deuxième balade sur la même route : mêmes identifiants, et le passage de la balade d'avant est classé.
5. Recette PC (avec W16) : une balade d'une heure près de Sarre-Union. Le HUD annonce les montées, le résultat s'affiche au sommet, et la même montée refaite le lendemain montre l'ancien record.

## 5. Hors périmètre (lot suivant, W21)

- **Portiques et lignes au sol** des segments du monde ouvert dans la scène. L'engine les tire de la couche `segments` du `.world`, que le monde vivant n'a pas : il faudrait que le générateur l'écrive, puis que l'engine la relise à chaque révision. Ce lot change le rendu, donc captures à valider.
- **Arches de bonus** au-delà des 3 premiers kilomètres. Elles sont placées sur la longueur de la route au départ, côté core comme côté engine.
- **Montées des bots à profil** (`attach_segments`) sur les segments trouvés en roulant.
- **Records recalculés depuis les journaux** (migration des profils) : les séances du monde ouvert n'y sont pas reprises.

## Livraison

Branche `claude/project-thread-49nsz6-w20`, empilée sur W19 (#873) : fusionner #873 d'abord.
