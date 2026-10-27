# Lot R0 – Mesure du délai du frein du trainer (marches de pente et de braquet)

## 1. Objectif

Le mode Cyber-Rogue (version 2.0, [plan de la série R](../2.0/PLAN_SERIE_R.md)) repose sur des changements de résistance rapides : bosses de 15 s du Puncheur, fenêtre de 1,5 s du Perfect Shift, grand pas de −3 vitesses (appui long sur B). Le temps de réponse du frein n'a jamais été mesuré ; l'essai 69 du 25 octobre a montré un retard d'environ 22 s sur des marches de 0 à 7 %, surtout au relâchement. Ce lot mesure ce délai sur le trainer du propriétaire et en tire les réglages du mode : vitesse de variation de la pente envoyée, durée minimale d'une bosse, avance des arches.

Ce lot a deux parties :
- **R0a (délégable) :** le script de mesure. C'est le même outil que l'outil X5 (« banc de latence du trainer par paliers ») du plan des outils de test ; si X5 est livré avant, R0a se réduit à vérifier qu'il couvre le §4.1 ;
- **R0b (propriétaire, sur le vélo) :** l'essai et la lecture des résultats.

## 2. À lire

1. `docs/lots/00_INDEX.md` (règles communes, paragraphe « Série R »), `docs/2.0/PLAN_SERIE_R.md` §2 et §5.
2. `docs/lots/LOT_Q3_journal_ftms.md` (horodatage des commandes FTMS et des accusés) et `docs/lots/LOT_Q4_rampe_de_pente.md` (rampe de la pente envoyée).
3. Code : `core/src/openride_core/ftms_driver.py`, `core/src/openride_core/session.py` (rampe `max_delta`, envoi immédiat au changement de braquet), `core/src/openride_core/tools/log_report.py`, `core/src/openride_core/sim_scenarios.py`.

## 3. Prérequis

Q3 et Q4 livrés (journal des commandes FTMS, rampe à deux vitesses). Pour R0b : trainer et Click appairés, capteur de cadence du trainer actif.

## 4. Travail demandé

### 4.1 R0a : script `step_latency`

- Nouvel outil `python -m openride_core.tools.step_latency` qui pilote le trainer en SIM, sans engine, et joue une suite de marches. Chaque marche dure 30 s, précédée de 30 s de stabilisation à la pente de départ :
  - pente envoyée : 0→4, 0→7, 0→10, 4→0, 7→0, 10→0 et 0→−3 % ;
  - braquet (formule centrée de la décision Q2, 1 point par vitesse) sur une pente de 3 % : +1, −1, +3 et −3 vitesses ;
  - chaque marche est jouée 3 fois, dans un ordre mélangé (graine affichée).
- Pendant l'essai, la rampe du core est **coupée** (`grade_rate` infini pour l'outil seul) : on mesure le trainer, pas le core.
- Le cycliste garde une cadence de 85 ± 3 rpm, affichée en grand dans le terminal avec le compte à rebours de la marche suivante. Une marche jouée hors de 82 à 88 rpm est marquée « cadence hors plage » et rejouée une fois à la fin.
- Le cycliste appuie sur Z (ou sur la touche Entrée) quand il **sent** le couple changer : c'est le délai ressenti.
- Mesures par marche, à partir de l'horodatage de la commande FTMS envoyée (journal de Q3) :
  - `t_ack` : délai de l'accusé du trainer ;
  - `t10`, `t50`, `t90` : temps pour atteindre 10, 50 et 90 % du changement de puissance à cadence constante (puissance lissée sur 1 s, état stable = moyenne des 10 dernières secondes de la marche) ;
  - `t_felt` : délai ressenti (appui sur Z) ;
  - fréquence réelle des notifications de puissance du trainer.
- Sortie : un tableau texte et un fichier JSON sous `~/OpenRide/essais/` (médiane et écart des 3 répétitions par marche). Le fichier ne contient ni adresse Bluetooth ni nom de trainer : seulement `trainer_kind` (« FTMS ») et la date.
- Mode `--simulate` sur le trainer simulé (`ble_sim.py`) avec un modèle de réponse du 1er ordre réglable (`--tau-up`, `--tau-down`), pour tester l'outil sans matériel.

### 4.2 R0b : essai sur le vélo (propriétaire)

- Échauffement de 10 min, puis le programme du §4.1 (environ 25 min). Les marches à 10 % sont courtes ; arrêter à tout moment avec Ctrl+C, les mesures déjà faites sont gardées.
- Garder le JSON en local. Ne publier dans le dépôt que les valeurs (médianes), sans nom ni modèle de trainer (règle de confidentialité du projet).

### 4.3 Règles de décision (appliquées après l'essai, consignées dans le plan)

| Mesure | Décision tirée |
| --- | --- |
| `t90` des marches montantes et descendantes | Limite de variation de la pente envoyée en mode Cyber-Rogue (`[rogue] grade_rate_up_pct_per_s`, `grade_rate_down_pct_per_s`) : la plus rapide que le trainer suit, sans dépasser 100 %/s |
| `t90` de 0→10 % | Durée minimale d'une bosse : `max(15 s, 2 × t90)` ; au-delà de 7,5 s, le Puncheur passe à des bosses de 30 s (variante 30/30) |
| `t50` des braquets ±1 | Avance des arches de Perfect Shift : l'arche est posée `t50` avant la rupture de pente, pour que le frein change au bon moment |
| `t_felt` | Taille de la fenêtre de Perfect Shift : 1,5 s si `t_felt` médian ≤ 1 s, sinon `t_felt` + 0,5 s, au plus 3 s |
| Écart montée / descente | Si le relâchement dépasse 10 s, les salles évitent les chutes de plus de 5 points en moins de 10 s (règle du générateur R3) |

## 5. Fichiers concernés

- **Créés :** `core/src/openride_core/tools/step_latency.py`, `core/tests/test_step_latency.py`.
- **Modifiés :** `README.md` (une ligne dans la liste des outils), `docs/SUIVI_AVANCEMENT.md` (une ligne) ; après R0b, `docs/2.0/PLAN_SERIE_R.md` §2 (valeurs retenues).
- **Interdits :** `session.py`, `ftms_driver.py` (l'outil utilise le pilote tel quel).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `(cd core && pytest -q)` passe.
2. En `--simulate --tau-up 2 --tau-down 6`, l'outil retrouve `t50` à ± 15 % de la valeur théorique (τ × ln 2) pour chaque marche.
3. Une marche jouée hors de la plage de cadence est marquée et rejouée une fois.
4. Le JSON produit ne contient ni adresse Bluetooth ni nom de modèle (test sur le trainer simulé).
5. R0b : le propriétaire a joué au moins une répétition de chaque marche ; les valeurs retenues sont notées dans le plan.

## 8. Hors périmètre

- Réglage de la rampe du mode classique (lot Q4).
- Latence du Click (outil X7 du plan des outils de test).
