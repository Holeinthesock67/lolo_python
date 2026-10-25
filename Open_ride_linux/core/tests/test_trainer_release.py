"""Le trainer doit toujours être rendu libre en partant : aucune consigne (ERG ou pente) ne reste
active et le contrôle FTMS est rendu (Reset), pour qu'une autre application puisse s'en servir."""

import asyncio
import os
import signal
import struct

from openride_core import __main__ as cli
from openride_core import ftms, ftms_driver
from openride_core.config import BikeConfig, Config, TrainerConfig
from openride_core.ftms_driver import FtmsDriver, release_trainer
from openride_core.mock_driver import MockDriver

from test_drivers_session import FakeClient, fake_finder, ibd, make_factory, make_session, wait_for


def cp_ops(client):
    return [w[0] for uuid, w in client.writes if uuid == ftms.CONTROL_POINT]


def assert_released(client):
    """Les deux dernières écritures : pente 0 % puis Reset ; puis déconnexion."""
    last = [w for uuid, w in client.writes if uuid == ftms.CONTROL_POINT][-2:]
    assert last[0][0] == ftms.OP_SET_SIM_PARAMS and struct.unpack_from("<h", last[0], 3)[0] == 0
    assert last[1] == ftms.cmd_reset()
    assert not client.is_connected


async def start_driver(client, **kw):
    drv = FtmsDriver(TrainerConfig(), BikeConfig(), device_finder=fake_finder,
                     client_factory=make_factory(client), **kw)
    task = asyncio.create_task(drv.run())
    await wait_for(lambda: ftms.INDOOR_BIKE_DATA in client.cbs)
    client.cbs[ftms.INDOOR_BIKE_DATA](None, bytearray(ibd(200)))
    return drv, task


def test_reset_command_encoding():
    assert ftms.cmd_reset() == bytes([0x01])


def test_stop_after_erg_cancels_target_and_releases_control():
    async def scenario():
        client = FakeClient([ftms.INDOOR_BIKE_DATA, ftms.FEATURE])
        drv, task = await start_driver(client)
        drv.set_target_power(250)
        await wait_for(lambda: ftms.OP_SET_TARGET_POWER in cp_ops(client))
        drv.stop()
        await asyncio.wait_for(task, 3)
        assert_released(client)
    asyncio.run(scenario())


def test_release_survives_a_hanging_write(monkeypatch):
    """Une écriture BLE qui ne répond plus ne bloque ni le Reset ni la déconnexion."""
    monkeypatch.setattr(ftms_driver, "RELEASE_WRITE_TIMEOUT_S", 0.05)

    class HangingSim(FakeClient):
        releasing = False

        async def write_gatt_char(self, uuid, data, response=True):
            if self.releasing and data[0] == ftms.OP_SET_SIM_PARAMS:
                await asyncio.sleep(10)
            await super().write_gatt_char(uuid, data, response)

    async def scenario():
        client = HangingSim([ftms.INDOOR_BIKE_DATA])
        drv, task = await start_driver(client)
        await wait_for(lambda: ftms.OP_SET_SIM_PARAMS in cp_ops(client))
        client.releasing = True
        drv.stop()
        await asyncio.wait_for(task, 2)
        assert cp_ops(client)[-1] == ftms.OP_RESET and not client.is_connected
    asyncio.run(scenario())


def test_reset_refusal_is_harmless():
    async def scenario():
        client = FakeClient([ftms.INDOOR_BIKE_DATA])
        drv, task = await start_driver(client)
        client.cbs[ftms.CONTROL_POINT](None, bytearray([ftms.OP_RESPONSE, ftms.OP_RESET, 0x02]))
        assert not drv.control_refused
        drv.stop()
        await asyncio.wait_for(task, 3)
    asyncio.run(scenario())


def test_cancelled_driver_still_disconnects():
    """Tâche annulée (arrêt forcé du core) : la liaison BLE est quand même fermée."""
    async def scenario():
        client = FakeClient([ftms.INDOOR_BIKE_DATA])
        drv, task = await start_driver(client)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        assert not client.is_connected
    asyncio.run(scenario())


def test_session_shutdown_releases_trainer_even_if_fit_fails(tmp_path, monkeypatch):
    async def scenario():
        client = FakeClient([ftms.INDOOR_BIKE_DATA])
        drv = FtmsDriver(TrainerConfig(), BikeConfig(), device_finder=fake_finder,
                         client_factory=make_factory(client))
        s = make_session(tmp_path, monkeypatch, drv, 5760)
        s._on_command("select_route", {}, 1)
        s._on_command("start", {}, 2)
        task = asyncio.create_task(drv.run())
        await wait_for(lambda: ftms.INDOOR_BIKE_DATA in client.cbs)

        def broken_finish(*a, **k):
            raise OSError("disque plein")
        monkeypatch.setattr(s, "_finish", broken_finish)
        s.server.start()
        await s._shutdown([task])
        assert task.done()
        assert_released(client)
    asyncio.run(scenario())


def test_sighup_stops_the_core_cleanly(tmp_path, monkeypatch):
    """Terminal fermé (SIGHUP) : arrêt propre au lieu d'une mort sans relâcher le trainer."""
    if not hasattr(signal, "SIGHUP"):
        pytest.skip("SIGHUP non disponible sur cette plateforme")
    stopped = []

    class Driver(MockDriver):
        async def run(self):
            while not stopped:
                await asyncio.sleep(0.01)

        def stop(self):
            stopped.append(True)

    async def scenario():
        s = make_session(tmp_path, monkeypatch, Driver(), 5770)
        run = asyncio.create_task(s.run())
        await asyncio.sleep(0.2)
        os.kill(os.getpid(), signal.SIGHUP)
        await asyncio.wait_for(run, 5)
        assert stopped
    asyncio.run(scenario())


def test_release_trainer_command(monkeypatch):
    """`openride-core release-trainer` : connexion, pente 0 %, Reset, déconnexion."""
    client = FakeClient([ftms.INDOOR_BIKE_DATA, ftms.CONTROL_POINT])

    async def fake_release(trainer, bike, address):
        return await release_trainer(trainer, bike, address, device_finder=fake_finder,
                                     client_factory=make_factory(client))
    monkeypatch.setattr(ftms_driver, "release_trainer", fake_release)
    monkeypatch.setattr("openride_core.config.load", lambda path=None: Config())
    assert cli.main(["release-trainer"]) == 0
    assert cp_ops(client)[0] == ftms.OP_REQUEST_CONTROL
    assert_released(client)


def test_release_trainer_when_absent():
    async def nobody(name, address, timeout):
        return None
    assert asyncio.run(release_trainer(TrainerConfig(), BikeConfig(), device_finder=nobody)) is False
