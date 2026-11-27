"""Fichier de diagnostic (lot DG1) : aucune valeur privée dans l'archive, dossier choisi, commande IPC.

Les valeurs « privées » ci-dessous sont fictives ; le test vérifie qu'aucune ne reste dans l'archive.
"""

from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path

import jsonschema
import pytest
from openride_core import config as config_mod
from openride_core import diagnostic

SCHEMAS = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc"

# Valeurs fictives qui ne doivent jamais sortir.
SECRET_NAME = "Camille Testeur"
SECRET_PROFILE_ID = "camille"
TRAINER_NAME = "VeloFictif 4242"
TRAINER_ADDR = "AA:BB:CC:11:22:33"
CLICK_ADDR = "C1:1C:00:00:00:07"
HR_ADDR = "BB:00:00:00:00:01"
SECRET_UUID = "12345678-9abc-4def-8123-456789abcdef"
SECRET_SSID = "BoxDuVoisin"
SECRET_GPS = ("12.34567", "98.76543")
SECRET_FTP = "287"
SECRET_WEIGHT = "73.4"
SECRET_SERIAL = "SN99887766"
SECRET_MODEL = "ModeleSecret-X"
SECRET_MAIL = "camille.testeur@example.org"
SECRET_IP = "192.168.1.57"


def _config() -> config_mod.Config:
    cfg = config_mod.Config()
    cfg.rider.ftp_w = float(SECRET_FTP)
    cfg.rider.mass_kg = float(SECRET_WEIGHT)
    cfg.trainer.device_name = TRAINER_NAME
    cfg.drivers.trainer_address = TRAINER_ADDR
    cfg.drivers.click_address = CLICK_ADDR
    cfg.drivers.hr_address = HR_ADDR
    cfg.render.quality = "medium"
    return cfg


def _home(tmp_path: Path) -> Path:
    home = tmp_path / "maison"
    logs = home / "OpenRide" / "Logs"
    logs.mkdir(parents=True)
    (home / "Téléchargements").mkdir()
    lines = [
        f"2026-11-22 10:00:00 INFO    core Trainer trouvé : {TRAINER_NAME} ({TRAINER_ADDR})",
        f"2026-11-22 10:00:01 INFO    core Click + : {CLICK_ADDR} ; ceinture {HR_ADDR}",
        f"2026-11-22 10:00:02 INFO    core dev_{TRAINER_ADDR.replace(':', '_')} appareil BlueZ {SECRET_UUID}",
        "2026-11-22 10:00:03 INFO    core Service FTMS 00001826-0000-1000-8000-00805f9b34fb",
        f"2026-11-22 10:00:04 INFO    core Device Information : serial: {SECRET_SERIAL}, model: {SECRET_MODEL}",
        f"2026-11-22 10:00:05 WARNING core Wi-Fi SSID : {SECRET_SSID} faible",
        f"2026-11-22 10:00:06 INFO    core Départ lat={SECRET_GPS[0]} lon={SECRET_GPS[1]}",
        f"2026-11-22 10:00:07 INFO    core Repère {SECRET_GPS[0]}, {SECRET_GPS[1]}",
        f"2026-11-22 10:00:08 INFO    core FTP {SECRET_FTP} W, poids {SECRET_WEIGHT} kg",
        f"2026-11-22 10:00:09 ERROR   core Profil {SECRET_NAME} ({SECRET_PROFILE_ID}) : {home}/OpenRide/x illisible",
        f"2026-11-22 10:00:10 INFO    core Contact {SECRET_MAIL} depuis {SECRET_IP}",
        "2026-11-22 10:00:11 WARNING core Trainer : CP occupé après 2 renvois",
    ]
    (logs / "openride_2026-11-22_10-00-00.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return home


def _devices() -> dict:
    return {"trainer": {"status": "CONNECTED", "name": TRAINER_NAME, "address": TRAINER_ADDR, "busy": False},
            "click": [{"side": "plus", "status": "CONNECTED", "battery_pct": 80}],
            "hr": {"status": "NONE", "source": None, "battery_pct": None}}


def _archive_text(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        return "\n".join(zf.read(n).decode("utf-8") for n in zf.namelist())


def test_archive_has_no_private_value(tmp_path):
    home = _home(tmp_path)
    res = diagnostic.write(_config(), "telechargements", home=home, devices=_devices(),
                           profile_entries=[(SECRET_PROFILE_ID, SECRET_NAME), ("principal", "Principal")],
                           engine_version="6.0.0", gpu="GeForce GTX 1060", now=datetime(2026, 11, 22, 12, 0, 0))
    path = home / "Téléchargements" / "openride_diagnostic_2026-11-22_12-00-00.zip"
    assert res["path"] == "~/Téléchargements/openride_diagnostic_2026-11-22_12-00-00.zip"
    assert path.is_file() and res["size_kb"] >= 1 and res["masked"] > 0
    text = _archive_text(path)
    secrets = [SECRET_NAME, *SECRET_NAME.split(), SECRET_PROFILE_ID, TRAINER_NAME, TRAINER_ADDR, CLICK_ADDR, HR_ADDR,
               TRAINER_ADDR.replace(":", "_"), SECRET_UUID, SECRET_SSID, *SECRET_GPS, SECRET_FTP, SECRET_WEIGHT,
               SECRET_SERIAL, SECRET_MODEL, SECRET_MAIL, SECRET_IP, str(home), "maison"]
    for secret in secrets:
        assert secret.lower() not in text.lower(), f"valeur privée restée dans le diagnostic : {secret}"
    # Ce qui sert au diagnostic reste lisible.
    report = json.loads(zipfile.ZipFile(path).read("diagnostic.json"))
    assert report["qualite"] == "medium"
    assert report["versions"]["openride_engine"] == "6.0.0"
    assert report["capteurs"]["trainer"] == {"status": "CONNECTED", "busy": False}
    assert set(report["reglages"]["rider"].values()) == {diagnostic.MASK}
    assert report["reglages"]["trainer"]["latency_tau_s"] == config_mod.TrainerConfig().latency_tau_s
    assert "00001826-0000-1000-8000-00805f9b34fb" in text        # UUID standard du Bluetooth gardé
    assert "<appareil-1>" in text and "CP occupé après 2 renvois" in text
    assert "envoyé nulle part" in zipfile.ZipFile(path).read("LISEZMOI.txt").decode("utf-8")


def test_same_device_keeps_same_mark():
    m = diagnostic.Masker()
    out = m.mask(f"{TRAINER_ADDR} puis {CLICK_ADDR} puis {TRAINER_ADDR.lower()} puis dev_{TRAINER_ADDR.replace(':', '_')}")
    assert out == "<appareil-1> puis <appareil-2> puis <appareil-1> puis dev_<appareil-1>"


@pytest.mark.parametrize("dest, folder", [("openride", "OpenRide/Diagnostics"), ("bureau", "Desktop"),
                                          ("telechargements", "Téléchargements")])
def test_dest_dir(tmp_path, dest, folder):
    (tmp_path / "Desktop").mkdir()
    assert diagnostic.dest_dir(dest, tmp_path) == tmp_path / folder


def test_dest_dir_follows_user_dirs(tmp_path):
    (tmp_path / ".config").mkdir()
    (tmp_path / "Mes envois").mkdir()
    (tmp_path / ".config" / "user-dirs.dirs").write_text('XDG_DOWNLOAD_DIR="$HOME/Mes envois"\n', encoding="utf-8")
    assert diagnostic.dest_dir("telechargements", tmp_path) == tmp_path / "Mes envois"


def test_unknown_dest_refused(tmp_path):
    with pytest.raises(diagnostic.DiagnosticError):
        diagnostic.dest_dir("nuage", tmp_path)


def test_ipc_command(tmp_path, monkeypatch):
    from test_contract_ipc import make_session

    s, cap = make_session(tmp_path, monkeypatch)
    home = _home(tmp_path)
    s.import_home = home
    s._on_command("create_diagnostic", {"dest": "openride", "engine_version": "6.0.0"}, 9)
    msgs = cap.of("diagnostic")
    assert len(msgs) == 1
    msg = msgs[0]
    jsonschema.validate(msg, json.loads((SCHEMAS / "diagnostic.schema.json").read_text(encoding="utf-8")))
    assert msg["ok"] and msg["request_cmd_id"] == 9 and msg["path"].startswith("~/OpenRide/Diagnostics/")
    assert list((home / "OpenRide" / "Diagnostics").glob("*.zip"))
    s._on_command("create_diagnostic", {"dest": "nuage"}, 10)
    assert any(e.get("code") == "bad_args" for e in cap.of("error"))
