# Lot M4 – Journal de séance : biais ERG et coupures des appareils

## 1. Objectif

Depuis L6, le journal JSONL enregistre la cible ERG envoyée (`target_w`), mais pas la part qui vient du réglage au Click (biais ± 2 % par appui, PR #73), ni les coupures du trainer, du Click et de la ceinture. Après une séance, on ne sait donc pas si un écart à la cible vient du coureur, d'un biais volontaire ou d'une coupure. Ce lot ajoute ces deux informations au journal et au bilan `summary`.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_L6_cible_erg_journal.md` (livraison), `docs/lots/LOT_K7_bilan_seance.md`.
2. `docs/SRS_v1.1.md` §6 (ERG) et §9 (journal : liste des champs).
3. Code : `core/src/openride_core/journal.py` (`Record`, `JournalWriter`, `read_journal`), `core/src/openride_core/session.py` (écriture à 1 Hz, `erg.change_bias`, statuts des appareils), `core/src/openride_core/workout.py` (`ErgController`, biais), `core/src/openride_core/fit_export.py` (`journal_to_fit` : ne retient que les lignes `record`, `event` et `header`), `core/src/openride_core/tools/session_summary.py`, `core/src/openride_core/replay.py`, `core/src/openride_core/tools/history.py`.

## 3. Prérequis

Aucun.

## 4. Travail demandé

- **Biais.** `Record` gagne `erg_bias_pct: float | None = None` : biais appliqué à la cible à cet instant (0 sans appui), `None` hors ERG actif. `target_w` garde son sens (cible réellement envoyée, biais compris).
- **Coupures.** Nouvelle sorte de ligne `{"kind": "device", "ts": ..., "device": "trainer" | "click_plus" | "click_minus" | "hr", "state": "up" | "down"}`, écrite au **changement** d'état seulement (pas à 1 Hz), par la méthode `JournalWriter.device(...)`. Les états viennent de ce que la session connaît déjà (`status` du pilote, `connected` des fournisseurs) : aucune entrée-sortie Bluetooth ajoutée dans la boucle.
- **Compatibilité.** Les lignes `event` gardent leurs quatre valeurs (`fit_export` lève une erreur sur une valeur inconnue : c'est pour cela que les coupures ont leur propre sorte de ligne). Un journal antérieur se relit comme avant (`recover`, `summary`, `replay`, `history`, `log_report`).
- **Bilan.** `summary` (texte et `--json`) :
  - par bloc ERG : biais moyen et écart à la cible **sans biais** (cible du `.zwo` × FTP), à côté de l'écart actuel ;
  - section `devices` : nombre de coupures et durée totale par appareil ; absente pour un journal sans lignes `device`.
  - Les clés JSON existantes ne changent pas ; les nouvelles sont documentées en tête du module.

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/journal.py`, `core/src/openride_core/session.py`, `core/src/openride_core/tools/session_summary.py`, tests correspondants (`test_journal_fit.py`, `test_session_summary.py`, et un nouveau `core/tests/test_journal_devices.py` pour la séance simulée : `test_ble_sim.py` est modifié par M1), `docs/SRS_v1.1.md` §9, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `fit_export.py`, `replay.py`, `tools/history.py` (lecture seule : ils doivent continuer à marcher sans changement), contrat IPC.

## 6. Modifications de contrat autorisées

`docs/SRS_v1.1.md` §9 : ajouter le biais ERG à la liste des champs et décrire les lignes `device`, en précisant qu'ils sont absents des journaux antérieurs au 24 octobre 2026.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Séance simulée ERG (`MockDriver`, temps accéléré, `.zwo` de deux blocs) avec deux appuis « + » au bloc 2 : `erg_bias_pct` vaut 0 au bloc 1, 4 après les appuis ; `null` en SIM et en pause.
3. Séance avec le Bluetooth simulé et le scénario `coupures` : lignes `device` `down` puis `up` pour le trainer, le Click « − » et la ceinture, une par changement ; `summary --json` compte une coupure par appareil, durées à ± 2 s du scénario.
4. `recover` sur ce journal : FIT identique, octet pour octet hors horodatage de création, à celui obtenu en retirant les lignes `device` du journal.
5. Les journaux de test existants donnent exactement le même `summary` qu'avant le lot.

## 8. Hors périmètre

- Biais ou coupures dans le FIT (champs de développeur).
- Affichage dans l'engine (F2, G).
- Intervalles RR (voir M2, §8).

## 9. Livraison (24 octobre 2026)

- `journal.py` : `Record.erg_bias_pct` (biais − 100 %, `None` hors ERG actif), `JournalWriter.device(device, state, ts)` (valeurs contrôlées), en-tête du module.
- `session.py` : état des appareils lu à chaque pas sur ce que la session connaît déjà (`status` du pilote ou `connected` de `MockDriver`, `status` des `ZwiftClickProvider` et adresse du boîtier tenu, `connected` de la ceinture) ; une ligne `device` par changement, l'état à l'ouverture du journal servant de référence. Le boîtier « + » est celui de `click_address` (à défaut l'adresse du « + » réel, `sim_scenarios.PLUS_ADDRESS`) ; un boîtier jamais connecté n'a pas d'état.
- **Fichier hors liste, indispensable :** `recorder.py` (`SessionRecorder.device`, réécriture des lignes `device` à la réouverture du journal) : la session écrit par lui et non directement par `JournalWriter`. `records` et `events` ne voient pas ces lignes : le FIT de fin de séance ne change pas.
- `session_summary.py` : par bloc, `bias_pct`, `target_nobias_w`, `delta_nobias_w` ; section `devices` ({drops, down_s}). Ces clés n'apparaissent que si le journal porte ces informations : un journal antérieur donne exactement le même bilan (tests existants inchangés).
- Tests : `core/tests/test_journal_devices.py` (critère 2 : `test_erg_bias_is_journaled`, `test_bias_is_null_in_sim` ; 3 : `test_coupures_scenario_device_lines`, marqué `slow`, ~65 s ; 4 : `test_recover_ignores_device_lines` ; bilan : `test_summary_devices_section`). Critère 5 : `test_session_summary.py` inchangé et vert.
