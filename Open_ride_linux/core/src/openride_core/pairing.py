"""Appairage côté core (lot N12) : garder dans `~/OpenRide/config.toml` le matériel trouvé.

`openride-core devices --save` recherche les appareils (`tools/devices.py`), fait identifier le
boîtier « + » du Click par un appui, puis écrit le nom et l'adresse du trainer, les deux
boîtiers et la ceinture dans la configuration locale, hors du dépôt. Rien n'est écrit ailleurs
(ni journal, ni dépôt, ni `/tmp`).

L'écriture (`config_edit.py`) garde le fichier tel quel (commentaires, autres sections, clés
inconnues) et ne remplace que les lignes des clés d'appareils ; une copie `config.toml.bak` est
faite avant, et le résultat doit passer `config.validate`, sinon rien n'est écrit.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Awaitable, Callable

from . import config as config_mod
from . import config_edit

log = logging.getLogger("pairing")

IDENTIFY_TIMEOUT_S = 15.0

# Clé de PairedDevices -> (section, clé de config.toml)
CONFIG_TARGETS: dict[str, tuple[str, str]] = {
    "trainer_name": ("trainer", "device_name"),
    "trainer_address": ("drivers", "trainer_address"),
    "click_plus_address": ("drivers", "click_address"),
    "click_minus_address": ("drivers", "click_minus_address"),
    "hr_name": ("drivers", "hr_name"),
    "hr_address": ("drivers", "hr_address"),
}

PlusWaiter = Callable[[list[str], float], Awaitable[str | None]]


class PairingError(Exception):
    """Écriture refusée (valeur invalide, fichier illisible) ; message lisible."""


@dataclass
class PairedDevices:
    trainer_name: str = ""
    trainer_address: str = ""
    click_plus_address: str = ""
    click_minus_address: str = ""
    hr_name: str = ""
    hr_address: str = ""

    def items(self) -> list[tuple[str, str]]:
        return [(f.name, getattr(self, f.name)) for f in fields(self)]


def _rssi(d: dict[str, Any]) -> int:
    return d["rssi"] if d.get("rssi") is not None else -999


def from_inventory(inventory: dict[str, Any], plus_address: str | None = None) -> PairedDevices:
    """Choisit le matériel dans le résultat de `tools.devices.inventory`.

    Trainer FTMS au meilleur RSSI ; Click : `plus_address` (boîtier qui a envoyé « + ») sinon le
    premier trouvé ; ceinture d'abord, montre seulement sans ceinture.
    """
    devices = list(inventory.get("devices", [])) + list(inventory.get("connected", []))

    def best(role: str) -> dict[str, Any] | None:
        cands = [d for d in devices if d.get("role") == role]
        return max(cands, key=_rssi) if cands else None

    out = PairedDevices()
    trainer = best("trainer")
    if trainer:
        out.trainer_name, out.trainer_address = trainer.get("name") or "", trainer["address"].upper()
    clicks: list[str] = []
    for d in devices:
        if d.get("role") == "click" and d["address"].upper() not in clicks:
            clicks.append(d["address"].upper())
    plus = plus_address.upper() if plus_address and plus_address.upper() in clicks else None
    if clicks:
        out.click_plus_address = plus or clicks[0]
        others = [a for a in clicks if a != out.click_plus_address]
        out.click_minus_address = others[0] if others else ""
    hr = best("hr_strap") or best("hr_watch")
    if hr:
        out.hr_name, out.hr_address = hr.get("name") or "", hr["address"].upper()
    return out


# --- écriture de config.toml ------------------------------------------------------------------

def _values(paired: PairedDevices) -> list[tuple[str, str, str]]:
    return [(*CONFIG_TARGETS[name], value) for name, value in paired.items() if value]


def plan(paired: PairedDevices, text: str) -> tuple[str, list[str]]:
    """Texte final et lignes changées ; les valeurs vides ne remplacent rien."""
    return config_edit.plan_text(text, _values(paired))


def save(paired: PairedDevices, path: Path | None = None) -> list[str]:
    """Écrit les appareils dans `path` (défaut : `~/OpenRide/config.toml`) ; renvoie les lignes changées.

    Lève `PairingError` si le fichier final ne passe pas `config.validate` : rien n'est écrit.
    """
    try:
        return config_edit.update_config(path or config_mod.DEFAULT_CONFIG_PATH, _values(paired))
    except config_edit.ConfigEditError as exc:
        raise PairingError(str(exc)) from None


# --- identification du boîtier « + » -----------------------------------------------------------

async def wait_plus_press(addresses: list[str], timeout: float) -> str | None:
    """Se connecte aux boîtiers donnés et renvoie l'adresse de celui qui envoie « + »."""
    from .input_providers import ZwiftClickProvider
    from .zwift_click import InputEvent

    providers = [ZwiftClickProvider(a) for a in addresses]
    tasks = [asyncio.create_task(p.run()) for p in providers]
    try:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            for addr, p in zip(addresses, providers):
                while not p.events.empty():
                    if p.events.get_nowait() in (InputEvent.PLUS_SHORT, InputEvent.PLUS_LONG):
                        return addr
            await asyncio.sleep(0.05)
        return None
    finally:
        for p in providers:
            p.stop()
        await asyncio.wait(tasks, timeout=3.0)
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


# --- recherche et appairage depuis le menu (lot N13, contrat IPC révision 1.2) -----------------

SCAN_TIMEOUT_S = 8.0
SCAN_MAX_ITEMS = 12
SCAN_NAME_MAX = 24
SCAN_ROLES = ("trainer", "click", "hr_strap", "hr_watch")
SCAN_STATES = ("IDLE", "READY")   # recherche et enregistrement hors séance seulement
MAX_SCAN_DATAGRAM = 1400


async def scan_inventory(sim: Any, timeout: float) -> dict[str, Any]:
    """Inventaire de `tools.devices` : Bluetooth simulé si `sim` est donné, sinon BlueZ.

    La recherche prend le verrou BLE commun : pendant que le trainer, le Click ou la ceinture
    cherchent à se (re)connecter, BlueZ refuserait une seconde recherche (InProgress) ; on attend
    donc la fin de leur tentative. Les nouveaux essais (autre application) sont dans `session`.
    """
    from .ble_util import ble_lock
    from .tools import devices as devices_tool

    if sim is not None:
        scanner, connected = devices_tool.sim_sources(sim)
    else:
        scanner, connected = devices_tool.ble_scan, devices_tool.bluez_connected
    async with ble_lock():
        return await devices_tool.inventory(scanner, connected, timeout, {})


def is_in_progress(exc: BaseException) -> bool:
    """BlueZ refuse : une recherche ou une connexion est déjà en cours."""
    return "org.bluez.Error.InProgress" in str(exc)


def scan_error_message(exc: BaseException) -> str:
    """Raison lisible d'un échec de recherche, pour l'écran Appareils."""
    text = str(exc)
    if is_in_progress(exc):
        return ("Bluetooth occupé par une autre recherche (une autre application ?). "
                "Fermez-la puis relancez la recherche.")
    if any(k in text for k in ("NotReady", "NotPowered", "No Bluetooth adapters", "not turned on")):
        return "Bluetooth éteint ou absent : allumez-le puis relancez la recherche."
    return f"Recherche des appareils impossible : {text}"


def configured_addresses(cfg: config_mod.Config) -> set[str]:
    d = cfg.drivers
    return {a.upper() for a in (d.trainer_address, d.click_address, d.click_minus_address, d.hr_address) if a}


def scan_items(inventory: dict[str, Any], configured: set[str]) -> list[dict[str, Any]]:
    """Éléments de `scan_results` : appareils utiles, rôle puis RSSI, au plus 12, noms coupés à 24."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for d in list(inventory.get("devices", [])) + list(inventory.get("connected", [])):
        role, addr = d.get("role"), str(d.get("address", "")).upper()
        if role not in SCAN_ROLES or not addr or addr in seen:
            continue
        seen.add(addr)
        out.append({"role": role, "name": str(d.get("name") or "")[:SCAN_NAME_MAX], "address": addr,
                    "rssi": d.get("rssi"), "configured": addr in configured})
    out.sort(key=lambda it: (SCAN_ROLES.index(it["role"]), -(it["rssi"] if it["rssi"] is not None else -999)))
    return out[:SCAN_MAX_ITEMS]


def scan_results_message(request_cmd_id: int, items: list[dict[str, Any]], done: bool,
                         plus_address: str | None = None, version: int = 1) -> dict[str, Any]:
    """Message `scan_results` tenant en 1 400 octets (éléments en trop retirés par la fin)."""
    import json

    items = list(items)
    while True:
        msg = {"type": "scan_results", "v": version, "request_cmd_id": request_cmd_id, "done": done,
               "items": items, "plus_address": plus_address}
        if len(json.dumps(msg, separators=(",", ":")).encode("utf-8")) <= MAX_SCAN_DATAGRAM or not items:
            return msg
        items = items[:-1]


def paired_from_args(args: dict[str, Any], items: list[dict[str, Any]]) -> PairedDevices:
    """Commande `pair_devices` : adresses choisies (null : valeur actuelle gardée) et noms trouvés."""
    names = {it["address"]: it.get("name", "") for it in items}
    out = PairedDevices()
    for key, field_name in (("trainer", "trainer_address"), ("click_plus", "click_plus_address"),
                            ("click_minus", "click_minus_address"), ("hr", "hr_address")):
        value = args.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            raise PairingError(f"pair_devices : « {key} » doit être une adresse ou null")
        setattr(out, field_name, value.upper())
    if out.trainer_address and names.get(out.trainer_address):
        out.trainer_name = names[out.trainer_address]
    if out.hr_address and names.get(out.hr_address):
        out.hr_name = names[out.hr_address]
    if out.click_plus_address and out.click_plus_address == out.click_minus_address:
        raise PairingError("pair_devices : le même boîtier ne peut pas être à la fois « + » et « − »")
    return out
