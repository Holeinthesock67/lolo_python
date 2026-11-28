"""Lot AG1 : en Course (et dans les manches « Course » de la ligue d'hiver), un bot distancé par le premier chasse.

Essai du 28 novembre (manche 1 de la ligue, Course en tours) : « les bots semblent peu agressifs, les barres sont
bien bleues ». Les bots roulaient sous leur CP sur le plat (réserve pleine du départ à l'arrivée) et la réponse aux
départs ne voyait que les coureurs de leur groupe (2 s) : un cycliste parti seul n'était jamais chassé. Les autres
modes gardent leur ligne de `MODE_TACTICS` (pas de chasse hors de la Course).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from openride_core import bot_tactics as bt
from openride_core.bots import ProfileBot
from openride_core.rogue.wbal import WbalState

from test_grandprix_session import env  # noqa: F401  (fixture partagée)


def _bot(mode: str, bot_id: str = "bot1") -> ProfileBot:
    b = ProfileBot("rouleur", bot_id=bot_id)
    b.set_scale(1.0)
    b.physics.v = 10.0
    bt.start_race([b], 1, mode)
    return b


def _tick(bots: list[ProfileBot], field: bt.Field, rider_s: float, t_s: float,
          unseen: frozenset[str] = frozenset()) -> None:
    """Le champ relu à `t_s` (temps du champ), le cycliste à `rider_s`, les bots figés."""
    field.t, field._acc = t_s - bt.TICK_S, 0.0
    bt.update_field(field, bots, (rider_s, 10.0), bt.TICK_S, unseen=unseen)


def test_only_the_race_row_chases() -> None:
    race = bt.MODE_TACTICS["race"]
    assert race.chase and replace(race, chase=False) == bt.MODE_TACTICS["classic"]   # le reste du classique
    assert not any(row.chase for k, row in bt.MODE_TACTICS.items() if k != "race")


def test_bot_dropped_by_the_leader_chases_then_stops_when_empty() -> None:
    b, field = _bot("race"), bt.Field()
    _tick([b], field, b.s + 100.0, bt.RESPONSE_START_S + 1.0)    # 10 s de retard
    assert b.tactics.chasing and b.tactics.chases == 1
    assert bt.CHASE_FACTOR[0] < b.tactics.chase_factor < bt.CHASE_FACTOR[1]
    power, tactical = b.tactics.adjust(b, b.spec.flat * b.cp_w, False, b.t, b.s)
    assert power == pytest.approx(b.tactics.chase_factor * b.cp_w) and power > b.cp_w   # il puise dans sa réserve
    assert not tactical                                     # ceux de son groupe restent dans sa roue (lot AS1)
    assert b.move() == "respond"                            # écrit dans le bandeau (lot BA1)
    b.wbal = WbalState(0.10 * b.w_prime_j)                     # réserve vidée : il s'arrête...
    _tick([b], field, b.s + 100.0, bt.RESPONSE_START_S + 2.0)
    assert not b.tactics.chasing
    b.wbal = WbalState(0.40 * b.w_prime_j)                     # ... et ne repart pas sous 50 %
    _tick([b], field, b.s + 100.0, bt.RESPONSE_START_S + 3.0)
    assert not b.tactics.chasing
    b.wbal = WbalState(0.60 * b.w_prime_j)
    _tick([b], field, b.s + 300.0, bt.RESPONSE_START_S + 4.0)   # 30 s : chasse à fond
    assert b.tactics.chasing and b.tactics.chase_factor == pytest.approx(bt.CHASE_FACTOR[1])
    _tick([b], field, b.s + 15.0, bt.RESPONSE_START_S + 5.0)    # revenu à 1,5 s : dans le groupe, fini
    assert not b.tactics.chasing and b.tactics.chases == 2


def test_no_chase_at_start_too_far_unseen_or_outside_the_race() -> None:
    b = _bot("race")
    _tick([b], bt.Field(), b.s + 100.0, bt.RESPONSE_START_S - 5.0)     # mise en route
    assert not b.tactics.chasing
    _tick([b], bt.Field(), b.s + 700.0, bt.RESPONSE_START_S + 1.0)     # 70 s : trop loin pour partir
    assert not b.tactics.chasing
    _tick([b], bt.Field(), b.s + 100.0, bt.RESPONSE_START_S + 1.0, frozenset({bt.RIDER_ID}))   # Échappée
    assert not b.tactics.chasing
    for mode in ("classic", "grandprix", "survivor", "track_full"):
        o = _bot(mode)
        _tick([o], bt.Field(), o.s + 100.0, bt.RESPONSE_START_S + 1.0)
        assert not o.tactics.chasing, mode


def test_leading_bot_does_not_chase_itself() -> None:
    lead, back = _bot("race", "lead"), _bot("race", "back")
    lead.physics.s = back.s + 100.0
    _tick([lead, back], bt.Field(), lead.s - 300.0, bt.RESPONSE_START_S + 1.0)   # le cycliste derrière
    assert not lead.tactics.chasing and back.tactics.chasing


def test_race_session_bots_spend_their_reserve_on_a_rider_who_escapes(env) -> None:
    make, run, _, _ = env
    s, _, errors = make(7590, opponents=4, laps=3)
    s.bot_tactics_seed = 1
    s.cfg.race.opponents, s.cfg.race.laps = 4, 3
    s._on_command("start", {"mode": "race"}, 2)
    assert not errors and s._mode_tactics("race") == "race"
    bots = list(s.bots)
    assert {b.tactics.mode for b in bots} == {"race"}
    run(s, 60.0)
    s.driver.base_power_w = 420.0                           # le cycliste part seul et tient
    low = {b.id: 100.0 for b in bots}

    def check(sess):
        for b in bots:
            low[b.id] = min(low[b.id], b.wbal_pct)

    run(s, 240.0, check, every=1)
    assert sum(b.tactics.chases for b in bots) >= 1
    assert min(low.values()) < 70.0                         # la barre n'est plus pleine : il a chassé
