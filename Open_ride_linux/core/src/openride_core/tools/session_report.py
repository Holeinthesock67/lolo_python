"""Analyse automatique d'une séance réelle (lot X12) : `openride-core session-report`.

    openride-core session-report [JOURNAL.jsonl|SEANCE.fit] [--log run_trainer.log] [--engine-log engine.log]
                                 [--out DOSSIER] [--json]

Sans fichier, le dernier journal. Tout se calcule en local, sans réseau : le journal et le FIT restent
sur le PC, le rapport va dans `~/OpenRide/rapports/<séance>/` (hors du dépôt) :
`rapport.html` (tableaux et courbes SVG, sans dépendance), `sections.csv` et `resume.json`.

Définitions :
- **Sections de pente** : relevés hors pauses, dans l'ordre de la distance ; coupure dès que la pente du
  parcours s'écarte de plus de 1,5 point de la moyenne de la section ; une section de moins de 200 m
  rejoint sa voisine de pente la plus proche, et deux voisines à moins de 1,5 point se rejoignent. Pente du parcours :
  champ `grade` du journal, sinon tirée de l'altitude (FIT). Par section : longueur, pente moyenne du
  parcours, pente envoyée médiane, braquet le plus utilisé, puissance, cadence, vitesse et FC médianes.
- **Retard pente → effort** : à chaque marche de pente de plus de 3 points (écart entre les médianes
  des 10 s avant et des 10 s après), ancien palier de puissance = médiane des 10 s avant, nouveau
  palier = médiane de 30 à 60 s après ; retard = premier instant où la puissance (moyenne centrée sur
  3 s) a fait 63 % du chemin. Marche ignorée si la cadence tombe à 0 dans la minute, ou si les deux
  paliers diffèrent de moins de 20 W.
- **ERG** : par bloc (`block`), écart de la puissance à la cible (`target_w`) : médiane et p90 de
  l'écart absolu (W), secondes hors de ± 5 % de la cible.
- **Coupures** : lignes `device` du journal ; avec `--log`, coupures du trainer et du Click et appuis par
  boîtier lus par `log_report`. Avec `--engine-log`, images par seconde des lignes `[perf-rendu]`.
- **Série T** : lignes `segment` (temps de chaque montée et sprint, record, bonus) et `powerup` (bonus pris).
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

from ..config import OPENRIDE_HOME
from ..journal import read_journal
from .session_summary import SummaryError, _device_drops, load_session, running_records

REPORTS_DIR = OPENRIDE_HOME / "rapports"
SECTION_GRADE_PTS = 1.5
SECTION_MIN_M = 200.0
STEP_GRADE_PTS = 3.0
STEP_BEFORE_S = 10
STEP_NEW_LEVEL_S = (30, 60)
STEP_MIN_W = 20.0
STEP_SHARE = 0.63
ERG_BAND = 0.05
SECTION_COLUMNS = ("index", "start_m", "length_m", "grade_pct", "grade_sent_pct", "gear", "power_w",
                   "cadence_rpm", "speed_kmh", "hr_bpm")
PERF_LINE = re.compile(r"\[perf-rendu\] images/s moy ([0-9.]+) ; temps d'image p50 ([0-9.]+) / p99 ([0-9.]+) "
                       r"/ max ([0-9.]+) ms")


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def _med(values: list[float]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(median(vals), 1) if vals else None


def _p90(values: list[float]) -> float | None:
    vals = sorted(values)
    return round(vals[min(int(len(vals) * 0.9), len(vals) - 1)], 1) if vals else None


# --- lecture ----------------------------------------------------------------------------------------

def load(path: Path) -> dict[str, Any]:
    """Relevés hors pauses (pente complétée par l'altitude si besoin), lignes `device`, `segment`, `powerup`."""
    session = load_session(path)
    recs = sorted(running_records(session.records, session.events), key=lambda r: r["ts"])
    _fill_grade(recs)
    game: dict[str, list[dict]] = {"segment": [], "powerup": []}
    if Path(path).suffix.lower() == ".jsonl":
        for line in read_journal(Path(path)):
            if isinstance(line, dict) and line.get("kind") in game:
                game[line["kind"]].append(line)
    return {"records": recs, "devices": _device_drops(session), "segments": game["segment"],
            "powerups": game["powerup"], "format": session.fmt}


def _fill_grade(recs: list[dict]) -> None:
    """Pente tirée de l'altitude sur 50 m quand le relevé n'a pas de `grade` (FIT)."""
    if all(_num(r.get("grade")) is not None for r in recs):
        return
    j = 0
    for r in recs:
        if _num(r.get("grade")) is not None:
            continue
        d, a = _num(r.get("distance")), _num(r.get("alt"))
        while j < len(recs) and (_num(recs[j].get("distance")) or 0.0) < (d or 0.0) - 50.0:
            j += 1
        base = recs[j]
        bd, ba = _num(base.get("distance")), _num(base.get("alt"))
        r["grade"] = round((a - ba) / (d - bd) * 100.0, 2) if None not in (d, a, bd, ba) and d - bd > 5.0 else 0.0


# --- calculs ----------------------------------------------------------------------------------------

def _grade(r: dict) -> float:
    return _num(r.get("grade")) or 0.0


def _span(grp: list[dict]) -> float:
    return (_num(grp[-1].get("distance")) or 0.0) - (_num(grp[0].get("distance")) or 0.0)


def _mean_grade(grp: list[dict]) -> float:
    return sum(_grade(r) for r in grp) / len(grp)


def grade_groups(recs: list[dict]) -> list[list[dict]]:
    """Relevés groupés par pente homogène : coupure dès que la pente s'écarte de plus de 1,5 point de la
    moyenne du groupe ; puis un groupe de moins de 200 m rejoint le voisin de pente la plus proche, et deux
    voisins à moins de 1,5 point l'un de l'autre se rejoignent."""
    groups: list[list[dict]] = []
    total = 0.0                                  # somme des pentes du dernier groupe
    for r in recs:
        g = _grade(r)
        if groups and abs(g - total / len(groups[-1])) <= SECTION_GRADE_PTS:
            groups[-1].append(r)
            total += g
        else:
            groups.append([r])
            total = g
    while len(groups) > 1:
        short = min(range(len(groups)), key=lambda k: _span(groups[k]))
        if _span(groups[short]) < SECTION_MIN_M:
            g = _mean_grade(groups[short])
            nbrs = [k for k in (short - 1, short + 1) if 0 <= k < len(groups)]
            k = min(nbrs, key=lambda n: abs(_mean_grade(groups[n]) - g))
            lo, hi = min(k, short), max(k, short)
            groups[lo:hi + 1] = [groups[lo] + groups[hi]]
            continue
        close = next((k for k in range(len(groups) - 1)
                      if abs(_mean_grade(groups[k]) - _mean_grade(groups[k + 1])) <= SECTION_GRADE_PTS), None)
        if close is None:
            break
        groups[close:close + 2] = [groups[close] + groups[close + 1]]
    return groups


def sections(recs: list[dict]) -> list[dict[str, Any]]:
    groups = grade_groups(recs)
    out = []
    for k, grp in enumerate(groups, start=1):
        start = _num(grp[0].get("distance")) or 0.0
        end = _num(grp[-1].get("distance")) or start
        gears = Counter(r.get("gear") for r in grp if r.get("gear") is not None)
        out.append({
            "index": k, "start_m": round(start, 1), "length_m": round(end - start, 1),
            "grade_pct": round(sum(_num(r.get("grade")) or 0.0 for r in grp) / len(grp), 1),
            "grade_sent_pct": _med([_num(r.get("grade_sent")) for r in grp]),
            "gear": gears.most_common(1)[0][0] if gears else None,
            "power_w": _med([_num(r.get("power")) for r in grp]),
            "cadence_rpm": _med([_num(r.get("cadence")) for r in grp]),
            "speed_kmh": _med([(_num(r.get("speed")) or 0.0) * 3.6 for r in grp]),
            "hr_bpm": _med([_num(r.get("hr")) for r in grp if (_num(r.get("hr")) or 0) > 0]),
        })
    return out


def grade_steps(recs: list[dict]) -> list[dict[str, Any]]:
    """Marches de pente de plus de 3 points et temps pour que la puissance fasse 63 % du chemin."""
    grades = [_num(r.get("grade")) or 0.0 for r in recs]
    powers = [_num(r.get("power")) or 0.0 for r in recs]
    cads = [_num(r.get("cadence")) for r in recs]
    smooth = [sum(powers[max(i - 1, 0):i + 2]) / len(powers[max(i - 1, 0):i + 2]) for i in range(len(powers))]
    lo, hi = STEP_NEW_LEVEL_S
    out: list[dict[str, Any]] = []
    i = STEP_BEFORE_S
    while i + hi <= len(recs):
        before, after = median(grades[i - STEP_BEFORE_S:i]), median(grades[i:i + STEP_BEFORE_S])
        if abs(after - before) <= STEP_GRADE_PTS or abs(grades[i] - grades[i - 1]) < 0.5:
            i += 1
            continue
        old, new = median(powers[i - STEP_BEFORE_S:i]), median(powers[i + lo:i + hi])
        held = all(c is None or c > 0 for c in cads[i:i + hi])
        lag = None
        if held and abs(new - old) >= STEP_MIN_W:
            for k in range(i, i + hi):
                if (smooth[k] - old) / (new - old) >= STEP_SHARE:
                    lag = float(k - i)
                    break
        out.append({"distance_m": round(_num(recs[i].get("distance")) or 0.0, 1), "t_s": round(recs[i]["ts"] - recs[0]["ts"], 1),
                    "grade_from_pct": round(before, 1), "grade_to_pct": round(after, 1),
                    "power_from_w": round(old, 1), "power_to_w": round(new, 1), "lag_s": lag,
                    "note": "" if lag is not None else ("cadence nulle" if not held else "palier de puissance inchangé")})
        i += hi
    return out


def erg_blocks(recs: list[dict]) -> list[dict[str, Any]]:
    blocks: dict[int, list[tuple[float, float]]] = {}
    for r in recs:
        p, tgt, b = _num(r.get("power")), _num(r.get("target_w")), r.get("block")
        if p is not None and tgt and b is not None:
            blocks.setdefault(int(b), []).append((p, tgt))
    out = []
    for b, pairs in sorted(blocks.items()):
        dev = [abs(p - t) for p, t in pairs]
        out.append({"block": b, "seconds": len(pairs), "target_w": _med([t for _, t in pairs]),
                    "delta_median_w": _med(dev), "delta_p90_w": _p90(dev),
                    "outside_5pct_s": sum(1 for p, t in pairs if abs(p - t) > ERG_BAND * t)})
    return out


def engine_perf(text: str) -> dict[str, Any] | None:
    rows = [tuple(float(x) for x in m.groups()) for m in PERF_LINE.finditer(text)]
    if not rows:
        return None
    fps = [r[0] for r in rows]
    return {"count": len(rows), "fps_min": min(fps), "fps_median": round(median(fps), 1),
            "frame_p99_max_ms": max(r[2] for r in rows), "frame_max_ms": max(r[3] for r in rows)}


def trainer_log(text: str) -> dict[str, Any]:
    from .log_report import analyse

    rep = analyse(text.splitlines())
    return {"trainer_disconnections": rep.trainer.disconnections, "trainer_lost_s": round(rep.trainer.lost_duration_s, 1),
            "click_disconnections": rep.click.disconnections, "click_presses": dict(rep.click.presses),
            "pauses": len(rep.pauses), "errors": len(rep.errors)}


def build(path: Path, log_text: str | None = None, engine_text: str | None = None) -> dict[str, Any]:
    data = load(path)
    recs = data["records"]
    return {
        "source": Path(path).name, "format": data["format"], "records": len(recs),
        "distance_m": round(max((_num(r.get("distance")) or 0.0) for r in recs), 1),
        "sections": sections(recs), "grade_steps": grade_steps(recs), "erg": erg_blocks(recs),
        "devices": data["devices"],
        "segments": [{k: s.get(k) for k in ("segment_id", "lap", "type", "category", "time_s", "pr", "bonuses")}
                     for s in data["segments"]],
        "powerups": [{k: p.get(k) for k in ("powerup", "t", "duration_s")} for p in data["powerups"]],
        "log": trainer_log(log_text) if log_text is not None else None,
        "engine": engine_perf(engine_text) if engine_text is not None else None,
        "_profile": [(round(_num(r.get("distance")) or 0.0, 1), _num(r.get("alt")), _num(r.get("power"))) for r in recs],
    }


# --- sorties ----------------------------------------------------------------------------------------

def _svg_profile(profile: list[tuple], secs: list[dict], width: int = 900, height: int = 220) -> str:
    """Altitude (gris) et puissance (orange) le long de la distance, sections en bandes alternées."""
    pts = [(d, a, p) for d, a, p in profile if d is not None]
    if len(pts) < 2:
        return ""
    d0, d1 = pts[0][0], pts[-1][0] or 1.0
    span = max(d1 - d0, 1.0)
    alts = [a for _, a, _ in pts if a is not None]
    pows = [p for _, _, p in pts if p is not None]

    def xs(d):
        return 40 + (d - d0) / span * (width - 50)

    def line(vals, lo, hi, color):
        if not vals or hi <= lo:
            return ""
        coords = " ".join(f"{xs(d):.1f},{height - 20 - (v - lo) / (hi - lo) * (height - 40):.1f}"
                          for d, v in vals if v is not None)
        return f'<polyline fill="none" stroke="{color}" stroke-width="1.5" points="{coords}"/>'

    bands = "".join(f'<rect x="{xs(s["start_m"]):.1f}" y="10" width="{max(xs(s["start_m"] + s["length_m"]) - xs(s["start_m"]), 0.5):.1f}" '
                    f'height="{height - 30}" fill="{"#eef" if s["index"] % 2 else "#fff"}"/>' for s in secs)
    return (f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="profil et puissance">{bands}'
            + line([(d, a) for d, a, _ in pts], min(alts or [0]), max(alts or [1]), "#777")
            + line([(d, p) for d, _, p in pts], 0.0, max(pows or [1]), "#d9822b")
            + f'<text x="40" y="{height - 4}" font-size="11">{d0 / 1000:.1f} km</text>'
            + f'<text x="{width - 60}" y="{height - 4}" font-size="11">{d1 / 1000:.1f} km</text></svg>')


def _table(rows: list[dict], cols: tuple[str, ...]) -> str:
    if not rows:
        return "<p>—</p>"
    head = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
    body = "".join("<tr>" + "".join(f"<td>{html.escape('—' if r.get(c) is None else str(r.get(c)))}</td>" for c in cols)
                   + "</tr>" for r in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


def write(out: dict[str, Any], folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "sections.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=SECTION_COLUMNS, delimiter=";")
        w.writeheader()
        w.writerows(out["sections"])
    public = {k: v for k, v in out.items() if not k.startswith("_")}
    (folder / "resume.json").write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding="utf-8")
    parts = [f"<h1>Séance {html.escape(out['source'])}</h1>",
             f"<p>{out['records']} relevés hors pauses, {out['distance_m'] / 1000:.2f} km.</p>",
             _svg_profile(out["_profile"], out["sections"]),
             "<h2>Sections de pente</h2>", _table(out["sections"], SECTION_COLUMNS),
             "<h2>Retard pente → effort</h2>",
             _table(out["grade_steps"], ("distance_m", "t_s", "grade_from_pct", "grade_to_pct", "power_from_w",
                                         "power_to_w", "lag_s", "note")),
             "<h2>ERG</h2>", _table(out["erg"], ("block", "seconds", "target_w", "delta_median_w", "delta_p90_w",
                                                 "outside_5pct_s")),
             "<h2>Coupures</h2>", _table([{"appareil": k, **v} for k, v in out["devices"].items()], ("appareil", "drops", "down_s")),
             "<h2>Segments et bonus</h2>", _table(out["segments"], ("segment_id", "lap", "type", "category", "time_s", "pr")),
             _table(out["powerups"], ("powerup", "t", "duration_s"))]
    if out["log"]:
        parts += ["<h2>Journal du core</h2>", f"<pre>{html.escape(json.dumps(out['log'], ensure_ascii=False, indent=2))}</pre>"]
    if out["engine"]:
        parts += ["<h2>Images par seconde</h2>", _table([out["engine"]], tuple(out["engine"]))]
    page = ("<!doctype html><html lang=\"fr\"><meta charset=\"utf-8\"><title>Rapport de séance</title>"
            "<style>body{font-family:sans-serif;margin:16px;max-width:1000px}table{border-collapse:collapse;margin:8px 0}"
            "td,th{border:1px solid #ccc;padding:2px 6px;text-align:right}th{background:#f4f4f4}</style>"
            + "".join(parts) + "</html>")
    (folder / "rapport.html").write_text(page, encoding="utf-8")
    return folder / "rapport.html"


def format_text(out: dict[str, Any]) -> str:
    lines = [f"Séance {out['source']} : {out['records']} relevés, {out['distance_m'] / 1000:.2f} km, "
             f"{len(out['sections'])} section(s) de pente"]
    for s in out["sections"]:
        lines.append(f"  {s['index']:>2}. {s['start_m'] / 1000:6.2f} km +{s['length_m']:5.0f} m  pente {s['grade_pct']:+5.1f} %"
                     f"  envoyée {s['grade_sent_pct'] if s['grade_sent_pct'] is not None else '—'}  braquet {s['gear'] or '—'}"
                     f"  {s['power_w'] or '—'} W  {s['cadence_rpm'] or '—'} rpm  {s['speed_kmh'] or '—'} km/h")
    for st in out["grade_steps"]:
        lag = f"{st['lag_s']:.0f} s" if st["lag_s"] is not None else st["note"]
        lines.append(f"  marche {st['grade_from_pct']:+.1f} → {st['grade_to_pct']:+.1f} % à {st['distance_m'] / 1000:.2f} km :"
                     f" {st['power_from_w']:.0f} → {st['power_to_w']:.0f} W, retard {lag}")
    for b in out["erg"]:
        lines.append(f"  ERG bloc {b['block']} : écart médian {b['delta_median_w']} W, p90 {b['delta_p90_w']} W, "
                     f"{b['outside_5pct_s']} s hors ± 5 %")
    return "\n".join(lines) + "\n"


def run(path: Path | None, log: Path | None = None, engine_log: Path | None = None, out_dir: Path | None = None,
        as_json: bool = False) -> int:
    from ..journal import latest_journal

    if path is None:
        path = latest_journal()
        if path is None:
            print("Aucun journal trouvé.", file=sys.stderr)
            return 1
    try:
        out = build(Path(path), log.read_text(errors="replace") if log else None,
                    engine_log.read_text(errors="replace") if engine_log else None)
    except (SummaryError, OSError) as exc:
        print(f"openride-core session-report : {exc}", file=sys.stderr)
        return 1
    page = write(out, out_dir or REPORTS_DIR / Path(path).stem)
    if as_json:
        print(json.dumps({k: v for k, v in out.items() if not k.startswith("_")}, ensure_ascii=False, indent=2))
    else:
        print(format_text(out) + f"Rapport : {page}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m openride_core.tools.session_report",
                                description="Analyse automatique d'une séance (lot X12).")
    p.add_argument("file", nargs="?", type=Path, help="journal .jsonl ou .fit (défaut : dernier journal)")
    p.add_argument("--log", type=Path, help="journal du core (run_trainer.log)")
    p.add_argument("--engine-log", type=Path, help="journal de l'engine (lignes [perf-rendu])")
    p.add_argument("--out", type=Path, help="dossier du rapport (défaut : ~/OpenRide/rapports/<séance>)")
    p.add_argument("--json", action="store_true", help="sortie JSON")
    a = p.parse_args(argv)
    return run(a.file, a.log, a.engine_log, a.out, a.json)


if __name__ == "__main__":
    sys.exit(main())
