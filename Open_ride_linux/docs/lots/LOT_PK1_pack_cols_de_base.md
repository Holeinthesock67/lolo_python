# Lot PK1 – Pack « Cols célèbres » livré avec le jeu

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Pack « Cols célèbres » livré de base : construit une fois sur le PC (`scripts/build_pack_base.sh`), rangé dans le paquet hors git avec un manifeste, installé sans réseau au premier lancement avec les contenus de départ, crédits OpenStreetMap / Copernicus / WorldCover | Python + Bash | O16, O25, O29, HP1, CL1 (recette) | Moyenne | En PR le 13 novembre |

## 1. Objectif

Décision du propriétaire du 12 novembre (21 h 49) : « le pack col est à mettre de base ». Le pack n'est plus un contenu facultatif construit chez le joueur avec le réseau : il est construit une fois sur le PC, livré dans le paquet du jeu (installateur J9) et installé au premier lancement, sans réseau. Les données OpenStreetMap et Copernicus sont créditées dans l'écran Contenus et dans la notice.

## 2. Spécification

| # | Règle |
| --- | --- |
| PK1-1 | **Construction** (`scripts/build_pack_base.sh [SORTIE]`, sur le PC, réseau) : chaque col est construit à part (`route-pack-build cols_celebres --only ID`, contrôle longueur et dénivelé à ± 5 % de `route_recipe.py`), puis installé dans un dossier de travail (`route-pack-install`, jamais dans `~/OpenRide`) et compilé (`build`, couches par défaut, comme `build-all`). Temps de chaque col (construction + compilation) et poids de chaque `.world` notés. Un col refusé n'arrête pas les autres : il est listé et le script sort en code 1. |
| PK1-2 | **Paquet** : `SORTIE/packs/cols_celebres/` (défaut `Open_ride_linux/paquet/`, ignoré par git) avec `gpx/<dossier du pack>/` (traces, fiches, `pack.toml`), `routes/<id>.world/` et `manifest.json` (format 1 : cols, empreinte de chaque trace, poids de chaque parcours, temps, liste des fichiers avec taille et SHA-256, poids total, licence et crédits). La sortie est remplacée d'un coup à la fin. Le jeu lit le paquet dans `OPENRIDE_PAQUET`, sinon dans `Open_ride_linux/paquet/`. |
| PK1-3 | **Installation** (`pack_bundle.install`) : le paquet est contrôlé (tailles et empreintes) avant toute copie ; abîmé, rien n'est installé et la raison s'affiche. Les traces vont dans `~/OpenRide/GPX/<dossier du pack>/` si aucun pack du même nom n'y est ; chaque parcours compilé est copié s'il manque **et** si la trace du joueur est celle du paquet (même SHA-256) : le catalogue le voit « prêt » et rien n'est recompilé au lancement. Jamais d'écrasement, jamais de réseau. |
| PK1-4 | **Premier lancement** : les contenus de départ (`starter`, `run --first-run`) installent le pack avec le reste (90 à 100 % de l'avancement) ; le détail de la ligne compte « N cols célèbres » et son état tient compte des cols. |
| PK1-5 | **Écran Contenus** : avec le paquet, la ligne « Pack « Cols célèbres » » ne demande plus le réseau (`network: false`, pas de confirmation), dit « livrées avec le jeu » et installe depuis le paquet. Sans paquet (installation depuis le dépôt), rien ne change : construction par le réseau (lot O29). Dans les deux cas, le détail porte les crédits. |
| PK1-6 | **Crédits** : OpenStreetMap (ODbL 1.0), Copernicus GLO-30 (© DLR, © Airbus, programme Copernicus), ESA WorldCover 2021 (CC BY 4.0), dans le manifeste, sur la ligne du pack et au §10 du guide d'utilisation (la notice d'installation J9 y renverra). |

## 3. Contrat

Aucun changement : pas de révision IPC (la 1.17 reste libre), le message `contents` garde ses champs ; les crédits passent dans `detail`.

## 4. Fichiers

- Core : `pack_bundle.py` (paquet, manifeste, contrôle, installation, outil `python -m openride_core.pack_bundle manifest|verify|info`), `contents.py` (contenus de départ, ligne et installation du pack).
- Script : `scripts/build_pack_base.sh`.
- Tests : `core/tests/test_pack_bundle.py` (faux paquet aux vrais `.world`, parcours vus « prêts » par le catalogue, pack réseau déjà installé gardé, paquet abîmé, contenus de départ, crédits, script de bout en bout avec un faux compilateur) ; `conftest.py` du core et du compilateur : `OPENRIDE_PAQUET` vide pour tous les tests.
- Docs : guide d'utilisation (§4 packs, §7 Contenus, §10 crédits), `.gitignore` (`paquet/`).

## 5. Recette PC (fil de fusion, sans le propriétaire, ≈ 1 h à 2 h selon Overpass)

Depuis `~/Games/lolo_python/Open_ride_linux`, branche du lot, après CL1 si fusionné (Khardung La, Abra Málaga).

1. **Construction** : `scripts/build_pack_base.sh 2>&1 | tee ~/OpenRide/mesures-2026-11-01-auto/rPK1/construction.log` : temps et poids de chaque col, poids total (il fixe la taille de l'installateur J9). Attendu : tous les cols construits (19, ou 21 avec CL1), code 0.
2. **Contrôle** : `core/.venv/bin/python -m openride_core.pack_bundle verify` puis `info --json > …/rPK1/pack.json`. Longueur et dénivelé dans ± 5 % : lignes « construit » du journal.
3. **Banc perf** low / medium / high sur Stelvio, Ticlio et Hakone route 1, au départ et au sommet : `python3 engine/tests/sim_bench.py --world paquet/packs/cols_celebres/routes/<id>.world --quality <q> --probe --at-m <0 puis longueur − 200>`. Budgets GPU 8 / 13 / 16 ms, pire image < 100 ms.
4. **Captures** : départ et sommet des trois cols en medium ; écran « Réglages › Contenus » avec la ligne du pack et ses crédits.
5. **Premier lancement sans réseau** : profil neuf (`HOME` temporaire), réseau coupé (`unshare -rn` ou Wi-Fi coupé), `openride --trainer mock --input keyboard` : les contenus de départ installent les cols, ils sont dans la liste des parcours, rien n'est compilé au lancement (`~/OpenRide/Logs/`).

**Part du propriétaire** : valider la planche et dire si le poids total convient.
