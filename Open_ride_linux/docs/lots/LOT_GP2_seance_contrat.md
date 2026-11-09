# Lot GP2 – Branchement dans la séance, réglages et contrat

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : mode `grandprix` dans la séance, réglages `[grandprix]`, champ `state.gp`, message `gp_hit`, `summary.gp`, colonne du mode au plan des boutons | Python | GP1 | Moyenne | Livré le 8 novembre (PR #774, version 4.0) |

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

## 5. Livraison (7 novembre 2026)

- Séance : `start` avec `mode: "grandprix"` (bots à profil d'après `grandprix.opponents` et `bots.level_pct`, sur une boucle `grandprix.laps` tours, sinon `grandprix.distance_km`) ; refus `bad_args` en ERG, avec `ftp_test`, `plan_day`, un argument `bots`, en monde ouvert, sur un parcours en ligne trop court ou avec des réglages hors bornes ; `set_ride_mode` vers l'ERG : `busy`.
- Boutons : Z court utilise l'objet ; A court change de voie seulement quand `gp.pick` est vrai (sinon vue) ; flèches gauche et droite changent toujours de voie ; A long revient au placement automatique (sinon vue par défaut). Voie forcée : placement de l'abri (lot AS2) au centre de la voie.
- Vitesse virtuelle du cycliste et des bots fixée par `GrandPrixMode.step` ; pente envoyée calculée avant, sans les objets ; vent contraire appliqué à la physique seulement, autour du pas.
- Réglages `grandprix.opponents` (2 à 4), `grandprix.laps` (1 à 5), `grandprix.distance_km` (5 à 30), `grandprix.chaos` (`soft`, `normal`, `wild`), `grandprix.box_every_m` (1 000 à 3 000 m par 500 m ; le plan disait `box_every_km`, réécrit en mètres au pas des autres réglages, 2,5 km ajouté).
- Objets : commandes génériques `list_mode_options` et `set_mode_option` (message `mode_options`, code `mode_option_invalid`), section `[items]` de `~/OpenRide/grandprix.toml` (commentaires gardés, `config_edit.update_toml`) ; commandes du Mode WTF gardées en alias une révision.
- Contrat : révision 1.7 (`state.gp`, `bots[].item` et `bots[].fx`, `summary.gp`, `gp_hit`, `mode_options`), schémas, colonne du mode au §7.1 de la spécification ; journal `gp_start`, `gp`, `gp_summary`.
- Budget : pire trame 3 558 octets avec 4 adversaires et `devices` ; avec 11 (lot GP10), 4 032 octets sans `devices`, mais la trame qui porte `devices` perd ses bots : à régler au lot GP10.
- Tests : `core/tests/test_grandprix_session.py` (critères 1, 2 et refus), `test_ipc_budget.py` (critère 3), suite complète du core (critère 4). L'engine reste en 1.6 jusqu'aux lots GP7 et GP8.
