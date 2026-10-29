"""Mode ROGUE dans la session du core (lot R8) : tout ce que la session branche sur le moteur de run.

`CoreSession` ne garde que de petits points d'entrée ; la logique est ici, testable sans trainer :
validation de `start_run`, entrées (boutons, braquets), pas de run, rampe de pente, messages `room` et
`loot`, lignes du journal, reprise après un plantage.

Un pas de run (`RogueMode.step`) est appelé à chaque tour de la boucle à 50 Hz seulement quand la séance
est `RUNNING` : en pause (Y, Échap, engine perdu, journal en panne) il n'est pas appelé, donc le moteur de
run, le Firewall, les fenêtres de temps et W'bal sont figés.
"""

from __future__ import annotations

import base64
import random
import zlib
from dataclasses import dataclass
from typing import Any

from ..config import Config
from ..physics import PhysicsParams, RiderPhysics
from .balance import DEFAULT_BALANCE, RogueBalance, balance_hash
from .combat import apply_gear_buttons
from .progress import DEFAULT_CHASSIS, Chassis, ChassisError, RogueStats, apply_chassis, choose_chassis, run_event
from .rooms import OBJECTIVES, RoomRider
from .run import RunEngine, RunInputs, RunOutputs
from .scenario import compose_run

DURATIONS = (30, 45, 60, 90)
SNAPSHOT_PHASES = ("WARMUP", "ROOM", "CORRIDOR", "BOSS", "COOLDOWN")
FIGHT_PHASES = ("ROOM", "BOSS")
GEAR_BUTTONS = ("PLUS_SHORT", "MINUS_SHORT", "PLUS_LONG", "MINUS_LONG")
GAME_BUTTONS = ("Z_SHORT", "Z_LONG", "A_SHORT", "A_LONG")
KEPT_MESSAGES = 12                      # messages `room` et `loot` gardés pour `rogue_resync`
JOURNAL_ROUTE_ID = "rogue"              # parcours inscrit au journal d'une run (la trame `state` porte route_id null)
RESULTS_HOLD_S = 3.0                    # phase RESULTS montée à l'engine (jingle de fin) avant FINISHED et le bilan


class RunInvalid(ValueError):
    """`start_run` refusé ; `code` est le code d'erreur du contrat (`run_invalid`, `item_locked`)."""

    def __init__(self, message: str, code: str = "run_invalid") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RunRequest:
    objective: str
    duration_min: int
    seed: int
    w_prime_j: float
    chassis: str


def _number(value: Any, name: str, lo: float, hi: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
        raise RunInvalid(f"{name} : un nombre est attendu")
    if not lo <= value <= hi:
        raise RunInvalid(f"{name} : {value} hors de {lo:g} à {hi:g}")
    return float(value)


def parse_start_run(args: Any, cfg: Config, rng: random.Random | None = None) -> RunRequest:
    """Arguments de `start_run` vérifiés ; `RunInvalid` sinon. `seed` nul : tirée au hasard ; `w_prime_j` nul : `[rogue]`."""
    if not isinstance(args, dict):
        raise RunInvalid("arguments absents")
    objective = args.get("objective")
    if objective not in OBJECTIVES:
        raise RunInvalid(f"objectif « {objective} » hors liste ({', '.join(OBJECTIVES)})")
    duration = args.get("duration_min")
    if isinstance(duration, bool) or duration not in DURATIONS:
        raise RunInvalid(f"durée {duration!r} hors liste ({', '.join(map(str, DURATIONS))} min)")
    seed = args.get("seed")
    if seed is None:
        seed = (rng or random.Random()).randrange(1, 2**31 - 1)
    elif isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**31:
        raise RunInvalid(f"graine {seed!r} : un entier de 0 à 2^31 est attendu")
    w_prime = args.get("w_prime_j")
    w_prime = cfg.rogue.w_prime_j if w_prime is None else _number(w_prime, "w_prime_j", 5000.0, 60000.0)
    chassis = args.get("chassis", DEFAULT_CHASSIS)
    if chassis is None:
        chassis = DEFAULT_CHASSIS
    if not isinstance(chassis, str):
        raise RunInvalid("chassis : un identifiant est attendu")
    return RunRequest(objective, int(duration), int(seed), float(w_prime), chassis)


def hello_block(cfg: Config, w_prime_estimate_j: float | None, chassis: tuple[Chassis, ...] | None = None,
                stats: RogueStats | None = None, lives: int | None = None) -> dict:
    """Objet `hello_ack.config.rogue` (contrat 1.4 et lot R9)."""
    from .progress import config_block

    block: dict[str, Any] = {
        "w_prime_j": cfg.rogue.w_prime_j, "w_prime_estimate_j": w_prime_estimate_j,
        "cp_w": cfg.rogue.cp_w or cfg.rider.ftp_w, "objectives": list(OBJECTIVES), "durations_min": list(DURATIONS)}
    if chassis is not None and stats is not None:
        block.update(config_block(chassis, stats, DEFAULT_CHASSIS, lives or 0))
    return block


def journal_line(text: str, ts: float, t: float) -> dict | None:
    """Ligne `rogue` du journal d'après une ligne du moteur de run (`rogue room id=3 ...`)."""
    parts = text.split()
    if len(parts) < 2 or parts[0] != "rogue":
        return None
    name = parts[1]
    fields: dict[str, Any] = {}
    for tok in parts[2:]:
        if "=" in tok:
            k, v = tok.split("=", 1)
            if k == "hash":
                fields[k] = v
                continue
            fields[k] = float(v) if v.replace(".", "", 1).lstrip("-").isdigit() and "." in v else (
                int(v) if v.lstrip("-").isdigit() else v)
    event = {"room": "room_start", "defeat": "defeat", "card": "card_taken", "results": "run_end",
             "room_skipped": "room_skipped", "life_used": "life_used", "balance": "balance"}.get(name)
    if name == "room_end":
        event = {"won": "room_won", "fled": "room_fled"}.get(str(fields.get("outcome")), "room_end")
    elif name == "phase":
        event = "boss_phase" if fields.get("phase") == "BOSS" else "phase"
    if event is None:
        return None
    return {"kind": "rogue", "event": event, "ts": round(ts, 3), "t": round(t, 2), **fields}


class RogueMode:
    """Une run en cours dans la session."""

    def __init__(self, cfg: Config, request: RunRequest, balance: RogueBalance = DEFAULT_BALANCE,
                 chassis: Chassis | None = None, lives: int = 0, params: PhysicsParams | None = None) -> None:
        self.cfg, self.request, self.chassis_id = cfg, request, chassis.id if chassis else DEFAULT_CHASSIS
        self.balance = apply_chassis(balance, chassis) if chassis else balance
        ftp = cfg.rider.ftp_w
        self.rider = RoomRider(ftp_w=ftp, params=params or PhysicsParams.from_config(cfg))
        cp = cfg.rogue.cp_w or ftp
        scenario = compose_run(request.objective, request.duration_min, request.seed, self.rider, self.balance)
        self.engine = RunEngine(scenario, self.rider, request.w_prime_j, cp, self.balance, lives=lives)
        self.gear = self.balance.gear_ref
        self.buttons: set[str] = set()
        self.shift_pending = False
        self.grade_sent = 0.0
        self.room_id = 0
        self.phase = ""
        self.sent: list[dict] = []          # messages `room` et `loot` récents, renvoyés par `rogue_resync`
        self.out: RunOutputs | None = None
        self.results_s = 0.0                # temps passé en RESULTS ; la séance se termine après RESULTS_HOLD_S
        self.hash = balance_hash(self.balance)

    # --- entrées ------------------------------------------------------------------------------

    def press(self, event: str) -> None:
        """Bouton de jeu (Z, A) : pris en compte au prochain pas de run."""
        if event in GAME_BUTTONS:
            self.buttons.add(event)

    def shift(self, event: str) -> bool:
        """Bouton de braquet (+, −, courts et longs) : appliqué tout de suite, piratage respecté."""
        if event not in GEAR_BUTTONS:
            return False
        cs = self.engine.combat
        hack, forced = (cs.hack_kind, cs.forced_gear) if cs is not None else (None, None)
        new = apply_gear_buttons(self.gear, (event,), hack, forced, self.balance)
        self.shift_pending = new != self.gear or self.shift_pending
        self.gear = new
        return True

    # --- pas de run ---------------------------------------------------------------------------

    @property
    def in_fight(self) -> bool:
        return self.engine.room is not None and self.engine.phase in FIGHT_PHASES

    def step(self, dt: float, power_w: float, cadence_rpm: float, physics: RiderPhysics, input_lost: bool,
             ts: float) -> tuple[RunOutputs, list[dict]]:
        """Un pas à `dt` s. Rend les sorties du moteur et les lignes à écrire au journal.

        La distance de la salle est celle de `physics.s` : remise à zéro hors des salles, de sorte que
        chaque salle commence à 0 m ; la vitesse, elle, continue d'une salle à l'autre.
        """
        e = self.engine
        fight = self.in_fight
        inp = RunInputs(power_w=power_w, cadence_rpm=cadence_rpm, gear=self.gear, ftp_w=self.cfg.rider.ftp_w,
                        s_m=physics.s if fight else 0.0, v_mps=physics.v, buttons=frozenset(self.buttons),
                        input_lost=input_lost)
        self.buttons.clear()
        out = e.step(dt, inp)
        self.out = out
        if out.force_gear:
            self.gear = out.force_gear
            self.shift_pending = True
        physics.step(power_w, out.grade_enemy, 0.0, dt)       # vitesse virtuelle sur la pente de l'ennemi
        new_room = e.room_id != self.room_id
        if new_room or not (e.room is not None and e.phase in FIGHT_PHASES):
            physics.s = 0.0
        lines = [ln for ln in (journal_line(t, ts, e.t_total) for t in out.journal) if ln]
        lines += [{"kind": "rogue", "event": "perfect_shift", "ts": round(ts, 3), "t": round(e.t_total, 2)}
                  for ev in out.rogue["events"] if ev == "perfect_shift"]
        self.sent += out.messages
        del self.sent[:-KEPT_MESSAGES]
        if (out.phase != self.phase or new_room) and out.phase in SNAPSHOT_PHASES:
            lines.append(self.snapshot_line(ts))
        self.phase, self.room_id = out.phase, e.room_id
        if self.finished:
            self.results_s += dt
        return out, lines

    def target_grade(self, rate_up: float, rate_down: float, dt: float) -> tuple[float, bool]:
        """Pente envoyée après la rampe propre au mode ; immédiate au changement de braquet."""
        out = self.out
        target = out.grade_sent if out is not None else 0.0
        shifted, self.shift_pending = self.shift_pending, False
        if shifted:
            self.grade_sent = target
        else:
            rate = rate_up if target >= self.grade_sent else rate_down
            self.grade_sent += min(max(target - self.grade_sent, -rate * dt), rate * dt)
        return self.grade_sent, shifted

    # --- fin, reprise -------------------------------------------------------------------------

    @property
    def finished(self) -> bool:
        return self.engine.phase == "RESULTS"

    @property
    def done(self) -> bool:
        """Résultats montrés assez longtemps : la séance passe en FINISHED avec le bilan (lot X40)."""
        return self.results_s >= RESULTS_HOLD_S

    def summary(self) -> dict:
        """Bilan `summary.rogue` ; `abandoned` si la run n'a pas atteint les résultats."""
        if not self.finished:
            return self.engine.abandon()
        return self.engine.summary()

    def run_line(self, ts: float) -> dict:
        """Ligne `rogue_run` du journal : expérience, pièces, châssis et statistiques la lisent (V2, V3b, R9)."""
        line = run_event(self.engine.summary() if self.finished else self.summary(), self.engine.t_total / 60.0,
                         self.engine.lives_used, self.chassis_id)
        return {**line, "ts": round(ts, 3)}

    def snapshot_line(self, ts: float) -> dict:
        data = base64.b64encode(zlib.compress(self.engine.snapshot(), 6)).decode("ascii")
        return {"kind": "rogue_snapshot", "ts": round(ts, 3), "t": round(self.engine.t_total, 2),
                "gear": self.gear, "chassis": self.chassis_id, "data": data,
                "req": {"objective": self.request.objective, "duration_min": self.request.duration_min,
                        "seed": self.request.seed, "w_prime_j": self.request.w_prime_j}}

    def restore(self, line: dict) -> None:
        """Reprend au début de la phase du dernier instantané (salle en cours : bouclier, or, deck de son début)."""
        self.engine.restore(zlib.decompress(base64.b64decode(line["data"])))
        self.gear = int(line.get("gear", self.gear))
        self.room_id = self.engine.room_id
        self.phase = self.engine.phase
        self.grade_sent = 0.0
        self.buttons.clear()

    def resync(self) -> list[dict]:
        """Messages `room` et `loot` récents, pour `rogue_resync`."""
        return list(self.sent)


def choose(chassis_table: tuple[Chassis, ...] | None, stats: RogueStats | None, chassis_id: str) -> Chassis | None:
    """Châssis demandé ; sans table de progression, seul le standard existe. Lève `RunInvalid`."""
    if chassis_table is None or stats is None:
        if chassis_id != DEFAULT_CHASSIS:
            raise RunInvalid(f"châssis « {chassis_id} » indisponible (progression absente)", "item_locked")
        return None
    try:
        return choose_chassis(chassis_table, stats, chassis_id)
    except ChassisError as exc:
        raise RunInvalid(str(exc), exc.code) from None
