"""Robustesse du serveur IPC face aux messages malformés (lot J2, contrat IPC §6).

Un datagramme illisible ou non conforme est ignoré et compté ; il ne doit jamais faire
tomber la boucle du core.
"""

from __future__ import annotations

import json
import logging
import random
import socket
import time

import pytest

from openride_core.ipc_server import IpcServer, _invalid_reason


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server():
    received: list[tuple[str, dict, int]] = []
    srv = IpcServer(port_state=_free_port(), port_commands=_free_port(),
                    on_command=lambda n, a, i: received.append((n, a, i)))
    srv.start()
    srv.received = received  # type: ignore[attr-defined]
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.tx = tx  # type: ignore[attr-defined]
    yield srv
    tx.close()
    srv.stop()


def _send(srv: IpcServer, payload: bytes) -> None:
    srv.tx.sendto(payload, ("127.0.0.1", srv.port_commands))  # type: ignore[attr-defined]


def _drain(srv: IpcServer, expected_total: int, timeout: float = 2.0) -> None:
    """Lit les datagrammes jusqu'à en avoir traité `expected_total` (rejetés ou transmis)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        srv.process_incoming_datagrams()
        if srv.invalid_datagrams + len(srv.received) >= expected_total:  # type: ignore[attr-defined]
            return
        time.sleep(0.005)


MALFORMED: list[bytes] = [
    json.dumps([1, 2]).encode(),
    json.dumps({"type": "cmd", "cmd_id": "3", "name": "x"}).encode(),
    json.dumps({"type": "cmd", "cmd_id": None, "name": "x"}).encode(),
    json.dumps({"type": "cmd", "cmd_id": 5, "name": "select_route", "args": [1]}).encode(),
    json.dumps("texte").encode(),
    json.dumps({}).encode(),
    json.dumps({"type": 3}).encode(),
    json.dumps({"type": "cmd", "cmd_id": True, "name": "pause"}).encode(),
    json.dumps({"type": "cmd", "cmd_id": -1, "name": "pause"}).encode(),
    json.dumps({"type": "cmd", "cmd_id": 7, "name": ""}).encode(),
    json.dumps({"type": "cmd", "cmd_id": 8}).encode(),
    b"\xff\xfe\x00 pas de l'UTF-8",
    b"{pas du json",
]


def test_malformed_datagrams_are_counted_and_ignored(server: IpcServer) -> None:
    for payload in MALFORMED:
        _send(server, payload)
    _drain(server, len(MALFORMED))
    assert server.invalid_datagrams == len(MALFORMED)
    assert server.received == []  # type: ignore[attr-defined]
    assert server.last_cmd_id == 0

    # Une commande valide passe ensuite normalement.
    _send(server, json.dumps({"type": "cmd", "v": 1, "cmd_id": 1, "name": "pause", "args": {}}).encode())
    _drain(server, len(MALFORMED) + 1)
    assert server.received == [("pause", {}, 1)]  # type: ignore[attr-defined]


def test_null_or_missing_args_become_empty_dict(server: IpcServer) -> None:
    _send(server, json.dumps({"type": "cmd", "v": 1, "cmd_id": 1, "name": "select_route", "args": None}).encode())
    _send(server, json.dumps({"type": "cmd", "v": 1, "cmd_id": 2, "name": "start"}).encode())
    _drain(server, 2)
    assert server.received == [("select_route", {}, 1), ("start", {}, 2)]  # type: ignore[attr-defined]


def test_hello_with_text_version_is_refused_without_crash(server: IpcServer) -> None:
    server._handle_message({"type": "hello", "v": "1"})
    assert server.engine_connected is False


def test_random_messages_never_raise() -> None:
    """2 000 messages construits au hasard à partir des champs du contrat (graine fixe)."""
    srv = IpcServer(on_command=lambda n, a, i: None)
    rng = random.Random(20261023)
    values = [None, True, False, 0, 1, -3, 2**40, 1.5, float("nan"), "", "cmd", "hello", "heartbeat",
              "bye", "pause", [], [1], {}, {"route_id": 3}, {"event": None}]
    keys = ["type", "v", "cmd_id", "name", "args", "engine_version", "route_id"]
    for _ in range(2000):
        if rng.random() < 0.1:
            msg = rng.choice(values)
        else:
            msg = {k: rng.choice(values) for k in rng.sample(keys, rng.randint(0, len(keys)))}
            if rng.random() < 0.5:
                msg["type"] = rng.choice(["cmd", "hello", "heartbeat", "bye", "state", "x"])
        if _invalid_reason(msg) is None:
            srv._handle_message(msg)


def test_command_callback_exception_does_not_stop_loop(caplog: pytest.LogCaptureFixture) -> None:
    def boom(name, args, cmd_id):
        raise RuntimeError("bogue de commande")

    srv = IpcServer(on_command=boom)
    with caplog.at_level(logging.ERROR, logger="ipc_server"):
        srv._handle_message({"type": "cmd", "v": 1, "cmd_id": 4, "name": "pause"})
    assert srv.last_cmd_id == 4
    assert "bogue de commande" in caplog.text


def test_rejection_warnings_are_rate_limited(server: IpcServer, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="ipc_server"):
        for i in range(500):
            _send(server, b"[]")
            if i % 20 == 19:
                _drain(server, i + 1, timeout=0.5)   # vide la file de réception au fil de l'envoi
        _drain(server, 500)
    assert server.invalid_datagrams >= 450   # UDP local : quelques pertes possibles
    warnings = [r for r in caplog.records if "ignoré" in r.getMessage()]
    assert 1 <= len(warnings) <= 2
