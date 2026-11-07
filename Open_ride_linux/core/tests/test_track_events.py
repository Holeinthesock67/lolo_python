"""Lot VD6 : épreuves de piste (paquet `track/` du core), courses simulées de bout en bout.

Chaque épreuve : cas positifs et négatifs, même graine même résultat, aucune pente renvoyée, trame
`track` sous le budget de l'IPC.
"""

from __future__ import annotations

import json
import random
from typing import Callable

import pytest

from openride_core import ipc_budget
from openride_core import track as T
from openride_core.track import ME, Entrant, TrackError
from openride_core.track.base import lines_crossed, place_points
from openride_core.track.keirin import PACER_END_KMH, PACER_START_KMH
from openride_core.track.madison import RELAY_M
from openride_core.track.points import SPRINT_POINTS

LAP = 250.0
DT = 0.25


def entrants(n_bots: int) -> list[Entrant]:
    return [Entrant(ME, "Toi")] + [Entrant(f"b{i}", f"Bot {i}", level=50.0 + i) for i in range(n_bots)]


def build(eid: str, settings: dict | None = None, seed: int = 0) -> T.TrackEvent:
    s = T.check(eid, settings or {})
    return T.make(eid, entrants(T.field_size(eid, s)), s, seed=seed, clock=lambda: 0.0)


def grid(ev: T.TrackEvent) -> dict[str, float]:
    """Grille derrière la ligne (courses en peloton) : 1,5 m entre deux coureurs."""
    return {rid: -1.5 * i for i, rid in enumerate(ev.riders)}


def sides(ev: T.TrackEvent) -> dict[str, float]:
    """Poursuites : l'équipe du cycliste sur la ligne, l'autre un demi-tour plus loin."""
    mine = ev.riders[ME].team or ME
    return {rid: 0.0 if (r.team or rid) == mine else LAP / 2 for rid, r in ev.riders.items()}


Speed = Callable[[str, float, float], float]   # (coureur, instant, distance) → vitesse


def run(ev: T.TrackEvent, speed: Speed | dict[str, float], start: dict[str, float] | None = None,
        dt: float = DT, until: float = 20_000.0, seed: int = 1) -> list[dict]:
    """Fait rouler chaque coureur à la vitesse donnée (bruit de ±2 % tiré de la graine) jusqu'à la fin."""
    rng = random.Random(seed)
    fn = speed if callable(speed) else (lambda rid, t, s: speed.get(rid, 13.0))
    pos = {rid: (x, 0.0) for rid, x in (start if start is not None else grid(ev)).items()}
    ev.start(0.0, pos)
    t, msgs = 0.0, []
    while not ev.finished and t < until:
        t += dt
        for rid, (x, _) in pos.items():
            v = max(fn(rid, t, x), 0.0) * (1.0 + 0.02 * rng.uniform(-1.0, 1.0))
            pos[rid] = (x + v * dt, v)
        msgs += ev.step(t, pos)
    return msgs


def kinds(msgs: list[dict], kind: str) -> list[dict]:
    return [m for m in msgs if m["event"] == kind]


def bunch(base: float = 12.5, spread: float = 0.15) -> dict[str, float]:
    """Vitesses d'un peloton : le cycliste un peu plus vite que tous, les bots rangés par niveau."""
    out = {ME: base + spread * 12}
    for i in range(11):
        out[f"b{i}"] = base + spread * i
    return out


# --- registre et réglages ------------------------------------------------------------------------

def test_registry_covers_every_event_of_the_plan():
    assert set(T.EVENTS) == {"free", "pursuit", "kilo", "500", "flying_200", "hour", "scratch", "points", "tempo",
                             "elimination", "keirin", "omnium", "team_sprint", "team_pursuit", "madison"}
    assert [e for e, s in T.EVENTS.items() if s.erg] == ["free"]   # épreuves en SIM, séance libre aussi en ERG


def test_options_defaults_and_refusals():
    assert T.check("scratch", {}) == {"opponents": 7, "laps": 20, "bot_tactics": "full"}
    assert T.check("pursuit", {"opponents": 0, "distance_m": 3000}) == {"opponents": 0, "distance_m": 3000,
                                                                       "bot_tactics": "full"}
    assert T.check("kilo", {}) == {"opponents": 0}   # seul contre le chrono : pas de réglage de tactique (VD7)
    assert T.check("scratch", {"bot_tactics": "simple"})["bot_tactics"] == "simple"
    assert T.field_size("team_pursuit", {"opponents": 1}) == 7       # 3 coéquipiers + 4 adversaires
    assert T.field_size("madison", {"opponents": 3}) == 7            # 1 coéquipier + 3 équipes de 2
    with pytest.raises(TrackError):
        T.check("nope", {})
    with pytest.raises(TrackError):
        T.check("scratch", {"laps": 7})
    with pytest.raises(TrackError):
        T.check("scratch", {"opponents": 2})
    with pytest.raises(TrackError):
        T.check("keirin", {"opponents": 7})
    with pytest.raises(TrackError):
        T.check("scratch", {"laps": True})
    with pytest.raises(TrackError):
        T.check("kilo", {"vent": 3})
    with pytest.raises(TrackError):
        T.check("scratch", {"bot_tactics": "rusée"})
    with pytest.raises(TrackError):
        T.check("kilo", {"bot_tactics": "full"})
    with pytest.raises(TrackError):
        T.make("scratch", entrants(3), {"opponents": 7})


def test_field_refusals():
    with pytest.raises(TrackError):
        T.Scratch([Entrant("b0", "x"), Entrant("b1", "y"), Entrant("b2", "z"), Entrant("b3", "w")], laps=10)
    with pytest.raises(TrackError):
        T.Scratch([Entrant(ME, "Toi")] + [Entrant("b0", "x")] * 3, laps=10)
    with pytest.raises(TrackError):
        T.Scratch(entrants(2), laps=10)
    with pytest.raises(TrackError):
        T.Madison(entrants(7), laps=30)                      # sans équipes
    with pytest.raises(TrackError):
        T.Pursuit(entrants(1), distance_m=2500.0)
    with pytest.raises(TrackError):
        T.TimeTrial(entrants(0), variant="1km")
    with pytest.raises(TrackError):
        T.Hour(entrants(0), duration_s=1800)
    ev = build("kilo")
    with pytest.raises(TrackError):
        ev.step(1.0, {ME: (1.0, 1.0)})                       # step avant start
    ev.start(0.0, {ME: (0.0, 0.0)})
    with pytest.raises(TrackError):
        ev.start(0.0, {ME: (0.0, 0.0)})


def test_lines_crossed_helper():
    assert lines_crossed(-3.0, 260.0, LAP) == [0.0, 250.0]
    assert lines_crossed(0.0, 250.0, LAP) == [250.0]
    assert lines_crossed(10.0, 10.0, LAP) == []
    assert [place_points(p) for p in (1, 2, 20, 30)] == [40, 38, 2, 1]


# --- contre-la-montre, heure, séance libre -------------------------------------------------------

@pytest.mark.parametrize("eid,timed", [("kilo", 1000.0), ("500", 500.0), ("flying_200", 200.0)])
def test_time_trials(eid, timed):
    ev = build(eid)
    msgs = run(ev, {ME: 15.0}, start={ME: 0.0})
    rec = ev.record()
    assert ev.finished and rec["id"] == f"track:{eid}" and rec["distance_m"] == timed
    assert rec["time_s"] == pytest.approx(timed / 15.0, rel=0.03)
    assert ev.summary()["place"] == 1 and kinds(msgs, "result")
    if eid == "flying_200":
        assert kinds(msgs, "timing")[0]["d_m"] == 425.0      # 2 tours et demi d'élan, 200 m chronométrés


def test_time_trial_unfinished_has_no_record():
    ev = build("kilo")
    run(ev, {ME: 10.0}, start={ME: 0.0}, until=60.0)
    assert not ev.finished and ev.record() is None and ev.frame()["to_go_m"] > 0


def test_hour_record_distance_and_lap_table():
    ev = build("hour")
    run(ev, {ME: 12.5}, start={ME: 0.0}, dt=1.0)
    rec = ev.record()
    assert ev.finished and ev.elapsed_s == pytest.approx(3600.0)
    assert rec["id"] == "track:hour" and rec["time_s"] == 3600.0
    assert rec["distance_m"] == pytest.approx(45_000.0, rel=0.01)
    s = ev.summary()
    assert len(s["laps"]) == int(rec["distance_m"] // LAP) and s["best_lap_s"] == pytest.approx(20.0, rel=0.05)


def test_free_session_never_ends_and_keeps_best_lap():
    ev = build("free", {"opponents": 0})
    msgs = run(ev, lambda rid, t, s: 10.0 if t < 30 else 14.0, start={ME: 0.0}, until=200.0)
    assert not ev.finished and len(kinds(msgs, "lap")) == len(ev.my_laps) >= 9
    assert ev.record() == {"id": "track:best_lap", "time_s": round(min(ev.my_laps), 3), "distance_m": LAP}
    assert min(ev.my_laps) == pytest.approx(LAP / 14.0, rel=0.05)


def test_grid_start_behind_the_line_does_not_count_a_lap():
    ev = build("free", {"opponents": 0})
    run(ev, {ME: 12.0}, start={ME: -6.0}, until=30.0)
    assert len(ev.my_laps) == 1 and ev.my_laps[0] == pytest.approx(LAP / 12.0, rel=0.05)


# --- poursuites ----------------------------------------------------------------------------------

def test_pursuit_both_finish_faster_wins():
    ev = build("pursuit", {"opponents": 1, "distance_m": 3000})
    run(ev, {ME: 14.0, "b0": 13.5}, start=sides(ev))
    s = ev.summary()
    assert ev.finished and s["winner"] == ME and s["place"] == 1
    assert s["times_s"][ME] == pytest.approx(3000 / 14.0, rel=0.03) and s["times_s"]["b0"] > s["times_s"][ME]
    assert ev.record()["id"] == "track:pursuit_3000"


def test_pursuit_catch_ends_the_race():
    ev = build("pursuit", {"opponents": 1})
    msgs = run(ev, {ME: 10.0, "b0": 14.0}, start=sides(ev))
    assert ev.finished and kinds(msgs, "caught") == [{"event": "caught", "team": ME, "by": "b0"}]
    assert ev.summary()["place"] == 2 and ev.record() is None


def test_pursuit_alone_against_the_clock():
    ev = build("pursuit", {"opponents": 0, "distance_m": 4000})
    run(ev, {ME: 14.0}, start={ME: 0.0})
    assert ev.finished and ev.frame()["gap_m"] is None and ev.record()["time_s"] == pytest.approx(4000 / 14, rel=0.03)


@pytest.mark.parametrize("place", [1, 2, 3])
def test_team_sprint_each_leads_a_lap_then_swings(place):
    ev = build("team_sprint", {"opponents": 1, "place": place})
    order = ev.teams["home"].order[:]
    assert order.index(ME) == place - 1
    msgs = run(ev, {}, start=sides(ev))
    swings = [m for m in kinds(msgs, "relay") if m["team"] == "home"]
    assert [m["rider"] for m in swings] == order[:2]
    assert [m["rider"] for m in kinds(msgs, "out") if m["rider"] in order] == order[:2]
    s = ev.summary()
    assert ev.finished and s["times_s"]["home"] == pytest.approx(750 / 13.0, rel=0.04)
    assert ev.record()["id"] == "track:team_sprint"


def test_team_pursuit_relays_rotate_and_time_on_third_rider():
    ev = build("team_pursuit", {"opponents": 1, "relay_laps": 0.5})
    speeds = {rid: 13.0 for rid in ev.riders}
    speeds["b2"] = 12.0                                   # le 3e coéquipier décroche
    msgs = run(ev, speeds, start=sides(ev))
    home = [m for m in kinds(msgs, "relay") if m["team"] == "home"]
    assert len(home) >= 25 and home[0]["rider"] == ME and home[0]["lead"] == "b0"
    assert {"event": "out", "rider": "b2", "reason": "dropped"} in msgs
    s = ev.summary()
    assert ev.finished and s["times_s"]["home"] == pytest.approx(4000 / 13.0, rel=0.04)


def test_team_pursuit_third_rider_is_never_dropped():
    ev = build("team_pursuit", {"opponents": 0})
    msgs = run(ev, {ME: 13.0, "b0": 13.0, "b1": 11.0, "b2": 10.5}, start={rid: 0.0 for rid in ev.riders})
    assert [m["rider"] for m in kinds(msgs, "out")] == ["b2"]   # seul le 4e est lâché : le chrono attend le 3e
    assert ev.finished and ev.record()["time_s"] == pytest.approx(4000 / 11.0, rel=0.04)


# --- courses en peloton --------------------------------------------------------------------------

def test_scratch_bell_arrival_and_ranking():
    ev = build("scratch", {"opponents": 5, "laps": 10})
    msgs = run(ev, bunch())
    assert ev.finished and len(kinds(msgs, "bell")) == 1 and len(kinds(msgs, "arrival")) == 6
    s = ev.summary()
    assert s["ranking"][0] == ME and s["ranking"][1:] == ["b4", "b3", "b2", "b1", "b0"]
    assert ev.frame()["bell"] and ev.frame()["laps_to_go"] == 1


def test_scratch_lap_gained_ranks_ahead():
    ev = build("scratch", {"opponents": 4, "laps": 20})
    msgs = run(ev, {ME: 12.0, "b0": 14.5, "b1": 12.2, "b2": 12.1, "b3": 12.3})
    assert {"event": "lap_gained", "unit": "b0", "points": 0} in msgs
    assert ev.summary()["ranking"][0] == "b0" and ev.summary()["laps_up"]["b0"] >= 1


def test_scratch_lapped_rider_still_finishes_with_the_grace():
    ev = build("scratch", {"opponents": 3, "laps": 10})
    run(ev, {ME: 6.0, "b0": 13.0, "b1": 13.1, "b2": 13.2})
    s = ev.summary()
    assert ev.finished and s["ranking"][-1] == ME and s["place"] == 4


def test_points_race_sprints_doubled_at_the_end_and_laps():
    ev = build("points", {"opponents": 4, "laps": 20})
    msgs = run(ev, {ME: 13.0, "b0": 12.8, "b1": 12.6, "b2": 12.4, "b3": 12.2})
    sprints = kinds(msgs, "points")
    first = [m for m in sprints if m["why"] == "sprint_1"]
    last = [m for m in sprints if m["why"] == "sprint_2"]
    assert [m["points"] for m in first] == list(SPRINT_POINTS)
    assert [m["points"] for m in last] == [2 * p for p in SPRINT_POINTS]
    pts = ev.points()
    assert pts[ME] == 15 and ev.summary()["place"] == 1


def test_points_race_lap_is_worth_twenty():
    ev = build("points", {"opponents": 4, "laps": 20})
    msgs = run(ev, {ME: 15.0, "b0": 12.0, "b1": 12.1, "b2": 12.2, "b3": 12.3})
    gained = [m for m in msgs if m["event"] == "lap_gained" and m["unit"] == ME]
    assert gained and gained[0]["points"] == 20 and ev.points()[ME] >= 20 * len(gained)


def test_tempo_point_per_lap_from_the_fifth():
    ev = build("tempo", {"opponents": 3, "laps": 10})
    msgs = run(ev, {ME: 13.0, "b0": 12.5, "b1": 12.4, "b2": 12.3})
    tempo = kinds(msgs, "points")
    assert [m["why"] for m in tempo] == [f"lap_{k}" for k in range(5, 11)]
    assert all(m["unit"] == ME and m["points"] == 1 for m in tempo) and ev.points()[ME] == 6


def test_elimination_slowest_out_every_two_laps():
    ev = build("elimination", {"opponents": 4})
    speeds = {ME: 13.0, "b0": 12.0, "b1": 12.2, "b2": 12.4, "b3": 12.6}
    msgs = run(ev, speeds)
    outs = kinds(msgs, "out")
    assert [m["rider"] for m in outs] == ["b0", "b1", "b2", "b3"]
    assert all(m["reason"] == "eliminated" for m in outs)
    assert ev.finished and ev.summary()["ranking"] == [ME, "b3", "b2", "b1", "b0"] and ev.frame()["laps"] == 8


def test_elimination_me_out_first():
    ev = build("elimination", {"opponents": 3})
    msgs = run(ev, {ME: 11.0, "b0": 12.0, "b1": 12.2, "b2": 12.4})
    assert kinds(msgs, "out")[0]["rider"] == ME and ev.summary()["place"] == 4


def keirin_speed(ev: T.Keirin, want: dict[str, float]) -> Speed:
    """Les coureurs restent derrière le derny tant qu'il roule, puis sprintent à leur vitesse."""
    def fn(rid: str, t: float, s: float) -> float:
        v = want.get(rid, 15.0)
        if ev.pacer_on:
            v = min(v, ev.pacer_v, max((ev.pacer_d - 2.0 - (s - ev.origin)) / DT, 0.0))
        return v
    return fn


def test_keirin_pacer_ramps_then_leaves_three_laps_out():
    ev = build("keirin", {"opponents": 3, "laps": 8})
    msgs = run(ev, keirin_speed(ev, {ME: 17.0, "b0": 16.0, "b1": 16.5, "b2": 15.5}))
    off = kinds(msgs, "pacer_off")
    assert len(off) == 1 and not kinds(msgs, "out")
    assert ev.pacer_v == pytest.approx(PACER_END_KMH / 3.6, rel=0.01) and PACER_START_KMH < PACER_END_KMH
    assert ev.finished and ev.summary()["ranking"][0] == ME
    assert ev.frame()["pacer"]["on"] is False


def test_keirin_passing_the_pacer_relegates():
    ev = build("keirin", {"opponents": 3})
    want = {"b0": 14.0, "b1": 14.0, "b2": 14.0}
    base = keirin_speed(ev, want)
    msgs = run(ev, lambda rid, t, s: 16.0 if rid == ME else base(rid, t, s))
    assert {"event": "out", "rider": ME, "reason": "passed_pacer"} in msgs
    assert ev.summary()["ranking"][-1] == ME


def test_madison_relays_every_375_m_with_launch_speed():
    ev = build("madison", {"opponents": 3, "laps": 20})
    assert ev.racer("home") == ME
    msgs = run(ev, {})
    relays = [m for m in kinds(msgs, "relay") if m["team"] == "home"]
    assert len(relays) == pytest.approx(20 * LAP / RELAY_M, abs=1.5)
    assert relays[0]["rider"] == ME and relays[0]["to"] == "b0" and relays[0]["v"] > 10
    assert relays[1]["rider"] == "b0" and relays[1]["to"] == ME
    assert ev.finished and set(ev.summary()["ranking"]) == {"home", "t2", "t3", "t4"}


def test_madison_team_distance_counts_only_the_racer():
    ev = build("madison", {"opponents": 3, "laps": 20})
    # le coéquipier au repos roule vite en haut de la piste : il ne fait pas avancer l'équipe
    run(ev, lambda rid, t, s: 20.0 if rid == "b0" and ev.racer("home") == ME else 13.0, until=40.0)
    home = ev.units["home"]
    assert home.d < 40.0 * 13.5


def test_omnium_four_events_and_place_points():
    ev = build("omnium", {"opponents": 3})
    msgs = run(ev, {ME: 13.0, "b0": 12.0, "b1": 12.3, "b2": 12.6})
    subs = [m["sub"] for m in kinds(msgs, "sub_start")]
    assert subs == ["scratch", "tempo", "elimination", "points"]
    s = ev.summary()
    assert ev.finished and [x["sub"] for x in s["subs"]] == subs
    assert [x["place"] for x in s["subs"][:3]] == [1, 1, 1]
    assert ev.points()[ME] == 3 * 40 + s["subs"][3]["points"] and s["place"] == 1
    assert not kinds(msgs, "lap") or all("sub" not in m for m in kinds(msgs, "lap"))


# --- communs : pause, graine, pente, trame --------------------------------------------------------

ALL = [("free", {"opponents": 3}), ("pursuit", {"opponents": 1}), ("kilo", {}), ("500", {}), ("flying_200", {}),
       ("scratch", {"opponents": 11, "laps": 10}), ("points", {"opponents": 11, "laps": 20}),
       ("tempo", {"opponents": 11}), ("elimination", {"opponents": 11}), ("keirin", {"opponents": 6}),
       ("omnium", {"opponents": 11}), ("team_sprint", {"opponents": 1}), ("team_pursuit", {"opponents": 1}),
       ("madison", {"opponents": 5, "laps": 20})]


def _start_for(ev: T.TrackEvent) -> dict[str, float]:
    return sides(ev) if isinstance(ev, T.Pursuit) else grid(ev)


def _speed_for(ev: T.TrackEvent) -> Speed:
    v = bunch()
    if isinstance(ev, T.Keirin):
        return keirin_speed(ev, {k: x + 2.0 for k, x in v.items()})
    return lambda rid, t, s: v.get(rid, 13.0)


@pytest.mark.parametrize("eid,settings", ALL)
def test_same_seed_same_result(eid, settings):
    out = []
    for _ in range(2):
        ev = build(eid, settings, seed=7)
        msgs = run(ev, _speed_for(ev), start=_start_for(ev), until=1500.0, seed=3)
        out.append((msgs, ev.summary(), ev.frame()))
    assert out[0] == out[1]
    assert eid == "free" or out[0][1]["finished"]


@pytest.mark.parametrize("eid,settings", ALL)
def test_no_event_returns_a_grade(eid, settings):
    ev = build(eid, settings)
    msgs = run(ev, _speed_for(ev), start=_start_for(ev), until=600.0)
    text = json.dumps([msgs, ev.frame(), ev.summary(), ev.take_journal()])
    assert "grade" not in text and "slope" not in text and not hasattr(ev, "grade")


@pytest.mark.parametrize("eid,settings", ALL)
def test_pause_freezes_the_event(eid, settings):
    ev = build(eid, settings)
    run(ev, _speed_for(ev), start=_start_for(ev), until=30.0)
    before = json.dumps(ev.frame())
    frozen = {rid: (r.s, 0.0) for rid, r in ev.riders.items()}
    for _ in range(40):                                   # instant chronométré figé : la séance est en pause
        assert ev.step(ev.t, frozen) == []
    assert json.dumps(ev.frame()) == before


@pytest.mark.parametrize("eid,settings", ALL)
def test_track_frame_fits_the_ipc_budget(eid, settings):
    ev = build(eid, settings)
    run(ev, _speed_for(ev), start=_start_for(ev), until=200.0)
    worst = ipc_budget.size({"track": ipc_budget.worst_track()})
    assert ipc_budget.size({"track": ev.frame()}) <= worst <= ipc_budget.TRACK_FRAME_MAX
    assert set(ev.frame()) - set(ipc_budget.worst_track()) <= {"d_m", "to_go_m", "timed", "time_s", "time_left_s",
                                                                "avg_kmh", "last_lap_s", "best_lap_s", "gap_m",
                                                                "gap_s", "lead", "order"}


def test_journal_lines_and_laps_for_the_fit():
    ev = build("scratch", {"opponents": 3, "laps": 10})
    run(ev, bunch())
    lines = ev.take_journal()
    assert all(ln["kind"] == "track" and ln["track"] == "scratch" for ln in lines)
    laps = [ln for ln in lines if ln["event"] == "lap" and ln["rider"] == ME]
    assert len(laps) == len(ev.my_laps) >= 10 and ev.take_journal() == []
