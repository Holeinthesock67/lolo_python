# Lot PP4 – Records de puissance au bilan et signal « FTP à revoir »

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Records de puissance de la séance au bilan, signal « FTP à revoir » (proposition seulement) | Python + GDScript | PP1, PP2, PP3 | Petite | PR ouverte le 21 novembre (série PP, 6.0) |

## 1. Objectif

Dire au joueur, à la fin de sa séance et seulement là, ce que sa séance a changé à sa courbe de puissance : les durées où il vient de faire mieux que sur les 6 derniers mois, et, si sa FTP réglée paraît fausse de plus de 5 %, le signal « FTP à revoir » (plan `docs/6.0/PLAN_SERIE_PP.md`, lot PP4). Rien pendant la séance, rien d'écrit sans accord (décision Q2 du 21 novembre).

## 2. Travail demandé

### 2.1 Core

- `core/src/openride_core/tools/power_records.py` : `session_report(journal, ftp, dossier, cache, sources)` compare la courbe de la séance (13 durées, lot PP1) aux meilleurs efforts des 6 derniers mois du profil, séance exclue :
  - record : au moins 1 W de mieux (watts arrondis) ; durée jamais tenue avant : record « premier effort » ;
  - première séance du profil : aucun record (tout le serait) ; séance non comptée (rejeu, séance simulée d'un joueur) : rien ;
  - au plus 4 records, les plus grands gains en pour cent, rangés par durée, avec le mot « libre » ou « ERG » ;
  - signal « FTP à revoir » : estimation du lot PP2 (séance comprise) à plus de 5 % de la FTP réglée.
- `session.py` : `_after_session_power` à la fin d'une séance finie, calcul hors de la boucle à 50 Hz (comme `summary.collection`), puis `summary.power_records` et `summary.ftp_review`, absents s'il n'y a rien à dire.
- Contrat : révision 1.29 (déjà réservée à la série PP par le lot PP3), objets facultatifs de `summary` (« Bilan 1.29 » de `docs/contracts/ipc_v1.md`, `state.schema.json`).
- Ligne de commande : `python -m openride_core.tools.power_records JOURNAL.jsonl [--ftp W] [--json]`.

### 2.2 Engine

- `summary_view_model.gd` : `records_beaten` ajoute, après les records de segments, « ★ Puissance 5 min · libre   310 W   avant 300 W » (ou « premier effort ») ; les lignes au-delà de trois restent comptées (« … et 2 autres records »).
- `ftp_review` : « FTP à revoir : ta FTP estimée est de 262 W, ta FTP réglée de 250 W (plus haute). » puis « Pour la changer : « Qui roule ? › Ma puissance », au menu. Rien n'est changé sans toi. », à la place du verdict du Cyber-Rogue (une séance de Cyber-Rogue garde son verdict).

## 3. Critères d'acceptation

1. `(cd core && pytest -q)` passe, dont `core/tests/test_power_records.py` (records sur 6 mois, séance trop vieille écartée, premier effort, première séance et séance non comptée, record ERG, signal à 5 %, bilan de la séance rempli).
2. `engine/tests/unit/test_summary_view_model.gd` : lignes des records de puissance et du signal, rien sans signal.
3. Recette PC : logique, fumée + medium (pas d'écran nouveau ; le bilan garde sa mise en page).

## 4. Livraison

21 novembre 2026, PR empilée sur PP3 : module `power_records.py`, branchement de fin de séance, contrat 1.29 complété, bilan de l'engine, tests du core et de l'engine. Aucune donnée réelle : séances fabriquées (modèle à 250 W).
