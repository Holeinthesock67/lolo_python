"""Lot GP4 : Voiture d'équipe (véhicule et abri d'AS6) et Furtif (Échappée de TT4 plus vol d'objet).

Critères du cahier `docs/lots/LOT_GP4_voiture_furtif.md` §4 : gain de la voiture d'équipe à ± 10 % du plan
(`test_grandprix.test_plan_gains_within_10_pct`, ligne `team_car`) ; vol refusé sans coureur à moins de 50 m ;
supplément de pente de la voiture toujours négatif ou nul, rampes respectées.
"""

import json
import math
from types import SimpleNamespace

import pytest

from openride_core import bot_tactics, draft, traffic
from openride_core.grandprix import ME
from openride_core.grandprix.items import DEFAULT_ITEMS
from openride_core.session import ESCORT_GAP_M

from test_grandprix import V_EQ, Sim
from test_grandprix_session import DT, STATE_LIMIT_BYTES, T0_WALL, env, validator  # noqa: F401 (fixture)


# --- règles du mode (module pur) -----------------------------------------------------------------

def test_team_car_escort_lasts_its_six_seconds():
    assert DEFAULT_ITEMS["team_car"].escort == "team_car" and "team_car" in traffic.KINDS
    assert all(not s.escort for k, s in DEFAULT_ITEMS.items() if k != "team_car")   # donnée, pas de branche
    sim = Sim({ME: 250.0, "b": 250.0})
    assert sim.mode.escorts() == []
    sim.give("b", "team_car")
    assert sim.mode.use("b")
    sim.run(1.0)
    assert sim.mode.escorts() == [("b", "team_car")]
    assert sim.phys["b"].v == pytest.approx(1.5 * V_EQ, rel=1e-6)
    sim.run(5.1)
    assert sim.mode.escorts() == []


def test_stealth_unseen_ten_seconds_and_steal_within_50_m():
    sim = Sim({"a": 250.0, ME: 250.0}, gap_m=40.0)          # « a » 40 m devant
    sim.give(ME, "stealth")
    sim.give("a", "homing")
    assert not sim.mode.unseen(ME)
    assert sim.mode.use(ME)
    assert sim.mode.racers[ME].held == "homing" and sim.mode.racers["a"].held is None
    sim.run(1.0)
    assert sim.mode.unseen(ME) and not sim.mode.unseen("a")
    sim.run(9.1)
    assert not sim.mode.unseen(ME)


def test_steal_refused_without_rider_within_50_m():
    sim = Sim({"a": 250.0, ME: 250.0}, gap_m=60.0)          # « a » 60 m devant : trop loin
    sim.give(ME, "stealth")
    sim.give("a", "star")
    assert sim.mode.use(ME)                                  # le Furtif part quand même
    assert sim.mode.racers[ME].held is None and sim.mode.racers["a"].held == "star"
    assert not [ln for ln in sim.mode.take_journal() if ln["event"] == "steal"]
    alone = Sim({ME: 250.0, "b": 250.0})                     # personne devant
    alone.give(ME, "stealth")
    alone.give("b", "gel")
    assert alone.mode.use(ME) and alone.mode.racers[ME].held is None and alone.mode.racers["b"].held == "gel"


def test_stealth_bot_gives_no_shelter_but_keeps_its_wheel():
    """Un bot sous le Furtif n'abrite plus le cycliste ni les bots qui le suivent (même règle que l'Échappée)."""
    ahead = SimpleNamespace(id="b2", kind="constant", s=3.0, v=11.0)
    assert draft.best_draft(0.0, [ahead])[0] > 0.0
    ahead.shelters = False
    assert draft.best_draft(0.0, [ahead]) == (0.0, None)
    follower = SimpleNamespace(id="b3", kind="constant", s=0.0, v=11.0, params=None, draft=0.0, wheel=None,
                               push=0.0)
    for _ in range(100):
        draft.update_bots([ahead, follower], None, DT)
    assert follower.draft == 0.0


# --- séance --------------------------------------------------------------------------------------

def test_team_car_drawn_and_felt_as_shelter_only(env, monkeypatch):
    """La voiture d'équipe est un véhicule d'AS6 de la liste `vehicles`, juste devant le cycliste ; son abri
    lisse la pente envoyée vers le bas seulement (jamais au-dessus de celle sans abri), avec les rampes de
    l'abri (lissage d'une seconde), puis disparaît avec l'effet."""
    make, run, frame, _ = env
    # Lot BT1 : bots à l'objectif par défaut du jeu (Tempo), allure proche de la séance d'avant
    s, _, errors = make(6900, objective="tempo")
    s.cfg.ride.vehicle_draft = "on"
    s._on_command("start", {"mode": "grandprix"}, 2)
    assert not errors
    gp = s.grandprix
    steps: list[tuple[float, float, float, float, float, str | None]] = []
    vehicles: list[list[dict]] = []
    step = s._step

    def recording(dt, now):
        s0, v0 = s.physics.s, s.physics.v
        step(dt, now)
        steps.append((s0, v0, s._draft, s._suction, s._grade_sent, s._draft_bot))
        if s._escorts:
            s._frame_count = 0
            s._fill_vehicles_frame()
            vehicles.append(s.state.vehicles)

    monkeypatch.setattr(s, "_step", recording)
    run(s, 5.0)
    me = gp.racers[ME]
    me.held, me.charges = "team_car", 1
    assert s._grandprix_press("Z_SHORT")
    run(s, 12.0)
    # 6 s de voiture au plus : elle attend que la place devant soit libre pendant BLOCK_LOOK_S (ici, un bot à
    # rattraper la retient moins d'une seconde : 0,66 s avec l'échelle des bots de #900), puis reste jusqu'à la fin
    # de l'effet
    assert vehicles and 6.0 / DT - 50 <= len(vehicles) <= 6.0 / DT + 3
    car = vehicles[0][0]
    assert (car["id"], car["kind"], car["dir"]) == ("tc0", "team_car", 1)
    state_v = validator("state")
    d = frame(s)
    d["vehicles"] = vehicles[0]
    state_v.validate(d)
    assert len(json.dumps(d, ensure_ascii=False).encode()) < STATE_LIMIT_BYTES
    drafts = [x[2] for x in steps[int(5.0 / DT):]]
    assert max(drafts) > 0.3 and max(drafts) <= traffic.VEHICLE_ALPHA_CAP + 1e-9
    assert drafts[-1] == 0.0                                  # abri parti avec la voiture
    ramp = traffic.VEHICLE_ALPHA_CAP * (1.0 - math.exp(-DT / draft.SMOOTH_TAU_S)) + 1e-9
    assert max(abs(b - a) for a, b in zip(drafts, drafts[1:])) <= max(ramp, draft.SMOOTH_MIN_RATE * DT + 1e-9)
    assert any(x[5] == "veh:tc0" for x in steps)
    # Même pas, même position, même vitesse, sans aucun abri : la pente envoyée avec la voiture n'est jamais plus
    # haute (supplément négatif ou nul) et plus basse derrière elle
    ref, _, errors = make(6910)
    ref.cfg.powerups.mode = "off"
    ref._on_command("start", {"bots": []}, 2)
    assert not errors

    def no_draft(*_args):
        ref._draft, ref._suction = 0.0, 0.0

    monkeypatch.setattr(ref, "_update_draft", no_draft)
    wall = T0_WALL
    below = 0
    for s0, v0, _alpha, _suction, sent, source in steps:
        ref.physics.s, ref.physics.v = s0, v0
        wall += DT
        ref._step(DT, wall)
        assert sent <= ref._grade_sent + 1e-9
        below += source == "veh:tc0" and sent < ref._grade_sent - 1e-6
    assert below > 0                                          # l'abri de la voiture se ressent


def test_team_car_respects_vehicle_draft_setting(env):
    make, run, _, _ = env
    s, _, errors = make(6920)                                 # `vehicle_draft = "off"` (fixture)
    s._on_command("start", {"mode": "grandprix"}, 2)
    assert not errors
    me = s.grandprix.racers[ME]
    me.held, me.charges = "team_car", 1
    assert s._grandprix_press("Z_SHORT")
    run(s, 2.0)
    assert s._escorts and s._draft_bot != "veh:tc0"           # dessinée, mais sans abri ressenti


def test_stealth_in_session_unseen_and_no_shelter(env):
    make, run, _, _ = env
    s, _, errors = make(6930)
    s._on_command("start", {"mode": "grandprix"}, 2)
    assert not errors
    gp = s.grandprix
    bot = s.bots[0]
    racer = gp.racers[bot.id]
    racer.held, racer.charges = "stealth", 1
    assert gp.use(bot.id)
    me = gp.racers[ME]
    me.held, me.charges = "stealth", 1
    assert s._grandprix_press("Z_SHORT")
    run(s, 1.0)
    assert s._unseen_ids() == {bot_tactics.RIDER_ID, bot.id}
    assert bot.shelters is False and all(b.shelters for b in s.bots[1:])
    run(s, 10.0)
    assert s._unseen_ids() == frozenset() and bot.shelters is True


def test_escort_sits_just_ahead_of_its_rider(env):
    make, run, _, _ = env
    s, _, errors = make(6940)
    s._on_command("start", {"mode": "grandprix"}, 2)
    me = s.grandprix.racers[ME]
    me.held, me.charges = "team_car", 1
    assert s._grandprix_press("Z_SHORT")
    run(s, 1.0)
    car = s._escorts[0]
    gap = car.s - car.length * 0.5 - s.physics.s - draft.BIKE_LENGTH_M * 0.5
    assert gap == pytest.approx(ESCORT_GAP_M, abs=s.physics.v * DT + 1e-6)
    assert car.lateral == pytest.approx(s._lane.m, abs=0.05)


@pytest.mark.parametrize("level_pct", [100, 110, 120, 130, 140, 150])
def test_team_car_never_overlaps_a_rider(env, level_pct):
    """Banc du 13 novembre (44 contacts voiture d'équipe / bot) : la voiture d'un coureur remorqué ne passe jamais
    sous un autre coureur. Elle se glisse devant dès que la place est libre, puis le bloc coureur et voiture double
    les plus lents (placement AS2 au gabarit de la voiture). Pire cas : tous les bots remorqués sans arrêt.
    Niveaux 100 à 150 % : avant le correctif, la voiture d'un bot bien plus fort que le cycliste passait sous lui
    (('tc3', 'me', 3.10, 0.40) à 120 %, commentaire de #909)."""
    make, run, _, _ = env
    # bots à fond (objectif « max » de make, lot BT1) : pire cas des bots plus forts que le cycliste
    s, _, errors = make(6950, level_pct=level_pct)
    s.cfg.ride.vehicle_draft = "on"
    s._on_command("start", {"mode": "grandprix"}, 2)
    assert not errors
    gp = s.grandprix
    run(s, 20.0)
    shown = 0
    cars: set[str] = set()
    for _ in range(40):
        for b in s.bots:
            r = gp.racers[b.id]
            if r.held is None and not any(a.item == "team_car" and a.until_t > gp.clock for a in r.fx):
                r.held, r.charges = "team_car", 1
                assert gp.use(b.id)
        for _ in range(25):
            run(s, DT)
            places = {ME: (s.physics.s, s._lane.m), **{b.id: (b.s, b.lane.m) for b in s.bots}}
            ids = list(gp.racers)
            for car in s._escorts:
                shown += 1
                cars.add(car.id)
                towed = ids[int(car.id[2:])]
                for rid, (o_s, o_m) in places.items():
                    if rid == towed:
                        continue
                    overlap = (abs(car.s - o_s) < car.length * 0.5 + draft.BIKE_LENGTH_M * 0.5
                               and abs(car.lateral - o_m) < car.half_width + draft.RIDER_WIDTH_M * 0.5)
                    assert not overlap, (car.id, rid, car.s - o_s, car.lateral - o_m)
    # Les voitures roulent bien devant leurs bots : plus de 5 s de voiture en tout. Elles attendent que la place soit
    # libre (bloc entier, BLOCK_LOOK_S) : à 150 %, dans le plateau serré, une seule voiture passe, 301 trames
    assert cars and shown > 250, (cars, shown)


def test_towed_bot_held_up_rides_at_the_speed_ahead(env):
    """Bot remorqué enfermé derrière un coureur plus lent (lot PL1) : sa vitesse du Grand Prix suit la puissance
    voulue avant l'enfermement (`unblocked_w`), puis il freine à la vitesse de celui devant. Avant, la puissance
    coupée par l'enfermement donnait une vitesse d'équilibre nulle : il s'arrêtait net une trame sur deux."""
    make, run, _, _ = env
    s, _, errors = make(6960, level_pct=150)
    s.cfg.ride.vehicle_draft = "on"
    s._on_command("start", {"mode": "grandprix"}, 2)
    assert not errors
    gp = s.grandprix
    run(s, 20.0)
    for _ in range(20):
        for b in s.bots:
            r = gp.racers[b.id]
            if r.held is None and not any(a.item == "team_car" and a.until_t > gp.clock for a in r.fx):
                r.held, r.charges = "team_car", 1
                gp.use(b.id)
        for _ in range(25):
            run(s, DT)
            towed = dict(gp.escorts())
            for b in s.bots:
                if b.id in towed:
                    assert b.v > 1.0, (b.id, gp.clock)          # jamais arrêté net sous la voiture d'équipe


@pytest.mark.slow
@pytest.mark.parametrize("watts", [190, 200, 210])
def test_team_car_never_meets_road_users(env, monkeypatch, watts):
    """Banc rGP4v du 16 novembre (contacts « car_a / core ») : la voiture d'équipe d'un bot ne touche ni un cycliste
    du décor (lot AS7) ni un véhicule de la circulation. Sa carrosserie reste sur la chaussée permise à un vélo
    (`draft.lane_target`, bornes au gabarit du bloc) : un bot remorqué qui double ne la pousse plus sur un
    cycliste venant en face ; elle n'apparaît pas sur un usager de la route. Boucle de 5 km d'un tour (circulation
    et cyclistes du décor ; parcours demo en ligne jusqu'au lot GPL1, le Grand Prix se court sur une boucle), tous
    les coureurs remorqués dès que possible. Avant : 14 à 16 trames de contact avec un cycliste venant en face à
    190, 200 et 210 W."""
    import test_grandprix_session as tgs
    from openride_core import demo_world
    monkeypatch.setattr(tgs, "POWER_W", float(watts))
    make, run, _, tmp = env
    world = demo_world.write_world(tmp / "routes", "boucle", 5000.0)
    (world / "route.json").write_text(json.dumps(tgs.loop_route(5000.0)), encoding="utf-8")
    s, _, errors = make(6970, route_id="boucle", laps=1)
    s.cfg.grandprix.chaos, s.cfg.grandprix.box_every_m = "wild", 1000
    s.cfg.ride.vehicle_draft = "on"
    s._on_command("start", {"mode": "grandprix"}, 2)
    assert not errors
    gp = s.grandprix
    shown = met = 0
    t = 0.0
    while s.state.session_state == "RUNNING" and t < 900.0:
        run(s, DT)
        t += DT
        if int(t / DT) % 150 == 0:                            # toutes les 3 s environ (cadence du banc de recherche)
            for rid in [ME] + [b.id for b in s.bots]:
                r = gp.racers[rid]
                if r.held is None and not any(a.item == "team_car" and a.until_t > gp.clock for a in r.fx):
                    r.held, r.charges = "team_car", 1
                    gp.use(rid)
        users = [(u.s, u.lane_m, draft.BIKE_LENGTH_M * 0.5, draft.RIDER_WIDTH_M * 0.5)
                 for u in (s.road_cyclists.on_route(r) for r in s.road_cyclists.riders())]
        users += [(v.s, v.lateral, v.length * 0.5, v.half_width)
                  for v in (s.traffic.on_route(x) for x in s.traffic.vehicles)]
        for car in s._escorts:
            shown += 1
            met += any(abs(car.s - u_s) < car.length * 0.5 + half_len and abs(car.lateral - u_m) < car.half_width + half_w
                       for u_s, u_m, half_len, half_w in users)
    assert shown > 1000 and met == 0, (shown, met)
