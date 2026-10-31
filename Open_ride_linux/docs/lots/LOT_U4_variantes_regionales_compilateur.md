# Lot U4 – Compilateur : variante régionale par tuile (géologie et architecture simplifiées)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Compilateur : variante régionale par tuile (table de géologie et d'architecture à grosse maille) | Python | U1 (U2 utile) | Petite | Oui, après U1, **version 3.0** (issue #334) |

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
