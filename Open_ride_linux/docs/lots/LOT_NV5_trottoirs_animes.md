# Lot NV5 – Ville néon : trottoirs animés

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Passants plus nombreux en ville néon : 8 à 12 personnes par 100 m, sur le trottoir derrière les voitures garées (les voitures garées sont livrées par le lot NV4) | GDScript | NV4, P21 | Petite | **En revue** (26 novembre) |

Sixième lot du parcours « Avenue de la Lagune ».

## 1. Objectif

Les trottoirs de la ville néon sont animés : promeneurs, coureurs, enfants et personnes assises, sans jardinier ni paysan.

## 2. Contraintes

- Hors de la ville néon, placement des passants inchangé (vérifié par le test).
- Budget des passants affichés inchangé (24 / 48 / 80 selon le préréglage) : seul le nombre de personnes posées change.
- Aucune révision du contrat IPC.

## 3. Réalisation

- `passersby_model.gd` : `city_at` (règle `neon_at` de `biome_model.gd`), cases de ville à `CITY_PER_CELL` personnes, écart `CITY_EDGE_M` du bord de la chaussée, rôles `ROLES_CITY`.
- `living_decor.gd` : passe `neon_at` au modèle des passants.

## 4. Critères d'acceptation

- [x] `test_passersby_model.gd` : 35 à 60 personnes sur 500 m de ville, toutes sur le trottoir, placement inchangé ailleurs.
- [x] Capture au cloud sans erreur de script.
- [ ] Banc PC avec le lot NV4 (fil de fusion).
