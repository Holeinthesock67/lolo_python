# Lot Q5 – Fréquence cardiaque relayée par le trainer figée

## 1. Objectif

Essai du 25 octobre : la ceinture cardio était appairée au trainer, qui relayait la fréquence cardiaque dans ses données FTMS. Quand la ceinture a été retirée, le trainer a continué à envoyer la dernière valeur : 105 bpm sans changer pendant 42 s. Cette fausse FC est passée dans le `.jsonl`, le FIT et les moyennes. Ce lot détecte une FC relayée qui ne bouge plus et l'écrit comme absente.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_M2_ceinture_cardio_reelle.md` (repli de la cardio sur le trainer).
2. Code : `core/src/openride_core/ftms_driver.py` (`_on_ibd`, `_on_hr`, `poll` : `hr_bpm`), `session.py` (priorité de la ceinture sur la FC du trainer), `hr_monitor.py`, `recorder.py`, `fit_export.py` (champ `hr` absent = pas de FC), `journal.py`, `ble_sim.py`, `sim_scenarios.py`.

## 3. Prérequis

Aucun. `ftms_driver.py` est aussi modifié par Q3 : faire Q3 et Q5 l'un après l'autre.

## 4. Travail demandé

- **Détection, dans le driver FTMS** (source « trainer » seulement, jamais la ceinture connectée directement) :
  - la FC relayée est dite figée si sa valeur n'a pas changé d'un seul bpm depuis `[trainer] hr_relay_freeze_s` secondes (défaut 15, bornes 5 à 120) ;
  - une vraie FC change presque toujours d'au moins 1 bpm en 15 s ; en cas de doute, les tests fixent les cas limites ;
  - tant qu'elle est figée, `poll` rend `hr_bpm = None` ;
  - elle redevient valide dès que la valeur change.
- **Journal :** une ligne à l'entrée (`Cardio relayée par le trainer figée à 105 bpm depuis 15 s : ignorée`) et une à la sortie (`Cardio relayée de nouveau valide`), pas de répétition.
- **FIT et `.jsonl` :** aucune FC pendant la période figée (le champ manque, comme sans ceinture) ; les moyennes l'excluent.
- **Résumé de séance** (`openride-core summary`) : durée totale de FC ignorée, si elle n'est pas nulle.
- **Simulation :** scénario `fc_relayee_figee` dans `sim_scenarios.py` (FC qui varie, puis figée 40 s, puis qui reprend).

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/ftms_driver.py`, `config.py` (`[trainer] hr_relay_freeze_s`), `sim_scenarios.py`, `ble_sim.py` (FC relayée figée), `tools/session_summary.py` ; `README.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `core/tests/test_hr_relay_freeze.py`.
- **Interdits :** `hr_monitor.py` (la ceinture directe n'est pas concernée), `fit_export.py` (déjà correct : champ absent = pas de FC), l'engine, le contrat IPC.

## 6. Modifications de contrat autorisées

Aucune. Dans la trame `state`, `hr` vaut déjà `null` quand il n'y a pas de mesure.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. FC relayée qui varie de ±2 bpm : jamais ignorée sur 10 min simulées.
3. FC relayée fixe à 105 : ignorée au bout de 15 s ± 0,5 s, une seule ligne de journal, `hr` absent du `.jsonl` et du FIT pendant la période, moyenne et maximum calculés sans elle.
4. Reprise : première valeur différente acceptée aussitôt, ligne « de nouveau valide ».
5. Ceinture connectée directement (`--hr sim`) avec une valeur fixe : jamais ignorée (le lot ne touche que la FC du trainer).
6. Scénario `fc_relayee_figee` vert dans la matrice de simulation.

**Sur le PC cible (le propriétaire) :** avec la ceinture appairée au trainer, la retirer 60 s et vérifier dans le résumé et le FIT que la FC manque pendant cette période.

## 8. Hors périmètre

- Connexion de la ceinture directement à OpenRide quand le trainer la garde (réglage de l'appareil, essai M2).
- Détection d'une FC aberrante qui varie (trop haute ou trop basse).
