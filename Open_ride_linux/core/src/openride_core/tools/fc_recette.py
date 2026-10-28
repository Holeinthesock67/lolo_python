"""Recette guidée de la fréquence cardiaque (lot X9) : ceinture retirée puis remise, sur le vélo ou simulée.

    python -m openride_core.tools.fc_recette                       # essai guidé de 4 min sur le vélo
    python -m openride_core.tools.fc_recette --sim                 # Bluetooth simulé, FC relayée par le trainer
    python -m openride_core.tools.fc_recette --sim --source ceinture
    python -m openride_core.tools.fc_recette --analyse DOSSIER|JOURNAL.jsonl|SEANCE.fit [--retrait 60 --remise 120]
    python -m openride_core.tools.fc_recette --materiel

L'essai guidé (module `guide` : bips, compte à rebours, rappel du matériel) dure quatre phases de
`--phase-s` secondes (60 par défaut) : ceinture portée, retirée, remise, portée. Le vrai pilote du trainer
(FC relayée, gel du lot Q5 compris) et la ceinture Bluetooth si `[drivers] hr = "ble"` sont relevés à
1 Hz dans `fc.csv` (t, phase, source, fc, contact, puissance), la FC retenue étant celle de la séance :
la ceinture d'abord, sinon celle du trainer.

Contrôles :
- **absence** : pendant le retrait, la FC disparaît au plus `--absence` s (10) après le retrait et ne
  revient pas. Pour une FC relayée par le trainer, seul le gel la fait disparaître : le délai admis est
  alors `hr_relay_freeze_s + 2` s s'il dépasse 10 s (écart noté au rapport) ;
- **valeur figée** : aucune valeur identique plus de `--fige` s (15) pendant que la puissance varie
  d'au moins 5 W ;
- **retour** : la FC revient au plus `--retour` s (20) après la remise ;
- la source (ceinture Bluetooth ou relais du trainer) est notée.

`--analyse` refait les contrôles sur un dossier de l'outil (`fc.csv`), un journal de séance ou un FIT,
les phases étant alors placées par `--retrait` et `--remise` (secondes depuis le premier relevé).
`--sim` joue l'essai devant le Bluetooth simulé (événements `contact` et `bpm` figé) ; avec `--gel 120`
la valeur figée passe et le contrôle échoue, ce que vérifient les tests.

Écrit `rapport.txt`, `rapport.json`, `fc.csv` et `guide.jsonl` dans `~/OpenRide/fc_recette/<date>_<heure>/`.
Code de sortie : 0 si tous les contrôles passent, 1 sinon, 2 si l'entrée est illisible.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import math
import sys
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from .guide import Guide

DEFAULT_OUT = Path.home() / "OpenRide" / "fc_recette"
PHASES = (("portee", "Ceinture portée : roule normalement"),
          ("retiree", "Retire la ceinture (ou décroche-la de la peau)"),
          ("remise", "Remets la ceinture (mouille les électrodes)"),
          ("portee_fin", "Ceinture portée : roule normalement"))
COLUMNS = ("t", "phase", "source", "fc", "contact", "puissance")
SOURCES = {"ceinture": "ceinture Bluetooth", "trainer": "relais du trainer", "inconnue": "inconnue"}
FREEZE_MIN_S = 5.0   # borne basse de hr_relay_freeze_s (configuration)
MARGIN_S = 2.0   # FC relayée : le gel la retire au plus tard une notification après hr_relay_freeze_s


@dataclass
class Limits:
    absent_s: float = 10.0      # FC absente au plus 10 s après le retrait
    frozen_s: float = 15.0      # aucune valeur identique plus de 15 s pendant que la puissance varie
    back_s: float = 20.0        # FC revenue au plus 20 s après la remise
    power_var_w: float = 5.0    # « la puissance varie » : au moins 5 W d'écart sur la plage
    freeze_cfg_s: float = 15.0  # hr_relay_freeze_s de la configuration (FC relayée)


# --- contrôles ------------------------------------------------------------------------------

def phase_starts(samples: list[dict[str, Any]]) -> dict[str, float]:
    starts: dict[str, float] = {}
    for s in samples:
        starts.setdefault(s["phase"], s["t"])
    return starts


def check_absence(samples: list[dict[str, Any]], limits: Limits, source: str) -> dict[str, Any]:
    deadline = limits.absent_s
    note = ""
    if source == "trainer" and limits.freeze_cfg_s + MARGIN_S > deadline:
        deadline = limits.freeze_cfg_s + MARGIN_S
        note = (f" (FC relayée : délai admis {deadline:g} s = hr_relay_freeze_s {limits.freeze_cfg_s:g} s + "
                f"{MARGIN_S:g} s ; pour tenir {limits.absent_s:g} s, régler hr_relay_freeze_s à "
                f"{max(limits.absent_s - MARGIN_S, FREEZE_MIN_S):g} s)")
    during = [s for s in samples if s["phase"] == "retiree"]
    if not during:
        return {"nom": "absence", "ok": False, "detail": "aucun relevé pendant le retrait", "delai_admis_s": deadline}
    t0 = during[0]["t"]
    if during[-1]["fc"] is not None:
        return {"nom": "absence", "ok": False, "delai_admis_s": deadline,
                "detail": f"FC encore là à la fin du retrait ({during[-1]['fc']} bpm){note}"}
    gone = during[-1]["t"]
    for s in reversed(during):
        if s["fc"] is not None:
            break
        gone = s["t"]
    delay = gone - t0
    return {"nom": "absence", "ok": delay <= deadline, "delai_s": round(delay, 1), "delai_admis_s": deadline,
            "detail": f"FC absente {delay:.0f} s après le retrait (au plus {deadline:g} s){note}"}


def check_frozen(samples: list[dict[str, Any]], limits: Limits) -> dict[str, Any]:
    worst: tuple[float, Any, float] = (0.0, None, 0.0)
    run: list[dict[str, Any]] = []
    for s in samples + [{"t": None, "fc": None, "puissance": None}]:
        if run and s["fc"] == run[0]["fc"]:
            run.append(s)
            continue
        if len(run) > 1:
            powers = [r["puissance"] for r in run if r["puissance"] is not None]
            spread = max(powers) - min(powers) if powers else 0.0
            length = run[-1]["t"] - run[0]["t"]
            if spread >= limits.power_var_w and length > worst[0]:
                worst = (length, run[0]["fc"], run[0]["t"])
        run = [s] if s["fc"] is not None else []
    length, value, at = worst
    detail = (f"plus longue valeur identique : {value} bpm pendant {length:.0f} s à partir de {at:.0f} s"
              if value is not None else "aucune valeur répétée pendant que la puissance varie")
    return {"nom": "valeur figée", "ok": length <= limits.frozen_s, "duree_s": round(length, 1),
            "detail": f"{detail} (au plus {limits.frozen_s:g} s)"}


def check_back(samples: list[dict[str, Any]], limits: Limits) -> dict[str, Any]:
    t0 = phase_starts(samples).get("remise")
    if t0 is None:
        return {"nom": "retour", "ok": False, "detail": "aucun relevé après la remise"}
    back = next((s["t"] for s in samples if s["t"] >= t0 and s["fc"] is not None), None)
    if back is None:
        return {"nom": "retour", "ok": False, "detail": "FC jamais revenue après la remise"}
    delay = back - t0
    return {"nom": "retour", "ok": delay <= limits.back_s, "delai_s": round(delay, 1),
            "detail": f"FC revenue {delay:.0f} s après la remise (au plus {limits.back_s:g} s)"}


def evaluate(samples: list[dict[str, Any]], limits: Limits, source: str) -> dict[str, Any]:
    checks = [check_absence(samples, limits, source), check_frozen(samples, limits), check_back(samples, limits)]
    return {"ok": all(c["ok"] for c in checks), "source": source, "source_texte": SOURCES[source],
            "releves": len(samples), "limites": asdict(limits), "controles": checks}


def report_text(report: dict[str, Any]) -> str:
    lines = ["Recette de la fréquence cardiaque (lot X9)", "",
             f"  source : {report['source_texte']} ; {report['releves']} relevés", ""]
    for c in report["controles"]:
        lines.append(f"  [{'OK' if c['ok'] else 'ÉCHEC'}] {c['nom']} : {c['detail']}")
    lines += ["", "Verdict : " + ("tout passe" if report["ok"] else "au moins un contrôle échoue")]
    return "\n".join(lines) + "\n"


def write_outputs(samples: list[dict[str, Any]], report: dict[str, Any], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "fc.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for s in samples:
            w.writerow({k: "" if s.get(k) is None else s[k] for k in COLUMNS})
    (out / "rapport.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "rapport.txt").write_text(report_text(report), encoding="utf-8")


# --- analyse a posteriori -------------------------------------------------------------------

class InputError(Exception):
    """Dossier, journal ou FIT illisible ou sans relevé."""


def phase_at(t: float, retrait: float, remise: float, phase_s: float) -> str:
    if t < retrait:
        return "portee"
    if t < remise:
        return "retiree"
    return "remise" if t < remise + phase_s else "portee_fin"


def _num(v: str) -> Any:
    if v in ("", None):
        return None
    if v in ("True", "False"):
        return v == "True"
    f = float(v)
    return int(f) if f.is_integer() else f


def load_samples(path: Path, retrait: float, remise: float) -> tuple[list[dict[str, Any]], str]:
    """Relevés (t, phase, fc, puissance…) et source d'un dossier de l'outil, d'un journal ou d'un FIT."""
    path = Path(path)
    if path.is_dir():
        csv_path = path / "fc.csv"
        if not csv_path.is_file():
            raise InputError(f"pas de fc.csv dans {path}")
        with csv_path.open(encoding="utf-8") as fh:
            rows = [{k: (v if k in ("phase", "source") else _num(v)) for k, v in r.items()} for r in csv.DictReader(fh)]
        if not rows:
            raise InputError(f"aucun relevé dans {csv_path}")
        sources = {r["source"] for r in rows if r["source"]}
        source = "ceinture" if "ceinture" in sources else "trainer" if "trainer" in sources else "inconnue"
        return rows, source
    from .session_summary import SummaryError, load_session

    try:
        session = load_session(path)
    except SummaryError as exc:
        raise InputError(str(exc)) from exc
    t0 = session.records[0]["ts"]
    phase_s = remise - retrait
    samples = [{"t": round(r["ts"] - t0, 3), "phase": phase_at(r["ts"] - t0, retrait, remise, phase_s),
                "source": "", "fc": r.get("hr"), "contact": None, "puissance": r.get("power")}
               for r in session.records]
    hr_devices = [d for d in session.devices if d.get("device") == "hr"]
    source = "inconnue" if session.fmt == "fit" else "ceinture" if hr_devices else "trainer"
    return samples, source


# --- essai guidé ----------------------------------------------------------------------------

async def run_trial(trainer: Any, strap: Any, phase_s: float, guide: Guide,
                    on_phase: Any = None, period_s: float = 1.0) -> list[dict[str, Any]]:
    """Déroule les quatre phases ; relève à `period_s` la FC que retiendrait la séance."""
    tasks = [asyncio.create_task(d.run()) for d in (trainer, strap) if d is not None]
    samples: list[dict[str, Any]] = []
    t0 = time.monotonic()
    try:
        end = t0 + 60.0
        guide.step("Connexion du trainer" + (" et de la ceinture" if strap else ""), 60.0)
        while time.monotonic() < end and not (trainer.status == "CONNECTED"
                                              and (strap is None or strap.bpm is not None)):
            guide.tick()
            await asyncio.sleep(0.2)
        guide.measure("trainer connecté", trainer.status, ok=trainer.status == "CONNECTED")
        if strap is not None:
            guide.measure("ceinture", f"{strap.bpm} bpm" if strap.bpm else strap.status, ok=strap.bpm is not None)
        t0 = time.monotonic()
        for k, (key, text) in enumerate(PHASES):
            guide.step(text, phase_s, index=k + 1, total=len(PHASES))
            if on_phase is not None:
                on_phase(key)
            phase_end = t0 + (k + 1) * phase_s
            while True:
                now = time.monotonic()
                if now >= phase_end - 1e-3:
                    break
                m = trainer.poll(now - t0)
                strap_bpm = strap.bpm if strap is not None else None
                hr = strap_bpm if strap_bpm is not None else m.hr_bpm
                samples.append({"t": round(now - t0, 2), "phase": key,
                                "source": "ceinture" if strap_bpm is not None else "trainer" if hr else "",
                                "fc": hr, "contact": strap.contact if strap is not None else None,
                                "puissance": round(m.power_w)})
                guide.tick({"FC": f"{hr} bpm" if hr else "—", "puissance": f"{m.power_w:.0f} W"})
                await asyncio.sleep(max(0.0, min(period_s, phase_end - time.monotonic())))
    finally:
        for d in (trainer, strap):
            if d is not None:
                d.stop()
        await asyncio.gather(*tasks, return_exceptions=True)
    return samples


def sim_world(source: str) -> Any:
    """Monde simulé de l'essai : trainer qui relaie la FC, ou ceinture Bluetooth et trainer sans relais."""
    from .. import sim_scenarios

    trainer = {"appear_at": 0.2, "connect_delay_s": 0.2, "rider_power_w": 180, "cadence_rpm": 88}
    if source == "trainer":
        trainer["relayed_hr"] = True
    spec = {"seed": 9, "trainer": trainer, "click": None, "events": [],
            "hr": {"appear_at": 0.2, "connect_delay_s": 0.2, "tau_s": 3.0} if source == "ceinture" else None}
    return sim_scenarios.build_world(spec, click=False)


def sim_rider(world: Any, source: str) -> Any:
    """Le cycliste simulé : change d'allure à chaque phase, retire la ceinture (trainer : dernière valeur
    figée), puis la remet."""
    watts = {"portee": 180, "retiree": 210, "remise": 170, "portee_fin": 200}

    def on_phase(key: str) -> None:
        world.trainer.rider_power_w = watts[key]
        if source == "trainer" and key == "retiree":
            world.trainer.fixed_relayed_hr = int(round(130 + 3.0 * math.sin(world.now() * 0.5)))
        elif source == "trainer" and key == "remise":
            world.trainer.fixed_relayed_hr = None
        elif source == "ceinture" and key in ("retiree", "remise"):
            world.hr.contact = key == "remise"
    return on_phase


async def main_async(args: argparse.Namespace) -> int:
    from .. import config as config_mod
    from ..ftms_driver import FtmsDriver
    from ..hr_monitor import HeartRateProvider

    cfg = config_mod.load(args.config)
    if args.gel is not None:
        cfg = replace(cfg, trainer=replace(cfg.trainer, hr_relay_freeze_s=args.gel))
    out = args.out or DEFAULT_OUT / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    guide = Guide("Recette de la fréquence cardiaque", out / "guide.jsonl",
                  sound=False if args.muet or args.sim else None, screen=None if not args.sim else False)
    guide.prepare("fc_recette", wait=not args.sim and not args.sans_attente and sys.stdin.isatty(),
                  auto_s=0 if args.sim else 10.0)
    world = on_phase = None
    if args.sim:
        source = args.source
        world = sim_world(source)
        on_phase = sim_rider(world, source)
        trainer = FtmsDriver(cfg.trainer, cfg.bike, None, device_finder=world.find_device,
                             client_factory=world.client_factory)
        strap = (HeartRateProvider(None, "", device_finder=world.find_device, client_factory=world.client_factory)
                 if source == "ceinture" else None)
    else:
        source = "ceinture" if cfg.drivers.hr == "ble" else "trainer"
        trainer = FtmsDriver(cfg.trainer, cfg.bike, cfg.drivers.trainer_address or None)
        strap = HeartRateProvider(cfg.drivers.hr_address or None, cfg.drivers.hr_name) if source == "ceinture" else None
    runner = asyncio.create_task(world.run()) if world is not None else None
    try:
        samples = await run_trial(trainer, strap, args.phase_s, guide, on_phase)
    finally:
        if world is not None:
            world.stop()
            runner.cancel()
            await asyncio.gather(runner, return_exceptions=True)
    report = evaluate(samples, limits_from(args, cfg.trainer.hr_relay_freeze_s), source)
    guide.finish(report["ok"], "Recette finie : tout passe" if report["ok"] else "Recette finie : voir le rapport")
    guide.close()
    write_outputs(samples, report, out)
    print()
    print(report_text(report), end="")
    print(f"Rapport : {out}")
    return 0 if report["ok"] else 1


def limits_from(args: argparse.Namespace, freeze_cfg_s: float) -> Limits:
    return Limits(absent_s=args.absence, frozen_s=args.fige, back_s=args.retour, freeze_cfg_s=freeze_cfg_s)


def analyse(args: argparse.Namespace) -> int:
    from .. import config as config_mod

    freeze = args.gel if args.gel is not None else config_mod.load(args.config).trainer.hr_relay_freeze_s
    try:
        samples, source = load_samples(args.analyse, args.retrait, args.remise)
    except InputError as exc:
        print(f"Entrée illisible : {exc}")
        return 2
    report = evaluate(samples, limits_from(args, freeze), args.source if args.source_imposee else source)
    print(report_text(report), end="")
    if args.out:
        write_outputs(samples, report, args.out)
        print(f"Rapport : {args.out}")
    return 0 if report["ok"] else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Recette guidée de la fréquence cardiaque (lot X9).")
    ap.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    ap.add_argument("--sim", action="store_true", help="Bluetooth simulé, cycliste simulé")
    ap.add_argument("--source", choices=("trainer", "ceinture"), default=None,
                    help="avec --sim : FC relayée par le trainer (défaut) ou ceinture Bluetooth ; "
                         "avec --analyse : impose la source")
    ap.add_argument("--analyse", type=Path, metavar="ENTREE", help="dossier de l'outil, JOURNAL.jsonl ou FIT")
    ap.add_argument("--retrait", type=float, default=60.0, help="avec --analyse : s du retrait (défaut 60)")
    ap.add_argument("--remise", type=float, default=120.0, help="avec --analyse : s de la remise (défaut 120)")
    ap.add_argument("--phase-s", type=float, default=60.0, help="durée de chaque phase (défaut 60)")
    ap.add_argument("--absence", type=float, default=10.0, help="FC absente au plus N s après le retrait (10)")
    ap.add_argument("--fige", type=float, default=15.0, help="valeur identique au plus N s (15)")
    ap.add_argument("--retour", type=float, default=20.0, help="FC revenue au plus N s après la remise (20)")
    ap.add_argument("--gel", type=float, help="hr_relay_freeze_s imposé (défaut : celui de la configuration)")
    ap.add_argument("--out", type=Path, help=f"dossier de sortie (défaut : {DEFAULT_OUT}/<date>)")
    ap.add_argument("-v", "--verbose", action="store_true", help="journal des pilotes à l'écran")
    ap.add_argument("--materiel", action="store_true", help="affiche le matériel à préparer et quitte")
    ap.add_argument("--sans-attente", action="store_true", help="démarre sans attendre « Entrée »")
    ap.add_argument("--muet", action="store_true", help="sans bips")
    args = ap.parse_args(argv)
    args.source_imposee = args.source is not None
    args.source = args.source or "trainer"
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.materiel:
        from .guide import materials_text
        print(materials_text(["fc_recette"]), end="")
        return 0
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)-7s %(name)s %(message)s")
    if args.analyse is not None:
        return analyse(args)
    try:
        return asyncio.run(main_async(args))
    except (KeyboardInterrupt, EOFError):
        print("\nInterrompu.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
