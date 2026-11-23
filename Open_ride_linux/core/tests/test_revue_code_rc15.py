"""Revue de code, vague 2, lot RC15 : outils du core (constats C7-01, C7-02, C7-03, C6-01, C6-03, C6-04).

Chaque test échoue sur `main` d'avant la correction. Aucune donnée personnelle : séances fabriquées,
adresses Bluetooth fictives, dossier personnel temporaire.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from openride_core import profiles
from openride_core.rogue import mode as rogue_mode
from openride_core.tools import coupures
from openride_core.tools import essai_physique as EP
from openride_core.tools import estimate_cp as ecp
from openride_core.tools import history
from openride_core.tools.log_report import analyse

# ---------------------------------------------------------------- C7-01 : fiche Cyber-Rogue


def test_c7_01_rogue_fiche_accepts_the_header_the_run_writes():
    """La run Cyber-Rogue écrit `route_id = "rogue"` à l'en-tête : la fiche doit continuer, pas s'arrêter."""
    toutes = EP.fiches()
    entetes = {"rogue-depart": rogue_mode.JOURNAL_ROUTE_ID, "gp-voies": "demo-circuit"}
    for fid, route in entetes.items():
        d = EP.Deroule(toutes[fid], 200.0)
        actions = d.lire({"kind": "header", "version": 1, "route_id": route, "source": "simulated"})
        assert not d.fini and [a.sorte for a in actions] == [], fid
    autre = EP.Deroule(toutes["rogue-depart"], 200.0)
    assert [a.sorte for a in autre.lire({"kind": "header", "route_id": "demo"})] == ["terrain"] and autre.fini


# ---------------------------------------------------------------- C7-02 : réglages du joueur

CHILD = textwrap.dedent("""
    import os, subprocess, sys
    from openride_core.tools import essai_physique as EP

    class FakeProc:
        def __init__(self, *a, **k):
            self.pid, self.stopped = 424242, False
            print("PRET", flush=True)
        def poll(self):
            return 0 if self.stopped else None
        def wait(self, timeout=None):
            self.stopped = True
            return 0

    procs = []
    def fake_popen(*a, **k):
        procs.append(FakeProc(*a, **k))
        return procs[-1]

    def fake_killpg(pid, sig):
        print("ARRET", sig, flush=True)
        for p in procs:
            p.stopped = True

    subprocess.Popen = fake_popen
    os.killpg = fake_killpg
    sys.exit(EP.main(sys.argv[1:]))
""")

CONFIG_AVANT = "# réglage du joueur\n[rider]\nftp_w = 250\n"
PROFIL_AVANT = "[profil]\nnom = \"Joueur\"\ntype = \"joueur\"\n"


def _home(tmp_path: Path) -> tuple[dict, Path, Path]:
    home = tmp_path / "home"
    cfg = home / "OpenRide" / "config.toml"
    prof = home / "OpenRide" / "Profils" / "principal" / "profil.toml"
    prof.parent.mkdir(parents=True)
    cfg.write_text(CONFIG_AVANT, encoding="utf-8")
    prof.write_text(PROFIL_AVANT, encoding="utf-8")
    env = {**os.environ, "HOME": str(home), "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("OPENRIDE_PROFIL", None)
    return env, cfg, prof


def _start_child(tmp_path: Path, env: dict, *args: str) -> subprocess.Popen:
    script = tmp_path / "enfant.py"
    script.write_text(CHILD, encoding="utf-8")
    proc = subprocess.Popen([sys.executable, str(script), *args], env=env, cwd=tmp_path,
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    lu = []
    fin = time.monotonic() + 60
    while time.monotonic() < fin:
        line = proc.stdout.readline()
        if not line:
            break
        lu.append(line)
        if line.startswith("PRET"):
            return proc
    proc.kill()
    pytest.fail("le guide n'a pas lancé le jeu : " + "".join(lu))


def _essais(env: dict) -> Path:
    return Path(env["HOME"]) / "OpenRide" / "Essais"


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGHUP])
def test_c7_02_signal_restores_player_settings(tmp_path, sig):
    """Terminal fermé (SIGHUP) ou SIGTERM pendant l'essai : jeu arrêté, réglages du joueur remis."""
    env, cfg, prof = _home(tmp_path)
    proc = _start_child(tmp_path, env, "lancer", "gp-voies", "--muet", "--cible", "200")
    try:
        marqueur = _essais(env) / EP.SAUVEGARDE_DIR / EP.MARQUEUR
        assert marqueur.is_file(), "aucune copie des réglages sur disque pendant l'essai"
        assert (cfg.read_text(encoding="utf-8"), prof.read_text(encoding="utf-8")) != (CONFIG_AVANT, PROFIL_AVANT)
        proc.send_signal(sig)
        out, _ = proc.communicate(timeout=60)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.returncode == 1, out
    assert "ARRET" in out
    assert cfg.read_text(encoding="utf-8") == CONFIG_AVANT
    assert prof.read_text(encoding="utf-8") == PROFIL_AVANT
    assert not marqueur.exists()


def test_c7_02_killed_guide_is_restored_by_restaurer(tmp_path):
    """Guide tué sans `finally` (SIGKILL, PC éteint) : `restaurer` remet les réglages depuis la copie."""
    env, cfg, prof = _home(tmp_path)
    proc = _start_child(tmp_path, env, "lancer", "gp-voies", "--muet", "--cible", "200")
    proc.kill()
    proc.communicate(timeout=30)
    assert "opponents" in prof.read_text(encoding="utf-8") + cfg.read_text(encoding="utf-8")
    r = subprocess.run([sys.executable, "-m", "openride_core.tools.essai_physique", "restaurer"], env=env,
                       cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert cfg.read_text(encoding="utf-8") == CONFIG_AVANT
    assert prof.read_text(encoding="utf-8") == PROFIL_AVANT
    again = subprocess.run([sys.executable, "-m", "openride_core.tools.essai_physique", "restaurer"], env=env,
                           cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert "Rien à restaurer" in again.stdout


def test_c7_02_backup_roundtrip_and_absent_file(tmp_path):
    present, absent = tmp_path / "config.toml", tmp_path / "p" / "profil.toml"
    present.write_text("a = 1\n", encoding="utf-8")
    EP.sauvegarder_reglages([present, absent], tmp_path / "Essais")
    present.write_text("a = 2\n", encoding="utf-8")
    absent.parent.mkdir()
    absent.write_text("b = 1\n", encoding="utf-8")
    lignes = EP.restaurer_reglages(tmp_path / "Essais")
    assert present.read_text(encoding="utf-8") == "a = 1\n" and not absent.exists() and len(lignes) == 2
    assert EP.restaurer_reglages(tmp_path / "Essais") == []


# ---------------------------------------------------------------- C7-03 : essai à blanc


def test_c7_03_sim_refused_on_player_profile_and_defaults_to_trial(monkeypatch, capsys):
    lances = []
    monkeypatch.setattr(EP.subprocess, "Popen", lambda *a, **k: pytest.fail("jeu lancé sur le vrai profil"))
    assert EP.main(["lancer", "velodrome-elimination", "--sim", "--profil", "principal", "--muet"]) == 2
    assert "refusé" in capsys.readouterr().err
    monkeypatch.setattr(EP, "lancer", lambda f, profil, sim, *a, **k: lances.append((profil, sim)) or 0)
    assert EP.main(["lancer", "velodrome-elimination", "--sim"]) == 0
    assert EP.main(["lancer", "velodrome-elimination"]) == 0
    assert lances == [(profiles.TRIAL_ID, True), ("principal", False)]


# ---------------------------------------------------------------- C6-01 : séances simulées

NOW = 1_800_000_000.0


def _journal(folder: Path, name: str, start_ts: float, source: str, dur_w=((1200, 280.0),)) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    lines = [{"kind": "header", "version": 1, "route_id": "demo", "workout_id": None, "source": source},
             {"kind": "event", "event": "start", "ts": start_ts}]
    t = start_ts
    for dur, w in dur_w:
        for _ in range(int(dur)):
            lines.append({"kind": "record", "ts": t, "power": w, "cadence": 90, "speed": 8.0, "distance": 0.0})
            t += 1.0
    lines.append({"kind": "event", "event": "stop", "ts": t})
    path = folder / f"{name}.jsonl"
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def player_and_trial(tmp_path):
    base = tmp_path / "Profils"
    ctxs = {}
    for pid in ("principal", profiles.TRIAL_ID):
        ctx = profiles.ProfileContext.for_id(pid, base)
        _journal(ctx.journal_dir, "sim", time.time() - 3600, "simulated")
        ctxs[pid] = ctx
    yield ctxs
    profiles.activate(None)


def test_c6_01_history_skips_simulated_sessions_of_a_player_profile(player_and_trial):
    for pid, attendu in (("principal", 0), (profiles.TRIAL_ID, 1)):
        ctx = player_and_trial[pid]
        profiles.activate(ctx)
        r = history.compute_history(ftp=250.0, weeks=4)
        assert len(r["sessions"]) == attendu, pid
        assert sum(w["count"] for w in r["weeks"]) == attendu, pid


def test_c6_01_history_counts_live_and_old_journals(tmp_path):
    ctx = profiles.ProfileContext.for_id("principal", tmp_path / "Profils")
    _journal(ctx.journal_dir, "live", time.time() - 7200, "live")
    old = _journal(ctx.journal_dir, "ancien", time.time() - 3600, "live")
    lignes = old.read_text(encoding="utf-8").splitlines()
    head = json.loads(lignes[0])
    del head["source"]   # journal d'avant le champ `source` : séance réelle
    old.write_text("\n".join([json.dumps(head)] + lignes[1:]) + "\n", encoding="utf-8")
    _journal(ctx.journal_dir, "rejeu", time.time() - 600, "replay")
    profiles.activate(ctx)
    try:
        r = history.compute_history(ftp=250.0, weeks=4)
    finally:
        profiles.activate(None)
    assert sorted(s["filename"] for s in r["sessions"]) == ["ancien.jsonl", "live.jsonl"]


def test_c6_01_cp_estimate_skips_simulated_sessions_of_a_player_profile(tmp_path):
    def build(pid):
        ctx = profiles.ProfileContext.for_id(pid, tmp_path / "Profils")
        for i, t in enumerate((180, 300, 480, 720, 1200)):
            _journal(ctx.journal_dir, f"s{i}", NOW - 86400 * (5 + i), "simulated", ((60, 100.0), (t, 250.0 + 20000.0 / t)))
        return ctx

    joueur, essai = build("principal"), build(profiles.TRIAL_ID)
    try:
        profiles.activate(joueur)
        r = ecp.estimate(None, 250.0, 90, now=NOW)
        assert r["sessions"] == 0 and r["estimate"] is None
        profiles.activate(essai)
        r = ecp.estimate(None, 250.0, 90, now=NOW)
        assert r["sessions"] == 5 and r["estimate"] is not None
    finally:
        profiles.activate(None)


# ---------------------------------------------------------------- C6-03 : pertes du trainer


def _log(*rows: tuple[str, str, str]) -> list[str]:
    return [f"2026-11-01 {ts},000 {lvl:<7} ftms_driver {msg}" for ts, lvl, msg in rows]


def test_c6_03_driver_info_lines_are_not_trainer_losses():
    """Séance d'une heure sans coupure : les lignes d'information du pilote ne sont pas des pertes."""
    rep = analyse(_log(
        ("19:00:00", "INFO", "Trainer : fonctions FTMS : x ; consignes : y"),
        ("19:00:01", "INFO", "Trainer connecté (HomeTrainer 0000)"),
        ("19:10:00", "INFO", "Trainer : état machine STARTED"),
        ("19:20:00", "INFO", "Trainer : puissance revenue (180 W) 1.2 s après la reprise du contrôle"),
        ("19:30:00", "WARNING", "Trainer : le frein a lâché (300 W puis 0 W à 90 tr/min, volant x) ; reprise"),
        ("19:40:00", "WARNING", "Trainer : contrôle FTMS perdu (Fitness Machine Status 0xFF)"),
        ("19:59:59", "INFO", "Trainer : 2 perte(s) de frein détectée(s)."),
        ("20:00:00", "INFO", "Trainer déconnecté."),
    ))
    assert rep.trainer.connections == 1
    assert rep.trainer.disconnections == 0
    assert rep.trainer.lost_duration_s == 0.0


def test_c6_03_link_exception_is_still_a_loss():
    rep = analyse(_log(
        ("19:00:01", "INFO", "Trainer connecté (HomeTrainer 0000)"),
        ("19:10:00", "WARNING", "Trainer : plus de données du trainer"),
        ("19:10:05", "INFO", "Trainer connecté (HomeTrainer 0000)"),
    ))
    assert (rep.trainer.connections, rep.trainer.disconnections) == (2, 1)
    assert rep.trainer.lost_duration_s == pytest.approx(5.0)


def test_c6_03_every_driver_trainer_line_is_classified():
    """Toute chaîne « Trainer : … » du pilote, sauf l'exception de liaison (%s), est une ligne sans perte."""
    import re

    from openride_core.tools import log_report

    src = (Path(log_report.__file__).resolve().parents[1] / "ftms_driver.py").read_text(encoding="utf-8")
    formats = set(re.findall(r'log\.(?:info|warning|error)\(\s*"Trainer : ([^"]*)"', src))
    assert "%s" in formats and len(formats) > 10
    for fmt in formats - {"%s"}:
        rendu = re.sub(r"%02x", "11", fmt)
        rendu = re.sub(r"%[-+ #0]*\d*(?:\.\d+)?[sdfgx]", "1", rendu).replace("%%", "%")
        assert not log_report.is_trainer_loss("WARNING", "Trainer : " + rendu), fmt
    assert log_report.is_trainer_loss("WARNING", "Trainer : plus de données du trainer")
    assert not log_report.is_trainer_loss("INFO", "Trainer : plus de données du trainer")


# ---------------------------------------------------------------- C6-04 : boîtiers bloqués


class _FakeGuide:
    def __init__(self, interrupt_on_wait: bool = False):
        self.steps, self.interrupt = [], interrupt_on_wait

    def step(self, title, *a, **k):
        self.steps.append(title)

    def wait(self, s):
        if self.interrupt and self.steps and self.steps[-1].startswith("Les deux"):
            raise KeyboardInterrupt

    def measure(self, *a, **k):
        pass

    def log(self, *a, **k):
        pass


def _bt(monkeypatch, refuse=()):
    state: dict[str, bool] = {}
    calls: list[tuple[str, bool]] = []

    def fake(address, block):
        calls.append((address, block))
        if block and address in refuse:
            return False
        state[address] = block
        return True

    monkeypatch.setattr(coupures, "bluetooth_block", fake)
    return state, calls


def _cfg(minus="C1:1C:00:00:00:01"):
    return SimpleNamespace(drivers=SimpleNamespace(click_address="C1:1C:00:00:00:03", click_minus_address=minus))


def test_c6_04_ctrl_c_during_cut_unblocks_both_boxes(monkeypatch, tmp_path):
    state, _ = _bt(monkeypatch)
    table = coupures.actions(False, 0.0)
    with pytest.raises(KeyboardInterrupt):
        coupures.live([table["clicks"]], _cfg(), _FakeGuide(interrupt_on_wait=True), tmp_path, 0.0)
    assert state and not any(state.values()), state


def test_c6_04_second_block_refused_unblocks_the_first(monkeypatch, tmp_path):
    state, _ = _bt(monkeypatch, refuse={"C1:1C:00:00:00:01"})
    guide = _FakeGuide()
    monkeypatch.setattr(coupures.time, "sleep", lambda s: None)
    coupures.live([coupures.actions(False, 0.0)["clicks"]], _cfg(), guide, tmp_path, 0.0)
    assert not any(state.values()), state
    assert "Retire la pile des deux boîtiers" in guide.steps


def test_c6_04_single_address_falls_back_to_manual_for_both_boxes(monkeypatch, tmp_path):
    state, calls = _bt(monkeypatch)
    guide = _FakeGuide()
    coupures.live([coupures.actions(False, 0.0)["clicks"]], _cfg(minus=""), guide, tmp_path, 0.0)
    assert calls == [] and "Retire la pile des deux boîtiers" in guide.steps
