"""Tests des braquets (SRS §12) et de la configuration."""

from pathlib import Path

import pytest

from openride_core.config import Config, ConfigError, GearingConfig, from_dict, load, validate
from openride_core.gearing import Gearing


def test_fixed_step_per_click():
    """15 novembre : chaque clic ajoute 0,5 point de pente, braquet 12 neutre (1 : −5,5 %, 24 : +6 %)."""
    g = Gearing(GearingConfig())
    assert len(g.offsets) == 24
    steps = [b - a for a, b in zip(g.offsets, g.offsets[1:])]
    assert max(steps) - min(steps) < 1e-9 and steps[0] == pytest.approx(0.5)   # même pas partout
    assert g.offsets[0] == pytest.approx(-5.5)
    assert g.offsets[11] == 0.0
    assert g.offsets[-1] == pytest.approx(6.0)


def test_start_gear_is_neutral():
    g = Gearing(GearingConfig())
    assert g.k == 12
    for terrain in (-6.0, 0.0, 4.0):
        assert g.effective_grade(terrain, 0.5) == pytest.approx(terrain * 0.5)


def test_click_feels_the_same_on_climb_flat_and_descent():
    """Remarque du 15 novembre : pas assez de différence entre les braquets. Un clic vaut 0,5 point partout,
    à toute difficulté (la difficulté ne touche que le terrain), tant qu'aucune borne n'est atteinte."""
    g = Gearing(GearingConfig())
    for terrain in (-4.0, 0.0, 6.0):
        for difficulty in (0.5, 1.0):
            g.k = 14
            a = g.effective_grade(terrain, difficulty)
            g.k = 15
            assert g.effective_grade(terrain, difficulty) - a == pytest.approx(0.5)


def test_big_gear_is_hard_in_descent_small_gear_easy_on_steep_climb():
    """Remarques du 15 novembre : en descente le 24 était le plus facile, et le 1 trop dur dans les fortes
    pentes (12 % à 50 % : 2,2 % envoyés)."""
    g = Gearing(GearingConfig())
    g.k = 24
    assert g.effective_grade(-4.0, 1.0) == pytest.approx(2.0)     # on peut appuyer en descente
    descent = []
    for k in range(1, 25):
        g.k = k
        descent.append(g.effective_grade(-5.0, 0.5))
    assert all(a < b for a, b in zip(descent, descent[1:]))      # chaque clic durcit, aussi en descente
    g.k = 1
    assert g.effective_grade(12.0, 0.5) == pytest.approx(0.5)


def test_effective_grade_bounds():
    g = Gearing(GearingConfig())
    g.k = 24
    assert g.effective_grade(12.0) == 16.0          # borne haute
    g.k = 1
    assert g.effective_grade(-10.0) == -10.0        # borne basse
    for k in range(1, 25):
        g.k = k
        for terrain in (-25, -5, 0, 5, 25):
            assert -10.0 <= g.effective_grade(terrain) <= 16.0


def test_small_gear_never_turns_a_climb_into_a_descent():
    """Essai du 24 octobre : une montée reste au moins plate."""
    g = Gearing(GearingConfig())
    for k in range(1, 25):
        g.k = k
        for terrain in (0.5, 1.0, 3.0, 6.0):
            assert g.effective_grade(terrain) >= 0.0
    g.k = 1
    assert g.effective_grade(3.0) == 0.0
    assert g.effective_grade(8.0) == pytest.approx(2.5)


def test_track_offset_shifts_whole_range_harder():
    """Vélodrome : `[velodrome] gear_offset_pct` (0,5 point) décale toute la gamme, sans changer le pas."""
    cfg = Config()
    assert cfg.velodrome.gear_offset_pct == pytest.approx(0.5)
    g = Gearing(GearingConfig())
    for k in range(1, 25):
        g.k = k
        assert g.effective_grade(0.0, place_offset_pct=0.5) == pytest.approx(g.effective_grade(0.0) + 0.5)
    g.k = 12
    assert g.effective_grade(30.0, place_offset_pct=0.5) == g.grade_max          # bornes inchangées


def test_neutral_gear_out_of_range_is_refused():
    with pytest.raises(ConfigError) as info:
        validate(from_dict({"gearing": {"neutral_gear": 30}}))
    assert (info.value.section, info.value.key) == ("gearing", "neutral_gear")


def test_shift_limits():
    g = Gearing(GearingConfig())
    for _ in range(30):
        g.shift_up()
    assert g.k == 24
    for _ in range(30):
        g.shift_down()
    assert g.k == 1


def test_nan_grade_gives_flat_and_infinite_grade_is_clamped():
    # Audit du 24 octobre (R4) : NaN passait le bornage et faisait lever l'encodage FTMS.
    g = Gearing(GearingConfig())
    assert g.effective_grade(float("nan")) == 0.0
    assert g.effective_grade(5.0, difficulty=float("nan")) == 0.0
    assert g.effective_grade(float("inf")) == g.grade_max
    assert g.effective_grade(float("-inf")) == g.grade_min


def test_config_defaults_and_partial_override(tmp_path: Path):
    assert load(tmp_path / "absent.toml") == Config()
    f = tmp_path / "config.toml"
    f.write_text('[rider]\nftp_w = 280\n[gearing]\nn_gears = 20\n[inconnu]\nx = 1\n', encoding="utf-8")
    cfg = load(f)
    assert cfg.rider.ftp_w == 280.0 and isinstance(cfg.rider.ftp_w, float)
    assert cfg.rider.mass_kg == 75.0
    assert cfg.gearing.n_gears == 20
    assert cfg.total_mass_kg == 84.0


def test_from_dict_ignores_unknown_keys():
    cfg = from_dict({"bike": {"cda_m2": 0.3, "foo": 1}})
    assert cfg.bike.cda_m2 == 0.3
