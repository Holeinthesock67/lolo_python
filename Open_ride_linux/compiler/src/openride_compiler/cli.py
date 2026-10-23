"""Ligne de commande `openride-compiler` (lot B1 §3.3).

    openride-compiler build <fichier.gpx> [--name NOM] [--out DOSSIER] [--out-and-back] [--force]
    openride-compiler verify <dossier.world>
    openride-compiler info <dossier.world>

Codes de retour : 0 succès, 1 erreur d'entrée, 2 erreur interne.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import constants as C
from .errors import EXIT_INPUT, EXIT_INTERNAL, EXIT_OK, CompileError
from .gpx import read_gpx
from .pipeline import compile_route
from .verify import verify_world, world_info
from .writer import build_manifest, normalize_name, sha256_of, write_world


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

    v = sub.add_parser("verify", help="contrôle un dossier .world")
    v.add_argument("world", type=Path)

    i = sub.add_parser("info", help="résume un dossier .world")
    i.add_argument("world", type=Path)
    return parser


def cmd_build(args: argparse.Namespace) -> int:
    t0 = time.monotonic()
    name = normalize_name(args.name if args.name else args.gpx.stem)
    points = read_gpx(args.gpx)
    compiled = compile_route(points, out_and_back=args.out_and_back)
    manifest = build_manifest(name, compiled, args.gpx.name, sha256_of(args.gpx))
    world = write_world(args.out, name, manifest, compiled.route, force=args.force)
    r = compiled.route
    print(f"{world} : {r['length_m'] / 1000:.2f} km, {r['n']} points, type {r['type']}, "
          f"{compiled.grade_clamped_points} point(s) limité(s) à ± {C.GRADE_LIMIT_PCT:.0f} % "
          f"({time.monotonic() - t0:.1f} s)")
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
    return EXIT_OK


COMMANDS = {"build": cmd_build, "verify": cmd_verify, "info": cmd_info}


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
