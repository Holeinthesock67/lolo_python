# Lot BC1 – Catalogue et calcul des cartes dans le core

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série BC : catalogue `data/collection.toml` (42 cartes), calcul des cartes gagnées depuis les séances comptées, éditions de saison, cartes vues, annonce d'une carte à la fois, commande `openride-core collection` | Python | BC0, V2, MJ2 (livrés) | Moyenne | En PR (7 novembre) ; core seul, sans contrat ni affichage |

Série BC (version 5.0, badges et cartes à collectionner, demande du propriétaire du 7 novembre 2026). Plan de la série : `docs/5.0/PLAN_SERIE_BC.md`.

## 1. Objectif

Calculer en module pur les cartes gagnées par un profil, à partir des séances déjà comptées par la progression, et choisir la seule carte à annoncer.

## 2. À lire

`docs/5.0/PLAN_SERIE_BC.md` §3 à §8 ; `core/src/openride_core/progression.py` (`recompute`, `add_stats`, `SessionFacts`) ; `core/src/openride_core/profiles.py` (`counted_sources`, `owns`).

## 3. Travail demandé

- `progression.py` : sortes de lignes de jeu gardées dans les faits (`FACT_EVENT_KINDS` : ajout de `ftp_test`, `wtf_summary`, `survivor_summary`), cache des faits en version 3, `add_stats` publique.
- `data/collection.toml` : catalogue vérifié à la lecture (clés, types, dates, défis cités, familles, longueurs des textes).
- `collection.py` : `load_catalogue`, `evaluate(progress, cards, table, tz, now)`, `easter`, `season_edition`, `load_seen`, `save_seen`, `announcement`, `card_line`.
- `tools/collection.py` : `openride-core collection [--dir] [--json]`, sans rien écrire.

## 4. Critères d'acceptation

1. `core/tests/test_collection.py` : catalogue livré valide et refus de chaque erreur ; carte gagnée à la bonne séance ; heures locales (fuseau donné) ; minuit franchi ; saisons par année et fenêtre qui passe le 31 décembre ; Pâques (dates connues) ; semaines et jours d'affilée ; anniversaire et 29 février ; modes de jeu ; séances simulées et rejouées refusées dans un profil de joueur, comptées dans le profil d'essai ; séance courte, autre profil et journal repris ; séance datée dans le futur ; annonce d'une seule carte, fichier abîmé sans avalanche ; commande `--json`.
2. Les tests de la progression, des pièces et de la série R passent sans changement (expérience identique).

## 5. Hors périmètre

Contrat IPC (BC2), affichage (BC3, BC5, BC6), visuels (BC4).

## Fichiers

`core/src/openride_core/collection.py`, `core/src/openride_core/data/collection.toml`, `core/src/openride_core/tools/collection.py`, `core/src/openride_core/progression.py`, `core/src/openride_core/__main__.py`, `core/tests/test_collection.py`.
