"""Lot T7 : série T branchée dans la séance (segments, records, bonus, maillots, écarts, reprise).

Parcours de démonstration : `climb1` (0 à 1 500 m, catégorie 4) puis `sprint1` (2 860 à 3 290 m),
5 km au total. Critères d'acceptation du cahier `docs/lots/LOT_T7_branchement_seance.md` §7.
"""

import json
import time
from pathlib import Path

import jsonschema
import pytest

from openride_core import fit_export
from openride_core.bots import ConstantPowerBot
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.journal import read_journal
from openride_core.mock_driver import MockDriver
from openride_core.physics import PhysicsParams
from openride_core.route import RouteSample
from openride_core.session import CoreSession
from openride_core.zwift_click import InputEvent

IPC_DIR = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc"
DT = 0.02
T0_WALL = 1_790_000_000.0
NEW_KEYS = {"segment", "powerup", "jerseys", "bot_ahead", "bot_behind"}

ERG_ZWO = """<?xml version="1.0" encoding="UTF-8"?>
<workout_file>
    <name>ERG segments</name>
    <workout>
        <SteadyState Duration="1200" Power="0.80"/>
    </workout>
</workout_file>
"""


def validator(name: str) -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(json.loads((IPC_DIR / f"{name}.schema.json").read_text("utf-8")))


class ConstRoute:
    """Ligne droite de 5 km plein nord à pente constante (comparaisons avec et sans bonus)."""
    is_loop, length_m, type = False, 5000.0, "line"

    def __init__(self, grade_pct: float = 3.0) -> None:
        self.g = grade_pct

    def wrap(self, s: float) -> float:
        return min(max(s, 0.0), self.length_m)

    def sample(self, s: float) -> RouteSample:
        return RouteSample(x=0.0, y=0.0, z=-s, lat=48.0, lon=7.0, alt_m=200.0 + s * self.g / 100.0,
                           grade_pct=self.g, heading_deg=0.0)

    def grade_at(self, s: float) -> float:
        return self.g


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """`make(port, ...)` crée une séance sur le parcours de démonstration ; `run(s, secondes)` la fait avancer."""
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    wall = [T0_WALL]
    monkeypatch.setattr(time, "time", lambda: wall[0])
    workouts = tmp_path / "Workouts"
    workouts.mkdir()
    (workouts / "erg.zwo").write_text(ERG_ZWO, encoding="utf-8")

    def make(port: int, power: float = 250.0, bots=None, cfg: Config | None = None) -> tuple[CoreSession, list]:
        cfg = cfg or Config()
        cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
        s = CoreSession(cfg, driver=MockDriver(base_power_w=power, ramp_amplitude_w=0.0),
                        inputs=[NullProvider()], journal_dir=tmp_path / "journal",
                        routes_root=tmp_path / "routes", workouts_dir=workouts, bots=bots,
                        records_path=tmp_path / "records.json", powerups_path=tmp_path / "powerups.toml")
        sent: list[dict] = []
        s.server.send_raw = lambda m, max_size=None: sent.append(m)
        s.server.send_input_event = lambda ev: None
        s._on_command("select_route", {"route_id": "demo"}, 1)
        return s, sent

    def run(s: CoreSession, seconds: float, every=None) -> None:
        for i in range(int(round(seconds / DT))):
            wall[0] += DT
            s._step(DT, wall[0])
            if every and i % 15 == 0:   # trame state à environ 30 Hz
                every(frame(s))

    return make, run, tmp_path


def frame(s: CoreSession) -> dict:
    """Trame `state` telle que la boucle de la séance l'envoie."""
    s.state.bots = [b.to_dict() for b in s.bots] if s.bots else None
    s._fill_race_frame()
    return s.state.to_dict()


def results(sent: list[dict]) -> list[dict]:
    return [m for m in sent if m.get("type") == "segment_result"]


def ride_to_end(s: CoreSession, run, frames: list | None = None) -> None:
    run(s, 900.0, frames.append if frames is not None else None)
    assert s.state.session_state == "FINISHED"


# --- critères 1 et 2 : trames, messages, records, journal -------------------------------------

def test_demo_route_frames_results_records_and_journal(env):
    make, run, tmp = env
    s, sent = make(7100)
    s._on_command("start", {}, 2)
    journal = s._rec.path
    frames: list[dict] = []
    ride_to_end(s, run, frames)

    state_v, result_v = validator("state"), validator("segment_result")
    for f in frames:
        assert not list(state_v.iter_errors(f))
    seen = [f["segment"]["id"] for f in frames if "segment" in f]
    assert seen[0] == "climb1" and "sprint1" in seen
    assert any(f["segment"]["elapsed_s"] is not None for f in frames if f.get("segment", {}).get("id") == "climb1")
    assert all("bot_ahead" not in f and "bot_behind" not in f for f in frames)   # sans bot

    msgs = results(sent)
    assert [m["segment_id"] for m in msgs] == ["climb1"] * 3 + ["sprint1"] * 3
    for m in msgs:
        result_v.validate(m)
    assert msgs[0] == msgs[1] == msgs[2] and msgs[3] == msgs[4] == msgs[5]
    assert msgs[0]["pr"] and msgs[0]["pr_time_s"] is None and not msgs[0]["with_powerup"]
    assert msgs[0]["equipment_gain_s"] is None

    book = json.loads((tmp / "records.json").read_text(encoding="utf-8"))["routes"]["demo"]
    assert book["climb1"]["no_bonus"][0]["time_s"] == msgs[0]["time_s"]
    assert book["sprint1"]["no_bonus"][0]["time_s"] == msgs[3]["time_s"]
    assert book["climb1"]["bonus"] == []

    lines = list(read_journal(journal))
    segs = [ln for ln in lines if ln.get("kind") == "segment"]
    assert [(ln["segment_id"], ln["lap"], ln["type"]) for ln in segs] == [("climb1", 0, "climb"),
                                                                          ("sprint1", 0, "sprint")]
    summary = s.state.summary["segments"]
    assert [p["segment_id"] for p in summary["passes"]] == ["climb1", "sprint1"]
    assert summary["more"] is False and set(summary["jerseys"]) == {"sprint", "kom"}
    assert summary["jerseys"]["kom"] == "me"   # seul en course : maillot à pois
    assert any(ln.get("kind") == "jersey" and ln["jersey"] == "kom" for ln in lines)

    # Deuxième séance : records relus, temps rangé derrière le premier si plus lent
    s2, sent2 = make(7102, power=200.0)
    s2._on_command("start", {}, 2)
    ride_to_end(s2, run)
    m2 = results(sent2)[0]
    assert not m2["pr"] and m2["pr_time_s"] == msgs[0]["time_s"] and (m2["rank"], m2["rank_total"]) == (2, 2)
    book = json.loads((tmp / "records.json").read_text(encoding="utf-8"))["routes"]["demo"]
    assert len(book["climb1"]["no_bonus"]) == 2


# --- critère 3 : bonus aéro par Z_SHORT ----------------------------------------------------

def _paired(make, port: int, cfg_wind: bool):
    out = []
    for k in range(2):
        cfg = Config()
        if cfg_wind:
            cfg.wind.mode, cfg.wind.speed_kmh, cfg.wind.from_deg, cfg.wind.feel = "fixed", 30, 0, "grade"
        s, sent = make(port + 2 * k, cfg=cfg)
        s.route = ConstRoute()
        s._on_command("start", {}, 2)
        out.append((s, sent))
    return out


@pytest.mark.parametrize("wind", [False, True])
def test_aero_bonus_by_z_short_changes_speed_not_route_grade(env, wind):
    make, run, _ = env
    (a, _), (b, sent_b) = _paired(make, 7110 if not wind else 7120, wind)
    run(a, 30.0)
    run(b, 30.0)
    b.race.powerups.reserve = "aero"
    assert frame(b)["powerup"] == {"held": "aero", "active": None, "remaining_s": 0.0}
    b._handle_input(InputEvent.Z_SHORT)
    assert frame(b)["powerup"]["active"] == "aero" and frame(b)["powerup"]["held"] is None
    run(a, 10.0)
    run(b, 10.0)
    assert b.physics.v > a.physics.v + 0.1
    assert b.physics.p.cda_m2 == pytest.approx(a.physics.p.cda_m2 * 0.75)
    if wind:
        assert 0.0 < b._wind_offset < a._wind_offset   # supplément de vent calculé avec le CdA courant
    else:
        assert b._grade_sent == pytest.approx(a._grade_sent)   # pente envoyée au trainer inchangée
    run(b, 6.0)
    assert b.race.powerups.active is None and b.physics.p.cda_m2 == pytest.approx(a.physics.p.cda_m2)
    while b.physics.s < 1510.0:   # fin de la montée (plus lente avec le vent de face)
        run(b, 10.0)
    climb = [m for m in results(sent_b) if m["segment_id"] == "climb1"]
    assert climb and climb[0]["with_powerup"] is True
    assert b.race.book.table("demo", "climb1", True) and not b.race.book.table("demo", "climb1", False)
    lines = [ln for ln in read_journal(b._rec.path) if ln.get("kind") == "powerup"]
    assert [(ln["powerup"], ln["duration_s"]) for ln in lines] == [("aero", 15.0)]


# --- critère 4 : ERG --------------------------------------------------------------------------

def test_erg_times_segments_without_powerups(env):
    make, run, _ = env
    s, sent = make(7130)
    s._on_command("select_workout", {"workout_id": "erg"}, 2)
    s._on_command("start", {}, 3)
    frames: list[dict] = []
    run(s, 30.0, frames.append)
    s.race.powerups.reserve = "power"
    run(s, 600.0, frames.append)
    assert frames and all("powerup" not in f for f in frames)
    msgs = results(sent)
    assert msgs and msgs[0]["segment_id"] == "climb1" and not msgs[0]["with_powerup"]
    assert s.race.powerups.reserve == "power"   # pas de bonus de fin de segment en ERG
    s._handle_input(InputEvent.Z_SHORT)   # en ERG, Z est le bloc suivant (§7.1, lot O17), pas le bonus
    assert s.erg is None and s.state.mode == "SIM"   # bloc unique : l'entraînement se termine
    assert s.race.powerups.active is None and s.race.powerups.reserve == "power"   # gardée pour la SIM


# --- critère 5 : pause pendant un segment -----------------------------------------------------

def test_user_pause_inside_segment_cancels_the_pass(env):
    make, run, tmp = env
    s, sent = make(7140)
    s._on_command("start", {}, 2)
    run(s, 60.0)
    assert 0.0 < s.physics.s < 1500.0
    s._on_command("pause", {}, 3)
    run(s, 5.0)
    s._on_command("resume", {}, 4)
    run(s, 400.0)
    assert s.physics.s > 1500.0
    assert not [m for m in results(sent) if m["segment_id"] == "climb1"]
    assert not s.race.book.table("demo", "climb1", False)
    assert not (tmp / "records.json").exists() or "climb1" not in json.loads(
        (tmp / "records.json").read_text(encoding="utf-8"))["routes"].get("demo", {})


# --- séance A du 28 octobre : montée 1 coupée par deux pertes du trainer -------------------------

@pytest.mark.recette_sans_velo
def test_climb_starting_at_zero_gives_result_without_pause(env):
    """Montée 1 de la démo (départ à s = 0), sans pause : chrono en direct, résultat, record et journal."""
    make, run, _ = env
    s, sent = make(7154)
    s._on_command("start", {}, 2)
    frames: list[dict] = []
    while s.physics.s < 1510.0:
        run(s, 10.0, frames.append)
    assert any(f.get("segment", {}).get("id") == "climb1" and f["segment"]["elapsed_s"] is not None
               for f in frames)
    assert results(sent) and {m["segment_id"] for m in results(sent)} == {"climb1"}
    assert s.race.book.table("demo", "climb1", False)
    assert [ln["segment_id"] for ln in read_journal(s._rec.path) if ln.get("kind") == "segment"] == ["climb1"]


@pytest.mark.recette_sans_velo
def test_trainer_lost_inside_climb_starting_at_zero_keeps_the_pass(env):
    """Montée 1 de la démo (départ à s = 0) : arrêt au départ, deux coupures du trainer en pleine montée.

    Le passage est suspendu pendant les pauses subies puis chronométré : résultat, record et journal.
    """
    make, run, tmp = env
    s, sent = make(7150)
    s.driver.base_power_w = 0.0
    s._on_command("start", {}, 2)
    run(s, 10.0)                       # immobile sur la ligne de départ
    assert s.physics.s == 0.0
    s.driver.base_power_w = 250.0
    run(s, 40.0)
    for k in range(2):
        assert 0.0 < s.physics.s < 1500.0
        s.driver.simulate_disconnect()
        run(s, 5.0)
        assert (s.state.session_state, s.state.pause_reason) == ("PAUSED", "trainer_lost")
        assert frame(s)["segment"]["id"] == "climb1" and frame(s)["segment"]["elapsed_s"] is not None
        s.driver.simulate_reconnect()
        s._on_command("resume", {}, 3 + k)
        run(s, 20.0)
    while s.physics.s < 1510.0:
        run(s, 10.0)
    msgs = [m for m in results(sent) if m["segment_id"] == "climb1"]
    assert msgs and msgs[0]["pr"]
    assert msgs[0]["time_s"] < s._t_session   # temps des pauses exclu
    assert s.race.book.table("demo", "climb1", False)
    lines = list(read_journal(s._rec.path))
    assert [ln.get("reason") for ln in lines if ln.get("event") == "pause"] == ["trainer_lost"] * 2
    assert [ln["segment_id"] for ln in lines if ln.get("kind") == "segment"] == ["climb1"]


@pytest.mark.recette_sans_velo
def test_user_pause_before_moving_keeps_the_climb(env):
    """Pause Y sur la ligne de départ (s = 0), avant le premier coup de pédale : la montée compte."""
    make, run, _ = env
    s, sent = make(7152)
    s._on_command("start", {}, 2)
    s._on_command("pause", {}, 3)
    run(s, 5.0)
    s._on_command("resume", {}, 4)
    while s.physics.s < 1510.0:
        run(s, 10.0)
    assert [m["segment_id"] for m in results(sent)][:1] == ["climb1"]


# --- critère 6 : quatre bots de N9 ------------------------------------------------------------

def test_four_bots_neighbours_gaps_and_kom(env):
    make, run, _ = env
    params = PhysicsParams.from_config(Config())
    bots = [ConstantPowerBot(w, bot_id=f"b{w}", params=params, s=0.0) for w in (320, 280, 200, 160)]
    s, sent = make(7150, bots=bots)
    s._on_command("start", {}, 2)
    frames: list[dict] = []
    run(s, 400.0, frames.append)
    state_v = validator("state")
    late = frames[-1]
    assert not list(state_v.iter_errors(late))
    assert late["bot_ahead"] in {"b320", "b280"} and late["bot_behind"] in {"b200", "b160"}
    assert all("gap_s" in b and "jersey" in b for b in late["bots"])
    assert late["jerseys"]["kom"] == "b320"
    kom = {b["id"]: b["jersey"] for b in late["bots"]}
    assert kom["b320"] == "kom" and kom["b160"] is None
    climb = [m for m in results(sent) if m["segment_id"] == "climb1"][0]
    assert (climb["rank"], climb["rank_total"]) == (3, 3)   # bots arrivés avant toi seulement


# --- critère 7 : bonus coupés ; trames 1.0 inchangées sans segment ---------------------------

@pytest.mark.recette_sans_velo
def test_powerups_off_and_route_without_segments(env):
    make, run, _ = env
    cfg = Config()
    cfg.powerups.mode = "off"
    s, sent = make(7160, cfg=cfg)
    s._on_command("start", {}, 2)
    race = s.race
    frames: list[dict] = []
    ride_to_end(s, run, frames)
    assert all("powerup" not in f for f in frames)
    assert race.arches.positions == [] and race.powerups.reserve is None
    assert len(results(sent)) == 6   # segments, records et maillots restent

    cfg2 = Config()
    cfg2.powerups.mode = "off"
    s2, sent2 = make(7162, cfg=cfg2)
    s2._segments = ()
    s2._on_command("start", {}, 2)
    frames2: list[dict] = []
    run(s2, 20.0, frames2.append)
    assert frames2 and all(not (NEW_KEYS & set(f)) for f in frames2)
    assert not results(sent2)


# --- critère 8 : reprise après un plantage du core ----------------------------------------------

@pytest.mark.recette_sans_velo
def test_game_lines_are_kept_after_crash_resume(env):
    make, run, _ = env
    a, _ = make(7170)
    a._on_command("start", {}, 2)
    run(a, 300.0)                       # montée terminée
    assert a.race.powerups.reserve is not None
    a._handle_input(InputEvent.Z_SHORT)
    run(a, 2.0)
    path = a._rec.path
    a._rec._writer._fh.close()          # mort brutale : ni fin de séance ni FIT

    b, _ = make(7172)
    b.resume_session(path)
    assert b.race is not None and b.race.segments
    b._on_command("resume", {}, 3)
    run(b, 600.0)
    assert b.state.session_state == "FINISHED"
    kinds = [ln.get("kind") for ln in read_journal(path)]
    assert kinds.count("powerup") == 1
    segs = [ln["segment_id"] for ln in read_journal(path) if ln.get("kind") == "segment"]
    assert segs == ["climb1", "sprint1"]
    assert "jersey" in kinds
