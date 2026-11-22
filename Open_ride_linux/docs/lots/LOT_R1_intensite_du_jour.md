# Lot R1 – Intensité du jour sur les écrans Prêt

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Ligne « Intensité du jour : facile / moyen / dur » avec les watts des bots, première ligne des écrans Prêt à bots | GDScript | GP-niv et BOT-elo (#941) | Petite | PR du 21 novembre |

## 1. Objectif

Accord du propriétaire du 21 novembre (« Ok r1 et r5 ») sur la stratégie des bots : « les watts fixent la dose du
jour, la tête fait gagner ». Avant de partir, le cycliste choisit la dose en un mot, et voit tout de suite les
watts que viseront les bots. Critères : ludique, un défi quand il le veut, pas à 100 % à chaque séance.

## 2. La règle

- **Ligne** : « Intensité : moyen », à droite « bots ≈ 225 W » (`bots_preview`, révision 1.22, sans nouvelle
  commande) ; la durée estimée de la course et la cote Elo passent dans la ligne d'état quand le focus est sur la
  ligne (premier banc du 21/11 : « Intensité du jour : … », durée et cote étaient coupés dans la rangée). Elle reprend la ligne grisée « Bots » de #941 et
  devient la première ligne de réglage, juste sous « Lancer » (« Démarrer » en session libre).
- **Trois mots** sur le réglage commun `bots.objective` (`bot_effort.OBJECTIVES`) : **facile** = endurance (65 %),
  **moyen** = tempo (80 %, défaut), **dur** = à fond (100 %). **A** passe au mot suivant (facile → moyen → dur →
  facile), envoie `set_setting bots.objective` : la dose est gardée pour les séances suivantes. Récupération et
  seuil restent choisis dans « Réglages » ; ils s'affichent « récupération » et « seuil », et A passe au mot
  au-dessus (facile, dur).
- **Où** : Dernier survivant, Grand Prix, Course, vélodrome, session libre, ERG et mode WTF quand un **Peloton** est choisi
  (bots à profil calibrés sur l'effort) ; pas de ligne sans bots calibrés. La ligne « Objectif des bots » quitte
  les écrans Prêt du Dernier survivant et du Grand Prix (même réglage, en double).
- **Vélodrome** : l'épreuve fixe la dose (décision du 15 novembre, `bot_effort.TRACK_EFFORT`) : ligne grisée,
  « Intensité fixée : dur », mot tiré de l'objectif renvoyé par `bots_preview`.
- **Course conseillée** (Dernier survivant) : l'objectif du besoin du jour (`start.objective`) s'affiche ; A le
  change pour cette course seulement, le réglage commun ne bouge pas.
- **Mots écrits** : focus sur la ligne, la ligne d'état dit « Intensité du jour : A pour facile, moyen ou dur. Les
  bots roulent à ces watts ; la course reste serrée. », puis « Course estimée à ≈ 9 min. Ta cote : 1540. »
- **Mode Course** (#939, demande du propriétaire du 21 novembre) : même ligne sur son écran Prêt (mode à réglages
  comme le Grand Prix) ; « Objectif des bots » retiré de `race_keys`, tours et adversaires ajoutés à `PREVIEW_KEYS`.

## 3. Tests

- `engine/tests/unit/test_intensity_menu.gd` : session libre avec et sans peloton, vélodrome grisé, course
  conseillée ; `test_grandprix_menu.gd` : cycle des trois mots, `set_setting`, watts effacés puis renvoyés ;
  `test_survivor_menu.gd` : focus gardé quand la ligne arrive, première ligne sous « Lancer ».
- Banc de menus `bots_elo` (captures elo_pret_gp, elo_pret_ds, elo_pret_velodrome) : écrans à valider par le
  propriétaire avant fusion ; FTP fictive 250 W.

## Livraison

- PR du 21 novembre, empilée sur #941 (branche `claude/project-thread-49umhu`).
