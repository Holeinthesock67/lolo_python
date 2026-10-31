# Lot CT6 – Crédits gagnés en tête et capacités payées

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CT : crédits gagnés en tête et capacités payées | Python | TT2 à TT5 (4.0), Y10, CT1 | Moyenne | Prêt (version 5.0) |

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`.

## 1. Objectif

Remplacer le hasard des bonus par une économie : rouler devant pour les autres remplit une jauge de capacités (25, 50 et 100 %), qui paie les effets du catalogue de la 4.0 (série TT). Décision du 29 octobre : les effets viennent de la 4.0.

## 2. À lire

1. `docs/5.0/PLAN_SERIE_CT.md` (décisions du propriétaire du 29 octobre), `docs/SPECIFICATION_GENERALE.md` §6.1 et §7.1, `docs/contracts/ipc_v1.md`.
2. Plan de la série TT (4.0, PR #571) et cahiers TT2 à TT5 (TT2 modèle unique, TT3 Aspiration +, TT4 Échappée, TT5 Rouleau) ; code `powerups.py` réécrit par TT2 (modèle d'effets décrit par des données), `classic.py`, `draft.py`.

## 3. Prérequis

TT2 à TT5 (4.0) livrés ; Y10 livré ; CT1 fusionné.

## 4. Travail demandé

- Module pur `tactical/credits.py`.
- **Gain** : le travail aérodynamique fourni pour les autres, `aéro × v × α_suiveur` intégré, quand au moins un coureur profite de l'abri du cycliste ; rien pour un coureur seul. Un relais compte à partir de 15 s en tête.
- **Paliers** : Sillage furtif (25 %) = effet `breakaway` (« Échappée ») de la 4.0, avec son refus à moins de 400 m de l'arrivée ; Bouclier d'inertie (50 %) = nouvel effet du modèle TT2 : pas de Burnout et pas de perte en virage pendant 10 s ; Overdrive aéro (100 %) = effet `aero` (CdA × 0,75) sur 20 à 25 s.
- **Boutons** : Z court déclenche la capacité la plus haute que la jauge peut payer sous 100 % ; Z long l'Overdrive. A reste aux vues et aux variantes (§7.1).
- Pas de bonus au hasard dans ce mode ; les bonus classiques (T6) restent dans le classique.
- Records : séance comptée « avec bonus » (T5).

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/tactical/credits.py`, `core/tests/test_tactical_credits.py`.
- **Modifiés :** `powerups.py` (nouvel effet par données seulement), `session.py`, `tactical/balance.toml`, ce cahier, `00_INDEX.md`.
- **Interdits :** l'engine ; aucun deuxième système de bonus.

## 6. Modifications de contrat autorisées

Aucune : les champs viennent du lot CT1.

## 7. Critères d'acceptation

1. `pytest -q` passe.
2. Cycliste seul devant pendant 5 min : jauge à 0. Avec un bot dans la roue : 15 s de relais à 300 W, jauge à 25 % (valeur réglée par CT0).
3. Z court à 60 % : Bouclier ; Z long à 100 % : Overdrive ; Z long à 90 % : refus motivé (champ `refused` de TT1).

## 8. Hors périmètre

Bots qui dépensent des crédits.
