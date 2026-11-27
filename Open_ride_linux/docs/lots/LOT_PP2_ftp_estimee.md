# Lot PP2 – FTP estimée depuis la courbe, proposée au joueur

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| FTP estimée (3 sources, confiance en mots, proposition à accepter, évolution par mois) | Python | PP1, O10, R16, MJ4 | Petite | **Livré le 24 novembre** (PR #973) |

## 1. Objectif

Estimer la FTP du profil en cours depuis sa courbe de puissance (PP1) et la **proposer** au joueur, sans jamais l'écrire seule (décision Q2 du 21 novembre). Plan : `docs/6.0/PLAN_SERIE_PP.md` §3.2, §3.3 et §10. Ni écran ni contrat : l'écran « Ma puissance » (PP3) affichera ce résultat au menu.

## 2. Travail demandé

- Une seule source retenue, écrite en toutes lettres, de la plus fiable à la moins fiable :
  1. test de rampe de moins de 6 semaines sans avertissement bloquant (`too_short`, `trainer_dropout`, `paused`) : « Fiable » ;
  2. puissance critique (modèle de R16) sur les efforts **libres** de 3 à 20 min des 6 dernières semaines, mêmes garde-fous que R16 : « Fiable » avec au moins 4 durées dont 20 min, « Indicative » sinon ;
  3. 95 % du meilleur effort libre de 20 min des 6 dernières semaines : « Indicative ».
- Sinon « Pas assez de données », avec la raison (« aucun effort libre de plus de 8 min depuis 6 semaines »).
- Séances ERG jamais comptées (décision Q1), sauf le test de rampe.
- Proposition « Utiliser 249 W comme FTP » quand l'estimation diffère de la FTP réglée ; signal `review` au-delà de 5 % d'écart (§5 du plan, lu par PP4).
- Acceptation : `--accept W` (et `accept(W)`) écrit `rider.ftp_w` par `config_edit.update_layers` (profil en cours, lot MJ4), seulement si l'estimation du moment vaut toujours W.
- Évolution mois par mois sur 6 mois : meilleurs 5 et 20 min libres, FTP du mois (test de rampe du mois, sinon 95 % du 20 min).
- Deux avertissements toujours donnés : efforts à fond supposés ; calibration du home trainer.
- Outil `python -m openride_core.tools.ftp_estimate` (texte, `--json`, `--accept W`).

## 3. Critères d'acceptation

1. `(cd core && pytest -q)` passe ; `core/tests/test_ftp_estimate.py` : CP fiable, séances ERG écartées, repli sur le 20 min et raison lisible, efforts trop anciens, rampe récente prioritaire et rampe douteuse écartée, signal à 5 %, évolution mensuelle, acceptation refusée si la valeur a changé, outil.
2. Séances fabriquées (FTP fictive 250 W) ; aucune écriture de la configuration sans `--accept`.
3. Rien pendant que le joueur roule : l'outil n'est appelé par aucune séance dans ce lot.

## 4. Livraison

- **Créés :** `core/src/openride_core/tools/ftp_estimate.py`, `core/tests/test_ftp_estimate.py`, ce cahier.
- **Modifiés :** `README.md`, `CLAUDE.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne chacun).
- Recette PC : catégorie logique (fumée + medium).
