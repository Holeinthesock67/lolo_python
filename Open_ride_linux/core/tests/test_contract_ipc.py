"""Tests de contrat IPC (SRS §12, contrat §8) : chaque trame émise par le core valide son schéma."""

import asyncio
import json
import re
from pathlib import Path

import jsonschema

from openride_core import fit_export
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.ipc_budget import encode
from openride_core.ipc_server import LIST_MESSAGE_TYPES, IpcServer, IpcState
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession

CONTRACTS = Path(__file__).resolve().parents[2] / "docs" / "contracts"
IPC_DIR = CONTRACTS / "ipc"
MAX_DATAGRAM = 1400         # marge interne des trames `state` du core (place des ajouts de la 2.0)
MAX_STATE_DATAGRAM = 4096  # state depuis la révision 1.3, tout message hors parties depuis la 1.5 (§2)
MAX_LIST_DATAGRAM = 60000   # messages en parties et `plans` (§2, ipc_server.LIST_MESSAGE_TYPES)


def schema(name: str) -> dict:
    return json.loads((IPC_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def assert_valid(msg: dict) -> None:
    errors = [e.message for e in jsonschema.Draft202012Validator(schema(msg["type"])).iter_errors(msg)]
    assert not errors, f"{msg['type']} invalide : {errors}"
    # Limite unique du contrat (révision 1.5, §2) : 4 096 octets hors listes. Les trames `state`, envoyées
    # à 30 Hz, restent sous 1 400 octets : les tests le vérifient pour garder la place des ajouts de la 2.0.
    if msg["type"] in LIST_MESSAGE_TYPES:
        limit = MAX_LIST_DATAGRAM
    elif msg["type"] == "state":
        limit = MAX_DATAGRAM
    else:
        limit = MAX_STATE_DATAGRAM
    assert len(encode(msg)) <= limit


class Capture:
    """Remplace IpcServer.send_raw pour garder les trames émises."""

    def __init__(self, server: IpcServer) -> None:
        self.frames: list[dict] = []
        server.send_raw = self.frames.append   # type: ignore[method-assign]

    def of(self, typ: str) -> list[dict]:
        return [f for f in self.frames if f["type"] == typ]


def make_session(tmp_path, monkeypatch, driver=None, port=5900):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    s = CoreSession(cfg, driver=driver or MockDriver(), inputs=[NullProvider()],
                    journal_dir=tmp_path / "journal",
                       routes_root=tmp_path / "routes")
    return s, Capture(s.server)


def run_steps(s, n, t0=100.0):
    for i in range(n):
        s._step(0.02, t0 + i * 0.02)


def test_all_message_schemas_exist():
    for name in ("state", "cmd", "hello", "hello_ack", "heartbeat", "input", "error", "shutdown", "bye",
                 "routes", "workouts", "scan_results", "settings", "imports", "workout_saved",
                 "segment_result", "room", "loot", "garage", "progression", "xp_result", "plans"):
        jsonschema.Draft202012Validator.check_schema(schema(name))


def test_state_frames_in_every_session_state(tmp_path, monkeypatch):
    async def scenario():
        s, cap = make_session(tmp_path, monkeypatch)
        seen = []

        def snap():
            s.server.send_state(s.state)
            seen.append((s.state.session_state, s.state.pause_reason))

        snap()                                                   # IDLE
        s._on_command("select_route", {"route_id": "demo"}, 1); snap()       # READY
        s._on_command("start", {}, 2); run_steps(s, 120); snap()             # RUNNING
        for reason in ("user", "engine_lost", "trainer_lost", "recording_failed"):
            s._set_state("PAUSED", reason); snap()
        s._set_state("RUNNING"); run_steps(s, 60, 200.0)
        s._on_command("end_session", {"save": True}, 3); snap()             # FINISHED avec FIT
        assert s.state.summary["fit_path"]
        s._on_command("select_route", {"route_id": "demo"}, 4)
        s._on_command("start", {}, 5); run_steps(s, 60, 300.0)
        s._on_command("end_session", {"save": False}, 6); snap()            # FINISHED sans FIT
        assert s.state.summary["fit_path"] is None
        s._set_state("ERROR"); snap()
        for frame in cap.of("state"):
            assert_valid(frame)
        assert {st for st, _ in seen} >= {"IDLE", "READY", "RUNNING", "PAUSED", "FINISHED", "ERROR"}
    asyncio.run(scenario())


def test_hello_ack_input_error_shutdown(tmp_path, monkeypatch):
    async def scenario():
        s, cap = make_session(tmp_path, monkeypatch, port=5910)
        s.server._handle_message({"type": "hello", "v": 1, "engine_version": "test"})
        s._handle_input(__import__("openride_core.zwift_click", fromlist=["InputEvent"]).InputEvent.PLUS_LONG)
        s.server.send_error("route_not_found", "absent")
        s.server.send_shutdown()
        s.server._handle_message({"type": "hello", "v": 2, "engine_version": "futur"})   # version_mismatch
        for typ in ("hello_ack", "input", "error", "shutdown"):
            assert cap.of(typ), f"aucune trame {typ}"
        for frame in cap.frames:
            assert_valid(frame)
    asyncio.run(scenario())


def contract_json_blocks() -> list[dict]:
    text = (CONTRACTS / "ipc_v1.md").read_text(encoding="utf-8")
    return [json.loads(b) for b in re.findall(r"```json\n(.*?)\n```", text, re.S)]


def test_contract_examples_are_valid():
    state, erg, cmd, devices, routes, workouts = contract_json_blocks()[:6]
    assert_valid(state)
    assert_valid({**state, "mode": "ERG", "erg": erg})
    assert_valid(cmd)
    assert_valid({**state, "devices": devices})
    assert_valid(routes)
    assert_valid(workouts)
    assert_valid({"type": "cmd", "v": 1, "cmd_id": 3, "name": "list_routes", "args": {}})


def test_v1_1_additions_are_optional_and_checked():
    """Révision 1.1 : une trame v1 reste valide ; les nouvelles valeurs sont contrôlées."""
    state, _erg, _cmd, devices, routes, workouts = contract_json_blocks()[:6]
    assert "devices" not in state and "bots" not in state
    assert_valid({**state, "session_state": "PAUSED", "pause_reason": "core_restarted"})
    validator = jsonschema.Draft202012Validator(schema("state"))
    bad_devices = {**devices, "click": [{"side": "left", "status": "CONNECTED", "battery_pct": 80}]}
    assert list(validator.iter_errors({**state, "devices": bad_devices}))
    bad_bots = [{"id": "b1", "name": "Bot", "s": 1.0, "v": 2.0, "kind": "robot"}]
    assert list(validator.iter_errors({**state, "bots": bad_bots}))
    summary = {"duration_s": 3600.0, "distance_m": 30000.0, "avg_power_w": 200.0, "fit_path": None,
               "np_w": None, "intensity_factor": None, "tss": None, "blocks": [[1, 150.0, None]]}
    assert_valid({**state, "session_state": "FINISHED", "summary": summary})
    routes_validator = jsonschema.Draft202012Validator(schema("routes"))
    bad_route = {**routes["items"][0], "status": "compiled"}
    assert list(routes_validator.iter_errors({**routes, "items": [bad_route]}))
    workouts_validator = jsonschema.Draft202012Validator(schema("workouts"))
    bad_profile = {**workouts["items"][0], "profile": [[600, 0.5]]}
    assert list(workouts_validator.iter_errors({**workouts, "items": [bad_profile]}))


def test_worst_case_lists_fit_in_list_datagrams():
    """200 parcours tiennent en une partie ; 200 entraînements de 30 blocs en 4 parties."""
    route = {"id": "x" * 60, "name": "Parcours au nom assez long " * 2, "status": "outdated",
             "length_m": 123456.7, "route_type": "out_and_back", "has_terrain": True,
             "error": None}
    routes = {"type": "routes", "v": 1, "request_cmd_id": 1, "part": 1, "parts": 1,
              "truncated": True, "items": [route] * 200}
    assert_valid(routes)
    workout = {"id": "w" * 40, "name": "Entraînement au nom long", "duration_s": 5400.0,
               "block_count": 60, "selectable": True, "error": None,
               "profile": [[300.0, 0.55, 1.25]] * 30, "profile_truncated": True}
    per_part = 50
    for start in range(0, 200, per_part):
        assert_valid({"type": "workouts", "v": 1, "request_cmd_id": 1, "part": start // per_part + 1,
                      "parts": 4, "truncated": False, "items": [workout] * per_part})


def test_full_state_frame_fits_in_datagram():
    st = IpcState(route_id="col-du-galibier-par-le-lautaret-version-longue", route_length_m=48000.0,
                  hr=172, mode="ERG", summary=None,
                  erg={"workout_name": "Seuil 2x20 avec rampes et sprints", "block_index": 12,
                       "block_count": 40, "block_type": "interval_on", "block_remaining_s": 512.25,
                       "block_total_s": 1200.0, "target_w": 238.0, "next_target_w": 125.0,
                       "bias_pct": 102.0, "paused": False})
    devices = {"trainer": {"status": "RECONNECTING", "name": "HomeTrainer 0000 avec un nom long",
                           "address": "C1:1C:00:00:00:03"},
               "click": [{"side": "plus", "status": "CONNECTED", "battery_pct": 100},
                         {"side": "minus", "status": "SEARCHING", "battery_pct": 100}],
               "hr": {"status": "CONNECTED", "source": "trainer", "battery_pct": 100}}
    frame = {**st.to_dict(), "seq": 123456789, "devices": devices,
             "bots": [{"id": f"bot-{i}", "name": "Fantôme du 24/10", "s": 12873.456 + i,
                       "v": 9.123, "kind": "ghost"} for i in range(5)]}
    assert_valid(frame)
    size = len(encode(frame))
    assert size <= MAX_DATAGRAM, f"trame de {size} octets"


def test_state_floats_rounded_and_realistic_frame_fits():
    """Décision D1 de l'audit IPC du 26 octobre : flottants arrondis, trame réaliste sous 1 400 octets.

    Valeurs en pleine précision, comme celles que la physique et la route donnent au core, et vrai nom
    du fantôme (accentué). Sans `devices` (29 trames sur 30), la trame ERG avec 5 bots doit tenir.
    """
    st = IpcState(route_id="col-du-galibier-par-le-lautaret-version-longue", route_length_m=48000.123456789,
                  hr=172, mode="ERG", seq=123456789, t=3599.123456789012, s=28450.123456789012,
                  v=11.123456789012345, grade=7.812345678901234, grade_sent=4.123456789,
                  power=248.12345678901, power_3s=245.3456789, cadence=79.12345678901234,
                  lat=45.07312345678901, lon=6.402712345678901, alt=1834.2123456789012,
                  erg={"workout_name": "Seuil 2x20 avec rampes et sprints", "block_index": 12,
                       "block_count": 40, "block_type": "interval_on", "block_remaining_s": 512.25,
                       "block_total_s": 1200.0, "target_w": 238.0, "next_target_w": 125.0,
                       "bias_pct": 102.0, "paused": False},
                  bots=[{"id": f"bot-{i}", "name": "Fantôme du 24/10", "s": 12873.46 + i, "v": 9.123,
                         "kind": "ghost"} for i in range(5)])
    frame = st.to_dict()
    assert (frame["t"], frame["s"], frame["v"], frame["lat"], frame["lon"]) == (
        3599.12, 28450.12, 11.123, 45.073123, 6.402712)
    assert frame["power"] == 248.1 and frame["cadence"] == 79.1 and frame["alt"] == 1834.21
    assert frame["route_length_m"] == 48000.1 and frame["grade"] == 7.81
    assert_valid(frame)
    size = len(json.dumps(frame, separators=(",", ":")).encode())
    assert size <= MAX_DATAGRAM, f"trame de {size} octets"
    # Les champs absents ou nuls ne sont pas touchés.
    idle = IpcState(route_length_m=None).to_dict()
    assert idle["route_length_m"] is None and idle["t"] == 0.0


def test_full_summary_frame_fits_in_datagram():
    st = IpcState(route_id="col-du-galibier-par-le-lautaret-version-longue", route_length_m=48000.0,
                  session_state="FINISHED", mode="ERG",
                  summary={"duration_s": 5400.25, "distance_m": 45123.4, "avg_power_w": 212.3,
                           "fit_path": "/home/utilisateur/OpenRide/Activities/2026-10-24-213000-openride.fit",
                           "np_w": 231.4, "intensity_factor": 0.874, "tss": 114.6,
                           "elevation_gain_m": 1834.2, "avg_cadence_rpm": 87.3, "avg_hr_bpm": 148.2,
                           "max_power_w": 612.0,
                           "blocks": [[i, 238.4, 240.0] for i in range(1, 25)], "blocks_truncated": True})
    frame = {**st.to_dict(), "seq": 123456789}
    assert_valid(frame)


ERG_ZWO = """<workout_file><name>Contrat ERG</name><workout>
<Warmup Duration="60" PowerLow="0.5" PowerHigh="0.75"/>
<IntervalsT Repeat="2" OnDuration="20" OffDuration="20" OnPower="1.2" OffPower="0.5"/>
<FreeRide Duration="30"/>
<Cooldown Duration="30" PowerLow="0.7" PowerHigh="0.4"/>
</workout></workout_file>"""


def test_state_frames_in_erg(tmp_path, monkeypatch):
    """Lot F : trames state en ERG (blocs, pause ERG, roue libre, fin) et erreur workout_invalid."""
    async def scenario():
        workouts = tmp_path / "Workouts"
        workouts.mkdir()
        (workouts / "erg.zwo").write_text(ERG_ZWO, encoding="utf-8")
        (workouts / "casse.zwo").write_text("<workout_file><workout>", encoding="utf-8")
        s, cap = make_session(tmp_path, monkeypatch, port=5920)
        s.workouts_dir = workouts
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("select_workout", {"workout_id": "casse"}, 2)
        assert cap.of("error")[-1]["code"] == "workout_invalid"
        s._on_command("select_workout", {"workout_id": "erg"}, 3)
        s._on_command("start", {}, 4)
        types = set()
        for step in range(230):                     # 200 s de blocs + 5 s de pause
            run_steps(s, 50, 100.0 + step)          # 1 s par tour
            if step == 10:
                s._on_command("input_event", {"event": "Y_SHORT"}, 5)   # pause de la séance (Y) puis reprise
            if step == 15:
                s._on_command("resume", {}, 6)
            s.server.send_state(s.state)
            if s.state.erg:
                types.add(s.state.erg["block_type"])
        erg_frames = [f for f in cap.of("state") if f["erg"] is not None]
        assert {"warmup", "interval_on", "interval_off", "freeride", "cooldown"} <= types
        assert any(f["erg"]["paused"] for f in erg_frames)
        assert any(f["mode"] == "ERG" for f in erg_frames)
        assert any(f["erg"]["next_target_w"] is None for f in erg_frames)
        assert cap.of("state")[-1]["erg"] is None and cap.of("state")[-1]["mode"] == "SIM"
        for frame in cap.frames:
            assert_valid(frame)
    asyncio.run(scenario())


def test_v1_3_wind_and_draft_are_optional_and_fit():
    """Révision 1.3 (lot P1) : `wind`, `draft` et `draft_bot` facultatifs, trame la plus chargée sous 1 400 octets."""
    state, erg, _cmd, devices, _routes, _workouts = contract_json_blocks()[:6]
    assert "wind" not in state and "draft" not in state
    assert_valid(state)
    # Arrondis du contrat : vitesses au centième, direction au dixième, rafale au centième, aspiration au millième
    wind = {"speed_mps": 16.67, "from_deg": 247.1, "head_mps": -12.35, "gust": 0.99}
    assert_valid({**state, "wind": wind, "draft": 0.312, "draft_bot": "b1"})
    bots = [{"id": f"bot{i}xyz", "name": "N" * 16, "s": 123456.79, "v": 16.123, "kind": "constant"}
            for i in range(4)]
    bots.append({"id": "ghost", "name": "G" * 16, "s": 123456.79, "v": 16.123, "kind": "ghost"})
    # `wind` n'est jamais dans la trame qui porte `devices` : les deux trames les plus chargées
    assert_valid({**state, "mode": "ERG", "erg": erg, "devices": devices, "bots": bots,
                  "draft": 0.45, "draft_bot": "bot0xyz"})
    assert_valid({**state, "mode": "ERG", "erg": erg, "bots": bots,
                  "wind": wind, "draft": 0.45, "draft_bot": "bot0xyz"})
    validator = jsonschema.Draft202012Validator(schema("state"))
    assert list(validator.iter_errors({**state, "draft": 0.5}))
    assert list(validator.iter_errors({**state, "wind": {**wind, "gust": 1.5}}))
    assert list(validator.iter_errors({**state, "wind": {"speed_mps": 3.0}}))


def test_v1_3_state_limit_rev_and_modes(tmp_path, monkeypatch):
    """Révision 1.3 (audit IPC, D1 et D3) : state jusqu'à 4 096 octets, `rev` et `modes` facultatifs ;
    révision 1.5 : la même limite pour tout message hors messages en parties."""
    from openride_core import ipc_server
    assert ipc_server.MAX_DATAGRAM_SIZE == MAX_STATE_DATAGRAM
    assert ipc_server.CONTRACT_REV == "1.5"   # révision 1.5 annoncée depuis le monde ouvert (lots W10 à W12)

    class Sock:
        def __init__(self):
            self.sent = []

        def sendto(self, payload, addr):
            self.sent.append(payload)

    srv = ipc_server.IpcServer()
    srv._tx_sock = Sock()
    big_state = {"type": "state", "pad": "x" * 2500}
    srv.send_raw(big_state)                                  # 2,5 ko : passe depuis la 1.3
    srv.send_raw({"type": "state", "pad": "x" * 4200})       # au-delà de 4 096 octets : jetée
    srv.send_raw({"type": "error", "pad": "x" * 2500})       # même limite pour tout message depuis la 1.5
    srv.send_raw({"type": "error", "pad": "x" * 4200})       # au-delà : jeté
    assert len(srv._tx_sock.sent) == 2 and all(b'"pad"' in p for p in srv._tx_sock.sent)

    async def scenario():
        s, cap = make_session(tmp_path, monkeypatch, port=5930)
        s.server._handle_message({"type": "hello", "v": 1, "rev": "1.3", "engine_version": "test"})
        s.server._handle_message({"type": "hello", "v": 1, "engine_version": "ancien"})   # sans rev : accepté
        acks = cap.of("hello_ack")
        assert len(acks) == 2
        for ack in acks:
            assert_valid(ack)
            assert ack["rev"] == "1.5" and ack["config"]["modes"] == ["ride", "erg", "open_world", "rogue"]
        assert s.server.engine_rev is None
    asyncio.run(scenario())
    hello = jsonschema.Draft202012Validator(schema("hello"))
    assert not list(hello.iter_errors({"type": "hello", "v": 1, "engine_version": "x"}))
    assert not list(hello.iter_errors({"type": "hello", "v": 1, "rev": "1.3", "engine_version": "x"}))
    assert list(hello.iter_errors({"type": "hello", "v": 1, "rev": 1.3, "engine_version": "x"}))


def assert_valid_1_4_state(msg: dict) -> None:
    """Trame state de la révision 1.4 : schéma et limite de 4 096 octets (§2)."""
    errors = [e.message for e in jsonschema.Draft202012Validator(schema("state")).iter_errors(msg)]
    assert not errors, f"state invalide : {errors}"
    assert len(encode(msg)) <= MAX_STATE_DATAGRAM


def test_v1_4_contract_examples_are_valid():
    """Révision 1.4 (lot T1) : exemples du §7 pour les séries R, T et V."""
    blocks = contract_json_blocks()
    state, erg, _cmd, devices = blocks[:4]
    t_extras, rogue, segment_result, loot, xp_result, hello_ack = blocks[6:]
    # Trame 1.0 inchangée, toujours valide
    assert_valid(state)
    # Trame classique : segment, bonus, maillots et 5 bots à profil
    bot = t_extras["bots"][0]
    bots = [{**bot, "id": f"b{i}", "profile": p} for i, p in
            enumerate(("climber", "rouleur", "sprinter", "diesel", None))]
    assert_valid_1_4_state({**state, **t_extras, "bots": bots, "devices": devices})
    assert_valid_1_4_state({**state, **t_extras, "mode": "ERG", "erg": erg})
    # Mode ROGUE : position géographique nulle et objet rogue
    assert_valid_1_4_state({**state, "mode": "ROGUE", "route_id": None, "lat": None, "lon": None,
                            "alt": None, "gear": 7, "gears_total": 12, "rogue": rogue})
    for msg in (segment_result, loot, xp_result, hello_ack):
        assert_valid(msg)
    # hello_ack sans les objets des séries R et V
    cfg = {k: v for k, v in hello_ack["config"].items() if k not in ("rogue", "progression")}
    assert_valid({**hello_ack, "config": {**cfg, "modes": ["ride", "erg"]}})
    progression = {"type": "progression", "v": 1, "request_cmd_id": 12,
                   **hello_ack["config"]["progression"]}
    assert_valid(progression)
    room = {"type": "room", "v": 1, "room_id": 7, "part": 1, "parts": 1, "archetype": "puncheur",
            "variant": "b", "length_m": 1500.0, "nominal_s": 180.0,
            "profile": [[s * 10.0, 3.5] for s in range(151)],
            "markers": [{"kind": "strike_target", "s_m": 900.0, "len_m": 60.0, "param": None}],
            "next": {"room_id": 8, "archetype": "grimpeur"}}
    assert_valid(room)
    garage = {"type": "garage", "v": 1, "request_cmd_id": 13, "part": 1, "parts": 1, "items": [
        {"id": "wheels-carbon-40", "slot": "wheels", "name": "Roues carbone 40", "state": "equipped",
         "level_required": 6, "price": 180, "challenge": None, "mass_delta_kg": -0.4,
         "cda_delta_pct": -1.5, "terrain": "rolling", "look": "wheels_carbon_40"}]}
    assert_valid(garage)
    for name, args in (("start_run", {"objective": "threshold", "duration_min": 45, "seed": None,
                                      "w_prime_j": None, "chassis": "blinde"}),
                       ("rogue_resync", {}), ("list_garage", {}),
                       ("equip", {"slot": "wheels", "item_id": "wheels-carbon-40"}),
                       ("buy", {"item_id": "helmet-aero"}),
                       ("set_avatar", {"avatar": hello_ack["config"]["progression"]["avatar"]})):
        assert_valid({"type": "cmd", "v": 1, "cmd_id": 20, "name": name, "args": args})


def test_v1_4_values_are_checked():
    """Révision 1.4 : les nouvelles valeurs hors liste sont refusées."""
    blocks = contract_json_blocks()
    state = blocks[0]
    t_extras, rogue, segment_result = blocks[6:9]
    validator = jsonschema.Draft202012Validator(schema("state"))
    assert list(validator.iter_errors({**state, **t_extras, "powerup": {"held": "turbo", "active": None,
                                                                          "remaining_s": 0.0}}))
    assert list(validator.iter_errors({**state, "rogue": {**rogue, "posture": "SPRINT"}}))
    assert list(validator.iter_errors({**state, "mode": "OPEN_WORLD"}))
    bad = {**t_extras["bots"][0], "profile": "puncheur"}
    assert list(validator.iter_errors({**state, "bots": [bad]}))
    assert list(jsonschema.Draft202012Validator(schema("segment_result")).iter_errors(
        {**segment_result, "kind": "descent"}))


def test_world_segments_layer_example_is_valid():
    """Format .world 1.3 : l'exemple de couche segments.json valide son schéma (§8 bis)."""
    text = (CONTRACTS / "world_format_v1.md").read_text(encoding="utf-8")
    i = text.index("## 8 bis.")
    layer = json.loads(re.search(r"```json\n(.*?)\n```", text[i:], re.S).group(1))
    seg_schema = json.loads((CONTRACTS / "world" / "segments.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(seg_schema)
    errors = [e.message for e in jsonschema.Draft202012Validator(seg_schema).iter_errors(layer)]
    assert not errors, errors
    from openride_core.segments import Segment
    seg = Segment(**{k: v for k, v in layer["segments"][1].items()})
    assert seg.to_dict() == layer["segments"][1]
