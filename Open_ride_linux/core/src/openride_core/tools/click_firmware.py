"""Comparaison du Zwift Click avant et après une mise à jour du firmware.

    python -m openride_core.tools.click_firmware releve --etiquette avant_maj    # 1 min
    python -m openride_core.tools.click_firmware capture --etiquette avant_maj   # relevé + recette 30 min
    python -m openride_core.tools.click_firmware capture --etiquette apres_maj
    python -m openride_core.tools.click_firmware compare                         # dernier avant / dernier après
    python -m openride_core.tools.click_firmware compare DOSSIER_AVANT DOSSIER_APRES

`releve` cherche les boîtiers qui s'annoncent (un appui réveille chacun), se connecte à chacun tour à
tour et note : publicité (nom, services, données constructeur), service Device Information (fabricant,
modèle, versions du firmware, du matériel et du logiciel ; le numéro de série n'est pas lu), batterie,
table GATT complète (services, caractéristiques, propriétés), réponse au « RideOn » et types de
messages des premières secondes. Écrit `profil_ble.json` et `profil_ble.txt`.

`capture` fait le relevé, puis la recette guidée du lot X8 (`click_recette`, 30 min par défaut) dans
`recette/`, avec en plus un relevé trame par trame : `trames.csv` (instant, boîtier, type, longueur,
octets) et `trames_stats.json` (intervalle entre trames, longueurs par type, part de trames répétées).

`compare` met les deux captures côte à côte, boîtier par boîtier (gauche, droit) : versions, boutons
reconnus, silences et coupures, délai des appuis, rythme des trames ; sort un verdict (MIEUX, PAREIL,
MOINS BIEN) et signale tout changement du protocole BLE (table GATT, types ou longueurs de messages,
réponse au RideOn, touches inconnues). Écrit `comparaison.txt` et `comparaison.json` dans le dossier
« après ». La sortie n'affiche que le côté des boîtiers, pas leur adresse.

Dossiers : `~/OpenRide/Logs/click_<date>_<heure>_<etiquette>/`. Les adresses des boîtiers ne sont
écrites que dans ces dossiers locaux. Fermer OpenRide et couper le Bluetooth du téléphone (Zwift
Companion) avant chaque relevé : un boîtier relié ailleurs ne s'annonce pas.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import zwift_click
from ..ftms import uuid16
from . import click_recette as cr

LOGS = Path.home() / "OpenRide" / "Logs"
PREFIX = "click_"
SCAN_S = 20.0
LISTEN_S = 5.0
DIS = {  # Device Information (0x180A), sans le numéro de série (0x2A25)
    "fabricant": uuid16(0x2A29), "modele": uuid16(0x2A24), "firmware": uuid16(0x2A26),
    "materiel": uuid16(0x2A27), "logiciel": uuid16(0x2A28),
}
BATTERY_LEVEL = uuid16(0x2A19)
RATE_CHANGE = 0.30        # écart relatif du rythme des trames signalé comme changement de protocole
DELAY_WORSE_S = 0.30      # délai médian des appuis plus long de 0,3 s : moins bien
SIDES = ("gauche", "droit")


# --- Relevé BLE -----------------------------------------------------------------------------------

Advert = dict[str, Any]   # {address, name, rssi, service_uuids, manufacturer_data {id: hex}}


async def bleak_scan(timeout: float) -> list[Advert]:
    from bleak import BleakScanner

    found = await BleakScanner.discover(timeout=timeout, return_adv=True)
    out = []
    for dev, ad in found.values():
        out.append({"address": str(dev.address).upper(), "name": dev.name or ad.local_name or "",
                    "rssi": ad.rssi, "service_uuids": sorted(ad.service_uuids or ()),
                    "manufacturer_data": {str(k): bytes(v).hex() for k, v in (ad.manufacturer_data or {}).items()}})
    return out


def bleak_client(address: str) -> Any:
    from bleak import BleakClient

    return BleakClient(address, timeout=15.0)


def is_click(ad: Advert) -> bool:
    return (zwift_click.CLICK_NAME.lower() in (ad.get("name") or "").lower()
            or zwift_click.ZWIFT_SERVICE in ad.get("service_uuids", ()))


def _text(raw: bytes) -> str:
    return bytes(raw).decode("utf-8", "replace").strip("\x00 ").strip()


async def profile_unit(ad: Advert, client_factory: Callable[[str], Any], listen_s: float = LISTEN_S) -> dict[str, Any]:
    """Se connecte à un boîtier et relève ce qui pourrait changer avec le firmware."""
    unit: dict[str, Any] = {**ad, "dis": {}, "battery_pct": None, "gatt": [], "rideon_reply_hex": None,
                            "first_types": {}, "first_lengths": {}, "notifications": 0, "error": None}
    replies: list[bytes] = []

    def on_async(_c: Any, data: bytearray) -> None:
        unit["notifications"] += 1
        key = f"0x{data[0]:02X}" if data else "vide"
        unit["first_types"][key] = unit["first_types"].get(key, 0) + 1
        lens = unit["first_lengths"].setdefault(key, [])
        if len(data) not in lens:
            lens.append(len(data))
            lens.sort()

    try:
        async with client_factory(ad["address"]) as client:
            for svc in client.services:
                unit["gatt"].append({"uuid": str(svc.uuid), "characteristics": sorted(
                    ({"uuid": str(ch.uuid), "properties": sorted(ch.properties)} for ch in svc.characteristics),
                    key=lambda c: (c["uuid"], c["properties"]))})
            unit["gatt"].sort(key=lambda s: s["uuid"])
            chars = {c["uuid"] for s in unit["gatt"] for c in s["characteristics"]}
            for key, uuid in DIS.items():
                if uuid in chars:
                    try:
                        unit["dis"][key] = _text(await client.read_gatt_char(uuid))
                    except Exception as exc:   # lecture refusée : notée, le relevé continue
                        unit["dis"][key] = f"illisible ({exc})"
            if BATTERY_LEVEL in chars:
                try:
                    unit["battery_pct"] = int((await client.read_gatt_char(BATTERY_LEVEL))[0])
                except Exception:
                    pass
            if zwift_click.ZWIFT_ASYNC in chars:
                await client.start_notify(zwift_click.ZWIFT_ASYNC, on_async)
            if zwift_click.ZWIFT_SYNC_TX in chars:
                await client.start_notify(zwift_click.ZWIFT_SYNC_TX, lambda _c, d: replies.append(bytes(d)))
            if zwift_click.ZWIFT_SYNC_RX in chars:
                await client.write_gatt_char(zwift_click.ZWIFT_SYNC_RX, zwift_click.RIDE_ON, response=True)
            await asyncio.sleep(listen_s)
            unit["rideon_reply_hex"] = replies[0].hex() if replies else None
    except Exception as exc:
        unit["error"] = f"{type(exc).__name__}: {exc}"
    return unit


async def releve(scan: Callable[[float], Awaitable[list[Advert]]] = bleak_scan,
                 client_factory: Callable[[str], Any] = bleak_client, scan_s: float = SCAN_S,
                 listen_s: float = LISTEN_S, say: Callable[[str], None] = print) -> dict[str, Any]:
    say(f"Appuie sur un bouton de CHAQUE boîtier du Click (recherche pendant {scan_s:.0f} s)…")
    ads = [a for a in await scan(scan_s) if is_click(a)]
    say(f"{len(ads)} boîtier(s) trouvé(s)" + ("" if len(ads) >= 2 else
        " : si un boîtier manque, il est peut-être relié au téléphone ou à OpenRide"))
    units = []
    for i, ad in enumerate(sorted(ads, key=lambda a: a["address"]), 1):
        say(f"Relevé du boîtier {i}/{len(ads)} (garde-le réveillé : un appui de temps en temps)…")
        units.append(await profile_unit(ad, client_factory, listen_s))
    return {"date": datetime.now().isoformat(timespec="seconds"), "units": units}


def profile_text(profile: dict[str, Any]) -> str:
    lines = [f"Relevé BLE du Zwift Click ({profile['date']})", ""]
    if not profile["units"]:
        lines.append("Aucun boîtier trouvé.")
    for i, u in enumerate(profile["units"], 1):
        dis = u["dis"]
        lines.append(f"Boîtier {i} : {u.get('name') or '?'}, firmware {dis.get('firmware', 'non lu')}, "
                     f"modèle {dis.get('modele', '?')}, matériel {dis.get('materiel', '?')}, "
                     f"logiciel {dis.get('logiciel', '?')}, batterie {u['battery_pct'] if u['battery_pct'] is not None else '?'} %")
        if u["error"]:
            lines.append(f"  ERREUR : {u['error']}")
        lines.append(f"  services : {len(u['gatt'])}, caractéristiques : {sum(len(s['characteristics']) for s in u['gatt'])}")
        lines.append(f"  réponse au RideOn : {u['rideon_reply_hex'] or 'aucune'}")
        lines.append(f"  messages des {u['notifications']} premières notifications : "
                     + (", ".join(f"{k} ×{v}" for k, v in sorted(u["first_types"].items())) or "aucun"))
    return "\n".join(lines) + "\n"


# --- Relevé trame par trame pendant la recette ----------------------------------------------------

class TracingRecorder(cr.Recorder):
    """Enregistreur de la recette qui garde aussi chaque trame (instant, type, longueur, octets)."""

    def __init__(self, clock: Callable[[], float]) -> None:
        super().__init__(clock)
        self.frames: list[tuple[float, str, bytes]] = []

    def raw(self, address: str, data: bytes) -> None:
        self.frames.append((self.t(), address, bytes(data)))
        super().raw(address, data)

    def write_extra(self, out: Path) -> None:
        with (out / "trames.csv").open("w", encoding="utf-8") as fh:
            fh.write("t_s;boitier;type;longueur;octets\n")
            for t, address, data in self.frames:
                kind = f"0x{data[0]:02X}" if data else "vide"
                fh.write(f"{t:.3f};{address};{kind};{len(data)};{data.hex()}\n")
        sides = {a: u.side for a, u in self.units.items()}
        stats = {a: {"side": sides.get(a, "?"), **frame_stats([(t, d) for t, ad, d in self.frames if ad == a])}
                 for a in sides if a != "?"}
        (out / "trames_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


def frame_stats(frames: list[tuple[float, bytes]]) -> dict[str, Any]:
    """Intervalle entre trames (ms), types et longueurs, part de trames identiques à la précédente."""
    gaps = [(b[0] - a[0]) * 1000.0 for a, b in zip(frames, frames[1:])]
    types: dict[str, int] = {}
    lengths: dict[str, list[int]] = {}
    repeats = 0
    for i, (_, data) in enumerate(frames):
        key = f"0x{data[0]:02X}" if data else "vide"
        types[key] = types.get(key, 0) + 1
        if len(data) not in lengths.setdefault(key, []):
            lengths[key].append(len(data))
        if i and data == frames[i - 1][1]:
            repeats += 1
    return {"frames": len(frames), "interval_ms_p50": round(_pct(gaps, 0.5), 1),
            "interval_ms_p95": round(_pct(gaps, 0.95), 1), "interval_ms_max": round(max(gaps, default=0.0), 1),
            "types": types, "lengths": {k: sorted(v) for k, v in lengths.items()},
            "repeat_ratio": round(repeats / len(frames), 3) if frames else 0.0}


# --- Comparaison ----------------------------------------------------------------------------------

def load_capture(folder: Path) -> dict[str, Any]:
    """Une capture : relevé BLE, rapport de la recette et statistiques des trames, par côté."""
    def read(p: Path) -> Any:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    profile = read(folder / "profil_ble.json") or {"units": []}
    report = read(folder / "recette" / "rapport.json")
    stats = read(folder / "recette" / "trames_stats.json") or {}
    side_of = {u["address"]: u["side"] for u in (report or {}).get("units", [])}
    for a, s in stats.items():
        side_of.setdefault(a, s.get("side", "?"))
    sides: dict[str, dict[str, Any]] = {}
    for u in profile["units"]:
        sides.setdefault(side_of.get(u["address"], "?"), {})["profile"] = u
    for u in (report or {}).get("units", []):
        sides.setdefault(u["side"], {})["recette"] = u
        sides[u["side"]]["address"] = u["address"]
    for a, s in stats.items():
        sides.setdefault(side_of.get(a, "?"), {})["trames"] = s
    # Un relevé dont le boîtier n'a pas été vu par la recette : côté déduit de l'autre boîtier.
    if "?" in sides and "profile" in sides["?"] and len([k for k in sides if k in SIDES]) == 1:
        other = next(k for k in SIDES if k not in sides)
        sides[other] = sides.pop("?")
    steps = (report or {}).get("steps", [])
    return {"folder": str(folder), "profile": profile, "report": report, "sides": sides, "steps": steps}


def _gatt_map(unit: dict[str, Any] | None) -> dict[str, list[str]]:
    if not unit:
        return {}
    return {f"{s['uuid']}/{c['uuid']}": c["properties"] for s in unit.get("gatt", []) for c in s["characteristics"]}


def _median_delay(steps: list[dict[str, Any]], side: str | None = None) -> float | None:
    d = [s["delay_s"] for s in steps if s.get("ok") and s.get("delay_s") is not None
         and (side is None or s.get("side") == side)]
    return round(statistics.median(d), 2) if d else None


def compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    protocol: list[str] = []
    better: list[str] = []
    worse: list[str] = []
    rows: list[dict[str, Any]] = []
    for side in SIDES:
        b, a = before["sides"].get(side, {}), after["sides"].get(side, {})
        if not b and not a:
            continue
        bp, ap = b.get("profile"), a.get("profile")
        br, ar = b.get("recette") or {}, a.get("recette") or {}
        bt, at = b.get("trames") or {}, a.get("trames") or {}
        row: dict[str, Any] = {"side": side,
                               "firmware": [(bp or {}).get("dis", {}).get("firmware"), (ap or {}).get("dis", {}).get("firmware")],
                               "battery_pct": [br.get("battery_pct", (bp or {}).get("battery_pct")),
                                               ar.get("battery_pct", (ap or {}).get("battery_pct"))]}
        if not a:
            worse.append(f"boîtier {side} absent après la mise à jour")
        if bp and ap:
            for key in ("modele", "materiel", "logiciel"):
                if bp["dis"].get(key) != ap["dis"].get(key):
                    row.setdefault("dis_changes", []).append([key, bp["dis"].get(key), ap["dis"].get(key)])
            gb, ga = _gatt_map(bp), _gatt_map(ap)
            added, removed = sorted(set(ga) - set(gb)), sorted(set(gb) - set(ga))
            changed = sorted(k for k in set(ga) & set(gb) if ga[k] != gb[k])
            if added or removed or changed:
                protocol.append(f"boîtier {side} : table GATT modifiée ("
                                + ", ".join(x for x in (f"{len(added)} caractéristique(s) ajoutée(s)" if added else "",
                                                        f"{len(removed)} retirée(s)" if removed else "",
                                                        f"{len(changed)} aux propriétés changées" if changed else "") if x)
                                + ")")
                row["gatt"] = {"added": added, "removed": removed, "changed": changed}
            rb, ra = bp.get("rideon_reply_hex"), ap.get("rideon_reply_hex")
            if (rb is None) != (ra is None) or (rb and ra and (len(rb) != len(ra) or rb[:12] != ra[:12])):
                protocol.append(f"boîtier {side} : réponse au RideOn changée ({rb or 'aucune'} → {ra or 'aucune'})")
        if bt and at:
            for k in sorted(set(at["types"]) - set(bt["types"])):
                protocol.append(f"boîtier {side} : nouveau type de message {k} (×{at['types'][k]})")
            for k in sorted(set(bt["types"]) - set(at["types"])):
                if bt["types"][k] >= 10:
                    protocol.append(f"boîtier {side} : type de message {k} disparu (×{bt['types'][k]} avant)")
            for k in sorted(set(at["lengths"]) & set(bt["lengths"])):
                if at["lengths"][k] != bt["lengths"][k] and k == f"0x{zwift_click.MSG_KEYPAD_STATUS:02X}":
                    protocol.append(f"boîtier {side} : longueur des trames {k} {bt['lengths'][k]} → {at['lengths'][k]}")
            p50b, p50a = bt.get("interval_ms_p50") or 0, at.get("interval_ms_p50") or 0
            if p50b and p50a and abs(p50a - p50b) / p50b > RATE_CHANGE:
                protocol.append(f"boîtier {side} : rythme des trames changé ({p50b:.0f} ms → {p50a:.0f} ms entre deux trames)")
            row["interval_ms_p95"] = [bt.get("interval_ms_p95"), at.get("interval_ms_p95")]
        unknown = sorted(k for k in ar.get("buttons", {}) if k.startswith("bit"))
        if unknown:
            protocol.append(f"boîtier {side} : touches inconnues {', '.join(unknown)} (tableau de bits 0x23 changé ?)")
        keys_b, keys_a = sorted(br.get("buttons", {})), sorted(ar.get("buttons", {}))
        row["keys"] = [keys_b, keys_a]
        if br and ar:
            for name, label in (("silences", "silences"), ("drops", "coupures")):
                nb = len(br["silences"]) if name == "silences" else br["drops"]
                na = len(ar["silences"]) if name == "silences" else ar["drops"]
                row[name] = [nb, na]
                if na > nb:
                    worse.append(f"boîtier {side} : {label} {nb} → {na}")
                elif na < nb:
                    better.append(f"boîtier {side} : {label} {nb} → {na}")
            row["max_silence_s"] = [br["max_silence_s"], ar["max_silence_s"]]
        db, da = _median_delay(before["steps"], side), _median_delay(after["steps"], side)
        row["median_delay_s"] = [db, da]
        if db is not None and da is not None:
            if da - db > DELAY_WORSE_S:
                worse.append(f"boîtier {side} : appuis plus lents ({db:.2f} s → {da:.2f} s, délai médian consigne → événement)")
            elif db - da > DELAY_WORSE_S:
                better.append(f"boîtier {side} : appuis plus rapides ({db:.2f} s → {da:.2f} s)")
        rows.append(row)
    gb = (before["report"] or {}).get("guided_ok"), (after["report"] or {}).get("guided_ok")
    total = (after["report"] or before["report"] or {}).get("guided_total")
    if None not in gb:
        if gb[1] < gb[0]:
            worse.append(f"boutons reconnus aux étapes guidées : {gb[0]} → {gb[1]} sur {total}")
        elif gb[1] > gb[0]:
            better.append(f"boutons reconnus aux étapes guidées : {gb[0]} → {gb[1]} sur {total}")
    fw_changed = any(r["firmware"][0] != r["firmware"][1] for r in rows)
    verdict = "MOINS BIEN" if worse else "MIEUX" if better else "PAREIL"
    notes = []
    left = next((r for r in rows if r["side"] == "gauche"), None)
    if left and left.get("silences", [0, 0])[0] > left.get("silences", [0, 0])[1]:
        notes.append("Les silences du boîtier gauche ont diminué : la mise à jour passe par l'appli Zwift, qui "
                     "« débloque » ce boîtier pour 24 h. Refaire une capture « apres_maj_j1 » au moins 24 h après "
                     "la mise à jour pour savoir si l'amélioration tient au firmware.")
    if not fw_changed:
        notes.append("Version du firmware identique (ou non lue) sur les deux captures : la mise à jour a-t-elle eu lieu ?")
    return {"verdict": verdict, "protocol_changed": bool(protocol), "protocol": protocol, "better": better,
            "worse": worse, "notes": notes, "units": rows,
            "guided_ok": list(gb), "guided_total": total,
            "before": before["folder"], "after": after["folder"]}


def _pair(v: list[Any], fmt: str = "{}") -> str:
    b, a = (("?" if x is None else fmt.format(x)) for x in v)
    return b if b == a else f"{b} → {a}"


def compare_text(c: dict[str, Any]) -> str:
    lines = [f"Zwift Click avant / après mise à jour du firmware : {c['verdict']}"]
    lines.append("PROTOCOLE BLE MODIFIÉ : OpenRide devra peut-être être adapté" if c["protocol_changed"]
                 else "Protocole BLE inchangé (table GATT, messages, RideOn)")
    lines += ["", f"Avant : {c['before']}", f"Après : {c['after']}", ""]
    if None not in c["guided_ok"]:
        lines.append(f"Étapes guidées réussies : {_pair(c['guided_ok'])} sur {c['guided_total']}")
    for r in c["units"]:
        lines.append(f"Boîtier {r['side']} : firmware {_pair(r['firmware'])}, batterie {_pair(r['battery_pct'], '{} %')}")
        lines.append(f"  touches vues : {', '.join(r['keys'][0]) or 'aucune'}"
                     + ("" if r["keys"][0] == r["keys"][1] else f" → {', '.join(r['keys'][1]) or 'aucune'}"))
        if "silences" in r:
            lines.append(f"  silences {_pair(r['silences'])} (le plus long {_pair(r['max_silence_s'], '{:.0f} s')}), "
                         f"coupures {_pair(r['drops'])}")
        lines.append(f"  délai médian des appuis {_pair(r['median_delay_s'], '{:.2f} s')}"
                     + (f", 95 % des trames à moins de {_pair(r['interval_ms_p95'], '{:.0f} ms')}" if r.get("interval_ms_p95") else ""))
        for key, b, a in r.get("dis_changes", []):
            lines.append(f"  {key} : {b} → {a}")
    for title, items in (("Changements du protocole BLE", c["protocol"]), ("Mieux", c["better"]),
                         ("Moins bien", c["worse"]), ("À noter", c["notes"])):
        if items:
            lines += ["", f"{title} :"] + [f"  - {x}" for x in items]
    return "\n".join(lines) + "\n"


def latest(logs: Path, label: str) -> Path | None:
    found = sorted(p for p in logs.glob(f"{PREFIX}*_{label}") if p.is_dir())
    return found[-1] if found else None


# --- Commandes ------------------------------------------------------------------------------------

def out_dir(label: str, logs: Path = LOGS) -> Path:
    return logs / f"{PREFIX}{datetime.now().strftime('%Y-%m-%d_%H%M')}_{label}"


def write_profile(profile: dict[str, Any], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "profil_ble.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "profil_ble.txt").write_text(profile_text(profile), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Zwift Click avant et après une mise à jour du firmware.")
    sub = ap.add_subparsers(dest="command", required=True)
    for name, text in (("releve", "relevé BLE de chaque boîtier (1 min)"),
                       ("capture", "relevé BLE puis recette guidée du lot X8")):
        p = sub.add_parser(name, help=text)
        p.add_argument("--etiquette", default="avant_maj", help="fin du nom du dossier (avant_maj, apres_maj…)")
        p.add_argument("--logs", type=Path, default=LOGS, help=f"dossier parent (défaut : {LOGS})")
        if name == "capture":
            p.add_argument("--minutes", type=float, default=30.0, help="surveillance de la recette (défaut 30)")
            p.add_argument("--rappel", type=float, default=5.0, help="minutes entre deux rappels d'appui")
            p.add_argument("--muet", action="store_true", help="sans bips")
    c = sub.add_parser("compare", help="compare deux captures et donne un verdict")
    c.add_argument("avant", type=Path, nargs="?", help="dossier avant (défaut : dernier *_avant_maj)")
    c.add_argument("apres", type=Path, nargs="?", help="dossier après (défaut : dernier *_apres_maj*)")
    c.add_argument("--logs", type=Path, default=LOGS)
    c.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.command == "compare":
        before = args.avant or latest(args.logs, "avant_maj")
        after = args.apres or (sorted(p for p in args.logs.glob(f"{PREFIX}*_apres_maj*") if p.is_dir()) or [None])[-1]
        if before is None or after is None:
            print("Captures introuvables : donner les deux dossiers (avant, après).", file=sys.stderr)
            return 2
        result = compare(load_capture(before), load_capture(after))
        (after / "comparaison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        (after / "comparaison.txt").write_text(compare_text(result), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else compare_text(result), end="")
        return 0 if result["verdict"] != "MOINS BIEN" and not result["protocol_changed"] else 1

    out = out_dir(args.etiquette, args.logs)
    try:
        profile = asyncio.run(releve())
    except KeyboardInterrupt:
        print("\nInterrompu.")
        return 1
    write_profile(profile, out)
    print(profile_text(profile), end="")
    if args.command == "releve":
        print(f"Relevé : {out}")
        return 0 if profile["units"] else 1
    print("\nRecette guidée du Click : les consignes suivent.")
    argv2 = ["--out", str(out / "recette"), "--minutes", f"{args.minutes:g}", "--rappel", f"{args.rappel:g}"]
    code = cr.main(argv2 + (["--muet"] if args.muet else []), recorder_cls=TracingRecorder)
    print(f"Capture complète : {out}")
    return code


if __name__ == "__main__":
    sys.exit(main())
