# Lot PP6 – Jeu à ta mesure : bots, durée tenable et temps prévu calés sur ta courbe

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Bots calés sur ta courbe selon la durée de la course, durée tenable annoncée, temps prévu sur un parcours, seuils d'attaque du Grand Prix et rythme de l'élimination | Python (+ GDScript pour les textes du menu) | PP1, BT1, Elo #941, mode Course #939, stratégie R1 #966 | Moyenne | PR ouverte le 23 novembre (série PP, 6.0) pour le branchement des bots et `hold_s` ; fiche de la course, temps prévu, Grand Prix et élimination en PP6b (cahier) |

## 1. Objectif

Idées du §8.2 du plan `docs/6.0/PLAN_SERIE_PP.md`, retenues par le propriétaire le 21 novembre (Q4) : que la difficulté suive ce que **ce** cycliste tient vraiment sur la durée de la course, et non un seul pourcentage de FTP. Toujours dit en watts au menu, jamais changé sans le dire (§8.5).

## 2. Point d'accroche dans le code existant

- `bot_effort.py` (lot BT1) : puissance des bots = FTP × `curve_pct(durée)` × objectif × niveau. `POWER_CURVE` est une courbe **générique** (1 min : 160 %, 5 min : 120 %, 20 min : 105 %, 1 h : 100 %).
- PP6 remplace, pour le joueur en cours, `curve_pct` par sa **courbe personnelle** (`power_curve.compute`, fenêtre 6 mois, efforts libres) exprimée en % de sa FTP, là où elle a un effort à fond récent ; ailleurs, la courbe générique reste (mélange sur le logarithme de la durée, pour éviter une marche).
- L'Elo des bots (#941) et le mode Course (#939) règlent **qui** gagne et **comment** ; PP6 ne touche que l'allure visée selon la durée. Rien n'est doublé : un seul point d'entrée, `bot_effort.curve_pct_for(profile_curve, duration_s)`.

## 3. Travail prévu (après cadrage)

1. `bot_effort.py` : `curve_pct_for(curve, d)`, courbe personnelle si le point existe et date de moins de 6 mois, sinon courbe générique ; bornes : jamais plus de ± 15 % de la courbe générique (un record isolé ne rend pas la course impossible).
2. **Durée tenable annoncée** : fiche de la course au menu, « À ce niveau, tu tiens environ 12 min » (durée où ta courbe croise la puissance visée).
3. **Temps prévu pour toi** sur la fiche d'un parcours : « Temps estimé pour toi : 23 min », calculé par le cycliste de référence de `route_stats.py` à la puissance de ta courbe pour cette durée (itération comme `target_pct`).
4. **Grand Prix** : seuil des boîtes « ! ATTAQUE » calé sur ton 15 s et ton 1 min au lieu d'un chiffre fixe.
5. **Élimination au vélodrome** : rythme des tours calé sur ton 1 à 3 min.
6. Rien pendant la séance : tout se lit au menu ; la course elle-même roule comme avant, seule l'allure visée change.

## 4. Cadrage avec le fil « Coder niveau des bots et Elo » (21 novembre)

1. **Un seul branchement** dans `bot_effort.py` : champ facultatif `curve` de `Effort` (durée → % de la FTP, `None` = courbe type), utilisé par `target_pct` à la place de `curve_pct`. Tout en hérite : `bots.effort_target`, `calibrate_bots`, aperçu des bots, `summary.bots_effort`, course conseillée, `bots_race`.
2. **Construction** : `CoreSession._bot_effort()` la construit une seule fois au départ depuis `power_curve.compute` (cache), normalisée par la FTP ; jamais dans la boucle à 50 Hz, aucune lecture de FIT au départ ; la courbe utilisée est écrite au journal pour rejouer la course à l'identique.
3. **Repli par durée** : 6 semaines, sinon 6 mois, sinon courbe type ; interpolation sur le logarithme de la durée ; borne ± 15 % de la courbe type.
4. **Libre ou ERG** : le meilleur des deux par durée (décision du propriétaire, 21/11 21 h 34 ; un effort ERG ne dépasse jamais ce que le cycliste tient).
5. **Elo (#941)** : la cote reste un multiplicateur par-dessus (`level_factor`) ; la courbe ne recale jamais la cote.
6. R1, RW et R5 ne sont pas concernés (R1 ne choisit que `share_pct`).
7. **Durée tenable et temps prévu** : inverse de la courbe, une seule fonction `hold_s(pct)` dans `bot_effort.py`, partagée par le Grand Prix (seuils d'attaque) et le Dernier survivant (rythme d'élimination).
8. Contrôle : option `--courbe` de `tools/elo_campagne.py` pour vérifier que la cote converge aussi avec une courbe de joueur ; le mode Course (#939) reçoit tout tel quel.
9. Ordre : code après la fusion de #941, #939 et #966 (règle du 21/11) ; ligue d'hiver (série CH) : la manche utilise la courbe personnelle.

## 4 bis. PP6b (cahier, à coder ensuite)

Points 2 à 5 du §3, qui changent des écrans ou des modes : durée tenable sur la fiche de la course (« À ce niveau, tu tiens environ 12 min »), temps prévu pour toi sur la fiche d'un parcours, seuils des boîtes « ! ATTAQUE » du Grand Prix calés sur ton 15 s et ton 1 min, rythme de l'élimination au vélodrome. Tous lisent `bot_effort.hold_s` et `Effort.curve`, déjà livrés.

## 5. Critères d'acceptation

1. Tests du core : courbe personnelle utilisée, repli générique sans point, bornes ± 15 %, durée tenable, temps prévu.
2. Banc simulé `elo_campagne` (validation des bots sans essai vélo, décision du 21/11) toujours vert.
3. Recette PC : logique, fumée + medium ; captures seulement si une fiche du menu change.

## 6. Livraison

23 novembre 2026, PR empilée sur PP7b, après la fusion de #941, #939 et #966 :

- `bot_effort.py` : champ facultatif `Effort.curve`, `curve_pct_for` (courbe du cycliste entre sa plus courte et sa plus longue durée, ± 15 % de la courbe type, ailleurs la courbe type), `hold_s` (inverse), `personal_curve` (meilleur effort par durée, libre ou ERG, 6 semaines sinon 6 mois, rendue décroissante) ; `target_pct` la suit ;
- `session.py` : `_rider_curve` calculée hors de la boucle (`ipc_lists.rider_curve`) au lancement, au changement de profil et après chaque séance ; `_bot_effort` la passe à tous les modes (Grand Prix, Course, ligue, vélodrome, aperçu des bots) ; ligne de log « courbe du cycliste » ou « courbe type » ; champ `curve` de la ligne `bots` du journal au départ (pour rejouer la course) ;
- `tools/elo_campagne.py --courbe` : campagne avec la courbe d'un cycliste fictif (puncheur à FTP 250 W).

Testé par `core/tests/test_bot_effort_courbe.py`. Recette PC : logique, fumée + medium ; aucun écran ne change.
