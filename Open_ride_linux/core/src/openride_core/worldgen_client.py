"""Client du générateur du monde ouvert (lot W9, `docs/contracts/worldgen_v1.md`).

Lance `openride-worldgen`, lui parle en lignes JSON (entrée et sortie standard) et recopie sa sortie
d'erreur dans le journal du core, que le lanceur range avec la rotation du lot M8. La lecture se fait
dans deux fils ; la boucle à 50 Hz ne fait que vider une file (`drain`).
"""

from __future__ import annotations

import json
import logging
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from .launcher import worldgen_command

log = logging.getLogger("worldgen")

CLOSE_TIMEOUT_S = 5.0     # attente de `closed` à la fin de la séance (contrat §3)


class WorldgenClient:
    def __init__(self, session_dir: Path, config_path: Path | None = None, cmd: list[str] | None = None,
                 extra_args: list[str] | None = None) -> None:
        self.session_dir = Path(session_dir)
        self.cmd = [*(cmd or worldgen_command()), "--session", str(self.session_dir),
                    *(["--config", str(config_path)] if config_path else []), *(extra_args or [])]
        self._proc: subprocess.Popen[bytes] | None = None
        self._inbox: queue.Queue[dict[str, Any]] = queue.Queue()
        self._threads: list[threading.Thread] = []
        self.bad_lines = 0           # lignes illisibles ignorées (contrat §2)
        self.closed = False          # `closed` reçu
        self.exit_code: int | None = None

    # --- processus -----------------------------------------------------------------------

    def start(self) -> None:
        log.info("Lancement du générateur : %s", " ".join(self.cmd))
        self._proc = subprocess.Popen(self.cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, bufsize=0)
        for target, stream in ((self._read_out, self._proc.stdout), (self._read_err, self._proc.stderr)):
            t = threading.Thread(target=target, args=(stream,), name="worldgen-io", daemon=True)
            t.start()
            self._threads.append(t)

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _read_out(self, stream: Any) -> None:
        for raw in iter(stream.readline, b""):
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                self.bad_lines += 1
                log.warning("Ligne illisible du générateur ignorée (%d au total) : %.80s", self.bad_lines, line)
                continue
            if isinstance(msg, dict) and isinstance(msg.get("type"), str):
                if msg["type"] == "closed":
                    self.closed = True
                self._inbox.put(msg)
            else:
                self.bad_lines += 1

    def _read_err(self, stream: Any) -> None:
        for raw in iter(stream.readline, b""):
            text = raw.decode("utf-8", "replace").rstrip()
            if text:
                log.info("générateur : %s", text)

    # --- dialogue ------------------------------------------------------------------------

    def send(self, msg: dict[str, Any]) -> bool:
        """Une ligne JSON vers le générateur ; faux si le processus est parti."""
        if not self.alive or self._proc is None or self._proc.stdin is None:
            return False
        try:
            self._proc.stdin.write((json.dumps(msg, ensure_ascii=False, separators=(",", ":")) + "\n").encode())
            self._proc.stdin.flush()
            return True
        except (BrokenPipeError, OSError, ValueError):
            return False

    def drain(self) -> list[dict[str, Any]]:
        """Messages reçus depuis le dernier appel ; ne bloque jamais."""
        out: list[dict[str, Any]] = []
        while True:
            try:
                out.append(self._inbox.get_nowait())
            except queue.Empty:
                return out

    def close(self, timeout: float = CLOSE_TIMEOUT_S) -> None:
        """Fin de séance : `close`, attente de `closed` (5 s au plus), puis arrêt du processus."""
        proc = self._proc
        if proc is None:
            return
        if self.alive:
            self.send({"type": "close"})
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline and not self.closed and self.alive:
                time.sleep(0.02)
            try:
                if proc.stdin:
                    proc.stdin.close()
            except OSError:
                pass
            try:
                proc.wait(timeout=max(0.2, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                log.warning("Le générateur ne s'arrête pas : arrêt forcé.")
                proc.kill()
                proc.wait()
        self.exit_code = proc.returncode
        for t in self._threads:
            t.join(1.0)
        self._proc = None
