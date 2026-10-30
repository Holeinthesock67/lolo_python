#!/usr/bin/env python3
"""Banc visuel du mode Cyber-Rogue (lot X41) : une run du lot X40 rejouée dans la vraie scène, captures aux moments clés.

Usage :
    rogue_bench.py --godot CHEMIN [--objective threshold|endurance|vo2max] [--seed 5] [--trace F.jsonl]
                   [--size 1280x720] [--quality low] [--speed 20] [--native] [--out DOSSIER]

Sans `--trace`, le banc joue d'abord la run dans la vraie séance du core (`rogue_bout_en_bout`, lot X40) et en garde
la trace : chaque message que le core envoie à l'engine (`state`, `room`, `loot`, `input`). Il lance ensuite la
vraie scène Godot (`main.tscn`, `--test-mode`), sous Xvfb (OpenGL logiciel) ou, avec `--native`, à l'écran, et la
rejoue face à un faux core, en temps accéléré `--speed` fois. Aux moments clés (échauffement, chaque salle à
120 m de son début, pause, couloir avec ses cartes, boss, retour au calme, résultats, bilan), le banc fige la
trame 1,5 s, demande une capture puis vérifie :

- l'image : ni noire ni uniforme, néons dessinés (pixels vifs et saturés) pendant la run ;
- ce que la scène affiche (`rogue_host.test_info()` de la ligne `screenshot`) : scène du mode active, ruban,
  repères, Firewall et ennemi en salle, salle affichée = salle de la trame, hologramme du HUD, écran des cartes
  en couloir, scène quittée au bilan, menu de pause et de bilan, bandeau sans message d'erreur ;
- deux salles de suite qui ne donnent pas la même image ;
- le journal de Godot : aucune erreur ni avertissement de script ; aucune demande `rogue_resync` (les salles
  arrivent avant leurs trames).

Sortie : une ligne [OK] / [ÉCHEC] par vérification, `rapport.html` (planche des captures et tableau) et les PNG.
Code de sortie 0 si tout passe, 1 si une vérification échoue, 2 si Godot ou xvfb-run manque.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
ENGINE_DIR = TESTS_DIR.parent
sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(ENGINE_DIR.parent / "core" / "src"))

from fake_core import CONTRACT_VERSION, EngineLog, FakeCore, now  # noqa: E402
from visual_check import (GODOT_ISSUE, GODOT_TOLERATED, Capture, Report, free_udp_ports, mean_abs_diff,  # noqa: E402
                          read_png, write_html)

HOLD_S = 1.5                     # trame figée avant chaque capture : lissage de la position, ennemi, HUD
FRAME_HZ = 25.0                  # trames renvoyées pendant le gel
ROOM_CAPTURE_M = 120.0           # capture d'une salle à 120 m de son début
WARMUP_CAPTURE_S = 20.0
CORRIDOR_CAPTURE_S = 3.0         # après l'offre de cartes
COOLDOWN_CAPTURE_S = 10.0
FIGHT = ("ROOM", "BOSS")
DARK_MIN_LUM = 0.01              # scène néon : fond sombre, mais jamais noire
UNIFORM_MIN_STD = 0.02
NEON_MIN = 0.002                 # part minimale de pixels vifs et saturés pendant la run
# Échauffement, retour au calme et résultats : vide et grille seuls (rogue_scene.gd, RIBBON_PHASES), sans
# ruban ni HUD classique (caché pendant la run depuis le lot R19) ; la grille seule fait environ 0,1 %.
NEON_MIN_EMPTY = 0.0005
RIBBON_PHASES = ("ROOM", "CORRIDOR", "BOSS", "RECOVERY")
ROOM_DIFF_MIN = 1.0              # écart moyen (niveaux sur 255) entre deux salles de suite
CONFIG = "rogue"


def load_trace(path: Path) -> list[tuple[float, dict]]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            out.append((float(d["t"]), d["msg"]))
    return out


def make_trace(objective: str, seed: int, path: Path) -> list[str]:
    """Run du lot X40 ; rend ses vérifications en échec (la trace est gardée quand même)."""
    from openride_core.tools import rogue_bout_en_bout as x40
    rep = x40.run(objective, 30, seed, trace=path)
    return [f"{label} : {detail}" for ok, label, detail in rep.checks if ok is False]


def moments(trace: list[tuple[float, dict]]) -> list[tuple[int, str]]:
    """(indice du message `state`, nom) des captures, dans l'ordre de la trace."""
    out: list[tuple[int, str]] = []
    seen: set[str] = set()
    t_warmup = t_cool = loot_t = None

    def add(i: int, name: str) -> None:
        if name not in seen:
            seen.add(name)
            out.append((i, name))

    for i, (t, m) in enumerate(trace):
        if m.get("type") == "loot":
            loot_t = t
            continue
        if m.get("type") != "state":
            continue
        st = m.get("session_state")
        rg = m.get("rogue") or {}
        ph = rg.get("phase")
        if st == "PAUSED":
            add(i, "pause")
        elif st == "FINISHED":
            add(i, "bilan")
        elif ph == "WARMUP":
            t_warmup = t if t_warmup is None else t_warmup
            if t - t_warmup >= WARMUP_CAPTURE_S:
                add(i, "echauffement")
        elif ph in FIGHT and float(rg.get("s_room") or 0.0) >= ROOM_CAPTURE_M:
            add(i, "boss" if ph == "BOSS" else f"salle_{rg.get('room_id')}_{rg.get('archetype')}")
        elif ph == "CORRIDOR" and loot_t is not None and t - loot_t >= CORRIDOR_CAPTURE_S:
            add(i, "couloir_cartes")
        elif ph == "COOLDOWN":
            t_cool = t if t_cool is None else t_cool
            if t - t_cool >= COOLDOWN_CAPTURE_S:
                add(i, "retour_au_calme")
        elif ph == "RESULTS":
            add(i, "resultats")
    return out


class Bench:
    def __init__(self, args, out: Path, report: Report) -> None:
        self.args, self.out, self.report = args, out, report
        self.width, self.height = (int(v) for v in args.size.lower().split("x"))
        self.seq = 0

    def check(self, scene: str, name: str, ok: bool, detail: str = "") -> bool:
        return self.report.check(CONFIG, scene, name, ok, detail)

    def send_state(self, core: FakeCore, msg: dict) -> None:
        self.seq += 1
        core.send({**msg, "seq": self.seq})

    def capture(self, core: FakeCore, scene: str) -> tuple[Any, dict] | None:
        png = (self.out / f"{len(self.report.captures):02d}_{scene}.png").resolve()
        mark = core.log.mark()
        core.send({"type": "_test", "v": CONTRACT_VERSION, "action": "screenshot", "path": str(png), "tag": scene})
        hit = core.log.wait_for(r"^screenshot (\{.*\})$", 10.0, mark)
        if not self.check(scene, "capture enregistrée", hit is not None and png.exists(),
                          "" if hit else "aucune ligne « screenshot » dans le journal de l'engine"):
            return None
        info = json.loads(hit[1].group(1))
        self.report.captures.append(Capture(CONFIG, scene, png, info))
        return read_png(png), info

    def replay(self, core: FakeCore, trace: list[tuple[float, dict]], marks: list[tuple[int, str]]) -> list[tuple]:
        """Rejoue la trace ; aux moments choisis, fige la trame puis capture. Rend (nom, trame, image, info)."""
        at = dict(marks)
        shots = []
        t0 = trace[0][0]
        start = now()
        for i, (t, m) in enumerate(trace):
            wait = start + (t - t0) / self.args.speed - now()
            if wait > 0:
                time.sleep(wait)
            if m.get("type") == "state":
                self.send_state(core, m)
            else:
                core.send(m)
            if i in at:
                held = now()
                while now() - held < HOLD_S:
                    time.sleep(1.0 / FRAME_HZ)
                    self.send_state(core, m)
                shot = self.capture(core, at[i])
                start += now() - held                  # le temps du gel ne compte pas dans la trace
                if shot is not None:
                    shots.append((at[i], m, shot[0], shot[1]))
        return shots

    def check_shot(self, name: str, frame: dict, img, info: dict) -> None:
        lum, std, neon = image_stats(img)
        rg = frame.get("rogue") or {}
        ri = info.get("rogue") or {}
        self.check(name, "taille de l'image", (img.width, img.height) == (self.width, self.height),
                   f"{img.width}x{img.height}")
        self.check(name, "image ni noire ni uniforme", lum > DARK_MIN_LUM and std > UNIFORM_MIN_STD,
                   f"luminance {lum:.3f}, écart type {std:.3f}")
        widgets = info.get("widgets") or {}
        menu = widgets.get("menu", {}).get("visible", False)
        banner = widgets.get("banner", {})
        shown = banner.get("text", "") if banner.get("visible") else ""
        self.check(name, "bandeau sans message d'erreur", "introuvable" not in shown and "rreur" not in shown,
                   shown.replace("\n", " | ")[:120] or "bandeau vide")
        if name == "bilan":
            self.check(name, "scène du mode quittée au bilan", not ri, "active" if ri else "quittée")
            self.check(name, "menu du bilan affiché", menu, "")
            return
        self.check(name, "scène du mode active", bool(ri), json.dumps(ri, ensure_ascii=False)[:160])
        if not ri:
            return
        floor = NEON_MIN if rg.get("phase") in RIBBON_PHASES else NEON_MIN_EMPTY
        self.check(name, "néons dessinés", neon >= floor, f"{neon:.2%} de pixels vifs et saturés (au moins {floor:.2%})")
        if name == "pause":
            self.check(name, "menu de pause affiché", menu, "")
        if rg.get("phase") in FIGHT and frame.get("session_state") == "RUNNING":
            self.check(name, "salle affichée = salle de la trame", ri.get("room_shown") == rg.get("room_id"),
                       f"affichée {ri.get('room_shown')}, trame {rg.get('room_id')}")
            self.check(name, "ruban, repères et Firewall", ri.get("ribbon") and ri.get("markers", 0) > 0 and ri.get("firewall"),
                       f"ruban {ri.get('ribbon')}, {ri.get('markers')} repère(s), Firewall {ri.get('firewall')}")
            self.check(name, "ennemi affiché", bool(ri.get("enemy")), f"archétype {ri.get('enemy_archetype') or '—'}")
        if frame.get("session_state") == "RUNNING":
            if ri.get("corridor"):   # l'écran du couloir occupe le centre : hologramme retiré
                self.check(name, "hologramme retiré au couloir", not ri.get("holo"), ri.get("holo") or "retiré")
            else:
                self.check(name, "hologramme du HUD", bool(ri.get("hud")) and bool(ri.get("holo")),
                           (ri.get("holo") or "").replace("\n", " · "))
            classic = [k for k in ("panel_left", "panel_right", "panel", "profile", "chart_sim")
                       if widgets.get(k, {}).get("visible")]
            self.check(name, "HUD classique caché pendant la run", not classic, ", ".join(classic) or "caché")
        if name == "couloir_cartes":
            self.check(name, "écran des cartes du couloir", bool(ri.get("corridor")), "")


def image_stats(img) -> tuple[float, float, float]:
    """Luminance moyenne, écart type et part de pixels vifs et saturés (néons), sur un pixel sur deux."""
    n = s = s2 = neon = 0
    for y in range(0, img.height, 2):
        for x in range(0, img.width, 2):
            r, g, b = img.pixel(x, y)
            lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
            n += 1
            s += lum
            s2 += lum * lum
            hi, lo = max(r, g, b), min(r, g, b)
            if hi >= 180 and hi - lo >= 100:
                neon += 1
    mean = s / n
    return mean, max(s2 / n - mean * mean, 0.0) ** 0.5, neon / n


def run(args, out: Path, report: Report) -> None:
    if args.trace:
        trace_path = Path(args.trace)
    else:
        trace_path = out / "trace.jsonl"
        failed = make_trace(args.objective, args.seed, trace_path)
        report.check(CONFIG, "run", "run du lot X40 sans échec", not failed, " | ".join(failed))
    trace = load_trace(trace_path)
    marks = moments(trace)
    report.notes.append(f"Trace {trace_path.name} : {len(trace)} messages ; captures : {', '.join(n for _, n in marks)}")
    bench = Bench(args, out, report)
    state_port, cmd_port = free_udp_ports(2)
    engine_log = out / "engine.log"
    engine_log.write_text("")
    core = FakeCore(state_port, cmd_port, EngineLog(engine_log))
    core.auto_hello_ack = True
    core.start()
    cmd = [args.godot, "--path", str(ENGINE_DIR), "--resolution", args.size, "--audio-driver", "Dummy"]
    if not args.native:
        cmd = ["xvfb-run", "-a", "-s", f"-screen 0 {bench.width}x{bench.height}x24"] + cmd + [
            "--rendering-driver", "opengl3", "--rendering-method", "gl_compatibility"]
    cmd += ["--", f"--ipc-state-port={state_port}", f"--ipc-cmd-port={cmd_port}", "--test-mode",
            f"--quality={args.quality}"]
    print(f"== Run rejouée ×{args.speed:g} : {len(marks)} captures ==", flush=True)
    with engine_log.open("w") as fh:
        proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        t0 = now()
        while now() - t0 < 30.0 and not core.messages("hello"):
            time.sleep(0.1)
        time.sleep(1.5)
        shots = bench.replay(core, trace, marks)
    finally:
        core.stop()
        try:
            os.killpg(proc.pid, 15)
            proc.wait(timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(proc.pid, 9)
            except ProcessLookupError:
                pass
    for name, frame, img, info in shots:
        bench.check_shot(name, frame, img, info)
    taken = {n for n, *_ in shots}
    expected = {"echauffement", "pause", "couloir_cartes", "boss", "retour_au_calme", "resultats", "bilan"}
    rooms = [s for s in shots if s[0].startswith("salle_")]
    bench.check("run", "moments clés capturés", expected <= taken and len(rooms) >= 2,
                f"{len(shots)} capture(s) ; manquent : {', '.join(sorted(expected - taken)) or 'aucun'} ; {len(rooms)} salle(s)")
    for a, b in zip(rooms, rooms[1:]):
        d = mean_abs_diff(a[2], b[2])
        bench.check(b[0], "image différente de la salle précédente", d >= ROOM_DIFF_MIN, f"écart moyen {d:.1f} niveaux sur 255")
    resync = core.messages("cmd", name="rogue_resync")
    bench.check("run", "aucune demande rogue_resync", not resync, f"{len(resync)} demande(s)")
    issues = [ln for ln in engine_log.read_text(errors="replace").splitlines()
              if GODOT_ISSUE.search(ln) and not GODOT_TOLERATED.search(ln)]
    bench.check("journal", "aucune erreur ni avertissement Godot", not issues, " | ".join(issues[:5]))


def main() -> int:
    ap = argparse.ArgumentParser(description="Banc visuel du mode Cyber-Rogue (lot X41).")
    ap.add_argument("--godot", required=True)
    ap.add_argument("--objective", default="threshold", help="objectif de la run jouée (sans --trace)")
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--trace", help="trace d'une run du lot X40 (rogue_bout_en_bout --trace) au lieu d'en jouer une")
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--quality", default="low")
    ap.add_argument("--speed", type=float, default=20.0, help="accélération du rejeu (défaut ×20)")
    ap.add_argument("--native", action="store_true", help="écran réel et rendu habituel, sans Xvfb")
    ap.add_argument("--out", type=Path, default=None, help="dossier des captures et du rapport")
    args = ap.parse_args()
    if not (Path(args.godot).is_file() and os.access(args.godot, os.X_OK)):
        print(f"Godot introuvable : {args.godot}", file=sys.stderr)
        return 2
    if not args.native and shutil.which("xvfb-run") is None:
        print("xvfb-run introuvable (paquet xvfb) ; ou --native", file=sys.stderr)
        return 2
    out = args.out or Path(tempfile.mkdtemp(prefix="openride-rogue-bench-"))
    out.mkdir(parents=True, exist_ok=True)
    report = Report()
    t0 = time.time()
    run(args, out, report)
    path = write_html(report, out, time.time() - t0)
    fails = report.failures()
    print(f"Banc visuel du Cyber-Rogue : {len(report.checks) - len(fails)}/{len(report.checks)} vérifications réussies")
    print(f"Rapport : {path}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
