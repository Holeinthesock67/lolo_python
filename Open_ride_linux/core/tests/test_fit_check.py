"""Contrôle d'un FIT de séance réelle (lot X11) : FIT fabriqués par le core (propre, pause, trou, FC figée)."""

import json
from pathlib import Path

import pytest

from openride_core.__main__ import main as core_main
from openride_core.fit_export import write_fit
from openride_core.journal import JournalWriter, Record
from openride_core.tools import fit_check

T0 = 1_790_000_000.0


def session(n=120, pause=None, hole=None, frozen=None):
    """`n` s à 1 Hz ; `pause` (début, fin) sans relevé, avec ses événements ; `hole` (début, fin) sans relevé
    ni pause ; `frozen` (début, fin) où la FC reste à 104 bpm."""
    records, dist = [], 0.0
    for i in range(n):
        if pause and pause[0] <= i < pause[1] or hole and hole[0] <= i < hole[1]:
            continue
        dist += 8.0
        hr = 104 if frozen and frozen[0] <= i < frozen[1] else 120 + i % 6
        records.append({"ts": T0 + i, "t": float(i), "distance": dist, "speed": 8.0, "power": 200 + (i % 9) * 2,
                        "cadence": 88, "hr": hr})
    events = [{"event": "start", "ts": T0}]
    if pause:
        events += [{"event": "pause", "ts": T0 + pause[0] - 0.5}, {"event": "resume", "ts": T0 + pause[1]}]
    events.append({"event": "stop", "ts": T0 + n - 1})
    return records, events


def write(tmp_path, name, **kw):
    records, events = session(**kw)
    path = tmp_path / f"{name}.fit"
    write_fit(records, events, path)
    return path, records, events


def levels(path, journal=None):
    messages, errors, ok = fit_check.decode(path)
    return {ln["controle"]: ln["niveau"] for ln in fit_check.check(messages, errors, ok, journal)}


@pytest.mark.parametrize("name, kw, failed", [
    ("propre", {}, set()),
    ("pause", {"pause": (40, 70)}, set()),
    ("trou", {"hole": (40, 50)}, {"trous aux pauses"}),
    ("fc_figee", {"frozen": (30, 60)}, {"FC figée"}),
])
def test_four_fabricated_files(tmp_path, name, kw, failed):
    path, _, _ = write(tmp_path, name, **kw)
    got = levels(path)
    assert {k for k, v in got.items() if v == "ÉCHEC"} == failed, got
    assert len(got) == 7 and got["décodage"] == "OK" and got["totaux de la séance"] == "OK"


def journal_lines(records, events, scale=1.0):
    lines = [{"kind": "event", "event": e["event"], "ts": e["ts"]} for e in events]
    lines += [{"kind": "record", **r, "distance": r["distance"] * scale} for r in records]
    return sorted(lines, key=lambda x: x["ts"])


def test_against_journal(tmp_path):
    path, records, events = write(tmp_path, "pause", pause=(40, 70))
    assert levels(path, journal_lines(records, events))["face au journal"] == "OK"
    assert levels(path, journal_lines(records, events, scale=1.05))["face au journal"] == "ÉCHEC"


def test_missing_messages_and_corrupt_file(tmp_path):
    path, _, _ = write(tmp_path, "propre")
    messages, errors, ok = fit_check.decode(path)
    del messages["activity"]
    got = {ln["controle"]: ln["niveau"] for ln in fit_check.check(messages, errors, ok)}
    assert got["messages obligatoires"] == "ÉCHEC"
    raw = bytearray(path.read_bytes())
    raw[-1] ^= 0xFF   # CRC faux
    bad = tmp_path / "abime.fit"
    bad.write_bytes(bytes(raw))
    assert levels(bad)["décodage"] == "ÉCHEC"


def test_cli(tmp_path, capsys):
    path, records, events = write(tmp_path, "trou", hole=(40, 50))
    journal = tmp_path / "seance.jsonl"
    with JournalWriter(journal) as j:
        for e in events:
            j.event(e["event"], e["ts"])
        for r in records:
            j.record(Record(**{k: r[k] for k in ("ts", "t", "distance", "speed", "power", "cadence", "hr")}))
    assert core_main(["fit-check", str(path), "--journal", str(journal)]) == 1
    out = capsys.readouterr().out
    assert "[ÉCHEC] trous aux pauses : 1 trou(s) hors pause, le premier de 39 à 50 s" in out
    assert "[OK] face au journal" in out
    assert core_main(["fit-check", str(write(tmp_path, "propre")[0]), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert core_main(["fit-check", str(tmp_path / "absent.fit")]) == 2


def test_without_sdk(monkeypatch, tmp_path, capsys):
    import builtins
    real = builtins.__import__

    def fake(name, *a, **kw):
        if name == "garmin_fit_sdk":
            raise ImportError(name)
        return real(name, *a, **kw)
    monkeypatch.setattr(builtins, "__import__", fake)
    assert fit_check.run(Path(tmp_path / "x.fit")) == 2
    assert "pip install -e 'core[dev]'" in capsys.readouterr().out
