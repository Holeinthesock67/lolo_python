"""Import des données Garmin Connect (bibliothèque non officielle `garminconnect`).

Principe de robustesse : chaque réponse brute est stockée telle quelle (table raw_garmin),
puis analysée séparément. Si Garmin change un champ, rien n'est perdu : on corrige le
parseur et on ré-analyse les données brutes.
"""
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import db

log = logging.getLogger("garmin")


class RateLimited(Exception):
    """Garmin demande de ralentir (HTTP 429)."""


def dig(d, *path, default=None):
    """Accès sûr dans dicts/listes imbriqués."""
    for p in path:
        if isinstance(d, dict):
            d = d.get(p)
        elif isinstance(d, list) and isinstance(p, int) and -len(d) <= p < len(d):
            d = d[p]
        else:
            return default
        if d is None:
            return default
    return d


# ---------- parseurs (fonctions pures, testables) ----------
def _pos(v):
    """Garmin renvoie -1 ou -2 quand la mesure n'existe pas : on le traite comme absent."""
    return None if v is None or (isinstance(v, (int, float)) and v < 0) else v


def parse_stats(s):
    return {k: _pos(v) for k, v in dict(resting_hr=dig(s, "restingHeartRate"), steps=dig(s, "totalSteps"),
                body_battery_high=dig(s, "bodyBatteryHighestValue"),
                body_battery_low=dig(s, "bodyBatteryLowestValue"),
                stress_avg=dig(s, "averageStressLevel")).items()}


def parse_hrv(h):
    return dict(hrv_last_night=dig(h, "hrvSummary", "lastNightAvg"),
                hrv_weekly_avg=dig(h, "hrvSummary", "weeklyAvg"),
                hrv_status=dig(h, "hrvSummary", "status"))


def parse_sleep(s):
    dto = dig(s, "dailySleepDTO", default={})
    start_min = None
    ms = dto.get("sleepStartTimestampLocal")
    if ms:  # horodatage « local » exprimé en ms ; on lit h/min comme du UTC
        t = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        start_min = t.hour * 60 + t.minute + (1440 if t.hour < 12 else 0)  # après minuit = +24 h
    return dict(sleep_seconds=dto.get("sleepTimeSeconds"),
                sleep_score=dig(dto, "sleepScores", "overall", "value"),
                sleep_start_min=start_min)


def parse_readiness(r):
    return dict(training_readiness=dig(r, "score") if isinstance(r, dict) else dig(r, 0, "score"))


def parse_vo2(m):
    g = dig(m, 0, "generic", default={}) if isinstance(m, list) else dig(m, "generic", default={})
    return dict(vo2max=g.get("vo2MaxPreciseValue") or g.get("vo2MaxValue"))


ENDPOINTS = [  # (nom, méthode de la bibliothèque, parseur)
    ("stats", "get_stats", parse_stats),
    ("hrv", "get_hrv_data", parse_hrv),
    ("sleep", "get_sleep_data", parse_sleep),
    ("readiness", "get_training_readiness", parse_readiness),
    ("maxmetrics", "get_max_metrics", parse_vo2),
]


def parse_activity(a):
    start = a.get("startTimeLocal") or ""
    return dict(activity_id=a.get("activityId"), day=start[:10], start_local=start,
                type=dig(a, "activityType", "typeKey"), name=a.get("activityName"),
                duration_s=a.get("duration"), distance_m=a.get("distance"),
                avg_hr=a.get("averageHR"), max_hr=a.get("maxHR"),
                avg_power=a.get("avgPower"), norm_power=a.get("normPower"),
                elevation_gain_m=a.get("elevationGain"), calories=a.get("calories"),
                training_load=a.get("activityTrainingLoad"))


def parse_sets(payload, activity_id):
    """Séries d'une séance de musculation (get_activity_exercise_sets)."""
    out = []
    for i, st in enumerate(dig(payload, "exerciseSets", default=[]) or []):
        ex = (st.get("exercises") or [{}])
        best = max(ex, key=lambda e: e.get("probability") or 0) if ex else {}
        w = st.get("weight")
        if w is not None:
            w = round(w / 1000, 2) if w > 500 else w   # Garmin renvoie des grammes
            w = None if w < 0 else w
        out.append(dict(activity_id=activity_id, set_idx=i, set_type=st.get("setType"),
                        category=best.get("category"), exercise=best.get("name"),
                        reps=st.get("repetitionCount"), weight_kg=w,
                        duration_s=st.get("duration"), start_time=st.get("startTime"),
                        probability=best.get("probability"), wkt_step=st.get("wktStepIndex")))
    return out


SET_COLS = ("activity_id", "set_idx", "set_type", "category", "exercise", "reps", "weight_kg",
            "duration_s", "start_time", "probability", "wkt_step")


def store_sets(con, aid, rows):
    con.execute("DELETE FROM strength_sets WHERE activity_id=?", (aid,))
    for r in rows:
        con.execute(f"INSERT OR REPLACE INTO strength_sets ({','.join(SET_COLS)}) VALUES ({','.join('?' for _ in SET_COLS)})",
                    [r[c] for c in SET_COLS])


def reparse_sets(con):
    """Reconstruit strength_sets depuis les réponses brutes déjà stockées (aucun appel réseau)."""
    n = 0
    for day, payload in con.execute("SELECT day, payload FROM raw_garmin WHERE endpoint='exercise_sets'").fetchall():
        aid = int(day.split(":", 1)[1])
        store_sets(con, aid, parse_sets(json.loads(payload), aid))
        n += 1
    con.commit()
    return n


# ---------- connexion ----------
def login(email, password, tokenstore):
    """Utilise le jeton enregistré ; sinon connexion par identifiants (+ code MFA saisi)."""
    from garminconnect import Garmin
    ts = str(Path(tokenstore).expanduser())
    try:
        api = Garmin()
        api.login(ts)
        return api
    except Exception as e:
        log.info("Pas de jeton valide (%s) : connexion par identifiants.", type(e).__name__)
    if not (email and password):
        raise SystemExit("Identifiants manquants : renseigne GARMIN_EMAIL et GARMIN_PASSWORD "
                         "dans le fichier .env pour la première connexion.")
    api = Garmin(email=email, password=password,
                 prompt_mfa=lambda: input("Code MFA Garmin : ").strip())
    api.login(ts)  # les versions récentes enregistrent le jeton dans `ts`
    if not Path(ts).exists() and hasattr(api, "garth"):  # anciennes versions
        api.garth.dump(ts)
    return api


# ---------- collecte ----------
class Collector:
    def __init__(self, api, con, pause=0.7):
        self.api, self.con, self.pause = api, con, pause

    def _call(self, method, *args):
        time.sleep(self.pause)
        try:
            return getattr(self.api, method)(*args)
        except Exception as e:
            msg = str(e)
            if "429" in msg or "Too Many" in msg:
                raise RateLimited(msg) from e
            if "401" in msg or "nauthori" in msg:
                raise PermissionError("Jeton Garmin expiré : relance `python coach.py login`.") from e
            log.warning("%s%s : %s", method, args, msg[:150])
            return None

    def _raw(self, day, name, payload):
        self.con.execute("INSERT OR REPLACE INTO raw_garmin VALUES (?,?,?,?)",
                         (day, name, json.dumps(payload, ensure_ascii=False),
                          datetime.now().isoformat(timespec="seconds")))

    def run(self, start, end):
        d = start
        while d <= end:
            iso = d.isoformat()
            row = {"day": iso}
            for name, method, parser in ENDPOINTS:
                payload = self._call(method, iso)
                if payload is None:
                    continue
                self._raw(iso, name, payload)
                row.update({k: v for k, v in parser(payload).items() if v is not None})
            db.upsert(self.con, "daily", row, "day")
            self.con.commit()
            log.info("Garmin %s : %d champs", iso, len(row) - 1)
            d += timedelta(days=1)
        self._activities(start, end)
        self._weights(start, end)
        reparse_sets(self.con)   # applique les règles de lecture actuelles à tout l'historique
        self._strength_sets()
        self.con.commit()

    def _activities(self, start, end):
        acts = self._call("get_activities_by_date", start.isoformat(), end.isoformat()) or []
        for a in acts:
            row = parse_activity(a)
            if row["activity_id"]:
                db.upsert(self.con, "activities", row, "activity_id")
        log.info("Garmin : %d activités", len(acts))

    def _strength_sets(self, limit=120):
        """Détail série par série des séances de musculation pas encore lues."""
        todo = [r[0] for r in self.con.execute(
            "SELECT activity_id FROM activities WHERE type='strength_training' "
            "AND (activity_id NOT IN (SELECT activity_id FROM strength_fetched) "
            "     OR day >= date('now', '-3 day')) "  # séances récentes relues : charges parfois corrigées après coup
            "ORDER BY start_local DESC LIMIT ?", (limit,))]
        for aid in todo:
            payload = self._call("get_activity_exercise_sets", aid)
            if payload is None:
                continue
            self._raw(f"activity:{aid}", "exercise_sets", payload)
            rows = parse_sets(payload, aid)
            store_sets(self.con, aid, rows)
            self.con.execute("INSERT OR REPLACE INTO strength_fetched VALUES (?,?,?)",
                             (aid, len(rows), datetime.now().isoformat(timespec="seconds")))
            self.con.commit()
        if todo:
            log.info("Garmin : détail des séries lu pour %d séance(s) de musculation", len(todo))

    def _weights(self, start, end):
        payload = self._call("get_body_composition", start.isoformat(), end.isoformat())
        for e in dig(payload, "dateWeightList", default=[]):
            day, w = e.get("calendarDate"), e.get("weight")
            if day and w:
                db.upsert(self.con, "daily",
                          {"day": day, "weight_kg": round(w / 1000 if w > 300 else w, 2)}, "day")
