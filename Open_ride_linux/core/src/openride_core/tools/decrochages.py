"""Décrochages de la résistance et pompage (lot X44, après la séance du 29 octobre).

Une chute brutale de la puissance pendant un effort peut venir du trainer (le frein lâche) ou du
cycliste : fatigue (la cadence baisse d'abord), ou relâchement (il tourne les jambes sans appuyer : la
cadence ne bouge pas, la puissance si). Une cadence inchangée ne suffit donc pas à accuser le trainer
(essais du 30 octobre : deux relâchements classés « trainer »). Le diagnostic se lit image par image,
puissance, cadence et vitesse du volant ensemble, avec l'effort demandé (pente envoyée, durée d'un effort
dur) et ce que le trainer annonce au même moment (Fitness Machine Status 0x01, 0x02, 0x03, 0x14, 0xFF,
lignes `ftms` du journal écrites depuis la PR #580), plus le repère du cycliste (Z long, lot X47).

- `detect_drops` : chutes de plus de `DROP_FRAC` (60 %) en moins de `DROP_WINDOW_S` (3 s) depuis au
  moins `DROP_MIN_W` (150 W) ;
- `classify`, dans cet ordre :
  1. `arret` : cadence sous `CADENCE_STOP_RPM` au bout de la chute ;
  2. `fatigue` : cadence tombée d'au moins `CADENCE_FALL_RPM` avant que la puissance passe sous la moitié
     de son niveau ;
  3. cadence pas restée à ± `CADENCE_SAME_RPM` de son niveau d'avant : `indetermine` ;
  4. `trainer`, seulement sur une preuve : repère du cycliste à ± `MERGE_S` s, statut du trainer qui
     arrête ou réinitialise (`TRAINER_STATUSES`) à ± `STATUS_AROUND_S` s, frein revenu au plus
     `RETAKE_PROOF_S` s après la reprise du contrôle par le pilote (« frein lâché » puis « puissance
     revenue », PR #580 : un cycliste qui relâche ne repart pas au moment précis où le pilote reprend la
     main), ou volant qui s'emballe de `SPEED_RISE_PCT` % ou plus (plus rien ne freine) ;
  5. `fatigue` : effort dur juste avant (au-dessus de `HARD_W` depuis `HARD_S` s ou plus) ;
  6. `relachement` : effort facile (moins de `EASY_W` W, pente envoyée à ± `EASY_GRADE_PCT` %) : le cycliste
     tourne les jambes sans appuyer, ce qui est normal sur le plat ;
  7. sinon `indetermine`. Un volant qui s'effondre ne tranche pas : le frein peut l'arrêter dès que le
     cycliste n'appuie plus, comme un frein qui fait n'importe quoi. Dans le doute, jamais « trainer ».
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
import re
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
SPEED_RISE_PCT = 5.0       # trainer : volant qui s'emballe de 5 % (plus de frein)
RETAKE_PROOF_S = 3.0       # trainer : puissance revenue au plus 3 s après la reprise du contrôle (pilote, #580) …
RETAKE_AFTER_S = 15.0      # … lue jusqu'à 15 s après le début de la chute
SPEED_AFTER_S = 5.0        # vitesse d'après : médiane des 5 s qui suivent la fin de la chute
HARD_W = 450.0             # fatigue probable : plus de 450 W …
HARD_S = 8.0               # … tenus 8 s ou plus juste avant la chute
EASY_W = 250.0             # relâchement : effort de moins de 250 W …
EASY_GRADE_PCT = 1.0       # … sur une pente envoyée à ± 1 % (sur le plat, rien n'oblige à appuyer)
# Fitness Machine Status qui disent que le trainer s'arrête ou repart de zéro (pas les échos de consigne).
TRAINER_STATUSES = ("RESET", "STOPPED_OR_PAUSED_BY_USER", "STOPPED_BY_SAFETY_KEY", "SPIN_DOWN_STATUS",
                    "CONTROL_PERMISSION_LOST")


@dataclass(frozen=True)
class Sample:
    t: float                    # s, même horloge que les statuts
    power_w: float
    cadence_rpm: float
    speed_kmh: float | None = None   # vitesse annoncée par le trainer (volant)
    grade_pct: float | None = None   # pente envoyée en SIM (None : ERG ou inconnue)


@dataclass
class Drop:
    t: float                    # début de la chute
    from_w: float
    to_w: float
    duration_s: float
    cadence_before: float | None
    cadence_during: float | None
    cadence_fall_lead_s: float | None   # avance de la baisse de cadence sur la mi-chute (s, > 0 : avant)
    kind: str = "indetermine"           # trainer, fatigue, relachement, arret, indetermine
    speed_change_pct: float | None = None   # vitesse du volant après la chute / avant (%)
    grade_pct: float | None = None      # pente envoyée au début de la chute
    hard_s: float = 0.0                 # durée de l'effort au-dessus de HARD_W juste avant la chute
    reason: str = ""                    # ce qui a décidé le diagnostic
    statuses: list[str] = field(default_factory=list)
    marked: bool = False                # repère « décrochage » du cycliste à ± 10 s (lot X47)
    back_after_s: float | None = None   # frein lâché vu par le pilote, puissance revenue après la reprise (s)
    stopped: bool = False               # cadence sous 20 tr/min au bout de la chute


@dataclass
class Pumping:
    t0: float
    t1: float
    mean_w: float | None
    amplitude_pct: float | None
    period_s: float | None
    zero_drops: int


KIND_TEXT = {"trainer": "trainer", "fatigue": "fatigue", "relachement": "relâchement du cycliste",
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
    v0 = _median([x.speed_kmh for x in _between(samples, t0 - BEFORE_S, t0 + 0.001) if x.speed_kmh is not None])
    v1 = _median([x.speed_kmh for x in _between(samples, end.t, end.t + SPEED_AFTER_S) if x.speed_kmh is not None])
    if v0 and v1 is not None:
        drop.speed_change_pct = round(100.0 * (v1 - v0) / v0, 1)
    start = next((x for x in reversed(samples) if x.t <= t0), None)
    drop.grade_pct = start.grade_pct if start is not None else None
    hard_from = t0
    for x in reversed([x for x in samples if x.t <= t0]):
        if x.power_w < HARD_W:
            break
        hard_from = x.t
    drop.hard_s = round(t0 - hard_from, 2)
    drop.kind, drop.reason = classify(drop)
    return drop


def classify(d: Drop) -> tuple[str, str]:
    """Diagnostic d'une chute et sa raison (ordre du docstring du module) : « trainer » seulement sur preuve."""
    if d.stopped:
        return "arret", "cadence à l'arrêt"
    if d.cadence_fall_lead_s is not None and d.cadence_fall_lead_s >= 0:
        return "fatigue", "cadence tombée d'abord"
    if d.cadence_before is None or d.cadence_during is None \
            or abs(d.cadence_during - d.cadence_before) > CADENCE_SAME_RPM:
        return "indetermine", "cadence ni stable ni tombée d'abord"
    if d.marked:
        return "trainer", "repère du cycliste"
    status = next((st for st in d.statuses if any(name in st for name in TRAINER_STATUSES)), None)
    if status:
        return "trainer", f"statut du trainer ({status})"
    if d.back_after_s is not None and d.back_after_s <= RETAKE_PROOF_S:
        return "trainer", f"frein revenu {d.back_after_s:g} s après la reprise du contrôle"
    if d.speed_change_pct is not None and d.speed_change_pct >= SPEED_RISE_PCT:
        return "trainer", f"volant qui s'emballe ({d.speed_change_pct:+g} %)"
    if d.hard_s >= HARD_S:
        return "fatigue", f"plus de {HARD_W:g} W depuis {d.hard_s:g} s"
    if d.from_w < EASY_W and d.grade_pct is not None and abs(d.grade_pct) <= EASY_GRADE_PCT:
        return "relachement", f"{d.from_w:g} W sur une pente de {d.grade_pct:g} % : rien n'oblige à appuyer"
    return "indetermine", "cadence gardée, sans preuve : repère Z long, statut du trainer ou volant qui s'emballe"


def attach(drops: list[Drop], statuses: list[tuple[float, str]], marks: list[float]) -> list[Drop]:
    """Statuts du trainer à ± 5 s et repères du cycliste à ± 10 s de chaque chute."""
    for d in drops:
        d.statuses = [f"{t - d.t:+.1f} s {txt}" for t, txt in statuses if abs(t - d.t) <= STATUS_AROUND_S]
        d.marked = any(abs(t - d.t) <= MERGE_S for t in marks)
        seen = [(t, txt) for t, txt in statuses if d.t - STATUS_AROUND_S <= t <= d.t + RETAKE_AFTER_S]
        d.back_after_s = None
        if any(txt.startswith(BRAKE_LOSS_TEXT) for _, txt in seen):
            back = next((m for _, txt in seen if (m := BACK_RE.match(txt))), None)
            d.back_after_s = float(back.group(1)) if back else None
        d.kind, d.reason = classify(d)   # statuts et repère comptent comme preuves
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


BRAKE_LOSS_TEXT = "frein lâché"
BACK_RE = re.compile(r"puissance revenue \(.* après ([0-9.]+) s\)")


def status_text(line: dict) -> str:
    """Texte d'une ligne `ftms` du journal (PR #580)."""
    ev = line.get("event")
    if ev == "status":
        return f"statut {line.get('name') or line.get('code')} [{line.get('data', '')}]"
    if ev == "training_status":
        return f"Training Status [{line.get('data', '')}]"
    if ev == "brake_loss":
        return f"{BRAKE_LOSS_TEXT} ({line.get('from_w')} → {line.get('to_w')} W, {line.get('cadence_rpm')} tr/min)"
    if ev == "power_back":
        return f"puissance revenue ({line.get('power_w')} W après {line.get('after_s')} s)"
    if ev == "power_not_back":
        return f"puissance pas revenue après {line.get('after_s')} s"
    if ev == "momentum_brake":
        return (f"frein d'élan +{line.get('boost_pct')} % ({line.get('from_w')} → {line.get('to_w')} W, "
                f"{line.get('cadence_rpm')} tr/min)")
    if ev == "momentum_end":
        return f"frein d'élan relâché après {line.get('after_s')} s ({line.get('why')})"
    return str(ev)


def read_journal(path: Path) -> Source:
    from ..journal import read_journal as lines_of

    samples, statuses, marks = [], [], []
    for ln in lines_of(path):
        kind = ln.get("kind")
        if kind == "record" and ln.get("ts") is not None and ln.get("power") is not None:
            speed = ln.get("speed")
            grade = ln.get("grade_sent") if ln.get("mode", "SIM") == "SIM" else None
            samples.append(Sample(float(ln["ts"]), float(ln["power"]), float(ln.get("cadence") or 0.0),
                                  None if speed is None else 3.6 * float(speed), None if grade is None else float(grade)))
        elif kind == "ftms" and ln.get("ts") is not None:
            statuses.append((float(ln["ts"]), status_text(ln)))
        elif kind == "event" and ln.get("event") == "decrochage" and ln.get("ts") is not None:
            marks.append(float(ln["ts"]))
    t0 = samples[0].t if samples else 0.0
    shift = lambda t: t - t0   # noqa: E731  temps depuis le premier relevé
    return Source(path.name, [Sample(shift(s.t), s.power_w, s.cadence_rpm, s.speed_kmh, s.grade_pct) for s in samples],
                  [(shift(t), txt) for t, txt in statuses], [shift(t) for t in marks],
                  [(0.0, shift(samples[-1].t) if samples else 0.0, "séance")])


def read_bench(folder: Path) -> Source:
    with (folder / "samples.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    steps = json.loads((folder / "protocol.json").read_text(encoding="utf-8")) if (folder / "protocol.json").is_file() else []
    grades = [(float(st["t_s"]), step_grade(st.get("mode"), st.get("value"), st.get("grade_pct"))) for st in steps]
    samples = [Sample(float(r["t_s"]), float(r["power_w"]), float(r["cadence_rpm"]),
                      float(r["speed_kmh"]) if r.get("speed_kmh") else None, grade_at(grades, float(r["t_s"])))
               for r in rows]
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
    end = samples[-1].t if samples else 0.0
    segments = [(float(st["t_s"]), float(steps[k + 1]["t_s"]) if k + 1 < len(steps) else end, f"palier {k + 1}")
                for k, st in enumerate(steps)]
    return Source(folder.name, samples, statuses, marks, segments)


def step_grade(mode: str | None, value: Any, grade_pct: Any) -> float | None:
    """Pente envoyée par un palier du banc : `sim` (pente), `sim_w` (pente calculée), None en ERG."""
    if mode == "sim":
        return float(value)
    if mode == "sim_w" and grade_pct is not None:
        return float(grade_pct)
    return None


def grade_at(grades: list[tuple[float, float | None]], t: float) -> float | None:
    """Pente du palier en cours à l'instant `t` (paliers triés par début)."""
    current = None
    for t0, g in grades:
        if t0 > t:
            break
        current = g
    return current


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
                     f" tr/min, volant {_f(d.speed_change_pct, ' %')} : {KIND_TEXT[d.kind]} ({d.reason})"
                     + (" ; repère du cycliste" if d.marked else ""))
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
        f"<td>{_f(d.cadence_fall_lead_s)}</td><td>{_f(d.speed_change_pct)}</td><td>{_f(d.grade_pct)}</td>"
        f"<td class=\"{d.kind}\">{html.escape(KIND_TEXT[d.kind])} ({html.escape(d.reason)})</td>"
        f"<td>{'oui' if d.marked else ''}</td><td>{html.escape('; '.join(d.statuses))}</td></tr>"
        for d in drops) or "<tr><td colspan=\"10\">Aucune chute brutale de la puissance.</td></tr>"
    prow = "".join(
        f"<tr><td>{html.escape(label)}</td><td>{_f(p.mean_w)}</td><td>{_f(p.amplitude_pct)}</td>"
        f"<td>{_f(p.period_s)}</td><td>{p.zero_drops}</td></tr>" for label, p in pumps)
    return f"""<h2>Décrochages</h2>
<p>Chute de plus de {DROP_FRAC * 100:.0f} % en {DROP_WINDOW_S:g} s depuis {DROP_MIN_W:g} W ou plus. « fatigue » : cadence
tombée de {CADENCE_FALL_RPM:g} tr/min avant la mi-chute, ou plus de {HARD_W:g} W depuis {HARD_S:g} s. À cadence égale
(± {CADENCE_SAME_RPM:g} tr/min), « trainer » seulement sur preuve : repère du cycliste, statut d'arrêt du trainer, volant
qui gagne {SPEED_RISE_PCT:g} %, frein revenu au plus {RETAKE_PROOF_S:g} s après la reprise du contrôle par le pilote ; « relâchement » : moins de {EASY_W:g} W sur une pente à ± {EASY_GRADE_PCT:g} % ; sinon
« indéterminé ».</p>
<table class="drops"><tr><th>t (s)</th><th>Puissance (W)</th><th>Durée (s)</th><th>Cadence avant → pendant</th>
<th>Avance de la cadence (s)</th><th>Volant (%)</th><th>Pente (%)</th><th>Diagnostic</th><th>Repère</th><th>Trainer à ± {STATUS_AROUND_S:g} s</th></tr>{rows}</table>
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
