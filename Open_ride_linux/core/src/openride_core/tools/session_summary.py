"""Bilan d'une séance enregistrée (lot K7, SRS §6, §9, §11) : `openride-core summary`.

    openride-core summary [FICHIER] [--ftp W] [--json]

FICHIER est un journal `.jsonl` ou un `.fit` ; sans fichier, le dernier journal
(`journal.latest_journal`). Tout se calcule hors ligne, en moins d'une seconde.

Définitions :
- **Échantillons** : les relevés à 1 Hz ; chacun compte pour 1 s. Les relevés tombés dans une
  pause (entre `pause` et `resume`) sont écartés, et la série reprend sans trou après la pause :
  le temps de pause n'entre ni dans la durée, ni dans NP, ni dans les zones.
- **Durée de roulage** : temps chronométré (`fit_export.summarize`, hors pauses).
- **Distance** : plus grande distance relevée. **Dénivelé positif** : altitude lissée par moyenne
  glissante sur les 10 dernières secondes (fenêtre partielle au début), puis montées cumulées par paliers d'au moins 1 m (hystérésis).
- **Puissance moyenne** : moyenne des échantillons (0 W compris, puissance absente = 0 W).
- **Puissance normalisée (NP)** : moyenne glissante sur 30 s (calculée dès le 30ᵉ échantillon),
  élevée à la puissance 4, moyennée, racine 4. Séance de moins de 30 s : NP = moyenne.
- **IF** = NP / FTP ; **TSS** = durée_h × IF² × 100.
- **Zones de Coggan** (puissance de chaque seconde, en % de la FTP) : Z1 < 55, Z2 < 75,
  Z3 < 90, Z4 < 105, Z5 < 120, Z6 < 150, Z7 au-delà.
- **Meilleures puissances** : meilleure moyenne sur 5 s, 1 min, 5 min et 20 min ; absente si la
  séance est plus courte que la fenêtre.
- **Cadence, FC** : moyenne et maximum ; cadence nulle (roue libre) et FC à 0 ou absente ignorées.
- **ERG** : par bloc (`block` du journal), durée et puissance moyenne. La cible ERG n'est pas
  écrite dans le journal (format v1) : l'écart à la cible est alors signalé comme indisponible.
  Un `.fit` ne porte pas les blocs : `erg` vaut `null`.

Clés de la sortie `--json` (stables) :
    source, format ("jsonl" | "fit"), ftp_w, start_ts, duration_s, elapsed_s, distance_m,
    elevation_gain_m, avg_power_w, np_w, if, tss, zones (liste de {zone, low_pct, high_pct,
    seconds, pct}), best_power_w ({"5s", "1min", "5min", "20min"} : W ou null),
    cadence ({avg, max} ou null), hr ({avg, max} ou null),
    erg (null ou {target_available, note, blocks : [{block, seconds, avg_power_w,
    target_w, delta_w}]}).
Les puissances sont arrondies à 0,1 W, IF à 0,01, TSS à 0,1.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..fit_export import summarize
from ..journal import read_journal

ZONES: tuple[tuple[str, float, float | None], ...] = (
    ("Z1", 0.0, 55.0), ("Z2", 55.0, 75.0), ("Z3", 75.0, 90.0), ("Z4", 90.0, 105.0),
    ("Z5", 105.0, 120.0), ("Z6", 120.0, 150.0), ("Z7", 150.0, None),
)
BEST_WINDOWS: tuple[tuple[str, int], ...] = (("5s", 5), ("1min", 60), ("5min", 300), ("20min", 1200))
NP_WINDOW_S = 30
ALT_SMOOTH_S = 10
CLIMB_THRESHOLD_M = 1.0


class SummaryError(Exception):
    """Fichier introuvable, illisible, vide ou d'extension non prise en charge."""


@dataclass
class Session:
    records: list[dict]
    events: list[dict]
    fmt: str


# --- lecture ----------------------------------------------------------------------------

def load_session(path: Path) -> Session:
    path = Path(path)
    ext = path.suffix.lower()
    if ext not in (".jsonl", ".fit"):
        raise SummaryError(f"extension non prise en charge ({path.suffix or 'aucune'}) : attendu .jsonl ou .fit")
    if not path.is_file():
        raise SummaryError(f"fichier introuvable : {path}")
    try:
        session = _load_jsonl(path) if ext == ".jsonl" else _load_fit(path)
    except SummaryError:
        raise
    except Exception as exc:
        raise SummaryError(f"fichier illisible ({path}) : {exc}") from exc
    if not session.records:
        raise SummaryError(f"aucun relevé dans {path}")
    return session


def _load_jsonl(path: Path) -> Session:
    records, events = [], []
    for line in read_journal(path):
        if not isinstance(line, dict):
            continue
        if line.get("kind") == "record" and line.get("ts") is not None:
            records.append(line)
        elif line.get("kind") == "event" and line.get("event") and line.get("ts") is not None:
            events.append(line)
    return Session(records, events, "jsonl")


def _load_fit(path: Path) -> Session:
    from fit_tool.profile.messages.event_message import EventMessage
    from fit_tool.profile.messages.record_message import RecordMessage
    from fit_tool.profile.profile_type import Event, EventType

    from ..fit_export import iter_records

    records, events = [], []
    for rec in iter_records(path):
        m = rec.message
        if isinstance(m, RecordMessage) and m.timestamp is not None:
            records.append({
                "ts": m.timestamp / 1000.0, "alt": m.altitude, "distance": m.distance or 0.0,
                "speed": m.speed or 0.0, "power": m.power, "cadence": m.cadence, "hr": m.heart_rate,
            })
        elif isinstance(m, EventMessage) and m.timestamp is not None and _enum_value(m.event) == Event.TIMER.value:
            kind = _enum_value(m.event_type)
            if kind == EventType.START.value:
                events.append({"event": "start" if not events else "resume", "ts": m.timestamp / 1000.0})
            elif kind == EventType.STOP_ALL.value:
                events.append({"event": "pause", "ts": m.timestamp / 1000.0})
    if events and events[-1]["event"] == "pause":
        events[-1]["event"] = "stop"
    return Session(records, events, "fit")


def _enum_value(v: Any) -> Any:
    return getattr(v, "value", v)   # fit-tool relit les énumérations en entiers


def running_records(records: list[dict], events: list[dict]) -> list[dict]:
    """Relevés hors pauses : ceux qui tombent strictement entre `pause` et `resume` sont écartés."""
    pauses: list[tuple[float, float]] = []
    paused_at: float | None = None
    for ev in sorted(events, key=lambda e: e["ts"]):
        if ev["event"] == "pause" and paused_at is None:
            paused_at = ev["ts"]
        elif ev["event"] == "resume" and paused_at is not None:
            pauses.append((paused_at, ev["ts"]))
            paused_at = None
    if paused_at is not None:
        pauses.append((paused_at, math.inf))
    return [r for r in records if not any(a < r["ts"] < b for a, b in pauses)]


# --- calculs ----------------------------------------------------------------------------

def rolling_means(values: list[float], window: int) -> list[float]:
    """Moyennes glissantes complètes sur `window` échantillons (aucune si la série est plus courte)."""
    if window <= 0 or len(values) < window:
        return []
    out, acc = [], sum(values[:window])
    out.append(acc / window)
    for i in range(window, len(values)):
        acc += values[i] - values[i - window]
        out.append(acc / window)
    return out


def normalized_power(powers: list[float]) -> float:
    if not powers:
        return 0.0
    rolled = rolling_means(powers, NP_WINDOW_S) or [sum(powers) / len(powers)]
    return (sum(p ** 4 for p in rolled) / len(rolled)) ** 0.25


def elevation_gain(altitudes: list[float]) -> float:
    if not altitudes:
        return 0.0
    # Moyenne glissante sur les 10 dernières secondes (fenêtre partielle au début).
    smooth, acc = [], 0.0
    for i, a in enumerate(altitudes):
        acc += a
        if i >= ALT_SMOOTH_S:
            acc -= altitudes[i - ALT_SMOOTH_S]
        smooth.append(acc / min(i + 1, ALT_SMOOTH_S))
    gain, ref = 0.0, smooth[0]
    for a in smooth[1:]:
        if a - ref >= CLIMB_THRESHOLD_M:
            gain += a - ref
            ref = a
        elif a < ref:
            ref = a
    return gain


def zone_of(power: float, ftp: float) -> int:
    pct = power / ftp * 100.0
    for i, (_, _, high) in enumerate(ZONES):
        if high is None or pct < high:
            return i
    return len(ZONES) - 1


def _avg_max(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {"avg": round(sum(values) / len(values), 1), "max": round(max(values), 1)}


def compute_summary(session: Session, ftp_w: float, source: str = "") -> dict[str, Any]:
    if ftp_w <= 0:
        raise SummaryError(f"FTP invalide : {ftp_w}")
    s = summarize(session.records, session.events)
    recs = running_records(session.records, session.events)
    powers = [max(0.0, float(r["power"])) if r.get("power") is not None else 0.0 for r in recs]
    duration_s = s.timer_s

    np_w = normalized_power(powers)
    intensity = np_w / ftp_w
    tss = duration_s / 3600.0 * intensity ** 2 * 100.0

    zone_s = [0] * len(ZONES)
    for p in powers:
        zone_s[zone_of(p, ftp_w)] += 1
    n = len(powers)
    zones = [{"zone": name, "low_pct": lo, "high_pct": hi, "seconds": zone_s[i],
              "pct": round(zone_s[i] / n * 100.0, 1) if n else 0.0}
             for i, (name, lo, hi) in enumerate(ZONES)]

    best = {}
    for key, win in BEST_WINDOWS:
        rolled = rolling_means(powers, win)
        best[key] = round(max(rolled), 1) if rolled else None

    alts = [float(r["alt"]) for r in recs if r.get("alt") is not None]
    cads = [float(r["cadence"]) for r in recs if r.get("cadence")]
    hrs = [float(r["hr"]) for r in recs if r.get("hr")]

    return {
        "source": source,
        "format": session.fmt,
        "ftp_w": round(ftp_w, 1),
        "start_ts": s.start_ts,
        "duration_s": round(duration_s, 1),
        "elapsed_s": round(s.elapsed_s, 1),
        "distance_m": round(s.distance_m, 1),
        "elevation_gain_m": round(elevation_gain(alts), 1),
        "avg_power_w": round(sum(powers) / n, 1) if n else 0.0,
        "np_w": round(np_w, 1),
        "if": round(intensity, 2),
        "tss": round(tss, 1),
        "zones": zones,
        "best_power_w": best,
        "cadence": _avg_max(cads),
        "hr": _avg_max(hrs),
        "erg": _erg_blocks(recs, powers),
    }


def _erg_blocks(recs: list[dict], powers: list[float]) -> dict[str, Any] | None:
    blocks: dict[int, list[float]] = {}
    for r, p in zip(recs, powers):
        if r.get("block") is not None and r.get("mode", "ERG") == "ERG":
            blocks.setdefault(int(r["block"]), []).append(p)
    if not blocks:
        return None
    targets: dict[int, list[float]] = {}
    for r in recs:
        if r.get("block") is not None and r.get("target_w") is not None:
            targets.setdefault(int(r["block"]), []).append(float(r["target_w"]))
    out = []
    for b in sorted(blocks):
        avg = sum(blocks[b]) / len(blocks[b])
        tgt = sum(targets[b]) / len(targets[b]) if b in targets else None
        out.append({"block": b, "seconds": len(blocks[b]), "avg_power_w": round(avg, 1),
                    "target_w": round(tgt, 1) if tgt is not None else None,
                    "delta_w": round(avg - tgt, 1) if tgt is not None else None})
    available = bool(targets)
    return {"target_available": available,
            "note": None if available else "cible ERG absente du journal : écart à la cible indisponible",
            "blocks": out}


# --- affichage --------------------------------------------------------------------------

def _hms(seconds: float) -> str:
    total = int(round(max(seconds, 0.0)))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


def format_text(r: dict[str, Any]) -> str:
    lines = [
        f"Bilan de séance : {r['source']}",
        f"Durée {_hms(r['duration_s'])} (écoulé {_hms(r['elapsed_s'])}), distance {r['distance_m'] / 1000:.2f} km, "
        f"dénivelé + {r['elevation_gain_m']:.0f} m",
        f"Puissance : moyenne {r['avg_power_w']:.0f} W, NP {r['np_w']:.0f} W ; "
        f"FTP {r['ftp_w']:.0f} W, IF {r['if']:.2f}, TSS {r['tss']:.0f}",
        "Zones :",
    ]
    for z in r["zones"]:
        rng = f"< {z['high_pct']:.0f} %" if z["low_pct"] == 0 else (
            f"> {z['low_pct']:.0f} %" if z["high_pct"] is None else f"{z['low_pct']:.0f} à {z['high_pct']:.0f} %")
        lines.append(f"  {z['zone']} {rng:<12} {_hms(z['seconds']):>8}  {z['pct']:5.1f} %")
    best = ", ".join(f"{k} {v:.0f} W" for k, v in r["best_power_w"].items() if v is not None)
    lines.append(f"Meilleures puissances : {best or 'séance trop courte'}")
    if r["cadence"]:
        lines.append(f"Cadence : moyenne {r['cadence']['avg']:.0f}, max {r['cadence']['max']:.0f} rpm")
    if r["hr"]:
        lines.append(f"FC : moyenne {r['hr']['avg']:.0f}, max {r['hr']['max']:.0f} bpm")
    if r["erg"]:
        lines.append("ERG, par bloc :")
        for b in r["erg"]["blocks"]:
            delta = f", écart {b['delta_w']:+.0f} W" if b["delta_w"] is not None else ""
            lines.append(f"  bloc {b['block']:>2} : {_hms(b['seconds'])}, {b['avg_power_w']:.0f} W{delta}")
        if r["erg"]["note"]:
            lines.append(f"  ({r['erg']['note']})")
    return "\n".join(lines)


def run(path: Path | None, ftp: float | None, as_json: bool, config_path: Path | None = None) -> int:
    from .. import config as config_mod
    from ..journal import latest_journal

    if path is None:
        path = latest_journal()
        if path is None:
            print("Aucun journal trouvé.", file=sys.stderr)
            return 1
    if ftp is None:
        try:
            ftp = float(config_mod.load(config_path).rider.ftp_w)
        except config_mod.ConfigError as exc:
            print(f"openride-core : configuration invalide : {exc} (utiliser --ftp)", file=sys.stderr)
            return 1
    try:
        result = compute_summary(load_session(path), ftp, str(path))
    except SummaryError as exc:
        print(f"openride-core summary : {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if as_json else format_text(result))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m openride_core.tools.session_summary",
                                description="Bilan d'une séance (.jsonl ou .fit).")
    p.add_argument("file", nargs="?", type=Path, help="journal .jsonl ou .fit (défaut : dernier journal)")
    p.add_argument("--ftp", type=float, help="FTP en watts (défaut : config.toml)")
    p.add_argument("--json", action="store_true", help="sortie JSON")
    p.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    a = p.parse_args(argv)
    return run(a.file, a.ftp, a.json, a.config)


if __name__ == "__main__":
    raise SystemExit(main())
