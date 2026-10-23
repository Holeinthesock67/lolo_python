# Lot H1 – Intégration continue (GitHub Actions)

## 1. Objectif

Lancer automatiquement toutes les suites de tests d'OpenRide à chaque envoi et à chaque demande de fusion qui touche `Open_ride_linux/` :
- core et compilateur, en Python 3.11 (minimum déclaré) et 3.14 (version du PC cible) ;
- tests de l'engine sans écran, avec Godot 4.3 officiel ;
- contrôle que les vecteurs de route sont à jour.

Ce lot ferme le constat F6 de l'audit (partie intégration continue).

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `CLAUDE.md` (section « Commandes ») et `.claude/commands/tests.md`.
3. `docs/AUDIT_2026-10-23.md`, constat F6.
4. `core/pyproject.toml`, `compiler/pyproject.toml`, `engine/tests/run_engine_tests.sh`.

## 3. Prérequis

Aucun. Partir de `main` à jour. Les trois suites passent aujourd'hui en local : 103 tests du core, 53 du compilateur, tests de l'engine verts (vérifié le 23 octobre dans un conteneur Linux sans écran, avec Godot 4.3 téléchargé depuis GitHub).

## 4. Travail demandé

**Exception à la règle du dépôt, accordée par Laurent le 23 octobre :** GitHub n'exécute que les fichiers de `.github/workflows/` à la racine du dépôt. Ce lot crée donc `.github/workflows/openride.yml`, hors de `Open_ride_linux/`. Aucun autre fichier hors de `Open_ride_linux/`.

### 4.1 Déclenchement

- `push` et `pull_request`, filtrés par `paths: ["Open_ride_linux/**", ".github/workflows/openride.yml"]` : les autres projets du dépôt ne déclenchent rien.
- `workflow_dispatch` pour une relance manuelle.
- `concurrency` par branche, pour annuler une exécution devenue inutile.

### 4.2 Tâches

| Tâche | Contenu |
| --- | --- |
| `python` (matrice 3.11 et 3.14) | `pip install -e "core[dev]"`, puis `pip install -e "compiler[dev]"` ; `pytest -q` dans `core/` puis dans `compiler/` ; `python -m openride_core.tools.route_vectors --check` |
| `engine` | Python 3.14 et core installés (le faux core en a besoin) ; téléchargement de `Godot_v4.3-stable_linux.x86_64.zip` depuis les publications GitHub de `godotengine/godot`, mis en cache (`actions/cache`) ; `GODOT=… engine/tests/run_engine_tests.sh` |

- `working-directory: Open_ride_linux` partout.
- Dépendances système éventuelles du compilateur (`rasterio` arrive en roue binaire : vérifier qu'aucun paquet `apt` n'est nécessaire, et le noter).
- Cache `pip` activé (`actions/setup-python` avec `cache: pip` et les deux `pyproject.toml` comme clés).
- Durée totale visée : moins de 10 minutes.

### 4.3 Fichier de contraintes (deuxième moitié de F6)

- `Open_ride_linux/constraints.txt` : versions exactes des dépendances directes et de test, relevées dans un environnement où tout passe en 3.14.
- La tâche `python` en 3.14 installe avec `-c constraints.txt`. La tâche 3.11 installe sans contraintes, pour détecter tôt une rupture de compatibilité.
- `CLAUDE.md` n'est pas modifié ; le README du projet gagne une ligne sur la mise à jour de ce fichier.

### 4.4 Badge

Un badge d'état dans `Open_ride_linux/README.md`, en tête.

## 5. Fichiers concernés

- **Nouveaux :** `.github/workflows/openride.yml` (racine du dépôt, exception accordée), `Open_ride_linux/constraints.txt`.
- **Modifiés :** `Open_ride_linux/README.md` (badge et une ligne sur les contraintes), `docs/AUDIT_2026-10-23.md` (suivi de F6), `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Sur la demande de fusion du lot, les trois tâches (`python` 3.11, `python` 3.14, `engine`) sont vertes ; le lien vers l'exécution figure dans le rapport.
2. Un envoi qui ne touche que `Jeux/` ou `QR/` ne déclenche pas le workflow (vérifié par une branche de test, ou par la lecture du filtre `paths` dans le rapport).
3. Un test volontairement cassé (commit temporaire sur une branche de test, puis supprimé) fait échouer la tâche concernée ; le lien est dans le rapport.
4. La deuxième exécution utilise le cache de Godot (ligne « Cache restored » dans le journal de la tâche).
5. `constraints.txt` permet une installation en 3.14 suivie de tests verts.

## 8. Hors périmètre

- Publication de paquets, analyse de couverture en ligne, outils de style (`ruff`, etc.) : à proposer séparément.
- Tests sur le matériel (impossibles en intégration continue).


## 9. Livraison (23 octobre 2026)

Branche `lot-h1-integration-continue` (PR #11), fusionnée dans `main`. Les 5 critères d'acceptation du §7 sont tenus :
- Tâches `python (3.11)`, `python (3.14)` (avec `-c constraints.txt`) et `engine (Godot 4.3)` vertes en ~45 s ([run 39957459543](https://github.com/Holeinthesock67/lolo_python/actions/runs/39957459543)).
- Test volontairement cassé sur une branche temporaire `test-h1-echec` (supprimée ensuite) en échec comme attendu ([run 39950579981](https://github.com/Holeinthesock67/lolo_python/actions/runs/39950579981)).
- Cache de Godot 4.3 restauré dès la seconde exécution (`Cache restored from key: godot-4.3-stable-linux-x86_64`).
- `rasterio 1.4.4` s'installe en roue binaire `manylinux_2_28_x86_64` sans paquet `apt` supplémentaire.
- Aucun écart.
