# Lot P24 – Animaux par terrain : troupeaux des prés, moutons en pente, chevaux, lièvres, cris

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Animaux par terrain : vaches et chevaux dans les prés, moutons sur les prairies en pente, lièvres des champs qui détalent, meuglements, bêlements et hennissements | GDScript | P11, P17, P22, P23, Y14 | Moyenne | **Livré le 27 octobre**, séance sur le PC à faire |

## 1. Objectif

Demande du propriétaire du 27 octobre (« ça manque de vie : animaux, oiseaux, véhicules sur terre et dans le ciel »), troisième lot de la deuxième vague du décor vivant (P22 à P27). Le bétail de P11 ne vient que des rares points `livestock` d'OpenStreetMap : en campagne, les prés restent vides. Avec les terrains ouverts du format 1.5 (P22), ce lot ajoute :

- des troupeaux dans les prés (vaches ou chevaux) et dans les prairies (moutons, qui tiennent sur les pentes) ;
- des lièvres dans les champs et les prés près de la route, qui filent en zigzag au passage ;
- les meuglements, bêlements et hennissements des troupeaux quand on passe à côté ;
- deux espèces détaillées de plus, le cheval et le lièvre, construites comme les autres animaux depuis Y14 (`people_mesh.gd`, demande du propriétaire du 27 octobre : « animaux trop simplistes »).

## 2. À lire

1. `docs/lots/LOT_P11_animaux.md`, `docs/lots/LOT_P22_pres_champs_routes_voisines.md`, `docs/lots/LOT_P23_oiseaux_campagne.md`, le lot Y14 (personnages et animaux construits par code, `people_mesh.gd`).
2. Code : `engine/scripts/fauna_placer.gd`, `fauna_behaviour.gd`, `fauna_renderer.gd`, `sound_player.gd`, `osm_streamer.gd` (tâche de fond qui place les animaux d'un tronçon).

## 3. Prérequis

P11, P17, P22 (terrains ouverts dans la couche végétation), P23 et Y14 (maillages des animaux avec le Builder de `people_mesh.gd`).

## 4. Travail demandé

- **`fauna_placer.gd`** :
  - troupeaux (`herd`) dans PASTURE_SHARE (7 sur 10, à `fauna.livestock = 1`) des prés et des prairies d'au moins 5 000 m², tirés de l'identifiant de la zone ; un pré donne des vaches (3 à 12) ou, une fois sur HORSE_SHARE (35 %), des chevaux (2 à 6), une prairie des moutons ; les bêtes sont dans un disque de 40 m autour d'un point de la zone, dans la zone, avec les exclusions au sol de P11 ; les moutons tiennent jusqu'à 45 % de pente, les autres jusqu'à 25 % ; aucun troupeau de plus dans un pré qui a déjà un point `livestock` ;
  - lièvres (`hare`) : au plus 2 par tronçon de 1 000 m, chacun avec une chance de 8 sur 10 à `fauna.deer = 1` (les lièvres sont du gibier, comme le chevreuil : pas de nouvelle clé de thème), dans un champ ou un pré de 15 à 60 m de la route, qui fuient loin d'elle ;
  - un chevreuil porte aussi `species`, comme toutes les bêtes au sol.
- **`fauna_behaviour.gd`** : un troupeau meugle, bêle ou hennit une fois par période de 40 s (décalée par son identifiant) quand le cycliste est à moins de 120 m d'une de ses bêtes, jamais au chargement ; un lièvre file dès que le cycliste est à moins de 25 m, à 11 m/s en zigzag (± 2,5 m, période 0,8 s), puis disparaît après 3,5 s. `wild_alpha` remplace `deer_alpha` pour les deux bêtes sauvages.
- **`fauna_renderer.gd`** : espèces `horse` (cheval bai : crinière et queue sombres, liste et balzanes blanches, encolure qui broute) et `hare` (longues oreilles à pointe noire, ventre et queue blancs), construites avec le Builder de `people_mesh.gd`, chacune avec son `MultiMesh` créé au démarrage ; bêtes au sol tirées de `GROUND_SPECIES` ; lièvre et chevreuil mis à jour à chaque image par `wild_transform`. Même budget `living(preset).animals` qu'avant.
- **`sound_player.gd`** : `cow_moo`, `sheep_baa` et `horse_neigh`, synthétisés comme les autres sons brefs, remplaçables par `~/OpenRide/Sounds/<sorte>.ogg`.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/fauna_placer.gd`, `fauna_behaviour.gd`, `fauna_renderer.gd`, `sound_player.gd` ; `engine/tests/unit/test_fauna_placer.gd`, `test_fauna_behaviour.gd`, `test_fauna_mesh.gd`, `test_sound_player.gd` ; `engine/tests/README.md`, `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** le compilateur, le core, les contrats, `crowd_renderer.gd`, `people_mesh.gd` (fil des personnages).

## 6. Modifications de contrat autorisées

Aucune : ni IPC, ni format, ni thème, ni touche. Désactivé avec le reste par `[render] living = false`, `fauna.livestock = 0` (troupeaux) ou `fauna.deer = 0` (lièvres) dans le thème.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Placement : sur 40 prés, de 20 à 36 troupeaux, vaches et chevaux (2 à 6), aucun mouton, toutes les bêtes dans leur pré et hors du couloir de la route ; déterministe ; `fauna.livestock = 0` : aucun ; un pré avec un point `livestock` ne garde que le troupeau du point ; sur une pente de 30 %, moutons sur les prairies, ni vache ni cheval ; sur 30 km de champs, de 35 à 60 lièvres, au plus 2 par kilomètre, de 15 à 60 m de la route, dans leur tronçon ; `fauna.deer = 0` : aucun lièvre.
3. Comportement : à 100 m d'un troupeau de vaches, 3 meuglements en 121 s ; à plus de 400 m, aucun ; les chevaux hennissent ; lièvre immobile à 26 m, en fuite à 24 m, 11 m en 1 s loin de la route avec un écart de côté, disparu après 3,5 s.
4. Affichage : deux chevaux et un lièvre affichés ; un lièvre parti est caché ; cheval et lièvre de 100 à 1 500 triangles, pieds à y = 0, tête qui broute à l'avant, pattes immobiles ; mise à jour de 177 animaux sous 0,45 ms par image (`fauna_frame_200`).

**Sur le PC cible (le propriétaire) :** séance sur un parcours de campagne compilé avec les couches OSM : vaches, chevaux et moutons dans les prés, jamais dans un champ cultivé ni sur la route, lièvre qui détale au passage, un meuglement de temps en temps ; perte de moins de 1 image/s en `low` (P27 fera la mesure complète).

## 8. Hors périmètre

- Texture des prés et des cultures, insectes au champ dans les fonds sonores : plus tard (P27 ou série Y).
- Faune par biome (U12, version 3.0), oiseaux de nuit (P19, version 2.0).

## 9. Livraison

Développé au-dessus de Y14 (maillages des animaux par le Builder de `people_mesh.gd`) et de P22 (format 1.5).

- Mesures ici (machine partagée, Godot 4.3 sans écran) : mise à jour de 177 animaux en 0,35 ms par image en `high`.
- Tests : `test_fauna_placer.gd` (35 vérifications), `test_fauna_behaviour.gd` (40), `test_fauna_mesh.gd` (30), `test_sound_player.gd` (16).
- Reste sur le PC cible : la séance décrite au §7.
