# Rapport d'équilibrage des bonus (lot TT8)

8 novembre 2026. Cahier : `docs/lots/LOT_TT8_equilibrage_recette.md` ; plan : `docs/4.0/PLAN_SERIE_TT.md` §2 (cible **1,5 à 2,5 s dans le terrain idéal**, presque rien ailleurs).

## 1. Méthode

Outil `python -m openride_core.tools.bonus_bench` (`core/src/openride_core/tools/bonus_bench.py`, décrit dans `docs/OUTILS_DE_TEST.md`). Physique du core au pas de 20 ms, sans trainer ni engine, rejouable à l'octet près (graine 8). Pour chaque bonus, 50 passages : un cycliste virtuel du lot X27 (stratégie `pente`, FTP de 200 à 320 W, 70 à 95 % de FTP sur le plat, masse cycliste et vélo de 70 à 95 kg, bruit de ± 2 %) roule son terrain idéal deux fois avec les mêmes watts, avec et sans le bonus lancé à t = 0. Le gain est l'avance au bout de 60 s, en secondes. Pour l'Échappée, c'est ce que perd un suiveur collé (0,3 à 1,5 m) à la fin du bonus. « Ailleurs » : le même cycliste hors du terrain du bonus.

Les valeurs essayées passent par `--values` (format de `~/OpenRide/powerups.toml`). Aucun essai ne touche au rendu : rien à mesurer sur le PC en low, medium et high pour ce lot (le banc GPU de la série est celui de TT6).

## 2. Valeurs de départ (plan §2)

| Bonus | Durée | Gain médian | Min – max | Dans la cible |
| --- | --- | --- | --- | --- |
| Plume | 20 s | 1,84 s | 1,43 – 2,07 s | 98 % |
| Casque aéro | 15 s | 1,24 s | 1,00 – 1,41 s | 0 % |
| Puissance | 15 s | 1,34 s | 1,19 – 1,45 s | 0 % |
| Enclume | 15 s | 2,34 s | 1,63 – 2,87 s | 62 % |
| Aspiration + | 40 s | 2,39 s | 1,69 – 3,40 s | 56 % |
| Échappée | 20 s | 1,00 s | 0,73 – 1,27 s | 0 % |
| Rouleau compresseur | 30 s | 2,55 s | 1,17 – 5,06 s | 38 % |

Hors cible : Casque, Puissance et Échappée en dessous. L'Aspiration + collée à la roue et le Rouleau sur la terre sont au-dessus.

## 3. Essais

Seules les durées changent. Les facteurs restent ceux du plan, retenus par le propriétaire le 29 octobre.

| Essai | Casque | Puissance | Aspiration + | Échappée | Rouleau | Médianes (Casque, Puissance, Aspiration +, Échappée, Rouleau) |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 18 s | 18 s | 35 s | 30 s | 25 s | 1,50 ; 1,61 ; 2,11 ; 1,89 ; 2,14 s |
| 2 | 20 s | 19 s | 32 s | 35 s | 24 s | 1,67 ; 1,70 ; 1,93 ; 2,29 ; 2,06 s |
| 3 | 19 s | 20 s | 30 s | 40 s | 22 s | 1,59 ; 1,79 ; 1,81 ; 2,77 ; 1,89 s |

Retenu pour les bonus tactiques (essai 1) : **Aspiration + 35 s**, **Échappée 30 s**, **Rouleau 25 s**. Ce sont les valeurs les plus proches du plan qui mettent la médiane dans la cible. Plume et Enclume ne changent pas.

Rouleau : l'écart vient de la surface. Médianes à 25 s : 1,44 s sur un chemin compact (× 2), 2,28 s sur le gravier (× 2,5) et 3,21 s sur la terre (× 3). La part dans la cible reste donc basse quelle que soit la durée ; la durée est calée sur le gravier, la surface du milieu.

**Casque aéro et Puissance** (jeu `classiques`) : gardés à 15 s, en attente du choix du propriétaire. La règle du plan (§3) veut que `classiques` soit identique à la 2.0 (test du rejeu de TT2). Les allonger (Casque 20 s, Puissance 18 s : médianes 1,67 et 1,61 s) les mettrait dans la cible, mais changerait le jeu `classiques` et ses records.

## 4. Valeurs retenues

Sortie de `python -m openride_core.tools.bonus_bench` (50 passages, graine 8) :

| Bonus | Facteur | Durée | Gain médian | Min – max | Dans la cible | Ailleurs |
| --- | --- | --- | --- | --- | --- | --- |
| Plume | 0.9 | 20 s | 1.84 s | 1.43 – 2.07 s | 98 % | 0.12 s |
| Casque aéro | 0.75 | 15 s | 1.24 s | 1.00 – 1.41 s | 0 % | 0.16 s |
| Puissance | 1.1 | 15 s | 1.34 s | 1.19 – 1.45 s | 0 % | 0.54 s |
| Enclume | 1.6 | 15 s | 2.34 s | 1.63 – 2.87 s | 62 % | 0.00 s |
| Aspiration + | 1.5 | 35 s | 2.11 s | 1.50 – 2.99 s | 84 % | 0.04 s |
| Échappée | 1 | 30 s | 1.89 s | 1.38 – 2.33 s | 94 % | 0.00 s |
| Rouleau compresseur | 1 | 25 s | 2.14 s | 0.98 – 4.27 s | 36 % | 0.00 s |

| Bonus | Refus (sur les appuis) |
| --- | --- |
| Plume | accepté 41, erg 9 |
| Casque aéro | accepté 48, erg 2 |
| Puissance | accepté 45, erg 5 |
| Enclume | accepté 19, erg 4, no_descent 27 |
| Aspiration + | accepté 30, erg 5, no_bots 15 |
| Échappée | accepté 14, erg 6, near_finish 6, no_bots 24 |
| Rouleau compresseur | accepté 11, erg 9, no_gravel 30 |

Tirage du jeu `tactiques` : feather 12, aero 11, power 5, anvil 13, draft_plus 3, breakaway 3, roller 3, aucun 0.

Verdict : hors de la cible : aero, power.

Hors du terrain idéal, le gain est presque nul : 0,00 à 0,16 s. Seule la Puissance garde 0,54 s sur le plat, parce que + 10 % de watts aide partout ; c'est le comportement de la 2.0. L'Enclume ne donne rien sur le plat (effet suspendu au-dessus de − 0,5 %).

## 5. Recette sur le vélo (propriétaire)

Deux sessions de 10 min au plus, en SIM, avec le jeu `tactiques`. Les bonus sont tirés au hasard (parmi ceux qui servent à cet endroit) : on lance chaque bonus obtenu, dans son terrain quand c'est possible.

1. **Bots** : parcours de démonstration, 4 bots. Pour une Aspiration +, se placer dans la roue d'un bot avant de lancer (ressenti : pente plus douce d'environ 0,4 point). Pour une Échappée, la lancer devant un bot (il doit décrocher sans réagir pendant 30 s, avatar transparent). Un appui à moins de 400 m de l'arrivée doit être refusé (« arrivée proche »).
2. **Gravel** : gravel « gravier » (toute la route), sans bots. Pour un Rouleau, le supplément de pente du gravel doit disparaître en 20 m et revenir à la fin. Pour une Enclume, l'essayer d'abord sur le plat (refus « pas de descente », bonus gardé) puis en descente.

Compte-rendu attendu pour chaque session : `OK|KO note/5`.

| Session | Résultat |
| --- | --- |
| 1. Bots | à faire |
| 2. Gravel | à faire |
