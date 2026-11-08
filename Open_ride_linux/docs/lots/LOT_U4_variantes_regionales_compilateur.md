# Lot U4 – Compilateur : variante régionale par tuile (géologie et architecture simplifiées)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Compilateur : variante régionale par tuile (table de géologie et d'architecture à grosse maille) | Python | U1 (U2 utile) | Petite | En PR le 8 novembre (PR #785, empilée sur U2 #734), **version 3.0** (issue #334) |

## 1. Objectif

**Version 3.0.** Donner à chaque tuile une variante régionale (couleur des roches et des terres, matériaux des toits et des murs) tirée d'une table d'ébauche à grosse maille, modifiable par le thème, sans aucune coordonnée précise dans le dépôt.

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` §3 et §9 (risque 6), `docs/lots/LOT_U1_contrat_biomes.md` §4.1 et §4.3.
2. Code : `compiler/src/openride_compiler/biomes.py` (U2, si livré), `terrain.py`, `writer.py`.

## 3. Prérequis

U1 livré ; U2 utile (même fichier de tuile, champ `variant`).

## 4. Travail demandé

- Table `compiler/src/openride_compiler/data/regional_variants.toml` : zones rectangulaires en degrés entiers (au plus fin 1°), chacune avec une variante `ground` et une variante `roofs`, plus des règles générales (zones arides → `toit_plat_blanc`, latitudes au-delà de 58° → `bois`, tropiques → `laterite_rouge`). Les zones françaises restent larges (une par grande région géologique) ; aucune coordonnée plus fine que le degré.
- Module `regional.py` : `variant_for(lat, lon, biome_shares) -> {"ground", "roofs"}` ; la zone la plus petite qui contient le point gagne, puis les règles générales, puis une variante neutre (`calcaire_blanc` et `tuile_plate`).
- Une variante par tuile proche (au centre de la tuile), recopiée dans les tuiles lointaines qui la contiennent (variante majoritaire).
- Option `--variant GROUND,ROOFS` pour imposer la variante.

## 5. Fichiers concernés

- **Nouveaux :** `compiler/src/openride_compiler/regional.py`, `compiler/src/openride_compiler/data/regional_variants.toml`, `compiler/tests/test_regional.py`.
- **Modifiés :** `compiler/src/openride_compiler/biomes.py` ou `writer.py` (écriture de `variant`), `cli.py`, `compiler/pyproject.toml` (données embarquées), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** core, engine, contrats.

## 6. Modifications de contrat autorisées

Aucune (U1).

## 7. Critères d'acceptation

1. `pytest` passe dans `compiler/`.
2. Test de la table : toute coordonnée de la table est un entier de degrés (aucune décimale).
3. Point fictif en zone aride : `toit_plat_blanc` ; à 62° : `bois` ; hors de toute zone : variante neutre.
4. `--variant basalte,ardoise` : imposé sur toutes les tuiles.
5. Deux compilations : même variante pour les mêmes tuiles.

## 8. Hors périmètre

Rendu des variantes (U14), carte géologique réelle.

## 9. Réalisation (8 novembre)

- Table `data/regional_variants.toml` : 19 zones (grandes régions géologiques françaises, quelques zones européennes), quatre règles générales, variante neutre. Une zone contient `lat_min <= lat < lat_max` et `lon_min <= lon < lon_max` ; à surface égale, l'ordre alphabétique des noms départage.
- **Membre par membre :** `ground` et `roofs` se choisissent séparément (plus petite zone qui donne ce membre, puis première règle qui le donne, puis neutre) ; un membre que rien ne donne reste `null`, comme le contrat le permet.
- **Écart au §4, toits :** le cahier date d'avant U23, qui a donné à chaque biome son style de bâtiment (chalet, pisé, case, paillote, bois peint…) quand la tuile n'a pas de toit régional. Pour ne pas les effacer, les règles générales et la variante neutre ne posent que `ground` (aride → `gres_rose`, au-delà de 58° → `granite_gris`, tropiques → `laterite_rouge`, volcanique → `basalte`, neutre `calcaire_blanc`) ; seules les zones posent `roofs`, et les zones de montagne (Alpes, Pyrénées) le laissent au biome. Ajouter `roofs` à une règle ou au neutre dans la table suffit pour revenir à la lettre du cahier.
- `--variant GROUND,ROOFS` (un membre vide reste `null`) pour `build`, `build-all` et `add-layer biome` ; seul, il produit aussi la couche biome.
- `verify` contrôle que `variant` est `null` ou un couple pris dans l'énumération du contrat.
- « Modifiable par le thème » : le thème change l'aspect de chaque variante (`variants`, U14) ; le choix de la variante reste dans la table du compilateur (aucun changement de contrat).
