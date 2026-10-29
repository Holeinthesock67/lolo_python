"""Export FIT minimal (SRS §9), avec la bibliothèque fit-tool.

Messages : file_id, event (début, pauses, fin), record à 1 Hz, lap, session (cycling /
virtual_activity) et activity. Aucun envoi en ligne.

fit-tool attend des horodatages en millisecondes Unix et des positions en degrés
(il convertit lui-même en semicercles, degrés × 2³¹ / 180).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.activity_message import ActivityMessage
from fit_tool.profile.messages.device_info_message import DeviceInfoMessage
from fit_tool.profile.messages.event_message import EventMessage
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage
from fit_tool.profile.profile_type import (
    Activity, Event, EventType, FileType, LapTrigger, Manufacturer, SessionTrigger, Sport, SubSport,
)

from .config import OPENRIDE_HOME
from .journal import read_journal

ACTIVITIES_DIR = OPENRIDE_HOME / "Activities"
FIT_EPOCH_S = 631065600  # 1989-12-31 00:00:00 UTC


def _ms(ts: float) -> int:
    return int(round(ts * 1000))


@dataclass
class Summary:
    start_ts: float
    end_ts: float
    elapsed_s: float
    timer_s: float
    distance_m: float
    avg_speed: float
    max_speed: float
    avg_power: float | None
    max_power: float | None
    avg_hr: int | None
    max_hr: int | None
    avg_cadence: int | None
    n_records: int


def _avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def summarize(records: list[dict], events: list[dict]) -> Summary:
    start = min([r["ts"] for r in records] + [e["ts"] for e in events])
    end = max([r["ts"] for r in records] + [e["ts"] for e in events])

    # Temps chronométré : somme des intervalles entre start/resume et pause/stop.
    timer = 0.0
    running_since: float | None = None
    for ev in sorted(events, key=lambda e: e["ts"]):
        if ev["event"] in ("start", "resume") and running_since is None:
            running_since = ev["ts"]
        elif ev["event"] in ("pause", "stop") and running_since is not None:
            timer += ev["ts"] - running_since
            running_since = None
    if running_since is not None:
        timer += end - running_since
    if not events:
        timer = end - start

    powers = [r["power"] for r in records if r.get("power") is not None]
    hrs = [r["hr"] for r in records if r.get("hr")]
    cads = [r["cadence"] for r in records if r.get("cadence")]
    speeds = [r.get("speed", 0.0) for r in records]
    distance = max((r.get("distance", 0.0) for r in records), default=0.0)
    max_speed = max(speeds, default=0.0)
    # Garde-fou : un chrono aberrant (horloge déréglée) ne doit pas produire une vitesse absurde,
    # que le format FIT refuse (uint16) et qui ferait échouer tout l'export.
    avg_speed = min(distance / timer, max_speed) if timer > 0 else 0.0
    return Summary(
        start_ts=start, end_ts=end, elapsed_s=end - start, timer_s=timer,
        distance_m=distance,
        avg_speed=avg_speed,
        max_speed=max_speed,
        avg_power=_avg(powers), max_power=max(powers) if powers else None,
        avg_hr=round(_avg(hrs)) if hrs else None, max_hr=max(hrs) if hrs else None,
        avg_cadence=round(_avg(cads)) if cads else None,
        n_records=len(records),
    )


def _event(ts: float, event_type: EventType) -> EventMessage:
    m = EventMessage()
    m.timestamp = _ms(ts)
    m.event = Event.TIMER
    m.event_type = event_type
    m.event_group = 0
    return m


def lap_starts(lines: list[dict]) -> list[float]:
    """Instants des tours : début de chaque salle et de chaque phase du boss d'une run Cyber-Rogue (lot R8)."""
    return sorted(ln["ts"] for ln in lines if ln.get("kind") == "rogue" and ln.get("event") == "room_start")


def write_fit(records: list[dict], events: list[dict], path: Path, laps: list[float] | None = None) -> Summary:
    """Écrit le fichier FIT et renvoie le résumé de la séance. `laps` : débuts de tours (un seul tour sinon)."""
    if not records:
        raise ValueError("aucun échantillon : rien à exporter")
    s = summarize(records, events)
    if not events:
        events = [{"event": "start", "ts": s.start_ts}, {"event": "stop", "ts": s.end_ts}]

    b = FitFileBuilder(auto_define=True, min_string_size=50)

    fid = FileIdMessage()
    fid.type = FileType.ACTIVITY
    fid.manufacturer = Manufacturer.DEVELOPMENT.value
    fid.product = 1
    fid.serial_number = 0x0E0DE001
    fid.time_created = _ms(s.start_ts)
    b.add(fid)

    dev = DeviceInfoMessage()
    dev.timestamp = _ms(s.start_ts)
    dev.manufacturer = Manufacturer.DEVELOPMENT.value
    dev.product = 1
    dev.software_version = 0.1
    b.add(dev)

    timeline: list[tuple[float, int, object]] = []
    type_map = {"start": EventType.START, "resume": EventType.START,
                "pause": EventType.STOP_ALL, "stop": EventType.STOP_ALL}
    for ev in events:
        if ev["event"] not in type_map:   # resume_after_crash (lot N8) : pas un événement du chronomètre
            continue
        # À horodatage égal : start avant records, stop après.
        order = 0 if ev["event"] in ("start", "resume") else 2
        timeline.append((ev["ts"], order, _event(ev["ts"], type_map[ev["event"]])))

    for r in records:
        m = RecordMessage()
        m.timestamp = _ms(r["ts"])
        if r.get("lat") is not None and r.get("lon") is not None:
            m.position_lat = r["lat"]
            m.position_long = r["lon"]
        if r.get("alt") is not None:
            m.altitude = r["alt"]
        m.distance = r.get("distance", 0.0)
        m.speed = r.get("speed", 0.0)
        if r.get("power") is not None:
            m.power = int(round(r["power"]))
        if r.get("cadence") is not None:
            m.cadence = int(round(r["cadence"]))
        if r.get("hr"):
            m.heart_rate = int(r["hr"])
        timeline.append((r["ts"], 1, m))

    for _, _, msg in sorted(timeline, key=lambda x: (x[0], x[1])):
        b.add(msg)

    def fill_totals(m) -> None:
        m.timestamp = _ms(s.end_ts)
        m.start_time = _ms(s.start_ts)
        m.total_elapsed_time = s.elapsed_s
        m.total_timer_time = s.timer_s
        m.total_distance = s.distance_m
        m.avg_speed = s.avg_speed
        m.max_speed = s.max_speed
        if s.avg_power is not None:
            m.avg_power = int(round(s.avg_power))
            m.max_power = int(round(s.max_power))
        if s.avg_hr is not None:
            m.avg_heart_rate = s.avg_hr
            m.max_heart_rate = s.max_hr
        if s.avg_cadence is not None:
            m.avg_cadence = s.avg_cadence
        m.event = Event.LAP
        m.event_type = EventType.STOP
        m.sport = Sport.CYCLING
        m.sub_sport = SubSport.VIRTUAL_ACTIVITY

    bounds = [s.start_ts] + [t for t in sorted(laps or []) if s.start_ts < t < s.end_ts] + [s.end_ts]
    n_laps = len(bounds) - 1
    if n_laps == 1:
        lap = LapMessage()
        fill_totals(lap)
        lap.message_index = 0
        lap.lap_trigger = LapTrigger.SESSION_END
        b.add(lap)
    else:
        for i in range(n_laps):
            lo, hi = bounds[i], bounds[i + 1]
            part = [r for r in records if lo <= r["ts"] < hi or (i == n_laps - 1 and r["ts"] == hi)]
            lap = LapMessage()
            lap.timestamp = _ms(hi)
            lap.start_time = _ms(lo)
            lap.total_elapsed_time = lap.total_timer_time = hi - lo
            if part:
                lap.total_distance = max(part[-1].get("distance", 0.0) - part[0].get("distance", 0.0), 0.0)
                lap.avg_speed = min(lap.total_distance / (hi - lo), s.max_speed) if hi > lo else 0.0
                powers = [r["power"] for r in part if r.get("power") is not None]
                if powers:
                    lap.avg_power, lap.max_power = int(round(_avg(powers))), int(round(max(powers)))
            lap.event = Event.LAP
            lap.event_type = EventType.STOP
            lap.sport = Sport.CYCLING
            lap.sub_sport = SubSport.VIRTUAL_ACTIVITY
            lap.message_index = i
            lap.lap_trigger = LapTrigger.SESSION_END if i == n_laps - 1 else LapTrigger.MANUAL
            b.add(lap)

    sess = SessionMessage()
    fill_totals(sess)
    sess.event = Event.SESSION
    sess.message_index = 0
    sess.first_lap_index = 0
    sess.num_laps = n_laps
    sess.trigger = SessionTrigger.ACTIVITY_END
    b.add(sess)

    act = ActivityMessage()
    act.timestamp = _ms(s.end_ts)
    act.total_timer_time = s.timer_s
    act.num_sessions = 1
    act.type = Activity.MANUAL
    act.event = Event.ACTIVITY
    act.event_type = EventType.STOP
    offset = datetime.fromtimestamp(s.end_ts).astimezone().utcoffset()
    # local_date_time : secondes brutes depuis l'époque FIT, décalées à l'heure locale.
    act.local_timestamp = int(s.end_ts + (offset.total_seconds() if offset else 0)) - FIT_EPOCH_S
    b.add(act)

    path.parent.mkdir(parents=True, exist_ok=True)
    b.build().to_file(str(path))
    return s


def default_fit_path(start_ts: float, route_name: str | None) -> Path:
    """FIT de la séance dans le dossier des séances du profil en cours (lot MJ1)."""
    from . import profiles

    stamp = datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d_%H-%M")
    return profiles.current().activities_dir / f"{stamp}_{route_name or 'seance'}.fit"


def journal_to_fit(journal_path: Path, out_path: Path | None = None) -> tuple[Path, Summary]:
    """Convertit un journal JSONL en FIT (utilisé en fin de séance et par `recover`)."""
    records, events, route_id, rogue = [], [], None, []
    for line in read_journal(journal_path):
        kind = line.get("kind")
        if kind == "rogue":
            rogue.append(line)
        if kind == "record":
            records.append(line)
        elif kind == "event":
            events.append(line)
        elif kind == "header":
            route_id = line.get("route_id")
    if not records:
        raise ValueError(f"journal vide : {journal_path}")
    out_path = out_path or default_fit_path(records[0]["ts"], route_id)
    return out_path, write_fit(records, events, out_path, lap_starts(rogue))


def iter_records(fit_path: Path) -> Iterable:
    """Relecture d'un FIT (tests et vérification)."""
    from fit_tool.fit_file import FitFile
    return FitFile.from_file(str(fit_path)).records
