# Lot X9 – Recette de la fréquence cardiaque

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : Recette guidée de la fréquence cardiaque (gel, retrait, retour) | Python | Q5 | Petite | **Livré le 28 octobre** (branche `claude/project-thread-818r6t-x9`), essai sur le vélo ; issue #207 |

## 1. Objectif

La ceinture du propriétaire est ANT+ seule : sa fréquence arrive par le trainer, et une ceinture retirée a donné une valeur figée (105 bpm pendant 42 s le 25 octobre). Le lot Q5 traite le gel ; ce lot le vérifie automatiquement, sur le vélo et au cloud.

## 2. À lire

`core/src/openride_core/hr_monitor.py`, `drivers` (FC relayée par le trainer), `core/tests/test_hr_relay_freeze.py`, `tools/guide.py`, `tools/click_recette.py` (modèle d'essai guidé).

## 3. Travail demandé

- **`python -m openride_core.tools.fc_recette`** : essai guidé de 4 min (guide X5/X8 : bips, compte à rebours, préavis du matériel) : 60 s ceinture portée, 60 s retirée, 60 s remise, 60 s portée ; relevés à 1 Hz (source, valeur, contact) dans `fc.csv`.
- **Contrôles automatiques** (aussi en `--analyse JOURNAL.jsonl|FIT`) : pendant le retrait, FC absente du journal et du FIT au plus 10 s après le retrait ; aucune valeur identique plus de 15 s pendant que la puissance varie ; FC revenue dans les 20 s après la remise ; la source (ceinture Bluetooth ou relais du trainer) notée.
- **`--sim`** : la même chose devant le Bluetooth simulé (événements `contact` et `bpm` figé), pour la CI.
- Rapport `rapport.txt`, `rapport.json` dans `~/OpenRide/fc_recette/<date>/`.

## 4. Fichiers

- **Nouveaux :** `core/src/openride_core/tools/fc_recette.py`, `core/tests/test_fc_recette.py`.
- **Modifiés :** `tools/guide.py` (essai `fc_recette` dans `guide materiel`), `docs/OUTILS_DE_TEST.md`, `docs/PROTOCOLE_TEST_2026-10-26.md` (bloc B), ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 5. Critères d'acceptation

1. `--sim` passe ; un scénario où la FC reste figée fait échouer le contrôle « valeur figée ».
2. `--analyse` sur des journaux fabriqués (gel, trou, retour tardif) donne les bons verdicts.

## 6. Hors périmètre

Changer le traitement du gel (Q5).

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x9`).

- **`python -m openride_core.tools.fc_recette`** : essai guidé (guide X5/X8, essai `fc_recette` de `guide materiel`), 4 phases de `--phase-s` s (60) ; vrai pilote du trainer (gel Q5 compris) et ceinture Bluetooth si `[drivers] hr = "ble"` ; la FC relevée est celle que retient la séance (ceinture d'abord, sinon relais). `fc.csv` : t, phase, source, fc, contact, puissance.
- **Contrôles** : absence au plus 10 s après le retrait, aucune valeur identique plus de 15 s pendant que la puissance varie d'au moins 5 W, retour au plus 20 s après la remise, source notée. Seuils réglables (`--absence`, `--fige`, `--retour`).
- **Écart avec le §3 :** une FC relayée par le trainer ne disparaît que par le gel du lot Q5, au bout de `hr_relay_freeze_s` (15 s par défaut, 5 au moins). Pour cette source, le délai admis est `hr_relay_freeze_s` + 2 s et le rapport le dit, avec le réglage qui tiendrait 10 s (8 s). Le traitement du gel n'est pas changé (hors périmètre).
- **`--analyse`** : dossier de l'outil (`fc.csv`), journal `.jsonl` (source : ceinture si une ligne `device` « hr » existe, sinon relais) ou FIT (source inconnue) ; phases placées par `--retrait` et `--remise`.
- **`--sim`** : trainer simulé qui relaie la FC (au retrait, la dernière valeur reste figée, comme le 25 octobre) ou ceinture simulée (`--source ceinture`, contact perdu puis retrouvé) ; le cycliste simulé change d'allure à chaque phase. `--gel 120` laisse passer la valeur figée : absence et valeur figée échouent.
- Tests : `core/tests/test_fc_recette.py` (12 tests : essai bon, valeur figée avec et sans puissance qui varie, absence tardive admise seulement pour le relais, retour tardif, analyse d'un journal, d'un FIT et d'un dossier, trois essais simulés en parallèle, essai du guide, phases).

