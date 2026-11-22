"""Lot R4 : rivaux reconnaissables (même nom, équipe, caractère et cote d'une course à l'autre)."""

import json
import random
from pathlib import Path

from openride_core import bot_tactics, rivals
from openride_core.bots import PROFILES, bots_from_menu
from openride_core.physics import PhysicsParams


def test_names_are_fictional_short_and_unique():
    assert len(set(rivals.NAMES)) == len(rivals.NAMES) >= 44
    assert all(0 < len(n) <= rivals.NAME_MAX for n in rivals.NAMES)
    assert len({t for t, _ in rivals.TEAMS}) == len(rivals.TEAMS) == 11
    assert set(rivals.PROFILE_LABELS) == set(PROFILES)


def test_same_key_same_rival_across_races(tmp_path: Path):
    path = tmp_path / rivals.FILE_NAME
    r1 = rivals.load(path)
    a = r1.names_for(["climber", "rouleur", "climber"])
    assert len(set(a)) == 3 and r1.changed
    rivals.save(path, r1)
    r2 = rivals.load(path)
    assert r2.names_for(["climber", "rouleur", "climber"]) == a and not r2.changed
    # Autre plateau : climber#1 garde son nom, sprinter#1 est nouveau
    b = r2.names_for(["climber", "sprinter"])
    assert b[0] == a[0] and b[1] not in a and r2.changed


def test_default_roster_is_reproducible():
    assert rivals.Roster().names_for(["climber", "diesel"]) == rivals.Roster().names_for(["climber", "diesel"])


def test_style_team_and_personality_follow_the_name():
    ro = rivals.Roster()
    ro.ensure(["climber#1", "sprinter#1"])
    r = ro.get("climber#1")
    assert r.profile == "climber" and r.style().startswith("Grimpeur, ")
    assert r.personality == bot_tactics.personality_of(r.name)
    assert r.color.startswith("#") and r.team.startswith("Équipe ")
    d = ro.describe(["climber#1", "nobody#1"], ratings={"climber#1": 1532.4})
    assert len(d) == 1 and d[0]["rating"] == 1532 and d[0]["name"] == r.name


def test_teams_are_spread():
    ro = rivals.Roster(seed=3)
    keys = [f"{p}#{i}" for p in PROFILES for i in (1, 2, 3)][:11]
    ro.ensure(keys)
    assert len({r.team for r in ro.rivals.values()}) == 11   # 11 rivaux, 11 équipes différentes


def test_renew_replaces_three_and_never_brings_back(tmp_path: Path):
    ro = rivals.Roster(seed=5)
    keys = [f"{p}#{i}" for p, n in (("climber", 3), ("rouleur", 3), ("sprinter", 3), ("diesel", 2))
            for i in range(1, n + 1)]
    before = {k: r.name for k, r in zip(keys, ro.ensure(keys))}
    left = ro.renew(keys, 3, random.Random(1))
    after = {k: ro.get(k).name for k in keys}
    assert len(left) == 3 and sum(before[k] != after[k] for k in keys) == 3
    assert not set(after.values()) & {before[k] for k in left}
    path = tmp_path / rivals.FILE_NAME
    rivals.save(path, ro)
    again = rivals.load(path)
    assert {k: again.get(k).name for k in keys} == after and len(again.retired) == 3


def test_exhausted_pool_falls_back_to_profile_names():
    ro = rivals.Roster()
    names = ro.names_for(["climber"] * 50)
    assert names[: len(rivals.NAMES)] == [ro.get(f"climber#{i}").name for i in range(1, len(rivals.NAMES) + 1)]
    assert names[len(rivals.NAMES)] == f"Grimpeur {len(rivals.NAMES) + 1}"


def test_bad_file_gives_empty_roster(tmp_path: Path):
    path = tmp_path / rivals.FILE_NAME
    path.write_text("{pas du json", encoding="utf-8")
    assert rivals.load(path).rivals == {}
    path.write_text(json.dumps({"version": 99}), encoding="utf-8")
    assert rivals.load(path).rivals == {}


def test_menu_bots_take_rival_names(tmp_path: Path):
    ro = rivals.Roster()
    items = [{"kind": "profile", "profile": "climber"}, {"kind": "constant", "power_w": 200},
             {"kind": "profile", "profile": "climber"}]
    bots = bots_from_menu(items, PhysicsParams(), 250.0, None, tmp_path, names=ro.names_for)
    assert [b.name for b in bots] == [ro.get("climber#1").name, "Bot 200 W", ro.get("climber#2").name]
