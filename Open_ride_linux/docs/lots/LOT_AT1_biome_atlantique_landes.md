# Lots AT1 et AT2 – Biome `atlantic_heath` : Atlantique et landes (version 6.0)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| 18e biome `atlantic_heath` (Asturies, Pays basque, Bretagne, îles britanniques) : bruyère, ajonc, fougère aigle, murets de pierre sèche, pose par table régionale commune aux parcours et au monde ouvert | Python, GDScript, JSON | U24, JP1 | Moyenne | En PR le 12 novembre, **version 6.0** |

## 1. Objectif

Deuxième biome de l'étude `ETUDE_BIOMES_V6.md` (§3.2), ordre validé par le propriétaire le 12 novembre (« ok 1 à 4 ») : Atlantique et landes en premier, puis hauts plateaux (19e biome `high_plateau`, autre fil), puis variantes. Corrige aussi l'Angliru, sorti méditerranéen à l'étape 1 de la recette U18 : il sort désormais en landes atlantiques sur ses prés et ses landes, en forêt tempérée dans ses bois.

## 2. Contenu livré

### AT1 : contrat, rendu

| Où | Changement |
| --- | --- |
| Contrat | `world_format_v1.md` §8 quater, §9 (espèces) et journal ; schémas `biome`, `manifest`, `theme` (et sa copie du compilateur) ; description de `hello_ack.config.biome` |
| Compilateur, core | `biomes.BIOMES`, `config.BIOMES` : `[render] biome = "atlantic_heath"` accepté, proposé au menu « Biome du décor » sous le nom « Atlantique et landes » |
| Thème par défaut 2.0 | `biomes.atlantic_heath` : sol olive de lande, granite et schiste en pente, neige au-dessus de 1 800 m ; végétation basse dominante (bruyère 10, fougère aigle 6, ajonc 5, chêne 1, bouleau 1, 320 plants par ha, plus rien au-dessus de 1 100 m) ; ciel bas et brumeux ; vent dans les landes ; moutons, poneys, goélands |
| Espèces construites par code (`tree_species.gd`) | `heather` (plaque de coussins mauves et brun-vert, 0,55 m), `gorse` (buisson épineux vert sombre piqué de fleurs jaunes, 1,6 m), `bracken` (deux touffes de frondes, 1 m, caduque : rousse à l'automne, absente l'hiver) ; toutes passent au modèle lointain à 150 m et restent hors des forêts lointaines en imposteurs |
| Saisons (`tree_sway.gdshader`) | L'automne et l'hiver des feuillus s'appliquent à tout feuillage (codes 8 à 10) au lieu des seules feuilles et aiguilles : la fronde caduque de la fougère suit la même règle que les feuilles. Palmiers et fougères arborescentes, persistants, ne changent pas |
| Murets (`ground_details.gd`) | Nouvelle sorte `wall`, disposée en file (`LAYOUT = row`) : tronçons de 6 m bout à bout des deux côtés de la route, alignés sur le cap et penchés selon la pente, écart au bord de 1,5 à 7 m au-delà du dégagement de 3 m (bruit continu le long de la route), brèches (15 %), pierre de la roche du biome ou de la variante régionale, éclaircie. Maillage : talus trapézoïdal, deux assises de pierres saillantes de tailles et de teintes inégales, pierres de couronnement de chant, moins de 500 triangles |
| Budgets | `living(preset).ground_walls` = 100 en low, medium et high (5 tronçons de route × 2 côtés × 10 murets, environ 50 000 triangles) ; `GroundDetails.budgets(living)` lit toutes les clés au lieu de dictionnaires recopiés dans quatre fichiers |
| Bâtiments, faune, ciel | Style `pierre_seche` par défaut ; rôle `cow` joué par des moutons, volées en V de goélands ; parapentes fréquents, montgolfières rares |

### AT2 : pose du biome

Table embarquée `compiler/src/openride_compiler/data/biome_zones.toml`, **commune à tous les biomes régionaux** (le Japon, lot JP2, y rangera son entrée). Pour chaque biome : classe propre au compilateur (203 pour `atlantic_heath`), codes de Köppen, classes WorldCover ; puis des rectangles en degrés entiers. Un point de la grille des biomes dans un rectangle, sous un climat de la liste, voit ses échantillons des classes de la liste prendre la classe du biome. Atlantique : Cfb, Cfc et Csb ; arbustes (20, et `natural=heath` d'OSM), prairie (30), mousses (100) ; les arbres restent forêt tempérée, les cultures restent cultures. Rectangles : Galice et Minho, Asturies et Cantabrie, Pays basque, Bretagne, Cornouailles et Devon, pays de Galles, Pennines et Lake District, Écosse, Irlande.

La règle est dans `biomes.py` (`regional_rule`, `Inputs.regional` injectable comme `zones` et `volcanic`) : le compilateur des parcours GPX et le générateur du monde ouvert (`classify_level`, lot W17) la suivent sans code de plus.

## 3. Hors périmètre

- Haies bocagères, chênes et châtaigniers tordus par le vent (lot suivant si le propriétaire le souhaite).
- Fond sonore propre (pluie fine, vent côtier) : le vent des conifères sert de vent des landes.
- Parcours du pack de cols (Angliru, Covadonga, Jaizkibel…) : recette sur PC avec OSM.

## 4. Essais

- Tests : `compiler/tests/test_biome_zones.py` (table, cols connus, Köppen hors liste, forêts et cultures gardées, injection) ; `engine/tests/unit/test_ground_details.gd` §9 (murets des deux côtés, alignés, jamais à moins de 3 m du bord bouts compris, maillage dans l'ordre avant de Godot) ; espèces par `test_vegetation_biomes.gd`, `test_tree_faces.gd`, `test_forest_impostors.gd` ; comptes de biomes tirés de la liste.
- Captures cloud (rendu logiciel, vitrine des biomes, low, medium, high, 1680x1050) : `/mnt/project-files/captures/at1-landes-2026-11-12/`, à valider par le propriétaire.
- Banc GPU sur le PC (budgets 8, 13 et 16 ms) : vitrine `--biomes atlantic_heath,temperate_grassland` en low, medium et high par la file du PC ; attendu proche de la prairie (plantes basses à 72 à 180 triangles, murets légers).
