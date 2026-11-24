"""Cache brut des données téléchargées (SRS §7, deux étages de cache ; lot B2 §3.2).

- Dossier racine : `~/.cache/openride/dem/`, ou la variable d'environnement
  `OPENRIDE_DEM_CACHE` (tests).
- Téléchargement : fichier temporaire voisin puis renommage, délai d'attente de 60 s,
  3 reprises à délai croissant, un message par fichier.
- Un fichier présent n'est jamais retéléchargé ; `offline` interdit tout accès réseau.
- Revue de code K1-01 (24 novembre) : un téléchargement plus court que la taille annoncée par le serveur
  est refusé et repris ; l'appelant peut passer `validate`, qui contrôle le contenu avant qu'il n'entre dans
  le cache (page d'erreur servie en 200), et un fichier déjà en cache qui ne passe pas ce contrôle est
  supprimé puis retéléchargé, au lieu d'être refusé à chaque lancement.
"""

from __future__ import annotations

import http.client
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
# Contrôle du contenu d'un fichier téléchargé : lève ValueError s'il n'est pas ce qu'on attend.
Validator = Callable[[Path], None]


def stderr_log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def dem_cache_dir() -> Path:
    env = os.environ.get(CACHE_ENV)
    return Path(env) if env else Path.home() / ".cache" / "openride" / "dem"


class NotFoundError(CompileError):
    """Le serveur répond 404 : le fichier n'existe pas."""


def _announced_length(resp) -> int | None:
    """Taille annoncée par l'en-tête Content-Length, ou None (en-tête absent ou illisible)."""
    headers = getattr(resp, "headers", None)
    value = headers.get("Content-Length") if headers is not None else None
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


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

    def fetch(self, url: str, dest: Path, label: str | None = None,
              validate: Validator | None = None) -> Path:
        """Renvoie `dest`, en le téléchargeant s'il manque. Lève CompileError ou NotFoundError.

        `validate` contrôle le contenu (ValueError s'il est faux) : avant l'entrée dans le cache, et pour un
        fichier déjà en cache, qui est alors supprimé puis retéléchargé.
        """
        dest = Path(dest)
        label = label or dest.name
        if dest.is_file():
            if validate is None:
                return dest
            try:
                validate(dest)
                return dest
            except ValueError as exc:
                if self.offline:
                    raise CompileError(f"{label} illisible dans le cache ({dest} : {exc}) et réseau interdit "
                                       "(--offline) : relancer sans --offline pour le retélécharger") from exc
                self.log(f"{label} illisible dans le cache ({exc}) : supprimé, nouveau téléchargement")
                dest.unlink(missing_ok=True)
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
                    announced = _announced_length(resp)
                size = tmp.stat().st_size
                if announced is not None and size != announced:
                    # connexion fermée proprement avant la fin : sans ce contrôle, gardé pour toujours
                    raise http.client.IncompleteRead(b"", max(announced - size, 0))
                if validate is not None:
                    validate(tmp)
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
            except (urllib.error.URLError, OSError, TimeoutError, http.client.HTTPException, ValueError) as exc:
                tmp.unlink(missing_ok=True)
                last_error = exc
        raise CompileError(f"échec du téléchargement de {label} après {RETRIES} reprises : {last_error}")
