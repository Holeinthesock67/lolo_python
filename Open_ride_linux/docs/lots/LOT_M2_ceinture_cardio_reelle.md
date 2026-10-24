# Lot M2 – Ceinture cardio réelle : mesure complète, choix de l'appareil, batterie

## 1. Objectif

`hr_monitor.py` sait se connecter à une ceinture Bluetooth (service Heart Rate 0x180D), mais il ne lit que la fréquence et prend le premier appareil qui annonce le service. Sur le PC cible, une montre Garmin qui diffuse sa fréquence cardiaque peut passer avant la ceinture, et une ceinture mal mouillée envoie des valeurs fausses avec le bit « contact absent ». Ce lot rend la ceinture réelle utilisable en séance : mesure complète, contact du capteur, choix explicite de l'appareil, batterie et diagnostic au journal.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/SIMULATION_BLE.md` (ceinture simulée).
2. Spécification Bluetooth « Heart Rate Service 1.0 » et caractéristique Heart Rate Measurement 0x2A37 : drapeaux (format 8/16 bits, contact du capteur sur 2 bits, énergie dépensée, intervalles RR en 1/1024 s).
3. Code : `core/src/openride_core/hr_monitor.py`, `core/src/openride_core/ftms.py` (`parse_hr_measurement`, utilisée aussi par `ftms_driver.py` et `tools/ble_diag.py`), `core/src/openride_core/ble_util.py` (`find_device`), `core/src/openride_core/ble_sim.py` (`SimHrStrap`), `core/src/openride_core/config.py` (`hr`, `hr_address`, `hr_name`), `core/src/openride_core/session.py` (`build_hr`, priorité de la ceinture sur le trainer).

## 3. Prérequis

Aucun.

## 4. Travail demandé

- **Décodage complet.** Nouvelle fonction `ftms.parse_hr_measurement_full(data) -> HrMeasurement` (dataclass : `bpm`, `contact` : `True`, `False` ou `None` si non géré, `energy_kj`, `rr_ms` : liste). `parse_hr_measurement` reste, inchangée pour ses appelants (elle peut s'appuyer sur la nouvelle). Trame trop courte : `ValueError`, comme aujourd'hui.
- **Contact.** Si la ceinture gère le contact et le signale absent, la mesure est ignorée (`bpm` devient `None` au bout de `STALE_S`, la séance reprend la fréquence du trainer). Une ligne de journal au passage contact présent / absent, pas une par mesure.
- **Intervalles RR.** Gardés dans le fournisseur (`last_rr_ms`, 30 dernières valeurs), sans écriture au journal de séance (voir §8).
- **Choix de l'appareil.** Quand `hr_address` est vide, la recherche (5 s) **liste** tous les appareils qui annoncent 0x180D (nom, adresse, RSSI) dans une ligne `INFO`, puis choisit : nom contenant `hr_name` s'il est donné, sinon le RSSI le plus fort, en écartant les noms qui ressemblent à une montre (`Forerunner`, `Fenix`, `Venu`, `Watch`, liste en constante) sauf s'il n'y a qu'elles. L'adresse retenue est écrite au journal avec le conseil « mettre hr_address = "…" dans config.toml ».
- **Batterie.** Lecture du niveau (service 0x180F) à la connexion s'il existe, propriété `battery_pct`, une ligne de journal ; avertissement sous 15 %.
- **Simulateur.** `SimHrStrap` gagne de quoi tester : bit de contact (réglage `contact`, événement `contact` avec `value`), intervalles RR cohérents avec `bpm`, niveau de batterie (`battery_pct`), et un second appareil facultatif `hr_watch` (montre qui diffuse). Les clés nouvelles sont validées par `sim_scenarios.py` comme les autres et documentées dans `docs/SIMULATION_BLE.md`.

## 5. Fichiers concernés

- **Nouveaux :** `core/tests/test_hr_monitor.py`.
- **Modifiés :** `core/src/openride_core/hr_monitor.py`, `core/src/openride_core/ftms.py` (ajout seulement), `core/src/openride_core/ble_sim.py` (ceinture et montre simulées), `core/src/openride_core/sim_scenarios.py` (validation des nouvelles clés), `docs/SIMULATION_BLE.md`, `README.md` (section ceinture, si elle existe), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `ftms_driver.py`, `session.py`, `journal.py` (lecture seule), contrat IPC.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Décodage : vecteurs de test écrits à la main pour chaque combinaison de drapeaux (8 et 16 bits, contact géré présent ou absent, énergie, 0 à 9 intervalles RR) ; les tests existants de `parse_hr_measurement` passent sans modification.
3. Ceinture simulée avec contact absent pendant 10 s : `bpm` passe à `None` en au plus `STALE_S`, revient au retour du contact ; deux lignes de journal en tout.
4. Ceinture et montre simulées présentes, `hr_name` vide : la ceinture est choisie (même si la montre a un meilleur RSSI) ; montre seule : la montre est choisie ; `hr_address` donné : seul cet appareil est contacté.
5. Batterie simulée à 10 % : `battery_pct` vaut 10 et un avertissement est écrit.
6. Séance complète `CoreSession` avec `--hr sim` : la fréquence de la ceinture passe toujours avant celle du trainer (test existant inchangé).

**Sur le vélo (Laurent) :** une séance avec la ceinture réelle et la montre allumée ; vérifier au journal la liste des appareils trouvés, l'appareil choisi et la batterie.

## 8. Hors périmètre

- Écriture des intervalles RR ou de la batterie au journal de séance et dans le FIT (champs `hrv`) : lot à part après M4.
- Gel observé quand la montre Garmin s'est connectée (24 octobre) : à instruire avec le matériel ; le rapport note seulement si le simulateur reproduit quelque chose.
- Ceintures ANT+.
