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
