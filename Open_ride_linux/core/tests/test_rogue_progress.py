"""Lot R9 : châssis, statistiques recalculées, coffres, vies."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import jsonschema
import pytest

from openride_core import coins
from openride_core.physics import PhysicsParams
from openride_core.profile import Profile
from openride_core.progression import DEFAULT_TABLE_PATH, SessionFacts, load_table, recompute
from openride_core.rogue import progress as rp
from openride_core.rogue.balance import DEFAULT_BALANCE
from openride_core.rogue.combat import target_at
from openride_core.rogue.rooms import RoomRider
from openride_core.rogue.run import RunEngine, RunInputs, grade_sent

from test_progression import write_journal
from test_rogue_run import RIDER, Rider, engine, scenario

TABLE = load_table(None)
CHASSIS = rp.load_chassis(TABLE)
B = DEFAULT_BALANCE


def event(objective="threshold", result="victory", boss="won", gold=100, ps=10, cards=(), won=3, lives_used=0, d=45):
    summary = {"result": result, "objective": objective, "duration_min": d, "seed": 1, "rooms_won": won,
               "rooms_fled": 0, "rooms_skipped": 0, "rooms_total": 4, "defeats": 0, "boss": boss, "gold": gold,
               "cards": list(cards), "perfect_shifts": ps, "unlocks": []}
    return rp.run_event(summary, 44.0, lives_used)


def stats(*events):
    return rp.stats_from_events(list(events))


# --- catalogue -----------------------------------------------------------------------------------

def test_catalogue_matches_the_cahier():
    assert [c.id for c in CHASSIS] == ["standard", "blinde", "conducteur", "collecteur", "survolte", "endurant"]
    by = {c.id: c for c in CHASSIS}
    assert (by["blinde"].unlock, by["blinde"].threshold, by["blinde"].bonus) == ("boss_won", 1, {"shield_max": 10.0})
    assert (by["conducteur"].threshold, by["conducteur"].bonus) == (50, {"ps_window_s": 0.15})
    assert (by["collecteur"].threshold, by["collecteur"].bonus) == (500, {"gold_mult": 0.10})
    assert (by["survolte"].unlock, by["survolte"].threshold, by["survolte"].bonus) == ("vo2max_runs", 3, {"adrenaline_start": 20.0})
    assert (by["endurant"].unlock, by["endurant"].bonus) == ("endurance_runs", {"overheat_frac": 0.03})


@pytest.mark.parametrize("chassis_id, key, expected", [
    ("blinde", "shield_max", 110.0), ("conducteur", "ps_window_s", 1.65), ("collecteur", "gold_mult", 1.1),
    ("survolte", "adrenaline_start", 20.0), ("endurant", "overheat_frac", 0.78)])
def test_each_chassis_applies_its_bonus_and_only_that(chassis_id, key, expected):
    c = next(c for c in CHASSIS if c.id == chassis_id)
    b = rp.apply_chassis(B, c)
    assert getattr(b, key) == pytest.approx(expected)
    changed = {f for f in B.__dataclass_fields__ if getattr(b, f) != getattr(B, f)}
    assert changed == {key}


def test_bonus_bound_of_ten_percent_is_checked():
    for c in CHASSIS:
        for key, delta in c.bonus.items():
            ref = getattr(B, key)
            assert ref == 0 or delta <= 0.10 * ref + 1e-9
    too_much = rp.Chassis("x", "X", "", "none", 0, {"shield_max": 10.5})
    with pytest.raises(rp.ChassisError, match="dépasse 10 %"):
        rp.check_bounds(too_much)
    with pytest.raises(rp.ChassisError, match="non permise"):
        rp.check_bounds(rp.Chassis("x", "X", "", "none", 0, {"gear_ref": 1}))
    with pytest.raises(rp.ChassisError, match="au plus 20"):
        rp.check_bounds(rp.Chassis("x", "X", "", "none", 0, {"adrenaline_start": 25.0}))


def test_no_chassis_changes_the_trainer_grade_or_target_power():
    rider = RoomRider(ftp_w=250.0, params=PhysicsParams(mass_kg=84.0, cda_m2=0.32))
    from openride_core.rogue.rooms import generate_room
    ref = generate_room("diesel", "", "threshold", 120.0, rider, 5, B)
    for c in CHASSIS:
        b = rp.apply_chassis(B, c)
        room = generate_room("diesel", "", "threshold", 120.0, rider, 5, b)
        assert room.target_frac == ref.target_frac and room.profile == ref.profile
        for gear in (1, 6, 12):
            for g in (-3.0, 0.0, 8.0):
                assert grade_sent(g, gear, b) == grade_sent(g, gear, B)


def test_table_errors_name_the_key():
    def table(rows):
        t = load_table(None)
        t.data["chassis"] = rows
        return t
    with pytest.raises(rp.ChassisError, match="unlock : « lune » inconnu"):
        rp.load_chassis(table([{"id": "standard", "name": "S", "unlock": "none", "threshold": 0},
                               {"id": "a", "name": "A", "unlock": "lune", "threshold": 1}]))
    with pytest.raises(rp.ChassisError, match="en double"):
        rp.load_chassis(table([{"id": "standard", "name": "S", "unlock": "none", "threshold": 0},
                               {"id": "standard", "name": "S", "unlock": "none", "threshold": 0}]))
    with pytest.raises(rp.ChassisError, match="premier châssis"):
        rp.load_chassis(table([{"id": "a", "name": "A", "unlock": "boss_won", "threshold": 1}]))
    with pytest.raises(rp.ChassisError, match="clé inconnue"):
        rp.load_chassis(table([{"id": "standard", "name": "S", "unlock": "none", "threshold": 0, "x": 1}]))


# --- déblocages ----------------------------------------------------------------------------------

def test_each_chassis_unlocks_at_its_condition():
    assert rp.unlocked(CHASSIS, stats()) == ["standard"]
    assert "blinde" not in rp.unlocked(CHASSIS, stats(event(boss="fled", result="defeat")))
    assert "blinde" in rp.unlocked(CHASSIS, stats(event()))
    assert "conducteur" not in rp.unlocked(CHASSIS, stats(event(ps=49)))
    assert "conducteur" in rp.unlocked(CHASSIS, stats(event(ps=30), event(ps=20)))
    assert "collecteur" not in rp.unlocked(CHASSIS, stats(event(gold=499)))
    assert "collecteur" in rp.unlocked(CHASSIS, stats(event(gold=250), event(gold=250)))
    three = [event("vo2max", d=30) for _ in range(3)]
    assert "survolte" not in rp.unlocked(CHASSIS, stats(*three[:2]))
    assert "survolte" in rp.unlocked(CHASSIS, stats(*three))
    abandoned = [event("endurance", result="abandoned", boss="not_reached") for _ in range(3)]
    assert "endurant" not in rp.unlocked(CHASSIS, stats(*abandoned))
    assert "endurant" in rp.unlocked(CHASSIS, stats(*[event("endurance") for _ in range(3)]))


def test_choice_refuses_unknown_and_locked_chassis():
    st = stats(event())
    assert rp.choose_chassis(CHASSIS, st, None).id == "standard"
    assert rp.choose_chassis(CHASSIS, st, "blinde").id == "blinde"
    with pytest.raises(rp.ChassisError) as locked:
        rp.choose_chassis(CHASSIS, st, "survolte")
    assert locked.value.code == "item_locked"
    with pytest.raises(rp.ChassisError) as unknown:
        rp.choose_chassis(CHASSIS, st, "fusée")
    assert unknown.value.code == "run_invalid"


def test_config_block_follows_the_contract():
    schema = json.loads((Path(__file__).resolve().parents[2] / "docs/contracts/ipc/hello_ack.schema.json").read_text())
    rogue = schema["properties"]["config"]["properties"]["rogue"]
    block = {"w_prime_j": 20000, "w_prime_estimate_j": None, "cp_w": 240, "objectives": ["threshold"],
             "durations_min": [45], **rp.config_block(CHASSIS, stats(event()), "standard", 2)}
    jsonschema.validate(block, rogue)
    assert block["chassis"]["unlocked"] == ["standard", "blinde"] and block["lives"] == 2


# --- chassis en jeu ------------------------------------------------------------------------------

def test_gold_and_start_adrenaline_reach_the_run():
    base = engine()
    Rider(base).run()
    rich = RunEngine(scenario(), RIDER, 20000.0, 250.0, rp.apply_chassis(B, next(c for c in CHASSIS if c.id == "collecteur")))
    Rider(rich).run()
    assert rich.gold > base.gold * 1.05
    sv = RunEngine(scenario(), RIDER, 20000.0, 250.0, rp.apply_chassis(B, next(c for c in CHASSIS if c.id == "survolte")))
    r = Rider(sv)
    r.run(max_s=215.0)
    first = next(o for o in r.outs if o.rogue["phase"] == "ROOM")
    assert first.rogue["adrenaline"] >= 20.0


# --- vies ----------------------------------------------------------------------------------------

def defeat_run(lives):
    e = RunEngine(scenario(), RIDER, 20000.0, 250.0, B, lives=lives)
    e.gold = 200.0
    r = Rider(e, power_mult=0.2)        # puissance très basse : le mur rattrape et la défaite arrive
    r.run(max_s=700.0)
    return e, r


def test_defeat_with_a_life_keeps_the_gold_and_uses_the_life():
    with_life, r1 = defeat_run(1)
    without, r0 = defeat_run(0)
    assert without.defeats >= 1 and with_life.defeats >= 1
    assert with_life.lives_used == 1 and without.lives_used == 0
    assert with_life.gold > without.gold
    assert any("life_used" in line for o in r1.outs for line in o.journal)
    assert any(o.phase == "RECOVERY" for o in r1.outs)         # la récupération de 60 s reste


def test_lives_beyond_the_reserve_are_not_invented():
    e, _ = defeat_run(1)
    assert e.lives_used <= 1


# --- statistiques --------------------------------------------------------------------------------

def test_stats_recomputed_from_the_journal_equal_stats_kept_run_by_run():
    runs = [event("threshold", cards=("roller", "heal")), event("vo2max", d=30, result="defeat", boss="fled", gold=40),
            event("endurance", result="abandoned", boss="not_reached", ps=0, won=1, cards=("roller",)),
            event("threshold", gold=300, ps=22, cards=("roller",))]
    kept = rp.RogueStats()
    for ev in runs:
        kept.add(ev)
    assert rp.stats_from_events(runs).to_dict() == kept.to_dict()
    d = kept.to_dict()
    assert d["buckets"]["threshold/45"]["runs"] == 2 and d["buckets"]["threshold/45"]["best_gold"] == 300
    assert d["buckets"]["endurance/45"]["abandoned"] == 1 and d["buckets"]["vo2max/30"]["finished"] == 1
    assert d["top_card"] == "roller" and d["gold_total"] == 540 and d["buckets"]["threshold/45"]["bosses_won"] == 2


def test_stats_come_back_from_session_journals(tmp_path):
    runs = [event("threshold", gold=120, cards=("roller",)), event("vo2max", d=30, result="defeat", boss="fled", gold=40)]
    kept = rp.RogueStats()
    for i, ev in enumerate(runs):
        write_journal(tmp_path / f"s{i}.jsonl", minutes=10, start_ts=1_760_000_000.0 + i * 20000, extra_lines=[ev])
        kept.add(ev)
    progress = recompute(tmp_path, TABLE)
    st = rp.rogue_stats(progress)
    assert st.total("runs") == 2 and st.to_dict() == kept.to_dict()
    assert progress.stats["rogue_bosses"] == 1                 # l'expérience et les statistiques lisent la même ligne
    assert rp.rogue_stats(recompute(tmp_path, TABLE)).to_dict() == kept.to_dict()   # rien à stocker : tout se recalcule


# --- pièces, vies achetées -----------------------------------------------------------------------

def test_gold_converts_to_coins_and_boss_keeps_its_fixed_gain():
    ct = coins.coin_table(TABLE)
    facts = SessionFacts(journal="j", events=[event(gold=250)])
    assert coins.session_coins(facts, ct) == 25 + 50          # 250 or / 10 + boss de la table


def test_lives_are_capped_in_the_reserve():
    ct = coins.coin_table(TABLE)
    progress = type("P", (), {})()
    profile = Profile()
    profile.lives = {"bought": 3, "used": 0, "spent": 90}
    with pytest.raises(coins.CoinsError) as exc:
        coins.buy_life(progress, profile, ct)
    assert exc.value.code == "item_locked"
    assert ct.life_price == 30 and ct.max_lives == 3 and ct.rogue_gold_per_coin == 10


def test_run_event_feeds_xp_and_stats_with_the_same_line():
    ev = event()
    assert ev["kind"] == "rogue_run" and ev["bosses"] == [rp.BOSS_ID] and ev["chassis"] == "standard"
    assert event(boss="fled", result="defeat")["bosses"] == []
