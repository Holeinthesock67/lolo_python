"""Lot R22 : lisibilité du Cyber-Rogue côté core (contrat révision 1.16).

Raison de chaque Z court refusé, verdict des arches de Perfect Shift ratées, temps restant de la phase,
étapes à venir, temps du choix en couloir, consigne de puissance et avance sur le Firewall en secondes.
"""

from __future__ import annotations

from dataclasses import replace

import jsonschema
import pytest

from openride_core.rogue.combat import (SHIFT_LATE_S, CombatInputs, Z_REASONS, combat_start, combat_step)
from openride_core.rogue.rooms import generate_room
from test_rogue_run import (B, DT, RIDER, ROGUE_SCHEMA, Rider, corridor_script, engine, fight_engine,
                            run_to_corridor, step_in_room)


def _base(**kw):
    d = dict(power_w=0, cadence_rpm=85, posture="FLUIDE", gear=6, ftp_w=250, s_m=0.0, v_mps=8.0)
    d.update(kw)
    return d


# --- Z court : la raison du refus -----------------------------------------------------------------

def test_z_reasons_are_listed_in_the_schema():
    enum = ROGUE_SCHEMA["properties"]["z_reason"]["enum"]
    assert set(Z_REASONS) == set(enum) - {None}


def test_strike_refused_for_adrenaline_then_overheat():
    room = generate_room("boss", "phase1", "threshold", 210.0, RIDER, 1)
    lock = next(m for m in room.markers if m.kind == "strike_target")
    st = replace(combat_start(room, 1), adrenaline=20.0)
    new, ev = combat_step(st, CombatInputs(**_base(s_m=lock.s_m, buttons=frozenset({"Z_SHORT"}))), room, B, DT)
    assert "z_refused" in ev and new.z_reason == "adrenaline"
    hot = replace(combat_start(room, 1), adrenaline=90.0, over_s=999.0)
    new, ev = combat_step(hot, CombatInputs(**_base(s_m=lock.s_m, power_w=400, objective="endurance",
                                                     buttons=frozenset({"Z_SHORT"}))), room, B, DT)
    assert "z_refused" in ev and new.z_reason == "overheat"


def test_diesel_strike_without_tunnel_charge():
    room = generate_room("diesel", "", "threshold", 240.0, RIDER, 1)
    lock = next(m for m in room.markers if m.kind == "strike_target")
    new, ev = combat_step(combat_start(room, 1), CombatInputs(**_base(s_m=lock.s_m, buttons=frozenset({"Z_SHORT"}))),
                          room, B, DT)
    assert new.z_reason == "no_charge" and "hit" not in ev


def test_purge_beacon_without_hack():
    room = generate_room("saboteur", "", "threshold", 240.0, RIDER, 1)
    beacon = next(m for m in room.markers if m.kind == "purge")
    st = combat_start(room, 1)
    # balise atteinte d'un bond, piratage tiré puis effacé : l'appui tombe sans piratage en cours
    st = replace(st, done_markers=frozenset(("hack", i) for i, m in enumerate(room.markers) if m.kind == "purge"))
    new, ev = combat_step(st, CombatInputs(**_base(s_m=beacon.s_m, buttons=frozenset({"Z_SHORT"}))), room, B, DT)
    assert new.z_reason == "no_hack" and "purge" not in ev


def test_z_reason_lasts_one_frame():
    room = generate_room("diesel", "", "threshold", 240.0, RIDER, 1)
    st, ev = combat_step(combat_start(room, 1), CombatInputs(**_base(s_m=5.0, buttons=frozenset({"Z_SHORT"}))),
                         room, B, DT)
    assert st.z_reason == "no_target"
    st, ev = combat_step(st, CombatInputs(**_base(s_m=5.4)), room, B, DT)
    assert st.z_reason is None and ev == ()


def test_run_reports_cursed_and_gold_refusals():
    e = fight_engine(first="grimpeur", deck=("cursed",))
    m = next(m for m in e.room.markers if m.kind == "strike_target")
    e.combat = replace(e.combat, adrenaline=80.0)
    out = step_in_room(e, m.s_m, gear=10, buttons=("Z_SHORT",))
    assert "z_refused" in out.rogue["events"] and out.rogue["z_reason"] == "cursed"
    out = step_in_room(e, m.s_m + 1.0, gear=10)
    assert out.rogue["z_reason"] is None
    jsonschema.validate(out.rogue, ROGUE_SCHEMA)

    e = engine()
    r = Rider(e)
    t0 = run_to_corridor(e, r)
    e.gold = 5.0
    r.script = corridor_script(t0, [(1, "Z_SHORT")])
    r.run(max_s=t0 + 1.2)
    refused = [o.rogue for o in r.outs if "z_refused" in o.rogue["events"]]
    assert refused and refused[-1]["z_reason"] == "gold" and e.rerolls == 0


# --- Perfect Shift : verdict des arches ratées ----------------------------------------------------

def _arch_room():
    for seed in range(1, 40):
        room = generate_room("grimpeur", "", "threshold", 240.0, RIDER, seed)
        arches = [m for m in room.markers if m.kind == "arch"]
        if arches:
            return room, arches[0]
    raise AssertionError("aucune salle avec une arche")


def _ride_past(room, arch, shift_at_s=None, direction=None, v=8.0):
    """Roule de 30 m avant l'arche jusqu'au verdict ; change de vitesse à `shift_at_s` (s par rapport à l'arche)."""
    st = combat_start(room, 1)
    gear = st.gear
    s = arch.s_m - 30.0
    shifted = False
    misses, events = [], []
    end = arch.s_m + (0.5 * B.ps_window_s + SHIFT_LATE_S) * v + 5.0
    while s < end:
        t_rel = (s - arch.s_m) / v
        if shift_at_s is not None and not shifted and t_rel >= shift_at_s:
            gear += 1 if direction == "up" else -1
            shifted = True
        st, ev = combat_step(st, CombatInputs(**_base(s_m=s, gear=gear, v_mps=v)), room, B, DT)
        events += ev
        if "shift_missed" in ev:
            misses.append(st.shift_miss)
        s += v * DT
    return events, misses


def test_perfect_shift_has_no_miss_verdict():
    room, arch = _arch_room()
    events, misses = _ride_past(room, arch, 0.0, arch.param)
    assert "perfect_shift" in events and misses == []


@pytest.mark.parametrize("at, wrong, reason", [(-2.0, False, "early"), (1.2, False, "late"),
                                               (0.0, True, "wrong_way"), (None, False, "none")])
def test_missed_arch_verdicts(at, wrong, reason):
    room, arch = _arch_room()
    direction = arch.param if not wrong else ("down" if arch.param == "up" else "up")
    events, misses = _ride_past(room, arch, at, direction)
    assert "perfect_shift" not in events
    assert misses and misses[0][0] == reason
    if reason in ("early", "late"):
        assert misses[0][1] == pytest.approx(at, abs=0.15)


# --- état : temps restant, étapes à venir, consigne, Firewall en secondes --------------------------

def test_warmup_countdown_next_steps_and_target():
    e = engine()
    r = Rider(e)
    r.run(max_s=10.0)
    st = r.outs[-1].rogue
    jsonschema.validate(st, ROGUE_SCHEMA)
    assert st["phase_left_s"] == pytest.approx(190.0, abs=0.2)
    assert st["next"][0]["kind"] == "relic" and st["next"][0]["in_s"] == pytest.approx(170.0, abs=0.2)
    assert st["next"][1] == {"kind": "room", "in_s": st["phase_left_s"], "archetype": "diesel"}
    assert st["target_pct"]["lo"] < st["target_pct"]["hi"]
    assert st["firewall_gap_s"] is None and st["loot_stage"] is None
    r.run(max_s=182.0)                                       # relique offerte : premier temps du choix
    st = r.outs[-1].rogue
    assert st["loot_stage"] == "card" and st["next"][0]["kind"] == "room"


def test_room_gap_in_seconds_and_corridor_stages():
    e = engine()
    r = Rider(e)
    while e.phase != "ROOM":
        r.run(max_s=r.t + DT)
    r.run(max_s=r.t + 5.0)
    st = r.outs[-1].rogue
    jsonschema.validate(st, ROGUE_SCHEMA)
    v = r.body.v
    assert st["firewall_gap_s"] == pytest.approx(min(st["firewall_gap_m"] / max(v, 1.0), 99.0), abs=0.2)
    assert st["phase_left_s"] is None and st["target_pct"]["hi"] is None
    assert st["next"][0]["kind"] == "corridor" and st["next"][0]["in_s"] > 0
    t0 = run_to_corridor(e, r)
    r.script = corridor_script(t0, [(1, "A_SHORT"), (2, "A_LONG"), (3, "RIGHT_SHORT")])
    r.run(max_s=t0 + 1.5)
    assert r.outs[-1].rogue["loot_stage"] == "card"
    r.run(max_s=t0 + 3.5)
    st = r.outs[-1].rogue
    assert st["loot_stage"] == "door" and st["next"][0] == {"kind": "room", "in_s": st["phase_left_s"],
                                                           "archetype": "grimpeur"}
    jsonschema.validate(st, ROGUE_SCHEMA)


def test_cooldown_points_to_results():
    e = engine()
    r = Rider(e)
    while e.phase != "COOLDOWN" and r.t < 4000:
        r.run(max_s=r.t + DT)
    st = r.outs[-1].rogue
    assert st["next"] == [{"kind": "results", "in_s": st["phase_left_s"], "archetype": None}]
    assert st["target_pct"] == {"lo": 0, "hi": round(B.cooldown_frac * 100)}
