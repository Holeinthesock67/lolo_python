"""Lot DS3 : tactique de survie des bots du mode « Dernier survivant »."""

from __future__ import annotations

import random

from openride_core.bots import PROFILES, SURVIVAL_SAFE_CP, ProfileBot
from openride_core.survivor import (ME, SPRINT_FROM_M, SurvivorRace, arch_positions, plan_field)

DT = 0.05


def bot(profile: str = "rouleur", level: float = 100.0, bot_id: str = "bot1") -> ProfileBot:
    b = ProfileBot(profile, bot_id=bot_id)
    b.set_scale(level / 100.0)
    return b


def test_danger_near_arch_sprints_with_profile_fraction() -> None:
    for name, spec in PROFILES.items():
        b = bot(name)
        b.survival = (300.0, True, False, 350.0)
        assert b.target_power(0.0) == spec.survival * b.cp_w
    assert PROFILES["sprinter"].survival == 1.50 and PROFILES["diesel"].survival == 1.20


def test_no_sprint_before_threshold_or_without_reserve() -> None:
    b = bot()
    b.survival = (500.0, True, False, 350.0)
    assert b.target_power(0.0) == PROFILES["rouleur"].flat * b.cp_w
    b.survival = (300.0, True, False, 350.0)
    assert b.target_power(0.0, wbal_pct=9.0) == PROFILES["rouleur"].flat * b.cp_w


def test_safe_bot_saves_energy_and_unhinted_bot_unchanged() -> None:
    b = bot()
    plain = b.target_power(0.0)
    b.survival = (300.0, False, True, 350.0)
    assert b.target_power(0.0) == min(plain, SURVIVAL_SAFE_CP * b.cp_w)
    b.survival = None
    assert b.target_power(0.0) == plain


def test_wbal_never_negative_during_long_sprint() -> None:
    b = bot("sprinter")
    b.survival = (300.0, True, False, 400.0)
    for _ in range(int(300 / DT)):
        b.step(DT)
        assert b.wbal.w_bal_j >= 0.0
    assert b.wbal_pct <= 10.0 + 1e-6 and b.power_w <= b.cp_w   # réserve à 10 % : fin du sprint


def test_hints_danger_and_safe() -> None:
    r = SurvivorRace(arch_positions(4, 2), [(f"bot{i}", f"B{i}", 100.0) for i in range(1, 5)], 2, seed=3)
    pos = {ME: (1700.0, 10.0), "bot1": (1800.0, 10.0), "bot2": (1690.0, 10.0),
           "bot3": (1650.0, 10.0), "bot4": (1640.0, 10.0)}
    r.start(0.0, pos)
    r.step(0.1, pos)
    h = r.survival_hints()
    assert ME not in h
    assert h["bot1"][:3] == (200.0, False, True)          # 16 s devant le dernier
    assert h["bot3"][1] and h["bot4"][1]                  # deux derniers
    assert h["bot2"][1:3] == (False, False)               # 5,0 s du dernier : ni menacé, ni à l'abri
    lo, hi = SPRINT_FROM_M
    assert all(lo <= v[3] <= hi for v in h.values())


def test_hints_ignore_whether_last_is_rider_or_bot() -> None:
    """Pas d'élastique : même situation, mêmes consignes, que le dernier soit le cycliste ou un bot."""
    def hints(last: str) -> tuple:
        r = SurvivorRace(arch_positions(2, 2), [("bot1", "A", 100.0), ("bot2", "B", 100.0)], 2, seed=1)
        others = [x for x in (ME, "bot2") if x != last]
        pos = {"bot1": (1800.0, 10.0), last: (1500.0, 10.0), others[0]: (1790.0, 10.0)}
        r.start(0.0, pos)
        r.step(0.1, pos)
        return r.survival_hints()["bot1"][:3]
    assert hints(ME) == hints("bot2")


def test_bot_past_current_arch_targets_next_one() -> None:
    r = SurvivorRace(arch_positions(3, 1), [(f"bot{i}", f"B{i}", 100.0) for i in range(1, 4)], 1, seed=0)
    r.start(0.0, {ME: (900.0, 10.0), "bot1": (990.0, 10.0), "bot2": (0.0, 1.0), "bot3": (0.0, 1.0)})
    r.step(1.0, {ME: (950.0, 10.0), "bot1": (1100.0, 10.0), "bot2": (1.0, 1.0), "bot3": (1.0, 1.0)})
    assert r.survival_hints()["bot1"][0] == 900.0


def race_once(seed: int, spread: str, n: int = 4) -> list[str]:
    """Course de bots à profil (niveaux du plateau du mode) et d'un cycliste plus fort ; ordre des éliminés."""
    field = plan_field(n, 100.0, spread)
    profiles = ["rouleur"] * n                       # même profil : seul le niveau et la tactique jouent
    bots = []
    for i, (_, level) in enumerate(field):
        b = ProfileBot(profiles[i], bot_id=f"bot{i + 1}")
        b.set_scale(level / 100.0 * random.Random(seed * 31 + i).uniform(0.99, 1.01))
        bots.append(b)
    me = ProfileBot("rouleur", bot_id=ME)
    me.set_scale(1.30)
    r = SurvivorRace(arch_positions(n, 1), [(b.id, b.name, lv) for b, (_, lv) in zip(bots, field)], 1,
                     seed=seed)
    everyone = [me, *bots]
    r.start(0.0, {b.id: (b.s, b.v) for b in everyone})
    t = 0.0
    while not r.finished and t < 3600.0:
        hints = r.survival_hints()
        for b in bots:
            b.survival = hints.get(b.id)
        t += DT
        for b in everyone:
            if not r.is_out(b.id):
                b.step(DT)
        r.step(t, {b.id: (b.s, b.v) for b in everyone})
    return [line[1] for line in r.summary()["eliminated"]]


def test_same_level_order_varies_between_races() -> None:
    orders = {tuple(race_once(seed, "tight")) for seed in range(12)}
    assert len(orders) > 1


def test_wide_spread_weakest_bot_goes_first_most_of_the_time() -> None:
    firsts = [race_once(seed, "wide")[0] for seed in range(20)]
    assert sum(1 for f in firsts if f == "bot4") >= 16          # 80 % des courses au moins
