"""Météo horaire via Open-Meteo (gratuit, sans clé).

- jours anciens  : API « archive » (observations/réanalyse, ~5 jours de délai)
- jours récents + prévisions : API « forecast » (past_days + forecast_days)
Les prévisions sont ré-écrasées plus tard par les valeurs observées.
"""
import logging
import time
from datetime import date, timedelta

import requests

import db

log = logging.getLogger("weather")
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
FORECAST = "https://api.open-meteo.com/v1/forecast"
HOURLY = "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,wind_speed_10m"


def _get(url, params, tries=3):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            log.warning("Open-Meteo essai %d/%d : %s", i + 1, tries, e)
            time.sleep(2 * (i + 1))
    raise RuntimeError("Open-Meteo injoignable")


def _store(con, js, source):
    h = js["hourly"]
    for i, ts in enumerate(h["time"]):
        db.upsert(con, "weather_hourly", dict(
            ts=ts, temp_c=h["temperature_2m"][i], feels_c=h["apparent_temperature"][i],
            humidity=h["relative_humidity_2m"][i], precip_mm=h["precipitation"][i],
            wind_kmh=h["wind_speed_10m"][i], source=source), "ts")
    con.commit()
    return len(h["time"])


def sync(con, lat, lon, tz, start, today=None, forecast_days=4):
    today = today or date.today()
    cut = today - timedelta(days=7)          # au-delà : archive ; en deçà : forecast
    base = dict(latitude=lat, longitude=lon, hourly=HOURLY, timezone=tz)
    n = 0
    if start <= cut:
        n += _store(con, _get(ARCHIVE, dict(base, start_date=start.isoformat(),
                                            end_date=cut.isoformat())), "archive")
        recent_start = cut + timedelta(days=1)
    else:
        recent_start = start
    past = min(max((today - recent_start).days, 0), 92)
    n += _store(con, _get(FORECAST, dict(base, past_days=past, forecast_days=forecast_days)),
                "recent")
    log.info("Météo : %d heures enregistrées", n)
    return n
