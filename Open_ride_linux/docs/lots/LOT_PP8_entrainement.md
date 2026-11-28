# Lot PP8 – Entraînement : le coach lit la courbe, test de rampe au bon moment

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Coach : point faible tiré de la courbe (PP5), test de rampe proposé seulement quand la FTP estimée s'écarte ; intervalles calés sur la courbe et courbe avant/après un plan en PP8b | Python | PP2, PP5, série CO | Moyenne | PR ouverte le 21 novembre (série PP, 6.0) ; PP8b en cahier |

## 1. Objectif

Idées du §8.4 du plan `docs/6.0/PLAN_SERIE_PP.md`, retenues par le propriétaire le 21 novembre (Q4) : que la séance conseillée (série CO) s'appuie sur la courbe de puissance plutôt que sur des règles à date fixe. Une seule source pour le point faible : le profil du lot PP5 ; le coach ne garde pas un second calcul qui pourrait dire autre chose.

## 2. Travail demandé (PP8)

`core/src/openride_core/coach.py` :

1. **Point faible** : sans test de FTP récent, le coach n'avait pas de profil de puissance (signal S4) ; il reprend désormais le point faible de « Se connaître » (PP5, durée 5 s, 1 min, 5 min ou 20 min) et le traduit en besoin par la table `[profile] need` de `data/coach.toml` (5 s et 1 min : anaérobie ; 5 et 20 min : aérobie intense). Il sert au départage R7, comme avant. Avec un test récent, S4 reste calculé comme avant.
2. **Test de rampe au bon moment** (règle R4) :
   - FTP estimée (PP2) à plus de 5 % de la FTP réglée : test proposé, avec la raison en watts (« Ta FTP estimée (262 W) s'écarte de plus de 5 % de ta FTP réglée (250 W) : un test de rampe la confirmera. ») ;
   - FTP estimée **Fiable** et à moins de 5 % : pas de test, même si le dernier test date de plus de 6 semaines (pas à date fixe) ;
   - sans estimation : la règle d'âge reste (`r4_ftp_age_days`).
3. `advice_today` (ligne de commande `openride-core coach` et commande IPC `get_coach`) lit la courbe du profil (cache commun du lot PP1) ; une courbe illisible laisse le conseil comme avant. Les sorties gardent leurs clés ; `signals.curve` s'ajoute (point faible et signal FTP).

## 3. PP8b (cahier, à coder ensuite)

- **Intervalles calés sur la courbe** : un 30/30 ou un 1 min réglé sur ton meilleur 1 min (ou 5 min) plutôt que sur un pourcentage de FTP, pour les efforts courts ; option des entraînements créés au menu (`workout_menu.py`), cible écrite en watts.
- **Courbe avant et après un plan** : à la fin d'un plan de plusieurs semaines (`plans.py`), bilan des 13 durées avant et après, au menu.

**Livré le 26 novembre (PR PP8b, révision IPC prise à la fusion)** :

- Intervalles : ligne « Base de l'effort » (FTP, ton 1 min, ton 5 min) de « Créer un entraînement » ; sur la courbe, « Puissance de l'effort » va de 50 à 120 % de ton meilleur effort des 6 derniers mois (courbe type × FTP sans effort de cette durée, toutes les séances comptées comme le coach). Le core convertit en % de la FTP dans le `.zwo` et écrit les watts dans le nom (« Intervalles 6 × 1 min à 342 W (95 % de ton 1 min) ») ; la récupération reste en % de la FTP. Contrat : `create_workout.on_ref`, `workout_saved.target_w`.
- Courbe du plan : fiche « Plan en cours », « Ta courbe, avant → depuis le début du plan » (« après le plan » une fois fini), aux quatre durées de « Se connaître » (5 s, 1 min, 5 min, 20 min) plutôt qu'aux 13, pour tenir dans la fiche ; avant = meilleur des 6 mois d'avant le début, après = meilleur depuis le début. Contrat : `plans.active.curve`.

## 4. Critères d'acceptation

1. `core/tests/test_coach_courbe.py` : point faible de la courbe sans test récent, départage R7 ; R4 proposé quand l'estimation s'écarte, retenu quand elle confirme la FTP malgré un test ancien, règle d'âge sans estimation.
2. Les tests existants du coach (`test_coach*.py`) passent sans changement.
3. Recette PC : logique, fumée + medium.
