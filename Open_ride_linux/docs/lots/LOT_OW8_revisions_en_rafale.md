# Lot OW8 : monde ouvert, révisions de route en rafale et attentes du fil principal

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série OW (monde ouvert) : plus de révision identique quand la route s'arrête, révision sans changement de route sans rien reconstruire, travaux OSM et ruban d'une route remplacée jamais attendus sur le fil principal | Python, GDScript | W8, W10 | Petite | **En revue** (PR à venir) |

Demande du 26/11 (point 2 du banc `rZONES26c`, Tromsø en medium) : attente du fil principal sur la tâche OSM et
coût du décor vivant. Lot indépendant des lots BF1 et PG1. Correction globale : aucune règle propre à une zone.

## 1. Constat (banc rZONES26c, Tromsø, medium)

- 6 images de 1,4 à 1,6 s (aucun pipeline compilé, `process` ~1,7 s) vers 2,3 à 2,5 km, puis 233 images de 110 à
  150 ms, poste « décor » de 35 à 52 ms.
- `engine.log` : 331 lignes `world_revision`, dont plus de 320 identiques (`length_m=4388.4 from_part=4`), une toutes
  les 0,5 s, à partir du choix « Carrefour … : branche 0 (click) » de 17:13:04. Le core passe de 1 à ~118 messages
  « autres » par minute. Les autres zones : 0 à 7 révisions.
- Cause : la branche choisie finit sur un sens unique sans demi-tour possible (« plus de route connue »).
  `WorldSession._extend()` rendait vrai dès que la route était plus courte que l'horizon, même sans rien ajouter :
  chaque `progress` du core (deux par seconde) publiait une révision identique, avec le même statut « missing ».
- Côté engine, chaque révision appelait `swap_route` : attente synchrone (`BgTasks.wait`) des travaux OSM et du
  ruban en cours sur les parties réécrites (un tronçon de bâtiments : 656 ms), puis `living_world.set_route` et
  `living_decor.extend_route` sur toute la route connue (le poste « décor »).

## 2. Travail

- OW8-1 (générateur) : `_extend()` ne rend vrai que si une étape est ajoutée ou l'arrivée posée ; « plus de route
  connue » annoncé une fois. Test `test_stopped_route_publishes_no_identical_revision` (échouait avant : 30
  révisions identiques).
- OW8-2 (engine, `live_world.gd`) : une révision dont les parties lues sont celles déjà là (`same_parts`) garde le
  même objet route et rend `same_route` ; `main.gd` ne lit alors que les tuiles nouvelles (`swap_route` depuis la
  fin), sans refaire ruban, OSM, décor vivant ni repères. Garde aussi pour les révisions de tuiles du générateur
  (`changed_from_part` = dernière partie, réécrite à l'identique).
- OW8-3 (engine, `osm_streamer.gd`, `world_streamer.gd`) : les travaux d'une route remplacée ne sont plus attendus
  par `swap_route` : ils finissent en fond, leur résultat est jeté (`_orphans`, libérés quand ils sont finis,
  attendus seulement par `clear()` et `flush()`).
- Tests : `test_live_world.gd` (route inchangée, carrefours relus, altitude réglée = changement),
  `test_live_streamer.gd` (travail de l'ancienne route mis de côté puis libéré).

## 3. Recette

- Banc : `ow_zone_tromso` en medium (file `ow_multi_zones.toml`, cache séparé) : au plus quelques révisions après le
  carrefour de 17:13 (lignes `same=1` pour les tuiles), plus d'image au-dessus de 1 s hors chargement, poste
  « décor » revenu au niveau des autres zones.
- Rien ne change pour une route qui s'allonge normalement (autres zones).

## Livraison

- PR à venir (branche `claude/project-thread-gn65yi-ow`).
