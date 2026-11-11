"""Lot TT2 : modèle unique de bonus décrit par des données (Plume, Casque, Puissance, Enclume)."""

from __future__ import annotations

import hashlib
import json
import random
import time
from collections import Counter
from pathlib import Path

import pytest

from openride_core import classic, fit_export, powerups, profile
from openride_core.config import Config
from openride_core.grandprix import effects as gp_effects
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.physics import PhysicsParams, RiderPhysics, steady_speed
from openride_core.powerups import (
    DEFAULT_TABLE,
    Context,
    EffectSpec,
    PowerUpError,
    PowerUps,
    descent_ahead,
    load_table,
)
from openride_core.session import CoreSession
from openride_core.wind import grade_offset_pct
from openride_core.zwift_click import InputEvent

PLAN = PhysicsParams(mass_kg=84.0, cda_m2=0.32, crr=0.004)   # cycliste et vélo du plan §2
DESCENT = Context(grade_pct=-4.0, has_bots=False, descent_ahead=lambda: True)
FLAT = Context(grade_pct=0.0)


# --- table ------------------------------------------------------------------------------------

def test_one_table_no_branch_per_bonus():
    s = DEFAULT_TABLE.specs
    assert list(s)[:4] == ["feather", "aero", "power", "anvil"]   # puis les lots TT3 à TT5
    assert [(k, v.effect, v.factor, v.duration_s) for k, v in s.items()][:4] == [
        ("feather", "mass", 0.90, 20.0), ("aero", "cda", 0.75, 15.0), ("power", "power", 1.10, 15.0),
        ("anvil", "mass", 1.6, 15.0)]
    assert DEFAULT_TABLE.kinds("classiques") == ("feather", "aero", "power")
    assert DEFAULT_TABLE.kinds("tactiques")[:4] == ("feather", "aero", "power", "anvil")
    # Les objets du Grand Prix sont des lignes du même modèle (plan GP §5).
    assert gp_effects.EffectSpec is EffectSpec and gp_effects.EFFECTS is powerups.EFFECTS
    assert {"kick", "slip", "speed_floor", "cap", "immune", "wind", "mass", "cda", "breakaway"} <= set(powerups.EFFECTS)
    with pytest.raises(ValueError):
        powerups.PowerUpSpec("x", "kick", 1.2, 5.0, "X")       # effet réservé au Grand Prix
    with pytest.raises(ValueError):
        powerups.PowerUpSpec("x", "mass", 1.2, 5.0, "X", refuse_unless=(("lune", "erg"),))


def test_file_sections_bounds_and_alias(tmp_path: Path):
    f = tmp_path / "powerups.toml"
    f.write_text("[lightweight]\nduration_s = 15\n[anvil]\nfactor = 2.0\n", encoding="utf-8")
    t = load_table(f)
    assert t.specs["feather"].duration_s == 15.0 and t.specs["anvil"].factor == 2.0
    for text in ("[anvil]\nfactor = 0.8\n", "[anvil]\nfactor = 3\n", "[feather]\nfactor = 1.2\n",
                 "[lightweight]\nfactor = 0.9\n[feather]\nfactor = 0.9\n"):
        f.write_text(text, encoding="utf-8")
        with pytest.raises(PowerUpError):
            load_table(f)


# --- tirage selon le contexte -----------------------------------------------------------------

def test_classiques_draw_ignores_context_like_2_0():
    a, b = PowerUps(seed=3), PowerUps(seed=3)
    assert [a.award("segment") for _ in range(50)] == [b.award("segment", DESCENT) for _ in range(50)]
    assert "anvil" not in {a.award("arch", DESCENT) for _ in range(300)}


def test_tactiques_draw_anvil_only_with_a_descent_ahead():
    pu = PowerUps(seed=5, set_name="tactiques")
    assert "anvil" not in Counter(pu.award("segment", FLAT) for _ in range(500))
    drawn = Counter(pu.award("segment", DESCENT) for _ in range(2000))
    assert set(drawn) == {"feather", "aero", "power", "anvil"} and all(400 < n < 600 for n in drawn.values())


def test_descent_ahead_needs_300_m_under_minus_1_5_within_5_km():
    profile_ = lambda start, length, g: (lambda s: g if start <= s < start + length else 0.0)
    assert descent_ahead(profile_(1000.0, 350.0, -3.0), 0.0)
    assert not descent_ahead(profile_(1000.0, 250.0, -3.0), 0.0)          # trop courte
    assert not descent_ahead(profile_(1000.0, 1000.0, -1.0), 0.0)         # pas assez raide
    assert not descent_ahead(profile_(5200.0, 1000.0, -3.0), 0.0)         # au-delà des 5 km
    assert not descent_ahead(profile_(1000.0, 1000.0, -3.0), 0.0, length_m=1100.0)   # après l'arrivée


# --- activation, refus, suspension ------------------------------------------------------------

def test_anvil_refused_unless_descending_reserve_kept():
    pu = PowerUps(set_name="tactiques")
    pu.reserve = "anvil"
    assert not pu.activate(10.0, Context(grade_pct=-1.0))
    assert pu.reserve == "anvil" and pu.active is None
    assert pu.contract()["refused"] == {"kind": "anvil", "reason": "no_descent"}
    pu.step(1.98)
    assert "refused" in pu.contract()
    pu.step(0.04)
    assert "refused" not in pu.contract()                                   # 2 s
    assert pu.activate(20.0, Context(grade_pct=-1.5)) and pu.active == "anvil"
    assert pu.params(PLAN).mass_kg == pytest.approx(84.0 * 1.6)


def test_anvil_held_above_minus_half_percent_time_runs():
    pu = PowerUps(set_name="tactiques")
    pu.reserve = "anvil"
    assert pu.activate(0.0, DESCENT)
    pu.step(5.0, Context(grade_pct=0.0))
    assert pu.held and pu.params(PLAN) is PLAN and pu.remaining_s == pytest.approx(10.0)
    pu.step(1.0, Context(grade_pct=-0.6))
    assert not pu.held and pu.params(PLAN).mass_kg == pytest.approx(134.4)


def test_erg_refusal_reason():
    pu = PowerUps()
    pu.reserve = "aero"
    pu.set_erg(True)
    assert not pu.activate(1.0) and pu.contract()["refused"]["reason"] == "erg" and pu.reserve == "aero"


def test_sim_feel_uses_base_mass_for_mass_bonuses():
    pu = PowerUps()
    pu.reserve = "feather"
    assert pu.activate(0.0)
    p = pu.params(PLAN)
    assert p.mass_kg == pytest.approx(75.6) and pu.feel_params(p, PLAN).mass_kg == 84.0
    off_base = grade_offset_pct(10.0, 3.0, 0.3, 200.0, PLAN, 10.0)
    assert grade_offset_pct(10.0, 3.0, 0.3, 200.0, pu.feel_params(p, PLAN), 10.0) == off_base
    pu = PowerUps()
    pu.reserve = "aero"
    assert pu.activate(0.0)
    assert pu.feel_params(pu.params(PLAN), PLAN).cda_m2 == pytest.approx(0.24)   # le CdA se sent


# --- gains dans le terrain idéal (plan §2, test sur physics.py) ------------------------------

def gain_s(kind: str, grade: float, power_w: float = 250.0, horizon_s: float = 60.0, dt: float = 0.02) -> float:
    """Temps gagné sur un cycliste identique sans bonus, mesuré `horizon_s` après l'activation."""
    pu = PowerUps(set_name="tactiques")
    pu.reserve = kind
    ctx = Context(grade_pct=grade)
    assert pu.activate(0.0, ctx)
    v = steady_speed(power_w, grade, PLAN)
    a, b = RiderPhysics(PLAN, 0.0, v), RiderPhysics(PLAN, 0.0, v)
    t = 0.0
    while t < horizon_s - 1e-9:
        t += dt
        a.p = pu.params(PLAN)
        a.step(pu.power(power_w), grade, dt=dt)
        b.step(power_w, grade, dt=dt)
        pu.step(dt, ctx)
    return (a.s - b.s) / v


@pytest.mark.parametrize("kind, grade, plan_s", [
    ("feather", 8.0, 2.0), ("anvil", -6.0, 2.3), ("anvil", -3.0, 1.5), ("aero", 0.0, 1.3), ("power", 8.0, 1.4)])
def test_gain_in_ideal_terrain_matches_plan(kind, grade, plan_s):
    """Chiffres du plan §2 à 0,15 s près. Plume et Enclume à −6 % sont dans la cible de 1,5 à 2,5 s ;
    Casque (1,24 s), Puissance (1,40 s) et Enclume à −3 % (1,46 s) restent un peu en dessous, comme le
    plan l'annonçait : l'équilibrage est le travail du lot TT8."""
    assert gain_s(kind, grade) == pytest.approx(plan_s, abs=0.15)


@pytest.mark.parametrize("kind, grade", [("feather", 8.0), ("anvil", -6.0)])
def test_gain_within_target(kind, grade):
    assert 1.5 <= gain_s(kind, grade) <= 2.5


# --- séance : non-régression et refus ---------------------------------------------------------

class _Seeded(random.Random):
    def __init__(self, seed=None):
        super().__init__(7)


def _trace(tmp: Path, monkeypatch: pytest.MonkeyPatch, mode: str, toml: str = "") -> tuple[str, float]:
    """Séance rejouée de 10 min sur le parcours de démonstration, Z toutes les 40 s, sans vent ni bot ;
    empreinte de (s, v, pente envoyée, objet `powerup`) toutes les secondes."""
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp / "act")
    monkeypatch.setattr(profile, "PROFILE_PATH", tmp / "profile.json")
    monkeypatch.setattr(powerups.random, "Random", _Seeded)
    wall = [1_790_000_000.0]
    monkeypatch.setattr(time, "time", lambda: wall[0])
    (tmp / "powerups.toml").write_text(toml, encoding="utf-8")
    cfg = Config()
    cfg.powerups.mode = mode
    cfg.ipc.port_state, cfg.ipc.port_commands = 7990, 7991
    s = CoreSession(cfg, driver=MockDriver(base_power_w=250.0, ramp_amplitude_w=0.0), inputs=[NullProvider()],
                    journal_dir=tmp / "j", routes_root=tmp / "r", workouts_dir=tmp / "w",
                    records_path=tmp / "rec.json", powerups_path=tmp / "powerups.toml")
    s.server.send_raw = lambda m, max_size=None: None
    s.server.send_input_event = lambda ev: None
    s._on_command("select_route", {"route_id": "demo"}, 1)
    s._on_command("start", {}, 2)
    h = hashlib.sha256()
    for i in range(int(600 / 0.02)):
        wall[0] += 0.02
        s._step(0.02, wall[0])
        if i % 2000 == 1999:
            s._handle_input(InputEvent.Z_SHORT)
        if i % 50 == 0:
            pu = None
            if s.race:
                s._fill_race_frame()
                pu = s.state.to_dict().get("powerup")
                if pu:   # nom de la 2.0 lu comme celui du contrat 1.13 (référence calculée sur `main`)
                    pu = {k: {"light": "feather"}.get(v, v) if isinstance(v, str) else v for k, v in pu.items()}
            h.update(json.dumps([round(s.physics.s, 6), round(s.physics.v, 6), round(s._grade_sent, 4), pu]).encode())
    return h.hexdigest(), round(s.physics.s, 6)


# Empreintes de la même séance rejouée avec le code de `main` du 8 novembre (e88969b7, avant TT1 et TT2) :
# mode `off`, et mode `on` de la 2.0 avec `[lightweight] duration_s = 15` (`light` lu `feather`).
GOLDEN_OFF = ("136ab72b667e12dce4c2d8556a4bf44cd269b6d08ca52cf59d68966224f9fe97", 4126.41948)
GOLDEN_ON = ("0f1ffcefa789395f510b2fd33184400574cea4fcfde5467e0d91edf8aeb92412", 4140.599843)


def test_off_session_identical_to_2_0(tmp_path, monkeypatch):
    assert _trace(tmp_path, monkeypatch, "off") == GOLDEN_OFF


def test_classiques_session_identical_to_2_0_with_15_s_feather(tmp_path, monkeypatch):
    """Seules différences voulues avec la 2.0 : la Plume dure 20 s (plan §2, ramenée ici à 15 s), son nom
    au contrat est `feather` (la référence remplace `light`), et le supplément de pente SIM d'un bonus de
    masse est calculé à la masse de base (sans vent ni abri ici, il n'y en a pas)."""
    assert _trace(tmp_path, monkeypatch, "classiques", "[lightweight]\nduration_s = 15\n") == GOLDEN_ON


def test_classic_race_frame_shows_refusal_and_journal_line():
    race = classic.ClassicRace("demo", (), 5000.0, powerups_on=True, powerup_set="tactiques",
                               grade_at=lambda s: 0.0)
    race.powerups.reserve = "anvil"
    race.step(0.0, 0.02, 100.0, 250.0, ())
    assert not race.activate(0.02)
    f = race.frame(0.02, 100.0, 10.0, ())
    assert f["powerup"] == {"held": "anvil", "active": None, "remaining_s": 0.0,
                            "refused": {"kind": "anvil", "reason": "no_descent"}}
    assert race.journal[-1]["refused"] == "no_descent" and race.journal[-1]["powerup"] == "anvil"
    race.set_erg(True)
    race.powerups.refused = None
    assert "powerup" not in race.frame(0.04, 100.0, 10.0, ())                    # ERG : absent (T-Q2)
    assert not race.activate(0.04)
    assert race.frame(0.04, 100.0, 10.0, ())["powerup"]["refused"]["reason"] == "erg"   # sauf 2 s après un refus
    for _ in range(101):
        race.step(0.04, 0.02, 100.0, 250.0, ())
    assert "powerup" not in race.frame(2.1, 100.0, 10.0, ())
