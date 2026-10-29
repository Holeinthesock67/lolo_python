# Lot AS4 – Abri dans un groupe

Série AS, version 2.0. Décision du propriétaire du 29 octobre 2026 : **plafond de 55 % au cœur d'un groupe** (45 % aujourd'hui).

## 1. Objectif

P3 ne compte qu'une file : les bots devant, à moins de 3 m les uns des autres, avec un bonus par rang. Dans un vrai groupe, l'abri vient aussi des coureurs sur les côtés et en diagonale, et grandit au cœur du groupe (Blocken et coll. 2018, peloton : jusqu'à 90 % au milieu d'un grand peloton). OpenRide a au plus quelques bots, plus les cyclistes du décor d'AS7 : ce lot calcule l'abri de tous les coureurs proches devant et sur les côtés, plafonné à 55 %.

## 2. À lire

`docs/lots/LOT_P3_aspiration_bots.md`, `LOT_AS1_abri_entre_bots.md`, `LOT_AS2_zone_laterale_placement.md` ; code `draft.py`.

## 3. Prérequis

AS2 livré (position latérale). AS7 peut arriver avant ou après : le calcul prend la liste des coureurs quelle qu'elle soit.

## 4. Travail demandé

- **Abri de groupe.** Pour un coureur, chaque source devant lui à moins de 15 m et à moins de 1,5 m sur le côté donne un abri `α_i` (courbe de P3 × `lateral_factor` d'AS2). L'abri total vaut `1 − Π(1 − k·α_i)`, avec `k` = 0,6 pour les sources après la plus forte (constante en tête de `draft.py`, à recaler sur les mesures publiées). Il est plafonné à `ALPHA_GROUP_CAP` = 0,55.
- **Compatibilité.** Une seule source : résultat identique à P3. File de 2 ou 3 coureurs dans l'axe : résultat à ±0,02 des facteurs de file de P3 (1,12, 1,18), qui disparaissent au profit du calcul de groupe.
- **Taille de la source.** L'abri d'une source est multiplié par `(CdA_source / CdA_réf)^0,5`, borné de 0,85 à 1,15 : un gros gabarit abrite un peu plus. Les bots à profil ont leur CdA selon leur masse (T12) ; le cycliste a le sien.
- **Poussée vers l'avant.** Inchangée (2,5 % pour le coureur suivi à moins de 1 m), pour chaque coureur.
- **Coût.** 12 coureurs (5 bots, le cycliste, 6 cyclistes du décor) : moins de 0,2 ms par pas pour tous les abris.

## 5. Fichiers concernés

`core/src/openride_core/draft.py`, `session.py`, `bots.py` (CdA de la source), `core/tests/test_draft.py`, `docs/SRS_v1.1.md` (§5 : plafond 0,55 en groupe), `docs/SUIVI_AVANCEMENT.md`. Interdits : l'engine, le contrat.

## 6. Modifications de contrat autorisées

Aucune. `draft` peut maintenant monter à 0,55. La jauge et la pastille gardent l'échelle `draft / 0,45` bornée à 100 % : décider en recette s'il faut passer l'échelle à 0,55 (question au propriétaire, pas de changement sans son accord).

## 7. Critères d'acceptation

1. `pytest` passe en entier.
2. Une source : identique à P3 à 1e-6 près.
3. File de 3 dans l'axe : à ±0,02 de l'abri de P3.
4. Cycliste au milieu d'un groupe de 5 (deux devant, deux en diagonale, un sur le côté) : abri entre 0,45 et 0,55 ; jamais au-dessus de 0,55.
5. Sources à plus de 1,5 m sur le côté ou derrière : aucune contribution.
6. Coût : moins de 0,2 ms par pas avec 12 coureurs.

## 8. Hors périmètre

Grand peloton de plus de 20 coureurs, mouvements de peloton (remontées, frottements).
