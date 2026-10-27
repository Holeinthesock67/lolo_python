"""Cache local du monde ouvert (lot W2, `docs/2.0/PLAN_SERIE_W.md` §4).

Arborescence sous `[open_world] cache_dir` (`~/OpenRide/Cache/monde` par défaut) :

    brut/dem/<tuile>.tif                 relief Copernicus (si absent du cache du compilateur)
    brut/osm/<region>.sqlite             extrait régional converti (W3) ou tuiles versées (W13)
    brut/tuiles/14/<x>/<y>.mvt           tuiles vectorielles OpenFreeMap (W13)
    genere/<zone>/<IX>_<IN>/             carré de 1 km de la grille fixe de la zone UTM (W7)
    genere/<zone>/far/<IX5>_<IN5>.f32    tuile lointaine de 5 km
    seances/<id>.world/                  mondes vivants des séances (W8)
    index.sqlite                         une ligne par entrée : taille, dernière utilisation, versions

- Le relief déjà téléchargé par le compilateur (`~/.cache/openride/dem/`) est relu sans copie et
  n'est jamais supprimé : il appartient au compilateur.
- Éviction au-delà du plafond : carrés générés d'abord (ils se recalculent sans réseau), puis
  tuiles lointaines, puis données brutes ; chaque fois la moins récemment utilisée d'abord ; les
  entrées préchargées (W-Q4) passent après toutes les autres ; une entrée épinglée ou utilisée par
  la séance en cours n'est jamais supprimée.
- Index illisible ou absent : reconstruit depuis le disque, sans rien supprimer.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from ..cache import Log, dem_cache_dir, stderr_log
from ..elevation import CopernicusGlo30Provider, copernicus_tile_name
from ..errors import CompileError

GB = 1_000_000_000
KINDS = ("square", "far", "dem", "tile", "osm")
EVICTION_RANK = {"square": 0, "far": 1, "dem": 2, "tile": 2, "osm": 2}
LAYER_FILES = ("buildings", "vegetation", "water", "poi")

# Valeurs par défaut de la section [open_world] (mêmes que `openride_core.config.OpenWorldConfig`).
OPEN_WORLD_DEFAULTS: dict[str, Any] = {
    "cache_dir": "~/OpenRide/Cache/monde", "cache_max_gb": 5.0, "horizon_m": 3000.0, "offer_m": 300.0,
    "lock_m": 30.0, "preview_m": 500.0, "recenter_m": 10000.0, "network": True,
    "prefetch_history": True, "prefetch_radius_km": 10.0,
}


def default_config_path() -> Path:
    return Path.home() / "OpenRide" / "config.toml"


def read_open_world_config(path: Path | None = None) -> dict[str, Any]:
    """Section [open_world] de `config.toml` complétée par les valeurs par défaut.

    Le core valide la section (types, bornes) ; le compilateur ne dépend pas du core et ne lit ici
    que les deux clés dont il a besoin sans les revalider en détail.
    """
    path = path or default_config_path()
    out = dict(OPEN_WORLD_DEFAULTS)
    if path.is_file():
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise CompileError(f"{path} illisible : {exc}") from exc
        section = data.get("open_world") or {}
        if not isinstance(section, dict):
            raise CompileError(f"{path}, [open_world] : section attendue")
        out.update({k: v for k, v in section.items() if k in out})
    try:
        out["cache_max_gb"] = float(out["cache_max_gb"])
    except (TypeError, ValueError) as exc:
        raise CompileError(f"[open_world] cache_max_gb invalide : {out['cache_max_gb']!r}") from exc
    if out["cache_max_gb"] <= 0:
        raise CompileError(f"[open_world] cache_max_gb doit être positif (reçu {out['cache_max_gb']:g})")
    return out


def _size(path: Path) -> int:
    if path.is_symlink() or path.is_file():
        return path.lstat().st_size if path.is_symlink() else path.stat().st_size
    if path.is_dir():
        return sum(p.stat().st_size for p in path.rglob("*") if p.is_file() and not p.is_symlink())
    return 0


@dataclass
class Entry:
    key: str
    kind: str
    path: str               # relatif à la racine du cache
    bytes: int
    last_used: float
    pinned: bool
    prefetch: bool
    region: str | None
    versions: dict[str, Any]


class WorldCache:
    """Gestionnaire du cache du monde ouvert. `clock` est remplaçable (tests)."""

    def __init__(self, root: Path, max_bytes: int, clock: Callable[[], float] = time.time,
                 dem_dir: Path | None = None, log: Log = stderr_log) -> None:
        self.root = Path(root).expanduser()
        self.max_bytes = int(max_bytes)
        self.clock = clock
        self.log = log
        self.compiler_dem_dir = Path(dem_dir) if dem_dir else dem_cache_dir() / CopernicusGlo30Provider.name
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "index.sqlite"
        self.db = self._open()

    @classmethod
    def from_config(cls, config_path: Path | None = None, **kw) -> "WorldCache":
        cfg = read_open_world_config(config_path)
        return cls(Path(str(cfg["cache_dir"])).expanduser(), int(cfg["cache_max_gb"] * GB), **kw)

    # --- index ---------------------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, isolation_level=None)
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS entries (
                key TEXT PRIMARY KEY, kind TEXT NOT NULL, path TEXT NOT NULL, bytes INTEGER NOT NULL,
                last_used REAL NOT NULL, pinned INTEGER NOT NULL DEFAULT 0, prefetch INTEGER NOT NULL DEFAULT 0,
                region TEXT, versions TEXT NOT NULL DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS regions (
                region TEXT PRIMARY KEY, pinned INTEGER NOT NULL DEFAULT 0, name TEXT, bbox TEXT);
        """)
        db.execute("SELECT count(*) FROM entries").fetchone()
        return db

    def _open(self) -> sqlite3.Connection:
        fresh = not self.db_path.is_file()
        try:
            db = self._connect()
        except sqlite3.DatabaseError as exc:
            self.log(f"index du cache illisible ({exc}) : reconstruction depuis le disque")
            for suffix in ("", "-wal", "-shm"):
                Path(f"{self.db_path}{suffix}").unlink(missing_ok=True)
            db = self._connect()
            fresh = True
        if fresh:
            self.db = db
            self.rebuild()
        return db

    @staticmethod
    def _row(r: tuple) -> Entry:
        return Entry(r[0], r[1], r[2], int(r[3]), float(r[4]), bool(r[5]), bool(r[6]), r[7], json.loads(r[8]))

    def get(self, key: str) -> Entry | None:
        r = self.db.execute("SELECT key, kind, path, bytes, last_used, pinned, prefetch, region, versions "
                            "FROM entries WHERE key = ?", (key,)).fetchone()
        return self._row(r) if r else None

    def entries(self) -> list[Entry]:
        rows = self.db.execute("SELECT key, kind, path, bytes, last_used, pinned, prefetch, region, versions "
                               "FROM entries ORDER BY key").fetchall()
        return [self._row(r) for r in rows]

    def add(self, key: str, kind: str, path: Path, versions: dict[str, Any] | None = None,
            region: str | None = None, prefetch: bool = False) -> Entry:
        """Enregistre une entrée écrite (de façon atomique) sous la racine du cache."""
        if kind not in KINDS:
            raise ValueError(f"sorte d'entrée inconnue : {kind}")
        path = Path(path)
        rel = os.path.relpath(path, self.root)
        if rel.startswith(".."):
            raise ValueError(f"{path} n'est pas dans le cache {self.root}")
        pinned = bool(region and self.db.execute(
            "SELECT pinned FROM regions WHERE region = ?", (region,)).fetchone() == (1,))
        self.db.execute(
            "INSERT OR REPLACE INTO entries (key, kind, path, bytes, last_used, pinned, prefetch, region, versions) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (key, kind, rel, _size(path), self.clock(), int(pinned), int(prefetch), region,
             json.dumps(versions or {}, sort_keys=True)))
        if region:
            self.db.execute("INSERT OR IGNORE INTO regions (region) VALUES (?)", (region,))
        return self.get(key)  # type: ignore[return-value]

    def touch(self, key: str) -> None:
        self.db.execute("UPDATE entries SET last_used = ? WHERE key = ?", (self.clock(), key))

    def mark_used(self, key: str) -> None:
        """Une entrée préchargée qui sert pendant une séance redevient ordinaire."""
        self.db.execute("UPDATE entries SET last_used = ?, prefetch = 0 WHERE key = ?", (self.clock(), key))

    def is_valid(self, key: str, versions: dict[str, Any]) -> bool:
        e = self.get(key)
        return e is not None and (self.root / e.path).exists() and e.versions == versions

    def total_bytes(self) -> int:
        return int(self.db.execute("SELECT coalesce(sum(bytes), 0) FROM entries").fetchone()[0])

    # --- chemins -------------------------------------------------------------------------------

    def dem_path(self, lat_sw: int, lon_sw: int) -> Path:
        """Tuile de relief : celle du compilateur si elle existe (jamais copiée), sinon `brut/dem/`."""
        name = f"{copernicus_tile_name(lat_sw, lon_sw)}.tif"
        shared = self.compiler_dem_dir / name
        return shared if shared.is_file() else self.root / "brut" / "dem" / name

    def osm_db_path(self, region: str) -> Path:
        return self.root / "brut" / "osm" / f"{region.replace('/', '_')}.sqlite"

    def vector_tile_path(self, x: int, y: int, z: int = 14) -> Path:
        return self.root / "brut" / "tuiles" / str(z) / str(x) / f"{y}.mvt"

    def square_dir(self, zone: str, ix: int, i_n: int) -> Path:
        return self.root / "genere" / zone / f"{ix}_{i_n}"

    def far_path(self, zone: str, ix5: int, in5: int) -> Path:
        return self.root / "genere" / zone / "far" / f"{ix5}_{in5}.f32"

    def sessions_dir(self) -> Path:
        return self.root / "seances"

    @staticmethod
    def square_key(zone: str, ix: int, i_n: int) -> str:
        return f"square:{zone}/{ix}_{i_n}"

    @staticmethod
    def far_key(zone: str, ix5: int, in5: int) -> str:
        return f"far:{zone}/{ix5}_{in5}"

    # --- liens vers une séance (format §13) ----------------------------------------------------

    @staticmethod
    def global_index(e0: float, n0: float, ix: int, iz: int, size_m: int = 1000) -> tuple[int, int]:
        """Tuile de séance (ix, iz) → indices globaux (est, nord) de la grille de `size_m`."""
        return int(round(e0 / size_m)) + ix, int(round(n0 / size_m)) - iz - 1

    def link_square(self, session_dir: Path, zone: str, e0: float, n0: float, ix: int, iz: int) -> list[Path]:
        """Lie le carré du cache aux fichiers `terrain/near/tile_ix_iz.f32` et `<couche>/tile_ix_iz.json`."""
        gx, gn = self.global_index(e0, n0, ix, iz)
        src = self.square_dir(zone, gx, gn)
        made = []
        pairs = [(src / "near.f32", Path("terrain") / "near" / f"tile_{ix}_{iz}.f32")]
        pairs += [(src / f"{layer}.json", Path(layer) / f"tile_{ix}_{iz}.json") for layer in LAYER_FILES]
        for target, rel in pairs:
            if target.is_file():
                made.append(_symlink(target, Path(session_dir) / rel))
        return made

    def link_far(self, session_dir: Path, zone: str, e0: float, n0: float, fx: int, fz: int) -> Path | None:
        gx, gn = self.global_index(e0, n0, fx, fz, 5000)
        target = self.far_path(zone, gx, gn)
        if not target.is_file():
            return None
        return _symlink(target, Path(session_dir) / "terrain" / "far" / f"tile_{fx}_{fz}.f32")

    # --- régions et épinglage ------------------------------------------------------------------

    def set_region(self, region: str, name: str | None = None, bbox: Iterable[float] | None = None) -> None:
        self.db.execute("INSERT OR IGNORE INTO regions (region) VALUES (?)", (region,))
        if name is not None:
            self.db.execute("UPDATE regions SET name = ? WHERE region = ?", (name, region))
        if bbox is not None:
            self.db.execute("UPDATE regions SET bbox = ? WHERE region = ?", (json.dumps(list(bbox)), region))

    def pin(self, region: str, pinned: bool = True) -> None:
        self.set_region(region)
        self.db.execute("UPDATE regions SET pinned = ? WHERE region = ?", (int(pinned), region))
        self.db.execute("UPDATE entries SET pinned = ? WHERE region = ?", (int(pinned), region))

    def regions(self) -> list[dict[str, Any]]:
        rows = self.db.execute("""
            SELECT r.region, coalesce(r.name, r.region), r.pinned, r.bbox,
                   coalesce(sum(e.bytes), 0), max(e.last_used)
            FROM regions r LEFT JOIN entries e ON e.region = r.region
            GROUP BY r.region ORDER BY r.region""").fetchall()
        return [{"id": r[0], "name": r[1], "pinned": bool(r[2]), "bbox": json.loads(r[3]) if r[3] else None,
                 "bytes": int(r[4]), "last_used": r[5]} for r in rows]

    # --- éviction et nettoyage -----------------------------------------------------------------

    def _delete(self, e: Entry) -> None:
        path = self.root / e.path
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
        self.db.execute("DELETE FROM entries WHERE key = ?", (e.key,))

    def evict(self, in_use: Iterable[str] = ()) -> list[str]:
        """Supprime des entrées jusqu'à passer sous le plafond ; renvoie les clés supprimées."""
        total = self.total_bytes()
        if total <= self.max_bytes:
            return []
        keep = set(in_use)
        candidates = [e for e in self.entries() if not e.pinned and e.key not in keep]
        candidates.sort(key=lambda e: (e.prefetch, EVICTION_RANK[e.kind], e.last_used, e.key))
        removed = []
        for e in candidates:
            if total <= self.max_bytes:
                break
            self._delete(e)
            total -= e.bytes
            removed.append(e.key)
        if total > self.max_bytes:
            self.log(f"cache du monde : {total / GB:.2f} Go après éviction, au-dessus du plafond "
                     f"de {self.max_bytes / GB:.2f} Go (entrées épinglées ou en cours d'usage)")
        return removed

    def clean(self, generated_only: bool = True, include_pinned: bool = False) -> list[str]:
        kinds = ("square", "far") if generated_only else KINDS
        removed = []
        for e in self.entries():
            if e.kind in kinds and (include_pinned or not e.pinned):
                self._delete(e)
                removed.append(e.key)
        return removed

    def info(self) -> dict[str, Any]:
        by_kind = {k: 0 for k in KINDS}
        count = {k: 0 for k in KINDS}
        for e in self.entries():
            by_kind[e.kind] += e.bytes
            count[e.kind] += 1
        return {"root": str(self.root), "bytes": self.total_bytes(), "max_bytes": self.max_bytes,
                "by_kind": by_kind, "count": count, "regions": self.regions()}

    # --- reconstruction ------------------------------------------------------------------------

    def rebuild(self) -> int:
        """Relit le disque et recrée l'index ; garde les épinglages connus. Ne supprime rien."""
        self.db.execute("DELETE FROM entries")
        found = 0

        def add(key: str, kind: str, path: Path, versions: dict | None = None) -> None:
            nonlocal found
            self.add(key, kind, path, versions)
            self.db.execute("UPDATE entries SET last_used = ? WHERE key = ?", (path.stat().st_mtime, key))
            found += 1

        brut = self.root / "brut"
        for p in sorted((brut / "dem").glob("*.tif")):
            add(f"dem:{p.stem}", "dem", p)
        for p in sorted((brut / "osm").glob("*.sqlite")):
            add(f"osm:{p.stem}", "osm", p)
            self.db.execute("UPDATE entries SET region = ? WHERE key = ?", (p.stem, f"osm:{p.stem}"))
        for p in sorted((brut / "tuiles").glob("*/*/*.mvt")):
            z, x = p.parent.parent.name, p.parent.name
            add(f"tile:{z}/{x}/{p.stem}", "tile", p)
        genere = self.root / "genere"
        for zone in sorted(d for d in genere.glob("*") if d.is_dir()):
            for sq in sorted(d for d in zone.glob("*_*") if d.is_dir() and not d.name.startswith(".")):
                meta = sq / "meta.json"
                try:
                    versions = json.loads(meta.read_text(encoding="utf-8")).get("versions", {}) if meta.is_file() else {}
                except ValueError:
                    versions = {}
                add(f"square:{zone.name}/{sq.name}", "square", sq, versions)
            for f in sorted((zone / "far").glob("*.f32")):
                add(f"far:{zone.name}/{f.stem}", "far", f)
        self.db.execute("UPDATE entries SET pinned = 1 WHERE region IN (SELECT region FROM regions WHERE pinned = 1)")
        if found:
            self.log(f"index du cache reconstruit : {found} entrée(s)")
        return found

    def close(self) -> None:
        self.db.close()


def _symlink(target: Path, link: Path) -> Path:
    link.parent.mkdir(parents=True, exist_ok=True)
    tmp = link.with_name(f".{link.name}.tmp-{os.getpid()}")
    tmp.unlink(missing_ok=True)
    os.symlink(target, tmp)
    os.replace(tmp, link)
    return link


# --- ligne de commande ------------------------------------------------------------------------

def _fmt_bytes(n: int) -> str:
    return f"{n / GB:.2f} Go" if n >= GB / 10 else f"{n / 1e6:.1f} Mo"


def cmd_cache_info(args) -> int:
    cache = WorldCache.from_config(args.config, log=lambda _: None)
    info = cache.info()
    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0
    labels = {"square": "carrés générés", "far": "tuiles lointaines", "dem": "relief",
              "tile": "tuiles vectorielles", "osm": "bases OpenStreetMap"}
    print(f"Cache du monde ouvert : {info['root']}")
    print(f"Taille : {_fmt_bytes(info['bytes'])} sur {_fmt_bytes(info['max_bytes'])}")
    for k in KINDS:
        print(f"  {labels[k]:<22} {info['count'][k]:>6}  {_fmt_bytes(info['by_kind'][k])}")
    for r in info["regions"]:
        print(f"  région {r['name']}{' (épinglée)' if r['pinned'] else ''} : {_fmt_bytes(r['bytes'])}")
    return 0


def cmd_cache_clean(args) -> int:
    cache = WorldCache.from_config(args.config, log=lambda _: None)
    generated_only = not args.all
    what = "tout le cache (épinglés compris)" if args.all else "les carrés et tuiles lointaines générés"
    if not args.yes:
        try:
            ok = input(f"Supprimer {what} de {cache.root} ? [o/N] ").strip().lower() in ("o", "oui", "y", "yes")
        except EOFError:
            ok = False
        if not ok:
            print("Rien supprimé.")
            return 0
    before = cache.total_bytes()
    removed = cache.clean(generated_only=generated_only, include_pinned=args.all)
    print(f"{len(removed)} entrée(s) supprimée(s), {_fmt_bytes(before - cache.total_bytes())} libérés.")
    return 0


def add_info_arguments(p) -> None:
    p.add_argument("--config", type=Path, default=None, help="config.toml (défaut : ~/OpenRide/config.toml)")
    p.add_argument("--json", action="store_true", help="sortie au format JSON")


def add_clean_arguments(p) -> None:
    p.add_argument("--config", type=Path, default=None, help="config.toml (défaut : ~/OpenRide/config.toml)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--generated", action="store_true", help="carrés et tuiles lointaines seulement (défaut)")
    g.add_argument("--all", action="store_true", help="tout le cache, régions épinglées comprises")
    p.add_argument("--yes", action="store_true", help="sans confirmation")
