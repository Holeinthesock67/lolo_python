# Lot CT4 – Catapulte cinétique : charge dans la roue et déclenchement

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CT : catapulte cinétique : charge dans la roue et déclenchement | Python | AS2, CT2 | Moyenne | Prêt (version 5.0) |

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`.

## 1. Objectif

Rester dans la roue charge un condensateur ; une relance franche le libère en une impulsion de vitesse de 3 s. Décision du 29 octobre : la charge est proportionnelle à l'abri reçu (et non une zone de 0,5 à 1,5 m, trop étroite sur un home trainer) et le déclencheur est en pourcentage de la FTP.

## 2. À lire

1. `docs/5.0/PLAN_SERIE_CT.md` (décisions du propriétaire du 29 octobre), `docs/SPECIFICATION_GENERALE.md` §6.1 et §7.1, `docs/contracts/ipc_v1.md`.
2. Cahiers `LOT_P3_aspiration_bots.md`, `LOT_AS2_zone_laterale_placement.md`, `LOT_T6_bonus.md` ; code `draft.py`, `powerups.py`, `session.py`.

## 3. Prérequis

AS2 (position latérale) et CT2 livrés.

## 4. Travail demandé

- Module pur `tactical/catapulte.py`.
- **Charge** : `sling_pct` augmente de `100 × α / 0,40 / 15` % par seconde (pleine en 15 s roue dans la roue, en 30 s environ à 3 m), descend de 10 %/s hors abri ; vidée si le cycliste passe devant.
- **Déclencheur** : charge pleine et hausse d'au moins `sling_jump_pct` (50 %) de la FTP sur 2 s, tenue au moins 1 s, sur la puissance mesurée. Ignoré dans les 5 s qui suivent une reconnexion du trainer et pendant un segment suspendu.
- **Effet** : puissance prise en compte × `sling_boost` (1,25 proposé) pendant 3 s, comme le bonus « puissance » de T6 ; jamais au journal ni au FIT ; aucun effet sur la pente envoyée.
- **Intensité des relances** (`soft`, `normal`, `strong` : 30, 50, 70 % de la FTP).
- **Densité** : une catapulte toutes les 60 s au plus.
- Les bots ont la même catapulte (même module).

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/tactical/catapulte.py`, `core/tests/test_tactical_catapulte.py`.
- **Modifiés :** `session.py`, `bots.py`, `tactical/balance.toml`, ce cahier, `00_INDEX.md`.
- **Interdits :** l'engine, `draft.py` (lecture seulement).

## 6. Modifications de contrat autorisées

Aucune : les champs viennent du lot CT1.

## 7. Critères d'acceptation

1. `pytest -q` passe.
2. Roue dans la roue (α 0,40) : pleine en 15 s ; à 3 m (α 0,20) : pleine en 30 s.
3. Pic de +50 % de la FTP en 2 s, charge pleine : impulsion de 3 s ; même pic charge à 90 % : rien.
4. Coupure simulée (0 W pendant 3 s puis retour) : aucun déclenchement.
5. Puissance du journal identique avec et sans catapulte.

## 8. Hors périmètre

Rétro-radar et parade (CT5) ; affichage (CT10).
