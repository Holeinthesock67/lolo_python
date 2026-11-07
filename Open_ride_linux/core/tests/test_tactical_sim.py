"""Lot CT0 : table d'équilibrage de la Course tactique, bouchons des règles et simulateur d'équilibrage."""

from __future__ import annotations

import re
import time
import tomllib
from dataclasses import fields, replace
from pathlib import Path

import pytest

from openride_core.draft import ALPHA_MAX, draft_coefficient
from openride_core.rogue.balance import BalanceError
from openride_core.rogue.wbal import wbal_initial, wbal_step
from openride_core.tactical import bouchons as rules
from openride_core.tactical.balance import (DEFAULT_BALANCE, EMBEDDED_PATH, TacticalBalance, apply_overrides,
                                            balance_hash, load_balance)
from openride_core.tools import tactical_sim as sim

NOWHERE = Path("/nonexistent/tactical_balance.toml")
BAL = DEFAULT_BALANCE


# --- table d'équilibrage -----------------------------------------------------------------------------------

def test_embedded_table_equals_defaults():
    assert load_balance(NOWHERE) == DEFAULT_BALANCE


def test_every_field_is_in_the_file_with_a_french_comment():
    text = EMBEDDED_PATH.read_text(encoding="utf-8")
    assert {f.name for f in fields(TacticalBalance)} == set(tomllib.loads(text))
    for f in fields(TacticalBalance):
        assert re.search(rf"^{f.name} = .*?#\s*(\S.*)$", text, re.M), f"{f.name} : commentaire manquant"


def test_override_keeps_other_values(tmp_path):
    over = tmp_path / "tactical_balance.toml"
    over.write_text("burnout_s = 6\n", encoding="utf-8")
    bal = load_balance(over)
    assert bal.burnout_s == 6.0 and bal.burnout_cap_pct == DEFAULT_BALANCE.burnout_cap_pct
    assert balance_hash(bal) != balance_hash(DEFAULT_BALANCE)


@pytest.mark.parametrize("data, key", [({"burnout": 8}, "burnout"), ({"burnout_s": "8"}, "burnout_s"),
                                       ({"burnout_s": -1}, "burnout_s"), ({"dt_s": 0}, "dt_s")])
def test_bad_override_names_the_key(data, key):
    with pytest.raises(BalanceError, match=key):
        apply_overrides(DEFAULT_BALANCE, data)


def test_required_override_must_exist():
    with pytest.raises(BalanceError):
        load_balance(NOWHERE, required=True)


# --- bouchons des règles -----------------------------------------------------------------------------------

def _ride(power_w: float, seconds: float, cp_w: float = 250.0, w_prime_j: float = 20000.0, dt: float = 0.1,
          start_j: float | None = None):
    """Réserve de Skiba et Burnout, puissance prise en compte plafonnée pendant le Burnout."""
    w = wbal_initial(w_prime_j) if start_j is None else replace(wbal_initial(w_prime_j), w_bal_j=start_j)
    burn = rules.Burnout()
    started, applied = 0, []
    for _ in range(round(seconds / dt)):
        p = min(power_w, rules.burnout_cap_w(cp_w, BAL)) if burn.active else power_w
        applied.append((burn.active, p))
        w = wbal_step(w, power_w, 0.0, dt, cp_w=cp_w, w_prime_j=w_prime_j)
        burn, new = rules.burnout_step(burn, w.w_bal_j, dt, BAL)
        started += new
    return w, burn, started, applied


def test_burnout_after_half_a_second_at_zero_then_capped_at_70_pct_of_cp_for_8_s():
    # 150 % de la CP (375 W) avec W′ = 20 kJ : réserve vide en 160 s, Burnout 0,5 s plus tard
    w, burn, started, applied = _ride(375.0, 160.0 + 0.5 + 8.0)
    assert started == 1
    capped = [p for active, p in applied if active]
    assert len(capped) == pytest.approx(80, abs=1)                   # 8 s au pas de 0,1 s
    assert max(capped) <= 0.70 * 250.0 + 1e-9                         # 175 W au plus
    assert rules.burnout_cap_w(250.0, BAL) == pytest.approx(175.0)


def test_cutting_under_cp_at_1_pct_avoids_the_burnout():
    w, burn, started, _ = _ride(375.0, 160.0 * 0.99)                 # 1 % de réserve
    assert w.w_bal_j > 0.0 and started == 0
    w2 = wbal_step(w, 200.0, 0.0, 10.0, cp_w=250.0, w_prime_j=20000.0)
    assert w2.w_bal_j > w.w_bal_j                                      # sous la CP, la réserve remonte


def test_short_touch_of_zero_is_tolerated_and_shield_prevents_the_burnout():
    state, new = rules.burnout_step(rules.Burnout(), 0.0, 0.4, BAL)
    assert not new and not state.active
    state, new = rules.burnout_step(state, 100.0, 0.1, BAL)          # repassé sous la CP : compte remis à 0
    assert state == rules.Burnout()
    shielded, new = rules.burnout_step(rules.Burnout(empty_s=5.0), 0.0, 0.5, BAL, shielded=True)
    assert not new and not shielded.active


def test_sling_charge_follows_the_shelter():
    def time_to_full(alpha: float) -> float:
        c, t = 0.0, 0.0
        while c < 100.0:
            c, t = rules.sling_charge(c, alpha, 0.1, BAL), t + 0.1
        return t

    assert time_to_full(ALPHA_MAX) == pytest.approx(BAL.sling_full_s, abs=0.11)   # roue dans la roue : 15 s
    assert 25.0 < time_to_full(draft_coefficient(3.0)) < 35.0                      # à 3 m : environ 30 s
    assert rules.sling_charge(50.0, 0.0, 1.0, BAL) == pytest.approx(50.0 - BAL.sling_decay_pct_s)
    assert rules.sling_power(300.0, 100.0, BAL) == pytest.approx(300.0 * (1 + BAL.sling_gain_pct / 100))
    assert rules.sling_power(300.0, 0.0, BAL) == 300.0


def test_abilities_follow_the_buttons_of_the_plan():
    assert rules.ability_for(100.0, True, BAL) == "aero"               # Z long : Overdrive à jauge pleine
    assert rules.ability_for(99.0, True, BAL) is None
    assert rules.ability_for(60.0, False, BAL) == "shield"             # Z court : la plus haute payable
    assert rules.ability_for(30.0, False, BAL) == "breakaway"
    assert rules.ability_for(10.0, False, BAL) is None
    assert rules.credits_pct(BAL.credits_full_kj * 1000.0 * 2, BAL) == 100.0


# --- simulateur --------------------------------------------------------------------------------------------

def test_common_scale_keeps_the_profiles_relative_strengths():
    c = sim.CIRCUITS["plat"]
    scales = sim.calibration(c, BAL)
    assert len(set(scales.values())) == 1
    rider_t = sim._solo_time(c.parts, sim.PhysicsParams(mass_kg=BAL.rider_mass_kg + BAL.bike_mass_kg),
                             lambda g: BAL.rider_ftp_w * BAL.bots_level_pct / 100)
    mean = sum(sim._bot_time(p, c, scales[p], BAL) for p in sim.BOT_PROFILES) / len(sim.BOT_PROFILES)
    assert mean == pytest.approx(rider_t, rel=1e-3)


def test_same_seed_same_race_and_report():
    c = sim.CIRCUITS["bosse_finale"]
    assert sim.race(c, "mixte", 7) == sim.race(c, "mixte", 7)
    a = sim.simulate(["plat", "col"], ["suceur", "echappee"], 3, 5, BAL)
    b = sim.simulate(["plat", "col"], ["suceur", "echappee"], 3, 5, BAL, jobs=2)
    assert sim.report_markdown(a, sim.criteria(a)) == sim.report_markdown(b, sim.criteria(b))


def test_every_runner_finishes_and_the_rules_are_used():
    out = [sim.race(sim.CIRCUITS[c], st, 3) for c in ("col", "vallonne") for st in sim.STRATEGIES]
    for r in out:
        assert all(g is not None and g >= 0.0 for g in r["gaps_s"].values())
        assert r["winner"] in (sim.RIDER_ID, *sim.BOT_PROFILES)
    assert sum(r["slings"] for r in out) > 0
    assert sum(r["abilities"] for r in out) > 0                          # le rouleur et le mixte achètent


def test_breakaway_rider_never_gets_shelter_credits_from_nobody():
    r = sim.race(sim.CIRCUITS["col"], "echappee", 2)
    assert r["abilities"] == 0                                           # seul devant : il n'abrite personne


def test_criteria_name_every_strategy_and_profile():
    out = sim.simulate(["plat"], list(sim.STRATEGIES), 1, 1, BAL)
    texts = " ".join(c["text"] for c in sim.criteria(out))
    for st in sim.STRATEGIES:
        assert f"stratégie {st}" in texts
    assert "Sprinteur" in texts and "Diesel" in texts


def test_twenty_races_are_quick():
    t0 = time.perf_counter()
    sim.simulate(["vallonne"], ["mixte"], 20, 1, BAL)
    assert time.perf_counter() - t0 < 30.0   # 200 courses en moins de 60 s : environ 0,15 s par course


def test_cli_refuses_unknown_names(capsys):
    assert sim.main(["--strategies", "kamikaze", "--races", "1"]) == 2
    assert "kamikaze" in capsys.readouterr().err


def test_cli_writes_the_report(tmp_path):
    rep = tmp_path / "r.md"
    rc = sim.main(["--races", "1", "--circuits", "plat", "--strategies", "suceur", "--report", str(rep),
                   "--balance", str(NOWHERE.with_name("absent.toml"))])
    assert rc == 2                                                       # surcharge demandée mais absente
    rc = sim.main(["--races", "1", "--circuits", "plat", "--strategies", "suceur", "--report", str(rep)])
    assert rc in (0, 1) and rep.read_text(encoding="utf-8").startswith("# Rapport d'équilibrage")


# --- recherche automatique -----------------------------------------------------------------------------------

def _fake_out(wins_by_circuit: dict[str, dict[str, int]]) -> dict:
    batches = []
    for c, wins in wins_by_circuit.items():
        for st in sim.STRATEGIES:
            batches.append({"circuit": c, "strategy": st, "races": sum(wins.values()), "wins": dict(wins)})
    return {"batches": batches}


def test_score_is_lower_when_wins_are_shared():
    even = {p: 2 for p in (sim.RIDER_ID, *sim.BOT_PROFILES)}
    one = {p: (10 if p == "sprinter" else 0) for p in (sim.RIDER_ID, *sim.BOT_PROFILES)}
    assert sim.shares(_fake_out({"plat": even}))["sprinter"] == pytest.approx(sim.TARGET_SHARE)
    assert sim.score(_fake_out({"plat": even})) < sim.score(_fake_out({"plat": one}))


def test_tunable_values_exist_and_spare_the_owner_decisions():
    names = {f.name for f in fields(TacticalBalance)}
    assert set(sim.TUNABLE) <= names
    for decided in ("burnout_cap_pct", "burnout_s", "sling_full_s", "relay_min_s", "aero_cost_pct"):
        assert decided not in sim.TUNABLE
    for key, (step, lo, hi) in sim.TUNABLE.items():
        assert step > 0 and lo <= getattr(BAL, key) <= hi, key


def test_overrides_are_a_valid_override_file(tmp_path):
    best = replace(BAL, bot_sprint_cp_pct=180.0)
    text = sim.overrides_toml(BAL, best)
    assert text == "bot_sprint_cp_pct = 180.0\n"
    over = tmp_path / "t.toml"
    over.write_text(text, encoding="utf-8")
    assert load_balance(over) == best
    assert sim.overrides_toml(BAL, BAL) == ""


def test_search_keeps_the_start_when_nothing_is_better(monkeypatch):
    monkeypatch.setattr(sim, "simulate", lambda *a, **k: {"batches": []})
    monkeypatch.setattr(sim, "score", lambda out: 1.0)
    best, sc = sim.search(BAL, 1, 1, 2, 1)
    assert best == BAL and sc == 1.0


# --- Elo et baroudeur ----------------------------------------------------------------------------------------

def test_elo_winner_gains_what_the_others_lose():
    from openride_core.tactical import elo
    r = elo.update({}, ["a", "b", "c"])
    assert r["a"] > elo.ELO_START > r["c"]
    assert sum(r.values()) == pytest.approx(3 * elo.ELO_START)
    assert elo.expected(1600, 1400) == pytest.approx(1 / (1 + 10 ** -0.5))
    # battre plus fort que soi rapporte plus
    up_strong = elo.update({"a": 1400, "b": 1600}, ["a", "b"])["a"] - 1400
    up_weak = elo.update({"a": 1600, "b": 1400}, ["a", "b"])["a"] - 1600
    assert up_strong > up_weak > 0


def test_report_has_an_elo_line_per_bot_and_strategy():
    out = sim.simulate(["plat"], ["suceur", "mixte"], 2, 1, BAL)
    ratings = sim.elo_ratings(out)
    assert set(ratings) == {*sim.BOT_PROFILES, "rider:suceur", "rider:mixte"}
    assert "## Classement Elo" in sim.report_markdown(out, sim.criteria(out))


def test_baroudeur_attacks_early():
    from openride_core.tools.tactical_sim import _bot_power, _make_field
    import random
    field = _make_field("suceur", sim.calibration(sim.CIRCUITS["plat"], BAL), BAL, random.Random(1), 12000.0)
    bar = next(r for r in field if r.profile == "baroudeur")
    p = _bot_power(bar, 0.0, 11000.0, BAL.dt_s, random.Random(1), BAL)
    assert p == pytest.approx(BAL.baroudeur_cp_pct / 100 * bar.cp_w) and bar.escaping


def test_pending_terrain_is_reported_but_not_failed():
    wins = {p: 0 for p in (sim.RIDER_ID, *sim.BOT_PROFILES)}
    wins["sprinter"] = 3
    checks = sim.criteria(_fake_out({"plat": wins}))
    rouleur = next(c for c in checks if "Rouleur" in c["text"])
    assert rouleur["ok"] and rouleur["pending"] and "CT20" in rouleur["text"]
    diesel = next(c for c in checks if "Diesel" in c["text"])
    assert not diesel["ok"]
