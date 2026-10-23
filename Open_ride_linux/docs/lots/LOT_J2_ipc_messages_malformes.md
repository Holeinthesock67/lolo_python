# Lot J2 – Robustesse du serveur IPC face aux messages malformés

## 1. Objectif

Le contrat IPC §6 dit : « Datagramme illisible : ignoré, compteur incrémenté ». Aujourd'hui, seul un JSON invalide est ignoré. Un JSON valide mais mal formé fait tomber la boucle du core (audit J du 23 octobre, constat J-M2, prouvé par script) :

| Datagramme reçu | Résultat actuel |
| --- | --- |
| `[1, 2]` (pas un objet) | `AttributeError` hors de `process_incoming_datagrams`, la boucle s'arrête |
| `{"type":"cmd","cmd_id":"3","name":"x"}` | `TypeError` (comparaison chaîne / entier) |
| `{"type":"cmd","cmd_id":null,"name":"x"}` | `TypeError` |
| `{"type":"cmd","cmd_id":5,"name":"select_route","args":null}` | `AttributeError` dans `session._on_command` |

La séance n'est pas perdue (le FIT est écrit à l'arrêt), mais elle s'interrompt. Ce lot rend le serveur tolérant, sans toucher à `session.py`.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/contracts/ipc_v1.md` §4, §5, §6 et les schémas `docs/contracts/ipc/cmd.schema.json`, `hello.schema.json`, `heartbeat.schema.json`, `bye.schema.json`.
3. Code : `core/src/openride_core/ipc_server.py` ; `core/tests/test_contract_ipc.py`, `core/tests/test_ipc_mock.py`.

## 3. Prérequis

Aucun. Partir de `main` à jour.

## 4. Travail demandé

Dans `ipc_server.py` uniquement :
- Validation légère, **sans `jsonschema` à l'exécution** (dépendance de test seulement) : le message est un objet ; `type` est une chaîne ; pour `cmd`, `cmd_id` est un entier ≥ 1 (pas un booléen), `name` une chaîne non vide, `args` absent ou un objet (absent devient `{}`).
- Tout message qui ne respecte pas ces règles est traité comme un datagramme illisible : ignoré, compteur `invalid_datagrams` incrémenté, avertissement au journal **limité** (au plus un message par tranche de 10 s, avec le nombre de rejets depuis le précédent) pour ne pas noyer `~/run_victory.log`.
- Une exception levée par le rappel `on_command` (bogue d'une commande) est rattrapée : `log.exception`, la commande est considérée comme traitée (l'accusé avance), la boucle continue.
- Les messages valides gardent exactement le comportement actuel (tests existants inchangés).

## 5. Fichiers concernés

- **Nouveau :** `core/tests/test_ipc_robustesse.py`.
- **Modifiés :** `core/src/openride_core/ipc_server.py`, `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune : le lot applique la règle « datagramme illisible » de §6 aux messages JSON non conformes. Si un cas ne semble pas couvert par le contrat, le signaler.

## 7. Critères d'acceptation

1. `cd core && pytest -q` passe en entier.
2. Les quatre datagrammes du tableau du §1, et au moins : `"texte"`, `{}`, `{"type": 3}`, `{"type":"cmd","cmd_id":true,"name":"pause"}`, `{"type":"cmd","cmd_id":-1,"name":"pause"}`, `{"type":"hello","v":"1"}`, des octets non UTF-8, sont envoyés **par une vraie socket UDP** à un `IpcServer` démarré sur des ports libres : aucun ne lève d'exception, `invalid_datagrams` compte chacun, et une commande valide envoyée ensuite est bien transmise à `on_command`.
3. Test aléatoire reproductible (graine fixe, 2 000 messages JSON construits au hasard à partir des champs du contrat) : aucune exception ne sort de `process_incoming_datagrams`.
4. Un `on_command` qui lève `RuntimeError` : la boucle continue, `last_cmd_id` avance, l'exception est journalisée.
5. Avertissement limité : 500 messages invalides en moins de 10 s donnent au plus 2 lignes `WARNING`.
6. Durée des nouveaux tests : moins de 5 s.

## 8. Hors périmètre

- Validation côté engine Godot (`ipc_client.gd`).
- Authentification ou filtrage des adresses sources (localhost uniquement, usage personnel).
