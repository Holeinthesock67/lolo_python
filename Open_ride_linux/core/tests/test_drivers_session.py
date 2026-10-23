"""Tests du pilote FTMS, du fournisseur Click et de la boucle de séance (client BLE simulé)."""

import asyncio
import struct

from openride_core import fit_export, ftms, zwift_click
from openride_core.config import Config, TrainerConfig, BikeConfig
from openride_core.ftms_driver import FtmsDriver
from openride_core.input_providers import NullProvider, ZwiftClickProvider
from openride_core.mock_driver import MockDriver, TrainerMetrics
from openride_core.session import CoreSession
from openride_core.zwift_click import InputEvent


class FakeServices:
    def __init__(self, uuids):
        self.uuids = set(uuids)

    def get_characteristic(self, uuid):
        return object() if uuid in self.uuids else None


class FakeClient:
    def __init__(self, uuids):
        self.services = FakeServices(uuids)
        self.cbs, self.writes = {}, []
        self.is_connected = True
        self.disconnected_cb = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.is_connected = False

    async def start_notify(self, uuid, cb):
        self.cbs[uuid] = cb

    async def read_gatt_char(self, uuid):
        return struct.pack("<II", 0x4402, 0x2008)  # puissance+cadence ; power_target+SIM

    async def write_gatt_char(self, uuid, data, response=True):
        self.writes.append((uuid, bytes(data)))

    def drop(self):
        self.disconnected_cb(self)


def make_factory(client):
    def factory(dev, disconnected_callback=None, timeout=None):
        client.disconnected_cb = disconnected_callback
        return client
    return factory


async def fake_finder(name, address, timeout):
    return "fake-device"


def ibd(power, cadence=80, hr=0):
    flags = 0x0200 | 0x0040 | 0x0004
    return struct.pack("<HHHhB", flags, 2500, int(cadence * 2), power, hr)


async def wait_for(cond, timeout=2.0):
    end = asyncio.get_running_loop().time() + timeout
    while not cond():
        assert asyncio.get_running_loop().time() < end, "délai dépassé"
        await asyncio.sleep(0.01)


def test_ftms_driver_data_and_commands():
    async def scenario():
        client = FakeClient([ftms.INDOOR_BIKE_DATA, ftms.FEATURE, ftms.HR_MEASUREMENT])
        trainer = TrainerConfig(power_smooth_tau_s=0.0)
        drv = FtmsDriver(trainer, BikeConfig(), device_finder=fake_finder,
                         client_factory=make_factory(client))
        assert drv.status == "RECONNECTING"
        task = asyncio.create_task(drv.run())
        await wait_for(lambda: ftms.INDOOR_BIKE_DATA in client.cbs)
        client.cbs[ftms.INDOOR_BIKE_DATA](None, bytearray(ibd(215, 85, hr=0)))
        m = drv.poll()
        assert drv.status == "CONNECTED" and m.connected
        assert m.power_w == 215 and m.cadence_rpm == 85
        assert m.hr_bpm is None                      # 0 bpm = pas de mesure
        client.cbs[ftms.HR_MEASUREMENT](None, bytearray([0x00, 142]))
        assert drv.poll().hr_bpm == 142

        drv.set_sim_grade(40.0)                      # borné à +16 %
        def grade_written():
            return any(w[0] == ftms.OP_SET_SIM_PARAMS and struct.unpack_from("<h", w, 3)[0] == 1600
                       for _, w in client.writes)
        await wait_for(grade_written)
        ops = [w[1][0] for w in client.writes]
        assert ops[:2] == [ftms.OP_REQUEST_CONTROL, ftms.OP_START_RESUME]
        sim = [w for _, w in client.writes if w[0] == ftms.OP_SET_SIM_PARAMS][-1]
        assert struct.unpack_from("<h", sim, 3)[0] == 1600

        drv.stop()
        await asyncio.wait_for(task, 3)
        last = client.writes[-2][1]                  # résistance relâchée en partant…
        assert last[0] == ftms.OP_SET_SIM_PARAMS and struct.unpack_from("<h", last, 3)[0] == 0
        assert client.writes[-1][1] == ftms.cmd_reset()   # … puis contrôle FTMS rendu
    asyncio.run(scenario())


def test_ftms_driver_smoothing_and_loss():
    async def scenario():
        client = FakeClient([ftms.INDOOR_BIKE_DATA])
        now = [100.0]
        drv = FtmsDriver(TrainerConfig(power_smooth_tau_s=1.0), BikeConfig(),
                         device_finder=fake_finder, client_factory=make_factory(client),
                         clock=lambda: now[0])
        task = asyncio.create_task(drv.run())
        await wait_for(lambda: ftms.INDOOR_BIKE_DATA in client.cbs)
        drv.poll()
        client.cbs[ftms.INDOOR_BIKE_DATA](None, bytearray(ibd(300)))
        now[0] += 1.0
        p = drv.poll().power_w
        assert 150 < p < 220                         # 300·(1−e⁻¹) ≈ 190, pas un saut direct
        now[0] += 4.0                                # plus aucune donnée
        assert not drv.poll().connected and drv.status == "LOST"
        drv.stop()
        await asyncio.wait_for(task, 3)
    asyncio.run(scenario())


def click_frame(mask):
    out = bytearray([zwift_click.MSG_KEYPAD_STATUS, 0x08])
    v = mask
    while v > 0x7F:
        out.append(v & 0x7F | 0x80)
        v >>= 7
    out.append(v)
    return bytearray(out)


def test_click_provider_events_and_status():
    async def scenario():
        client = FakeClient([zwift_click.ZWIFT_ASYNC])
        now = [0.0]
        prov = ZwiftClickProvider(device_finder=fake_finder, client_factory=make_factory(client),
                                  clock=lambda: now[0])
        assert prov.status == "LOST"
        task = asyncio.create_task(prov.run())
        await wait_for(lambda: zwift_click.ZWIFT_ASYNC in client.cbs and prov.status == "CONNECTED")
        assert client.writes[0] == (zwift_click.ZWIFT_SYNC_RX, zwift_click.RIDE_ON)
        cb = client.cbs[zwift_click.ZWIFT_ASYNC]
        cb(None, click_frame(0xFFFFFFFF))
        for mask, held, expected in [(0xFFFFEFFF, 0.2, InputEvent.PLUS_SHORT),
                                     (0xFFFFFEFF, 1.5, InputEvent.MINUS_LONG)]:
            cb(None, click_frame(mask))
            now[0] += held
            cb(None, click_frame(0xFFFFFFFF))
            assert prov.events.get_nowait() == expected
        cb(None, bytearray([zwift_click.MSG_BATTERY_LEVEL, 0x10, 0x00, 0x10, 60]))
        prov.stop()
        await asyncio.wait_for(task, 3)
    asyncio.run(scenario())


def make_session(tmp_path, monkeypatch, driver=None, base_port=5700):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = base_port, base_port + 1
    return CoreSession(cfg, driver=driver or MockDriver(), inputs=[NullProvider()],
                       journal_dir=tmp_path / "journal",
                       routes_root=tmp_path / "routes")


def test_session_ride_gears_and_fit(tmp_path, monkeypatch):
    async def scenario():
        s = make_session(tmp_path, monkeypatch)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        assert s.state.session_state == "READY"
        s._on_command("start", {}, 2)
        k0, now = s.gearing.k, 1000.0
        for _ in range(500):                         # 10 s à 50 Hz
            now += 0.02
            s._step(0.02, now)
        assert s.state.session_state == "RUNNING" and s.state.s > 10 and s.state.power > 0
        s._handle_input(InputEvent.PLUS_SHORT)
        assert s.gearing.k == k0 + 1 and s.state.gear == k0 + 1
        s._on_command("end_session", {"save": True}, 3)
        assert s.state.session_state == "FINISHED"
        assert s.state.summary and (tmp_path / "act").glob("*.fit")
    asyncio.run(scenario())


def test_session_pauses_when_trainer_lost(tmp_path, monkeypatch):
    class LostDriver(MockDriver):
        def poll(self, t):
            return TrainerMetrics(connected=False)

    async def scenario():
        s = make_session(tmp_path, monkeypatch, LostDriver(), 5710)
        s._on_command("select_route", {}, 1)
        s._on_command("start", {}, 2)
        s._step(0.02, 10.0)
        assert s.state.session_state == "RUNNING"
        s._step(0.02, 13.5)
        assert (s.state.session_state, s.state.pause_reason) == ("PAUSED", "trainer_lost")
    asyncio.run(scenario())


def test_session_grade_is_rate_limited(tmp_path, monkeypatch):
    async def scenario():
        s = make_session(tmp_path, monkeypatch, base_port=5720)
        s._on_command("select_route", {}, 1)
        s._on_command("start", {}, 2)
        s.gearing.k = s.gearing.n_gears              # plus grand braquet : consigne forte
        for i in range(25):
            s._step(0.02, 50.0 + i * 0.02)
        assert abs(s._grade_sent) <= 2.0 * 0.5 + 1e-6    # ≤ 2 points/s sur 0,5 s
    asyncio.run(scenario())


def test_ble_connections_are_serialized():
    """Trainer et Click ne doivent jamais scanner/se connecter en même temps (BlueZ InProgress)."""
    async def scenario():
        active, peak = [0], [0]

        async def slow_finder(name, address, timeout):
            active[0] += 1
            peak[0] = max(peak[0], active[0])
            await asyncio.sleep(0.05)
            active[0] -= 1
            return "dev"

        c1 = FakeClient([ftms.INDOOR_BIKE_DATA])
        c2 = FakeClient([zwift_click.ZWIFT_ASYNC])
        drv = FtmsDriver(TrainerConfig(), BikeConfig(), device_finder=slow_finder,
                         client_factory=make_factory(c1))
        click = ZwiftClickProvider(device_finder=slow_finder, client_factory=make_factory(c2))
        tasks = [asyncio.create_task(drv.run()), asyncio.create_task(click.run())]
        await wait_for(lambda: click.status == "CONNECTED" and drv.status == "CONNECTED")
        assert peak[0] == 1
        drv.stop()
        click.stop()
        await asyncio.wait_for(asyncio.gather(*tasks), 3)
    asyncio.run(scenario())


def test_gear_shift_bypasses_grade_rate_limit(tmp_path, monkeypatch):
    async def scenario():
        s = make_session(tmp_path, monkeypatch, base_port=5730)
        s._on_command("select_route", {}, 1)
        s._on_command("start", {}, 2)
        for i in range(10):
            s._step(0.02, 60.0 + i * 0.02)
        before = s._grade_sent
        for _ in range(8):
            s._handle_input(InputEvent.PLUS_SHORT)
        s._step(0.02, 61.0)
        target = s.gearing.effective_grade(s.route.grade_at(s.physics.s))
        assert abs(s._grade_sent - target) < 0.5 and abs(s._grade_sent - before) > 0.04
    asyncio.run(scenario())


def test_input_event_command_and_autoresume(tmp_path, monkeypatch):
    async def scenario():
        s = make_session(tmp_path, monkeypatch, base_port=5740)
        s._autoresume = True
        s._on_command("select_route", {}, 1)
        s._on_command("start", {}, 2)
        k = s.gearing.k
        s._on_command("input_event", {"event": "PLUS_SHORT"}, 3)
        s._on_command("input_event", {"event": "n'importe quoi"}, 4)   # ignoré sans planter
        assert s.gearing.k == k + 1
        s._on_engine_lost()
        assert s.state.pause_reason == "engine_lost"
        s.server.engine_connected = True
        s._step(0.02, 5.0)
        assert s.state.session_state == "RUNNING"
    asyncio.run(scenario())


def test_long_press_jumps_three_gears(tmp_path, monkeypatch):
    async def scenario():
        s = make_session(tmp_path, monkeypatch, base_port=5750)
        s._on_command("select_route", {}, 1)
        s._on_command("start", {}, 2)
        k = s.gearing.k
        s._handle_input(InputEvent.PLUS_LONG)
        assert s.gearing.k == k + 3
        s._handle_input(InputEvent.MINUS_LONG)
        s._handle_input(InputEvent.MINUS_LONG)
        assert s.gearing.k == k - 3
        s.gearing.k = s.gearing.n_gears - 1          # butée haute respectée
        s._handle_input(InputEvent.PLUS_LONG)
        assert s.gearing.k == s.gearing.n_gears
    asyncio.run(scenario())
