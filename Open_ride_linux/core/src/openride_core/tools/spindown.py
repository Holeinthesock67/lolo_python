"""Sonde d'étalonnage du home trainer (lot ET1) : `openride-ble-diag spindown`.

But : savoir, en 5 minutes sur le vélo, si le trainer fait vraiment l'étalonnage FTMS qu'il annonce
(Spin Down Control, opcode 0x13). Cadrage : `plans/CADRAGE_ETALONNAGE_FTMS_2026-11-22.md` des fichiers
du projet. Rien n'est ajouté au jeu tant que la sonde n'a pas répondu.

Déroulé : lecture des capacités (bit `spin_down_control`, compensation d'offset du service Cycling
Power, en lecture seule), prise de contrôle, commande 0x13 « lancer », puis écoute jusqu'au résultat
ou à la fin du délai : réponse du Control Point et vitesses cibles, états 0x14 (« pédalez »,
« arrêtez de pédaler », réussite, échec), Training Status et vitesse du volant. Chaque étape est
écrite en mots pour le cycliste. À la sortie, toujours : Reset, qui rend le contrôle.

Le rapport (JSON) ne garde ni le nom ni l'adresse du trainer.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable

from .. import ftms

SAY_STEPS = {
    "SPIN_DOWN_REQUESTED": "Pédalez pour lancer le volant au-dessus de la vitesse demandée.",
    "STOP_PEDALING": "Arrêtez de pédaler maintenant et laissez le volant ralentir seul.",
    "SUCCESS": "Étalonnage réussi.",
    "ERROR": "Étalonnage en échec (le trainer le signale).",
    "SPEED_TOO_LOW": "Trop lent : accélérez.",
    "SPEED_TOO_HIGH": "Trop vite : ralentissez un peu.",
}


def _has(client: Any, uuid: str) -> bool:
    services = getattr(client, "services", None)
    return services is not None and services.get_characteristic(uuid) is not None


async def probe(client: Any, *, duration_s: float = 90.0, cp_timeout_s: float = 3.0,
                say: Callable[[str], None] = print) -> dict[str, Any]:
    """Sonde sur un client connecté (façon BleakClient). Renvoie le rapport ; `verdict` vaut
    `success`, `error`, `refused`, `not_announced`, `no_response` ou `timeout`."""
    t0 = time.monotonic()
    report: dict[str, Any] = {"events": [], "commands": []}
    cp_event = asyncio.Event()
    done = asyncio.Event()
    last_cp: dict[str, Any] = {}
    speeds: list[float] = []

    def event(kind: str, **fields: Any) -> None:
        report["events"].append({"t": round(time.monotonic() - t0, 2), "kind": kind, **fields})

    def on_cp(_ch: Any, data: bytearray) -> None:
        raw = bytes(data)
        resp = ftms.parse_control_response(raw)
        last_cp.clear()
        last_cp.update(raw=raw.hex(), result=resp.result_name if resp else None,
                       request_op=f"0x{resp.request_op:02x}" if resp else None)
        targets = ftms.parse_spin_down_targets(raw)
        if targets is not None:
            last_cp["target_kmh"] = list(targets)
        cp_event.set()

    def on_status(_ch: Any, data: bytearray) -> None:
        raw = bytes(data)
        name = ftms.parse_spin_down_status(raw)
        if name is None:
            event("machine_status", raw=raw.hex())
            return
        event("spin_down_status", status=name)
        if name in SAY_STEPS:
            say(SAY_STEPS[name])
        if name in ("SUCCESS", "ERROR") or name.startswith("UNKNOWN"):
            report["final_status"] = name
            done.set()

    def on_training(_ch: Any, data: bytearray) -> None:
        name = ftms.parse_training_status(bytes(data))
        event("training_status", status=name)
        if name in SAY_STEPS:
            say(SAY_STEPS[name])

    def on_ibd(_ch: Any, data: bytearray) -> None:
        v = ftms.parse_indoor_bike_data(bytes(data)).speed_kmh
        if v is not None:
            speeds.append(float(v))

    async def control(label: str, payload: bytes) -> dict[str, Any]:
        cp_event.clear()
        entry: dict[str, Any] = {"command": label, "sent": payload.hex(), "response": None}
        try:
            await client.write_gatt_char(ftms.CONTROL_POINT, payload, response=True)
            await asyncio.wait_for(cp_event.wait(), timeout=cp_timeout_s)
            entry["response"] = dict(last_cp)
        except asyncio.TimeoutError:
            pass
        except Exception as exc:  # noqa: BLE001 : erreur ATT ou liaison, notée telle quelle
            entry["error"] = str(exc)
        report["commands"].append(entry)
        return entry

    # 1. Capacités (lecture seule)
    announced = None
    if _has(client, ftms.FEATURE):
        feats = ftms.parse_features(bytes(await client.read_gatt_char(ftms.FEATURE)))
        announced = "spin_down_control" in feats.target
        report["targets_announced"] = feats.target
    report["spin_down_announced"] = announced
    if _has(client, ftms.CYCLING_POWER_FEATURE):
        report["cycling_power"] = ftms.parse_cp_offset_features(
            bytes(await client.read_gatt_char(ftms.CYCLING_POWER_FEATURE)))
    else:
        report["cycling_power"] = None
    if announced is False:
        say("Le trainer n'annonce pas l'étalonnage FTMS : rien à essayer.")
        report["verdict"] = "not_announced"
        return report

    # 2. Abonnements, contrôle et commande 0x13
    await client.start_notify(ftms.CONTROL_POINT, on_cp)
    if _has(client, ftms.MACHINE_STATUS):
        await client.start_notify(ftms.MACHINE_STATUS, on_status)
    if _has(client, ftms.TRAINING_STATUS):
        await client.start_notify(ftms.TRAINING_STATUS, on_training)
    if _has(client, ftms.INDOOR_BIKE_DATA):
        await client.start_notify(ftms.INDOOR_BIKE_DATA, on_ibd)
    try:
        ctrl = await control("request_control", ftms.cmd_request_control())
        if (ctrl.get("response") or {}).get("result") != "SUCCESS":
            say("Le trainer refuse le contrôle : couper Zwift, la montre ou le téléphone, puis recommencer.")
            report["verdict"] = "refused"
            return report
        sd = await control("spin_down_start", ftms.cmd_spin_down(True))
        resp = sd.get("response")
        if resp is None:
            say("Pas de réponse du trainer à l'étalonnage.")
            report["verdict"] = "no_response"
            return report
        if resp.get("result") != "SUCCESS":
            say(f"Le trainer refuse l'étalonnage ({resp.get('result')}) : il l'annonce sans le faire.")
            report["verdict"] = "refused"
            return report
        if "target_kmh" in resp:
            lo, hi = resp["target_kmh"]
            report["target_kmh"] = [lo, hi]
            say(f"Étalonnage accepté. Pédalez jusqu'à {hi:.0f} km/h environ (au moins {lo:.0f} km/h), "
                "puis attendez la consigne « Arrêtez de pédaler ».")
        else:
            say("Étalonnage accepté, sans vitesse cible : pédalez vers 35 km/h et attendez la consigne.")
        try:
            await asyncio.wait_for(done.wait(), timeout=duration_s)
        except asyncio.TimeoutError:
            say(f"Pas de résultat en {duration_s:.0f} s.")
            report["verdict"] = "timeout"
            return report
        report["verdict"] = "success" if report.get("final_status") == "SUCCESS" else "error"
        return report
    finally:
        if speeds:
            report["speed_kmh"] = {"max": round(max(speeds), 1), "last": round(speeds[-1], 1), "count": len(speeds)}
        if getattr(client, "is_connected", True):
            await control("reset (contrôle rendu)", ftms.cmd_reset())
        say("Contrôle du trainer rendu.")
