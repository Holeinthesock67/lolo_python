"""Pack « Cols célèbres » livré avec le jeu (lot PK1) : dossier du paquet, manifeste, installation sans réseau.

Le pack est construit une fois sur le PC (`scripts/build_pack_base.sh` : `route-pack-build cols_celebres`
puis compilation de chaque col) et livré dans le paquet du jeu, **hors git**. Il est rangé ainsi :

    <paquet>/packs/cols_celebres/
        manifest.json            liste des cols, tailles, empreintes SHA-256, crédits (écrit par `manifest`)
        gpx/<dossier du pack>/   traces GPX, fiches .toml et pack.toml, comme `route-pack-install` les pose
        routes/<id>.world/       parcours compilés

Le dossier `<paquet>` est donné par la variable `OPENRIDE_PAQUET`, sinon c'est `Open_ride_linux/paquet/`
(installation depuis le dépôt ; l'installateur J9 y pose le pack ou donne la variable).

Les contenus de départ (`contents.install_starter`, premier lancement) installent le pack depuis ce
dossier : traces dans `~/OpenRide/GPX/<dossier du pack>/`, parcours compilés dans le dossier des parcours.
Jamais d'écrasement, jamais de réseau : un parcours n'est copié que s'il manque, et seulement si la trace
du joueur est celle du paquet (même SHA-256), pour que le catalogue le voie « prêt » et ne le recompile pas.
Le paquet est contrôlé (tailles et empreintes) avant toute copie ; un paquet abîmé n'installe rien.

Module sans dépendance au compilateur. Outil : `python -m openride_core.pack_bundle manifest|verify|info`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ENV_VAR = "OPENRIDE_PAQUET"
PACK_ID = "cols_celebres"
MANIFEST = "manifest.json"
FORMAT = 1
DEFAULT_CREDITS = ("Données routières © contributeurs OpenStreetMap, licence ODbL 1.0 ; "
                   "altitude Copernicus GLO-30 © DLR e.V. 2010-2014 et © Airbus Defence and Space GmbH "
                   "2014-2018, fournie dans le cadre du programme Copernicus ; biomes © ESA WorldCover "
                   "project 2021, CC BY 4.0")
DEFAULT_LICENSE = "ODbL 1.0 (données OpenStreetMap)"
_CHUNK = 1024 * 1024


class BundleError(Exception):
    """Paquet du pack absent, illisible ou abîmé ; message lisible."""


def default_root() -> Path:
    """Dossier du paquet : `OPENRIDE_PAQUET`, sinon `Open_ride_linux/paquet/` à côté du core."""
    env = os.environ.get(ENV_VAR, "").strip()
    if env:
        return Path(env).expanduser()
    return Path(__file__).resolve().parents[3] / "paquet"


def pack_dir(root: Path | None = None, pack: str = PACK_ID) -> Path:
    return (root if root is not None else default_root()) / "packs" / pack


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def _files(base: Path) -> list[Path]:
    """Fichiers ordinaires sous `base`, triés ; refuse les liens symboliques."""
    out = []
    for p in sorted(base.rglob("*")):
        if p.is_symlink():
            raise BundleError(f"lien symbolique refusé dans le paquet : {p}")
        if p.is_file():
            out.append(p)
    return out


def route_id(gpx_name: str) -> str:
    """Identifiant du parcours compilé d'une trace : nom normalisé, comme `build` et le catalogue."""
    import re
    import unicodedata

    stem = Path(gpx_name).stem
    ascii_text = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-") or "parcours"


def _pack_meta(gpx_pack: Path) -> dict[str, Any]:
    try:
        data = tomllib.loads((gpx_pack / "pack.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


@dataclass
class BundledRoute:
    id: str
    gpx: str            # nom du fichier GPX dans le dossier du pack
    gpx_sha256: str
    bytes: int          # octets du .world


@dataclass
class BundledPack:
    """Pack lu dans le paquet (manifeste chargé, fichiers non encore contrôlés)."""
    dir: Path
    name: str
    folder: str                       # dossier du pack dans ~/OpenRide/GPX/
    credits: str
    license: str
    routes: list[BundledRoute]
    files: list[dict[str, Any]]
    total_bytes: int
    manifest: dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def gpx_pack(self) -> Path:
        return self.dir / "gpx" / self.folder

    @property
    def routes_dir(self) -> Path:
        return self.dir / "routes"


# --- manifeste (construction, sur le PC) ----------------------------------------------------------

def write_manifest(pdir: Path, build_times: dict[str, float] | None = None, now: float | None = None) -> dict[str, Any]:
    """Écrit `manifest.json` du pack rangé dans `pdir` ; renvoie le manifeste. BundleError si incomplet."""
    pdir = Path(pdir)
    gpx_root = pdir / "gpx"
    folders = sorted(p for p in gpx_root.iterdir() if p.is_dir()) if gpx_root.is_dir() else []
    if len(folders) != 1:
        raise BundleError(f"un seul dossier de pack attendu dans {gpx_root} (trouvé : {len(folders)})")
    gpx_pack = folders[0]
    meta = _pack_meta(gpx_pack)
    routes_root = pdir / "routes"
    routes = []
    for gpx in sorted(gpx_pack.glob("*.gpx")):
        rid = route_id(gpx.name)
        wdir = routes_root / f"{rid}.world"
        if not (wdir / "manifest.json").is_file():
            raise BundleError(f"parcours compilé absent pour {gpx.name} : {wdir}")
        try:
            source = json.loads((wdir / "manifest.json").read_text(encoding="utf-8")).get("source") or {}
        except (OSError, ValueError) as exc:
            raise BundleError(f"manifeste illisible : {wdir}") from exc
        sha = _sha256(gpx)
        if source.get("gpx_sha256") not in (None, sha):
            raise BundleError(f"{wdir.name} n'a pas été compilé depuis {gpx.name} (empreinte différente)")
        size = sum(f.stat().st_size for f in _files(wdir))
        entry: dict[str, Any] = {"id": rid, "gpx": gpx.name, "gpx_sha256": sha, "bytes": size}
        if build_times and rid in build_times:
            entry["build_s"] = round(float(build_times[rid]), 1)
        routes.append(entry)
    if not routes:
        raise BundleError(f"aucune trace dans {gpx_pack}")
    files = [{"path": f.relative_to(pdir).as_posix(), "bytes": f.stat().st_size, "sha256": _sha256(f)}
             for f in _files(pdir) if f.name != MANIFEST or f.parent != pdir]
    manifest = {
        "format": FORMAT,
        "pack": pdir.name,
        "name": str(meta.get("name") or "Cols célèbres"),
        "folder": gpx_pack.name,
        "license": str(meta.get("license") or DEFAULT_LICENSE),
        "credits": DEFAULT_CREDITS,
        "built": time.strftime("%Y-%m-%d", time.localtime(now)),
        "routes": routes,
        "files": files,
        "total_bytes": sum(f["bytes"] for f in files),
    }
    (pdir / MANIFEST).write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


# --- lecture et contrôle --------------------------------------------------------------------------

def load(pdir: Path | None = None) -> BundledPack | None:
    """Pack du paquet, ou None s'il n'y en a pas (ou si son manifeste est illisible ou d'un autre format)."""
    pdir = Path(pdir) if pdir is not None else pack_dir()
    try:
        m = json.loads((pdir / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(m, dict) or m.get("format") != FORMAT:
        return None
    try:
        folder = str(m["folder"])
        if not folder or "/" in folder or folder.startswith("."):
            return None
        routes = [BundledRoute(str(r["id"]), str(r["gpx"]), str(r["gpx_sha256"]), int(r["bytes"]))
                  for r in m["routes"]]
        files = [dict(f) for f in m["files"]]
    except (KeyError, TypeError, ValueError):
        return None
    return BundledPack(pdir, str(m.get("name") or "Cols célèbres"), folder, str(m.get("credits") or DEFAULT_CREDITS),
                       str(m.get("license") or DEFAULT_LICENSE), routes, files, int(m.get("total_bytes") or 0), m)


def verify(pack: BundledPack, deep: bool = True) -> list[str]:
    """Écarts entre le paquet et son manifeste (tailles, et empreintes si `deep`) ; [] si tout va bien."""
    errors = []
    base = pack.dir.resolve()
    for f in pack.files:
        rel = str(f.get("path", ""))
        path = (pack.dir / rel).resolve()
        if not rel or base not in path.parents:
            errors.append(f"chemin refusé : {rel!r}")
            continue
        if not path.is_file() or (pack.dir / rel).is_symlink():
            errors.append(f"fichier absent : {rel}")
            continue
        if path.stat().st_size != int(f.get("bytes", -1)):
            errors.append(f"taille différente : {rel}")
        elif deep and _sha256(path) != f.get("sha256"):
            errors.append(f"empreinte différente : {rel}")
    return errors


# --- installation chez le joueur ------------------------------------------------------------------

def _installed_folder(gpx_dir: Path, name: str) -> Path | None:
    """Dossier de `gpx_dir` dont le `pack.toml` porte ce nom (pack déjà installé, par le paquet ou le réseau)."""
    if not gpx_dir.is_dir():
        return None
    for d in sorted(p for p in gpx_dir.iterdir() if p.is_dir() and not p.name.startswith(".")):
        if str(_pack_meta(d).get("name", "")) == name:
            return d
    return None


def installed_count(pack: BundledPack, routes_dir: Path) -> int:
    """Cols du paquet dont le parcours compilé est en place."""
    return sum((routes_dir / f"{r.id}.world" / "manifest.json").is_file() for r in pack.routes)


def install(pack: BundledPack, gpx_dir: Path, routes_dir: Path,
            progress: Callable[[int], None] = lambda pct: None) -> tuple[bool, list[str]]:
    """Installe ce qui manque du pack ; renvoie (traces copiées ?, parcours copiés). BundleError si abîmé."""
    errors = verify(pack)
    if errors:
        raise BundleError(f"paquet du pack abîmé ({len(errors)} écart(s), dont {errors[0]})")
    progress(20)
    gpx_dir.mkdir(parents=True, exist_ok=True)
    folder = _installed_folder(gpx_dir, pack.name)
    copied_gpx = False
    if folder is None:
        target = gpx_dir / pack.folder
        if target.exists():
            raise BundleError(f"dossier {target} déjà pris par autre chose que le pack")
        tmp = gpx_dir / f".{pack.folder}.paquet"
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.copytree(pack.gpx_pack, tmp)
        tmp.rename(target)
        folder, copied_gpx = target, True
    progress(40)
    routes_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    todo = [r for r in pack.routes if not (routes_dir / f"{r.id}.world" / "manifest.json").is_file()]
    for i, r in enumerate(todo):
        mine = folder / r.gpx
        # Trace absente (col refusé chez le joueur) ou différente (pack construit par le réseau) : le
        # parcours du paquet ne lui correspond pas ; la compilation habituelle s'en charge.
        if not mine.is_file() or _sha256(mine) != r.gpx_sha256:
            continue
        dst = routes_dir / f"{r.id}.world"
        with tempfile.TemporaryDirectory(dir=routes_dir, prefix=f".{r.id}.paquet-") as tmp:
            stage = Path(tmp) / dst.name
            shutil.copytree(pack.routes_dir / dst.name, stage)
            if dst.exists():   # dossier incomplet d'un essai précédent (pas de manifest.json)
                shutil.rmtree(dst)
            stage.rename(dst)
        copied.append(r.id)
        progress(40 + int(60 * (i + 1) / len(todo)))
    progress(100)
    return copied_gpx, copied


# --- outil ----------------------------------------------------------------------------------------

def _mb(n: int) -> str:
    return f"{n / (1024 * 1024):.1f} Mo"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m openride_core.pack_bundle",
                                 description="pack Cols célèbres livré dans le paquet (lot PK1)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("manifest", help="écrit manifest.json d'un pack rangé (gpx/ et routes/)")
    m.add_argument("dir", type=Path)
    m.add_argument("--times", type=Path, help="JSON {id: secondes} des temps de construction")
    v = sub.add_parser("verify", help="contrôle tailles et empreintes du paquet")
    v.add_argument("dir", type=Path, nargs="?")
    i = sub.add_parser("info", help="liste les cols du paquet, leur poids et le total")
    i.add_argument("dir", type=Path, nargs="?")
    i.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "manifest":
        times = json.loads(args.times.read_text(encoding="utf-8")) if args.times else None
        try:
            man = write_manifest(args.dir, times)
        except BundleError as exc:
            print(f"pack_bundle : {exc}", file=sys.stderr)
            return 1
        print(f"Manifeste écrit : {len(man['routes'])} col(s), {len(man['files'])} fichier(s), "
              f"{_mb(man['total_bytes'])}.")
        return 0
    pack = load(args.dir)
    if pack is None:
        print(f"pack_bundle : aucun pack lisible dans {args.dir or pack_dir()}", file=sys.stderr)
        return 1
    if args.cmd == "verify":
        errors = verify(pack)
        for e in errors:
            print(f"  {e}")
        print(f"{len(pack.files)} fichier(s) contrôlé(s), {len(errors)} écart(s).")
        return 1 if errors else 0
    if args.json:
        print(json.dumps(pack.manifest | {"files": len(pack.files)}, indent=1, ensure_ascii=False))
        return 0
    print(f"Pack « {pack.name} » ({pack.dir}), construit le {pack.manifest.get('built', '?')} :")
    times = {e.get("id"): e["build_s"] for e in pack.manifest.get("routes", []) if "build_s" in e}
    for r in pack.routes:
        extra = f", construit en {times[r.id]} s" if r.id in times else ""
        print(f"  {r.id:<28} {_mb(r.bytes):>10}{extra}")
    print(f"Total : {len(pack.routes)} col(s), {_mb(pack.total_bytes)}.")
    print(f"Crédits : {pack.credits}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
