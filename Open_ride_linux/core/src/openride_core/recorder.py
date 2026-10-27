"""Enregistrement d'une séance : journal sur disque, copie en mémoire, FIT (SRS §9, contrat IPC §6).

Le journal JSONL protège la séance contre un plantage du programme. Une copie en mémoire
protège contre une panne d'écriture (disque plein, fichier fermé) :
- une erreur d'écriture ne remonte jamais vers la boucle du core : elle est signalée une fois
  par `on_failure`, l'écriture sur disque s'arrête et la mémoire continue ;
- `reopen()` ouvre un nouveau journal et y réécrit toute la séance depuis la mémoire ;
- le FIT est produit depuis la mémoire, donc même si le journal est inutilisable.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from .fit_export import Summary, default_fit_path, summarize, write_fit
from .journal import TIMER_EVENTS, JournalWriter, Record

log = logging.getLogger("recorder")

WRITE_ERRORS = (OSError, ValueError)


class SessionRecorder:
    def __init__(self, journal_dir: Path, route_id: str | None,
                 on_failure: Callable[[Exception], None] | None = None,
                 fit_dir: Path | None = None, workout_id: str | None = None,
                 resume_path: Path | None = None, lines: list[dict] | None = None,
                 source: str | None = None, plan: dict | None = None) -> None:
        """Nouvelle séance, ou suite d'une séance (`resume_path` et ses `lines`, lot N8).

        En reprise, le journal existant est continué sans nouvel en-tête et les lignes déjà
        écrites sont reprises en mémoire : le FIT final contient toute la séance.
        """
        self.journal_dir = journal_dir
        self.route_id = route_id
        self.workout_id = workout_id
        self.source = source             # origine de la séance pour la progression (lot V2)
        self.plan = plan   # séance d'un plan d'entraînement actif (lot O11), en-tête du journal
        self.on_failure = on_failure
        self.fit_dir = fit_dir
        self.lines: list[dict] = list(lines or [])   # séance complète, dans l'ordre : événements et relevés
        self.failed = False
        self.path: Path | None = None
        self._writer: JournalWriter | None = None
        self._reopen_count = 0
        if resume_path is not None:
            self._open(resume_path, header=False)
        else:
            self._open(self._new_path())

    # --- fichier -------------------------------------------------------------------------

    def _new_path(self) -> Path:
        stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        suffix = f"_reprise-{self._reopen_count}" if self._reopen_count else ""
        return self.journal_dir / f"{stamp}{suffix}.jsonl"

    def _open(self, path: Path, header: bool = True) -> bool:
        try:
            self._writer = JournalWriter(path, route_id=self.route_id, workout_id=self.workout_id,
                                         header=header, source=self.source, plan=self.plan)
            self.path = path
            return True
        except WRITE_ERRORS as exc:
            self._fail(exc)
            return False

    def _fail(self, exc: Exception) -> None:
        first = not self.failed
        self.failed = True
        if self._writer is not None:
            try:
                self._writer.close()
            except WRITE_ERRORS:
                pass
            self._writer = None
        log.error("Écriture du journal impossible : %s", exc)
        if first and self.on_failure:
            self.on_failure(exc)

    def _write(self, line: dict) -> None:
        if self.failed or self._writer is None:
            return
        try:
            if line["kind"] == "event":
                self._writer.event(line["event"], line["ts"])
            elif line["kind"] == "device":
                self._writer.device(line["device"], line["state"], line["ts"])
            else:
                fields = {k: v for k, v in line.items() if k != "kind"}
                self._writer.record(Record(**fields))
        except WRITE_ERRORS as exc:
            self._fail(exc)

    # --- API -----------------------------------------------------------------------------

    def event(self, name: str, ts: float) -> None:
        line = {"kind": "event", "event": name, "ts": ts}
        self.lines.append(line)
        self._write(line)

    def device(self, device: str, state: str, ts: float) -> None:
        """Coupure ou retour d'un appareil (lot M4) ; absent du FIT (`records`, `events`)."""
        line = {"kind": "device", "ts": ts, "device": device, "state": state}
        self.lines.append(line)
        self._write(line)

    def record(self, rec: Record) -> None:
        line = {"kind": "record", **asdict(rec)}
        self.lines.append(line)
        self._write(line)

    def reopen(self) -> bool:
        """Après une panne : nouveau journal contenant toute la séance. Renvoie le succès."""
        if not self.failed:
            return True
        self._reopen_count += 1
        self.failed = False
        if not self._open(self._new_path()):
            return False
        for line in self.lines:
            self._write(line)
            if self.failed:
                return False
        log.info("Journal rouvert : %s (%d lignes réécrites)", self.path, len(self.lines))
        return True

    @property
    def records(self) -> list[dict]:
        return [ln for ln in self.lines if ln["kind"] == "record"]

    @property
    def events(self) -> list[dict]:
        return [ln for ln in self.lines if ln["kind"] == "event" and ln["event"] in TIMER_EVENTS]

    def finish(self, save: bool, ts: float | None = None) -> tuple[Path | None, Summary, str | None]:
        """Clôt la séance. Renvoie (chemin du FIT ou None, résumé, erreur éventuelle du FIT)."""
        self.event("stop", ts if ts is not None else time.time())
        if self._writer is not None:
            try:
                self._writer.close()
            except WRITE_ERRORS as exc:
                self._fail(exc)
            self._writer = None
        records, events = self.records, self.events
        summary = summarize(records, events)
        if not save:
            return None, summary, None
        if not records:
            return None, summary, "séance sans relevé : aucun FIT produit"
        try:
            out = default_fit_path(records[0]["ts"], self.route_id)
            if self.fit_dir is not None:
                out = self.fit_dir / out.name
            write_fit(records, events, out)
            return out, summary, None
        except Exception as exc:   # le FIT ne doit jamais faire tomber le core
            log.error("Export FIT impossible : %s", exc)
            return None, summary, str(exc)
