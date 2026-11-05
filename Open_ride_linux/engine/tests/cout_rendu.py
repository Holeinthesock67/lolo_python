#!/usr/bin/env python3
"""Coût de chaque effet de rendu sur le PC cible : un banc par effet coupé ou allégé, en low, medium et high.

Usage :
    cout_rendu.py lancer [--out DOSSIER] [--qualites low,medium,high] [--biome farmland] [--duree 70]
                         [--variantes base,sans_ombres,...] [--godot CHEMIN]
    cout_rendu.py analyser DOSSIER
    cout_rendu.py --list

Recherche d'optimisation du 5 novembre (recette U18 : GPU au-dessus du budget en medium et high sur les
cultures et la forêt). Chaque variante relance `sim_bench.py --native --probe` sur un parcours de 6 km tout entier dans un biome
(`make_biome_world.py --biome`, lot U19 ; défaut `farmland`, le plus lourd à la recette U18), à 60 km/h, et une seule
différence avec le préréglage, passée à l'engine par OPENRIDE_RENDER_DIAG (`scripts/render_diag.gd`) ou par
`--culling on`. `analyser` écrit `cout.md` et `cout.json` : temps GPU médian, images/s, p99, part des secondes où
le GPU est saturé, et gain par rapport à `base` de la même qualité ; `planche/` garde la dernière capture de
chaque variante (coût visuel, à juger à l'œil).

Code de sortie : 0, ou 2 si l'appel est impossible (aucun budget n'est jugé ici).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR))
import perf_probe  # noqa: E402
import recette_u18  # noqa: E402

QUALITIES = ("low", "medium", "high")
# (nom, OPENRIDE_RENDER_DIAG, options de sim_bench, qualités concernées, ce que la variante enlève à l'image)
VARIANTS: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...], str], ...] = (
    ("base", "", (), QUALITIES, "préréglage tel quel"),
    ("sans_ombres", "sans_ombres", (), QUALITIES, "aucune ombre portée (borne du coût des ombres)"),
    ("sans_ombres_arbres", "sans_ombres_arbres", (), QUALITIES, "arbres sans ombre portée"),
    ("ombres_2_cascades", "ombres_2_cascades", (), ("medium", "high"), "2 cascades d'ombre au lieu de 4"),
    ("ombres_200m", "ombres_m=200", (), ("medium", "high"), "ombres jusqu'à 200 m au lieu de 400 / 600"),
    ("atlas_2048", "atlas=2048", (), ("medium", "high"), "atlas des ombres 2048 au lieu de 4096"),
    ("filtre_low", "filtre=low", (), ("medium", "high"), "bord des ombres moins doux"),
    ("sans_ssao", "sans_ssao", (), ("medium", "high"), "sans occlusion ambiante"),
    ("ssao_low", "ssao=low", (), ("medium", "high"), "occlusion ambiante basse"),
    ("sans_ssil", "sans_ssil", (), ("medium", "high"), "sans lumière indirecte d'écran"),
    ("sans_brume", "sans_brume", (), ("medium", "high"), "sans brume volumétrique"),
    ("brume_ambiante", "brume_ambiante", (), ("medium", "high"), "brume éclairée par le ciel (montagnes sombres)"),
    ("msaa2", "msaa=2", (), ("medium", "high"), "MSAA 2× au lieu de 4×"),
    ("msaa0", "msaa=0", (), ("medium", "high"), "sans MSAA ni SMAA (bords crénelés)"),
    ("msaa0_smaa", "msaa=0,screen_aa=smaa", (), ("medium", "high"), "SMAA à la place du MSAA (comme low)"),
    ("sans_glow", "sans_glow", (), ("medium", "high"), "sans halo"),
    ("herbe_50", "herbe=0.5", (), QUALITIES, "moitié des touffes d'herbe"),
    ("vegetation_50", "vegetation=0.5", (), QUALITIES, "moitié moins d'arbres"),
    ("arbres_lod0_300m", "arbres_lod0_m=300", (), QUALITIES, "arbres détaillés jusqu'à 300 m au lieu de 450"),
    ("tri_visible", "", ("--culling", "on"), QUALITIES, "tri de ce que la caméra ne voit pas (lot S1)"),
    # Réglages propres à Godot (recherche du 5 novembre, G1 à G7) : presque sans perte visuelle attendue.
    ("feuillage_simple", "feuillage_simple", (), QUALITIES, "herbe et arbres en diffuse_lambert, sans reflets (G1)"),
    ("arbres_loin_simple", "arbres_loin_simple", (), QUALITIES, "arbres lointains sans vent ni reflets (G3)"),
    ("halo_3_niveaux", "halo_niveaux=3,halo_lineaire", (), ("medium", "high"), "halo à 3 niveaux, agrandi en linéaire (G6)"),
    ("aniso_8", "anisotropy=8", (), ("high",), "filtrage anisotrope 8× au lieu de 16× (G5)"),
    ("godot_gratuits", "feuillage_simple,arbres_loin_simple,halo_niveaux=3,halo_lineaire,anisotropy=8,brume_ambiante",
     (), QUALITIES, "les quatre réglages Godot et la brume éclairée ensemble"),
    # Améliorations à faible coût (5 novembre soir) : le « gain » attendu est négatif (coût), à garder près de 0.
    ("soleil_brume", "soleil_brume=0.3", (), QUALITIES, "AJOUT : halo du soleil dans le brouillard (fog_sun_scatter)"),
    ("terrain_macro", "terrain_macro=0.35", (), QUALITIES, "AJOUT : prés plus ou moins mûrs à l'échelle de 600 m"),
    ("herbe_degrade", "herbe_degrade=0.35", (), QUALITIES, "AJOUT : herbe au pied plus sombre, pointe plus claire"),
    ("embellis", "soleil_brume=0.3,terrain_macro=0.35,herbe_degrade=0.35,brume_ambiante", (), QUALITIES,
     "AJOUT : les trois améliorations et la brume éclairée ensemble"),
)
NAMES = [v[0] for v in VARIANTS]


def plan(qualities: list[str], names: list[str]) -> list[tuple[str, tuple]]:
    return [(q, v) for q in qualities for v in VARIANTS if v[0] in names and q in v[3]]


def cmd_lancer(args: argparse.Namespace) -> int:
    out: Path = args.out
    # Pire cas (règle du métier : mesurer là où ça coûte le plus) : un parcours de 6 km tout entier dans le
    # biome, relief et végétation du biome (make_biome_world --biome), plutôt que le premier km du tour.
    routes = out / "routes"
    world = routes / f"banc-{args.biome}.world"
    if not world.is_dir():
        import make_biome_world
        try:
            make_biome_world.generate(routes, f"banc-{args.biome}", (args.biome,) * 3)
        except (ImportError, RuntimeError, ValueError) as exc:
            print(f"parcours du banc impossible : {exc}", file=sys.stderr)
            return 2
    runs = plan(args.qualites, args.variantes)
    print(f"{len(runs)} bancs de {args.duree:.0f} s (≈ {len(runs) * (args.duree + 30) / 60:.0f} min)", flush=True)
    t0 = time.time()
    for k, (q, (name, diag, extra, _qs, _what)) in enumerate(runs):
        rdir = out / q / name
        rdir.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, str(TESTS_DIR / "sim_bench.py"), "--native", "--probe", "--muet",
               "--quality", q, "--size", args.size, "--world", str(world),
               "--speed-kmh", "60", "--every", "30", "--duration", f"{args.duree:.0f}", "--out", str(rdir), *extra]
        if args.godot:
            cmd += ["--godot", str(args.godot)]
        env = {**os.environ, "OPENRIDE_RENDER_DIAG": diag}
        print(f"[{k + 1}/{len(runs)}] {q} {name} ({(time.time() - t0) / 60:.0f} min)", flush=True)
        with (rdir / "sim_bench.txt").open("w", encoding="utf-8") as fh:
            subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, env=env)
    (out / "biome.txt").write_text(args.biome + "\n", encoding="utf-8")
    return analyse(out)


def measure(rdir: Path, warm_s: float) -> dict[str, Any] | None:
    sdir = recette_u18.run_dir(rdir)
    if sdir is None:
        return None
    rows = recette_u18.probe_rows(sdir)
    t_min = min(perf_probe.values(rows, "t_s"), default=0.0) + warm_s
    rows = [r for r in rows if isinstance(r.get("t_s"), (int, float)) and r["t_s"] >= t_min]

    def med(key: str) -> float | None:
        v = perf_probe.values(rows, key)
        return round(statistics.median(v), 2) if v else None

    util = perf_probe.values(rows, "gpu_util_pct")
    engine_log = (sdir / "engine.log").read_text(encoding="utf-8", errors="replace") if (sdir / "engine.log").is_file() else ""
    return {"secondes": len(rows), "gpu_ms": med("gpu_ms"), "fps": med("fps"), "p99_ms": med("frame_p99_ms"),
            "primitives": med("primitives"), "appels": med("draw_calls"),
            "gpu_sature_pct": round(100.0 * sum(u > 95.0 for u in util) / len(util), 1) if util else None,
            "diag_vu": "Diagnostic de rendu" in engine_log, "dossier": sdir}


def analyse(out: Path) -> int:
    targets = perf_probe.load_targets()
    warm = float(targets.get("warmup_s", 20))
    planche = out / "planche"
    planche.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {}
    for q in QUALITIES:
        base = None
        for name, diag, _extra, qs, what in VARIANTS:
            if q not in qs or not (out / q / name).is_dir():
                continue
            m = measure(out / q / name, warm)
            if m is None:
                continue
            sdir = m.pop("dossier")
            shots = sorted(sdir.glob("*_t*.png"))
            if shots:
                shutil.copy(shots[-1], planche / f"{q}_{name}.png")
            if name == "base":
                base = m
            gain = (round(base["gpu_ms"] - m["gpu_ms"], 2) if base and base.get("gpu_ms") is not None
                    and m.get("gpu_ms") is not None else None)
            m.update({"enleve": what, "diag": diag, "gain_gpu_ms": gain,
                      "diag_non_vu": bool(diag) and not m.pop("diag_vu")})
            m.pop("diag_vu", None)
            result.setdefault(q, {})[name] = m
    (out / "cout.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    biome = (out / "biome.txt").read_text(encoding="utf-8").strip() if (out / "biome.txt").is_file() else "?"
    lines = [f"# Coût des effets de rendu (biome {biome}, 60 km/h)", "",
             "Gain = GPU médian de `base` moins celui de la variante (positif : la variante coûte moins).", ""]
    for q, rows in result.items():
        budget = targets["presets"][q]["gpu_ms_median_max"]
        lines += [f"## {q} (budget GPU {budget} ms)", "",
                  "| Variante | Ce qu'elle enlève | GPU ms | gain ms | i/s | p99 ms | GPU saturé % | primitives | appels |",
                  "| --- " * 9 + "|"]
        for name, m in sorted(rows.items(), key=lambda kv: -(kv[1]["gain_gpu_ms"] or 0) if kv[0] != "base" else -1e9):
            warn = " (diagnostic non vu au journal)" if m["diag_non_vu"] else ""
            lines.append(f"| {name} | {m['enleve']}{warn} | " + " | ".join(
                recette_u18.fmt(m[k]) for k in ("gpu_ms", "gain_gpu_ms", "fps", "p99_ms", "gpu_sature_pct",
                                                "primitives", "appels")) + " |")
        lines.append("")
    (out / "cout.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Résultat : {out / 'cout.md'} ; planche : {planche}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--list", action="store_true", help="énumérer les variantes et quitter")
    sub = ap.add_subparsers(dest="cmd")
    la = sub.add_parser("lancer")
    la.add_argument("--out", type=Path,
                    default=Path.home() / "OpenRide" / "mesures" / time.strftime("%Y-%m-%d") / "cout_rendu")
    la.add_argument("--qualites", default=",".join(QUALITIES))
    la.add_argument("--biome", default="farmland")
    la.add_argument("--duree", type=float, default=70.0, help="durée de chaque banc en s (défaut 70)")
    la.add_argument("--variantes", default=",".join(NAMES))
    la.add_argument("--size", default="1680x1011")
    la.add_argument("--godot", type=Path, default=Path(os.environ["GODOT"]) if os.environ.get("GODOT") else None)
    an = sub.add_parser("analyser")
    an.add_argument("dossier", type=Path)
    args = ap.parse_args(argv)
    if args.list or args.cmd is None:
        for name, diag, extra, qs, what in VARIANTS:
            print(f"{name:20} {','.join(qs):17} {diag or ' '.join(extra) or '—':22} {what}")
        return 0 if args.list else 2
    if args.cmd == "analyser":
        return analyse(args.dossier) if args.dossier.is_dir() else 2
    args.qualites = [q for q in args.qualites.split(",") if q in QUALITIES]
    args.variantes = [v for v in args.variantes.split(",") if v in NAMES]
    if not args.qualites or not args.variantes:
        print("qualités ou variantes inconnues (voir --list)", file=sys.stderr)
        return 2
    return cmd_lancer(args)


if __name__ == "__main__":
    sys.exit(main())
