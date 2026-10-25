"""Analyseur de journal de séance OpenRide (Lot H6, SRS §14.1).

Extrait un résumé structuré (humain ou JSON) d'un fichier de journal du core
(par défaut ``~/run_trainer.log``) : connexions/déconnexions du trainer FTMS et du
Zwift Click, pauses, performances de la boucle et seuils Rust (SRS §14.1).

Section Click enrichie (lot K8) : durées de connexion et délais de reconnexion (calculés sur
les horodatages, donc aussi pour les anciens journaux, et par boîtier quand la ligne porte
l'adresse : le Click récent en a deux), temps depuis le dernier appui et
cadence des notifications (nouvelles lignes du lot K8), et coupures « corrélées » au trainer :
celles qui tombent à moins de ``CORRELATION_WINDOW_S`` d'une écriture au trainer (valeur portée
par la ligne de coupure) ou d'un événement du trainer dans le journal (connexion, reconnexion,
perte, commande refusée…).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

STEP_P99_LIMIT_MS = 5.0
LAG_P99_LIMIT_MS = 20.0
CPU_LIMIT_PCT = 15.0
CONSECUTIVE_BREACHES = 3
CORRELATION_WINDOW_S = 2.0

DEFAULT_LOG_PATH = Path.home() / "run_trainer.log"

# Chaînes de format exactes présentes dans le code source de openride_core
# (vérifiées par test unitaire contre les fichiers sources).
CORE_FORMAT_STRINGS: dict[str, tuple[str, str]] = {
    "core_started": (
        "session.py",
        "Core démarré (trainer=%s, entrées=%s).",
    ),
    "core_stopped": (
        "session.py",
        "Arrêt du core…",
    ),
    "session_transition": (
        "session.py",
        "Séance : %s -> %s%s",
    ),
    "perf": (
        "session.py",
        'Perf : pas p50 %.2f / p99 %.2f / max %.2f ms ; retard p99 %.1f / max %.1f ms ;"\n'
        '                         " CPU %.1f %%',
    ),
    "trainer_lost_pause": (
        "session.py",
        "Trainer perdu : pause automatique.",
    ),
    "engine_lost_pause": (
        "session.py",
        "Engine perdu : pause automatique.",
    ),
    "trainer_control_refused_fatal": (
        "session.py",
        "Le trainer refuse le contrôle FTMS après deux reprises.",
    ),
    "trainer_connected": (
        "ftms_driver.py",
        "Trainer connecté (%s)",
    ),
    "trainer_reconnect": (
        "ftms_driver.py",
        "Reconnexion au trainer dans %.0f s",
    ),
    "trainer_cmd_refused": (
        "ftms_driver.py",
        "Commande 0x%02x refusée : %s",
    ),
    "trainer_warning": (
        "ftms_driver.py",
        "Trainer : %s",
    ),
    "click_connected": (
        "input_providers.py",
        "Zwift Click connecté (adresse %s, recherche %.1f s, %d tentative(s))",
    ),
    "click_disconnected": (
        "input_providers.py",
        'Zwift Click déconnecté (adresse %s) après %.1f s de connexion : dernière notification il y a %s, "\n'
        '                          "dernier appui il y a %s, %d notification(s), dernière écriture au trainer il y a %s, "\n'
        '                          "raison : %s ; appuyez sur un bouton pour le réveiller',
    ),
    "click_rate": (
        "input_providers.py",
        "Click : %d notification(s) en %.0f s (%.1f par seconde)",
    ),
    "click_press": (
        "input_providers.py",
        "Click : %s",
    ),
    "click_not_found": (
        "input_providers.py",
        "Zwift Click introuvable (appuyez sur un bouton)",
    ),
    "journal_write_error": (
        "recorder.py",
        "Écriture du journal impossible : %s",
    ),
    "fit_export_error": (
        "recorder.py",
        "Export FIT impossible : %s",
    ),
}

LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s+"
    r"(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)\s+"
    r"(?P<logger>\S+)\s+"
    r"(?P<msg>.+)$"
)


FTMS_PATTERNS: dict[str, re.Pattern[str]] = {
    "write": re.compile(r"^FTMS > (?P<op>[A-Za-z0-9_]+)(?: (?P<args>.*?))? \((?P<hex>[0-9a-fA-F ]+)\)$"),
    "response": re.compile(r"^FTMS < réponse (?P<op>[A-Za-z0-9_]+) (?P<result>[A-Za-z0-9_]+) en (?P<ms>[0-9.]+) ms$"),
    "timeout": re.compile(r"^FTMS < sans réponse(?: à (?P<op>[A-Za-z0-9_]+))? après (?P<ms>[0-9.]+) ms$"),
    "status": re.compile(r"^FTMS < statut (?P<name>[A-Za-z0-9_]+)(?: (?P<args>.*?))? \((?P<origin>écho probable de notre commande|par un tiers)\)$"),
}

PATTERNS: dict[str, re.Pattern[str]] = {
    "core_started": re.compile(
        r"^Core démarré \(trainer=(?P<trainer>[^,]+), entrées=(?P<input>[^)]+)\)\.$"
    ),
    "core_stopped": re.compile(r"^Arrêt du core…$"),
    "session_transition": re.compile(
        r"^Séance : (?P<old>\S+) -> (?P<new>\S+)(?: \((?P<reason>[^)]+)\))?$"
    ),
    "perf": re.compile(
        r"^Perf : pas p50 (?P<step_p50>[0-9.]+) / p99 (?P<step_p99>[0-9.]+) / max (?P<step_max>[0-9.]+) ms ; "
        r"retard p99 (?P<lag_p99>[0-9.]+) / max (?P<lag_max>[0-9.]+) ms ; "
        r"CPU (?P<cpu>[0-9.]+) %$"
    ),
    "trainer_lost_pause": re.compile(r"^Trainer perdu : pause automatique\.$"),
    "engine_lost_pause": re.compile(r"^Engine perdu : pause automatique\.$"),
    "trainer_control_refused_fatal": re.compile(
        r"^Le trainer refuse le contrôle FTMS après deux reprises\.$"
    ),
    "trainer_connected": re.compile(r"^Trainer connecté \((?P<device>.+)\)$"),
    "trainer_reconnect": re.compile(r"^Reconnexion au trainer dans (?P<delay>[0-9.]+) s$"),
    "trainer_cmd_refused": re.compile(
        r"^Commande 0x(?P<op>[0-9a-fA-F]{2}) refusée : (?P<reason>.+)$"
    ),
    "trainer_warning": re.compile(r"^Trainer : (?P<err>.+)$"),
    # Ancien format (« Zwift Click connecté » seul) et format du lot K8.
    "click_connected": re.compile(
        r"^Zwift Click connecté"
        r"(?: \(adresse (?P<address>.+), recherche (?P<search>[0-9.]+) s, (?P<attempts>\d+) tentative\(s\)\))?$"
    ),
    "click_disconnected": re.compile(
        r"^Zwift Click déconnecté (?:\(veille \?\) : appuyez sur un bouton pour le réveiller"
        r"|(?:\(adresse (?P<address>[^)]+)\) )?après (?P<connected>[0-9.]+) s de connexion : dernière notification il y a (?P<since_notif>[0-9.]+ s|jamais), "
        r"dernier appui il y a (?P<since_press>[0-9.]+ s|jamais), (?P<notifs>\d+) notification\(s\), "
        r"dernière écriture au trainer il y a (?P<since_write>[0-9.]+ s|jamais), "
        r"raison : (?P<reason>.+) ; appuyez sur un bouton pour le réveiller)$"
    ),
    "click_rate": re.compile(
        r"^Click : (?P<count>\d+) notification\(s\) en (?P<span>[0-9.]+) s \((?P<rate>[0-9.]+) par seconde\)$"
    ),
    "click_press": re.compile(
        r"^Click : (?P<ev>PLUS_SHORT|MINUS_SHORT|PLUS_LONG|MINUS_LONG|plus_short|minus_short|plus_long|minus_long)$"
    ),
    "click_not_found": re.compile(
        r"^(?:Click : )?Zwift Click introuvable \(appuyez sur un bouton\)$"
    ),
    "journal_write_error": re.compile(r"^Écriture du journal impossible : (?P<err>.+)$"),
    "fit_export_error": re.compile(r"^Export FIT impossible : (?P<err>.+)$"),
}


@dataclass
class FtmsReport:
    """Statistiques de la trace Control Point FTMS (lot Q3)."""
    writes: dict[str, int] = field(default_factory=dict)
    delays_ms: list[float] = field(default_factory=list)
    delay_median_ms: float | None = None
    delay_p95_ms: float | None = None
    delay_max_ms: float | None = None
    timeouts: int = 0
    third_party_statuses: int = 0
    echo_statuses: int = 0
    third_party_status_details: list[str] = field(default_factory=list)
    echo_status_details: list[str] = field(default_factory=list)

    @property
    def total_writes(self) -> int:
        return sum(self.writes.values())

    @property
    def has_trace(self) -> bool:
        return bool(self.writes or self.delays_ms or self.timeouts or self.third_party_statuses or self.echo_statuses)

@dataclass
class TrainerReport:
    connections: int = 0
    disconnections: int = 0
    reconnections: int = 0
    control_refusals: int = 0
    connected_duration_s: float = 0.0
    lost_duration_s: float = 0.0
    devices: list[str] = field(default_factory=list)


@dataclass
class ClickDrop:
    """Une coupure du Click (lot K8). Les champs `None` manquent dans les anciens journaux."""
    timestamp: str
    connected_s: float | None = None          # depuis la connexion précédente (horodatages)
    since_notification_s: float | None = None
    since_press_s: float | None = None
    notifications: int | None = None
    since_trainer_write_s: float | None = None
    reason: str | None = None
    nearest_trainer_event_s: float | None = None   # écart au plus proche événement trainer du journal
    trainer_correlated: bool = False


@dataclass
class ClickReport:
    connections: int = 0
    disconnections: int = 0
    failed_attempts: int = 0
    presses: dict[str, int] = field(
        default_factory=lambda: {
            "plus_short": 0,
            "minus_short": 0,
            "plus_long": 0,
            "minus_long": 0,
        }
    )
    # Lot K8
    connection_durations_s: list[float] = field(default_factory=list)
    connection_min_s: float | None = None
    connection_median_s: float | None = None
    connection_max_s: float | None = None
    reconnect_delays_s: list[float] = field(default_factory=list)
    reconnect_delay_median_s: float | None = None
    reconnect_delay_max_s: float | None = None
    search_durations_s: list[float] = field(default_factory=list)
    since_press_at_drop_s: list[float] = field(default_factory=list)
    notification_rates: list[float] = field(default_factory=list)
    notification_rate_min: float | None = None
    notification_rate_avg: float | None = None
    drops: list[ClickDrop] = field(default_factory=list)
    trainer_correlated_drops: int = 0


@dataclass
class PauseEvent:
    timestamp: str
    from_state: str
    to_state: str
    reason: str | None = None


@dataclass
class PerfReport:
    count: int = 0
    step_p50_max_ms: float = 0.0
    step_p99_max_ms: float = 0.0
    step_max_ms: float = 0.0
    lag_p99_max_ms: float = 0.0
    lag_max_ms: float = 0.0
    cpu_max_pct: float = 0.0
    step_p99_breaches: int = 0
    lag_p99_breaches: int = 0
    cpu_breaches: int = 0
    max_consecutive_step_breaches: int = 0
    max_consecutive_lag_breaches: int = 0
    max_consecutive_cpu_breaches: int = 0


@dataclass
class Report:
    start: str | None = None
    end: str | None = None
    duration_s: float = 0.0
    trainer_mode: str | None = None
    input_mode: str | None = None
    trainer: TrainerReport = field(default_factory=TrainerReport)
    ftms: FtmsReport = field(default_factory=FtmsReport)
    click: ClickReport = field(default_factory=ClickReport)
    pauses: list[PauseEvent] = field(default_factory=list)
    transitions: list[PauseEvent] = field(default_factory=list)
    perf: PerfReport = field(default_factory=PerfReport)
    rust_threshold_reached: bool = False
    fit_path: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unreadable_lines: int = 0
    sessions_count: int = 1
    sessions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_ts(ts_str: str) -> datetime | None:
    try:
        return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S,%f")
    except ValueError:
        return None


def _split_sessions(lines: Iterable[str]) -> list[list[str]]:
    """Découpe les lignes en lancements sur 'Core démarré'.

    Les lignes précédant le premier 'Core démarré' (ex. chargement initial du parcours
    en autostart) sont rattachées au premier lancement.
    """
    chunks: list[list[str]] = []
    current: list[str] = []
    seen_start = False

    for raw in lines:
        line = raw.rstrip("\r\n")
        m = LINE_RE.match(line)
        if m and PATTERNS["core_started"].match(m.group("msg")):
            if seen_start and current:
                chunks.append(current)
                current = []
            seen_start = True
        current.append(line)

    if current:
        chunks.append(current)
    return chunks


def _analyse_single_session(lines: list[str]) -> Report:
    rep = Report()
    first_dt: datetime | None = None
    last_dt: datetime | None = None

    trainer_up_since: datetime | None = None
    trainer_lost_since: datetime | None = None

    consec_step = 0
    consec_lag = 0
    consec_cpu = 0

    # Par boîtier (le Click récent en a deux, « + » et « − ») ; clé None : ligne sans adresse.
    click_up_since: dict[str | None, datetime] = {}
    click_down_since: dict[str | None, datetime] = {}
    click_drop_dts: list[datetime | None] = []
    trainer_event_dts: list[datetime] = []

    for line in lines:
        m = LINE_RE.match(line)
        if not m:
            if line.strip():
                rep.unreadable_lines += 1
            continue
        ts_str = m.group("ts")
        level = m.group("level")
        msg = m.group("msg")
        dt = _parse_ts(ts_str)
        if dt is not None:
            if first_dt is None:
                first_dt = dt
                rep.start = ts_str
            last_dt = dt
            rep.end = ts_str

        if dt is not None and (m.group("logger") == "ftms_driver" or msg.startswith("Trainer ")):
            trainer_event_dts.append(dt)

        if level == "ERROR":
            rep.errors.append(f"{ts_str} {msg}")
        elif level == "WARNING":
            rep.warnings.append(f"{ts_str} {msg}")

        m_start = PATTERNS["core_started"].match(msg)
        if m_start:
            rep.trainer_mode = m_start.group("trainer")
            rep.input_mode = m_start.group("input")
            continue

        m_tr_conn = PATTERNS["trainer_connected"].match(msg)
        if m_tr_conn:
            rep.trainer.connections += 1
            dev = m_tr_conn.group("device")
            if dev not in rep.trainer.devices:
                rep.trainer.devices.append(dev)
            if dt is not None:
                if trainer_lost_since is not None:
                    rep.trainer.lost_duration_s += max((dt - trainer_lost_since).total_seconds(), 0.0)
                    trainer_lost_since = None
                if trainer_up_since is None:
                    trainer_up_since = dt
            continue

        if PATTERNS["trainer_reconnect"].match(msg):
            rep.trainer.reconnections += 1
            continue

        if PATTERNS["trainer_warning"].match(msg) or PATTERNS["trainer_lost_pause"].match(msg):
            if trainer_lost_since is None:
                rep.trainer.disconnections += 1
                if dt is not None:
                    trainer_lost_since = dt
            if dt is not None and trainer_up_since is not None:
                rep.trainer.connected_duration_s += max((dt - trainer_up_since).total_seconds(), 0.0)
                trainer_up_since = None
            continue

        if PATTERNS["trainer_cmd_refused"].match(msg) or PATTERNS["trainer_control_refused_fatal"].match(msg):
            rep.trainer.control_refusals += 1
            continue

        m_ftms_w = FTMS_PATTERNS["write"].match(msg)
        if m_ftms_w:
            op = m_ftms_w.group("op")
            rep.ftms.writes[op] = rep.ftms.writes.get(op, 0) + 1
            continue

        m_ftms_r = FTMS_PATTERNS["response"].match(msg)
        if m_ftms_r:
            rep.ftms.delays_ms.append(float(m_ftms_r.group("ms")))
            continue

        m_ftms_to = FTMS_PATTERNS["timeout"].match(msg)
        if m_ftms_to:
            rep.ftms.timeouts += 1
            continue

        m_ftms_st = FTMS_PATTERNS["status"].match(msg)
        if m_ftms_st:
            origin = m_ftms_st.group("origin")
            if "écho" in origin:
                rep.ftms.echo_statuses += 1
                rep.ftms.echo_status_details.append(m_ftms_st.group("name"))
            else:
                rep.ftms.third_party_statuses += 1
                rep.ftms.third_party_status_details.append(m_ftms_st.group("name"))
            continue

        m_click_up = PATTERNS["click_connected"].match(msg)
        if m_click_up:
            rep.click.connections += 1
            if m_click_up.group("search") is not None:
                rep.click.search_durations_s.append(float(m_click_up.group("search")))
            if dt is not None:
                key = _click_key(m_click_up.group("address"))
                if key not in click_down_since and None in click_down_since and len(click_down_since) == 1:
                    key_down: str | None = None   # coupure d'un ancien journal, sans adresse
                else:
                    key_down = key
                if key_down in click_down_since:
                    down_dt = click_down_since.pop(key_down)
                    rep.click.reconnect_delays_s.append(round((dt - down_dt).total_seconds(), 3))
                click_up_since[key] = dt
            continue

        m_click_down = PATTERNS["click_disconnected"].match(msg)
        if m_click_down:
            rep.click.disconnections += 1
            drop = ClickDrop(timestamp=ts_str)
            if m_click_down.group("connected") is not None:
                drop.since_notification_s = _ago_s(m_click_down.group("since_notif"))
                drop.since_press_s = _ago_s(m_click_down.group("since_press"))
                drop.notifications = int(m_click_down.group("notifs"))
                drop.since_trainer_write_s = _ago_s(m_click_down.group("since_write"))
                drop.reason = m_click_down.group("reason")
                if drop.since_press_s is not None:
                    rep.click.since_press_at_drop_s.append(drop.since_press_s)
            if dt is not None:
                key = _click_key(m_click_down.group("address"))
                if key is None and len(click_up_since) == 1:
                    key = next(iter(click_up_since))   # un seul boîtier connecté : c'est lui
                if key is None and len(click_up_since) > 1:
                    # Ligne sans adresse et deux boîtiers connectés : durée lue dans la ligne.
                    if m_click_down.group("connected") is not None:
                        drop.connected_s = float(m_click_down.group("connected"))
                        rep.click.connection_durations_s.append(drop.connected_s)
                else:
                    if key in click_up_since:
                        drop.connected_s = round((dt - click_up_since.pop(key)).total_seconds(), 3)
                        rep.click.connection_durations_s.append(drop.connected_s)
                    click_down_since[key] = dt
            rep.click.drops.append(drop)
            click_drop_dts.append(dt)
            continue

        m_rate = PATTERNS["click_rate"].match(msg)
        if m_rate:
            rep.click.notification_rates.append(float(m_rate.group("rate")))
            continue

        if PATTERNS["click_not_found"].match(msg):
            rep.click.failed_attempts += 1
            continue

        m_press = PATTERNS["click_press"].match(msg)
        if m_press:
            key = m_press.group("ev").lower()
            rep.click.presses[key] = rep.click.presses.get(key, 0) + 1
            continue

        m_trans = PATTERNS["session_transition"].match(msg)
        if m_trans:
            ev = PauseEvent(
                timestamp=ts_str,
                from_state=m_trans.group("old"),
                to_state=m_trans.group("new"),
                reason=m_trans.group("reason"),
            )
            rep.transitions.append(ev)
            if ev.to_state == "PAUSED":
                rep.pauses.append(ev)
            continue

        m_perf = PATTERNS["perf"].match(msg)
        if m_perf:
            p = rep.perf
            p.count += 1
            step_p50 = float(m_perf.group("step_p50"))
            step_p99 = float(m_perf.group("step_p99"))
            step_max = float(m_perf.group("step_max"))
            lag_p99 = float(m_perf.group("lag_p99"))
            lag_max = float(m_perf.group("lag_max"))
            cpu = float(m_perf.group("cpu"))

            p.step_p50_max_ms = max(p.step_p50_max_ms, step_p50)
            p.step_p99_max_ms = max(p.step_p99_max_ms, step_p99)
            p.step_max_ms = max(p.step_max_ms, step_max)
            p.lag_p99_max_ms = max(p.lag_p99_max_ms, lag_p99)
            p.lag_max_ms = max(p.lag_max_ms, lag_max)
            p.cpu_max_pct = max(p.cpu_max_pct, cpu)

            if step_p99 > STEP_P99_LIMIT_MS:
                p.step_p99_breaches += 1
                consec_step += 1
                p.max_consecutive_step_breaches = max(p.max_consecutive_step_breaches, consec_step)
            else:
                consec_step = 0

            if lag_p99 > LAG_P99_LIMIT_MS:
                p.lag_p99_breaches += 1
                consec_lag += 1
                p.max_consecutive_lag_breaches = max(p.max_consecutive_lag_breaches, consec_lag)
            else:
                consec_lag = 0

            if cpu > CPU_LIMIT_PCT:
                p.cpu_breaches += 1
                consec_cpu += 1
                p.max_consecutive_cpu_breaches = max(p.max_consecutive_cpu_breaches, consec_cpu)
            else:
                consec_cpu = 0

            if (
                p.max_consecutive_step_breaches >= CONSECUTIVE_BREACHES
                or p.max_consecutive_lag_breaches >= CONSECUTIVE_BREACHES
                or p.max_consecutive_cpu_breaches >= CONSECUTIVE_BREACHES
            ):
                rep.rust_threshold_reached = True
            continue

    if first_dt is not None and last_dt is not None:
        rep.duration_s = round(max((last_dt - first_dt).total_seconds(), 0.0), 3)
        if trainer_up_since is not None:
            rep.trainer.connected_duration_s += max((last_dt - trainer_up_since).total_seconds(), 0.0)
        if trainer_lost_since is not None:
            rep.trainer.lost_duration_s += max((last_dt - trainer_lost_since).total_seconds(), 0.0)

    rep.trainer.connected_duration_s = round(rep.trainer.connected_duration_s, 3)
    rep.trainer.lost_duration_s = round(rep.trainer.lost_duration_s, 3)

    for drop, ddt in zip(rep.click.drops, click_drop_dts):
        if ddt is not None and trainer_event_dts:
            drop.nearest_trainer_event_s = round(
                min(abs((t - ddt).total_seconds()) for t in trainer_event_dts), 3)
    _finalize_click(rep.click)
    _finalize_ftms(rep.ftms)
    return rep


def _click_key(address: str | None) -> str | None:
    return address.strip().upper() if address else None


def _ago_s(text: str) -> float | None:
    return None if text == "jamais" else float(text.removesuffix(" s"))



def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * 0.95
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return round(s[int(k)], 1)
    d0 = s[int(f)] * (c - k)
    d1 = s[int(c)] * (k - f)
    return round(d0 + d1, 1)


def _finalize_ftms(f: FtmsReport) -> None:
    if f.delays_ms:
        f.delay_median_ms = round(statistics.median(f.delays_ms), 1)
        f.delay_p95_ms = _p95(f.delays_ms)
        f.delay_max_ms = round(max(f.delays_ms), 1)

def _finalize_click(c: ClickReport) -> None:
    """Statistiques dérivées des listes de la section Click (aussi après fusion de lancements)."""
    d = sorted(c.connection_durations_s)
    c.connection_min_s = d[0] if d else None
    c.connection_max_s = d[-1] if d else None
    c.connection_median_s = round(statistics.median(d), 3) if d else None
    r = c.reconnect_delays_s
    c.reconnect_delay_median_s = round(statistics.median(r), 3) if r else None
    c.reconnect_delay_max_s = max(r) if r else None
    n = c.notification_rates
    c.notification_rate_min = min(n) if n else None
    c.notification_rate_avg = round(sum(n) / len(n), 2) if n else None
    for drop in c.drops:
        drop.trainer_correlated = any(
            v is not None and v <= CORRELATION_WINDOW_S
            for v in (drop.since_trainer_write_s, drop.nearest_trainer_event_s))
    c.trainer_correlated_drops = sum(1 for drop in c.drops if drop.trainer_correlated)


def _merge_reports(reports: list[Report]) -> Report:
    if not reports:
        return Report(sessions_count=0)
    if len(reports) == 1:
        r = reports[0]
        r.sessions_count = 1
        return r

    merged = Report(
        start=reports[0].start,
        end=reports[-1].end,
        duration_s=round(sum(r.duration_s for r in reports), 3),
        trainer_mode=reports[-1].trainer_mode,
        input_mode=reports[-1].input_mode,
        sessions_count=len(reports),
        sessions=[r.to_dict() for r in reports],
    )
    for r in reports:
        merged.trainer.connections += r.trainer.connections
        merged.trainer.disconnections += r.trainer.disconnections
        merged.trainer.reconnections += r.trainer.reconnections
        merged.trainer.control_refusals += r.trainer.control_refusals
        merged.trainer.connected_duration_s = round(
            merged.trainer.connected_duration_s + r.trainer.connected_duration_s, 3
        )
        merged.trainer.lost_duration_s = round(
            merged.trainer.lost_duration_s + r.trainer.lost_duration_s, 3
        )
        for d in r.trainer.devices:
            if d not in merged.trainer.devices:
                merged.trainer.devices.append(d)

        merged.click.connections += r.click.connections
        merged.click.disconnections += r.click.disconnections
        merged.click.failed_attempts += r.click.failed_attempts
        for k, v in r.click.presses.items():
            merged.click.presses[k] = merged.click.presses.get(k, 0) + v
        merged.click.connection_durations_s.extend(r.click.connection_durations_s)
        merged.click.reconnect_delays_s.extend(r.click.reconnect_delays_s)
        merged.click.search_durations_s.extend(r.click.search_durations_s)
        merged.click.since_press_at_drop_s.extend(r.click.since_press_at_drop_s)
        merged.click.notification_rates.extend(r.click.notification_rates)
        merged.click.drops.extend(r.click.drops)

        merged.pauses.extend(r.pauses)
        merged.transitions.extend(r.transitions)

        mp, rp = merged.perf, r.perf
        mp.count += rp.count
        mp.step_p50_max_ms = max(mp.step_p50_max_ms, rp.step_p50_max_ms)
        mp.step_p99_max_ms = max(mp.step_p99_max_ms, rp.step_p99_max_ms)
        mp.step_max_ms = max(mp.step_max_ms, rp.step_max_ms)
        mp.lag_p99_max_ms = max(mp.lag_p99_max_ms, rp.lag_p99_max_ms)
        mp.lag_max_ms = max(mp.lag_max_ms, rp.lag_max_ms)
        mp.cpu_max_pct = max(mp.cpu_max_pct, rp.cpu_max_pct)
        mp.step_p99_breaches += rp.step_p99_breaches
        mp.lag_p99_breaches += rp.lag_p99_breaches
        mp.cpu_breaches += rp.cpu_breaches
        mp.max_consecutive_step_breaches = max(
            mp.max_consecutive_step_breaches, rp.max_consecutive_step_breaches
        )
        mp.max_consecutive_lag_breaches = max(
            mp.max_consecutive_lag_breaches, rp.max_consecutive_lag_breaches
        )
        mp.max_consecutive_cpu_breaches = max(
            mp.max_consecutive_cpu_breaches, rp.max_consecutive_cpu_breaches
        )
        if r.rust_threshold_reached:
            merged.rust_threshold_reached = True
        if r.fit_path:
            merged.fit_path = r.fit_path

        mf, rf = merged.ftms, r.ftms
        for op, count in rf.writes.items():
            mf.writes[op] = mf.writes.get(op, 0) + count
        mf.delays_ms.extend(rf.delays_ms)
        mf.timeouts += rf.timeouts
        mf.third_party_statuses += rf.third_party_statuses
        mf.echo_statuses += rf.echo_statuses
        mf.third_party_status_details.extend(rf.third_party_status_details)
        mf.echo_status_details.extend(rf.echo_status_details)
        merged.errors.extend(r.errors)
        merged.warnings.extend(r.warnings)
        merged.unreadable_lines += r.unreadable_lines

    _finalize_click(merged.click)
    _finalize_ftms(merged.ftms)
    return merged


def analyse(lines: Iterable[str], all_sessions: bool = False) -> Report:
    """Analyse un flux de lignes de journal et renvoie un Report structuré."""
    chunks = _split_sessions(lines)
    if not chunks:
        return Report(sessions_count=0)
    if not all_sessions:
        rep = _analyse_single_session(chunks[-1])
        rep.sessions_count = 1
        return rep
    reports = [_analyse_single_session(c) for c in chunks]
    return _merge_reports(reports)



def _format_ftms_details(f: FtmsReport) -> list[str]:
    """Lignes de la trace FTMS (lot Q3) ; section absente sans trace."""
    if not f.has_trace:
        return []
    writes_desc = ", ".join(f"{op} {count}" for op, count in sorted(f.writes.items()))
    w_str = f"{f.total_writes} écriture(s)" + (f" ({writes_desc})" if writes_desc else "")
    lines = [f"Commandes FTMS : {w_str}"]
    if f.delays_ms:
        med = f"{f.delay_median_ms:.1f} ms" if f.delay_median_ms is not None else "?"
        p95_val = f"{f.delay_p95_ms:.1f} ms" if f.delay_p95_ms is not None else "?"
        max_val = f"{f.delay_max_ms:.1f} ms" if f.delay_max_ms is not None else "?"
        lines.append(f"                 délai écriture → accusé : médiane {med}, p95 {p95_val}, max {max_val} ; {f.timeouts} expiration(s)")
    elif f.timeouts:
        lines.append(f"                 délai écriture → accusé : aucun accusé ; {f.timeouts} expiration(s)")
    if f.third_party_statuses or f.echo_statuses:
        lines.append(f"                 statuts : {f.third_party_statuses} par un tiers, {f.echo_statuses} écho(s) probable(s)")
    return lines

def format_report(rep: Report) -> str:
    """Formate le rapport en français lisible (~10 lignes)."""
    pr = rep.click.presses
    total_presses = sum(pr.values())
    pauses_desc = (
        ", ".join(f"{p.timestamp.split()[-1]} ({p.reason or 'sans raison'})" for p in rep.pauses)
        if rep.pauses
        else "aucune"
    )
    rust_str = "OUI (seuil franchi 3x consécutives)" if rep.rust_threshold_reached else "non"
    lines = [
        f"Séance : {rep.start or '?'} -> {rep.end or '?'} ({rep.duration_s:.1f} s, {rep.sessions_count} lancement(s))",
        f"Modes  : trainer={rep.trainer_mode or '?'}, entrées={rep.input_mode or '?'}",
        f"Trainer: {rep.trainer.connections} connexion(s), {rep.trainer.disconnections} perte(s), "
        f"{rep.trainer.reconnections} reconnexion(s), {rep.trainer.control_refusals} refus "
        f"(connecté {rep.trainer.connected_duration_s:.1f} s / perdu {rep.trainer.lost_duration_s:.1f} s)",
        *_format_ftms_details(rep.ftms),
        f"Click  : {rep.click.connections} connexion(s), {rep.click.disconnections} déconnexion(s), "
        f"{rep.click.failed_attempts} échec(s) de scan",
        f"Appuis : {total_presses} (court +{pr['plus_short']} / -{pr['minus_short']}, "
        f"long +{pr['plus_long']} / -{pr['minus_long']})",
        *_format_click_details(rep.click),
        f"Pauses : {len(rep.pauses)} ({pauses_desc})",
        f"Perf   : {rep.perf.count} relevé(s) — pas p99 max {rep.perf.step_p99_max_ms:.2f} ms "
        f"(seuil {STEP_P99_LIMIT_MS} ms), retard p99 max {rep.perf.lag_p99_max_ms:.1f} ms "
        f"(seuil {LAG_P99_LIMIT_MS} ms), CPU max {rep.perf.cpu_max_pct:.1f} % (seuil {CPU_LIMIT_PCT} %)",
        f"Rust   : seuil SRS §14.1 atteint = {rust_str}",
        f"Alertes: {len(rep.errors)} erreur(s), {len(rep.warnings)} avertissement(s)",
    ]
    return "\n".join(lines)


def _fmt_s(v: float | None) -> str:
    return "?" if v is None else f"{v:.1f} s"


def _format_click_details(c: ClickReport) -> list[str]:
    """Lignes du diagnostic des coupures (lot K8), seulement s'il y a de quoi dire."""
    out: list[str] = []
    if c.connection_durations_s:
        out.append(f"         connexions : min {_fmt_s(c.connection_min_s)}, médiane {_fmt_s(c.connection_median_s)}, "
                   f"max {_fmt_s(c.connection_max_s)} ; reconnexion médiane {_fmt_s(c.reconnect_delay_median_s)}, "
                   f"max {_fmt_s(c.reconnect_delay_max_s)}")
    if c.notification_rates:
        out.append(f"         notifications : {c.notification_rate_avg:.1f}/s en moyenne, "
                   f"min {c.notification_rate_min:.1f}/s")
    if c.drops:
        presses = ", ".join(f"{v:.0f} s" for v in c.since_press_at_drop_s) or "?"
        out.append(f"         coupures : dernier appui avant coupure {presses} ; "
                   f"{c.trainer_correlated_drops}/{len(c.drops)} à moins de {CORRELATION_WINDOW_S:.0f} s "
                   "d'une écriture ou d'un événement du trainer")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m openride_core.tools.log_report",
        description="Analyse un journal de séance OpenRide (~/run_trainer.log par défaut).",
    )
    parser.add_argument(
        "journal",
        nargs="?",
        type=Path,
        default=DEFAULT_LOG_PATH,
        help="Chemin du journal à analyser (défaut : ~/run_trainer.log)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Sortie JSON structurée pour l'automatisation",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="all_sessions",
        help="Analyse tous les lancements présents dans le fichier (défaut : dernier lancement)",
    )
    args = parser.parse_args(argv)

    path = Path(args.journal).expanduser()
    if not path.is_file():
        print(f"Erreur : fichier journal introuvable : {path}", file=sys.stderr)
        return 1

    with path.open(encoding="utf-8", errors="replace") as fh:
        rep = analyse(fh, all_sessions=args.all_sessions)

    if args.as_json:
        print(json.dumps(rep.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_report(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
