# Lot X11 – Contrôle d'un FIT de séance réelle

## 1. Objectif

Ligne 21 de la recette 1.0 : le FIT d'une vraie séance doit s'importer dans Garmin Connect et GoldenCheetah. H5 valide les FIT de test, pas ceux d'une séance réelle (pauses, coupures, FC figée). Ce lot vérifie un FIT réel **en local** : les fichiers ne quittent jamais le PC et ne vont jamais dans le dépôt.

## 2. À lire

`core/src/openride_core/fit_writer.py` (ou le module FIT du core), `core/tests/test_fit_sdk.py` (SDK officiel Garmin, extra `dev`), `journal.py`.

## 3. Travail demandé

- **`openride-core fit-check FICHIER.fit [--journal JOURNAL.jsonl] [--json]`** : décodage complet par le SDK Garmin (erreurs et avertissements) ; contrôles : messages obligatoires (`file_id`, `session`, `lap`, `activity`), horodatage croissant, puissance et cadence continues hors pauses, trous exactement aux pauses du chronomètre, FC figée (même valeur plus de 15 s alors que la puissance varie), distance et durée face au journal (± 1 %), totaux de `session` face aux enregistrements.
- Sortie : une ligne OK/ATTENTION/ÉCHEC par contrôle ; code 0, 1 si un échec.
- Sans SDK installé : message lisible (installer l'extra `dev`).

## 4. Fichiers

- **Nouveaux :** `core/src/openride_core/tools/fit_check.py`, `core/tests/test_fit_check.py` (FIT fabriqués par le core lui-même : séance propre, pause, trou, FC figée).
- **Modifiés :** `__main__.py` (sous-commande), `README.md` et `CLAUDE.md` (liste des commandes, comparée par `test_docs_coherence`), `docs/OUTILS_DE_TEST.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 5. Critères d'acceptation

1. Les quatre FIT fabriqués donnent les verdicts attendus.
2. Aucun fichier d'activité réel n'est ajouté au dépôt (scanner X23).

## 6. Hors périmètre

L'import dans Garmin Connect lui-même (fait par le propriétaire).
