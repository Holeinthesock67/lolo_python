"""Lot R6 : machine à états de la run, couloirs, deck, boss."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import jsonschema
import pytest

from openride_core.physics import PhysicsParams, RiderPhysics
from openride_core.rogue import cards as cardlib
from openride_core.rogue.balance import DEFAULT_BALANCE
from openride_core.rogue.combat import target_at
from openride_core.rogue.run import RunEngine, RunInputs, Scenario, Step, grade_sent
from openride_core.rogue.rooms import RoomRider

RIDER = RoomRider(ftp_w=250.0, params=PhysicsParams(mass_kg=84.0, cda_m2=0.32))
B = DEFAULT_BALANCE
DT = 0.05
SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "docs/contracts/ipc/state.schema.json").read_text())
ROGUE_SCHEMA = SCHEMA["properties"]["rogue"]
SUMMARY_SCHEMA = SCHEMA["properties"]["summary"]["properties"]["rogue"]


def room(a, nominal=120.0, objective="threshold", variant=""):
    return Step("room", nominal, a, variant, objective)


def scenario(first="diesel", doors=("puncheur", "grimpeur"), boss_s=(70.0, 80.0, 60.0), warmup=200.0,
             corridor=20.0, cooldown=30.0, objective="threshold", seed=3):
    d = tuple(room(a, 100.0, "vo2max" if a == "puncheur" else objective) for a in doors)
    steps = [Step("warmup", warmup), room(first, 100.0, objective),
             Step("corridor", corridor, doors=d), Step("corridor", corridor)]
    steps += [Step("boss", s, "boss", f"phase{i + 1}", objective) for i, s in enumerate(boss_s)]
    steps += [Step("cooldown", cooldown)]
    return Scenario(objective, 30, seed, tuple(steps))


class Rider:
    """Cycliste simulé : tient la cible en salle (à `power_mult` près), 0,6 FTP ailleurs."""

    def __init__(self, engine, power_mult=1.0, gear=6, cadence=85.0, script=None):
        self.e, self.mult, self.gear, self.cad, self.script = engine, power_mult, gear, cadence, script or {}
        self.body = RiderPhysics(RIDER.params)
        self.room_id = None
        self.t = 0.0
        self.phases, self.messages, self.events, self.outs = [], [], [], []

    def run(self, max_s=4000.0):
        e = self.e
        out = None
        while self.t < max_s:
            if e.room is not None and e.room_id != self.room_id:
                self.room_id = e.room_id
                self.body = RiderPhysics(RIDER.params)
            in_room = e.room is not None and e.phase in ("ROOM", "BOSS")
            power = target_at(e.room, self.body.s) * RIDER.ftp_w * self.mult if in_room else 0.6 * RIDER.ftp_w
            buttons = frozenset(self.script.get(round(self.t / DT), ()))
            inp = RunInputs(power_w=power, cadence_rpm=self.cad, gear=self.gear, ftp_w=RIDER.ftp_w,
                            s_m=self.body.s if e.room is not None else 0.0, v_mps=self.body.v, buttons=buttons)
            out = e.step(DT, inp)
            if out.force_gear:
                self.gear = out.force_gear
            self.body.step(power, out.grade_enemy, 0.0, DT)
            if not self.phases or self.phases[-1] != out.phase:
                self.phases.append(out.phase)
            self.messages += out.messages
            self.events += out.rogue["events"]
            self.outs.append(out)
            if len(self.outs) % 40 == 1:
                jsonschema.validate(out.rogue, ROGUE_SCHEMA)
            self.t += DT
            if out.finished:
                break
        return out


def engine(sc=None, **kw):
    return RunEngine(sc or scenario(**kw), RIDER, 20000.0, 250.0, B)


def test_full_run_passes_through_all_phases():
    e = engine()
    r = Rider(e)
    out = r.run()
    assert out.finished
    assert r.phases == ["WARMUP", "ROOM", "CORRIDOR", "ROOM", "CORRIDOR", "BOSS", "COOLDOWN", "RESULTS"]
    summary = e.summary()
    jsonschema.validate(summary, SUMMARY_SCHEMA)
    assert summary["result"] == "victory" and summary["boss"] == "won"
    assert summary["rooms_won"] + summary["rooms_fled"] == 2 and summary["rooms_total"] == 2
    kinds = [m["type"] for m in r.messages]
    assert kinds.count("room") >= 1 + 2 + 3 and kinds.count("loot") >= 2
    assert max(o.rogue["boss_phase"] or 0 for o in r.outs) == 3


def test_relic_offered_at_third_minute():
    e = engine()
    r = Rider(e, script={})
    r.script = {round(181.0 / DT): ("A_SHORT",), round(182.0 / DT): ("A_LONG",)}
    r.run(max_s=190.0)
    assert "card_taken" in r.events and len(e.relics) == 1
    loot = [m for m in r.messages if m["type"] == "loot"][0]
    assert all(c["kind"] == "relic" for c in loot["cards"])


def corridor_script(start_t, presses):
    """Boutons dans le couloir qui commence à `start_t` (s) : [(décalage, bouton)]."""
    return {round((start_t + dt) / DT): (b,) for dt, b in presses}


def test_corridor_without_input_takes_no_card_and_left_door():
    e = engine()
    r = Rider(e)
    r.run()
    assert e.deck == () and e.summary()["cards"] == []
    first_door = next(m for m in r.messages if m["type"] == "loot" and m["cards"][0]["kind"] != "relic")
    left = first_door["doors"][0]
    played = [o.rogue["archetype"] for o in r.outs if o.phase == "ROOM"]
    assert left["archetype"] == "puncheur" and "puncheur" in played and "grimpeur" not in played


def run_to_corridor(e, r):
    """Avance la simulation jusqu'au premier couloir ; renvoie l'instant d'entrée."""
    while e.phase != "CORRIDOR" and r.t < 2000:
        r.run(max_s=r.t + DT)
    return r.t


def test_corridor_pick_card_and_right_door():
    e = engine()
    r = Rider(e)
    t0 = run_to_corridor(e, r)
    r.script = corridor_script(t0, [(1, "A_SHORT"), (2, "A_LONG"), (3, "A_SHORT"), (4, "A_SHORT"), (5, "A_LONG")])
    r.run(max_s=t0 + 7)
    assert len(e.deck) == 1 and "card_taken" in r.events
    out = r.outs[-1]
    assert out.rogue["loot_focus"] is None and e.door_pick == 1
    r.run(max_s=t0 + 22)
    assert r.outs[-1].rogue["archetype"] == "grimpeur"


def test_reroll_costs_and_needs_gold():
    e = engine()
    r = Rider(e)
    t0 = run_to_corridor(e, r)
    e.gold = 40.0
    r.script = corridor_script(t0, [(1, "Z_SHORT"), (2, "Z_SHORT"), (3, "Z_SHORT")])
    r.run(max_s=t0 + 5)
    assert e.rerolls == 2 and e.gold == pytest.approx(40 - 15 - 20)
    loot = [m for m in r.messages if m["type"] == "loot"][-1]
    assert loot["reroll_cost"] == 25 and loot["gold"] == 5


def test_cards_catalogue_and_deck_rules():
    deck = cardlib.deck_add((), "overdrive")
    deck = cardlib.deck_add(deck, "heal")
    deck = cardlib.deck_add(deck, "cursed")
    assert set(deck) == {"overdrive", "heal", "cursed"}
    again = cardlib.deck_add(deck, "overdrive")
    assert again.count("overdrive") == 1
    assert cardlib.deck_add(cardlib.deck_add((), "polarity"), "polarity") == ("polarity",)
    for cid, c in cardlib.CARDS.items():
        assert c.name and len(c.text) <= 120 and len(c.id) <= 24 and len(c.name) <= 32
    assert cardlib.draw("a", 3, ()) == cardlib.draw("a", 3, ())
    assert not set(cardlib.draw("a", 3, ("roller", "heal"))) & {"roller", "heal"}


def fight_engine(first="grimpeur", objective="threshold", deck=(), relics=(), seed=3):
    steps = (Step("warmup", 1.0), room(first, 200.0, objective), Step("corridor", 10.0),
             Step("boss", 60.0, "boss", "phase1", objective), Step("cooldown", 10.0))
    e = RunEngine(Scenario(objective, 30, seed, steps), RIDER, 20000.0, 250.0, B)
    e.deck, e.relics = tuple(deck), tuple(relics)
    inp = RunInputs(power_w=150, cadence_rpm=85, gear=6, ftp_w=250)
    for _ in range(round(1.2 / DT)):
        out = e.step(DT, inp)
    assert e.phase == "ROOM"
    return e


def step_in_room(e, s, gear=6, cadence=85.0, power=200.0, buttons=(), v=8.0, n=1):
    out = None
    for _ in range(n):
        out = e.step(DT, RunInputs(power_w=power, cadence_rpm=cadence, gear=gear, ftp_w=250, s_m=s, v_mps=v,
                                   buttons=frozenset(buttons)))
    return out


def test_grade_sent_never_leaves_trainer_range():
    for g in range(-10, 14):
        for gear in range(1, 13):
            assert -10.0 <= grade_sent(float(g), gear, B) <= 16.0
    assert grade_sent(5.0, 6) == 5.0 and grade_sent(5.0, 12) == 11.0 and grade_sent(-9.0, 1) == -10.0
    e = fight_engine(deck=("overdrive", "roller"))
    for gear in (1, 6, 12):
        out = step_in_room(e, 400.0, gear=gear)
        assert -10.0 <= out.grade_sent <= 16.0


def test_roller_clips_at_6_and_holds_3_s():
    e = fight_engine(first="grimpeur", objective="threshold", deck=("roller",))
    steep = next(s for s, g in e.room.profile if g >= 9.9)
    out = step_in_room(e, steep)
    assert out.grade_enemy == pytest.approx(6.0)
    flat = next(s for s, g in e.room.profile if g < 5.0)
    out = step_in_room(e, flat)
    assert out.grade_enemy == pytest.approx(6.0)                     # tenu 3 s après la pente
    out = step_in_room(e, flat, n=round(3.2 / DT))
    assert out.grade_enemy < 6.0


def test_overdrive_effect_and_automatic_return():
    e = fight_engine(deck=("overdrive",))
    base = step_in_room(e, 300.0, gear=11)
    g0 = base.grade_enemy
    out = step_in_room(e, 300.0, gear=12)
    assert out.grade_enemy == pytest.approx(g0 + 4.0)
    step_in_room(e, 300.0, gear=12)
    out = step_in_room(e, 300.0, gear=12, n=round(8.2 / DT))
    assert out.force_gear is None or out.force_gear == 6
    step_in_room(e, 300.0, gear=12, n=round(1 / DT))
    again = step_in_room(e, 300.0, gear=12)                           # recharge 45 s : pas de nouvel effet
    assert again.grade_enemy == pytest.approx(g0)


def test_overdrive_force_gear_returned_once():
    e = fight_engine(deck=("overdrive",))
    forced = []
    for _ in range(round(10 / DT)):
        o = step_in_room(e, 300.0, gear=12)
        if o.force_gear:
            forced.append(o.force_gear)
    assert forced == [6]


def test_heal_only_in_gear_1_above_95_rpm():
    e = fight_engine(deck=("heal",))
    e.shield = 50.0
    e.combat = replace(e.combat, shield=50.0)
    step_in_room(e, 300.0, gear=1, cadence=100.0, n=round(10 / DT))
    assert e.shield == pytest.approx(60.0, abs=0.5)
    step_in_room(e, 300.0, gear=2, cadence=100.0, n=round(5 / DT))
    step_in_room(e, 300.0, gear=1, cadence=90.0, n=round(5 / DT))
    assert e.shield == pytest.approx(60.0, abs=0.5)


def test_cursed_boosts_damage_and_blocks_z():
    plain = fight_engine()
    cursed = fight_engine(deck=("cursed",))
    for eng, gear in ((plain, 10), (cursed, 10)):
        step_in_room(eng, 300.0, gear=gear, power=250.0, n=round(1 / DT))
    d_plain = plain.combat.enemy_hp_max - plain.combat.enemy_hp
    d_cursed = cursed.combat.enemy_hp_max - cursed.combat.enemy_hp
    assert d_cursed / d_plain == pytest.approx(1.35, rel=0.01)
    strike = fight_engine(first="grimpeur", deck=("cursed",))
    m = next(m for m in strike.room.markers if m.kind == "strike_target")
    strike.combat = replace(strike.combat, adrenaline=80.0)
    out = step_in_room(strike, m.s_m, gear=10, buttons=("Z_SHORT",))
    assert "hit" not in out.rogue["events"] and strike.combat.adrenaline >= 80.0
    out = step_in_room(strike, m.s_m, gear=9, buttons=("Z_SHORT",))
    assert "hit" in out.rogue["events"]


def test_shifter_and_relics():
    e = fight_engine(deck=("shifter",), relics=("relic_window", "relic_shield"))
    bx = e._eff_balance()
    assert bx.ps_window_s == pytest.approx(3.0) and bx.shield_max == 120.0     # (1,5 + 0,3) × 2 plafonné à 3 s
    e = fight_engine(deck=("shifter",), relics=("relic_window",) * 1)
    assert e._eff_balance().ps_window_s == pytest.approx(3.0)       # plafonné à 3 s
    arch = next(m for m in e.room.markers if m.kind == "arch")
    e.shield = 80.0
    e.combat = replace(e.combat, shield=80.0, prev_gear=6)
    prev = arch.param
    gear = 7 if prev == "up" else 5
    out = step_in_room(e, arch.s_m, gear=gear)
    assert "perfect_shift" in out.rogue["events"] and e.shield == pytest.approx(83.0, abs=0.1)
    e = fight_engine(relics=("relic_gold",))
    assert e._gold_mult() == 1.25


def test_polarity_inverts_once_per_room_bounded():
    e = fight_engine(deck=("polarity",))
    steep = next(s for s, g in e.room.profile if g >= 6.0)
    base = step_in_room(e, steep).grade_enemy
    out = step_in_room(e, steep, buttons=("Z_LONG",))
    assert out.grade_enemy == pytest.approx(max(-base, -3.0)) and out.grade_enemy >= -3.0
    step_in_room(e, steep, n=round(8.2 / DT))
    out = step_in_room(e, steep, buttons=("Z_LONG",))
    assert out.grade_enemy == pytest.approx(base)                     # une seule fois par salle


def test_springboard_after_descent():
    e = fight_engine(first="puncheur", objective="vo2max", deck=("springboard",))
    down = next(s for s, g in e.room.profile if g <= -1.0)
    up = next(s for s, g in e.room.profile if g > 3.0 and s > down)
    step_in_room(e, down, gear=9, n=round(2.5 / DT))                  # posture Fluide installée
    e.combat = replace(e.combat, adrenaline=0.0)
    step_in_room(e, up, gear=9)
    assert e.combat.adrenaline >= 15.0 - 1.0
    hp = e.combat.enemy_hp
    step_in_room(e, up, gear=9, power=250.0, n=round(1 / DT))
    boosted = hp - e.combat.enemy_hp
    step_in_room(e, up, gear=9, power=250.0, n=round(6 / DT))
    hp = e.combat.enemy_hp
    step_in_room(e, up, gear=9, power=250.0, n=round(1 / DT))
    assert boosted / (hp - e.combat.enemy_hp) == pytest.approx(1.5, rel=0.1)


def test_siphon_on_hooked_bump():
    e = fight_engine(first="puncheur", objective="vo2max", deck=("siphon",))
    zone = next(m for m in e.room.markers if m.kind == "parry_zone")
    e.combat = replace(e.combat, bins=(100.0, 100.0, 100.0, 200.0, 200.0), adrenaline=0.0)
    out = step_in_room(e, zone.s_m + 1, buttons=("Z_SHORT",))
    assert "parry" in out.rogue["events"] and e.combat.adrenaline >= 49.0


def test_defeat_during_boss_goes_to_cooldown():
    steps = (Step("warmup", 1.0), Step("corridor", 5.0), Step("boss", 60.0, "boss", "phase1", "threshold"),
             Step("boss", 60.0, "boss", "phase2", "threshold"), Step("boss", 60.0, "boss", "phase3", "threshold"),
             Step("cooldown", 5.0))
    e = RunEngine(Scenario("threshold", 30, 1, steps), RIDER, 20000.0, 250.0, B)
    phases = []
    for _ in range(round(300 / DT)):
        out = e.step(DT, RunInputs(power_w=0, cadence_rpm=85, gear=6, ftp_w=250, s_m=5.0, v_mps=3.0,
                                   buttons=frozenset()))
        if e.firewall is not None:
            e.firewall.body.s = 5.0 - 0.0           # le mur colle au joueur : défaite rapide
            e.firewall.step(0.0, 5.0)
        if not phases or phases[-1] != out.phase:
            phases.append(out.phase)
        if out.finished:
            break
    assert e.defeats == 1 and e.summary()["boss"] == "fled"          # une seule défaite : le boss s'enfuit
    assert "COOLDOWN" in phases and "RECOVERY" not in phases and e.rooms_started == 1


def test_snapshot_restore_midroom_identical_continuation():
    sc = scenario()
    a = engine(sc)
    ra = Rider(a)
    ra.run(max_s=260.0)                                  # milieu de la première salle
    snap = a.snapshot()
    body_state = (ra.body.s, ra.body.v)
    ra.run(max_s=700.0)
    tail_a = [(o.phase, round(o.grade_sent, 6), o.rogue["enemy_hp"], o.rogue["gold"]) for o in ra.outs[-400:]]
    b = engine(sc)
    b.restore(snap)
    rb = Rider(b)
    rb.t = 260.0
    rb.body = RiderPhysics(RIDER.params, *body_state)
    rb.room_id = b.room_id
    rb.run(max_s=700.0)
    tail_b = [(o.phase, round(o.grade_sent, 6), o.rogue["enemy_hp"], o.rogue["gold"]) for o in rb.outs[-400:]]
    assert tail_a == tail_b
    assert a.summary() == b.summary()


def test_abandon_gives_abandoned_summary():
    e = engine()
    Rider(e).run(max_s=100.0)
    s = e.abandon()
    jsonschema.validate(s, SUMMARY_SCHEMA)
    assert s["result"] == "abandoned" and s["boss"] == "not_reached"
