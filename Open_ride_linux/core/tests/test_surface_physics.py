"""Roulement des routes non revêtues (lot U21, `surface_physics.py`) : facteurs, surface effective selon
`[gravel] mode`, supplément de pente, transition de 20 m, colonne `surface` de la route, configuration."""

from __future__ import annotations

import json

import pytest

from openride_core import surface_physics as SP
from openride_core.config import Config, ConfigError, from_dict
from openride_core.demo_world import build_route
from openride_core.route import Route, WorldError


def _cfg() -> Config:
    return Config()


def _route(surface: list[str] | None, length_m: float = 1000.0) -> Route:
    data = build_route(length_m, grade=lambda s: 0.0)
    if surface is not None:
        data["surface"] = surface
    return Route(json.loads(json.dumps(data)))


def test_offset_on_flat_crr_0004_factor_25() -> None:
    assert SP.grade_offset_pct(0.004, 2.5, 0.0) == pytest.approx(0.6, abs=0.01)
    assert SP.grade_offset_pct(0.004, 1.0, 5.0) == 0.0
    assert SP.grade_offset_pct(0.004, 3.0, 20.0) == pytest.approx(0.8 * 0.98058, abs=0.001)   # cos θ


def test_factors_and_effective_surface() -> None:
    g = _cfg().gravel
    assert (g.mode, g.factor_compacted, g.factor_gravel, g.factor_dirt) == ("off", 2.0, 2.5, 3.0)
    assert [SP.crr_factor(s, g) for s in SP.SURFACES] == [1.0, 2.0, 2.5, 3.0]
    assert SP.effective_surface("dirt", "off") == "paved"
    assert SP.effective_surface("dirt", "auto") == "dirt"
    assert SP.effective_surface("paved", "gravel") == "gravel"     # surface imposée (U-Q8)
    assert SP.effective_surface("dirt", "compacted") == "compacted"


def test_route_surface_column_and_surface_at() -> None:
    n = _route(None).n
    r = _route(["paved"] * 50 + ["gravel"] * (n - 50))
    assert r.surface_at(495.0) == "paved" and r.surface_at(500.0) == "gravel" and r.surface_at(504.9) == "gravel"
    assert r.surface_at(r.length_m) == "gravel" and r.surface_at(-5.0) == "paved"
    assert _route(None).surface is None and _route(None).surface_at(300.0) == "paved"
    with pytest.raises(WorldError, match="surface"):
        _route(["sand"] * n)
    with pytest.raises(WorldError, match="surface"):
        _route(["paved"] * (n - 1))


def test_transition_over_20m_without_step() -> None:
    g = _cfg().gravel
    n = _route(None).n
    r = _route(["paved"] * 50 + ["gravel"] * (n - 50))
    values = [SP.blended_factor(r, 495.0 + k * 0.5, "auto", g) for k in range(60)]
    assert values[0] == 1.0 and values[-1] == 2.5
    assert all(b >= a for a, b in zip(values, values[1:]))
    assert max(b - a for a, b in zip(values, values[1:])) <= 1.5 * 0.5 / 20.0 + 1e-9    # pente du fondu, pas de marche
    assert SP.blended_factor(r, 510.0, "auto", g) == pytest.approx(1.75)
    assert SP.blended_factor(r, 300.0, "off", g) == 1.0
    assert SP.blended_factor(_route(None), 300.0, "gravel", g) == 2.5   # imposée sans colonne (critère 4 bis)
    assert SP.blended_factor(_route(None), 300.0, "auto", g) == 1.0


@pytest.mark.parametrize("section, message", [
    ({"mode": "boue"}, "mode"), ({"factor_gravel": 3.5}, "factor_gravel"), ({"factor_dirt": 0.5}, "factor_dirt"),
])
def test_invalid_gravel_config(section, message) -> None:
    with pytest.raises(ConfigError, match=message):
        from_dict({"gravel": section})


def test_gravel_config_read() -> None:
    cfg = from_dict({"gravel": {"mode": "auto", "factor_compacted": 1.5}})
    assert cfg.gravel.mode == "auto" and cfg.gravel.factor_compacted == 1.5 and cfg.gravel.factor_dirt == 3.0
