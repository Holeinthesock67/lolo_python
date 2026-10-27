# Lot W2 – Cache local du monde ouvert : arborescence, versions, plafond, éviction, épinglage

## 1. Objectif

Tout ce que le monde ouvert télécharge ou génère reste sur le PC pour ne jamais être retéléchargé ni recalculé (demande du propriétaire, plan §4). Ce lot écrit le gestionnaire de ce cache, utilisé par tous les autres lots du générateur, et les commandes `cache-info` et `cache-clean`.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_W.md` §4 et §8 (W-Q3 : 5 Go ; W-Q4 : préchargement), `docs/lots/LOT_W1_contrat_monde_vivant.md` §4.2 et §4.5 (tels que validés).
2. Code : `compiler/src/openride_compiler/cache.py` (`Downloader`, `dem_cache_dir`), `elevation.py` (`CopernicusGlo30Provider.tile_path`), `core/src/openride_core/config.py` (validation des sections).

## 3. Prérequis

W1 livré (arborescence et section `[open_world]` validées).

## 4. Travail demandé

- Module `worldgen/store.py`, classe `WorldCache(root, max_bytes, clock=time.time)` :
  - arborescence du plan §4 : `brut/dem/`, `brut/osm/<region>.sqlite`, `brut/tuiles/14/<x>/<y>.mvt`, `genere/<zone>/<IX>_<IN>/` (carrés de 1 km), `genere/<zone>/far/<IX5>_<IN5>.f32`, `seances/` ;
  - index `index.sqlite` à la racine : une ligne par entrée (`key`, `kind` = `dem`, `osm`, `tile`, `square`, `far`, `bytes`, `last_used`, `pinned`, `prefetch`, `region`, `versions` en JSON) ; écritures en transaction, base en mode WAL ;
  - `dem_path(lat_sw, lon_sw)` : renvoie d'abord le fichier du cache du compilateur (`~/.cache/openride/dem/`, variable `OPENRIDE_DEM_CACHE` respectée) s'il existe, sans copie ; sinon `brut/dem/` ;
  - `touch(key)` à chaque lecture, `add(key, kind, path, versions, region=None, prefetch=False)` après chaque écriture atomique ;
  - `is_valid(key, versions)` : vrai si les versions enregistrées (générateur, sources) sont égales ; un carré périmé est à régénérer (sans téléchargement) ;
  - `evict()` : tant que la taille dépasse `max_bytes`, supprime dans cet ordre : carrés générés les moins récemment utilisés, puis tuiles lointaines, puis données brutes les moins récemment utilisées ; les entrées `prefetch` passent en dernier ; les entrées `pinned` jamais ; une entrée utilisée par la séance en cours (liste fournie) jamais ;
  - `pin(region, True | False)`, `regions()` (nom, taille, épinglée, dernière utilisation, emprise) pour le menu (W11) ;
  - `link_into(session_dir, ...)` : crée les liens symboliques des carrés vers le dossier de séance (format W1 §4.2) ;
  - reconstruction de l'index depuis le disque si `index.sqlite` manque ou est illisible (journal en français, aucun fichier supprimé dans ce cas).
- Les fichiers du dépôt du compilateur (`~/.cache/openride/dem/`) ne sont jamais supprimés par l'éviction : ils appartiennent au compilateur.
- Commandes : `openride-compiler cache-info` (taille totale, par sorte et par région, plafond) et `openride-compiler cache-clean [--generated | --all] [--yes]` (`--generated` par défaut : seulement les carrés générés ; épinglés gardés sauf `--all`).
- Configuration : section `[open_world]` validée dans `core/src/openride_core/config.py` (types, bornes : `cache_max_gb` de 0,5 à 500, `horizon_m` de 1 000 à 10 000, etc., `ConfigError` lisible) ; le compilateur lit les mêmes clés par une petite fonction de lecture TOML (`tomllib`), sans dépendre du core.

## 5. Fichiers concernés

- **Nouveaux :** `compiler/src/openride_compiler/worldgen/store.py`, `compiler/tests/test_world_store.py`.
- **Modifiés :** `compiler/src/openride_compiler/cli.py` (`cache-info`, `cache-clean`), `core/src/openride_core/config.py`, `core/tests/test_config.py` (ou un nouveau test), `docs/SRS_v1.1.md` §11 si W1 ne l'a pas complété, `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** l'engine, les contrats.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest` passe dans `core/` et `compiler/`, sans réseau.
2. Plafond de 1 Mo, cinq carrés de 300 Ko ajoutés à des instants croissants : après `evict()`, les plus anciens sont supprimés jusqu'à passer sous le plafond ; un carré épinglé ou utilisé par la séance reste.
3. Ordre d'éviction vérifié : carré généré avant donnée brute, entrée `prefetch` après les autres de même sorte.
4. Tuile de relief présente dans le cache du compilateur : `dem_path` la renvoie et rien n'est copié ; `evict()` n'y touche pas.
5. Versions différentes : `is_valid` faux ; index supprimé : reconstruit, mêmes tailles.
6. `cache-info` et `cache-clean --generated --yes` sur un cache de test : sortie lisible, carrés générés supprimés, données brutes gardées.
7. `[open_world] cache_max_gb = -1` : `ConfigError` qui nomme la clé.

## 8. Hors périmètre

Téléchargements (W3, W13), génération (W7), menu des régions (W11).
