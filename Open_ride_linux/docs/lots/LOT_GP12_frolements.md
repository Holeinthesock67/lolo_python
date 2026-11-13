# Lot GP12 – Aucun frôlement entre coureurs du Grand Prix

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : voie imposée qui double, objets qui ne poussent personne dans une roue | Python | GP2, GP3, PL1 | Petite | Fait (banc PC à faire) |

Série GP (mode « Grand Prix des objets »). Plan de la série : `docs/4.0/PLAN_SERIE_GP.md`. Accord du propriétaire du 12 novembre 2026 (constat du lot GP10).

## 1. Objectif

Le banc compte les contacts entre coureurs (« aucun contact », lot P32 ; règle du lot PL1 : moins d'une longueur de vélo en long et d'une largeur de coureur en travers). Course simulée de 3 tours avant ce lot : 1 frôlement à 4 adversaires, 3 à 11, à la limite de 1,7 m roue à roue. Objectif : zéro, sans exception propre au mode, sans révision IPC et sans toucher à `main.gd`.

## 2. Causes

1. **Voie imposée** (esquive d'un bot, flèches ou A du cycliste) : la séance coupait le placement (`Lane.auto` faux). Le coureur gardait le centre de sa voie sans doubler, sans couloir et sans être enfermé (lot PL1) : il roulait dans la roue d'un plus lent de la même voie.
2. **Objets** : un coup de fouet ou une super-forme change la vitesse virtuelle après le freinage roue contre roue du bot ; une glissade du coureur de devant le ralentit d'un coup. L'enfermement, calculé au pas précédent avec les anciennes vitesses, ne freinait pas le suivant à temps, ni le cycliste.

## 3. Livraison (12 novembre 2026)

- `draft.Lane.follow` (vrai par défaut) : faux, c'est une **voie tenue** : placement automatique sans prendre de roue ni d'éventail, la cible reste `home` ; dépassement à gauche, couloir et enfermement comme tout le monde. La voie imposée du Grand Prix devient une voie tenue (`session._sync_grandprix_lanes`) au lieu d'un placement coupé. Le placement coupé (`auto` faux : fantôme, bot éliminé du Dernier survivant, cycliste sans « Placement dans la roue » hors voie imposée) ne change pas.
- `session._brake_grandprix_wheels` : après les objets du pas, l'enfermement (`draft.blocked_by`) est recalculé avec les nouvelles vitesses, du premier coureur au dernier, et chacun freine roue contre roue à `BRAKE_GAP_M` comme un bot (lot PL1), cycliste compris (vitesse virtuelle seulement : la pente envoyée ne dépend toujours pas des objets). Le freinage se transmet le long d'une file dans le même pas.
- Pas de révision IPC, `main.gd` non touché, simulateur d'équilibrage (lot GP5) inchangé : il n'a pas de placement.
- Tests : `test_draft_lane.py::test_gp12_held_lane_passes_but_never_takes_a_wheel`, `test_grandprix_session.py::test_gp12_object_never_pushes_into_a_wheel` et `test_gp12_three_laps_without_contact` (lent, chaos normal et fou ; le cas normal comptait un contact avant ce lot).
- Mesure dans le cloud : 40 courses de 3 tours simulées avec la séance (2, 4, 7 et 11 adversaires, chaos normal et fou), aucun contact ; avant le correctif, des contacts dès la première course.

## 4. Reste

Banc PC `grand_prix` (et `grand_prix_onze` après GP10) en `low`, `medium` et `high` : « décor : aucun contact sur la route », budgets GPU 8, 13 et 16 ms.
