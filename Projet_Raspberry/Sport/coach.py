#!/usr/bin/env python3
"""Coach : synchronise Garmin + météo, puis génère l'instantané pour le coach.

  python coach.py login     # première connexion Garmin (MFA) -> enregistre le jeton
  python coach.py sync      # Garmin + météo + exports (à planifier chaque matin)
  python coach.py activities --days 120   # rattrapage : effet d'entraînement + zones des activités
  python coach.py garmin | weather | report | integrity
  options : --days N (rattrapage), --config chemin
"""
import argparse
import logging
import os
import sys
import tomllib
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import db, garmin_source, integrity, report, weather_source  # noqa: E402


def load_env(path):
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def start_day(con, cfg, days):
    today = date.today()
    if days:
        return today - timedelta(days=days)
    last = con.execute("SELECT MAX(day) d FROM daily").fetchone()["d"]
    if not last:
        return today - timedelta(days=cfg["sync"]["days_back_first_run"])
    return date.fromisoformat(last) - timedelta(days=cfg["sync"]["refetch_days"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["login", "sync", "garmin", "activities", "weather", "report", "integrity"])
    ap.add_argument("--days", type=int, help="remonter de N jours (rattrapage)")
    ap.add_argument("--config", default=str(HERE / "config.toml"))
    a = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_env(HERE / ".env")
    cfg = tomllib.loads(Path(a.config).read_text(encoding="utf-8"))
    p = cfg["paths"]
    rel = lambda s: Path(s).expanduser() if Path(s).expanduser().is_absolute() else HERE / s
    con = db.connect(rel(p["database"]))
    tokenstore = Path(p["tokenstore"]).expanduser()

    if a.command == "login":
        garmin_source.login(os.getenv("GARMIN_EMAIL"), os.getenv("GARMIN_PASSWORD"), tokenstore)
        print(f"Connexion OK. Jeton enregistré dans {tokenstore}")
        return 0

    start = start_day(con, cfg, a.days)
    rc = 0
    if a.command in ("sync", "garmin", "activities"):
        try:
            api = garmin_source.login(os.getenv("GARMIN_EMAIL"), os.getenv("GARMIN_PASSWORD"), tokenstore)
            col = garmin_source.Collector(api, con, cfg["sync"]["pause_seconds"])
            if a.command == "activities":
                col.activities_only(date.today() - timedelta(days=a.days or 120), date.today())
            else:
                col.run(start, date.today())
        except garmin_source.RateLimited:
            logging.error("Garmin demande de ralentir (429) : réessaie dans quelques heures.")
            rc = 1
        except PermissionError as e:
            logging.error("%s", e)
            rc = 1
    if a.command in ("sync", "weather"):
        loc = cfg["location"]
        try:
            weather_source.sync(con, loc["latitude"], loc["longitude"], loc["timezone"], start)
        except RuntimeError as e:
            logging.error("%s", e)
            rc = 1
    if a.command in ("sync", "report", "activities"):
        out = report.export(con, rel(p["export_dir"]))
        logging.info("Exports écrits dans %s", out)
    if a.command in ("sync", "report", "integrity"):
        f = integrity.build(con, rel(p["export_dir"]) / "integrite.html")
        logging.info("Rapport d'intégrité : %s", f)
    return rc


if __name__ == "__main__":
    sys.exit(main())
