"""Bandeau « Core non joignable » du menu Profil (28 novembre) : les copies d'une requête renvoyées par l'engine
toutes les 200 ms ne relancent plus le calcul pendant QUERY_COPY_WINDOW_S, et `league_status` est calculé hors
de la boucle à 50 Hz quand elle tourne."""

from __future__ import annotations

import asyncio
import threading

from openride_core import ipc_server
from openride_core.ipc_server import IpcServer

from test_grandprix_session import env, validator  # noqa: F401  (fixture partagée)


class _Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def _server(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(ipc_server.time, "monotonic", clock)
    calls: list[tuple[str, int]] = []
    srv = IpcServer(on_command=lambda n, a, i: calls.append((n, i)))
    return srv, calls, clock


def _cmd(srv: IpcServer, cmd_id: int, name: str) -> None:
    srv._handle_message({"type": "cmd", "v": 1, "cmd_id": cmd_id, "name": name, "args": {}})


def test_query_copies_inside_the_window_are_not_recomputed(monkeypatch):
    srv, calls, clock = _server(monkeypatch)
    for _ in range(5):   # cinq copies empilées pendant un retard de la boucle
        _cmd(srv, 7, "league_status")
        clock.now += 0.2
    assert calls == [("league_status", 7)] and srv.query_copies_skipped == 4
    assert srv.last_cmd_id == 7   # l'accusé suit toujours
    _cmd(srv, 8, "get_coach")   # autre requête : traitée tout de suite
    assert calls[-1] == ("get_coach", 8)
    clock.now += ipc_server.QUERY_COPY_WINDOW_S
    _cmd(srv, 7, "league_status")   # réponse peut-être perdue : recalculée après la fenêtre (contrat §4)
    assert calls[-1] == ("league_status", 7) and len(calls) == 3


def test_hello_forgets_the_recent_queries(monkeypatch):
    srv, calls, clock = _server(monkeypatch)
    _cmd(srv, 1, "list_collection")
    srv._handle_message({"type": "hello", "v": 1, "engine_version": "x", "rev": ipc_server.CONTRACT_REV})
    _cmd(srv, 1, "list_collection")   # engine relancé : même numéro, nouvelle commande
    assert calls == [("list_collection", 1), ("list_collection", 1)]


def test_other_commands_keep_their_rule(monkeypatch):
    srv, calls, clock = _server(monkeypatch)
    _cmd(srv, 3, "rename_profile")
    _cmd(srv, 3, "rename_profile")   # copie d'une commande : ignorée par last_cmd_id, comme avant
    assert calls == [("rename_profile", 3)] and srv.query_copies_skipped == 0


def test_league_status_is_computed_off_the_loop(env):
    make, _, _, _ = env
    s, sent, _ = make(7180)
    seen: list[bool] = []
    original = s._league_status_message

    def spy(cmd_id: int):
        seen.append(threading.current_thread() is threading.main_thread())
        return original(cmd_id)

    s._league_status_message = spy

    async def run() -> None:
        s._on_command("league_status", {}, 5)
        assert not [m for m in sent if m.get("type") == "league"]   # pas calculé dans la boucle
        while s._bg_tasks:
            await asyncio.sleep(0.01)

    asyncio.run(run())
    (msg,) = [m for m in sent if m.get("type") == "league"]
    validator("league").validate(msg)
    assert msg["request_cmd_id"] == 5 and seen == [False]
