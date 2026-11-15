# Lot PK2 – Pentes des lacets fidèles dans le pack « Cols célèbres »

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Pentes des lacets fidèles aux valeurs connues dans les cols du pack (lissage du profil plus fort dans les virages serrés), pack reconstruit sur le PC | Python | O16, PK1 | Petite | À faire, **version 5.0** (décision du propriétaire du 15 novembre) |

## 1. Objectif

À l'essai J4 du 15 novembre (Alpe d'Huez, 5/5), la pente affichée montait à 13–14 % dans les premiers lacets, alors que les valeurs connues sont de 10 à 11,5 %. La trace lissée sur 300 m (`GAIN_SMOOTH_M`, `route_recipe.smooth_profile`) donne encore 11 à 13 % sur 500 m entre 1,75 et 2,25 km, et un pic de 18,8 % sur 100 m vers 9,7 km. En cause : le MNT à 30 m, qui voit le talus à chaque virage. Le propriétaire a choisi de corriger plus tard, en 5.0.

## 2. Travail demandé

- Mesurer, sur les 21 cols du paquet, les pentes sur 100 m et 500 m face aux valeurs publiées (Alpe d'Huez, Stelvio, Zoncolan et Angliru au moins).
- Renforcer le lissage là où la trace tourne fort (lacets), sans aplatir les vraies rampes : lissage adapté à la courbure, ou fenêtre plus large dans les virages serrés. Garder le contrôle à ± 5 % de la longueur et du dénivelé.
- Tests dans `compiler/tests/test_route_recipe.py` : profil synthétique en lacets avec talus, dont la pente lissée reste dans la tolérance.

## 3. Recette PC (file du PC)

Reconstruire le paquet (`scripts/build_pack_base.sh`, environ 30 min), puis `pack_bundle verify` et les bancs low, medium et high sur Stelvio, Ticlio et Hakone. Réinstaller ensuite les cols du profil : les traces du paquet changent d'empreinte et ne remplacent pas celles déjà installées (règle PK1-3) ; voir le script de ménage du 14 novembre. Enfin, 10 min sur l'Alpe d'Huez, avec la pente affichée dans les premiers lacets.
