# Lot X9 – Recette de la fréquence cardiaque

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
