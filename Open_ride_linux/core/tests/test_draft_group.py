"""Abri dans un groupe (lot AS4) : une source comme P3, file de P3 à ±0,02, cœur de groupe plafonné à 0,55,
sources hors zone sans effet, gabarit de la source, coût avec 12 coureurs."""

import math
import time
from types import SimpleNamespace

import pytest
from openride_core import draft as d
from openride_core.bots import ConstantPowerBot
from openride_core.physics import PhysicsParams

L = d.BIKE_LENGTH_M
P3_LINE_FACTORS = (1.00, 1.12, 1.18)   # effet de file de P3, remplacé par le calcul de groupe
P3_CAP = 0.45


def src(s: float, lane: float | None = None, sid: str = "b", cda: float | None = None) -> SimpleNamespace:
    return SimpleNamespace(s=s, id=sid, kind="constant", lane_m=lane, cda_m2=cda)


def p3_line(gap0: float, gap_between: float, n: int) -> float:
    """Abri de P3 derrière une file de `n` bots espacés de `gap_between`, le premier à `gap0`."""
    return min(d.draft_coefficient(gap0) * P3_LINE_FACTORS[n - 1], P3_CAP)


def test_constants():
    assert d.ALPHA_GROUP_CAP == 0.55 and d.K_GROUP == 0.6
    assert d.CDA_REF_M2 == PhysicsParams().cda_m2


# --- critère 2 : une seule source, identique à P3 --------------------------------------------------

@pytest.mark.parametrize("lane", [None, 1.2])
def test_one_source_is_p3(lane):
    for gap in [0.0, 0.3, 0.5, 1.0, 2.0, 5.0, 10.0, 14.9, 14.99, 16.0]:
        alpha, _ = d.best_draft(100.0 - L - gap, [src(100.0, lane)], lane_m=lane)
        assert alpha == pytest.approx(d.draft_coefficient(gap), abs=1e-6), gap


# --- critère 3 : file de 2 ou 3 dans l'axe, à ±0,02 de P3 ------------------------------------------

@pytest.mark.parametrize("lane", [None, 1.2])
def test_line_in_axis_close_to_p3(lane):
    for gap0 in [0.3, 0.5, 1.0, 1.5, 2.0, 3.0]:
        for gap_b in [0.3, 0.5, 0.75, 1.0]:
            for n in (2, 3):
                line = [src(100.0 + i * (L + gap_b), lane, f"b{i}") for i in range(n)]
                alpha, best = d.best_draft(100.0 - L - gap0, line, lane_m=lane)
                assert alpha == pytest.approx(p3_line(gap0, gap_b, n), abs=0.02), (gap0, gap_b, n)
                assert best == "b0"


# --- critère 4 : cœur d'un groupe de 5 -------------------------------------------------------------

def group_of_five(me: float = 1.2) -> list[SimpleNamespace]:
    """Deux devant dans la roue, deux en diagonale (demi-roue décalée), un à côté."""
    s0 = 100.0
    return [src(s0 + L + 0.5, me, "a1"), src(s0 + 2 * L + 1.0, me, "a2"),
            src(s0 + L + 0.5, me - 0.6, "g1"), src(s0 + L + 0.5, me + 0.6, "g2"),
            src(s0 + 0.5, me - d.SIDE_CLEAR_M, "c1")]


def test_heart_of_a_group_of_five():
    alpha, best = d.best_draft(100.0, group_of_five(), lane_m=1.2)
    assert 0.45 <= alpha <= 0.55 and best == "a1"
    alone, _ = d.best_draft(100.0, group_of_five()[:1], lane_m=1.2)
    assert alpha > alone + 0.05


def test_never_above_cap():
    pack = [src(100.0 + L + 0.3 + 0.5 * i, 1.2 + 0.3 * ((i % 3) - 1), f"p{i}", 0.45) for i in range(11)]
    alpha, _ = d.best_draft(100.0, pack, lane_m=1.2)
    assert alpha == d.ALPHA_GROUP_CAP


# --- critère 5 : hors zone, aucune contribution ----------------------------------------------------

def test_sources_aside_or_behind_give_nothing():
    lead = [src(100.0 + L + 0.5, 1.2, "a")]
    base, _ = d.best_draft(100.0, lead, lane_m=1.2)
    far_side = [src(100.0 + L + 0.5, 1.2 + 1.6, "x"), src(100.0 + 0.5, 1.2 - 1.6, "y")]
    behind = [src(100.0 - L - 0.5, 1.2, "z"), src(100.0 - 0.5, 1.2 + 0.9, "w")]
    assert d.best_draft(100.0, lead + far_side + behind, lane_m=1.2) == (base, "a")
    assert d.best_draft(100.0, far_side + behind, lane_m=1.2) == (0.0, None)


def test_side_by_side_gives_flank_shelter_only_in_two_dimensions():
    alpha, best = d.best_draft(100.0, [src(100.5, 1.2 + d.SIDE_CLEAR_M, "c")], lane_m=1.2)
    assert alpha == pytest.approx(d.FLANK_ALPHA) and best == "c"
    assert d.best_draft(100.0, [src(100.5, None, "c")]) == (0.0, None)   # une dimension : comme P3


# --- gabarit de la source ---------------------------------------------------------------------------

def test_source_size():
    gap = 0.5
    ref = d.draft_coefficient(gap)
    big, _ = d.best_draft(100.0 - L - gap, [src(100.0, cda=0.40)])
    small, _ = d.best_draft(100.0 - L - gap, [src(100.0, cda=0.20)])
    assert big == pytest.approx(ref * math.sqrt(0.40 / 0.32))
    assert small == pytest.approx(ref * d.SIZE_MIN)
    huge, _ = d.best_draft(100.0 - L - gap, [src(100.0, cda=1.0)])
    assert huge == pytest.approx(ref * d.SIZE_MAX)


def test_bot_size_ignores_the_push():
    b = ConstantPowerBot(250.0, params=PhysicsParams(cda_m2=0.36))
    b.push = d.PUSH_FROM_BEHIND
    b.params.cda_m2 *= 1.0 - b.push      # comme la session après le pas précédent
    assert d.size_factor(b) == pytest.approx(math.sqrt(0.36 / 0.32))
    assert d.size_factor(d.Source(0.0, 0.0, cda_m2=0.32)) == 1.0
    assert d.size_factor(d.Source(0.0, 0.0)) == 1.0


# --- poussée inchangée, bots en groupe ----------------------------------------------------------------

def test_bots_in_group_get_group_draft():
    bots = [ConstantPowerBot(250.0, bot_id=f"b{i}", s=100.0 + i * (L + 0.5), v=9.0) for i in range(3)]
    for b in bots:
        b.lane.m = 1.2
    last = bots[0]
    target, _ = d.draft_for(last.s, bots, 20_000.0, True, skip=last, lane_m=1.2)
    d.update_bots(bots, None, 10.0, 20_000.0, True)   # dt long : abri lissé = cible
    assert last.draft == pytest.approx(target, rel=1e-3)
    assert last.draft > d.draft_coefficient(0.5)
    assert bots[1].push == d.PUSH_FROM_BEHIND and last.push == 0.0


# --- critère 6 : coût avec 12 coureurs ----------------------------------------------------------------

def test_cost_twelve_riders():
    bots = [ConstantPowerBot(240.0, bot_id=f"b{i}", s=1.2 * i, v=9.0) for i in range(11)]
    for i, b in enumerate(bots):
        b.lane.m = 0.3 + 0.45 * (i % 4)
    rider = d.Source(6.0, 9.0, lane_m=1.2, cda_m2=0.32)
    n = 2000
    best = math.inf
    for _ in range(3):
        t0 = time.perf_counter()
        for _ in range(n):
            d.update_bots(bots, rider, 0.02, 20_000.0, True)
            d.best_draft(rider.s, bots, 20_000.0, True, rider.v, lane_m=rider.lane_m)
        best = min(best, (time.perf_counter() - t0) * 1000.0 / n)
    assert best < 0.2, f"{best:.4f} ms par pas"
