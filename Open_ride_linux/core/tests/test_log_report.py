"""Tests unitaires de l'analyseur de journal de séance (Lot H6, SRS §14.1)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from openride_core.tools.log_report import (
    CONSECUTIVE_BREACHES,
    CORE_FORMAT_STRINGS,
    CPU_LIMIT_PCT,
    LAG_P99_LIMIT_MS,
    PATTERNS,
    STEP_P99_LIMIT_MS,
    analyse,
    format_report,
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
    assert rep.trainer.devices == ["HomeTrainer 0000"]
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
        "trainer_connected": ("HomeTrainer 0000",),
        "trainer_reconnect": (2.0,),
        "trainer_cmd_refused": (0x11, "CONTROL_NOT_PERMITTED"),
        "trainer_warning": ("plus de données du trainer",),
        "click_connected": ("C1:1C:00:00:00:01", 3.24, 2),
        "click_disconnected": ("C1:1C:00:00:00:01", 75.0, "0.1 s", "jamais", 750, "0.4 s", "lien perdu (rappel bleak)"),
        "click_rate": (598, 60.0, 9.97),
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
        fmt = re.sub(r'"\n\s+"', "", raw_fmt)
        args = sample_args[key]
        rendered = fmt % args if args else fmt
        assert PATTERNS[key].match(rendered), (
            f"Le motif '{key}' ne reconnaît pas le message formaté : {rendered!r}"
        )


def test_click_diagnostic_k8() -> None:
    """Lot K8 : durées de connexion, reconnexions, appuis, cadence et corrélation au trainer."""
    rep = analyse((LOGS_DIR / "seance_click_coupures.log").read_text(encoding="utf-8").splitlines())
    c = rep.click
    assert (c.connections, c.disconnections) == (4, 3)
    assert c.connection_durations_s == [75.0, 70.0, 10.0]
    assert (c.connection_min_s, c.connection_median_s, c.connection_max_s) == (10.0, 70.0, 75.0)
    assert c.reconnect_delays_s == [3.0, 8.0, 4.0]
    assert (c.reconnect_delay_median_s, c.reconnect_delay_max_s) == (4.0, 8.0)
    assert c.search_durations_s == [4.0, 3.0, 8.0, 4.0]
    assert c.since_press_at_drop_s == [12.0, 45.0]
    assert c.notification_rates == [10.0, 9.8] and c.notification_rate_min == 9.8
    # 1 s après une écriture au trainer : corrélée ; 10 s : non ; 1 s après une perte du trainer : corrélée.
    assert [d.trainer_correlated for d in c.drops] == [True, False, True]
    assert c.drops[0].since_trainer_write_s == 1.0 and c.drops[1].since_trainer_write_s == 10.0
    assert c.drops[2].since_press_s is None and c.drops[2].nearest_trainer_event_s == 1.0
    assert c.drops[0].reason == "lien perdu (rappel bleak)" and c.drops[0].notifications == 750
    assert c.trainer_correlated_drops == 2

    text = format_report(rep)
    assert "médiane 70.0 s" in text and "2/3 à moins de 2 s" in text


def test_click_diagnostic_old_logs_and_json_keys(capsys: pytest.CaptureFixture[str]) -> None:
    # Ancien format : compteurs inchangés, durées calculées sur les horodatages.
    rep = analyse((LOGS_DIR / "seance_coupures.log").read_text(encoding="utf-8").splitlines())
    assert (rep.click.connections, rep.click.disconnections, rep.click.failed_attempts) == (3, 2, 1)
    assert rep.click.connection_durations_s == [68.0, 53.0]
    assert rep.click.reconnect_delays_s == [12.0, 6.0]
    assert all(d.notifications is None for d in rep.click.drops)

    assert main([str(LOGS_DIR / "seance_click_coupures.log"), "--json"]) == 0
    click = json.loads(capsys.readouterr().out)["click"]
    for old_key in ("connections", "disconnections", "failed_attempts", "presses"):
        assert old_key in click
    for new_key in ("connection_durations_s", "connection_median_s", "reconnect_delays_s",
                    "since_press_at_drop_s", "notification_rates", "drops", "trainer_correlated_drops"):
        assert new_key in click
    assert set(click["drops"][0]) == {"timestamp", "connected_s", "since_notification_s", "since_press_s",
                                      "notifications", "since_trainer_write_s", "reason",
                                      "nearest_trainer_event_s", "trainer_correlated"}

    merged = analyse((LOGS_DIR / "seance_click_coupures.log").read_text(encoding="utf-8").splitlines() * 2,
                     all_sessions=True)
    assert merged.click.connection_durations_s == [75.0, 70.0, 10.0] * 2
    assert merged.click.trainer_correlated_drops == 4


def _click_lines(*events: tuple[str, str]) -> list[str]:
    head = "2026-10-24 19:00:00,000 INFO    core    Core démarré (trainer=ftms, entrées=click)."
    tail = (" après {d} s de connexion : dernière notification il y a 0.1 s, dernier appui il y a jamais, "
            "10 notification(s), dernière écriture au trainer il y a jamais, raison : lien perdu (rappel bleak) ; "
            "appuyez sur un bouton pour le réveiller")
    out = [head]
    for ts, ev in events:
        kind, _, rest = ev.partition(" ")
        if kind == "up":
            msg = f"INFO    input   Zwift Click connecté (adresse {rest}, recherche 1.0 s, 1 tentative(s))"
        else:
            addr, _, d = rest.partition(" ")
            msg = "WARNING input   Zwift Click déconnecté" + (f" (adresse {addr})" if addr != "-" else "") \
                + tail.format(d=d)
        out.append(f"2026-10-24 {ts},000 {msg}")
    return out


def test_click_diagnostic_two_boxes() -> None:
    """Click récent à deux boîtiers : durées et reconnexions comptées par adresse (audit du 24 octobre)."""
    rep = analyse(_click_lines(
        ("19:00:05", "up AA:01"), ("19:00:55", "up AA:02"),
        ("19:01:05", "down AA:01 60.0"),       # le boîtier 1 est resté 60 s, pas 10 s
        ("19:01:09", "up AA:01"),              # reconnexion du boîtier 1 en 4 s
        ("19:01:15", "down AA:02 20.0"),
    ))
    assert rep.click.connection_durations_s == [60.0, 20.0]
    assert rep.click.reconnect_delays_s == [4.0]

    # Journal d'avant la correction : coupure sans adresse, deux boîtiers connectés → durée de la ligne.
    rep = analyse(_click_lines(("19:00:05", "up AA:01"), ("19:00:55", "up AA:02"),
                               ("19:01:05", "down - 60.0")))
    assert rep.click.connection_durations_s == [60.0]
