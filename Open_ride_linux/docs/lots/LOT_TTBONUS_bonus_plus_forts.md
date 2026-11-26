# Lot TT-BONUS – Bonus plus longs et plus forts, temps gagné affiché

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série TT : Plume, Casque aéro et Puissance à 30 s et plus forts ; « Casque aéro : +4,2 s » à la fin du bonus (révision IPC 1.41) | Python + GDScript | TT8 | Petite | **En revue** (PR à fusionner sur « go » du propriétaire) |

Série TT (bonus tactiques, version 4.0). Source : essai vélo du propriétaire du 22 novembre (« essai 4 : bonus trop courts et trop faibles ») et fiche de cohérence du level design au home trainer du même jour, §3 bis (hors dépôt, profils synthétiques, FTP fictive 250 W).

## 1. Objectif

Qu'un bonus se sente sur le vélo : 4 à 5 s gagnées sur le terrain où il a du sens, loin du bruit naturel du trainer (0,7 s par minute), comme un objet du Grand Prix. Le dire au joueur à la fin du bonus.

## 2. Constat (essai du 22 novembre)

Gain calculé 60 s après l'activation pour un cycliste d'exemple à 140 W, valeurs d'avant le lot :

| Bonus | Réglage d'avant | Plat | +3 % | −3 % |
| --- | --- | --- | --- | --- |
| Casque aéro | CdA × 0,75, 15 s | 1,2 s | 0,4 s | 1,7 s |
| Puissance | × 1,10, 15 s | 0,5 s | 1,2 s | 0,2 s |
| Plume | masse × 0,9, 20 s | 0,2 s | 1,5 s | −0,6 s |

## 3. Travail fait

- `powerups.py` `DEFAULT_TABLE` : Plume masse × 0,8, Casque aéro CdA × 0,6, Puissance × 1,20, chacun 30 s (bornes `factor_bounds` inchangées). Les deux jeux (`classiques` et `tactiques`) tirent ces bonus : les valeurs valent pour les deux. Les bonus tactiques (Enclume, Aspiration +, Échappée, Rouleau) ne changent pas.
- Temps gagné : pendant un bonus de masse, de CdA ou de puissance, une ombre sans bonus part du même point à la même vitesse et roule avec la même puissance mesurée, la même pente, le même abri et le même vent (`PowerUps.track_gain`, appelé par la séance juste après le pas du cycliste). À la fin du bonus, l'avance prise plus ce que l'élan rapporte encore pendant 60 s (simulation courte, une fois par bonus, sans entrée-sortie) est convertie en secondes. Ligne `Bonus fini : Casque aéro, +4,2 s.` au journal du core.
- Contrat IPC, révision 1.41 (provisionnelle, après les 1.37 à 1.40 réservées) : champ facultatif `powerup.gain` (`{kind, gain_s}`) pendant 6 s. Un engine plus ancien l'ignore.
- HUD (`segment_hud_model.gd`, `hud_view.gd`) : « Casque aéro : +4,2 s » à la place de la ligne du bonus actif pendant 6 s, en vert (gagné) ou en rouge (perdu, « Plume : −0,6 s »), toujours écrit en mots.
- Banc `tools/bonus_bench.py` : cible 3,5 à 7 s pour la Plume, le Casque et la Puissance (1,5 à 2,5 s gardée pour les bonus tactiques), colonne « Cible ».

## 4. Résultats (cloud, physique du core)

Gain à 140 W, 84 kg, sur la séance réduite des tests (`core/tests/test_tt_bonus_gain.py`) :

| Bonus | Plat | +3 % | +6 à 8 % |
| --- | --- | --- | --- |
| Casque aéro × 0,6, 30 s | **4,2 s** | 2,1 s | 0,3 s |
| Puissance × 1,20, 30 s | 2,2 s | **4,7 s** | 5,8 s |
| Plume × 0,8, 30 s | 0,5 s | **4,9 s** | 7,1 s |

Banc `bonus_bench` (50 passages, graine 8, cyclistes de 200 à 320 W de FTP) : médianes Plume 5,98 s, Casque 4,29 s, Puissance 5,29 s ; bonus tactiques inchangés dans 1,5 à 2,5 s.

## 5. Critères d'acceptation

1. Tests du core et de l'engine verts (CI), dont `test_tt_bonus_gain.py` et `test_segment_hud_model.gd`.
2. Captures du bloc bonus (bonus actif de 30 s, temps gagné) validées par le propriétaire.
3. Essai vélo du propriétaire : d'abord avec la surcharge `~/OpenRide/powerups.toml` (mêmes valeurs, sans attendre la fusion), puis le temps gagné affiché après la fusion.

## 6. Fichiers touchés

`core/src/openride_core/powerups.py`, `classic.py`, `session.py` (un appel), `ipc_server.py`, `ipc_budget.py`, `tools/bonus_bench.py` ; `docs/contracts/ipc_v1.md`, `docs/contracts/ipc/state.schema.json` ; `engine/scripts/segment_hud_model.gd`, `hud_view.gd` ; tests du core et de l'engine ; galerie du HUD.

## Livraison

PR #1093 en revue (26 novembre 2026), branche `claude/project-thread-a4jljr`. Aucune charge PC : core pur et HUD, CI et cloud.
