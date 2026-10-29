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

def test_trace_rate_limit_under_2_lines_per_second(caplog):
    """Vérifie que la cadence des lignes FTMS ne dépasse pas 2 lignes/s en moyenne."""
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
        assert rate <= 2.0, f"Cadence trop élevée : {rate:.2f} lignes/s ({len(ftms_lines)} lignes en {duration:.2f} s)"

    asyncio.run(scenario())
