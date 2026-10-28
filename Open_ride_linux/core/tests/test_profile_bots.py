"""Bots à profil (lot T12) : CP, W′, masse, pic sur 10 s et stratégie par segment.

Critères du cahier `docs/lots/LOT_T12_bots_profil.md` §7 :
2. Montée de 5 km à 7 % : à CP égale en W/kg, le grimpeur gagne du temps sur le diesel ; sur 10 km de
   plat, le rouleur devance le grimpeur.
3. Sprint de 400 m : le sprinteur dépasse 10 W/kg dans les 200 derniers mètres, au plus 10 s, puis
   repasse sous sa CP ; sa réserve descend puis remonte.
4. Réserve vide : aucune puissance au-dessus de la CP tant qu'elle n'est pas remontée.
5. W′bal identique, pas à pas, à `wbal_step` avec la même puissance.
6. Trame avec 4 bots à profil validée par le schéma, sous 4 096 octets.
7. `start` avec un profil inconnu : `bot_invalid`, séance non démarrée.
8. Coût : 4 bots à profil ajoutent moins de 0,3 ms au pas p99.
"""

from __future__ import annotations

import asyncio
import json
import time

import pytest

from openride_core.bots import (PROFILES, BotError, ProfileBot, attach_segments, bots_from_menu,
                                profile_bot_names)
from openride_core.physics import PhysicsParams
from openride_core.rogue.wbal import wbal_initial, wbal_step
from openride_core.segments import Segment

from test_bots import assert_valid_state
from test_contract_ipc import make_session, run_steps

DT = 0.1


class FakeRoute:
    """Parcours ouvert de pente `grade(s)`, sans géométrie."""

    is_loop = False

    def __init__(self, length_m: float, grade=lambda s: 0.0) -> None:
        self.length_m = length_m
        self.grade = grade

    def sample(self, s: float):
        class Sample:
            pass
        out = Sample()
        out.grade_pct = self.grade(s)
        out.alt_m = 0.0
        return out


def seg(kind: str, s0: float, s1: float, seg_id: str | None = None) -> Segment:
    return Segment(id=seg_id or f"{kind}1", name=kind, type=kind, s_start=s0, s_end=s1, length_m=s1 - s0,
                   avg_grade_pct=7.0 if kind == "climb" else 0.0, gain_m=0.0,
                   category="2" if kind == "climb" else None, source="manual")


def ride(bot: ProfileBot, route: FakeRoute, until_m: float, max_s: float = 7200.0) -> float:
    t = 0.0
    while bot.s < until_m and t < max_s:
        bot.step(DT, route)
        t += DT
    return t


def test_profiles_of_27_october():
    assert {p: (v.name, v.mass_kg, v.cp_wkg, v.w_prime_j, v.peak_wkg) for p, v in PROFILES.items()} == {
        "climber": ("Grimpeur", 60.0, 4.0, 15000.0, 0.0), "rouleur": ("Rouleur", 72.0, 3.6, 20000.0, 0.0),
        "sprinter": ("Sprinteur", 80.0, 3.3, 25000.0, 12.0), "diesel": ("Diesel", 75.0, 3.8, 10000.0, 0.0)}
    b = ProfileBot("climber")
    d = b.to_dict()
    assert d["kind"] == "constant" and d["profile"] == "climber" and d["name"] == "Grimpeur"
    assert d["cp_w"] == 240.0 and d["mass_kg"] == 60.0 and d["wbal_pct"] == 100.0
    assert b.params.mass_kg == 68.0, "masse physique : profil plus vélo"
    with pytest.raises(BotError, match="profil de bot inconnu"):
        ProfileBot("puncheur")
    assert profile_bot_names(["climber", "diesel", "climber"]) == ["Grimpeur", "Diesel", "Grimpeur 2"]


def test_climber_beats_diesel_uphill_and_rouleur_beats_climber_on_the_flat():
    climb = FakeRoute(5000.0, lambda s: 7.0)
    climber = ProfileBot("climber", segments=(seg("climb", 0.0, 5000.0),))
    # Même CP en W/kg que le grimpeur (4,0) : seule la stratégie change.
    diesel = ProfileBot("diesel", segments=(seg("climb", 0.0, 5000.0),), scale=4.0 / 3.8)
    assert abs(climber.cp_w / climber.mass_kg - diesel.cp_w / diesel.mass_kg) < 1e-9
    assert ride(climber, climb, 5000.0) < ride(diesel, climb, 5000.0)
    flat = FakeRoute(10000.0)
    rouleur, climber = ProfileBot("rouleur"), ProfileBot("climber")
    assert ride(rouleur, flat, 10000.0) < ride(climber, flat, 10000.0)


def test_sprinter_peak_in_the_last_200_m_then_back_under_cp():
    route = FakeRoute(3000.0)
    b = ProfileBot("sprinter", segments=(seg("sprint", 1600.0, 2000.0),))
    powers: list[tuple[float, float, float]] = []   # (s avant le pas, puissance, réserve)
    while b.s < 2600.0:
        s = b.s
        b.step(DT, route)
        powers.append((s, b.power_w, b.wbal_pct))
    peak = [(s, p) for s, p, _ in powers if p / b.mass_kg > 10.0]
    assert peak, "pic du sprinteur"
    assert all(1800.0 <= s < 2000.0 for s, _ in peak), "pic dans les 200 derniers mètres"
    assert len(peak) * DT <= 10.0 + 1e-6, "pic de 10 s au plus"
    after = [p for s, p, _ in powers if s >= 2000.0]
    assert after and max(after) < b.cp_w, "sous la CP après le sprint"
    lowest = min(w for _, _, w in powers)
    assert lowest < 100.0 and powers[-1][2] > lowest, "réserve entamée puis rechargée"


def test_empty_reserve_caps_power_at_cp():
    route = FakeRoute(20000.0, lambda s: 7.0)
    b = ProfileBot("climber", segments=(seg("climb", 0.0, 20000.0),))
    b.wbal = wbal_initial(b.w_prime_j).__class__(w_bal_j=0.0)
    b.spec = b.spec.__class__(**{**b.spec.__dict__, "climb_reserve": -1.0})   # attaque même à 0 %
    for _ in range(50):
        b.step(DT, route)
        assert b.power_w <= b.cp_w + 1e-9
    assert b.wbal.w_bal_j == 0.0


def test_wbal_is_the_rogue_model_step_by_step():
    route = FakeRoute(5000.0, lambda s: 7.0 if s < 2500.0 else 0.0)
    b = ProfileBot("climber", segments=(seg("climb", 0.0, 2500.0),))
    ref = wbal_initial(b.w_prime_j)
    for _ in range(3000):
        b.step(DT, route)
        ref = wbal_step(ref, b.power_w, 0.0, DT, cp_w=b.cp_w, w_prime_j=b.w_prime_j)
        assert b.wbal == ref


def test_menu_profile_bots_and_unknown_profile():
    params = PhysicsParams()
    bots = bots_from_menu([{"kind": "profile", "profile": "climber"}, {"kind": "constant", "power_w": 200},
                           {"kind": "profile", "profile": "climber"}], params, 250.0, None, None)
    assert [(b.id, b.name) for b in bots] == [("bot1", "Grimpeur"), ("bot2", "Bot 200 W"), ("bot3", "Grimpeur 2")]
    with pytest.raises(BotError, match="profil de bot inconnu"):
        bots_from_menu([{"kind": "profile", "profile": "puncheur"}], params, 250.0, None, None)
    with pytest.raises(BotError, match="au plus 4"):
        bots_from_menu([{"kind": "profile", "profile": "diesel"}] * 3 + [{"kind": "constant", "power_w": 200}] * 2,
                       params, 250.0, None, None)
    attach_segments(bots, (seg("climb", 0.0, 100.0),))
    assert bots[0].segments and bots[2].segments


def test_start_with_profile_bots_frame_and_refusal(tmp_path, monkeypatch):
    async def scenario():
        s, cap = make_session(tmp_path, monkeypatch, port=6150)
        s.server.send_error = lambda code, message: cap.frames.append({"type": "error", "v": 1, "code": code,
                                                                         "message": message})
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {"bots": [{"kind": "profile", "profile": "puncheur"}]}, 2)
        assert cap.of("error")[-1]["code"] == "bot_invalid" and s.state.session_state == "READY"
        s._on_command("start", {"bots": [{"kind": "profile", "profile": p}
                                         for p in ("climber", "rouleur", "sprinter", "diesel")]}, 3)
        assert s.state.session_state == "RUNNING"
        assert all(b.segments for b in s.bots), "segments de la couche donnés aux bots"
        run_steps(s, 200)
        s.state.bots = [b.to_dict() for b in s.bots]   # comme la boucle à 30 Hz de CoreSession
        s._fill_race_frame()
        s.server.send_state(s.state)
        frame = cap.of("state")[-1]
        assert len(frame["bots"]) == 4
        for b in frame["bots"]:
            assert b["kind"] == "constant" and b["profile"] and b["cp_w"] > 0 and 0.0 <= b["wbal_pct"] <= 100.0
        assert_valid_state(frame)
        assert len(json.dumps(frame, ensure_ascii=False, separators=(",", ":")).encode()) < 4096
        s._on_command("end_session", {"save": False}, 4)

    asyncio.run(scenario())


def test_cli_bot_profile_option():
    from openride_core.__main__ import build_parser

    args = build_parser().parse_args(["run", "--bot-profile", "climber", "--bot-profile", "diesel", "--bot", "200"])
    assert args.bot_profile == ["climber", "diesel"] and args.bot == [200.0]
    with pytest.raises(SystemExit):
        build_parser().parse_args(["run", "--bot-profile", "puncheur"])


def test_four_profile_bots_cost_under_0_3_ms():
    from openride_core.demo_world import build_route
    from openride_core.route import Route

    route = Route(build_route(30_000.0))
    segments = (seg("climb", 0.0, 15000.0), seg("sprint", 15000.0, 15400.0))
    bots = [ProfileBot(p, bot_id=f"b{i}", segments=segments) for i, p in enumerate(PROFILES)]
    for _ in range(100):
        for b in bots:
            b.step(0.02, route)
    durations = []
    for _ in range(1000):
        t0 = time.perf_counter()
        for b in bots:
            b.step(0.02, route)
        durations.append(time.perf_counter() - t0)
    durations.sort()
    assert durations[int(len(durations) * 0.99)] * 1000.0 < 0.3
