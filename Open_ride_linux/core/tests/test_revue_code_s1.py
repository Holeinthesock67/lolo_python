"""Lot RV1 : corrections de la revue de code du 22 novembre 2026 (vague 1, `session.py`).

S1-01 journal impossible à ouvrir au départ, S2-01 vent fantôme de la séance suivante, S2-03 CdA de base
des bots du Dernier survivant, S1-07 `set_bots` et S1-03 demi-tour pendant une épreuve de piste."""

import time

import pytest

from openride_core import fit_export, profile, velodrome
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.session import SURVIVOR_RETIRED_S, CoreSession

DT = 0.02


@pytest.fixture
def make(tmp_path, monkeypatch):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    monkeypatch.setattr(profile, "PROFILE_PATH", tmp_path / "profile.json")
    wall = [1_790_000_000.0]
    monkeypatch.setattr(time, "time", lambda: wall[0])
    velodrome.write_velodrome(tmp_path / "routes")

    def build(port, power_w=250.0, setup=None, journal_dir=None):
        cfg = Config()
        cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
        cfg.depart.mode = "immediat"
        if setup:
            setup(cfg)
        s = CoreSession(cfg, driver=MockDriver(base_power_w=power_w, ramp_amplitude_w=0.0),
                        inputs=[NullProvider()], journal_dir=journal_dir or tmp_path / "journal",
                        routes_root=tmp_path / "routes", workouts_dir=tmp_path / "wk",
                        records_path=tmp_path / "records.json", powerups_path=tmp_path / "powerups.toml",
                        wtf_path=tmp_path / "wtf.toml")
        errors = []
        s.server.send_raw = lambda m, max_size=None: None
        s.server.send_error = lambda code, message: errors.append(code)
        s.server.send_input_event = lambda ev: None

        def run(seconds):
            for _ in range(int(seconds / DT)):
                if s.state.session_state != "RUNNING":
                    return
                wall[0] += DT
                s._step(DT, wall[0])

        return s, errors, run

    return build


# S1-01 ------------------------------------------------------------------------------------

def test_journal_impossible_au_depart_met_en_pause_puis_reprend(make, tmp_path):
    blocker = tmp_path / "bloque"
    blocker.write_text("un fichier à la place du dossier", encoding="utf-8")
    s, errors, run = make(6902, journal_dir=blocker / "journal")
    s._on_command("select_route", {"route_id": "demo"}, 1)
    s._on_command("start", {}, 2)
    # Avant la correction : RUNNING sans journal ni pause, une seule erreur.
    assert (s.state.session_state, s.state.pause_reason) == ("PAUSED", "recording_failed")
    assert "recording_failed" in errors and s._rec.failed
    # Tant que le dossier manque, la reprise est refusée et la séance reste en pause.
    s._on_command("resume", {}, 3)
    assert s.state.session_state == "PAUSED"
    # Dossier réparé : la reprise rouvre un journal qui contient le départ.
    blocker.unlink()
    s._on_command("resume", {}, 4)
    assert s.state.session_state == "RUNNING" and not s._rec.failed and s._rec.path is not None
    run(2.0)
    assert s._rec.path.exists() and '"start"' in s._rec.path.read_text(encoding="utf-8")


def test_journal_normal_au_depart_ne_met_pas_en_pause(make):
    s, errors, _ = make(6904)
    s._on_command("select_route", {"route_id": "demo"}, 1)
    s._on_command("start", {}, 2)
    assert s.state.session_state == "RUNNING" and "recording_failed" not in errors


# S2-01 ------------------------------------------------------------------------------------

def _wind(cfg):
    cfg.wind.mode, cfg.wind.speed_kmh, cfg.wind.from_deg, cfg.wind.feel = "fixed", 30.0, 0.0, "grade"


def _velodrome_speed(s, run, cmd_id):
    s._on_command("select_route", {"route_id": velodrome.TRACK_ID}, cmd_id)
    s._on_command("start", {}, cmd_id + 1)
    assert s.state.session_state == "RUNNING" and not s.wind.active   # salle couverte : vent coupé
    run(120.0)
    return s.physics.v


def test_vent_de_la_seance_precedente_ne_reste_pas(make):
    s, _, run = make(6906, setup=_wind)
    s._on_command("select_route", {"route_id": "demo"}, 1)
    s._on_command("start", {}, 2)
    run(20.0)
    assert s._head_mps != 0.0 and s.physics.p.wind_mps == pytest.approx(s._head_mps)
    assert s._base_params.wind_mps == 0.0, "le vent du pas ne doit pas s'écrire dans les paramètres de base"
    s._on_command("end_session", {"save": False}, 3)
    after_wind = _velodrome_speed(s, run, 4)
    assert s.physics.p.wind_mps == 0.0 and s._base_params.wind_mps == 0.0

    fresh, _, run_fresh = make(6908, setup=_wind)
    assert after_wind == pytest.approx(_velodrome_speed(fresh, run_fresh, 1), rel=1e-6)


def test_vent_des_bots_remis_a_zero_quand_le_vent_est_coupe(make):
    s, _, run = make(6910, setup=_wind)
    s._on_command("select_route", {"route_id": "demo"}, 1)
    s._on_command("start", {"bots": [{"kind": "constant", "power_w": 200}]}, 2)
    run(5.0)
    bot = s.bots[0]
    assert bot.params.wind_mps != 0.0
    s.wind.mode = "off"   # vent coupé alors que le bot reste (bots de la ligne de commande, réglage changé)
    run(0.1)
    assert bot.params.wind_mps == 0.0


# S2-03 ------------------------------------------------------------------------------------

def test_cda_de_base_des_bots_garde_au_retrait_d_un_elimine(make):
    def setup(cfg):
        cfg.survivor.opponents, cfg.survivor.spacing_km = 2, 2

    s, errors, run = make(6912, power_w=220.0, setup=setup)
    s._on_command("select_route", {"route_id": "demo"}, 1)
    s._on_command("start", {"mode": "survivor"}, 2)
    assert s.state.session_state == "RUNNING", errors
    run(2.0)
    base = {b.id: s._bot_cda[id(b)] for b in s.bots}
    assert len(base) == 2
    out, kept = s.bots[0], s.bots[1]
    kept.params.cda_m2 = base[kept.id] * 0.9   # poussée de l'aspiration en cours sur ce bot
    s._survivor_out[out.id] = s._t_session - SURVIVOR_RETIRED_S - 1.0   # éliminé depuis assez longtemps
    s._update_draft = lambda *args, **kwargs: None   # la poussée posée ci-dessus reste jusqu'au retrait
    run(DT)
    assert [b.id for b in s.bots] == [kept.id]
    assert s._bot_cda[id(kept)] == pytest.approx(base[kept.id])   # avant la correction : la base réduite


def test_cda_de_base_garde_pour_un_bot_conserve_par_set_bots(make):
    s, _, run = make(6914)
    bots = [{"kind": "constant", "power_w": 180}, {"kind": "constant", "power_w": 220}]
    s._on_command("select_route", {"route_id": "demo"}, 1)
    s._on_command("start", {"bots": bots}, 2)
    run(2.0)
    kept = s.bots[0]
    base = s._bot_cda[id(kept)]
    kept.params.cda_m2 = base * 0.9
    s._on_command("pause", {}, 3)
    s._on_command("set_bots", {"bots": bots[:1]}, 4)
    assert s.bots == [kept] and s._bot_cda == {id(kept): pytest.approx(base)}


# S1-07 et S1-03 ---------------------------------------------------------------------------

def _scratch(make, port):
    s, errors, run = make(port, power_w=300.0)
    s._on_command("select_route", {"route_id": velodrome.TRACK_ID}, 1)
    s._on_command("start", {"mode": "track", "track": {"event": "scratch"}}, 2)
    assert s.state.session_state == "RUNNING" and s.track_event is not None, errors
    run(10.0)
    return s, errors, run


def test_set_bots_refuse_pendant_une_epreuve_de_piste(make):
    s, errors, _ = _scratch(make, 6916)
    ids = [b.id for b in s.bots]
    assert ids
    s._on_command("pause", {}, 3)
    s._on_command("set_bots", {"bots": []}, 4)
    assert errors[-1] == "busy" and [b.id for b in s.bots] == ids


def test_demi_tour_refuse_pendant_une_epreuve_de_piste(make):
    s, errors, _ = _scratch(make, 6918)
    assert "épreuve de piste" in s._u_turn_refusal("RUNNING")
    s._on_command("pause", {}, 3)
    s._on_command("u_turn", {}, 4)
    assert s.physics.direction > 0 and errors, "le demi-tour doit être refusé avec une erreur"


def test_demi_tour_garde_en_seance_libre_sur_la_piste(make):
    s, _, run = make(6920)
    s._on_command("select_route", {"route_id": velodrome.TRACK_ID}, 1)
    s._on_command("start", {}, 2)
    run(10.0)
    assert s.track_event is None and s._u_turn_refusal("RUNNING") is None


# --- C2-01 : montée qui finit au dernier point du parcours (vague 2) ---

def test_segment_fini_au_dela_du_dernier_point_ne_bloque_pas_le_depart(tmp_path):
    """Les bornes des segments sont arrondies à 0,1 m, la longueur du parcours au millimètre : une fin
    arrondie au-dessus de la longueur était acceptée par le chargeur et refusée par la minuterie, dont
    l'erreur arrêtait le core au départ."""
    import json

    from openride_core import demo_world
    from openride_core.route import load_world
    from openride_core.segment_timing import SegmentTimer

    world_dir = demo_world.write_demo_world(tmp_path / "w")
    length = load_world(world_dir).route.length_m
    path = world_dir / "segments.json"
    layer = json.loads(path.read_text(encoding="utf-8"))
    layer["segments"][-1]["s_end"] = round(length + 0.07, 3)
    path.write_text(json.dumps(layer), encoding="utf-8")

    world = load_world(world_dir)
    assert world.segments, "la couche ne doit pas être écartée"
    assert world.segments[-1].s_end == pytest.approx(length)      # ramenée à la longueur du parcours
    SegmentTimer(world.segments, length)                           # ne lève plus


def test_minuterie_meme_tolerance_que_le_chargeur():
    from types import SimpleNamespace

    from openride_core.segment_timing import SegmentTimer

    seg = SimpleNamespace(id="c1", name="Col", type="climb", s_start=9000.0, s_end=10000.7)
    timer = SegmentTimer([seg], 10000.678)
    timer.add(SimpleNamespace(id="c2", name="Col 2", type="climb", s_start=9500.0, s_end=10000.7))
    with pytest.raises(ValueError):
        SegmentTimer([SimpleNamespace(id="c3", name="x", type="climb", s_start=9000.0, s_end=10001.0)], 10000.678)
