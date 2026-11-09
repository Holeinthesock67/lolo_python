# Lot N18 – Bots réglés depuis les menus

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| 1.x série N : bots réglés depuis les menus (écran Prêt et écran de pause) | Python + GDScript | O3, O4, O7, O32, O35, PL1 | Moyenne | En PR : interne (contrat et menus), **version 1.x**, contrat IPC révision 1.9 |

## 1. Objectif

Régler les bots de la séance depuis les menus au lieu de `config.toml` ou de la ligne de commande : nombre, puissance de chacun, fantôme, avant la séance et pendant la séance dans l'écran de pause. Demande du propriétaire du 27 octobre (décision D11 de l'audit de cohérence) : ce réglage passe par les menus, pas par un geste du Click. Version 1.x.

## 2. Mise à jour du 8 novembre 2026

Le cahier date du 27 octobre. Depuis, d'autres lots ont livré une grande partie de la demande :

| Partie de la demande | Livré par | État au 8 novembre |
| --- | --- | --- |
| Bots choisis avant la séance : « Bot 1 » à « Bot 4 » (puissance constante, % de la FTP ou profil), fantôme | Écran **Prêt** (lots O7 et O35), argument `bots` de `start` (révision 1.3) | Fait |
| Nombre de bots | « Peloton : 4, 8 ou 11 bots » de l'écran Prêt (lot PL1, révision 1.6) : 11 bots et un fantôme au plus | Fait |
| Niveau des bots à profil | Réglage « Niveau des bots » (`bots.level_pct`, lot T13) dans Réglages › Séance | Fait |
| Bots gardés d'une séance à l'autre | Derniers choix du profil (lot O32, `derniers_choix.json`, `hello_ack.config.last_choices.bots`) : l'écran Prêt repart des bots de la dernière séance | Fait |
| Bots changés pendant la séance | Écran de pause : **ce lot** | Fait dans la PR du lot |
| Événement au journal | Ligne `bots` du journal : **ce lot** | Fait dans la PR du lot |

**Réglages et `config.toml`.** Le cahier du 27 octobre demandait des entrées « Bots » dans Réglages, écrites dans `config.toml`. L'écran Prêt et les derniers choix du profil font déjà ce travail : les bots se règlent là où on prépare la séance et reviennent à la séance suivante, par profil de joueur. Une deuxième liste dans Réglages et `config.toml` ferait deux endroits pour le même choix, avec une règle de priorité à inventer : c'est une exception que la spécification générale évite (principe du 27 octobre). Le lot ne l'ajoute donc pas : choix du propriétaire du 8 novembre (« Écran Prêt + derniers choix »). Le « Niveau des bots » reste le seul réglage des bots dans Réglages, parce qu'il vaut pour tous les bots à profil, y compris ceux du Dernier survivant et du Grand Prix.

## 3. À lire

1. `docs/SPECIFICATION_GENERALE.md` §5.1 (exigence 1.x-UI-2) et §7.1 ; `docs/SRS_v1.1.md` §13 (bots) ; cahiers [N9](LOT_N9_bots_core.md), [O7](LOT_O7_affichage_bots.md), O35, O32 et [PL1](LOT_PL1_peloton.md).
2. Code : `core/src/openride_core/bots.py` (`bots_from_menu`, `merge_menu_bots`), `session.py` (`_set_bots_paused`, `_journal_bots`), `last_choices.py` ; engine : `menu_model.gd` (écran Prêt et écran de pause), `main.gd`, `ipc_client.gd`.

## 4. Travail fait

- **Écran de pause (engine) :** en session libre, ERG et mode WTF, l'écran de pause reprend sous la difficulté et les lignes du mode les lignes de l'écran Prêt : « Bot 1 : … » à « Bot n : … » (une ligne vide sous le dernier bot, quatre au plus), « Fantôme de la dernière séance » et « Peloton ». Elles se changent comme sur l'écran Prêt (A maintenu : choix suivant ; « aucun » retire le bot). Rien n'est envoyé tant qu'on reste en pause : à la reprise (**Reprendre** ou **Y**), si une ligne a changé, l'engine envoie `set_bots` avec la liste entière, puis `resume`. Pas de lignes de bots en Cyber-Rogue ni en Dernier survivant (le core compose le plateau). Les bots choisis deviennent aussi les derniers choix de l'écran Prêt.
- **Contrat (révision 1.9) :** commande `set_bots` `{ "bots": [...] }`, même liste que l'argument `bots` de `start` (révisions 1.3 à 1.6 : bots constants en watts ou en % de la FTP, bots à profil, fantôme ; 11 bots et un fantôme au plus), acceptée en `PAUSED` seulement. Hors pause, en Cyber-Rogue, en Dernier survivant et au Grand Prix : `error` `busy`. Liste refusée : `error` `bot_invalid`, rien ne change. La décision D6 de l'audit IPC reste vraie : `set_setting` répond `busy` pendant la séance, la commande dédiée suit le modèle de `set_difficulty` et de `set_ride_mode`. Numéro : 1.7 est la révision du Grand Prix et du vélodrome, 1.8 est réservée à la collection de cartes (lot BC2, PR #758) ; N18 prend la 1.9, première libre.
- **Core :** `bots.merge_menu_bots` rapproche la liste demandée des bots en cours : un bot demandé à l'identique garde sa place et son id ; un bot constant dont seule la puissance change (même rang) garde le coureur de ce rang, nouvelle puissance tout de suite ; le fantôme demandé garde le fantôme en cours. Un bot nouveau part à la hauteur et à la vitesse du cycliste (rangé par deux comme au départ, `draft.start_grid`), avec un id jamais pris dans la séance (chronos des segments, écarts et maillots suivent les ids) ; un fantôme nouveau part au temps de la séance ; un bot à profil nouveau est calibré comme au départ (lot T13). Un bot non repris disparaît. Le choix est noté dans les derniers choix du profil (lot O32).
- **Journal :** ligne `{"kind": "bots", "ts", "t", "reason": "start" | "set_bots", "bots": [{id, name, kind, power_w | profile, level_pct}]}` au départ d'une séance qui a des bots et à chaque `set_bots` accepté (format dans `journal.py`) ; absente du FIT ; les lectures qui ne la connaissent pas l'ignorent.

## 5. Fichiers concernés

- **Modifiés :** `bots.py`, `session.py`, `classic.py` (bots ajoutés chronométrés depuis leur place), `journal.py`, `recorder.py`, `docs/contracts/ipc_v1.md`, `docs/contracts/ipc/cmd.schema.json`, `ipc_server.py` (révision annoncée) ; engine : `menu_model.gd`, `main.gd`, `ipc_client.gd` ; tests du core (`test_set_bots_n18.py`) et de l'engine (`test_menu_model.gd`, `test_free_erg_menu.gd`) ; spécification générale, guide, suivi.

## 6. Modifications de contrat autorisées

Commande `set_bots` (acceptée en `PAUSED`), révision 1.9 ; ligne `bots` du journal.

## 7. Critères d'acceptation

1. Tests du core et de l'engine au vert.
2. Écran Prêt : trois bots à 180, 220 et 260 W choisis, présents à la séance suivante (derniers choix du profil, lot O32 ; déjà couvert par `test_derniers_choix.py` et `test_menu_model.gd`).
3. Écran de pause : un bot retiré n'est plus dans `bots` à la trame suivant la reprise ; le journal le note (`test_set_bots_n18.py`).
4. Tout se règle au Click selon le §7.1 et au clavier (A maintenu sur la ligne, Y ou Reprendre pour reprendre).
5. Captures de l'écran de pause avec ses lignes de bots en `low`, `medium` et `high`, validées par le propriétaire avant la fusion.

Aucune recette sur le vélo : les critères se vérifient en séance simulée.

## 8. Hors périmètre

Bots à profil choisis un par un sur l'écran de pause avec leur niveau propre (la liste `BOT_CHOICES` de l'écran Prêt reste la même) ; liste de bots dans Réglages et `config.toml` (voir §2) ; bots du Dernier survivant et du Grand Prix (composés par le core).
