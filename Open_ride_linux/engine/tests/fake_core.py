#!/usr/bin/env python3
"""Faux core OpenRide pour tester l'engine sans écran (lot D6, audit F9).

Bibliothèque standard seulement. Le faux core :
- écoute le port de commandes (hello, heartbeat, cmd, bye) et répond comme le vrai core
  (hello_ack, remise à zéro de last_cmd_id à chaque hello) ;
- envoie des trames `state` à 30 Hz au format de core/src/openride_core/ipc_server.py ;
- rejoue les scénarios du lot D et lit le journal de l'engine (lignes « [test] clé=valeur »,
  voir engine/tests/README.md) pour vérifier ses réactions.

Usage : fake_core.py --engine-log FICHIER [--state-port 5005] [--cmd-port 5006] [--scenarios 1,2,…]
Code de sortie : 0 si tous les scénarios passent, 1 sinon.
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

CONTRACT_VERSION = 1
STATE_HZ = 30.0
SPEED_MPS = 8.0


def now() -> float:
    return time.monotonic()


@dataclass
class Received:
    t: float
    msg: dict[str, Any]


class EngineLog:
    """Lit au fil de l'eau le journal de l'engine et garde les lignes « [test] » horodatées."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lines: list[tuple[float, str]] = []
        self._pos = 0
        self._partial = ""

    def poll(self) -> None:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(self._pos)
            chunk = fh.read()
            self._pos = fh.tell()
        if not chunk:
            return
        data = self._partial + chunk
        parts = data.split("\n")
        self._partial = parts.pop()
        t = now()
        for line in parts:
            if line.startswith("[test] "):
                self.lines.append((t, line[len("[test] "):]))

    def mark(self) -> int:
        self.poll()
        return len(self.lines)

    def since(self, mark: int) -> list[tuple[float, str]]:
        self.poll()
        return self.lines[mark:]

    def wait_for(self, pattern: str, timeout: float, mark: int = 0) -> tuple[float, re.Match[str]] | None:
        rx = re.compile(pattern)
        deadline = now() + timeout
        idx = mark
        while True:
            self.poll()
            while idx < len(self.lines):
                t, line = self.lines[idx]
                idx += 1
                m = rx.search(line)
                if m:
                    return t, m
            if now() > deadline:
                return None
            time.sleep(0.01)


@dataclass
class FakeCore:
    state_port: int
    cmd_port: int
    log: EngineLog
    received: list[Received] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)
    # Comportement réglable par les scénarios.
    streaming: bool = False
    silent: bool = False          # core muet : n'émet plus rien du tout
    auto_hello_ack: bool = False
    session_state: str = "IDLE"
    route_id: str | None = "demo"
    accept_cmd: Callable[[dict[str, Any], int], bool] = lambda msg, count: True
    difficulty_pct: int = 50
    seq: int = 0
    last_cmd_id: int = 0
    _cmd_counts: dict[int, int] = field(default_factory=dict)
    _s0: float = 0.0
    _t0: float = field(default_factory=now)
    _stop: bool = False

    def start(self) -> None:
        self.rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rx.bind(("127.0.0.1", self.cmd_port))
        self.rx.settimeout(0.05)
        self.tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        threading.Thread(target=self._rx_loop, daemon=True).start()
        threading.Thread(target=self._state_loop, daemon=True).start()

    def stop(self) -> None:
        self._stop = True

    # --- émission ------------------------------------------------------------------------

    def send(self, msg: dict[str, Any]) -> None:
        if self.silent:
            return
        self.tx.sendto(json.dumps(msg, separators=(",", ":")).encode("utf-8"),
                       ("127.0.0.1", self.state_port))

    def current_s(self) -> float:
        if self.session_state != "RUNNING":
            return self._s0
        return self._s0 + SPEED_MPS * (now() - self._t0)

    def set_running(self, running: bool) -> None:
        self._s0 = self.current_s()
        self._t0 = now()
        self.session_state = "RUNNING" if running else "READY"

    def state_msg(self, seq: int | None = None, s: float | None = None) -> dict[str, Any]:
        running = self.session_state == "RUNNING"
        return {
            "type": "state", "v": SPEED_MPS if running else 0.0,
            "seq": self.seq if seq is None else seq, "t": now() - self._t0,
            "session_state": self.session_state, "pause_reason": None,
            "trainer_status": "MOCK", "input_status": "KEYBOARD", "mode": "SIM",
            "route_id": self.route_id, "route_length_m": None,
            "s": self.current_s() if s is None else s,
            "grade": 0.0, "grade_sent": 0.0, "difficulty_pct": self.difficulty_pct, "power": 200.0, "power_3s": 200.0, "cadence": 85.0,
            "hr": None, "gear": 12, "gears_total": 24, "lat": 0.0, "lon": 0.0, "alt": 0.0,
            "erg": None, "summary": None, "last_cmd_id": self.last_cmd_id,
        }

    def send_state(self) -> None:
        self.seq += 1
        self.send(self.state_msg())

    def _state_loop(self) -> None:
        period = 1.0 / STATE_HZ
        nxt = now()
        while not self._stop:
            if self.streaming and not self.silent:
                with self.lock:
                    self.send_state()
            nxt += period
            time.sleep(max(0.0, nxt - now()))

    # --- réception -----------------------------------------------------------------------

    def _rx_loop(self) -> None:
        while not self._stop:
            try:
                data, _ = self.rx.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                return
            try:
                msg = json.loads(data.decode("utf-8"))
            except ValueError:
                continue
            with self.lock:
                self.received.append(Received(now(), msg))
                self._handle(msg)

    def _handle(self, msg: dict[str, Any]) -> None:
        kind = msg.get("type")
        if kind == "hello" and not self.silent:
            self.last_cmd_id = 0      # comme le vrai core (contrat §4)
            self._cmd_counts.clear()
            if self.auto_hello_ack:
                self.send_hello_ack()
        elif kind == "cmd" and not self.silent:
            cmd_id = int(msg.get("cmd_id", 0))
            name = str(msg.get("name", ""))
            count = self._cmd_counts.get(cmd_id, 0) + 1
            self._cmd_counts[cmd_id] = count
            if cmd_id > self.last_cmd_id and self.accept_cmd(msg, count):
                self.last_cmd_id = cmd_id

            if getattr(self, "catalog_data", None):
                if name == "list_routes":
                    if not getattr(self, "drop_all_catalog", False):
                        if getattr(self, "drop_first_catalog", False) and "routes" not in getattr(self, "_dropped_lists", set()):
                            self._dropped_lists.add("routes")
                        else:
                            self.send_list("routes", cmd_id, self.catalog_data.get("routes", []))
                elif name == "list_workouts":
                    if not getattr(self, "drop_all_catalog", False):
                        if getattr(self, "drop_first_catalog", False) and "workouts" not in getattr(self, "_dropped_lists", set()):
                            self._dropped_lists.add("workouts")
                        else:
                            self.send_list("workouts", cmd_id, self.catalog_data.get("workouts", []))
                elif name == "select_route":
                    args = msg.get("args", {})
                    self.route_id = str(args.get("route_id", self.route_id))
                elif name == "select_workout":
                    args = msg.get("args", {})
                    self.workout_id = args.get("workout_id")
                elif name == "start":
                    self.set_running(True)
                elif name == "set_difficulty":
                    args = msg.get("args", {})
                    pct = args.get("pct")
                    if isinstance(pct, (int, float)):
                        self.difficulty_pct = int(round(max(0, min(100, pct))))

    def send_list(self, kind: str, cmd_id: int, items: list) -> None:
        """Réponse `routes` ou `workouts` (contrat v1.1 §4), en deux parties avec --split-catalog.

        Avec --split-catalog, la partie 2 part avant la partie 1 pour vérifier l'assemblage de l'engine.
        """
        if getattr(self, "split_catalog", False) and len(items) >= 2:
            half = len(items) // 2
            chunks = [(2, items[half:]), (1, items[:half])]
        else:
            chunks = [(1, items)]
        for part, chunk in chunks:
            self.send({"type": kind, "v": CONTRACT_VERSION, "request_cmd_id": cmd_id,
                       "part": part, "parts": len(chunks), "items": chunk, "truncated": False})

    def send_hello_ack(self) -> None:
        self.send({"type": "hello_ack", "v": CONTRACT_VERSION, "core_version": "fake",
                   "config": {"ftp_w": 250, "gears_total": 24, "theme": "default",
                              "difficulty_pct": self.difficulty_pct}})

    def messages(self, kind: str, since: float = 0.0, name: str | None = None) -> list[Received]:
        with self.lock:
            return [r for r in self.received if r.msg.get("type") == kind and r.t >= since
                    and (name is None or r.msg.get("name") == name)]

    def test_command(self, name: str, args: dict[str, Any] | None = None) -> None:
        """Demande à l'engine (lancé avec --test-mode) d'envoyer une commande."""
        self.send({"type": "_test", "v": CONTRACT_VERSION, "action": "send_command",
                   "name": name, "args": args or {}})


# --- scénarios -------------------------------------------------------------------------------

class ScenarioFailed(Exception):
    pass


def check(cond: bool, message: str) -> None:
    if not cond:
        raise ScenarioFailed(message)


def last_banner(core: FakeCore, mark: int = 0) -> str | None:
    text = None
    for _t, line in core.log.since(mark):
        if line.startswith("banner text="):
            text = line[len("banner text="):]
    return text


def scenario_hello(core: FakeCore) -> str:
    """1. hello répété jusqu'au hello_ack, puis arrêt des hello."""
    deadline = now() + 6.0
    while len(core.messages("hello")) < 3 and now() < deadline:
        time.sleep(0.05)
    hellos = core.messages("hello")
    check(len(hellos) >= 3, f"seulement {len(hellos)} hello en 6 s")
    gaps = [b.t - a.t for a, b in zip(hellos[-3:], hellos[-2:])]
    check(all(0.7 <= g <= 1.3 for g in gaps), f"hello non espacés d'1 s : {gaps}")
    mark = core.log.mark()
    with core.lock:
        core.send_hello_ack()
    t_ack = now()
    core.auto_hello_ack = True
    core.streaming = True
    check(core.log.wait_for(r"^hello_ack config=.*gears_total", 2.0, mark) is not None,
          "hello_ack non journalisé par l'engine")
    time.sleep(2.5)
    late = core.messages("hello", since=t_ack + 0.1)
    check(not late, f"{len(late)} hello encore envoyés après le hello_ack")
    return f"{len(hellos)} hello espacés de {gaps[-1]:.2f} s, aucun après le hello_ack"


def scenario_retry(core: FakeCore) -> str:
    """2. Commande ignorée trois fois : renvoyée, puis acquittée."""
    core.accept_cmd = lambda msg, count: msg.get("name") != "pause" or count >= 4
    mark = core.log.mark()
    t0 = now()
    core.test_command("pause")
    hit = core.log.wait_for(r"^cmd_acked name=pause id=(\d+) sends=(\d+)", 3.0, mark)
    check(hit is not None, "commande « pause » jamais acquittée")
    time.sleep(0.6)
    sends = core.messages("cmd", since=t0, name="pause")
    check(len(sends) == 4, f"{len(sends)} envois reçus au lieu de 4")
    gaps = [b.t - a.t for a, b in zip(sends, sends[1:])]
    check(all(0.15 <= g <= 0.30 for g in gaps), f"renvois mal espacés : {gaps}")
    check(len({r.msg["cmd_id"] for r in sends}) == 1, "cmd_id changé entre les renvois")
    core.accept_cmd = lambda msg, count: True
    return f"4 envois (écarts {', '.join(f'{g:.2f}' for g in gaps)} s), acquittée, plus de renvoi"


def scenario_timeout(core: FakeCore) -> str:
    """3. Commande jamais acquittée : abandon au bout de 3 s ± 0,3 s, signal émis."""
    core.accept_cmd = lambda msg, count: msg.get("name") != "resume"
    mark = core.log.mark()
    t0 = now()
    core.test_command("resume")
    hit = core.log.wait_for(r"^cmd_failed name=resume id=\d+ after_ms=(\d+)", 4.5, mark)
    check(hit is not None, "aucun abandon de « resume » en 4,5 s")
    after_ms = int(hit[1].group(1))
    check(2700 <= after_ms <= 3300, f"abandon après {after_ms} ms")
    banner = core.log.wait_for(r"^banner text=.*resume", 1.0, mark)
    check(banner is not None, "pas de message à l'écran pour la commande abandonnée")
    time.sleep(0.5)
    sends = core.messages("cmd", since=t0, name="resume")
    check(sends[-1].t - sends[0].t <= 3.3, "renvois après l'abandon")
    core.accept_cmd = lambda msg, count: True
    return f"abandon après {after_ms} ms, {len(sends)} envois, bandeau affiché"


def scenario_out_of_order(core: FakeCore) -> str:
    """6. Trames state en désordre : seule la plus récente est appliquée."""
    core.streaming = False
    time.sleep(0.1)
    mark = core.log.mark()
    with core.lock:
        base = core.seq
        s = core.current_s()
        core.send(core.state_msg(seq=base + 1, s=s))
        core.send(core.state_msg(seq=base + 3, s=s + 0.6))
        core.send(core.state_msg(seq=base + 2, s=s + 0.3))
        core.seq = base + 3
    check(core.log.wait_for(rf"^state_late seq={base + 2}\b", 1.0, mark) is not None,
          "trame en retard non signalée comme ignorée")
    applied = [ln for _t, ln in core.log.since(mark) if ln.startswith("state seq=")]
    seqs = [int(re.match(r"state seq=(\d+)", ln).group(1)) for ln in applied]
    check(base + 2 not in seqs, f"trame {base + 2} appliquée malgré son retard")
    check(seqs[-1:] == [base + 3], f"dernière trame appliquée : {seqs}")
    core.streaming = True
    return f"trames {base + 1}, {base + 3} appliquées, {base + 2} ignorée"


def scenario_error(core: FakeCore) -> str:
    """7. Trame error : le bandeau contient le code."""
    mark = core.log.mark()
    with core.lock:
        core.send({"type": "error", "v": CONTRACT_VERSION, "code": "route_invalid",
                   "message": "parcours de test illisible"})
    hit = core.log.wait_for(r"^banner text=.*route_invalid", 1.0, mark)
    check(hit is not None, "le bandeau ne montre pas le code route_invalid")
    return "bandeau : " + hit[1].string[len("banner text="):]


def scenario_core_silent(core: FakeCore) -> str:
    """4. Faux core muet 1,5 s : bandeau, extrapolation ≤ 1 s puis caméra figée, reprise."""
    with core.lock:
        core.set_running(True)
    time.sleep(1.0)
    mark = core.log.mark()
    with core.lock:
        core.silent = True
    time.sleep(1.5)
    with core.lock:
        core.silent = False
    t_back = now()
    check(core.log.wait_for(r"^banner text=.*non joignable", 0.1, mark) is not None,
          "bandeau « core non joignable » absent")
    returned = core.log.wait_for(r"^core_returned", 1.0, mark)
    check(returned is not None, "reprise des trames non vue par l'engine")
    time.sleep(0.5)
    cams = []
    for _t, ln in core.log.since(mark):
        m = re.match(r"cam s=([\d.]+) age_ms=(\d+) frozen=(\d) moved=(\d)", ln)
        if m:
            cams.append((float(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))))
    silent_cams = [c for c in cams if c[1] >= 200]
    check(len(silent_cams) >= 10, f"trop peu de positions de caméra pendant le silence ({len(silent_cams)})")
    moved_ages = [c[1] for c in silent_cams if c[3]]
    last_move_ms = max(moved_ages) if moved_ages else 0
    check(last_move_ms <= 1100, f"caméra encore en mouvement {last_move_ms} ms après la dernière trame")
    early = [c[0] for c in silent_cams if c[1] <= 400]
    late = [c[0] for c in silent_cams if 900 <= c[1] <= 1000]
    check(bool(early) and bool(late) and late[0] - early[0] >= SPEED_MPS * 0.4,
          "pas d'extrapolation pendant la première seconde de silence")
    frozen = [c for c in silent_cams if c[1] > 1100]
    check(bool(frozen) and all(c[2] == 1 and c[3] == 0 for c in frozen), "caméra non figée après 1,1 s")
    check(all(b[0] >= a[0] for a, b in zip(cams, cams[1:])), "la caméra a reculé")
    banner = last_banner(core, mark) or ""
    check("non joignable" not in banner, f"bandeau encore affiché après la reprise : {banner!r}")
    return (f"bandeau affiché ; dernier mouvement {last_move_ms} ms après la dernière trame, "
            f"figée ensuite ; reprise vue {returned[0] - t_back:.2f} s après, bandeau retiré")


def scenario_shutdown(core: FakeCore) -> str:
    """5. shutdown : l'engine ne quitte pas et renvoie des hello."""
    mark = core.log.mark()
    with core.lock:
        core.send({"type": "shutdown", "v": CONTRACT_VERSION})
        core.silent = True
        core.streaming = False
    t0 = now()
    check(core.log.wait_for(r"^banner text=.*Le core s'est arrêté", 1.0, mark) is not None,
          "bandeau « Le core s'est arrêté » absent")
    time.sleep(2.6)
    hellos = core.messages("hello", since=t0)
    beats = core.messages("heartbeat", since=now() - 1.0)
    check(len(hellos) >= 2, f"{len(hellos)} hello après le shutdown")
    check(len(beats) >= 1, "plus de heartbeat : l'engine a quitté ?")
    # Nouveau core : seq repart de zéro.
    with core.lock:
        core.seq = 0
        core.silent = False
        core.streaming = True
    hit = core.log.wait_for(r"^state seq=[1-9]\d? ", 2.5, mark)
    check(hit is not None, "trames du nouveau core (seq remis à 0) non appliquées")
    time.sleep(1.2)
    banner = last_banner(core, mark) or ""
    check("arrêté" not in banner and "non joignable" not in banner, f"bandeau resté : {banner!r}")
    return f"{len(hellos)} hello en 2,6 s, heartbeats continus, nouveau core accepté (seq repart à 1)"


def scenario_heartbeat(core: FakeCore) -> str:
    """8. Heartbeats à 2 Hz ± 20 % pendant 10 s."""
    t0 = now()
    time.sleep(10.0)
    beats = core.messages("heartbeat", since=t0)
    rate = len(beats) / 10.0
    check(1.6 <= rate <= 2.4, f"{len(beats)} heartbeats en 10 s ({rate:.2f} Hz)")
    gaps = [b.t - a.t for a, b in zip(beats, beats[1:])]
    return f"{len(beats)} heartbeats en 10 s ({rate:.2f} Hz, écart max {max(gaps):.2f} s)"


SCENARIOS: dict[int, tuple[str, Callable[[FakeCore], str]]] = {
    1: ("hello jusqu'au hello_ack", scenario_hello),
    2: ("commande renvoyée puis acquittée", scenario_retry),
    3: ("commande abandonnée après 3 s", scenario_timeout),
    4: ("core injoignable", scenario_core_silent),
    5: ("shutdown du core", scenario_shutdown),
    6: ("trames en désordre", scenario_out_of_order),
    7: ("trame error", scenario_error),
    8: ("heartbeats à 2 Hz", scenario_heartbeat),
}
# Ordre d'exécution : le scénario 1 exige un engine qui vient de démarrer.
RUN_ORDER = [1, 2, 3, 6, 7, 4, 5, 8]

REFERENCE_ERG_BLOCKS: list[tuple[str, float, int, int | None]] = [
    ("warmup", 600.0, 125, 238),
    ("steady", 1200.0, 238, 300),
    ("interval_on", 60.0, 300, 125),
    ("interval_off", 60.0, 125, 300),
    ("interval_on", 60.0, 300, 125),
    ("interval_off", 60.0, 125, 300),
    ("interval_on", 60.0, 300, 125),
    ("interval_off", 60.0, 125, 0),
    ("freeride", 120.0, 0, 175),
    ("cooldown", 300.0, 175, None),
]


def run_erg_workout_stream(state_port: int, cmd_port: int) -> int:
    """Émet les trames `state` avec `erg` pour les 10 blocs de référence du lot F (lot I6 §4.2)."""
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("127.0.0.1", cmd_port))
    rx.settimeout(5.0)
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Attend le signal de démarrage (« hello ») du script de test Godot
        rx.recvfrom(4096)
    except TimeoutError:
        print("fake_core --erg-workout : aucun hello reçu sur le port de commandes", file=sys.stderr)
        return 1
    finally:
        rx.close()

    dt = 1.0 / STATE_HZ
    seq = 0
    sim_t = 0.0

    def send_workout_pass(workout_name: str, pause_block_idx: int | None) -> None:
        nonlocal seq, sim_t
        n_blocks = len(REFERENCE_ERG_BLOCKS)
        for idx, (b_type, b_total, target_w, next_w) in enumerate(REFERENCE_ERG_BLOCKS, start=1):
            # Pour chaque bloc (tous >= 60 s), on émet les 4,5 dernières secondes à 30 Hz
            steps = int(round(4.5 * STATE_HZ))
            for step in range(steps):
                rem_s = round(max(4.5 - step * dt, 0.0), 2)
                paused = (pause_block_idx == idx and rem_s <= 3.1)
                seq += 1
                sim_t += dt
                frame = {
                    "v": SPEED_MPS,
                    "type": "state",
                    "seq": seq,
                    "ts_ms": int(round(sim_t * 1000.0)),
                    "session": "RUNNING",
                    "mode": "ERG",
                    "route_id": "demo",
                    "s": 100.0,
                    "d": 100.0,
                    "t": round(sim_t, 2),
                    "p": target_w,
                    "p3": target_w,
                    "cad": 90,
                    "hr": None,
                    "gear": 12,
                    "gear_max": 24,
                    "g": 0.0,
                    "g_sim": 0.0,
                    "erg": {
                        "workout_name": workout_name,
                        "block_index": idx,
                        "block_count": n_blocks,
                        "block_type": b_type,
                        "block_remaining_s": rem_s,
                        "block_total_s": b_total,
                        "target_w": target_w,
                        "next_target_w": next_w,
                        "bias_pct": 100,
                        "paused": paused,
                    },
                    "ble": {"trainer": "connected", "click": "connected"},
                    "last_cmd_id": 0,
                }
                tx.sendto(json.dumps(frame, separators=(",", ":")).encode("utf-8"), ("127.0.0.1", state_port))
                time.sleep(0.001)

    # Passe 1 : 10 blocs sans pause -> 10 bips attendus
    send_workout_pass("Référence lot F", pause_block_idx=None)
    # Passe 2 : 10 blocs avec pause pendant les 3 dernières secondes du bloc 4 -> 0 bip au bloc 4
    send_workout_pass("Référence lot F (pause)", pause_block_idx=4)

    tx.sendto(json.dumps({"type": "shutdown", "v": CONTRACT_VERSION}).encode("utf-8"), ("127.0.0.1", state_port))
    tx.close()
    return 0



def run_catalog_server(state_port: int, cmd_port: int, catalog_path: Path, drop_first: bool = False,
                       drop_all: bool = False, split: bool = False) -> int:
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Erreur lecture catalogue {catalog_path} : {exc}", file=sys.stderr)
        return 1

    core = FakeCore(state_port, cmd_port, EngineLog(Path("engine.log")))
    core.catalog_data = catalog
    core.drop_first_catalog = drop_first
    core.drop_all_catalog = drop_all
    core.split_catalog = split
    core._dropped_lists = set()
    core.auto_hello_ack = True
    core.streaming = True
    core.start()

    deadline = now() + 30.0
    while now() < deadline:
        time.sleep(0.05)
        with core.lock:
            # Sortir quand un message bye arrive ou après start
            byes = [r for r in core.received if r.msg.get("type") == "bye"]
            starts = [r for r in core.received if r.msg.get("type") == "cmd" and r.msg.get("name") == "start"]
            if byes or (starts and (now() - starts[0].t > 1.0)):
                break

    core.stop()
    return 0

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state-port", type=int, default=5005)
    ap.add_argument("--cmd-port", type=int, default=5006)
    ap.add_argument("--engine-log", type=Path, default=None)
    ap.add_argument("--scenarios", default=",".join(map(str, RUN_ORDER)),
                    help="numéros à jouer, dans l'ordre (le 1 doit venir en premier)")
    ap.add_argument("--erg-workout", action="store_true",
                    help="émet un entraînement ERG simulé (10 blocs du lot F) pour le test du lot I6")
    ap.add_argument("--catalog", type=Path, default=None,
                    help="fichier JSON du catalogue (lot N3)")
    ap.add_argument("--drop-first-catalog", action="store_true",
                    help="ignore la 1re demande de chaque liste pour tester la relance (lot N3)")
    ap.add_argument("--drop-all-catalog", action="store_true",
                    help="ignore toutes les demandes de listes pour tester l'erreur (lot N3)")
    ap.add_argument("--split-catalog", action="store_true",
                    help="envoie chaque liste en deux parties, la 2e d'abord (assemblage, lot N3)")
    args = ap.parse_args()
    if args.erg_workout:
        return run_erg_workout_stream(args.state_port, args.cmd_port)
    if args.catalog:
        return run_catalog_server(args.state_port, args.cmd_port, args.catalog, args.drop_first_catalog,
                                  args.drop_all_catalog, args.split_catalog)
    if args.engine_log is None:
        ap.error("--engine-log est requis hors --erg-workout")
    wanted = [int(x) for x in args.scenarios.split(",") if x.strip()]

    core = FakeCore(args.state_port, args.cmd_port, EngineLog(args.engine_log))
    core.start()
    if 1 not in wanted:
        core.auto_hello_ack = True
        core.streaming = True
    results: list[tuple[int, bool, str]] = []
    for num in wanted:
        title, func = SCENARIOS[num]
        try:
            detail = func(core)
            ok = True
        except ScenarioFailed as exc:
            detail, ok = str(exc), False
            # Remet un état sain pour les scénarios suivants.
            core.silent, core.streaming, core.auto_hello_ack = False, True, True
            core.accept_cmd = lambda msg, count: True
        results.append((num, ok, detail))
        print(f"[{'OK' if ok else 'ÉCHEC'}] scénario {num} – {title} : {detail}", flush=True)
    core.stop()
    failed = [r for r in results if not r[1]]
    print(f"Scénarios : {len(results) - len(failed)}/{len(results)} réussis", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
