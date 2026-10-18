"""Base SQLite du coach : schéma, connexion, upsert."""
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_garmin (
  day TEXT NOT NULL, endpoint TEXT NOT NULL, payload TEXT, fetched_at TEXT,
  PRIMARY KEY (day, endpoint));

CREATE TABLE IF NOT EXISTS daily (
  day TEXT PRIMARY KEY,
  resting_hr REAL, hrv_last_night REAL, hrv_weekly_avg REAL, hrv_status TEXT,
  sleep_seconds REAL, sleep_score REAL, sleep_start_min REAL,
  body_battery_high REAL, body_battery_low REAL, stress_avg REAL, steps REAL,
  training_readiness REAL, vo2max REAL, weight_kg REAL);

CREATE TABLE IF NOT EXISTS activities (
  activity_id INTEGER PRIMARY KEY, day TEXT, start_local TEXT, type TEXT, name TEXT,
  duration_s REAL, distance_m REAL, avg_hr REAL, max_hr REAL, avg_power REAL,
  norm_power REAL, elevation_gain_m REAL, calories REAL, training_load REAL);

CREATE TABLE IF NOT EXISTS strength_sets (
  activity_id INTEGER NOT NULL, set_idx INTEGER NOT NULL,
  set_type TEXT,                  -- ACTIVE (série) ou REST (repos)
  category TEXT, exercise TEXT,   -- clés Garmin, ex. BENCH_PRESS / INCLINE_DUMBBELL_BENCH_PRESS
  reps INTEGER, weight_kg REAL, duration_s REAL, start_time TEXT,
  probability REAL,               -- confiance de la détection automatique de la montre (100 = saisi ou confirmé)
  wkt_step INTEGER,               -- étape de l'entraînement programmé (NULL = séance libre)
  PRIMARY KEY (activity_id, set_idx));

CREATE TABLE IF NOT EXISTS strength_fetched (activity_id INTEGER PRIMARY KEY, n_sets INTEGER, fetched_at TEXT);

CREATE TABLE IF NOT EXISTS weather_hourly (
  ts TEXT PRIMARY KEY,            -- heure locale 'YYYY-MM-DDTHH:00'
  temp_c REAL, feels_c REAL, humidity REAL, precip_mm REAL, wind_kmh REAL,
  source TEXT);                   -- 'archive' (observé) ou 'recent' (modèle/prévision)

DROP VIEW IF EXISTS v_activity_weather;
DROP VIEW IF EXISTS v_duplicates;
DROP VIEW IF EXISTS v_activities;
DROP VIEW IF EXISTS v_weather_daily;

-- Doublons : une même sortie enregistrée par deux appareils (montre + Edge 810, par ex.).
-- Même jour, même type, enregistrements qui se chevauchent dans le temps. On garde l'enregistrement le plus
-- complet : FC + puissance > FC seule > puissance seule > rien ; à égalité, le plus long.
CREATE VIEW v_activities AS
  SELECT a.* FROM activities a
  WHERE NOT EXISTS (
    SELECT 1 FROM activities b
    WHERE b.activity_id <> a.activity_id AND b.day = a.day AND b.type = a.type
      -- les deux enregistrements se chevauchent sur au moins la moitié du plus court
      AND (MIN(julianday(a.start_local) + a.duration_s / 86400.0, julianday(b.start_local) + b.duration_s / 86400.0)
           - MAX(julianday(a.start_local), julianday(b.start_local))) * 86400 >= 0.5 * MIN(a.duration_s, b.duration_s)
      AND MIN(a.duration_s, b.duration_s) > 0
      AND ( (b.avg_hr IS NOT NULL)*2 + (b.avg_power IS NOT NULL) > (a.avg_hr IS NOT NULL)*2 + (a.avg_power IS NOT NULL)
         OR ( (b.avg_hr IS NOT NULL)*2 + (b.avg_power IS NOT NULL) = (a.avg_hr IS NOT NULL)*2 + (a.avg_power IS NOT NULL)
              AND (b.duration_s > a.duration_s OR (b.duration_s = a.duration_s AND b.activity_id < a.activity_id)))));

-- Les enregistrements écartés (pour les signaler)
CREATE VIEW v_duplicates AS
  SELECT a.* FROM activities a WHERE a.activity_id NOT IN (SELECT activity_id FROM v_activities);

CREATE VIEW v_weather_daily AS
  SELECT substr(ts,1,10) AS day, ROUND(MIN(temp_c),1) AS tmin, ROUND(MAX(temp_c),1) AS tmax,
         ROUND(AVG(humidity),0) AS humidity, ROUND(SUM(precip_mm),1) AS precip_mm,
         ROUND(MAX(wind_kmh),0) AS wind_max_kmh
  FROM weather_hourly GROUP BY substr(ts,1,10);

CREATE VIEW v_activity_weather AS
  SELECT a.*, w.temp_c, w.feels_c, w.humidity, w.precip_mm, w.wind_kmh
  FROM v_activities a
  LEFT JOIN weather_hourly w
    ON w.ts = substr(replace(a.start_local,' ','T'),1,13) || ':00';
"""


def connect(path):
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    cols = {r[1] for r in con.execute("PRAGMA table_info(strength_sets)")}
    for c, t in (("probability", "REAL"), ("wkt_step", "INTEGER")):
        if c not in cols:
            con.execute(f"ALTER TABLE strength_sets ADD COLUMN {c} {t}")
    # valeurs sentinelles de Garmin (-1, -2 = « pas de mesure ») -> absent
    for col in ("resting_hr", "hrv_last_night", "sleep_seconds", "sleep_score", "body_battery_high",
                "body_battery_low", "stress_avg", "steps", "training_readiness", "vo2max", "weight_kg"):
        con.execute(f"UPDATE daily SET {col} = NULL WHERE {col} < 0")
    con.commit()
    return con


def upsert(con, table, row, key):
    """Insère ou met à jour ; une valeur None n'écrase jamais une valeur existante."""
    cols = list(row)
    others = [c for c in cols if c != key]
    action = ("DO UPDATE SET " + ", ".join(
        f"{c}=COALESCE(excluded.{c}, {table}.{c})" for c in others)) if others else "DO NOTHING"
    sql = (f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)}) "
           f"ON CONFLICT({key}) {action}")
    con.execute(sql, [row[c] for c in cols])
