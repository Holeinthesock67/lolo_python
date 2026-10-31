"""Run Cyber-Rogue de bout en bout dans la vraie séance du core, en temps accéléré (lot X40).

    python -m openride_core.tools.rogue_bout_en_bout [--objective threshold|endurance|vo2max|tous] [--duration 30]
        [--seed 5] [--profil moyen] [--trace FICHIER.jsonl] [--json]

La vraie séance (`CoreSession`, mode ROGUE du lot R8) tourne sans trainer réel ni engine, au pas d'une seconde :
`start_run`, `start`, puis le cycliste simulé de `rogue_sim` (lot R7) pédale la cible des salles, choisit ses
cartes et ses portes, fait ses Perfect Shifts et ses appuis sur Z. Ses appuis passent par le même chemin que
ceux du Click (`_handle_input`), sa puissance par le trainer simulé (`MockDriver`). Au milieu de la première
salle, Y met la run en pause pendant une minute, puis `resume` la reprend ; `rogue_resync` est demandé une fois.
Chaque message que la séance envoie à l'engine (`state` à chaque pas, `room`, `loot`, `input`, `error`) est
relevé ; `--trace` les écrit, un par ligne, pour le banc visuel du mode (lot X41).

Vérifications : run composée puis lancée ; phases dans l'ordre (échauffement, salles et couloirs, boss,
retour au calme, résultats) ; appuis du cycliste reçus par le moteur de run ; pause qui fige le temps de run,
W'bal et le mur, pente du trainer relâchée ; `rogue_resync` qui renvoie la dernière salle ; trames `state`,
`room` et `loot` valides pour les schémas du contrat (si `jsonschema` est installé) et sous la limite de
taille ; séance terminée d'elle-même après les résultats, avec `summary.rogue` ; journal relu (`rogue_run`,
instantanés de chaque phase, enregistrements en mode ROGUE) ; durée de la run proche de celle demandée.
Le journal, le FIT et la progression restent dans un dossier temporaire.

Code de sortie : 0 si toutes les vérifications passent, 1 sinon, 2 pour un appel invalide.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest import mock

from .. import fit_export
from ..config import Config
from ..input_providers import NullProvider
from ..ipc_budget import STATE_LIMIT_1_3, size
from ..ipc_server import MAX_DATAGRAM_SIZE
from ..journal import read_journal
from ..mock_driver import MockDriver
from ..rogue.mode import DURATIONS
from ..rogue.rooms import OBJECTIVES
from ..session import CoreSession
from ..zwift_click import InputEvent
from .rogue_sim import DT, PROFILES, Bot

IPC_DIR = Path(__file__).resolve().parents[4] / "docs" / "contracts" / "ipc"
PAUSE_AFTER_S = 30.0            # pause demandée après 30 s dans la première salle
PAUSE_S = 60.0
END_WAIT_S = 30.0               # temps laissé à la séance pour finir après les résultats
DURATION_TOLERANCE = 0.25       # durée de la run : à 25 % près de celle demandée
ORDER = ("WARMUP", "ROOM", "CORRIDOR", "BOSS", "COOLDOWN", "RESULTS")
GEAR_PRESS = {1: InputEvent.PLUS_SHORT, -1: InputEvent.MINUS_SHORT}


class RunError(Exception):
    """Appel invalide : objectif, durée ou profil inconnu."""


@dataclass
class Report:
    objective: str
    duration_min: int
    seed: int
    profile: str
    checks: list[tuple[bool | None, str, str]] = field(default_factory=list)
    summary: dict | None = None
    phases: list[str] = field(default_factory=list)
    run_s: float = 0.0
    wall_s: float = 0.0
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return all(c[0] is not False for c in self.checks)

    def add(self, ok: bool | None, label: str, detail: str) -> None:
        self.checks.append((ok, label, detail))


def _validators() -> dict[str, Any] | None:
    try:
        import jsonschema
    except ImportError:
        return None
    return {n: jsonschema.Draft202012Validator(json.loads((IPC_DIR / f"{n}.schema.json").read_text("utf-8")))
            for n in ("state", "room", "loot")}


def _phase_order_ok(phases: list[str]) -> bool:
    """Échauffement d'abord, résultats à la fin, boss après la dernière salle, aucun retour en arrière au-delà."""
    if not phases or phases[0] != "WARMUP" or phases[-1] != "RESULTS":
        return False
    if "BOSS" not in phases or "COOLDOWN" not in phases:
        return False
    last_room = max(i for i, p in enumerate(phases) if p in ("ROOM", "CORRIDOR")) if "ROOM" in phases else -1
    return last_room < phases.index("BOSS") < phases.index("COOLDOWN") < phases.index("RESULTS")


def run(objective: str = "threshold", duration_min: int = 30, seed: int = 5, profile: str = "moyen",
        trace: Path | None = None) -> Report:
    if objective not in OBJECTIVES:
        raise RunError(f"objectif inconnu : {objective} ({', '.join(OBJECTIVES)})")
    if duration_min not in DURATIONS:
        raise RunError(f"durée inconnue : {duration_min} ({', '.join(map(str, DURATIONS))})")
    if profile not in PROFILES:
        raise RunError(f"profil inconnu : {profile} ({', '.join(PROFILES)})")
    prof = PROFILES[profile]
    rep = Report(objective, duration_min, seed, profile)
    t_wall = time.perf_counter()
    validators = _validators()
    with tempfile.TemporaryDirectory(prefix="openride-rogue-bout-en-bout-") as tmp_s, \
            mock.patch.object(fit_export, "ACTIVITIES_DIR", Path(tmp_s) / "Activities"):
        tmp = Path(tmp_s)
        s, driver, sent = new_session(tmp, prof)
        s._on_command("start_run", {"objective": objective, "duration_min": duration_min, "seed": seed}, 1)
        rg = s.rogue
        rep.add(rg is not None and s.state.session_state == "READY", "run composée (start_run)",
                f"séance {s.state.session_state}, mode {s.state.mode}")
        if rg is None:
            rep.wall_s = time.perf_counter() - t_wall
            return rep
        s._on_command("start", {}, 2)
        rep.add(s.state.session_state == "RUNNING" and s.state.mode == "ROGUE", "run lancée (start)",
                f"séance {s.state.session_state}, mode {s.state.mode}")
        bot = Bot(rg.engine, prof, seed, body=s.physics)
        pressed = {"Z": 0, "A": 0, "gear": 0}
        pause: dict[str, Any] = {}
        results_at: float | None = None
        limit = 3 * duration_min * 60.0
        frames = 0
        while s._t_session < limit and s.state.session_state == "RUNNING":
            e = rg.engine
            bot_step(s, bot, driver, pressed)
            frames += 1
            if not pause and e.phase == "ROOM" and s.physics.s > 0 and e.t_phase >= PAUSE_AFTER_S:
                pause = _pause_and_resume(s, sent)
            if rg.finished and results_at is None:
                results_at = s._t_session
            if results_at is not None and s._t_session - results_at > END_WAIT_S:
                break
        rep.run_s = rg.engine.t_total
        _check_messages(rep, sent, validators)
        _check_run(rep, s, rg, sent, pressed, pause, results_at, limit)
        if s.state.session_state == "RUNNING":       # la séance n'a pas fini d'elle-même : on la termine
            s._on_command("end_session", {"save": True}, 9)
        rep.summary = (s.state.summary or {}).get("rogue")
        summ = rep.summary or {}
        rep.add(summ.get("result") in ("victory", "defeat"), "bilan de la run (summary.rogue)",
                f"résultat {summ.get('result')}, boss {summ.get('boss')}, salles gagnées {summ.get('rooms_won')}"
                f"/{summ.get('rooms_total')}, or {summ.get('gold')}, Perfect Shifts {summ.get('perfect_shifts')}")
        _check_journal(rep, tmp / "journal")
        rep.counts = {"state": frames, **{k: sum(1 for _, m in sent if m.get("type") == k)
                                          for k in ("room", "loot", "input", "error")}}
        if trace is not None:
            trace.parent.mkdir(parents=True, exist_ok=True)
            with trace.open("w", encoding="utf-8") as f:
                for t, m in sent:
                    f.write(json.dumps({"t": round(t, 2), "msg": m}, ensure_ascii=False, separators=(",", ":")) + "\n")
    rep.wall_s = time.perf_counter() - t_wall
    return rep


def new_session(tmp: Path, prof: Any, inputs: list | None = None) -> tuple[CoreSession, MockDriver, list]:
    """Vraie séance du core sur un trainer simulé, journal et profil dans `tmp`, messages vers l'engine relevés."""
    cfg = Config()
    cfg.rider.ftp_w = prof.ftp_w
    cfg.rogue.w_prime_j = prof.w_prime_j
    driver = MockDriver(base_power_w=0.0, ramp_amplitude_w=0.0)
    s = CoreSession(cfg, driver=driver, inputs=inputs or [NullProvider()], journal_dir=tmp / "journal",
                    routes_root=tmp / "routes", workouts_dir=tmp / "workouts", records_path=tmp / "records.json",
                    powerups_path=tmp / "powerups.toml", profile_path=tmp / "profile.json",
                    config_path=tmp / "config.toml")
    sent: list[tuple[float, dict]] = []
    s.server.send_raw = lambda m, max_size=None: sent.append((s._t_session, m))
    s.server.send_input_event = lambda ev: sent.append((s._t_session, {"type": "input", "event": ev}))
    return s, driver, sent


def bot_step(s: CoreSession, bot: Bot, driver: MockDriver, pressed: dict) -> float:
    """Un pas d'une seconde : le cycliste simulé appuie, pédale, puis la séance avance. Renvoie sa puissance."""
    rg = s.rogue
    power, cadence, buttons, _ = bot.decide()
    for _ in range(round(abs(bot.gear - rg.gear))):   # braquet voulu : appuis courts sur + ou −
        s._handle_input(GEAR_PRESS[1 if bot.gear > rg.gear else -1])
        pressed["gear"] = pressed.get("gear", 0) + 1
    for b in sorted(buttons):
        s._handle_input(InputEvent(b))
        pressed[b[0]] = pressed.get(b[0], 0) + 1
    driver.base_power_w, driver.base_cadence_rpm = power, cadence
    s._step(DT, time.monotonic())
    bot.gear = rg.gear                           # braquet imposé (piratage) ou refusé
    s.server.send_state(s.state)
    return power


def _pause_and_resume(s: CoreSession, sent: list) -> dict[str, Any]:
    """Y pendant la salle, une minute de pause, puis `resume` : ce que la pause doit figer est relevé."""
    e = s.rogue.engine
    before = (e.t_total, round(e.wbal.w_bal_j, 1), round(e.firewall.state.gap_m, 1) if e.firewall else None)
    s._handle_input(InputEvent.Y_SHORT)
    paused = s.state.session_state
    grade = s.driver.sim_grade_pct
    for _ in range(int(PAUSE_S / DT)):
        s._step(DT, time.monotonic())
        s.server.send_state(s.state)
    after = (e.t_total, round(e.wbal.w_bal_j, 1), round(e.firewall.state.gap_m, 1) if e.firewall else None)
    n0 = len(sent)
    s._on_command("rogue_resync", {}, 3)
    resync = [m for _, m in sent[n0:]]
    s._on_command("resume", {}, 4)
    return {"paused": paused, "frozen": before == after, "before": before, "after": after, "grade": grade,
            "resumed": s.state.session_state, "resync": resync, "room_id": e.room_id}


def _check_messages(rep: Report, sent: list, validators: dict | None) -> None:
    worst: dict[str, int] = {}
    invalid: list[str] = []
    for _, m in sent:
        kind = m.get("type", "?")
        worst[kind] = max(worst.get(kind, 0), size(m))
        if validators and kind in validators:
            err = next(iter(validators[kind].iter_errors(m)), None)
            if err is not None and len(invalid) < 3:
                invalid.append(f"{kind} : {err.message[:120]}")
    over = [k for k, n in worst.items() if n > (STATE_LIMIT_1_3 if k == "state" else MAX_DATAGRAM_SIZE)]
    rep.add(not over, "messages sous la limite de taille",
            ", ".join(f"{k} {n} o" for k, n in sorted(worst.items())) + (f" ; trop grands : {', '.join(over)}" if over else ""))
    if validators is None:
        rep.add(None, "schémas du contrat", "jsonschema absent : non vérifié")
    else:
        rep.add(not invalid, "trames state, room et loot valides pour les schémas du contrat",
                "; ".join(invalid) or "toutes valides")
    errors = [m for _, m in sent if m.get("type") == "error"]
    rep.add(not errors, "aucune erreur envoyée à l'engine",
            "; ".join(f"{m.get('code')} : {m.get('message')}" for m in errors[:3]) or "aucune")


def _check_run(rep: Report, s: CoreSession, rg: Any, sent: list, pressed: dict, pause: dict,
               results_at: float | None, limit: float) -> None:
    phases: list[str] = []
    for _, m in sent:
        if m.get("type") == "state" and m.get("rogue"):
            p = m["rogue"].get("phase")
            if not phases or phases[-1] != p:
                phases.append(p)
    rep.phases = phases
    rep.add(_phase_order_ok(phases), "phases dans l'ordre (échauffement, salles et couloirs, boss, retour au calme, résultats)",
            " → ".join(_compact(phases)))
    rooms = {m["room_id"] for _, m in sent if m.get("type") == "room"}
    loots = sum(1 for _, m in sent if m.get("type") == "loot")
    rep.add(len(rooms) >= 2 and loots > 0, "salles et offres envoyées à l'engine",
            f"{len(rooms)} salle(s) (boss compris), {loots} message(s) loot")
    summ = rg.engine.summary()
    rep.add(pressed["Z"] > 0 and pressed["A"] > 0 and summ["perfect_shifts"] > 0,
            "appuis du cycliste reçus par la run (Z, A, braquets)",
            f"Z {pressed['Z']}, A {pressed['A']}, braquets {pressed['gear']} ; Perfect Shifts {summ['perfect_shifts']}, "
            f"cartes {len(summ['cards'])}")
    if not pause:
        rep.add(False, "pause par Y dans une salle", "aucune salle de plus de 30 s")
    else:
        b, a = pause["before"], pause["after"]
        rep.add(pause["paused"] == "PAUSED" and pause["frozen"] and pause["grade"] == 0.0 and pause["resumed"] == "RUNNING",
                "pause par Y : run figée, pente relâchée, reprise",
                f"séance {pause['paused']} puis {pause['resumed']} ; temps {b[0]:.0f} → {a[0]:.0f} s, W'bal {b[1]:.0f} → "
                f"{a[1]:.0f} J, mur {b[2]} → {a[2]} m ; pente du trainer {pause['grade']} %")
        rs = pause["resync"]
        rep.add(any(m.get("type") == "room" and m.get("room_id") == pause["room_id"] for m in rs),
                "rogue_resync renvoie la salle en cours", f"{len(rs)} message(s) renvoyé(s)")
    target = rep.duration_min * 60.0
    rep.add(results_at is not None and abs(rep.run_s - target) <= DURATION_TOLERANCE * target,
            f"run jusqu'aux résultats, durée à {DURATION_TOLERANCE:.0%} près",
            f"{rep.run_s / 60:.1f} min pour {rep.duration_min} min demandées" if results_at is not None
            else f"résultats non atteints en {limit / 60:.0f} min (phase {rg.engine.phase})")
    st = s.state.session_state
    rep.add(results_at is not None and st == "FINISHED", "séance terminée d'elle-même après les résultats",
            f"séance {st}" + (f" {s._t_session - results_at:.0f} s après les résultats" if results_at is not None else ""))


def _compact(phases: list[str]) -> list[str]:
    out: list[str] = []
    for p in phases:
        if out and out[-1].split(" ×")[0] == p:
            n = int(out[-1].split(" ×")[1]) + 1 if " ×" in out[-1] else 2
            out[-1] = f"{p} ×{n}"
        else:
            out.append(p)
    return out


def _check_journal(rep: Report, journal_dir: Path) -> None:
    files = sorted(journal_dir.glob("*.jsonl"))
    if not files:
        rep.add(False, "journal de la run", "aucun journal écrit")
        return
    lines = list(read_journal(files[-1]))
    kinds = {ln.get("kind") for ln in lines}
    snaps = [ln for ln in lines if ln.get("kind") == "rogue_snapshot"]
    run_line = next((ln for ln in lines if ln.get("kind") == "rogue_run"), None)
    modes = {ln.get("mode") for ln in lines if ln.get("kind") == "record"}
    ok = run_line is not None and len(snaps) >= 4 and modes == {"ROGUE"} and "rogue" in kinds
    rep.add(ok, "journal : ligne rogue_run, instantanés des phases, enregistrements ROGUE",
            f"{len(lines)} lignes, {len(snaps)} instantané(s), rogue_run "
            f"{'présente' if run_line else 'absente'}, modes {sorted(m for m in modes if m)}")


def format_text(reps: list[Report]) -> str:
    out = []
    for r in reps:
        out.append(f"Run {r.objective} {r.duration_min} min, graine {r.seed}, profil {r.profile} : "
                   f"{r.run_s / 60:.1f} min de run calculées en {r.wall_s:.1f} s")
        for ok, label, detail in r.checks:
            tag = "INFO" if ok is None else ("OK" if ok else "ÉCHEC")
            out.append(f"  [{tag}] {label} : {detail}")
        if r.counts:
            out.append("  messages : " + ", ".join(f"{k} {n}" for k, n in r.counts.items()))
        out.append(f"{r.objective} : {'OK' if r.ok else 'ÉCHEC'}")
    return "\n".join(out) + "\n"


def to_json(r: Report) -> dict:
    return {"objective": r.objective, "duration_min": r.duration_min, "seed": r.seed, "profile": r.profile,
            "ok": r.ok, "run_s": round(r.run_s, 1), "wall_s": round(r.wall_s, 2), "phases": _compact(r.phases),
            "summary": r.summary, "counts": r.counts,
            "checks": [{"ok": ok, "label": label, "detail": d} for ok, label, d in r.checks]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run Cyber-Rogue de bout en bout dans la séance du core (lot X40).")
    ap.add_argument("--objective", default="threshold", help=f"{', '.join(OBJECTIVES)} ou tous")
    ap.add_argument("--duration", type=int, default=30, help="durée de la run en minutes (30, 45, 60, 90)")
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--profil", default="moyen", help=f"cycliste simulé : {', '.join(PROFILES)}")
    ap.add_argument("--trace", type=Path, help="messages envoyés à l'engine, un par ligne (banc visuel, lot X41) ; "
                                               "avec « tous », un fichier par objectif à côté")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    objectives = list(OBJECTIVES) if args.objective == "tous" else [args.objective]
    reps = []
    try:
        for obj in objectives:
            trace = args.trace
            if trace is not None and len(objectives) > 1:
                trace = trace.with_name(f"{trace.stem}_{obj}{trace.suffix}")
            reps.append(run(obj, args.duration, args.seed, args.profil, trace))
    except RunError as exc:
        print(f"ÉCHEC : {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps([to_json(r) for r in reps], ensure_ascii=False, indent=2))
    else:
        print(format_text(reps), end="")
    return 0 if all(r.ok for r in reps) else 1


if __name__ == "__main__":
    sys.exit(main())
