"""Décrochages de la résistance et pompage (lot X44, après la séance du 29 octobre).

Une chute brutale de la puissance pendant un effort peut venir du trainer (le frein lâche : la
puissance s'effondre alors que la cadence reste la même) ou du cycliste (fatigue : la cadence baisse
d'abord, la puissance suit). Le bon diagnostic se lit image par image, puissance et cadence ensemble,
avec ce que le trainer annonce au même moment (Fitness Machine Status 0x14, 0x02, 0x03, 0xFF et Training
Status, lignes `ftms` du journal écrites depuis la PR #580).

- `detect_drops` : chutes de plus de `DROP_FRAC` (60 %) en moins de `DROP_WINDOW_S` (3 s) depuis au
  moins `DROP_MIN_W` (150 W) ;
- `classify` : `arret` (cadence sous `CADENCE_STOP_RPM` au bout de la chute), `fatigue` (cadence tombée
  d'au moins `CADENCE_FALL_RPM` avant que la puissance passe sous la moitié de son niveau), `trainer`
  (cadence restée à ± `CADENCE_SAME_RPM` de son niveau d'avant pendant toute la chute), sinon
  `indetermine` ;
- `pumping` : sur une plage de temps, amplitude crête à crête de la moyenne sur 4 s (en % de la moyenne),
  période dominante (autocorrélation de cette moyenne, entre 4 et 30 s) et chutes à 0 W à cadence non
  nulle. Une moyenne sur 4 s efface les coups de pédale (2,4 par seconde à 73 tr/min), qu'un relevé à
  1 Hz prendrait pour des vagues de 4 à 6 s.

Sources acceptées : un dossier du banc `trainer_steps` (`samples.csv`, `events.csv`) ou un journal de
séance `.jsonl` (lignes `record` à 1 Hz, lignes `ftms`, repères `decrochage` du lot X47).

    python -m openride_core.tools.decrochages ~/OpenRide/trainer_steps/2026-10-29_201500
    python -m openride_core.tools.decrochages ~/OpenRide/journal/2026-10-29_20-05-12.jsonl --html rapport.html
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import statistics
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DROP_FRAC = 0.60          # chute : la puissance perd au moins 60 % …
DROP_WINDOW_S = 3.0       # … en 3 s au plus …
DROP_MIN_W = 150.0        # … depuis au moins 150 W (médiane des 3 s d'avant)
MERGE_S = 10.0            # deux chutes à moins de 10 s n'en font qu'une
BEFORE_S = 5.0            # niveau d'avant : médiane des 5 s qui précèdent la chute
CADENCE_SAME_RPM = 8.0    # trainer : cadence à ± 8 tr/min de son niveau d'avant pendant la chute
CADENCE_FALL_RPM = 10.0   # fatigue : cadence tombée de 10 tr/min avant la moitié de la chute
CADENCE_STOP_RPM = 20.0   # arrêt de pédalage
STATUS_AROUND_S = 5.0     # statuts du trainer relevés à ± 5 s de la chute
MEAN_S = 4.0              # moyenne glissante du pompage
PERIOD_MIN_S, PERIOD_MAX_S = 4.0, 30.0
PERIOD_MIN_CORR = 0.30    # autocorrélation minimale pour annoncer une période
ZERO_W = 10.0             # chute à 0 W : puissance sous 10 W …
ZERO_CADENCE_RPM = 40.0   # … cadence d'au moins 40 tr/min
GRID_S = 0.5              # pas du rééchantillonnage


@dataclass(frozen=True)
class Sample:
    t: float                    # s, même horloge que les statuts
    power_w: float
    cadence_rpm: float


@dataclass
class Drop:
    t: float                    # début de la chute
    from_w: float
    to_w: float
    duration_s: float
    cadence_before: float | None
    cadence_during: float | None
    cadence_fall_lead_s: float | None   # avance de la baisse de cadence sur la mi-chute (s, > 0 : avant)
    kind: str = "indetermine"           # trainer, fatigue, arret, indetermine
    statuses: list[str] = field(default_factory=list)
    marked: bool = False                # repère « décrochage » du cycliste à ± 10 s (lot X47)
    stopped: bool = False               # cadence sous 20 tr/min au bout de la chute


@dataclass
class Pumping:
    t0: float
    t1: float
    mean_w: float | None
    amplitude_pct: float | None
    period_s: float | None
    zero_drops: int


KIND_TEXT = {"trainer": "trainer (cadence inchangée)", "fatigue": "fatigue (cadence d'abord)",
             "arret": "arrêt de pédalage", "indetermine": "indéterminé"}


# --- analyse -------------------------------------------------------------------------------

def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _between(samples: list[Sample], t0: float, t1: float) -> list[Sample]:
    return [s for s in samples if t0 <= s.t < t1]


def detect_drops(samples: list[Sample]) -> list[Drop]:
    """Chutes brutales de la puissance (fonction pure)."""
    drops: list[Drop] = []
    for i in range(1, len(samples)):
        s, prev = samples[i], samples[i - 1]
        if drops and s.t - drops[-1].t < MERGE_S:
            continue
        before = _median([x.power_w for x in _between(samples, prev.t - DROP_WINDOW_S, prev.t + 0.001)])
        # La chute commence au dernier relevé encore à son niveau (moins de 10 % de perte).
        if before is None or before < DROP_MIN_W or s.power_w >= 0.9 * before or prev.power_w < 0.9 * before:
            continue
        end = next((x for x in samples[i:] if x.t - prev.t <= DROP_WINDOW_S and x.power_w <= (1 - DROP_FRAC) * before),
                   None)
        if end is None:
            continue
        drops.append(_describe(samples, prev.t, before, end))
    return drops


def _describe(samples: list[Sample], t0: float, before_w: float, end: Sample) -> Drop:
    cad_before = _median([x.cadence_rpm for x in _between(samples, t0 - BEFORE_S, t0)])
    during = _between(samples, t0, end.t + 0.001)
    cad_during = min((x.cadence_rpm for x in during), default=None)   # la plus basse pendant la chute
    half = next((x.t for x in during if x.power_w <= before_w / 2), end.t)
    fall = None
    if cad_before is not None:
        fall = next((x.t for x in _between(samples, t0 - BEFORE_S, end.t + 0.001)
                     if x.cadence_rpm <= cad_before - CADENCE_FALL_RPM), None)
    drop = Drop(round(t0, 2), round(before_w, 1), round(end.power_w, 1), round(end.t - t0, 2),
                cad_before, cad_during, None if fall is None else round(half - fall, 2))
    drop.stopped = end.cadence_rpm < CADENCE_STOP_RPM
    drop.kind = classify(drop)
    return drop


def classify(d: Drop) -> str:
    if d.stopped:
        return "arret"
    if d.cadence_fall_lead_s is not None and d.cadence_fall_lead_s >= 0:
        return "fatigue"
    if d.cadence_before is not None and d.cadence_during is not None \
            and abs(d.cadence_during - d.cadence_before) <= CADENCE_SAME_RPM:
        return "trainer"
    return "indetermine"


def attach(drops: list[Drop], statuses: list[tuple[float, str]], marks: list[float]) -> list[Drop]:
    """Statuts du trainer à ± 5 s et repères du cycliste à ± 10 s de chaque chute."""
    for d in drops:
        d.statuses = [f"{t - d.t:+.1f} s {txt}" for t, txt in statuses if abs(t - d.t) <= STATUS_AROUND_S]
        d.marked = any(abs(t - d.t) <= MERGE_S for t in marks)
    return drops


def _grid_means(samples: list[Sample], t0: float, t1: float) -> list[float]:
    """Moyenne glissante sur 4 s, au pas de 0,5 s (échantillons irréguliers)."""
    out = []
    t = t0 + MEAN_S
    while t <= t1:
        win = [x.power_w for x in _between(samples, t - MEAN_S, t)]
        if win:
            out.append(statistics.fmean(win))
        t += GRID_S
    return out


def _period(series: list[float]) -> float | None:
    n = len(series)
    lo, hi = int(PERIOD_MIN_S / GRID_S), int(PERIOD_MAX_S / GRID_S)
    if n < 2 * lo:
        return None
    m = statistics.fmean(series)
    dev = [v - m for v in series]
    var = sum(v * v for v in dev)
    if var <= 1e-9:
        return None
    corr = {lag: sum(dev[k] * dev[k + lag] for k in range(n - lag)) / var * n / (n - lag)
            for lag in range(lo - 1, min(hi, n // 2) + 2)}
    # Premier maximum local au-dessus du seuil : la période, pas un de ses multiples.
    for lag in range(lo, min(hi, n // 2) + 1):
        if corr[lag] > PERIOD_MIN_CORR and corr[lag] >= corr[lag - 1] and corr[lag] >= corr.get(lag + 1, -1.0):
            return lag * GRID_S
    return None


def pumping(samples: list[Sample], t0: float, t1: float) -> Pumping:
    seg = _between(samples, t0, t1)
    means = _grid_means(samples, t0, t1)
    mean_w = statistics.fmean([s.power_w for s in seg]) if seg else None
    amp = None
    if means and mean_w:
        ordered = sorted(means)
        lo, hi = ordered[int(0.05 * (len(ordered) - 1))], ordered[int(0.95 * (len(ordered) - 1))]
        amp = round((hi - lo) / mean_w * 100.0, 1)
    period = _period(means)
    zeros, low = 0, False
    for s in seg:
        is_low = s.power_w < ZERO_W and s.cadence_rpm >= ZERO_CADENCE_RPM
        zeros += int(is_low and not low)
        low = is_low
    return Pumping(round(t0, 2), round(t1, 2), None if mean_w is None else round(mean_w, 1), amp, period, zeros)


# --- lecture --------------------------------------------------------------------------------

@dataclass
class Source:
    name: str
    samples: list[Sample]
    statuses: list[tuple[float, str]]
    marks: list[float]
    segments: list[tuple[float, float, str]]   # plages du pompage (paliers du banc, ou séance entière)


def status_text(line: dict) -> str:
    """Texte d'une ligne `ftms` du journal (PR #580)."""
    ev = line.get("event")
    if ev == "status":
        return f"statut {line.get('name') or line.get('code')} [{line.get('data', '')}]"
    if ev == "training_status":
        return f"Training Status [{line.get('data', '')}]"
    if ev == "brake_loss":
        return f"frein lâché ({line.get('from_w')} → {line.get('to_w')} W, {line.get('cadence_rpm')} tr/min)"
    if ev == "power_back":
        return f"puissance revenue ({line.get('power_w')} W après {line.get('after_s')} s)"
    if ev == "power_not_back":
        return f"puissance pas revenue après {line.get('after_s')} s"
    return str(ev)


def read_journal(path: Path) -> Source:
    from ..journal import read_journal as lines_of

    samples, statuses, marks = [], [], []
    for ln in lines_of(path):
        kind = ln.get("kind")
        if kind == "record" and ln.get("ts") is not None and ln.get("power") is not None:
            samples.append(Sample(float(ln["ts"]), float(ln["power"]), float(ln.get("cadence") or 0.0)))
        elif kind == "ftms" and ln.get("ts") is not None:
            statuses.append((float(ln["ts"]), status_text(ln)))
        elif kind == "event" and ln.get("event") == "decrochage" and ln.get("ts") is not None:
            marks.append(float(ln["ts"]))
    t0 = samples[0].t if samples else 0.0
    shift = lambda t: t - t0   # noqa: E731  temps depuis le premier relevé
    return Source(path.name, [Sample(shift(s.t), s.power_w, s.cadence_rpm) for s in samples],
                  [(shift(t), txt) for t, txt in statuses], [shift(t) for t in marks],
                  [(0.0, shift(samples[-1].t) if samples else 0.0, "séance")])


def read_bench(folder: Path) -> Source:
    with (folder / "samples.csv").open(encoding="utf-8") as fh:
        samples = [Sample(float(r["t_s"]), float(r["power_w"]), float(r["cadence_rpm"])) for r in csv.DictReader(fh)]
    statuses: list[tuple[float, str]] = []
    marks: list[float] = []
    events = folder / "events.csv"
    if events.is_file():
        with events.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r["type"] == "ftms":
                    statuses.append((float(r["t_s"]), r["detail"]))
                elif r["type"] == "decrochage":
                    marks.append(float(r["t_s"]))
    segments = []
    proto = folder / "protocol.json"
    if proto.is_file():
        steps = json.loads(proto.read_text(encoding="utf-8"))
        end = samples[-1].t if samples else 0.0
        for k, st in enumerate(steps):
            t1 = float(steps[k + 1]["t_s"]) if k + 1 < len(steps) else end
            segments.append((float(st["t_s"]), t1, f"palier {k + 1}"))
    return Source(folder.name, samples, statuses, marks, segments)


def read_source(path: Path) -> Source:
    return read_bench(path) if path.is_dir() else read_journal(path)


# --- sorties --------------------------------------------------------------------------------

def analyse(src: Source) -> tuple[list[Drop], list[tuple[str, Pumping]]]:
    drops = attach(detect_drops(src.samples), src.statuses, src.marks)
    pumps = [(label, pumping(src.samples, t0, t1)) for t0, t1, label in src.segments]
    return drops, pumps


def _f(v: Any, unit: str = "") -> str:
    return "—" if v is None else f"{v:g}{unit}"


def text_report(src: Source, drops: list[Drop], pumps: list[tuple[str, Pumping]]) -> str:
    lines = [f"Décrochages et pompage : {src.name}"]
    if not drops:
        lines.append("Aucune chute brutale de la puissance.")
    for d in drops:
        lines.append(f"  {d.t:8.1f} s  {d.from_w:g} → {d.to_w:g} W en {d.duration_s:g} s, cadence "
                     f"{_f(d.cadence_before and round(d.cadence_before))} → {_f(d.cadence_during and round(d.cadence_during))}"
                     f" tr/min : {KIND_TEXT[d.kind]}" + (" ; repère du cycliste" if d.marked else ""))
        for st in d.statuses:
            lines.append(f"             trainer {st}")
    lines.append("Pompage (moyenne sur 4 s) :")
    for label, p in pumps:
        lines.append(f"  {label:<12} moyenne {_f(p.mean_w, ' W'):>8}  amplitude {_f(p.amplitude_pct, ' %'):>8}  "
                     f"période {_f(p.period_s, ' s'):>6}  chutes à 0 W {p.zero_drops}")
    return "\n".join(lines) + "\n"


def html_section(drops: list[Drop], pumps: list[tuple[str, Pumping]]) -> str:
    """Section HTML (tableaux) pour `rapport.html` du banc ou un rapport à part."""
    rows = "".join(
        f"<tr><td>{d.t:g}</td><td>{d.from_w:g} → {d.to_w:g}</td><td>{d.duration_s:g}</td>"
        f"<td>{_f(d.cadence_before and round(d.cadence_before))} → {_f(d.cadence_during and round(d.cadence_during))}</td>"
        f"<td>{_f(d.cadence_fall_lead_s)}</td><td class=\"{d.kind}\">{html.escape(KIND_TEXT[d.kind])}</td>"
        f"<td>{'oui' if d.marked else ''}</td><td>{html.escape('; '.join(d.statuses))}</td></tr>"
        for d in drops) or "<tr><td colspan=\"8\">Aucune chute brutale de la puissance.</td></tr>"
    prow = "".join(
        f"<tr><td>{html.escape(label)}</td><td>{_f(p.mean_w)}</td><td>{_f(p.amplitude_pct)}</td>"
        f"<td>{_f(p.period_s)}</td><td>{p.zero_drops}</td></tr>" for label, p in pumps)
    return f"""<h2>Décrochages</h2>
<p>Chute de plus de {DROP_FRAC * 100:.0f} % en {DROP_WINDOW_S:g} s depuis {DROP_MIN_W:g} W ou plus. « trainer » : cadence
à ± {CADENCE_SAME_RPM:g} tr/min de son niveau d'avant ; « fatigue » : cadence tombée de {CADENCE_FALL_RPM:g} tr/min
avant la mi-chute.</p>
<table class="drops"><tr><th>t (s)</th><th>Puissance (W)</th><th>Durée (s)</th><th>Cadence avant → pendant</th>
<th>Avance de la cadence (s)</th><th>Diagnostic</th><th>Repère</th><th>Trainer à ± {STATUS_AROUND_S:g} s</th></tr>{rows}</table>
<h2>Pompage</h2>
<p>Moyenne glissante sur {MEAN_S:g} s (efface les coups de pédale) : amplitude crête à crête (5e à 95e centile) en %
de la moyenne, période dominante entre {PERIOD_MIN_S:g} et {PERIOD_MAX_S:g} s, chutes à 0 W à cadence d'au moins
{ZERO_CADENCE_RPM:g} tr/min.</p>
<table class="pump"><tr><th>Plage</th><th>Moyenne (W)</th><th>Amplitude (%)</th><th>Période (s)</th>
<th>Chutes à 0 W</th></tr>{prow}</table>
"""


def write_html(src: Source, drops: list[Drop], pumps: list[tuple[str, Pumping]], path: Path) -> Path:
    path.write_text(f"""<!doctype html><html lang="fr"><meta charset="utf-8"><title>Décrochages</title>
<style>body{{font-family:system-ui,sans-serif;margin:24px;color:#1d2421;background:#f6f7f5}}
table{{border-collapse:collapse;margin-top:8px;font-size:13px}}td,th{{border:1px solid #d9ddd9;padding:4px 8px}}
th{{background:#eef0ee}}.trainer{{color:#b3261e;font-weight:600}}.fatigue{{color:#7a5b00}}</style>
<h1>Décrochages et pompage : {html.escape(src.name)}</h1>{html_section(drops, pumps)}</html>
""", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m openride_core.tools.decrochages",
                                 description="Décrochages du trainer ou fatigue, et pompage (lot X44).")
    ap.add_argument("source", type=Path, help="dossier du banc trainer_steps ou journal de séance .jsonl")
    ap.add_argument("--html", type=Path, help="rapport HTML")
    ap.add_argument("--json", action="store_true", help="résultat en JSON")
    a = ap.parse_args(argv)
    if not a.source.exists():
        print(f"Introuvable : {a.source}", file=sys.stderr)
        return 2
    src = read_source(a.source)
    drops, pumps = analyse(src)
    if a.json:
        print(json.dumps({"drops": [asdict(d) for d in drops],
                          "pumping": [{"label": lb, **asdict(p)} for lb, p in pumps]}, ensure_ascii=False, indent=1))
    else:
        print(text_report(src, drops, pumps), end="")
    if a.html:
        print(f"Rapport : {write_html(src, drops, pumps, a.html)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
