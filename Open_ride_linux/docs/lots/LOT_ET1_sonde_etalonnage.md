# Lot ET1 – Sonde d'étalonnage du trainer (Spin Down Control FTMS)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| `openride-ble-diag spindown` : le trainer fait-il vraiment l'étalonnage qu'il annonce ? Sans écran | Python | — | Petite | En revue (PR à venir) |

## 1. Objectif

Audit du 22 novembre (§10, étalonnage absent face aux jeux du même type), lancé par le propriétaire le 22 novembre (« Étalonnage et diagnostic »). Le trainer annonce `spin_down_control` (relevé du 22 octobre, `docs/spikes.md` §4) mais OpenRide ne l'a jamais envoyé. Cadrage : `plans/CADRAGE_ETALONNAGE_FTMS_2026-11-22.md` des fichiers du projet. L'écran « Étalonner le trainer » ne se fait que si la sonde réussit sur le vrai vélo.

## 2. Travail fait

- `ftms.py` : opcode 0x13 (`cmd_spin_down`), vitesses cibles de la réponse, états 0x14 (« demandé », « arrêtez de pédaler », réussite, échec), Training Status utiles, compensation d'offset du Cycling Power Feature (lecture seule).
- `tools/spindown.py` (`probe`) : capacités, prise de contrôle, 0x13 « lancer », écoute jusqu'au résultat ou au délai, consignes écrites pour le cycliste, Reset dans tous les cas. Verdicts : `success`, `error`, `refused`, `not_announced`, `no_response`, `timeout`. Rapport sans nom ni adresse du trainer.
- `openride-ble-diag spindown [--duration 90]`.
- BLE simulé : option `spin_down` du trainer (`ok`, `error`, `refuse`) et `spin_down_stop_s`.

## 3. Tests

`core/tests/test_spindown_probe.py` : trames, réussite avec les étapes dans l'ordre et contrôle rendu, échec, refus, trainer qui n'annonce rien (aucune commande), rapport sans identité.

## 4. Essai sur le vélo (5 min, après le 28 novembre, planifié par le coordinateur)

Zwift, montre et téléphone déconnectés du trainer. Depuis `/home/utilisateur/Games/lolo_python/Open_ride_linux/core` :

```bash
source .venv/bin/activate && openride-ble-diag spindown --duration 90
```

Suivre les lignes `>>>` du terminal. À rapporter : la ligne « Résultat » et le fichier `spike_reports/*_spindown.json`.

## Livraison

Branche `claude/project-thread-4vofwp-etalonnage`. Outil seul, sans engine ni écran : CI et cloud seulement, pas de banc PC.
