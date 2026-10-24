"""Diagnostic BLE du sprint 0 (SRS §13) : HomeTrainer (FTMS) et Zwift Click.

Établit les faits à noter dans docs/spikes.md : services exposés, capacités FTMS, plage de
puissance, fréquence réelle des notifications, présence du pont cardio, réponses aux commandes
0x11 (SIM) et 0x05 (ERG), handshake et messages du Click.

Exemples (sur le PC Ubuntu, Zwift et téléphone déconnectés) :
    openride-ble-diag scan
    openride-ble-diag trainer --name "HomeTrainer" --duration 30
    openride-ble-diag trainer --name "HomeTrainer" --control --sim-grade 4 --erg 150
    openride-ble-diag click --duration 60

Chaque commande écrit un rapport JSON dans ./spike_reports/.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import statistics
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

from .. import ftms, zwift_click

log = logging.getLogger("ble_diag")
REPORT_DIR = Path("spike_reports")


# --- Utilitaires ----------------------------------------------------------------------

def save_report(kind: str, report: dict) -> Path:
    REPORT_DIR.mkdir(exist_ok=True)
    path = REPORT_DIR / f"{datetime.now():%Y-%m-%d_%H-%M-%S}_{kind}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    log.info("Rapport écrit : %s", path)
    return path


def rate_stats(timestamps: list[float]) -> dict:
    """Fréquence et régularité d'une suite d'horodatages."""
    if len(timestamps) < 2:
        return {"count": len(timestamps)}
    gaps = [b - a for a, b in zip(timestamps, timestamps[1:])]
    span = timestamps[-1] - timestamps[0]
    return {
        "count": len(timestamps),
        "rate_hz": round((len(timestamps) - 1) / span, 3) if span > 0 else None,
        "gap_mean_s": round(statistics.mean(gaps), 4),
        "gap_min_s": round(min(gaps), 4),
        "gap_max_s": round(max(gaps), 4),
        "gap_stdev_s": round(statistics.pstdev(gaps), 4),
    }


async def find_device(name: str | None, address: str | None, timeout: float) -> BLEDevice:
    if address:
        dev = await BleakScanner.find_device_by_address(address, timeout=timeout)
    else:
        needle = (name or "").lower()
        dev = await BleakScanner.find_device_by_filter(
            lambda d, ad: needle in (d.name or ad.local_name or "").lower(), timeout=timeout)
    if dev is None:
        raise SystemExit(f"Appareil introuvable (nom={name!r}, adresse={address!r}).")
    log.info("Trouvé : %s [%s]", dev.name, dev.address)
    return dev


def dump_gatt(client: BleakClient) -> list[dict]:
    tree = []
    for service in client.services:
        entry = {"uuid": service.uuid, "description": service.description, "characteristics": []}
        for ch in service.characteristics:
            entry["characteristics"].append(
                {"uuid": ch.uuid, "description": ch.description, "properties": ch.properties})
        tree.append(entry)
        log.info("Service %s (%s)", service.uuid, service.description)
        for ch in entry["characteristics"]:
            log.info("    %s  %-40s %s", ch["uuid"], ch["description"], ",".join(ch["properties"]))
    return tree


def has_char(client: BleakClient, uuid: str) -> bool:
    return client.services.get_characteristic(uuid) is not None


# --- scan -----------------------------------------------------------------------------

async def cmd_scan(args: argparse.Namespace) -> None:
    log.info("Scan BLE pendant %.0f s…", args.timeout)
    found = await BleakScanner.discover(timeout=args.timeout, return_adv=True)
    rows = []
    for dev, adv in sorted(found.values(), key=lambda da: -(da[1].rssi or -999)):
        row = {"name": dev.name or adv.local_name, "address": dev.address, "rssi": adv.rssi,
               "service_uuids": adv.service_uuids,
               "manufacturer_ids": list(adv.manufacturer_data.keys())}
        rows.append(row)
        tags = []
        if ftms.FTMS_SERVICE in adv.service_uuids:
            tags.append("FTMS")
        if ftms.HR_SERVICE in adv.service_uuids:
            tags.append("HR")
        if 2378 in adv.manufacturer_data:
            tags.append("ZWIFT")
        log.info("%4s dBm  %-20s %-25s %s", adv.rssi, dev.address, row["name"], " ".join(tags))
    save_report("scan", {"devices": rows})


# --- trainer --------------------------------------------------------------------------

async def cmd_trainer(args: argparse.Namespace) -> None:
    dev = await find_device(args.name, args.address, args.timeout)
    report: dict = {"device": {"name": dev.name, "address": dev.address}}
    ibd_times: list[float] = []
    hr_times: list[float] = []
    samples: list[dict] = []
    cp_responses: list[dict] = []
    cp_event = asyncio.Event()

    def on_ibd(_ch, data: bytearray) -> None:
        t = time.monotonic()
        ibd_times.append(t)
        parsed = ftms.parse_indoor_bike_data(bytes(data))
        if len(samples) < 2000:
            samples.append({"t": round(t - t0, 3), "raw": data.hex(), **asdict(parsed)})
        log.info("IBD  P=%s W  cad=%s rpm  v=%s km/h  HR=%s", parsed.power_w, parsed.cadence_rpm,
                 parsed.speed_kmh, parsed.heart_rate_bpm)

    def on_hr(_ch, data: bytearray) -> None:
        hr_times.append(time.monotonic())
        log.info("HR   %d bpm", ftms.parse_hr_measurement(bytes(data)))

    def on_cp(_ch, data: bytearray) -> None:
        resp = ftms.parse_control_response(bytes(data))
        entry = {"raw": data.hex()}
        if resp:
            entry.update(request_op=f"0x{resp.request_op:02x}", result=resp.result_name)
            log.info("CP   réponse op=0x%02x -> %s", resp.request_op, resp.result_name)
        cp_responses.append(entry)
        cp_event.set()

    async def control(client: BleakClient, label: str, payload: bytes) -> dict:
        cp_event.clear()
        log.info("CP   envoi %s : %s", label, payload.hex())
        await client.write_gatt_char(ftms.CONTROL_POINT, payload, response=True)
        try:
            await asyncio.wait_for(cp_event.wait(), timeout=3.0)
            return {"command": label, "sent": payload.hex(), "response": cp_responses[-1]}
        except asyncio.TimeoutError:
            log.warning("CP   pas de réponse à %s", label)
            return {"command": label, "sent": payload.hex(), "response": None}

    t0 = time.monotonic()
    async with BleakClient(dev, timeout=args.timeout) as client:
        report["gatt"] = dump_gatt(client)
        report["ftms_present"] = has_char(client, ftms.INDOOR_BIKE_DATA)
        if not report["ftms_present"]:
            save_report("trainer", report)
            raise SystemExit("Pas de service FTMS sur cet appareil.")

        if has_char(client, ftms.FEATURE):
            feats = ftms.parse_features(bytes(await client.read_gatt_char(ftms.FEATURE)))
            report["features"] = asdict(feats) | {"supports_sim": feats.supports_sim,
                                                  "supports_erg": feats.supports_erg}
            log.info("Capacités machine : %s", ", ".join(feats.machine))
            log.info("Consignes possibles : %s", ", ".join(feats.target))
        if has_char(client, ftms.SUPPORTED_POWER_RANGE):
            pr = ftms.parse_power_range(bytes(await client.read_gatt_char(ftms.SUPPORTED_POWER_RANGE)))
            report["power_range"] = asdict(pr)
            log.info("Plage de puissance : %d à %d W, pas %d W", pr.min_w, pr.max_w, pr.increment_w)

        report["hr_service_present"] = has_char(client, ftms.HR_MEASUREMENT)
        log.info("Service cardio (0x180D) exposé : %s", report["hr_service_present"])

        await client.start_notify(ftms.INDOOR_BIKE_DATA, on_ibd)
        if report["hr_service_present"]:
            await client.start_notify(ftms.HR_MEASUREMENT, on_hr)

        commands = []
        if args.control:
            await client.start_notify(ftms.CONTROL_POINT, on_cp)
            commands.append(await control(client, "request_control", ftms.cmd_request_control()))
            commands.append(await control(client, "start_resume", ftms.cmd_start_resume()))

        log.info("Écoute pendant %.0f s ; pédalez pour générer des données…", args.duration)
        phase = args.duration / 3 if args.control else args.duration
        try:
            await asyncio.sleep(phase)
            if args.control:
                if args.sim_grade is not None:
                    commands.append(await control(client, f"sim grade {args.sim_grade}%",
                                                  ftms.cmd_set_sim_params(args.sim_grade)))
                    await asyncio.sleep(phase)
                if args.erg is not None:
                    commands.append(await control(client, f"erg {args.erg} W",
                                                  ftms.cmd_set_target_power(args.erg)))
                    await asyncio.sleep(phase)
        finally:
            if args.control and client.is_connected:
                # Toujours relâcher la résistance en partant, même après une interruption.
                commands.append(await control(client, "sim grade 0% (relâche)",
                                              ftms.cmd_set_sim_params(0.0)))
                # Puis rendre le contrôle FTMS, pour qu'une autre application puisse le prendre.
                commands.append(await control(client, "reset (contrôle rendu)", ftms.cmd_reset()))
            report["commands"] = commands

    report["indoor_bike_data_rate"] = rate_stats(ibd_times)
    report["hr_rate"] = rate_stats(hr_times)
    report["samples"] = samples
    log.info("Fréquence Indoor Bike Data : %s", report["indoor_bike_data_rate"])
    save_report("trainer", report)


# --- click ----------------------------------------------------------------------------

async def cmd_click(args: argparse.Namespace) -> None:
    if args.address or args.name:
        dev = await find_device(args.name, args.address, args.timeout)
    else:
        log.info("Recherche du Zwift Click (appuyez sur un bouton : LED bleue clignotante)…")
        dev = await find_device(zwift_click.CLICK_NAME, None, args.timeout)

    report: dict = {"device": {"name": dev.name, "address": dev.address},
                    "messages": [], "events": [], "sync_tx": []}
    classifier = zwift_click.PressClassifier()
    type_counts: dict[str, int] = {}
    t0 = time.monotonic()

    def on_async(_ch, data: bytearray) -> None:
        t = time.monotonic()
        msg_type, fields = zwift_click.parse_async(bytes(data))
        key = f"0x{msg_type:02x}"
        type_counts[key] = type_counts.get(key, 0) + 1
        if len(report["messages"]) < 3000:
            report["messages"].append({"t": round(t - t0, 3), "type": key, "raw": data.hex(),
                                       "fields": fields})
        if msg_type == zwift_click.MSG_BATTERY_LEVEL:
            log.info("Batterie : %s %%", fields.get(2))
            return
        buttons = zwift_click.parse_click_buttons(bytes(data))
        if buttons is None:
            log.debug("Message %s %s", key, data.hex())
            return
        for ev in classifier.feed(buttons, t):
            report["events"].append({"t": round(t - t0, 3), "event": ev.value})
            log.info(">>> %s", ev.value)

    def on_sync_tx(_ch, data: bytearray) -> None:
        report["sync_tx"].append(data.hex())
        log.info("SYNC_TX : %s (%r)", data.hex(), bytes(data[:8]))

    async with BleakClient(dev, timeout=args.timeout) as client:
        report["gatt"] = dump_gatt(client)
        await client.start_notify(zwift_click.ZWIFT_ASYNC, on_async)
        await client.start_notify(zwift_click.ZWIFT_SYNC_TX, on_sync_tx)
        if has_char(client, zwift_click.ZWIFT_UNKNOWN_6):
            await client.start_notify(zwift_click.ZWIFT_UNKNOWN_6,
                                      lambda _c, d: log.debug("UNKNOWN_6 : %s", d.hex()))
        log.info("Handshake : envoi de %r", zwift_click.RIDE_ON)
        await client.write_gatt_char(zwift_click.ZWIFT_SYNC_RX, zwift_click.RIDE_ON, response=True)
        log.info("Prêt. Testez : appuis courts (< 0,5 s) et longs (≥ 0,9 s) sur + et −, %.0f s.",
                 args.duration)
        await asyncio.sleep(args.duration)

    report["message_type_counts"] = type_counts
    save_report("click", report)


# --- point d'entrée -------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="openride-ble-diag", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--timeout", type=float, default=20.0, help="délai de recherche/connexion (s)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("scan", help="lister les appareils BLE visibles")

    t = sub.add_parser("trainer", help="diagnostic FTMS du home trainer")
    t.add_argument("--name", default="HomeTrainer", help="partie du nom annoncé (défaut : HomeTrainer)")
    t.add_argument("--address", help="adresse MAC (prioritaire sur --name)")
    t.add_argument("--duration", type=float, default=30.0, help="durée d'écoute (s)")
    t.add_argument("--control", action="store_true",
                   help="prendre le contrôle et tester les commandes")
    t.add_argument("--sim-grade", type=float, default=None, help="pente à tester en SIM (%%)")
    t.add_argument("--erg", type=float, default=None, help="puissance à tester en ERG (W)")

    c = sub.add_parser("click", help="diagnostic du Zwift Click")
    c.add_argument("--name", help="nom annoncé (défaut : Zwift Click)")
    c.add_argument("--address", help="adresse MAC")
    c.add_argument("--duration", type=float, default=60.0, help="durée d'écoute (s)")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("bleak").setLevel(logging.INFO if args.verbose else logging.WARNING)
    handler = {"scan": cmd_scan, "trainer": cmd_trainer, "click": cmd_click}[args.command]
    try:
        asyncio.run(handler(args))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
