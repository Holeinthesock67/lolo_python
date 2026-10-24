"""Test hors ligne : fausses réponses Garmin/Open-Meteo, base temporaire."""
import random
import sys
import tempfile
import types
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import coach, db, garmin_source as gs, report, weather_source as ws

sys.stdout.reconfigure(encoding="utf-8")  # console Windows (cp1252) : l'instantané contient des « → »
random.seed(1)
TODAY = date(2026, 10, 16)


class FakeGarmin:
    def get_stats(self, d):
        return {"restingHeartRate": 52 + random.randint(-2, 2), "totalSteps": 8000,
                "bodyBatteryHighestValue": 90, "bodyBatteryLowestValue": 20, "averageStressLevel": 30,
                "moderateIntensityMinutes": 20, "vigorousIntensityMinutes": 10}

    def get_training_status(self, d):
        return {"mostRecentTrainingStatus": {"latestTrainingStatusData": {"123": {
                    "trainingStatusFeedbackPhrase": "PRODUCTIVE_6", "primaryTrainingDevice": True,
                    "acuteTrainingLoadDTO": {"dailyTrainingLoadAcute": 281, "dailyTrainingLoadChronic": 260,
                                             "dailyAcuteChronicWorkloadRatio": 1.1, "acwrStatus": "OPTIMAL"}}}},
                "mostRecentTrainingLoadBalance": {"metricsTrainingLoadBalanceDTOMap": {"123": {
                    "primaryTrainingDevice": True, "monthlyLoadAerobicLow": 792, "monthlyLoadAerobicHigh": 0,
                    "monthlyLoadAnaerobic": 119, "monthlyLoadAerobicLowTargetMin": 300, "monthlyLoadAerobicLowTargetMax": 650,
                    "monthlyLoadAerobicHighTargetMin": 300, "monthlyLoadAerobicHighTargetMax": 650,
                    "monthlyLoadAnaerobicTargetMin": 0, "monthlyLoadAnaerobicTargetMax": 200,
                    "trainingBalanceFeedbackPhrase": "AEROBIC_HIGH_SHORTAGE"}}}}

    def get_cycling_ftp(self):
        return {"functionalThresholdPower": 262, "sport": "CYCLING"}

    def get_activity_hr_in_timezones(self, aid):
        return [{"zoneNumber": 1, "secsInZone": 1500}, {"zoneNumber": 2, "secsInZone": 5400},
                {"zoneNumber": 3, "secsInZone": 300}, {"zoneNumber": 4, "secsInZone": 0}, {"zoneNumber": 5, "secsInZone": 0}]

    def get_hrv_data(self, d):
        return {"hrvSummary": {"lastNightAvg": 60 + random.randint(-6, 6), "weeklyAvg": 60, "status": "BALANCED"}}

    def get_sleep_data(self, d):
        ms = int(datetime(2026, 10, 15, 23, 15, tzinfo=timezone.utc).timestamp() * 1000)
        return {"dailySleepDTO": {"sleepTimeSeconds": 27000, "sleepStartTimestampLocal": ms,
                                  "sleepScores": {"overall": {"value": 80}}}}

    def get_training_readiness(self, d):
        return [{"score": 70}]

    def get_max_metrics(self, d):
        return [{"generic": {"vo2MaxPreciseValue": 49.5}}]

    def get_activity_exercise_sets(self, aid):
        return {"activityId": aid, "exerciseSets": [
            {"setType": "ACTIVE", "repetitionCount": 8, "weight": 19000.0, "duration": 40,
             "exercises": [{"category": "BENCH_PRESS", "name": "INCLINE_DUMBBELL_BENCH_PRESS", "probability": 100}]},
            {"setType": "REST", "duration": 90, "exercises": []},
            {"setType": "ACTIVE", "repetitionCount": 5, "weight": None, "duration": 30,
             "exercises": [{"category": "PULL_UP", "name": "NEUTRAL_GRIP_PULL_UP", "probability": 100}]}]}

    def get_body_composition(self, a, b):
        return {"dateWeightList": [{"calendarDate": b, "weight": 78500.0}]}

    def get_activities_by_date(self, a, b):
        return [{"activityId": 1, "activityName": "Sortie Z2", "startTimeLocal": "2026-10-11 08:30:00",
                 "activityType": {"typeKey": "road_biking"}, "duration": 7200, "distance": 55000,
                 "averageHR": 135, "maxHR": 160, "avgPower": 170, "normPower": 180,
                 "elevationGain": 400, "calories": 1300, "activityTrainingLoad": 150.0,
                 "aerobicTrainingEffect": 3.1, "anaerobicTrainingEffect": 0.2, "trainingEffectLabel": "BASE"},
                {"activityId": 3, "activityName": "4x4 HT", "startTimeLocal": "2026-10-15 19:00:00",
                 "activityType": {"typeKey": "indoor_cycling"}, "duration": 2700, "averageHR": 150, "avgPower": 220,
                 "aerobicTrainingEffect": 4.3, "anaerobicTrainingEffect": 1.8, "trainingEffectLabel": "VO2MAX",
                 "hrTimeInZone_1": 600, "hrTimeInZone_2": 900, "hrTimeInZone_3": 300, "hrTimeInZone_4": 300, "hrTimeInZone_5": 840},
                {"activityId": 2, "activityName": "Musculation", "startTimeLocal": "2026-10-12 18:37:00",
                 "activityType": {"typeKey": "strength_training"}, "duration": 2400, "averageHR": 80}]


def fake_weather(url, params):
    if "start_date" in params:
        s, e = date.fromisoformat(params["start_date"]), date.fromisoformat(params["end_date"])
    else:
        s, e = TODAY - timedelta(days=params["past_days"]), TODAY + timedelta(days=params["forecast_days"] - 1)
    times, d = [], s
    while d <= e:
        times += [f"{d.isoformat()}T{h:02d}:00" for h in range(24)]
        d += timedelta(days=1)
    n = len(times)
    temp = 11.0 if "start_date" in params else 12.0   # observé (archive) ≠ modèle (forecast)
    return {"hourly": {"time": times, "temperature_2m": [temp] * n, "apparent_temperature": [10.0] * n,
                       "relative_humidity_2m": [70] * n, "precipitation": [0.1] * n, "wind_speed_10m": [15] * n}}


def main():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:  # coach.main ne ferme pas sa base
        con = db.connect(Path(t) / "c.db")
        start = TODAY - timedelta(days=40)
        gs.Collector(FakeGarmin(), con, pause=0).run(start, TODAY)
        ws._get = fake_weather
        n = ws.sync(con, 48.85, 2.35, "Europe/Paris", start, today=TODAY)
        out = report.export(con, Path(t) / "export", today=TODAY)

        assert con.execute("SELECT COUNT(*) FROM daily").fetchone()[0] == 41
        assert con.execute("SELECT COUNT(*) FROM raw_garmin WHERE day NOT LIKE 'activity:%' AND endpoint<>'ftp'").fetchone()[0] == 41 * 6
        # nouveaux indicateurs : charge, répartition, FTP, effet d'entraînement, zones, minutes OMS
        import training
        m = training.metrics(con, TODAY)
        assert m["load"]["acwr"] == 1.1 and m["load"]["training_status"] == "Productif", m["load"]
        assert m["balance"]["aer_high"]["state"] == "sous la cible" and m["balance"]["feedback"] == "Déficit aérobie intense"
        assert m["ftp"]["watts"] == 262 and m["ftp"]["wkg"] == round(262 / 78.5, 2), m["ftp"]
        assert "last_4x4" not in m and "sunday" not in m   # le 4×4 se pilote sur la charge aérobie intense
        # natation étiquetée « Base » malgré du temps en Z4 : pas intense ; CrossFit ≥ 30 min : intense
        mk = lambda **k: {**dict(type="lap_swimming", duration_s=2700, te_label="AEROBIC_BASE", aerobic_te=3.7,
                                 anaerobic_te=2.3, z4_s=840, z5_s=120), **k}
        assert not training.is_intense(mk()) and training.is_intense(mk(type="indoor_cardio", te_label=None, aerobic_te=1.6))
        assert m["oms"]["total"] == 7 * (20 + 2 * 10), m["oms"]
        z = con.execute("SELECT z2_s, te_label FROM activities WHERE activity_id=1").fetchone()
        assert z["z2_s"] == 5400 and z["te_label"] == "BASE"
        assert (out / "coach_metrics.json").exists()
        assert con.execute("SELECT weight_kg FROM daily WHERE day=?", (TODAY.isoformat(),)).fetchone()[0] == 78.5
        assert con.execute("SELECT sleep_start_min FROM daily LIMIT 1").fetchone()[0] == 23 * 60 + 15
        a = con.execute("SELECT * FROM v_activity_weather").fetchone()
        assert a["temp_c"] == 12.0, "jointure météo/activité"
        # relance : pas de doublons, et une valeur None n'écrase rien
        gs.Collector(FakeGarmin(), con, pause=0).run(TODAY - timedelta(days=2), TODAY)
        assert con.execute("SELECT COUNT(*) FROM daily").fetchone()[0] == 41
        db.upsert(con, "daily", {"day": TODAY.isoformat(), "resting_hr": None}, "day")
        assert con.execute("SELECT resting_hr FROM daily WHERE day=?", (TODAY.isoformat(),)).fetchone()[0] is not None
        sets = con.execute("SELECT exercise, reps, weight_kg FROM strength_sets WHERE set_type='ACTIVE' ORDER BY set_idx").fetchall()
        assert [tuple(r) for r in sets] == [("INCLINE_DUMBBELL_BENCH_PRESS", 8, 19.0), ("NEUTRAL_GRIP_PULL_UP", 5, None)], sets
        import integrity
        integrity.build(con, Path(t) / "integrite.html", today=TODAY)
        assert "Musculation : détail des séries" in (Path(t) / "integrite.html").read_text(encoding="utf-8")
        # parseur tolérant
        assert gs.parse_hrv({}) == dict(hrv_last_night=None, hrv_weekly_avg=None, hrv_status=None)
        assert gs.parse_vo2(None)["vo2max"] is None

        test_error_classification()
        test_login(Path(t))
        test_settings(Path(t))
        test_weather_archive_refresh(con)
        test_deleted_activities(con)
        print(f"Météo : {n} heures ; fichiers : {sorted(p.name for p in out.iterdir())}\n")
        print((out / "coach_snapshot.md").read_text(encoding="utf-8"))
        print("TOUS LES TESTS OK")
        con.close()  # Windows : fermer la base avant de supprimer le dossier temporaire


def garmin_error(cls_name, code, url):
    """Exception façon garminconnect : erreur HTTP d'origine (avec son code) enveloppée."""
    inner = Exception(f"{code} Client Error: for url: {url}")
    inner.response = types.SimpleNamespace(status_code=code)
    outer = type(cls_name, (Exception,), {})(f"API client error ({code}): {inner}")
    outer.__cause__ = inner
    return outer


class Raising:
    def __init__(self, exc):
        self.exc = exc

    def get_activity_hr_in_timezones(self, aid):
        raise self.exc


def test_error_classification():
    """Bug 1 : un numéro d'activité contenant 429 ou 401 ne doit pas passer pour un 429 / 401."""
    url = "https://connect.garmin.com/activity-service/activity/{}/hrTimeInZones"
    call = lambda exc: gs.Collector(Raising(exc), None, pause=0)._call("get_activity_hr_in_timezones", 1)
    assert call(garmin_error("GarminConnectConnectionError", 404, url.format(20871429000))) is None
    assert call(garmin_error("GarminConnectConnectionError", 404, url.format(20871401000))) is None
    assert call(Exception("404 Client Error: Not Found for url: " + url.format(20871429000))) is None
    for exc, expected in [(garmin_error("GarminConnectTooManyRequestsError", 429, url.format(1)), gs.RateLimited),
                          (Exception("429 Client Error: Too Many Requests"), gs.RateLimited),
                          (type("GarminConnectTooManyRequestsError", (Exception,), {})("Rate limit exceeded"), gs.RateLimited),
                          (garmin_error("GarminConnectAuthenticationError", 401, url.format(1)), PermissionError)]:
        try:
            call(exc)
            raise AssertionError(f"{exc!r} aurait dû lever {expected.__name__}")
        except expected:
            pass


def test_login(t):
    """Bug 2 : sans .env (le Pi), un jeton inutilisable ne demande jamais d'identifiants ; la synchro continue."""
    tok = t / "tok"
    tok.mkdir()
    fail = {"exc": None}

    class FakeApi:
        def __init__(self, **k):
            pass

        def login(self, ts):
            if fail["exc"]:
                raise fail["exc"]

    sys.modules["garminconnect"] = types.SimpleNamespace(Garmin=FakeApi)
    reachable = gs._reachable
    try:
        def expect(exc_type, ts=tok):
            try:
                gs.login(None, None, ts)
                raise AssertionError(f"login aurait dû lever {exc_type.__name__}")
            except exc_type:
                pass

        assert isinstance(gs.login(None, None, tok), FakeApi)                 # jeton valide
        expect(PermissionError, t / "absent")                                 # pas de jeton
        fail["exc"] = ConnectionError("Name or service not known")
        gs._reachable = lambda: False
        expect(gs.GarminUnavailable)                                          # réseau coupé
        gs._reachable = lambda: True
        fail["exc"] = type("GarminConnectAuthenticationError", (Exception,), {})("Username and password are required")
        expect(PermissionError)                                               # jeton refusé
        fail["exc"] = garmin_error("GarminConnectTooManyRequestsError", 429, "https://sso.garmin.com")
        expect(gs.RateLimited)

        # bout en bout : Garmin injoignable -> code retour 1, mais météo, exports et intégrité produits
        fail["exc"] = ConnectionError("Name or service not known")
        gs._reachable = lambda: False
        cfg = t / "config.toml"
        cfg.write_text(f"[location]\nname='x'\nlatitude=48.9\nlongitude=7.1\ntimezone='Europe/Paris'\n"
                       f"[settings]\nremote=''\n[sync]\ndays_back_first_run=10\nrefetch_days=3\npause_seconds=0\n"
                       f"[paths]\ndatabase='{(t / 'e2e.db').as_posix()}'\ntokenstore='{tok.as_posix()}'\n"
                       f"export_dir='{(t / 'e2e').as_posix()}'\n", encoding="utf-8")
        assert coach.main(["sync", "--config", str(cfg)]) == 1
        for f in ("coach_snapshot.md", "daily.csv", "integrite.html"):
            assert (t / "e2e" / f).exists(), f
        e2e = db.connect(t / "e2e.db")
        assert e2e.execute("SELECT COUNT(*) FROM weather_hourly").fetchone()[0] > 0
        e2e.close()
    finally:
        gs._reachable = reachable
        del sys.modules["garminconnect"]


def test_settings(t):
    """Lieu météo lu dans l'onglet Réglages : géocodage, cache, secours, jamais d'exception."""
    import json
    from openpyxl import Workbook
    import settings_source as ss
    d = t / "settings"
    xlsx = t / "carnet_test.xlsx"

    def make(value):
        wb = Workbook()
        ws_ = wb.active
        ws_.title = "Réglages"
        ws_.append(["Paramètre", "Valeur"])
        ws_.append(["Taille (cm)", 176])
        if value is not None:
            ws_.append(["Lieu météo", value])
        wb.save(xlsx)

    calls = []
    def geo(q):
        calls.append(q)
        return {"Ville A": dict(name="Ville A, Pays", latitude=45.0, longitude=5.0, timezone="Europe/Paris")}.get(q)
    fetch_ok = lambda remote, dest: xlsx
    fetch_ko = lambda remote, dest: None
    cfg = {"location": dict(name="secours", latitude=1.0, longitude=2.0, timezone="UTC")}

    assert ss.resolve({}, d, fetch=fetch_ko, geocode_fn=geo) is None                  # rien du tout
    assert ss.resolve(cfg, d, fetch=fetch_ko, geocode_fn=geo)["name"] == "secours"     # config.toml en secours
    make("Ville A")
    loc = ss.resolve(cfg, d, fetch=fetch_ok, geocode_fn=geo)
    assert (loc["latitude"], loc["query"]) == (45.0, "Ville A") and calls == ["Ville A"]
    assert json.loads((d / "location.json").read_text(encoding="utf-8"))["name"] == "Ville A, Pays"
    ss.resolve(cfg, d, fetch=fetch_ok, geocode_fn=geo)
    assert calls == ["Ville A"], "même lieu : pas de nouveau géocodage"
    make("Ville inconnue")
    assert ss.resolve(cfg, d, fetch=fetch_ok, geocode_fn=geo)["name"] == "Ville A, Pays"   # dernier lieu connu
    assert ss.resolve(cfg, d, fetch=fetch_ko, geocode_fn=geo)["name"] == "Ville A, Pays"   # feuille injoignable
    make(None)
    assert ss.resolve(cfg, d, fetch=fetch_ok, geocode_fn=geo)["name"] == "Ville A, Pays"   # ligne absente
    def boom(q):
        raise ConnectionError("réseau coupé")
    make("Ville B")
    assert ss.resolve(cfg, d, fetch=fetch_ok, geocode_fn=boom)["name"] == "Ville A, Pays"
    assert ss.cached_place(d) == "Ville A, Pays"
    # coordonnées saisies directement, sans appel réseau
    g = ss.geocode("43,48 ; -1,56")
    assert (g["latitude"], g["longitude"], g["timezone"]) == (43.48, -1.56, "auto"), g
    assert ss.geocode("43.48, -1.56")["longitude"] == -1.56
    # géocodage : premier résultat, filtré par le pays s'il est donné
    class R:
        def __init__(self, js): self.js = js
        def raise_for_status(self): pass
        def json(self): return self.js
    res = {"results": [dict(name="Paris", latitude=33.6, longitude=-95.5, timezone="America/Chicago", country="États-Unis", country_code="US"),
                       dict(name="Paris", latitude=48.85, longitude=2.35, timezone="Europe/Paris", country="France", country_code="FR", admin1="Île-de-France")]}
    get = lambda url, params, timeout: R(res)
    assert ss.geocode("Paris", get=get)["latitude"] == 33.6
    fr = ss.geocode("Paris, France", get=get)
    assert (fr["latitude"], fr["name"]) == (48.85, "Paris, Île-de-France, France"), fr
    assert ss.geocode("Paris, Japon", get=get) is None


def test_weather_archive_refresh(con):
    """Bug 3 : une synchro quotidienne (début récent) remplace les heures « recent » par l'archive observée."""
    day = (TODAY - timedelta(days=4)).isoformat()
    row = lambda: con.execute("SELECT source, temp_c FROM weather_hourly WHERE ts=?", (f"{day}T10:00",)).fetchone()
    assert tuple(row()) == ("recent", 12.0)
    later = TODAY + timedelta(days=5)
    ws.sync(con, 48.85, 2.35, "Europe/Paris", later - timedelta(days=3), today=later)
    assert tuple(row()) == ("archive", 11.0), tuple(row())
    # heure absente de l'archive (pas encore publiée) : la valeur « recent » est conservée
    ts = f"{TODAY.isoformat()}T10:00"
    ws._store(con, {"hourly": {"time": [ts], "temperature_2m": [None], "apparent_temperature": [None],
                               "relative_humidity_2m": [None], "precipitation": [None], "wind_speed_10m": [None]}}, "archive")
    assert con.execute("SELECT source FROM weather_hourly WHERE ts=?", (ts,)).fetchone()[0] == "recent"


class FakeGarminDown(FakeGarmin):
    def get_activities_by_date(self, a, b):
        raise Exception("500 Server Error: Internal Server Error")


class FakeGarminDeleted(FakeGarmin):
    def get_activities_by_date(self, a, b):
        return [x for x in super().get_activities_by_date(a, b) if x["activityId"] != 3]


def test_deleted_activities(con):
    """Bug 4 : une activité supprimée dans Garmin Connect disparaît de la base (sauf si l'appel a échoué)."""
    ids = lambda: {r[0] for r in con.execute("SELECT activity_id FROM activities")}
    assert ids() == {1, 2, 3}
    gs.Collector(FakeGarminDown(), con, pause=0).run(TODAY - timedelta(days=5), TODAY)
    assert ids() == {1, 2, 3}, "réponse en erreur : rien ne doit être supprimé"
    gs.Collector(FakeGarminDeleted(), con, pause=0).run(TODAY - timedelta(days=2), TODAY)
    assert ids() == {1, 2}, ids()
    assert not con.execute("SELECT 1 FROM raw_garmin WHERE day='activity:3'").fetchone(), "le brut recréerait l'activité"
    gs.reparse_daily(con)
    assert ids() == {1, 2}
    # la musculation (activité 2, hors de la fenêtre relue) garde ses séries
    assert con.execute("SELECT COUNT(*) FROM strength_sets WHERE activity_id=2").fetchone()[0] == 3


main()
