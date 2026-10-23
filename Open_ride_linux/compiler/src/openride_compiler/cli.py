"""Ligne de commande `openride-compiler` (lot B1 §3.3).

    openride-compiler build <fichier.gpx> [--name NOM] [--out DOSSIER] [--out-and-back] [--force]
                            [--layers route,terrain] [--offline]
    openride-compiler add-layer <dossier.world> terrain [--offline]
    openride-compiler verify <dossier.world>
    openride-compiler info <dossier.world>

Codes de retour : 0 succès, 1 erreur d'entrée, 2 erreur interne.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import constants as C
from .cache import Log, stderr_log
from .elevation import CopernicusGlo30Provider, ElevationProvider
from .errors import EXIT_INPUT, EXIT_INTERNAL, EXIT_OK, CompileError
from .frame import LocalFrame
from .gpx import read_gpx
from .osm import OverpassClient
from .osm_layers import (
    build_osm_layers,
    buildings_manifest,
    load_existing_near_tiles,
    poi_manifest,
    replace_layer_dir,
    vegetation_manifest,
    water_manifest,
    write_buildings_dir,
    write_poi_dir,
    write_vegetation_dir,
    write_water_dir,
)
from .pipeline import compile_route
from .terrain import build_terrain, replace_terrain_dir, terrain_manifest, write_terrain
from .theme import check_theme
from .verify import verify_world, world_info
from .writer import build_manifest, normalize_name, replace_manifest, sha256_of, write_world

LAYERS = ("route", "terrain", "buildings", "vegetation", "poi", "water")
DEFAULT_LAYERS = ("route", "terrain")
OSM_LAYERS = ("buildings", "vegetation", "poi", "water")


def make_provider(offline: bool, log: Log = stderr_log) -> ElevationProvider:
    """Source d'altitude de la ligne de commande (remplacée par une source synthétique dans les tests)."""
    return CopernicusGlo30Provider(offline=offline, log=log)


def make_osm_client(offline: bool, log: Log = stderr_log) -> OverpassClient:
    """Client Overpass de la ligne de commande (remplacé dans les tests)."""
    return OverpassClient(offline=offline, log=log)


def parse_layers(text: str) -> tuple[str, ...]:
    layers = tuple(dict.fromkeys(s.strip() for s in text.split(",") if s.strip()))
    unknown = [la for la in layers if la not in LAYERS]
    if unknown or "route" not in layers:
        raise argparse.ArgumentTypeError(
            f"couches possibles : {', '.join(LAYERS)} (route obligatoire) ; reçu : {text!r}")
    return layers


class _Parser(argparse.ArgumentParser):
    """Une erreur d'usage est une erreur d'entrée (code 1), pas une erreur interne."""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        self.exit(EXIT_INPUT, f"{self.prog} : erreur : {message}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="openride-compiler", description="Compile une trace GPX en parcours .world.")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    b = sub.add_parser("build", help="compile un GPX en dossier .world")
    b.add_argument("gpx", type=Path)
    b.add_argument("--name", help="nom du parcours (défaut : nom du fichier normalisé)")
    b.add_argument("--out", type=Path, default=C.ROUTES_DIR, help=f"dossier de sortie (défaut : {C.ROUTES_DIR})")
    b.add_argument("--out-and-back", action="store_true", help="aller-retour : la trace puis son inverse")
    b.add_argument("--force", action="store_true", help="remplace un .world existant")
    b.add_argument("--layers", type=parse_layers, default=DEFAULT_LAYERS,
                   help="couches à produire, séparées par des virgules (défaut : route,terrain)")
    b.add_argument("--offline", action="store_true",
                   help="interdit le réseau : les tuiles d'altitude et OSM doivent être en cache")

    a = sub.add_parser("add-layer", help="régénère une couche d'un .world existant")
    a.add_argument("world", type=Path)
    a.add_argument("layer", choices=["terrain", "buildings", "vegetation", "poi", "water"])
    a.add_argument("--offline", action="store_true",
                   help="interdit le réseau : les données doivent être en cache")

    v = sub.add_parser("verify", help="contrôle un dossier .world")
    v.add_argument("world", type=Path)

    i = sub.add_parser("info", help="résume un dossier .world")
    i.add_argument("world", type=Path)

    tc = sub.add_parser("theme-check", help="contrôle un dossier de thème visuel")
    tc.add_argument("theme_dir", type=Path)

    default_gpx = Path.home() / "OpenRide" / "GPX"
    ls = sub.add_parser("list", help="liste les parcours (.world et .gpx) et leur statut")
    ls.add_argument("--gpx-dir", type=Path, default=default_gpx,
                    help=f"dossier des traces GPX (défaut : {default_gpx})")
    ls.add_argument("--routes-dir", type=Path, default=C.ROUTES_DIR,
                    help=f"dossier des parcours .world (défaut : {C.ROUTES_DIR})")

    ba = sub.add_parser("build-all", help="compile toutes les traces GPX nouvelles ou modifiées")
    ba.add_argument("--gpx-dir", type=Path, default=default_gpx,
                    help=f"dossier des traces GPX (défaut : {default_gpx})")
    ba.add_argument("--routes-dir", type=Path, default=C.ROUTES_DIR,
                    help=f"dossier de sortie des .world (défaut : {C.ROUTES_DIR})")
    ba.add_argument("--offline", action="store_true",
                    help="interdit le réseau : les tuiles d'altitude doivent être en cache")
    ba.add_argument("--dry-run", action="store_true",
                    help="affiche les compilations prévues sans rien écrire")
    return parser


def _report_alt(compiled) -> None:
    check = compiled.alt_check
    if check:
        print(f"altitude GPX / MNT : médiane {check['median_abs_diff_m']} m, max {check['max_abs_diff_m']} m, "
              f"{check['outlier_fraction']:.1%} des points à plus de {C.ALT_OUTLIER_M:.0f} m", file=sys.stderr)
        if "warning" in check:
            print(f"avertissement : {check['warning']}", file=sys.stderr)
    print(f"altitude de la route : {compiled.alt_source}", file=sys.stderr)


def cmd_build(args: argparse.Namespace) -> int:
    t0 = time.monotonic()
    name = normalize_name(args.name if args.name else args.gpx.stem)
    points = read_gpx(args.gpx)
    final = Path(args.out) / f"{name}.world"
    if final.exists() and not args.force:   # avant tout téléchargement
        raise CompileError(f"{final} existe déjà (utiliser --force pour le remplacer)")
    provider = make_provider(args.offline)
    compiled = compile_route(points, out_and_back=args.out_and_back, provider=provider)
    _report_alt(compiled)
    manifest = build_manifest(name, compiled, args.gpx.name, sha256_of(args.gpx))
    frame = LocalFrame.from_manifest(manifest)
    tiles = None
    if "terrain" in args.layers:
        tiles = build_terrain(compiled.route, frame, provider)
        manifest["layers"]["terrain"] = terrain_manifest(tiles, provider)

    osm_res = None
    if any(la in args.layers for la in OSM_LAYERS):
        osm_client = make_osm_client(args.offline)
        responses = osm_client.fetch_for_route(compiled.route, frame)
        near_tiles = tiles.get("near") if tiles is not None else None
        osm_res = build_osm_layers(compiled.route, frame, responses, near_tiles=near_tiles, provider=provider)
        if "buildings" in args.layers:
            manifest["layers"]["buildings"] = buildings_manifest(osm_res)
        if "vegetation" in args.layers:
            manifest["layers"]["vegetation"] = vegetation_manifest(osm_res)
        if "poi" in args.layers:
            manifest["layers"]["poi"] = poi_manifest(osm_res)
        if "water" in args.layers:
            manifest["layers"]["water"] = water_manifest(osm_res)

    def extra(folder: Path) -> None:
        if tiles is not None:
            write_terrain(folder / "terrain", tiles)
        if osm_res is not None:
            if "buildings" in args.layers:
                write_buildings_dir(folder / "buildings", osm_res.buildings_chunks)
            if "vegetation" in args.layers:
                write_vegetation_dir(folder / "vegetation", osm_res.vegetation_chunks)
            if "poi" in args.layers:
                write_poi_dir(folder / "poi", osm_res.poi_chunks)
            if "water" in args.layers:
                write_water_dir(folder / "water", osm_res.water_chunks)

    world = write_world(args.out, name, manifest, compiled.route, force=args.force, extra=extra)
    r = compiled.route
    print(f"{world} : {r['length_m'] / 1000:.2f} km, {r['n']} points, type {r['type']}, "
          f"{compiled.grade_clamped_points} point(s) limité(s) à ± {C.GRADE_LIMIT_PCT:.0f} %, "
          f"couches {','.join(args.layers)} ({time.monotonic() - t0:.1f} s)")
    return EXIT_OK


def cmd_add_layer(args: argparse.Namespace) -> int:
    t0 = time.monotonic()
    world = Path(args.world)
    try:
        manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
        route_file = (manifest.get("route") or {}).get("file", "route.json")
        route = json.loads((world / route_file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, AttributeError) as exc:
        raise CompileError(f"{world} : parcours illisible ({exc})") from exc
    if manifest.get("projection") != "utm":
        raise CompileError(f"{world} : projection {manifest.get('projection')!r} ; cette couche demande "
                           "un parcours compilé en UTM (les parcours synthétiques ne sont pas géoréférencés)")
    frame = LocalFrame.from_manifest(manifest)
    if args.layer == "terrain":
        provider = make_provider(args.offline)
        tiles = build_terrain(route, frame, provider)
        replace_terrain_dir(world, tiles)
        manifest.setdefault("layers", {})["terrain"] = terrain_manifest(tiles, provider)
        manifest["format_version"] = C.FORMAT_VERSION
        replace_manifest(world, manifest)
        count = sum(len(g) for g in tiles.values())
        print(f"{world} : couche terrain régénérée, {count} tuile(s) ({time.monotonic() - t0:.1f} s)")
        return EXIT_OK

    osm_client = make_osm_client(args.offline)
    responses = osm_client.fetch_for_route(route, frame)
    near_tiles = load_existing_near_tiles(world)
    needs_y = args.layer in ("buildings", "poi", "water")
    provider = make_provider(args.offline) if (not near_tiles and needs_y) else None
    osm_res = build_osm_layers(route, frame, responses, near_tiles=near_tiles, provider=provider)
    if args.layer == "buildings":
        replace_layer_dir(world, "buildings", write_buildings_dir, osm_res.buildings_chunks)
        manifest.setdefault("layers", {})["buildings"] = buildings_manifest(osm_res)
        count = osm_res.buildings_count
    elif args.layer == "vegetation":
        replace_layer_dir(world, "vegetation", write_vegetation_dir, osm_res.vegetation_chunks)
        manifest.setdefault("layers", {})["vegetation"] = vegetation_manifest(osm_res)
        count = osm_res.vegetation_count
    elif args.layer == "poi":
        replace_layer_dir(world, "poi", write_poi_dir, osm_res.poi_chunks)
        manifest.setdefault("layers", {})["poi"] = poi_manifest(osm_res)
        count = osm_res.poi_count
    else:
        replace_layer_dir(world, "water", write_water_dir, osm_res.water_chunks)
        manifest.setdefault("layers", {})["water"] = water_manifest(osm_res)
        count = osm_res.water_lines_count + osm_res.water_areas_count
    manifest["format_version"] = C.FORMAT_VERSION
    replace_manifest(world, manifest)
    print(f"{world} : couche {args.layer} régénérée, {count} objet(s) ({time.monotonic() - t0:.1f} s)")
    return EXIT_OK


def cmd_verify(args: argparse.Namespace) -> int:
    problems = verify_world(args.world)
    if problems:
        print(f"{args.world} : {len(problems)} problème(s)")
        for p in problems:
            print(f"  - {p}")
        return EXIT_INPUT
    print(f"{args.world} : valide")
    return EXIT_OK


def cmd_info(args: argparse.Namespace) -> int:
    problems = verify_world(args.world)
    if problems:
        print(f"{args.world} : invalide ({len(problems)} problème(s)), lancer « verify » pour le détail",
              file=sys.stderr)
        return EXIT_INPUT
    info = world_info(args.world)
    print(f"Nom               : {info['name']}")
    print(f"Longueur          : {info['length_m'] / 1000:.3f} km")
    print(f"Type              : {info['type']}")
    print(f"Pente maximale    : {info['grade_max_pct']:.1f} %")
    print(f"Pente minimale    : {info['grade_min_pct']:.1f} %")
    print(f"Dénivelé positif  : {info['climb_m']:.0f} m")
    print(f"Points limités    : {info['grade_clamped_points']}")
    print(f"Altitude          : {info['alt_source']}")
    terrain = info["terrain"]
    if terrain.get("present"):
        tiles = terrain.get("tiles") or {}
        print(f"Terrain           : {len(tiles.get('near', []))} tuile(s) proche(s), "
              f"{len(tiles.get('far', []))} lointaine(s) ({', '.join(terrain.get('sources', []))})")
    else:
        print("Terrain           : absent")
    return EXIT_OK


def cmd_theme_check(args: argparse.Namespace) -> int:
    issues = check_theme(args.theme_dir)
    errors = [iss for iss in issues if iss.severity == "error"]
    warnings = [iss for iss in issues if iss.severity == "warning"]
    for w in warnings:
        print(f"avertissement : {w.message}")
    if errors:
        print(f"{args.theme_dir} : {len(errors)} erreur(s)")
        for e in errors:
            print(f"  - {e.message}")
        return EXIT_INPUT
    print(f"{args.theme_dir} : valide")
    return EXIT_OK


def _catalog_entries(routes_dir: Path, gpx_dir: Path) -> list:
    """Utilise openride_core.catalog.list_routes si installé, sinon lecture minimale équivalente."""
    try:
        from openride_core.catalog import list_routes
        return list_routes(routes_dir, gpx_dir)
    except ImportError:
        pass

    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _Entry:
        id: str
        name: str
        status: str
        length_m: float | None
        route_type: str | None
        has_terrain: bool
        gpx_path: Path | None
        error: str | None = None

    gpx_by_name: dict[str, tuple[Path, str, str]] = {}
    gpx_by_norm: dict[str, Path] = {}
    if gpx_dir.is_dir():
        for gf in sorted(p for p in gpx_dir.iterdir() if p.is_file() and p.suffix.lower() == ".gpx"):
            gpx_by_name[gf.name] = (gf, sha256_of(gf), normalize_name(gf.stem))
            gpx_by_norm.setdefault(normalize_name(gf.stem), gf)

    matched: set[Path] = set()
    entries: list[_Entry] = []
    if routes_dir.is_dir():
        for wdir in sorted(p for p in routes_dir.iterdir() if p.is_dir() and p.name.endswith(".world")):
            rid = wdir.name[: -len(".world")]
            problems = verify_world(wdir)
            if problems:
                entries.append(_Entry(rid, rid, "invalid", None, None, False, gpx_by_norm.get(rid), problems[0]))
                if rid in gpx_by_norm:
                    matched.add(gpx_by_norm[rid])
                continue
            m = json.loads((wdir / "manifest.json").read_text(encoding="utf-8"))
            src = m.get("source") or {}
            gname, gsha = src.get("gpx"), src.get("gpx_sha256")
            gpath = gpx_by_name[gname][0] if gname in gpx_by_name else gpx_by_norm.get(rid)
            if gpath:
                matched.add(gpath)
            st = "outdated" if (gpath and gsha and sha256_of(gpath) != gsha) else "ready"
            rinfo = m.get("route") or {}
            tlayer = (m.get("layers") or {}).get("terrain") or {}
            entries.append(_Entry(
                rid, str(m.get("name") or rid), st,
                float(rinfo.get("length_m", 0.0)), str(rinfo.get("type", "open")),
                bool(tlayer.get("present")), gpath, None,
            ))
    for gname, (gpath, _sha, nid) in gpx_by_name.items():
        if gpath not in matched:
            entries.append(_Entry(nid, gpath.stem, "to_compile", None, None, False, gpath, None))
    return entries


def cmd_list(args: argparse.Namespace) -> int:
    entries = _catalog_entries(Path(args.routes_dir).expanduser(), Path(args.gpx_dir).expanduser())
    print(f"{'ID':<22} {'Statut':<12} {'Longueur':>10} {'Type':<13} {'Terrain':<8} Détail")
    print("-" * 80)
    for e in entries:
        length_str = f"{e.length_m / 1000:.2f} km" if e.length_m is not None else "-"
        type_str = e.route_type or "-"
        terr_str = "oui" if e.has_terrain else "non"
        detail = e.error or (e.gpx_path.name if e.gpx_path else "")
        print(f"{e.id:<22} {e.status:<12} {length_str:>10} {type_str:<13} {terr_str:<8} {detail}")
    return EXIT_OK


def cmd_build_all(args: argparse.Namespace) -> int:
    routes_dir = Path(args.routes_dir).expanduser()
    gpx_dir = Path(args.gpx_dir).expanduser()
    entries = _catalog_entries(routes_dir, gpx_dir)

    compiled_count = 0
    skipped_count = 0
    error_count = 0

    for e in entries:
        if e.status not in ("to_compile", "outdated") or e.gpx_path is None:
            skipped_count += 1
            continue
        if args.dry_run:
            print(f"[dry-run] à compiler : {e.id} ({e.status}, {e.gpx_path.name})")
            compiled_count += 1
            continue
        try:
            sub_args = argparse.Namespace(
                gpx=e.gpx_path,
                name=e.id,
                out=routes_dir,
                out_and_back=False,
                force=True,
                layers=LAYERS,
                offline=args.offline,
            )
            cmd_build(sub_args)
            compiled_count += 1
        except CompileError as exc:
            error_count += 1
            print(f"openride-compiler : erreur ({e.gpx_path.name}) : {exc}", file=sys.stderr)

    if args.dry_run:
        print(f"Résumé (dry-run) : {compiled_count} à compiler, {skipped_count} ignoré(s)")
        return EXIT_OK

    print(f"Résumé : {compiled_count} compilé(s), {skipped_count} ignoré(s), {error_count} en erreur")
    return EXIT_INPUT if error_count > 0 else EXIT_OK


COMMANDS = {
    "build": cmd_build,
    "add-layer": cmd_add_layer,
    "verify": cmd_verify,
    "info": cmd_info,
    "theme-check": cmd_theme_check,
    "list": cmd_list,
    "build-all": cmd_build_all,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except CompileError as exc:
        print(f"openride-compiler : erreur : {exc}", file=sys.stderr)
        return EXIT_INPUT
    except Exception as exc:  # noqa: BLE001 - toute autre erreur est interne
        print(f"openride-compiler : erreur interne : {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    sys.exit(main())
