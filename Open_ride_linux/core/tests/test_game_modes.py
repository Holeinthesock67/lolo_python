"""Série IM, lot IM1 : table des modes et point d'appel `fill_frame` (plans/CADRAGE_INTERFACE_MODES).

Le comportement est gardé par le filet « à l'identique » (`identique.py`, `scripts/modes_identique.py`) ; ce fichier
vérifie la table elle-même : ordre fixe, un adaptateur par objet de mode de la séance, champs vidés hors séance."""

from __future__ import annotations

from types import SimpleNamespace

from openride_core.game_modes import registry
from openride_core.game_modes.base import GameMode, ModeContext


def test_order_is_fixed():
    # ordre des lignes de session.py avant la série : mêmes décorations de `bots`, même journal
    assert [m.id for m in registry.MODES] == ["classic", "wtf", "survivor", "grandprix", "track", "rogue"]
    assert set(registry.BY_ID) == {m.id for m in registry.MODES}


def test_each_mode_reads_a_session_attribute():
    from openride_core.session import CoreSession
    import inspect
    init = inspect.getsource(CoreSession.__init__)
    for m in registry.MODES:
        assert f"self.{m.attr}:" in init, m.id


def test_default_does_nothing():
    state = SimpleNamespace(session_state="RUNNING")
    GameMode().fill_frame(ModeContext(SimpleNamespace(state=state)))
    assert vars(state) == {"session_state": "RUNNING"}


def test_fields_cleared_outside_session():
    sentinel = object()
    state = SimpleNamespace(session_state="IDLE", segment=sentinel, powerup=sentinel, jerseys=sentinel,
                            bot_ahead=sentinel, bot_behind=sentinel, wtf=sentinel, survivor=sentinel, gp=sentinel,
                            track=sentinel, rogue=sentinel, bots=None)
    live = SimpleNamespace(frame=lambda *a: {"x": 1})
    session = SimpleNamespace(state=state, race=live, wtf=live, survivor=live, grandprix=live, track_event=live,
                              rogue=None)
    ctx = ModeContext(session)
    for m in registry.MODES:
        m.fill_frame(ctx)
    assert all(getattr(state, k) is None for k in ("segment", "powerup", "jerseys", "bot_ahead", "bot_behind",
                                                    "wtf", "survivor", "gp", "track"))
    assert state.rogue is sentinel   # le Cyber-Rogue garde sa dernière trame (comme avant le lot IM1)


# --- lot IM2 : fin de séance et classement ---------------------------------------------------------------------


def test_road_modes_and_summary_keys():
    assert [m.id for m in registry.ROAD_MODES] == ["classic", "wtf", "survivor", "grandprix", "track"]
    keys = [m.summary_key for m in registry.ROAD_MODES]
    assert keys == ["segments", "wtf", "survivor", "gp", "track"] and len(set(keys)) == len(keys)


def test_elo_modes_cover_ranked_modes():
    # mêmes modes qu'avant IM2 dans `_elo_order` (cote Elo et ligue d'hiver)
    owners = {mode: m.id for m in registry.MODES for mode in m.elo_modes}
    assert owners == {"grandprix": "grandprix", "race": "grandprix", "survivor": "survivor", "track": "track"}


def test_ranking_none_until_the_end():
    from openride_core import bot_elo
    gp = registry.BY_ID["grandprix"]
    racer = SimpleNamespace(id=bot_elo.ME, finished=None)
    other = SimpleNamespace(id="bot1", finished=12.0)
    obj = SimpleNamespace(racers={bot_elo.ME: racer, "bot1": other}, order=lambda: [other, racer])
    assert gp.ranking(obj) is None
    racer.finished = 13.0
    assert gp.ranking(obj) == [["bot1"], [bot_elo.ME]]

    sv = registry.BY_ID["survivor"]
    me = SimpleNamespace(id=bot_elo.ME, place=None)
    b1, b2 = SimpleNamespace(id="bot1", place=None), SimpleNamespace(id="bot2", place=3)
    obj = SimpleNamespace(racers={bot_elo.ME: me, "bot1": b1, "bot2": b2})
    assert sv.ranking(obj) is None
    me.place = 2
    assert sv.ranking(obj) == bot_elo.order_from_places([(bot_elo.ME, 2), ("bot1", None), ("bot2", 3)],
                                                        unplaced_first=True)

    tr = registry.BY_ID["track"]
    ev = SimpleNamespace(finished=False, full_ranking=lambda: ["bot1", bot_elo.ME])
    assert tr.ranking(ev) is None
    ev.finished = True
    assert tr.ranking(ev) == [["bot1"], [bot_elo.ME]]
    assert registry.BY_ID["classic"].ranking(object()) is None
