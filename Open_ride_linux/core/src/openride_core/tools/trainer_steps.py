"""Banc de latence du trainer par paliers (lot X5, outil de l'essai R0).

Envoie au trainer une suite de paliers de pente (SIM) ou de puissance (ERG), à cadence tenue par
le cycliste, et mesure pour chaque palier :
- le délai entre la consigne et l'écriture au Control Point, puis l'accusé 0x80 ;
- le temps jusqu'à 10 %, 63 % et 90 % du changement de puissance (t10, t63, t90) ;
- le temps de stabilisation (puissance qui reste à ± 10 % du changement, au moins ± 5 W) ;
- le dépassement.

    python -m openride_core.tools.trainer_steps --mode sim               # vrai trainer
    python -m openride_core.tools.trainer_steps --mode erg --cadence 85
    python -m openride_core.tools.trainer_steps --trainer sim --mode sim --fast   # Bluetooth simulé
    python -m openride_core.tools.trainer_steps --trainer sim --response realiste --mode erg_paliers
    python -m openride_core.tools.trainer_steps --trainer sim --scenario decrochage_trainer --mode relances
    python -m openride_core.tools.trainer_steps --analyse DOSSIER        # relit samples.csv
    python -m openride_core.tools.trainer_steps --materiel               # matériel à préparer

L'essai est guidé (module `guide`) : rappel du matériel, puis à l'écran le palier en cours, un compte à
rebours, la puissance et la cadence en direct, une alerte si la cadence s'écarte de plus de 10 rpm, et un
bip à chaque palier. Le journal de l'essai (`guide.jsonl`) est écrit avec les autres fichiers.

Sortie dans `~/OpenRide/trainer_steps/<date>_<heure>/` : `samples.csv` (chaque trame Indoor
Bike Data), `events.csv` (consignes, écritures, accusés), `steps.csv` (résultats par palier) et
`rapport.html` (courbes). Le trainer est relâché à la fin (Reset, comme en séance).

Paliers à puissance cible et relances (lot X43, après la séance du 29 octobre) : un palier `sim_w` est
un palier SIM défini par la puissance visée. La pente envoyée est celle qui donne cette puissance à la
cadence demandée avec le plateau et le pignon réels (`--plateau`, `--pignon`, `--roue`) : en
entraînement direct, la vitesse du volant suit le braquet réel. Le trainer applique
F = m·g·(pente + Crr) + ½·Cw·v², avec la masse du `config.toml` local. Un plafond de puissance
(`--plafond`, moyenne sur 3 s) coupe le palier en cours et passe au suivant. Protocoles :
`paliers_puissance` (150 → 300 W, tenables) et `relances` (12 s à 470 W puis récupération, trois fois),
`relances_erg` (les mêmes en ERG). `samples.csv` garde aussi la vitesse annoncée par le trainer (volant)
et le niveau de résistance ; `steps.csv`, la cible, la pente envoyée et la vitesse théorique du volant.

Décrochages et pompage (lot X44) : le rapport dit pour chaque chute brutale de la puissance si elle vient
du trainer (cadence inchangée) ou du cycliste (cadence d'abord), avec les statuts annoncés par le trainer
(lignes `ftms` du pilote, PR #580, notées `ftms` dans `events.csv`), et mesure le pompage par palier
(module `decrochages`).

Suivi en direct (lot X45) : `--fenetre` ouvre une fenêtre de terminal à part (`suivi_direct`) qui montre
le palier, le compte à rebours, la puissance, la cadence et les alertes, et qui reste ouverte après la fin
de l'essai avec le verdict et les décrochages relevés ; utile quand le banc est lancé à distance.

Trainer simulé réaliste (lot X6) : `--response realiste` (frein à retard pur, serrage et relâchement,
volant d'inertie ; `--calibration steps.csv` d'un essai réel pour reprendre ses valeurs) ; le banc compare
alors chaque t63 mesuré à celui du modèle (retard + constante de temps), à ± 20 %. Protocoles en plus de
`sim` et `erg` : `marche_pente` (0 → 7 → 0 %), `erg_paliers` (150 → 250 → 150 W) et `rogue_fenetres`
(consignes de 1,5 s, fenêtres du mode Cyber-Rogue).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
import logging
import statistics
import struct
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import config
from ..physics import WHEEL_CIRCUMFERENCE_M, gear_speed_mps
from . import decrochages, suivi_direct
from .guide import Guide

DEFAULT_OUT = Path.home() / "OpenRide" / "trainer_steps"

# (mode, valeur, durée en s). Montée puis descente, petites et grandes marches, pour voir aussi
# le relâchement (lent sur le HomeTrainer : 10 à 15 s à l'essai du 25 octobre).
PROTOCOLS: dict[str, list[tuple[str, float, float]]] = {
    "sim": [("sim", 0.0, 60), ("sim", 4.0, 30), ("sim", 8.0, 30), ("sim", 4.0, 30), ("sim", 0.0, 30),
            ("sim", 8.0, 30), ("sim", 0.0, 40)],
    "erg": [("erg", 150.0, 60), ("erg", 250.0, 30), ("erg", 150.0, 30), ("erg", 300.0, 30),
            ("erg", 150.0, 40)],
    # Lot X6 : marches simples pour le trainer simulé réaliste, et fenêtres de 1,5 s (série R).
    "marche_pente": [("sim", 0.0, 30), ("sim", 7.0, 30), ("sim", 0.0, 40)],
    "erg_paliers": [("erg", 150.0, 30), ("erg", 250.0, 30), ("erg", 150.0, 40)],
    "rogue_fenetres": [("sim", 0.0, 20), ("sim", 6.0, 1.5), ("sim", 0.0, 1.5), ("sim", 6.0, 1.5),
                       ("sim", 0.0, 1.5), ("sim", 6.0, 1.5), ("sim", 0.0, 20)],
    # Lot X43 : paliers SIM tenables, définis par la puissance (séance du 29/10 : rester sous 250–350 W),
    # puis relances courtes de 10 à 15 s à 450–500 W, à cadence constante, pour voir si le frein lâche.
    "paliers_puissance": [("sim_w", 150.0, 60), ("sim_w", 200.0, 40), ("sim_w", 250.0, 40),
                          ("sim_w", 300.0, 40), ("sim_w", 200.0, 40), ("sim_w", 150.0, 40)],
    "relances": [("sim_w", 150.0, 60), ("sim_w", 470.0, 12), ("sim_w", 150.0, 45), ("sim_w", 470.0, 12),
                 ("sim_w", 150.0, 45), ("sim_w", 470.0, 12), ("sim_w", 150.0, 60)],
    "relances_erg": [("erg", 150.0, 60), ("erg", 470.0, 12), ("erg", 150.0, 45), ("erg", 470.0, 12),
                     ("erg", 150.0, 45), ("erg", 470.0, 12), ("erg", 150.0, 60)],
}
MODES = ("sim", "erg", "sim_w")   # sim : pente (%), erg : puissance (W), sim_w : SIM visant une puissance (W)
MODEL_TOL = 0.20        # t63 du trainer simulé réaliste : à ± 20 % du modèle (lot X6)
BASELINE_S = 5.0        # fenêtre de la valeur de départ, juste avant la consigne
FINAL_S = 5.0           # fenêtre de la valeur finale, fin du palier
SETTLE_PCT = 10.0       # stable : à ± 10 % du changement de puissance…
SETTLE_MIN_W = 5.0      # … et au moins ± 5 W (bruit des trames)
MIN_DELTA_W = 10.0      # en dessous, pas de délai mesurable
LEAD_IN_S = 10.0        # compte à rebours entre la connexion et le premier palier
CADENCE_TOL_RPM = 10.0  # alerte si la cadence s'écarte plus que ça de la cadence demandée…
CADENCE_ALERT_S = 3.0   # … pendant au moins ce temps
CEILING_WINDOW_S = 3.0  # plafond : moyenne de la puissance sur 3 s
CEILING_MARGIN = 1.25   # plafond par défaut : 125 % du plus fort palier du protocole
WHEEL_M = WHEEL_CIRCUMFERENCE_M


@dataclass(frozen=True)
class Gearing:
    """Plateau et pignon réels (dents) et circonférence de la roue (m) : vitesse du volant d'un
    trainer à entraînement direct pour une cadence donnée."""
    chainring: int
    sprocket: int
    wheel_m: float = WHEEL_M

    def speed_mps(self, cadence_rpm: float) -> float:
        return gear_speed_mps(cadence_rpm, self.chainring, self.sprocket, self.wheel_m)


def grade_for_power(target_w: float, cadence_rpm: float, gearing: Gearing, mass_kg: float, crr: float,
                    cw: float) -> float:
    """Pente (%) qui donne `target_w` au trainer à la vitesse du volant : P = v·(m·g·(s + Crr) + ½·Cw·v²),
    où Cw est la valeur envoyée au trainer (FTMS : le trainer applique lui-même le ½)."""
    v = gearing.speed_mps(cadence_rpm)
    if v <= 0.0 or mass_kg <= 0.0:
        raise ValueError("vitesse du volant ou masse nulle : pente impossible à calculer")
    return round(((target_w / v - 0.5 * cw * v * v) / (mass_kg * 9.80665) - crr) * 100.0, 2)


@dataclass
class Step:
    mode: str
    value: float
    hold_s: float
    grade_pct: float | None = None   # pente envoyée pour un palier `sim_w`


@dataclass
class Recording:
    """Ce que le banc a vu, horodaté sur la même horloge (secondes depuis le départ)."""
    # t, puissance, cadence, vitesse annoncée par le trainer (volant, km/h), niveau de résistance
    samples: list[tuple[float, float, float, float | None, float | None]] = field(default_factory=list)
    events: list[tuple[float, str, str]] = field(default_factory=list)        # t, type, détail
    steps: list[tuple[float, Step]] = field(default_factory=list)             # début, palier


@dataclass
class StepResult:
    index: int
    mode: str
    value: float
    from_value: float | None
    write_ms: float | None
    ack_ms: float | None
    baseline_w: float | None
    final_w: float | None
    delta_w: float | None
    t10_s: float | None
    t63_s: float | None
    t90_s: float | None
    settle_s: float | None
    overshoot_pct: float | None
    cadence_rpm: float | None
    note: str = ""
    grade_pct: float | None = None       # pente envoyée (palier `sim_w`)
    target_gap_w: float | None = None    # puissance finale − puissance visée (palier `sim_w` ou `erg`)
    speed_kmh: float | None = None       # vitesse annoncée par le trainer (médiane du palier)
    resistance: float | None = None      # niveau de résistance annoncé (médiane du palier)
    cut: bool = False                    # palier coupé par le plafond


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _window(samples: list[tuple], t0: float, t1: float, col: int = 1) -> list[float]:
    return [s[col] for s in samples if t0 <= s[0] < t1 and s[col] is not None]


def analyse_step(rec: Recording, i: int) -> StepResult:
    """Mesures d'un palier à partir de l'enregistrement (fonction pure, testée sans matériel)."""
    t_start, step = rec.steps[i]
    t_end = rec.steps[i + 1][0] if i + 1 < len(rec.steps) else (rec.samples[-1][0] if rec.samples else t_start)
    prev = rec.steps[i - 1][1] if i > 0 else None
    after = [e for e in rec.events if t_start <= e[0] < t_end]
    write = next((e[0] for e in after if e[1] == "write"), None)
    ack = next((e[0] for e in after if e[1] == "ack" and write is not None and e[0] >= write), None)
    seg = [s for s in rec.samples if t_start <= s[0] < t_end]
    base = _median(_window(rec.samples, t_start - BASELINE_S, t_start))
    final = _median(_window(rec.samples, t_end - FINAL_S, t_end))
    res = StepResult(i + 1, step.mode, step.value, prev.value if prev else None,
                     None if write is None else round((write - t_start) * 1000, 1),
                     None if ack is None or write is None else round((ack - write) * 1000, 1),
                     base, final, None, None, None, None, None, None,
                     _median(_window(rec.samples, t_start, t_end, col=2)))
    res.grade_pct = step.grade_pct
    res.speed_kmh = _median(_window(rec.samples, t_start, t_end, col=3))
    res.resistance = _median(_window(rec.samples, t_start, t_end, col=4))
    res.cut = any(e[1] == "ceiling" for e in after)
    if step.mode in ("erg", "sim_w") and final is not None:
        res.target_gap_w = round(final - step.value, 1)
    if res.cut:
        res.note = "coupé par le plafond"
    if prev is None:
        res.note = _join(res.note, "palier de départ")
        return res
    if base is None or final is None or not seg:
        res.note = _join(res.note, "pas assez de mesures")
        return res
    delta = final - base
    res.delta_w = round(delta, 1)
    if abs(delta) < MIN_DELTA_W:
        res.note = _join(res.note, "changement de puissance trop faible pour mesurer un délai")
        return res
    sign = 1.0 if delta > 0 else -1.0
    # Moyenne glissante sur 3 trames : une trame bruitée ne déclenche pas un seuil.
    smooth = [(seg[k][0], sum(s[1] for s in seg[max(0, k - 2):k + 1]) / len(seg[max(0, k - 2):k + 1]))
              for k in range(len(seg))]

    def crossing(frac: float) -> float | None:
        level = base + frac * delta
        for t, p in smooth:
            if sign * (p - level) >= 0:
                return round(t - t_start, 2)
        return None

    res.t10_s, res.t63_s, res.t90_s = crossing(0.10), crossing(0.63), crossing(0.90)
    tol = max(abs(delta) * SETTLE_PCT / 100.0, SETTLE_MIN_W)
    settle = None
    for t, p in reversed(smooth):
        if abs(p - final) > tol:
            break
        settle = t
    res.settle_s = None if settle is None else round(settle - t_start, 2)
    peak = max(sign * (p - final) for _, p in smooth)
    res.overshoot_pct = round(max(peak, 0.0) / abs(delta) * 100.0, 1)
    if res.t90_s is None:
        res.note = _join(res.note, "90 % jamais atteint pendant le palier")
    return res


def _join(a: str, b: str) -> str:
    return f"{a} ; {b}" if a else b


def analyse(rec: Recording) -> list[StepResult]:
    return [analyse_step(rec, i) for i in range(len(rec.steps))]


# --- fichiers ---------------------------------------------------------------------------

def save(rec: Recording, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "samples.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["t_s", "power_w", "cadence_rpm", "speed_kmh", "resistance"])
        w.writerows((f"{t:.3f}", f"{p:.1f}", f"{c:.1f}", "" if v is None else f"{v:.2f}", "" if r is None else f"{r:g}")
                    for t, p, c, v, r in rec.samples)
    with (out / "events.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["t_s", "type", "detail"])
        w.writerows((f"{t:.3f}", kind, detail) for t, kind, detail in rec.events)
    (out / "protocol.json").write_text(json.dumps(
        [{"t_s": round(t, 3), **asdict(s)} for t, s in rec.steps], ensure_ascii=False, indent=1),
        encoding="utf-8")


def load(out: Path) -> Recording:
    rec = Recording()
    with (out / "samples.csv").open(encoding="utf-8") as fh:
        # Essais d'avant le lot X43 : ni vitesse ni résistance.
        rec.samples = [(float(r["t_s"]), float(r["power_w"]), float(r["cadence_rpm"]), _opt(r.get("speed_kmh")),
                        _opt(r.get("resistance"))) for r in csv.DictReader(fh)]
    with (out / "events.csv").open(encoding="utf-8") as fh:
        rec.events = [(float(r["t_s"]), r["type"], r["detail"]) for r in csv.DictReader(fh)]
    for d in json.loads((out / "protocol.json").read_text(encoding="utf-8")):
        rec.steps.append((float(d["t_s"]), Step(d["mode"], float(d["value"]), float(d["hold_s"]),
                                                _opt(d.get("grade_pct")))))
    return rec


def _opt(v: Any) -> float | None:
    return None if v in (None, "") else float(v)


def _fmt(v: Any, unit: str = "") -> str:
    return "—" if v is None else f"{v:g}{unit}"


def write_results(results: list[StepResult], out: Path) -> str:
    with (out / "steps.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(asdict(results[0]).keys()) if results else ["index"])
        w.writeheader()
        for r in results:
            w.writerow(asdict(r))
    lines = ["palier  consigne        écriture  accusé   départ → final      t10     t63     t90  stable  dépass."
             "   écart   volant"]
    for r in results:
        unit = " %" if r.mode == "sim" else " W"
        cons = f"{_fmt(r.from_value)}→{_fmt(r.value)}{unit}" if r.from_value is not None else f"{_fmt(r.value)}{unit}"
        bf = f"{_fmt(r.baseline_w and round(r.baseline_w))} → {_fmt(r.final_w and round(r.final_w))} W"
        lines.append(f"{r.index:>6}  {cons:<14} {_fmt(r.write_ms, ' ms'):>9} {_fmt(r.ack_ms, ' ms'):>8}  "
                     f"{bf:<17} {_fmt(r.t10_s, ' s'):>7} {_fmt(r.t63_s, ' s'):>7} {_fmt(r.t90_s, ' s'):>7} "
                     f"{_fmt(r.settle_s, ' s'):>7} {_fmt(r.overshoot_pct, ' %'):>7} {_fmt(r.target_gap_w, ' W'):>7} "
                     f"{_fmt(r.speed_kmh and round(r.speed_kmh, 1), ' km/h'):>9}  {r.note}")
    text = "\n".join(lines) + "\n"
    (out / "steps.txt").write_text(text, encoding="utf-8")
    return text


def write_report(rec: Recording, results: list[StepResult], out: Path) -> Path:
    """Rapport HTML autonome : courbe de puissance, paliers et tableau."""
    width, height, pad = 960, 260, 40
    t_max = max([s[0] for s in rec.samples] + [1.0])
    p_max = max([s[1] for s in rec.samples] + [100.0]) * 1.1

    def x(t: float) -> float:
        return pad + (width - 2 * pad) * t / t_max

    def y(p: float) -> float:
        return height - pad - (height - 2 * pad) * p / p_max

    pts = " ".join(f"{x(t):.1f},{y(p):.1f}" for t, p, *_ in rec.samples)
    marks = "".join(
        f'<line x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{pad}" y2="{height - pad}" class="step"/>'
        f'<text x="{x(t) + 3:.1f}" y="{pad + 12}" class="lbl">{_step_short(s)}</text>'
        for t, s in rec.steps)
    rows = "".join(
        "<tr>" + "".join(f"<td>{_fmt(v)}</td>" for v in (
            r.index, r.from_value, r.value, r.write_ms, r.ack_ms, r.baseline_w and round(r.baseline_w),
            r.final_w and round(r.final_w), r.t10_s, r.t63_s, r.t90_s, r.settle_s, r.overshoot_pct,
            r.cadence_rpm and round(r.cadence_rpm), r.grade_pct, r.target_gap_w,
            r.speed_kmh and round(r.speed_kmh, 1), r.resistance)) + f"<td>{r.note}</td></tr>"
        for r in results)
    html = f"""<!doctype html><html lang="fr"><meta charset="utf-8"><title>Latence du trainer</title>
<style>body{{font-family:system-ui,sans-serif;margin:24px;color:#1d2421;background:#f6f7f5}}
svg{{background:#fff;border:1px solid #d9ddd9;max-width:100%}}polyline{{fill:none;stroke:#1f6f8b;stroke-width:1.5}}
.step{{stroke:#c2362b;stroke-dasharray:4 3}}.lbl{{font-size:11px;fill:#c2362b}}
table{{border-collapse:collapse;margin-top:16px;font-size:13px}}td,th{{border:1px solid #d9ddd9;padding:4px 8px;text-align:right}}
th{{background:#eef0ee}}</style>
<h1>Latence du trainer par paliers</h1>
<p>{datetime.now():%d/%m/%Y %H:%M}. Puissance de chaque trame Indoor Bike Data ; traits rouges : consignes.</p>
<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}">{marks}<polyline points="{pts}"/>
<text x="{pad}" y="{height - 10}" class="lbl" style="fill:#5d6762">0 s</text>
<text x="{width - pad - 30}" y="{height - 10}" class="lbl" style="fill:#5d6762">{t_max:.0f} s</text>
<text x="4" y="{pad}" class="lbl" style="fill:#5d6762">{p_max:.0f} W</text></svg>
<table><tr><th>Palier</th><th>De</th><th>À</th><th>Écriture (ms)</th><th>Accusé (ms)</th><th>Départ (W)</th>
<th>Final (W)</th><th>t10 (s)</th><th>t63 (s)</th><th>t90 (s)</th><th>Stable (s)</th><th>Dépassement (%)</th>
<th>Cadence</th><th>Pente envoyée (%)</th><th>Écart à la cible (W)</th><th>Volant (km/h)</th><th>Résistance</th>
<th>Note</th></tr>{rows}</table>
{decrochages.html_section(*decrochages.analyse(bench_source(rec, out.name)))}</html>
"""
    path = out / "rapport.html"
    path.write_text(html, encoding="utf-8")
    return path


def bench_source(rec: Recording, name: str) -> decrochages.Source:
    """L'essai vu par le module `decrochages` (lot X44) : relevés, statuts du trainer, paliers."""
    end = rec.samples[-1][0] if rec.samples else 0.0
    segments = [(t, rec.steps[k + 1][0] if k + 1 < len(rec.steps) else end, f"palier {k + 1}")
                for k, (t, _) in enumerate(rec.steps)]
    return decrochages.Source(name, [decrochages.Sample(t, p, c) for t, p, c, *_ in rec.samples],
                              [(t, d) for t, kind, d in rec.events if kind == "ftms"],
                              [t for t, kind, _ in rec.events if kind == "decrochage"], segments)


# --- banc -------------------------------------------------------------------------------

class _CpLogTap(logging.Handler):
    """Relève les lignes « FTMS > » et « FTMS < réponse » du journal FTMS (lot Q3)."""

    def __init__(self, rec: Recording, clock) -> None:
        super().__init__(logging.INFO)
        self.rec, self.clock = rec, clock

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        if msg.startswith("FTMS > "):
            self.rec.events.append((self.clock(), "write", msg[7:]))
        elif msg.startswith("FTMS < réponse"):
            self.rec.events.append((self.clock(), "ack", msg[7:]))
        elif msg.startswith("FTMS < sans réponse"):
            self.rec.events.append((self.clock(), "no_ack", msg[7:]))


def step_label(step: Step) -> str:
    if step.mode == "sim":
        return f"pente {step.value:g} %"
    if step.mode == "sim_w":
        return f"SIM {step.value:g} W" + ("" if step.grade_pct is None else f" (pente {step.grade_pct:g} %)")
    return f"ERG {step.value:g} W"


def _step_short(step: Step) -> str:
    return f"{step.value:g} %" if step.mode == "sim" else f"{step.value:g} W"


def plan_steps(steps: list[Step], cfg: config.Config, cw: float, cadence: float,
               gearing: Gearing | None) -> list[Step]:
    """Pentes des paliers `sim_w` (lot X43) ; refus si le plateau et le pignon manquent."""
    if any(s.mode == "sim_w" for s in steps) and gearing is None:
        raise ValueError("paliers à puissance cible : donner --plateau et --pignon (dents du braquet réel)")
    return [Step(s.mode, s.value, s.hold_s, grade_for_power(s.value, cadence, gearing, cfg.total_mass_kg,
                                                             cfg.bike.crr, cw))
            if s.mode == "sim_w" else s for s in steps]


def default_ceiling(steps: list[Step]) -> float | None:
    """Plafond par défaut : 125 % du plus fort palier en watts ; aucun pour un protocole en pentes."""
    watts = [s.value for s in steps if s.mode in ("erg", "sim_w")]
    return round(max(watts) * CEILING_MARGIN) if watts else None


async def run_bench(steps: list[Step], cfg: config.Config, *, sim_world: Any = None,
                    cadence: float = 85.0, connect_timeout_s: float = 60.0,
                    guide: Guide | None = None, lead_in_s: float = LEAD_IN_S,
                    gearing: Gearing | None = None, ceiling_w: float | None = None) -> Recording:
    from ..ftms import parse_indoor_bike_data
    from ..ftms_driver import FtmsDriver

    cfg.trainer.trace_ftms = True
    rec = Recording()
    t0 = time.monotonic()

    def clock() -> float:
        return time.monotonic() - t0

    if sim_world is not None:
        drv = FtmsDriver(cfg.trainer, cfg.bike, None, device_finder=sim_world.find_device,
                         client_factory=sim_world.client_factory)
    else:
        drv = FtmsDriver(cfg.trainer, cfg.bike, cfg.drivers.trainer_address or None)
    steps = plan_steps(steps, cfg, drv._cw, cadence, gearing)
    on_ibd = drv._on_ibd

    def tap(ch: Any, data: bytearray) -> None:
        on_ibd(ch, data)
        try:
            d = parse_indoor_bike_data(bytes(data))
            speed, res = d.speed_kmh, d.resistance_level
        except (ValueError, struct.error):   # trame tronquée : la puissance du pilote suffit
            speed = res = None
        rec.samples.append((clock(), drv._raw_power, float(drv._cadence or 0.0), speed,
                            None if res is None else float(res)))

    drv._on_ibd = tap   # avant run() : start_notify prend l'attribut de l'instance
    # Statuts du trainer et frein lâché (lignes `ftms` du pilote, PR #580) : dans events.csv (lot X44).
    drv.event_sink = lambda line: rec.events.append((clock(), "ftms", decrochages.status_text(line)))
    handler = _CpLogTap(rec, clock)
    ftms_log = logging.getLogger("ftms_driver")
    ftms_log.addHandler(handler)
    old_level = ftms_log.level
    ftms_log.setLevel(logging.INFO)
    g = guide or Guide("Banc de latence du trainer", sound=False, screen=False, out=io.StringIO())
    off_since: float | None = None

    def live() -> dict[str, Any]:
        return {"puissance": f"{drv._raw_power:.0f} W", "cadence": f"{drv._cadence or 0:.0f} rpm",
                "cible": f"{cadence:.0f} rpm"}

    async def hold(seconds: float, ceiling: bool = False) -> None:
        """Tient le palier ; avec `ceiling`, le coupe dès que la puissance moyenne sur 3 s dépasse le plafond."""
        nonlocal off_since
        end_hold = time.monotonic() + seconds
        start = clock()
        while time.monotonic() < end_hold:
            if ceiling and ceiling_w is not None and clock() - start >= CEILING_WINDOW_S:
                recent = _window(rec.samples, clock() - CEILING_WINDOW_S, clock() + 1.0)
                if recent and statistics.fmean(recent) > ceiling_w:
                    rec.events.append((clock(), "ceiling", f"{statistics.fmean(recent):.0f} W > {ceiling_w:g} W"))
                    g.alert(f"Plafond de {ceiling_w:g} W dépassé : palier coupé", beep=False)
                    return
            drv.poll()
            if task.done():
                raise RuntimeError("liaison au trainer perdue pendant l'essai")
            cad = float(drv._cadence or 0.0)
            if abs(cad - cadence) > CADENCE_TOL_RPM:
                off_since = off_since if off_since is not None else time.monotonic()
                if time.monotonic() - off_since >= CADENCE_ALERT_S and not g.banner:
                    g.alert(f"Cadence {cad:.0f} rpm : reviens à {cadence:.0f} rpm", beep=False)
            elif off_since is not None:
                off_since = None
                g.banner = ""
            g.tick(live())
            await asyncio.sleep(0.1)

    task = asyncio.create_task(drv.run())
    # Événements datés du scénario simulé (décrochages du frein, relances…, lot X46).
    world_task = asyncio.create_task(sim_world.run()) if sim_world is not None else None
    try:
        g.step("Connexion au trainer", connect_timeout_s, "pédale doucement pour le réveiller", beep=False)
        end = time.monotonic() + connect_timeout_s
        while drv.status != "CONNECTED":
            if time.monotonic() > end:
                raise RuntimeError("trainer introuvable ou muet : vérifier qu'aucune autre application ne le tient")
            g.tick()
            await asyncio.sleep(0.2)
        g.note("Trainer relié")
        if lead_in_s > 0:
            g.step(f"Pédale à {cadence:.0f} rpm", lead_in_s,
                   "garde le même braquet pendant tout l'essai ; premier palier à la fin du compte")
            await hold(lead_in_s)
        for i, step in enumerate(steps):
            g.step(step_label(step), step.hold_s, f"garde {cadence:.0f} rpm, ne change pas de braquet",
                   index=i + 1, total=len(steps))
            rec.steps.append((clock(), step))
            rec.events.append((clock(), "command", f"{step.mode} {step.value:g}"))
            if step.mode == "sim":
                drv.set_sim_grade(step.value, immediate=True)
            elif step.mode == "sim_w":
                drv.set_sim_grade(step.grade_pct, immediate=True)
            else:
                drv.set_target_power(step.value)
            await hold(step.hold_s, ceiling=True)
    finally:
        drv.stop()
        try:
            await asyncio.wait_for(task, timeout=10.0)
        except (asyncio.TimeoutError, Exception):
            task.cancel()
        if world_task is not None:
            sim_world.stop()
            world_task.cancel()
        ftms_log.removeHandler(handler)
        ftms_log.setLevel(old_level)
    return rec


def scenario_spec(name: str) -> dict[str, Any]:
    """Scénario du trainer simulé, vide s'il est illisible (l'erreur est donnée à la construction du monde)."""
    from ..sim_scenarios import SimScenarioError, load_scenario
    try:
        return load_scenario(name)
    except SimScenarioError:
        return {}


def scenario_gearing(spec: dict[str, Any]) -> Gearing | None:
    """Braquet réel du cycliste simulé d'un scénario (lot X46), ou None."""
    rider = spec.get("rider") or {}
    if rider.get("chainring") is None:
        return None
    return Gearing(rider["chainring"], rider["sprocket"], rider.get("wheel_m", WHEEL_M))


def load_protocol(name_or_path: str, fast: bool = False, fast_hold_s: float = 6.0) -> list[Step]:
    if name_or_path in PROTOCOLS:
        raw = [{"mode": m, "value": v, "hold_s": h} for m, v, h in PROTOCOLS[name_or_path]]
    else:
        raw = json.loads(Path(name_or_path).expanduser().read_text(encoding="utf-8"))["steps"]
    steps = [Step(str(d["mode"]), float(d["value"]), float(d["hold_s"])) for d in raw]
    for s in steps:
        if s.mode not in MODES or s.hold_s <= 0 or (s.mode in ("erg", "sim_w") and s.value <= 0):
            raise ValueError(f"palier invalide : {s}")
    if fast:   # essai rapide (Bluetooth simulé) : paliers de `fast_hold_s` (6 s) au plus
        steps = [Step(s.mode, s.value, min(s.hold_s, max(8.0, fast_hold_s) if i == 0 else fast_hold_s))
                 for i, s in enumerate(steps)]
    return steps


def model_checks(results: list[StepResult], model: Any, frame_s: float = 0.25) -> list[tuple[bool, str]]:
    """t63 mesuré contre le modèle du trainer simulé réaliste (lot X6), à ± MODEL_TOL : écriture de la
    consigne, retard du frein, constante de temps de serrage (puissance qui monte) ou de relâchement (qui
    baisse), plus une trame (`frame_s`) de retard de la moyenne glissante sur 3 trames de l'analyse.
    L'écart admis ne descend pas sous deux trames : le départ et le franchissement sont chacun lus à une
    trame près (paliers courts des tests). Paliers sans t63 ignorés."""
    out = []
    for r in results:
        if r.t63_s is None or r.delta_w is None:
            continue
        want = ((r.write_ms or 0.0) / 1000.0 + frame_s + model.delay_s
                + (model.tau_up_s if r.delta_w > 0 else model.tau_down_s))
        gap = (r.t63_s - want) / want
        out.append((abs(r.t63_s - want) <= max(MODEL_TOL * want, 2 * frame_s), f"palier {r.index} ({step_label(Step(r.mode, r.value, 0, r.grade_pct))}) : t63 "
                    f"{r.t63_s:g} s, modèle {want:.2f} s ({gap * 100:+.0f} %)"))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Banc de latence du trainer par paliers (lot X5, essai R0).")
    ap.add_argument("--mode", default="sim", help="protocole : " + ", ".join(PROTOCOLS)
                    + " ou fichier JSON {\"steps\": [...]}")
    ap.add_argument("--trainer", choices=("ftms", "sim"), default="ftms", help="vrai trainer ou Bluetooth simulé")
    ap.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    ap.add_argument("--cadence", type=float, default=85.0, help="cadence à tenir, rappelée à l'écran")
    ap.add_argument("--fast", action="store_true", help="paliers courts (essai du banc)")
    ap.add_argument("--plateau", type=int, help="dents du plateau réel (paliers sim_w, lot X43)")
    ap.add_argument("--pignon", type=int, help="dents du pignon réel (paliers sim_w)")
    ap.add_argument("--roue", type=float, default=WHEEL_M, help=f"circonférence de la roue en m (défaut {WHEEL_M})")
    ap.add_argument("--plafond", type=float,
                    help="puissance (W, moyenne sur 3 s) qui coupe le palier ; défaut : 125 %% du plus fort palier")
    ap.add_argument("--response", choices=("instant", "realiste"), default="instant",
                    help="réponse du trainer simulé (--trainer sim, lot X6)")
    ap.add_argument("--scenario", default="nominal",
                    help="scénario du trainer simulé (--trainer sim) : nom intégré (pignon_unique, "
                         "decrochage_trainer…) ou fichier JSON (lot X46)")
    ap.add_argument("--calibration", type=Path, help="steps.csv d'un essai réel : valeurs du modèle réaliste")
    ap.add_argument("--out", type=Path, help="dossier de sortie")
    ap.add_argument("--analyse", type=Path, metavar="DOSSIER", help="relit un essai et refait l'analyse")
    ap.add_argument("--materiel", action="store_true", help="affiche le matériel à préparer et quitte")
    ap.add_argument("--sans-attente", action="store_true", help="démarre sans attendre « Entrée »")
    ap.add_argument("--muet", action="store_true", help="sans bips")
    ap.add_argument("--fenetre", action="store_true",
                    help="suivi en direct dans une fenêtre à part, qui reste ouverte à la fin (lot X45)")
    args = ap.parse_args(argv)
    if args.materiel:
        from .guide import materials_text
        print(materials_text(["trainer_steps"]), end="")
        return 0
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for h in logging.getLogger().handlers:   # le journal FTMS passe en INFO pour le banc, pas à l'écran
        h.setLevel(logging.WARNING)

    if args.analyse:
        rec = load(args.analyse)
        out = args.analyse
    else:
        sim_spec = scenario_spec(args.scenario) if args.trainer == "sim" else {}
        try:
            # Trainer simulé réaliste : relâchement à 90 % vers 12 s, paliers rapides de 20 s.
            realiste = args.trainer == "sim" and (args.response == "realiste" or args.calibration is not None
                                                  or (sim_spec.get("trainer") or {}).get("response") == "realiste")
            steps = load_protocol(args.mode, args.fast, 20.0 if realiste else 6.0)
        except (OSError, ValueError, KeyError) as exc:
            print(f"Protocole illisible : {exc}", file=sys.stderr)
            return 2
        cfg = config.load(args.config) if args.config else config.load()
        if (args.plateau is None) != (args.pignon is None) or any(
                v is not None and v <= 0 for v in (args.plateau, args.pignon)) or args.roue <= 0:
            print("Braquet réel : donner --plateau et --pignon ensemble (dents > 0), --roue > 0", file=sys.stderr)
            return 2
        gearing = Gearing(args.plateau, args.pignon, args.roue) if args.plateau is not None else scenario_gearing(sim_spec)
        if any(s.mode == "sim_w" for s in steps) and gearing is None:
            print("Paliers à puissance cible : donner --plateau et --pignon (dents du braquet réel)", file=sys.stderr)
            return 2
        ceiling = args.plafond if args.plafond is not None else default_ceiling(steps)
        world = None
        if args.trainer == "sim":
            from ..sim_scenarios import SimScenarioError, build_world, load_scenario
            try:
                spec = load_scenario(args.scenario)
            except SimScenarioError as exc:
                print(f"Trainer simulé : {exc}", file=sys.stderr)
                return 2
            if gearing is not None:   # même braquet réel et même cadence pour le cycliste simulé (lot X46)
                spec["rider"] = {**(spec.get("rider") or {}), "chainring": gearing.chainring,
                                 "sprocket": gearing.sprocket, "wheel_m": gearing.wheel_m,
                                 "cadence_rpm": args.cadence}
            if realiste:
                # Le protocole demande de tenir la cadence quoi qu'il arrive : pas de limite de puissance.
                spec["trainer"]["response"] = "realiste"
                spec["trainer"].setdefault("rider_max_w", 2000)
                if args.calibration:
                    spec["trainer"]["calibration"] = str(args.calibration)
            try:
                world = build_world(spec, args.scenario, click=False, hr=False)
            except SimScenarioError as exc:
                print(f"Trainer simulé : {exc}", file=sys.stderr)
                return 2
        out = args.out or DEFAULT_OUT / datetime.now().strftime("%Y-%m-%d_%H%M%S")
        guide = Guide(f"Banc de latence du trainer ({args.mode})", out / "guide.jsonl",
                      sound=False if args.muet else None,
                      live_file=out / suivi_direct.LIVE_NAME if args.fenetre else None)
        if args.fenetre:
            guide.publish(force=True)
            opened = suivi_direct.launch(out / suivi_direct.LIVE_NAME)
            print(f"Fenêtre de suivi : {opened}" if opened else "Aucun terminal trouvé pour la fenêtre de suivi : "
                  f"lancer {' '.join(suivi_direct.command(out / suivi_direct.LIVE_NAME))}")
        try:
            interactive = args.trainer == "ftms" and not args.sans_attente and sys.stdin.isatty()
            guide.prepare("trainer_steps", wait=interactive, auto_s=0 if args.fast else 10.0)
            rec = asyncio.run(run_bench(steps, cfg, sim_world=world, cadence=args.cadence, guide=guide,
                                        lead_in_s=2.0 if args.fast else LEAD_IN_S, gearing=gearing,
                                        ceiling_w=ceiling))
        except (RuntimeError, KeyboardInterrupt, EOFError) as exc:
            guide.finish(False, f"Essai interrompu : {exc}")
            guide.close()
            print(f"Essai interrompu : {exc}", file=sys.stderr)
            return 1
        save(rec, out)
        results = analyse(rec)
        for r in results:
            if r.t90_s is not None:
                guide.measure(f"palier {r.index} ({step_label(Step(r.mode, r.value, 0, r.grade_pct))})", f"t90 {r.t90_s:g}", "s")
        drops, _ = decrochages.analyse(bench_source(rec, out.name))
        for d in drops:
            guide.note(f"Décrochage à {d.t:.0f} s ({d.from_w:g} → {d.to_w:g} W) : {decrochages.KIND_TEXT[d.kind]}")
        guide.finish(True, "Essai fini : tu peux arrêter de pédaler")
        guide.close()
    results = analyse(rec)
    print(write_results(results, out), end="")
    src = bench_source(rec, out.name)
    print(decrochages.text_report(src, *decrochages.analyse(src)), end="")
    print(f"Rapport : {write_report(rec, results, out)}")
    model = getattr(getattr(world, "trainer", None), "model", None) if not args.analyse else None
    if model is not None:
        checks = model_checks(results, model, 1.0 / world.trainer.ibd_hz)
        for ok, msg in checks:
            print(f"[{'OK' if ok else 'ÉCHEC'}] {msg}")
        return 0 if all(ok for ok, _ in checks) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
