"""Tests du lot Q3 : journal des commandes FTMS et des accusés du trainer."""

from __future__ import annotations

import asyncio
import io
import logging
import re
import pytest

from openride_core import ble_sim, ftms
from openride_core.__main__ import build_parser, cmd_run
from openride_core.config import BikeConfig, Config, ConfigError, TrainerConfig, from_dict
from openride_core.ftms_driver import ControlPoint, FtmsDriver, OP_NAMES, format_cp_write
from openride_core.tools import log_report
from openride_core.sim_scenarios import build_world


READY = {
    "trainer": {"appear_at": 0.0, "connect_delay_s": 0.02, "cp_latency_s": 0.05},
    "click": {"appear_at": 0.0, "connect_delay_s": 0.02},
    "hr": {"appear_at": 0.0, "connect_delay_s": 0.02},
}


# --- 1. Validation de la configuration et CLI -------------------------------------------

def test_config_trace_ftms_defaults_and_validation():
    cfg = Config()
    assert cfg.trainer.trace_ftms is False

    # Validation TOML
    loaded = from_dict({"trainer": {"trace_ftms": True}})
    assert loaded.trainer.trace_ftms is True

    with pytest.raises(ConfigError, match="booléen attendu"):
        from_dict({"trainer": {"trace_ftms": "oui"}})

    with pytest.raises(ConfigError, match="booléen attendu"):
        from_dict({"trainer": {"trace_ftms": 1}})


def test_cli_trace_ftms_option():
    parser = build_parser()
    args = parser.parse_args(["run", "--trace-ftms"])
    assert args.trace_ftms is True

    args_no = parser.parse_args(["run"])
    assert args_no.trace_ftms is False


# --- 2. Formatage des trames Control Point -----------------------------------------------

def test_format_cp_write_sim_payload():
    # Exemple cité dans le cahier LOT_Q3 : SIM pente 3.20 % crr 0.0040 cw 0.39 (11 0000 4001 28 27)
    payload = bytes.fromhex("11 0000 4001 28 27")
    op_name, vals, hex_str = format_cp_write(payload)
    assert op_name == "SIM"
    assert vals == "pente 3.20 % crr 0.0040 cw 0.390"
    assert hex_str == "11 0000 4001 28 27"


def test_format_cp_write_erg_and_control():
    payload_erg = ftms.cmd_set_target_power(200)
    op, vals, hex_str = format_cp_write(payload_erg)
    assert op == "ERG"
    assert vals == "cible 200 W"
    assert hex_str == "05 c800"

    assert format_cp_write(ftms.cmd_request_control()) == ("REQUEST_CONTROL", "", "00")
    assert format_cp_write(ftms.cmd_reset()) == ("RESET", "", "01")
    assert format_cp_write(ftms.cmd_start_resume()) == ("START_RESUME", "", "07")


# --- 3. Trace désactivée (Critère 2) ----------------------------------------------------

def test_trace_disabled_produces_no_ftms_trace_lines(caplog):
    async def scenario():
        world = build_world(READY, hr=False, click=False)
        cfg = TrainerConfig(trace_ftms=False, latency_tau_s=0.0)
        drv = FtmsDriver(
            cfg,
            BikeConfig(),
            device_finder=world.find_device,
            client_factory=world.client_factory,
        )
        task = asyncio.create_task(drv.run())
        try:
            with caplog.at_level(logging.INFO):
                for _ in range(50):
                    if drv.status == "CONNECTED":
                        break
                    await asyncio.sleep(0.02)
                assert drv.status == "CONNECTED"

                drv.set_sim_grade(4.0, immediate=True)
                await asyncio.sleep(0.15)
        finally:
            drv.stop()
            await task

        ftms_lines = [rec.message for rec in caplog.records if rec.message.startswith("FTMS")]
        assert len(ftms_lines) == 0, f"Lignes de trace FTMS inattendues : {ftms_lines}"

    asyncio.run(scenario())


# --- 4. Trace active et latence mesurée (Critère 3) --------------------------------------

def test_trace_active_with_simulated_trainer(caplog):
    async def scenario():
        world = build_world(READY, hr=False, click=False)
        # cp_latency_s = 0.05 -> réponse en ~50 ms
        cfg = TrainerConfig(trace_ftms=True, latency_tau_s=0.0)
        drv = FtmsDriver(
            cfg,
            BikeConfig(),
            device_finder=world.find_device,
            client_factory=world.client_factory,
        )
        task = asyncio.create_task(drv.run())
        try:
            with caplog.at_level(logging.INFO):
                for _ in range(50):
                    if drv.status == "CONNECTED":
                        break
                    await asyncio.sleep(0.02)
                assert drv.status == "CONNECTED"

                # Envoi d'une consigne SIM
                drv.set_sim_grade(3.5, immediate=True)
                for _ in range(50):
                    if any("FTMS > SIM" in r.message for r in caplog.records):
                        break
                    await asyncio.sleep(0.02)
                await asyncio.sleep(0.15)
        finally:
            drv.stop()
            await task

        lines = [rec.message for rec in caplog.records if rec.message.startswith("FTMS")]
        assert any(ln.startswith("FTMS > REQUEST_CONTROL") for ln in lines)
        assert any(ln.startswith("FTMS > START_RESUME") for ln in lines)
        assert any(ln.startswith("FTMS > SIM") for ln in lines)

        # Vérification des réponses et des délais (~50 ms ± 20 ms)
        responses = [ln for ln in lines if ln.startswith("FTMS < réponse")]
        assert len(responses) >= 3
        for resp in responses:
            m = re.search(r"en (\d+) ms", resp)
            assert m is not None, f"Délai manquant dans {resp}"
            delay = int(m.group(1))
            assert 30 <= delay <= 120, f"Délai {delay} ms incohérent avec latence 50 ms"

    asyncio.run(scenario())


def test_trace_timeout_reported(caplog):
    """Expiration du Control Point signalée dans la trace."""
    async def scenario():
        world = build_world(READY, hr=False, click=False)
        trainer = world.trainer
        assert trainer is not None

        async with world.client_factory(await world.find_device("HomeTrainer", None, 1.0)) as client:
            cp = ControlPoint(client, trace=True)
            await cp.enable()

            # Prise de contrôle préalable
            await cp.call(ftms.cmd_request_control())

            # Prochaine réponse silencieuse (drop de l'indication)
            trainer.pending_silent_responses = 1

            with caplog.at_level(logging.INFO):
                # Écriture qui expire
                res = await cp.call(ftms.cmd_set_target_power(200))
                assert res is None

            timeouts = [rec.message for rec in caplog.records if "FTMS < sans réponse" in rec.message]
            assert len(timeouts) == 1
            m = re.search(r"après (\d+) ms", timeouts[0])
            assert m is not None
            assert 950 <= int(m.group(1)) <= 1150

    asyncio.run(scenario())


# --- 5. Reset tiers vs écho d'OpenRide (Critère 4) ---------------------------------------

def test_reset_third_party_vs_echo(caplog):
    async def scenario():
        world = build_world(READY, hr=False, click=False)
        trainer = world.trainer
        assert trainer is not None
        cfg = TrainerConfig(trace_ftms=True)
        drv = FtmsDriver(
            cfg,
            BikeConfig(),
            device_finder=world.find_device,
            client_factory=world.client_factory,
        )
        task = asyncio.create_task(drv.run())
        try:
            for _ in range(50):
                if drv.status == "CONNECTED" and drv._cp is not None:
                    break
                await asyncio.sleep(0.02)
            assert drv._cp is not None

            with caplog.at_level(logging.INFO):
                # 1. Reset envoyé par un tiers
                trainer.notify(ftms.MACHINE_STATUS, bytes([0x01]))
                await asyncio.sleep(0.05)

                # 2. Reset envoyé par OpenRide, suivi d'un statut RESET en écho
                await drv._call_retrying(drv._cp, ftms.cmd_reset)
                trainer.notify(ftms.MACHINE_STATUS, bytes([0x01]))
                await asyncio.sleep(0.05)
        finally:
            drv.stop()
            await task

        status_lines = [rec.message for rec in caplog.records if "FTMS < statut RESET" in rec.message]
        assert len(status_lines) == 2
        assert "par un tiers" in status_lines[0]
        assert "écho probable de notre commande" in status_lines[1]

    asyncio.run(scenario())


# --- 6. Analyse log_report (Critère 5) ---------------------------------------------------

def test_log_report_ftms_section():
    sample_log = [
        "2026-10-25 10:00:00,000 INFO    core    Core démarré (trainer=sim, entrées=sim).",
        "2026-10-25 10:00:00,050 INFO    ftms_driver FTMS > REQUEST_CONTROL (00)",
        "2026-10-25 10:00:00,100 INFO    ftms_driver FTMS < réponse REQUEST_CONTROL SUCCESS en 50 ms",
        "2026-10-25 10:00:00,150 INFO    ftms_driver FTMS > START_RESUME (07)",
        "2026-10-25 10:00:00,200 INFO    ftms_driver FTMS < réponse START_RESUME SUCCESS en 40 ms",
        "2026-10-25 10:00:01,000 INFO    ftms_driver FTMS > SIM pente 3.20 % crr 0.0040 cw 0.196 (11 0000 4001 28 c4)",
        "2026-10-25 10:00:01,060 INFO    ftms_driver FTMS < réponse SIM SUCCESS en 60 ms",
        "2026-10-25 10:00:02,000 INFO    ftms_driver FTMS > SIM pente 4.00 % crr 0.0040 cw 0.196 (11 0000 9001 28 c4)",
        "2026-10-25 10:00:03,000 INFO    ftms_driver FTMS < sans réponse après 1000 ms",
        "2026-10-25 10:00:03,050 INFO    ftms_driver FTMS < statut RESET (par un tiers)",
        "2026-10-25 10:00:04,000 INFO    ftms_driver FTMS > RESET (01)",
        "2026-10-25 10:00:04,050 INFO    ftms_driver FTMS < réponse RESET SUCCESS en 50 ms",
        "2026-10-25 10:00:04,060 INFO    ftms_driver FTMS < statut RESET (écho probable de notre commande)",
        "2026-10-25 10:00:05,000 INFO    core    Arrêt du core…",
    ]

    rep = log_report.analyse(sample_log)
    f = rep.ftms
    assert f.has_trace is True
    assert f.total_writes == 5
    assert f.writes == {"REQUEST_CONTROL": 1, "START_RESUME": 1, "SIM": 2, "RESET": 1}
    assert f.timeouts == 1
    assert f.third_party_statuses == 1
    assert f.echo_statuses == 1

    # Délais : 50, 40, 60, 50 -> médiane 50.0, max 60.0
    assert f.delays_ms == [50.0, 40.0, 60.0, 50.0]
    assert f.delay_median_ms == 50.0
    assert f.delay_max_ms == 60.0
    assert f.delay_p95_ms is not None

    formatted = log_report.format_report(rep)
    assert "Commandes FTMS : 5 écriture(s)" in formatted
    assert "délai écriture → accusé : médiane 50.0 ms" in formatted
    assert "1 expiration(s)" in formatted
    assert "statuts : 1 par un tiers, 1 écho(s) probable(s)" in formatted


def test_log_report_absent_without_trace():
    sample_clean = [
        "2026-10-25 10:00:00,000 INFO    core    Core démarré (trainer=sim, entrées=sim).",
        "2026-10-25 10:00:05,000 INFO    core    Arrêt du core…",
    ]
    rep = log_report.analyse(sample_clean)
    assert rep.ftms.has_trace is False
    formatted = log_report.format_report(rep)
    assert "Commandes FTMS" not in formatted


# --- 7. Cadence et coût de journalisation (Critère 6) -----------------------------------

def test_trace_rate_limit_under_3_lines_per_second(caplog):
    """Vérifie que la cadence des lignes FTMS reste bornée : 2 lignes/s de commandes au plus, plus la
    ligne de mesures (une par notification Indoor Bike Data, soit environ 1 par seconde)."""
    async def scenario():
        world = build_world(READY, hr=False, click=False)
        cfg = TrainerConfig(trace_ftms=True)
        drv = FtmsDriver(
            cfg,
            BikeConfig(),
            device_finder=world.find_device,
            client_factory=world.client_factory,
        )
        task = asyncio.create_task(drv.run())
        try:
            for _ in range(50):
                if drv.status == "CONNECTED":
                    break
                await asyncio.sleep(0.02)

            # Laisser la prise de contrôle initiale et la première commande se terminer
            drv.set_sim_grade(2.0, immediate=True)
            await asyncio.sleep(0.5)

            with caplog.at_level(logging.INFO):
                idx_start = len(caplog.records)
                t_start = asyncio.get_running_loop().time()
                # Simulation de séance en régime établi pendant 4 s (pente stable)
                for i in range(40):
                    drv.set_sim_grade(2.0)
                    drv.poll(t_start + i * 0.1)
                    await asyncio.sleep(0.1)
                duration = asyncio.get_running_loop().time() - t_start
                idx_end = len(caplog.records)
        finally:
            drv.stop()
            await task

        steady_records = caplog.records[idx_start:idx_end]
        ftms_lines = [rec.message for rec in steady_records if rec.message.startswith("FTMS")]
        rate = len(ftms_lines) / duration
        assert rate <= 3.0, f"Cadence trop élevée : {rate:.2f} lignes/s ({len(ftms_lines)} lignes en {duration:.2f} s)"

    asyncio.run(scenario())


# --- 5. Mesures annoncées par le trainer (décrochage du 29 octobre) ---------------------------

def _ibd(speed_kmh: float, cadence_rpm: float, power_w: int, resistance: int | None = None) -> bytes:
    import struct
    flags = 0x0004 | 0x0040 | (0x0020 if resistance is not None else 0)
    out = struct.pack("<HH", flags, round(speed_kmh * 100)) + struct.pack("<H", round(cadence_rpm * 2))
    if resistance is not None:
        out += struct.pack("<h", resistance)
    return out + struct.pack("<h", power_w)


@pytest.mark.parametrize("trace, lines", [(True, 3), (False, 0)])
def test_trace_logs_trainer_measures_each_notification(caplog, trace, lines):
    """Avec trace_ftms : vitesse et niveau de résistance du trainer à côté de la consigne, une ligne par notification, 0,9 s d'écart au moins."""
    now = [100.0]
    drv = FtmsDriver(TrainerConfig(trace_ftms=trace), BikeConfig(), clock=lambda: now[0])
    drv._last_sent = ("sim", 0.68)
    with caplog.at_level(logging.INFO, logger="ftms_driver"):
        for t, power, level in [(0.0, 318, 40), (0.3, 300, 40), (1.0, 120, 38), (1.2, 100, 30), (2.0, 27, 12)]:
            now[0] = 100.0 + t
            drv._on_ibd(None, bytearray(_ibd(24.8, 73, power, level)))
    got = [r.getMessage() for r in caplog.records if r.getMessage().startswith("FTMS ~ mesures")]
    assert len(got) == lines
    if trace:
        assert "puissance 318 W" in got[0] and "niveau de résistance 40" in got[0]
        assert "vitesse du trainer 24.8 km/h" in got[0] and "consigne envoyée pente 0.68 %" in got[0]
        assert "puissance 120 W" in got[1] and "puissance 27 W" in got[2] and "niveau de résistance 12" in got[2]


# --- 6. Frein lâché par le trainer (29 octobre) -------------------------------------------------

def _drive(drv, now, frames):
    for t, power, rpm in frames:
        now[0] = 100.0 + t
        drv._on_ibd(None, bytearray(_ibd(30.0, rpm, power)))


def test_brake_loss_is_detected_and_control_taken_again(caplog):
    """449 W puis 0 W à cadence constante (20:21:35) : avertissement, consigne oubliée pour reprise du contrôle."""
    now = [100.0]
    drv = FtmsDriver(TrainerConfig(), BikeConfig(), clock=lambda: now[0])
    drv.set_sim_grade(2.8)
    drv._last_sent = ("sim", 2.8)
    with caplog.at_level(logging.INFO, logger="ftms_driver"):
        _drive(drv, now, [(0.0, 449, 73), (2.0, 449, 73), (4.0, 0, 73), (6.0, 0, 0)])
    msgs = [r.getMessage() for r in caplog.records]
    assert drv.brake_losses == 1 and drv._last_sent is None
    assert sum("le frein a lâché (449 W puis 0 W à 73 tr/min, volant 30 km/h)" in m for m in msgs) == 1

    with caplog.at_level(logging.INFO, logger="ftms_driver"):
        _drive(drv, now, [(7.0, 320, 70)])
    assert any(m.startswith("Trainer : puissance revenue (320 W) 3.0 s") for m in
               (r.getMessage() for r in caplog.records))


@pytest.mark.parametrize("frames, mode_value, why", [
    ([(0.0, 449, 73), (5.0, 0, 73)], ("sim", 2.8), "chute trop lente (plus de 3 s)"),
    ([(0.0, 150, 73), (2.0, 0, 73)], ("sim", 2.8), "pas de charge avant la chute"),
    ([(0.0, 449, 73), (2.0, 0, 20)], ("sim", 2.8), "cycliste qui a cessé de pédaler"),
    ([(0.0, 300, 80), (2.0, 0, 80)], ("erg", 0.0), "repos d'un bloc ERG à 0 W"),
])
def test_no_brake_loss_when_the_rider_or_the_workout_explains_it(frames, mode_value, why):
    now = [100.0]
    drv = FtmsDriver(TrainerConfig(), BikeConfig(), clock=lambda: now[0])
    if mode_value[0] == "erg":
        drv.set_target_power(mode_value[1])
    else:
        drv.set_sim_grade(mode_value[1])
    _drive(drv, now, frames)
    assert drv.brake_losses == 0, why


def test_brake_loss_retried_at_most_every_ten_seconds():
    now = [100.0]
    drv = FtmsDriver(TrainerConfig(), BikeConfig(), clock=lambda: now[0])
    drv.set_sim_grade(1.0)
    _drive(drv, now, [(0.0, 400, 80), (1.0, 0, 80), (2.0, 400, 80), (3.0, 0, 80), (12.0, 400, 80), (13.0, 0, 80)])
    assert drv.brake_losses == 2   # 1 s et 13 s : jamais deux fois en moins de 10 s


# --- 7. Spin Down Status et statuts à paramètres (hypothèse du 29 octobre) -------------------------

def test_spin_down_status_is_logged_even_without_trace(caplog):
    drv = FtmsDriver(TrainerConfig(trace_ftms=False), BikeConfig())
    with caplog.at_level(logging.INFO, logger="ftms_driver"):
        drv._on_status(None, bytearray([0x14, 0x01]))
    assert any("Spin Down Status" in r.getMessage() and "01" in r.getMessage() for r in caplog.records)


def test_status_parameters_are_traced(caplog):
    drv = FtmsDriver(TrainerConfig(trace_ftms=True), BikeConfig())
    with caplog.at_level(logging.INFO, logger="ftms_driver"):
        drv._on_status(None, bytearray([0x02, 0x01]))
    assert any("octets 01" in r.getMessage() for r in caplog.records)


# --- 8. Lignes `ftms` du journal JSONL ------------------------------------------------------------

def test_ftms_events_reach_the_journal_sink():
    now = [100.0]
    drv = FtmsDriver(TrainerConfig(trace_ftms=False), BikeConfig(), clock=lambda: now[0])
    got: list[dict] = []
    drv.event_sink = got.append
    drv._on_status(None, bytearray([0x14, 0x02]))
    drv._on_training_status(None, bytearray([0x00, 0x0d]))
    _drive(drv, now, [(0, 450, 80), (1, 440, 80), (2, 5, 80)])
    drv.set_sim_grade(2.0)
    kinds = [(g["event"], g.get("code"), g.get("data")) for g in got]
    assert ("status", "0x14", "02") in kinds and ("training_status", None, "000d") in kinds
    loss = next(g for g in got if g["event"] == "brake_loss")
    assert loss["kind"] == "ftms" and loss["from_w"] == 440 and loss["to_w"] == 5 and loss["cadence_rpm"] == 80


def test_ftms_line_is_written_by_the_recorder(tmp_path):
    from openride_core.recorder import SessionRecorder
    from openride_core.journal import read_journal
    rec = SessionRecorder(tmp_path, "r")
    rec.event("start", 1.0)
    rec.ftms({"ts": 2.0, "event": "brake_loss", "from_w": 450, "to_w": 5, "cadence_rpm": 80, "speed_kmh": 36.0})
    lines = list(read_journal(rec.path))
    assert [ln["kind"] for ln in lines] == ["header", "event", "ftms"]
    assert rec.events == [lines[1]] and lines[2]["event"] == "brake_loss"


# --- 8. Frein d'élan : volant en avance sur les pédales après une relance (30 octobre) ------------

def _sent_grade(drv) -> float:
    """Pente de la prochaine écriture SIM (consigne + frein d'élan), comme dans _flush_command."""
    return min(drv._want.value + drv._momentum_boost(), drv.cfg.grade_max_pct)


def test_momentum_brake_raises_the_grade_until_the_pedals_catch_up(caplog):
    """Sprint 600 W puis 150 W, volant à 30 km/h : +3 % jusqu'à ce que la puissance remonte à 60 % de la pointe."""
    now = [100.0]
    drv = FtmsDriver(TrainerConfig(), BikeConfig(), clock=lambda: now[0])
    got = []
    drv.event_sink = got.append
    drv.set_sim_grade(0.5)
    with caplog.at_level(logging.INFO, logger="ftms_driver"):
        _drive(drv, now, [(0.0, 600, 95), (0.5, 580, 95), (1.0, 150, 90)])
        assert drv.momentum_brakes == 1 and drv._immediate
        assert _sent_grade(drv) == pytest.approx(3.5)
        _drive(drv, now, [(1.5, 200, 85), (2.0, 380, 85)])
    assert _sent_grade(drv) == pytest.approx(0.5) and drv._immediate
    msgs = [r.getMessage() for r in caplog.records]
    assert any("frein d'élan n° 1 (600 W puis 150 W, volant 30 km/h) : pente +3.0 %" in m for m in msgs)
    assert any(m.startswith("Trainer : frein d'élan relâché après 1.0 s (puissance revenue, 380 W)") for m in msgs)
    assert [g["event"] for g in got] == ["momentum_brake", "momentum_end"]
    assert got[0]["from_w"] == 600 and got[0]["boost_pct"] == 3.0 and got[1]["why"] == "puissance revenue"


def test_momentum_brake_is_bounded_in_time_and_rate():
    """Tenu jusqu'à 6 s sans reprise (phase à 0 W de 5–6 s, essai 7bk), puis pas de nouvelle intervention avant 5 s."""
    now = [100.0]
    drv = FtmsDriver(TrainerConfig(), BikeConfig(), clock=lambda: now[0])
    drv.set_sim_grade(1.0)
    _drive(drv, now, [(0.0, 500, 90), (1.0, 100, 80), (2.0, 100, 80), (4.0, 0, 80), (6.5, 0, 70)])
    assert drv.momentum_brakes == 1 and _sent_grade(drv) == pytest.approx(4.0)   # encore tenu à 5,5 s
    _drive(drv, now, [(7.0, 0, 70)])
    assert _sent_grade(drv) == pytest.approx(1.0)   # relâché à 6 s
    _drive(drv, now, [(8.0, 500, 90), (9.0, 100, 80)])
    assert drv.momentum_brakes == 1   # 2 s après le relâchement
    _drive(drv, now, [(12.5, 500, 90), (13.0, 100, 80)])
    assert drv.momentum_brakes == 2


@pytest.mark.parametrize("hold_s", [4.0, 8.0])
def test_momentum_brake_hold_time_is_configurable(hold_s):
    """[trainer] momentum_brake_s : grille de passes 4, 6 et 8 s (fil de fusion, 31 octobre)."""
    now = [100.0]
    drv = FtmsDriver(TrainerConfig(momentum_brake_pct=6.0, momentum_brake_s=hold_s), BikeConfig(), clock=lambda: now[0])
    drv.set_sim_grade(0.5)
    _drive(drv, now, [(0.0, 600, 95), (1.0, 100, 90), (1.0 + hold_s - 0.2, 0, 0)])
    assert _sent_grade(drv) == pytest.approx(6.5)
    _drive(drv, now, [(1.0 + hold_s, 0, 0)])
    assert _sent_grade(drv) == pytest.approx(0.5)


def test_momentum_brake_ignores_an_isolated_zero_cadence(caplog):
    """7bk 12:25:07 : cadence lue à 0 1,7 s après le déclenchement, 60–99 tr/min ensuite ; le volant
    tourne encore à 34 km/h : le frein reste tenu (avant : relâché sur « pédalage arrêté »)."""
    now = [100.0]
    drv = FtmsDriver(TrainerConfig(), BikeConfig(), clock=lambda: now[0])
    drv.set_sim_grade(0.5)
    with caplog.at_level(logging.INFO, logger="ftms_driver"):
        _drive(drv, now, [(0.0, 546, 99), (1.0, 140, 95), (2.7, 0, 0), (3.7, 0, 0), (4.7, 20, 75), (5.7, 30, 90)])
    assert drv.momentum_brakes == 1 and _sent_grade(drv) == pytest.approx(3.5)
    assert not any("pédalage arrêté" in r.getMessage() for r in caplog.records)


def test_momentum_brake_released_when_the_flywheel_slows_down():
    """Le volant passe sous 20 km/h : pédalage arrêté, même si la cadence lue reste haute."""
    now = [100.0]
    got = []
    drv = FtmsDriver(TrainerConfig(), BikeConfig(), clock=lambda: now[0])
    drv.event_sink = got.append
    drv.set_sim_grade(0.5)
    for t, speed, rpm, power in [(0.0, 34.0, 99, 600), (1.0, 30.0, 90, 100), (2.0, 19.0, 90, 50)]:
        now[0] = 100.0 + t
        drv._on_ibd(None, bytearray(_ibd(speed, rpm, power)))
    assert _sent_grade(drv) == pytest.approx(0.5)
    assert got[-1]["event"] == "momentum_end" and got[-1]["why"] == "pédalage arrêté"


def test_momentum_brake_without_flywheel_speed_needs_a_lasting_low_cadence():
    """Trainer sans vitesse du volant : cadence basse plus de 2 s = pédalage arrêté, un 0 isolé ne suffit pas."""
    now = [100.0]
    drv = FtmsDriver(TrainerConfig(), BikeConfig(), clock=lambda: now[0])
    drv.set_sim_grade(0.5)

    def frame(t, power, rpm):
        now[0] = 100.0 + t
        drv._trainer_speed_kmh, drv._cadence = None, rpm
        drv._check_momentum(now[0], power)
    for t, power, rpm in [(0.0, 600, 95), (1.0, 100, 90), (2.0, 0, 0), (3.0, 20, 80), (4.0, 0, 0), (5.5, 0, 0)]:
        frame(t, power, rpm)
    assert drv.momentum_brakes == 1 and drv._momentum_at is not None   # 0 depuis 1,5 s seulement
    frame(6.1, 0, 0)
    assert drv._momentum_at is None


@pytest.mark.parametrize("pct, text", [
    (3.0, "Trainer : momentum_brakes = 2 (frein d'élan +3.0 %, tenu 6 s au plus)."),
    (0.0, "Trainer : momentum_brakes = 0 (frein d'élan coupé, momentum_brake_pct = 0)."),
])
def test_momentum_counter_line_is_written_to_core_log(caplog, pct, text):
    """Ligne compteur à la fin de la séance, même à 0 (7bk : aucune ligne momentum_brakes dans core.log)."""
    drv = FtmsDriver(TrainerConfig(momentum_brake_pct=pct), BikeConfig())
    drv.momentum_brakes = 2 if pct else 0
    drv._stop.set()
    with caplog.at_level(logging.INFO, logger="ftms_driver"):
        asyncio.run(drv.run())
    assert text in [r.getMessage() for r in caplog.records]


def test_momentum_brake_respects_the_grade_ceiling():
    now = [100.0]
    drv = FtmsDriver(TrainerConfig(grade_max_pct=10.0), BikeConfig(), clock=lambda: now[0])
    drv.set_sim_grade(9.0)
    _drive(drv, now, [(0.0, 500, 90), (1.0, 100, 80)])
    assert _sent_grade(drv) == pytest.approx(10.0)


@pytest.mark.parametrize("cfg, mode, frames, why", [
    (TrainerConfig(momentum_brake_pct=0.0), "sim", [(0.0, 600, 95), (1.0, 100, 90)], "réglage coupé"),
    (TrainerConfig(), "erg", [(0.0, 600, 95), (1.0, 100, 90)], "ERG : le trainer tient la puissance"),
    (TrainerConfig(), "sim", [(0.0, 200, 80), (1.0, 50, 80)], "pas de relance avant"),
    (TrainerConfig(), "sim", [(0.0, 600, 95), (1.0, 300, 90)], "baisse modérée"),
    (TrainerConfig(), "sim", [(0.0, 600, 95), (4.0, 100, 90)], "pointe trop ancienne"),
])
def test_no_momentum_brake_outside_a_relaunch_in_sim(cfg, mode, frames, why):
    now = [100.0]
    drv = FtmsDriver(cfg, BikeConfig(), clock=lambda: now[0])
    if mode == "erg":
        drv.set_target_power(250.0)
    else:
        drv.set_sim_grade(0.5)
    _drive(drv, now, frames)
    assert drv.momentum_brakes == 0, why


def test_momentum_brake_skipped_when_the_flywheel_is_slow():
    now = [100.0]
    drv = FtmsDriver(TrainerConfig(), BikeConfig(), clock=lambda: now[0])
    drv.set_sim_grade(0.5)
    for t, power in [(0.0, 600), (1.0, 100)]:
        now[0] = 100.0 + t
        drv._on_ibd(None, bytearray(_ibd(15.0, 80, power)))
    assert drv.momentum_brakes == 0


def test_momentum_brake_grade_is_written_to_the_trainer():
    """La pente majorée part au trainer à la notification suivante, sans attendre le renvoi."""
    sent = []

    class _Cp:
        async def write(self, payload, **_kw):
            sent.append(bytes(payload))

    now = [100.0]
    drv = FtmsDriver(TrainerConfig(), BikeConfig(), clock=lambda: now[0])
    drv.set_sim_grade(0.5)
    drv._last_sent, drv._last_sent_at = ("sim", 0.5), 99.9

    async def _call(cp, build):
        await cp.write(build())
    drv._call_retrying = _call
    _drive(drv, now, [(0.0, 600, 95), (1.0, 150, 90)])
    asyncio.run(drv._flush_command(_Cp()))
    assert drv._last_sent == ("sim", pytest.approx(3.5))
    assert sent and sent[-1] == ftms.cmd_set_sim_params(3.5, drv._crr, drv._cw, 0.0)
