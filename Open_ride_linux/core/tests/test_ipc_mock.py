"""Tests unitaires du serveur IPC UDP et du MockDriver (SRS §12, Sprint 1)."""

import socket
import json
import time
import pytest

from openride_core.ipc_server import IpcServer, IpcState, CONTRACT_VERSION
from openride_core.mock_driver import MockDriver


def test_mock_driver_metrics():
    driver = MockDriver(base_power_w=200.0, base_cadence_rpm=80.0, base_hr_bpm=135)
    m = driver.poll(0.0)
    assert m.connected is True
    assert m.power_w > 0
    assert m.cadence_rpm > 0
    assert m.hr_bpm is not None

    # Test ERG
    driver.set_target_power(260.0)
    m_erg = driver.poll(10.0)
    assert abs(m_erg.power_w - 260.0) < 5.0

    # Test Déconnexion simulée
    driver.simulate_disconnect()
    m_disc = driver.poll(15.0)
    assert m_disc.connected is False


def test_ipc_server_udp_flow():
    # Ports de test distincts pour éviter les conflits éventuels
    PORT_STATE = 5505
    PORT_CMD = 5506

    received_cmds = []

    def on_cmd(name, args, cmd_id):
        received_cmds.append((name, args, cmd_id))

    server = IpcServer(
        port_state=PORT_STATE,
        port_commands=PORT_CMD,
        on_command=on_cmd,
    )
    server.start()

    # Client simulé (représente l'engine Godot)
    client_rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_rx.setblocking(False)
    client_rx.bind(("127.0.0.1", PORT_STATE))

    client_tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        # 1. Envoi hello de l'engine
        hello_msg = {
            "type": "hello",
            "v": CONTRACT_VERSION,
            "engine_version": "0.1.0-test",
        }
        client_tx.sendto(json.dumps(hello_msg).encode("utf-8"), ("127.0.0.1", PORT_CMD))

        # Traitement côté serveur
        time.sleep(0.05)
        server.process_incoming_datagrams()
        assert server.engine_connected is True

        # Réception du hello_ack côté client
        ack_data, _ = client_rx.recvfrom(2048)
        ack_json = json.loads(ack_data.decode("utf-8"))
        assert ack_json["type"] == "hello_ack"
        assert ack_json["v"] == CONTRACT_VERSION

        # 2. Envoi commande select_route
        cmd_msg = {
            "type": "cmd",
            "v": CONTRACT_VERSION,
            "cmd_id": 1,
            "name": "select_route",
            "args": {"route_id": "test-pass"},
        }
        client_tx.sendto(json.dumps(cmd_msg).encode("utf-8"), ("127.0.0.1", PORT_CMD))

        time.sleep(0.05)
        server.process_incoming_datagrams()
        assert len(received_cmds) == 1
        assert received_cmds[0][0] == "select_route"
        assert received_cmds[0][2] == 1
        assert server.last_cmd_id == 1

        # 3. Émission d'un état 30 Hz
        state = IpcState(
            session_state="READY",
            route_id="test-pass",
            power=210.0,
            cadence=85.0,
            gear=12,
        )
        server.send_state(state)

        state_data, _ = client_rx.recvfrom(2048)
        state_json = json.loads(state_data.decode("utf-8"))
        assert state_json["type"] == "state"
        assert state_json["session_state"] == "READY"
        assert state_json["last_cmd_id"] == 1
        assert state_json["seq"] == 1

        # 4. Idempotence : renvoi du même cmd_id
        client_tx.sendto(json.dumps(cmd_msg).encode("utf-8"), ("127.0.0.1", PORT_CMD))
        time.sleep(0.05)
        server.process_incoming_datagrams()
        assert len(received_cmds) == 1  # Pas de doublon

    finally:
        server.stop()
        client_rx.close()
        client_tx.close()
