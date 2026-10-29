#!/usr/bin/env python3
"""Comparateur avant/après de bancs et de vitrines (lot X14).

    engine/tests/compare_bench.py AVANT APRÈS [--seuil-bruit 3] [--out DOSSIER]

AVANT et APRÈS sont deux dossiers de même nature :
- **bancs** : sorties de `sim_bench.py` (un dossier par scénario, sonde dans `<scénario>/sonde/sonde.csv`
  avec `--probe`, sinon `fps.csv`) ou de `perf_probe.py` (`sonde.csv`) ;
- **vitrines** : sorties de `vitrine_rendu.gd` (`vitrine.csv`) ou de `vitrine_biomes.gd` (`vitrine_biomes.csv`).

Pour chaque scénario ou vue présent des deux côtés et chaque mesure (images/s, temps d'image p99, GPU de
la vue, appels de dessin, triangles), l'écart relatif donne un verdict : « pareil » dans le bruit
(`--seuil-bruit`, en %, 3 par défaut), sinon « mieux » ou « moins bien » (plus d'images/s est mieux, moins
pour le reste). Les bancs sont résumés après `warmup_s` secondes (`perf_targets.json`), en médiane.

Écrit `comparaison.html` (préréglage appliqué de chaque côté, tableau des écarts, captures de même nom
côte à côte avec un curseur glissant) et `ecarts.csv` dans `--out` (défaut : `APRÈS/comparaison`).
Code de sortie : 0 si rien n'est « moins bien », 1 sinon, 2 si les dossiers sont illisibles ou de natures
différentes. Bibliothèque standard seulement.
"""

from __future__ import annotations

import argparse
import csv
import html
import os
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import perf_probe  # noqa: E402

# Mesures comparées : clé -> (libellé, plus grand = mieux).
METRICS = {
    "fps": ("images/s", True),
    "p99_ms": ("temps d'image p99 (ms)", False),
    "gpu_ms": ("GPU de la vue (ms)", False),
    "draw_calls": ("appels de dessin", False),
    "triangles": ("triangles", False),
}
# Colonnes des sources -> mesure comparée.
PROBE_COLUMNS = {"fps": "fps", "frame_p99_ms": "p99_ms", "gpu_ms": "gpu_ms", "draw_calls": "draw_calls",
                 "primitives": "triangles"}
FPS_COLUMNS = {"fps": "fps", "appels_de_dessin": "draw_calls"}
SHOWCASE_COLUMNS = {"triangles": "triangles", "appels_dessin": "draw_calls"}
SHOWCASE_KEYS = ("biome", "vue", "préréglage")
DEFAULT_NOISE_PCT = 3.0


@dataclass
class Side:
    """Un côté de la comparaison : nature, mesures par scénario ou vue, préréglages, captures."""
    root: Path
    kind: str = ""                                     # « banc » ou « vitrine »
    entries: dict[str, dict[str, float]] = field(default_factory=dict)
    presets: dict[str, str] = field(default_factory=dict)
    images: dict[str, Path] = field(default_factory=dict)


def _median(vals: list[float]) -> float | None:
    return statistics.median(vals) if vals else None


def _read_semicolon(path: Path, delimiter: str = ";") -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter=delimiter))
    return [{k: perf_probe._num(v) if isinstance(v, str) else v for k, v in r.items()} for r in rows]


def probe_entry(rows: list[dict[str, Any]], warmup_s: float) -> tuple[dict[str, float], str]:
    """Médianes d'une sonde après la chauffe, et préréglage(s) appliqué(s)."""
    ts = perf_probe.values(rows, "t_s")
    t0 = (min(ts) if ts else 0.0) + warmup_s
    steady = [r for r in rows if not isinstance(r.get("t_s"), (int, float)) or r["t_s"] >= t0] or rows
    out = {}
    for col, key in PROBE_COLUMNS.items():
        m = _median(perf_probe.values(steady, col))
        if m is not None:
            out[key] = m
    return out, ", puis ".join(perf_probe.presets_of(rows))


def load_side(root: Path, warmup_s: float) -> Side:
    side = Side(root)
    if not root.is_dir():
        raise SystemExit(f"dossier introuvable : {root}")
    showcases = sorted(p for p in root.rglob("*.csv") if p.name in ("vitrine.csv", "vitrine_biomes.csv"))
    probes = sorted(root.rglob("sonde.csv"))
    fps_files = sorted(root.rglob("fps.csv"))
    if showcases:
        side.kind = "vitrine"
        for path in showcases:
            for row in _read_semicolon(path):
                key = " / ".join(str(row[k]) for k in SHOWCASE_KEYS if k in row)
                side.entries[key] = {m: float(row[c]) for c, m in SHOWCASE_COLUMNS.items()
                                     if isinstance(row.get(c), (int, float))}
                side.presets[key] = str(row.get("qualite_appliquee") or row.get("préréglage") or "")
    elif probes or fps_files:
        side.kind = "banc"
        for path in probes:
            scen = path.parent.parent.name if path.parent.name == "sonde" else path.parent.name
            side.entries[scen], side.presets[scen] = probe_entry(perf_probe.read_engine_csv(path), warmup_s)
        for path in fps_files:   # banc sans sonde : images/s et appels de dessin relevés aux captures
            scen = path.parent.name
            if scen in side.entries:
                continue
            rows = _read_semicolon(path, ",")
            side.entries[scen] = {m: v for c, m in FPS_COLUMNS.items()
                                  if (v := _median(perf_probe.values(rows, c))) is not None}
            side.presets[scen] = ", ".join(sorted({str(r.get("qualite")) for r in rows if r.get("qualite")}))
    else:
        raise SystemExit(f"{root} : ni sonde (sonde.csv), ni fps.csv, ni vitrine (vitrine.csv)")
    for png in sorted(root.rglob("*.png")):
        side.images[png.relative_to(root).as_posix()] = png
    return side


def verdict(before: float, after: float, higher_is_better: bool, noise_pct: float) -> tuple[str, float | None]:
    """(« mieux » | « pareil » | « moins bien », écart en %)."""
    if before == 0:
        return ("pareil", 0.0) if after == 0 else ("moins bien" if (after > 0) != higher_is_better else "mieux", None)
    pct = (after - before) / abs(before) * 100.0
    if abs(pct) <= noise_pct:
        return "pareil", pct
    return ("mieux" if (pct > 0) == higher_is_better else "moins bien"), pct


def compare(before: Side, after: Side, noise_pct: float = DEFAULT_NOISE_PCT) -> list[dict[str, Any]]:
    rows = []
    for key in sorted(set(before.entries) & set(after.entries)):
        b, a = before.entries[key], after.entries[key]
        for metric, (label, higher) in METRICS.items():
            if metric in b and metric in a:
                v, pct = verdict(b[metric], a[metric], higher, noise_pct)
                rows.append({"entree": key, "mesure": metric, "libelle": label, "avant": b[metric], "apres": a[metric],
                             "ecart_pct": pct, "verdict": v})
    return rows


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["entree", "mesure", "avant", "apres", "ecart_pct", "verdict"])
        for r in rows:
            w.writerow([r["entree"], r["mesure"], f"{r['avant']:.3f}", f"{r['apres']:.3f}",
                        "" if r["ecart_pct"] is None else f"{r['ecart_pct']:+.1f}", r["verdict"]])


COLORS = {"mieux": "var(--ok)", "pareil": "var(--muted)", "moins bien": "var(--ko)"}


def write_html(before: Side, after: Side, rows: list[dict[str, Any]], noise_pct: float, out: Path) -> None:
    def rel(p: Path) -> str:
        return html.escape(os.path.relpath(p, out))

    presets = "".join(f"<tr><td>{html.escape(k)}</td><td>{html.escape(before.presets.get(k, '') or '?')}</td>"
                      f"<td>{html.escape(after.presets.get(k, '') or '?')}</td></tr>"
                      for k in sorted(set(before.entries) | set(after.entries)))
    table = "".join(
        f"<tr><td>{html.escape(r['entree'])}</td><td>{html.escape(r['libelle'])}</td><td>{r['avant']:.2f}</td>"
        f"<td>{r['apres']:.2f}</td><td>{'' if r['ecart_pct'] is None else format(r['ecart_pct'], '+.1f') + ' %'}</td>"
        f"<td style=\"color:{COLORS[r['verdict']]};font-weight:600\">{r['verdict']}</td></tr>" for r in rows)
    pairs = sorted(set(before.images) & set(after.images))
    figures = "".join(
        f'<figure><div class="cmp"><img src="{rel(before.images[n])}" alt="avant"><img class="top" '
        f'src="{rel(after.images[n])}" alt="après"></div><input type="range" min="0" max="100" value="50" '
        f'aria-label="curseur avant/après"><figcaption>{html.escape(n)} · gauche : avant, droite : après'
        f'</figcaption></figure>' for n in pairs)
    alone = sorted(set(before.images) ^ set(after.images))
    worse = sum(r["verdict"] == "moins bien" for r in rows)
    better = sum(r["verdict"] == "mieux" for r in rows)
    doc = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Comparaison avant après</title>
<style>
:root {{ --bg:#fafafa; --fg:#222; --muted:#666; --card:#fff; --line:#ddd; --ok:#1e8449; --ko:#c0392b; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#16181b; --fg:#e8e8e8; --muted:#9aa; --card:#1f2226; --line:#333; }} }}
body {{ background:var(--bg); color:var(--fg); font:15px/1.45 system-ui,sans-serif; margin:0 auto; max-width:1200px; padding:16px; }}
table {{ border-collapse:collapse; width:100%; margin-bottom:12px; }} td,th {{ border-bottom:1px solid var(--line); padding:4px 6px; text-align:left; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(420px,1fr)); gap:12px; }}
figure {{ margin:0; background:var(--card); border:1px solid var(--line); }} figcaption {{ font-size:12px; padding:4px 6px; color:var(--muted); }}
.cmp {{ position:relative; }} .cmp img {{ width:100%; display:block; }} .cmp img.top {{ position:absolute; inset:0; clip-path:inset(0 0 0 50%); }}
input[type=range] {{ width:100%; margin:0; }}
</style></head><body>
<h1>Comparaison avant / après</h1>
<p>Avant : <code>{html.escape(str(before.root))}</code><br>Après : <code>{html.escape(str(after.root))}</code><br>
Nature : {before.kind}. Bruit : ± {noise_pct:g} %. <b>{better} mieux, {worse} moins bien</b>, {len(rows) - better - worse} pareil.</p>
<h2>Préréglage appliqué</h2><table><tr><th>Entrée</th><th>Avant</th><th>Après</th></tr>{presets}</table>
<h2>Écarts</h2><table><tr><th>Entrée</th><th>Mesure</th><th>Avant</th><th>Après</th><th>Écart</th><th>Verdict</th></tr>{table}</table>
<h2>Captures ({len(pairs)} paires)</h2><div class="grid">{figures}</div>
{f"<p>Sans pendant de l'autre côté : {html.escape(', '.join(alone[:40]))}</p>" if alone else ""}
<script>
document.querySelectorAll("figure").forEach(f => {{
  const top = f.querySelector("img.top"), r = f.querySelector("input");
  if (top && r) r.addEventListener("input", () => {{ top.style.clipPath = `inset(0 0 0 ${{r.value}}%)`; }});
}});
</script>
</body></html>"""
    (out / "comparaison.html").write_text(doc, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Comparateur avant/après de bancs et de vitrines (lot X14).")
    ap.add_argument("avant", type=Path)
    ap.add_argument("apres", type=Path)
    ap.add_argument("--seuil-bruit", type=float, default=DEFAULT_NOISE_PCT, help="écart en %% jugé « pareil »")
    ap.add_argument("--out", type=Path, help="dossier du rapport (défaut : APRÈS/comparaison)")
    args = ap.parse_args(argv)
    warmup = float(perf_probe.load_targets().get("warmup_s", 0))
    try:
        before, after = load_side(args.avant, warmup), load_side(args.apres, warmup)
    except SystemExit as exc:
        print(f"ÉCHEC : {exc}", file=sys.stderr)
        return 2
    if before.kind != after.kind:
        print(f"ÉCHEC : natures différentes ({before.kind} avant, {after.kind} après)", file=sys.stderr)
        return 2
    rows = compare(before, after, args.seuil_bruit)
    if not rows:
        print("ÉCHEC : aucun scénario ni vue commun aux deux dossiers", file=sys.stderr)
        return 2
    out = args.out or args.apres / "comparaison"
    out.mkdir(parents=True, exist_ok=True)
    write_csv(rows, out / "ecarts.csv")
    write_html(before, after, rows, args.seuil_bruit, out)
    for r in rows:
        pct = "" if r["ecart_pct"] is None else f" ({r['ecart_pct']:+.1f} %)"
        print(f"  {r['verdict']:<10} {r['entree']} : {r['libelle']} {r['avant']:.2f} → {r['apres']:.2f}{pct}")
    worse = [r for r in rows if r["verdict"] == "moins bien"]
    print(f"Rapport : {out / 'comparaison.html'}")
    print(f"RÉSULTAT : {'rien de moins bien' if not worse else f'{len(worse)} mesure(s) moins bien'}")
    return 1 if worse else 0


if __name__ == "__main__":
    sys.exit(main())
