"""Lot V3b : pièces (gains, solde, état des pièces, achats, vies)."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from openride_core.coins import (
    CoinsError, balance, buy, buy_life, coin_table, earned_coins, item_state, owned_items,
    session_coins, use_life,
)
from openride_core.equipment import load_catalogue
from openride_core.profile import Profile, equip, load_profile, save_profile
from openride_core.progression import (
    ChallengeDone, LevelInfo, Progress, SessionFacts, SessionResult, _validate, level_for,
    load_table, recompute, session_gains,
)

from test_progression import write_journal


@pytest.fixture(scope="module")
def table():
    return load_table(user_path=None)


@pytest.fixture(scope="module")
def ct(table):
    return coin_table(table)


@pytest.fixture(scope="module")
def cat(table):
    return load_catalogue(table)


def progress_with(table, *, km_sessions=(), level_xp=None, challenges=()):
    """Progression synthétique : séances de N km, niveau forcé par `level_xp`."""
    results = [SessionResult(f := SessionFacts(journal=f"s{i}", duration_s=3600, distance_m=km * 1000),
                             session_gains(f, table), None) for i, km in enumerate(km_sessions)]
    total = level_xp if level_xp is not None else sum(r.gains.total for r in results)
    return Progress(sessions=results, errors=[], total_xp=total, level=level_for(total, table),
                    stats={}, challenges=[ChallengeDone(c, c, r, "s0", None) for c, r in challenges])


# --- gains --------------------------------------------------------------------------------

def test_session_coins(tmp_path, ct, table):
    from openride_core.progression import session_facts
    assert session_coins(session_facts(write_journal(tmp_path / "a.jsonl", km=30)), ct) == 30
    erg = session_facts(write_journal(tmp_path / "b.jsonl", erg=True))
    assert session_coins(erg, ct) == 30
    events = SessionFacts(journal="x", duration_s=3600, events=[
        {"kind": "segment"}, {"kind": "segment", "pr": True}, {"kind": "jersey", "jersey": "kom"},
        {"kind": "rogue_run", "minutes": 45, "bosses": ["chimere_centrale", "puncheur"]}])
    assert session_coins(events, ct) == 5 + 5 + 20 + 50 + 10
    assert session_coins(SessionFacts(journal="y", distance_m=12_999), ct) == 12   # arrondi inférieur


def test_refused_sessions_earn_nothing(tmp_path, ct, table):
    d = tmp_path / "j"
    d.mkdir()
    write_journal(d / "a.jsonl", km=30, start_ts=1_000_000)
    write_journal(d / "b.jsonl", km=30, minutes=4, start_ts=2_000_000)
    write_journal(d / "c.jsonl", km=30, source="replay", start_ts=3_000_000)
    assert earned_coins(recompute(d, table), ct) == 30


# --- état des pièces ------------------------------------------------------------------------

def test_item_states(table, cat):
    p = Profile()
    prog = progress_with(table, level_xp=table.thresholds[4], challenges=[("kom_first", "kit_pois")])
    assert prog.level.level == 5
    assert item_state(cat["frame_allround"], prog, p, cat) == "equipped"
    assert item_state(cat["frame_climber"], prog, p, cat) == "buyable"     # niveau 5
    assert item_state(cat["frame_aero"], prog, p, cat) == "locked"         # niveau 10
    assert item_state(cat["kit_pois"], prog, p, cat) == "owned"            # offerte par le défi
    assert item_state(cat["kit_neon"], prog, p, cat) == "locked"           # défi non réussi
    assert "kit_pois" in owned_items(prog, p, cat)


# --- achats -----------------------------------------------------------------------------------

def test_buy_then_equip(table, ct, cat):
    p = Profile()
    prog = progress_with(table, km_sessions=[100, 100], level_xp=table.thresholds[4])
    assert balance(prog, p, ct) == 200
    assert buy("frame_climber", prog, p, cat, ct, ts=1) == 50
    assert balance(prog, p, ct) == 50
    assert item_state(cat["frame_climber"], prog, p, cat) == "owned"
    equip(p, "frame", "frame_climber", owned_items(prog, p, cat))
    assert item_state(cat["frame_climber"], prog, p, cat) == "equipped"


@pytest.mark.parametrize("item_id, code", [
    ("frame_aero", "item_locked"),          # niveau 10 demandé
    ("kit_pois", "item_locked"),            # défi seulement
    ("frame_allround", "already_owned"),
    ("velo_volant", "item_unknown"),
])
def test_buy_refusals(table, ct, cat, item_id, code):
    p = Profile()
    prog = progress_with(table, km_sessions=[1000], level_xp=table.thresholds[4])
    with pytest.raises(CoinsError) as err:
        buy(item_id, prog, p, cat, ct)
    assert err.value.code == code and p.purchases == []


def test_not_enough_coins(table, ct, cat):
    p = Profile()
    prog = progress_with(table, km_sessions=[100], level_xp=table.thresholds[4])
    with pytest.raises(CoinsError) as err:
        buy("frame_climber", prog, p, cat, ct)
    assert err.value.code == "not_enough_coins" and p.purchases == []


def test_profile_erased_gives_coins_back(tmp_path, table, ct, cat):
    path = tmp_path / "profile.json"
    prog = progress_with(table, km_sessions=[200], level_xp=table.thresholds[4])
    p = load_profile(path)
    buy("frame_climber", prog, p, cat, ct)
    save_profile(p, path)
    assert balance(prog, load_profile(path), ct) == 50
    path.unlink()
    assert balance(prog, load_profile(path), ct) == 200


def test_negative_balance_blocks_without_removing(table, ct, cat):
    p = Profile()
    prog = progress_with(table, km_sessions=[200], level_xp=table.thresholds[4])
    buy("frame_climber", prog, p, cat, ct)
    cheaper = coin_table(_validate(_with(table, coins={"per_km": 0.5}), "test"))
    assert balance(prog, p, cheaper) == 0
    with pytest.raises(CoinsError, match="solde 0"):
        buy("wheels_light", prog, p, cat, cheaper)
    assert p.purchased == {"frame_climber"}


def _with(table, **sections):
    data = copy.deepcopy(table.data)
    for name, values in sections.items():
        data[name].update(values)
    return data


# --- vies -------------------------------------------------------------------------------------

def test_lives(table, ct):
    p = Profile()
    prog = progress_with(table, km_sessions=[40])
    assert buy_life(prog, p, ct) == 10
    assert p.lives == {"bought": 1, "used": 0, "spent": 30}
    with pytest.raises(CoinsError) as err:
        buy_life(prog, p, ct)
    assert err.value.code == "not_enough_coins"
    use_life(p)
    assert p.lives["used"] == 1
    with pytest.raises(CoinsError) as err:
        use_life(p)
    assert err.value.code == "no_life"


# --- table ------------------------------------------------------------------------------------

@pytest.mark.parametrize("values, key", [
    ({"per_kmm": 1}, "per_kmm"), ({"life_price": 2.5}, "life_price"), ({"per_km": -1}, "per_km"),
])
def test_invalid_coin_table(table, values, key):
    with pytest.raises(CoinsError, match=key):
        coin_table(_validate(_with(table, coins=values), "test"))


def test_cli_shows_coins(tmp_path):
    d = tmp_path / "journal"
    d.mkdir()
    write_journal(d / "a.jsonl", km=30)
    (tmp_path / "OpenRide").mkdir()
    (tmp_path / "OpenRide" / "profile.json").write_text(
        json.dumps({"version": 1, "purchases": [{"item_id": "wheels_light", "price": 20}]}), encoding="utf-8")
    env = {"HOME": str(tmp_path), "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    out = subprocess.run([sys.executable, "-m", "openride_core", "xp", "--dir", str(d), "--json"],
                         capture_output=True, text=True, check=True, env=env)
    data = json.loads(out.stdout)
    assert (data["coins_earned"], data["coins_balance"]) == (30, 10)
    assert data["sessions"][0]["coins"] == 30
