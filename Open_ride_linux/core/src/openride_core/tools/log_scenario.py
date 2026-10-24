"""Scénario de Bluetooth simulé tiré d'un journal du core (lot M5).

    python -m openride_core.tools.log_scenario [JOURNAL] [-o scenario.json] [--session N]
                                               [--from S] [--to S]

Relit `~/run_victory.log` (par défaut, dernière séance) et écrit un scénario au format de
`sim_scenarios.py` : la même suite de connexions, coupures, erreurs et appuis, rejouable par
`openride-core run --trainer sim --input sim --hr sim --sim-scenario scenario.json`.

Temps du scénario : secondes depuis la ligne « Core démarré » de la séance choisie ; `--from`
et `--to` gardent une fenêtre, temps recalés sur `--from`.

Correspondances :
- trainer : première connexion → `appear_at` ; « Reconnexion au trainer » sans erreur juste
  avant → `drop` ; « plus de données du trainer » → `silence` (commencé `FORCE_RECONNECT_S`
  plus tôt, jusqu'à la connexion suivante) ; erreur ATT lue (« ATT error: 0xNN », « renvoi »)
  → `att_error` avec le code ; « contrôle FTMS perdu » (0xFF) → `control_lost` ; commande
  refusée → `control_lost`, ou `refuse_control` si la séance a fini sur un refus du contrôle ;
- Click, par boîtier (adresse de `click_address` du simulateur, « …E7 », = `click_plus`,
  sinon `click_minus`) : première connexion → `appear_at`, coupure → `drop`, reconnexion
  suivante → `wake` ; appuis → `press` (long : 1 s) ;
- ceinture : première connexion → `appear_at`, coupure → `drop`.
Le reste (pauses, performances de la boucle, transitions) n'a pas d'équivalent : compté dans
le résumé écrit sur la sortie d'erreur.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from ..ftms_driver import FORCE_RECONNECT_S
from ..sim_scenarios import PLUS_ADDRESS, SimScenarioError, validate
from .log_report import DEFAULT_LOG_PATH, LINE_RE, PATTERNS, _click_key, _parse_ts, _split_sessions

# Lignes utiles absentes de `log_report.PATTERNS` (vérifiées contre le code source par
# `test_log_scenario.py`, comme `log_report.CORE_FORMAT_STRINGS`).
EXTRA_FORMAT_STRINGS: dict[str, tuple[str, str]] = {
    "hr_connected": ("hr_monitor.py", "Ceinture cardio connectée (%s)"),
    "hr_disconnected": ("hr_monitor.py", "Ceinture cardio déconnectée après %.1f s"),
    "trainer_control_lost": ("ftms_driver.py",
                             "Trainer : contrôle FTMS perdu (Fitness Machine Status 0xFF)"),
    "trainer_att_retry": ("ftms_driver.py",
                          "Trainer : écriture 0x%02x refusée (ATT 0x%02x), renvoi %d/%d"),
}
EXTRA_PATTERNS: dict[str, re.Pattern[str]] = {
    "hr_connected": re.compile(r"^Ceinture cardio connectée \((?P<device>.+)\)$"),
    "hr_disconnected": re.compile(r"^Ceinture cardio déconnectée après (?P<connected>[0-9.]+) s$"),
}
ATT_RE = re.compile(r"ATT (?:error: )?0x(?P<code>[0-9a-fA-F]{1,2})\b", re.IGNORECASE)
CONNECT_LEAD_S = 0.5   # l'appareil s'annonce un peu avant la ligne « connecté »
LONG_PRESS_S = 1.0
DROP_AFTER_ERROR_S = 0.5   # « Reconnexion » juste après une erreur du trainer : pas une coupure


class LogScenarioError(Exception):
    """Journal introuvable, illisible ou sans séance ; message lisible."""


def _box(address: str | None, last: str | None) -> str:
    addr = _click_key(address) or last
    return "click_plus" if addr == PLUS_ADDRESS else "click_minus"


def convert(lines: list[str], session: int | None = None, t_from: float | None = None,
            t_to: float | None = None, source: str = "") -> tuple[dict[str, Any], dict[str, Any]]:
    """Renvoie (scénario validé, résumé) pour la séance `session` (1 = première ; défaut : dernière)."""
    chunks = [c for c in _split_sessions(lines)
              if any(PATTERNS["core_started"].match(m.group("msg"))
                     for m in map(LINE_RE.match, c) if m)]
    if not chunks:
        raise LogScenarioError("aucune séance (ligne « Core démarré ») dans ce journal")
    if session is None:
        session = len(chunks)
    if not 1 <= session <= len(chunks):
        raise LogScenarioError(f"séance {session} absente : le journal en compte {len(chunks)}")
    chunk = chunks[session - 1]

    parsed: list[tuple[float, str]] = []
    t0: datetime | None = None
    for raw in chunk:
        m = LINE_RE.match(raw)
        if not m:
            continue
        dt = _parse_ts(m.group("ts"))
        if dt is None:
            continue
        msg = m.group("msg")
        if t0 is None and PATTERNS["core_started"].match(msg):
            t0 = dt
        parsed.append((dt.timestamp(), msg))
    assert t0 is not None
    base = t0.timestamp()
    rows = [(max(ts - base, 0.0), msg) for ts, msg in parsed]
    fatal_refusal = any(PATTERNS["trainer_control_refused_fatal"].match(msg) for _, msg in rows)

    events: list[dict[str, Any]] = []
    first: dict[str, float] = {}
    ignored: dict[str, int] = {}
    last_warn: tuple[float, str] | None = None   # dernier avertissement du trainer (t, sorte)
    last_control_lost: float | None = None
    pending_silence: float | None = None
    asleep_boxes: set[str] = set()
    last_click: str | None = None
    refused = False

    def ev(t: float, action: str, device: str | None = None, **extra: Any) -> None:
        e: dict[str, Any] = {"t": round(t, 2), "action": action}
        if device is not None:
            e["device"] = device
        e.update(extra)
        events.append(e)

    for t, msg in rows:
        if PATTERNS["trainer_connected"].match(msg):
            first.setdefault("trainer", t)
            if pending_silence is not None:
                start = max(pending_silence, 0.0)
                ev(start, "silence", "trainer", seconds=round(max(t - start, 0.1), 2))
                pending_silence = None
        elif PATTERNS["trainer_reconnect"].match(msg):
            if last_warn is not None and t - last_warn[0] <= DROP_AFTER_ERROR_S:
                if last_warn[1] == "link":   # exception de liaison juste avant : coupure
                    ev(last_warn[0], "drop", "trainer")
            else:
                ev(t, "drop", "trainer")   # liaison perdue (rappel de déconnexion)
            last_warn = None
        elif msg == EXTRA_FORMAT_STRINGS["trainer_control_lost"][1]:
            ev(t, "control_lost", "trainer")
            last_control_lost = t
        elif (m := PATTERNS["trainer_cmd_refused"].match(msg)):
            if fatal_refusal and not refused:
                ev(t, "refuse_control", "trainer")
                refused = True
            elif not fatal_refusal and (last_control_lost is None or t - last_control_lost > 2.0):
                ev(t, "control_lost", "trainer")
        elif (m := PATTERNS["trainer_warning"].match(msg)):
            err = m.group("err")
            att = ATT_RE.search(err)
            if "plus de données" in err:
                pending_silence = t - FORCE_RECONNECT_S
                last_warn = (t, "silence")
            elif att:
                ev(t, "att_error", "trainer", code=int(att.group("code"), 16), count=1)
                last_warn = (t, "att")
            else:
                # Exception de liaison (coupure si une reconnexion suit) ou simple information.
                last_warn = (t, "link")
                ignored["trainer_info"] = ignored.get("trainer_info", 0) + 1
        elif (m := PATTERNS["click_connected"].match(msg)):
            box = _box(m.group("address"), last_click)
            last_click = _click_key(m.group("address")) or last_click
            first.setdefault(box, t)
            if box in asleep_boxes:
                ev(max(t - CONNECT_LEAD_S, 0.0), "wake", box)
                asleep_boxes.discard(box)
        elif (m := PATTERNS["click_disconnected"].match(msg)):
            box = _box(m.group("address"), last_click)
            ev(t, "drop", box)
            asleep_boxes.add(box)
        elif (m := PATTERNS["click_press"].match(msg)):
            name = m.group("ev").upper()
            extra = {"duration_s": LONG_PRESS_S} if name.endswith("LONG") else {}
            ev(t, "press", button="+" if name.startswith("PLUS") else "-", **extra)
        elif EXTRA_PATTERNS["hr_connected"].match(msg):
            first.setdefault("hr", t)
        elif EXTRA_PATTERNS["hr_disconnected"].match(msg):
            ev(t, "drop", "hr")
        elif not PATTERNS["core_started"].match(msg):
            key = next((k for k, p in PATTERNS.items() if p.match(msg)), "autre")
            ignored[key] = ignored.get(key, 0) + 1

    # Fenêtre --from / --to
    lo = t_from or 0.0
    kept = [e for e in events if e["t"] >= lo and (t_to is None or e["t"] <= t_to)]
    for e in kept:
        e["t"] = round(e["t"] - lo, 2)

    def appear(key: str) -> float:
        return round(max(first[key] - CONNECT_LEAD_S - lo, 0.0), 2)

    spec: dict[str, Any] = {"description": f"Tiré de {source or 'journal'}, séance {session}"
                            + (f", fenêtre {lo:g} à {t_to:g} s" if t_from or t_to else "")}
    if "trainer" in first:
        spec["trainer"] = {"appear_at": appear("trainer"), "connect_delay_s": 0.3}
    if "click_plus" in first or "click_minus" in first:
        click: dict[str, Any] = {"connect_delay_s": 0.3}
        for key, role in (("click_plus", "plus"), ("click_minus", "minus")):
            click[role] = {"appear_at": appear(key)} if key in first else {"asleep": True}
        spec["click"] = click
    if "hr" in first:
        spec["hr"] = {"appear_at": appear("hr"), "connect_delay_s": 0.2}
    spec["events"] = sorted(kept, key=lambda e: e["t"])

    summary = {"source": source, "session": session, "sessions": len(chunks),
               "window": [lo, t_to], "events": len(kept),
               "dropped_outside_window": len(events) - len(kept), "ignored": ignored}
    candidate = dict(spec, source={"path": source, "session": session, "window": [lo, t_to]})
    try:
        return validate(candidate), summary
    except SimScenarioError:
        summary["source_key"] = "refusée par validate : source gardée dans la description"
    return validate(spec), summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m openride_core.tools.log_scenario",
                                description="Scénario de Bluetooth simulé tiré d'un journal du core.")
    p.add_argument("journal", nargs="?", type=Path, default=DEFAULT_LOG_PATH,
                   help=f"journal du core (défaut : {DEFAULT_LOG_PATH})")
    p.add_argument("-o", "--output", type=Path, help="fichier JSON écrit (défaut : sortie standard)")
    p.add_argument("--session", type=int, help="numéro de séance, 1 = première (défaut : dernière)")
    p.add_argument("--from", dest="t_from", type=float, help="début de la fenêtre (s)")
    p.add_argument("--to", dest="t_to", type=float, help="fin de la fenêtre (s)")
    a = p.parse_args(argv)
    try:
        try:
            lines = a.journal.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            raise LogScenarioError(f"lecture impossible de {a.journal} : {exc.strerror or exc}") \
                from None
        spec, summary = convert(lines, a.session, a.t_from, a.t_to, str(a.journal))
    except (LogScenarioError, SimScenarioError) as exc:
        print(f"log_scenario : {exc}", file=sys.stderr)
        return 1
    text = json.dumps(spec, ensure_ascii=False, indent=2)
    if a.output:
        a.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    ign = ", ".join(f"{k} {v}" for k, v in sorted(summary["ignored"].items())) or "aucune"
    print(f"Séance {summary['session']}/{summary['sessions']} : {summary['events']} événement(s) ; "
          f"lignes sans équivalent : {ign}"
          + (f" ; {summary['source_key']}" if "source_key" in summary else ""), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
