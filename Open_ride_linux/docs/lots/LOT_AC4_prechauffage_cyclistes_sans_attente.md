# Lot AC4 : préchauffage des cyclistes du décor sans attente sur le fil principal

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| À-coups de main : le préchauffage des cyclistes du décor attend les fils de travail image par image (étape d'attente du plan unique), une apparence par image | GDScript | PI2, AS7 | Petite | En cours (codé le 22 novembre, banc PC à faire) |

Fil global « Supprimer les à-coups récurrents de main » (21-22/11).

## Constat
- Bancs de la nuit du 21 au 22/11, galerie Cyber-Rogue medium (#956, #960, #965, tous avec main) : une image de
  532 à 571 ms au rechargement du parcours, cause « préchauffage », étape `cyclistes préchauffage` de 525 à 563 ms,
  0 pipeline compilé (ce ne sont pas des shaders).
- Même étape aux bancs GP de la nuit du 20 au 21 (rNUIT20) : 860 à 996 ms, à 0 m, avant le départ.
- Cause : `road_cyclists_renderer.gd warm_up` demandait les maillages des 16 apparences à tous les niveaux du
  préréglage aux fils de travail, puis **les attendait sur le fil principal** (`AvatarView.wait_parts`), puis
  construisait les 16 racines de réserve, le tout dans une seule étape du plan unique, donc dans une seule image.

## Correction (une seule voie, pour tous les modes)
- `warmup_plan.gd` : étape d'attente (`add_wait`, ou 3e élément `"attente"`) : son Callable renvoie vrai quand
  c'est prêt ; sinon elle reste en tête du plan et repasse à l'image suivante. Le départ attend déjà la fin du plan.
- `road_cyclists_renderer.gd warm_steps(camera)` : « cyclistes demande » (maillages demandés, sans attendre),
  « cyclistes attente » (`parts_ready`), « cyclistes apparence 0…15 » (une racine de réserve par image),
  « cyclistes affichage » (devant la caméra pendant WARM_FRAMES images). `main.gd _warmup_steps` les ajoute au plan.
- `warm_up(camera)` enchaîne les mêmes temps dans l'appel (tests) : mêmes fonctions, rien en double.

## Tests
- `test_warmup_plan.gd` : l'étape d'attente reste en tête tant qu'elle n'est pas prête, puis la suite joue ; une étape
  normale qui renvoie faux n'est pas rejouée.
- `test_road_cyclists_model.gd` : le plan joue demande, attente, 16 apparences et affichage ; 16 racines de réserve
  minuscules devant la caméra, comme `warm_up`.

## Recette PC
Catégorie : logique. Medium : galerie Cyber-Rogue (`rogue_galerie.py`) et `grand_prix_onze` ; attendu : aucune image
de plus de 150 ms due aux cyclistes (`cyclistes …` dans `saccades.csv`), délai jusqu'au départ à peu près le même.
