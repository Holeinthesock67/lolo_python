"""Ligne de commande `openride-compiler` (lot B1 §3.3).

    openride-compiler build <trace .gpx|.fit|.tcx|.fit.gz|.tcx.gz|.zip> [--name NOM] [--out DOSSIER] [--out-and-back] [--force]
                            [--layers route,terrain,buildings,vegetation,poi,water] [--offline]
    openride-compiler add-layer <dossier.world> terrain|buildings|vegetation|poi|water [--offline]
    openride-compiler list | build-all [--layers ...] [--dry-run] [--offline]
    openride-compiler theme-check <dossier du thème>
    openride-compiler theme-list [--themes-dir D] [--json]
    openride-compiler theme-install SOURCE [--name NOM] [--force] [--themes-dir D]
    openride-compiler verify <dossier.world>
    openride-compiler info <dossier.world>

Codes de retour : 0 succès, 1 erreur d'entrée, 2 erreur interne.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from . import constants as C
from .cache import Log, stderr_log
from .elevation import CopernicusGlo30Provider, ElevationProvider
from .errors import EXIT_INPUT, EXIT_INTERNAL, EXIT_OK, CompileError
from .frame import LocalFrame
from .track_formats import read_track, scan_tracks, track_stem
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
from .route_stats import (SORT_KEYS, LibraryError, compute_stats, duration_at, load_library, query,
                          sidecar_path, stats_usable)
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
    parser = _Parser(prog="openride-compiler", description="Compile une trace GPX, FIT ou TCX en parcours .world.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    b = sub.add_parser("build", help="compile une trace GPX, FIT ou TCX en dossier .world")
    b.add_argument("gpx", type=Path, help="trace GPX, FIT ou TCX, ou export Garmin .fit.gz, .tcx.gz, .zip "
                   "(format reconnu par l'extension ou le contenu)")
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
    ls = sub.add_parser("list", help="liste les parcours (.world et traces .gpx, .fit, .tcx, .fit.gz, .tcx.gz, .zip) et leur statut")
    ls.add_argument("--gpx-dir", type=Path, default=default_gpx,
                    help=f"dossier des traces GPX (défaut : {default_gpx})")
    ls.add_argument("--routes-dir", type=Path, default=C.ROUTES_DIR,
                    help=f"dossier des parcours .world (défaut : {C.ROUTES_DIR})")
    ls.add_argument("--sort", choices=SORT_KEYS, help="trie par nom, distance, dénivelé positif, pente "
                    "maximale, durée estimée ou difficulté (croissant)")
    ls.add_argument("--reverse", action="store_true", help="tri décroissant")
    ls.add_argument("--tag", help="seulement les parcours portant cette étiquette (fiche .toml)")
    ls.add_argument("--region", help="seulement les parcours dont la région contient ce texte")
    ls.add_argument("--status", choices=["ready", "to_compile", "outdated", "invalid"])
    ls.add_argument("--min-km", type=float, help="distance minimale en km")
    ls.add_argument("--max-km", type=float, help="distance maximale en km")
    ls.add_argument("--max-difficulty", type=int, choices=range(1, 6), metavar="1-5",
                    help="difficulté maximale (1 à 5)")
    ls.add_argument("--ftp", type=float, help="puissance de la durée estimée (défaut : FTP de config.toml, "
                    "sinon 200 W)")
    ls.add_argument("--json", action="store_true", help="sortie JSON (fiches complètes)")

    rpi = sub.add_parser("route-pack-install",
                         help="installe un pack de parcours (dossier ou .zip de traces et de fiches .toml)")
    rpi.add_argument("source", type=Path, help="dossier du pack ou archive .zip")
    rpi.add_argument("--name", help="nom du pack (défaut : pack.toml, sinon nom de la source)")
    rpi.add_argument("--force", action="store_true", help="remplace un pack installé du même nom")
    rpi.add_argument("--gpx-dir", type=Path, default=default_gpx,
                     help=f"dossier des traces, le pack va dans un sous-dossier (défaut : {default_gpx})")
    rpl = sub.add_parser("route-pack-list", help="liste les packs de parcours installés")
    rpl.add_argument("--gpx-dir", type=Path, default=default_gpx,
                     help=f"dossier des traces (défaut : {default_gpx})")
    rpl.add_argument("--json", action="store_true", help="sortie JSON")

    ba = sub.add_parser("build-all", help="compile toutes les traces nouvelles ou modifiées (GPX, FIT, TCX, archives Garmin)")
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
    stem = track_stem(args.gpx.name)
    name = normalize_name(args.name if args.name else (stem[0] if stem else args.gpx.stem))
    notes: list[str] = []
    points = read_track(args.gpx, notes)
    for note in notes:
        print(f"openride-compiler : {note}", file=sys.stderr)
    final = Path(args.out) / f"{name}.world"
    if final.exists() and not args.force:   # avant tout téléchargement
        raise CompileError(f"{final} existe déjà (utiliser --force pour le remplacer)")
    provider = make_provider(args.offline)
    compiled = compile_route(points, out_and_back=args.out_and_back, provider=provider)
    _report_alt(compiled)
    manifest = build_manifest(name, compiled, args.gpx.name, sha256_of(args.gpx))
    side = sidecar_path(args.gpx, stem[0] if stem else args.gpx.stem)
    if side.is_file():
        try:
            manifest["library"] = load_library(side)
        except LibraryError as exc:
            print(f"openride-compiler : fiche ignorée : {exc}", file=sys.stderr)
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
    stats: dict | None = None    # fiche calculée (lot O15)
    library: dict | None = None  # fiche saisie (lot O15)


def _library_for(track: Path | None, manifest: dict | None) -> dict | None:
    """Fiche saisie : `<trace>.toml` à côté de la trace, sinon celle copiée dans le manifeste."""
    if track is not None:
        stem = track_stem(track.name)
        side = sidecar_path(track, stem[0] if stem else track.stem)
        if side.is_file():
            try:
                return load_library(side)
            except LibraryError as exc:
                print(f"openride-compiler : fiche ignorée : {exc}", file=sys.stderr)
                return None
    lib = (manifest or {}).get("library")
    return lib if isinstance(lib, dict) else None


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
        for gf in scan_tracks(gpx_dir)[0]:
            try:
                sha = sha256_of(gf)
            except OSError:
                continue
            norm = normalize_name(track_stem(gf.name)[0])
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
                entry = CatalogEntry(rid, rid, "invalid", None, None, False, gpath, problems[0],
                                     library=_library_for(gpath, None))
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
                stats = manifest.get("stats")
                entry = CatalogEntry(
                    rid, str(manifest.get("name") or rid), status,
                    float(route["length_m"]), str(route.get("type", "open")),
                    bool(isinstance(tlayer, dict) and tlayer.get("present")), gpath, None,
                    stats=stats if stats_usable(stats) else compute_stats(route),
                    library=_library_for(gpath, manifest))
            if rid == DEMO_NAME:
                demo = entry
            else:
                entries.append(entry)

    if demo is None:
        demo = CatalogEntry(DEMO_NAME, DEMO_NAME, "ready", DEMO_LENGTH_M, "open", False, None, None)
    for gpath, _sha, norm in gpx_by_name.values():
        if gpath not in matched:
            entries.append(CatalogEntry(norm, track_stem(gpath.name)[0], "to_compile", None, None, False, gpath,
                                        None, library=_library_for(gpath, None)))
    return [demo, *sorted(entries, key=lambda e: (e.id, e.name))]


def _print_conflicts(gpx_dir: Path) -> None:
    for lost, kept in scan_tracks(gpx_dir)[1]:
        print(f"openride-compiler : conflit : {lost.name} ignoré, même parcours que {kept.name}",
              file=sys.stderr)


def _default_ftp() -> float:
    """FTP de config.toml si le core est installé et la configuration lisible, sinon 200 W."""
    try:
        from openride_core import config as core_config
        return float(core_config.load().rider.ftp_w)
    except Exception:   # core absent ou configuration invalide : la durée reste estimée à 200 W
        return 200.0


def _entry_json(e, gpx_dir: Path, power_w: float) -> dict:
    gpx = None
    if e.gpx_path is not None:
        try:
            gpx = e.gpx_path.relative_to(gpx_dir).as_posix()
        except ValueError:
            gpx = e.gpx_path.name
    return {"id": e.id, "name": e.name, "status": e.status, "length_m": e.length_m,
            "route_type": e.route_type, "has_terrain": e.has_terrain, "gpx": gpx, "error": e.error,
            "stats": e.stats, "library": e.library, "power_w": power_w,
            "duration_s": duration_at(e.stats, power_w)}


def _fmt_duration(seconds: int | None) -> str:
    return "-" if seconds is None else f"{seconds // 3600}h{seconds % 3600 // 60:02d}"


def cmd_list(args: argparse.Namespace) -> int:
    gpx_dir = Path(args.gpx_dir).expanduser()
    entries = _catalog_entries(Path(args.routes_dir).expanduser(), gpx_dir)
    _print_conflicts(gpx_dir)
    power = args.ftp if args.ftp else _default_ftp()
    filters = {"tag": args.tag, "region": args.region, "status": args.status, "min_km": args.min_km,
               "max_km": args.max_km, "max_difficulty": args.max_difficulty}
    entries = query(entries, sort=args.sort, filters=filters, reverse=args.reverse, power_w=power)
    if args.json:
        print(json.dumps([_entry_json(e, gpx_dir, power) for e in entries], indent=2, ensure_ascii=False,
                         sort_keys=True))
        return EXIT_OK
    print(f"{'ID':<22} {'Statut':<12} {'Longueur':>10} {'D+':>7} {'Pente':>6} {'Diff':>4} "
          f"{f'à {power:.0f} W':>8} {'Type':<13} {'Terrain':<8} Détail")
    print("-" * 110)
    for e in entries:
        st = e.stats or {}
        length_str = f"{e.length_m / 1000:.2f} km" if e.length_m is not None else "-"
        gain_str = f"{st['gain_m']:.0f} m" if "gain_m" in st else "-"
        grade_str = f"{st['max_grade_pct']:.0f} %" if "max_grade_pct" in st else "-"
        diff_str = str(st.get("difficulty", "-"))
        type_str = e.route_type or "-"
        terr_str = "oui" if e.has_terrain else "non"
        tags = ",".join((e.library or {}).get("tags", []))
        detail = e.error or (e.gpx_path.name if e.gpx_path else "")
        if tags:
            detail = f"{detail} [{tags}]".strip()
        print(f"{e.id:<22} {e.status:<12} {length_str:>10} {gain_str:>7} {grade_str:>6} {diff_str:>4} "
              f"{_fmt_duration(duration_at(e.stats, power)):>8} {type_str:<13} {terr_str:<8} {detail}")
    return EXIT_OK


def cmd_route_pack_install(args: argparse.Namespace) -> int:
    from .route_pack import install_pack
    name, count, target = install_pack(args.source, Path(args.gpx_dir).expanduser(), name=args.name,
                                       force=args.force)
    print(f"Pack « {name} » installé : {count} trace(s) dans {target}.")
    print("Compiler les parcours : openride-compiler build-all")
    return EXIT_OK


def cmd_route_pack_list(args: argparse.Namespace) -> int:
    from .route_pack import list_packs
    packs = list_packs(Path(args.gpx_dir).expanduser())
    if args.json:
        print(json.dumps(packs, indent=2, ensure_ascii=False, sort_keys=True))
        return EXIT_OK
    if not packs:
        print("Aucun pack de parcours installé.")
    for p in packs:
        extra = f" — {p['description']}" if p.get("description") else ""
        print(f"{p['id']:<22} {p['tracks']:>3} trace(s)  {p.get('name', p['id'])}{extra}")
    return EXIT_OK


def cmd_build_all(args: argparse.Namespace) -> int:
    routes_dir = Path(args.routes_dir).expanduser()
    gpx_dir = Path(args.gpx_dir).expanduser()
    entries = _catalog_entries(routes_dir, gpx_dir)
    _print_conflicts(gpx_dir)

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
    "route-pack-install": cmd_route_pack_install,
    "route-pack-list": cmd_route_pack_list,
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
