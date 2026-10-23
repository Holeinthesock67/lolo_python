"""Validation indépendante des fichiers FIT produits par OpenRide avec garmin-fit-sdk (Lot H5, SRS §9)."""

from __future__ import annotations

from pathlib import Path

import pytest
from garmin_fit_sdk import Decoder, Stream

from openride_core.fit_export import journal_to_fit, write_fit
from openride_core.journal import JournalWriter, Record

T0 = 1_790_000_000.0  # 2026
SEMICIRCLES_TO_DEG = 180.0 / (2**31)


def _decode_fit(path: Path) -> tuple[Decoder, dict, list]:
    stream = Stream.from_file(str(path))
    decoder = Decoder(stream)
    assert decoder.is_fit(), "Le fichier n'est pas reconnu comme FIT par garmin-fit-sdk"
    assert decoder.check_integrity(), "Le CRC du fichier FIT est invalide selon garmin-fit-sdk"
    stream.reset()
    messages, errors = decoder.read()
    return decoder, messages, errors


def _make_records(n: int = 600, with_hr: bool = True) -> tuple[list[dict], list[dict]]:
    records: list[dict] = []
    for i in range(n):
        ts = T0 + float(i + 1)
        rec = {
            "ts": ts,
            "t": float(i + 1),
            "lat": 45.123456 + i * 1e-5,
            "lon": 5.654321 + i * 1e-5,
            "alt": 500.0 + i * 0.2,
            "distance": 8.5 * (i + 1),
            "speed": 8.5,
            "power": 220,
            "cadence": 90,
            "hr": 145 if with_hr else None,
        }
        records.append(rec)
    events = [
        {"event": "start", "ts": T0 + 1.0},
        {"event": "stop", "ts": T0 + float(n)},
    ]
    return records, events


def _assert_valid_simple_session(fit_path: Path, expected_records: int) -> dict:
    _, messages, errors = _decode_fit(fit_path)
    assert errors == [], f"Erreurs garmin-fit-sdk : {errors}"

    for key in (
        "file_id_mesgs",
        "record_mesgs",
        "event_mesgs",
        "lap_mesgs",
        "session_mesgs",
        "activity_mesgs",
    ):
        assert key in messages and len(messages[key]) >= 1, f"Section {key} absente du FIT"

    assert len(messages["record_mesgs"]) == expected_records

    # 2. Message file_id
    fid = messages["file_id_mesgs"][0]
    assert fid["type"] == "activity"
    assert fid.get("manufacturer") is not None
    assert fid.get("product") is not None

    # 3. Message session
    sess = messages["session_mesgs"][0]
    assert sess["sport"] == "cycling"
    assert sess["sub_sport"] == "virtual_activity"

    recs = messages["record_mesgs"]
    last_dist = recs[-1]["distance"]
    elapsed = (recs[-1]["timestamp"] - recs[0]["timestamp"]).total_seconds()
    assert sess["total_distance"] == pytest.approx(last_dist, rel=0.01)
    assert sess["total_timer_time"] == pytest.approx(elapsed, rel=0.01)
    assert sess["total_elapsed_time"] == pytest.approx(elapsed, rel=0.01)
    return messages


def test_simple_10min_session_and_fields(tmp_path: Path) -> None:
    """Cas 1, 2, 3, 4 : séance simple de 10 min (600 enregistrements à 1 Hz)."""
    records, events = _make_records(600, with_hr=True)
    fit_path = tmp_path / "simple_10min.fit"
    write_fit(records, events, fit_path)

    messages = _assert_valid_simple_session(fit_path, expected_records=600)

    # 4. Vérification détaillée des champs record
    rec0 = messages["record_mesgs"][0]
    lat_deg = rec0["position_lat"] * SEMICIRCLES_TO_DEG
    lon_deg = rec0["position_long"] * SEMICIRCLES_TO_DEG
    assert lat_deg == pytest.approx(records[0]["lat"], abs=1e-6)
    assert lon_deg == pytest.approx(records[0]["lon"], abs=1e-6)
    assert rec0["power"] == records[0]["power"]
    assert rec0["cadence"] == records[0]["cadence"]
    assert rec0["heart_rate"] == records[0]["hr"]
    assert rec0["altitude"] == pytest.approx(records[0]["alt"], abs=0.5)
    assert rec0["speed"] == pytest.approx(records[0]["speed"], abs=0.05)


def test_session_with_two_pauses(tmp_path: Path) -> None:
    """Cas 5 : séance avec deux pauses, ordre des événements timer et temps chronométré."""
    records: list[dict] = []
    wall = T0
    events: list[dict] = [{"event": "start", "ts": wall + 1.0}]
    pause1_s = 30.0
    pause2_s = 45.0

    for i in range(120):
        wall += 1.0
        records.append({
            "ts": wall,
            "t": float(i + 1),
            "lat": 45.0 + i * 1e-5,
            "lon": 6.0,
            "alt": 300.0,
            "distance": 7.0 * (i + 1),
            "speed": 7.0,
            "power": 180,
            "cadence": 85,
            "hr": 135,
        })
        if i == 39:
            events.append({"event": "pause", "ts": wall})
            wall += pause1_s
            events.append({"event": "resume", "ts": wall})
        elif i == 79:
            events.append({"event": "pause", "ts": wall})
            wall += pause2_s
            events.append({"event": "resume", "ts": wall})

    events.append({"event": "stop", "ts": wall})

    fit_path = tmp_path / "pauses.fit"
    write_fit(records, events, fit_path)

    _, messages, errors = _decode_fit(fit_path)
    assert errors == []

    timer_events = [e for e in messages["event_mesgs"] if e.get("event") == "timer"]
    event_types = [e.get("event_type") for e in timer_events]
    assert len(event_types) == 6
    assert event_types[0] == "start"
    assert event_types[1] in ("stop_all", "stop")
    assert event_types[2] == "start"
    assert event_types[3] in ("stop_all", "stop")
    assert event_types[4] == "start"
    assert event_types[5] in ("stop_all", "stop")

    sess = messages["session_mesgs"][0]
    total_pauses = pause1_s + pause2_s
    assert sess["total_timer_time"] == pytest.approx(
        sess["total_elapsed_time"] - total_pauses, abs=1e-3
    )


def test_session_without_heart_rate(tmp_path: Path) -> None:
    """Cas 6 : séance sans fréquence cardiaque (champ heart_rate absent et non 0)."""
    records, events = _make_records(30, with_hr=False)
    fit_path = tmp_path / "no_hr.fit"
    write_fit(records, events, fit_path)

    _, messages, errors = _decode_fit(fit_path)
    assert errors == []
    for rec in messages["record_mesgs"]:
        assert "heart_rate" not in rec


def test_synthetic_3h_session(tmp_path: Path) -> None:
    """Cas 7 : séance synthétique de 3 h (10 800 enregistrements)."""
    records, events = _make_records(10_800, with_hr=True)
    fit_path = tmp_path / "3h.fit"
    write_fit(records, events, fit_path)

    _, messages, errors = _decode_fit(fit_path)
    assert errors == []
    assert len(messages["record_mesgs"]) == 10_800


def test_journal_to_fit_validation(tmp_path: Path) -> None:
    """Cas 8 : journal JSONL écrit par JournalWriter puis converti par journal_to_fit."""
    journal_path = tmp_path / "seance.jsonl"
    n = 120
    with JournalWriter(journal_path, route_id="alpe") as j:
        j.event("start", T0 + 1.0)
        for i in range(n):
            ts = T0 + float(i + 1)
            j.record(
                Record(
                    ts=ts,
                    t=float(i + 1),
                    lat=45.05 + i * 1e-5,
                    lon=6.05 + i * 1e-5,
                    alt=800.0 + i * 0.5,
                    distance=6.0 * (i + 1),
                    speed=6.0,
                    power=210.0,
                    cadence=82.0,
                    hr=150,
                    grade=5.0,
                    gear=10,
                )
            )
        j.event("stop", T0 + float(n))

    fit_path, _ = journal_to_fit(journal_path, tmp_path / "from_journal.fit")
    _assert_valid_simple_session(fit_path, expected_records=n)
