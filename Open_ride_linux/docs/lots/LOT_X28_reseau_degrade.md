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

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x28`).

- **Faux serveur** `fake_tile_server.py` : TileJSON, tuiles vectorielles synthétiques (un quadrillage d'environ 1,8 km, au large de la Camargue comme W15) et relief Copernicus synthétique (GeoTIFF de 120 × 120 pixels par degré, lu par le vrai fournisseur). Scénario : `latence_s`, `debit_ko_s`, `coupure_s` (comptée depuis le début du trajet ; le scénario `coupure` coupe de 10 à 22 s, en plein trajet), `erreurs`, `tronque`, `chemins`. Chaque demande est notée.
- **Générateur** : deux défauts trouvés par l'outil et corrigés.
  - Une tuile vectorielle en échec n'était jamais redemandée : la cellule de 5 km était marquée chargée. Désormais `TileSource` tient un recul par tuile et pour le TileJSON (`TILE_RETRY_S` : 2, 4, 8, 16 puis 30 s). La cellule reste « incomplète » ; ses tuiles sont redemandées à chaque `progress` une fois le recul écoulé, et le graphe est complété. Pendant la séance, rien n'attend. Au départ seulement, les tuiles en échec sont redemandées pendant 20 s au plus (`OPEN_TILES_WAIT_S`).
  - Une réponse tronquée (`http.client.IncompleteRead`) n'était pas rattrapée par `Net` ni par `Downloader`. Elle devient une erreur de téléchargement ordinaire. Une tuile illisible est supprimée et redemandée après son recul.
- **Options de test** du générateur : `--tiles-url` (autre TileJSON) et `--dem-url` (autre serveur de relief). Elles ne touchent pas `config.toml`.
- **Outil** `openride-worldgen-netcheck`. Il lance le vrai `openride-worldgen` en sous-processus, avec le cache temporaire plafonné à 20 Mo, dont 18 Mo de vieilles entrées.
  - Trajet : 25 s en temps accéléré ×40 à 12 m/s simulés, soit 12 km. C'est assez pour sortir des cellules chargées au départ : le générateur demande des tuiles vers t = 15 s, en plein trajet (à ×8, tout était chargé au départ et les pannes ne touchaient jamais le trajet). Puis une seconde séance de 5 s au même départ.
  - Scénarios dans `compiler/src/openride_compiler/worldgen/reseau/`.
  - Seuil de pause : le cycliste s'arrête, comme le core, sous 200 m de route connue devant lui. W16 n'admet aucune pause.
- **Mesuré au cloud** (critère 1) : les quatre scénarios passent, en 41 à 52 s chacun.
  - Des tuiles sont demandées pendant le trajet dans les quatre scénarios ; aucune pause d'attente (plus courte route connue devant : 1,8 km au moins).
  - Toutes les pannes servies sont reprises (coupure 21/21, erreurs 88/88, tronqué 85/85), avec un recul d'au moins 2 s.
  - Quatre des 18 vieilles entrées sont évincées, et le cache ne dépasse jamais le plafond.
  - Au retour : zéro demande au serveur, zéro téléchargement au bilan.
- **Critère 2** : `test_generator_without_retry_fails_errors_scenario` joue le scénario `erreurs` avec `TILE_RETRY_S = ()`. Le départ échoue : aucune tuile n'est redemandée.
- **Tests** : `compiler/tests/test_netcheck.py`. Ils couvrent :
  - le faux serveur (contenu, erreurs, coupure, troncature) ;
  - les scénarios mal écrits ;
  - le recul qui double, l'attente au seul départ, la tuile tronquée reprise ;
  - les vérifications du journal ;
  - les quatre scénarios et le critère 2.
- L'encodeur MVT des tests est passé dans `mvt.encode_tile`, partagé par le faux serveur et les tests. Le garde-fou réseau des tests du compilateur laisse passer la boucle locale.
