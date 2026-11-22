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
    from openride_core.rogue.combat import judged_band_pct, win_target
    tgt = win_target(e.room, 5.0, B)   # lot R28 : consigne qui gagne ; plafond = seuil de surchauffe + tolérance
    assert out.rogue["target_pct"] == judged_band_pct(tgt, overheat_limit(tgt, B), 250.0, B)
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


def test_warmup_trend_gains_at_target_then_none_in_corridor():
    """Lot R26 : l'échauffement charge l'adrénaline à sa consigne ; hors salle et hors échauffement : « none »."""
    e = engine()
    r = Rider(e)
    r.run(max_s=20.0)
    assert e.phase == "WARMUP"
    assert r.outs[-1].rogue["adrenaline_trend"]["cause"] == "gain" and r.outs[-1].rogue["adrenaline"] > 0.0
    while e.phase != "CORRIDOR" and r.t < 2000:
        r.run(max_s=r.t + DT)
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


# --- cartes : seuils en watts, déclenchement annoncé (choix du propriétaire du 14 novembre) --------------------

def test_card_texts_give_watts_from_the_ftp():
    from openride_core.rogue.cards import ALL, card_text
    assert card_text("overdrive", 250, B).startswith("Pousse au-dessus de 375 W")
    assert "sous 150 W" in card_text("heal", 250, B)
    assert card_text("cursed", 300, B).startswith("Au-dessus de 300 W")
    for cid, card in ALL.items():
        text = card_text(cid, 250, B)
        assert "{" not in text and "% de ta FTP" not in text and "vitesse 1" not in text.lower().replace("vitesse 1,", "")
        assert card.replaces_gear is None and card.kind != "gear"


def test_loot_message_carries_the_watts():
    e = engine()
    r = Rider(e)
    while e.phase != "CORRIDOR" and r.t < 2000:
        r.run(max_s=r.t + DT)
    e.offer = ("overdrive", "heal", "cursed")
    msg = e._loot_message()
    assert [c["text"].split(" W")[0][-3:] for c in msg["cards"]] == ["375", "150", "250"]
    assert all(c["replaces_gear"] is None for c in msg["cards"])


def test_card_on_once_per_trigger():
    e = fight_engine(deck=("overdrive", "cursed"))
    out = step_in_room(e, 300.0, power=200.0)
    assert "card_on" not in out.rogue["events"] and out.rogue["card_on"] is None
    out = step_in_room(e, 300.0, power=400.0)                     # 160 % : Overdrive (et Maudit, annoncé ensuite)
    assert out.rogue["events"].count("card_on") == 1 and out.rogue["card_on"] == "overdrive"
    jsonschema.validate(out.rogue, ROGUE_SCHEMA)
    seen = []
    for _ in range(round(3.0 / DT)):
        o = step_in_room(e, 300.0, power=400.0)
        if "card_on" in o.rogue["events"]:
            seen.append(o.rogue["card_on"])
    assert seen == []                                                # Maudit a déjà passé son seuil au même pas
    step_in_room(e, 300.0, power=200.0)
    out = step_in_room(e, 300.0, power=280.0)                        # repasse au-dessus de la FTP, moins de 5 s après
    assert "card_on" not in out.rogue["events"]
    step_in_room(e, 300.0, power=200.0, n=round(6.0 / DT))
    out = step_in_room(e, 300.0, power=280.0)
    assert out.rogue["card_on"] == "cursed"


def test_heal_announced_when_spinning_light():
    e = fight_engine(deck=("heal",))
    out = step_in_room(e, 300.0, power=120.0, cadence=100.0)
    assert out.rogue["card_on"] == "heal"
    out = step_in_room(e, 300.0, power=120.0, cadence=100.0)
    assert "card_on" not in out.rogue["events"]


# --- essai du 15 novembre : consignes jugées sur la puissance affichée (moyenne de 3 s) ----------------------

def test_target_judged_on_displayed_power_not_raw_spikes():
    room = generate_room("diesel", "", "threshold", 240.0, RIDER, 1)
    st = combat_start(room, 1)
    from openride_core.rogue.combat import win_target
    tgt_w = win_target(room, 5.0, B) * 250   # lot R28 : la consigne écrite, celle qui gagne
    # puissance brute qui oscille de ± 60 W autour de la consigne, moyenne affichée à la consigne
    gained = 0.0
    for k in range(round(10.0 / DT)):
        raw = tgt_w + (60.0 if k % 2 else -60.0)
        st, _ = combat_step(st, CombatInputs(**_base(s_m=5.0 + 0.01 * k, power_w=raw, power_avg_w=tgt_w + 1.0)), room, B, DT)
    assert st.adrenaline == pytest.approx(10.0 * B.adrenaline_per_s, abs=0.1)   # moyenne à la consigne : tout compte


def test_overheat_ignores_raw_spikes_under_the_ceiling():
    e = fight_engine(first="diesel", objective="endurance")
    out = step_in_room(e, 5.0, power=150.0)
    hi_w = out.rogue["target_pct"]["hi"] / 100 * 250
    from openride_core.rogue.run import RunInputs
    for k in range(round(8.0 / DT)):
        raw = hi_w + (80.0 if k % 2 else -80.0)
        out = e.step(DT, RunInputs(power_w=raw, cadence_rpm=85, gear=6, ftp_w=250, s_m=6.0 + 0.01 * k, v_mps=8.0,
                                   power_avg_w=hi_w - 5.0))
    assert not out.rogue["overheat"]



def test_adrenaline_carried_to_the_next_room_and_boss_phase():
    # essai du 15 novembre : remise à 0 à chaque phase, la phase 3 du boss (85 s) ne permettait aucune frappe
    e = engine()
    r = Rider(e)
    while e.phase not in ("ROOM", "BOSS") and r.t < 3000:
        r.run(max_s=r.t + DT)
    first = e.room_id
    e.combat = replace(e.combat, adrenaline=42.0)
    while e.room_id == first and r.t < 4000:
        r.run(max_s=r.t + DT)
    assert e.combat.adrenaline >= 42.0 - 1.0


# --- essai du 15 novembre : couloir court, cause de la défaite, boss qui remplit le temps restant -------

def test_corridors_last_45_s_and_runs_keep_their_duration():
    from openride_core.rogue.scenario import compose_run
    for d in (30, 45, 60, 90):
        for objective in ("endurance", "threshold", "vo2max"):
            sc = compose_run(objective, d, 5)
            corridors = [s for s in sc.steps if s.kind == "corridor"]
            assert corridors and all(s.nominal_s == 45.0 for s in corridors)
            total = sum(s.nominal_s + (s.doors[0].nominal_s if s.doors else 0.0) for s in sc.steps)
            assert abs(total - d * 60.0) < 1.0, (d, objective, total)
            rooms = [s.nominal_s for s in sc.steps if s.kind == "room"] + [x.nominal_s for s in corridors for x in s.doors[:1]]
            assert all(B.room_min_s <= x <= B.room_max_s for x in rooms)


def test_long_rooms_are_split_under_the_datagram_limit():
    from openride_core.ipc_budget import encode
    from openride_core.ipc_server import MAX_DATAGRAM_SIZE
    room = generate_room("boss", "phase2", "endurance", 480.0, RIDER, 7, B)
    parts = room.to_messages(3)
    assert len(parts) >= 2 and all(len(encode(m)) <= MAX_DATAGRAM_SIZE for m in parts)
    assert [m["part"] for m in parts] == list(range(1, len(parts) + 1)) and {m["parts"] for m in parts} == {len(parts)}
    whole = room.to_message(3)
    assert sum((m["profile"] for m in parts), []) == whole["profile"]
    assert sum((m["markers"] for m in parts), []) == whole["markers"]
    for m in parts:
        jsonschema.validate(m, _room_schema())
    short = generate_room("diesel", "", "endurance", 120.0, RIDER, 8, B).to_messages(4)
    assert len(short) == 1 and short[0]["parts"] == 1


def _room_schema():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    return json.loads((root / "docs/contracts/ipc/room.schema.json").read_text(encoding="utf-8"))


def test_boss_fills_the_time_left():
    e = engine()
    boss = [i for i, s in enumerate(e.sc.steps) if s.kind == "boss"]
    planned = sum(e.sc.steps[i].nominal_s for i in boss)
    e.idx, e.t_total = boss[0], 0.0
    before_cool = sum(s.nominal_s + (s.doors[0].nominal_s if s.doors else 0.0) for s in e.sc.steps[:boss[0]])
    e.t_total = before_cool - 60.0                     # une minute d'avance (salle finie plus vite)
    e._fit_boss_to_time_left()
    after = sum(e.sc.steps[i].nominal_s for i in boss)
    assert after == pytest.approx(planned + 60.0, abs=1.0)
    e.t_total = before_cool - 60.0 + 5.0               # sous 15 s d'écart : rien ne bouge
    e._fit_boss_to_time_left()
    assert sum(e.sc.steps[i].nominal_s for i in boss) == pytest.approx(after, abs=0.01)


def test_summary_says_why_the_run_was_lost():
    from openride_core.rogue.run import RunEngine, RunInputs, Scenario, Step
    steps = (Step("warmup", 1.0),) + tuple(Step("boss", 20.0, "boss", f"phase{k}", "endurance") for k in (1, 2, 3)) \
        + (Step("cooldown", 5.0),)
    e = RunEngine(Scenario("endurance", 30, 3, steps), RIDER, 20000.0, 250.0, B)
    s_m, rid, t = 0.0, None, 0.0
    while e.phase not in ("COOLDOWN", "RESULTS") and t < 600.0:   # roule sans jamais frapper
        if e.room_id != rid:
            rid, s_m = e.room_id, 0.0
        e.step(DT, RunInputs(power_w=60, cadence_rpm=85, gear=6, ftp_w=250, s_m=s_m, v_mps=8.0))
        s_m += 8.0 * DT
        t += DT
    summary = e.summary()
    cause = summary["end_cause"]
    assert summary["boss"] == "fled" and cause["cause"] == "boss_time" and cause["boss_phase"] == 3
    assert 1 <= cause["enemy_pct"] <= 100
    e.result = "victory"
    assert e.summary()["end_cause"] is None
    e2 = engine()
    assert e2.abandon()["end_cause"] == {"cause": "abandoned", "boss_phase": None, "enemy_pct": None}
