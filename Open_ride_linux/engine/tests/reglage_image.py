#!/usr/bin/env python3
"""Réglage du contraste et de la brume (5 novembre 2026, retour du propriétaire : « image un peu trop claire
et pas assez contrastée » avec la brume éclairée par le ciel).

Usage :
    reglage_image.py lancer [--out DOSSIER] [--qualites medium,high] [--variantes A,B,…] [--vitesse 75]
                            [--size 1680x1011] [--godot CHEMIN]
    reglage_image.py planche DOSSIER
    reglage_image.py --list

`lancer` génère les parcours de démonstration (`openride-core demo-biomes`), puis pour chaque qualité et
chaque variante roule le tour des six biomes (`sim_bench.py --native`, une capture par kilomètre, avec
OPENRIDE_RENDER_DIAG = réglages proposés de la qualité + ceux de la variante). `planche` met côte à côte,
pour chaque qualité, la capture du milieu de chaque biome sous chaque variante (`planche_<qualité>.jpg`,
Pillow) : seul l'œil juge, aucune mesure de performance ici (le contraste et la brume coûtent ≈ 0 ms).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR))
import make_biome_world  # noqa: E402
import recette_u18  # noqa: E402

# Réglages proposés le 6 novembre (étude ETUDE_OPTIMISATION_RENDU_2026-11-05.md §4), sans la brume éclairée
GODOT = "feuillage_simple,arbres_loin_simple,halo_niveaux=3,halo_lineaire,anisotropy=8"
PROPOSED = {
    "low": GODOT,   # validé le 6 novembre : ombres des arbres et herbe gardées (aucun gain mesuré)
    "medium": GODOT + ",msaa=2,atlas=2048",
    "high": GODOT + ",msaa=2,sans_ssil,atlas=2048",
}
# (nom, réglages ajoutés, description)
VARIANTS = (
    ("A", "brume_ambiante=1", "brume éclairée pleine (passe du 6 novembre, jugée trop claire)"),
    ("B", "brume_ambiante=0.5", "brume éclairée à moitié"),
    ("C", "brume_ambiante=0.5,contraste=1.15,agx_contraste=1.35", "à moitié, contraste relevé"),
    ("D", "brume_ambiante=0.35,brume_densite=0.7,contraste=1.12", "brume plus légère et moins éclairée"),
    ("E", "brume_ambiante=0.5,sans_glow", "brume éclairée à moitié, sans halo (−1 ms mesuré)"),
    ("F", "brume_ambiante=0.5,courbe_s=0.35", "à moitié, étalonnage en S (ombres plus denses)"),
    ("G", "brume_ambiante=0.5,courbe_s=0.35,soleil_brume=0.3,terrain_macro=0.35,herbe_degrade=0.35",
     "F avec les trois améliorations visuelles"),
)
NAMES = [v[0] for v in VARIANTS]


def diag_for(quality: str, extra: str) -> str:
    return ",".join(x for x in (PROPOSED[quality], extra) if x)


def cmd_lancer(args: argparse.Namespace) -> int:
    out: Path = args.out
    routes = out / "routes"
    routes.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "OPENRIDE_ENGINE": str(TESTS_DIR.parent)}
    p = subprocess.run([sys.executable, "-m", "openride_core", "demo-biomes", "--out", str(routes), "--json"],
                       capture_output=True, text=True, env=env)
    tour = routes / f"{recette_u18.TOUR_WORLD}.world"
    if p.returncode != 0 or not tour.is_dir():
        print(f"demo-biomes impossible (code {p.returncode}) : {p.stderr.strip()[-400:]}", file=sys.stderr)
        return 2
    length = make_biome_world.Plan(make_biome_world.TOUR, False, False).length_m
    if not 0.0 < args.vitesse <= 80.0:
        print("--vitesse : entre 0 et 80 km/h (limite du scénario de simulation du core)", file=sys.stderr)
        return 2
    duration = length / (args.vitesse / 3.6) + 45.0
    t0 = time.time()
    rc = 0
    for q in args.qualites:
        for name, extra, _what in VARIANTS:
            if name not in args.variantes:
                continue
            d = out / q / name
            d.mkdir(parents=True, exist_ok=True)
            os.environ["OPENRIDE_RENDER_DIAG"] = diag_for(q, extra)
            bargs = argparse.Namespace(size=args.size, culling="off", godot=args.godot)
            rc |= recette_u18.bench(bargs, d, tour, q, duration,
                                    ["--speed-kmh", f"{args.vitesse:g}", "--every-m", "1000"])
            print(f"{q} {name} fini ({(time.time() - t0) / 60:.0f} min)", flush=True)
    os.environ.pop("OPENRIDE_RENDER_DIAG", None)
    return cmd_planche(out) or (1 if rc else 0)


def middle_captures(sdir: Path) -> dict[str, Path]:
    """Capture du milieu de chaque biome du tour (2 km × k + 1 km)."""
    found = {}
    block = make_biome_world.BLOCK_M
    for png in sorted(sdir.glob("*_d[0-9][0-9][0-9][0-9][0-9].png")):
        k, rest = divmod(float(png.stem.rsplit("_d", 1)[1]), block)
        if abs(rest - block / 2) < 1.0 and int(k) < len(make_biome_world.TOUR):
            found[make_biome_world.TOUR[int(k)]] = png
    return found


def copy_captures(out: Path) -> int:
    """Captures du milieu de chaque biome copiées dans `planche/<qualité>_<variante>_<biome>.png` (sans Pillow)."""
    dest = out / "planche"
    dest.mkdir(exist_ok=True)
    n = 0
    for qdir in sorted(p for p in out.iterdir() if p.is_dir() and p.name in PROPOSED):
        for name in NAMES:
            if (qdir / name).is_dir():
                for biome, png in middle_captures(recette_u18.run_dir(qdir / name) or qdir / name).items():
                    shutil.copy(png, dest / f"{qdir.name}_{name}_{biome}.png")
                    n += 1
    print(f"{n} captures copiées dans {dest}")
    return n


def cmd_planche(out: Path) -> int:
    if copy_captures(out) == 0:
        print("aucune capture trouvée : passages en échec ? (voir */*/sim_bench.txt)", file=sys.stderr)
        return 1
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("Pillow absent : planches assemblées non faites, captures dans planche/", file=sys.stderr)
        return 0
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    for qdir in sorted(p for p in out.iterdir() if p.is_dir() and p.name in PROPOSED):
        cols = [(n, middle_captures(recette_u18.run_dir(qdir / n) or qdir / n)) for n in NAMES if (qdir / n).is_dir()]
        if not cols:
            continue
        w, left, top = 480, 200, 40
        h = w * 1011 // 1680
        rows = list(make_biome_world.TOUR)
        img = Image.new("RGB", (left + w * len(cols), top + h * len(rows)), (25, 25, 25))
        draw = ImageDraw.Draw(img)
        for j, (n, shots) in enumerate(cols):
            draw.text((left + j * w + 10, 8), f"variante {n}", fill="white", font=font)
            for i, biome in enumerate(rows):
                if biome in shots:
                    img.paste(Image.open(shots[biome]).convert("RGB").resize((w, h)), (left + j * w, top + i * h))
        for i, biome in enumerate(rows):
            draw.text((10, top + i * h + h // 2 - 10), biome, fill="white", font=font)
        dest = out / f"planche_{qdir.name}.jpg"
        img.save(dest, quality=88)
        print(f"Planche : {dest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="énumérer les variantes et quitter")
    sub = ap.add_subparsers(dest="cmd")
    la = sub.add_parser("lancer")
    la.add_argument("--out", type=Path,
                    default=Path.home() / "OpenRide" / "mesures" / time.strftime("%Y-%m-%d") / "reglage_image")
    la.add_argument("--qualites", default="medium,high")
    la.add_argument("--variantes", default="B,C,D,E,F,G")
    la.add_argument("--vitesse", type=float, default=75.0, help="km/h, 80 au plus (limite du scénario du core)")
    la.add_argument("--size", default="1680x1011")
    la.add_argument("--godot", type=Path, default=Path(os.environ["GODOT"]) if os.environ.get("GODOT") else None)
    pl = sub.add_parser("planche")
    pl.add_argument("dossier", type=Path)
    args = ap.parse_args(argv)
    if args.list:
        for q, d in PROPOSED.items():
            print(f"{q:8} {d}")
        for name, extra, what in VARIANTS:
            print(f"{name}  {extra:55} {what}")
        return 0
    if args.cmd == "lancer":
        args.qualites = [q for q in args.qualites.split(",") if q]
        args.variantes = [v for v in args.variantes.split(",") if v]
        return cmd_lancer(args)
    if args.cmd == "planche":
        return cmd_planche(args.dossier)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
