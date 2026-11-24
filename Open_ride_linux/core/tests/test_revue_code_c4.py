"""Revue de code, vague 2, lot C4 (constats C4-01, C4-02, C4-03, C4-05) : Cyber-Rogue et WTF.

- C4-01 : le Firewall des phases 2 et 3 du boss part `start_gap_m` derrière le joueur, pas collé à lui ;
- C4-02 : la bosse « aspirée » du Puncheur adoucit vraiment la pente envoyée (`grade_scale`) ;
- C4-03 : le pignon imposé du Saboteur s'applique sans appui, puis le braquet d'avant revient, sans Perfect Shift ;
- C4-05 : WTF, un seul fromage géant par descente.
"""

from __future__ import annotations

from dataclasses import replace

from openride_core.config import Config
from openride_core.physics import PhysicsParams, RiderPhysics
from openride_core.rogue.balance import DEFAULT_BALANCE as B
from openride_core.rogue.combat import CombatInputs, combat_start, combat_step
from openride_core.rogue.mode import RogueMode, parse_start_run
from openride_core.rogue.rooms import RoomRider, generate_room
from openride_core.rogue.run import RunEngine, RunInputs, Scenario, Step
from openride_core.wtf.mode import WtfInput, WtfMode
from openride_core.wtf.rules import WtfTable

RIDER = RoomRider(ftp_w=250.0, params=PhysicsParams(mass_kg=84.0, cda_m2=0.32))
DT = 0.05
FIGHT = ("ROOM", "BOSS", "RECOVERY")


# --- C4-01 : Firewall au début des phases 2 et 3 du boss ---------------------------------------

def test_firewall_starts_behind_the_rider_in_every_boss_phase():
    steps = (Step("warmup", 1.0), Step("corridor", 5.0), Step("boss", 40.0, "boss", "phase1", "threshold"),
             Step("boss", 40.0, "boss", "phase2", "threshold"), Step("boss", 40.0, "boss", "phase3", "threshold"),
             Step("cooldown", 5.0))
    e = RunEngine(Scenario("threshold", 30, 1, steps), RIDER, 20000.0, 250.0, B)
    s, rid, v, starts, min_gap = 0.0, None, 9.0, {}, {}
    for _ in range(round(200 / DT)):
        fight = e.room is not None and e.phase in FIGHT
        out = e.step(DT, RunInputs(power_w=260, cadence_rpm=85, gear=6, ftp_w=250, s_m=s if fight else 0.0,
                                   v_mps=v, buttons=frozenset(), power_avg_w=260))
        new = e.room_id != rid
        if new and e.firewall is not None:
            starts[e.boss_phase] = (s, e.firewall.body.s)
        if new or not (e.room is not None and e.phase in FIGHT):
            s = 0.0                                        # comme `RogueMode.step` : chaque salle commence à 0 m
        else:
            s += v * DT
        if e.firewall is not None and e.boss_phase:
            min_gap[e.boss_phase] = min(min_gap.get(e.boss_phase, 1e9), e.firewall.state.gap_m)
        rid = e.room_id
        if out.finished:
            break
    assert set(starts) == {1, 2, 3}
    assert starts[2][0] > 100.0 and starts[3][0] > 100.0  # la phase d'avant a bien fini loin du départ
    for phase, (_, wall_s) in starts.items():
        assert wall_s == -B.start_gap_m, phase             # le mur part derrière la ligne de départ de la salle
    assert min(min_gap.values()) > 0.5 * B.start_gap_m      # à puissance égale, jamais de contact


# --- C4-02 : bosse aspirée -------------------------------------------------------------------

def _puncheur_engine():
    steps = (Step("warmup", 1.0), Step("room", 200.0, "puncheur", "", "vo2max"), Step("corridor", 10.0),
             Step("cooldown", 10.0))
    e = RunEngine(Scenario("vo2max", 30, 3, steps), RIDER, 20000.0, 250.0, B)
    for _ in range(round(1.2 / DT)):
        e.step(DT, RunInputs(power_w=150, cadence_rpm=85, gear=6, ftp_w=250))
    assert e.phase == "ROOM"
    return e


def test_hooked_bump_halves_the_enemy_grade():
    e = _puncheur_engine()
    s = max(e.room.profile, key=lambda p: p[1])[0]          # sommet de la pente de la salle
    raw = e._raw_grade(e.room, s)
    assert raw > 2.0
    inp = RunInputs(power_w=200, cadence_rpm=85, gear=6, ftp_w=250, s_m=s, v_mps=8.0, buttons=frozenset(),
                    power_avg_w=200)
    e.combat = replace(e.combat, grade_scale=B.hook_grade_mult, hook_until_s=e.combat.t_s + 10.0)
    hooked = e.step(DT, inp)
    assert hooked.grade_enemy == raw * B.hook_grade_mult
    e.combat = replace(e.combat, grade_scale=1.0)
    plain = e.step(DT, replace(inp, s_m=s + 0.4))
    assert plain.grade_enemy == e._raw_grade(e.room, s + 0.4)


# --- C4-03 : pignon imposé du Saboteur --------------------------------------------------------

def test_forced_gear_change_is_not_a_player_shift():
    room = generate_room("saboteur", "", "threshold", 300.0, RIDER, 1)
    base = dict(power_w=200, cadence_rpm=85, posture="FLUIDE", ftp_w=250, v_mps=8, s_m=50.0)
    st = combat_start(room, 1, gear=6)
    st = replace(st, hack_kind="forced_gear", forced_gear=3, hack_t_s=st.t_s)
    st, ev = combat_step(st, CombatInputs(gear=6, **base), room, B, DT)       # début : braquet imposé
    assert st.gear == 3 and st.shift_t_s == combat_start(room, 1).shift_t_s and "perfect_shift" not in ev
    st, _ = combat_step(st, CombatInputs(gear=3, **base), room, B, DT)        # le mode a pris le pignon imposé
    st = replace(st, t_s=st.t_s + B.hack_max_s + 1)
    st, _ = combat_step(st, CombatInputs(gear=3, **base), room, B, DT)        # expiration
    assert st.hack_kind is None
    t0 = st.shift_t_s
    st, _ = combat_step(st, CombatInputs(gear=6, **base), room, B, DT)        # retour au braquet d'avant
    assert st.shift_t_s == t0                                                 # pas un changement du joueur
    st, _ = combat_step(st, CombatInputs(gear=7, **base), room, B, DT)        # un vrai appui compte
    assert st.shift_t_s > t0


def test_rogue_mode_applies_and_releases_the_forced_gear_without_buttons():
    cfg = Config()
    mode = RogueMode(cfg, parse_start_run({"objective": "threshold", "duration_min": 30, "seed": 5}, cfg))
    body = RiderPhysics(mode.rider.params)
    dt, t = 0.02, 0.0
    while not mode.in_fight:
        mode.step(dt, 250.0, 90.0, body, False, t)
        t += dt
        assert t < 1200.0
    mode.target_grade(5.0, 5.0, dt)
    assert mode.gear == 6
    e = mode.engine
    e.combat = replace(e.combat, hack_kind="forced_gear", forced_gear=3, hack_t_s=e.combat.t_s)
    mode.step(dt, 250.0, 90.0, body, False, t)
    assert mode.gear == 3                                   # sans aucun appui
    assert mode.shift("PLUS_SHORT") and mode.gear == 3      # appui refusé pendant le piratage
    e.combat = replace(e.combat, hack_kind=None, forced_gear=None)            # purge
    mode.step(dt, 250.0, 90.0, body, False, t + dt)
    assert mode.gear == 6 and mode.gear_before_hack is None


# --- C4-05 : WTF, un fromage par descente --------------------------------------------------------

def _ride(mode, state, seconds, grade):
    for _ in range(round(seconds / 0.02)):
        state["t"] += 0.02
        state["s"] += 12.0 * 0.02
        mode.step(WtfInput(state["t"], 0.02, state["s"], 12.0, 150.0, 90.0, grade, True))


def test_one_cheese_per_descent_then_other_gags():
    mode = WtfMode(WtfTable(frozenset({"cheese", "eggs", "upside_down", "micro"})), 250.0,
                   PhysicsParams(mass_kg=80.0), seed=1)
    state = {"t": 0.0, "s": 0.0}
    _ride(mode, state, 600.0, -5.0)                        # 10 min de descente à −5 %
    events = [ln["event"] for ln in mode.played]
    assert events.count("cheese") == 1
    assert len(events) > 3                                  # les autres gags sortent ensuite
    _ride(mode, state, 1.0, 0.0)                            # bosse courte : même descente
    _ride(mode, state, 60.0, -5.0)
    assert [ln["event"] for ln in mode.played].count("cheese") == 1
    _ride(mode, state, 10.0, 0.0)                           # vraie sortie de la descente
    _ride(mode, state, 80.0, -5.0)
    assert [ln["event"] for ln in mode.played].count("cheese") == 2
