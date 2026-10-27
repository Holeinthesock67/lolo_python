"""Contrat du monde ouvert (lot W1) : schémas, exemples et tailles des trames."""

from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
import pytest

from openride_core.ipc_server import IpcState

CONTRACTS = Path(__file__).resolve().parents[2] / "docs" / "contracts"
IPC_DIR = CONTRACTS / "ipc"
WORLD_DIR = CONTRACTS / "world"
MAX_DATAGRAM = 1400
MAX_STATE_DATAGRAM = 4096              # limite de `state` depuis la révision 1.3 (§2)
MAX_LIST_DATAGRAM = 60000
LIST_MESSAGES = ("places", "world_map", "world_regions")


def validator(folder: Path, name: str) -> jsonschema.Draft202012Validator:
    schema = json.loads((folder / f"{name}.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def errors(folder: Path, name: str, doc: dict) -> list[str]:
    return [e.message for e in validator(folder, name).iter_errors(doc)]


def size(msg: dict) -> int:
    return len(json.dumps(msg, separators=(",", ":"), ensure_ascii=False).encode())


def open_world(n_branches: int = 4) -> dict:
    return {"rev": 123456, "data": "downloading",
            "next": {"id": "j-1234567890123", "d_m": 287.45, "default": 1, "chosen": 2, "locked": False,
                     "b": [[-135 + 90 * i, "mcpk"[i % 4], -12.3 + i] for i in range(n_branches)]}}


def test_schemas_are_valid() -> None:
    for name in ("state", "cmd", "input", "error", "hello_ack", "world_status", *LIST_MESSAGES):
        validator(IPC_DIR, name)
    for name in ("manifest", "live", "route_part", "junctions"):
        validator(WORLD_DIR, name)


def test_state_without_open_world_still_valid_and_with_it_checked() -> None:
    base = {**IpcState().to_dict(), "seq": 1}
    assert errors(IPC_DIR, "state", base) == []
    assert errors(IPC_DIR, "state", {**base, "open_world": open_world()}) == []
    assert errors(IPC_DIR, "state", {**base, "open_world": {**open_world(), "next": None}}) == []
    assert errors(IPC_DIR, "state", {**base, "session_state": "PAUSED", "pause_reason": "world_data"}) == []
    bad = open_world()
    bad["next"]["b"][0] = [10, "autoroute", 1.0]
    assert errors(IPC_DIR, "state", {**base, "open_world": bad})
    bad = open_world(5)
    assert errors(IPC_DIR, "state", {**base, "open_world": bad})
    assert errors(IPC_DIR, "state", {**base, "open_world": {**open_world(), "data": "perdu"}})


def test_fullest_state_frame_fits_in_datagram() -> None:
    """ERG, 5 bots et un carrefour à 4 branches dans une trame de 1 400 octets au plus.

    `open_world` n'est pas dans la trame qui porte `devices` (une sur 30) : les deux pires cas
    sont contrôlés séparément.
    """
    st = IpcState(route_id="ow:ow-20261026-201500", route_length_m=48000.0, hr=172, mode="ERG",
                  erg={"workout_name": "Seuil 2x20 avec rampes et sprints", "block_index": 12,
                       "block_count": 40, "block_type": "interval_on", "block_remaining_s": 512.25,
                       "block_total_s": 1200.0, "target_w": 238.0, "next_target_w": 125.0,
                       "bias_pct": 102.0, "paused": False})
    devices = {"trainer": {"status": "RECONNECTING", "name": "HomeTrainer 0000 avec un nom long",
                           "address": "C1:1C:00:00:00:03"},
               "click": [{"side": "plus", "status": "CONNECTED", "battery_pct": 100},
                         {"side": "minus", "status": "SEARCHING", "battery_pct": 100}],
               "hr": {"status": "CONNECTED", "source": "trainer", "battery_pct": 100}}
    bots = [{"id": f"bot-{i}", "name": "Fantome 24/10", "s": 12873.456 + i, "v": 9.123, "kind": "ghost"}
            for i in range(5)]
    for extra in ({"open_world": open_world()}, {"devices": devices}):
        frame = {**st.to_dict(), "seq": 123456789, "bots": bots, **extra}
        assert errors(IPC_DIR, "state", frame) == []
        assert size(frame) <= MAX_DATAGRAM, f"trame de {size(frame)} octets ({list(extra)[0]})"
    # Si les deux tombaient ensemble, la trame resterait sous la limite de la révision 1.3.
    both = {**st.to_dict(), "seq": 123456789, "bots": bots, "open_world": open_world(), "devices": devices}
    assert errors(IPC_DIR, "state", both) == []
    assert size(both) <= MAX_STATE_DATAGRAM, f"trame de {size(both)} octets (open_world et devices)"


@pytest.mark.parametrize("name,args", [
    ("start_open_world", {"lat": 44.174, "lon": 5.279, "heading_deg": 90, "nav": "loop",
                          "target": None, "loop_km": 40, "seed": 7}),
    ("choose_branch", {"junction_id": "j123456", "branch": 0}),
    ("world_search", {"query": "Ventoux"}),
    ("world_map", {"lat": 44.174, "lon": 5.279, "radius_m": 8000}),
    ("world_regions", {}),
    ("world_pin", {"region_id": "provence-alpes-cote-d-azur", "pinned": True}),
])
def test_commands(name: str, args: dict) -> None:
    assert errors(IPC_DIR, "cmd", {"type": "cmd", "v": 1, "cmd_id": 9, "name": name, "args": args}) == []


def test_events_errors_hello_ack() -> None:
    for ev in ("LEFT_SHORT", "RIGHT_SHORT", "A_SHORT", "PLUS_SHORT"):
        assert errors(IPC_DIR, "input", {"type": "input", "v": 1, "event": ev}) == []
    for code in ("branch_locked", "unknown_junction", "world_unavailable"):
        assert errors(IPC_DIR, "error", {"type": "error", "v": 1, "code": code, "message": "x"}) == []
    ack = {"type": "hello_ack", "v": 1, "core_version": "0.1.0",
           "config": {"ftp_w": 250, "gears_total": 24, "theme": "default", "difficulty_pct": 50}}
    assert errors(IPC_DIR, "hello_ack", ack) == []
    ack["config"]["open_world_dir"] = "/home/utilisateur/OpenRide/Cache/monde/seances"
    assert errors(IPC_DIR, "hello_ack", ack) == []


def test_world_status_and_lists() -> None:
    status = {"type": "world_status", "v": 1, "phase": "tiles", "done_bytes": 1_200_000,
              "total_bytes": None, "squares_ready": 3, "squares_needed": 24, "message": "tuiles vectorielles"}
    assert errors(IPC_DIR, "world_status", status) == [] and size(status) <= MAX_DATAGRAM
    place = {"name": "Mont Ventoux (sommet du col des Tempêtes)", "kind": "pass", "lat": 44.174,
             "lon": 5.279, "cached": False, "source": "embedded"}
    places = {"type": "places", "v": 1, "request_cmd_id": 3, "part": 1, "parts": 1, "truncated": True,
              "items": [place] * 50}
    assert errors(IPC_DIR, "places", places) == [] and size(places) <= MAX_LIST_DATAGRAM
    # Carte : 100 routes de 40 points en mètres entiers tiennent dans une partie.
    road = {"c": "m", "xz": [-7999, 7999] * 40}
    wmap = {"type": "world_map", "v": 1, "request_cmd_id": 4, "part": 1, "parts": 2, "lat": 44.174,
            "lon": 5.279, "radius_m": 8000, "truncated": False, "roads": [road] * 100}
    assert errors(IPC_DIR, "world_map", wmap) == [] and size(wmap) <= MAX_LIST_DATAGRAM
    region = {"id": "provence-alpes-cote-d-azur", "name": "Provence-Alpes-Côte d'Azur", "bytes": 312_000_000,
              "pinned": True, "last_used": "2026-10-26T20:15:00", "bbox": [4.2, 42.9, 7.7, 45.2]}
    regions = {"type": "world_regions", "v": 1, "request_cmd_id": 5, "part": 1, "parts": 1,
               "cache_bytes": 4_100_000_000, "cache_max_bytes": 5_000_000_000, "items": [region] * 200}
    assert errors(IPC_DIR, "world_regions", regions) == [] and size(regions) <= MAX_LIST_DATAGRAM


def world_examples() -> list[dict]:
    text = (CONTRACTS / "world_format_v1.md").read_text(encoding="utf-8")
    section = text[text.index("## 13. Monde vivant"):]
    return [json.loads(b) for b in re.findall(r"```json\n(.*?)\n```", section, re.S)]


def test_live_world_examples() -> None:
    live, junctions = world_examples()
    assert errors(WORLD_DIR, "live", live) == []
    assert errors(WORLD_DIR, "junctions", junctions) == []


def test_live_manifest_and_route_part() -> None:
    manifest = {"format": "openride-world", "format_version": "1.2", "name": "ow-20261026-201500",
                "live": True, "origin_kind": "utm_grid",
                "origin": {"lat": 44.15, "lon": 5.25, "alt_m": 410.0, "utm_zone": "31T"},
                "grid": {"near_m": 1000, "far_m": 5000, "e0": 675000, "n0": 4890000},
                "projection": "utm",
                "route": {"present": True, "version": "1.0", "file": "route/", "length_m": 3410.0,
                          "ds_m": 10, "n": 342, "type": "open"}}
    assert errors(WORLD_DIR, "manifest", manifest) == []
    assert errors(WORLD_DIR, "manifest", {**manifest, "grid": {**manifest["grid"], "e0": 675500}})
    n = 101
    part = {"version": "1.0", "ds_m": 10, "n": n, "length_m": 1000.0, "type": "open", "s0_m": 2000.0,
            **{k: [0.0] * n for k in ("lat", "lon", "alt_m", "x", "z", "grade_pct", "heading_deg")}}
    assert errors(WORLD_DIR, "route_part", part) == []
    assert errors(WORLD_DIR, "route_part", {**part, "s0_m": 2500.0})
    assert errors(WORLD_DIR, "route_part", {k: v for k, v in part.items() if k != "s0_m"})


def test_junctions_with_four_full_previews_stay_small() -> None:
    preview = {k: [12345.67 + i for i in range(51)] for k in ("x", "y", "z")}
    branch = {"index": 0, "heading_deg": 275.0, "angle_deg": -85.0, "road_class": "m",
              "grade_pct_500m": 6.2, "dead_end": False, "preview": preview}
    junction = {"id": "j123456", "s_m": 2410.0, "x": 1520.4, "z": -830.2, "lock_s_m": 2380.0,
                "default": 1, "chosen": 1, "locked": False,
                "branches": [{**branch, "index": i} for i in range(4)]}
    doc = {"version": "1.0", "revision": 3, "junctions": [junction]}
    assert errors(WORLD_DIR, "junctions", doc) == []
    assert size(doc) < 20_000
    too_long = {**branch, "preview": {k: [0.0] * 52 for k in ("x", "y", "z")}}
    assert errors(WORLD_DIR, "junctions", {**doc, "junctions": [{**junction, "branches": [too_long]}]})


def test_worldgen_contract_example_lines_are_json() -> None:
    text = (CONTRACTS / "worldgen_v1.md").read_text(encoding="utf-8")
    block = text[text.index("## 7. Exemple"):]
    lines = [ln.split("→", 1)[1].strip() for ln in block.splitlines() if "→" in ln]
    msgs = [json.loads(ln) for ln in lines]
    assert [m["type"] for m in msgs][:2] == ["open", "status"]
    assert {m["type"] for m in msgs} == {"open", "status", "revision", "progress", "choose", "close", "closed"}
