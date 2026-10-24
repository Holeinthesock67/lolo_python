"""Conformité à la spécification Bluetooth SIG Fitness Machine Service v1.0 (audit du 24 octobre).

Chaque test cite l'article de la spécification (FTMS v1.0) ou du GATT Specification Supplement
qu'il vérifie.
"""

import asyncio
import struct

from openride_core import ftms, ftms_driver
from openride_core.config import BikeConfig, TrainerConfig
from openride_core.ftms_driver import FtmsDriver, release_trainer

from test_drivers_session import FakeClient, fake_finder, ibd, make_factory, wait_for


def cp_ops(client):
    return [w[0] for uuid, w in client.writes if uuid == ftms.CONTROL_POINT]


async def start(client, **trainer_kw):
    drv = FtmsDriver(TrainerConfig(power_smooth_tau_s=0.0, **trainer_kw), BikeConfig(),
                     device_finder=fake_finder, client_factory=make_factory(client))
    task = asyncio.create_task(drv.run())
    await wait_for(lambda: ftms.INDOOR_BIKE_DATA in client.cbs)
    client.cbs[ftms.INDOOR_BIKE_DATA](None, bytearray(ibd(150)))
    return drv, task


def features_reader(target_bits):
    async def read(uuid):
        return struct.pack("<II", 0x4402, target_bits)
    return read


# §4.16.3 : une procédure à la fois ------------------------------------------------------

def test_control_point_waits_for_the_response_before_the_next_write():
    async def scenario():
        client = FakeClient([ftms.INDOOR_BIKE_DATA], cp_result=None)   # réponses à la main
        drv, task = await start(client)
        await wait_for(lambda: cp_ops(client) == [ftms.OP_REQUEST_CONTROL])
        await asyncio.sleep(0.3)
        assert cp_ops(client) == [ftms.OP_REQUEST_CONTROL]   # rien tant que pas de réponse
        client.cbs[ftms.CONTROL_POINT](None, bytearray([0x80, ftms.OP_REQUEST_CONTROL, 0x01]))
        await wait_for(lambda: ftms.OP_START_RESUME in cp_ops(client))
        drv.stop()
        await asyncio.wait_for(task, 5)
    asyncio.run(scenario())


def test_control_point_goes_on_without_response():
    """Trainer muet : on continue après `CP_RESPONSE_TIMEOUT_S`, sans rester bloqué."""
    async def scenario():
        ftms_driver.CP_RESPONSE_TIMEOUT_S, saved = 0.05, ftms_driver.CP_RESPONSE_TIMEOUT_S
        try:
            client = FakeClient([ftms.INDOOR_BIKE_DATA], cp_result=None)
            drv, task = await start(client)
            await wait_for(lambda: ftms.OP_SET_SIM_PARAMS in cp_ops(client))
            drv.stop()
            await asyncio.wait_for(task, 3)
            assert cp_ops(client)[-1] == ftms.OP_RESET
        finally:
            ftms_driver.CP_RESPONSE_TIMEOUT_S = saved
    asyncio.run(scenario())


def test_release_trainer_enables_indications_before_writing():
    """§4.16.3 : écrire sans indications actives donne l'erreur ATT 0xFD."""
    events = []

    class Client(FakeClient):
        async def start_notify(self, uuid, cb):
            events.append(("notify", uuid))
            await super().start_notify(uuid, cb)

        async def write_gatt_char(self, uuid, data, response=True):
            events.append(("write", data[0]))
            await super().write_gatt_char(uuid, data, response)

    client = Client([ftms.INDOOR_BIKE_DATA])
    ok = asyncio.run(release_trainer(TrainerConfig(), BikeConfig(), device_finder=fake_finder,
                                     client_factory=make_factory(client)))
    assert ok
    assert events[0] == ("notify", ftms.CONTROL_POINT)
    assert [e[1] for e in events[1:]] == [ftms.OP_REQUEST_CONTROL, ftms.OP_SET_SIM_PARAMS,
                                          ftms.OP_RESET]


# §4.17 : Fitness Machine Status ---------------------------------------------------------

def test_control_permission_lost_takes_control_again():
    async def scenario():
        client = FakeClient([ftms.INDOOR_BIKE_DATA, ftms.MACHINE_STATUS])
        drv, task = await start(client)
        await wait_for(lambda: ftms.OP_SET_SIM_PARAMS in cp_ops(client))
        assert ftms.MACHINE_STATUS in client.cbs
        n = cp_ops(client).count(ftms.OP_REQUEST_CONTROL)
        client.cbs[ftms.MACHINE_STATUS](None, bytearray([ftms.STATUS_CONTROL_LOST]))
        await wait_for(lambda: cp_ops(client).count(ftms.OP_REQUEST_CONTROL) == n + 1)
        drv.stop()
        await asyncio.wait_for(task, 3)
    asyncio.run(scenario())


def test_user_stop_on_the_trainer_is_not_overridden():
    async def scenario():
        client = FakeClient([ftms.INDOOR_BIKE_DATA, ftms.MACHINE_STATUS])
        drv, task = await start(client)
        await wait_for(lambda: ftms.OP_SET_SIM_PARAMS in cp_ops(client))
        n = cp_ops(client).count(ftms.OP_START_RESUME)
        client.cbs[ftms.MACHINE_STATUS](None, bytearray([0x03]))   # clé de sécurité
        await asyncio.sleep(0.3)
        assert cp_ops(client).count(ftms.OP_START_RESUME) == n
        drv.stop()
        await asyncio.wait_for(task, 3)
    asyncio.run(scenario())


def test_parse_machine_status():
    assert ftms.parse_machine_status(b"\xff") == (0xFF, "CONTROL_PERMISSION_LOST")
    assert ftms.parse_machine_status(b"\x08\x96\x00") == (0x08, "TARGET_POWER_CHANGED")
    assert ftms.parse_machine_status(b"") is None


# §4.3 et tableau 4.15 : opcodes exclus si la fonction n'est pas annoncée ----------------

def test_erg_not_sent_when_power_target_not_supported():
    async def scenario():
        client = FakeClient([ftms.INDOOR_BIKE_DATA, ftms.FEATURE])
        client.read_gatt_char = features_reader(1 << 13)   # SIM seulement
        drv, task = await start(client)
        assert drv.supports_sim and not drv.supports_erg
        drv.set_target_power(200)
        await asyncio.sleep(0.4)
        assert ftms.OP_SET_TARGET_POWER not in cp_ops(client)
        drv.stop()
        await asyncio.wait_for(task, 3)
    asyncio.run(scenario())


def test_release_without_sim_support_only_resets():
    async def scenario():
        client = FakeClient([ftms.INDOOR_BIKE_DATA, ftms.FEATURE])
        client.read_gatt_char = features_reader(1 << 3)   # ERG seulement
        drv, task = await start(client)
        drv.set_target_power(200)
        await wait_for(lambda: ftms.OP_SET_TARGET_POWER in cp_ops(client))
        drv.stop()
        await asyncio.wait_for(task, 3)
        assert ftms.OP_SET_SIM_PARAMS not in cp_ops(client)
        assert cp_ops(client)[-1] == ftms.OP_RESET
    asyncio.run(scenario())


def test_trainer_without_control_point_is_read_only():
    async def scenario():
        client = FakeClient([ftms.INDOOR_BIKE_DATA], cp=False)
        drv, task = await start(client)
        await asyncio.sleep(0.3)
        assert drv.status == "CONNECTED" and drv.poll().power_w == 150
        assert cp_ops(client) == []
        drv.stop()
        await asyncio.wait_for(task, 3)
    asyncio.run(scenario())


# §4.14 : plage de puissance et pas minimal ----------------------------------------------

def test_erg_target_is_a_multiple_of_the_announced_increment():
    drv = FtmsDriver(TrainerConfig(), BikeConfig())
    drv.power_range, drv.power_increment = (0.0, 1000.0), 5.0
    drv.set_target_power(203)
    assert drv._want.value == 205.0
    drv.set_target_power(999)
    assert drv._want.value == 1000.0


def test_command_parameters_saturate_at_sint16():
    assert struct.unpack_from("<h", ftms.cmd_set_target_power(40000), 1)[0] == 32767
    sim = ftms.cmd_set_sim_params(400.0, wind_mps=-40.0)
    assert struct.unpack_from("<hh", sim, 1) == (-32768, 32767)


# Indoor Bike Data (GATT Specification Supplement, §4.9 et §4.19) ------------------------

def test_resistance_level_on_two_bytes():
    data = struct.pack("<HHhh", 0x0060, 2500, 42, 180)   # vitesse, résistance sint16, puissance
    d = ftms.parse_indoor_bike_data(data)
    assert (d.resistance_level, d.power_w) == (42, 180)


def test_resistance_level_on_one_byte():
    data = struct.pack("<HHBh", 0x0060, 2500, 42, 180)   # résistance uint8 (supplément actuel)
    d = ftms.parse_indoor_bike_data(data)
    assert (d.resistance_level, d.power_w) == (42, 180)


def test_expended_energy_not_available():
    data = struct.pack("<HHHHB", 0x0100, 2500, 0xFFFF, 0xFFFF, 0xFF)
    assert ftms.parse_indoor_bike_data(data).total_energy_kcal is None
    data = struct.pack("<HHHHB", 0x0100, 2500, 312, 600, 10)
    assert ftms.parse_indoor_bike_data(data).total_energy_kcal == 312


def test_split_data_record_keeps_heart_rate():
    """§4.19 : une trame « More Data » sans le champ cardio ne l'efface pas."""
    async def scenario():
        client = FakeClient([ftms.INDOOR_BIKE_DATA])
        drv, task = await start(client)
        client.cbs[ftms.INDOOR_BIKE_DATA](None, bytearray(ibd(150, hr=131)))
        client.cbs[ftms.INDOOR_BIKE_DATA](None, bytearray(struct.pack("<Hh", 0x0041, 155)))
        m = drv.poll()
        assert m.hr_bpm == 131 and m.power_w == 155
        drv.stop()
        await asyncio.wait_for(task, 3)
    asyncio.run(scenario())
