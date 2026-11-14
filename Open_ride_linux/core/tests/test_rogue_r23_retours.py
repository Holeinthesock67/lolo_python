"""Lot R23 : retours du Cyber-Rogue côté core (contrat révision 1.17).

Aucun événement perdu entre deux trames (boucle à 50 Hz, trame à 30 Hz), un seul retour par Z court dans toutes
les phases (`z_ok` et son action, ou `z_refused` et sa raison), tendance de l'adrénaline et plage de la consigne en
endurance.
"""

from __future__ import annotations

from dataclasses import replace

import jsonschema
import pytest

from openride_core.config import Config
from openride_core.physics import RiderPhysics
from openride_core.rogue.combat import (ADRENALINE_CAUSES, Z_ACTIONS, CombatInputs, combat_start, combat_step,
                                        overheat_limit)
from openride_core.rogue.mode import FRAME_EVENTS_MAX, RogueMode, parse_start_run
from openride_core.rogue.rooms import generate_room
from test_rogue_run import B, DT, RIDER, ROGUE_SCHEMA, Rider, engine, fight_engine, step_in_room

T0_WALL = 1_800_000_000.0


def _base(**kw):
    d = dict(power_w=0, cadence_rpm=85, posture="FLUIDE", gear=6, ftp_w=250, s_m=0.0, v_mps=8.0)
    d.update(kw)
    return d


def test_actions_and_causes_are_listed_in_the_schema():
    props = ROGUE_SCHEMA["properties"]
    assert set(Z_ACTIONS) == set(props["z_action"]["enum"]) - {None}
    assert set(ADRENALINE_CAUSES) == set(props["adrenaline_trend"]["properties"]["cause"]["enum"])
    assert "z_ok" in props["events"]["items"]["enum"]
    assert props["events"]["maxItems"] == FRAME_EVENTS_MAX


# --- trame à 30 Hz, pas à 50 Hz : aucun événement perdu ---------------------------------------------

def _mode():
    cfg = Config()
    return RogueMode(cfg, parse_start_run({"objective": "threshold", "duration_min": 30, "seed": 3}, cfg))


def test_events_of_every_step_reach_the_next_frame_once():
    mode = _mode()
    body = RiderPhysics(mode.rider.params)
    sent, presses = [], 0
    t, next_frame = 0.0, 0.0
    for i in range(1500):                                   # 30 s d'échauffement, Z toutes les 0,26 s environ
        if i % 13 == 0:
            mode.press("Z_SHORT")
            presses += 1
        mode.step(0.02, 150.0, 85.0, body, False, T0_WALL)
        t += 0.02
        if t >= next_frame:
            next_frame += 1.0 / 30.0
            frame = mode.take_frame()
            jsonschema.validate(frame, ROGUE_SCHEMA)
            sent += frame["events"]
            if "z_refused" in frame["events"]:
                assert frame["z_reason"] == "no_target"
            else:
                assert frame["z_reason"] is None
    assert sent.count("z_refused") == presses                # avant R23 : 2 pas sur 5 n'arrivaient jamais
    assert mode.take_frame()["events"] == []                 # rien n'est répété


def test_frame_keeps_the_feedback_of_the_step_that_made_it():
    e = fight_engine(first="grimpeur")
    m = next(m for m in e.room.markers if m.kind == "strike_target")
    e.combat = replace(e.combat, adrenaline=80.0)
    mode = _mode()
    mode.engine = e
    body = RiderPhysics(mode.rider.params)
    body.s = m.s_m
    mode.press("Z_SHORT")
    mode.step(0.02, 200.0, 85.0, body, False, T0_WALL)       # frappe
    body.s = m.s_m + 0.2
    mode.step(0.02, 200.0, 85.0, body, False, T0_WALL)       # pas suivant, sans appui
    frame = mode.take_frame()
    assert "z_ok" in frame["events"] and "hit" in frame["events"] and frame["z_action"] == "strike"
    assert mode.take_frame()["z_action"] is None


# --- un seul retour par Z court, dans toutes les phases ---------------------------------------------

def test_every_z_press_has_exactly_one_feedback_in_every_phase():
    e = engine()
    script = {k: ("Z_SHORT",) for k in range(0, 40000, 37)}   # Z toutes les 1,85 s, toute la run
    r = Rider(e, script=script)
    r.run()
    seen_phases = set()
    for k, out in enumerate(r.outs):
        ev = out.rogue["events"]
        n = ev.count("z_ok") + ev.count("z_refused")
        if k in script:
            assert n == 1, (k, out.phase, ev)
            seen_phases.add(out.phase)
            if "z_ok" in ev:
                assert out.rogue["z_action"] in Z_ACTIONS
            else:
                assert out.rogue["z_reason"] is not None
        else:
            assert n == 0, (k, out.phase, ev)
    assert {"WARMUP", "ROOM", "CORRIDOR", "BOSS", "COOLDOWN"} <= seen_phases


def test_warmup_without_relic_and_cooldown_say_no_target():
    e = engine()
    r = Rider(e, script={round(5.0 / DT): ("Z_SHORT",)})
    r.run(max_s=6.0)
    out = r.outs[round(5.0 / DT)]
    assert out.phase == "WARMUP" and out.rogue["events"] == ["z_refused"] and out.rogue["z_reason"] == "no_target"


def test_strike_and_charges_actions():
    e = fight_engine(first="grimpeur")
    m = next(m for m in e.room.markers if m.kind == "strike_target")
    e.combat = replace(e.combat, adrenaline=80.0)
    out = step_in_room(e, m.s_m, buttons=("Z_SHORT",))
    assert out.rogue["z_action"] == "strike" and "z_ok" in out.rogue["events"]
    jsonschema.validate(out.rogue, ROGUE_SCHEMA)
    room = generate_room("diesel", "", "threshold", 240.0, RIDER, 1)
    lock = next(m for m in room.markers if m.kind == "strike_target")
    st = replace(combat_start(room, 1), charges=2)
    new, ev = combat_step(st, CombatInputs(**_base(s_m=lock.s_m, buttons=frozenset({"Z_SHORT"}))), room, B, DT)
    assert "z_ok" in ev and new.z_action == "charges" and new.charges == 0


def test_rock_chip_then_rock():
    room = generate_room("grimpeur", "", "threshold", 240.0, RIDER, 1)
    rocks = [(i, m) for i, m in enumerate(room.markers) if m.kind == "rock"]
    if not rocks:
        pytest.skip("pas de rocher dans cette salle")
    i, rock = rocks[0]
    st = replace(combat_start(room, 1), roc_charges=3, rock_armor=((i, 2),))
    st, ev = combat_step(st, CombatInputs(**_base(s_m=rock.s_m, buttons=frozenset({"Z_SHORT"}))), room, B, DT)
    assert "z_ok" in ev and st.z_action == "rock_chip" and "hit" not in ev
    st, ev = combat_step(st, CombatInputs(**_base(s_m=rock.s_m + 0.1, buttons=frozenset({"Z_SHORT"}))), room, B, DT)
    assert "z_ok" in ev and st.z_action == "rock" and "hit" in ev


def test_reroll_is_a_z_ok():
    e = engine()
    r = Rider(e)
    while e.phase != "CORRIDOR" and r.t < 2000:
        r.run(max_s=r.t + DT)
    e.gold = 500
    out = e.step(DT, _run_inputs(("Z_SHORT",)))
    assert "z_ok" in out.rogue["events"] and out.rogue["z_action"] == "reroll"


def _run_inputs(buttons=()):
    from openride_core.rogue.run import RunInputs
    return RunInputs(power_w=150, cadence_rpm=85, gear=6, ftp_w=250, buttons=frozenset(buttons))


# --- adrénaline : tendance et surchauffe ----------------------------------------------------------

def test_adrenaline_trend_gain_below_stopped():
    room = generate_room("diesel", "", "threshold", 240.0, RIDER, 1)
    st = combat_start(room, 1)
    st, _ = combat_step(st, CombatInputs(**_base(s_m=5.0, power_w=500)), room, B, DT)
    assert st.adr_cause == "gain" and st.adr_rate == pytest.approx(B.adrenaline_per_s)
    st, _ = combat_step(st, CombatInputs(**_base(s_m=5.4, power_w=10)), room, B, DT)
    assert st.adr_cause == "below" and st.adr_rate == 0.0
    st, _ = combat_step(st, CombatInputs(**_base(s_m=5.8, power_w=500, posture="ARRET")), room, B, DT)
    assert st.adr_cause == "stopped"
    full = replace(st, adrenaline=B.adrenaline_max)
    st, _ = combat_step(full, CombatInputs(**_base(s_m=6.2, power_w=500)), room, B, DT)
    assert st.adr_cause == "full" and st.adr_rate == 0.0


def test_endurance_overheat_countdown_then_melt_and_target_range():
    e = fight_engine(first="diesel", objective="endurance")
    out = step_in_room(e, 5.0, power=150.0)
    assert out.rogue["target_pct"]["hi"] == round(overheat_limit(out.rogue["target_pct"]["lo"] / 100, B) * 100)
    assert out.rogue["target_pct"]["lo"] <= out.rogue["target_pct"]["hi"]
    hot = 250.0 * (out.rogue["target_pct"]["hi"] / 100 + 0.1)
    out = step_in_room(e, 6.0, power=hot, n=round(2.0 / DT))
    trend = out.rogue["adrenaline_trend"]
    assert trend["cause"] != "overheat" and trend["overheat_in_s"] == pytest.approx(B.overheat_after_s - 2.0, abs=0.1)
    out = step_in_room(e, 8.0, power=hot, n=round(4.0 / DT))
    trend = out.rogue["adrenaline_trend"]
    assert out.rogue["overheat"] and trend == {"rate_per_s": -B.overheat_adrenaline_per_s, "cause": "overheat",
                                               "overheat_in_s": None}
    jsonschema.validate(out.rogue, ROGUE_SCHEMA)


def test_threshold_room_keeps_open_target_and_no_overheat():
    e = fight_engine(first="diesel", objective="threshold")
    out = step_in_room(e, 5.0, power=400.0, n=round(8.0 / DT))
    assert out.rogue["target_pct"]["hi"] is None and not out.rogue["overheat"]
    assert out.rogue["adrenaline_trend"]["overheat_in_s"] is None


def test_trend_is_none_outside_rooms():
    e = engine()
    r = Rider(e)
    r.run(max_s=2.0)
    assert r.outs[-1].rogue["adrenaline_trend"] == {"rate_per_s": 0.0, "cause": "none", "overheat_in_s": None}


def test_overheat_limit_never_below_the_target():
    # Boss d'endurance : cible jusqu'à 85 % ; avant R23, tenir la consigne faisait fondre l'adrénaline (seuil 75 %).
    assert overheat_limit(0.68, B) == pytest.approx(B.overheat_frac + 0.03)
    assert overheat_limit(0.50, B) == B.overheat_frac
    assert overheat_limit(0.85, B) == pytest.approx(0.95)
    room = generate_room("boss", "phase3", "endurance", 60.0, RIDER, 1)
    from openride_core.rogue.combat import target_at
    st = combat_start(room, 1)
    for k in range(round(20.0 / DT)):                      # tient la cible + 5 points pendant 20 s
        s = 2.0 + 0.4 * k
        p = 250.0 * (target_at(room, s) + 0.05)
        st, _ = combat_step(st, CombatInputs(**_base(s_m=s, power_w=p, objective="endurance")), room, B, DT)
        assert not st.overheat
