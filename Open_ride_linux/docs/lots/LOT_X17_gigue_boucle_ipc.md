# Lot X17 – Gigue de la boucle physique et de l'IPC

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : Gigue de la boucle physique et des trames `state`, sous charge | Python + GDScript | — | Petite | **Livré le 28 octobre** (branche `claude/project-thread-818r6t-x17`) ; issue #215 |

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

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x17`).

- **`jitter.JitterMeter`** : histogramme fixe (cases de 0,05 ms jusqu'à 100 ms, puis une case « au-delà ») ; quantile à une case près, maximum exact. La boucle de `session.py` compte l'écart de chaque pas à 20 ms et le retard de chaque trame `state` sur son échéance fixe de 33,3 ms. Les trames partent sur un pas de physique : ce retard reste sous 20 ms par construction, et l'écart entre deux trames vaut 20 ou 40 ms. Le retard sur l'échéance est donc la seule mesure utile.
- **Journal** : à côté de la ligne `Perf` (toutes les 60 s), `Gigue : physique p50 … p99 … max … ms ; state p99 … max … ms (N pas)` pour la minute, puis `Gigue (séance entière) : …` à l'arrêt. La ligne « Core démarré » ne change pas.
- **Engine** : `ipc_client.gd` range l'écart entre trames `state` reçues (cases de 1 ms jusqu'à 500 ms) et écrit une ligne `[gigue] state : écart entre trames p50 … p99 … max … ms (N trames)` par minute. Les trames sont lues à chaque image : l'écart comprend la cadence de l'affichage.
- **`log_report --gigue`** : tableau par minute, ligne de la séance, lignes de l'engine ; verdict « p99 de la physique < 5 ms » sur la séance entière, sinon sur la pire minute ; code 1 au-delà. Le format est vérifié contre le source par `test_log_report`.
- **`python -m openride_core.tools.gigue_charge`** : séance simulée sans engine (HOME temporaire) pendant une charge.
  - `compilation` : `openride-compiler build` en boucle d'une trace fabriquée de 40 km, sans réseau, couches route, terrain et segments. Le MNT est une liste de tuiles qui ne couvre pas la trace : altitude 0.
  - `cpu` : un calcul par cœur.
  - `aucune` : la référence.
  - Le faux générateur du monde ouvert n'est pas branché : la compilation suffit au critère.
  - Verdict informatif au cloud, `--strict` sur le PC.
- **Mesuré au cloud** (`--duree 65`, compilation) : physique p50 0,30, p99 2,00, max 25,85 ms ; retard des trames `state` p99 15,5 ms. Sur 30 s, 8 compilations terminées pendant la séance.
- Tests :
  - `core/tests/test_jitter.py` (7 tests) : quantiles et maximum sur des pas fabriqués, case « au-delà », ligne reconnue, rapport par minute et séance, `log_report --gigue`, courte séance simulée, trace fabriquée ;
  - `engine/tests/unit/test_state_gap.gd` (6 vérifications) ;
  - motif ajouté à `test_log_report`.

