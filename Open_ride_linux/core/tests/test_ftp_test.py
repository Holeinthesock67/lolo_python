"""Tests de FTP : rampe par paliers et test de 20 minutes (lot O10)."""

import asyncio
import json
from pathlib import Path

import pytest
from test_plans import TWO_WEEKS, lib  # noqa: F401  (fixture)
from test_workout import make_session, run, workouts_dir  # noqa: F401  (fixture)

from openride_core import __main__ as cli
from openride_core import ftp_test, plans
from openride_core.ftp_test import FtpResult, RampWatch, estimate_ftp, ramp_workout, twenty_min_workout
from openride_core.journal import read_journal
from openride_core.tools.session_summary import compute_summary, format_text, load_session
from openride_core.workout import ErgController

CONFIG = """# Ma configuration
[rider]
ftp_w = 250  # FTP actuelle
mass_kg = 70.0

[trainer]
# commentaire conservé
latency_tau_s = 0.8
"""


def test_ramp_workout_steps():
    w = ramp_workout()
    steps = [b for b in w.blocks if b.type == "steady"]
    assert [b.start_w for b in steps[:3]] == [100, 120, 140] and steps[-1].start_w == 700
    assert len(steps) == 31 and all(b.absolute and b.duration_s == 60 for b in steps)
    assert w.blocks[0].type == "warmup" and w.blocks[0].duration_s == 300
    assert (w.blocks[-1].type, w.blocks[-1].start_w, w.blocks[-1].duration_s) == ("cooldown", 100, 300)
    assert ramp_workout(start_w=150, step_w=25, warmup_s=0).blocks[0].start_w == 150
    with pytest.raises(ValueError):
        ramp_workout(step_w=0)


def test_twenty_min_workout_and_plan_durations():
    w = twenty_min_workout(250.0)
    i = next(k for k, b in enumerate(w.blocks) if b.type == "freeride")
    assert sum(b.duration_s for b in w.blocks[:6]) == 1200 and w.blocks[i].duration_s == 1200
    assert sum(1 for b in w.blocks[:6] if b.type == "interval_on") == 2
    assert ftp_test.planned_duration_s("20min") == w.duration_s == 3300
    # Rampe attendue pour 250 W : dernier palier 320 W (meilleure minute visée 333 W).
    assert ftp_test.planned_duration_s("ramp") == 300 + 12 * 60 + 300
    assert ftp_test.kind_of("ftp_test:ramp") == "ramp" and ftp_test.kind_of("ftp_test:sprint") is None
    with pytest.raises(ftp_test.FtpTestError):
        ftp_test.workout_for("sprint", 250.0)


def test_plan_with_ftp_test_day(lib):  # noqa: F811
    pdir, wdir = lib
    (pdir / "test.toml").write_text(TWO_WEEKS.replace('workout = "endu"', 'workout = "ftp_test:ramp"'))
    plan = plans.load_plan("test", pdir, wdir)
    assert plan.durations_s["ftp_test:ramp"] == 1320.0
    week1 = plans.plan_summary(plan, 250.0, wdir)[0]
    assert week1["sessions"] == 2 and week1["tss"] > 0


# --- fin de la rampe -----------------------------------------------------------------------

def watch_at(step_w):
    w = ramp_workout()
    erg = ErgController(w, 250.0)
    erg.goto(next(i for i, b in enumerate(w.blocks) if b.start_w == step_w and b.type == "steady"))
    erg.step(3.0)   # lissage terminé
    return RampWatch(w), erg


@pytest.mark.parametrize("power,cadence,needed_s,reason", [
    (300, 40, 5.0, "cadence"), (230, 85, 10.0, "power"), (260, 85, None, None)])
def test_ramp_watch_criteria(power, cadence, needed_s, reason):
    watch, erg = watch_at(300)
    t = 0.0
    while t < 12.0 and not watch.reason:
        watch.update(0.1, power, cadence, erg)
        t += 0.1
    assert watch.reason == reason
    if needed_s:
        assert t == pytest.approx(needed_s, abs=0.15)


def test_ramp_watch_ignores_warmup_and_pause():
    w = ramp_workout()
    erg = ErgController(w, 250.0)
    watch = RampWatch(w)
    for _ in range(100):
        assert watch.update(0.1, 0.0, 0.0, erg) is None   # échauffement : pas de détection
    _, erg = watch_at(200)
    erg.toggle_pause()
    for _ in range(200):
        assert watch.update(0.1, 0.0, 0.0, erg) is None


# --- séance --------------------------------------------------------------------------------

class Rider:
    """Cycliste simulé : tient la cible jusqu'à `limit_w`, puis lâche (cadence 30, mi-puissance)."""

    def __init__(self, driver, session, limit_w=340):
        self.orig, self.s, self.limit = driver.poll, session, limit_w
        self.gave_up_at = None
        driver.poll = self.poll

    def poll(self, t):
        m = self.orig(t)
        erg = self.s.erg
        if erg and erg.block.type == "steady" and (erg.block.start_w or 0) > self.limit:
            self.gave_up_at = self.gave_up_at if self.gave_up_at is not None else self.s._t_session
            m.power_w, m.cadence_rpm = 0.5 * erg.target_w, 30.0
        return m


def journal_line(s, kind):
    path = sorted((s.journal_dir).glob("*.jsonl"))[-1]
    return path, [ln for ln in read_journal(path) if ln.get("kind") == kind]


def test_session_ramp_detects_end_and_writes_result(tmp_path, monkeypatch, workouts_dir):  # noqa: F811
    async def scenario():
        s, driver, errors = make_session(tmp_path, monkeypatch, workouts_dir, port=5970)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s.route.type = "loop"                       # parcours sans arrivée : le test va jusqu'au bout
        s._on_command("select_workout", {"workout_id": "ftp_test:ramp"}, 2)
        s._on_command("start", {}, 3)
        assert s.state.mode == "ERG" and s.state.erg["workout_name"] == "Test de FTP : rampe" and not errors
        rider = Rider(driver, s)
        cooldown = len(s.erg.workout.blocks) - 1
        while s.erg.index != cooldown:
            run(s, 0.5, dt=0.1)
            assert s._t_session < 1200
        assert s._t_session - rider.gave_up_at < 10.0          # fin détectée en moins de 10 s
        run(s, 10.0, dt=0.1)
        assert s.state.erg["block_type"] == "cooldown" and s.state.erg["target_w"] == 100
        s._on_command("end_session", {"save": True}, 4)
        path, lines = journal_line(s, "ftp_test")
        assert len(lines) == 1
        res = FtpResult.from_line(lines[0])
        records = [ln for ln in read_journal(path) if ln.get("kind") == "record"]
        steps = ftp_test.effort_blocks(s._workout)
        powers = [r["power"] for r in records if r["block"] in steps]
        best = max(sum(powers[i:i + 60]) / 60 for i in range(len(powers) - 59))
        assert 335 <= best <= 345 and res.step_w == 360
        assert res.ftp_w == pytest.approx(0.75 * best, abs=1) and res.previous_ftp_w == 250
        assert res.reliable and res.warnings == ()
        # Ligne `ftp_test` juste avant l'arrêt, et bilan de la séance.
        kinds = [ln["kind"] for ln in read_journal(path)]
        assert kinds[-2:] == ["ftp_test", "event"]
        summary = compute_summary(load_session(path), 250.0)
        assert summary["ftp_test"]["ftp_w"] == res.ftp_w
        assert f"FTP proposée {res.ftp_w} W" in format_text(summary)
    asyncio.run(scenario())


def test_session_skip_during_ramp_is_abandon(tmp_path, monkeypatch, workouts_dir):  # noqa: F811
    async def scenario():
        s, driver, _ = make_session(tmp_path, monkeypatch, workouts_dir, port=5972)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s.route.type = "loop"                       # parcours sans arrivée : le test va jusqu'au bout
        s._on_command("select_workout", {"workout_id": "ftp_test:ramp"}, 2)
        s._on_command("start", {}, 3)
        s._on_command("skip_block", {}, 4)        # échauffement : saut de bloc ordinaire
        assert s.erg.index == 1
        run(s, 70.0, dt=0.1)
        s._on_command("skip_block", {}, 5)        # pendant les paliers : abandon du test
        assert s.erg.block.type == "cooldown" and s._ramp_watch.reason == "abandon"
    asyncio.run(scenario())


def test_session_twenty_minutes_at_260(tmp_path, monkeypatch, workouts_dir):  # noqa: F811
    async def scenario():
        s, driver, _ = make_session(tmp_path, monkeypatch, workouts_dir, port=5974)
        driver.base_power_w, driver.ramp_amplitude_w = 260.0, 0.0
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s.route.type = "loop"                       # parcours sans arrivée : le test va jusqu'au bout
        s._on_command("select_workout", {"workout_id": "ftp_test:20min"}, 2)
        s._on_command("start", {}, 3)
        assert s._ramp_watch is None
        s.erg.goto(7)                               # début des 20 minutes libres
        s._sync_erg_state()
        assert s.state.mode == "SIM" and s.erg.block.type == "freeride"
        run(s, 1205.0, dt=0.25)
        assert s.erg.block.type == "cooldown"
        s._on_command("end_session", {"save": True}, 4)
        _, lines = journal_line(s, "ftp_test")
        assert (lines[0]["test"], lines[0]["ftp_w"], lines[0]["ref_power_w"]) == ("20min", 247, 260)
        assert lines[0]["warnings"] == [] and lines[0]["held_s"] >= 1199
    asyncio.run(scenario())


def test_autostart_and_command_line(tmp_path, monkeypatch, workouts_dir):  # noqa: F811
    async def scenario():
        s, _, _ = make_session(tmp_path, monkeypatch, workouts_dir, port=5976)
        s.check_autostart("demo", "ftp_test:20min")
    asyncio.run(scenario())
    for argv in (["run", "--ftp-test", "ramp"], ["run", "--autostart", "--ftp-test", "ramp", "--workout", "x"]):
        with pytest.raises(SystemExit) as exc:
            cli.main(argv)
        assert exc.value.code == 2
    args = cli.build_parser().parse_args(["run", "--autostart", "--ftp-test", "20min"])
    assert args.ftp_test == "20min"


# --- résultat --------------------------------------------------------------------------------

def records(seconds, power=260.0, block=8, cadence=90.0, t0=1000.0):
    return [{"kind": "record", "ts": t0 + i, "t": float(i), "power": power, "cadence": cadence, "block": block}
            for i in range(seconds)]


def test_estimate_twenty_minutes():
    r = estimate_ftp(records(1200), "20min", previous_ftp_w=250)
    assert (r.ftp_w, r.ref_power_w, r.held_s, r.warnings) == (247, 260, 1200, ())
    short = estimate_ftp(records(600), "20min")
    assert short.warnings == ("too_short",) and not short.reliable
    assert estimate_ftp(records(60, block=2), "20min").ftp_w is None


def test_estimate_warnings():
    recs = records(1200)
    down = [{"kind": "device", "ts": 1500.0, "device": "trainer", "state": "down"},
            {"kind": "device", "ts": 1503.0, "device": "trainer", "state": "up"}]
    r = estimate_ftp(recs, "20min", devices=down)
    assert r.warnings == ("trainer_dropout",) and not r.reliable and r.ftp_w == 247
    assert "coupure du trainer" in r.describe()
    paused = estimate_ftp(recs, "20min", events=[{"kind": "event", "ts": 1700.0, "event": "pause"}])
    assert paused.warnings == ("paused",)
    wobbly = [dict(rec, cadence=60.0 if i % 2 else 100.0) for i, rec in enumerate(recs)]
    r = estimate_ftp(wobbly, "20min")
    assert r.warnings == ("erratic_cadence",) and r.reliable
    outside = [{"kind": "device", "ts": 900.0, "device": "trainer", "state": "down"}]
    assert estimate_ftp(recs, "20min", devices=outside).warnings == ()


def test_estimate_ramp_too_short():
    r = estimate_ftp(records(120, power=120.0, block=2), "ramp")
    assert r.warnings == ("too_short",) and r.step_w == 100 and r.ftp_w == 90


# --- commande ftp-test -----------------------------------------------------------------------

def write_journal(directory: Path, name: str, result: FtpResult | None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    lines = [{"kind": "header", "version": 1, "route_id": "demo", "workout_id": "ftp_test:20min"},
             {"kind": "event", "event": "start", "ts": 1000.0}, *records(5)]
    if result is not None:
        lines.append(result.to_line())
    lines.append({"kind": "event", "event": "stop", "ts": 1006.0})
    path = directory / name
    path.write_text("".join(json.dumps(ln) + "\n" for ln in lines), encoding="utf-8")
    return path


GOOD = FtpResult("20min", 263, "95 % de la moyenne des 20 minutes", 277, 1200, None, (), 250, 1761550000.0)


def test_accept_changes_only_ftp(tmp_path, capsys):
    cfg = tmp_path / "config.toml"
    cfg.write_text(CONFIG, encoding="utf-8")
    jdir = tmp_path / "journal"
    write_journal(jdir, "2026-10-20_18-00-00.jsonl", GOOD)
    assert ftp_test.run(None, False, False, False, config_path=cfg, journal_dir=jdir) == 0
    out = capsys.readouterr().out
    assert "FTP actuelle 250 W, nouvelle 263 W, écart +13 W (+5.2 %)" in out
    assert cfg.read_text(encoding="utf-8") == CONFIG                    # sans --accept : rien d'écrit
    assert ftp_test.run(None, True, False, False, config_path=cfg, journal_dir=jdir) == 0
    before, after = CONFIG.splitlines(), cfg.read_text(encoding="utf-8").splitlines()
    changed = [(a, b) for a, b in zip(before, after) if a != b]
    assert len(after) == len(before) and len(changed) == 1
    assert changed[0][1].startswith("ftp_w = 263 ") and changed[0][1].endswith("# FTP actuelle")
    assert (tmp_path / "config.toml.bak").read_text(encoding="utf-8") == CONFIG


def test_accept_refuses_doubtful_and_out_of_bounds(tmp_path, capsys):
    cfg = tmp_path / "config.toml"
    cfg.write_text(CONFIG, encoding="utf-8")
    jdir = tmp_path / "journal"
    doubtful = FtpResult("20min", 263, "", 277, 1200, None, ("trainer_dropout",), 250, 1761550000.0)
    write_journal(jdir, "2026-10-20_18-00-00.jsonl", doubtful)
    assert ftp_test.run(None, True, False, False, config_path=cfg, journal_dir=jdir) == 1
    assert "résultat douteux" in capsys.readouterr().out and cfg.read_text(encoding="utf-8") == CONFIG
    assert ftp_test.run(None, True, True, False, config_path=cfg, journal_dir=jdir) == 0   # --force
    cfg.write_text(CONFIG, encoding="utf-8")
    huge = write_journal(jdir, "2026-10-21_18-00-00.jsonl",
                         FtpResult("ramp", 640, "", 853, 1500, 700, (), 250, 1761650000.0))
    assert ftp_test.run(huge, True, False, False, config_path=cfg, journal_dir=jdir) == 1
    assert "écriture refusée" in capsys.readouterr().out and cfg.read_text(encoding="utf-8") == CONFIG


def test_history_and_old_journals(tmp_path, capsys):
    cfg = tmp_path / "config.toml"
    cfg.write_text(CONFIG, encoding="utf-8")
    jdir = tmp_path / "journal"
    old = write_journal(jdir, "2026-10-01_18-00-00.jsonl", None)
    assert ftp_test.run(None, True, False, False, config_path=cfg, journal_dir=jdir) == 1
    assert ftp_test.run(None, False, False, True, journal_dir=jdir) == 0
    assert "Aucun test de FTP trouvé." in capsys.readouterr().out
    summary = compute_summary(load_session(old), 250.0)
    assert "ftp_test" not in summary and "FTP" not in format_text(summary).split("IF")[1]
    write_journal(jdir, "2026-10-20_18-00-00.jsonl", GOOD)
    write_journal(jdir, "2026-10-27_18-00-00.jsonl",
                  FtpResult("ramp", 270, "", 360, 900, 360, ("erratic_cadence",), 263, 1762150000.0))
    assert ftp_test.run(None, False, False, True, journal_dir=jdir) == 0
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 2 and "20 min" in out[0] and "FTP  263 W" in out[0]
    assert "rampe" in out[1] and "cadence erratique" in out[1]
    assert cli.main(["ftp-test", "--history", "--json", "--dir", str(jdir)]) == 0
    assert [t["ftp_w"] for t in json.loads(capsys.readouterr().out)] == [263, 270]
