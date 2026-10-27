"""Inventaire des appareils Bluetooth utiles à OpenRide (lot M3) : `openride-core devices`.

    openride-core devices [--timeout S] [--json] [--all] [--config FICHIER]
                          [--sim-scenario NOM|FICHIER] [--save [--yes]]

Recherche les appareils qui s'annoncent (8 s par défaut), les classe et propose le bloc
`[drivers]` de `config.toml` à recopier. Sans `--save` : aucune connexion aux appareils, aucune
écriture de `config.toml`. Avec `--save` (lot N12, `pairing.py`) : demande un appui sur « + »
pour reconnaître ce boîtier du Click (15 s au plus), montre les changements, demande
confirmation (sauf `--yes`) et les écrit dans la configuration (`--config` ou
`~/OpenRide/config.toml`), avec une copie `config.toml.bak`. Les appareils que BlueZ garde connectés (donc muets en recherche : Click resté
accroché, trainer réservé) sont listés à part.

Rôles : `trainer` (service FTMS 0x1826), `click` (nom « Zwift Click » ou service Zwift, comme
`zwift_click.py`), `hr_strap` et `hr_watch` (service 0x180D ; montre si le nom ressemble à une
montre, `hr_monitor.WATCH_NAME_HINTS`), `other` (affiché seulement avec `--all`).

Clés de la sortie `--json` (stables) :
    source ("ble" | "sim"), timeout_s,
    devices (liste de {role, name, address, rssi, services}),
    connected (liste de {role, name, address, advice}),
    proposed ({trainer_address, click_address, hr_address} : adresse ou null ;
              click_other_address : second boîtier du Click ou null),
    differences (liste de {key, address, issue : "configured_absent" | "present_not_configured"}).
`services` : noms courts des services reconnus (« FTMS », « Heart Rate », « Battery », « Zwift »).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from .. import ftms, zwift_click
from ..hr_monitor import looks_like_watch

DEFAULT_TIMEOUT_S = 8.0
ROLES = ("trainer", "click", "hr_strap", "hr_watch", "other")
SERVICE_NAMES = {ftms.FTMS_SERVICE: "FTMS", ftms.HR_SERVICE: "Heart Rate",
                 ftms.BATTERY_SERVICE: "Battery", zwift_click.ZWIFT_SERVICE: "Zwift"}
CONFIG_KEYS = ("trainer_address", "click_address", "hr_address")


@dataclass
class Found:
    name: str
    address: str
    rssi: int | None = None
    uuids: list[str] = field(default_factory=list)


@dataclass
class Device:
    role: str
    name: str
    address: str
    rssi: int | None
    services: list[str]


Scanner = Callable[[float], Awaitable[list[Found]]]
Connected = Callable[[], Awaitable[list[Found]]]


def classify(name: str | None, uuids: list[str]) -> str:
    low = [u.lower() for u in uuids]
    if ftms.FTMS_SERVICE in low:
        return "trainer"
    if zwift_click.ZWIFT_SERVICE in low or zwift_click.CLICK_NAME.lower() in (name or "").lower():
        return "click"
    if ftms.HR_SERVICE in low:
        return "hr_watch" if looks_like_watch(name) else "hr_strap"
    return "other"


def to_device(f: Found) -> Device:
    services = [SERVICE_NAMES[u.lower()] for u in f.uuids if u.lower() in SERVICE_NAMES]
    return Device(classify(f.name, f.uuids), f.name or "", f.address.upper(), f.rssi,
                  sorted(set(services)))


# --- recherche réelle -------------------------------------------------------------------------

async def ble_scan(timeout: float) -> list[Found]:
    """Recherche BLE réelle (BleakScanner), sans connexion."""
    from bleak import BleakScanner

    found = await BleakScanner.discover(timeout=timeout, return_adv=True)
    return [Found(dev.name or adv.local_name or "", dev.address, getattr(adv, "rssi", None),
                  list(getattr(adv, "service_uuids", None) or ()))
            for dev, adv in found.values()]


async def bluez_connected() -> list[Found]:
    """Appareils connus de BlueZ et connectés (lecture D-Bus, sans connexion nouvelle)."""
    try:
        from dbus_fast import BusType
        from dbus_fast.aio import MessageBus

        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        try:
            intro = await bus.introspect("org.bluez", "/")
            om = bus.get_proxy_object("org.bluez", "/", intro).get_interface(
                "org.freedesktop.DBus.ObjectManager")
            objects = await om.call_get_managed_objects()
        finally:
            bus.disconnect()
    except Exception:   # BlueZ absent, droits : liste vide
        return []
    out = []
    for ifaces in objects.values():
        dev = ifaces.get("org.bluez.Device1")
        if not dev or "Address" not in dev or not (dev.get("Connected") and dev["Connected"].value):
            continue
        name = str(dev["Alias"].value if "Alias" in dev else dev["Name"].value if "Name" in dev else "")
        uuids = [str(u) for u in (dev["UUIDs"].value if "UUIDs" in dev else [])]
        out.append(Found(name, str(dev["Address"].value), None, uuids))
    return out


# --- Bluetooth simulé -------------------------------------------------------------------------

def sim_sources(world: Any) -> tuple[Scanner, Connected]:
    """Recherche dans le monde simulé : tous les appareils annoncés pendant `timeout`."""
    async def scan(timeout: float) -> list[Found]:
        seen: dict[str, Found] = {}
        with world.discovery():   # InProgress si un pilote cherche au même moment, comme BlueZ
            end = world.now() + timeout
            while True:
                for d in world.devices:
                    if d.advertising():
                        seen[d.address] = Found(d.name, d.address, getattr(d, "rssi", -60), list(d.uuids))
                if world.now() >= end:
                    return list(seen.values())
                await asyncio.sleep(0.05)

    async def connected() -> list[Found]:
        return [Found(d.name, d.address, None, list(d.uuids)) for d in world.devices
                if d.client is not None]
    return scan, connected


# --- inventaire -------------------------------------------------------------------------------

def propose(devices: list[Device]) -> dict[str, str | None]:
    def best(role: str) -> Device | None:
        cands = [d for d in devices if d.role == role]
        return max(cands, key=lambda d: d.rssi if d.rssi is not None else -999) if cands else None
    trainer = best("trainer")
    hr = best("hr_strap") or best("hr_watch")   # la ceinture d'abord, comme hr_monitor
    clicks = sorted((d for d in devices if d.role == "click"), key=lambda d: d.address)
    return {"trainer_address": trainer.address if trainer else None,
            "click_address": clicks[0].address if clicks else None,
            "hr_address": hr.address if hr else None,
            "click_other_address": clicks[1].address if len(clicks) > 1 else None}


def differences(configured: dict[str, str], devices: list[Device],
                proposed: dict[str, str | None]) -> list[dict[str, str]]:
    present = {d.address for d in devices}
    out = []
    for key in CONFIG_KEYS:
        conf = (configured.get(key) or "").upper()
        if conf and conf not in present:
            out.append({"key": key, "address": conf, "issue": "configured_absent"})
        prop = proposed.get(key)
        others = {prop, proposed.get("click_other_address")} if key == "click_address" else {prop}
        if prop and conf not in others:
            out.append({"key": key, "address": prop, "issue": "present_not_configured"})
    return out


async def inventory(scanner: Scanner, connected: Connected, timeout: float,
                    configured: dict[str, str], show_all: bool = False,
                    source: str = "ble") -> dict[str, Any]:
    found = await scanner(timeout)
    devices = sorted((to_device(f) for f in found),
                     key=lambda d: (ROLES.index(d.role), -(d.rssi if d.rssi is not None else -999)))
    seen = {d.address for d in devices}
    linked = [to_device(f) for f in await connected() if f.address.upper() not in seen]
    useful = [d for d in devices if d.role != "other"]
    proposed = propose(useful + [d for d in linked if d.role != "other"])
    return {
        "source": source,
        "timeout_s": timeout,
        "devices": [asdict(d) for d in (devices if show_all else useful)],
        "connected": [{"role": d.role, "name": d.name, "address": d.address,
                       "advice": _advice(d.role)} for d in linked
                      if show_all or d.role != "other"],
        "proposed": proposed,
        "differences": differences(configured, useful + linked, proposed),
    }


def _advice(role: str) -> str:
    if role == "trainer":
        return "trainer réservé : openride-core release-trainer"
    if role == "click":
        return "Click resté accroché : bluetoothctl disconnect <adresse>"
    return "connecté par une autre application"


def format_text(r: dict[str, Any]) -> str:
    lines = [f"Appareils trouvés ({'Bluetooth simulé' if r['source'] == 'sim' else 'Bluetooth'}, "
             f"{r['timeout_s']:.0f} s) :"]
    if not r["devices"]:
        lines.append("  aucun (appareils éteints ou endormis ? pédaler, appuyer sur le Click)")
    for d in r["devices"]:
        rssi = f"{d['rssi']} dBm" if d["rssi"] is not None else "?"
        lines.append(f"  {d['role']:<9} {d['name'] or '?':<24} {d['address']}  RSSI {rssi:>8}  "
                     f"{', '.join(d['services']) or '-'}")
    if r["connected"]:
        lines.append("Connectés à BlueZ mais muets :")
        for d in r["connected"]:
            lines.append(f"  {d['role']:<9} {d['name'] or '?':<24} {d['address']}  ({d['advice']})")
    p = r["proposed"]
    lines.append("")
    lines.append("Bloc proposé pour ~/OpenRide/config.toml :")
    lines.append("[drivers]")
    for key in CONFIG_KEYS:
        lines.append(f'{key} = "{p[key]}"' if p[key] else f'# {key} : aucun appareil trouvé')
    if p.get("click_other_address"):
        lines.append(f"# second boîtier du Click : {p['click_other_address']} (trouvé seul)")
    if r["differences"]:
        lines.append("")
        lines.append("Différences avec la configuration :")
        for d in r["differences"]:
            what = ("configuré mais absent" if d["issue"] == "configured_absent"
                    else "présent mais non configuré")
            lines.append(f"  {d['key']} = {d['address']} : {what}")
    return "\n".join(lines)


def save_devices(result: dict[str, Any], config_path: Path | None, assume_yes: bool,
                 plus_waiter: Any, ask: Callable[[str], str] = input) -> int:
    """Suite de `--save` : identification du « + », différences, confirmation, écriture."""
    from .. import pairing

    clicks = sorted({d["address"] for d in result["devices"] + result["connected"] if d["role"] == "click"})
    plus = None
    if len(clicks) > 1:
        print("Appuyez sur le bouton + du Click…", flush=True)
        try:
            plus = asyncio.run(plus_waiter(clicks, pairing.IDENTIFY_TIMEOUT_S)) if plus_waiter else None
        except Exception as exc:   # Bluetooth indisponible pendant l'identification
            print(f"identification impossible : {exc}")
        if plus is None:
            print("Aucun appui reçu : le premier boîtier trouvé est pris pour le « + ».")
        else:
            print(f"Boîtier « + » : {plus}")
    paired = pairing.from_inventory(result, plus)
    path = config_path or pairing.config_mod.DEFAULT_CONFIG_PATH
    try:
        old = path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError as exc:
        print(f"openride-core devices : {path} : lecture impossible : {exc}", file=sys.stderr)
        return 1
    _, changes = pairing.plan(paired, old)
    if not changes:
        print(f"Aucun changement : {path} contient déjà ces appareils.")
        return 0
    print(f"Changements prévus dans {path} :")
    for line in changes:
        print(f"  {line}")
    if not assume_yes and ask("Enregistrer ? [o/N] ").strip().lower() not in ("o", "oui", "y", "yes"):
        print("Rien n'a été écrit.")
        return 1
    try:
        pairing.save(paired, path)
    except pairing.PairingError as exc:
        print(f"openride-core devices : {exc}", file=sys.stderr)
        return 1
    print(f"Enregistré dans {path} (copie de l'ancien fichier : {path.name}.bak).")
    return 0


def run(timeout: float = DEFAULT_TIMEOUT_S, as_json: bool = False, config_path: Path | None = None,
        sim_scenario: str | None = None, show_all: bool = False,
        scanner: Scanner | None = None, connected: Connected | None = None,
        save: bool = False, assume_yes: bool = False, plus_waiter: Any = None) -> int:
    from .. import config as config_mod
    from ..sim_scenarios import SimScenarioError, build_world, load_scenario

    try:
        cfg = config_mod.load(config_path)
    except config_mod.ConfigError as exc:
        print(f"openride-core devices : configuration invalide : {exc}", file=sys.stderr)
        return 1
    d = cfg.drivers
    configured = {"trainer_address": d.trainer_address, "click_address": d.click_address,
                  "hr_address": d.hr_address}

    async def go() -> dict[str, Any]:
        nonlocal scanner, connected
        source = "ble"
        if sim_scenario:
            world = build_world(load_scenario(sim_scenario), name=str(sim_scenario))
            world.now()
            scanner, connected = sim_sources(world)
            source = "sim"
        return await inventory(scanner or ble_scan, connected or bluez_connected, timeout,
                               configured, show_all, source)
    try:
        result = asyncio.run(go())
    except SimScenarioError as exc:
        print(f"openride-core devices : scénario de simulation refusé : {exc}", file=sys.stderr)
        return 1
    except Exception as exc:   # Bluetooth éteint, BlueZ absent
        print(f"openride-core devices : recherche impossible : {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if as_json else format_text(result))
    if not save:
        return 0
    if plus_waiter is None and not sim_scenario:
        from ..pairing import wait_plus_press
        plus_waiter = wait_plus_press
    print()
    return save_devices(result, config_path, assume_yes, plus_waiter)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="openride-core devices")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    p.add_argument("--json", action="store_true")
    p.add_argument("--all", action="store_true")
    p.add_argument("--config", type=Path)
    p.add_argument("--sim-scenario")
    p.add_argument("--save", action="store_true")
    p.add_argument("--yes", action="store_true")
    a = p.parse_args(argv)
    return run(a.timeout, a.json, a.config, a.sim_scenario, a.all, save=a.save, assume_yes=a.yes)


if __name__ == "__main__":
    raise SystemExit(main())
