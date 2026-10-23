# Lot I2 – Catalogue de parcours : compilation en lot et liste

## 1. Objectif

Préparer le menu des parcours (lot G) et simplifier l'usage en attendant :
- compiler d'un coup toutes les traces de `~/OpenRide/GPX/` qui ne le sont pas encore, ou qui ont changé ;
- lister les parcours avec leur statut : compilé, à compiler, à recompiler, invalide.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/SRS_v1.1.md` §7 (« Depuis le menu : un parcours non compilé affiche « à compiler » ») et §11 (arborescence).
3. `docs/contracts/world_format_v1.md` §2 (manifeste : source avec somme SHA-256 du GPX) et §10.
4. Code :
   - `compiler/src/openride_compiler/cli.py` (`cmd_build`, `cmd_verify`, `cmd_info`) ;
   - `compiler/src/openride_compiler/writer.py` et `verify.py` ;
   - `core/src/openride_core/route.py` (`routes_dir`, `find_world`, `load_world`, `WorldError`).

## 3. Prérequis

Lot B2 livré. Partir de `main` à jour.

## 4. Travail demandé

### 4.1 Côté core : `core/src/openride_core/catalog.py` (nouveau)

```python
@dataclass(frozen=True)
class RouteEntry:
    id: str                      # nom du parcours (dossier sans « .world »), ou nom du GPX
    name: str
    status: str                  # "ready", "to_compile", "outdated", "invalid"
    length_m: float | None
    route_type: str | None       # open, loop, out_and_back
    has_terrain: bool
    gpx_path: Path | None
    error: str | None = None

def list_routes(routes_root: Path, gpx_dir: Path) -> list[RouteEntry]: ...
```

- `ready` : `.world` lisible par `load_world`, dont la source correspond à un GPX présent et inchangé (même SHA-256), ou dont le GPX a disparu.
- `outdated` : `.world` lisible, mais le GPX source a changé (SHA-256 différent).
- `to_compile` : GPX sans `.world` correspondant.
- `invalid` : `.world` illisible (message de `WorldError`).
- La correspondance GPX ↔ `.world` se fait par la source du manifeste (nom et SHA-256), pas seulement par le nom.
- Le parcours de démonstration est toujours listé en premier.
- Aucune dépendance au compilateur ; lecture seule ; temps visé : moins de 200 ms pour 50 parcours (le SHA-256 d'un GPX est recalculé, le terrain n'est pas lu).
- `GPX_DIR = OPENRIDE_HOME / "GPX"` ajouté à `config.py`, à côté de `WORKOUTS_DIR`.

### 4.2 Côté compilateur

- `openride-compiler list [--gpx-dir D] [--routes-dir R]` : tableau des parcours (statut, longueur, type, terrain), à partir de `openride_core.catalog.list_routes` si le core est installé, sinon d'une lecture équivalente minimale (le compilateur n'a pas de dépendance obligatoire au core : documenter le choix retenu).
- `openride-compiler build-all [--gpx-dir D] [--offline] [--dry-run]` : compile les entrées `to_compile` et `outdated`, l'une après l'autre ; une erreur sur une trace est affichée et n'arrête pas les suivantes ; résumé final (compilées, ignorées, en erreur) ; code de sortie 1 si au moins une erreur.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/catalog.py`, `core/tests/test_catalog.py`, `compiler/tests/test_build_all.py`.
- **Modifiés :** `core/src/openride_core/config.py` (`GPX_DIR` seulement), `compiler/src/openride_compiler/cli.py` (deux sous-commandes), `README.md` et `CLAUDE.md` (commandes), `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune. Si le manifeste ne permet pas de retrouver le GPX source sans ambiguïté, s'arrêter et le signaler.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/` et `compiler/`, sans réseau (fournisseur d'altitude synthétique ou `--offline` avec un cache préparé par le test).
2. Avec un dossier préparé (un GPX compilé, un GPX modifié après compilation, un GPX jamais compilé, un `.world` corrompu), `list_routes` renvoie les quatre statuts attendus.
3. `build-all --dry-run` n'écrit rien et annonce les deux compilations prévues ; `build-all` les fait, puis `list` les montre `ready`.
4. Une trace invalide (moins de 500 m) dans le lot donne une erreur pour elle seule ; les autres sont compilées ; code de sortie 1.
5. `list_routes` sur 50 parcours synthétiques tient en moins de 200 ms (mesure affichée par le test, seuil large en intégration continue).

## 8. Hors périmètre

- Messages IPC pour exposer la liste à l'engine (lot G, contrat à décider par le propriétaire).
- Compilation lancée par le core en tâche de fond (lot G).

## 9. Livraison (23 octobre 2026, PR #21)

- `core/src/openride_core/catalog.py` (`RouteEntry`, `list_routes`) et `GPX_DIR` dans `config.py`.
- Sous-commandes `list` et `build-all` ajoutées à `openride-compiler` (`cli.py`), avec repli autonome si `openride-core` n'est pas installé.
- Tests `core/tests/test_catalog.py` et `compiler/tests/test_build_all.py`.
