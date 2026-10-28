# Lot X17 – Gigue de la boucle physique et de l'IPC

## 1. Objectif

Critère de la série W : gigue de la boucle à 50 Hz sous 5 ms pendant la génération du monde. Jamais mesurée, même en 1.0.

## 2. À lire

`core/src/openride_core/session.py` (boucle à 50 Hz, `DT_PHYSICS`), `ipc_server.py` (trames `state` à 30 Hz), `engine/scripts/ipc_client.gd` (réception), `tools/log_report.py`.

## 3. Travail demandé

- **Core** : mesure de l'écart de chaque pas de physique à 20 ms et de chaque envoi `state` à 33,3 ms ; toutes les 60 s et en fin de séance, une ligne `Gigue : physique p50 … p99 … max … ms ; state p99 … max … ms (N pas)`. Coût négligeable (compteurs, histogramme fixe).
- **Engine** : écart entre trames `state` reçues, même ligne dans son journal (`[gigue]`).
- **`log_report --gigue`** : tableau par minute ; vérification « p99 < 5 ms » de la physique.
- **Charge** : `python -m openride_core.tools.gigue_charge` lance une séance simulée (trainer `sim`, sans engine) pendant qu'une compilation (`openride-compiler build` du parcours de démonstration) ou le faux générateur du monde ouvert tourne, et rend le verdict.

## 4. Fichiers

- **Modifiés :** `session.py`, `ipc_server.py`, `engine/scripts/ipc_client.gd`, `tools/log_report.py`, `docs/OUTILS_DE_TEST.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `core/src/openride_core/jitter.py`, `tools/gigue_charge.py`, `core/tests/test_jitter.py`.

## 5. Critères d'acceptation

1. Histogramme testé sur des pas fabriqués (p99 et maximum justes).
2. `gigue_charge --duree 30` au cloud donne un rapport (verdict en INFO au cloud, strict sur le PC).
3. Le format de la ligne « Core démarré » ne change pas (lue par `log_report`).

## 6. Hors périmètre

Réduire la gigue.
