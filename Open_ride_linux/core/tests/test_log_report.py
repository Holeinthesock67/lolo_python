"""Tests unitaires de l'analyseur de journal de séance (Lot H6, SRS §14.1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openride_core.tools import log_report
from openride_core.tools.log_report import (
    CONSECUTIVE_BREACHES,
    CORE_FORMAT_STRINGS,
    CPU_LIMIT_PCT,
    LAG_P99_LIMIT_MS,
    PATTERNS,
    STEP_P99_LIMIT_MS,
    analyse,
     main,
)

LOGS_DIR = Path(__file__).parent / "data" / "logs"
CORE_SRC_DIR = Path(__file__).resolve().parents[1] / "src" / "openride_core"


def test_constants_match_srs_14_1() -> None:
    assert STEP_P99_LIMIT_MS == 5.0
    assert LAG_P99_LIMIT_MS == 20.0
    assert CPU_LIMIT_PCT == 15.0
    assert CONSECUTIVE_BREACHES == 3


def test_seance_normale() -> None:
    lines = (LOGS_DIR / "seance_normale.log").read_text(encoding="utf-8").splitlines()
    rep = analyse(lines)

    assert rep.sessions_count == 1
    assert rep.trainer_mode == "ftms"
    assert rep.input_mode == "click"
    assert rep.trainer.connections == 1
    assert rep.trainer.disconnections == 0
    assert rep.trainer.reconnections == 0
    assert rep.trainer.control_refusals == 0
    assert rep.trainer.devices == ["Victory 9908"]
    assert rep.trainer.connected_duration_s == pytest.approx(208.53, abs=0.1)

    assert rep.click.connections == 1
    assert rep.click.disconnections == 0
    assert rep.click.failed_attempts == 0
    assert rep.click.presses == {
        "plus_short": 2,
        "minus_short": 1,
        "plus_long": 1,
        "minus_long": 1,
    }

    assert rep.pauses == []
    assert rep.perf.count == 3
    assert rep.perf.step_p99_max_ms == pytest.approx(0.51)
    assert rep.perf.lag_p99_max_ms == pytest.approx(1.9)
    assert rep.perf.cpu_max_pct == pytest.approx(3.5)
    assert rep.rust_threshold_reached is False
    assert rep.errors == []
    assert rep.warnings == []


def test_seance_coupures() -> None:
    lines = (LOGS_DIR / "seance_coupures.log").read_text(encoding="utf-8").splitlines()
    rep = analyse(lines)

    assert rep.trainer.connections == 2
    assert rep.trainer.disconnections == 1
    assert rep.trainer.reconnections == 1
    assert rep.trainer.control_refusals == 1
    assert rep.trainer.lost_duration_s == pytest.approx(8.0, abs=0.1)
    assert rep.trainer.connected_duration_s == pytest.approx(171.05, abs=0.1)

    assert rep.click.connections == 3
    assert rep.click.disconnections == 2
    assert rep.click.failed_attempts == 1
    assert rep.click.presses["plus_short"] == 1
    assert rep.click.presses["minus_short"] == 1

    assert len(rep.pauses) == 1
    assert rep.pauses[0].from_state == "RUNNING"
    assert rep.pauses[0].to_state == "PAUSED"
    assert rep.pauses[0].reason == "trainer_lost"
    assert rep.rust_threshold_reached is False


def test_seance_tronquee_et_multi_lancements() -> None:
    lines = (LOGS_DIR / "seance_tronquee_multi.log").read_text(encoding="utf-8").splitlines()

    # Par défaut : seule la dernière séance est analysée
    rep_last = analyse(lines, all_sessions=False)
    assert rep_last.sessions_count == 1
    assert rep_last.trainer_mode == "ftms"
    assert rep_last.input_mode == "click"
    assert rep_last.perf.count == 3
    assert rep_last.perf.step_p99_breaches == 1
    assert rep_last.rust_threshold_reached is False

    # Avec --all : les deux séances sont agrégées et les 2 lignes tronquées comptées
    rep_all = analyse(lines, all_sessions=True)
    assert rep_all.sessions_count == 2
    assert len(rep_all.sessions) == 2
    assert rep_all.perf.count == 4
    assert rep_all.unreadable_lines == 2


def test_rust_threshold_only_after_three_consecutive_breaches() -> None:
    base = [
        "2026-10-22 18:00:00,000 INFO    core    Core démarré (trainer=mock, entrées=keyboard).",
        "2026-10-22 18:01:00,000 INFO    core    Perf : pas p50 0.20 / p99 6.10 / max 8.00 ms ; retard p99 1.0 / max 2.0 ms ; CPU 3.0 %",
        "2026-10-22 18:02:00,000 INFO    core    Perf : pas p50 0.20 / p99 5.50 / max 7.00 ms ; retard p99 1.0 / max 2.0 ms ; CPU 3.0 %",
    ]
    # 2 dépassements consécutifs seulement -> False
    assert analyse(base).rust_threshold_reached is False

    # Un relevé normal remet le compteur consécutif à 0, puis un 3e dépassement non consécutif -> False
    non_consec = base + [
        "2026-10-22 18:03:00,000 INFO    core    Perf : pas p50 0.20 / p99 0.50 / max 1.00 ms ; retard p99 1.0 / max 2.0 ms ; CPU 3.0 %",
        "2026-10-22 18:04:00,000 INFO    core    Perf : pas p50 0.20 / p99 7.00 / max 9.00 ms ; retard p99 1.0 / max 2.0 ms ; CPU 3.0 %",
    ]
    rep_nc = analyse(non_consec)
    assert rep_nc.perf.step_p99_breaches == 3
    assert rep_nc.perf.max_consecutive_step_breaches == 2
    assert rep_nc.rust_threshold_reached is False

    # 3 dépassements consécutifs sur step_p99 -> True
    three_step = base + [
        "2026-10-22 18:03:00,000 INFO    core    Perf : pas p50 0.20 / p99 5.10 / max 6.00 ms ; retard p99 1.0 / max 2.0 ms ; CPU 3.0 %",
    ]
    assert analyse(three_step).rust_threshold_reached is True

    # 3 dépassements consécutifs sur lag_p99 (> 20 ms) -> True
    three_lag = [
        "2026-10-22 18:00:00,000 INFO    core    Core démarré (trainer=mock, entrées=keyboard).",
        "2026-10-22 18:01:00,000 INFO    core    Perf : pas p50 0.20 / p99 0.40 / max 1.00 ms ; retard p99 21.0 / max 25.0 ms ; CPU 3.0 %",
        "2026-10-22 18:02:00,000 INFO    core    Perf : pas p50 0.20 / p99 0.40 / max 1.00 ms ; retard p99 22.5 / max 28.0 ms ; CPU 3.0 %",
        "2026-10-22 18:03:00,000 INFO    core    Perf : pas p50 0.20 / p99 0.40 / max 1.00 ms ; retard p99 20.1 / max 22.0 ms ; CPU 3.0 %",
    ]
    assert analyse(three_lag).rust_threshold_reached is True

    # 3 dépassements consécutifs sur CPU (> 15 %) -> True
    three_cpu = [
        "2026-10-22 18:00:00,000 INFO    core    Core démarré (trainer=mock, entrées=keyboard).",
        "2026-10-22 18:01:00,000 INFO    core    Perf : pas p50 0.20 / p99 0.40 / max 1.00 ms ; retard p99 1.0 / max 2.0 ms ; CPU 15.5 %",
        "2026-10-22 18:02:00,000 INFO    core    Perf : pas p50 0.20 / p99 0.40 / max 1.00 ms ; retard p99 1.0 / max 2.0 ms ; CPU 16.0 %",
        "2026-10-22 18:03:00,000 INFO    core    Perf : pas p50 0.20 / p99 0.40 / max 1.00 ms ; retard p99 1.0 / max 2.0 ms ; CPU 18.2 %",
    ]
    assert analyse(three_cpu).rust_threshold_reached is True


def test_cli_json_and_missing_file(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    rc = main([str(LOGS_DIR / "seance_normale.log"), "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    for required_key in ("perf", "trainer", "click", "pauses", "rust_threshold_reached"):
        assert required_key in data

    rc_text = main([str(LOGS_DIR / "seance_coupures.log")])
    assert rc_text == 0
    text_out = capsys.readouterr().out
    assert "Trainer:" in text_out
    assert "Click  :" in text_out

    missing = tmp_path / "introuvable.log"
    rc_err = main([str(missing)])
    assert rc_err == 1
    err_out = capsys.readouterr().err
    assert "introuvable" in err_out


def test_patterns_match_exact_core_source_format_strings() -> None:
    """Critère 6 : chaque motif reconnu correspond à la chaîne de format exacte du code du core."""
    assert set(PATTERNS.keys()) == set(CORE_FORMAT_STRINGS.keys())

    sample_args: dict[str, tuple] = {
        "core_started": ("ftms", "click"),
        "core_stopped": (),
        "session_transition": ("RUNNING", "PAUSED", " (trainer_lost)"),
        "perf": (0.21, 0.48, 1.12, 1.8, 4.2, 3.4),
        "trainer_lost_pause": (),
        "engine_lost_pause": (),
        "trainer_control_refused_fatal": (),
        "trainer_connected": ("Victory 9908",),
        "trainer_reconnect": (2.0,),
        "trainer_cmd_refused": (0x11, "CONTROL_NOT_PERMITTED"),
        "trainer_warning": ("plus de données du trainer",),
        "click_connected": (),
        "click_disconnected": (),
        "click_press": ("PLUS_SHORT",),
        "click_not_found": (),
        "journal_write_error": ("No space left on device",),
        "fit_export_error": ("fichier invalide",),
    }

    for key, (filename, raw_fmt) in CORE_FORMAT_STRINGS.items():
        src_text = (CORE_SRC_DIR / filename).read_text(encoding="utf-8")
        assert raw_fmt in src_text, (
            f"La chaîne de format pour '{key}' ({raw_fmt!r}) est absente de {filename}"
        )
        # Reconstitue la chaîne Python si elle est concaténée sur deux lignes dans le source
        fmt = raw_fmt.replace('"\n                         "', "")
        args = sample_args[key]
        rendered = fmt % args if args else fmt
        assert PATTERNS[key].match(rendered), (
            f"Le motif '{key}' ne reconnaît pas le message formaté : {rendered!r}"
        )
