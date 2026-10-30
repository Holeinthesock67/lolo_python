# Lot WTF7 – Engine : HUD des défis, surprise du chef, bilan et sons

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
