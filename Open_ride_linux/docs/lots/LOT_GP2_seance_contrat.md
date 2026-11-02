# Lot GP2 – Branchement dans la séance, réglages et contrat

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : mode `grandprix` dans la séance, réglages `[grandprix]`, champ `state.gp`, message `gp_hit`, `summary.gp`, colonne du mode au plan des boutons | Python | GP1 | Moyenne | Prêt (version 4.0 proposée) |

Série GP (mode « Grand Prix des objets », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_GP.md`.

## 1. Objectif

Brancher `GrandPrixMode` dans la séance, enregistrer les réglages et publier le contrat, sans rien changer aux autres modes.

## 2. À lire

`docs/4.0/PLAN_SERIE_GP.md` §4, §7 et §8.1 ; `core/src/openride_core/session.py` (branchement du Mode WTF) ; `core/src/openride_core/settings.py` ; `docs/contracts/ipc_v1.md` ; `docs/SPECIFICATION_GENERALE.md` §6.1 et §7.1.

## 3. Travail demandé

- `start` avec `mode: "grandprix"` ; `bad_args` en ERG, avec un fantôme ou un argument `bots` ; `set_ride_mode` répond `busy`.
- Z court relayé à `use`, A court, A long et flèches gauche et droite relayés à `set_lane` quand le choix de voie est affiché, sinon vues comme aujourd'hui.
- Effets appliqués à la vitesse virtuelle du joueur et des bots ; pente envoyée inchangée (seuls l'abri et le vent existants passent, avec leurs rampes et leur borne).
- Réglages `[grandprix]` par `set_setting` ; objets activés selon la question 4 du §10 du plan (commandes génériques `list_mode_options` et `set_mode_option` par défaut, alias WTF gardés une révision).
- Contrat : première révision libre à la fusion ; `state.gp`, `bots[].item` et `bots[].fx`, `gp_hit`, `summary.gp` ; colonne du mode au §7.1 de la spécification ; journal `gp`.

## 4. Critères d'acceptation

1. Séance simulée de 3 tours avec 4 bots, sans erreur ; FIT et journal avec la puissance mesurée intacte.
2. Test : la pente envoyée d'une séance avec objets est identique, au pas près, à celle d'une séance sans objets sur la même route et à la même vitesse virtuelle d'abri.
3. `python -m openride_core.ipc_budget` : pire trame sous 4 096 octets avec 4 puis 11 bots.
4. Les séances classique, WTF et Cyber-Rogue restent identiques au bit près (tests existants verts).
