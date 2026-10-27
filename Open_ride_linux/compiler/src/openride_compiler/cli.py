"""Ligne de commande `openride-compiler` (lot B1 §3.3).

    openride-compiler build <fichier.gpx> [--name NOM] [--out DOSSIER] [--out-and-back] [--force]
                            [--layers route,terrain,buildings,vegetation,poi,water] [--offline]
    openride-compiler add-layer <dossier.world> terrain|buildings|vegetation|poi|water [--offline]
    openride-compiler list | build-all [--layers ...] [--dry-run] [--offline]
    openride-compiler theme-check <dossier du thème>
    openride-compiler theme-list [--themes-dir D] [--json]
    openride-compiler theme-install SOURCE [--name NOM] [--force] [--themes-dir D]
    openride-compiler cache-info [--json] | cache-clean [--generated | --all] [--yes]
    openride-compiler region-add <région Geofabrik> [--keep-pbf] | region-update <région> | region-list [--json]
    openride-compiler verify <dossier.world>
    openride-compiler info <dossier.world>
    openride-compiler world-measure --lat LAT --lon LON [--heading DEG] [--km 10] [--region R] [--synthetic]

Codes de retour : 0 succès, 1 erreur d'entrée, 2 erreur interne.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from . import constants as C
from .cache import Log, stderr_log
from .elevation import CopernicusGlo30Provider, ElevationProvider
from .errors import EXIT_INPUT, EXIT_INTERNAL, EXIT_OK, CompileError
from .frame import LocalFrame
from .track_formats import read_track
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
from .worldgen import measure, region, store
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
    parser = _Parser(prog="openride-compiler", description="Compile une trace GPX, FIT ou TCX en parcours .world.")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    b = sub.add_parser("build", help="compile une trace GPX, FIT ou TCX en dossier .world")
    b.add_argument("gpx", type=Path, help="trace GPX, FIT ou TCX (format reconnu par l'extension ou le contenu)")
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
    ba.add_argument("--layers", type=parse_layers, default=DEFAULT_LAYERS,
                    help="couches à produire pour chaque trace (défaut : route,terrain)")
    ba.add_argument("--offline", action="store_true",
                    help="interdit le réseau : les tuiles d'altitude et OSM doivent être en cache")
    ba.add_argument("--dry-run", action="store_true",
                    help="affiche les compilations prévues sans rien écrire")

    tl = sub.add_parser("theme-list", help="liste les thèmes installés et intégrés")
    tl.add_argument("--themes-dir", type=Path, default=None,
                    help="dossier des thèmes (défaut : ~/OpenRide/Themes)")
    tl.add_argument("--json", action="store_true", help="sortie au format JSON")

    ti = sub.add_parser("theme-install", help="installe un pack de thème depuis un dossier ou une archive .zip")
    ti.add_argument("source", type=Path, help="dossier du pack ou archive .zip")
    ti.add_argument("--name", help="nom du thème (défaut : tiré de theme.json ou du dossier)")
    ti.add_argument("--force", action="store_true", help="remplace un thème existant")
    ti.add_argument("--themes-dir", type=Path, default=None,
                    help="dossier d'installation des thèmes (défaut : ~/OpenRide/Themes)")

    ci = sub.add_parser("cache-info", help="monde ouvert : taille du cache local, par sorte et par région (lot W2)")
    store.add_info_arguments(ci)
    cc = sub.add_parser("cache-clean", help="monde ouvert : vide le cache local (carrés générés par défaut)")
    store.add_clean_arguments(cc)
    for name, text in (("region-add", "monde ouvert : télécharge un extrait régional Geofabrik et le convertit (lot W3)"),
                       ("region-update", "monde ouvert : retélécharge la région si Geofabrik en publie une plus récente"),
                       ("region-list", "monde ouvert : régions du cache")):
        region.add_arguments(sub.add_parser(name, help=text), name)
    wm = sub.add_parser("world-measure",
                        help="monde ouvert : mesure volumes, temps de génération et débit (lot W0)")
    measure.add_arguments(wm)

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
    points = read_track(args.gpx)
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


def cmd_theme_list(args: argparse.Namespace) -> int:
    from .theme_packs import format_themes_text, list_themes
    themes = list_themes(themes_dir=args.themes_dir)
    if args.json:
        print(json.dumps(themes, indent=2, ensure_ascii=False))
    else:
        print(format_themes_text(themes))
    return EXIT_OK


def cmd_theme_install(args: argparse.Namespace) -> int:
    from .theme_packs import install_theme
    name, warnings = install_theme(
        source=args.source,
        name=args.name,
        force=args.force,
        themes_dir=args.themes_dir,
    )
    for w in warnings:
        print(f"avertissement : {w}")
    print(f"Thème « {name} » installé avec succès.")
    print("À ajouter dans config.toml :")
    print("[render]")
    print(f'theme = "{name}"')
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


# Parcours de démonstration du core (`openride_core.demo_world`), repris ici pour que le repli
# fonctionne sans le core ; `test_catalog_parity.py` vérifie que les deux valeurs restent égales.
DEMO_NAME = "demo"
DEMO_LENGTH_M = 5000.0


@dataclass(frozen=True)
class CatalogEntry:
    """Mêmes champs que `openride_core.catalog.RouteEntry`."""
    id: str
    name: str
    status: str                  # "ready", "to_compile", "outdated", "invalid"
    length_m: float | None
    route_type: str | None
    has_terrain: bool
    gpx_path: Path | None
    error: str | None = None


def _catalog_entries(routes_dir: Path, gpx_dir: Path) -> list:
    """Utilise openride_core.catalog.list_routes si installé, sinon le repli équivalent ci-dessous."""
    try:
        from openride_core.catalog import list_routes
    except ImportError:
        return fallback_catalog(routes_dir, gpx_dir)
    return list_routes(routes_dir, gpx_dir)


def _manifest_source(manifest: object) -> tuple[str | None, str | None]:
    src = manifest.get("source") if isinstance(manifest, dict) else None
    if not isinstance(src, dict):
        return None, None
    name, sha = src.get("gpx"), src.get("gpx_sha256")
    return (name if isinstance(name, str) and name else None,
            sha if isinstance(sha, str) and sha else None)


def fallback_catalog(routes_dir: Path, gpx_dir: Path) -> list[CatalogEntry]:
    """Catalogue sans le core, même règles que `openride_core.catalog.list_routes` (lot J6).

    Seule différence assumée : un `.world` est jugé par `verify_world` du compilateur au lieu de
    `load_world` du core.
    """
    routes_dir, gpx_dir = Path(routes_dir), Path(gpx_dir)
    gpx_by_name: dict[str, tuple[Path, str, str]] = {}
    gpx_by_sha: dict[str, list[Path]] = {}
    gpx_by_norm: dict[str, Path] = {}
    if gpx_dir.is_dir():
        for gf in sorted(p for p in gpx_dir.iterdir() if p.is_file() and p.suffix.lower() == ".gpx"):
            try:
                sha = sha256_of(gf)
            except OSError:
                continue
            norm = normalize_name(gf.stem)
            gpx_by_name[gf.name] = (gf, sha, norm)
            gpx_by_sha.setdefault(sha, []).append(gf)
            gpx_by_norm.setdefault(norm, gf)

    matched: set[Path] = set()
    entries: list[CatalogEntry] = []
    demo: CatalogEntry | None = None
    if routes_dir.is_dir():
        for wdir in sorted(p for p in routes_dir.iterdir()
                           if p.is_dir() and p.name.endswith(".world") and not p.name.startswith(".")):
            rid = wdir.name[: -len(".world")]
            try:
                manifest = json.loads((wdir / "manifest.json").read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                manifest = None
            problems = verify_world(wdir)
            src_name, src_sha = _manifest_source(manifest)

            # GPX source : par nom, puis par SHA-256 (GPX renommé), puis par identifiant normalisé.
            gpath: Path | None = None
            gsha: str | None = None
            if src_name and src_name in gpx_by_name:
                gpath, gsha, _ = gpx_by_name[src_name]
            elif src_sha and src_sha in gpx_by_sha:
                gpath, gsha = gpx_by_sha[src_sha][0], src_sha
            elif rid in gpx_by_norm:
                gpath = gpx_by_norm[rid]
                gsha = gpx_by_name[gpath.name][1]
            if gpath is not None:
                matched.add(gpath)

            if problems:
                entry = CatalogEntry(rid, rid, "invalid", None, None, False, gpath, problems[0])
            else:
                assert isinstance(manifest, dict)   # verify_world a lu le manifeste
                mroute = manifest.get("route") if isinstance(manifest.get("route"), dict) else {}
                route = json.loads((wdir / str(mroute.get("file", "route.json"))).read_text(encoding="utf-8"))
                status = "ready"
                if gpath is not None and src_sha is not None and gsha != src_sha:
                    status = "outdated"
                elif gpath is not None and src_sha is None and rid != DEMO_NAME:
                    status = "outdated"
                tlayer = (manifest.get("layers") or {}).get("terrain")
                entry = CatalogEntry(
                    rid, str(manifest.get("name") or rid), status,
                    float(route["length_m"]), str(route.get("type", "open")),
                    bool(isinstance(tlayer, dict) and tlayer.get("present")), gpath, None)
            if rid == DEMO_NAME:
                demo = entry
            else:
                entries.append(entry)

    if demo is None:
        demo = CatalogEntry(DEMO_NAME, DEMO_NAME, "ready", DEMO_LENGTH_M, "open", False, None, None)
    for gpath, _sha, norm in gpx_by_name.values():
        if gpath not in matched:
            entries.append(CatalogEntry(norm, gpath.stem, "to_compile", None, None, False, gpath, None))
    return [demo, *sorted(entries, key=lambda e: (e.id, e.name))]


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
                layers=args.layers,
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


def cmd_world_measure(args: argparse.Namespace) -> int:
    return measure.run_from_args(args)


COMMANDS = {
    "build": cmd_build,
    "add-layer": cmd_add_layer,
    "verify": cmd_verify,
    "info": cmd_info,
    "theme-check": cmd_theme_check,
    "theme-list": cmd_theme_list,
    "theme-install": cmd_theme_install,
    "list": cmd_list,
    "build-all": cmd_build_all,
    "cache-info": store.cmd_cache_info,
    "cache-clean": store.cmd_cache_clean,
    "region-add": region.cmd_region_add,
    "region-update": region.cmd_region_update,
    "region-list": region.cmd_region_list,
    "world-measure": cmd_world_measure,
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
