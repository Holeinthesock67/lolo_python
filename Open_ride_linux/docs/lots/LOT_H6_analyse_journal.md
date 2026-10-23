# Lot H6 – Analyseur du journal de séance

## 1. Objectif

Après chaque essai sur le vélo, le propriétaire colle des extraits de `~/run_trainer.log` pour qu'on les analyse. Ce lot fournit un outil qui produit directement le résumé utile :
- mesures de performance (`Perf`) comparées aux seuils de décision Rust (pas p99 > 5 ms, retard > 20 ms, CPU > 15 %) ;
- connexions, pertes et reconnexions du trainer et du Click, avec leurs heures ;
- changements d'état de la séance et leurs raisons ;
- appuis du Click reconnus ;
- avertissements et erreurs.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `.claude/commands/seance.md` : ce que l'analyse manuelle regarde aujourd'hui, et les seuils (pas p99 > 5 ms, retard > 20 ms, CPU > 15 %). `CLAUDE.md` et ce fichier les attribuent à la SRS §14.1, mais la SRS v1.1 ne les contient pas : les reprendre comme constantes nommées en tête du module, avec ce renvoi.
3. `docs/SRS_v1.1.md` §12 (exigences non fonctionnelles).
4. Code, pour les messages exacts du journal :
   - format des lignes : `__main__.py` (`%(asctime)s %(levelname)-7s %(name)s %(message)s`) ;
   - `session.py` (lignes `Perf :`, `Séance : X -> Y (raison)`, `Trainer perdu`, `Engine perdu`, `Parcours … chargé`, `Entraînement …`) ;
   - `ftms_driver.py` (`Trainer connecté`, `Reconnexion au trainer`, `Commande 0x.. refusée`) ;
   - `input_providers.py` (`Zwift Click connecté`, `Zwift Click déconnecté`, `Click : <appui>`) ;
   - `scripts/openride-dev.sh` (emplacement du journal, `OPENRIDE_LOG`).

## 3. Prérequis

Aucun. Partir de `main` à jour.

## 4. Travail demandé

### 4.1 Module `core/src/openride_core/tools/log_report.py` (nouveau)

Lancement : `python -m openride_core.tools.log_report [JOURNAL] [--json]` (défaut : `~/run_trainer.log`). Pas de nouvelle entrée dans `pyproject.toml` ni dans `__main__.py`, pour ne pas toucher aux fichiers d'autres lots.

**Analyse (fonction pure `analyse(lines: Iterable[str]) -> Report`, testable) :**
- **Perf :** nombre de relevés ; maximum et médiane de chaque mesure ; liste des relevés au-delà des seuils, avec l'heure.
- **Trainer :** heures de connexion, de perte, de reconnexion ; durée totale de déconnexion ; commandes refusées.
- **Click :** heures de connexion et de déconnexion ; nombre de déconnexions par heure ; délai moyen de reconnexion ; nombre d'appuis par type (`plus_short`, `minus_short`, `plus_long`, `minus_long`).
- **Séance :** transitions d'état avec raison ; pauses automatiques (`engine_lost`, `trainer_lost`) et leur durée.
- **Problèmes :** lignes WARNING et ERROR regroupées par message (texte sans les valeurs variables), avec le nombre et la première heure.
- Une ligne illisible est comptée et ignorée ; l'outil ne plante jamais sur un journal tronqué.
- Plusieurs séances dans le même fichier (le script ajoute à la fin) : découpage sur `Core démarré`, l'analyse porte sur la dernière par défaut, `--all` pour toutes.

**Sortie :** texte français de 10 à 25 lignes, lisible dans un terminal ; `--json` donne le même contenu en JSON.

### 4.2 Journaux de test

`core/tests/data/logs/` : 3 journaux courts, **écrits à la main** à partir des formats du code (pas de journal personnel) :
- séance normale ;
- séance avec 2 déconnexions du Click et 1 perte du trainer ;
- journal tronqué au milieu d'une ligne, avec deux séances.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/tools/log_report.py`, `core/tests/test_log_report.py`, `core/tests/data/logs/*.log`.
- **Modifiés :** `.claude/commands/seance.md` (utiliser l'outil dans l'analyse après essai), `README.md` (une ligne), `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune. Les messages du journal ne changent pas : si un message est trop ambigu pour être analysé, le signaler dans le rapport au lieu de le modifier.

## 7. Critères d'acceptation

1. `cd core && pytest -q` passe en entier.
2. Sur le journal à déconnexions, le rapport compte exactement 2 déconnexions du Click et 1 perte du trainer, avec les bonnes heures et durées.
3. Un relevé `Perf` avec un pas p99 de 6 ms est signalé comme dépassement ; un relevé à 4 ms ne l'est pas.
4. Le journal tronqué est analysé sans exception, et la ligne illisible est comptée.
5. `--json` produit un JSON valide qui contient les mêmes nombres que la sortie texte.
6. Un test vérifie que chaque motif reconnu correspond à un message réellement présent dans le code source (recherche du texte dans `src/`), pour détecter qu'un message a changé.

## 8. Hors périmètre

- Analyse du journal JSONL de séance (`.journal/`) : c'est le travail de `recover` et du FIT.
- Graphiques.
