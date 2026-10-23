"""Cache brut des données téléchargées (SRS §7, deux étages de cache ; lot B2 §3.2).

- Dossier racine : `~/.cache/openride/dem/`, ou la variable d'environnement
  `OPENRIDE_DEM_CACHE` (tests).
- Téléchargement : fichier temporaire voisin puis renommage, délai d'attente de 60 s,
  3 reprises à délai croissant, un message par fichier.
- Un fichier présent n'est jamais retéléchargé ; `offline` interdit tout accès réseau.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from .errors import CompileError

CACHE_ENV = "OPENRIDE_DEM_CACHE"
TIMEOUT_S = 60.0
RETRIES = 3
RETRY_DELAYS_S = (2.0, 4.0, 8.0)

Log = Callable[[str], None]


def stderr_log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def dem_cache_dir() -> Path:
    env = os.environ.get(CACHE_ENV)
    return Path(env) if env else Path.home() / ".cache" / "openride" / "dem"


class NotFoundError(CompileError):
    """Le serveur répond 404 : le fichier n'existe pas."""


class Downloader:
    """Téléchargements HTTP vers le cache, avec reprises. `sleep` est remplaçable pour les tests."""

    def __init__(self, offline: bool = False, log: Log = stderr_log,
                 sleep: Callable[[float], None] = time.sleep, timeout_s: float = TIMEOUT_S) -> None:
        self.offline = offline
        self.log = log
        self.sleep = sleep
        self.timeout_s = timeout_s
        self.downloads = 0
        self.bytes = 0

    def fetch(self, url: str, dest: Path, label: str | None = None) -> Path:
        """Renvoie `dest`, en le téléchargeant s'il manque. Lève CompileError ou NotFoundError."""
        dest = Path(dest)
        if dest.is_file():
            return dest
        label = label or dest.name
        if self.offline:
            raise CompileError(f"{label} absent du cache ({dest}) et réseau interdit (--offline)")
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(f".{dest.name}.tmp-{os.getpid()}")
        last_error: Exception | None = None
        for attempt in range(RETRIES + 1):
            if attempt:
                delay = RETRY_DELAYS_S[min(attempt - 1, len(RETRY_DELAYS_S) - 1)]
                self.log(f"  nouvelle tentative dans {delay:.0f} s ({attempt}/{RETRIES}) : {last_error}")
                self.sleep(delay)
            t0 = time.monotonic()
            try:
                self.log(f"téléchargement de {label}…")
                with urllib.request.urlopen(url, timeout=self.timeout_s) as resp, open(tmp, "wb") as out:
                    shutil.copyfileobj(resp, out, length=1 << 20)
                size = tmp.stat().st_size
                os.replace(tmp, dest)
                self.downloads += 1
                self.bytes += size
                self.log(f"  {label} : {size / 1e6:.1f} Mo en {time.monotonic() - t0:.1f} s")
                return dest
            except urllib.error.HTTPError as exc:
                tmp.unlink(missing_ok=True)
                if exc.code == 404:
                    raise NotFoundError(f"{label} introuvable sur le serveur (404) : {url}") from exc
                last_error = exc
            except (urllib.error.URLError, OSError, TimeoutError) as exc:
                tmp.unlink(missing_ok=True)
                last_error = exc
        raise CompileError(f"échec du téléchargement de {label} après {RETRIES} reprises : {last_error}")
