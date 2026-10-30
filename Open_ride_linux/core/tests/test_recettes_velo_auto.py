"""Lot X48 : la logique des blocs vélo encore ouverts, vérifiée sans vélo (`pytest -m recette_sans_velo`).

Chaque test reprend un bloc de la file des mesures du PC et vérifie ce que le core décide, avec
le trainer simulé. Le ressenti, la consigne et la résistance réelles du trainer restent sur le vélo
(décision de l'utilisateur du 29 octobre) :
- 7ae (O19) : en ERG, aucune consigne envoyée au trainer sous 50 W, quel que soit le chemin ;
- 7af (AS1) : trois bots à 230, 240 et 250 W et un cycliste à 240 W, 10 min sur le plat.
"""

from __future__ import annotations

import asyncio

import pytest
from test_draft import AS1Rider, FlatRoute, as1_ride
from test_workout import make_session, run, workouts_dir  # noqa: F401 (fixture)

from openride_core import draft as d
from openride_core.bots import ConstantPowerBot
from openride_core.free_erg import CADENCE_BAND_PCT
from openride_core.workout import BIAS_MIN_PCT, ERG_MIN_W
from openride_core.zwift_click import InputEvent

pytestmark = pytest.mark.recette_sans_velo

FREERIDE_ZWO = """<workout_file><name>Recette O19</name><workout>
<Warmup Duration="20" PowerLow="0.25" PowerHigh="0.4"/>
<FreeRide Duration="20"/>
<SteadyState Duration="20" Power="0.3"/>
<Cooldown Duration="20" PowerLow="0.3" PowerHigh="0.1"/>
</workout></workout_file>"""


def spy_targets(driver) -> list[float]:
    """Toutes les consignes ERG que la séance demande au trainer simulé, dans l'ordre."""
    sent: list[float] = []
    real = driver.set_target_power

    def spy(watts: float) -> bool:
        sent.append(watts)
        return real(watts)

    driver.set_target_power = spy
    return sent


# --- 7ae : aucune roue libre en ERG (lot O19) ---------------------------------------------------

def test_7ae_workout_with_freeride_never_sends_less_than_50_w(tmp_path, monkeypatch, workouts_dir):
    """Entraînement bas (FTP 100 W, blocs de 10 à 40 %), biais au minimum, FreeRide, pause, reprise,
    bloc suivant et fin : chaque consigne envoyée au trainer vaut au moins 50 W."""
    (workouts_dir / "recette_o19.zwo").write_text(FREERIDE_ZWO, encoding="utf-8")

    async def scenario():
        s, driver, errors = make_session(tmp_path, monkeypatch, workouts_dir, port=6610)
        s.cfg.rider.ftp_w = 100.0
        sent = spy_targets(driver)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("select_workout", {"workout_id": "recette_o19"}, 2)
        s._on_command("start", {}, 3)
        for _ in range(20):                               # biais au plus bas
            s._handle_input(InputEvent.MINUS_SHORT)
        assert s.state.erg["bias_pct"] == BIAS_MIN_PCT
        run(s, 30.0)                                       # échauffement puis FreeRide
        assert s.state.erg["block_type"] == "steady" and s.state.erg["target_w"] == ERG_MIN_W
        s._on_command("pause", {}, 4)
        run(s, 5.0)
        s._on_command("resume", {}, 5)
        run(s, 5.0)
        s._handle_input(InputEvent.Z_SHORT)                # bloc suivant
        run(s, 50.0)                                       # palier bas, retour au calme, fin
        assert not errors
        return sent

    sent = asyncio.run(scenario())
    assert sent, "aucune consigne ERG envoyée"
    assert min(sent) >= ERG_MIN_W, f"consigne sous {ERG_MIN_W} W : {min(sent)} W"


def test_7ae_free_erg_and_cadence_lock_never_send_less_than_50_w(tmp_path, monkeypatch, workouts_dir):
    """ERG libre à 50 W et biais au minimum, puis cadence verrouillée avec un cycliste qui cesse de
    pédaler 60 s : la cible descend jusqu'au plancher, jamais en dessous."""
    async def scenario():
        s, driver, errors = make_session(tmp_path, monkeypatch, workouts_dir, port=6620)
        sent = spy_targets(driver)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {}, 2)
        run(s, 2.0)
        s._on_command("pause", {}, 3)
        s._on_command("set_ride_mode", {"mode": "erg", "target_w": ERG_MIN_W}, 4)
        s._on_command("resume", {}, 5)
        for _ in range(20):
            s._handle_input(InputEvent.MINUS_SHORT)
        run(s, 5.0)
        assert s.state.erg["kind"] == "free" and s.state.erg["target_w"] == ERG_MIN_W
        s._on_command("set_ride_mode", {"mode": "cadence", "cadence_rpm": 90}, 6)
        driver.base_cadence_rpm = 0.0                       # le cycliste arrête de pédaler
        run(s, 60.0)
        assert s.state.erg["kind"] == "cadence" and s.state.erg["target_w"] == ERG_MIN_W
        driver.base_cadence_rpm = 90.0 * (1 + CADENCE_BAND_PCT / 100.0) + 10.0   # puis repart vite
        run(s, 10.0)
        assert s.state.erg["target_w"] > ERG_MIN_W
        assert not errors
        return sent

    sent = asyncio.run(scenario())
    assert sent and min(sent) >= ERG_MIN_W, f"consigne sous {ERG_MIN_W} W : {min(sent)} W"


# --- 7af : abri entre bots et derrière le cycliste (lot AS1) -------------------------------------

def test_7af_three_bots_230_240_250_and_a_rider_at_240_w():
    """Le bloc vélo 7af en temps accéléré : départ groupé, 10 min sur le plat.

    Chaque bot profite de l'abri au moins une fois, celui de 230 W reste mieux placé qu'un bot de
    230 W seul, et le cycliste prend aussi l'abri derrière les bots. L'abri reste sous le plafond de
    la SRS §5 et les vitesses restent plausibles."""
    flat = FlatRoute()
    bots = [ConstantPowerBot(w, bot_id=f"b{w}", s=3.0 * i, v=9.0) for i, w in enumerate((230.0, 240.0, 250.0))]
    rider = AS1Rider(240.0, s=4.5)
    solo = ConstantPowerBot(230.0, bot_id="solo", s=0.0, v=9.0)
    best = {b.id: 0.0 for b in bots}
    rider_best = [0.0]

    def probe():
        for b in bots:
            best[b.id] = max(best[b.id], b.draft)
        rider_best[0] = max(rider_best[0], rider.bot.draft)

    as1_ride(bots, rider, flat, 600.0, probe)
    as1_ride([solo], None, flat, 600.0)
    assert all(v > 0.2 for v in best.values()), best
    assert rider_best[0] > 0.2
    weakest = bots[0]
    assert weakest.s > solo.s + 2.0, f"230 W dans le groupe {weakest.s:.1f} m, seul {solo.s:.1f} m"
    for b in [*bots, rider.bot]:
        assert 0.0 <= b.draft <= d.ALPHA_CAP and 5.0 < b.v < 15.0
