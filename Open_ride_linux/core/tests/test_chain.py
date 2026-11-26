"""Enchaînement de parcours en session libre (série PE, lot PE1) : qui peut enchaîner, liste du parcours
suivant, phases de l'enchaînement, ligne de journal et tour du FIT par parcours, parcours d'un instant relu."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from openride_core import chain
from openride_core.chain import ChainContext, ChainSession
from openride_core.fit_export import lap_starts, write_fit
from openride_core.tools import fit_check

T0 = 1_790_000_000.0


@dataclass
class Entry:   # mêmes attributs que catalog.RouteEntry
    id: str
    name: str = ""
    status: str = "ready"
    length_m: float | None = 12_000.0
    route_type: str | None = "open"
    stats: dict | None = None
    library: dict | None = None


CATALOG = [
    Entry("demo", "Col du lacet", stats={"gain_m": 412.4}),
    Entry("erables", "Route des Érables", length_m=25_400.0),
    Entry("pres", "Circuit des Prés", route_type="loop", library={"tags": ["grandprix"]}),
    Entry("velodrome-250", "Vélodrome", route_type="loop", library={"tags": ["velodrome"]}),
    Entry("recif", "Récif des tortues", route_type="loop", library={"tags": ["grandprix", "libre"]}),
    Entry("brouillon", "Trace à compiler", status="to_compile"),
    Entry("volcan", "Volcan en flammes", route_type="loop"),
]


@pytest.mark.parametrize("ctx, code", [
    (ChainContext("ride"), None),
    (ChainContext("ride", enabled=False), "not_free"),
    (ChainContext("race"), "not_free"),
    (ChainContext("grandprix"), "not_free"),
    (ChainContext("survivor"), "not_free"),
    (ChainContext("track"), "not_free"),
    (ChainContext("wtf"), "not_free"),
    (ChainContext("ride", rogue=True), "not_free"),
    (ChainContext("ride", league=True), "not_free"),
    (ChainContext("ride", open_world=True), "open_world"),
    (ChainContext("ride", workout_running=True), "workout"),
    (ChainContext("ride", route_is_loop=True), "loop"),
])
def test_only_free_ride_on_an_open_route_can_chain(ctx, code):
    assert chain.refusal(ctx) == code
    if code is not None:
        assert chain.REFUSALS[code]   # raison écrite pour chaque refus


def test_candidates_ready_free_routes_without_the_current_one():
    ids = [c.id for c in chain.candidates(CATALOG, "demo", ["demo"])]
    assert ids == ["erables", "recif", "volcan"]   # ni le Grand Prix seul, ni la piste, ni une trace à compiler


def test_candidates_put_routes_already_ridden_last():
    offer = chain.candidates(CATALOG, "volcan", ["demo", "volcan"])
    assert [c.id for c in offer] == ["erables", "recif", "demo"]
    assert offer[-1].ridden and not offer[0].ridden
    assert offer[-1].to_dict() == {"id": "demo", "name": "Col du lacet", "length_m": 12000, "ascent_m": 412,
                                   "ridden": True}
    assert chain.candidates(CATALOG, "erables", ["erables"])[1].to_dict()["loop"] is True


def test_full_chain_two_routes_one_journal_line():
    cs = ChainSession.begin("demo", T0)
    assert cs.to_state(can_chain=True) == {"leg": 1, "can_chain": True}
    assert cs.open_choice(CATALOG) is None
    st = cs.to_state(True)
    assert st["phase"] == "choose" and [o["id"] for o in st["offer"]] == ["erables", "recif", "volcan"]
    assert cs.choose("velodrome-250") == "no_route"   # pas dans la liste
    assert cs.choose("erables") is None
    assert cs.to_state(True)["target"] == {"id": "erables", "name": "Route des Érables"}
    assert cs.open_choice(CATALOG) == "busy" and cs.choose("volcan") == "busy"
    line = cs.arrive(T0 + 1800.0, 12_034.5)
    assert line == {"kind": "chain", "event": "route_start", "ts": T0 + 1800.0, "route_id": "erables",
                    "leg": 2, "distance": 12034.5}
    assert cs.current == "erables" and cs.ridden == ["demo", "erables"]
    assert cs.to_state(True) == {"leg": 2, "can_chain": True}


def test_cancel_and_failed_load_go_back_without_ending_the_session():
    cs = ChainSession.begin("demo", T0)
    cs.open_choice(CATALOG)
    cs.cancel()
    assert cs.phase is None and cs.offer == []
    cs.open_choice(CATALOG)
    cs.choose("erables")
    cs.fail()   # parcours illisible : retour à la liste, sans lui
    assert cs.phase == "choose"
    assert [c.id for c in cs.offer] == ["recif", "volcan"]
    for rid in ("recif", "volcan"):
        cs.choose(rid)
        cs.fail()
    assert cs.phase is None   # plus rien à proposer : on roule au calme


def test_no_other_route_and_nothing_to_show_outside_free_ride():
    cs = ChainSession.begin("demo", T0)
    assert cs.open_choice([Entry("demo")]) == "no_route"
    assert cs.to_state(can_chain=False) is None


def test_each_chained_route_is_a_lap_of_the_single_fit(tmp_path):
    cs = ChainSession.begin("demo", T0)
    lines = [{"kind": "session", "event": "start", "ts": T0}]
    for i, rid in enumerate(["erables", "volcan"], start=1):
        cs.open_choice(CATALOG)
        cs.choose(rid)
        lines.append(cs.arrive(T0 + 300.0 * i, 8.0 * 300 * i))
    laps = lap_starts(lines)
    assert laps == [T0 + 300.0, T0 + 600.0]
    records = [{"ts": T0 + i, "distance": 8.0 * (i + 1), "speed": 8.0, "power": 150 + 50 * (i // 300),
                "cadence": 90, "hr": None} for i in range(900)]
    path = tmp_path / "seance.fit"
    write_fit(records, [{"event": "start", "ts": T0}, {"event": "stop", "ts": T0 + 899}], path, laps)
    messages, errors, ok = fit_check.decode(path)
    assert ok and errors == []
    assert [lap["avg_power"] for lap in messages["lap"]] == [150, 200, 250]
    assert messages["session"][0]["num_laps"] == 3


def test_route_of_an_instant_read_back_from_the_journal():
    lines = [{"kind": "chain", "event": "route_start", "ts": T0 + 100, "route_id": "erables"},
             {"kind": "segment", "ts": T0 + 150},
             {"kind": "chain", "event": "route_start", "ts": T0 + 200, "route_id": "volcan"}]
    legs = chain.legs_of(lines, "demo")
    assert legs == [("demo", 0.0), ("erables", T0 + 100), ("volcan", T0 + 200)]
    assert chain.route_at(legs, T0 + 50) == "demo"
    assert chain.route_at(legs, T0 + 100) == "erables"
    assert chain.route_at(legs, T0 + 999) == "volcan"
    assert chain.legs_of([], None) == [] and chain.route_at([], T0) is None
