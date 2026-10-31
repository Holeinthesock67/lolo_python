# Lot Q6 – Boîtier gauche du Click muet après la connexion

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Boîtier gauche du Click muet après la connexion : trace, détection, reprise | Python | — | Moyenne | Oui pour le code et la simulation ; essai sur le matériel par le propriétaire ; issue #173 |

## 1. Objectif

Essai du 25 octobre : les deux boîtiers du Zwift Click V2 sont restés connectés pendant toute la séance, mais le boîtier gauche (« − ») n'a plus envoyé d'appui 5 s après sa connexion. Il a ensuite envoyé environ 22 notifications par minute, aucune ne contenant de bouton. Tous les « − » sont venus du bouton B du boîtier droit (contournement déjà en place). Le problème était connu : `zwift_click.py` signale qu'un boîtier peut cesser d'envoyer ses boutons tant que l'application Zwift ne l'a pas « débloqué ». Ce lot cherche la cause et ajoute une reprise automatique si elle est possible.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_K8_diagnostic_click.md` (diagnostic du Click), `docs/AUDIT_FTMS_2026-10-24.md`.
2. Code : `core/src/openride_core/zwift_click.py` (protocole, `RIDE_ON`, décodage protobuf, `ClickButtons`), `input_providers.py` (`ZwiftClickProvider._connected_session` : abonnements puis écriture de `RIDE_ON` ; `_on_async` ; `ClickPair`), `tools/ble_diag.py`, `ble_sim.py`, `sim_scenarios.py`.
3. Documentation publique du protocole Zwift Click / Zwift Play (projets libres qui le décodent), à citer dans le rapport.

## 3. Prérequis

Aucun. Le lot est **délégable en deux parties** : diagnostic et code sans le matériel ici, essai sur le matériel par le propriétaire.

## 4. Travail demandé

- **Trace brute**, activée par `[drivers] click_trace_raw = true` (défaut faux) : pour chaque notification d'un boîtier, une ligne avec le boîtier (droit, gauche ou inconnu), la caractéristique, le type de message et la trame en hexadécimal. Au plus une ligne toutes les 2 s pour les messages de type répété sans bouton (avec le nombre de messages regroupés).
- **Classement des messages** dans `zwift_click.py` : boutons, batterie, message « vide » ou de maintien, et type inconnu. Ajouter un compteur par type au résumé du Click déjà écrit dans le journal.
- **Détection :** un boîtier connecté qui envoie des notifications, mais aucun bouton depuis `[drivers] click_mute_after_s` secondes (défaut 60), est déclaré « muet » une fois au journal (`Click gauche : connecté mais muet depuis 60 s`).
- **Reprise (option, défaut désactivée tant que le propriétaire n'a pas validé sur le matériel) :** `[drivers] click_rehandshake_s` (défaut 0 = jamais). Si un boîtier est muet, renvoyer `RIDE_ON` ; s'il reste muet, se désabonner puis se réabonner ; au troisième échec, déconnecter puis reconnecter. Chaque étape est notée au journal, avec au plus une tentative toutes les `click_rehandshake_s` secondes.
- **Simulation :** scénario `click_gauche_muet` dans `ble_sim.py` et `sim_scenarios.py` (boîtier gauche qui envoie des boutons pendant 5 s, puis seulement des messages sans bouton ; il se « débloque » au deuxième `RIDE_ON` en option, pour tester la reprise).
- **Rapport :** `docs/DIAG_CLICK_GAUCHE.md` (hypothèses, ce que montrent les traces, ce qu'il faut essayer sur le matériel).

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/zwift_click.py`, `input_providers.py` (classe `ZwiftClickProvider` seulement), `config.py` (`[drivers]`), `ble_sim.py`, `sim_scenarios.py`, `tools/ble_diag.py` (lecture de la trace) ; `README.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `core/tests/test_click_mute.py`, `docs/DIAG_CLICK_GAUCHE.md`.
- **Interdits :** `PressClassifier` (classement des appuis courts et longs), la correspondance des boutons, `session.py`, l'engine, le contrat IPC.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Trace brute désactivée : journal identique à aujourd'hui.
3. Scénario `click_gauche_muet` : « muet » signalé une fois après 60 s ± 1 s, compteurs par type justes, boîtier droit non touché.
4. Reprise active dans le scénario avec déblocage : appuis du boîtier gauche de nouveau reçus après le deuxième `RIDE_ON`, chaque étape notée ; sans déblocage : trois étapes puis arrêt des tentatives jusqu'au prochain appui reçu, sans boucle de reconnexion.
5. Aucune adresse Bluetooth réelle dans les tests, les traces d'exemple ou le rapport (adresses fictives `AA:BB:CC:…`).

**Sur le PC cible (le propriétaire) :** séance de 10 min avec `click_trace_raw = true`, puis avec `click_rehandshake_s = 30` ; dire si le boîtier gauche revient et joindre le résumé du Click.

## 8. Hors périmètre

- Mise à jour du micrologiciel du Click ou passage par l'application Zwift.
- Nouvelle correspondance des boutons (B = « − » reste en place).
