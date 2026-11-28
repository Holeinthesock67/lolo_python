# Lot RL3 : essais du monde ouvert au nouveau relief, en France et hors de France

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Bancs du monde ouvert au relief IGN (France) et FABDEM (ailleurs) : pentes, sol sous la route, frontière des sources, temps de génération, captures | Python, bancs PC | RL1, RL2, #1057 | Moyenne | À faire, **version 6.0** (demande du propriétaire du 25 novembre) |

## But
Vérifier sur le PC, avant le go de RL1 et RL2, que le nouveau relief est juste partout et ne casse rien.

## Étapes (PC, cache séparé, jamais `~/OpenRide/Cache/monde`)
1. Services réels : `pytest -m network tests/test_fabdem.py tests/test_ign_rge_alti.py` (graphie des archives
   FABDEM, requêtes partielles, couche et format IGN).
2. Banc multi-zones #1057 (`scripts/file_bancs/ow_multi_zones.toml`, medium) sur la tête de la PR, puis sur main :
   - **France (IGN)** : Biarritz (ville côtière), Lyon (grande ville), Sevrier et Grenoble (montagne, forêt).
   - **Hors de France (FABDEM)** : Almería, Tromsø, Funchal.
   - **Frontière des sources** : une zone à cheval sur la frontière (par exemple autour de Genève ou de Bâle),
     scénario à ajouter, pour l'écart NGF-IGN69 / EGM2008 et la couture IGN / FABDEM.
3. Contrôles : `controle_profil_altitude` (aucune pente > 15 %, aucun changement > 4 %/10 m, aucun « saut »),
   `controle_sol_route`, gels ; pentes maximales et dénivelé comparés à main pour chaque zone ; temps de
   génération par km (demandes IGN de 1 km).
4. Captures low/medium/high de Biarritz, Lyon et d'une zone hors de France, validées par le propriétaire.

## Résultat attendu
Villes françaises sans pentes de rue fantômes (Biarritz : plus de passages à 18-21 %), relief étranger au sol nu,
aucune marche visible à la frontière des sources, temps de génération dans la marge du plan W §3.3.
