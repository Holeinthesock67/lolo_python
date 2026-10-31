# Lot W14 – Enregistrer la balade comme parcours de la bibliothèque

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Enregistrer la balade comme parcours de la bibliothèque (GPX puis `.world`) | Python | W9 | Petite | Oui, après W9 (issue #269) |

## 1. Objectif

À la fin d'une séance en monde ouvert, proposer d'enregistrer la balade comme un parcours ordinaire (plan §2.5), pour la refaire plus tard en mode classique avec bots et segments.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_W.md` §2.5, `LOT_W9_core_monde_ouvert.md`.
2. Code : `core/src/openride_core/journal.py`, `catalog.py`, `launch_compile.py` (compilation au lancement, N11), `compiler/src/openride_compiler/gpx.py`, `cli.py` (`build`).

## 3. Prérequis

W9 livré.

## 4. Travail demandé

- Le core garde, pendant la séance, la suite des arêtes réellement parcourues (identifiants et sens), telle que publiée par le générateur.
- `end_session` avec `save` vrai en monde ouvert : écrit en plus `~/OpenRide/GPX/<id>.gpx` (`GPX_DIR` de `config.py`, compilé au lancement par N11), points tous les 10 m de la route **parcourue** (pas de la route engagée au-delà de l'arrivée), altitude du profil, nom « Balade du <date> » ; si la séance dépasse 500 m.
- Le parcours est compilé comme toute nouvelle trace au prochain lancement (N11), ou tout de suite par `openride-compiler build` en tâche de fond si le core en a le temps ; la compilation réutilise le relief et la base locale déjà en cache (aucun téléchargement si la zone est en cache).
- Commande `openride-core open-world-save <id>` pour le faire après coup depuis le dossier de séance (tant qu'il existe).
- Vie privée : le GPX reste dans le dossier personnel, jamais dans le dépôt ; aucun test n'utilise de coordonnées réelles du propriétaire.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/open_world_save.py`, `core/tests/test_open_world_save.py`.
- **Modifiés :** `core/src/openride_core/session.py` (appel en fin de séance), `__main__.py` (sous-commande), `docs/SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest` passe dans `core/`.
2. Séance simulée avec le faux générateur (W15) : 12 km parcourus, un changement de branche ; le GPX suit exactement les arêtes parcourues, 12 km à 20 m près.
3. Le GPX se compile (`openride-compiler build --offline` avec le relief synthétique) et le `.world` obtenu a la même longueur à 1 % près.
4. Séance de 300 m : pas de GPX.

## 8. Hors périmètre

Partage des balades, segments automatiques (série T).
