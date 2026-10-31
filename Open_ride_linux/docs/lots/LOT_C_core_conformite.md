# Lot C – Mise en conformité du core avec le contrat IPC

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Mise en conformité du core avec le contrat IPC (défauts de l'audit) | Python | — | Petite | **Livré le 23 octobre** |

## 1. Objectif

Corriger dans `openride-core` les écarts au contrat relevés par l'audit du 23 octobre 2026 (`docs/AUDIT_2026-10-23.md`) : E1, E2, M1, M2, M4, M5, la partie IPC de M6, M7 et F7. Ajouter les tests de contrat qui empêcheront ces écarts de revenir.

C'est un lot de **petite taille** et sans dépendance : un bon premier lot à confier.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/AUDIT_2026-10-23.md` §3.
3. `docs/contracts/ipc_v1.md` en entier, et les schémas `docs/contracts/ipc/*.schema.json`.
4. Code :
   - `core/src/openride_core/ipc_server.py`, `session.py`, `ftms_driver.py`, `ftms.py`, `config.py` ;
   - `core/src/openride_core/tools/run_mock_session.py` ;
   - les tests de `core/tests/`, en particulier `test_drivers_session.py`, dont les doublures BLE (`FakeClient`) sont à réutiliser.

## 3. Travail demandé

### C1. Redémarrage de l'engine (audit E1)

- **Défaut :** `IpcServer.last_cmd_id` n'est jamais remis à zéro. Un engine relancé numérote de nouveau ses commandes à partir de 1, et le core les ignore.
- **Correction :** à chaque `hello` valide, remettre `last_cmd_id` à 0 avant de répondre par `hello_ack`.
- **Contrat :** préciser dans `ipc_v1.md` §4 que « le compteur `cmd_id` est propre à une instance de l'engine ; le core le remet à zéro à chaque `hello` ».

### C2. Panne d'écriture du journal (audit E2)

- **Défaut :** une exception dans `JournalWriter.record` ou `event` remonte hors de `CoreSession._step` et arrête la boucle. À l'arrêt, `_finish` réécrit dans le journal fermé et le FIT n'est pas produit.
- **Comportement attendu** (contrat §6, ligne « Échec d'écriture du journal ») :
  - rattraper `OSError` et `ValueError` à chaque écriture ;
  - envoyer l'erreur `recording_failed` avec le message ;
  - passer en `PAUSED`. Ajouter une valeur `recording_failed` à `pause_reason`. C'est un ajout compatible : compléter l'énumération dans le contrat §3 et dans `state.schema.json`.
- **Mémoire tampon :**
  - pendant la panne, garder les enregistrements en mémoire, au plus 3 h à 1 Hz ;
  - à la reprise (`resume`), rouvrir un **nouveau** fichier journal ;
  - y réécrire l'en-tête, l'événement `start` d'origine et le contenu de la mémoire tampon ;
  - si la réouverture échoue encore, rester en pause et renvoyer l'erreur.
- **Fin de séance :** si le journal est inutilisable, produire le FIT à partir des données en mémoire (`fit_export.write_fit` accepte des listes).

### C3. Résumé de fin de séance (audit M1)

`summary` doit contenir exactement ce qu'imposent le contrat §3 et le schéma :
- `duration_s` : temps chronométré ;
- `distance_m` ;
- `avg_power_w` : 0 si aucune puissance ;
- `fit_path` : `null` si la séance n'est pas enregistrée.

### C4. Refus du contrôle FTMS et plage de puissance (audit M2)

**Refus du contrôle :**
- le pilote expose déjà `control_refused` ;
- s'il passe à vrai **après deux tentatives de reprise de contrôle**, la session passe en `ERROR` et envoie l'erreur `trainer_control_refused` ;
- ajouter un compteur de tentatives dans `FtmsDriver` ;
- un `start` depuis `ERROR` n'est pas permis ; un nouveau `select_route` sort de `ERROR`.

**Plage de puissance :**
- à la connexion, lire `SUPPORTED_POWER_RANGE` (0x2AD8, `ftms.parse_power_range`) si elle est exposée ;
- `set_target_power` borne la consigne à cette plage, ou à 0–2 000 W si elle est inconnue.

### C5. `hello_ack` construit depuis la configuration (audit M4)

- `ftp_w`, `gears_total` et `theme` viennent de la `Config` chargée.
- Passer ces valeurs à `IpcServer` à la construction, au lieu des constantes de la ligne 212.

### C6. Coefficient de difficulté (audit M7)

- La pente envoyée au trainer est multipliée par `trainer.difficulty_pct / 100` (SRS §5). Le coefficient s'applique avant la limitation de vitesse de variation et avant le bornage −10 / +16 %.
- La vitesse virtuelle continue d'utiliser la pente réelle.
- `state.grade_sent` reflète la valeur envoyée.

### C7. Suppression de la boucle en double (audit M5)

- `tools/run_mock_session.py` devient une enveloppe de quelques lignes : elle lance `CoreSession` avec `MockDriver`, le clavier et `autostart`.
- Toute sa logique propre est retirée.
- La commande `python -m openride_core.tools.run_mock_session` continue de fonctionner.

### C8. Schémas et tests de contrat (audit M6, F7)

**Schémas :**
- `cmd.schema.json` : ajouter `input_event` à l'énumération des noms ;
- `state.schema.json` : ajouter `recording_failed` à `pause_reason` (C2) ;
- nouveaux schémas dans `docs/contracts/ipc/` : `hello`, `hello_ack`, `heartbeat`, `input`, `error`, `shutdown`, `bye` (un fichier par message).

**Nouveau fichier de test `core/tests/test_contract_ipc.py`** :
- valide contre son schéma chaque trame émise par le core dans ces états : `IDLE`, `READY`, `RUNNING`, `PAUSED` (chaque raison), `FINISHED` avec et sans FIT, `ERROR`. Valider aussi `hello_ack`, `input`, `error` et `shutdown` ;
- valide les trames d'exemple du contrat §7 ;
- vérifie qu'une trame `state` complète, avec un objet `erg` rempli et une liste `bots` de 10 éléments `{id, s, v}`, ne dépasse pas 1 400 octets une fois encodée.

**Méthode :** pour capter les trames, remplacer `IpcServer.send_raw` dans les tests, ou écouter sur un port de test, comme le fait déjà `test_ipc_mock.py`.

**Dépendance de développement :** `jsonschema`.

## 4. Fichiers concernés

- **Modifiés :**
  - `core/src/openride_core/ipc_server.py`, `session.py`, `ftms_driver.py`, `journal.py` (si nécessaire pour C2) ;
  - `core/src/openride_core/tools/run_mock_session.py` ;
  - `core/pyproject.toml` (dépendance de développement) ;
  - `docs/contracts/ipc_v1.md` (C1, C2, journal des changements) ;
  - `docs/contracts/ipc/cmd.schema.json`, `state.schema.json`.
- **Nouveaux :**
  - `docs/contracts/ipc/<message>.schema.json` (7 fichiers) ;
  - `core/tests/test_contract_ipc.py` ;
  - tests ajoutés dans les fichiers existants.

## 5. Modifications de contrat autorisées

Uniquement des ajouts compatibles, version `v` = 1 inchangée :
- la règle de remise à zéro de `cmd_id` (C1) ;
- la valeur `recording_failed` de `pause_reason` (C2) ;
- les schémas manquants (C8).

Chaque modification a sa ligne au journal des changements du contrat (§8).

## 6. Critères d'acceptation

1. `pytest` passe en entier dans `core/`.
2. **C1 :** test qui reproduit l'audit (`hello`, `cmd_id` 5, nouveau `hello`, `cmd_id` 1) ; la seconde commande est traitée.
3. **C2 :**
   - un test ferme le fichier journal pendant `RUNNING` : la boucle continue, l'état passe à `PAUSED` / `recording_failed` et une trame `error` part ;
   - après `resume`, un nouveau journal contient toutes les secondes de la séance, sans trou ni doublon ;
   - la fin de séance produit un FIT lisible.
4. **C3 :** la trame `FINISHED` valide `state.schema.json`.
5. **C4 :**
   - avec le faux client BLE, deux réponses `CONTROL_NOT_PERMITTED` consécutives mettent la session en `ERROR` et envoient `trainer_control_refused` ;
   - une plage lue de 0 à 1 000 W borne une consigne de 1 500 W à 1 000 W.
6. **C5 :** avec `ftp_w` = 280 et 22 vitesses en configuration, `hello_ack` les reflète.
7. **C6 :** avec `difficulty_pct` = 50, `grade_sent` vaut la moitié de la pente effective (hors limitation), et la vitesse virtuelle est inchangée par rapport à 100 %.
8. **C7 :** `run_mock_session.py` fait moins de 40 lignes. Un lancement de 3 s produit un journal.
9. **C8 :** `test_contract_ipc.py` couvre les messages listés, et la taille maximale d'une trame est vérifiée.
10. La couverture de `session.py` et de `ipc_server.py` progresse. Donner les chiffres avant et après (`pytest --cov`).

## 7. Hors périmètre

- Le côté engine du contrat (lot D).
- Le mode ERG (lot F).
- La stabilité du Click, à traiter en interne avec le matériel.

## 8. Livraison (23 octobre 2026)

Réalisé par Claude, branche `lot-c-conformite`, fusionné dans `main`. Tous les critères du §6 sont tenus (55 tests à la livraison du lot, 75 après le lot A). Couverture : `ipc_server.py` de 77 à 81 %, `session.py` de 66 à 68 %, totale de 64 à 70 %.

**Écarts assumés :**
- C2 est porté par un nouveau module, `recorder.py` (`SessionRecorder`), plutôt que par `journal.py` : copie complète de la séance en mémoire, réouverture d'un journal `…_reprise-N.jsonl`, FIT produit depuis la mémoire.
- C3 : `summary.fit_path` peut valoir `null`. Le schéma a été élargi (ajout compatible, journal du contrat).
- C4 : le compteur de refus n'est remis à zéro que par une **consigne** acceptée. Une prise de contrôle acceptée suivie d'une consigne refusée aurait sinon bouclé sans fin.
- **Défaut de contrat découvert en écrivant les tests :** dans la trame `state`, le champ `v` désigne à la fois la version et la vitesse, et la vitesse l'emporte. Le schéma `state` contenait ce champ en double. Correction par clarification du contrat (§1) ; renommage en `speed` prévu pour un contrat v2.
- Le ré-envoi d'un `hello` par un même engine remet aussi `last_cmd_id` à 0 : une ancienne commande renvoyée après ce `hello` serait retraitée. Risque faible, noté pour le lot D.
