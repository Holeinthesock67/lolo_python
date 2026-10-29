"""Bluetooth simulé (`ble_sim.py`, `sim_scenarios.py`) : vrais pilotes contre des appareils simulés.

Chaque test déroule un petit scénario en temps réel (quelques secondes au plus) : c'est le même
code que `openride-core run --trainer sim --input sim --hr sim`, sans matériel.
"""

from __future__ import annotations

import asyncio
import json
import re
import struct

import pytest

from openride_core import ble_sim, ble_util, fit_export, ftms, hr_monitor
from openride_core.__main__ import build_parser, main
from openride_core.config import Config, ConfigError, from_dict
from openride_core.ftms_driver import FtmsDriver
from openride_core.input_providers import SimClickKeyboard, ZwiftClickProvider
from openride_core.session import CoreSession, build_driver, build_hr, build_inputs, build_sim_world
from openride_core.sim_scenarios import (SCENARIOS, SimScenarioError, build_world, load_scenario,
                                         validate)
from openride_core.zwift_click import InputEvent

READY = {"trainer": {"appear_at": 0.0, "connect_delay_s": 0.05},
         "click": {"appear_at": 0.05, "connect_delay_s": 0.05},
         "hr": {"appear_at": 0.0, "connect_delay_s": 0.05, "tau_s": 1.0}}


def sim_config(scenario: str = "nominal") -> Config:
    cfg = Config()
    cfg.drivers.trainer = cfg.drivers.input = cfg.drivers.hr = "sim"
    cfg.drivers.sim_scenario = scenario
    return cfg


async def wait_for(cond, timeout=5.0):
    end = asyncio.get_running_loop().time() + timeout
    while not cond():
        assert asyncio.get_running_loop().time() < end, "délai dépassé"
        await asyncio.sleep(0.02)


class Rig:
    """Monde simulé et vrais pilotes, lancés comme dans la séance."""

    def __init__(self, spec: dict, cfg: Config | None = None) -> None:
        cfg = cfg or sim_config()
        self.world = build_world(spec)
        self.driver = build_driver(cfg, self.world)
        self.inputs = build_inputs(cfg, self.world)
        self.hr = build_hr(cfg, self.world)
        self.parts = [self.driver, *self.inputs, self.hr, self.world]
        self.tasks: list[asyncio.Task] = []

    @property
    def trainer(self) -> ble_sim.SimTrainer:
        assert self.world.trainer is not None
        return self.world.trainer

    def start(self) -> "Rig":
        self.tasks = [asyncio.create_task(p.run()) for p in self.parts]
        return self

    async def stop(self) -> None:
        for p in self.parts:
            p.stop()
        done, pending = await asyncio.wait(self.tasks, timeout=5)
        assert not pending, "arrêt trop long"

    def events(self) -> list[InputEvent]:
        out = []
        for p in self.inputs:
            while not p.events.empty():
                out.append(p.events.get_nowait())
        return out

    def ops(self) -> list[int]:
        return [c.op for c in self.trainer.commands]


# --- trainer FTMS simulé ----------------------------------------------------------------

def test_control_point_rules():
    """0xFD sans indications, 0x05 sans contrôle, 0xFE pendant une procédure, Reset = contrôle rendu."""
    async def scenario():
        world = build_world(READY, hr=False, click=False)
        replies = []
        async with world.client_factory(await world.find_device("HomeTrainer", None, 1.0)) as client:
            with pytest.raises(ble_sim.SimBleError, match="0xfd"):
                await client.write_gatt_char(ftms.CONTROL_POINT, ftms.cmd_request_control())
            await client.start_notify(ftms.CONTROL_POINT, lambda _c, d: replies.append(bytes(d)))
            await client.write_gatt_char(ftms.CONTROL_POINT, ftms.cmd_set_target_power(200))
            with pytest.raises(ble_sim.SimBleError, match="0xfe"):
                await client.write_gatt_char(ftms.CONTROL_POINT, ftms.cmd_request_control())
            await wait_for(lambda: replies)
            assert replies[-1] == bytes([0x80, ftms.OP_SET_TARGET_POWER, 0x05])   # pas de contrôle
            for payload in (ftms.cmd_request_control(), ftms.cmd_start_resume(),
                            ftms.cmd_start_resume(), ftms.cmd_set_target_power(220)):
                n = len(replies)
                await client.write_gatt_char(ftms.CONTROL_POINT, payload)
                await wait_for(lambda: len(replies) > n)
            assert [r[2] for r in replies[-4:]] == [0x01, 0x01, 0x04, 0x01]   # 2e Start : déjà démarré
            assert world.trainer.mode == "erg" and world.trainer.target_w == 220
            await client.write_gatt_char(ftms.CONTROL_POINT, ftms.cmd_reset())
            await wait_for(lambda: replies[-1][1] == ftms.OP_RESET)
            assert world.trainer.released
    asyncio.run(scenario())


def test_ftms_driver_erg_sim_and_release():
    async def scenario():
        rig = Rig(READY).start()
        await wait_for(lambda: rig.driver.status == "CONNECTED")
        rig.driver.set_target_power(250)
        await wait_for(lambda: rig.trainer.mode == "erg" and rig.trainer.target_w == 250)
        await wait_for(lambda: abs(rig.driver.poll().power_w - 250) < 25, timeout=6)
        rig.driver.set_sim_grade(4.0)
        await wait_for(lambda: rig.trainer.mode == "sim" and rig.trainer.grade_pct == 4.0)
        await rig.stop()
        # Relâche : pente 0 % puis Reset, contrôle rendu, plus aucune consigne active.
        assert rig.ops()[-2:] == [ftms.OP_SET_SIM_PARAMS, ftms.OP_RESET]
        assert rig.trainer.released and rig.trainer.client is None
        assert ftms.OP_REQUEST_CONTROL in rig.ops()
    asyncio.run(scenario())


async def _watch_status(driver, seen: set) -> None:
    while True:
        seen.add(driver.status)
        await asyncio.sleep(0.01)


def test_att_error_0x80_is_resent_without_reconnecting(caplog):
    """Erreur ATT 0x80 ponctuelle (essai du 24 octobre) : renvoi de la consigne, liaison gardée (M1)."""
    async def scenario():
        rig = Rig(READY).start()
        await wait_for(lambda: rig.driver.status == "CONNECTED" and rig.trainer.control)
        rig.driver.set_target_power(200)
        await wait_for(lambda: rig.trainer.target_w == 200)
        seen: set = set()
        watcher = asyncio.create_task(_watch_status(rig.driver, seen))
        await rig.world.apply({"t": 0, "device": "trainer", "action": "att_error", "count": 1})
        rig.driver.set_target_power(240)
        await wait_for(lambda: rig.trainer.commands[-1].result is None)   # l'écriture ratée
        t_err = rig.trainer.commands[-1].t
        await wait_for(lambda: rig.trainer.target_w == 240)
        ok = next(c for c in rig.trainer.commands if c.t >= t_err and c.result == 0x01)
        assert ok.t - t_err < 0.6
        await asyncio.sleep(0.3)
        watcher.cancel()
        assert seen == {"CONNECTED"}
        assert rig.driver.reconnect_count == 0 and rig.driver.att_retries == 1
        assert rig.trainer.connections == 1
        await rig.stop()
    with caplog.at_level("INFO"):
        asyncio.run(scenario())
    msgs = [r.getMessage() for r in caplog.records]
    assert "Trainer : écriture 0x05 refusée (ATT 0x80), renvoi 1/2" in msgs
    assert "Trainer : écriture 0x05 acceptée au renvoi 1" in msgs
    assert not any("Reconnexion au trainer" in m for m in msgs)


@pytest.mark.parametrize("count, code, reconnects, deferrals", [
    (2, 0x80, 0, 0), (3, 0x80, 0, 1), (3, 0xFE, 0, 1), (3, 0x0E, 1, 0)])
def test_repeated_att_errors(count, code, reconnects, deferrals):
    """Deux erreurs de suite : renvois. Trois : Control Point occupé (0x80, 0xFE), consigne
    reportée sans couper la liaison ; autre code ATT : reconnexion, contrôle et consigne repris."""
    async def scenario():
        rig = Rig(READY).start()
        await wait_for(lambda: rig.driver.status == "CONNECTED" and rig.trainer.control)
        rig.driver.set_sim_grade(1.0)
        await wait_for(lambda: rig.trainer.grade_pct == 1.0)
        await rig.world.apply({"t": 0, "device": "trainer", "action": "att_error", "count": count,
                               "code": code})
        rig.driver.set_sim_grade(3.0)
        await wait_for(lambda: rig.trainer.grade_pct == 3.0 and rig.trainer.control, timeout=6)
        await wait_for(lambda: not rig.driver.busy)   # réponse 0x80 juste après l'écriture
        assert rig.driver.reconnect_count == reconnects
        assert rig.trainer.connections == 1 + reconnects
        assert rig.driver.att_retries == 2
        assert rig.driver.busy_deferrals == deferrals
        await rig.stop()
    asyncio.run(scenario())


@pytest.mark.parametrize("latency, refused", [(1.4, False), (2.0, True)])
def test_slow_procedure_serialises_the_next_write(monkeypatch, latency, refused):
    """Réponse plus lente que CP_RESPONSE_TIMEOUT_S : l'écriture suivante attend la réponse 0x80
    (CP_BUSY_GRACE_S de plus). Au-delà, 0xFE : le renvoi attend la réponse en cours."""
    async def scenario():
        rig = Rig(READY).start()
        await wait_for(lambda: rig.driver.status == "CONNECTED" and rig.trainer.control)
        rig.driver.set_sim_grade(1.0)
        await wait_for(lambda: rig.trainer.grade_pct == 1.0)
        replies: list[float] = []
        respond = rig.trainer._respond

        def spy(reply):
            replies.append(rig.world.now())
            respond(reply)
        monkeypatch.setattr(rig.trainer, "_respond", spy)
        rig.trainer.cp_latency_s = latency
        n = len(rig.trainer.commands)
        rig.driver.set_sim_grade(2.0)
        await wait_for(lambda: rig.trainer.grade_pct == 2.0)
        rig.trainer.cp_latency_s = 0.05
        rig.driver.set_sim_grade(3.0)   # demandée pendant la procédure lente
        await wait_for(lambda: rig.trainer.grade_pct == 3.0, timeout=4)
        cmds = rig.trainer.commands[n:]
        late_reply = replies[0]
        failed = [c for c in cmds if c.result is None]
        accepted = [c for c in cmds if c.result == 0x01]
        assert bool(failed) == refused
        assert accepted[1].t >= late_reply   # la pente 3 % part après la réponse de la pente 2 %
        assert rig.driver.reconnect_count == 0 and rig.driver.att_retries == int(refused)
        await rig.stop()
    asyncio.run(scenario())


def _grades(cmds) -> list[float]:
    return [struct.unpack_from("<h", c.payload, 3)[0] / 100.0 for c in cmds
            if c.op == ftms.OP_SET_SIM_PARAMS and c.result == 0x01]


def test_other_device_on_the_control_point_keeps_the_link(caplog):
    """Montre Garmin sur le trainer (28 octobre) : toute écriture refusée (ATT 0x80) pendant 3 s.

    Liaison gardée (jamais LOST, aucune reconnexion ni relâche), drapeau `busy` levé puis baissé,
    et seule la dernière pente demandée pendant ce temps est écrite ensuite.
    """
    async def scenario():
        rig = Rig(READY).start()
        await wait_for(lambda: rig.driver.status == "CONNECTED" and rig.trainer.control)
        rig.driver.set_sim_grade(1.0)
        await wait_for(lambda: rig.trainer.grade_pct == 1.0)
        seen: set = set()
        watcher = asyncio.create_task(_watch_status(rig.driver, seen))
        await rig.world.apply({"t": 0, "device": "trainer", "action": "other_device", "seconds": 3})
        n = len(rig.trainer.commands)
        for g in (2.0, 2.5, 3.0, 4.0):
            rig.driver.set_sim_grade(g, immediate=True)
            await asyncio.sleep(0.3)
        await wait_for(lambda: rig.driver.busy)
        await wait_for(lambda: rig.trainer.grade_pct == 4.0, timeout=8)
        await asyncio.sleep(0.2)
        watcher.cancel()
        assert seen == {"CONNECTED"}
        assert not rig.driver.busy and rig.driver.busy_deferrals >= 1
        assert rig.driver.reconnect_count == 0 and rig.trainer.connections == 1
        assert ftms.OP_RESET not in [c.op for c in rig.trainer.commands[n:]]
        assert _grades(rig.trainer.commands[n:]) == [4.0]
        await rig.stop()
    with caplog.at_level("INFO"):
        asyncio.run(scenario())
    msgs = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("Control Point occupé (ATT 0x80") for m in msgs)
    assert "Control Point de nouveau libre : consigne acceptée" in msgs
    assert not any("Reconnexion au trainer" in m for m in msgs)


def test_erg_target_survives_a_busy_control_point():
    """ERG pendant que le Control Point est occupé : pas de Reset ni de pente 0 % (la résistance
    ne tombe pas), la nouvelle cible part dès que le Control Point se libère."""
    async def scenario():
        rig = Rig(READY).start()
        await wait_for(lambda: rig.driver.status == "CONNECTED" and rig.trainer.control)
        rig.driver.set_target_power(200)
        await wait_for(lambda: rig.trainer.target_w == 200)
        await rig.world.apply({"t": 0, "device": "trainer", "action": "other_device", "seconds": 2.5})
        n = len(rig.trainer.commands)
        rig.driver.set_target_power(260)
        modes: set = set()
        end = rig.world.now() + 6
        while rig.trainer.target_w != 260:
            modes.add((rig.trainer.mode, rig.trainer.target_w))
            assert rig.world.now() < end, "cible jamais écrite"
            await asyncio.sleep(0.02)
        assert modes <= {("erg", 200.0)}   # jamais de remise à zéro entre les deux cibles
        ops = [c.op for c in rig.trainer.commands[n:] if c.result is not None]
        assert ftms.OP_RESET not in ops and ftms.OP_SET_SIM_PARAMS not in ops
        assert rig.driver.reconnect_count == 0
        await rig.stop()
    asyncio.run(scenario())


def test_burst_of_gear_changes_on_a_slow_control_point():
    """Rafale de braquets (5 « − » rapprochés) sur un Control Point occupé 0,6 s après chaque
    réponse : aucune reconnexion, et une pente écrite n'est jamais plus ancienne que la précédente."""
    async def scenario():
        spec = {**READY, "trainer": {**READY["trainer"], "busy_window_s": 0.6}}
        rig = Rig(spec).start()
        await wait_for(lambda: rig.driver.status == "CONNECTED" and rig.trainer.control)
        rig.driver.set_sim_grade(5.0)
        await wait_for(lambda: rig.trainer.grade_pct == 5.0, timeout=6)
        n = len(rig.trainer.commands)
        asked = [4.5, 4.0, 3.5, 3.0, 2.5]
        for g in asked:
            rig.driver.set_sim_grade(g, immediate=True)
            await asyncio.sleep(0.25)
        await wait_for(lambda: rig.trainer.grade_pct == 2.5, timeout=8)
        written = _grades(rig.trainer.commands[n:])
        assert written == sorted(written, reverse=True) and written[-1] == 2.5
        assert set(written) <= set(asked)
        assert rig.driver.reconnect_count == 0 and rig.trainer.connections == 1
        await rig.stop()
    asyncio.run(scenario())


def test_drop_during_write_reconnects_without_resend(monkeypatch):
    """Liaison coupée pendant l'écriture : reconnexion, pas de renvoi."""
    async def scenario():
        rig = Rig(READY).start()
        await wait_for(lambda: rig.driver.status == "CONNECTED" and rig.trainer.control)
        write = rig.trainer.write

        def dropping(uuid, data):
            if data and data[0] == ftms.OP_SET_TARGET_POWER:
                monkeypatch.setattr(rig.trainer, "write", write)
                rig.trainer.drop()
                raise ble_sim.SimBleError("Not connected")
            return write(uuid, data)
        monkeypatch.setattr(rig.trainer, "write", dropping)
        rig.driver.set_target_power(210)
        await wait_for(lambda: rig.driver.reconnect_count == 1)
        await wait_for(lambda: rig.trainer.target_w == 210, timeout=6)
        assert rig.driver.att_retries == 0
        await rig.stop()
    asyncio.run(scenario())


@pytest.mark.parametrize("message, code", [
    ("[org.bluez.Error.Failed] Operation failed with ATT error: 0x80", 0x80),
    ("[org.bluez.Error.Failed] Operation failed with ATT error: 0xfe", 0xFE),
    ("[org.bluez.Error.Failed] Operation failed with ATT error: 0xFD (Unlikely Error)", 0xFD),
    ("OPERATION FAILED WITH ATT ERROR: 0X0E", 0x0E),
    ("[org.bluez.Error.Failed] Not connected", None),
    ("", None),
])
def test_att_error_code(message, code):
    from openride_core.ftms_driver import att_error_code
    assert att_error_code(Exception(message)) == code
    assert att_error_code(asyncio.TimeoutError()) is None


def test_control_lost_is_taken_back():
    async def scenario():
        rig = Rig(READY).start()
        await wait_for(lambda: rig.driver.status == "CONNECTED" and rig.trainer.control)
        rig.driver.set_sim_grade(2.0)
        await wait_for(lambda: rig.trainer.grade_pct == 2.0)
        n = rig.ops().count(ftms.OP_REQUEST_CONTROL)
        await rig.world.apply({"t": 0, "device": "trainer", "action": "control_lost"})
        rig.driver.set_sim_grade(2.5)
        await wait_for(lambda: rig.ops().count(ftms.OP_REQUEST_CONTROL) > n)
        await wait_for(lambda: rig.trainer.grade_pct == 2.5)
        assert rig.driver.reconnect_count == 0 and not rig.driver.control_refused
        await rig.stop()
    asyncio.run(scenario())


def test_silent_control_loss_is_taken_back_after_a_refusal():
    """Contrôle retiré sans état 0xFF : la consigne suivante est refusée (0x05, vu le 22 octobre).

    Le refus arrive pendant l'écriture ; le pilote doit reprendre le contrôle au lieu de
    renvoyer la consigne jusqu'à l'erreur (défaut trouvé avec ce simulateur).
    """
    async def scenario():
        rig = Rig(READY).start()
        await wait_for(lambda: rig.driver.status == "CONNECTED" and rig.trainer.control)
        rig.driver.set_sim_grade(2.0)
        await wait_for(lambda: rig.trainer.grade_pct == 2.0)
        n = rig.ops().count(ftms.OP_REQUEST_CONTROL)
        rig.trainer.control = False
        rig.driver.set_sim_grade(3.0)
        await wait_for(lambda: rig.trainer.grade_pct == 3.0)
        assert rig.ops().count(ftms.OP_REQUEST_CONTROL) == n + 1
        await asyncio.sleep(0.3)
        assert not rig.driver.control_refused and rig.driver._refusals == 0
        await rig.stop()
    asyncio.run(scenario())


def test_refused_control_raises_the_flag():
    async def scenario():
        spec = {**READY, "trainer": {**READY["trainer"], "refuse_control": True}}
        rig = Rig(spec).start()
        rig.driver.set_sim_grade(2.0)
        await wait_for(lambda: rig.driver.control_refused, timeout=8)
        await rig.stop()
    asyncio.run(scenario())


def test_late_trainer_and_slow_connection():
    """Réveil tardif et connexion refusée une fois : RECONNECTING, puis CONNECTED."""
    async def scenario():
        spec = {**READY, "trainer": {"appear_at": 0.5, "connect_delay_s": 0.3, "connect_failures": 1}}
        rig = Rig(spec).start()
        await asyncio.sleep(0.3)
        assert rig.driver.status == "RECONNECTING"
        await wait_for(lambda: rig.driver.status == "CONNECTED", timeout=6)
        assert rig.driver.reconnect_count == 1 and rig.trainer.connections == 1
        await rig.stop()
    asyncio.run(scenario())


def test_trainer_drop_and_silence_reconnect(monkeypatch):
    import openride_core.ftms_driver as fd
    monkeypatch.setattr(fd, "FORCE_RECONNECT_S", 1.0)

    async def scenario():
        rig = Rig(READY).start()
        await wait_for(lambda: rig.driver.status == "CONNECTED")
        await rig.world.apply({"t": 0, "device": "trainer", "action": "drop"})
        await wait_for(lambda: rig.driver.status != "CONNECTED")
        await wait_for(lambda: rig.driver.status == "CONNECTED" and rig.trainer.connections == 2,
                       timeout=6)
        await rig.world.apply({"t": 0, "device": "trainer", "action": "silence", "seconds": 1.5})
        await wait_for(lambda: rig.trainer.connections == 3, timeout=6)   # « plus de données »
        await rig.stop()
    asyncio.run(scenario())


# --- Zwift Click simulé -----------------------------------------------------------------

def test_click_pair_relay_short_and_long_presses():
    async def scenario():
        rig = Rig(READY).start()
        clicks = [p for p in rig.inputs if isinstance(p, ZwiftClickProvider)]
        await wait_for(lambda: all(p.status == "CONNECTED" for p in clicks))
        await rig.world.press("+")              # relayé par le boîtier « − » : un seul événement
        await rig.world.press("-", 1.0)
        await rig.world.press("+", 0.7)         # entre court et long : sans effet, signalé
        await asyncio.sleep(0.2)
        assert rig.events() == [InputEvent.PLUS_SHORT, InputEvent.PLUS_UNCLEAR, InputEvent.MINUS_LONG]   # boîtier « + » puis « − »
        assert {p.battery_pct for p in clicks} == {80}
        await rig.stop()
    asyncio.run(scenario())


def test_sleeping_click_loses_the_waking_press():
    async def scenario():
        spec = {**READY, "click": {"asleep": True, "connect_delay_s": 0.05}}
        rig = Rig(spec).start()
        plus = rig.world.device("click_plus")
        await asyncio.sleep(0.3)
        assert plus.client is None              # endormi : ne s'annonce pas
        await rig.world.press("+")
        await wait_for(lambda: plus.client is not None, timeout=4)
        await asyncio.sleep(0.2)
        assert rig.events() == [] and plus.presses_lost == 1
        await wait_for(lambda: plus.ride_on)
        await rig.world.press("+")
        await asyncio.sleep(0.1)
        assert rig.events() == [InputEvent.PLUS_SHORT]
        await rig.stop()
    asyncio.run(scenario())


def test_click_drop_sleeps_until_pressed():
    async def scenario():
        rig = Rig(READY).start()
        minus = rig.world.device("click-")
        await wait_for(lambda: minus.client is not None and minus.ride_on)
        await rig.world.apply({"t": 0, "device": "click_minus", "action": "drop"})
        assert minus.asleep
        await asyncio.sleep(1.5)
        assert minus.client is None
        await rig.world.press("-")
        await wait_for(lambda: minus.ride_on, timeout=6)
        await rig.world.press("-")
        await asyncio.sleep(0.1)
        assert rig.events() == [InputEvent.MINUS_SHORT]
        await rig.stop()
    asyncio.run(scenario())


def test_sim_keyboard_presses_the_simulated_click():
    async def scenario():
        rig = Rig(READY).start()
        keys = next(p for p in rig.inputs if isinstance(p, SimClickKeyboard))
        await wait_for(lambda: all(b.ride_on for b in rig.world.clicks))
        keys.on_data("\x1b[5~")   # Page haut : + long, par le Click simulé
        await asyncio.sleep(1.2)
        assert rig.events() == [InputEvent.PLUS_LONG] and keys.events.empty()
        keys.on_data("z")          # Z court : bouton Z du boîtier droit simulé
        keys.on_data("\x1b[D")     # flèche gauche : boîtier gauche
        await asyncio.sleep(0.4)
        assert rig.events() == [InputEvent.Z_SHORT, InputEvent.LEFT_SHORT] and keys.events.empty()
        await rig.stop()
    asyncio.run(scenario())


def test_every_click_v2_button_and_the_control_file(tmp_path):
    """Tous les boutons du Click V2 simulé, appuyés par le fichier de commandes (banc des menus)."""
    control = tmp_path / "appuis.jsonl"

    async def scenario():
        rig = Rig({**READY, "control_file": str(control)}).start()
        await wait_for(lambda: all(b.ride_on for b in rig.world.clicks))
        with control.open("a", encoding="utf-8") as f:
            for button, duration in (("A", 1.0), ("A", 0.12), ("B", 0.12), ("Y", 1.0), ("Z", 1.0), ("UP", 0.12),
                                     ("DOWN", 0.12), ("RIGHT", 0.12), ("-", 1.0), ("bidon", 0.1), ("+", 0.12)):
                f.write(json.dumps({"action": "press", "button": button, "duration_s": duration}) + "\n")
                f.flush()
                await asyncio.sleep(duration + 0.3)
        await asyncio.sleep(0.3)
        # Boîtier droit (A, B = −, Y, Z, +) puis boîtier gauche (flèches, −), chacun dans l'ordre des appuis.
        assert rig.events() == [InputEvent.A_LONG, InputEvent.A_SHORT, InputEvent.MINUS_SHORT, InputEvent.Y_SHORT,
                                InputEvent.Z_LONG, InputEvent.PLUS_SHORT, InputEvent.UP_SHORT, InputEvent.DOWN_SHORT,
                                InputEvent.RIGHT_SHORT, InputEvent.MINUS_LONG]
        await rig.stop()
    asyncio.run(scenario())


# --- ceinture cardio ---------------------------------------------------------------------

def test_hr_strap_follows_power_and_goes_stale(monkeypatch):
    monkeypatch.setattr(hr_monitor, "STALE_S", 1.5)

    async def scenario():
        rig = Rig(READY).start()
        await wait_for(lambda: rig.hr.bpm is not None, timeout=4)
        rest = rig.hr.bpm
        rig.driver.set_target_power(300)
        await wait_for(lambda: rig.hr.bpm > rest + 20, timeout=8)
        await rig.world.apply({"t": 0, "device": "hr", "action": "sleep"})
        await rig.world.apply({"t": 0, "device": "hr", "action": "drop"})
        await wait_for(lambda: rig.hr.bpm is None, timeout=4)
        await rig.stop()
    asyncio.run(scenario())


def test_find_device_by_service(monkeypatch):
    from test_ble_util import FakeAdv, FakeDevice, install_fake_bleak

    class Adv(FakeAdv):
        def __init__(self, uuids):
            super().__init__(None)
            self.service_uuids = uuids

    strap = FakeDevice("AA:BB:CC:DD:EE:01", "Polar H10 1234")
    other = FakeDevice("AA:BB:CC:DD:EE:02", "HomeTrainer 0000")
    install_fake_bleak(monkeypatch, candidates=[(other, Adv([ftms.FTMS_SERVICE])),
                                                (strap, Adv([ftms.HR_SERVICE]))])
    found = asyncio.run(ble_util.find_device("", None, 1.0, service=ftms.HR_SERVICE))
    assert found is strap
    assert asyncio.run(ble_util.find_device("HomeTrainer", None, 1.0)) is other


# --- scénarios ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_builtin_scenarios_build(name):
    world = build_world(load_scenario(name))
    assert world.trainer and len(world.clicks) == 2 and world.hr
    assert all(ev["action"] in {"press"} or ev.get("device") for ev in world.events)


@pytest.mark.parametrize("spec, message", [
    ({"trainer": {"puissance": 3}}, "clé(s) inconnue(s) puissance"),
    ({"events": [{"t": 1, "action": "exploser"}]}, "action 'exploser' inconnue"),
    ({"events": [{"action": "drop"}]}, "« t » et « action »"),
    ({"events": [{"t": 1, "action": "silence"}]}, "« seconds » obligatoire"),
    ({"events": [{"t": -1, "action": "drop"}]}, "doit être positif"),
    ({"click": {"plus": {"name": "x"}}}, "click.plus"),
])
def test_scenario_validation(spec, message):
    with pytest.raises(SimScenarioError, match=re.escape(message)):
        validate(spec)


def test_scenario_from_json_file(tmp_path):
    path = tmp_path / "mon_scenario.json"
    path.write_text(json.dumps({"trainer": {}, "rider": {"watts": 150},
                                "events": [{"t": 2, "device": "trainer", "action": "att_error"}]}))
    world = build_world(load_scenario(str(path)))
    assert world.trainer.rider.watts == 150 and not world.clicks and world.hr is None
    assert len(world.events) == 1
    with pytest.raises(SimScenarioError, match="inconnu"):
        load_scenario(str(tmp_path / "absent.json"))


def test_scenario_events_play_in_order():
    async def scenario():
        spec = {**READY, "events": [{"t": 0.2, "device": "trainer", "action": "rider", "watts": 90},
                                    {"t": 0.1, "device": "hr", "action": "bpm", "bpm": 150}]}
        world = build_world(spec)
        task = asyncio.create_task(world.run())
        await asyncio.sleep(0.15)
        assert world.hr.fixed_bpm == 150 and world.trainer.rider.watts == 180
        await asyncio.sleep(0.15)
        assert world.trainer.rider.watts == 90
        world.stop()
        await asyncio.wait_for(task, 1)
    asyncio.run(scenario())


# --- configuration, ligne de commande et séance complète ------------------------------------

def test_config_accepts_sim_choices():
    cfg = from_dict({"drivers": {"trainer": "sim", "input": "sim", "hr": "sim",
                                 "sim_scenario": "coupures"}})
    assert (cfg.drivers.trainer, cfg.drivers.input, cfg.drivers.hr) == ("sim", "sim", "sim")
    with pytest.raises(ConfigError, match="hr"):
        from_dict({"drivers": {"hr": "montre"}})
    assert build_sim_world(Config()) is None   # mock + clavier : pas de Bluetooth simulé


def test_cli_sim_options(capsys):
    args = build_parser().parse_args(["run", "--trainer", "sim", "--input", "sim", "--hr", "sim",
                                      "--sim-scenario", "erreur_0x80"])
    assert (args.trainer, args.input, args.hr, args.sim_scenario) == ("sim", "sim", "sim", "erreur_0x80")
    assert main(["run", "--trainer", "sim", "--sim-scenario", "inexistant"]) == 1
    assert "scénario de simulation refusé" in capsys.readouterr().err


def test_full_session_without_hardware(tmp_path, monkeypatch):
    """Séance complète : trainer, Click et ceinture simulés, braquets, FC, puis relâche."""
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    spec = {**READY, "events": [{"t": 1.2, "action": "press", "button": "+"},
                                {"t": 1.6, "action": "press", "button": "+"},
                                {"t": 2.0, "action": "press", "button": "-", "duration_s": 1.0}]}
    monkeypatch.setitem(SCENARIOS, "test_complet", spec)
    cfg = sim_config("test_complet")
    cfg.ipc.port_state, cfg.ipc.port_commands = 5790, 5791

    async def scenario():
        s = CoreSession(cfg, journal_dir=tmp_path / "journal", routes_root=tmp_path / "routes")
        assert isinstance(s.driver, FtmsDriver) and s.sim is not None
        k0 = s.gearing.k
        task = asyncio.create_task(s.run(autostart=True))
        await wait_for(lambda: s.state.session_state == "RUNNING" and s.state.trainer_status == "CONNECTED")
        await wait_for(lambda: s.state.gear == k0 + 2, timeout=4)
        await wait_for(lambda: s.state.gear < k0, timeout=4)   # appui long : 10 braquets plus bas
        await wait_for(lambda: s.state.hr is not None and s.state.input_status == "CONNECTED")
        assert s.state.s > 0 and s.sim.trainer.mode == "sim"
        s.stop_event.set()
        await asyncio.wait_for(task, 10)
        assert s.sim.trainer.released and s.sim.trainer.client is None
        assert list((tmp_path / "act").glob("*.fit"))
    asyncio.run(scenario())


@pytest.mark.slow
def test_erreur_0x80_scenario_full_session(tmp_path, monkeypatch, caplog):
    """Scénario `erreur_0x80` en séance complète : aucun ERROR, une seule connexion du trainer (M1)."""
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    cfg = sim_config("erreur_0x80")
    cfg.ipc.port_state, cfg.ipc.port_commands = 5792, 5793

    async def scenario():
        s = CoreSession(cfg, journal_dir=tmp_path / "journal", routes_root=tmp_path / "routes")
        task = asyncio.create_task(s.run(autostart=True))
        await wait_for(lambda: s.driver.att_retries == 1, timeout=30)
        await asyncio.sleep(1.0)
        assert s.state.session_state == "RUNNING" and s.state.trainer_status == "CONNECTED"
        s.stop_event.set()
        await asyncio.wait_for(task, 10)
        assert s.sim.trainer.connections == 1 and s.driver.reconnect_count == 0
        assert s.sim.trainer.released
    with caplog.at_level("INFO"):
        asyncio.run(scenario())
    assert not [r for r in caplog.records if r.levelname == "ERROR"]


@pytest.mark.parametrize("recovers", [True, False])
def test_brake_loss_is_detected_and_control_retaken(caplog, recovers):
    """Frein coupé par le trainer sans erreur (29 octobre) : détection, nouvelle prise de contrôle, une seule fois."""
    async def scenario():
        spec = {**READY, "rider": {"watts": 320, "cadence_rpm": 80}}
        rig = Rig(spec).start()
        await wait_for(lambda: rig.driver.status == "CONNECTED" and rig.trainer.control)
        rig.driver.set_sim_grade(2.0)
        await wait_for(lambda: rig.trainer.grade_pct == 2.0 and rig.driver._raw_power > 250, timeout=8)
        n = rig.ops().count(ftms.OP_REQUEST_CONTROL)
        await rig.world.apply({"t": 0, "device": "trainer", "action": "brake_loss", "seconds": 2.5,
                               "value": recovers})
        await wait_for(lambda: rig.driver.brake_losses == 1, timeout=6)
        await wait_for(lambda: rig.ops().count(ftms.OP_REQUEST_CONTROL) > n)   # contrôle repris
        if recovers:
            await wait_for(lambda: rig.driver._raw_power > 250, timeout=6)
            assert rig.driver._brake_lost_at is None
        else:
            await asyncio.sleep(0.8)
            assert rig.driver._raw_power < 10
        assert rig.driver.brake_losses == 1 and rig.driver.reconnect_count == 0
        await rig.stop()
    with caplog.at_level("INFO"):
        asyncio.run(scenario())
    msgs = [r.getMessage() for r in caplog.records]
    assert sum("Trainer : le frein a lâché" in m for m in msgs) == 1
    assert any("puissance revenue" in m for m in msgs) == recovers
