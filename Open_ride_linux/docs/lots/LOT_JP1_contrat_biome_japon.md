# Lot JP1 – Contrat : 17e biome `japan` et toit `kawara` (version 6.0)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Contrat : 17e biome `japan` (Japon : montagnes humides) et toit `kawara`, reconnus partout avec un rendu de base | Python, GDScript, JSON | JP0 | Petite | En PR le 9 novembre, **version 6.0** |

## 1. Objectif

Premier lot de la série JP (`docs/6.0/PLAN_SERIE_JP.md`, plan validé par le propriétaire le 9 novembre). Ajouter le biome `japan` et la variante de toit `kawara` à toutes les énumérations fermées, pour que les lots suivants (pose au compilateur JP2, rendu JP3 à JP5, parcours JP6) n'aient plus de liste à toucher. Une seule liste, à jour partout (principe « pas d'exception »).

## 2. Contenu livré

| Où | Changement |
| --- | --- |
| Contrat | `world_format_v1.md` §8 quater et journal §12 ; schémas `biome`, `manifest`, `theme` (et sa copie du compilateur) ; description de `hello_ack.config.biome` |
| Compilateur | `biomes.BIOMES`, `regional.ROOFS` (la table U4 ne pose pas encore `kawara` : lot JP2) |
| Core | `config.BIOMES` : `[render] biome = "japan"` accepté, donc proposé au menu « Biome du décor » |
| Thème par défaut 2.0 | `biomes.japan` (andosol et mousse, lave grise, neige au-dessus de 2 600 m, forêt dense d'épicéas et de cyprès en attendant les sugi et hinoki de JP5, air humide, cigales, cerfs et macaques) ; variante `kawara` (enduit clair, bois sombre, tuiles grises) |
| Engine | `biome_ids.gd` ; nom « Japon » au menu ; style de bâtiment `kawara` (tuiles rondes grises, toit à croupe à large débord, enduit et bois sombre) posé par défaut dans le biome `japan` ; macaques en lisière ; parapentes rares ; shader multi-biome à 17 biomes (51 couches) |
| Tests | Comptes de biomes du compilateur et de l'engine tirés de la liste |

## 3. Hors périmètre

- Pose automatique de `japan` par le compilateur (JP2, sur la carte Köppen du lot U24).
- Espèces propres (sugi, hinoki, momiji, bambou), torii, lanternes (JP5) ; sons et ciel affinés (JP3).
- Niveau de terrain « horizon » pour voir le Fuji (JP4) ; parcours de Hakone (JP6).

## 4. Essai

Sans couche biome ni `--biome=japan`, rien ne change à l'écran. Avec `--biome=japan` (ou le menu), tout le parcours prend le biome. Captures et banc trois qualités (low 8, medium 13, high 16 ms) : avec la recette JP7, par la file du PC ; le coût attendu est celui d'un autre biome.
