#!/usr/bin/env python3
"""Avant/après des vitrines : captures en SSIM, comptes du CSV avec tolérance, planche (lot Z3, suite de X20).

Usage :
    vitrine_compare.py AVANT_DOSSIER APRES_DOSSIER [--out DOSSIER] [--seuil-ssim 0.97] [--tolerance 10]
                       [--planche 24]

Pour deux sorties d'une même vitrine (`vitrine_rendu.gd`, `vitrine_biomes.gd`, `vitrine_sols.gd`, lancées avec
le même préréglage et la même taille), sur la branche de référence puis sur la branche essayée :

- **captures** : les PNG de même nom sont réduits en vignettes de 640 pixels de large et comparés par la SSIM
  par blocs de `image_diff.py` (X20) ; échec sous `--seuil-ssim`. Une carte des écarts par paire
  (`<nom>_ecarts.png`). Une capture disparue est un échec, une capture nouvelle une information ;
- **comptes du CSV** : chaque CSV de même nom est lu ligne par ligne (clé : les premières colonnes de texte,
  par exemple biome, vue et préréglage). Les colonnes entières (triangles, appels de dessin, objets, arbres,
  bêtes…) doivent rester à `--tolerance` % près (et à plus de 2 unités, pour les petits comptes) ; les
  autres colonnes de texte, dont `qualite_appliquee`, doivent être identiques ; les mesures décimales (temps
  en ms, exposition) sont données à titre d'information. Une ligne disparue est un échec ;
- **planche** : `planche_avant_apres.png`, une rangée avant | après | écarts par capture, les `--planche`
  paires les moins semblables d'abord (règle des captures montrées au propriétaire), et `rapport.html` avec
  toutes les paires et tous les comptes.

Code de sortie : 0 si tout reste dans les seuils, 1 sinon, 2 si rien n'est comparable. Bibliothèque standard.
"""

from __future__ import annotations

import argparse
import csv
import html
import sys
import zlib
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import image_diff  # noqa: E402

DEFAULT_SSIM = 0.97          # même seuil que les références de visual_check.py (X20)
DEFAULT_TOLERANCE_PCT = 10.0
SMALL_COUNT = 2              # écart toujours admis sur un compte, en unités
DEFAULT_SHEET_ROWS = 24
THUMB_WIDTH = 320            # largeur d'une image de la planche
GAP = 6
TEXT_EXACT = "qualite_appliquee"


@dataclass
class Result:
    rows: list[tuple[bool | None, str, str]] = field(default_factory=list)
    pairs: list[tuple[str, float, float]] = field(default_factory=list)   # (nom, SSIM, écart moyen)

    def add(self, ok: bool | None, label: str, detail: str) -> None:
        self.rows.append((ok, label, detail))
        print(f"[{'INFO' if ok is None else 'OK' if ok else 'ÉCHEC'}] {label} : {detail}", flush=True)

    @property
    def failed(self) -> int:
        return sum(ok is False for ok, _, _ in self.rows)


# --- captures --------------------------------------------------------------------------------------

def _pngs(folder: Path) -> dict[str, Path]:
    return {p.name: p for p in sorted(folder.glob("*.png")) if not p.stem.endswith("_ecarts")
            and not p.name.startswith("planche")}


def compare_images(before: Path, after: Path, out: Path, seuil: float, res: Result) -> None:
    b, a = _pngs(before), _pngs(after)
    for name in sorted(b.keys() - a.keys()):
        res.add(False, f"capture {name}", "disparue après")
    for name in sorted(a.keys() - b.keys()):
        res.add(None, f"capture {name}", "nouvelle (aucune référence)")
    for name in sorted(b.keys() & a.keys()):
        try:
            ref = image_diff.vignette(image_diff.read_png(b[name]))
            img = image_diff.read_png(a[name])
            cmp = image_diff.compare(ref, img)
        except (OSError, ValueError, zlib.error) as exc:
            res.add(False, f"capture {name}", f"non comparable : {exc}")
            continue
        small = image_diff.resize(img, ref.width, ref.height)
        diff = image_diff.mean_abs_diff(ref, small)
        image_diff.write_png(out / f"{Path(name).stem}_ecarts.png", image_diff.ssim_map(ref, cmp))
        res.pairs.append((name, cmp.score, diff))
        res.add(cmp.score >= seuil, f"capture {name}",
                f"SSIM {cmp.score:.4f} (seuil {seuil:g}, pire bloc {cmp.worst:.3f}), écart moyen {diff:.2f} niveaux")


# --- comptes du CSV ---------------------------------------------------------------------------------

def _is_number(text: str) -> bool:
    try:
        float(text.replace(",", "."))
    except ValueError:
        return False
    return True


def _is_int(text: str) -> bool:
    return text.lstrip("-").isdigit()


def read_table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter=";")
        return list(reader.fieldnames or []), [dict(r) for r in reader]


def key_columns(header: list[str], rows: list[dict[str, str]]) -> list[str]:
    """Premières colonnes de texte (jusqu'à la qualité appliquée ou au premier nombre) : la clé d'une ligne."""
    keys: list[str] = []
    for col in header:
        if col == TEXT_EXACT or any(_is_number(r.get(col) or "") for r in rows):
            break
        keys.append(col)
    return keys or header[:1]


def compare_tables(before: Path, after: Path, tolerance: float, res: Result) -> list[tuple[str, str, str, str, str]]:
    """Compare les CSV de même nom ; renvoie les lignes du rapport (fichier, clé, colonne, avant, après)."""
    shown: list[tuple[str, str, str, str, str]] = []
    for path in sorted(before.glob("*.csv")):
        other = after / path.name
        if not other.is_file():
            res.add(False, f"tableau {path.name}", "absent après")
            continue
        header, rows_b = read_table(path)
        header_a, rows_a = read_table(other)
        keys = key_columns(header, rows_b)
        index_a = {tuple(r.get(k, "") for k in keys): r for r in rows_a}
        index_b = {tuple(r.get(k, "") for k in keys): r for r in rows_b}
        for missing in sorted(index_b.keys() - index_a.keys()):
            res.add(False, f"{path.name} {' / '.join(missing)}", "ligne disparue après")
        for new in sorted(index_a.keys() - index_b.keys()):
            res.add(None, f"{path.name} {' / '.join(new)}", "ligne nouvelle")
        for col in [c for c in header if c not in keys and c not in header_a]:
            res.add(False, f"tableau {path.name}", f"colonne « {col} » disparue après")
        cols = [c for c in header if c not in keys and c in header_a]
        moved = 0
        for key in sorted(index_b.keys() & index_a.keys()):
            rb, ra = index_b[key], index_a[key]
            label = f"{path.name} {' / '.join(key)}"
            for col in cols:
                vb, va = (rb.get(col) or "").strip(), (ra.get(col) or "").strip()
                if vb == va:
                    continue
                if _is_int(vb) and _is_int(va):
                    nb, na = int(vb), int(va)
                    pct = 100.0 * (na - nb) / max(abs(nb), 1)
                    ok = abs(na - nb) <= SMALL_COUNT or abs(pct) <= tolerance
                    res.add(ok, f"{label} · {col}", f"{nb} → {na} ({pct:+.1f} %, tolérance {tolerance:g} %)")
                elif _is_number(vb) and _is_number(va):
                    res.add(None, f"{label} · {col}", f"{vb} → {va} (mesure, information)")
                else:
                    res.add(False, f"{label} · {col}", f"« {vb} » → « {va} »")
                shown.append((path.name, " / ".join(key), col, vb, va))
                moved += 1
        res.add(True, f"tableau {path.name}", f"{len(index_b.keys() & index_a.keys())} lignes comparées, "
                f"{moved} valeurs changées (clé : {', '.join(keys)})")
    return shown


# --- planche et rapport ------------------------------------------------------------------------------

def _blit(dst: bytearray, dst_w: int, img: image_diff.Image, x0: int, y0: int) -> None:
    for y in range(img.height):
        i = ((y0 + y) * dst_w + x0) * 3
        j = y * img.width * 3
        dst[i:i + img.width * 3] = img.rgb[j:j + img.width * 3]


def write_sheet(before: Path, after: Path, out: Path, res: Result, max_rows: int) -> Path | None:
    """Planche avant | après | écarts des paires les moins semblables (SSIM la plus basse d'abord)."""
    pairs = sorted(res.pairs, key=lambda p: p[1])[:max_rows]
    if not pairs:
        return None
    thumbs = []
    for name, _, _ in pairs:
        row = []
        for path in (before / name, after / name, out / f"{Path(name).stem}_ecarts.png"):
            img = image_diff.read_png(path)
            row.append(image_diff.resize(img, THUMB_WIDTH, max(1, round(img.height * THUMB_WIDTH / img.width))))
        thumbs.append(row)
    width = 3 * THUMB_WIDTH + 4 * GAP
    height = sum(max(t.height for t in row) for row in thumbs) + (len(thumbs) + 1) * GAP
    canvas = bytearray(b"\x20" * (width * height * 3))
    y = GAP
    for row in thumbs:
        for k, t in enumerate(row):
            _blit(canvas, width, t, GAP + k * (THUMB_WIDTH + GAP), y)
        y += max(t.height for t in row) + GAP
    sheet = out / "planche_avant_apres.png"
    image_diff.write_png(sheet, image_diff.Image(width, height, bytes(canvas)))
    return sheet


def write_report(before: Path, after: Path, out: Path, res: Result, values: list[tuple[str, str, str, str, str]],
                 sheet: Path | None) -> Path:
    esc = html.escape
    parts = ["<!doctype html><meta charset='utf-8'><title>Vitrines avant/après</title>",
             "<style>body{font-family:sans-serif;margin:16px}table{border-collapse:collapse}"
             "td,th{border:1px solid #999;padding:3px 8px}tr.ko td{background:#fdd}img{width:320px}</style>",
             f"<h1>Vitrines avant/après</h1><p>Avant : {esc(str(before))}<br>Après : {esc(str(after))}<br>"
             f"{res.failed} échec(s).</p>"]
    if sheet:
        parts.append(f"<p>Planche : <a href='{esc(sheet.name)}'>{esc(sheet.name)}</a> (paires les moins semblables d'abord)</p>")
    parts.append("<h2>Captures</h2><table><tr><th>Capture</th><th>SSIM</th><th>Écart moyen</th>"
                 "<th>Avant</th><th>Après</th><th>Écarts</th></tr>")
    for name, score, diff in sorted(res.pairs, key=lambda p: p[1]):
        ko = any(ok is False and label == f"capture {name}" for ok, label, _ in res.rows)
        parts.append(f"<tr class='{'ko' if ko else ''}'><td>{esc(name)}</td><td>{score:.4f}</td><td>{diff:.2f}</td>"
                     f"<td><img src='{esc((before / name).resolve().as_uri())}'></td>"
                     f"<td><img src='{esc((after / name).resolve().as_uri())}'></td>"
                     f"<td><img src='{esc(Path(name).stem)}_ecarts.png'></td></tr>")
    parts.append("</table><h2>Comptes changés</h2><table><tr><th>Tableau</th><th>Ligne</th><th>Colonne</th>"
                 "<th>Avant</th><th>Après</th></tr>")
    for row in values:
        parts.append("<tr>" + "".join(f"<td>{esc(v)}</td>" for v in row) + "</tr>")
    parts.append("</table><h2>Vérifications</h2><ul>")
    for ok, label, detail in res.rows:
        parts.append(f"<li>{'INFO' if ok is None else 'OK' if ok else 'ÉCHEC'} {esc(label)} : {esc(detail)}</li>")
    parts.append("</ul>")
    page = out / "rapport.html"
    page.write_text("\n".join(parts), encoding="utf-8")
    return page


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("before", type=Path, help="dossier de la vitrine de référence (avant)")
    ap.add_argument("after", type=Path, help="dossier de la vitrine essayée (après)")
    ap.add_argument("--out", type=Path, help="dossier des écarts, de la planche et du rapport (défaut : APRES_ecarts)")
    ap.add_argument("--seuil-ssim", type=float, default=DEFAULT_SSIM, help=f"SSIM minimale (défaut {DEFAULT_SSIM:g})")
    ap.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE_PCT,
                    help=f"écart admis sur les comptes du CSV, en %% (défaut {DEFAULT_TOLERANCE_PCT:g})")
    ap.add_argument("--planche", type=int, default=DEFAULT_SHEET_ROWS,
                    help=f"nombre de paires sur la planche (défaut {DEFAULT_SHEET_ROWS})")
    a = ap.parse_args(argv)
    if not (a.before.is_dir() and a.after.is_dir()):
        print("ÉCHEC : AVANT_DOSSIER et APRES_DOSSIER doivent être des dossiers", file=sys.stderr)
        return 2
    out = a.out or a.after.parent / (a.after.name + "_ecarts")
    out.mkdir(parents=True, exist_ok=True)
    res = Result()
    compare_images(a.before, a.after, out, a.seuil_ssim, res)
    values = compare_tables(a.before, a.after, a.tolerance, res)
    if not res.rows:
        print("Rien à comparer : aucun PNG ni CSV de même nom", file=sys.stderr)
        return 2
    sheet = write_sheet(a.before, a.after, out, res, a.planche)
    page = write_report(a.before, a.after, out, res, values, sheet)
    print(f"Vitrines avant/après : {res.failed} échec(s) ; planche : {sheet or 'aucune'} ; rapport : {page}")
    return 1 if res.failed else 0


if __name__ == "__main__":
    sys.exit(main())
