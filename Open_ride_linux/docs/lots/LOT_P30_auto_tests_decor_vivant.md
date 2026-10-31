# Lot P30 – Auto-tests du décor vivant : comptes par sorte au banc, sons entendus, pause dans la vraie scène

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Auto-tests du décor vivant : objets par sorte et sons au banc simulé, sons du décor relevés, pause vérifiée dans la vraie scène | Python + GDScript | P27 | Petite | **Livré le 28 octobre** |

## 1. Objectif

Demande du propriétaire du 28 octobre : utiliser les outils d'auto-test quand ils existent et dire lesquels manquent. Pour le décor vivant (P22 à P29), trois manques relevés pendant P27, propres au décor (les autres propositions vont à la série X : vitesse imposée du banc dans X35, `living = false` comparé aux références 1.0 dans X20, lignes `ERROR` des tests unitaires et seuils de temps en dur dans X34) :

- le banc simulé ne disait rien du décor : on ne pouvait pas donner un avis chiffré sur les densités ;
- aucun test ne vérifiait qu'un son du décor se joue vraiment dans la scène ;
- la pause n'était vérifiée qu'en tests unitaires, pas dans la vraie scène.

## 2. À lire

`docs/lots/LOT_P27_integration_recette_decor_vivant_2.md`, `docs/OUTILS_DE_TEST.md` ; code : `engine/scripts/living_decor.gd` (`test_info`), `sound_player.gd`, `engine/tests/sim_bench.py`, `engine/tests/visual_check.py`.

## 3. Prérequis

P27 livré (scénario `decor_vivant_2`, scène `decor_vivant`).

## 4. Travail demandé

- **Sons entendus** (`living_decor.gd`) : les lecteurs 3D du décor sont tous créés au démarrage ; toutes les `SOUND_POLL_S` (0,25 s), ceux qui passent à `playing` sont comptés par nom de son (`sound_player.gd` `kind_of(stream)`) dans `sounds_heard`, remis à zéro par `configure`. Aucun changement dans les lots qui jouent les sons.
- **Signature de ce qui se fige** (`frozen_signature()`) : somme des positions des véhicules de la route et lointains, des cyclistes du décor, du ciel et des bateaux, arrondie au centimètre. `test_info` du décor donne `sounds` et `frozen_sig`.
- **Banc simulé** (`sim_bench.py`) : chaque capture relève les objets affichés par sorte (`birds`, `animals`, `vehicles`, `distant_vehicles`, `cyclists`, `aircraft`, `boats`) et les sons démarrés ; le rapport ajoute une courbe par sorte, un tableau (captures où la sorte est vue, médiane, maximum) et les sons, et `decor.csv` les garde. Section `bench` du scénario : `decor_expect` (sortes vues au moins une fois) et `sounds_expect` (groupes de sons dont un au moins doit démarrer). `decor_vivant_2` demande les oiseaux, les animaux, les véhicules lointains, les cyclistes et le ciel, et un son d'oiseau et un passage de véhicule : le véhicule de la route ne reste en vue que quelques secondes, souvent entre deux captures (30 s), et c'est son son de passage qui le prouve.
- **Pause dans la vraie scène** (`visual_check.py`, scène `decor_vivant`) : deux captures en pause à `DECOR_PAUSE_S` (2 s) d'écart, `frozen_sig` identique et non nul.
- **Défaut trouvé** : `fauna_renderer.gd` laissait `visible_instance_count` à −1 (toutes les instances) entre `set_preset` et la première mise à jour : les animaux du budget pouvaient s'afficher entassés à l'origine du monde pendant le chargement. `set_preset` le met à 0.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/living_decor.gd`, `sound_player.gd` (`kind_of`), `fauna_renderer.gd` (`set_preset`) ; `engine/tests/sim_bench.py`, `visual_check.py`, `sim_bench_scenarios/decor_vivant_2.json` ; tests `test_living_decor.gd`, `test_sound_player.gd`, `test_fauna_behaviour.gd` ; `docs/OUTILS_DE_TEST.md`, `engine/tests/README.md`, `docs/RECETTE_P27.md`, `docs/GUIDE_UTILISATION.md` (la pause fige les véhicules, les cyclistes, le ciel et les bateaux, pas les animaux), index.
- **Interdits :** le comportement des lots P23 à P29, les contrats.

## 6. Modifications de contrat autorisées

Aucune (le message de test `screenshot` donne deux champs de plus dans `decor`, hors contrat).

## 7. Critères d'acceptation

1. `test_living_decor.gd` : signature inchangée en pause ; `test_sound_player.gd` : `kind_of` ; `test_fauna_behaviour.gd` : aucune instance affichée avant la première mise à jour.
2. `sim_bench.py --scenario decor_vivant_2` : sortes vues et sons demandés vérifiés, `decor.csv`, courbe et tableau dans le rapport.
3. `visual_check.py` : `decor_pause` passe.
4. `test_docs_coherence.py` passe.

## 8. Hors périmètre

Vitesse imposée du banc (X35), `living = false` comparé aux références (X20), lignes `ERROR` des tests unitaires et seuils de temps en dur (X34).

## 9. Livraison

- Banc `decor_vivant_2` en `medium` dans le cloud (deux lancements) : 11 captures ; oiseaux vus 10 ou 11 fois sur 11 (19 au plus en route), animaux 10 ou 11/11 (5), véhicule de la route 1/11 puis 0/11, véhicules lointains 10/11 (12), cyclistes 9/11 (4), ciel 10/11 (4), bateaux 0 (aucun affiché sur ce trajet de 1,8 km : pas demandé par le scénario) ; sons : cri de rapace ×2, passage de véhicule ×1, « Allez ! » ×1. Aucun son d'avion en 5 min : le grondement ne se joue qu'au passage proche d'un avion, trop rare pour une attente fiable ; il reste affiché dans le tableau.
- `visual_check.py` en `1280x720:low` : `decor_pause` passe (signature identique sur 2 s).
- Tests : `test_living_decor.gd` (40), `test_sound_player.gd` (18), `test_fauna_behaviour.gd` (41).
