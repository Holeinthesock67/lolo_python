"""Coupures volontaires, attendu contre obtenu au journal (lot X10, outil officiel de l'essai 69).

    python -m openride_core.tools.coupures                     # pendant une séance OpenRide sur le PC
    python -m openride_core.tools.coupures --actions trainer,click_droit
    python -m openride_core.tools.coupures --sim               # Bluetooth simulé, engine relancé sous Xvfb
    python -m openride_core.tools.coupures --sim --sans-engine # core seul (CI, cloud)
    python -m openride_core.tools.coupures --analyse DOSSIER
    python -m openride_core.tools.coupures --materiel

Actions, dans l'ordre (`--actions` pour en choisir) :
- `godot` : processus de l'engine tué par l'outil (`SIGKILL`) ; attendu : le lanceur note le plantage
  et relance l'engine, qui refait son `hello` ;
- `trainer` : HomeTrainer éteint 5 s (consigne à l'écran) ; attendu : `down`, pause (`trainer_lost`),
  puis `up` et reprise ;
- `click_droit`, `clicks` : boîtier droit (« + »), puis les deux boîtiers, coupés 30 s
  (`bluetoothctl block` si l'adresse est dans `config.toml`, sinon consigne : retirer la pile) ;
  attendu : `down` puis `up` de chaque boîtier (un appui le réveille, l'outil le demande) ;
- `ceinture` : ceinture retirée 30 s ; attendu : FC absente au journal, puis revenue. FC relayée par le
  trainer (`[drivers] hr = "none"`) : le délai admis est celui du gel du lot Q5 + 2 s.
Le clavier reste actif en parallèle du Click (contrat IPC §6) : pas de repli à vérifier.

Chaque action est horodatée dans `actions.jsonl` avec ses attendus (ligne du journal de séance ou du
journal du lanceur et délai maximal, depuis le début ou la fin de la coupure). À la fin, l'outil copie le
dernier journal de séance (`journal.jsonl`) et celui du lanceur (`lanceur.log`) et écrit le tableau
attendu contre obtenu (`rapport.txt`, `rapport.json`) dans `~/OpenRide/coupures/<date>_<heure>/`.

`--sim` déroule les mêmes actions devant le Bluetooth simulé (scénario généré : `sleep` et `drop`, puis
`wake` ; `contact` pour la ceinture) avec le vrai lanceur (`launcher.Supervisor`) et Godot sous Xvfb ;
`--sans-engine` lance le core seul et saute `godot`. `--court` raccourcit les coupures (essai rapide).
Code de sortie : 0 si tout l'attendu est obtenu, 1 sinon, 2 si le dossier est illisible.
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
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .guide import Guide

DEFAULT_OUT = Path.home() / "OpenRide" / "coupures"
REPO = Path(__file__).resolve().parents[4]
ENGINE_DIR = REPO / "engine"
DEFAULT_GODOT = Path.home() / "Applications" / "godot" / "Godot_v4.7.2-stable_linux.x86_64"
LOG_TS_RE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),(\d{3}) ")
SLACK_S = 1.0          # horodatages du journal à la seconde près autour du début ou de la fin
GAP_S = 20.0           # entre deux actions, sur le vélo
FREEZE_MARGIN_S = 2.0  # FC relayée : retirée par le gel au plus une notification après hr_relay_freeze_s


@dataclass(frozen=True)
class Expect:
    label: str
    pattern: str    # expression régulière sur une ligne de la chronologie (voir `timeline`)
    ref: str        # "debut" ou "fin" de la coupure
    max_s: float


@dataclass(frozen=True)
class Action:
    key: str
    title: str
    seconds: float
    short_s: float
    expects: tuple[Expect, ...]


def _device(dev: str, label: str) -> tuple[Expect, Expect]:
    return (Expect(f"{label} : « down » au journal", rf"^device {dev} down$", "debut", 10.0),
            Expect(f"{label} : « up » au journal", rf"^device {dev} up$", "fin", 30.0))


def actions(hr_relayed: bool, freeze_s: float) -> dict[str, Action]:
    """Les actions et leurs attendus ; la ceinture dépend de la source de la FC."""
    absent_s = max(10.0, freeze_s + FREEZE_MARGIN_S) if hr_relayed else 10.0
    plus_down, plus_up = _device("click_plus", "boîtier droit")
    minus_down, minus_up = _device("click_minus", "boîtier gauche")
    trainer_down, trainer_up = _device("trainer", "trainer")
    return {a.key: a for a in (
        Action("godot", "Arrêt de Godot (SIGKILL)", 0.0, 0.0, (
            Expect("plantage noté par le lanceur", r"^log .*l'engine a planté", "debut", 5.0),
            Expect("engine relancé et relié au core", r"^log .*Reçu 'hello' de l'engine", "debut", 40.0))),
        Action("trainer", "HomeTrainer éteint", 5.0, 4.0, (
            trainer_down, Expect("pause automatique (trainer perdu)", r"^event pause$", "debut", 10.0),
            trainer_up, Expect("reprise de la séance", r"^event resume$", "fin", 30.0))),
        Action("click_droit", "Boîtier droit du Click coupé", 30.0, 6.0, (plus_down, plus_up)),
        Action("clicks", "Les deux boîtiers du Click coupés", 30.0, 6.0, (plus_down, minus_down, plus_up, minus_up)),
        Action("ceinture", "Ceinture retirée", 30.0, 10.0, (
            Expect("FC absente au journal", r"^fc absente$", "debut", absent_s),
            Expect("FC revenue au journal", r"^fc presente$", "fin", 20.0))),
    )}


# --- comparaison ----------------------------------------------------------------------------

def log_time(line: str) -> float | None:
    m = LOG_TS_RE.match(line)
    if not m:
        return None
    return time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")) + int(m.group(2)) / 1000.0


def timeline(journal: list[dict[str, Any]], log_lines: list[str]) -> list[tuple[float, str]]:
    """Chronologie commune : `device <appareil> up|down`, `event <nom>`, `fc absente|presente` (au
    changement, d'après les relevés) et `log <message>` (lignes horodatées du lanceur et du core)."""
    out: list[tuple[float, str]] = []
    hr_present: bool | None = None
    for x in journal:
        kind, ts = x.get("kind"), x.get("ts")
        if ts is None:
            continue
        if kind == "device":
            out.append((ts, f"device {x.get('device')} {x.get('state')}"))
        elif kind == "event":
            out.append((ts, f"event {x.get('event')}"))
        elif kind == "record":
            present = x.get("hr") is not None
            if present != hr_present and hr_present is not None:
                out.append((ts, f"fc {'presente' if present else 'absente'}"))
            hr_present = present
    for line in log_lines:
        t = log_time(line)
        if t is not None:
            out.append((t, "log " + line[24:].strip()))
    return sorted(out, key=lambda e: e[0])


def compare(done: list[dict[str, Any]], events: list[tuple[float, str]]) -> dict[str, Any]:
    """Pour chaque attendu, la première ligne qui correspond entre la référence (moins SLACK_S) et le
    début de l'action suivante : délai mesuré, OK s'il tient le délai maximal."""
    rows = []
    starts = sorted(a["debut"] for a in done)
    for a in done:
        nxt = next((s for s in starts if s > a["debut"]), float("inf"))
        for e in a["attendus"]:
            ref = a["debut"] if e["ref"] == "debut" else a["fin"]
            rx = re.compile(e["pattern"])
            hit = next((t for t, key in events if ref - SLACK_S <= t < nxt and rx.search(key)), None)
            delay = None if hit is None else round(max(hit - ref, 0.0), 1)
            rows.append({"action": a["action"], "attendu": e["label"], "depuis": e["ref"], "max_s": e["max_s"],
                         "delai_s": delay, "ok": delay is not None and delay <= e["max_s"]})
    return {"ok": all(r["ok"] for r in rows) and bool(rows), "lignes": rows}


def report_text(rep: dict[str, Any]) -> str:
    lines = ["Coupures volontaires : attendu contre obtenu (lot X10)", ""]
    for r in rep["lignes"]:
        got = "absent" if r["delai_s"] is None else f"{r['delai_s']:.1f} s"
        lines.append(f"  [{'OK' if r['ok'] else 'ÉCHEC'}] {r['action']:<12} {r['attendu']} : {got} "
                     f"après la {'coupure' if r['depuis'] == 'debut' else 'fin de la coupure'} "
                     f"(au plus {r['max_s']:g} s)")
    lines += ["", "Verdict : " + ("tout l'attendu est obtenu" if rep["ok"] else "au moins un attendu manque")]
    return "\n".join(lines) + "\n"


class InputError(Exception):
    """Dossier sans `actions.jsonl` ou journaux illisibles."""


def read_folder(folder: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    path = folder / "actions.jsonl"
    if not path.is_file():
        raise InputError(f"pas de actions.jsonl dans {folder}")
    done = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    journal: list[dict[str, Any]] = []
    if (folder / "journal.jsonl").is_file():
        from ..journal import read_journal
        journal = list(read_journal(folder / "journal.jsonl"))
    log_lines: list[str] = []
    if (folder / "lanceur.log").is_file():
        log_lines = (folder / "lanceur.log").read_text(encoding="utf-8", errors="replace").splitlines()
    if not journal and not log_lines:
        raise InputError(f"ni journal.jsonl ni lanceur.log dans {folder}")
    return done, journal, log_lines


def analyse(folder: Path) -> dict[str, Any]:
    done, journal, log_lines = read_folder(folder)
    rep = compare(done, timeline(journal, log_lines))
    (folder / "rapport.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    (folder / "rapport.txt").write_text(report_text(rep), encoding="utf-8")
    return rep


def entry(action: Action, start: float, end: float) -> dict[str, Any]:
    return {"action": action.key, "titre": action.title, "debut": round(start, 3), "fin": round(end, 3),
            "secondes": round(end - start, 1), "attendus": [asdict(e) for e in action.expects]}


# --- processus de l'engine ------------------------------------------------------------------

def _proc_table() -> dict[int, tuple[int, str]]:
    """pid → (pid du parent, nom du programme) de chaque processus visible."""
    out: dict[int, tuple[int, str]] = {}
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            stat = (d / "stat").read_text()
            argv0 = (d / "cmdline").read_bytes().split(b"\0")[0].decode(errors="replace")
        except OSError:
            continue
        out[int(d.name)] = (int(stat[stat.rindex(")") + 2:].split()[1]), Path(argv0).name)
    return out


def engine_pids(root: int | None = None) -> list[int]:
    """Processus Godot : tous, ou seulement les descendants de `root` (engine lancé par l'outil)."""
    table = _proc_table()

    def under(pid: int) -> bool:
        seen = set()
        while pid not in seen and pid > 1:
            seen.add(pid)
            if pid == root:
                return True
            pid = table.get(pid, (0, ""))[0]
        return False

    return [pid for pid, (_, name) in table.items()
            if name.startswith("Godot") and (root is None or under(pid))]


def kill_engine(root: int | None = None) -> list[int]:
    pids = engine_pids(root)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    return pids


# --- essai sur le PC ------------------------------------------------------------------------

def bluetooth_block(address: str, block: bool) -> bool:
    if not address or shutil.which("bluetoothctl") is None:
        return False
    return subprocess.run(["bluetoothctl", "block" if block else "unblock", address], capture_output=True,
                          timeout=10, check=False).returncode == 0


def live(chosen: list[Action], cfg: Any, guide: Guide, out: Path, gap_s: float) -> list[dict[str, Any]]:
    done: list[dict[str, Any]] = []
    blocks = {"click_droit": [cfg.drivers.click_address],
              "clicks": [cfg.drivers.click_address, cfg.drivers.click_minus_address]}
    manual = {"trainer": ("Éteins le HomeTrainer", "Rallume le HomeTrainer"),
              "click_droit": ("Retire la pile du boîtier droit", "Remets la pile, puis appuie sur un bouton"),
              "clicks": ("Retire la pile des deux boîtiers", "Remets les piles, puis appuie sur chaque boîtier"),
              "ceinture": ("Retire la ceinture", "Remets la ceinture (électrodes mouillées)")}
    for k, a in enumerate(chosen):
        guide.step(f"Prochaine coupure : {a.title}", gap_s, "roule normalement", index=k + 1, total=len(chosen))
        guide.wait(gap_s)
        start = time.time()
        if a.key == "godot":
            pids = kill_engine()
            guide.measure("Godot arrêté", f"{len(pids)} processus" if pids else "aucun processus trouvé",
                          ok=bool(pids))
            end = start
        else:
            addrs = [x for x in blocks.get(a.key, []) if x]
            auto = bool(addrs) and all(bluetooth_block(x, True) for x in addrs)
            guide.step(a.title if auto else manual[a.key][0], a.seconds, "par l'outil (bluetoothctl)" if auto else "")
            guide.wait(a.seconds)
            if auto:
                for x in addrs:
                    bluetooth_block(x, False)
            end = time.time()
            if a.key.startswith("click"):
                guide.step("Appuie sur un bouton de chaque boîtier coupé pour le réveiller", 10.0)
                guide.wait(10.0)
            elif not auto:
                guide.step(manual[a.key][1], 10.0)
                guide.wait(10.0)
        done.append(entry(a, start, end))
        guide.log("coupure", **done[-1])
        (out / "actions.jsonl").write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in done),
                                           encoding="utf-8")
    guide.step("Dernières reprises", 40.0, "roule encore 40 s")
    guide.wait(40.0)
    return done


# --- essai simulé ---------------------------------------------------------------------------

def free_udp_ports(n: int) -> list[int]:
    socks = [socket.socket(socket.AF_INET, socket.SOCK_DGRAM) for _ in range(n)]
    for s in socks:
        s.bind(("127.0.0.1", 0))
    ports = [s.getsockname()[1] for s in socks]
    for s in socks:
        s.close()
    return ports


def sim_plan(chosen: list[Action], short: bool, gap_s: float, first_s: float = 8.0
             ) -> tuple[list[tuple[Action, float, float]], list[dict[str, Any]], float]:
    """(action, début, fin) en secondes depuis le démarrage du core, événements du scénario, durée."""
    devices = {"trainer": ["trainer"], "click_droit": ["click_plus"], "clicks": ["click_plus", "click_minus"]}
    t, plan, events = first_s, [], []
    for a in chosen:
        secs = a.short_s if short else a.seconds
        plan.append((a, t, t + secs))
        for dev in devices.get(a.key, []):
            events += [{"t": t, "device": dev, "action": "sleep"}, {"t": t, "device": dev, "action": "drop"},
                       {"t": t + secs, "device": dev, "action": "wake"}]
        if a.key == "ceinture":
            events += [{"t": t, "device": "hr", "action": "contact", "value": False},
                       {"t": t + secs, "device": "hr", "action": "contact", "value": True}]
        t += secs + gap_s
    return plan, events, t + 15.0


def wait_line(path: Path, pattern: str, timeout: float, stop: threading.Event) -> float | None:
    rx = re.compile(pattern)
    end = time.monotonic() + timeout
    while time.monotonic() < end and not stop.is_set():
        if path.is_file():
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if rx.search(line):
                    return log_time(line)
        time.sleep(0.2)
    return None


def run_sim(chosen: list[Action], args: argparse.Namespace, out: Path) -> list[dict[str, Any]]:
    from ..launcher import Supervisor

    with_engine = not args.sans_engine
    chosen = [a for a in chosen if with_engine or a.key != "godot"]
    gap = args.ecart if args.ecart is not None else (6.0 if args.court else GAP_S)
    plan, events, duration = sim_plan(chosen, args.court, gap)
    tmp = Path(tempfile.mkdtemp(prefix="openride-coupures-"))
    home = tmp / "home"
    routes = home / ".local" / "share" / "openride" / "routes"
    routes.mkdir(parents=True)
    env = {**os.environ, "HOME": str(home), "PYTHONUNBUFFERED": "1", "PYTHONPATH": str(REPO / "core" / "src")}
    for k in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
        env.pop(k, None)
    subprocess.run([sys.executable, "-m", "openride_core.tools.fake_world", "--demo", "--terrain", "--out",
                    str(routes)], check=True, env=env, stdout=subprocess.DEVNULL)
    state_port, cmd_port = free_udp_ports(2)
    cfg = tmp / "config.toml"
    cfg.write_text(f"[ipc]\nport_state = {state_port}\nport_commands = {cmd_port}\n", encoding="utf-8")
    scen = tmp / "coupures.json"
    scen.write_text(json.dumps({"trainer": {"appear_at": 0.3, "connect_delay_s": 0.3},
                                "click": {"appear_at": 0.5, "connect_delay_s": 0.3},
                                "hr": {"appear_at": 0.5, "connect_delay_s": 0.2}, "events": events}),
                    encoding="utf-8")
    core_cmd = [sys.executable, "-m", "openride_core", "run", "--config", str(cfg), "--trainer", "sim",
                "--input", "sim", "--hr", "sim", "--autostart", "--route", "demo", "--sim-scenario", str(scen)]
    log_path = out / "lanceur.log"
    stop = threading.Event()
    t0_box: list[float] = []
    procs: list[subprocess.Popen] = []
    print(f"== coupures simulées : {', '.join(a.key for a, _, _ in plan)}, {duration:.0f} s"
          f"{'' if with_engine else ', sans engine'} ==", flush=True)

    def driver(engine_root: Callable[[], int | None], finish: Callable[[], None]) -> None:
        t0 = wait_line(log_path, r"Core démarré", 30.0, stop)
        if t0 is None:
            finish()
            return
        t0_box.append(t0)
        for a, start, _end in plan:
            if a.key == "godot":
                while time.time() < t0 + start and not stop.is_set():
                    time.sleep(0.05)
                if wait_line(log_path, r"Reçu 'hello' de l'engine", 60.0, stop) is not None:
                    kill_engine(engine_root())
        while time.time() < t0 + duration and not stop.is_set():
            time.sleep(0.2)
        finish()

    if with_engine:
        godot = args.godot
        engine_cmd = ["xvfb-run", "-a", "-s", "-screen 0 1024x600x24", godot, "--path", str(ENGINE_DIR),
                      "--resolution", "1024x600", "--audio-driver", "Dummy", "--rendering-driver", "opengl3",
                      "--rendering-method", "gl_compatibility", "--", f"--ipc-state-port={state_port}",
                      f"--ipc-cmd-port={cmd_port}", f"--routes-dir={routes}", "--test-mode"]
        sup = Supervisor(core_cmd, engine_cmd, ["true"], log_path, compile_enabled=False,
                         echo=lambda: False, say=lambda _m: None, restart_delay_s=0.5)
        saved = dict(os.environ)
        os.environ.clear()
        os.environ.update(env)   # le lanceur transmet son environnement au core et à l'engine
        thread = threading.Thread(target=driver, daemon=True,
                                  args=(lambda: sup.started_pids[-1] if len(sup.started_pids) > 1 else None,
                                        lambda: os.kill(os.getpid(), signal.SIGTERM)))
        thread.start()
        try:
            sup.run()
        finally:
            stop.set()
            os.environ.clear()
            os.environ.update(saved)
            thread.join(5.0)
            for pid in sup.started_pids:   # Xvfb des engines arrêtés : même groupe que leur xvfb-run
                try:
                    os.killpg(pid, signal.SIGKILL)
                except OSError:
                    pass
    else:
        with log_path.open("wb") as fh:
            core = subprocess.Popen(core_cmd, env=env, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
            procs.append(core)
            driver(lambda: None, lambda: core.send_signal(signal.SIGTERM))
            try:
                core.wait(30.0)
            except subprocess.TimeoutExpired:
                core.kill()
                core.wait()
    journals = sorted((home / "OpenRide" / "Activities" / ".journal").glob("*.jsonl"))
    if journals:
        shutil.copy(journals[-1], out / "journal.jsonl")
    shutil.rmtree(tmp, ignore_errors=True)
    if not t0_box:
        return []
    t0 = t0_box[0]
    return [entry(a, t0 + s, t0 + e) for a, s, e in plan]


# --- programme ------------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Coupures volontaires, attendu contre obtenu (lot X10).")
    ap.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    ap.add_argument("--actions", help="actions choisies, séparées par des virgules (défaut : toutes)")
    ap.add_argument("--sim", action="store_true", help="Bluetooth simulé, vrai lanceur, engine sous Xvfb")
    ap.add_argument("--sans-engine", action="store_true", help="avec --sim : core seul, sans l'action godot")
    ap.add_argument("--court", action="store_true", help="coupures raccourcies (essai rapide)")
    ap.add_argument("--ecart", type=float, help=f"secondes entre deux actions (défaut {GAP_S:g}, 6 avec --court)")
    ap.add_argument("--godot", default=os.environ.get("GODOT", str(DEFAULT_GODOT)), help="Godot 4.7 (--sim)")
    ap.add_argument("--journal", type=Path, help="journal de séance à joindre (défaut : le dernier)")
    ap.add_argument("--lanceur", type=Path, help="journal du lanceur (défaut : ~/run_trainer.log)")
    ap.add_argument("--analyse", type=Path, metavar="DOSSIER", help="refaire la comparaison d'un dossier")
    ap.add_argument("--out", type=Path, help=f"dossier de sortie (défaut : {DEFAULT_OUT}/<date>)")
    ap.add_argument("--materiel", action="store_true", help="affiche le matériel à préparer et quitte")
    ap.add_argument("--sans-attente", action="store_true", help="démarre sans attendre « Entrée »")
    ap.add_argument("--muet", action="store_true", help="sans bips")
    return ap.parse_args(argv)


def finish(folder: Path) -> int:
    try:
        rep = analyse(folder)
    except InputError as exc:
        print(f"Dossier illisible : {exc}")
        return 2
    print(report_text(rep), end="")
    print(f"Résultats : {folder}")
    return 0 if rep["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.materiel:
        from .guide import materials_text
        print(materials_text(["coupures"]), end="")
        return 0
    if args.analyse is not None:
        return finish(args.analyse)
    from .. import config as config_mod

    cfg = config_mod.load(args.config)
    hr_relayed = not args.sim and cfg.drivers.hr != "ble"
    table = actions(hr_relayed, cfg.trainer.hr_relay_freeze_s)
    keys = [k.strip() for k in args.actions.split(",")] if args.actions else list(table)
    unknown = [k for k in keys if k not in table]
    if unknown:
        print(f"action inconnue : {', '.join(unknown)} (connues : {', '.join(table)})")
        return 2
    chosen = [table[k] for k in keys]
    out = args.out or DEFAULT_OUT / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    if args.sim:
        done = run_sim(chosen, args, out)
    else:
        guide = Guide("Coupures volontaires", out / "guide.jsonl", sound=False if args.muet else None)
        guide.prepare("coupures", wait=not args.sans_attente and sys.stdin.isatty())
        try:
            done = live(chosen, cfg, guide, out, GAP_S)
        except (KeyboardInterrupt, EOFError):
            print("\nInterrompu.")
            return 1
        finally:
            guide.close()
        from ..journal import latest_journal
        from ..launcher import DEFAULT_LOG
        journal = args.journal or latest_journal()
        if journal is not None and journal.is_file():
            shutil.copy(journal, out / "journal.jsonl")
        lanceur = args.lanceur or DEFAULT_LOG
        if lanceur.is_file():
            shutil.copy(lanceur.resolve(), out / "lanceur.log")
    (out / "actions.jsonl").write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in done),
                                       encoding="utf-8")
    return finish(out)


if __name__ == "__main__":
    sys.exit(main())
