#!/usr/bin/env python3
"""Coût de chaque effet de rendu sur le PC cible : un banc par effet coupé ou allégé, en low, medium et high.

Usage :
    cout_rendu.py lancer [--out DOSSIER] [--qualites low,medium,high] [--biome farmland | --troncon B1,B2,…] [--duree 70]
                         [--variantes base,sans_ombres,...] [--repetitions N]
                         [--godot CHEMIN]
    cout_rendu.py analyser DOSSIER
    cout_rendu.py --list

Recherche d'optimisation du 5 novembre (recette U18 : GPU au-dessus du budget en medium et high sur les
cultures et la forêt). Chaque variante relance `sim_bench.py --native --probe` sur un parcours de 6 km tout entier dans un biome
(`make_biome_world.py --biome`, lot U19 ; défaut `farmland`, le plus lourd à la recette U18), à 60 km/h, et une seule
différence avec le préréglage, passée à l'engine par OPENRIDE_RENDER_DIAG (`scripts/render_diag.gd`) ou par
`--culling on`. `analyser` écrit `cout.md` et `cout.json` : temps GPU médian, images/s, p99, part des secondes où
le GPU est saturé, et gain par rapport à `base` de la même qualité ; `planche/` garde la dernière capture de
chaque variante (coût visuel, à juger à l'œil).

`--troncon farmland,temperate_forest,alpine` (6 novembre, lot « cultures et forêt ») : parcours de 2 km par biome,
comme le tour de la recette U18, au lieu de 6 km d'un seul biome. Le banc tout en cultures est sous le budget alors que
le bloc cultures du tour le dépasse (low 5,2 contre 7,8 ms) : ce que la caméra voit devant elle (la forêt du bloc
suivant) compte. La sonde est découpée biome par biome (`recette_u18.split_tour`, frontières de 300 m à part) et
`cout.md` donne le GPU médian de chaque variante dans chaque biome ; `--duree` par défaut : tous les blocs sauf le
dernier (qui ne sert qu'à ce que la caméra voit devant elle) ; une capture tous les 500 m.

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
SPEED_KMH = 60.0
BIOME_KEYS = ("gpu_ms", "fps", "p99_ms", "primitives")
# (nom, OPENRIDE_RENDER_DIAG, options de sim_bench, qualités concernées, ce que la variante enlève à l'image)
VARIANTS: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...], str], ...] = (
    ("base", "", (), QUALITIES, "préréglage tel quel"),
    ("passes", "", ("--gpu-profile",), QUALITIES, "même réglage que base, temps GPU de chaque passe (passes.md)"),
    # Ombres
    ("sans_ombres", "sans_ombres", (), QUALITIES, "aucune ombre portée (borne du coût des ombres)"),
    ("sans_ombres_arbres", "sans_ombres_arbres", (), QUALITIES, "arbres sans ombre portée"),
    ("sans_ombres_details", "sans_ombres_details", (), QUALITIES, "pierres et fleurs du sol sans ombre"),
    ("ombres_2_cascades", "ombres_2_cascades", (), ("medium", "high"), "2 cascades d'ombre au lieu de 4"),
    ("ombres_200m", "ombres_m=200", (), ("medium", "high"), "ombres jusqu'à 200 m au lieu de 400 / 600"),
    ("atlas_4096", "atlas=4096", (), ("medium", "high"), "COÛT : atlas des ombres 4096 au lieu de 2048"),
    ("filtre_low", "filtre=low", (), ("high",), "bord des ombres moins doux"),
    # Effets d'écran
    ("sans_ssao", "sans_ssao", (), ("medium", "high"), "sans occlusion ambiante"),
    ("ssao_low", "ssao=low", (), ("medium", "high"), "occlusion ambiante basse"),
    ("ssil_low", "ssil=low", (), ("medium", "high"), "COÛT : lumière indirecte d'écran « low » (coupée au préréglage)"),
    ("sans_brume", "sans_brume", (), ("medium", "high"), "sans brume volumétrique"),
    ("brume_light", "brume=light", (), ("high",), "grille de brume volumétrique du medium"),
    ("msaa4", "msaa=4", (), ("medium", "high"), "COÛT : MSAA 4× au lieu de 2×"),
    ("msaa0", "msaa=0", (), ("medium", "high"), "sans MSAA ni SMAA (bords crénelés)"),
    ("msaa0_smaa", "msaa=0,screen_aa=smaa", (), ("medium", "high"), "SMAA à la place du MSAA (comme low)"),
    ("sans_glow", "sans_glow", (), ("medium", "high"), "sans halo"),
    # Décor
    ("herbe_50", "herbe=0.5", (), QUALITIES, "moitié des touffes d'herbe"),
    ("vegetation_50", "vegetation_x=0.5", (), QUALITIES, "moitié moins d'arbres (densité du préréglage × 0,5)"),
    ("sans_arbres", "vegetation_x=0", (), QUALITIES, "aucun arbre proche (borne du coût des arbres)"),
    ("sans_imposteurs", "", ("--forest", "off"), QUALITIES, "sans les forêts lointaines en imposteurs (lot Y5)"),
    ("arbres_lod0_300m", "arbres_lod0_m=300", (), QUALITIES, "arbres détaillés jusqu'à 300 m au lieu de 450"),
    ("lod_maillage_1", "lod_maillage=1.0", (), ("high",), "niveaux de détail des maillages comme en medium"),
    ("lod_maillage_2", "lod_maillage=2.0", (), ("medium",), "niveaux de détail des maillages comme en low"),
    ("tri_visible", "", ("--culling", "on"), QUALITIES, "tri de ce que la caméra ne voit pas (lot S1)"),
    # Ciel
    ("ciel_temps_reel", "ciel=realtime", (), QUALITIES, "COÛT : carte de rayonnement du ciel recalculée à chaque image"),
    ("ciel_128", "ciel_radiance=128", (), QUALITIES, "carte de rayonnement du ciel en 128 au lieu de 256"),
    # Améliorations à faible coût (5 novembre soir) : le « gain » attendu est négatif (coût), à garder près de 0
    ("soleil_brume", "soleil_brume=0.3", (), QUALITIES, "AJOUT : halo du soleil dans le brouillard (fog_sun_scatter)"),
    ("terrain_macro", "terrain_macro=0.35", (), QUALITIES, "AJOUT : prés plus ou moins mûrs à l'échelle de 600 m"),
    ("herbe_degrade", "herbe_degrade=0.35", (), QUALITIES, "AJOUT : herbe au pied plus sombre, pointe plus claire"),
    ("embellis", "soleil_brume=0.3,terrain_macro=0.35,herbe_degrade=0.35", (), QUALITIES,
     "AJOUT : les trois améliorations ensemble"),
)
# Les réglages retenus par l'étude du 6 novembre (MSAA 2×, atlas 2048, halo à 3 niveaux, feuillage lambert, arbres
# lointains sans vent, brume éclairée, ciel allégé, high sans SSIL) sont dans les préréglages : `base` les mesure.
NAMES = [v[0] for v in VARIANTS]


def plan(qualities: list[str], names: list[str]) -> list[tuple[str, tuple]]:
    return [(q, v) for q in qualities for v in VARIANTS if v[0] in names and q in v[3]]


def troncon_duration(biomes: tuple[str, ...], speed_kmh: float = SPEED_KMH) -> float:
    """Durée d'un banc de tronçon : tous les blocs sauf le dernier, départ et chargement compris (45 s)."""
    import make_biome_world
    return max(1, len(biomes) - 1) * make_biome_world.BLOCK_M / (speed_kmh / 3.6) + 45.0


def cmd_lancer(args: argparse.Namespace) -> int:
    out: Path = args.out
    # Pire cas (règle du métier : mesurer là où ça coûte le plus) : un parcours de 6 km tout entier dans le
    # biome, relief et végétation du biome (make_biome_world --biome), plutôt que le premier km du tour.
    # Avec --troncon : un bloc de 2 km par biome, comme le tour (ce qui est devant la caméra compte).
    routes = out / "routes"
    biomes = tuple(args.troncon) if args.troncon else (args.biome,) * 3
    name = "banc-" + ("-".join(args.troncon) if args.troncon else args.biome)
    world = routes / f"{name}.world"
    if not world.is_dir():
        import make_biome_world
        try:
            make_biome_world.generate(routes, name, biomes)
        except (ImportError, RuntimeError, ValueError) as exc:
            print(f"parcours du banc impossible : {exc}", file=sys.stderr)
            return 2
    if args.troncon:
        (out / "troncon.txt").write_text(",".join(args.troncon) + "\n", encoding="utf-8")
    duration = args.duree if args.duree else (troncon_duration(biomes) if args.troncon else 70.0)
    shots = ["--every-m", "500"] if args.troncon else ["--every", "30"]
    # Répétitions alternées (règle du métier : le bruit d'un banc de 70 s est d'environ ±0,5 ms) : r1 de toutes les
    # variantes, puis r2…, la médiane des répétitions est gardée
    one = plan(args.qualites, args.variantes)
    runs = [(q, v, r) for r in range(1, args.repetitions + 1) for q, v in one
            if r == 1 or v[0] != "passes"]
    print(f"{len(runs)} bancs de {duration:.0f} s (≈ {len(runs) * (duration + 30) / 60:.0f} min)", flush=True)
    t0 = time.time()
    for k, (q, (name, diag, extra, _qs, _what), rep) in enumerate(runs):
        rdir = out / q / name / f"r{rep}" if args.repetitions > 1 else out / q / name
        rdir.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, str(TESTS_DIR / "sim_bench.py"), "--native", "--probe", "--muet",
               "--quality", q, "--size", args.size, "--world", str(world),
               "--speed-kmh", f"{SPEED_KMH:g}", *shots, "--duration", f"{duration:.0f}", "--out", str(rdir), *extra]
        if args.godot:
            cmd += ["--godot", str(args.godot)]
        env = {**os.environ, "OPENRIDE_RENDER_DIAG": diag}
        print(f"[{k + 1}/{len(runs)}] {q} {name} ({(time.time() - t0) / 60:.0f} min)", flush=True)
        with (rdir / "sim_bench.txt").open("w", encoding="utf-8") as fh:
            subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, env=env)
    (out / "biome.txt").write_text((",".join(args.troncon) if args.troncon else args.biome) + "\n", encoding="utf-8")
    return analyse(out)


def _median(rows: list[dict[str, Any]], key: str) -> float | None:
    v = perf_probe.values(rows, key)
    return round(statistics.median(v), 2) if v else None


def by_biome(sdir: Path, warm_s: float, troncon: tuple[str, ...], length_m: float | None) -> dict[str, Any]:
    """GPU médian, images/s, p99 et primitives de chaque biome du tronçon (frontières de 300 m à part)."""
    groups = recette_u18.split_tour(recette_u18.probe_rows(sdir), recette_u18.journal_distance(sdir / "seance.jsonl"),
                                    warm_s, length_m, troncon)
    return {b: {"secondes": len(rows), **{k: _median(rows, k) for k in BIOME_KEYS}} for b, rows in groups.items()}


def measure(rdir: Path, warm_s: float, troncon: tuple[str, ...] = (), length_m: float | None = None
            ) -> dict[str, Any] | None:
    sdir = recette_u18.run_dir(rdir)
    if sdir is None:
        return None
    rows = recette_u18.probe_rows(sdir)
    t_min = min(perf_probe.values(rows, "t_s"), default=0.0) + warm_s
    rows = [r for r in rows if isinstance(r.get("t_s"), (int, float)) and r["t_s"] >= t_min]

    def med(key: str) -> float | None:
        return _median(rows, key)

    util = perf_probe.values(rows, "gpu_util_pct")
    engine_log = (sdir / "engine.log").read_text(encoding="utf-8", errors="replace") if (sdir / "engine.log").is_file() else ""
    return {"secondes": len(rows), "gpu_ms": med("gpu_ms"), "fps": med("fps"), "p99_ms": med("frame_p99_ms"),
            "primitives": med("primitives"), "appels": med("draw_calls"),
            "gpu_sature_pct": round(100.0 * sum(u > 95.0 for u in util) / len(util), 1) if util else None,
            "diag_vu": "Diagnostic de rendu" in engine_log, "dossier": sdir,
            **({"par_biome": by_biome(sdir, warm_s, troncon, length_m)} if troncon else {})}


def gpu_passes(log: Path, skip: int = 5) -> dict[str, float]:
    """Médiane du temps GPU de chaque passe (blocs « GPU PROFILE » de Godot --gpu-profile, `skip` premiers ignorés)."""
    blocks: list[dict[str, float]] = []
    if log.is_file():
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("GPU PROFILE"):
                blocks.append({})
            elif blocks and line.lstrip().startswith("-") and line.rstrip().endswith("ms"):
                name, _, val = line.strip()[1:].rpartition(":")
                try:
                    blocks[-1][name.strip()] = float(val.strip()[:-2])
                except ValueError:
                    pass
    blocks = blocks[skip:]
    names = {n for b in blocks for n in b}
    return {n: round(statistics.median([b.get(n, 0.0) for b in blocks]), 3) for n in names}


def measure_reps(path: Path, warm: float, troncon: tuple[str, ...] = (), length_m: float | None = None
                 ) -> dict[str, Any] | None:
    """Mesure d'une variante : médiane de ses répétitions (`r1`, `r2`…) s'il y en a."""
    reps = sorted(p for p in path.glob("r[0-9]*") if p.is_dir())
    if not reps:
        return measure(path, warm, troncon, length_m)
    ms = [m for m in (measure(r, warm, troncon, length_m) for r in reps) if m is not None]
    if not ms:
        return None
    out = dict(ms[0])
    for key in ("gpu_ms", "fps", "p99_ms", "primitives", "appels", "gpu_sature_pct"):
        vals = [m[key] for m in ms if isinstance(m.get(key), (int, float))]
        out[key] = round(statistics.median(vals), 2) if vals else None
    out["gpu_ms_reps"] = [m.get("gpu_ms") for m in ms]
    if troncon:
        out["par_biome"] = {}
        for b in ms[0].get("par_biome", {}):
            parts = [m["par_biome"][b] for m in ms if b in m.get("par_biome", {})]
            out["par_biome"][b] = {"secondes": sum(p["secondes"] for p in parts)}
            for key in BIOME_KEYS:
                vals = [p[key] for p in parts if isinstance(p.get(key), (int, float))]
                out["par_biome"][b][key] = round(statistics.median(vals), 2) if vals else None
            out["par_biome"][b]["gpu_ms_reps"] = [p.get("gpu_ms") for p in parts]
    out["diag_vu"] = all(m["diag_vu"] for m in ms)
    return out


def write_passes(out: Path, passes: dict[str, dict[str, float]]) -> None:
    lines = ["# Temps GPU de chaque passe de rendu (Godot --gpu-profile, médiane après chauffe)", "",
             "Mesuré avec la variante `passes` (mêmes réglages que `base`). L'option de profil coûte un peu de temps",
             "GPU : comparer les passes entre elles, pas le total avec `base`.", ""]
    for q, rows in passes.items():
        total = sum(rows.values())
        lines += [f"## {q} (somme des passes {total:.2f} ms)", "", "| Passe | ms | part |", "| --- | --- | --- |"]
        for name, ms in sorted(rows.items(), key=lambda kv: -kv[1]):
            if ms >= 0.05:
                lines.append(f"| {name} | {ms:.2f} | {100 * ms / total:.0f} % |" if total else f"| {name} | {ms:.2f} | |")
        lines.append("")
    (out / "passes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def middle_shots(sdir: Path, troncon: tuple[str, ...]) -> dict[str, Path]:
    """Capture du milieu de chaque bloc du tronçon (`*_dNNNNN.png` de `--every-m 500`, à 2 km × k + 1 km)."""
    import make_biome_world
    picked: dict[str, Path] = {}
    for png in sorted(sdir.glob("*_d[0-9][0-9][0-9][0-9][0-9].png")) if troncon else []:
        k, rest = divmod(float(png.stem.rsplit("_d", 1)[1]), make_biome_world.BLOCK_M)
        if abs(rest - make_biome_world.BLOCK_M / 2) < 1.0 and int(k) < len(troncon):
            picked[troncon[int(k)]] = png
    return picked


def troncon_of(out: Path) -> tuple[tuple[str, ...], float | None]:
    """Biomes du tronçon (`troncon.txt`, écrit par `lancer --troncon`) et longueur de sa route compilée."""
    path = out / "troncon.txt"
    if not path.is_file():
        return (), None
    biomes = tuple(b for b in path.read_text(encoding="utf-8").strip().split(",") if b)
    try:
        info = json.loads((out / "routes" / f"banc-{'-'.join(biomes)}.json").read_text(encoding="utf-8"))
        length = float(info["length_m"])
    except (OSError, ValueError, KeyError, TypeError):
        length = None
    return biomes, length


def biome_lines(result: dict[str, Any], targets: dict[str, Any], troncon: tuple[str, ...]) -> list[str]:
    """Tableaux « GPU médian (gain) par biome » de chaque qualité, pour `cout.md`."""
    cols = [*troncon, "frontières"]
    lines = ["## Par biome du tronçon", "",
             "GPU médian en ms et, entre parenthèses, gain par rapport à `base` dans le même biome.", ""]
    for q, rows in result.items():
        budget = targets["presets"][q]["gpu_ms_median_max"]
        base = rows.get("base", {}).get("par_biome", {})
        lines += [f"### {q} (budget GPU {budget} ms)", "", "| Variante | " + " | ".join(cols) + " |",
                  "| --- " * (len(cols) + 1) + "|"]
        for name, m in rows.items():
            cells = []
            for b in cols:
                v = m.get("par_biome", {}).get(b, {}).get("gpu_ms")
                ref = base.get(b, {}).get("gpu_ms")
                if v is None:
                    cells.append("—")
                elif name == "base" or ref is None:
                    cells.append(f"**{v:.2f}**" if name == "base" and v > budget else f"{v:.2f}")
                else:
                    cells.append(f"{v:.2f} ({ref - v:+.2f})")
            lines.append(f"| {name} | " + " | ".join(cells) + " |")
        lines.append("")
    return lines


def analyse(out: Path) -> int:
    targets = perf_probe.load_targets()
    warm = float(targets.get("warmup_s", 20))
    troncon, length = troncon_of(out)
    planche = out / "planche"
    planche.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {}
    passes: dict[str, dict[str, float]] = {}
    for q in QUALITIES:
        base = None
        for name, diag, _extra, qs, what in VARIANTS:
            if q not in qs or not (out / q / name).is_dir():
                continue
            m = measure_reps(out / q / name, warm, troncon, length)
            if m is None:
                continue
            sdir = m.pop("dossier")
            if name == "passes":
                passes[q] = gpu_passes(sdir / "engine.log")
            shots = sorted(sdir.glob("*_t*.png"))
            if shots:
                shutil.copy(shots[-1], planche / f"{q}_{name}.png")
            for biome, png in middle_shots(sdir, troncon).items():
                shutil.copy(png, planche / f"{q}_{name}_{biome}.png")
            if name == "base":
                base = m
            gain = (round(base["gpu_ms"] - m["gpu_ms"], 2) if base and base.get("gpu_ms") is not None
                    and m.get("gpu_ms") is not None else None)
            m.update({"enleve": what, "diag": diag, "gain_gpu_ms": gain,
                      "diag_non_vu": bool(diag) and not m.pop("diag_vu")})
            m.pop("diag_vu", None)
            result.setdefault(q, {})[name] = m
    if passes:
        write_passes(out, passes)
    (out / "cout.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    biome = (out / "biome.txt").read_text(encoding="utf-8").strip() if (out / "biome.txt").is_file() else "?"
    socle = (out / "socle.txt").read_text(encoding="utf-8").strip() if (out / "socle.txt").is_file() else "préréglage"
    lines = [f"# Coût des effets de rendu (biome {biome}, 60 km/h, socle : {socle})", "",
             "Gain = GPU médian de `base` moins celui de la variante (positif : la variante coûte moins).",
             "Avec des répétitions, chaque chiffre est la médiane des répétitions (détail dans cout.json).", ""]
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
    if troncon:
        lines += biome_lines(result, targets, troncon)
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
    la.add_argument("--troncon", help="biomes du tronçon, 2 km chacun (ex. farmland,temperate_forest,alpine)")
    la.add_argument("--duree", type=float, default=None,
                    help="durée de chaque banc en s (défaut 70 ; avec --troncon : tous les blocs sauf le dernier)")
    la.add_argument("--variantes", default=",".join(NAMES))
    la.add_argument("--repetitions", type=int, default=1, help="bancs par variante, alternés (défaut 1)")
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
    if args.troncon:
        import make_biome_world
        args.troncon = [b for b in args.troncon.split(",") if b]
        if len(args.troncon) < 2 or any(b not in make_biome_world.TOUR for b in args.troncon):
            print(f"tronçon : au moins deux biomes parmi {', '.join(make_biome_world.TOUR)}", file=sys.stderr)
            return 2
    if not args.qualites or not args.variantes:
        print("qualités ou variantes inconnues (voir --list)", file=sys.stderr)
        return 2
    return cmd_lancer(args)


if __name__ == "__main__":
    sys.exit(main())
