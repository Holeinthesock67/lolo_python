"""Équilibrage des bots à profil (lot T13) : calibrage par simulation, niveau et réglage.

Critères du cahier `docs/lots/LOT_T13_equilibrage_bots.md` §7 :
2. Parcours de démonstration et parcours de synthèse (plat de 20 km, col de 10 km à 7 %) : chaque profil
   calibré à 100 % finit à 0,5 % près du temps du cycliste de référence.
3. Niveau 110 % : chaque bot finit plus vite qu'à 100 %, dans le rapport du cycliste de référence (1 %).
4. Montée puis plat : le grimpeur calibré passe devant le diesel calibré dans la montée, et les deux
   finissent ensemble.
5. Réglage `bots.level_pct` hors bornes : `setting_invalid` ; `level_pct` de `start` hors bornes :
   `bot_invalid`.
6. Coût : calibrage de 4 bots sur 100 km sous 0,5 s.
"""

from __future__ import annotations

import asyncio
import math
import time

import pytest

from openride_core import settings
from openride_core.bots import (CALIBRATION_DT, PROFILES, BotError, ConstantPowerBot, ProfileBot, RefRider,
                                RouteProfile, bots_from_menu, calibrate, calibrate_bots, ride_time)
from openride_core.config import Config
from openride_core.demo_world import build_route
from openride_core.physics import PhysicsParams
from openride_core.route import Route

from test_contract_ipc import make_session
from test_profile_bots import FakeRoute, seg

RIDER = RefRider(250.0, PhysicsParams(mass_kg=79.0))   # 70 kg + vélo de 9 kg (valeurs par défaut)
BIKE = 9.0
DEMO = Route(build_route())
SYNTHETIC = {
    "plat": (FakeRoute(20000.0), ()),
    "col": (FakeRoute(10000.0, lambda s: 7.0), (seg("climb", 0.0, 10000.0),)),
}


class Beyond:
    """Le parcours sans ligne d'arrivée (le bot n'est pas arrêté net) : on mesure le passage de la ligne."""

    is_loop = False

    def __init__(self, route) -> None:
        self.route, self.length_m = route, math.inf

    def sample(self, s: float):
        return self.route.sample(min(s, self.route.length_m))


def finish_time(bot, route, dt: float = CALIBRATION_DT) -> float:
    """Temps d'arrivée d'un bot conduit par son propre `step`, dernier pas au prorata."""
    open_road, t = Beyond(route), 0.0
    while t < 24 * 3600.0:
        s0 = bot.s
        bot.step(dt, open_road)
        if bot.s >= route.length_m:
            return t + (route.length_m - s0) / bot.v
        t += dt
    return t


def reference_time(route, level_pct: float = 100.0) -> float:
    return finish_time(ConstantPowerBot(RIDER.ftp_w * level_pct / 100.0, params=RIDER.params), route)


def calibrated(profile: str, route, segments, level_pct: float = 100.0) -> ProfileBot:
    scale = calibrate(profile, route, level_pct, RIDER, segments, BIKE)
    return ProfileBot(profile, params=RIDER.params, segments=segments, scale=scale, bike_mass_kg=BIKE)


def test_inline_simulation_is_the_bot_step():
    """`ride_time` reprend les équations de `RiderPhysics.step` et `wbal_step` : même temps, à l'arrondi
    près, qu'un bot conduit par son `step` sur un parcours dont la pente change tous les 10 m."""
    route = FakeRoute(6000.0, lambda s: (5.0, -2.0, 8.0, 0.0)[int(s // 10.0) % 4] if s < 4000.0 else 1.0)
    prof = RouteProfile(route)
    assert ride_time(prof, RIDER.params, power_w=230.0) == pytest.approx(reference_time(route, 92.0), rel=1e-9)
    segments = (seg("climb", 0.0, 4000.0), seg("sprint", 5600.0, 6000.0))
    for p in PROFILES:
        live = ProfileBot(p, params=RIDER.params, segments=segments, bike_mass_kg=BIKE)
        sim = ProfileBot(p, params=RIDER.params, segments=segments, bike_mass_kg=BIKE)
        assert ride_time(prof, sim.params, bot=sim) == pytest.approx(finish_time(live, route), rel=1e-9), p


@pytest.mark.parametrize("name", ["demo", "plat", "col"])
def test_each_profile_at_100_pct_finishes_with_the_reference_rider(name):
    route, segments = (DEMO, ()) if name == "demo" else SYNTHETIC[name]
    t_ref = reference_time(route)
    for p in PROFILES:
        t_bot = finish_time(calibrated(p, route, segments), route)
        assert abs(t_bot / t_ref - 1.0) < 0.005, (name, p, t_bot, t_ref)


def test_level_110_is_faster_in_the_reference_ratio():
    route, segments = SYNTHETIC["col"]
    ratio_ref = reference_time(route, 110.0) / reference_time(route, 100.0)
    for p in PROFILES:
        t100 = finish_time(calibrated(p, route, segments, 100.0), route)
        t110 = finish_time(calibrated(p, route, segments, 110.0), route)
        assert t110 < t100
        assert abs((t110 / t100) / ratio_ref - 1.0) < 0.01, p


def test_climber_leads_the_climb_and_finishes_with_the_diesel():
    route = FakeRoute(25000.0, lambda s: 7.0 if s < 5000.0 else 0.0)
    segments = (seg("climb", 0.0, 5000.0),)
    climber, diesel = calibrated("climber", route, segments), calibrated("diesel", route, segments)
    while diesel.s < 5000.0:
        climber.step(CALIBRATION_DT, route)
        diesel.step(CALIBRATION_DT, route)
    assert climber.s > diesel.s + 50.0, "le grimpeur passe le sommet devant"
    t_c, t_d = finish_time(climber, route), finish_time(diesel, route)
    assert abs(t_c - t_d) / t_d < 0.01, "arrivée ensemble"


def test_calibrate_bots_uses_bot_level_then_setting_once_per_pair():
    route, segments = SYNTHETIC["plat"]
    bots = [ProfileBot("rouleur", bot_id="a"), ProfileBot("rouleur", bot_id="b", level_pct=110.0),
            ProfileBot("rouleur", bot_id="c"), ConstantPowerBot(200.0)]
    scales = calibrate_bots(bots, route, RIDER, 90.0, segments, BIKE)
    assert set(scales) == {("rouleur", 90.0), ("rouleur", 110.0)}
    assert bots[0].scale == bots[2].scale == scales[("rouleur", 90.0)] < bots[1].scale
    assert bots[0].wbal_pct == 100.0 and bots[0].cp_w == pytest.approx(PROFILES["rouleur"].cp_wkg * 72.0
                                                                       * bots[0].scale)
    assert bots[3].power_w == 200.0


def test_level_setting_and_start_bounds():
    cfg = Config()
    item = next(it for it in settings.current(cfg) if it["key"] == "bots.level_pct")
    assert item == {"key": "bots.level_pct", "label": "Niveau des bots", "group": "ride", "value": 100,
                    "applies": "next_session", "type": "int", "min": 50, "max": 150, "step": 5, "unit": "%"}
    assert settings.step(cfg, "bots.level_pct", 150, +1) == 150
    assert settings.step(cfg, "bots.level_pct", 100, -1) == 95
    for bad in (45, 155, "beaucoup"):
        with pytest.raises(settings.SettingError):
            settings.check(cfg, "bots.level_pct", bad)
    params = PhysicsParams()
    bots = bots_from_menu([{"kind": "profile", "profile": "diesel", "level_pct": 90},
                           {"kind": "profile", "profile": "diesel"}], params, 250.0, None, None)
    assert [b.level_pct for b in bots] == [90.0, None]
    for bad in (40, 160, True, "90"):
        with pytest.raises(BotError, match="niveau de bot"):
            bots_from_menu([{"kind": "profile", "profile": "diesel", "level_pct": bad}], params, 250.0, None, None)


def test_session_calibrates_at_start_and_refuses_bad_level(tmp_path, monkeypatch):
    async def scenario():
        s, cap = make_session(tmp_path, monkeypatch, port=6160)
        errors: list[tuple[str, str]] = []
        s.server.send_error = lambda code, message: errors.append((code, message))
        s._on_command("set_setting", {"key": "bots.level_pct", "value": 200}, 1)
        assert errors[-1][0] == "setting_invalid"
        s.cfg.bots.level_pct = 90
        s._on_command("select_route", {"route_id": "demo"}, 2)
        s._on_command("start", {"bots": [{"kind": "profile", "profile": "climber", "level_pct": 170}]}, 3)
        assert errors[-1][0] == "bot_invalid" and s.state.session_state == "READY"
        s._on_command("start", {"bots": [{"kind": "profile", "profile": "climber"},
                                         {"kind": "profile", "profile": "climber", "level_pct": 110}]}, 4)
        assert s.state.session_state == "RUNNING"
        rider = RefRider(s.cfg.rider.ftp_w, PhysicsParams.from_config(s.cfg))
        for b, level in zip(s.bots, (90.0, 110.0)):
            assert b.scale == calibrate("climber", s.route, level, rider, tuple(s._segments), s.cfg.bike.mass_kg)
            assert b.to_dict()["cp_w"] == round(b.cp_w, 1)
        assert s.bots[0].cp_w < s.bots[1].cp_w
        s._on_command("end_session", {"save": False}, 5)

    asyncio.run(scenario())


def test_four_bots_on_100_km_under_half_a_second():
    route = Route(build_route(100_000.0))
    segments = (seg("climb", 20000.0, 30000.0), seg("sprint", 60000.0, 60400.0))
    bots = [ProfileBot(p, bot_id=f"b{i}") for i, p in enumerate(PROFILES)]
    t0 = time.perf_counter()
    scales = calibrate_bots(bots, route, RIDER, 100.0, segments, BIKE)
    assert time.perf_counter() - t0 < 0.5
    assert len(scales) == 4 and all(math.isfinite(k) and k > 0 for k in scales.values())
