"""Journal du Zwift Click pour le diagnostic des coupures (lot K8), avec les doublures BLE."""

import asyncio
import logging
import time

from openride_core import input_providers, zwift_click
from openride_core.input_providers import ZwiftClickProvider
from openride_core.tools.log_report import PATTERNS

from test_drivers_session import FakeClient, click_frame, fake_finder, make_factory, wait_for

RELEASED, PLUS = 0xFFFFFFFF, 0xFFFFEFFF


def click_lines(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "input"]


def test_click_connection_notifications_and_drop_are_journaled(caplog, monkeypatch):
    monkeypatch.setattr(input_providers, "last_trainer_write_at", lambda: time.monotonic() - 0.4)
    caplog.set_level(logging.INFO, logger="input")

    async def scenario():
        client = FakeClient([zwift_click.ZWIFT_ASYNC])
        now = [100.0]
        prov = ZwiftClickProvider(device_finder=fake_finder, client_factory=make_factory(client),
                                  clock=lambda: now[0])
        task = asyncio.create_task(prov.run())
        await wait_for(lambda: prov.status == "CONNECTED")
        cb = client.cbs[zwift_click.ZWIFT_ASYNC]
        # 25 notifications, dont 3 appuis (appui puis relâche) ; le dernier appui à t = 110.
        sent = 0
        for i in range(19):
            now[0] += 0.1
            cb(None, click_frame(RELEASED))
            sent += 1
        for _ in range(3):
            now[0] += 0.1
            cb(None, click_frame(PLUS))
            now[0] += 0.1
            cb(None, click_frame(RELEASED))
            sent += 2
        assert sent == 25
        last_press = now[0]
        now[0] += 5.0
        client.drop()
        await wait_for(lambda: prov.status == "LOST")
        await wait_for(lambda: any("déconnecté" in m for m in click_lines(caplog)))
        prov.stop()
        await asyncio.wait_for(task, 3)
        return last_press, now[0]

    last_press, t_drop = asyncio.run(scenario())
    lines = click_lines(caplog)
    up = next(m for m in lines if m.startswith("Zwift Click connecté"))
    assert up == "Zwift Click connecté (adresse fake-device, recherche 0.0 s, 1 tentative(s))"
    assert PATTERNS["click_connected"].match(up)
    assert sum(1 for m in lines if m == "Click : PLUS_SHORT") == 3

    down = next(m for m in lines if m.startswith("Zwift Click déconnecté"))
    m = PATTERNS["click_disconnected"].match(down)
    assert m, down
    assert float(m.group("connected")) == round(t_drop - 100.0, 1)
    assert m.group("since_notif") == "5.0 s"
    assert m.group("since_press") == f"{t_drop - last_press:.1f} s"   # appui reconnu à la relâche
    assert m.group("notifs") == "25"
    assert m.group("since_write") == "0.4 s"
    assert m.group("reason") == "lien perdu (rappel bleak)"


def test_click_notification_rate_every_minute(caplog, monkeypatch):
    monkeypatch.setattr(input_providers, "last_trainer_write_at", lambda: None)
    caplog.set_level(logging.INFO, logger="input")

    async def scenario():
        client = FakeClient([zwift_click.ZWIFT_ASYNC])
        now = [0.0]
        prov = ZwiftClickProvider(device_finder=fake_finder, client_factory=make_factory(client),
                                  clock=lambda: now[0])
        task = asyncio.create_task(prov.run())
        await wait_for(lambda: prov.status == "CONNECTED")
        cb = client.cbs[zwift_click.ZWIFT_ASYNC]
        for _ in range(600):
            now[0] += 0.1
            cb(None, click_frame(RELEASED))
        await wait_for(lambda: any("par seconde" in m for m in click_lines(caplog)))
        prov.stop()
        await asyncio.wait_for(task, 3)

    asyncio.run(scenario())
    lines = click_lines(caplog)
    rate = [m for m in lines if "par seconde" in m]
    assert rate == ["Click : 600 notification(s) en 60 s (10.0 par seconde)"]
    assert PATTERNS["click_rate"].match(rate[0])
    down = next(m for m in lines if m.startswith("Zwift Click déconnecté"))
    assert "dernier appui il y a jamais" in down and "trainer il y a jamais" in down
    assert "raison : arrêt du core" in down
