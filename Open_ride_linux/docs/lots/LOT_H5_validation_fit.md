# Lot H5 – Validation des FIT par le SDK officiel Garmin

## 1. Objectif

Relire les fichiers FIT produits par OpenRide avec un décodeur indépendant, le SDK Python officiel de Garmin (`garmin-fit-sdk`), en plus de `fit-tool` qui sert à les écrire. Un FIT accepté par le décodeur de Garmin a de bonnes chances d'être accepté par Garmin Connect. Le contrôle manuel dans GoldenCheetah et Garmin Connect reste le critère de la SRS, mais il devient une simple confirmation.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/SRS_v1.1.md` §9 (messages FIT attendus, semicercles, pauses).
3. Code : `core/src/openride_core/fit_export.py` (`write_fit`, `journal_to_fit`) ; `core/tests/test_journal_fit.py` (tests actuels, lecture par `fit-tool`).
4. Documentation du paquet `garmin-fit-sdk` sur PyPI (classe `Decoder`, `check_integrity`, `read`).

## 3. Prérequis

Aucun. Partir de `main` à jour.

## 4. Travail demandé

- Ajouter `garmin-fit-sdk` aux dépendances **de test** du core (`[project.optional-dependencies] dev`), justifié dans le rapport.
- Nouveau fichier `core/tests/test_fit_sdk.py`, qui produit des FIT avec le code existant puis les relit avec `garmin_fit_sdk.Decoder`.

**Cas :**

| Cas | Contrôles |
| --- | --- |
| Séance simple de 10 min | `is_fit()` et `check_integrity()` vrais ; aucune erreur de lecture (`errors` vide) ; messages `file_id`, `record`, `event`, `lap`, `session`, `activity` présents |
| Contenu de `file_id` | type `activity` ; fabricant et produit présents |
| Contenu de `session` | `sport` = cycling, `sub_sport` = virtual_activity ; totaux (distance, durée chronométrée, durée totale) cohérents avec les enregistrements à 1 % près |
| Enregistrements | positions relues en degrés à 1e-6 près des valeurs d'entrée (vérifie la conversion en semicercles) ; puissance, cadence, FC, altitude, vitesse égales aux entrées |
| Pauses | deux pauses : événements `timer` stop / start relus dans l'ordre ; temps chronométré = temps total − pauses |
| FC absente | enregistrements sans FC : champ absent, pas de valeur 0 |
| Séance de 3 h (synthétique) | lecture complète sans erreur ; nombre de `record` égal à l'entrée |
| `journal_to_fit` | FIT tiré d'un journal JSONL écrit par `JournalWriter` : mêmes contrôles que la séance simple |

Si le décodeur de Garmin signale un défaut dans un FIT d'OpenRide, **s'arrêter et le signaler** (avec la sortie du décodeur) avant de toucher à `fit_export.py`.

## 5. Fichiers concernés

- **Nouveau :** `core/tests/test_fit_sdk.py`.
- **Modifiés :** `core/pyproject.toml` (dépendance de test), `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Tous les cas du §4 ont un test, et `cd core && pip install -e ".[dev]" && pytest -q` passe en entier.
2. `fit_export.py` est inchangé, ou chaque changement est justifié par une erreur du décodeur citée dans le rapport.
3. Le rapport liste les messages et champs relus, pour servir de référence au contrôle manuel dans Garmin Connect.

## 8. Hors périmètre

- Envoi vers Garmin Connect ou tout service en ligne (hors périmètre du projet).
- Nouveaux champs FIT (puissance normalisée, zones, etc.).


## 9. Livraison (23 octobre 2026, PR #15)

- `garmin-fit-sdk>=21` ajouté aux dépendances de test (`core/pyproject.toml` et `constraints.txt`).
- `core/tests/test_fit_sdk.py` : 5 fonctions de test couvrant les 8 cas exigés (séance simple de 10 min / 600 échantillons, `file_id`, `session`, précision des coordonnées demi-cercles $\leftrightarrow$ degrés à $10^{-6}$ près, séance avec deux pauses, séance sans FC, séance de 3 h / 10 800 échantillons, conversion `journal_to_fit`).
- Aucun défaut ni avertissement signalé par `garmin_fit_sdk.Decoder` : `fit_export.py` est resté strictement inchangé.
