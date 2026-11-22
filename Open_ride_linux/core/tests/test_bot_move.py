"""Lot BA1 : geste des bots (`move` des éléments de `bots`, révision 1.33) montré au cycliste.

Essai du propriétaire du 22 novembre en mode Course : « rien n'indique quand un bot utilise un boost »."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from openride_core.bots import FULL_FRAME_BOTS, ProfileBot, light_frame

SCHEMA = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc" / "state.schema.json"


def test_move_follows_the_tactics_and_the_sprint_peak():
    b = ProfileBot("climber")
    assert b.move() is None and "move" not in b.to_dict()
    b.tactics.attack_until = b.t + 5.0
    assert b.move() == "attack" and b.to_dict()["move"] == "attack"
    b.tactics.attack_until = -1.0
    b.tactics.respond_to, b.tactics.respond_until = "me", b.t + 3.0
    assert b.to_dict()["move"] == "respond"
    b.tactics.respond_until = b.t - 1.0
    assert b.move() is None   # réponse finie
    b.tactics.respond_to = None
    b.peak_w = 900.0
    b.power_w = 900.0
    assert b.to_dict()["move"] == "sprint"
    b.power_w = 300.0
    assert "move" not in b.to_dict()


def test_move_kept_for_the_neighbours_only_and_valid_in_the_schema():
    bots = []
    for i in range(8):
        d = ProfileBot("rouleur", name=f"Rouleur {i + 1}").to_dict()
        d["id"], d["s"], d["move"] = f"b{i}", 100.0 * i, "attack"
        bots.append(d)
    out = light_frame(bots, 0.0)
    near = sorted(out, key=lambda b: b["s"])[:FULL_FRAME_BOTS]
    assert all(b.get("move") == "attack" for b in near)
    assert not any("move" in b for b in out if b not in near)
    items = json.loads(SCHEMA.read_text(encoding="utf-8"))["properties"]["bots"]["items"]
    for b in out:
        jsonschema.validate(b, items)
