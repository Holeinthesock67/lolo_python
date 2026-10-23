"""Chargement d'une séance enregistrée (journal JSONL ou fichier FIT) pour le rejeu dans `MockDriver` (SRS §12, lot H3)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fit_tool.profile.messages.record_message import RecordMessage

from .fit_export import iter_records
from .journal import read_journal


class ReplayError(Exception):
    """Fichier de rejeu introuvable, illisible, vide ou d'extension non prise en charge."""


@dataclass(frozen=True)
class ReplaySample:
    t: float                 # secondes depuis le début du rejeu
    power_w: float
    cadence_rpm: float
    hr_bpm: int | None


def _load_jsonl(path: Path) -> list[ReplaySample]:
    try:
        records = [line for line in read_journal(path)
                   if isinstance(line, dict) and line.get("kind") == "record"]
    except (OSError, UnicodeDecodeError) as exc:
        raise ReplayError(f"journal illisible ({path}) : {exc}") from exc

    if not records:
        raise ReplayError(f"aucun enregistrement dans le journal : {path}")

    try:
        raw_t0 = records[0].get("t")
        if raw_t0 is None:
            raw_t0 = records[0]["ts"]
        t0 = float(raw_t0)
        samples: list[ReplaySample] = []
        for r in records:
            rt = r.get("t") if r.get("t") is not None else r["ts"]
            t = max(0.0, float(rt) - t0)
            p = max(0.0, float(r["power"])) if r.get("power") is not None else 0.0
            cad = max(0.0, float(r["cadence"])) if r.get("cadence") is not None else 0.0
            hr_raw = r.get("hr")
            hr = int(hr_raw) if hr_raw not in (None, 0) else None
            samples.append(ReplaySample(t=t, power_w=p, cadence_rpm=cad, hr_bpm=hr))
    except (KeyError, TypeError, ValueError) as exc:
        raise ReplayError(f"enregistrement invalide dans le journal ({path}) : {exc}") from exc

    return samples


def _load_fit(path: Path) -> list[ReplaySample]:
    try:
        msgs = [r.message for r in iter_records(path) if isinstance(r.message, RecordMessage)]
    except Exception as exc:
        raise ReplayError(f"fichier FIT illisible ({path}) : {exc}") from exc

    if not msgs:
        raise ReplayError(f"aucun enregistrement dans le fichier FIT : {path}")

    try:
        if msgs[0].timestamp is None:
            raise ValueError("horodatage absent")
        ts0 = float(msgs[0].timestamp)
        # fit-tool expose `timestamp` en millisecondes Unix.
        scale = 1000.0 if ts0 > 1e11 else 1.0
        samples: list[ReplaySample] = []
        for m in msgs:
            if m.timestamp is None:
                raise ValueError("horodatage absent")
            t = max(0.0, (float(m.timestamp) - ts0) / scale)
            p = max(0.0, float(m.power)) if m.power is not None else 0.0
            cad = max(0.0, float(m.cadence)) if m.cadence is not None else 0.0
            hr = int(m.heart_rate) if m.heart_rate not in (None, 0) else None
            samples.append(ReplaySample(t=t, power_w=p, cadence_rpm=cad, hr_bpm=hr))
    except (TypeError, ValueError) as exc:
        raise ReplayError(f"enregistrement FIT invalide ({path}) : {exc}") from exc

    return samples


def load_replay(path: Path) -> list[ReplaySample]:
    """Charge une série d'échantillons de rejeu depuis un fichier `.jsonl` ou `.fit`."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext not in (".jsonl", ".fit"):
        raise ReplayError(
            f"extension non prise en charge pour le rejeu ({path.suffix or 'aucune'}) : "
            "attendu .jsonl ou .fit"
        )
    if not path.is_file():
        raise ReplayError(f"fichier de rejeu introuvable : {path}")
    if ext == ".jsonl":
        return _load_jsonl(path)
    return _load_fit(path)
