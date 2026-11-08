"""Tests unitaires du lot Q6 : boîtier gauche du Zwift Click muet après la connexion."""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from pathlib import Path

import pytest

from openride_core import ble_sim, input_providers, sim_scenarios, zwift_click
from openride_core.ble_sim import SimClickBox, SimWorld, keypad_message
from openride_core.input_providers import ClickPair, ZwiftClickProvider
from openride_core.sim_scenarios import build_world, load_scenario
from openride_core.tools import ble_diag
from test_drivers_session import FakeClient, click_frame, fake_finder, make_factory, wait_for

RELEASED = zwift_click.KEYPAD_ALL_RELEASED
PLUS = RELEASED & ~(1 << zwift_click.KEYPAD_PLUS_BIT)
MINUS = RELEASED & ~(1 << zwift_click.KEYPAD_MINUS_BIT)


def test_classify_message():
    """Classement des messages ASYNC en 'boutons', 'batterie', 'maintien', 'inconnu'."""
    assert zwift_click.classify_message(bytes([zwift_click.MSG_KEYPAD_STATUS, 0x08, 0x01])) == "boutons"
    assert zwift_click.classify_message(bytes([zwift_click.MSG_CLICK_NOTIFICATION, 0x08, 0x01])) == "boutons"
    assert zwift_click.classify_message(bytes([zwift_click.MSG_CONTROLLER_NOTIFICATION, 0x08])) == "boutons"
    assert zwift_click.classify_message(bytes([zwift_click.MSG_BATTERY_LEVEL, 0x10, 80])) == "batterie"
    assert zwift_click.classify_message(bytes([zwift_click.MSG_EMPTY, 0x00])) == "maintien"
    assert zwift_click.classify_message(bytes([0x99, 0x01])) == "inconnu"
    assert zwift_click.classify_message(b"") == "inconnu"
    assert zwift_click.classify_message(STATUS_UNLOCKED) == "etat"


STATUS_UNLOCKED = zwift_click.STATUS_HEADER + bytes([0x04, 0x08, 0x01, 0x10, 0x00])
STATUS_LOCKED = zwift_click.STATUS_HEADER + bytes([0x04, 0x08, 0x01, 0x10, 0x01])


def test_parse_status():
    """Le champ 2 du message d'état est le mode (0 : boutons en clair, 1 : verrouillé)."""
    assert zwift_click.parse_status(STATUS_UNLOCKED) == 0
    assert zwift_click.parse_status(STATUS_LOCKED) == 1
    assert zwift_click.parse_status(zwift_click.STATUS_HEADER + bytes([0x00])) == 0
    assert zwift_click.parse_status(bytes([zwift_click.MSG_EMPTY, 0x00])) is None
    assert zwift_click.parse_status(zwift_click.STATUS_HEADER) is None
    # Trames reçues du vrai boîtier gauche (30/10, numéro de série du champ 1 remplacé par des zéros) :
    # le champ de longueur 1 précède le mode.
    real_unlocked = bytes.fromhex("ff0500ea05180a0c0000000000000000000000001000180f20082809301f")
    real_locked = bytes.fromhex("ff0500ea05190a0c000000000000000000000000100118840720082809301f")
    assert zwift_click.classify_message(real_locked) == "etat"
    assert zwift_click.parse_status(real_unlocked) == 0
    assert zwift_click.parse_status(real_locked) == 1


def _locked_session(reset_locked: str, caplog, monkeypatch):
    """Boîtier gauche simulé : mode 0 puis mode 1 ; renvoie les écritures sur SYNC_RX."""
    monkeypatch.setattr(input_providers, "last_trainer_write_at", lambda: None)
    caplog.set_level(logging.INFO, logger="input")
    writes: list[bytes] = []

    async def scenario():
        client = FakeClient([zwift_click.ZWIFT_ASYNC, zwift_click.ZWIFT_SYNC_RX, zwift_click.ZWIFT_SYNC_TX])
        original = client.write_gatt_char

        async def tracking(char, data, response=True):
            writes.append(bytes(data))
            await original(char, data, response)

        client.write_gatt_char = tracking
        prov = ZwiftClickProvider(device_finder=fake_finder, client_factory=make_factory(client),
                                  reset_locked=reset_locked, side="gauche")
        task = asyncio.create_task(prov.run())
        await wait_for(lambda: prov.status == "CONNECTED")
        cb = client.cbs[zwift_click.ZWIFT_ASYNC]
        cb(None, STATUS_UNLOCKED)
        await asyncio.sleep(0.5)
        assert zwift_click.RESET_POD not in writes
        cb(None, STATUS_LOCKED)
        cb(None, STATUS_LOCKED)
        await asyncio.sleep(0.5)
        prov.stop()
        await asyncio.wait_for(task, 2.0)

    asyncio.run(scenario())
    return writes


def test_locked_status_resets_pod_once(caplog, monkeypatch):
    """Réglage activé : le mode 1 déclenche un seul redémarrage 0x18, noté au journal."""
    writes = _locked_session("reset", caplog, monkeypatch)
    assert writes.count(zwift_click.RESET_POD) == 1
    lines = [r.getMessage() for r in caplog.records]
    assert any("mode 1 (verrouillé par Zwift)" in m for m in lines)
    assert any("redémarrage du boîtier (0x18)" in m for m in lines)


def test_locked_status_without_setting_only_logs(caplog, monkeypatch):
    """Réglage désactivé (défaut) : l'état est journalisé, aucun octet 0x18 n'est écrit."""
    writes = _locked_session("off", caplog, monkeypatch)
    assert zwift_click.RESET_POD not in writes
    assert any("mode 1 (verrouillé par Zwift)" in r.getMessage() for r in caplog.records)


def test_locked_status_logs_window(caplog, monkeypatch):
    """Lot K9 : la fenêtre de boutons en clair du boîtier gauche est fermée et journalisée au verrou."""
    _locked_session("reset", caplog, monkeypatch)
    lines = [r.getMessage() for r in caplog.records]
    assert any("fenêtre de boutons de" in m and "fin par verrou" in m and "choix reset" in m for m in lines)


def _keep_session(caplog, monkeypatch, relock: bool):
    """Choix « keep » : activation complète, écho RideOn et défi 0xFF, puis verrou si `relock`."""
    monkeypatch.setattr(input_providers, "last_trainer_write_at", lambda: None)
    caplog.set_level(logging.INFO, logger="input")
    writes: list[bytes] = []
    result: dict = {}

    async def scenario():
        client = FakeClient([zwift_click.ZWIFT_ASYNC, zwift_click.ZWIFT_SYNC_RX, zwift_click.ZWIFT_SYNC_TX])
        original = client.write_gatt_char

        async def tracking(char, data, response=True):
            writes.append(bytes(data))
            await original(char, data, response)

        client.write_gatt_char = tracking
        prov = ZwiftClickProvider(device_finder=fake_finder, client_factory=make_factory(client),
                                  reset_locked="keep", side="gauche")
        task = asyncio.create_task(prov.run())
        await wait_for(lambda: len(writes) >= 3)
        client.cbs[zwift_click.ZWIFT_SYNC_TX](None, bytearray(b"RideOn\x01\x03"))
        cb = client.cbs[zwift_click.ZWIFT_ASYNC]
        cb(None, STATUS_UNLOCKED)
        await wait_for(lambda: writes.count(zwift_click.KEEP_UNLOCKED) >= 1)
        cb(None, bytes([0xFF, 0x03, 0x00, 0x11, 0x22]))   # défi
        await wait_for(lambda: writes.count(zwift_click.KEEP_UNLOCKED) >= 2)
        if relock:
            cb(None, STATUS_LOCKED)
            await wait_for(lambda: zwift_click.RESET_POD in writes)
        else:
            await asyncio.sleep(0.5)
        result["counts"] = dict(prov.msg_counts)
        prov.stop()
        await asyncio.wait_for(task, 2.0)
        result["windows"] = prov.windows

    asyncio.run(scenario())
    return writes, result


def test_keep_sends_full_activation_and_keep_replies(caplog, monkeypatch):
    """Essai D : trois écritures d'activation, `ff 04 00` à l'écho et au défi, aucun redémarrage sans verrou."""
    writes, result = _keep_session(caplog, monkeypatch, relock=False)
    assert writes[:3] == list(zwift_click.ACTIVATION)
    assert writes.count(zwift_click.KEEP_UNLOCKED) == 2
    assert zwift_click.RESET_POD not in writes
    assert result["counts"]["defi"] == 1 and result["counts"]["etat"] == 1
    assert [w["cause"] for w in result["windows"]] == ["arrêt"]
    assert result["windows"][0]["keep_replies"] == 2 and result["windows"][0]["policy"] == "keep"


def test_keep_falls_back_to_reset_when_lock_returns(caplog, monkeypatch):
    """Choix « keep » : si le verrou revient malgré `ff 04 00`, repli sur un seul redémarrage 0x18."""
    writes, result = _keep_session(caplog, monkeypatch, relock=True)
    assert writes.count(zwift_click.RESET_POD) == 1
    lines = [r.getMessage() for r in caplog.records]
    assert any("maintien échoué" in m and "2 réponses ff 04 00" in m for m in lines)
    assert result["windows"][0]["cause"] == "verrou"


def test_reset_policy_keeps_plain_handshake(monkeypatch):
    """Hors « keep », la poignée de main reste `RideOn` seul et aucun `ff 04 00` n'est écrit."""
    writes = []

    async def scenario():
        client = FakeClient([zwift_click.ZWIFT_ASYNC, zwift_click.ZWIFT_SYNC_RX, zwift_click.ZWIFT_SYNC_TX])
        prov = ZwiftClickProvider(device_finder=fake_finder, client_factory=make_factory(client),
                                  reset_locked="reset", side="gauche")
        task = asyncio.create_task(prov.run())
        await wait_for(lambda: prov.status == "CONNECTED" and client.writes)
        client.cbs[zwift_click.ZWIFT_SYNC_TX](None, bytearray(b"RideOn\x01\x03"))
        client.cbs[zwift_click.ZWIFT_ASYNC](None, bytes([0xFF, 0x03, 0x00]))
        await asyncio.sleep(0.4)
        writes.extend(d for _u, d in client.writes)
        prov.stop()
        await asyncio.wait_for(task, 2.0)

    asyncio.run(scenario())
    assert writes == [zwift_click.RIDE_ON]


def test_lock_policy_rejects_unknown_value():
    with pytest.raises(ValueError):
        ZwiftClickProvider(reset_locked="maybe")


def test_config_reads_old_boolean_and_choices():
    """`click_reset_locked` : trois choix ; les booléens d'avant le lot K9 restent lus."""
    from openride_core.config import ConfigError, from_dict

    assert from_dict({}).drivers.click_reset_locked == "reset"
    assert from_dict({"drivers": {"click_reset_locked": True}}).drivers.click_reset_locked == "reset"
    assert from_dict({"drivers": {"click_reset_locked": False}}).drivers.click_reset_locked == "off"
    assert from_dict({"drivers": {"click_reset_locked": "keep"}}).drivers.click_reset_locked == "keep"
    with pytest.raises(ConfigError):
        from_dict({"drivers": {"click_reset_locked": "toujours"}})


def test_classify_challenge():
    assert zwift_click.classify_message(bytes([0xFF, 0x03, 0x00])) == "defi"
    assert zwift_click.classify_message(STATUS_LOCKED) == "etat"


def test_trace_raw_disabled_log_identical(caplog, monkeypatch):
    """Critère 2 : trace brute désactivée, le journal est identique à aujourd'hui."""
    monkeypatch.setattr(input_providers, "last_trainer_write_at", lambda: None)
    caplog.set_level(logging.INFO, logger="input")

    async def scenario():
        client = FakeClient([zwift_click.ZWIFT_ASYNC])
        now = [100.0]
        prov = ZwiftClickProvider(
            device_finder=fake_finder,
            client_factory=make_factory(client),
            clock=lambda: now[0],
            trace_raw=False,
            side="gauche",
        )
        task = asyncio.create_task(prov.run())
        await wait_for(lambda: prov.status == "CONNECTED")
        cb = client.cbs[zwift_click.ZWIFT_ASYNC]
        for _ in range(10):
            now[0] += 0.1
            cb(None, click_frame(RELEASED))
        now[0] += 1.0
        prov.stop()
        await asyncio.wait_for(task, 2.0)

    asyncio.run(scenario())
    lines = [r.getMessage() for r in caplog.records if r.name == "input"]
    assert any("connecté" in m for m in lines)
    assert not any("type 0x" in m for m in lines)
    assert not any("résumé :" in m for m in lines)


def test_trace_raw_rate_limiting(caplog, monkeypatch):
    """Trace brute : au plus une ligne toutes les 2 s pour les messages répétés sans bouton."""
    monkeypatch.setattr(input_providers, "last_trainer_write_at", lambda: None)
    caplog.set_level(logging.INFO, logger="input")

    async def scenario():
        client = FakeClient([zwift_click.ZWIFT_ASYNC])
        now = [100.0]
        prov = ZwiftClickProvider(
            device_finder=fake_finder,
            client_factory=make_factory(client),
            clock=lambda: now[0],
            trace_raw=True,
            side="gauche",
        )
        task = asyncio.create_task(prov.run())
        await wait_for(lambda: prov.status == "CONNECTED")
        cb = client.cbs[zwift_click.ZWIFT_ASYNC]

        # 20 messages de maintien répétés en 1.5 s (< 2.0 s)
        for _ in range(20):
            now[0] += 0.05
            cb(None, bytes([zwift_click.MSG_EMPTY, 0x00]))

        # Passer le seuil de 2 s
        now[0] += 2.1
        cb(None, bytes([zwift_click.MSG_EMPTY, 0x00]))

        # Puis un appui bouton : doit être tracé immédiatement
        now[0] += 0.1
        cb(None, click_frame(MINUS))
        now[0] += 0.1
        cb(None, click_frame(RELEASED))

        prov.stop()
        await asyncio.wait_for(task, 2.0)

    asyncio.run(scenario())
    lines = [r.getMessage() for r in caplog.records if r.name == "input"]
    trace_lines = [m for m in lines if "ASYNC type" in m]
    assert len(trace_lines) >= 1
    # Doit avoir un message avec regroupement
    assert any("messages)" in m for m in trace_lines)
    # L'appui bouton est tracé
    assert any("Click gauche ASYNC type 0x23 (boutons)" in m for m in trace_lines)


def test_mute_detection_after_mute_after_s(caplog, monkeypatch):
    """Critère 3 : détection muet après click_mute_after_s, une seule fois."""
    monkeypatch.setattr(input_providers, "last_trainer_write_at", lambda: None)
    caplog.set_level(logging.INFO, logger="input")

    async def scenario():
        client = FakeClient([zwift_click.ZWIFT_ASYNC])
        now = [0.0]
        prov = ZwiftClickProvider(
            device_finder=fake_finder,
            client_factory=make_factory(client),
            clock=lambda: now[0],
            mute_after_s=60.0,
            side="gauche",
        )
        task = asyncio.create_task(prov.run())
        await wait_for(lambda: prov.status == "CONNECTED")
        cb = client.cbs[zwift_click.ZWIFT_ASYNC]

        # Envoie des notifications régulières sans bouton pendant 65 s
        for _ in range(65):
            now[0] += 1.0
            cb(None, bytes([zwift_click.MSG_EMPTY, 0x00]))
            await asyncio.sleep(0.005)

        prov.stop()
        await asyncio.wait_for(task, 2.0)

    asyncio.run(scenario())
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    mute_warnings = [m for m in warnings if "connecté mais muet depuis 60 s" in m]
    assert len(mute_warnings) == 1
    assert mute_warnings[0] == "Click gauche : connecté mais muet depuis 60 s"


def test_scenario_click_gauche_muet_sim():
    """Critère 3 : scénario click_gauche_muet dans ble_sim."""
    async def scenario():
        spec = load_scenario("click_gauche_muet")
        world = build_world(spec, trainer=False, hr=False)
        left_box = next(b for b in world.clicks if b.role == "-")
        right_box = next(b for b in world.clicks if b.role == "+")

        assert left_box.mute_after_s == 5.0
        assert right_box.mute_after_s is None

        # Simuler la connexion
        t_conn = world.now()
        left_box.on_connect()
        right_box.on_connect()
        left_box.write(zwift_click.ZWIFT_SYNC_RX, zwift_click.RIDE_ON)
        right_box.write(zwift_click.ZWIFT_SYNC_RX, zwift_click.RIDE_ON)

        assert not left_box.is_muted
        assert not right_box.is_muted

        # Simuler temps écoulé 6 s (> 5 s)
        left_box._connected_at = t_conn - 6.0
        assert left_box.is_muted
        assert not right_box.is_muted  # boîtier droit non touché

    asyncio.run(scenario())


def test_rehandshake_recovery_with_unblock(caplog, monkeypatch):
    """Critère 4 : reprise automatique avec déblocage au 2e RIDE_ON."""
    monkeypatch.setattr(input_providers, "last_trainer_write_at", lambda: None)
    caplog.set_level(logging.INFO, logger="input")

    async def scenario():
        client = FakeClient([zwift_click.ZWIFT_ASYNC, zwift_click.ZWIFT_SYNC_RX, zwift_click.ZWIFT_SYNC_TX])
        now = [0.0]
        ride_on_writes = [0]
        original_write = client.write_gatt_char

        async def tracking_write(char, data, response=True):
            if data == zwift_click.RIDE_ON:
                ride_on_writes[0] += 1
            return await original_write(char, data, response)

        client.write_gatt_char = tracking_write

        prov = ZwiftClickProvider(
            device_finder=fake_finder,
            client_factory=make_factory(client),
            clock=lambda: now[0],
            mute_after_s=2.0,
            rehandshake_s=2.0,
            side="gauche",
        )
        task = asyncio.create_task(prov.run())
        await wait_for(lambda: prov.status == "CONNECTED")
        cb = client.cbs[zwift_click.ZWIFT_ASYNC]

        assert ride_on_writes[0] == 1

        # Rendre muet en envoyant des messages sans bouton pendant > 2s
        for _ in range(10):
            now[0] += 0.5
            cb(None, bytes([zwift_click.MSG_EMPTY, 0x00]))
            await asyncio.sleep(0.05)

        # 2e RIDE_ON doit avoir été émis lors de la reprise étape 1
        await wait_for(lambda: ride_on_writes[0] >= 2)

        # Déblocage : l'appui bouton est reçu
        now[0] += 0.1
        cb(None, click_frame(MINUS))
        now[0] += 0.1
        cb(None, click_frame(RELEASED))
        await wait_for(lambda: not prov.events.empty())
        ev = prov.events.get_nowait()
        assert ev == zwift_click.InputEvent.MINUS_SHORT

        prov.stop()
        await asyncio.wait_for(task, 2.0)

    asyncio.run(scenario())
    lines = [r.getMessage() for r in caplog.records if r.name == "input"]
    assert any("connecté mais muet" in m for m in lines)
    assert any("tentative de reprise 1/3 (renvoi de RideOn)" in m for m in lines)


def test_rehandshake_without_unblock_stops_after_3_attempts(caplog, monkeypatch):
    """Critère 4 : sans déblocage, arrêt après 3 étapes, sans boucle."""
    monkeypatch.setattr(input_providers, "last_trainer_write_at", lambda: None)
    caplog.set_level(logging.INFO, logger="input")

    async def scenario():
        client = FakeClient([zwift_click.ZWIFT_ASYNC, zwift_click.ZWIFT_SYNC_RX, zwift_click.ZWIFT_SYNC_TX])
        # Add stop_notify and disconnect to FakeClient for recovery steps 2 and 3
        client.stop_notify = lambda char: asyncio.sleep(0)
        client.disconnect = lambda: client.drop()

        now = [0.0]
        prov = ZwiftClickProvider(
            device_finder=fake_finder,
            client_factory=make_factory(client),
            clock=lambda: now[0],
            mute_after_s=2.0,
            rehandshake_s=2.0,
            side="gauche",
        )
        task = asyncio.create_task(prov.run())
        await wait_for(lambda: prov.status == "CONNECTED")

        # Messages sans bouton pendant 10 s d'horloge du test. La boucle de surveillance du provider
        # tourne toutes les 0,2 s réelles : on lui laisse un tour par pas d'horloge.
        for _ in range(20):
            now[0] += 0.5
            cb = client.cbs.get(zwift_click.ZWIFT_ASYNC)
            if cb is not None:
                cb(None, bytes([zwift_click.MSG_EMPTY, 0x00]))
            await asyncio.sleep(0.25)

        prov.stop()
        await asyncio.wait_for(task, 2.0)

    asyncio.run(scenario())
    lines = [r.getMessage() for r in caplog.records if r.name == "input"]
    steps = [m for m in lines if "tentative de reprise" in m]
    assert len(steps) == 3
    assert "1/3" in steps[0]
    assert "2/3" in steps[1]
    assert "3/3" in steps[2]


def test_ble_diag_trace_subcommand(tmp_path, monkeypatch):
    """Lecture et analyse d'une trace brute par openride-ble-diag trace."""
    monkeypatch.setattr(ble_diag, "REPORT_DIR", tmp_path / "spike_reports")   # pas ./spike_reports du dépôt
    trace_file = tmp_path / "click_test.log"
    trace_file.write_text(
        "12:00:00 INFO input Click gauche ASYNC type 0x15 (maintien) : 1500 (15 messages)\n"
        "12:00:02 INFO input Click gauche ASYNC type 0x23 (boutons) : 2308feffff0f\n"
        "12:00:04 INFO input Click gauche ASYNC type 0x19 (batterie) : 191050\n",
        encoding="utf-8",
    )
    args = argparse.Namespace(file=str(trace_file))
    asyncio.run(ble_diag.cmd_trace(args))
    assert len(list((tmp_path / "spike_reports").glob("*_click_trace.json"))) == 1


def test_session_passes_q6_settings_and_side(tmp_path):
    """Les réglages [drivers] du fichier donné à la séance arrivent aux deux boîtiers (pas de relecture
    de ~/OpenRide/config.toml) ; le côté vient des adresses configurées, pas de la fin de l'adresse."""
    from openride_core.config import from_dict
    from openride_core.session import build_inputs

    cfg = from_dict({"drivers": {"input": "click", "click_trace_raw": True, "click_mute_after_s": 45.0,
                                 "click_rehandshake_s": 30.0, "click_reset_locked": "keep", "click_address": "AA:BB:CC:00:00:7F",
                                 "click_minus_address": "AA:BB:CC:00:00:3C"}})
    plus, minus = [p for p in build_inputs(cfg) if isinstance(p, ZwiftClickProvider)]
    for p in (plus, minus):
        assert (p.trace_raw, p.mute_after_s, p.rehandshake_s, p.reset_locked) == (True, 45.0, 30.0, "keep")
    assert plus.side == "droit"
    assert minus.side == "gauche"
    # Sans adresse configurée ni connexion, le côté n'est pas deviné
    bare = [p for p in build_inputs(from_dict({"drivers": {"input": "click"}}))
            if isinstance(p, ZwiftClickProvider)]
    assert [p.side for p in bare] == ["inconnu", "inconnu"]
    # Par défaut, le boîtier gauche verrouillé par Zwift est redémarré (essai PC du 30/10/2026)
    assert all(p.trace_raw is False and p.rehandshake_s == 0.0 and p.reset_locked == "reset" for p in bare)
