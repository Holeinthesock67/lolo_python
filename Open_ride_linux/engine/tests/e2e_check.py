#!/usr/bin/env python3
"""Essai de bout en bout sans écran : vrai core et vrai engine Godot (lot J8).

Usage : e2e_check.py --godot CHEMIN [--engine-routes-dir DOSSIER] [--keep]

Lance `openride-core run --trainer mock --input none --autostart` puis l'engine en `--test-mode`,
chacun avec un HOME temporaire et des ports UDP libres, et vérifie le dialogue réel :
hello / hello_ack, débit des trames `state`, même parcours `demo` des deux côtés, commande
`input_event` envoyée par le script, perte de l'engine (PAUSED engine_lost), `end_session`
(FINISHED, résumé conforme à `state.schema.json`, fichier FIT), HOME réel inchangé.

Chaque vérification imprime une ligne [OK] ou [ÉCHEC] avec sa mesure. Code de sortie 0 si tout
passe, 1 sinon ; en cas d'échec, les journaux sont gardés dans le dossier temporaire indiqué.
`--engine-routes-dir` donne à l'engine un autre dossier de parcours que celui du core (sert à
montrer que la vérification de longueur échoue sur une copie modifiée de `demo`).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

ENGINE_DIR = Path(__file__).resolve().parents[1]
STATE_SCHEMA = ENGINE_DIR.parent / "docs" / "contracts" / "ipc" / "state.schema.json"
START_GEAR = 12
INPUT_CMD_ID = 10_000          # au-dessus des cmd_id de l'engine : le core l'accepte
TOTAL_BUDGET_S = 60.0
# Mêmes tolérances que run_engine_tests.sh (avertissements connus du mode sans écran).
# Même tolérance que run_engine_tests.sh : le rendu factice des tests sans écran signale `Parameter "m" is null`
# pour les maillages générés par le code (avatar du lot V6), sans conséquence.
GODOT_TOLERATED = re.compile(r"ObjectDB instances (were )?leaked|resources still in use at exit|[Mm]esh.*(null|nul)|Parameter \"m\" is null")


def now() -> float:
    return time.monotonic()


def free_udp_ports(n: int) -> list[int]:
    socks = []
    for _ in range(n):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("127.0.0.1", 0))
        socks.append(s)
    ports = [s.getsockname()[1] for s in socks]
    for s in socks:
        s.close()
    return ports


class Proc:
    """Processus dont chaque ligne de sortie est horodatée à la réception et copiée dans un journal."""

    def __init__(self, name: str, argv: list[str], env: dict[str, str], log_path: Path) -> None:
        self.name = name
        self.lines: list[tuple[float, str]] = []
        self._cond = threading.Condition()
        self._log = log_path.open("w", encoding="utf-8")
        self.t_start = now()
        self.p = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                                  errors="replace", bufsize=1)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        assert self.p.stdout is not None
        for line in self.p.stdout:
            line = line.rstrip("\n")
            with self._cond:
                self.lines.append((now(), line))
                self._log.write(line + "\n")
                self._log.flush()
                self._cond.notify_all()

    def wait_for(self, pattern: str, timeout: float, after: float = 0.0) -> tuple[float, re.Match[str]] | None:
        rx = re.compile(pattern)
        deadline = now() + timeout
        idx = 0
        with self._cond:
            while True:
                for t, line in self.lines[idx:]:
                    m = rx.search(line)
                    if m and t >= after:
                        return t, m
                idx = len(self.lines)
                remaining = deadline - now()
                if remaining <= 0:
                    return None
                self._cond.wait(min(remaining, 0.1))

    def matching(self, pattern: str) -> list[tuple[float, re.Match[str]]]:
        rx = re.compile(pattern)
        with self._cond:
            return [(t, m) for t, line in self.lines if (m := rx.search(line))]

    def stop(self, sig: int = signal.SIGTERM, timeout: float = 5.0) -> int | None:
        if self.p.poll() is None:
            self.p.send_signal(sig)
            try:
                self.p.wait(timeout)
            except subprocess.TimeoutExpired:
                self.p.kill()
                self.p.wait(2)
        time.sleep(0.05)
        self._log.close()
        return self.p.returncode


class Report:
    def __init__(self) -> None:
        self.failed = 0

    def check(self, ok: bool, label: str, measure: str) -> bool:
        print(f"[{'OK' if ok else 'ÉCHEC'}] {label} : {measure}", flush=True)
        self.failed += not ok
        return ok


def snapshot_home(home: Path) -> dict[str, tuple[int, int]]:
    """Liste (taille, date) de ~/OpenRide et ~/run_trainer.log du HOME réel."""
    out: dict[str, tuple[int, int]] = {}
    paths = [home / "run_trainer.log"]
    root = home / "OpenRide"
    if root.is_dir():
        paths += [p for p in root.rglob("*")]
    for p in paths:
        try:
            st = p.stat()
        except OSError:
            continue
        out[str(p)] = (st.st_size, st.st_mtime_ns)
    return out


def send_cmd(port: int, cmd_id: int, name: str, args: dict[str, Any]) -> None:
    msg = {"type": "cmd", "v": 1, "cmd_id": cmd_id, "name": name, "args": args}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(json.dumps(msg).encode(), ("127.0.0.1", port))


def bind_state_port(port: int, timeout: float) -> socket.socket | None:
    deadline = now() + timeout
    while now() < deadline:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind(("127.0.0.1", port))
            s.settimeout(0.1)
            return s
        except OSError:
            s.close()
            time.sleep(0.02)
    return None


def read_states(sock: socket.socket, until, timeout: float) -> tuple[float, dict] | None:
    """Lit les trames `state` jusqu'à ce que `until(state)` soit vrai."""
    deadline = now() + timeout
    while now() < deadline:
        try:
            data = sock.recv(65536)
        except socket.timeout:
            continue
        try:
            msg = json.loads(data)
        except ValueError:
            continue
        if isinstance(msg, dict) and msg.get("type") == "state" and until(msg):
            return now(), msg
    return None


def run(godot: Path, engine_routes_dir: Path | None, keep: bool) -> int:
    t0 = now()
    real_home = Path.home()
    before = snapshot_home(real_home)
    tmp = Path(tempfile.mkdtemp(prefix="openride-e2e-"))
    home = tmp / "home"
    home.mkdir()
    state_port, cmd_port = free_udp_ports(2)
    cfg = tmp / "config.toml"
    cfg.write_text(f"[gearing]\nstart_gear = {START_GEAR}\n\n[ipc]\nport_state = {state_port}\n"
                   f"port_commands = {cmd_port}\n", encoding="utf-8")
    core_routes = home / ".local" / "share" / "openride" / "routes"
    env = {**os.environ, "HOME": str(home), "PYTHONUNBUFFERED": "1"}
    env.pop("XDG_DATA_HOME", None)
    env.pop("XDG_CONFIG_HOME", None)
    env.pop("XDG_CACHE_HOME", None)
    print(f"Dossier temporaire : {tmp} (ports {state_port} / {cmd_port})", flush=True)
    r = Report()
    core = engine = None
    try:
        core = Proc("core", [sys.executable, "-m", "openride_core", "run", "--config", str(cfg),
                             "--trainer", "mock", "--input", "none", "--autostart"],
                    env, tmp / "core.log")
        started = core.wait_for(r"Core démarré", 15.0)
        if not r.check(started is not None, "démarrage du core",
                       f"{started[0] - core.t_start:.2f} s" if started else "pas de « Core démarré » en 15 s"):
            return 1

        engine = Proc("engine", [str(godot), "--headless", "--path", str(ENGINE_DIR), "--",
                                 f"--ipc-state-port={state_port}", f"--ipc-cmd-port={cmd_port}",
                                 f"--routes-dir={engine_routes_dir or core_routes}", "--test-mode"],
                      env, tmp / "engine.log")

        # 1. hello puis hello_ack.
        hello = core.wait_for(r"Reçu 'hello' de l'engine version (\S+)", 15.0, after=engine.t_start)
        ack = engine.wait_for(r"hello_ack reçu : core (\S+),", 15.0)
        if hello and ack:
            dt = ack[0] - hello[0]
            r.check(dt < 3.0, "hello puis hello_ack",
                    f"{dt * 1000:.0f} ms entre hello reçu par le core et hello_ack reçu par l'engine "
                    f"({ack[0] - engine.t_start:.2f} s après le lancement de l'engine)")
            # Lot O2 : les deux côtés annoncent le numéro du fichier VERSION.
            expected = (ENGINE_DIR.parent / "VERSION").read_text(encoding="utf-8").strip()
            got = (hello[1].group(1), ack[1].group(1))
            r.check(got == (expected, expected), "versions de hello et hello_ack",
                    f"engine {got[0]}, core {got[1]}, VERSION {expected}")
        else:
            r.check(False, "hello puis hello_ack",
                    "hello absent du journal du core" if not hello else "hello_ack absent du journal de l'engine")

        # 2. Débit des trames state sur 5 s, seq croissant.
        first = engine.wait_for(r"\[test\] state seq=", 10.0)
        if first:
            time.sleep(max(0.0, first[0] + 5.2 - now()))
            window = [(t, int(m.group(1))) for t, m in engine.matching(r"\[test\] state seq=(\d+)")
                      if first[0] <= t < first[0] + 5.0]
            seqs = [s for _, s in window]
            increasing = all(b > a for a, b in zip(seqs, seqs[1:]))
            rate = len(window) / 5.0
            r.check(rate >= 25.0 and increasing, "trames state",
                    f"{rate:.1f} trames/s sur 5 s, seq {seqs[0]} à {seqs[-1]} "
                    f"{'croissant' if increasing else 'NON croissant'}" if seqs else "aucune trame")
        else:
            r.check(False, "trames state", "aucune trame state dans le journal de l'engine en 10 s")

        route = engine.wait_for(r"\[test\] route_loaded id=demo length_m=([0-9.]+)", 5.0)
        engine_length = float(route[1].group(1)) if route else None

        # 3. input_event envoyé au core : relayé à l'engine (bip) et braquet changé.
        t_cmd = now()
        send_cmd(cmd_port, INPUT_CMD_ID, "input_event", {"event": "PLUS_SHORT"})
        treated = core.wait_for(rf"Commande traitée : id={INPUT_CMD_ID} name=input_event", 3.0, after=t_cmd)
        beep = engine.wait_for(r"Bip : PLUS_SHORT", 3.0, after=t_cmd)
        r.check(treated is not None and beep is not None, "input_event relayé à l'engine",
                f"commande traitée par le core en {(treated[0] - t_cmd) * 1000:.0f} ms, "
                f"« Bip : PLUS_SHORT » dans le journal de l'engine après {(beep[0] - t_cmd) * 1000:.0f} ms"
                if treated and beep else
                ("commande absente du journal du core" if not treated else "aucun bip dans le journal de l'engine"))

        # 4. Arrêt de l'engine : le core passe en PAUSED (engine_lost).
        t_stop = now()
        engine.stop(signal.SIGTERM)
        sock = bind_state_port(state_port, 2.0)
        if sock is None:
            r.check(False, "perte de l'engine", f"port d'état {state_port} toujours occupé")
            return 1
        with sock:
            paused = read_states(sock, lambda s: s.get("session_state") == "PAUSED"
                                 and s.get("pause_reason") == "engine_lost", 5.0)
            r.check(paused is not None and paused[0] - t_stop < 3.0, "perte de l'engine",
                    f"PAUSED (engine_lost) {paused[0] - t_stop:.2f} s après l'arrêt de l'engine"
                    if paused else "pas de PAUSED engine_lost en 5 s")
            last = paused[1] if paused else None
            if last is None:
                got = read_states(sock, lambda s: True, 1.0)
                last = got[1] if got else None

            gear = last.get("gear") if last else None
            r.check(gear == START_GEAR + 1, "braquet après PLUS_SHORT",
                    f"gear {START_GEAR} → {gear} dans les trames du core")
            core_length = last.get("route_length_m") if last else None
            same = (engine_length is not None and isinstance(core_length, (int, float))
                    and abs(engine_length - core_length) <= 0.05)
            r.check(same, "même parcours demo des deux côtés",
                    f"core {core_length} m, engine {engine_length} m")

            # 5. end_session : FINISHED, résumé conforme, FIT écrit dans le dossier temporaire.
            t_end = now()
            send_cmd(cmd_port, INPUT_CMD_ID + 1, "end_session", {"save": True})
            fin = read_states(sock, lambda s: s.get("session_state") == "FINISHED", 5.0)
        if fin is None:
            r.check(False, "end_session", "pas de FINISHED en 5 s")
        else:
            state = fin[1]
            errors = schema_errors(state)
            summary = state.get("summary") or {}
            fit = Path(summary.get("fit_path") or "")
            fit_ok = fit.is_file() and fit.is_relative_to(tmp) and fit.stat().st_size > 0
            r.check(not errors and bool(summary), "end_session",
                    f"FINISHED en {(fin[0] - t_end) * 1000:.0f} ms, résumé {json.dumps(summary, ensure_ascii=False)}"
                    + (f", écarts au schéma : {errors}" if errors else ", trame conforme à state.schema.json"))
            r.check(fit_ok, "fichier FIT",
                    f"{fit} ({fit.stat().st_size} octets)" if fit_ok else f"absent ou hors du dossier temporaire : {fit}")

        issues = [m.string for _, m in engine.matching(r"SCRIPT ERROR|ERROR:|WARNING:")
                  if not GODOT_TOLERATED.search(m.string)]
        r.check(not issues, "erreurs et avertissements de Godot",
                "aucun" if not issues else f"{len(issues)} : {issues[:3]}")

        rc = core.stop(signal.SIGINT, timeout=10.0)
        r.check(rc == 0, "arrêt du core", f"code de sortie {rc}")
        after = snapshot_home(real_home)
        changed = sorted(set(before.items()) ^ set(after.items()))
        r.check(not changed, "HOME réel inchangé",
                f"~/OpenRide et ~/run_trainer.log de {real_home} identiques" if not changed
                else f"modifiés : {sorted({p for p, _ in changed})[:5]}")
        elapsed = now() - t0
        r.check(elapsed < TOTAL_BUDGET_S, "durée totale", f"{elapsed:.1f} s (limite {TOTAL_BUDGET_S:.0f} s)")
    finally:
        for p in (engine, core):
            if p is not None:
                p.stop(signal.SIGKILL, timeout=2.0)
        if r.failed or keep:
            print(f"Journaux gardés dans {tmp} (core.log, engine.log)")
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    print("RÉSULTAT : " + ("bout en bout OK" if not r.failed else f"ÉCHEC ({r.failed} vérification(s))"))
    return 0 if not r.failed else 1


def schema_errors(state: dict) -> list[str]:
    import jsonschema
    schema = json.loads(STATE_SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [f"{'/'.join(map(str, e.path)) or '(racine)'} : {e.message}" for e in validator.iter_errors(state)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--godot", type=Path, required=True, help="exécutable Godot 4.7")
    ap.add_argument("--engine-routes-dir", type=Path, help="dossier de parcours de l'engine (défaut : celui du core)")
    ap.add_argument("--keep", action="store_true", help="garder le dossier temporaire même si tout passe")
    args = ap.parse_args(argv)
    if not os.access(args.godot, os.X_OK):
        print(f"Godot introuvable : {args.godot}")
        return 2
    return run(args.godot, args.engine_routes_dir, args.keep)


if __name__ == "__main__":
    sys.path.insert(0, str(ENGINE_DIR.parent / "scripts"))
    from isolation_tests import verrou_suite   # une seule suite de tests ou banc à la fois

    with verrou_suite("e2e_check"):
        code = main()
    sys.exit(code)
