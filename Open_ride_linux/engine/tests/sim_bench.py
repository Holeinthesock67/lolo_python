#!/usr/bin/env python3
"""Banc d'essai simulé : vrai core sur Bluetooth simulé, vrai engine, captures et rapport.

Usage :
    sim_bench.py --godot CHEMIN [--scenario NOM|FICHIER.json]... [--world demo|village|osm|DOSSIER.world]
                 [--workout erg_court|FICHIER.zwo] [--duration S] [--every S] [--difficulty PCT]
                 [--size 1280x720] [--quality low] [--native] [--out DOSSIER] [--list]

Pour chaque scénario, le banc lance `openride-core run --trainer sim --input sim --hr sim
--sim-scenario … --autostart` (vrais pilotes FTMS, Click et ceinture devant les appareils
simulés de `ble_sim.py`) puis la vraie scène Godot (`main.tscn`, `--test-mode`), sous Xvfb
(OpenGL logiciel) ou, avec `--native`, dans une fenêtre sur l'écran réel pour regarder l'essai.
Le core et l'engine ont un HOME temporaire et des ports UDP libres : rien n'est écrit dans le
vrai dossier personnel.

Pendant la séance, le banc demande à l'engine une capture toutes les `--every` secondes et
juste après chaque événement du scénario (coupure, appui, silence…), avec le texte du HUD et
du bandeau. À la fin : `end_session`, arrêt propre du core, `log_report` sur le journal du
core, `openride-core summary` sur la séance, puis `rapport.html` : vérifications, courbes de la
séance (altitude, puissance et cible, fréquence cardiaque, pente envoyée, braquet) avec les
événements, et planche des captures.

Scénarios : ceux du core (`sim_scenarios.SCENARIOS`), ceux du banc (`sim_bench_scenarios/*.json`,
qui peuvent fixer `world`, `workout`, `duration_s` et `difficulty_pct` dans une section
`bench`), ou un fichier JSON au format de `docs/SIMULATION_BLE.md`. `--list` les énumère.

Code de sortie : 0 si toutes les vérifications passent, 1 sinon, 2 si Godot ou xvfb-run manque.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
ENGINE_DIR = TESTS_DIR.parent
REPO = ENGINE_DIR.parent
sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(REPO / "core" / "src"))

from e2e_check import Proc, free_udp_ports, now, send_cmd, snapshot_home  # noqa: E402
from openride_core import sim_scenarios  # noqa: E402

BENCH_SCENARIOS_DIR = TESTS_DIR / "sim_bench_scenarios"
CMD_ID_BASE = 20_000
GODOT_ISSUE = re.compile(r"SCRIPT ERROR|ERROR:|WARNING:")
# Mêmes tolérances que visual_check.py (avertissements connus du mode test et de Xvfb).
GODOT_TOLERATED = re.compile(
    r"ObjectDB instances leaked|resources still in use at exit|[Mm]esh.*(null|nul)|V-Sync|set_use_vsync")
# Lignes du journal du core gardées pour la frise des événements.
CORE_EVENT = re.compile(r"Reconnexion|reconnect|perdu|coupé|déconnect|connecté|renvoi|refus|ERROR|"
                        r"PAUSED|RUNNING|FINISHED|silence|plus de données|ceinture|Click|contrôle", re.I)
ERG_SHORT_ZWO = """<workout_file>
  <author>OpenRide</author><name>ERG court (banc simulé)</name>
  <description>Échauffement, trois répétitions et retour au calme : 5 min 30.</description>
  <sportType>bike</sportType>
  <workout>
    <Warmup Duration="60" PowerLow="0.50" PowerHigh="0.70"/>
    <IntervalsT Repeat="3" OnDuration="60" OffDuration="30" OnPower="1.05" OffPower="0.55"/>
    <SteadyState Duration="30" Power="0.80"/>
    <Cooldown Duration="30" PowerLow="0.60" PowerHigh="0.40"/>
  </workout>
</workout_file>
"""


class BenchProc(Proc):
    """Comme Proc, sans erreur si le processus écrit encore après la fermeture de son journal."""

    def _read(self) -> None:
        try:
            super()._read()
        except ValueError:
            pass


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[bool, str, str]] = []

    def check(self, ok: bool, label: str, measure: str) -> bool:
        print(f"[{'OK' if ok else 'ÉCHEC'}] {label} : {measure}", flush=True)
        self.rows.append((ok, label, measure))
        return ok

    @property
    def failed(self) -> int:
        return sum(not ok for ok, _, _ in self.rows)


# --- scénarios ---------------------------------------------------------------------------------

def bench_scenarios() -> dict[str, Path]:
    return {p.stem: p for p in sorted(BENCH_SCENARIOS_DIR.glob("*.json"))}


def resolve_scenario(name: str) -> tuple[str, dict[str, Any], dict[str, Any], str]:
    """(nom, scénario BLE, réglages du banc, argument --sim-scenario) d'un nom ou d'un fichier."""
    bench = bench_scenarios()
    if name in sim_scenarios.SCENARIOS:
        return name, sim_scenarios.load_scenario(name), {}, name
    path = bench.get(name) or Path(name)
    if not path.is_file():
        raise SystemExit(f"scénario inconnu : {name} (--list pour la liste)")
    doc = json.loads(path.read_text(encoding="utf-8"))
    settings = doc.pop("bench", {}) or {}
    spec = sim_scenarios.validate(doc)
    return path.stem, spec, settings, ""


def list_scenarios() -> None:
    print("Scénarios du core :")
    for k, v in sim_scenarios.SCENARIOS.items():
        print(f"  {k:24s} {v.get('description', '')}")
    print("Scénarios du banc (engine/tests/sim_bench_scenarios/) :")
    for k, p in bench_scenarios().items():
        doc = json.loads(p.read_text(encoding="utf-8"))
        print(f"  {k:24s} {doc.get('description', '')}")


def scenario_duration(spec: dict[str, Any]) -> float:
    ts = [float(e.get("t", 0)) + float(e.get("seconds", 0) or 0) for e in spec.get("events", [])]
    return max(ts, default=0.0)


# --- parcours ----------------------------------------------------------------------------------

def prepare_world(kind: str, routes: Path, tmp: Path) -> str:
    """Écrit le parcours dans le dossier des parcours du core et renvoie son identifiant."""
    routes.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONPATH": str(REPO / "core" / "src")}
    if kind == "demo":
        subprocess.run([sys.executable, "-m", "openride_core.tools.fake_world", "--demo", "--terrain",
                        "--out", str(routes)], check=True, env=env, stdout=subprocess.DEVNULL)
        return "demo"
    if kind in ("village", "osm"):
        script = "make_sim_world.py" if kind == "village" else "make_osm_world.py"
        work = tmp / f"world-{kind}"
        subprocess.run([sys.executable, str(TESTS_DIR / script), "--out", str(work)], check=True,
                       stdout=subprocess.DEVNULL)
        world = next(work.glob("*.world"))
        shutil.copytree(world, routes / world.name, dirs_exist_ok=True)
        return world.stem
    src = Path(kind).expanduser()
    if not (src / "manifest.json").is_file():
        raise SystemExit(f"parcours introuvable : {kind} (demo, village, osm ou dossier .world)")
    shutil.copytree(src, routes / src.name, dirs_exist_ok=True)
    return src.stem


# --- une séance --------------------------------------------------------------------------------

class Bench:
    def __init__(self, args: argparse.Namespace, name: str, spec: dict[str, Any], settings: dict[str, Any],
                 scenario_arg: str, out: Path) -> None:
        self.args = args
        self.name = name
        self.spec = spec
        self.scenario_arg = scenario_arg
        self.world = str(settings.get("world") or args.world)
        self.workout = settings.get("workout", args.workout)
        self.difficulty = settings.get("difficulty_pct", args.difficulty)
        self.duration = float(args.duration or settings.get("duration_s") or
                              min(max(scenario_duration(spec) + 15.0, 45.0), 600.0))
        self.every = float(args.every or settings.get("every_s") or 15.0)
        self.out = out
        self.report = Report()
        self.shots: list[dict[str, Any]] = []
        self.core_events: list[tuple[float, str]] = []
        self.banners: list[tuple[float, str]] = []
        self.summary_text = ""
        self.log_report_text = ""
        self.records: list[dict[str, Any]] = []
        self.t_core = 0.0
        self.t0_wall = 0.0

    # Temps relatif au « Core démarré » (même origine que les événements du scénario).
    def rel(self, t: float) -> float:
        return t - self.t_core

    def run(self) -> Report:
        a = self.args
        r = self.report
        self.out.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix="openride-bench-"))
        home = tmp / "home"
        home.mkdir()
        routes = home / ".local" / "share" / "openride" / "routes"
        route_id = prepare_world(self.world, routes, tmp)
        state_port, cmd_port = free_udp_ports(2)
        cfg_lines = [f"[ipc]\nport_state = {state_port}\nport_commands = {cmd_port}\n"]
        if self.difficulty is not None:
            cfg_lines.append(f"[trainer]\ndifficulty_pct = {float(self.difficulty)}\n")
        cfg = tmp / "config.toml"
        cfg.write_text("\n".join(cfg_lines), encoding="utf-8")
        argv = [sys.executable, "-m", "openride_core", "run", "--config", str(cfg), "--trainer", "sim",
                "--input", "sim", "--hr", "sim", "--autostart", "--route", route_id]
        if self.scenario_arg:
            argv += ["--sim-scenario", self.scenario_arg]
        else:
            scen = tmp / f"{self.name}.json"
            scen.write_text(json.dumps(self.spec), encoding="utf-8")
            argv += ["--sim-scenario", str(scen)]
        if self.workout:
            wdir = home / "OpenRide" / "Workouts"
            wdir.mkdir(parents=True)
            if self.workout == "erg_court":
                (wdir / "erg_court.zwo").write_text(ERG_SHORT_ZWO, encoding="utf-8")
                wid = "erg_court"
            else:
                src = Path(self.workout).expanduser()
                shutil.copy(src, wdir / src.name)
                wid = src.stem
            argv += ["--workout", wid]
        env = {**os.environ, "HOME": str(home), "PYTHONUNBUFFERED": "1",
               "PYTHONPATH": str(REPO / "core" / "src")}
        for k in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
            env.pop(k, None)
        width, height = (int(v) for v in a.size.lower().split("x"))
        print(f"== {self.name} : parcours {route_id}, {self.duration:.0f} s"
              f"{', ERG ' + str(self.workout) if self.workout else ', SIM'}"
              f"{f', difficulté {self.difficulty} %' if self.difficulty is not None else ''} ==", flush=True)
        core = engine = None
        try:
            core = BenchProc("core", argv, env, self.out / "core.log")
            started = core.wait_for(r"Core démarré", 20.0)
            if not r.check(started is not None, "démarrage du core",
                           "« Core démarré » lu" if started else "pas de « Core démarré » en 20 s"):
                return r
            self.t_core = started[0]
            cmd = [a.godot, "--path", str(ENGINE_DIR), "--resolution", f"{width}x{height}",
                   "--audio-driver", "Dummy"]
            if not a.native:
                cmd = ["xvfb-run", "-a", "-s", f"-screen 0 {width}x{height}x24"] + cmd + [
                    "--rendering-driver", "opengl3", "--rendering-method", "gl_compatibility"]
            cmd += ["--", f"--ipc-state-port={state_port}", f"--ipc-cmd-port={cmd_port}",
                    f"--routes-dir={routes}", "--test-mode", f"--quality={a.quality}"]
            engine = BenchProc("engine", [str(c) for c in cmd], env, self.out / "engine.log")
            ack = engine.wait_for(r"hello_ack reçu", 30.0)
            r.check(ack is not None, "engine relié au core",
                    f"hello_ack {self.rel(ack[0]):.1f} s après le démarrage du core" if ack else "pas de hello_ack en 30 s")
            loaded = engine.wait_for(rf"route_loaded id={re.escape(route_id)}", 30.0)
            r.check(loaded is not None, "parcours chargé par l'engine",
                    f"{route_id} à {self.rel(loaded[0]):.1f} s" if loaded else f"{route_id} non chargé en 30 s")
            self._capture_loop(engine, state_port)
            t_end = now()
            send_cmd(cmd_port, CMD_ID_BASE, "end_session", {"save": True})
            fin = core.wait_for(r"FINISHED", 10.0, after=t_end)
            time.sleep(1.0)
            self._shot(engine, state_port, "fin")
            time.sleep(1.5)
            self._collect(core, engine)
            r.check(fin is not None or self._final_state(core) in ("FINISHED", "ERROR"), "fin de séance",
                    "FINISHED après end_session" if fin else f"dernier état lu : {self._final_state(core)}")
        finally:
            for p in (engine,):
                if p is not None:
                    p.stop(signal.SIGTERM, timeout=5.0)
            rc = core.stop(signal.SIGINT, timeout=15.0) if core is not None else None
            if core is not None:
                r.check(rc == 0, "arrêt du core", f"code de sortie {rc}")
        self._after(home)
        if not a.keep:
            shutil.rmtree(tmp, ignore_errors=True)
        else:
            print(f"Dossier temporaire gardé : {tmp}")
        return r

    def _shot(self, engine: Proc, port: int, tag: str) -> None:
        idx = len(self.shots)
        path = (self.out / f"{idx:03d}_{tag}.png").resolve()
        t = now()
        msg = {"type": "_test", "action": "screenshot", "path": str(path), "tag": tag}
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(json.dumps(msg).encode(), ("127.0.0.1", port))
        got = engine.wait_for(r"\[test\] screenshot (\{.*\})$", 5.0, after=t)
        info: dict[str, Any] = {"tag": tag, "t": self.rel(t), "file": path.name, "ok": False}
        if got:
            try:
                data = json.loads(got[1].group(1))
                info.update(ok=bool(data.get("ok")), fps=data.get("fps"), meshes=data.get("meshes"),
                            widgets={k: v.get("text", "") for k, v in data.get("widgets", {}).items()
                                     if v.get("visible")})
            except ValueError:
                pass
        self.shots.append(info)

    def _capture_loop(self, engine: Proc, port: int) -> None:
        """Captures périodiques et juste après chaque événement du scénario, jusqu'à la durée voulue."""
        plan: list[tuple[float, str]] = []
        t = 3.0
        while t < self.duration:
            plan.append((t, f"t{int(t):03d}"))
            t += self.every
        for k, ev in enumerate(self.spec.get("events", [])):
            et = float(ev.get("t", 0))
            if et >= self.duration:
                continue
            label = f"{ev.get('device', 'trainer') if ev.get('action') != 'press' else 'click'}_{ev.get('action')}"
            plan.append((et + 2.0, f"ev{k}_{label}"))
            if ev.get("seconds") and et + float(ev["seconds"]) < self.duration:
                plan.append((et + float(ev["seconds"]) - 0.5, f"ev{k}_{label}_fin"))
        plan.sort()
        for at, tag in plan:
            wait = self.t_core + at - now()
            if wait > 0:
                time.sleep(wait)
            if engine.p.poll() is not None:
                self.report.check(False, "engine vivant", f"engine arrêté à {self.rel(now()):.0f} s")
                return
            self._shot(engine, port, tag)
        wait = self.t_core + self.duration - now()
        if wait > 0:
            time.sleep(wait)

    def _final_state(self, core: Proc) -> str:
        states = core.matching(r"\b(RUNNING|PAUSED|FINISHED|ERROR)\b")
        return states[-1][1].group(1) if states else "?"

    def _collect(self, core: Proc, engine: Proc) -> None:
        for t, m in core.matching(r".+"):
            line = m.string
            if CORE_EVENT.search(line) and "Perf" not in line and "Reçu 'hello'" not in line:
                self.core_events.append((self.rel(t), line))
        for t, m in engine.matching(r"\[test\] banner text=(.*)$"):
            self.banners.append((self.rel(t), m.group(1)))

    def _after(self, home: Path) -> None:
        r = self.report
        a = self.args
        # Captures.
        ok = [s for s in self.shots if s.get("ok")]
        r.check(len(ok) == len(self.shots) and ok, "captures de l'engine",
                f"{len(ok)}/{len(self.shots)} images enregistrées")
        fps = [s["fps"] for s in ok if isinstance(s.get("fps"), (int, float)) and s["tag"].startswith("t")]
        if fps:
            print(f"   images par seconde de l'engine : min {min(fps):.0f}, médiane {sorted(fps)[len(fps) // 2]:.0f}")
        # Erreurs Godot.
        log = (self.out / "engine.log").read_text(encoding="utf-8", errors="replace").splitlines()
        issues = [ln for ln in log if GODOT_ISSUE.search(ln) and not GODOT_TOLERATED.search(ln)]
        r.check(not issues, "erreurs et avertissements de Godot", "aucun" if not issues else " | ".join(issues[:3]))
        # Exceptions du core.
        core_log = (self.out / "core.log").read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),(\d{3}) .*Core démarré", core_log, re.M)
        if m:   # heure murale du « Core démarré » : origine des événements, comme `ts` du journal
            self.t0_wall = time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")) + int(m.group(2)) / 1000
        tb = core_log.count("Traceback")
        r.check(tb == 0, "exceptions du core", f"{tb} trace(s) Python dans core.log")
        # Journal de séance, FIT, bilan et log_report.
        journals = sorted((home / "OpenRide" / "Activities" / ".journal").glob("*.jsonl"))
        fits = sorted((home / "OpenRide" / "Activities").glob("*.fit"))
        r.check(bool(journals) and bool(fits), "journal et FIT écrits",
                f"{len(journals)} journal(aux), {len(fits)} FIT")
        if journals:
            for line in journals[-1].read_text(encoding="utf-8").splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("kind") in ("record", "device", "event"):
                    self.records.append(row)
            shutil.copy(journals[-1], self.out / "seance.jsonl")
        env = {**os.environ, "HOME": str(home), "PYTHONPATH": str(REPO / "core" / "src")}
        target = str(fits[-1]) if fits else (str(journals[-1]) if journals else "")
        if target:
            p = subprocess.run([sys.executable, "-m", "openride_core", "summary", target], env=env,
                               capture_output=True, text=True)
            self.summary_text = p.stdout + p.stderr
            r.check(p.returncode == 0, "openride-core summary", "bilan lu" if p.returncode == 0 else p.stderr[-200:])
        p = subprocess.run([sys.executable, "-m", "openride_core.tools.log_report", str(self.out / "core.log")],
                           env=env, capture_output=True, text=True)
        self.log_report_text = p.stdout + p.stderr
        r.check(p.returncode == 0, "log_report", "analyse du journal du core lue" if p.returncode == 0
                else p.stderr[-200:])
        self._scenario_checks()
        (self.out / "log_report.txt").write_text(self.log_report_text, encoding="utf-8")
        (self.out / "summary.txt").write_text(self.summary_text, encoding="utf-8")
        write_html(self)
        del a

    def _scenario_checks(self) -> None:
        """Attentes tirées des événements : ce que l'écran et le journal doivent montrer."""
        r = self.report
        recs = [x for x in self.records if x.get("kind") == "record"]
        t0 = self.t0_wall
        devs = [x for x in self.records if x.get("kind") == "device"]
        for ev in self.spec.get("events", []):
            t = float(ev.get("t", 0))
            if t + 8 > self.duration:
                continue
            dev, act = ev.get("device", "trainer"), ev.get("action")
            if act == "drop":
                downs = [d for d in devs if d.get("device") == dev and d.get("state") == "down"
                         and d["ts"] - t0 >= t - 1]
                ups = [d for d in devs if d.get("device") == dev and d.get("state") == "up"
                       and downs and d["ts"] >= downs[0]["ts"]]
                back = f", revenu {ups[0]['ts'] - t0 - t:.1f} s après" if ups else ", pas revenu"
                r.check(bool(downs) and (bool(ups) or dev in ("click_plus", "click_minus")),
                        f"coupure de {dev} à {t:.0f} s : « down » puis « up » au journal",
                        f"down {downs[0]['ts'] - t0 - t:+.1f} s{back}" if downs else "aucune ligne down")
            if act == "silence" and float(ev.get("seconds", 0)) >= 6:
                end = t + float(ev["seconds"])
                seen = [s for s in self.shots if t + 5 <= s["t"] <= end + 1
                        and "PAUSED" in s.get("widgets", {}).get("status", "")]
                r.check(bool(seen), f"trainer muet à {t:.0f} s : pause visible à l'écran",
                        f"{seen[0]['file']} : « {seen[0]['widgets']['status']} »" if seen
                        else "aucune capture ne montre PAUSED")
                after = [s for s in self.shots if end + 4 <= s["t"] <= end + 25]
                running = [s for s in after if "RUNNING" in s.get("widgets", {}).get("status", "")]
                if after:
                    r.check(bool(running), f"reprise après le silence de {t:.0f} s",
                            f"{running[0]['file']} : RUNNING" if running else "toujours en pause à l'écran")
        if self.workout and recs:
            targets = [x["target_w"] for x in recs if x.get("target_w")]
            r.check(bool(targets), "consignes ERG au journal",
                    f"{len(targets)} échantillons avec cible, de {min(targets):.0f} à {max(targets):.0f} W"
                    if targets else "aucune cible ERG dans le journal")
            erg_shots = [s for s in self.shots if s.get("widgets", {}).get("erg_title")]
            r.check(bool(erg_shots), "bandeau ERG à l'écran",
                    f"{len(erg_shots)} capture(s), ex. « {erg_shots[0]['widgets']['erg_title']} »" if erg_shots
                    else "bandeau ERG jamais visible")
        if recs and not self.workout:
            grades = [x.get("grade") for x in recs if x.get("grade") is not None]
            sent = [x.get("grade_sent") for x in recs if x.get("grade_sent") is not None]
            if grades and sent:
                print(f"   pente du parcours {min(grades):.1f} à {max(grades):.1f} %, "
                      f"pente envoyée {min(sent):.1f} à {max(sent):.1f} %")
        hr = [x.get("hr") for x in recs if x.get("hr")]
        if "hr" in self.spec:
            r.check(bool(hr), "fréquence cardiaque au journal",
                    f"{len(hr)} échantillons, {min(hr)} à {max(hr)} bpm" if hr else "aucune fréquence cardiaque")


# --- rapport HTML ------------------------------------------------------------------------------

def svg_chart(records: list[dict[str, Any]], key: str, label: str, color: str, events: list[tuple[float, str]],
              key2: str | None = None, color2: str = "#888", width: int = 900, height: int = 120) -> str:
    recs = [x for x in records if x.get("kind") == "record" and x.get(key) is not None]
    if len(recs) < 2:
        return ""
    t0 = recs[0]["ts"]
    xs = [x["ts"] - t0 for x in recs]
    vals = [float(x[key]) for x in recs]
    vals2 = [float(x[key2]) if x.get(key2) is not None else None for x in recs] if key2 else []
    allv = vals + [v for v in vals2 if v is not None]
    lo, hi = min(allv), max(allv)
    if hi - lo < 1e-6:
        hi = lo + 1.0
    tmax = max(xs[-1], 1.0)

    def pt(x: float, v: float) -> str:
        return f"{40 + x / tmax * (width - 50):.1f},{10 + (1 - (v - lo) / (hi - lo)) * (height - 25):.1f}"

    line = " ".join(pt(x, v) for x, v in zip(xs, vals))
    parts = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="{html.escape(label)}">',
             f'<text x="2" y="12" class="lbl">{html.escape(label)}</text>',
             f'<text x="2" y="{height - 8}" class="lbl">{lo:.0f}</text><text x="2" y="26" class="lbl">{hi:.0f}</text>']
    for et, txt in events:
        if 0 <= et <= tmax:
            x = 40 + et / tmax * (width - 50)
            parts.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="0" y2="{height}" class="ev"><title>{html.escape(txt)}</title></line>')
    if key2:
        seg = " ".join(pt(x, v) for x, v in zip(xs, vals2) if v is not None)
        parts.append(f'<polyline points="{seg}" fill="none" stroke="{color2}" stroke-width="1.5" stroke-dasharray="4 3"/>')
    parts.append(f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="1.6"/></svg>')
    return "".join(parts)


def write_html(b: Bench) -> None:
    rows = "".join(f'<tr class="{"ok" if ok else "ko"}"><td>{"OK" if ok else "ÉCHEC"}</td><td>{html.escape(lb)}</td>'
                   f"<td>{html.escape(ms)}</td></tr>" for ok, lb, ms in b.report.rows)
    events = [(float(e.get("t", 0)), f"{e.get('t')} s : {e.get('device', 'trainer')} {e.get('action')}")
              for e in b.spec.get("events", [])]
    charts = "".join([
        svg_chart(b.records, "alt", "Altitude (m)", "#5b7f3a", events),
        svg_chart(b.records, "power", "Puissance (W, tirets : cible ERG)", "#c0392b", events, "target_w", "#2c3e50"),
        svg_chart(b.records, "hr", "Fréquence cardiaque (bpm)", "#8e44ad", events),
        svg_chart(b.records, "grade", "Pente du parcours (%, tirets : pente envoyée)", "#d35400", events,
                  "grade_sent", "#16a085"),
        svg_chart(b.records, "gear", "Braquet", "#2980b9", events),
        svg_chart(b.records, "speed", "Vitesse (m/s)", "#34495e", events),
    ])
    shots = []
    for s in b.shots:
        w = s.get("widgets", {})
        txt = " · ".join(f"{k} : {v}" for k, v in w.items() if v and k in
                         ("power", "speed", "grade", "hr", "status", "banner", "erg_title", "erg_target"))
        shots.append(f'<figure><a href="{s["file"]}"><img src="{s["file"]}" loading="lazy" alt="{html.escape(s["tag"])}"></a>'
                     f'<figcaption><b>{s["t"]:.0f} s · {html.escape(s["tag"])}</b> · {s.get("fps", "?")} img/s'
                     f'<br>{html.escape(txt)}</figcaption></figure>')
    evlines = "\n".join(f"{t:7.1f} s  {line}" for t, line in b.core_events[-400:])
    banners = "\n".join(f"{t:7.1f} s  {txt}" for t, txt in b.banners) or "(aucun)"
    doc = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Banc simulé {html.escape(b.name)}</title>
<style>
:root {{ --bg:#fafafa; --fg:#222; --muted:#666; --card:#fff; --line:#ddd; --ok:#1e8449; --ko:#c0392b; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#16181b; --fg:#e8e8e8; --muted:#9aa; --card:#1f2226; --line:#333; }} }}
body {{ background:var(--bg); color:var(--fg); font:15px/1.45 system-ui,sans-serif; margin:0 auto; max-width:1200px; padding:16px; }}
table {{ border-collapse:collapse; width:100%; }} td {{ border-bottom:1px solid var(--line); padding:4px 6px; vertical-align:top; }}
tr.ok td:first-child {{ color:var(--ok); font-weight:600; }} tr.ko td:first-child {{ color:var(--ko); font-weight:600; }}
.chart {{ width:100%; height:auto; background:var(--card); border:1px solid var(--line); margin:4px 0; }}
.chart .lbl {{ font-size:11px; fill:var(--muted); }} .chart .ev {{ stroke:#e67e22; stroke-width:1; stroke-dasharray:2 3; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:10px; }}
figure {{ margin:0; background:var(--card); border:1px solid var(--line); }} figure img {{ width:100%; display:block; }}
figcaption {{ font-size:12px; padding:4px 6px; color:var(--muted); }}
pre {{ background:var(--card); border:1px solid var(--line); padding:8px; overflow:auto; max-height:360px; font-size:12px; }}
</style></head><body>
<h1>Banc simulé : {html.escape(b.name)}</h1>
<p>{html.escape(str(b.spec.get("description", "")))}<br>Parcours <b>{html.escape(b.world)}</b>,
{f"ERG {html.escape(str(b.workout))}" if b.workout else "SIM"}, {b.duration:.0f} s,
{f"difficulté {b.difficulty} %, " if b.difficulty is not None else ""}{b.args.size} {b.args.quality}
{"(écran réel)" if b.args.native else "(Xvfb, OpenGL logiciel)"}.</p>
<h2>Vérifications</h2><table>{rows}</table>
<h2>Courbes de la séance</h2><p>Lignes orange : événements du scénario.</p>{charts}
<h2>Captures</h2><div class="grid">{"".join(shots)}</div>
<h2>Bandeau de l'engine</h2><pre>{html.escape(banners)}</pre>
<h2>Bilan (openride-core summary)</h2><pre>{html.escape(b.summary_text)}</pre>
<h2>log_report</h2><pre>{html.escape(b.log_report_text)}</pre>
<h2>Journal du core (lignes d'événements)</h2><pre>{html.escape(evlines)}</pre>
</body></html>"""
    (b.out / "rapport.html").write_text(doc, encoding="utf-8")


def write_index(out: Path, results: list[tuple[str, Report]]) -> None:
    rows = "".join(f'<tr><td><a href="{html.escape(n)}/rapport.html">{html.escape(n)}</a></td>'
                   f'<td>{len(r.rows) - r.failed}/{len(r.rows)}</td><td>{"OK" if not r.failed else "ÉCHEC"}</td></tr>'
                   for n, r in results)
    (out / "index.html").write_text(
        '<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Banc simulé</title>'
        '<style>body{font:15px system-ui;margin:16px;background:#fafafa;color:#222}td{padding:4px 10px;'
        'border-bottom:1px solid #ddd}@media (prefers-color-scheme: dark){body{background:#16181b;color:#eee}'
        'a{color:#8cf}}</style></head><body><h1>Banc simulé</h1><table><tr><th>Scénario</th><th>Vérifications</th>'
        f"<th>Résultat</th></tr>{rows}</table></body></html>", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--godot", type=Path, default=Path(os.environ.get(
        "GODOT", Path.home() / "Applications/godot/Godot_v4.3-stable_linux.x86_64")))
    ap.add_argument("--scenario", action="append", help="scénario (répétable ; défaut : demo)")
    ap.add_argument("--world", default="demo", help="demo, village (bâtiments, montée et descente), osm, ou dossier .world")
    ap.add_argument("--workout", help="ERG : erg_court (5 min 30 intégré) ou fichier .zwo")
    ap.add_argument("--duration", type=float, help="durée de chaque séance en s (défaut : fin du scénario + 15 s)")
    ap.add_argument("--every", type=float, help="intervalle des captures en s (défaut : celui du scénario, sinon 15)")
    ap.add_argument("--difficulty", type=float, help="[trainer] difficulty_pct de la configuration")
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--quality", default="low", help="low, medium, high (défaut low)")
    ap.add_argument("--native", action="store_true", help="fenêtre sur l'écran réel, sans Xvfb")
    ap.add_argument("--out", type=Path, default=Path.home() / "OpenRide" / "sim_bench" / time.strftime("%Y-%m-%d_%H%M%S"))
    ap.add_argument("--keep", action="store_true", help="garder le HOME temporaire")
    ap.add_argument("--list", action="store_true", help="énumérer les scénarios et quitter")
    args = ap.parse_args(argv)
    if args.list:
        list_scenarios()
        return 0
    if not os.access(args.godot, os.X_OK):
        print(f"Godot introuvable : {args.godot} (option --godot ou variable GODOT)")
        return 2
    if not args.native and shutil.which("xvfb-run") is None:
        print("xvfb-run introuvable : installer xvfb, xauth et libgl1-mesa-dri (ou lancer avec --native)")
        return 2
    real_home = Path.home()
    before = snapshot_home(real_home)
    results: list[tuple[str, Report]] = []
    for name in args.scenario or ["demo"]:
        sname, spec, settings, sarg = resolve_scenario(name)
        rep = Bench(args, sname, spec, settings, sarg, args.out / sname).run()
        results.append((sname, rep))
    after = snapshot_home(real_home)
    changed = sorted({p for p, _ in set(before.items()) ^ set(after.items())
                      if not Path(p).is_relative_to(args.out)})
    ok_home = not changed
    print(f"[{'OK' if ok_home else 'ÉCHEC'}] HOME réel inchangé : "
          + ("oui" if ok_home else f"modifiés : {changed[:5]}"))
    write_index(args.out, results)
    failed = sum(r.failed for _, r in results) + (not ok_home)
    print(f"Rapport : {args.out / 'index.html'}")
    print("RÉSULTAT : " + ("banc simulé OK" if not failed else f"ÉCHEC ({failed} vérification(s))"))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
