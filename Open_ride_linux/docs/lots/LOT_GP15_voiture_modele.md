# Lot GP15 – Modèle de la voiture d'équipe refait (GP-voiture-modele)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : voiture d'équipe en un seul modèle (break, galerie et vélos sur le toit) | GDScript, Python | GP4, GP7, AS11 | Petite | **En revue** (planche low, medium, high et banc PC à faire) |

Série GP (mode « Grand Prix des objets »). Demande du propriétaire du 19 novembre 2026 : la modélisation 3D de la voiture d'équipe est « plutôt mauvaise » (forme, proportions, détails).

## 1. Constat

Depuis GP4 (#912, #919), la voiture d'équipe est un véhicule du core (`vehicles`, identifiant `tc<rang>`, sorte `car_a`) : traffic_renderer.gd dessinait donc une **berline rouge** du décor, et `gp_scene.gd` dessinait **en plus**, 5 m devant le coureur, l'ancienne caisse du lot GP7 (pavé blanc, habitacle encre, deux baguettes bleues pour les vélos, roues cylindres). Les deux se superposaient (capture `captures/gp4/voiture_equipe_medium.png`) : caisse rouge, toit bleu, baguettes qui sortent du toit.

## 2. Livraison

- Une seule voiture, sans exception propre au mode : nouvelle sorte `team_car` de `vehicle_mesh.gd` (même constructeur que les véhicules du décor, mêmes zones de couleur et même shader) : break de 4,8 m, long toit plat et hayon presque droit, trois vitres de côté, bande de l'équipe sous les vitres et flèche sur les portières (seconde couleur, bleu `fresh` de la charte GP), caisse blanche, galerie (rails, deux barres, trois rails à vélo), trois vélos de course debout sur le toit en sens alternés (cadres bleus, pneus, selle, cintre, pédalier), antenne radio, phares, calandre, feux arrière verticaux, plaques, rétroviseurs. 1 938 triangles (budget de 2 000 par véhicule, `test_vehicle_mesh.gd`).
- Core : `traffic.KINDS["team_car"]` (demi-largeur 1,04 m, longueur 4,8 m, part nulle : jamais tirée), abri et aspiration comme la berline ; `grandprix/items.py` : `escort="team_car"`. `pick_kind` saute les sortes à part nulle, aussi au-delà de la somme des parts (core et engine).
- Engine : `traffic_model.gd` et `traffic_renderer.gd` connaissent la sorte (son de passage de la berline) ; l'effet « car » de `gp_scene.gd` (l'ancienne caisse) est retiré.
- Contrat IPC révision 1.21 : sorte `team_car` dans `vehicles` (ajout compatible, journal du §8).
- Vitrine `engine/tests/vitrine_voiture_equipe.gd` : la voiture d'équipe et l'ancienne berline côte à côte, vues de côté, trois quarts avant, de la poursuite et de dessus.

## 3. Reste

- Planche des captures low, medium et high (banc `grand_prix_gp4_voiture`, caméra `follow_far`) validée par le propriétaire.
- Banc GPU PC low, medium et high (budgets 8, 13 et 16 ms) par la file du PC.
