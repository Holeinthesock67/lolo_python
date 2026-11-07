"""FIT de séance prêt pour Garmin Connect et GoldenCheetah (lot X56, recette 1.0 ligne 21).

Lu par le SDK officiel de Garmin (celui de Garmin Connect) : totaux que les deux logiciels affichent
sans recalculer, appareil créateur, tours complets, et contrôle de compatibilité de `fit-check`
sur des défauts fabriqués. Aucun vrai fichier d'activité : tout est fabriqué par `write_fit`.
"""

from __future__ import annotations

import pytest

from openride_core.fit_export import climb, normalized_power, write_fit
from openride_core.tools import fit_check

T0 = 1_790_000_000.0


def ride(n=600, power=lambda i: 200, alt=lambda i: 300.0 + i * 0.1, hr=True):
    records = [{"ts": T0 + i, "lat": 45.2 + i * 1e-5, "lon": 5.7 + i * 1e-5, "alt": alt(i),
                "distance": 8.0 * (i + 1), "speed": 8.0, "power": power(i), "cadence": 85 + i % 10,
                "hr": 130 + i % 5 if hr else None} for i in range(n)]
    return records, [{"event": "start", "ts": T0}, {"event": "stop", "ts": T0 + n - 1}]


def decoded(tmp_path, records, events, laps=None):
    path = tmp_path / "seance.fit"
    write_fit(records, events, path, laps)
    messages, errors, ok = fit_check.decode(path)
    assert ok and errors == []
    return path, messages


def test_session_carries_the_totals_garmin_connect_displays(tmp_path):
    records, events = ride(alt=lambda i: 300.0 + (i if i < 300 else 600 - i) * 0.2)
    _, m = decoded(tmp_path, records, events)
    s = m["session"][0]
    assert s["total_work"] == 600 * 200                      # J : 200 W pendant 600 s
    assert s["total_calories"] == 120                        # 120 kJ ≈ 120 kcal
    assert s["normalized_power"] == 200                      # puissance constante : NP = moyenne
    assert s["max_cadence"] == 94 and s["avg_cadence"] == 90
    assert s["total_ascent"] == pytest.approx(60, abs=1) and s["total_descent"] == pytest.approx(60, abs=1)
    assert s["sport"] == "cycling" and s["sub_sport"] == "virtual_activity"
    dev = m["device_info"][0]
    assert dev["product_name"] == "OpenRide" and dev["device_index"] == "creator"
    assert dev["software_version"] > 0


def test_each_lap_has_full_totals_that_add_up(tmp_path):
    records, events = ride(power=lambda i: 150 if i < 300 else 250)
    _, m = decoded(tmp_path, records, events, laps=[T0 + 300])
    laps, s = m["lap"], m["session"][0]
    assert len(laps) == 2 == s["num_laps"]
    assert [lap["avg_power"] for lap in laps] == [150, 250]
    assert all(lap.get(k) is not None for lap in laps
               for k in ("avg_heart_rate", "max_heart_rate", "avg_cadence", "max_cadence", "total_calories"))
    assert sum(lap["total_work"] for lap in laps) == s["total_work"]
    assert s["normalized_power"] > s["avg_power"]           # effort variable : NP au-dessus de la moyenne


def test_ride_without_heart_rate_nor_position(tmp_path):
    records, events = ride(n=120, hr=False)
    for r in records:
        del r["lat"], r["lon"], r["alt"]
    path, m = decoded(tmp_path, records, events)
    s = m["session"][0]
    assert s.get("avg_heart_rate") is None and s.get("total_ascent") is None
    lines = {ln["controle"]: ln["niveau"] for ln in fit_check.check(m, [], True, header=fit_check.read_header(path))}
    assert lines["compatibilité Garmin Connect et GoldenCheetah"] == "OK" and lines["totaux affichés"] == "OK"


def test_normalized_power_and_climb_helpers():
    assert normalized_power([200.0] * 29) is None           # moins de 30 s : pas de NP
    assert normalized_power([100.0] * 60 + [300.0] * 60) > 200
    assert climb([100.0, 100.4, 99.8, 100.3]) == (0, 0)      # bruit sous l'hystérésis de 1 m
    assert climb([100.0, 105.0, 102.0, 110.0]) == (13, 3)


def test_openride_fit_passes_the_compatibility_check(tmp_path, capsys):
    records, events = ride()
    path, _ = decoded(tmp_path, records, events, laps=[T0 + 200, T0 + 400])
    assert fit_check.run(path) == 0
    out = capsys.readouterr().out
    assert "[OK] compatibilité Garmin Connect et GoldenCheetah" in out and "[OK] totaux affichés" in out


@pytest.mark.parametrize("defect, expected", [
    (lambda m: m["session"][0].update(sport="running"), "sport running"),
    (lambda m: m["lap"][0].update(start_time=m["record"][0]["timestamp"].replace(year=2020),
                                  timestamp=m["record"][0]["timestamp"].replace(year=2020)),
     "fini avant le premier enregistrement"),
    (lambda m: m["activity"][0].update(num_sessions=2), "annonce 2 séance"),
    (lambda m: m["activity"][0].pop("local_timestamp"), "heure locale"),
    (lambda m: m["session"][0].update(num_laps=3), "annonce 3 tour"),
    (lambda m: m["file_id"][0].pop("time_created"), "file_id sans time_created"),
    (lambda m: m["record"][5].update(position_lat=2**31 - 2), "hors du globe"),
], ids=["sport", "tour_avant_releves", "seances", "heure_locale", "tours", "date_creation", "position"])
def test_fabricated_defects_fail_the_compatibility_check(tmp_path, defect, expected):
    records, events = ride(n=120)
    path, m = decoded(tmp_path, records, events)
    defect(m)
    recs = [dict(r, t=r["timestamp"].timestamp()) for r in m["record"]]
    issues = fit_check.compat_issues(m, recs, fit_check.read_header(path))
    assert any(expected in i for i in issues), issues


@pytest.mark.parametrize("header, expected", [
    (bytes([13]) + b"\x20" * 7 + b".FIT" + b"\x00\x00", "13 octets"),
    (bytes([14]) + b"\x20" * 7 + b"XFIT" + b"\x00\x00", "signature"),
])
def test_header_rejected_by_goldencheetah(header, expected):
    assert expected in fit_check._header_issue(header)


def test_fit_from_before_3_0_gets_a_warning_for_missing_totals(tmp_path):
    records, events = ride(n=120)
    _, m = decoded(tmp_path, records, events)
    for k in ("total_calories", "total_work", "total_ascent"):
        m["session"][0].pop(k)
    lines = {ln["controle"]: ln for ln in fit_check.check(m, [], True)}
    assert lines["totaux affichés"]["niveau"] == "ATTENTION"
    assert "total_calories" in lines["totaux affichés"]["detail"]
