"""Enregistrement d'une séance : journal sur disque, copie en mémoire, FIT (SRS §9, contrat IPC §6).

Le journal JSONL protège la séance contre un plantage du programme. Une copie en mémoire
protège contre une panne d'écriture (disque plein, fichier fermé) :
- une erreur d'écriture ne remonte jamais vers la boucle du core : elle est signalée une fois
  par `on_failure`, l'écriture sur disque s'arrête et la mémoire continue ;
- `reopen()` ouvre un nouveau journal et y réécrit toute la séance depuis la mémoire ;
- le FIT est produit depuis la mémoire, donc même si le journal est inutilisable ;
- en séance, le FIT s'écrit dans un fil à part (`FitExporter`, revue S1-02) : la boucle à 50 Hz ne
  s'arrête plus 1 à 3 s à chaque fin de séance.
"""

from __future__ import annotations

import ctypes
import gc
import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import wait as futures_wait
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .fit_export import Summary, default_fit_path, lap_starts, summarize, write_fit
from .journal import GAME_KINDS, TIMER_EVENTS, JournalWriter, Record, record_line

log = logging.getLogger("recorder")

WRITE_ERRORS = (OSError, ValueError)


def release_heap() -> None:
    """Rend au système la mémoire libérée après l'export FIT.

    L'export d'un FIT (`fit_tool`, un objet par champ de chaque relevé) monte à environ 25 Mo pour
    12 min de séance. Python libère tout, mais l'allocateur de la glibc gardait ces pages : le core
    grossissait d'un coup à chaque fin de parcours plus longue que les précédentes (+26 Mo sur le
    village du banc d'endurance, lu comme une fuite de +23 Mo/h). `malloc_trim` les rend ; sans
    glibc, rien à faire.
    """
    gc.collect()
    try:
        ctypes.CDLL(None).malloc_trim(0)
    except (OSError, AttributeError):
        pass


class SessionRecorder:
    def __init__(self, journal_dir: Path, route_id: str | None,
                 on_failure: Callable[[Exception], None] | None = None,
                 fit_dir: Path | None = None, workout_id: str | None = None,
                 resume_path: Path | None = None, lines: list[dict] | None = None,
                 source: str | None = None, plan: dict | None = None,
                 progression: dict | None = None, profile: dict | None = None) -> None:
        """Nouvelle séance, ou suite d'une séance (`resume_path` et ses `lines`, lot N8).

        En reprise, le journal existant est continué sans nouvel en-tête et les lignes déjà
        écrites sont reprises en mémoire : le FIT final contient toute la séance.
        """
        self.journal_dir = journal_dir
        self.route_id = route_id
        self.workout_id = workout_id
        self.source = source             # origine de la séance pour la progression (lot V2)
        self.plan = plan   # séance d'un plan d'entraînement actif (lot O11), en-tête du journal
        self.progression = progression   # `loadout` et `ftp_w` de l'en-tête (série V, lot V11)
        self.profile = profile           # `profile_id` et `profile_type` de l'en-tête (série MJ, lot MJ2)
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
        path, n = self.journal_dir / f"{stamp}{suffix}.jsonl", 1
        while path.exists():   # deux séances dans la même seconde : jamais dans le même journal
            n += 1
            path = self.journal_dir / f"{stamp}{suffix}_{n}.jsonl"
        return path

    def _open(self, path: Path, header: bool = True) -> bool:
        try:
            self._writer = JournalWriter(path, route_id=self.route_id, workout_id=self.workout_id,
                                         header=header, source=self.source, plan=self.plan,
                                         progression=self.progression, profile=self.profile)
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
                self._writer.event(line["event"], line["ts"], line.get("reason"),
                                   {k: v for k, v in line.items() if k not in ("kind", "event", "ts", "reason")})
            elif line["kind"] == "device":
                self._writer.device(line["device"], line["state"], line["ts"])
            elif line["kind"] == "ftp_test":
                self._writer.ftp_test(line)
            elif line["kind"] == "junction":
                self._writer.junction(line)
            elif line["kind"] == "ftms":
                self._writer.ftms(line)
            elif line["kind"] == "bots":
                self._writer.bots(line)
            elif line["kind"] in GAME_KINDS:
                self._writer.game(line)
            else:
                fields = {k: v for k, v in line.items() if k != "kind"}
                self._writer.record(Record(**fields))
        except WRITE_ERRORS as exc:
            self._fail(exc)

    # --- API -----------------------------------------------------------------------------

    def event(self, name: str, ts: float, reason: str | None = None) -> None:
        line = {"kind": "event", "event": name, "ts": ts}
        if reason:
            line["reason"] = reason   # raison de la pause, lue par le chronométrage des segments
        self.lines.append(line)
        self._write(line)

    def u_turn(self, ts: float, s: float, distance: float, direction: int) -> None:
        """Demi-tour depuis la pause (lot N17) : position `s` sur le parcours, distance parcourue et nouveau sens ;
        hors du chronomètre (`events`), donc absent du FIT, qui garde une distance croissante."""
        line = {"kind": "event", "event": "u_turn", "ts": ts, "s": round(s, 2), "distance": round(distance, 2),
                "dir": direction}
        self.lines.append(line)
        self._write(line)

    def device(self, device: str, state: str, ts: float) -> None:
        """Coupure ou retour d'un appareil (lot M4) ; absent du FIT (`records`, `events`)."""
        line = {"kind": "device", "ts": ts, "device": device, "state": state}
        self.lines.append(line)
        self._write(line)

    def ftp_test(self, line: dict) -> None:
        """Résultat d'un test de FTP (lot O10), écrit avant `finish`."""
        self.lines.append(line)
        self._write(line)

    def ftms(self, line: dict) -> None:
        """Statut ou perte de frein du trainer (ligne `ftms`) ; absente du FIT."""
        line = {**line, "kind": "ftms"}
        self.lines.append(line)
        self._write(line)

    def junction(self, line: dict) -> None:
        """Branche prise à un carrefour du monde ouvert (lot W9) ; absente du FIT."""
        line = {**line, "kind": "junction"}
        self.lines.append(line)
        self._write(line)

    def bots(self, line: dict) -> None:
        """Bots de la séance au départ et à chaque changement de la pause (lot N18) ; absente du FIT."""
        line = {**line, "kind": "bots"}
        self.lines.append(line)
        self._write(line)

    def game(self, line: dict) -> None:
        """Ligne de jeu de la série T (`powerup`, `segment`, `jersey`, lot T7) ; absente du FIT."""
        self.lines.append(line)
        self._write(line)

    def record(self, rec: Record) -> None:
        line = record_line(rec)
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
    def devices(self) -> list[dict]:
        return [ln for ln in self.lines if ln["kind"] == "device"]

    @property
    def events(self) -> list[dict]:
        return [ln for ln in self.lines if ln["kind"] == "event" and ln["event"] in TIMER_EVENTS]

    def finish(self, save: bool, ts: float | None = None,
               private_start_m: float = 0.0) -> tuple[Path | None, Summary, str | None]:
        """Clôt la séance et écrit le FIT tout de suite. Renvoie (chemin du FIT ou None, résumé, erreur
        éventuelle du FIT). `private_start_m` : zone privée au départ du FIT (lot PZ1), 0 si coupée.
        Hors de la boucle seulement (outils, tests, dernier recours) : la boucle passe par `close_session` et
        `FitExporter` (revue S1-02)."""
        job, summary, error = self.close_session(save, ts=ts, private_start_m=private_start_m)
        if job is None:
            return None, summary, error
        path, error = job.run()
        return path, summary, error

    def close_session(self, save: bool, ts: float | None = None,
              private_start_m: float = 0.0) -> tuple[FitJob | None, Summary, str | None]:
        """Clôt la séance sans écrire le FIT : événement `stop`, journal fermé, résumé (quelques
        millisecondes). Renvoie (export à faire ou None, résumé, raison de l'absence de FIT ou None).
        Le chemin du FIT est fixé ici, avec le profil en cours (revue S1-02)."""
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
        except Exception as exc:   # profil illisible : le FIT manque, le core reste debout
            log.error("Export FIT impossible : %s", exc)
            return None, summary, str(exc)
        if self.fit_dir is not None:
            out = self.fit_dir / out.name
        return FitJob(records, events, out, lap_starts(self.lines), private_start_m), summary, None


@dataclass
class FitJob:
    """Export FIT d'une séance close : données figées, sans lien avec l'enregistreur (revue S1-02).
    `run` peut tourner dans un autre fil que la boucle."""
    records: list[dict]
    events: list[dict]
    path: Path
    laps: list[float] = field(default_factory=list)
    private_start_m: float = 0.0

    def run(self) -> tuple[Path | None, str | None]:
        """Écrit le FIT (écriture atomique de `write_fit`). Renvoie (chemin ou None, erreur ou None) ;
        ne lève jamais : le FIT ne doit pas faire tomber le core.

        Ramasse-miettes automatique coupé le temps de l'export : `fit_tool` crée des centaines de milliers
        d'objets, qui déclenchaient des collectes complètes de 100 à 200 ms, verrou de Python tenu, donc
        boucle arrêtée d'autant (mesuré pour une heure : pas le plus long 0,23 s avec, 0,04 s sans ; export
        deux fois plus court). Ces objets n'ont pas de cycles ; `release_heap` fait une collecte à la fin."""
        was_enabled = gc.isenabled()
        gc.disable()
        try:
            write_fit(self.records, self.events, self.path, self.laps, self.private_start_m)
            return self.path, None
        except Exception as exc:
            log.error("Export FIT impossible : %s", exc)
            return None, str(exc)
        finally:
            if was_enabled:
                gc.enable()
            release_heap()


class FitExporter:
    """Exports FIT hors de la boucle à 50 Hz (revue S1-02) : un fil à part, un export à la fois dans
    l'ordre des séances. La boucle appelle `poll` à chaque pas : les fins d'export (`on_done`) y sont
    traitées, dans le fil de la boucle, jamais dans celui de l'export. `wait` attend les exports en
    cours avant l'arrêt du core.

    Le fil garde le verrou de Python par tranches de `sys.getswitchinterval()` (5 ms) : la boucle
    prend du retard de quelques millisecondes au plus pendant l'export, au lieu de s'arrêter 1 à 3 s.
    """

    def __init__(self) -> None:
        self._pool: ThreadPoolExecutor | None = None
        self._pending: list[tuple[Future, Callable[[Path | None, str | None], None] | None]] = []

    @property
    def busy(self) -> bool:
        return bool(self._pending)

    def submit(self, job: FitJob, on_done: Callable[[Path | None, str | None], None] | None = None) -> None:
        if self._pool is None:
            self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fit-export")
        t0 = time.monotonic()

        def work() -> tuple[Path | None, str | None]:
            out = job.run()
            if out[0] is not None:
                log.info("FIT écrit en %.1f s hors de la boucle : %s", time.monotonic() - t0, out[0])
            return out

        self._pending.append((self._pool.submit(work), on_done))

    def poll(self) -> None:
        """Fins d'export arrivées depuis le dernier appel, traitées dans le fil appelant."""
        if not self._pending or not any(f.done() for f, _ in self._pending):
            return
        still: list[tuple[Future, Callable[[Path | None, str | None], None] | None]] = []
        for fut, on_done in self._pending:
            if not fut.done():
                still.append((fut, on_done))
                continue
            try:
                path, error = fut.result()
            except Exception as exc:   # `FitJob.run` ne lève pas ; garde-fou
                path, error = None, str(exc)
            if on_done is not None:
                try:
                    on_done(path, error)
                except Exception:
                    log.exception("Fin d'export FIT mal traitée")
        self._pending = still

    def wait(self, timeout: float | None = None, process: bool = True) -> bool:
        """Attend les exports en cours (au plus `timeout` secondes), puis traite leurs fins (`process` faux :
        appel depuis un autre fil que la boucle, qui appellera `poll` elle-même). Vrai si tout est écrit."""
        if self._pending:
            log.info("Export FIT en cours : attente avant l'arrêt.")
            futures_wait([f for f, _ in self._pending], timeout=timeout)
        if not process:
            return all(f.done() for f, _ in self._pending)
        self.poll()
        if self._pending:
            log.error("Export FIT inachevé après %.0f s : le journal de la séance reste (openride-core recover).",
                      timeout or 0.0)
            return False
        return True

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=False)
            self._pool = None
