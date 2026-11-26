#!/usr/bin/env python3
"""Essai d'endurance avant livraison (lot EN1) : séance de 2 h puis saison complète de la ligue d'hiver, enchaînées
dans le même core et le même engine, sur le Bluetooth simulé.

    essai_endurance.py [--godot CHEMIN] [--native] [--quality medium] [--phase tout|seance|saison]
                       [--seance-min 120] [--manche-s S] [--debut AAAA-MM-JJ] [--court] [--sans-engine] [--out DOSSIER]

Ce que fait l'essai (procédure et critères : `docs/ESSAI_ENDURANCE.md`) :

1. **Séance de 2 h** (`--seance-min`) : balade libre sur un anneau synthétique, effort du cycliste virtuel changé
   toutes les 5 min et un appui du Click à chaque changement (comme le scénario `endurance` de `sim_bench.py`, mais
   deux fois plus long et sans relancer les processus) ; le parcours est relancé s'il se termine.
2. **Saison de la ligue** : 8 semaines simulées sans relancer le core. Le core tourne sous `horloge_decalee.py` :
   l'horloge murale avance au mercredi de chaque semaine, la manche de la semaine est courue en mode Course
   (`start` avec `league` = vrai, 11 rivaux, environ 27 min par manche), puis la ligue est relue le lundi qui
   suit la semaine 8 : saison close, 8 résultats « joueur », 12 coureurs au classement.

Mesures : sonde de performance de l'engine (temps GPU de la vue, images/s, saccades, mémoire vidéo) et du système
(mémoire et CPU du core et de Godot) chaque seconde, taille des fichiers du profil et des journaux chaque minute
(`fichiers.csv`). Verdict dans `verdict.md` et `verdict.json`, code de sortie 0 si tout passe, 1 sinon, 2 pour
un appel invalide (Godot absent).

Garde-fous : HOME temporaire (rien n'est lu ni écrit dans le vrai ~/OpenRide, ni dans `~/OpenRide/Cache/monde`) ;
aucun réseau ; aucun fichier du jeu modifié ; ports UDP libres. `--court` : essai à blanc (séance de 6 min, manches
de 90 s) pour vérifier la chaîne en une trentaine de minutes. `--sans-engine` : core seul (cloud, sans Godot).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import statistics
import sys
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR))
import sim_bench  # noqa: E402
from sim_bench import ENGINE_DIR, REPO, BenchProc, free_udp_ports, now, render_section, send_cmd  # noqa: E402
import perf_probe  # noqa: E402
import rendu_jeu  # noqa: E402

sys.path.insert(0, str(REPO / "core" / "src"))
from openride_core import velodrome  # noqa: E402
from openride_core.demo_world import write_world  # noqa: E402
from openride_core.tools.route_vectors import _route  # noqa: E402

try:   # ligue d'hiver (série CH) : absente du core avant CH3 (#989)
    from openride_core import league  # noqa: E402
except ImportError:   # pragma: no cover - version sans ligue
    league = None

ROUTE_ID = "anneau_endurance"
LINE_ID = "ligne_endurance"     # manche à arrivée en côte (parcours en ligne)
# Parcours de chaque terrain de manche (`league.Round.terrain`) : la manche refuse un parcours qui ne s'y prête pas.
TERRAIN_ROUTES = {"boucle": ROUTE_ID, "grandprix": ROUTE_ID, "piste": velodrome.TRACK_ID, "arrivee_cote": LINE_ID}
FIELD = 11                       # rivaux de la manche (`league.FIELD_SIZE`)
WEEKS = 8
EFFORT_CYCLE = ((220, 90), (200, 90), (260, 85), (180, 80), (300, 90), (240, 80))   # FTP fictive 250 W
EFFORT_PERIOD_S = 300.0
FILES_PERIOD_S = 60.0
CMD_BASE = 30_000
GPU_BUDGET_MS = {"low": 8.0, "medium": 13.0, "high": 16.0}   # perf_targets.json (budgets du propriétaire)

# Critères chiffrés (docs/ESSAI_ENDURANCE.md §3). Mémoire en Mo, tailles en Mo sauf mention.
LIMITS = {
    "core_rss_max_mb": 400.0,          # core seul : ~120 Mo mesurés au cloud ; marge ×3
    "core_slope_mb_h": 20.0,           # perf_probe.ENDURANCE_LIMITS
    "godot_slope_mb_h": 100.0,
    "godot_growth_mb": 300.0,          # mémoire de Godot, dernière demi-heure contre la première après la mise en route
    "vram_slope_mb_h": 50.0,
    "gpu_drift_pct": 10.0,             # temps GPU de la vue, dernière demi-heure contre la première
    "stutters_per_h": 6.0,
    "journal_mb_per_h": 15.0,          # journaux de séance (.jsonl) : par heure roulée
    "fit_kb_per_h": 1500.0,            # FIT : un enregistrement par seconde
    "core_log_mb": 50.0,               # journal du core sur tout l'essai
    "engine_log_mb": 50.0,
    "ligue_kb": 100.0,
    "elo_kb": 200.0,
    "profile_growth_mb": 200.0,        # ~/OpenRide entier, fin contre début
}


class _Stop(Exception):
    """Arrêt anticipé de l'essai (core absent) : le verdict s'écrit quand même."""


class Clock:
    """Horloge murale du core : décalage écrit dans un fichier que `horloge_decalee.py` relit chaque seconde."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.set(datetime.now())

    def set(self, when: datetime) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"decalage_s": when.timestamp() - time.time(), "jour": when.isoformat()}),
                       encoding="utf-8")
        tmp.replace(self.path)

    def go(self, when: datetime) -> None:
        self.set(when)
        time.sleep(2.0)   # relu chaque seconde par le core


def write_ring(routes: Path, length_m: float) -> None:
    """Anneau fermé de `length_m` (pas de 10 m) avec une bosse douce de 8 m : la manche de la ligue se court en tours."""
    world = write_world(routes, ROUTE_ID, length_m, title="Anneau d'endurance (banc)")
    n = int(length_m / 10.0) + 1
    headings = [i * 360.0 / (n - 1) for i in range(n)]
    alts = [100.0 + 8.0 * (1.0 - abs(2.0 * i / (n - 1) - 1.0)) for i in range(n)]
    (world / "route.json").write_text(json.dumps(_route(headings, alts, ds=10.0, last=10.0, kind="loop")),
                                      encoding="utf-8")


def dir_mb(path: Path, pattern: str = "*") -> float:
    if not path.exists():
        return 0.0
    return sum(p.stat().st_size for p in path.rglob(pattern) if p.is_file()) / 1e6


def next_monday(d: date) -> date:
    return d + timedelta(days=(7 - d.weekday()) % 7 or 7)


def write_line(routes: Path, length_m: float) -> None:
    """Parcours en ligne de `length_m`, plat puis une côte de 4 % sur son dernier kilomètre (arrivée en côte)."""
    climb = min(1000.0, 0.3 * length_m)
    write_world(routes, LINE_ID, length_m, title="Ligne d'endurance (banc)",
                grade=lambda s: 4.0 if s >= length_m - climb else 0.0)


def line_length_m(manche_s: float | None) -> float:
    """Longueur du parcours en ligne pour une manche d'environ `manche_s` à ~9 m/s (1 km de course au moins)."""
    return max(2000.0, round((manche_s or 27 * 60) * 9.0, -2))


def race_over(mode: str, lines: list[str]) -> bool:
    """Issue de la manche connue dans les lignes du core lues depuis son départ : depuis le lot RT2, l'arrivée ne
    ferme plus la séance (le cycliste roule au calme jusqu'à « Terminer et enregistrer », A maintenu) ; le banc
    demande alors le bilan comme le joueur. Course et Grand Prix : arrivée ; Dernier survivant : cycliste éliminé
    ou dernier en course ; piste : cycliste sorti ou épreuve finie."""
    text = "\n".join(lines)
    if mode in ("race", "grandprix"):
        return re.search(r"Arrivée \((?:race|grandprix)\)", text) is not None
    if mode == "survivor":
        out = re.findall(r"Dernier survivant : (.+?) éliminé à l'arche", text)
        return "cycliste" in out or len(out) >= FIELD
    if mode == "track":
        return re.search(r"Épreuve de piste \S+ : event = (?:finish|out, rider = me)\b", text) is not None
    return False


class Endurance:
    def __init__(self, args: argparse.Namespace) -> None:
        self.a = args
        self.out: Path = args.out
        self.checks: list[dict[str, Any]] = []
        self.phases: list[dict[str, Any]] = []      # nom, début et fin (secondes depuis le démarrage du core)
        self.files_rows: list[dict[str, Any]] = []
        self.weeks: list[dict[str, Any]] = []
        self.cmd_id = CMD_BASE
        self.effort_i = 0
        self.t0 = 0.0

    # --- outils ---------------------------------------------------------------------------------

    def check(self, ok: bool | None, label: str, measure: str) -> None:
        tag = "OK" if ok else ("INFO" if ok is None else "ÉCHEC")
        print(f"[{tag}] {label} : {measure}", flush=True)
        self.checks.append({"ok": ok, "label": label, "measure": measure})

    def rel(self) -> float:
        return now() - self.t0

    def cmd(self, name: str, args: dict[str, Any] | None = None) -> None:
        self.cmd_id += 1
        send_cmd(self.cmd_port, self.cmd_id, name, args or {})

    def control(self, line: dict[str, Any]) -> None:
        with self.control_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line) + "\n")

    def next_effort(self) -> None:
        watts, rpm = EFFORT_CYCLE[self.effort_i % len(EFFORT_CYCLE)]
        self.control({"device": "trainer", "action": "rider", "watts": watts, "cadence_rpm": rpm})
        self.control({"action": "press", "button": "+" if self.effort_i % 2 else "-"})
        self.effort_i += 1

    def sample_files(self, phase: str) -> None:
        root = self.home / "OpenRide"
        self.files_rows.append({
            "t_s": round(self.rel(), 1), "phase": phase, "profil_mo": round(dir_mb(root), 3),
            "journaux_mo": round(dir_mb(root, "*.jsonl"), 3), "fit_mo": round(dir_mb(root, "*.fit"), 3),
            "core_log_mo": round(self.core_log.stat().st_size / 1e6, 3) if self.core_log.exists() else 0.0,
            "engine_log_mo": round(self.engine_log.stat().st_size / 1e6, 3) if self.engine_log.exists() else 0.0,
        })

    def ride(self, phase: str, seconds: float, until_finished: bool, relaunch: dict[str, Any] | None,
             mode: str | None = None) -> bool:
        """Roule `seconds` (ou jusqu'à FINISHED si `until_finished`) : effort changé toutes les 5 min, fichiers
        relevés chaque minute, parcours relancé s'il finit (balade libre). Avec `mode` (manche de la ligue) : une
        fois l'issue connue (`race_over`), bilan demandé par `end_session`. Rend vrai si FINISHED est vu."""
        start = now()
        after = start
        asked = False
        next_effort = start + EFFORT_PERIOD_S
        next_files = start
        while now() - start < seconds:
            if now() >= next_effort:
                self.next_effort()
                next_effort += EFFORT_PERIOD_S
            if now() >= next_files:
                self.sample_files(phase)
                next_files += FILES_PERIOD_S
            if mode is not None and not asked and race_over(mode, [ln for tt, ln in self.core.lines if tt >= start]):
                asked = True
                self.cmd("end_session", {"save": True})   # « A maintenu = bilan », comme le joueur
            fin = self.core.wait_for(r"-> FINISHED", 1.0, after=after)
            if fin is not None:
                after = fin[0] + 1e-3
                if until_finished:
                    return True
                if relaunch is not None:
                    self.start_session(relaunch)
            if self.core.p.poll() is not None:
                self.check(False, f"{phase} : core vivant", f"code de sortie {self.core.p.returncode}")
                return False
            if self.engine is not None and self.engine.p.poll() is not None:
                self.check(False, f"{phase} : engine vivant", f"code de sortie {self.engine.p.returncode}")
                return False
        return False

    def session_state(self) -> str:
        """Dernier état de séance lu dans le journal du core (« Séance : A -> B »)."""
        for _, ln in reversed(self.core.lines):
            m = re.search(r"Séance : \S+ -> (\w+)", ln)
            if m:
                return m.group(1)
        return "IDLE"

    def close_open_session(self) -> None:
        """Séance restée ouverte (manche précédente sans issue dans le temps imparti) : fermée avant le
        `select_route` suivant, refusé hors de IDLE, READY, FINISHED et ERROR."""
        if self.session_state() in ("IDLE", "READY", "FINISHED", "ERROR"):
            return
        t = now()
        self.cmd("end_session", {"save": True})
        fin = self.core.wait_for(r"-> (?:FINISHED|IDLE|ERROR)", 15.0, after=t)
        self.check(fin is not None, "séance restée ouverte : fermée", "end_session accepté" if fin else "absente en 15 s")
        time.sleep(1.0)

    def start_session(self, start_args: dict[str, Any], route_id: str = ROUTE_ID) -> tuple[bool, str]:
        self.close_open_session()
        t = now()
        self.cmd("select_route", {"route_id": route_id})
        ready = self.core.wait_for(r"-> READY", 30.0, after=t)
        if ready is None:
            return False, "pas de READY en 30 s après select_route"
        self.cmd("start", start_args)
        run = self.core.wait_for(r"-> RUNNING", 20.0, after=ready[0])
        if run is not None:
            return True, f"départ {run[0] - t:.1f} s après select_route"
        refus = [ln for tt, ln in self.core.lines if tt >= ready[0] and re.search(r"refus|bad_args|ERROR|erreur", ln, re.I)]
        return False, refus[-1][:200] if refus else "pas de RUNNING en 20 s"

    def find(self, name: str) -> Path | None:
        hits = sorted(self.home.rglob(name))
        return hits[0] if hits else None

    def league_json(self) -> dict[str, Any] | None:
        p = self.find("ligue.json")
        try:
            return json.loads(p.read_text(encoding="utf-8")) if p else None
        except (OSError, ValueError):
            return None

    # --- déroulé ----------------------------------------------------------------------------------

    def run(self) -> int:
        a = self.a
        self.out.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix="openride-endurance-"))
        self.home = tmp / "home"
        self.home.mkdir()
        real_home = Path(os.environ.get("HOME", "/nonexistent")).resolve()
        assert self.home.resolve() != real_home and "Cache/monde" not in str(self.home)
        routes = self.home / ".local" / "share" / "openride" / "routes"
        routes.mkdir(parents=True)
        write_ring(routes, a.anneau_m)
        write_line(routes, line_length_m(a.manche_s))
        velodrome.write_velodrome(routes)
        state_port, self.cmd_port = free_udp_ports(2)
        cfg = tmp / "config.toml"
        cfg.write_text("\n".join([f"[ipc]\nport_state = {state_port}\nport_commands = {self.cmd_port}\n",
                                  render_section(a.quality), '[depart]\nmode = "immediat"\n']), encoding="utf-8")
        self.control_file = tmp / "appuis.jsonl"
        self.control_file.write_text("", encoding="utf-8")
        w0, r0 = EFFORT_CYCLE[0]
        scen = tmp / "endurance_saison.json"
        scen.write_text(json.dumps({
            "description": "Essai d'endurance (lot EN1) : effort piloté par le banc (control_file).",
            "trainer": {"appear_at": 0.3, "connect_delay_s": 0.3},
            "rider": {"strategy": "constante", "watts": w0, "cadence_rpm": r0},
            "click": {"appear_at": 0.5, "connect_delay_s": 0.3}, "hr": {"appear_at": 0.5, "connect_delay_s": 0.2},
            "events": [], "control_file": str(self.control_file)}), encoding="utf-8")
        clock = Clock(tmp / "horloge.json")
        env = {**os.environ, "HOME": str(self.home), "PYTHONUNBUFFERED": "1", "PYTHONPATH": str(REPO / "core" / "src")}
        for k in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "OPENRIDE_PROFIL"):
            env.pop(k, None)
        if a.manche_s:
            env["OPENRIDE_ESSAI_MANCHE_S"] = str(a.manche_s)
        argv = [sys.executable, str(TESTS_DIR / "horloge_decalee.py"), "openride_core", str(clock.path), "run",
                "--config", str(cfg), "--trainer", "sim", "--input", "sim", "--hr", "sim",
                "--sim-scenario", str(scen)]   # sans --route : sans --autostart, le parcours vient de select_route
        self.core_log, self.engine_log = self.out / "core.log", self.out / "engine.log"
        self.core = self.engine = None
        sampler = perf_probe.SystemSampler()
        debut = a.debut or next_monday(date.today())
        print(f"== Essai d'endurance : {a.phase}, qualité {a.quality}, séance {a.seance_min:g} min, "
              f"saison du lundi {debut.isoformat()}{', essai à blanc' if a.court else ''} ==", flush=True)
        try:
            clock.set(datetime.combine(debut - timedelta(days=2), datetime.min.time()) + timedelta(hours=10))
            self.core = BenchProc("core", argv, env, self.core_log)
            started = self.core.wait_for(r"Core démarré", 30.0)
            self.check(started is not None, "démarrage du core", "« Core démarré » lu" if started else "absent en 30 s")
            if started is None:
                raise _Stop
            self.t0 = started[0]
            if not a.sans_engine:
                cmd = rendu_jeu.godot_cmd([a.godot, "--path", str(ENGINE_DIR), "--resolution", a.size,
                                           "--audio-driver", "Dummy"], a.native, *(int(v) for v in a.size.split("x")))
                cmd += ["--", f"--ipc-state-port={state_port}", f"--ipc-cmd-port={self.cmd_port}",
                        f"--routes-dir={routes}", "--test-mode", f"--quality={a.quality}",
                        f"--perf-probe={(self.out / 'moteur.csv').resolve()}"]
                self.engine = BenchProc("engine", [str(c) for c in cmd], env, self.engine_log)
                ack = self.engine.wait_for(r"hello_ack reçu", 60.0)
                self.check(ack is not None, "engine relié au core", "hello_ack reçu" if ack else "pas de hello_ack en 60 s")
            sampler.start()
            if a.phase in ("tout", "seance"):
                self.phase_seance()
            if a.phase in ("tout", "saison"):
                self.phase_saison(clock, debut)
        except _Stop:
            pass
        finally:
            if self.engine is not None:
                self.engine.stop(signal.SIGTERM, timeout=10.0)
            sampler.stop()
            if self.core is not None:
                rc = self.core.stop(signal.SIGINT, timeout=20.0)
                self.check(rc == 0, "arrêt du core", f"code de sortie {rc}")
        return self.finish(tmp, sampler)

    def phase_seance(self) -> None:
        a = self.a
        t = self.rel()
        ok, detail = self.start_session({})
        self.check(ok, "séance : départ", detail)
        if ok:
            self.ride("seance", a.seance_min * 60.0, until_finished=False, relaunch={})
            t_end = now()
            self.cmd("end_session", {"save": True})
            fin = self.core.wait_for(r"-> FINISHED", 15.0, after=t_end)
            self.check(fin is not None, "séance : fin enregistrée", "FINISHED après end_session" if fin else "absente en 15 s")
            time.sleep(3.0)
        self.sample_files("seance")
        self.phases.append({"phase": "seance", "debut_s": t, "fin_s": self.rel()})

    def phase_saison(self, clock: Clock, debut: date) -> None:
        a = self.a
        t = self.rel()
        timeout = (a.manche_s or 27 * 60) * 3 + 600
        for i in range(WEEKS):
            day = debut + timedelta(weeks=i, days=2)
            clock.go(datetime.combine(day, datetime.min.time()) + timedelta(hours=18))
            self.cmd("league_status")
            if i == 0:
                self.cmd("league_new")
                for _ in range(20):
                    if self.league_json():
                        break
                    time.sleep(0.5)
                if not self.check_league_created():
                    break
            t_week = self.rel()
            rnd = league.ROUNDS[i] if league is not None else None
            mode = rnd.mode if rnd is not None else "race"
            playable = getattr(league, "PLAYABLE_MODES", ("race",))
            row: dict[str, Any] = {"semaine": i + 1, "jour": day.isoformat(), "mode": mode}
            if mode not in playable:
                # Mode pas encore branché dans la ligue (CH3b) : la semaine est simulée pour les rivaux, comme une
                # semaine non courue ; ce n'est pas un échec de l'essai.
                row.update(depart=False, detail=f"{rnd.short if rnd else mode} : pas encore jouable dans cette version")
                self.weeks.append(row)
                self.check(None, f"saison : manche {i + 1} ({day.isoformat()})", row["detail"] + ", simulée pour les rivaux")
                continue
            route_id = TERRAIN_ROUTES.get(rnd.terrain if rnd is not None else "boucle", ROUTE_ID)
            row["parcours"] = route_id
            ok, detail = self.start_session({"mode": mode, "league": True}, route_id)
            row.update(depart=ok, detail=detail)
            if ok:
                # Dernier survivant (une arche par rival, 1 km au moins entre deux) et élimination de la piste (un
                # rival sorti tous les 4 tours de 250 m) : jusqu'à 11 km quelle que soit `--manche-s`, à ~6 m/s
                limit = max(timeout, FIELD * 1000.0 / 6.0 + 600) if mode in ("survivor", "track") else timeout
                row["arrivee"] = self.ride(f"manche {i + 1}", limit, until_finished=True, relaunch=None, mode=mode)
                time.sleep(3.0)
                data = self.league_json() or {}
                res = (data.get("results") or {}).get(str(i))
                row["resultat"] = res
                row["duree_min"] = round((self.rel() - t_week) / 60.0, 1)
            self.weeks.append(row)
            self.check(bool(ok and row.get("arrivee") and row.get("resultat")), f"saison : manche {i + 1} ({day.isoformat()})",
                       f"{detail} ; arrivée en {row.get('duree_min', '?')} min, place "
                       f"{((row.get('resultat') or {}).get('places') or {}).get('me', '?')}" if ok else detail)
        end = debut + timedelta(weeks=WEEKS, days=1)
        clock.go(datetime.combine(end, datetime.min.time()) + timedelta(hours=9))
        self.cmd("league_status")
        time.sleep(3.0)
        data = self.league_json() or {}
        results = data.get("results") or {}
        joueur = sum(1 for r in results.values() if r.get("source") == "joueur")
        playable_weeks = sum(1 for w in self.weeks if "pas encore jouable" not in str(w.get("detail")))
        self.check(joueur == playable_weeks and len(results) == WEEKS, "saison : résultats",
                   f"{joueur} manche(s) courue(s) par le joueur sur {playable_weeks} jouable(s), "
                   f"{len(results)} sur {WEEKS} au calendrier (les autres simulées)")
        self.check(data.get("closed") == "fin", "saison : close le lundi qui suit la semaine 8",
                   f"état {data.get('closed')!r}, dernier jour vu {data.get('last_seen')}")
        self.sample_files("saison")
        self.phases.append({"phase": "saison", "debut_s": t, "fin_s": self.rel()})

    def check_league_created(self) -> bool:
        data = self.league_json()
        if data is None:
            unknown = [ln for _, ln in self.core.lines if "league" in ln and re.search(r"inconnu|unknown", ln, re.I)]
            self.check(False, "saison : créée", "ligue.json absent" + (" ; la ligue (CH3, #989) n'est pas dans cette "
                                                                     "version du core" if unknown else ""))
            return False
        self.check(len(data.get("rivals") or []) == 11, "saison : créée", f"saison {data.get('number')}, "
                   f"{len(data.get('rivals') or [])} rivaux, départ {data.get('start')}")
        return True

    # --- analyse ----------------------------------------------------------------------------------

    def finish(self, tmp: Path, sampler: perf_probe.SystemSampler) -> int:
        a = self.a
        if self.engine is not None and (self.out / "moteur.csv").exists():
            rows = perf_probe.merge(perf_probe.read_engine_csv(self.out / "moteur.csv"), sampler.rows)
            perf_probe.write_report(rows, self.out / "sonde", "Sonde de performance : essai d'endurance",
                                    real_window=a.native, engine_dir=self.out)
        else:
            t_first = sampler.rows[0]["unix_s"] if sampler.rows else 0.0
            rows = [{**r, "t_s": r["unix_s"] - t_first} for r in sampler.rows]
        self.analyse(rows)
        self.write(rows)
        if not a.garder:
            shutil.rmtree(tmp, ignore_errors=True)
        else:
            print(f"Dossier temporaire gardé : {tmp}")
        failed = sum(1 for c in self.checks if c["ok"] is False)
        print(f"== {len(self.checks) - failed} vérification(s) sur {len(self.checks)} sans échec ; verdict : "
              f"{self.out / 'verdict.md'}", flush=True)
        return 1 if failed else 0

    def analyse(self, rows: list[dict[str, Any]]) -> None:
        a = self.a
        real = a.native
        warm = perf_probe.ENDURANCE_LIMITS["warmup_s"] if not a.court else 30.0
        span = max(perf_probe.values(rows, "t_s") or [0.0]) - min(perf_probe.values(rows, "t_s") or [0.0])
        long_enough = span - warm >= 1200.0
        # Mémoire du core.
        core = perf_probe.values(rows, "core_rss_mb")
        if core:
            self.check(max(core) <= LIMITS["core_rss_max_mb"], "mémoire du core : maximum",
                       f"{max(core):.0f} Mo (au plus {LIMITS['core_rss_max_mb']:.0f})")
        for key, lim, label in (("core_rss_mb", "core_slope_mb_h", "core"), ("godot_rss_mb", "godot_slope_mb_h", "Godot"),
                                ("vram_mb", "vram_slope_mb_h", "mémoire vidéo")):
            slope = perf_probe.slope_per_hour(rows, key, min(perf_probe.values(rows, "t_s") or [0.0]) + warm)
            if slope is not None:
                self.check(slope <= LIMITS[lim] if long_enough else None, f"croissance : {label}",
                           f"{slope:+.1f} Mo/h (au plus {LIMITS[lim]:.0f}"
                           + ("" if long_enough else ", indicatif : moins de 20 min mesurées") + ")")
        halves = self.first_last(rows, warm, 1800.0)
        if halves:
            first, last = halves
            g1, g2 = perf_probe.values(first, "godot_rss_mb"), perf_probe.values(last, "godot_rss_mb")
            if g1 and g2:
                d = statistics.median(g2) - statistics.median(g1)
                self.check(d <= LIMITS["godot_growth_mb"], "mémoire de Godot : fin contre début",
                           f"{statistics.median(g1):.0f} → {statistics.median(g2):.0f} Mo ({d:+.0f}, au plus "
                           f"+{LIMITS['godot_growth_mb']:.0f})")
            p1, p2 = perf_probe.values(first, "gpu_ms"), perf_probe.values(last, "gpu_ms")
            if p1 and p2 and statistics.median(p1) > 0:
                drift = (statistics.median(p2) / statistics.median(p1) - 1.0) * 100.0
                self.check(drift <= LIMITS["gpu_drift_pct"] if real else None, "temps GPU de la vue : dérive",
                           f"{statistics.median(p1):.2f} → {statistics.median(p2):.2f} ms ({drift:+.0f} %, au plus "
                           f"+{LIMITS['gpu_drift_pct']:.0f} %)" + ("" if real else ", indicatif sous Xvfb"))
        # Temps GPU de la vue par phase, contre le budget du préréglage.
        budget = GPU_BUDGET_MS.get(a.quality)
        for ph in self.phases:
            sel = [r for r in rows if ph["debut_s"] + warm <= r.get("t_s", -1) <= ph["fin_s"]]
            gpu = perf_probe.values(sel, "gpu_ms")
            if gpu and budget:
                med, p95 = statistics.median(gpu), perf_probe.percentile(gpu, 0.95)
                self.check(med <= budget if real else None, f"{ph['phase']} : GPU de la vue ({a.quality})",
                           f"médiane {med:.2f} ms, 95e centile {p95:.2f} ms (médiane au plus {budget:g} ms)"
                           + ("" if real else ", indicatif sous Xvfb"))
        if any("frame_max_ms" in r for r in rows):
            for ok, label, measure in perf_probe.endurance_checks(rows, real_window=real):
                if "saccades" in label or "images/s" in label:
                    self.check(ok, label, measure)
        # Fichiers produits.
        if self.files_rows:
            last, first = self.files_rows[-1], self.files_rows[0]
            hours = max(sum(p["fin_s"] - p["debut_s"] for p in self.phases) / 3600.0, 1e-3)
            self.check(last["journaux_mo"] / hours <= LIMITS["journal_mb_per_h"], "journaux de séance",
                       f"{last['journaux_mo']:.1f} Mo pour {hours:.2f} h ({last['journaux_mo'] / hours:.1f} Mo/h, au plus "
                       f"{LIMITS['journal_mb_per_h']:g})")
            self.check(last["fit_mo"] * 1000 / hours <= LIMITS["fit_kb_per_h"], "fichiers FIT",
                       f"{last['fit_mo'] * 1000:.0f} Ko ({last['fit_mo'] * 1000 / hours:.0f} Ko/h, au plus "
                       f"{LIMITS['fit_kb_per_h']:g})")
            self.check(last["core_log_mo"] <= LIMITS["core_log_mb"], "journal du core",
                       f"{last['core_log_mo']:.1f} Mo (au plus {LIMITS['core_log_mb']:g})")
            if self.engine is not None:
                self.check(last["engine_log_mo"] <= LIMITS["engine_log_mb"], "journal de l'engine",
                           f"{last['engine_log_mo']:.1f} Mo (au plus {LIMITS['engine_log_mb']:g})")
            growth = last["profil_mo"] - first["profil_mo"]
            self.check(growth <= LIMITS["profile_growth_mb"], "profil ~/OpenRide : croissance",
                       f"{growth:+.1f} Mo (au plus {LIMITS['profile_growth_mb']:g})")
        for name, lim in (("ligue.json", "ligue_kb"), ("elo.json", "elo_kb")):
            p = self.find(name)
            if p is not None:
                kb = p.stat().st_size / 1000
                self.check(kb <= LIMITS[lim], f"taille de {name}", f"{kb:.1f} Ko (au plus {LIMITS[lim]:g})")
        fits = list(self.home.rglob("*.fit"))
        expected = (1 if any(p["phase"] == "seance" for p in self.phases) else 0) + \
            sum(1 for w in self.weeks if w.get("arrivee"))
        self.check(len(fits) >= expected, "séances enregistrées (FIT)", f"{len(fits)} (au moins {expected})")
        text = self.core_log.read_text(encoding="utf-8", errors="replace") if self.core_log.exists() else ""
        crashes = [ln for ln in text.splitlines() if "Traceback" in ln or " CRITICAL " in ln]
        self.check(not crashes, "journal du core : aucune exception", f"{len(crashes)} trace(s)"
                   + (f", ex. {crashes[0][:160]}" if crashes else ""))

    @staticmethod
    def first_last(rows: list[dict[str, Any]], warm: float, window: float) -> tuple[list, list] | None:
        ts = perf_probe.values(rows, "t_s")
        if not ts or max(ts) - min(ts) - warm < 2 * window:
            return None
        a0, end = min(ts) + warm, max(ts)
        return ([r for r in rows if a0 <= r.get("t_s", -1) < a0 + window],
                [r for r in rows if end - window < r.get("t_s", -1) <= end])

    def write(self, rows: list[dict[str, Any]]) -> None:
        if self.files_rows:
            cols = list(self.files_rows[0])
            (self.out / "fichiers.csv").write_text(",".join(cols) + "\n" + "".join(
                ",".join(str(r[c]) for c in cols) + "\n" for r in self.files_rows), encoding="utf-8")
        if rows and self.engine is None:
            perf_probe.write_csv(rows, self.out / "systeme.csv")
        failed = sum(1 for c in self.checks if c["ok"] is False)
        verdict = "RÉUSSI" if not failed else f"ÉCHEC ({failed})"
        lines = [f"# Essai d'endurance : {verdict}", "",
                 f"Phase {self.a.phase}, qualité {self.a.quality}, séance {self.a.seance_min:g} min"
                 f"{', essai à blanc (--court)' if self.a.court else ''}"
                 f"{', core seul' if self.engine is None else ''}"
                 f"{', fenêtre réelle' if self.a.native else ', Xvfb (mesures GPU indicatives)'}.", "",
                 "| Résultat | Vérification | Mesure |", "| --- | --- | --- |"]
        for c in self.checks:
            tag = "OK" if c["ok"] else ("info" if c["ok"] is None else "**ÉCHEC**")
            lines.append(f"| {tag} | {c['label']} | {c['measure'].replace('|', '/')} |")
        if self.weeks:
            lines += ["", "## Saison", "", "| Semaine | Jour simulé | Départ | Durée (min) | Place |", "| --- | --- | --- | --- | --- |"]
            for w in self.weeks:
                place = ((w.get("resultat") or {}).get("places") or {}).get("me", "-")
                lines.append(f"| {w['semaine']} | {w['jour']} | {'oui' if w['depart'] else w['detail'][:60]} | "
                             f"{w.get('duree_min', '-')} | {place} |")
        (self.out / "verdict.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (self.out / "verdict.json").write_text(json.dumps({"verdict": verdict, "checks": self.checks, "phases": self.phases,
                                                          "semaines": self.weeks, "limites": LIMITS},
                                                         indent=1, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--godot", type=Path, default=Path(os.environ.get(
        "GODOT", Path.home() / "Applications/godot/Godot_v4.7.2-stable_linux.x86_64")))
    ap.add_argument("--native", action="store_true", help="fenêtre sur l'écran réel (mesures GPU jugées)")
    ap.add_argument("--quality", choices=sorted(GPU_BUDGET_MS), default="medium")
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--phase", choices=["tout", "seance", "saison"], default="tout")
    ap.add_argument("--seance-min", type=float, default=120.0)
    ap.add_argument("--manche-s", type=float, default=None, help="durée visée d'une manche (défaut : celle du jeu, ~27 min)")
    ap.add_argument("--anneau-m", type=float, default=3000.0)
    ap.add_argument("--debut", type=date.fromisoformat, default=None, help="lundi de la semaine 1 (défaut : lundi prochain)")
    ap.add_argument("--court", action="store_true", help="essai à blanc : séance de 6 min, manches de 90 s")
    ap.add_argument("--sans-engine", action="store_true", help="core seul (cloud, sans Godot)")
    ap.add_argument("--garder", action="store_true", help="garde le HOME temporaire (profil produit)")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    if a.court:
        a.seance_min = min(a.seance_min, 6.0)
        a.manche_s = a.manche_s or 90.0
        a.anneau_m = min(a.anneau_m, 1500.0)
    if a.debut is not None and a.debut.weekday() != 0:
        ap.error("--debut doit être un lundi")
    if not a.sans_engine and not os.access(a.godot, os.X_OK):
        print(f"Godot introuvable : {a.godot} (option --godot, variable GODOT, ou --sans-engine)")
        return 2
    if not a.sans_engine and not a.native and shutil.which("xvfb-run") is None:
        print("xvfb-run introuvable : lancer avec --native ou --sans-engine")
        return 2
    a.out = a.out or Path.home() / "OpenRide" / "rapports" / f"endurance-{datetime.now():%Y%m%d-%H%M}"
    return Endurance(a).run()


if __name__ == "__main__":
    sys.path.insert(0, str(REPO / "scripts"))
    from isolation_tests import verrou_suite   # une seule suite de tests ou banc à la fois

    with verrou_suite("essai_endurance"):
        code = main()
    sys.exit(code)
