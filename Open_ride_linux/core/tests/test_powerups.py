"""Lot T6 : bonus légèreté, aérodynamique et puissance (module pur `powerups`)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from openride_core.physics import PhysicsParams, RiderPhysics, steady_speed
from openride_core.powerups import (DEFAULT_TABLE, KINDS, ArchSchedule, PowerUpError, PowerUps,
                                    load_table)

BASE = PhysicsParams(mass_kg=80.0, cda_m2=0.32)


def test_default_values_match_plan():
    s = DEFAULT_TABLE.specs
    assert (s["lightweight"].factor, s["aero"].factor, s["power"].factor) == (0.90, 0.75, 1.10)
    assert all(spec.duration_s == 15.0 for spec in s.values())
    assert DEFAULT_TABLE.arch_every_m == 5000.0 and DEFAULT_TABLE.per_segment


def test_award_random_single_reserve_replaced():
    pu = PowerUps(seed=4)
    kinds = Counter(pu.award("segment") for _ in range(3000))
    assert set(kinds) == set(KINDS)
    assert all(800 < n < 1200 for n in kinds.values())     # tirage uniforme
    first = pu.reserve
    pu.award("arch")
    assert pu.reserve in KINDS                              # une seule réserve, remplacée
    with pytest.raises(ValueError):
        pu.award("ravito")
    assert first is not None


def test_activate_duration_and_expiry():
    pu = PowerUps(seed=1)
    assert not pu.activate(0.0)                 # rien en réserve
    pu.award("segment")
    kind = pu.reserve
    assert pu.activate(10.0)
    assert pu.active == kind and pu.reserve is None and pu.remaining_s == 15.0
    pu.award("arch")
    assert not pu.activate(11.0)                # un bonus déjà actif : la réserve attend
    for _ in range(int(14.98 / 0.02)):
        pu.step(0.02)
    assert pu.active == kind
    pu.step(0.04)
    assert pu.active is None and pu.remaining_s == 0.0
    assert pu.activate(30.0)                    # la réserve gardée s'active ensuite
    assert [u.kind for u in pu.uses][0] == kind
    assert pu.uses[0].to_dict() == {"kind": kind, "t_start": 10.0, "duration_s": 15.0}


def force(pu: PowerUps, kind: str) -> None:
    pu.reserve = kind
    assert pu.activate(0.0)


def test_effects_on_params_and_power():
    pu = PowerUps()
    assert pu.params(BASE) is BASE and pu.power(250.0) == 250.0
    force(pu, "lightweight")
    assert pu.params(BASE).mass_kg == pytest.approx(72.0)
    assert pu.params(BASE).cda_m2 == BASE.cda_m2
    pu = PowerUps()
    force(pu, "aero")
    assert pu.params(BASE).cda_m2 == pytest.approx(0.24)
    pu = PowerUps()
    force(pu, "power")
    assert pu.power(250.0) == pytest.approx(275.0)
    assert pu.params(BASE) is BASE


def test_each_bonus_speeds_up_where_expected():
    flat_base = steady_speed(250.0, 0.0, BASE)
    climb_base = steady_speed(250.0, 8.0, BASE)
    pu = PowerUps()
    force(pu, "aero")
    assert steady_speed(250.0, 0.0, pu.params(BASE)) > flat_base * 1.08
    assert steady_speed(250.0, 8.0, pu.params(BASE)) < climb_base * 1.03   # peu d'effet en montée
    pu = PowerUps()
    force(pu, "lightweight")
    assert steady_speed(250.0, 8.0, pu.params(BASE)) > climb_base * 1.08
    pu = PowerUps()
    force(pu, "power")
    assert steady_speed(pu.power(250.0), 8.0, BASE) > climb_base * 1.08


def test_physics_with_bonus_only_changes_virtual_speed():
    # La puissance mesurée reste celle écrite ; seule la vitesse virtuelle change.
    pu = PowerUps()
    force(pu, "power")
    a, b = RiderPhysics(BASE), RiderPhysics(BASE)
    measured = 220.0
    for _ in range(int(15 / 0.02)):
        a.step(measured, 0.0, 0.0, 0.02)
        b.step(pu.power(measured), 0.0, 0.0, 0.02)
        pu.step(0.02)
    assert b.s > a.s and pu.active is None


def test_erg_disables_bonus_keeps_reserve():
    pu = PowerUps(seed=2)
    pu.award("segment")
    pu.activate(0.0)
    pu.award("arch")
    reserve = pu.reserve
    pu.set_erg(True)
    assert pu.active is None
    assert pu.award("segment") is None and pu.reserve == reserve
    assert not pu.activate(5.0)
    assert pu.params(BASE) is BASE and pu.power(200.0) == 200.0
    pu.set_erg(False)
    assert pu.activate(6.0)


def test_state_dict():
    pu = PowerUps()
    assert pu.state_dict() == {"reserve": None, "active": None, "remaining_s": 0.0}
    force(pu, "aero")
    pu.step(2.04)
    assert pu.state_dict() == {"reserve": None, "active": "aero", "remaining_s": 13.0}


def test_arches_open_and_loop():
    arches = ArchSchedule(5000.0, 23_000.0)
    assert arches.positions == [5000.0, 10_000.0, 15_000.0, 20_000.0]
    assert arches.crossed(4999.0, 5000.0) == 1
    assert arches.crossed(5000.0, 5001.0) == 0
    assert arches.crossed(0.0, 23_000.0) == 4
    loop = ArchSchedule(5000.0, 12_000.0, loop=True)
    assert loop.positions == [5000.0, 10_000.0]
    assert loop.crossed(0.0, 36_000.0) == 6              # 3 tours × 2 arches
    assert loop.crossed(11_000.0, 17_500.0) == 1         # 17 000 = arche de 5 km du 2e tour
    assert ArchSchedule(0.0, 10_000.0).crossed(0.0, 10_000.0) == 0
    assert ArchSchedule(5000.0, 5000.0).positions == []  # pas d'arche sur la ligne d'arrivée


def test_load_table_file(tmp_path: Path):
    assert load_table(tmp_path / "absent.toml") is DEFAULT_TABLE
    f = tmp_path / "powerups.toml"
    f.write_text("[aero]\nfactor = 0.8\n[obtain]\narch_every_m = 0\nper_segment = false\n",
                 encoding="utf-8")
    t = load_table(f)
    assert t.specs["aero"].factor == 0.8 and t.specs["aero"].duration_s == 15.0
    assert t.specs["power"].factor == 1.10
    assert t.arch_every_m == 0.0 and not t.per_segment
    pu = PowerUps(table=t)
    assert pu.award("segment") is None and pu.award("arch") is not None


@pytest.mark.parametrize("text", [
    "[aero]\nfactor = 3\n",
    "[power]\nduration_s = 0\n",
    "[power]\nfactor = \"fort\"\n",
    "[turbo]\nfactor = 1.2\n",
    "[obtain]\narch_every_m = 100\n",
    "[obtain]\nper_segment = 1\n",
    "[aero\n",
])
def test_load_table_rejects(tmp_path: Path, text: str):
    f = tmp_path / "powerups.toml"
    f.write_text(text, encoding="utf-8")
    with pytest.raises(PowerUpError):
        load_table(f)
