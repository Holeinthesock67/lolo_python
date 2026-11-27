"""Fichier de diagnostic local (lot DG1, recommandation M14 de l'audit du 22 novembre).

Un seul fichier `.zip` à joindre à un signalement : versions, qualité graphique, état des capteurs,
réglages et erreurs récentes des journaux du lanceur. **Rien n'est envoyé** : le fichier est écrit
dans le dossier choisi par le cycliste (Téléchargements, Bureau ou `~/OpenRide/Diagnostics/`).

Tout le texte passe par `Masker` avant d'être écrit : noms (utilisateur, machine, profils), adresses
Bluetooth, nom, modèle et numéro de série des appareils, poids, FTP et puissance critique, positions
GPS, réseaux Wi-Fi, adresses IP et courriels sont remplacés par des repères (`<appareil-1>`,
`<masqué>`…). Le test `test_diagnostic.py` vérifie qu'aucune valeur privée ne reste dans l'archive.

Commande IPC `create_diagnostic` (révision 1.37), réponse `diagnostic` ; en ligne de commande :
`openride-core diagnostic [--dest openride|telechargements|bureau]`.
"""

from __future__ import annotations

import dataclasses
import getpass
import json
import os
import platform
import re
import socket
import sys
import zipfile
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from . import __version__

DESTS = ("openride", "telechargements", "bureau")
DEST_LABELS = {"openride": "dossier OpenRide", "telechargements": "Téléchargements", "bureau": "Bureau"}
MASK = "<masqué>"
LOG_FILES = 2            # derniers journaux du lanceur lus
LOG_ERRORS_MAX = 200     # lignes d'avertissement et d'erreur gardées par journal
LOG_TAIL = 150           # dernières lignes gardées par journal
LINE_MAX = 400           # caractères par ligne de journal

# Sections de la configuration écrites en entier masqué : tout y est personnel (FTP, poids, âge…).
PRIVATE_SECTIONS = ("rider",)
# Clés masquées où qu'elles soient : identité des appareils, poids, puissances de référence, positions.
PRIVATE_KEY_WORDS = {"address", "name", "serial", "model", "ftp", "mass", "weight", "poids", "cp", "lat", "lon",
                     "latitude", "longitude", "ssid", "wifi", "email"}
# Identifiants de profil sans rien de personnel.
NEUTRAL_PROFILE_IDS = {"principal", "_essai", "essai"}

_SIG_UUID_TAIL = "-0000-1000-8000-00805f9b34fb"
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Courriel
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "<courriel>"),
    # Réseau Wi-Fi nommé : « SSID : MaBox », « wifi=MaBox »
    (re.compile(r"(?i)\b((?:wi-?fi\s+)?(?:ssid|wi-?fi|réseau))\b(\s*[:=]\s*|\s+)(\"[^\"]*\"|'[^']*'|\S+)"), r"\1\2" + MASK),
    # Identité d'un appareil : « serial: 123 », « modèle = X », « fabricant : Y », « numéro de série 42 »
    (re.compile(r"(?i)\b(serial(?: number)?|num[ée]ro de s[ée]rie|s[ée]rie|model(?: number)?|mod[èe]le|"
                r"manufacturer(?: name)?|fabricant|firmware|hardware revision)\b(\s*[:=]\s*|\s+)"
                r"(\"[^\"]*\"|'[^']*'|[^\s,;)]+)"), r"\1\2" + MASK),
    # Poids, FTP et puissance critique : la valeur suit le mot (« FTP 250 W », « poids=72.5 »)
    (re.compile(r"(?i)\b(ftp(?:_w)?|cp_w|poids|masse|mass(?:_kg)?|weight)\b([^\d\n]{0,12}?)\d+(?:[.,]\d+)?"),
     r"\1\2" + MASK),
    # Position : « lat=48.12345 », « lon : 7.0412 », et la forme JSON ou GDScript « "lat": 48.12 » (revue E1-07)
    (re.compile(r"(?i)\b(lat(?:itude)?|lon(?:gitude)?|lng)\b([\"']?\s*[:=]?\s*)-?\d{1,3}(?:[.,]\d+)?"),
     r"\1\2<position>"),
    # Couple de coordonnées « 48.8712, 7.1234 » (au moins trois décimales chacune)
    (re.compile(r"-?\b\d{1,3}\.\d{3,}\s*[,; ]\s*-?\d{1,3}\.\d{3,}\b"), "<position>"),
    # Adresse IPv4 (hors boucle locale)
    (re.compile(r"\b(?!127\.0\.0\.1\b)(?:\d{1,3}\.){3}\d{1,3}\b"), "<ip>"),
]
_MAC_RE = re.compile(r"(?<![0-9A-Za-z])[0-9A-Fa-f]{2}(?:[:_-][0-9A-Fa-f]{2}){5}(?![0-9A-Za-z])")
_UUID_RE = re.compile(r"\b[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\b")


class DiagnosticError(ValueError):
    """Destination inconnue ou dossier impossible à écrire."""


class Masker:
    """Remplace les valeurs privées d'un texte. Les mêmes adresses gardent le même repère
    (`<appareil-1>`, `<appareil-2>`…), pour suivre un appareil dans le journal sans le nommer."""

    def __init__(self, secrets: Iterable[str] = (), home: Path | None = None) -> None:
        words = {s.strip() for s in secrets if s and len(s.strip()) >= 3}
        # Plus long d'abord : « HomeTrainer 0000 » avant « HomeTrainer ».
        self._literals = sorted(words, key=len, reverse=True)
        self._literal_re = (re.compile("|".join(re.escape(w) for w in self._literals), re.IGNORECASE)
                            if self._literals else None)
        self._home = str(home) if home else None
        self._devices: dict[str, str] = {}
        self.count = 0

    def _device(self, raw: str) -> str:
        key = re.sub(r"[^0-9a-f]", "", raw.lower())
        if key not in self._devices:
            self._devices[key] = f"<appareil-{len(self._devices) + 1}>"
        return self._devices[key]

    def _sub(self, pattern: re.Pattern[str], repl: Any, text: str) -> str:
        out, n = pattern.subn(repl, text)
        self.count += n
        return out

    def mask(self, text: str) -> str:
        if self._home and self._home not in ("/", ""):
            text = self._sub(re.compile(re.escape(self._home)), "~", text)
        text = self._sub(re.compile(r"/home/[^/\s]+"), "/home/<utilisateur>", text)
        if self._literal_re is not None:
            text = self._sub(self._literal_re, MASK, text)
        text = self._sub(_MAC_RE, lambda m: self._device(m.group(0)), text)
        text = self._sub(_UUID_RE, lambda m: m.group(0) if m.group(0).lower().endswith(_SIG_UUID_TAIL)
                         else self._device(m.group(0)), text)
        for pattern, repl in _PATTERNS:
            text = self._sub(pattern, repl, text)
        return text


def _user_names() -> list[str]:
    """Identifiant et nom complet du compte (champ GECOS), nom de la machine."""
    names: list[str] = []
    try:
        names.append(getpass.getuser())
    except (KeyError, OSError):
        pass
    try:
        import pwd

        gecos = pwd.getpwuid(os.getuid()).pw_gecos.split(",")[0]
        names.append(gecos)
        names.extend(gecos.split())
    except (ImportError, KeyError, OSError):
        pass
    try:
        host = socket.gethostname()
        names.extend([host, host.split(".")[0]])
    except OSError:
        pass
    return names


def collect_secrets(cfg: Any, profile_entries: Iterable[tuple[str, str]] = (),
                    devices: dict[str, Any] | None = None) -> list[str]:
    """Valeurs à masquer mot pour mot : compte, machine, noms et adresses des appareils de la
    configuration et de l'objet `devices`, noms et identifiants des profils."""
    secrets = _user_names()
    for section in ("drivers", "trainer"):
        obj = getattr(cfg, section, None)
        if obj is None or not dataclasses.is_dataclass(obj):
            continue
        for f in dataclasses.fields(obj):
            if re.search(r"(address|name)", f.name):
                value = getattr(obj, f.name, "")
                if isinstance(value, str):
                    secrets.append(value)
    for dev in _iter_devices(devices):
        for key in ("name", "address"):
            if isinstance(dev.get(key), str):
                secrets.append(dev[key])
    for pid, name in profile_entries:
        if pid not in NEUTRAL_PROFILE_IDS:
            secrets.append(pid)
        if name and name.lower() not in NEUTRAL_PROFILE_IDS:
            secrets.append(name)
            secrets.extend(name.split())
    return [s for s in secrets if isinstance(s, str) and s.strip()]


def _iter_devices(devices: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not devices:
        return []
    out: list[dict[str, Any]] = []
    for value in devices.values():
        if isinstance(value, dict):
            out.append(value)
        elif isinstance(value, list):
            out.extend(v for v in value if isinstance(v, dict))
    return out


def _private_key(key: str) -> bool:
    """Clé d'identité ou personnelle : un de ses mots (séparés par « _ ») est dans `PRIVATE_KEY_WORDS`."""
    return any(word in PRIVATE_KEY_WORDS for word in key.lower().split("_"))


def safe_config(cfg: Any) -> dict[str, Any]:
    """Configuration effective sans valeur privée : sections personnelles et clés d'identité masquées."""
    if not dataclasses.is_dataclass(cfg):
        return {}
    out: dict[str, Any] = {}
    for f in dataclasses.fields(cfg):
        section = getattr(cfg, f.name)
        if not dataclasses.is_dataclass(section):
            continue
        values = dataclasses.asdict(section)
        if f.name in PRIVATE_SECTIONS:
            out[f.name] = {k: MASK for k in values}
            continue
        out[f.name] = {k: (MASK if _private_key(k) and v not in ("", None) else v)
                       for k, v in values.items()}
    return out


def safe_devices(devices: dict[str, Any] | None) -> dict[str, Any]:
    """État des capteurs (connecté, batterie, occupé) sans nom ni adresse."""
    if not devices:
        return {}

    def clean(d: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in d.items() if k not in ("name", "address")}

    out: dict[str, Any] = {}
    for key, value in devices.items():
        if isinstance(value, dict):
            out[key] = clean(value)
        elif isinstance(value, list):
            out[key] = [clean(v) for v in value if isinstance(v, dict)]
        else:
            out[key] = value
    return out


def _os_name() -> str:
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return platform.system()


def _package_version(name: str) -> str:
    try:
        from importlib.metadata import version

        return version(name)
    except Exception:  # noqa: BLE001 : paquet absent ou métadonnées illisibles
        return "absent"


def versions(engine_version: str = "", gpu: str = "") -> dict[str, str]:
    return {
        "openride_core": __version__,
        "openride_engine": engine_version or "inconnue",
        "python": platform.python_version(),
        "systeme": _os_name(),
        "noyau": platform.release(),
        "bleak": _package_version("bleak"),
        "carte_graphique": gpu or "inconnue",
    }


def log_excerpts(logs_dir: Path, files: int = LOG_FILES) -> list[tuple[str, list[str]]]:
    """Derniers journaux du lanceur : avertissements et erreurs, puis les dernières lignes."""
    try:
        logs = sorted((p for p in logs_dir.glob("*.log") if p.is_file()), key=lambda p: p.stat().st_mtime)
    except OSError:
        return []
    out: list[tuple[str, list[str]]] = []
    for path in logs[-files:]:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        errors = [ln for ln in lines if re.search(r"WARNING|ERROR|CRITICAL|Traceback|Exception", ln)]
        body = (["--- avertissements et erreurs ---"] + errors[-LOG_ERRORS_MAX:]
                + ["", "--- dernières lignes ---"] + lines[-LOG_TAIL:])
        out.append((path.name, [ln[:LINE_MAX] for ln in body]))
    return out


def dest_dir(dest: str, home: Path) -> Path:
    """Dossier choisi : Téléchargements et Bureau suivent `~/.config/user-dirs.dirs` (noms français ou anglais)."""
    if dest not in DESTS:
        raise DiagnosticError(f"destination inconnue « {dest} » (attendu : {', '.join(DESTS)})")
    if dest == "openride":
        return home / "OpenRide" / "Diagnostics"
    key, names = (("XDG_DOWNLOAD_DIR", ("Téléchargements", "Downloads")) if dest == "telechargements"
                  else ("XDG_DESKTOP_DIR", ("Bureau", "Desktop")))
    try:
        for line in (home / ".config" / "user-dirs.dirs").read_text(encoding="utf-8").splitlines():
            if line.startswith(key + "="):
                raw = line.split("=", 1)[1].strip().strip('"').replace("$HOME", str(home))
                if raw and Path(raw).is_dir():
                    return Path(raw)
    except OSError:
        pass
    for name in names:
        if (home / name).is_dir():
            return home / name
    return home / names[0]


def build_report(cfg: Any, *, devices: dict[str, Any] | None = None, engine_version: str = "", gpu: str = "",
                 session_state: str = "", extra: dict[str, Any] | None = None, now: datetime | None = None
                 ) -> dict[str, Any]:
    """Contenu de `diagnostic.json`, avant masquage du texte."""
    render = getattr(cfg, "render", None)
    return {
        "cree_le": (now or datetime.now()).strftime("%Y-%m-%d %H:%M"),
        "versions": versions(engine_version, gpu),
        "qualite": getattr(render, "quality", "inconnue"),
        "etat_seance": session_state or "inconnu",
        "capteurs": safe_devices(devices),
        "reglages": safe_config(cfg),
        **(extra or {}),
    }


def write(cfg: Any, dest: str = "openride", *, home: Path | None = None, logs_dir: Path | None = None,
          devices: dict[str, Any] | None = None, profile_entries: Iterable[tuple[str, str]] = (),
          engine_version: str = "", gpu: str = "", session_state: str = "", extra: dict[str, Any] | None = None,
          now: datetime | None = None) -> dict[str, Any]:
    """Écrit l'archive masquée ; renvoie {path, size_kb, masked, dest}. Lève `DiagnosticError`."""
    home = home or Path.home()
    now = now or datetime.now()
    folder = dest_dir(dest, home)
    masker = Masker(collect_secrets(cfg, profile_entries, devices), home=home)
    report = build_report(cfg, devices=devices, engine_version=engine_version, gpu=gpu,
                          session_state=session_state, extra=extra, now=now)
    files: dict[str, str] = {
        "LISEZMOI.txt": _readme(now),   # texte fixe, sans valeur à masquer
        "diagnostic.json": masker.mask(json.dumps(report, ensure_ascii=False, indent=2, default=str)),
    }
    for name, lines in log_excerpts(logs_dir or home / "OpenRide" / "Logs"):
        files[f"journaux/{name}"] = masker.mask("\n".join(lines) + "\n")
    try:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"openride_diagnostic_{now.strftime('%Y-%m-%d_%H-%M-%S')}.zip"
        tmp = path.with_suffix(".zip.part")
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, text in files.items():
                zf.writestr(name, text)
        os.replace(tmp, path)
    except OSError as exc:
        raise DiagnosticError(f"écriture impossible dans {DEST_LABELS.get(dest, dest)} : {exc.strerror or exc}") from exc
    shown = str(path).replace(str(home), "~", 1)
    return {"path": shown, "size_kb": max(1, round(path.stat().st_size / 1024)), "masked": masker.count,
            "dest": dest}


def _readme(now: datetime) -> str:
    return (f"Diagnostic OpenRide du {now.strftime('%d/%m/%Y à %H:%M')}.\n\n"
            "Ce fichier n'a été envoyé nulle part : joignez-le vous-même à votre signalement.\n"
            "Contenu : versions, qualité graphique, état des capteurs, réglages et extraits des journaux.\n"
            "Masqué : noms (compte, machine, profils), adresses Bluetooth, nom, modèle et série des appareils,\n"
            "poids, FTP, positions GPS, réseaux Wi-Fi, adresses IP et courriels.\n")


def main(argv: list[str] | None = None) -> int:
    """`openride-core diagnostic [--dest …]` : même fichier que le bouton des réglages."""
    import argparse

    from . import config as config_mod
    from . import profiles

    p = argparse.ArgumentParser(prog="openride-core diagnostic", description=__doc__.splitlines()[0])
    p.add_argument("--dest", choices=DESTS, default="openride")
    args = p.parse_args(argv)
    try:
        cfg = config_mod.load()
    except Exception:  # noqa: BLE001 : configuration illisible, le diagnostic reste utile
        cfg = config_mod.Config()
    try:
        entries = [(c.id, c.name) for c in profiles.list_contexts()]
    except Exception:  # noqa: BLE001
        entries = []
    try:
        res = write(cfg, args.dest, profile_entries=entries, session_state="hors séance")
    except DiagnosticError as exc:
        print(f"Diagnostic : {exc}", file=sys.stderr)
        return 1
    print(f"Diagnostic écrit : {res['path']} ({res['size_kb']} ko, {res['masked']} valeurs masquées). "
          "Rien n'a été envoyé.")
    return 0
