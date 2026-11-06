# Lot WTF7 – Engine : HUD des défis, surprise du chef, bilan et sons

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série WTF : engine, HUD des défis, surprise du chef, bilan et sons | GDScript | WTF2, WTF4 | Moyenne | En PR le 6 novembre (version 2.0) : HUD, invite du chef et bilan livrés le 31 octobre, sons en PR |

Série WTF (mode « What the fuck », demande du propriétaire du 29 octobre 2026). Plan de la série : `docs/2.0/PLAN_SERIE_WTF.md`.

## 1. Objectif

HUD des micro-défis (défi, cible, barre de progression, résultats), des œufs (œufs restants, distance) et de la surprise du chef (tandem, cloche, plat, refus par Z, tempo de la musette, hauteur du soufflé, piment qui brûle) ; points WTF ; bilan de fin de séance (`summary.wtf`) ; sons et jingles (bus « Events »).

## 2. Critères d'acceptation

1. Tests Godot passent ; guide d'utilisation mis à jour (Z court refuse le plat).
2. Captures montrées au propriétaire avant fusion.

## 3. Livraison partielle (30 octobre)

- `engine/scripts/wtf/wtf_hud_model.gd` (sans nœud) et `wtf_view.gd` (enfant du HUD) : bandeau du gag sous le panneau central (nom, temps restant, points ; « prochain gag dans … » entre deux), carte du gag (effondrement, fromage, micro-défis, œufs, tempête, plats du chef), invite « Z : NON MERCI, CHEF ! » pendant la révélation, Katamari et horloge à gauche ; style cartoon des maquettes (bord encre, ombre décalée, couleurs vives).
- `summary_view_model.gd` : lignes du bilan `summary.wtf` (points, gags joués, Katamari, pas de records).
- Tests : `engine/tests/unit/test_wtf_hud_model.gd`.
- Reste : sons et jingles (bus « Events »), captures montrées au propriétaire.

## 4. Livraison des sons (6 novembre, en PR)

- `engine/scripts/wtf/wtf_sound_model.gd` (sans nœud) : compare `state.wtf` d'une trame à l'autre et rend les sons à jouer, au plus deux par trame, rien à la première trame du mode :
  - un son par début de gag (Lune, Jupiter, monde à l'envers, effondrement, fromage, micro-défis, œufs, vélo minuscule, tornade, caméras, chef) ;
  - pendant le gag : cloche du chef, œuf cassé, écrasé par le fromage, manche de micro-défi gagnée ou perdue ;
  - fin du gag : arpège avec des points, trombone triste sans ;
  - règles permanentes : « pop » du Katamari, « boing » d'un objet trop gros (nouveau champ `kata.bonks`, révision 1.6 du contrat), klaxon de la mamie qui attaque, poissons.
- Les 22 sons `wtf_*` rejoignent la palette commune `event_sounds_model.gd` (`JINGLES`, bus « Events », remplaçables par `~/OpenRide/Sounds/<nom>.ogg`) ; deux timbres ajoutés à la synthèse de `sound_player.gd` : `slide` (glissando) et `noise` (bruit filtré).
- Tests : `engine/tests/unit/test_wtf_sounds.gd`.
- Reste : écoute courte sur le PC (fil de fusion), puis validation du propriétaire.
