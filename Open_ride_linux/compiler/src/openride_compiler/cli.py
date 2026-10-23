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
from .pipeline import compile_route
from .terrain import build_terrain, replace_terrain_dir, terrain_manifest, write_terrain
from .verify import verify_world, world_info
from .writer import build_manifest, normalize_name, replace_manifest, sha256_of, write_world

LAYERS = ("route", "terrain")


def make_provider(offline: bool, log: Log = stderr_log) -> ElevationProvider:
    """Source d'altitude de la ligne de commande (remplacée par une source synthétique dans les tests)."""
    return CopernicusGlo30Provider(offline=offline, log=log)


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
    b.add_argument("--layers", type=parse_layers, default=LAYERS,
                   help="couches à produire, séparées par des virgules (défaut : route,terrain)")
    b.add_argument("--offline", action="store_true",
                   help="interdit le réseau : les tuiles d'altitude doivent être en cache")

    a = sub.add_parser("add-layer", help="régénère une couche d'un .world existant")
    a.add_argument("world", type=Path)
    a.add_argument("layer", choices=["terrain"])
    a.add_argument("--offline", action="store_true",
                   help="interdit le réseau : les tuiles d'altitude doivent être en cache")

    v = sub.add_parser("verify", help="contrôle un dossier .world")
    v.add_argument("world", type=Path)

    i = sub.add_parser("info", help="résume un dossier .world")
    i.add_argument("world", type=Path)
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
    extra = None
    if "terrain" in args.layers:
        tiles = build_terrain(compiled.route, LocalFrame.from_manifest(manifest), provider)
        manifest["layers"]["terrain"] = terrain_manifest(tiles, provider)

        def extra(folder: Path) -> None:
            write_terrain(folder / "terrain", tiles)

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
        raise CompileError(f"{world} : projection {manifest.get('projection')!r} ; le terrain demande "
                           "un parcours compilé en UTM (les parcours synthétiques ne sont pas géoréférencés)")
    provider = make_provider(args.offline)
    tiles = build_terrain(route, LocalFrame.from_manifest(manifest), provider)
    replace_terrain_dir(world, tiles)
    manifest.setdefault("layers", {})["terrain"] = terrain_manifest(tiles, provider)
    manifest["format_version"] = C.FORMAT_VERSION
    replace_manifest(world, manifest)
    count = sum(len(g) for g in tiles.values())
    print(f"{world} : couche terrain régénérée, {count} tuile(s) ({time.monotonic() - t0:.1f} s)")
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


COMMANDS = {"build": cmd_build, "add-layer": cmd_add_layer, "verify": cmd_verify, "info": cmd_info}


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
