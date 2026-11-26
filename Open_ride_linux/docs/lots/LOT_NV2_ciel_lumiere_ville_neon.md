# Lot NV2 – Ville néon : ciel, lumière et brume

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Ambiance du paysage `ville_neon` : ciel à trois couleurs, grand soleil bas, lumière rasante, brume rose, puis nuit violette étoilée (`neon_fx.gd`, `atmosphere_view.gd`, `sky_clouds.gdshader`) | GDScript | NV1, DB2, P19 | Moyenne | **En revue** (26 novembre) |

Deuxième lot du parcours « Avenue de la Lagune » (cadrage hors dépôt : `/mnt/project-files/plans/CADRAGE_AVENUE_LAGUNE_2026-11-26.md`). La route mouillée et ses reflets, prévus d'abord ici, attendent la mesure sur le PC (lot NV0) et passent dans un lot à part.

## 1. Objectif

Dans une tuile du paysage `ville_neon`, le ciel, la lumière et la brume sont ceux des planches validées le 26 novembre : coucher du soleil rose et orange au départ, puis nuit violette. Hors de ce paysage, rien ne change.

## 2. Contraintes

- **Image par défaut inchangée au pixel près** : tout est conditionné à `neon_level > 0` (vérifié sur `vitrine_nuit.gd`, vues de jour identiques avant et après).
- Pas d'exception : même mécanique que la lueur du volcan (`set_fire`), une seule règle (`biome_model.gd`, `neon_at`).
- Le paysage **impose sa lumière** quelle que soit l'heure choisie : sinon les néons des lots suivants ne se voient pas. C'est écrit dans le thème (section `neon`), pas dans une démonstration.
- Coût : quelques opérations de plus dans le shader du ciel, seulement en ville néon. Aucune lampe, aucun reflet d'écran dans ce lot.
- Aucune révision du contrat IPC ni du format des parcours.

## 3. Réalisation

- `neon_fx.gd` (nœud du décor vivant, `living_world.gd`) : `neon_level` (0 à 1, lissé à 0,5 par seconde, entier dès la première image), `night` (coucher du soleil tenu 2 min, nuit complète à 10 min de roulage dans le paysage, arrêtée en pause), `palette` (section `neon` du thème), `night_override` pour les captures.
- `biome_model.gd` : `any_neon`.
- `atmosphere_view.gd` : `set_neon(level, night, palette)`, `_with_neon` après l'heure et le feu (brume, teinte et énergie de la lumière, direction du soleil, lumière ambiante, étoiles), `neon_sky` (haut, milieu, horizon du coucher à la nuit), paramètres du shader du ciel.
- `sky_clouds.gdshader` : `neon_level`, dégradé à trois couleurs, grand soleil de 6° de rayon et son halo, soleil ordinaire caché à pleine ambiance.
- `main.gd` : `set_neon` à côté de `set_fire`.
- Thème par défaut (et copie du compilateur) : couleurs du ciel du prototype (`sky_top`, `sky_mid`, `sky_horizon`).
- `tests/vitrine_nuit.gd` : option `--neon 1` pour les captures.

## 4. Critères d'acceptation

1. `engine/tests/unit/test_neon_landscape.gd` (27 vérifications) : `neon_fx.gd` inactif sans paysage néon, ambiance dès la première image, coucher tenu, nuit qui tombe, pause, nuit imposée ; `set_neon` sans effet à ambiance nulle ou sans section, brume rose et soleil bas au coucher, lumière faible d'en haut et étoiles la nuit, fondu à l'entrée.
2. Tests graphiques de référence (`tests/golden`) inchangés.
3. Captures au cloud (`vitrine_nuit.gd --neon 1`, `medium`) validées par le propriétaire.
4. PC : banc `medium` sur la vitrine ou sur le parcours du lot NV6, dans les budgets 8 / 13 / 16 ms (par le fil de fusion, après le 28 novembre).

## 5. Livraison

Prêt le 26 novembre, empilé sur NV1 (PR #1085). La PR s'ouvre après la fusion de NV1.
