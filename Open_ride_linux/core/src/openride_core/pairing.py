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
import time
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Awaitable, Callable

from . import config as config_mod
from . import config_edit

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
