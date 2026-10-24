# Lot M6 – Recette sans matériel : chaque scénario simulé joué en séance complète

## 1. Objectif

`test_ble_sim.py` teste les comportements du simulateur par de courts cas isolés, et une seule séance `CoreSession` complète. Les sept scénarios intégrés (`demo`, `nominal`, `reveil_tardif`, `erreur_0x80`, `connexions_retardees`, `coupures`, `controle_refuse`) ne sont jamais joués **de bout en bout** avec la vraie boucle de séance, le journal et l'export FIT. Ce lot ajoute cette matrice : chaque scénario donne une séance dont on vérifie les invariants (pas de plantage, FIT valide, relâche du trainer, état final attendu).

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/SIMULATION_BLE.md`, `docs/lots/LOT_H4_endurance_simulee.md` (marque `slow`).
2. `docs/SRS_v1.1.md` §9 (journal, FIT) et §12 (critères de stabilité).
3. Code : `core/src/openride_core/session.py` (`CoreSession`, `build_sim_world`), `core/src/openride_core/sim_scenarios.py` (`SCENARIOS`), `core/src/openride_core/fit_export.py`, `core/src/openride_core/tools/session_summary.py`, `core/src/openride_core/tools/log_report.py` (`analyse`).
4. Tests : `core/tests/test_ble_sim.py` (`test_full_session_without_hardware`, réglages `sim_config`, ports IPC distincts), `core/tests/test_fit_sdk.py` (validation par le SDK Garmin).

## 3. Prérequis

Aucun. Les invariants sont choisis pour rester vrais avant et après M1 (renvoi après 0x80) : le nombre de reconnexions du scénario `erreur_0x80` n'est **pas** vérifié.

## 4. Travail demandé

- Nouveau fichier de tests paramétré par les noms de `SCENARIOS` (un scénario ajouté plus tard est joué sans modifier le test) ; marque `slow`.
- Pour chaque scénario, une séance en ERG **et** une en SIM (`.zwo` court fourni par le test ; parcours `demo`), de la durée du scénario plus 10 s (au plus 130 s), avec trainer, Click et ceinture simulés, journal et FIT dans `tmp_path`, puis arrêt propre.
- **Invariants vérifiés :**
  - aucune exception non rattrapée (journal Python au niveau `ERROR` vide, hors lignes attendues listées dans une table du test) ;
  - état final `FINISHED`, sauf `controle_refuse` : `ERROR` avec la raison `trainer_control_refused` ;
  - le FIT existe et passe le SDK Garmin (comme `test_fit_sdk.py`) ; son nombre d'échantillons est égal au nombre de lignes `record` du journal ;
  - le trainer simulé a reçu la relâche (pente 0 % puis Reset) et n'est plus contrôlé ;
  - aucune consigne ERG hors de la plage annoncée ; en SIM, aucune pente hors des bornes de la configuration ;
  - `summary` et `log_report` lisent le journal et le log sans erreur.
- **Table d'attentes** propre à chaque scénario, en tête du test (exemples : `coupures` → au moins une reconnexion du trainer et une du Click « − » ; `reveil_tardif` → premier échantillon avec puissance après 6 s ; `nominal` → aucune reconnexion).
- Durée totale de la matrice relevée dans le rapport ; si elle dépasse 6 min, proposer un découpage (par exemple ERG seulement en intégration continue ordinaire, SIM le dimanche) sans toucher au workflow.

## 5. Fichiers concernés

- **Nouveaux :** `core/tests/test_sim_matrix.py`.
- **Modifiés :** `docs/SIMULATION_BLE.md` (section « Tests automatiques »), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** tout le code de `core/src/` (lecture seule : un défaut trouvé est **signalé** avec son test en échec marqué `xfail(strict=True)` et sa raison, pas corrigé), `.github/workflows/` (lot J5 ouvert).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/` ; `pytest -q -m "not slow"` ne lance pas la matrice.
2. Les 7 scénarios × 2 modes sont joués ; chaque invariant du §4 a une assertion avec un message qui nomme le scénario et le mode.
3. Retirer la relâche du trainer (essai local, non livré) fait échouer la matrice : le rapport le montre.
4. Ajouter un scénario factice à `SCENARIOS` par `monkeypatch` dans un petit test à part le fait jouer sans autre changement.
5. Durée de la matrice et du reste de la suite relevées dans le rapport.

## 8. Hors périmètre

- Accélération du temps du simulateur (les délais de `FtmsDriver` sont en temps réel).
- Modification de l'intégration continue (J5).
