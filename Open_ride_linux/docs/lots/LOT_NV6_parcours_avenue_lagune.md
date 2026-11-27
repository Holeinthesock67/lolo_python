# Lot NV6 – Ville néon : parcours « Avenue de la Lagune »

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Parcours de démonstration « Avenue de la Lagune » : boucle plate de 15 km (5 km en variante de recette, pour les bancs) dans une ville de bord de mer inventée, toutes les tuiles dans le paysage `ville_neon`, ajoutée au jeu de base | Python, GDScript | NV1, NV2, NV3, GP13b | Moyenne | **En revue** (26 novembre) |

Quatrième lot du parcours vitrine de la ville néon (cadrage hors dépôt : `/mnt/project-files/plans/CADRAGE_AVENUE_LAGUNE_2026-11-26.md`). Premier parcours roulable : le ciel et la lumière viennent du lot NV2, les néons des façades du lot NV3 ; les enseignes, le mobilier de rue, les voitures garées et les passants des lots NV4 et NV5.

## 1. Objectif

Un parcours livré avec le jeu, sans réseau, dense partout, pour montrer la ville néon : avenue d'immeubles, front de mer, port, vieux quartier. En boucle, dans la liste générale « Parcours ».

## 2. Contraintes

- Création originale : ville, noms de lieux, d'hôtels, de cafés et de cinéma inventés pour OpenRide ; aucune donnée réelle (origine fictive 45° N, 2° E).
- Format des parcours inchangé (le paysage `ville_neon` est du lot NV1) ; aucune révision du contrat IPC ; rien dans le profil ni la ligue.
- Les autres parcours de démonstration sont identiques au bit près (seule la règle de plage `shore: sand` est ajoutée, pour cette boucle).
- Coût de rendu : près de 1 500 bâtiments sur les 15 km, dont des tours de 30 étages ; environ 900 000 triangles en `medium` au cloud. **Banc PC obligatoire avant fusion** (budgets 8 / 13 / 16 ms).

## 3. Réalisation

- `demo_biomes.py` : boucle `lagune` de `LOOPS` (15 km depuis le 27 novembre, demande du propriétaire : avenue, front de mer de 3,6 km, port, vieux quartier, quartier des tours, quartier des villas ; variante de recette `lagune_recette` de 5 km sans tours ni villas, prise par `Plan(recette=True)`, table `LOOP_RECETTE` ; biome `coast`, variante `LAGUNE_VARIANT` : toits plats, paysage `ville_neon`), relief `lagune_relief` (plat, butte du port de 5 m, 3,1 % au plus), tronçon `sea` de 2 400 à 6 000 m (plage de sable sur tout le tronçon, la mer à gauche), décor `_lagune` et rangées d'immeubles `_row` (façades pastel `LAGUNE_PASTELS`, 2 à 18 étages selon le quartier, tours au second rang), ligne `demo-lagune` de `DEMO_SET`, fiche de `DEMO_LIBRARY`, option `--lagune`.
- `grass_tufts.gd` : aucune touffe d'herbe sur le dallage de la ville néon (`biome_model.neon_at`, comme la lave du volcan).
- Jeu de base : 11 parcours de démonstration écrits par `openride-core demo-biomes` (12 parcours avec la piste dans les contenus de départ) ; liste verrouillée (`test_jeu_de_base.py`), captures (`captures_demo.py`), scénarios de menu `parcours_demo` et `contenus`.

| Tronçon | Abscisses | Décor |
| --- | --- | --- |
| Avenue de la Lagune | 0 à 2 370 m et 13 800 à 15 000 m | Immeubles de 3 à 10 étages des deux côtés, tours de 8 à 16 étages derrière |
| Front de mer | 2 400 à 6 000 m | Plage et mer à gauche, hôtels de 5 à 12 étages à droite |
| Port | 6 000 à 7 400 m | Entrepôts bas, butte de 5 m |
| Vieux quartier | 7 410 à 9 380 m | Maisons de ville de 2 à 4 étages, serrées, cinéma, cafés |
| Quartier des tours | 9 400 à 11 780 m | Commerces de 2 à 4 étages au pied de tours de 12 à 30 étages, sur deux rangs |
| Quartier des villas | 11 800 à 13 780 m | Maisons basses espacées, petits immeubles et parcs derrière |

Variante de recette (`--recette`, bancs) : la boucle de 5 km d'avant (avenue jusqu'à 1 370 m, front de mer de 1 400 à 2 900 m, port jusqu'à 3 800 m, vieux quartier jusqu'à 4 930 m), sans tours ni villas.

## 4. Critères d'acceptation

- [x] `test_lagune_loop` : boucle fermée de 15 km (`test_lagune_recette` : 5 km en recette), pente de −3,5 à +3,5 %, 4 à 7 m de montée par tour, toutes les tuiles en `ville_neon`, plus de 1 000 bâtiments, plage de sable, mer à gauche, aucun bâtiment côté mer.
- [x] Liste du jeu de base, fiche, captures et scénarios de menu à jour (`test_jeu_de_base.py`, `test_biome_demo_world.py`).
- [x] Banc des menus au cloud : `parcours_demo` et `contenus` (voie clavier).
- [ ] Banc PC `low`, `medium`, `high` dans les budgets, 0 contact (fil de fusion).
- [ ] Captures validées par le propriétaire.

## 5. Limites connues

- Pas de vrai pont : la « bosse » du port est une butte du terrain.
- Pas encore d'enseignes, de mobilier, de voitures garées ni de passants en nombre (lots NV4 et NV5) ; pas de route mouillée (après la mesure NV0).
- Les joueurs déjà installés reçoivent le parcours par « Réglages › Contenus › Contenus de départ ».
