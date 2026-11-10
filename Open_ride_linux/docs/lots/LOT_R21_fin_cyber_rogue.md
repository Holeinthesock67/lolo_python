# Lot R21 – Fin du Cyber-Rogue : sons de la purge et du coffre, achat d'une vie

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Fin du Cyber-Rogue : événement `purge` et son de la purge, son du coffre de fin, achat d'une vie depuis le départ du mode (contrat révision 1.14) | Python, GDScript | R9, R18, R19 | Petite | En revue le 10 novembre, **version 2.0** |

## 1. Objectif

Demande du propriétaire du 10 novembre : terminer le mode Cyber-Rogue avant l'essai sur le vélo du 11 novembre. Ce lot ferme les trois manques laissés par R18 et R19 (cahier R19 §4) :

- la balise de purge réussie et le coffre de fin avaient leur son, mais rien ne le déclenchait ;
- `coins.buy_life` existait, mais aucune commande ne permettait d'acheter une vie.

## 2. À lire

`docs/lots/LOT_R9_progression_permanente.md` (§4.2 coffres et vies), `LOT_R18_bruitages_rogue.md` (§4.1), `LOT_R19_branchement_final.md` (§4), `docs/contracts/ipc_v1.md` (révision 1.14).

## 3. Travail fait

- **Purge.** Le core ajoute l'événement `purge` à `rogue.events` quand Z court tombe sur une balise de purge pendant un piratage, qui s'arrête (`combat.py`). Un appui sur la balise sans piratage ne donne rien. L'engine joue `rogue_purge` (`EVENT_SOUNDS`).
- **Coffre de fin.** L'engine joue `rogue_chest` à l'entrée dans le retour au calme (`COOLDOWN`), une seule fois, comme les autres sons dérivés d'un changement de phase. C'est le moment où l'or de la run devient des pièces (R9 §4.2).
- **Achat d'une vie.**
  - Le core accepte la commande `buy_life` hors séance (`garage.buy_life`). Il répond par le message `progression`, avec `lives` et `coins` à jour. Refus possibles : `not_enough_coins`, `item_locked` (réserve pleine) ou `busy`.
  - `hello_ack.config.rogue` porte aussi `life_price` et `max_lives`.
  - L'écran de départ du mode montre « Vies : N / 3 ». S'il reste de la place et que les pièces suffisent, valider demande « Acheter une vie pour P pièces ? Solde après : S ». Un refus s'affiche sous « Lancer ».
- **Contrat :** révision 1.14, avec ses ajouts compatibles (§8 de `ipc_v1.md`, schémas `state`, `cmd` et `hello_ack`). Le core annonce `rev` « 1.14 ».

## 4. Tests

- `core/tests/test_rogue_r21_finitions.py` :
  - `purge` émis pendant un piratage, et pas sans piratage ;
  - `purge` accepté par le schéma ;
  - achat d'une vie : vies, pièces, `hello_ack` et `progression` ;
  - refus en réserve pleine et sans pièces ;
  - commande valide.
- `engine/tests/unit/test_rogue_sound_model.gd` : son de la purge, coffre à l'entrée dans `COOLDOWN`, une seule fois.
- `engine/tests/unit/test_rogue_menu_model.gd` :
  - élément « Vies » et texte de la confirmation ;
  - mise à jour par `progression` ;
  - pièces insuffisantes et réserve pleine ;
  - pas d'élément sans `life_price`.

## 5. Reste au propriétaire

Sur le vélo le 11 novembre : le ressenti du mode (recette R14, rejouée sur `main`). L'écoute du coffre et de la purge se fait pendant cette run.

## Livraison

En revue le 10 novembre.
