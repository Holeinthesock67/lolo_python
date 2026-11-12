"""Lot GP2 : mode « Grand Prix des objets » branché dans la séance (plateau, objets, voies, trame, bilan).

Critères du cahier `docs/lots/LOT_GP2_seance_contrat.md` §4 : course de 3 tours avec 4 bots sans erreur,
puissance mesurée intacte au journal et au FIT ; pente envoyée identique, pas à pas, à celle d'une séance sans
objets à la même position, la même vitesse virtuelle et le même abri ; trame sous 4 096 octets ; les autres
modes ne changent pas (leurs tests restent verts)."""

import json
import time
import tomllib
from pathlib import Path

import jsonschema
import pytest

from openride_core import fit_export, profile, settings
from openride_core.bots import ProfileBot
from openride_core.config import Config
from openride_core.demo_world import write_world
from openride_core.grandprix import ITEM_IDS, ME
from openride_core.grandprix.mode import LANE_CENTRES_M
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession
from openride_core.draft import BIKE_LENGTH_M
from openride_core.tools.bots_race import contacts
from openride_core.tools.route_vectors import _route

IPC_DIR = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc"
DT = 0.02
T0_WALL = 1_790_000_000.0
STATE_LIMIT_BYTES = 4096
POWER_W = 250.0

ERG_ZWO = """<?xml version="1.0" encoding="UTF-8"?>
<workout_file><name>ERG</name><workout><SteadyState Duration="600" Power="0.70"/></workout></workout_file>
"""


def validator(name: str) -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(json.loads((IPC_DIR / f"{name}.schema.json").read_text("utf-8")))


def loop_route(lap_m: float = 1500.0) -> dict:
    """Circuit fermé de `lap_m` (pas de 10 m), une bosse douce de 6 m."""
    n = int(lap_m / 10.0) + 1
    headings = [i * 360.0 / (n - 1) for i in range(n)]
    alts = [100.0 + 6.0 * (1.0 - abs(2.0 * i / (n - 1) - 1.0)) for i in range(n)]
    return _route(headings, alts, ds=10.0, last=10.0, kind="loop")


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    monkeypatch.setattr(profile, "PROFILE_PATH", tmp_path / "profile.json")
    wall = [T0_WALL]
    monkeypatch.setattr(time, "time", lambda: wall[0])
    workouts = tmp_path / "Workouts"
    workouts.mkdir()
    (workouts / "erg.zwo").write_text(ERG_ZWO, encoding="utf-8")
    world = write_world(tmp_path / "routes", "anneau", 1500.0)
    (world / "route.json").write_text(json.dumps(loop_route()), encoding="utf-8")

    def make(port: int, opponents: int = 4, laps: int = 3, distance_km: int = 10, route_id: str = "anneau",
             level_pct: int = 100) -> tuple[CoreSession, list, list]:
        cfg = Config()
        cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
        cfg.grandprix.opponents, cfg.grandprix.laps, cfg.grandprix.distance_km = opponents, laps, distance_km
        cfg.bots.level_pct = level_pct
        cfg.ride.vehicle_draft = "off"
        s = CoreSession(cfg, driver=MockDriver(base_power_w=POWER_W, ramp_amplitude_w=0.0),
                        inputs=[NullProvider()], journal_dir=tmp_path / "journal",
                        routes_root=tmp_path / "routes", workouts_dir=workouts,
                        records_path=tmp_path / "records.json", powerups_path=tmp_path / "powerups.toml",
                        wtf_path=tmp_path / "wtf.toml", grandprix_path=tmp_path / "grandprix.toml")
        sent: list[dict] = []
        errors: list[tuple[str, str]] = []
        s.server.send_raw = lambda m, max_size=None: sent.append(m)
        s.server.send_error = lambda code, msg: errors.append((code, msg))
        s.server.send_input_event = lambda ev: None
        s._on_command("select_route", {"route_id": route_id}, 1)
        return s, sent, errors

    def frame(s: CoreSession) -> dict:
        s.state.bots = [b.to_dict() for b in s.bots] or None
        s._fill_race_frame()
        s._fill_grandprix_frame()
        s._lighten_bots_frame()
        return s.state.to_dict()

    def run(s: CoreSession, seconds: float, check=None, every: int = 15) -> None:
        for i in range(int(round(seconds / DT))):
            if s.state.session_state != "RUNNING":
                return
            wall[0] += DT
            s._step(DT, wall[0])
            if check and i % every == 0:
                check(s)

    return make, run, frame, tmp_path


def test_three_laps_four_bots_frames_hits_and_bilan(env):
    make, run, frame, tmp_path = env
    s, sent, errors = make(6800)
    s._on_command("start", {"mode": "grandprix"}, 2)
    assert not errors and s.state.session_state == "RUNNING" and s.race is None
    assert [type(b) for b in s.bots] == [ProfileBot] * 4
    gp = s.grandprix
    assert gp.lap_m == pytest.approx(1500.0) and gp.length_m == pytest.approx(4500.0)
    assert len(gp.boxes.rows) == 3                       # une rangée par tour, à 500 m de la ligne
    state_v = validator("state")
    seen: list[dict] = []

    def check(sess):
        d = frame(sess)
        state_v.validate(d)
        assert len(json.dumps(d, ensure_ascii=False).encode()) < STATE_LIMIT_BYTES
        assert d["mode"] == "SIM" and "segment" not in d and "powerup" not in d
        assert all("item" in b and "fx" in b for b in d["bots"])
        seen.append(d["gp"])
        if d["gp"]["held"]:
            sess._grandprix_press("Z_SHORT")             # le cycliste lance tout ce qu'il reçoit

    me = gp.racers[ME]
    me.held, me.charges = "musette_x3", 3                # de quoi toucher un bot dès le départ
    run(s, 1200, check)
    assert s.state.session_state == "FINISHED" and not errors
    assert {f["lap"][1] for f in seen} == {3} and max(f["lap"][0] for f in seen) == 3
    summary = s.state.summary["gp"]
    assert 1 <= summary["place"] <= 5 and summary["of"] == 5 and summary["laps"] == 3
    assert sum(summary["launched"].values()) >= 1
    hits = [m for m in sent if m.get("type") == "gp_hit"]
    hit_v = validator("gp_hit")
    for m in hits:
        hit_v.validate(m)
    assert len(hits) % 3 == 0 and hits                   # chaque coup envoyé 3 fois
    # Puissance mesurée intacte au journal et au FIT
    journal = next((tmp_path / "journal").glob("*.jsonl"))
    lines = [json.loads(x) for x in journal.read_text("utf-8").splitlines()]
    records = [ln for ln in lines if ln.get("kind") == "record"]
    assert records and {ln["power"] for ln in records} == {round(POWER_W)}
    kinds = [ln.get("kind") for ln in lines]
    assert "gp_start" in kinds and "gp" in kinds and kinds[-1] != "gp_start" and "gp_summary" in kinds
    assert s.state.summary["fit_path"] and Path(s.state.summary["fit_path"]).is_file()
    assert s.grandprix is None and s.state.gp is None


def test_grade_sent_ignores_objects(env, monkeypatch):
    """Pas à pas, la pente envoyée d'une course avec objets (coups de fouet, glissade) est celle d'une séance
    sans objets placée à la même position, à la même vitesse virtuelle et au même abri."""
    make, run, frame, _ = env
    a, _, errors = make(6810)
    a._on_command("start", {"mode": "grandprix"}, 2)
    assert not errors
    gp = a.grandprix
    me = gp.racers[ME]
    me.held, me.charges = "gel_x3", 3
    steps: list[tuple[float, float, float, float]] = []
    pressed = [0]

    def check(sess):
        if pressed[0] < 3 and sess._grandprix_press("Z_SHORT"):
            pressed[0] += 1
        if pressed[0] == 3 and not gp.objects:           # un bidon sur sa voie, 20 m devant : glissade
            gp.objects.add("bottle", sess.physics.s + 20.0, me.lane, gp.clock, 90.0)
            pressed[0] += 1

    step = a._step

    def recording(dt, now):
        s0, v0 = a.physics.s, a.physics.v
        step(dt, now)
        steps.append((s0, v0, a._draft, a._suction, a._grade_sent))

    monkeypatch.setattr(a, "_step", recording)
    run(a, 90, check, every=50)
    assert sum(gp.racers[ME].launched.values()) == 3 and gp.racers[ME].received.get("bottle") == 1

    b, _, errors = make(6820)
    b.cfg.powerups.mode = "off"
    b._on_command("start", {"bots": []}, 2)               # séance classique, sans bot ni objet
    assert not errors and b.grandprix is None and not b.bots
    now = {}

    def same_draft(*_args):                               # même abri (bots et véhicules) que la course
        b._draft, b._suction = now["draft"], now["suction"]

    monkeypatch.setattr(b, "_update_draft", same_draft)
    wall = T0_WALL
    for s0, v0, draft, suction, sent in steps:
        b.physics.s, b.physics.v = s0, v0
        now.update(draft=draft, suction=suction)
        wall += DT
        b._step(DT, wall)
        assert b._grade_sent == pytest.approx(sent, abs=1e-12)


def test_start_refusals_and_erg_refused(env):
    make, run, _, _ = env
    s, _, errors = make(6830, route_id="demo")           # parcours en ligne de 5 km, course de 10 km
    s._on_command("start", {"mode": "grandprix"}, 2)
    assert errors[-1][0] == "bad_args" and "trop court" in errors[-1][1] and s.state.session_state == "READY"
    s, _, errors = make(6840)
    s._on_command("start", {"mode": "grandprix", "bots": []}, 2)
    assert errors[-1][0] == "bad_args" and s.state.session_state == "READY"
    s._on_command("select_workout", {"workout_id": "erg"}, 3)
    s._on_command("start", {"mode": "grandprix"}, 4)
    assert errors[-1][0] == "bad_args" and s.state.session_state == "READY"
    s._on_command("select_workout", {"workout_id": None}, 5)
    s.cfg.grandprix.box_every_m = 1200
    s._on_command("start", {"mode": "grandprix"}, 6)
    assert errors[-1][0] == "bad_args" and "boîtes" in errors[-1][1]
    s.cfg.grandprix.box_every_m = 2500                   # pas de 500 m : accepté
    s._on_command("start", {"mode": "grandprix"}, 7)
    assert s.state.session_state == "RUNNING"
    run(s, 1)
    s._on_command("set_ride_mode", {"mode": "erg"}, 8)
    assert errors[-1][0] == "busy" and s.state.mode == "SIM"
    s, _, errors = make(6850, route_id="demo", distance_km=5)
    s._on_command("start", {"mode": "grandprix"}, 2)
    assert not errors and s.grandprix.lap_m is None and s.grandprix.length_m == 5000.0


def test_lane_buttons_and_pause(env):
    make, run, frame, _ = env
    s, _, errors = make(6860)
    s._on_command("start", {"mode": "grandprix"}, 2)
    run(s, 2)
    gp = s.grandprix
    assert gp.lane_target(ME) is None and s._lane.auto
    assert s._grandprix_press("RIGHT_SHORT") and gp.lane_target(ME) == 2
    # lot GP12 : voie tenue (sans roue ni éventail), mais il double et s'écarte comme les autres
    assert s._lane.auto and not s._lane.follow and s._lane.home == LANE_CENTRES_M[2]
    assert s._grandprix_press("LEFT_SHORT") and gp.lane_target(ME) == 1
    assert not s._grandprix_press("A_SHORT") or frame(s)["gp"]["pick"]   # A court : seulement si choix affiché
    gp.objects.add("bottle", s.physics.s + 60.0, 1, gp.clock, 90.0)
    assert frame(s)["gp"]["pick"] and s._grandprix_press("A_SHORT") and gp.lane_target(ME) == 2
    assert s._grandprix_press("A_LONG") and gp.lane_target(ME) is None
    run(s, 0.1)
    assert s._lane.auto and s._lane.follow and s._lane.home == pytest.approx(1.2)
    assert not s._grandprix_press("A_LONG") and not s._grandprix_press("UP_SHORT")   # vue de caméra
    # Pause : objets figés, puis 3 s sans coup reçu après la reprise
    clock = gp.clock
    s._on_command("pause", {}, 3)
    for _ in range(10):
        s._step(DT, T0_WALL)
    assert gp.clock == clock and gp.was_paused
    s._on_command("resume", {}, 4)
    run(s, 0.1)
    assert gp.grace_until == pytest.approx(clock + 3.0, abs=0.05)
    assert not errors


def _contacts(s: CoreSession) -> set[tuple[str, str]]:
    """Paires de coureurs encore en course qui se touchent (règle du banc, lot PL1 : `bots_race.contacts`)."""
    gp = s.grandprix
    runners = [(b.id, b.s, b.lane.m) for b in s.bots if gp.racers[b.id].finished is None]
    if gp.racers[ME].finished is None:
        runners.append((ME, s.physics.s, s._lane.m))
    return contacts(runners)


@pytest.mark.slow
@pytest.mark.parametrize("chaos", ["normal", "wild"])
def test_gp12_three_laps_without_contact(env, chaos):
    """Lot GP12 : course de 3 tours à 4 adversaires, le cycliste lance tout ce qu'il reçoit : aucun contact entre
    coureurs (voies imposées qui doublent, objets qui ne poussent personne dans une roue). Avant : 1 à 3 frôlements."""
    make, run, _, _ = env
    s, _, errors = make(6880 if chaos == "normal" else 6890)
    s.cfg.grandprix.chaos = chaos
    s._on_command("start", {"mode": "grandprix"}, 2)
    assert s.grandprix is not None and s.grandprix.chaos == chaos
    s.grandprix.rng.seed(0)                               # tirage des boîtes fixé : esquives et coups pendant la course
    touching: set[tuple[str, str]] = set()
    new: list[tuple[float, tuple[str, str]]] = []
    forced = [0]

    def check(sess):
        nonlocal touching
        if sess.grandprix is None:                        # arrivée du cycliste : bilan
            return
        now = _contacts(sess)
        new.extend((round(sess._t_session, 2), p) for p in now - touching)
        touching = now
        forced[0] += any(sess.grandprix.lane_target(r) is not None for r in sess.grandprix.racers)
        if sess.grandprix.racers[ME].held:
            sess._grandprix_press("Z_SHORT")

    run(s, 1200, check, every=1)
    assert s.state.session_state == "FINISHED" and not errors
    assert forced[0] > 0                                  # des voies imposées pendant la course
    assert new == []


def test_gp12_object_never_pushes_into_a_wheel(env):
    """Lot GP12 : file de trois coureurs roue dans la roue ; celui de devant glisse (bidon) : les deux suivants
    freinent dans le même pas, quel que soit l'ordre des bots ; un coup de fouet ne pousse pas dans la roue devant."""
    make, run, _, _ = env
    s, _, _ = make(6900, opponents=3)
    s._on_command("start", {"mode": "grandprix"}, 2)
    run(s, 0.1)
    a, b, c = s.bots[:3]
    base = s.physics.s + 50.0
    for bot, k in ((c, 0), (a, 1), (b, 2)):              # c devant, puis a, puis b : ordre de la liste mélangé
        bot.physics.s, bot.physics.v = base - k * (BIKE_LENGTH_M + 0.05), 10.0
        bot.lane.m = bot.lane.target = bot.lane.home = 1.45
        bot.lane.rate, bot.lane.blocked = 0.0, None
    s.physics.v = 8.0
    s._brake_grandprix_wheels(s.bots)
    assert a.lane.blocked is None and b.lane.blocked is None   # même vitesse : aucun enfermé
    c.physics.v = 7.0                                    # glissade du premier
    s._brake_grandprix_wheels(s.bots)
    assert a.physics.v == pytest.approx(7.0) and b.physics.v == pytest.approx(7.0)
    a.physics.v, b.physics.v, c.physics.v = 10.0, 10.0 * 1.4, 10.0   # coup de fouet du dernier
    s._brake_grandprix_wheels(s.bots)
    assert b.physics.v == pytest.approx(10.0)


def test_mode_options_and_wtf_alias(env):
    make, _, _, tmp_path = env
    s, sent, errors = make(6870)
    s._on_command("list_mode_options", {"mode": "grandprix"}, 2)
    msg = sent[-1]
    validator("mode_options").validate(msg)
    assert msg["mode"] == "grandprix" and [o["id"] for o in msg["options"]] == list(ITEM_IDS)
    assert all(o["on"] for o in msg["options"])
    path = tmp_path / "grandprix.toml"
    path.write_text("# mes valeurs\n[gel]\nkick = 1.25\n", encoding="utf-8")
    s._on_command("set_mode_option", {"mode": "grandprix", "id": "storm", "on": False}, 3)
    msg = sent[-1]
    assert msg["type"] == "mode_options" and not next(o for o in msg["options"] if o["id"] == "storm")["on"]
    text = path.read_text("utf-8")
    assert "# mes valeurs" in text and tomllib.loads(text) == {"gel": {"kick": 1.25}, "items": {"storm": False}}
    s._on_command("start", {"mode": "grandprix"}, 4)
    assert "storm" not in s.grandprix.enabled
    s._on_command("set_mode_option", {"mode": "grandprix", "id": "storm", "on": True}, 5)
    assert "storm" in s.grandprix.enabled and "storm" in s.grandprix.table.enabled
    s._on_command("set_mode_option", {"mode": "grandprix", "id": "banane", "on": True}, 6)
    assert errors[-1][0] == "mode_option_invalid"
    s._on_command("set_mode_option", {"mode": "kart", "id": "gel", "on": True}, 7)
    assert errors[-1][0] == "bad_args"
    s._on_command("list_mode_options", {}, 8)
    assert errors[-1][0] == "bad_args"
    # Mode WTF : commande générique et ancienne commande, même fichier
    s._on_command("set_mode_option", {"mode": "wtf", "id": "cheese", "on": False}, 9)
    msg = sent[-1]
    validator("mode_options").validate(msg)
    assert msg["mode"] == "wtf" and not next(o for o in msg["options"] if o["id"] == "cheese")["on"]
    s._on_command("list_wtf_rules", {}, 10)
    assert sent[-1]["type"] == "wtf_rules" and not next(r for r in sent[-1]["rules"] if r["id"] == "cheese")["on"]
    s._on_command("set_wtf_rule", {"id": "cheese", "on": True}, 11)
    assert sent[-1]["type"] == "wtf_rules" and next(r for r in sent[-1]["rules"] if r["id"] == "cheese")["on"]


def test_classic_ride_unchanged_after_grandprix(env):
    make, run, _, _ = env
    s, _, _ = make(6880)
    s._on_command("start", {"mode": "grandprix"}, 2)
    run(s, 5)
    s._on_command("end_session", {"save": False}, 3)
    s._on_command("select_route", {"route_id": "anneau"}, 4)
    s._on_command("start", {}, 5)
    assert s.grandprix is None and s.state.gp is None and s.bots == [] and s.race is not None
    assert s._lane.auto and s._lane.home == pytest.approx(1.2)


def test_settings_and_mode_pending_until_gp9_bounds_kept():
    """Avant GP9 (écran du mode) : réglages `grandprix.*` hors du menu et mode non annoncé, rangés avec leur
    lot ; la séance garde les bornes du fichier, et `start` lance le mode (lots GP7 et GP8)."""
    from openride_core import config as config_mod
    from openride_core.ipc_server import CORE_MODES, PENDING_MODES
    gp_keys = {("grandprix", k) for k in ("opponents", "laps", "distance_km", "chaos", "box_every_m")}
    assert not any(st.section == "grandprix" for st in settings.SETTINGS)
    assert all(config_mod.PENDING_KEYS[k] == "GP9" for k in gp_keys)
    assert PENDING_MODES == {"grandprix": "GP9"} and "grandprix" not in CORE_MODES
    assert config_mod.BOUNDS[("grandprix", "opponents")] == (2, 4)
    assert config_mod.CHOICES[("grandprix", "chaos")] == ("soft", "normal", "wild")
    gc = Config().grandprix
    assert (gc.box_every_m, gc.laps, gc.distance_km) == (1500, 3, 10)