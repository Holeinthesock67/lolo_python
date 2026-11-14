# Lot SM1 – Parcours de démonstration sous-marin « Récif des tortues »

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Biome `reef` (fond marin), ambiance sous l'eau, laminaires, coraux, gorgones, poissons, tortues, raies, boucle de 8 km « Récif des tortues » | Python, GDScript, JSON | O37, O38, U10, U12, HP1 | Moyenne | En PR le 13 novembre |

## 1. Objectif

Demande du propriétaire du 13 novembre (22 h 29) : « un parcours démo dans un monde sous-marin luxuriant ». Plan : `/mnt/project-files/plans/PLAN_DEMO_SOUS_MARIN.md` (dossier du projet). Choix validés le 13 novembre à 22 h 32 (« Ok pour recommandations ») : tout le parcours sous l'eau, sans cyclistes du décor, voitures ni maisons ; « Récif des tortues ». Le propriétaire a aussi demandé une boucle, puisque le parcours ne fait que 8 km.

## 2. Contenu livré

| Où | Changement |
| --- | --- |
| Contrat | `world_format_v1.md` §8 quater, §9 et journal §12 ; schémas `biome`, `manifest`, `theme` (et sa copie du compilateur) : biome `reef`, espèces `kelp`, `coral`, `sea_fan`, fond d'ambiance `underwater`. C'est un ajout compatible, sans IPC. |
| Compilateur | `biomes.BIOMES` (jamais voté sur un parcours réel) ; `demo_biomes.py` : boucles `LOOPS` (circuit O38 et récif), relief `reef_relief` plafonné sous la surface (`reef_cap`, jamais au-dessus de −4 m), zones de laminaires et de coraux, quatre lieux nommés ; `--recif` ; entrée `demo-recif` « Récif des tortues » du jeu de base |
| Core | `config.BIOMES` (« fond marin » au menu « Biome du décor ») ; `traffic.underwater_route` : pas de circulation ni de cyclistes du décor quand le fond marin couvre au moins la moitié de la route (`session._traffic_for`, comme au vélodrome) |
| Thème par défaut 2.0 | `biomes.reef` : sable corallien, roche du récif ; laminaires, coraux et gorgones (260 par hectare dans les zones) ; eau `#1a7f9a` ; lumière bleutée ; fond `underwater` ; faune `birds` (poissons) et `deer` (tortues, raies) ; pas de saison |
| Engine | `atmosphere_model.gd` : clé `underwater` (poids des biomes sous l'eau), qui donne un brouillard plein à 230 m, un horizon couleur de l'eau, une lumière d'en haut plus faible et aucune brume de chaleur ; `atmosphere_view.gd` : ciel noyé dans le brouillard (`fog_sky_affect`), surface vue d'en dessous (`sea_ceiling.gdshader`) et bulles qui suivent la caméra ; caustiques sur le fond (`terrain_biomes.gdshader`, émission jusqu'à 70 m) ; `tree_species.gd` : laminaire (balancement × 4), corail branchu (rigide), gorgone en éventail, couleurs d'instance tirées dans une palette (`tree_renderer.gd`) ; `fauna_placer.gd` / `fauna_renderer.gd` : bancs de poissons jaunes et bleus, tortues et raies qui tournent entre le fond et la surface (`agl`, `min_agl`, `below_y`, `radius`), battement lent (`FLAP_HZ`) ; `ambience_*` : fond `underwater` (grondement sourd et bulles) ; `living_decor.gd` : parcours sous l'eau sans circulation, cyclistes du décor, avions, spectateurs, passants ni objets du bord ; rochers sur le fond, pas de parapente |
| Tests | `test_biome_demo_world.py` (boucle, profondeurs, plafond, lieux, pas de circulation), `test_traffic.py` ; engine : `test_atmosphere_model.gd` (sous l'eau), `test_fauna_biomes.gd` (faune du fond marin) |

## 3. Coût attendu et recette PC

Le brouillard proche cache le lointain. Les ajouts sont l'émission des caustiques (près de la caméra seulement), 96 bulles, un grand carré non éclairé et les poissons dans le budget des oiseaux. Recette à faire sur le PC du propriétaire : banc en low, medium et high sur `demo-recif` (budgets GPU 8, 13 et 16 ms), 0 contact, puis planche de captures (départ, laminaires, corail, tombant) à valider avant fusion.

## 4. Limites

- Pas d'épave dans ce lot : il faudrait un nouvel objet de décor posé sur un point (à prévoir si le propriétaire le veut après la planche).
- La route reste une route revêtue (la physique ne change pas) ; les laminaires, coraux et gorgones sont mélangés dans toutes les zones (le biome n'a qu'une liste d'espèces).
