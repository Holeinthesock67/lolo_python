"""Lot R5 : règles de combat du Cyber-Rogue."""

from __future__ import annotations

from dataclasses import replace

import pytest

from openride_core.physics import PhysicsParams, RiderPhysics
from openride_core.rogue.balance import DEFAULT_BALANCE
from openride_core.rogue.combat import (DONE, RECOVERY, CombatInputs, apply_gear_buttons,
                                        combat_start, combat_step, target_at, target_mean)
from openride_core.rogue.firewall import Firewall
from openride_core.rogue.rooms import BOSS_PHASES, OBJECTIVES, RoomRider, generate_room

RIDER = RoomRider(ftp_w=250.0, params=PhysicsParams(mass_kg=84.0, cda_m2=0.32))
B = DEFAULT_BALANCE
DT = 0.02


def ride(room, power_mult=1.0, gear=6, posture="FLUIDE", cadence=85.0, objective="threshold", seed=1,
         buttons_at=None, balance=B, with_wall=False):
    """Joueur qui suit la cible ; renvoie (état final, événements [(t, nom)], premier état à 0 PV)."""
    player = RiderPhysics(RIDER.params)
    state = combat_start(room, seed, balance, gear=gear)
    wall = Firewall(room, RIDER, balance) if with_wall else None
    events = []
    t = 0.0
    while state.phase != DONE and t < room.nominal_s * 3:
        p = target_at(room, player.s) * RIDER.ftp_w * power_mult
        player.step(p, room.profile[min(int(player.s // 10), len(room.profile) - 1)][1], 0.0, DT)
        contact = wall.step(DT, player.s).contact if wall else False
        buttons = frozenset((buttons_at or {}).get(round(t / DT), ()))
        inp = CombatInputs(power_w=p, cadence_rpm=cadence, posture=posture, gear=gear, ftp_w=RIDER.ftp_w,
                           s_m=player.s, v_mps=player.v, contact=contact, buttons=buttons, objective=objective)
        state, ev = combat_step(state, inp, room, balance, DT)
        events += [(t, e) for e in ev]
        t += DT
    return state, events


CASES = [(a, v, o) for a in ("diesel", "puncheur", "grimpeur", "sprinteur", "saboteur") for v in ("",)
         for o in OBJECTIVES] + [("boss", ph, o) for ph in BOSS_PHASES for o in ("endurance", "threshold")]


@pytest.mark.parametrize("a,v,o", CASES)
def test_rider_on_target_is_never_defeated_and_wins_late(a, v, o):
    """Sans bonus de timing ni de braquet, suivre la cible juste ne suffit pas toujours : la salle se gagne tard
    (85 à 100 % de la distance) ou l'ennemi fuit, jamais de défaite (PV réglés par le lot R7)."""
    room = generate_room(a, v, o, 300.0, RIDER, 1)
    state, events = ride(room, objective=room.objective)
    assert state.outcome in ("won", "fled") and "defeat" not in [e for _, e in events]
    if state.outcome == "won":
        assert 0.85 <= state.down_s_m / room.length_m <= 1.0, state.down_s_m / room.length_m


def test_puncheur_30_30_wins_late_or_flees():
    room = generate_room("puncheur", "30_30", "vo2max", 300.0, RIDER, 2)
    state, _ = ride(room, objective="vo2max")
    assert state.outcome in ("won", "fled")
    if state.outcome == "won":
        assert 0.85 <= state.down_s_m / room.length_m <= 1.0


@pytest.mark.parametrize("objective,field_name", [("endurance", "hp_factor_endurance"), ("threshold", "hp_factor_threshold"),
                                                   ("vo2max", "hp_factor_vo2max")])
def test_enemy_hp_follows_the_factor_of_its_objective(objective, field_name):
    room = generate_room("diesel" if objective != "vo2max" else "grimpeur", "", objective, 300.0, RIDER, 1)
    for factor in (1.0, 1.5):
        bal = replace(B, **{field_name: factor})
        hp = combat_start(room, 1, bal).enemy_hp_max
        assert hp == pytest.approx(factor * target_mean(room) * room.nominal_s)


def test_boss_hp_has_its_own_factor():
    room = generate_room("boss", "phase1", "threshold", 300.0, RIDER, 1)
    bal = replace(B, boss_hp_factor=1.5, hp_factor_threshold=1.0)
    assert combat_start(room, 1, bal).enemy_hp_max == pytest.approx(1.5 * target_mean(room) * room.nominal_s)


def test_rider_under_target_is_caught_by_the_wall():
    room = generate_room("diesel", "", "threshold", 480.0, RIDER, 1)
    state, events = ride(room, power_mult=0.8, with_wall=True)
    names = [e for _, e in events]
    assert "firewall_contact" in names and state.gold_lost > 0
    assert state.shield < B.shield_max


def test_deterministic_with_crits():
    room = generate_room("diesel", "", "threshold", 120.0, RIDER, 1)
    r1 = ride(room, posture="VELOCE", cadence=105.0, seed=7, buttons_at={100: ("Z_SHORT",)})
    r2 = ride(room, posture="VELOCE", cadence=105.0, seed=7, buttons_at={100: ("Z_SHORT",)})
    r3 = ride(room, posture="VELOCE", cadence=105.0, seed=8)
    assert r1 == r2
    assert any(e == "crit" for _, e in r1[1])
    assert [e for e in r1[1] if e[1] == "crit"] != [e for e in r3[1] if e[1] == "crit"]


def test_crit_doubles_damage_and_roc_armor():
    room = generate_room("diesel", "", "threshold", 120.0, RIDER, 1)
    fluid, _ = ride(room, posture="FLUIDE")
    veloce, _ = ride(room, posture="VELOCE", cadence=105.0)
    assert veloce.down_s_m < fluid.down_s_m                      # critiques : l'ennemi tombe plus tôt
    arret, _ = ride(room, posture="ARRET")
    assert arret.outcome == "fled" and arret.down_s_m is None


def test_defeat_recovery_and_gold_loss():
    room = generate_room("diesel", "", "threshold", 240.0, RIDER, 1)
    state = combat_start(room, 1)
    base = dict(power_w=200, cadence_rpm=85, posture="FLUIDE", gear=6, ftp_w=250, s_m=100, v_mps=8,
                contact=True, run_gold=100.0)
    events, t = [], 0.0
    while state.phase == "FIGHT":
        state, ev = combat_step(state, CombatInputs(**base), room, B, 0.1)
        events += ev
        t += 0.1
    assert t == pytest.approx(25.0, abs=0.2)                      # 100 / 4 par seconde
    assert "defeat" in events and "firewall_contact" in events and events.count("firewall_contact") == 1
    assert state.phase == RECOVERY and state.shield == B.recovery_shield and state.gold == 0
    assert state.gold_lost == pytest.approx(t * B.contact_gold_per_s + 25.0, abs=0.2)
    for _ in range(int(B.recovery_s / 0.1) + 5):
        state, _ = combat_step(state, CombatInputs(**base), room, B, 0.1)
    assert state.phase == DONE and state.outcome == "defeat"


def test_boss_defeat_flees_without_recovery():
    room = generate_room("boss", "phase1", "threshold", 210.0, RIDER, 1)
    state = replace(combat_start(room, 1), shield=0.5)
    state, ev = combat_step(state, CombatInputs(power_w=200, cadence_rpm=85, posture="FLUIDE", gear=6,
                            ftp_w=250, s_m=100, v_mps=8, contact=True), room, B, 0.5)
    assert "defeat" in ev and state.phase == DONE and state.outcome == "boss_fled"


def test_armor_by_posture():
    room = generate_room("diesel", "", "threshold", 240.0, RIDER, 1)
    losses = {}
    for posture in ("ROC", "FLUIDE", "VELOCE"):
        st = combat_start(room, 1)
        st, _ = combat_step(st, CombatInputs(power_w=0, cadence_rpm=60, posture=posture, gear=6, ftp_w=250,
                                             s_m=50, v_mps=5, contact=True), room, B, 1.0)
        losses[posture] = B.shield_max - st.shield
    assert losses["ROC"] == pytest.approx(2.8) and losses["FLUIDE"] == pytest.approx(4.0)
    assert losses["VELOCE"] == pytest.approx(4.8)


def test_perfect_shift_window_and_direction():
    room = generate_room("puncheur", "", "vo2max", 300.0, RIDER, 1)
    arch = next(m for m in room.markers if m.kind == "arch" and m.param == "up")

    def shift(offset_s, gear_from, gear_to, v=8.0):
        st = replace(combat_start(room, 1, gear=gear_from), prev_gear=gear_from)
        inp = CombatInputs(power_w=200, cadence_rpm=85, posture="FLUIDE", gear=gear_to, ftp_w=250,
                           s_m=arch.s_m - offset_s * v, v_mps=v)
        return combat_step(st, inp, room, B, DT)

    st, ev = shift(0.7, 6, 7)
    assert "perfect_shift" in ev and st.perfect_shifts == 1 and st.adrenaline >= 10
    assert "perfect_shift" not in shift(0.8, 6, 7)[1]
    assert "perfect_shift" not in shift(0.3, 6, 5)[1]            # mauvais sens
    st2, ev2 = shift(0.1, 6, 7)
    # le même Perfect Shift ne compte qu'une fois
    st2, ev3 = combat_step(replace(st2, prev_gear=6), CombatInputs(power_w=200, cadence_rpm=85, posture="FLUIDE",
                           gear=7, ftp_w=250, s_m=arch.s_m, v_mps=8), room, B, DT)
    assert "perfect_shift" not in ev3


def test_gear_buttons():
    assert apply_gear_buttons(8, {"MINUS_LONG"}, None, None) == 5
    assert apply_gear_buttons(2, {"MINUS_LONG"}, None, None) == 1
    assert apply_gear_buttons(11, {"PLUS_LONG"}, None, None) == 12
    assert apply_gear_buttons(6, {"PLUS_SHORT"}, None, None) == 7
    assert apply_gear_buttons(6, {"PLUS_SHORT", "Y", "A_SHORT"}, "blocked", None) == 6
    assert apply_gear_buttons(6, {"PLUS_SHORT"}, "forced_gear", 3) == 3
    assert apply_gear_buttons(6, {"Y", "A_SHORT", "A_LONG", "Z_SHORT"}, None, None) == 6


def test_strike_needs_adrenaline_and_consumes_it():
    room = generate_room("boss", "phase1", "threshold", 210.0, RIDER, 1)
    lock = next(m for m in room.markers if m.kind == "strike_target")
    base = dict(power_w=0, cadence_rpm=85, posture="FLUIDE", gear=6, ftp_w=250, s_m=lock.s_m, v_mps=8,
                buttons=frozenset({"Z_SHORT"}))
    st = combat_start(room, 1)
    low, ev = combat_step(replace(st, adrenaline=40.0), CombatInputs(**base), room, B, DT)
    assert ev == () and low.enemy_hp == st.enemy_hp
    hit, ev = combat_step(replace(st, adrenaline=60.0), CombatInputs(**base), room, B, DT)
    assert "hit" in ev and hit.adrenaline == pytest.approx(10.0)
    assert st.enemy_hp - hit.enemy_hp == pytest.approx(0.06 * st.enemy_hp_max)


def test_diesel_tunnel_charges_released_by_z():
    room = generate_room("diesel", "", "threshold", 240.0, RIDER, 1)
    tun = next(m for m in room.markers if m.kind == "tunnel")
    strike = next(m for m in room.markers if m.kind == "strike_target")
    st = combat_start(room, 1)
    for _ in range(round(21 / DT)):
        st, _ = combat_step(st, CombatInputs(power_w=0, cadence_rpm=91, posture="FLUIDE", gear=6, ftp_w=250,
                                             s_m=tun.s_m + 1.0, v_mps=0.0), room, B, DT)
    assert st.charges == 2
    st, ev = combat_step(st, CombatInputs(power_w=0, cadence_rpm=91, posture="FLUIDE", gear=6, ftp_w=250,
                                          s_m=strike.s_m, v_mps=8.0, buttons=frozenset({"Z_SHORT"})), room, B, DT)
    assert "hit" in ev and st.charges == 0 and st.adrenaline == 0
    assert st.enemy_hp_max - st.enemy_hp == pytest.approx(0.08 * st.enemy_hp_max, rel=1e-6)


def test_grimpeur_rock_needs_charges():
    room = generate_room("grimpeur", "", "threshold", 300.0, RIDER, 1)
    rock = next(m for m in room.markers if m.kind == "rock")
    st = combat_start(room, 1)
    for _ in range(round(11 / DT)):
        st, _ = combat_step(st, CombatInputs(power_w=0, cadence_rpm=60, posture="ROC", gear=6, ftp_w=250,
                                             s_m=0.0, v_mps=0.0), room, B, DT)
    assert st.roc_charges == 2
    z = CombatInputs(power_w=0, cadence_rpm=60, posture="ROC", gear=6, ftp_w=250, s_m=rock.s_m, v_mps=5.0,
                     buttons=frozenset({"Z_SHORT"}))
    st, ev = combat_step(st, z, room, B, DT)
    assert ev == () and st.roc_charges == 1
    st, ev = combat_step(st, z, room, B, DT)
    assert "hit" in ev and st.roc_charges == 0
    assert st.enemy_hp_max - st.enemy_hp == pytest.approx(0.08 * st.enemy_hp_max, rel=1e-6)


def test_sprinter_pad_triples_damage():
    room = generate_room("sprinteur", "", "vo2max", 200.0, RIDER, 1)
    pad = next(m for m in room.markers if m.kind == "pad")
    base = dict(cadence_rpm=100, posture="FLUIDE", ftp_w=250, s_m=pad.s_m + 1, v_mps=12)
    st = combat_start(room, 1)
    on, _ = combat_step(st, CombatInputs(power_w=400, gear=10, **base), room, B, 1.0)
    low_gear, _ = combat_step(st, CombatInputs(power_w=400, gear=9, **base), room, B, 1.0)
    weak, _ = combat_step(st, CombatInputs(power_w=300, gear=10, **base), room, B, 1.0)
    assert st.enemy_hp - on.enemy_hp == pytest.approx(1.6 * 1.16 * 3)
    assert st.enemy_hp - low_gear.enemy_hp == pytest.approx(1.6 * 1.12)
    assert st.enemy_hp - weak.enemy_hp == pytest.approx(1.2 * 1.16)


def test_saboteur_hack_blocks_and_purge_cancels_without_attack():
    room = generate_room("saboteur", "", "threshold", 300.0, RIDER, 1)
    purge = next(m for m in room.markers if m.kind == "purge")
    st = combat_start(room, 1)
    base = dict(power_w=200, cadence_rpm=85, posture="FLUIDE", gear=6, ftp_w=250, v_mps=8)
    st, _ = combat_step(replace(st, adrenaline=80.0), CombatInputs(s_m=purge.s_m - 80, **base), room, B, DT)
    assert st.hack_kind in ("blocked", "forced_gear")
    hp = st.enemy_hp
    st, ev = combat_step(st, CombatInputs(s_m=purge.s_m, buttons=frozenset({"Z_SHORT"}), **base), room, B, DT)
    assert st.hack_kind is None and "hit" not in ev and st.adrenaline >= 79.9
    assert hp - st.enemy_hp < 0.01 * st.enemy_hp_max
    # sans purge, le piratage expire
    st = combat_start(room, 1)
    st, _ = combat_step(st, CombatInputs(s_m=purge.s_m - 80, **base), room, B, DT)
    st, _ = combat_step(replace(st, t_s=st.t_s + B.hack_max_s + 1), CombatInputs(s_m=purge.s_m - 79, **base), room, B, DT)
    assert st.hack_kind is None


def test_parry_boss_wave_and_puncheur_hook():
    room = generate_room("boss", "phase2", "threshold", 300.0, RIDER, 1)
    zones = [m for m in room.markers if m.kind == "parry_zone"]
    base = dict(power_w=0, cadence_rpm=85, posture="FLUIDE", gear=6, ftp_w=250, v_mps=8)
    st = combat_start(room, 1)
    st1, ev = combat_step(st, CombatInputs(s_m=zones[0].s_m + 1, buttons=frozenset({"Z_SHORT"}), **base), room, B, DT)
    assert "parry" in ev and st1.adrenaline == st.adrenaline and st1.enemy_hp == st.enemy_hp
    st2, ev = combat_step(st1, CombatInputs(s_m=zones[0].s_m + zones[0].len_m + 1, **base), room, B, DT)
    assert "parry_miss" not in ev and st2.shield == st.shield
    st3, ev = combat_step(st, CombatInputs(s_m=zones[0].s_m + zones[0].len_m + 1, **base), room, B, DT)
    assert "parry_miss" in ev and st3.shield == st.shield - B.unparried_hit

    pun = generate_room("puncheur", "", "vo2max", 300.0, RIDER, 1)
    zone = next(m for m in pun.markers if m.kind == "parry_zone")
    tgt = target_at(pun, zone.s_m) * 250
    st = replace(combat_start(pun, 1), bins=(100.0, 100.0, 100.0, 200.0, 200.0))
    st, ev = combat_step(st, CombatInputs(s_m=zone.s_m + 1, buttons=frozenset({"Z_SHORT"}), **{**base, "power_w": 200}),
                         pun, B, DT)
    assert "parry" in ev
    st, ev = combat_step(st, CombatInputs(s_m=zone.s_m + zone.len_m + 1, **{**base, "power_w": 0}), pun, B, DT)
    assert st.grade_scale == B.hook_grade_mult and st.shield == B.shield_max
    # pas d'aspiration et effort sous la cible : −10
    weak = replace(combat_start(pun, 1), bins=(150.0,) * 5)
    weak, ev = combat_step(weak, CombatInputs(s_m=zone.s_m + zone.len_m + 1, **{**base, "power_w": tgt * 0.5}), pun, B, DT)
    assert "parry_miss" in ev and weak.shield == B.shield_max - B.unparried_hit


def test_z_outside_markers_and_other_buttons_do_nothing():
    room = generate_room("diesel", "", "threshold", 240.0, RIDER, 1)
    st = replace(combat_start(room, 1), adrenaline=90.0)
    base = dict(power_w=0, cadence_rpm=85, posture="ARRET", gear=6, ftp_w=250, s_m=5.0, v_mps=8)
    for button in ("Z_SHORT", "Z_LONG", "Y", "A_SHORT", "A_LONG"):
        new, ev = combat_step(st, CombatInputs(buttons=frozenset({button}), **base), room, B, DT)
        assert ev == () and new.adrenaline == 90.0 and new.enemy_hp == st.enemy_hp


def test_overheat_only_in_endurance():
    room = generate_room("diesel", "", "endurance", 240.0, RIDER, 1)
    for objective, expected in (("endurance", True), ("threshold", False)):
        st = replace(combat_start(room, 1), adrenaline=50.0)
        for _ in range(round(12 / DT)):
            st, _ = combat_step(st, CombatInputs(power_w=200, cadence_rpm=85, posture="FLUIDE", gear=6,
                                                 ftp_w=250, s_m=10.0, v_mps=8, objective=objective), room, B, DT)
        assert st.overheat is expected
        assert (st.adrenaline < 50.0) is expected
    st = replace(combat_start(room, 1), adrenaline=50.0)
    for _ in range(round(4 / DT)):
        st, _ = combat_step(st, CombatInputs(power_w=200, cadence_rpm=85, posture="FLUIDE", gear=6, ftp_w=250,
                                             s_m=10.0, v_mps=8, objective="endurance"), room, B, DT)
    assert not st.overheat


def test_constants_come_from_balance():
    room = generate_room("diesel", "", "threshold", 240.0, RIDER, 1)
    inp = CombatInputs(power_w=250, cadence_rpm=85, posture="FLUIDE", gear=6, ftp_w=250, s_m=10.0, v_mps=8)
    a, _ = combat_step(combat_start(room, 1), inp, room, B, 1.0)
    weaker = replace(B, hp_factor_threshold=B.hp_factor_threshold / 2)
    b, _ = combat_step(combat_start(room, 1, weaker), inp, room, weaker, 1.0)
    assert b.enemy_hp_max == pytest.approx(a.enemy_hp_max / 2)
    gear12 = replace(B, gear_step=0.1)
    c, _ = combat_step(combat_start(room, 1, gear12, gear=12), replace(inp, gear=12), room, gear12, 1.0)
    d, _ = combat_step(combat_start(room, 1, B, gear=12), replace(inp, gear=12), room, B, 1.0)
    assert (c.enemy_hp_max - c.enemy_hp) > (d.enemy_hp_max - d.enemy_hp)
