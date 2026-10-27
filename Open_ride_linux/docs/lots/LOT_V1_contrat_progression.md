# Lot V1 – Contrat : progression, Garage et avatar (IPC, ajouts compatibles)

## 1. Objectif

Décrire dans le contrat IPC tout ce que l'engine doit savoir ou demander pour la progression de la série V : niveau, pièces, équipement et avatar choisis au démarrage, bilan d'expérience en fin de séance, catalogue du Garage, achats et choix depuis le menu. Le core reste le maître : il calcule, l'engine affiche et demande.

**Lot interne (décision du propriétaire) :** il change le contrat ; il est validé par le propriétaire avant tout lot qui l'utilise (V6 à V9, V11).

## 2. À lire

1. `docs/2.0/PLAN_SERIE_V.md` (tout), `docs/contracts/ipc_v1.md` §4, §5 et §8, schémas `docs/contracts/ipc/hello_ack.schema.json`, `cmd.schema.json`, `routes.schema.json` (messages en parties).
2. Cahiers `LOT_V2_moteur_experience.md`, `LOT_V3_catalogue_equipement.md`, `LOT_V3b_pieces.md`, `LOT_V4_profil_local.md` : noms des champs côté core (`XpGains`, `LevelInfo`, identifiants d'équipement, emplacements).
3. `docs/2.0/PLAN_SERIE_T.md` §3.5 (message `segment_result`, révision partagée) et `docs/2.0/PLAN_SERIE_R.md` (contrat R1).

## 3. Prérequis

- **Révision 1.4 (V-Q4, décision D2 de l'audit IPC du 26 octobre, validée par le propriétaire) :** la 1.2 est prise par Q1 et N13, P1 passe en 1.3 ; R1, T1 et V1 forment ensemble la révision 1.4, en un seul lot de contrat (même fichier `ipc_v1.md`).
- P1 livré (il fixe la révision précédente).

## 4. Travail demandé

### 4.1 `hello_ack.config.progression` (facultatif)

Objet présent dès que le core connaît la progression (absent sinon : l'engine n'affiche rien de la série V) :

| Champ | Type | Sens |
| --- | --- | --- |
| `level` | entier 1 à 50 | Niveau actuel |
| `xp` | entier | Expérience totale |
| `xp_level_start`, `xp_next_level` | entier, entier ou `null` | Seuils du niveau actuel et du suivant (`null` au niveau 50) |
| `coins` | entier ≥ 0 | Solde de pièces |
| `equipped` | objet | Identifiant choisi par emplacement : `frame`, `wheels`, `helmet`, `kit`, `socks`, `glasses` |
| `avatar` | objet | Réglages de l'avatar (§4.4) |
| `lives` | entier ≥ 0 | Vies du mode Cyber-Rogue en réserve (série R) |

### 4.2 Message `xp_result` (core vers engine, en fin de séance)

Message dédié (décision D7 de l'audit IPC, validée par le propriétaire ; nommé `xp_result` pour ne pas le confondre avec l'entier `progression.xp`). Envoyé quand `session_state` passe à `FINISHED`, après le `summary`, puis répété une fois par seconde tant que la séance reste `FINISHED` (au plus 10 fois), comme `hello` se répète : une perte UDP ne fait pas disparaître le bilan.

Champs : `eligible` (booléen), `reason` (`too_short`, `replay`, `simulated`, `imported` ou `null`), `gains` (liste de `{source, points}` dans l'ordre du plan §2.1 : `distance`, `climb`, `erg`, `erg_bonus`, `segment`, `segment_pr`, `jersey`, `rogue`, `rogue_boss`), `total`, `level_before`, `level_after`, `xp_total`, `xp_next_level`, `coins_gained`, `coins_total`, `unlocked` (identifiants d'équipement devenus achetables), `challenges` (défis réussis dans la séance : `{id, name, reward_item}`), `equipment_gain_s` (temps gagné ou perdu par l'équipement sur la séance, négatif si gagné, ou `null`).

Taille : 1 400 octets au plus (au plus 8 déblocages et 4 défis listés, `more` vrai au-delà).

### 4.3 Commandes et catalogue du Garage

| `name` | `args` | Effet |
| --- | --- | --- |
| `list_garage` | `{}` | Demande le catalogue ; réponse `garage` en parties, comme `routes` |
| `equip` | `{ "slot": chaîne, "item_id": chaîne }` | Choisit une pièce possédée ; `error` `item_locked` sinon |
| `buy` | `{ "item_id": chaîne }` | Achète une pièce débloquée ; `error` `not_enough_coins` ou `item_locked` |
| `set_avatar` | `{ "avatar": objet }` | Remplace les réglages de l'avatar (§4.4) ; valeurs hors bornes : `error` `avatar_invalid` |

- Hors séance seulement (`IDLE`, `READY`) : sinon `error` `busy` (code existant de la révision 1.2).
- Après `equip`, `buy` ou `set_avatar` réussi, le core envoie un message dédié `progression` (`v`, `request_cmd_id` et les champs de l'objet du §4.1) : l'engine n'a pas à recalculer. Pas de nouveau `hello_ack`, que l'engine traite comme la fin de la poignée de main (décision D7 de l'audit IPC).
- Message `garage` : `v`, `request_cmd_id`, `part`, `parts`, `items`. Élément : `id`, `slot`, `name`, `state` (`locked`, `buyable`, `owned`, `equipped`), `level_required`, `price`, `challenge` (texte du défi qui l'offre, ou `null`), `mass_delta_kg`, `cda_delta_pct`, `terrain` (`flat`, `rolling`, `climb`, `all`), `look` (identifiant de rendu pour V7).
- Nouveaux codes d'erreur : `item_locked`, `not_enough_coins`, `avatar_invalid`.
- Élément de `routes` : champ facultatif `terrain` (`flat`, `rolling`, `climb` ou `null`, calculé par le core, lot V3 §4.3) pour le conseil d'équipement de l'écran « Prêt » (V8).

### 4.4 Avatar

Objet `avatar` : `height` (`S`, `M`, `L`, `XL`), `build` (`slim`, `medium`, `strong`), `skin` (indice 0 à 7 d'une palette fixe), `hair` (style 0 à 5), `hair_color` (0 à 7), `kit_primary`, `kit_secondary` (indices 0 à 15 d'une palette fixe), `number` (entier 0 à 999), et deux seuils de la position en danseuse lus dans `[avatar]` de `config.toml` (lot V6) : `standing_grade_pct` (pente, 8 par défaut) et `standing_power_pct` (% de la FTP, 150 par défaut), transmis dans `hello_ack` mais non modifiables par `set_avatar`. Choix par listes et palettes : tout se règle au Click. Aucune mesure réelle (taille, masse) du cycliste n'y figure.

### 4.5 Champ ajouté à `segment_result` (série T)

`equipment_gain_s` (nombre ou `null`) : temps gagné ou perdu par l'équipement sur le passage. Ajouté par T1 si T1 passe après V1, sinon par V1.

### 4.6 Livrables

`ipc_v1.md` (§4, §5, journal des changements), schémas `hello_ack` et `cmd`, nouveaux `garage.schema.json`, `progression.schema.json` et `xp_result.schema.json`, trames d'exemple, tests de contrat (`core/tests/test_contract_ipc.py`) : taille maximale de `xp`, d'un `hello_ack` complet et d'une partie de `garage`.

## 5. Fichiers concernés

- **Modifiés :** `docs/contracts/ipc_v1.md`, `docs/contracts/ipc/*.schema.json` cités, `core/tests/test_contract_ipc.py`, `docs/SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `docs/contracts/ipc/garage.schema.json`, `progression.schema.json`, `xp_result.schema.json`.
- **Interdits :** le code du core et de l'engine (V11 et V6 à V9 les branchent).

## 6. Modifications de contrat autorisées

Celles du §4, toutes compatibles (`v` reste 1).

## 7. Critères d'acceptation

1. Les schémas valident les trames d'exemple ; un `hello_ack` sans `progression` reste valide (rétrocompatibilité).
2. `xp_result` le plus long possible (8 déblocages, 4 défis, 9 sources) tient dans 1 400 octets ; une partie de `garage` dans 60 000.
3. Le propriétaire valide le contrat (V-Q4 et D7 sont déjà tranchés).

## 8. Hors périmètre

Le calcul (V2, V3, V3b, V4), le branchement dans la séance (V11), l'affichage (V6 à V9).
