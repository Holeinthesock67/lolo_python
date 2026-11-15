"""Tests des braquets (SRS §12) et de la configuration."""

from pathlib import Path

import pytest

from openride_core.config import Config, GearingConfig, from_dict, load
from openride_core.gearing import Gearing


def test_ratios_strictly_increasing():
    g = Gearing(GearingConfig())
    assert len(g.ratios) == 24
    assert all(a < b for a, b in zip(g.ratios, g.ratios[1:]))
    assert g.ratios[0] == pytest.approx(0.3185)
    assert g.ratios[-1] == pytest.approx(3.38)


def test_range_widened_30_percent_at_both_ends_twice():
    """Demandes des 14 et 15 novembre : à chaque fois braquet 1 plus facile de 30 %, braquet 24 plus dur de 30 %
    (0,65 à 2,00 avant le 14, 0,455 à 2,60 le 14)."""
    g = Gearing(GearingConfig())
    assert g.ratios[0] == pytest.approx(0.65 * 0.7 * 0.7)
    assert g.ratios[-1] == pytest.approx(2.00 * 1.3 * 1.3)
    steps = [b / a for a, b in zip(g.ratios, g.ratios[1:])]
    assert max(steps) - min(steps) < 1e-9          # même pas sur toute la gamme : aucune exception
    for terrain in (0.0, 6.0):                     # chaque clic durcit, à plat comme en montée (difficulté 50 %)
        sent = []
        for k in range(1, 25):
            g.k = k
            sent.append(g.effective_grade(terrain, 0.5))
        assert all(a < b for a, b in zip(sent, sent[1:]))


def test_r12_is_about_neutral():
    g = Gearing(GearingConfig())
    assert g.k == 12
    assert g.ratio == pytest.approx(0.986, abs=0.01)


def test_step_about_11_percent():
    g = Gearing(GearingConfig())
    assert g.ratios[1] / g.ratios[0] == pytest.approx(1.108, abs=0.002)


def test_effective_grade_formula_and_bounds():
    g = Gearing(GearingConfig())
    g.k = 24
    assert g.effective_grade(0.0) == pytest.approx((0 + 2) * 3.38 - 2)
    assert g.effective_grade(12.0) == 16.0          # borne haute
    assert g.effective_grade(-10.0) == -10.0        # borne basse : -20 % bornée
    g.k = 1
    assert g.effective_grade(-10.0) == pytest.approx(-8 * 0.3185 - 2)  # petit braquet : descente adoucie
    for k in range(1, 25):
        g.k = k
        for terrain in (-25, -5, 0, 5, 25):
            assert -10.0 <= g.effective_grade(terrain) <= 16.0


def test_effective_grade_keeps_terrain_sign():
    """Essai du 24 octobre : un petit braquet ne doit pas faire d'une montée une descente."""
    g = Gearing(GearingConfig())
    for k in range(1, 25):
        g.k = k
        for terrain in (0.5, 1.0, 3.0, 6.0):
            assert g.effective_grade(terrain) >= 0.0
            assert g.effective_grade(-terrain) <= 0.0
    g.k = 1
    assert g.effective_grade(1.0) == 0.0          # (1 + 2) × 0,3185 − 2 < 0 : ramené à plat
    assert g.effective_grade(6.0) == pytest.approx((6 + 2) * 0.3185 - 2)
    g.k = 24
    assert g.effective_grade(-1.0) == 0.0         # (−1 + 2) × 3,38 − 2 > 0 : une descente reste au plus plate


def test_small_gear_flattens_gentle_climbs_only():
    """Séance A du 28 octobre : en braquet 1 à 50 %, 3,6 % devenait 0,12 % (route plate, plage 0,40–3,00).

    Depuis le 15 novembre (0,3185, demande du propriétaire), le braquet 1 rend plates les montées jusqu'à
    2 / 0,3185 − 2 ≈ 4,3 % : point à juger en sortie. Au-delà, la montée se sent encore, et dès le braquet 3
    une montée de 3,6 % reste une montée."""
    g = Gearing(GearingConfig())
    g.k = 1
    assert 2 / g.ratio - 2 == pytest.approx(4.28, abs=0.01)
    assert g.effective_grade(3.6, 0.5) == 0.0
    assert g.effective_grade(6.0, 0.5) == pytest.approx(((6 + 2) * 0.3185 - 2) * 0.5)
    assert g.effective_grade(6.0, 0.5) > 0.2
    g.k = 3
    assert g.effective_grade(3.6, 0.5) > 0.0


def test_track_scale_shifts_whole_range_harder():
    """Vélodrome (14 novembre) : `[velodrome] gear_scale` 1,25 multiplie chaque rapport, sans changer l'étagement."""
    cfg = Config()
    assert cfg.velodrome.gear_scale == pytest.approx(1.25)
    g = Gearing(GearingConfig())
    for k in range(1, 25):
        g.k = k
        assert g.effective_grade(0.0, scale=1.25) == pytest.approx(2 * g.ratio * 1.25 - 2)
        assert g.effective_grade(0.0, scale=1.25) > g.effective_grade(0.0)
        assert g.effective_grade(0.0, scale=1.0) == g.effective_grade(0.0)
    g.k = 24
    assert g.effective_grade(0.0, scale=1.25) == pytest.approx(6.45)  # 2 × 3,38 × 1,25 − 2 à plat
    g.k = 12
    assert g.effective_grade(30.0, scale=1.25) == g.grade_max          # bornes inchangées


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
