# Lot X28 – Réseau dégradé pour le monde ouvert

## 1. Objectif

W8 doit marcher hors ligne et W16 exige aucune pause d'attente. Sans outil, il faut couper sa box.

## 2. À lire

`compiler/src/openride_compiler/worldgen/vector_tiles.py` (`fetch`, `ensure`, `prefetch_plan`), `region.py`, `cache.py`, `elevation.py`, l'outil `openride-worldgen-fake` (W15).

## 3. Travail demandé

- **Faux serveur de tuiles** `compiler/src/openride_compiler/worldgen/fake_tile_server.py` (`http.server`, fil à part) : sert des tuiles vectorielles et de relief synthétiques ; scénario JSON : latence (fixe ou aléatoire), coupure entre deux instants, erreurs 429/500/503, réponses tronquées, débit limité.
- **Outil** `openride-worldgen-netcheck --scenario lent|coupure|erreurs|tronque` : lance le vrai générateur sur ce serveur (URL de tuiles remplacée), roule une trajectoire simulée et vérifie : aucune exception, pas de pause d'attente plus longue que le seuil de W16, tuiles redemandées après erreur avec recul, cache plafonné (éviction), retour au même endroit sans aucun téléchargement.
- Tests pytest sur des scénarios courts.

## 4. Fichiers

- **Nouveaux :** `fake_tile_server.py`, `compiler/src/openride_compiler/worldgen/netcheck.py`, `compiler/tests/test_netcheck.py`.
- **Modifiés :** `compiler/pyproject.toml` (point d'entrée), `docs/OUTILS_DE_TEST.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 5. Critères d'acceptation

1. Les quatre scénarios tournent au cloud en moins d'une minute chacun.
2. Un générateur modifié pour ne pas réessayer échoue au scénario `erreurs`.

## 6. Hors périmètre

Changer la politique de cache.
