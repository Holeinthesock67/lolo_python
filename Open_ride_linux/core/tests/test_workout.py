"""Tests des entraînements ERG (lot F) : lecture `.zwo`, contrôleur ERG, intégration dans la session."""

import asyncio
import logging
from pathlib import Path

import pytest

from openride_core import fit_export
from openride_core.config import Config
from openride_core.demo_world import write_world
from openride_core.input_providers import NullProvider
from openride_core.journal import read_journal
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession
from openride_core.workout import (
    MAX_REPEAT, ErgController, WorkoutError, list_workouts, load_workout, parse_workout,
)
from openride_core.zwift_click import InputEvent

FTP = 250.0

REFERENCE_ZWO = """<?xml version="1.0" encoding="UTF-8"?>
<workout_file>
    <author>OpenRide</author>
    <name>Référence lot F</name>
    <description>Échauffement, palier, 3 x 1 min, roue libre, retour au calme</description>
    <sportType>bike</sportType>
    <workout>
        <Warmup Duration="600" PowerLow="0.5" PowerHigh="0.75"/>
        <SteadyState Duration="1200" Power="0.95"/>
        <IntervalsT Repeat="3" OnDuration="60" OffDuration="60" OnPower="1.2" OffPower="0.5"/>
        <FreeRide Duration="120"/>
        <Cooldown Duration="300" PowerLow="0.7" PowerHigh="0.4"/>
    </workout>
</workout_file>
"""

# Casse libre, balise inconnue textevent (au niveau des blocs et dans un bloc), attribut Cadence.
TEXTEVENT_ZWO = """<WORKOUT_FILE>
    <Name>Avec messages</Name>
    <Workout>
        <steadystate duration="300" power="0.6" Cadence="90">
            <textevent timeoffset="10" message="Allez !"/>
        </steadystate>
        <textevent timeoffset="20" message="Encore"/>
        <textevent timeoffset="30" message="Toujours"/>
        <Ramp Duration="120" PowerLow="0.6" PowerHigh="0.9"/>
    </Workout>
</WORKOUT_FILE>
"""

INVALID_ZWOS = {
    "mal_forme": "<workout_file><name>x</name><workout><SteadyState Duration='60' Power='0.5'></workout>",
    "sans_duree": "<workout_file><workout><SteadyState Power='0.8'/></workout></workout_file>",
    "puissance_negative": "<workout_file><workout><Warmup Duration='60' PowerLow='-0.1' PowerHigh='0.5'/>"
                          "</workout></workout_file>",
    "trop_fort": "<workout_file><workout><SteadyState Duration='60' Power='3.5'/></workout></workout_file>",
    "course_a_pied": "<workout_file><sportType>run</sportType><workout>"
                     "<SteadyState Duration='60' Power='0.8'/></workout></workout_file>",
    "aucun_bloc": "<workout_file><name>vide</name><workout><textevent message='rien'/></workout></workout_file>",
}


@pytest.fixture
def workouts_dir(tmp_path: Path) -> Path:
    d = tmp_path / "Workouts"
    d.mkdir()
    (d / "reference.zwo").write_text(REFERENCE_ZWO, encoding="utf-8")
    (d / "textevent.zwo").write_text(TEXTEVENT_ZWO, encoding="utf-8")
    for name, text in INVALID_ZWOS.items():
        (d / f"invalide_{name}.zwo").write_text(text, encoding="utf-8")
    return d


def advance(ctrl: ErgController, seconds: float, dt: float = 0.02) -> ErgController:
    """Avance le contrôleur de `seconds` secondes par pas de 50 Hz."""
    for _ in range(round(seconds / dt)):
        ctrl.step(dt)
    return ctrl


def reference(workouts_dir: Path) -> ErgController:
    return ErgController(load_workout(workouts_dir / "reference.zwo"), FTP)


# --- lecture ------------------------------------------------------------------------------

def test_reference_file_blocks(workouts_dir):
    w = load_workout(workouts_dir / "reference.zwo")
    assert w.id == "reference" and w.name == "Référence lot F"
    assert len(w.blocks) == 10
    assert w.duration_s == 2580.0
    expected = [("warmup", 600, 0.5, 0.75), ("steady", 1200, 0.95, 0.95)]
    expected += [("interval_on", 60, 1.2, 1.2), ("interval_off", 60, 0.5, 0.5)] * 3
    expected += [("freeride", 120, None, None), ("cooldown", 300, 0.7, 0.4)]
    assert [(b.type, b.duration_s, b.start_frac, b.end_frac) for b in w.blocks] == expected


def test_metadata_tags_logged_at_debug_only(workouts_dir, caplog):
    with caplog.at_level(logging.DEBUG, logger="workout"):
        load_workout(workouts_dir / "reference.zwo")
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    debug = " ".join(r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG)
    assert "« author »" in debug and "« sportType »" in debug


def test_unknown_tags_warn_once_per_name(workouts_dir, caplog):
    with caplog.at_level(logging.WARNING, logger="workout"):
        w = load_workout(workouts_dir / "textevent.zwo")
    assert w.name == "Avec messages"
    assert [b.type for b in w.blocks] == ["steady", "ramp"]
    warnings = [r.getMessage() for r in caplog.records]
    assert sum("« textevent »" in m for m in warnings) == 1
    assert sum("cadence" in m for m in warnings) == 1


@pytest.mark.parametrize("name", sorted(INVALID_ZWOS))
def test_invalid_files_raise_workout_error(workouts_dir, name):
    with pytest.raises(WorkoutError) as exc:
        load_workout(workouts_dir / f"invalide_{name}.zwo")
    assert str(exc.value)


def test_list_workouts_marks_invalid_files(workouts_dir):
    infos = {i.id: i for i in list_workouts(workouts_dir)}
    assert infos["reference"].selectable and infos["reference"].duration_s == 2580.0
    assert len(infos["reference"].profile) == 10
    assert infos["textevent"].selectable
    for name in INVALID_ZWOS:
        info = infos[f"invalide_{name}"]
        assert not info.selectable and info.error
    assert list_workouts(workouts_dir / "absent") == []


def test_intervals_repeat_must_be_integer():
    with pytest.raises(WorkoutError):
        parse_workout("<workout_file><workout><IntervalsT Repeat='1.5' OnDuration='30' OffDuration='30'"
                      " OnPower='1' OffPower='0.5'/></workout></workout_file>", "x")


def test_intervals_repeat_is_bounded():
    """Un Repeat aberrant est refusé au lieu de déplier des millions de blocs (vérification du 24 octobre, R1)."""
    zwo = ("<workout_file><workout><IntervalsT Repeat='{}' OnDuration='1' OffDuration='1'"
           " OnPower='1' OffPower='0.5'/></workout></workout_file>")
    assert len(parse_workout(zwo.format(MAX_REPEAT), "x").blocks) == 2 * MAX_REPEAT
    with pytest.raises(WorkoutError, match="dépasse"):
        parse_workout(zwo.format(MAX_REPEAT + 1), "x")
    with pytest.raises(WorkoutError):
        parse_workout(zwo.format(2_000_000), "x")


# --- contrôleur ---------------------------------------------------------------------------

def test_targets(workouts_dir):
    c = reference(workouts_dir)
    assert c.target_w == 125                       # t = 0 : 0,5 × 250
    c.step(300.0)
    assert c.target_w == 156                       # 0,625 × 250 = 156,25
    c.step(300.0)
    assert c.block.type == "steady"
    c.step(300.0)                                  # plein palier, lissage fini
    assert c.target_w == 238                       # 0,95 × 250 = 237,5, arrondi au pair
    c.step(900.0)                                  # t = 2400 : premier intervalle « on »
    assert c.block.type == "interval_on"
    c.step(10.0)
    assert c.target_w == 300                       # 1,2 × 250


def test_block_change_smoothing(workouts_dir):
    c = reference(workouts_dir)
    c.step(599.98)
    assert c.target_w == 187                       # 0,74999 × 250 = 187,498
    c.step(0.02)                                   # passage échauffement → palier
    assert c.block.type == "steady" and c.target_w == 188   # 0,75 × 250 = 187,5
    seen = [advance(c, 0.02).target_w for _ in range(100)]  # 2 s par pas de 50 Hz
    assert abs(seen[49] - 213) <= 1                # à 1 s
    assert seen == sorted(seen) and seen[-1] == 238
    assert advance(c, 1.0).target_w == 238


def test_bias(workouts_dir):
    c = reference(workouts_dir)
    c.step(1000.0)                                 # plein palier
    for _ in range(5):
        c.change_bias(+1)
    assert c.bias_pct == 110 and c.target_w == 261  # appliqué tout de suite
    for _ in range(10):
        c.change_bias(+1)
    assert c.bias_pct == 120 and c.target_w == 285
    for _ in range(40):
        c.change_bias(-1)
    assert c.bias_pct == 80


def test_skip_and_pause(workouts_dir):
    c = reference(workouts_dir)
    c.step(1200.0)                                 # milieu du palier
    assert c.block.type == "steady"
    c.skip()
    assert c.block.type == "interval_on" and c.index == 2 and c.target_w == 238
    assert advance(c, 1.0).target_w == 269         # (0,95 + 1,2) / 2 × 250 = 268,75
    assert advance(c, 1.0).target_w == 300
    remaining = c.to_dict()["block_remaining_s"]
    c.toggle_pause()
    advance(c, 30.0)
    assert c.paused and c.to_dict()["block_remaining_s"] == remaining
    c.toggle_pause()
    assert not c.paused and c.to_dict()["block_remaining_s"] == remaining
    assert advance(c, 1.0).to_dict()["block_remaining_s"] == pytest.approx(remaining - 1.0, abs=0.01)


def test_freeride_and_end(workouts_dir):
    c = reference(workouts_dir)
    c.step(2170.0)
    assert c.block.type == "freeride" and c.is_freeride and not c.target_active
    d = c.to_dict()
    assert d["target_w"] == 0 and d["next_target_w"] == 175
    c.step(110.0)                                  # début du retour au calme
    assert c.block.type == "cooldown" and c.target_w == 175   # pas de lissage après la roue libre
    assert c.to_dict()["next_target_w"] is None
    c.skip()
    assert c.finished


# --- session ------------------------------------------------------------------------------

@pytest.mark.parametrize("dt", [-10.0, -1e-9, float("nan"), float("inf"), float("-inf")])
def test_step_refuses_invalid_dt(workouts_dir, dt):
    """Lot M9 (constat R3) : pas de temps négatif, infini ou NaN refusé ; l'état ne bouge pas."""
    reference = ErgController(load_workout(workouts_dir / "reference.zwo"), FTP)
    with pytest.raises(ValueError, match="pas de temps invalide"):
        reference.step(dt)
    assert reference.t_block == 0.0 and reference.index == 0


def test_step_zero_is_accepted(workouts_dir):
    reference = ErgController(load_workout(workouts_dir / "reference.zwo"), FTP)
    reference.step(0.0)
    assert reference.t_block == 0.0 and not reference.finished


@pytest.mark.parametrize("ftp", [0, -200.0, float("nan"), float("inf")])
def test_constructor_refuses_invalid_ftp(workouts_dir, ftp):
    with pytest.raises(ValueError, match="FTP invalide"):
        ErgController(load_workout(workouts_dir / "reference.zwo"), ftp)


def make_session(tmp_path, monkeypatch, workouts_dir, port=5950):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    cfg = Config()
    cfg.rider.ftp_w = FTP
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    driver = MockDriver()
    s = CoreSession(cfg, driver=driver, inputs=[NullProvider()], journal_dir=tmp_path / "journal",
                    routes_root=tmp_path / "routes", workouts_dir=workouts_dir)
    errors: list[tuple[str, str]] = []
    s.server.send_error = lambda code, message: errors.append((code, message))   # type: ignore
    return s, driver, errors


def run(s, seconds, dt=0.02):
    """Pas de simulation en temps accéléré (le trainer simulé reste connecté)."""
    for _ in range(round(seconds / dt)):
        s._step(dt, 0.0)


def test_session_erg_flow(tmp_path, monkeypatch, workouts_dir):
    async def scenario():
        s, driver, errors = make_session(tmp_path, monkeypatch, workouts_dir)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("select_workout", {"workout_id": "reference"}, 2)
        assert s.state.mode == "SIM" and s.state.erg is None and not errors
        s._on_command("start", {}, 3)
        assert s.state.mode == "ERG" and s.state.erg["block_count"] == 10
        run(s, 1.0)
        assert driver.target_power_w == pytest.approx(s.state.erg["target_w"], abs=1)
        assert 125 <= s.state.erg["target_w"] <= 126
        # Biais : appuis courts.
        for _ in range(5):
            s._handle_input(InputEvent.PLUS_SHORT)
        assert s.state.erg["bias_pct"] == 110 and s.gearing.k == 12
        for _ in range(5):
            s._handle_input(InputEvent.MINUS_SHORT)
        # Pause ERG : temps du bloc arrêté, pente 0 %.
        s.erg.t_block = 300.0
        s._handle_input(InputEvent.MINUS_LONG)
        remaining = s.state.erg["block_remaining_s"]
        run(s, 5.0)
        assert s.state.erg["paused"] and driver.target_power_w is None and driver.sim_grade_pct == 0.0
        assert s.state.erg["block_remaining_s"] == pytest.approx(remaining, abs=0.1)
        s._handle_input(InputEvent.MINUS_LONG)
        run(s, 0.02)
        assert driver.target_power_w is not None
        assert s.state.erg["block_remaining_s"] == pytest.approx(remaining, abs=0.1)
        # Saut de bloc : appui long + puis commande skip_block.
        s._handle_input(InputEvent.PLUS_LONG)
        assert s.state.erg["block_type"] == "steady"
        s._on_command("skip_block", {}, 4)
        assert s.state.erg["block_type"] == "interval_on" and s.state.erg["block_index"] == 3
    asyncio.run(scenario())


def test_session_freeride_uses_gears(tmp_path, monkeypatch, workouts_dir):
    async def scenario():
        s, driver, _ = make_session(tmp_path, monkeypatch, workouts_dir, port=5960)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("select_workout", {"workout_id": "reference"}, 2)
        s._on_command("start", {}, 3)
        for _ in range(8):
            s._on_command("skip_block", {}, 0)
        run(s, 1.0)
        erg = s.state.erg
        assert s.state.mode == "SIM" and erg["block_type"] == "freeride"
        assert erg["target_w"] == 0 and erg["next_target_w"] == 175
        assert driver.target_power_w is None
        s._handle_input(InputEvent.PLUS_SHORT)
        assert s.gearing.k == 13 and s.state.erg["bias_pct"] == 100
        s._on_command("skip_block", {}, 0)
        run(s, 0.1)
        assert s.state.mode == "ERG" and driver.target_power_w == 175
        s._on_command("skip_block", {}, 0)             # dernier bloc : fin de l'entraînement
        assert s.state.mode == "SIM" and s.state.erg is None
        run(s, 0.1)
        assert driver.target_power_w is None and s.state.session_state == "RUNNING"
    asyncio.run(scenario())


def test_session_invalid_workout(tmp_path, monkeypatch, workouts_dir):
    async def scenario():
        s, _, errors = make_session(tmp_path, monkeypatch, workouts_dir, port=5970)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        for i, wid in enumerate(["invalide_mal_forme", "absent", "../reference"]):
            s._on_command("select_workout", {"workout_id": wid}, 2 + i)
            assert errors[-1][0] == "workout_invalid"
        assert len(errors) == 3
        s._on_command("start", {}, 9)
        run(s, 0.5)
        assert s.state.mode == "SIM" and s.state.erg is None and s.state.session_state == "RUNNING"
    asyncio.run(scenario())


def test_session_null_workout_returns_to_sim(tmp_path, monkeypatch, workouts_dir):
    async def scenario():
        s, _, _ = make_session(tmp_path, monkeypatch, workouts_dir, port=5980)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("select_workout", {"workout_id": "reference"}, 2)
        s._on_command("select_workout", {"workout_id": None}, 3)
        s._on_command("start", {}, 4)
        assert s.state.mode == "SIM" and s.erg is None
    asyncio.run(scenario())


def test_session_pause_stops_workout_time(tmp_path, monkeypatch, workouts_dir):
    async def scenario():
        s, _, _ = make_session(tmp_path, monkeypatch, workouts_dir, port=5990)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("select_workout", {"workout_id": "reference"}, 2)
        s._on_command("start", {}, 3)
        run(s, 2.0)
        remaining = s.state.erg["block_remaining_s"]
        s._on_command("pause", {}, 4)
        run(s, 5.0)
        assert s.state.erg["block_remaining_s"] == remaining
    asyncio.run(scenario())


def test_full_workout_journal(tmp_path, monkeypatch, workouts_dir):
    async def scenario():
        s, _, _ = make_session(tmp_path, monkeypatch, workouts_dir, port=6000)
        write_world(tmp_path / "routes", "long", 40000.0)   # assez long pour tout l'entraînement
        s._on_command("select_route", {"route_id": "long"}, 1)
        s._on_command("select_workout", {"workout_id": "reference"}, 2)
        s._on_command("start", {}, 3)
        run(s, 2600.0, dt=0.1)                              # temps accéléré
        assert s.erg is None and s.state.mode == "SIM" and s.state.session_state == "RUNNING"
        s._on_command("end_session", {"save": False}, 4)
        records = [r for r in read_journal(next((tmp_path / "journal").glob("*.jsonl")))
                   if r["kind"] == "record"]
        erg_records = [r for r in records if r["mode"] == "ERG"]
        assert len(erg_records) > 2000
        assert all(r["target_w"] is not None and r["target_w"] > 0 for r in erg_records)
        blocks = [r["block"] for r in records if r["block"] is not None]
        assert blocks == sorted(blocks) and blocks[0] == 1 and blocks[-1] == 10
        assert set(blocks) == set(range(1, 11))
        assert {r["mode"] for r in records if r["block"] == 9} == {"SIM"}   # roue libre
        assert all(r["target_w"] is None for r in records if r["block"] == 9)
        assert records[-1]["block"] is None and records[-1]["target_w"] is None  # après la fin

        # Critère 2 du lot L6 : SteadyState 0,8 × FTP = 200 W, biais 110 % = 220 W, puis FreeRide.
        (workouts_dir / "l6_cible.zwo").write_text(
            "<workout_file><name>L6</name><workout>"
            "<SteadyState Duration='10' Power='0.8'/>"
            "<FreeRide Duration='5'/>"
            "</workout></workout_file>",
            encoding="utf-8",
        )
        jdir2 = tmp_path / "journal_l6"
        s2 = CoreSession(
            s.cfg, driver=MockDriver(), inputs=[NullProvider()], journal_dir=jdir2,
            routes_root=tmp_path / "routes", workouts_dir=workouts_dir,
        )
        s2._on_command("select_route", {"route_id": "long"}, 10)
        s2._on_command("select_workout", {"workout_id": "l6_cible"}, 11)
        s2._on_command("start", {}, 12)
        run(s2, 4.0)   # t = 1..4 s : avant biais (200 W)
        for _ in range(5):
            s2._handle_input(InputEvent.PLUS_SHORT)  # bias_pct = 110 % -> 220 W
        run(s2, 14.0)  # jusqu'à t = 18 s (traverse fin du SteadyState à 10 s, FreeRide 10..15 s, puis fin)
        s2._on_command("end_session", {"save": False}, 13)
        recs2 = [r for r in read_journal(next(jdir2.glob("*.jsonl"))) if r["kind"] == "record"]
        before_bias = [r for r in recs2 if r["t"] <= 4.0]
        after_bias = [r for r in recs2 if 5.0 <= r["t"] <= 9.5]
        freeride_recs = [r for r in recs2 if r["block"] == 2]
        post_workout = [r for r in recs2 if r["block"] is None]
        assert before_bias and all(r["target_w"] == 200 for r in before_bias)
        assert after_bias and all(r["target_w"] == 220 for r in after_bias)
        assert freeride_recs and all(r["target_w"] is None for r in freeride_recs)
        assert post_workout and all(r["target_w"] is None for r in post_workout)
    asyncio.run(scenario())
