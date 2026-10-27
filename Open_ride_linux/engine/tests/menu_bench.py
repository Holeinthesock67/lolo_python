#!/usr/bin/env python3
"""Banc des menus : vrai core sur Bluetooth simulé, vrai engine, parcours des menus au « Click ».

Usage :
    menu_bench.py [--godot CHEMIN] [--parcours NOM]... [--native] [--out DOSSIER] [--keep] [--list]

Comme `sim_bench.py`, mais sans `--autostart` : le core démarre en IDLE, comme depuis l'icône de
bureau (`openride`). Le banc joue des appuis du Click dans l'engine (message de test `menu_input`,
`--test-mode`), lit l'écran affiché dans le journal de l'engine (captures `screenshot`) et vérifie
chaque étape. Le core et l'engine ont un HOME temporaire et des ports UDP libres : rien n'est écrit
dans le vrai dossier personnel.

Parcours (`--list`) :
- `connexion_auto` : tout se connecte, l'écran « Connexion des appareils » passe seul à l'accueil ;
- `appareils` : un seul boîtier du Click (unilatéral) → « Passer », puis Réglages → Appareils :
  recherche, choix, enregistrement dans config.toml, « Relancer » (code de sortie 64 de l'engine) ;
- `sessions` : menu principal, choix du monde, session libre démarrée puis terminée, session ERG
  (entraînement choisi, consigne ERG reçue), puis « Session simulée » (code de sortie 65) ;
- `reglages` : Réglages → FTP + 15 W enregistrée dans config.toml, qualité changée tout de suite, ligne « OpenRide X.Y.Z » en bas,
  puis curseur de difficulté sur l'écran de pause (`set_difficulty`).

Résultat : captures et `rapport.html` dans `--out` (défaut : dossier temporaire). Code de sortie : 0
si toutes les vérifications passent, 1 sinon, 2 si Godot ou xvfb-run manque.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import signal
import socket
import sys
import tempfile
import time
from pathlib import Path
from collections.abc import Callable
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
ENGINE_DIR = TESTS_DIR.parent
REPO = ENGINE_DIR.parent
sys.path.insert(0, str(TESTS_DIR))

from e2e_check import free_udp_ports, now  # noqa: E402
from sim_bench import ERG_SHORT_ZWO, BenchProc, Report  # noqa: E402

READY = {"trainer": {"appear_at": 0.3, "connect_delay_s": 0.3},
         "click": {"appear_at": 0.5, "connect_delay_s": 0.3},
         "hr": {"appear_at": 0.5, "connect_delay_s": 0.2}, "events": []}
# Boîtier « − » qui n'apparaît jamais : un seul boîtier relié (unilatéral).
UNILATERAL = {**READY, "click": {"appear_at": 0.5, "connect_delay_s": 0.3, "minus": {"appear_at": 100000}}}


class Run:
    """Un parcours : core et engine lancés, appuis, captures et vérifications."""

    def __init__(self, args: argparse.Namespace, name: str, out: Path) -> None:
        self.args = args
        self.name = name
        self.out = out
        self.report = Report()
        self.shots: list[dict[str, Any]] = []
        self.state_port = self.cmd_port = 0
        self.engine: BenchProc | None = None
        self.core: BenchProc | None = None
        self.home = Path()
        self.config = Path()

    # --- engine ----------------------------------------------------------------------------

    def _send(self, msg: dict[str, Any]) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(json.dumps(msg).encode(), ("127.0.0.1", self.state_port))

    def press(self, *events: str, pause: float = 0.35) -> None:
        for ev in events:
            self._send({"type": "_test", "action": "menu_input", "event": ev})
            time.sleep(pause)

    def command(self, name: str, args: dict[str, Any] | None = None) -> None:
        """Commande du contrat envoyée par l'engine (ses numéros de commande restent cohérents)."""
        self._send({"type": "_test", "action": "command", "name": name, "args": args or {}})

    def shot(self, tag: str) -> dict[str, Any]:
        assert self.engine is not None
        path = (self.out / f"{len(self.shots):02d}_{tag}.png").resolve()
        t = now()
        self._send({"type": "_test", "action": "screenshot", "path": str(path), "tag": tag})
        got = self.engine.wait_for(r"\[test\] screenshot (\{.*\})$", 8.0, after=t)
        info: dict[str, Any] = {"tag": tag, "file": path.name, "title": "", "menu": "", "visible": False}
        if got:
            data = json.loads(got[1].group(1))
            w = data.get("widgets", {})
            info.update(title=w.get("menu_title", {}).get("text", ""), menu=w.get("menu", {}).get("text", ""),
                        visible=bool(w.get("menu", {}).get("visible")))
        self.shots.append(info)
        return info

    def expect(self, tag: str, title: str, *texts: str) -> dict[str, Any]:
        info = self.shot(tag)
        self.report.check(info["visible"] and info["title"] == title, f"{tag} : écran « {title} »",
                          f"titre « {info['title']} »")
        for t in texts:
            self.report.check(t in info["menu"], f"{tag} : « {t} »", info["menu"][:160])
        return info

    def focus_to(self, item: str, limit: int = 8) -> bool:
        """Appuis courts sur + jusqu'au focus sur l'élément dont le texte commence par `item`."""
        for _ in range(limit):
            info = self.shot("_focus")
            self.shots.pop()
            if f"[{item}" in info["menu"]:
                return True
            self.press("PLUS_SHORT")
        return False

    # --- lancement -------------------------------------------------------------------------

    def start(self, scenario: dict[str, Any], extra_config: str = "", workout: bool = False) -> bool:
        a = self.args
        r = self.report
        self.out.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix="openride-menus-"))
        self.tmp = tmp
        self.home = tmp / "home"
        routes = self.home / ".local" / "share" / "openride" / "routes"
        routes.mkdir(parents=True)
        shutil.copytree(ENGINE_DIR / "demo" / "demo.world", routes / "demo.world")
        if workout:
            wdir = self.home / "OpenRide" / "Workouts"
            wdir.mkdir(parents=True)
            (wdir / "erg_court.zwo").write_text(ERG_SHORT_ZWO, encoding="utf-8")
        self.state_port, self.cmd_port = free_udp_ports(2)
        self.config = tmp / "config.toml"
        self.config.write_text(f"[ipc]\nport_state = {self.state_port}\nport_commands = {self.cmd_port}\n"
                               + extra_config, encoding="utf-8")
        scen = tmp / "scenario.json"
        scen.write_text(json.dumps(scenario), encoding="utf-8")
        env = {**os.environ, "HOME": str(self.home), "PYTHONUNBUFFERED": "1",
               "PYTHONPATH": str(REPO / "core" / "src")}
        for k in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
            env.pop(k, None)
        argv = [sys.executable, "-m", "openride_core", "run", "--config", str(self.config), "--trainer", "sim",
                "--input", "sim", "--hr", "sim", "--sim-scenario", str(scen)]
        self.core = BenchProc("core", argv, env, self.out / "core.log")
        if not r.check(self.core.wait_for(r"Core démarré", 20.0) is not None, "démarrage du core", "« Core démarré »"):
            return False
        cmd = [str(a.godot), "--path", str(ENGINE_DIR), "--resolution", "1280x720", "--audio-driver", "Dummy"]
        if not a.native:
            cmd = ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24"] + cmd + [
                "--rendering-driver", "opengl3", "--rendering-method", "gl_compatibility"]
        cmd += ["--", f"--ipc-state-port={self.state_port}", f"--ipc-cmd-port={self.cmd_port}",
                f"--routes-dir={routes}", "--test-mode", "--quality=low"]
        self.engine = BenchProc("engine", cmd, env, self.out / "engine.log")
        ok = self.engine.wait_for(r"hello_ack reçu", 30.0) is not None
        r.check(ok, "engine relié au core", "hello_ack")
        r.check(self.engine.wait_for(r"route_loaded id=demo", 30.0) is not None, "décor de fond chargé", "demo")
        return ok

    def stop(self) -> None:
        if self.engine is not None and self.engine.p.poll() is None:
            self.engine.stop(signal.SIGTERM, timeout=5.0)
        if self.core is not None:
            rc = self.core.stop(signal.SIGINT, timeout=15.0)
            self.report.check(rc == 0, "arrêt du core", f"code de sortie {rc}")
        if not self.args.keep:
            shutil.rmtree(self.tmp, ignore_errors=True)


# --- parcours ------------------------------------------------------------------------------------

def parcours_connexion_auto(run: Run) -> None:
    if not run.start(READY):
        return
    time.sleep(6.0)   # appareils simulés reliés en une seconde, puis CONNECT_HOLD_S
    run.expect("accueil_seul", "OpenRide", "[Parcours : ", "Session libre", "Trainer")


def parcours_appareils(run: Run) -> None:
    r = run.report
    if not run.start(UNILATERAL):
        return
    time.sleep(3.0)
    run.expect("connexion", "Connexion des appareils", "[Passer — ", "Click − : recherche")
    run.press("PLUS_LONG")
    run.expect("accueil", "OpenRide", "[Parcours : ", "Session ERG")
    run.press("MINUS_SHORT", "MINUS_SHORT", "PLUS_LONG")
    run.expect("reglages", "Réglages", "[Appareils : rechercher et appairer]")
    t = now()
    run.press("PLUS_LONG")
    assert run.engine is not None
    done = run.engine.wait_for(r"scan_results done=true items=(\d+)", 20.0, after=t)
    r.check(done is not None and int(done[1].group(1)) >= 3, "recherche des appareils simulés",
            f"{done[1].group(1)} appareil(s)" if done else "pas de scan_results en 20 s")
    run.expect("appareils", "Appareils", "Trainer : HomeTrainer", "Ceinture :", "appareil(s) trouvé(s)", "[Enregistrer]")
    if not run.focus_to("Enregistrer"):
        r.check(False, "Enregistrer actif", "focus jamais sur « Enregistrer »")
        return
    run.press("PLUS_LONG")
    info = run.shot("confirmation")
    r.check(info["title"].startswith("Enregistrer") and "[Non]" in info["menu"], "confirmation avant l'écriture",
            f"« {info['title']} » {info['menu'][:60]}")
    run.press("PLUS_SHORT", "PLUS_LONG")   # Oui
    time.sleep(2.0)
    text = run.config.read_text(encoding="utf-8")
    r.check("[trainer]" in text and "address" in text, "config.toml écrit par pair_devices", text.replace("\n", " ")[:160])
    run.expect("enregistre", "Appareils", "Relancer OpenRide maintenant", "Enregistré")
    run.focus_to("Relancer")
    run.press("PLUS_LONG")
    rc = None
    deadline = now() + 10.0
    while now() < deadline and rc is None:
        rc = run.engine.p.poll()
        time.sleep(0.2)
    r.check(rc == 64, "Relancer : l'engine sort avec le code 64 (relance par le lanceur)", f"code {rc}")


def _wait_state(run: Run, pattern: str, timeout: float = 10.0, after: float = 0.0) -> bool:
    assert run.core is not None
    return run.core.wait_for(pattern, timeout, after=after) is not None


def parcours_sessions(run: Run) -> None:
    r = run.report
    if not run.start(READY, workout=True):
        return
    time.sleep(5.0)
    run.expect("accueil", "OpenRide", "[Parcours : ", "Session libre", "Session ERG", "Session simulée")
    run.press("PLUS_LONG")
    run.expect("mondes", "Parcours", "[demo")
    run.press("PLUS_LONG")
    run.expect("monde_choisi", "OpenRide", "[Parcours : demo")
    # Session libre : Prêt puis Démarrer.
    run.press("PLUS_SHORT", "PLUS_LONG")
    run.expect("pret_libre", "Prêt : session libre — demo", "[Démarrer]")
    t = now()
    run.press("PLUS_LONG")
    r.check(_wait_state(run, r"RUNNING", 10.0, after=t), "session libre démarrée", "core en RUNNING")
    time.sleep(3.0)
    info = run.shot("en_seance")
    r.check(not info["visible"], "menu caché pendant la séance", f"visible={info['visible']}")
    run.command("pause")   # touche P ou bouton Y : envoyée par l'engine
    time.sleep(1.5)
    run.expect("pause", "Pause", "[Reprendre]")
    t = now()
    run.press("PLUS_SHORT", "PLUS_LONG")   # Terminer et enregistrer
    r.check(_wait_state(run, r"-> FINISHED", 15.0, after=t), "séance terminée et enregistrée", "core en FINISHED")
    time.sleep(1.0)
    run.expect("bilan", "Fin de séance", "[Nouvelle séance]")
    run.press("PLUS_LONG")
    time.sleep(1.0)
    run.expect("accueil_apres", "OpenRide", "Parcours : demo")
    # Session ERG.
    run.press("PLUS_SHORT", "PLUS_SHORT", "PLUS_LONG")
    run.expect("erg_liste", "Session ERG : entraînement", "ERG court")
    if run.focus_to("ERG court"):
        run.press("PLUS_LONG")
    run.expect("pret_erg", "Prêt : session ERG — demo", "[Démarrer]")
    t = now()
    run.press("PLUS_LONG")
    r.check(_wait_state(run, r"RUNNING", 10.0, after=t), "session ERG démarrée", "core en RUNNING")
    time.sleep(4.0)
    info = run.shot("en_seance_erg")
    assert run.engine is not None
    r.check(_wait_state(run, r"ERG court|erg_court", 1.0), "entraînement ERG choisi par le core", "« ERG court » au journal du core")
    run.command("end_session", {"save": False})
    time.sleep(2.0)
    run.press("MINUS_SHORT")   # Quitter (bilan)… ou accueil selon l'état : on revient à l'accueil
    info = run.shot("_apres_erg")
    run.shots.pop()
    if info["title"] == "Fin de séance":
        run.focus_to("Nouvelle séance")
        run.press("PLUS_LONG")
    # Session simulée.
    run.focus_to("Session simulée")
    run.press("PLUS_LONG")
    run.expect("simulee_confirmation", "Session simulée ? OpenRide redémarre sans matériel", "[Non]")
    run.press("PLUS_SHORT", "PLUS_LONG")
    rc = None
    deadline = now() + 10.0
    while now() < deadline and rc is None:
        rc = run.engine.p.poll()
        time.sleep(0.2)
    r.check(rc == 65, "Session simulée : l'engine sort avec le code 65 (relance sans matériel)", f"code {rc}")


def parcours_reglages(run: Run) -> None:
    r = run.report
    if not run.start(READY):
        return
    time.sleep(5.0)
    run.press("MINUS_SHORT", "MINUS_SHORT", "PLUS_LONG")
    run.expect("reglages", "Réglages", "FTP : 250 W", "Difficulté en SIM : ■■■■■□□□□□ 50 %")
    run.focus_to("FTP")
    run.press("PLUS_LONG")
    run.press("PLUS_SHORT", "PLUS_SHORT", "PLUS_SHORT")
    run.expect("ftp_modifiee", "FTP", "[265 W")
    run.press("PLUS_LONG")
    time.sleep(1.0)
    text = run.config.read_text(encoding="utf-8")
    r.check("ftp_w = 265" in text, "FTP écrite dans config.toml", text.replace("\n", " ")[:120])
    run.expect("reglages_apres", "Réglages", "FTP : 265 W")
    run.focus_to("Qualité")
    t = now()
    run.press("PLUS_LONG", "PLUS_SHORT", "PLUS_LONG")
    assert run.engine is not None
    r.check(run.engine.wait_for(r"Qualité graphique : medium", 5.0, after=t) is not None,
            "qualité appliquée tout de suite au décor", "« Qualité graphique : medium » au journal de l'engine")
    r.check("quality = \"medium\"" in run.config.read_text(encoding="utf-8"), "qualité écrite dans config.toml", "medium")
    version = (Path(__file__).resolve().parents[2] / "VERSION").read_text(encoding="utf-8").strip()
    run.focus_to("Plafond du vent", limit=12)
    run.expect("reglages_version", "Réglages", f"OpenRide {version}")
    run.press("MINUS_LONG")   # retour à l'accueil
    run.focus_to("Session libre")
    run.press("PLUS_LONG")                 # Session libre (sans monde : parcours)
    run.press("PLUS_LONG")                 # demo
    t = now()
    run.press("PLUS_LONG")                 # Démarrer
    r.check(_wait_state(run, r"-> RUNNING", 10.0, after=t), "séance démarrée", "RUNNING")
    run.command("pause")
    time.sleep(1.5)
    run.press("MINUS_SHORT")
    run.expect("pause_difficulte", "Pause", "[Difficulté : ■■■■■□□□□□ 50 %]")
    t = now()
    run.press("PLUS_LONG", "MINUS_SHORT", "PLUS_LONG")
    r.check(_wait_state(run, r"Difficulté : 50 % -> 40 %", 5.0, after=t), "curseur de la pause : set_difficulty",
            "« Difficulté : 50 % -> 40 % » au journal du core")
    run.expect("pause_apres", "Pause", "Difficulté : ■■■■□□□□□□ 40 %")
    run.command("end_session", {"save": False})
    time.sleep(1.0)


def parcours_erg(run: Run) -> None:
    """Lot N16 : sous-menu ERG, créer un entraînement par intervalles puis importer un fichier."""
    r = run.report
    if not run.start(READY, workout=True):
        return
    assert run.home is not None and run.core is not None
    wdir = run.home / "OpenRide" / "Workouts"
    downloads = run.home / "Téléchargements"
    downloads.mkdir(parents=True)
    (downloads / "seuil_import.zwo").write_text(ERG_SHORT_ZWO.replace("ERG court", "Seuil importé"), encoding="utf-8")
    time.sleep(5.0)
    run.press("PLUS_SHORT", "PLUS_SHORT", "PLUS_LONG")   # Session ERG
    run.expect("erg_sous_menu", "Session ERG : entraînement", "ERG court", "Créer un entraînement",
               "Importer un fichier")
    run.focus_to("Créer")
    run.press("PLUS_LONG")
    run.expect("creer", "Créer un entraînement", "Répétitions : 5", "Puissance de l'effort : 105 % de la FTP")
    run.focus_to("Répétitions")
    run.press("PLUS_LONG", "PLUS_SHORT", "PLUS_LONG")
    run.expect("creer_6", "Créer un entraînement", "Répétitions : 6")
    run.focus_to("Enregistrer")
    run.press("PLUS_LONG")
    time.sleep(1.5)
    created = wdir / "intervalles_6x240s_105.zwo"
    r.check(created.is_file(), "entraînement créé dans ~/OpenRide/Workouts", created.name)
    run.expect("cree", "Session ERG : entraînement", "Créé : Intervalles 6 × 4 min à 105 %",
               "[Intervalles 6 × 4 min à 105 % (")
    run.press("PLUS_LONG")
    info = run.shot("_apres_choix")
    run.shots.pop()
    if info["title"] == "Parcours":
        run.press("PLUS_LONG")
    run.expect("pret_cree", "Prêt : session ERG — demo", "[Démarrer]")
    t = now()
    run.press("PLUS_LONG")
    r.check(_wait_state(run, r"RUNNING", 10.0, after=t), "séance avec l'entraînement créé", "core en RUNNING")
    r.check(_wait_state(run, r"intervalles_6x240s_105|Intervalles 6", 2.0), "entraînement créé lu par le core",
            "« intervalles_6x240s_105 » au journal du core")
    run.command("end_session", {"save": False})
    time.sleep(2.0)
    info = run.shot("_apres_seance")
    run.shots.pop()
    if info["title"] == "Fin de séance":
        run.focus_to("Nouvelle séance")
        run.press("PLUS_LONG")
        time.sleep(1.0)
    run.focus_to("Session ERG")
    run.press("PLUS_LONG")
    run.focus_to("Importer", limit=10)
    run.press("PLUS_LONG")
    time.sleep(0.5)
    run.expect("importer", "Importer un entraînement", "[seuil_import.zwo", "Téléchargements")
    run.press("PLUS_LONG")
    time.sleep(1.5)
    r.check((wdir / "seuil_import.zwo").is_file(), "fichier importé dans ~/OpenRide/Workouts", "seuil_import.zwo")
    run.expect("importe", "Session ERG : entraînement", "Importé : Seuil importé", "[Seuil importé")


PARCOURS: dict[str, Callable[[Run], None]] = {
    "connexion_auto": parcours_connexion_auto,
    "appareils": parcours_appareils,
    "sessions": parcours_sessions,
    "reglages": parcours_reglages,
    "erg": parcours_erg,
}


def write_html(out: Path, runs: list[Run]) -> Path:
    parts = ["<!doctype html><meta charset='utf-8'><title>Banc des menus</title>",
             ("<style>body{font-family:sans-serif;margin:16px}img{width:420px;border:1px solid #888}"
              "figure{display:inline-block;margin:6px}.ko{color:#b00}.ok{color:#070}</style>"),
             "<h1>Banc des menus</h1>"]
    for run in runs:
        parts.append(f"<h2>{html.escape(run.name)} : {len(run.report.rows) - run.report.failed}/"
                     f"{len(run.report.rows)}</h2><ul>")
        for ok, label, measure in run.report.rows:
            parts.append(f"<li class='{'ok' if ok else 'ko'}'>{'OK' if ok else 'ÉCHEC'} {html.escape(label)} : "
                         f"{html.escape(measure)}</li>")
        parts.append("</ul>")
        for s in run.shots:
            parts.append(f"<figure><img src='{html.escape(run.name)}/{html.escape(s['file'])}'>"
                         f"<figcaption>{html.escape(s['tag'])} : {html.escape(s['title'])}</figcaption></figure>")
    path = out / "rapport.html"
    path.write_text("\n".join(parts), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--godot", type=Path, default=Path(os.environ.get(
        "GODOT", Path.home() / "Applications/godot/Godot_v4.3-stable_linux.x86_64")))
    ap.add_argument("--parcours", action="append", choices=sorted(PARCOURS))
    ap.add_argument("--native", action="store_true", help="fenêtre sur l'écran réel au lieu de Xvfb")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--keep", action="store_true", help="garde le HOME temporaire")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)
    if args.list:
        for name in PARCOURS:
            print(name)
        return 0
    if not os.access(args.godot, os.X_OK):
        print(f"Godot introuvable : {args.godot}")
        return 2
    if not args.native and shutil.which("xvfb-run") is None:
        print("xvfb-run introuvable")
        return 2
    out = args.out or Path(tempfile.mkdtemp(prefix="openride-banc-menus-"))
    runs: list[Run] = []
    for name in args.parcours or list(PARCOURS):
        print(f"== {name} ==", flush=True)
        run = Run(args, name, out / name)
        try:
            PARCOURS[name](run)
        finally:
            run.stop()
        runs.append(run)
    report = write_html(out, runs)
    failed = sum(r.report.failed for r in runs)
    print(f"Rapport : {report}\n{'OK' if failed == 0 else f'{failed} vérification(s) en échec'}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
