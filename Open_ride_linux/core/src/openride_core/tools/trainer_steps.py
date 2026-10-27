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
    python -m openride_core.tools.trainer_steps --analyse DOSSIER        # relit samples.csv
    python -m openride_core.tools.trainer_steps --materiel               # matériel à préparer

L'essai est guidé (module `guide`) : rappel du matériel, puis à l'écran le palier en cours, un compte à
rebours, la puissance et la cadence en direct, une alerte si la cadence s'écarte de plus de 10 rpm, et un
bip à chaque palier. Le journal de l'essai (`guide.jsonl`) est écrit avec les autres fichiers.

Sortie dans `~/OpenRide/trainer_steps/<date>_<heure>/` : `samples.csv` (chaque trame Indoor
Bike Data), `events.csv` (consignes, écritures, accusés), `steps.csv` (résultats par palier) et
`rapport.html` (courbes). Le trainer est relâché à la fin (Reset, comme en séance).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
import logging
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import config
from .guide import Guide

DEFAULT_OUT = Path.home() / "OpenRide" / "trainer_steps"

# (mode, valeur, durée en s). Montée puis descente, petites et grandes marches, pour voir aussi
# le relâchement (lent sur le HomeTrainer : 10 à 15 s à l'essai du 25 octobre).
PROTOCOLS: dict[str, list[tuple[str, float, float]]] = {
    "sim": [("sim", 0.0, 60), ("sim", 4.0, 30), ("sim", 8.0, 30), ("sim", 4.0, 30), ("sim", 0.0, 30),
            ("sim", 8.0, 30), ("sim", 0.0, 40)],
    "erg": [("erg", 150.0, 60), ("erg", 250.0, 30), ("erg", 150.0, 30), ("erg", 300.0, 30),
            ("erg", 150.0, 40)],
}
BASELINE_S = 5.0        # fenêtre de la valeur de départ, juste avant la consigne
FINAL_S = 5.0           # fenêtre de la valeur finale, fin du palier
SETTLE_PCT = 10.0       # stable : à ± 10 % du changement de puissance…
SETTLE_MIN_W = 5.0      # … et au moins ± 5 W (bruit des trames)
MIN_DELTA_W = 10.0      # en dessous, pas de délai mesurable
LEAD_IN_S = 10.0        # compte à rebours entre la connexion et le premier palier
CADENCE_TOL_RPM = 10.0  # alerte si la cadence s'écarte plus que ça de la cadence demandée…
CADENCE_ALERT_S = 3.0   # … pendant au moins ce temps


@dataclass
class Step:
    mode: str
    value: float
    hold_s: float


@dataclass
class Recording:
    """Ce que le banc a vu, horodaté sur la même horloge (secondes depuis le départ)."""
    samples: list[tuple[float, float, float]] = field(default_factory=list)   # t, puissance, cadence
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


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _window(samples: list[tuple[float, float, float]], t0: float, t1: float, col: int = 1) -> list[float]:
    return [s[col] for s in samples if t0 <= s[0] < t1]


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
    if prev is None:
        res.note = "palier de départ"
        return res
    if base is None or final is None or not seg:
        res.note = "pas assez de mesures"
        return res
    delta = final - base
    res.delta_w = round(delta, 1)
    if abs(delta) < MIN_DELTA_W:
        res.note = "changement de puissance trop faible pour mesurer un délai"
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
        res.note = "90 % jamais atteint pendant le palier"
    return res


def analyse(rec: Recording) -> list[StepResult]:
    return [analyse_step(rec, i) for i in range(len(rec.steps))]


# --- fichiers ---------------------------------------------------------------------------

def save(rec: Recording, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "samples.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["t_s", "power_w", "cadence_rpm"])
        w.writerows((f"{t:.3f}", f"{p:.1f}", f"{c:.1f}") for t, p, c in rec.samples)
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
        rec.samples = [(float(r["t_s"]), float(r["power_w"]), float(r["cadence_rpm"])) for r in csv.DictReader(fh)]
    with (out / "events.csv").open(encoding="utf-8") as fh:
        rec.events = [(float(r["t_s"]), r["type"], r["detail"]) for r in csv.DictReader(fh)]
    for d in json.loads((out / "protocol.json").read_text(encoding="utf-8")):
        rec.steps.append((float(d["t_s"]), Step(d["mode"], float(d["value"]), float(d["hold_s"]))))
    return rec


def _fmt(v: Any, unit: str = "") -> str:
    return "—" if v is None else f"{v:g}{unit}"


def write_results(results: list[StepResult], out: Path) -> str:
    with (out / "steps.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(asdict(results[0]).keys()) if results else ["index"])
        w.writeheader()
        for r in results:
            w.writerow(asdict(r))
    lines = ["palier  consigne        écriture  accusé   départ → final      t10     t63     t90  stable  dépass."]
    for r in results:
        unit = " %" if r.mode == "sim" else " W"
        cons = f"{_fmt(r.from_value)}→{_fmt(r.value)}{unit}" if r.from_value is not None else f"{_fmt(r.value)}{unit}"
        bf = f"{_fmt(r.baseline_w and round(r.baseline_w))} → {_fmt(r.final_w and round(r.final_w))} W"
        lines.append(f"{r.index:>6}  {cons:<14} {_fmt(r.write_ms, ' ms'):>9} {_fmt(r.ack_ms, ' ms'):>8}  "
                     f"{bf:<17} {_fmt(r.t10_s, ' s'):>7} {_fmt(r.t63_s, ' s'):>7} {_fmt(r.t90_s, ' s'):>7} "
                     f"{_fmt(r.settle_s, ' s'):>7} {_fmt(r.overshoot_pct, ' %'):>7}  {r.note}")
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

    pts = " ".join(f"{x(t):.1f},{y(p):.1f}" for t, p, _ in rec.samples)
    marks = "".join(
        f'<line x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{pad}" y2="{height - pad}" class="step"/>'
        f'<text x="{x(t) + 3:.1f}" y="{pad + 12}" class="lbl">{s.value:g}{" %" if s.mode == "sim" else " W"}</text>'
        for t, s in rec.steps)
    rows = "".join(
        "<tr>" + "".join(f"<td>{_fmt(v)}</td>" for v in (
            r.index, r.from_value, r.value, r.write_ms, r.ack_ms, r.baseline_w and round(r.baseline_w),
            r.final_w and round(r.final_w), r.t10_s, r.t63_s, r.t90_s, r.settle_s, r.overshoot_pct,
            r.cadence_rpm and round(r.cadence_rpm))) + f"<td>{r.note}</td></tr>"
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
<th>Cadence</th><th>Note</th></tr>{rows}</table></html>
"""
    path = out / "rapport.html"
    path.write_text(html, encoding="utf-8")
    return path


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
    return f"pente {step.value:g} %" if step.mode == "sim" else f"ERG {step.value:g} W"


async def run_bench(steps: list[Step], cfg: config.Config, *, sim_world: Any = None,
                    cadence: float = 85.0, connect_timeout_s: float = 60.0,
                    guide: Guide | None = None, lead_in_s: float = LEAD_IN_S) -> Recording:
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
    on_ibd = drv._on_ibd

    def tap(ch: Any, data: bytearray) -> None:
        on_ibd(ch, data)
        rec.samples.append((clock(), drv._raw_power, float(drv._cadence or 0.0)))

    drv._on_ibd = tap   # avant run() : start_notify prend l'attribut de l'instance
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

    async def hold(seconds: float) -> None:
        nonlocal off_since
        end_hold = time.monotonic() + seconds
        while time.monotonic() < end_hold:
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
            else:
                drv.set_target_power(step.value)
            await hold(step.hold_s)
    finally:
        drv.stop()
        try:
            await asyncio.wait_for(task, timeout=10.0)
        except (asyncio.TimeoutError, Exception):
            task.cancel()
        ftms_log.removeHandler(handler)
        ftms_log.setLevel(old_level)
    return rec


def load_protocol(name_or_path: str, fast: bool = False) -> list[Step]:
    if name_or_path in PROTOCOLS:
        raw = [{"mode": m, "value": v, "hold_s": h} for m, v, h in PROTOCOLS[name_or_path]]
    else:
        raw = json.loads(Path(name_or_path).expanduser().read_text(encoding="utf-8"))["steps"]
    steps = [Step(str(d["mode"]), float(d["value"]), float(d["hold_s"])) for d in raw]
    for s in steps:
        if s.mode not in ("sim", "erg") or s.hold_s <= 0:
            raise ValueError(f"palier invalide : {s}")
    if fast:   # essai rapide (Bluetooth simulé) : paliers de 6 s au plus
        steps = [Step(s.mode, s.value, min(s.hold_s, 8.0 if i == 0 else 6.0)) for i, s in enumerate(steps)]
    return steps


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Banc de latence du trainer par paliers (lot X5, essai R0).")
    ap.add_argument("--mode", default="sim", help="protocole : sim, erg ou fichier JSON {\"steps\": [...]}")
    ap.add_argument("--trainer", choices=("ftms", "sim"), default="ftms", help="vrai trainer ou Bluetooth simulé")
    ap.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    ap.add_argument("--cadence", type=float, default=85.0, help="cadence à tenir, rappelée à l'écran")
    ap.add_argument("--fast", action="store_true", help="paliers courts (essai du banc)")
    ap.add_argument("--out", type=Path, help="dossier de sortie")
    ap.add_argument("--analyse", type=Path, metavar="DOSSIER", help="relit un essai et refait l'analyse")
    ap.add_argument("--materiel", action="store_true", help="affiche le matériel à préparer et quitte")
    ap.add_argument("--sans-attente", action="store_true", help="démarre sans attendre « Entrée »")
    ap.add_argument("--muet", action="store_true", help="sans bips")
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
        try:
            steps = load_protocol(args.mode, args.fast)
        except (OSError, ValueError, KeyError) as exc:
            print(f"Protocole illisible : {exc}", file=sys.stderr)
            return 2
        cfg = config.load(args.config) if args.config else config.load()
        world = None
        if args.trainer == "sim":
            from ..sim_scenarios import build_world, load_scenario
            world = build_world(load_scenario("nominal"), "nominal", click=False, hr=False)
        out = args.out or DEFAULT_OUT / datetime.now().strftime("%Y-%m-%d_%H%M%S")
        guide = Guide(f"Banc de latence du trainer ({args.mode})", out / "guide.jsonl",
                      sound=False if args.muet else None)
        try:
            interactive = args.trainer == "ftms" and not args.sans_attente and sys.stdin.isatty()
            guide.prepare("trainer_steps", wait=interactive, auto_s=0 if args.fast else 10.0)
            rec = asyncio.run(run_bench(steps, cfg, sim_world=world, cadence=args.cadence, guide=guide,
                                        lead_in_s=2.0 if args.fast else LEAD_IN_S))
        except (RuntimeError, KeyboardInterrupt, EOFError) as exc:
            guide.finish(False, f"Essai interrompu : {exc}")
            guide.close()
            print(f"Essai interrompu : {exc}", file=sys.stderr)
            return 1
        save(rec, out)
        results = analyse(rec)
        for r in results:
            if r.t90_s is not None:
                guide.measure(f"palier {r.index} ({step_label(Step(r.mode, r.value, 0))})", f"t90 {r.t90_s:g}", "s")
        guide.finish(True, "Essai fini : tu peux arrêter de pédaler")
        guide.close()
    results = analyse(rec)
    print(write_results(results, out), end="")
    print(f"Rapport : {write_report(rec, results, out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
