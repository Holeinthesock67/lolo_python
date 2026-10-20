"""Test hors ligne : fausses réponses Garmin/Open-Meteo, base temporaire."""
import random
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import db, garmin_source as gs, report, weather_source as ws

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
    return {"hourly": {"time": times, "temperature_2m": [12.0] * n, "apparent_temperature": [10.0] * n,
                       "relative_humidity_2m": [70] * n, "precipitation": [0.1] * n, "wind_speed_10m": [15] * n}}


def main():
    with tempfile.TemporaryDirectory() as t:
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
        print(f"Météo : {n} heures ; fichiers : {sorted(p.name for p in out.iterdir())}\n")
        print((out / "coach_snapshot.md").read_text(encoding="utf-8"))
        print("TOUS LES TESTS OK")
        con.close()  # Windows : fermer la base avant de supprimer le dossier temporaire


main()
