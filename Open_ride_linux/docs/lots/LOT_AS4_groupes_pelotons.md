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

## 9. Livraison (31 octobre 2026)

Branche empilée sur celle d'AS2 (position latérale, `lateral_factor`) : à fusionner après AS2.

- **Calcul de groupe.** `draft._group_draft` : chaque source devant à moins de 15 m et à moins de `GROUP_SIDE_M` (1,5 m) sur le côté donne `α_i` = courbe de P3 × `lateral_factor` × gabarit ; la plus forte compte entière, les autres avec `K_GROUP` = 0,6, et avec `K_LINE` = 0,3 quand elles sont cachées derrière un coureur plus proche sur leur ligne (masque = `lateral_factor` de l'écart entre les deux sources). Plafond `ALPHA_GROUP_CAP` = 0,55, puis vent de travers comme avant. `ALPHA_CAP` (0,45) et `LINE_FACTORS` disparaissent.
- **Écart au cahier, `k`.** Avec `k` = 0,6 pour toutes les sources, une file de 3 dans l'axe sort à + 0,05 de P3 (critère 3 : ± 0,02). D'où le second coefficient `K_LINE` = 0,3 pour les sources cachées dans la file, recalé sur les facteurs de P3 (écart au plus 0,018 pour un cycliste de 0,3 à 3 m derrière une file serrée de 0,3 à 1 m) ; `K_GROUP` = 0,6 reste celui du cahier pour les diagonales, qui ne sont pas cachées.
- **Flanc.** Une source dont les roues chevauchent celles du coureur (côte à côte, 0,9 m d'écart avec AS2) donne `FLANK_ALPHA` = 0,05, à recaler sur les mesures publiées ; en une dimension (sans `lane_m`), rien, comme P3.
- **Gabarit.** `size_factor` : `(CdA / 0,32)^0,5` borné de 0,85 à 1,15 ; CdA du cycliste (`Source.cda_m2`, sa physique) ou de la physique du bot, poussée du pas précédent retirée. Les bots à profil n'ont pas aujourd'hui de CdA selon leur masse (le cahier le supposait, T12 ne le fait pas) : ils ont tous le CdA de la configuration, gabarit 1. Le leur donner changerait leur calibrage (T13) : décision à part.
- **Coût.** 12 coureurs (11 bots et le cycliste) : moins de 0,2 ms par pas pour tous les abris, roues suivies et poussées (`test_cost_twelve_riders`) ; `lateral_factor` garde ses constantes calculées une fois.
- **Contrat.** Schéma `state` : `draft` jusqu'à 0,55. La jauge et la pastille gardent l'échelle `draft / 0,45` bornée à 100 % : passer à 0,55 reste une question au propriétaire.
- **Banc.** `draft_bench` gagne la partie 4 (cœur d'un groupe de cinq). Tests : `core/tests/test_draft_group.py` (critères 2 à 6).

### Mesures du 31 octobre (cloud, `python -m openride_core.tools.draft_bench`)

| Mesure | AS2 seul | AS2 + AS4 |
| --- | --- | --- |
| File à 0,5 m, derrière 1 / 2 / 3 bots | 81,8 / 91,6 / 95,5 W | 81,8 / 90,5 / 95,3 W |
| File à 3 m, derrière 1 / 2 / 3 bots | 43,8 / 49,1 / 51,7 W | 43,8 / 49,9 / 53,2 W |
| Cœur d'un groupe de cinq, 250 W seul | — | abri 0,531, 113,8 W gagnés (45,5 %) |

Groupe libre, bots à 230, 240 et 250 W et cycliste à 240 W, 10 min, placement activé, moyenne de trois départs :

| Coureur | À l'abri, AS2 seul | À l'abri, AS2 + AS4 | Watts gagnés, AS2 seul | AS2 + AS4 |
| --- | --- | --- | --- | --- |
| Bot 230 W | 29 % | 63 % | 15,5 W | 17,9 W |
| Bot 240 W | 25 % | 86 % | 11,5 W | 14,5 W |
| Bot 250 W | 11 % | 27 % | 4,2 W | 5,0 W |
| Cycliste 240 W | 28 % | 59 % | 8,7 W | 11,6 W |

La part du temps « à l'abri » (abri > 0,01) bondit surtout à cause du flanc : deux coureurs côte à côte se donnent désormais 0,05. Les watts gagnés, eux, ne montent que de 1 à 3 W. Contacts : 5,7 s sur 30 min placement activé, sous la borne de 1 % du banc.
