#!/usr/bin/env python3
"""Scanner de confidentialité du dépôt lolo_python (lot X23).

Le dépôt est public. Ce script cherche ce qui ne doit jamais y entrer :
- mots interdits (noms, lieux, nom du trainer…) et zones GPS privées, lus dans une liste
  locale qui reste hors du dépôt : `~/OpenRide/privacy_denylist.txt` sur le PC, variable
  d'environnement `PRIVACY_DENYLIST` (secret GitHub) dans la CI ;
- adresses Bluetooth qui ne sont pas des adresses de test ;
- fichiers d'activité (FIT, GPX, TCX, KML, JSONL) et fichiers de secrets ;
- clés et jetons (GitHub, AWS, Google, Slack, Anthropic, clés privées) ;
- auteur, committer et message de chaque commit (`--commits`).

Modes : `--all` (fichiers suivis, défaut), `--staged` (crochet pre-commit), `--commits A..B`
(lignes ajoutées et métadonnées de chaque commit), `--paths F…`. Code de sortie 1 si un
constat, 2 si l'appel est invalide. Les mots trouvés sont masqués dans la sortie.

Bibliothèque standard seulement : le crochet tourne avant toute installation.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DENYLIST = Path.home() / "OpenRide" / "privacy_denylist.txt"

# Adresses Bluetooth fictives admises (tests, docs) : préfixes de test ou trois octets nuls.
TEST_MAC = re.compile(
    r"^(C1:1C|AA:|BB:|C0:FF:EE|D1:22:33|11:22:33|12:34:56|5A:1A|11:11:11|00:00:00)", re.I)
MAC = re.compile(r"(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}(?![0-9A-Fa-f:])")

FORBIDDEN_SUFFIXES = (".fit", ".fit.gz", ".gpx", ".tcx", ".kml", ".kmz", ".jsonl")
FORBIDDEN_NAMES = (".env", "run_trainer.log", "privacy_denylist.txt")
# Fichiers d'exemple admis malgré leur nom.
ALLOWED_PATHS = re.compile(r"(^|/)(\.env\.example|config\.example\.toml)$")

SECRETS = [
    ("jeton GitHub", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b")),
    ("clé AWS", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("clé Google", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("jeton Slack", re.compile(r"\bxox[abpr]-[0-9A-Za-z-]{10,}\b")),
    ("clé Anthropic", re.compile(r"\bsk-ant-[0-9A-Za-z_\-]{20,}\b")),
    ("clé privée", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
]

# Coordonnées : « 48.12345, 7.12345 », « lat = 48.123 … lon = 7.123 », attributs GPX.
COORD_PAIR = re.compile(r"(-?\d{1,2}\.\d{2,})\s*[,;/ ]\s*(-?\d{1,3}\.\d{2,})")
COORD_LAT = re.compile(r"\blat(?:itude)?\b[\"']?\s*[:=]\s*[\"']?(-?\d{1,2}\.\d+)", re.I)
COORD_LON = re.compile(r"\b(?:lon|lng|longitude)\b[\"']?\s*[:=]\s*[\"']?(-?\d{1,3}\.\d+)", re.I)

ALLOWED_EMAIL = re.compile(
    r"^(\d+\+[A-Za-z0-9-]+@users\.noreply\.github\.com|noreply@github\.com|noreply@anthropic\.com)$")


@dataclass
class Denylist:
    words: list[str] = field(default_factory=list)          # normalisés
    patterns: list[re.Pattern] = field(default_factory=list)
    zones: list[tuple[float, float, float]] = field(default_factory=list)   # lat, lon, rayon km

    @property
    def empty(self) -> bool:
        return not (self.words or self.patterns or self.zones)


def normalize(text: str) -> str:
    """Minuscules sans accents : « Élise » et « ELISE » donnent le même mot."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def parse_denylist(text: str) -> Denylist:
    dl = Denylist()
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("regex:"):
            dl.patterns.append(re.compile(line[6:].strip(), re.I))
        elif line.startswith("zone:"):
            lat, lon, radius = (float(x) for x in line[5:].split(","))
            dl.zones.append((lat, lon, radius))
        else:
            dl.words.append(normalize(line))
    return dl


def load_denylist(path: Path | None) -> Denylist:
    env = os.environ.get("PRIVACY_DENYLIST", "")
    parts = [env] if env.strip() else []
    p = path or DEFAULT_DENYLIST
    if p.is_file():
        parts.append(p.read_text(encoding="utf-8"))
    return parse_denylist("\n".join(parts))


def mask(word: str) -> str:
    return word[0] + "*" * (len(word) - 1) if word else word


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@dataclass
class Finding:
    where: str
    rule: str
    detail: str

    def __str__(self) -> str:
        return f"{self.where}: {self.rule} : {self.detail}"


def scan_text(where: str, text: str, dl: Denylist) -> list[Finding]:
    out: list[Finding] = []
    for no, line in enumerate(text.splitlines(), 1):
        loc = f"{where}:{no}"
        norm = normalize(line)
        for w in dl.words:
            if re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", norm):
                out.append(Finding(loc, "mot interdit", mask(w)))
        for pat in dl.patterns:
            if pat.search(line):
                out.append(Finding(loc, "motif interdit", mask(pat.pattern)))
        for m in MAC.finditer(line):
            if not TEST_MAC.match(m.group(0)):
                out.append(Finding(loc, "adresse Bluetooth réelle ?", m.group(0)[:8] + ":**:**:**"))
        for label, pat in SECRETS:
            if pat.search(line):
                out.append(Finding(loc, label, "valeur masquée"))
        if dl.zones:
            points = [(float(a), float(b)) for a, b in COORD_PAIR.findall(line)]
            lats, lons = COORD_LAT.findall(line), COORD_LON.findall(line)
            points += [(float(a), float(b)) for a, b in zip(lats, lons)]
            for lat, lon in points:
                if abs(lat) > 90 or abs(lon) > 180:
                    continue
                if any(distance_km(lat, lon, zl, zo) <= zr for zl, zo, zr in dl.zones):
                    out.append(Finding(loc, "coordonnée dans une zone privée", "valeur masquée"))
    return out


def scan_path_name(path: str) -> list[Finding]:
    low = path.lower()
    name = low.rsplit("/", 1)[-1]
    if ALLOWED_PATHS.search(low):
        return []
    if low.endswith(FORBIDDEN_SUFFIXES):
        return [Finding(path, "fichier d'activité", "les traces restent sur le PC")]
    if name in FORBIDDEN_NAMES or name.startswith(".env."):
        return [Finding(path, "fichier personnel ou de secrets", "à garder hors du dépôt")]
    return []


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout


def read_blob(data: bytes) -> str | None:
    if b"\0" in data[:8192]:
        return None   # binaire
    return data.decode("utf-8", errors="replace")


def scan_files(paths: list[str], root: Path, dl: Denylist, staged: bool = False) -> list[Finding]:
    out: list[Finding] = []
    for p in paths:
        out += scan_path_name(p)
        if staged:
            data = subprocess.run(["git", "show", f":{p}"], cwd=root, capture_output=True).stdout
        else:
            f = root / p
            if not f.is_file():
                continue
            data = f.read_bytes()
        text = read_blob(data)
        if text is not None:
            out += scan_text(p, text, dl)
    return out


def scan_commits(rng: str, root: Path, dl: Denylist) -> list[Finding]:
    out: list[Finding] = []
    shas = git("rev-list", "--no-merges", rng, cwd=root).split()
    for sha in shas:
        short = sha[:9]
        meta = git("show", "-s", "--format=%an%x00%ae%x00%cn%x00%ce%x00%B", sha, cwd=root)
        an, ae, cn, ce, msg = (meta.split("\0") + [""] * 5)[:5]
        for role, email in (("auteur", ae), ("committer", ce)):
            if not ALLOWED_EMAIL.match(email.strip()):
                out.append(Finding(f"commit {short}", f"adresse e-mail de l'{role}", "pas une adresse noreply"))
        out += scan_text(f"commit {short} (auteur et committer)", f"{an}\n{cn}", dl)
        out += scan_text(f"commit {short} (message)", msg, dl)
        diff = git("show", "--format=", "--unified=0", "--no-color", "--no-ext-diff", sha, cwd=root)
        current = "?"
        added: list[str] = []
        for line in diff.splitlines():
            if line.startswith("+++ "):
                if added:
                    out += scan_text(f"commit {short} {current}", "\n".join(added), dl)
                    added = []
                current = line[6:] if line.startswith("+++ b/") else line[4:]
                out += scan_path_name(current) if current != "/dev/null" else []
            elif line.startswith("+") and not line.startswith("+++"):
                added.append(line[1:])
        if added:
            out += scan_text(f"commit {short} {current}", "\n".join(added), dl)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--all", action="store_true", help="fichiers suivis par git (défaut)")
    mode.add_argument("--staged", action="store_true", help="fichiers indexés (crochet pre-commit)")
    mode.add_argument("--commits", metavar="A..B", help="commits d'une plage : métadonnées et lignes ajoutées")
    mode.add_argument("--paths", nargs="+", metavar="FICHIER", help="fichiers donnés")
    ap.add_argument("--denylist", type=Path, help=f"liste locale (défaut : {DEFAULT_DENYLIST})")
    ap.add_argument("--require-denylist", action="store_true",
                    help="échoue si aucune liste de mots n'est disponible")
    args = ap.parse_args(argv)

    try:
        root = Path(git("rev-parse", "--show-toplevel", cwd=Path.cwd()).strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("privacy_scan : à lancer dans un dépôt git", file=sys.stderr)
        return 2
    dl = load_denylist(args.denylist)
    if dl.empty:
        msg = ("privacy_scan : aucune liste de mots interdits (fichier local ou PRIVACY_DENYLIST) ; "
               "seuls les contrôles génériques tournent")
        print(msg, file=sys.stderr)
        if args.require_denylist:
            return 2

    if args.commits:
        findings = scan_commits(args.commits, root, dl)
        label = f"commits {args.commits}"
    elif args.staged:
        paths = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z", cwd=root).split("\0")
        findings = scan_files([p for p in paths if p], root, dl, staged=True)
        label = "fichiers indexés"
    elif args.paths:
        rel = [os.path.relpath(Path(p).resolve(), root) for p in args.paths]
        findings = scan_files(rel, root, dl)
        label = "fichiers donnés"
    else:
        paths = git("ls-files", "-z", cwd=root).split("\0")
        findings = scan_files([p for p in paths if p], root, dl)
        label = "fichiers suivis"

    for f in findings:
        print(f)
    if findings:
        print(f"privacy_scan : {len(findings)} constat(s) dans les {label}.", file=sys.stderr)
        return 1
    print(f"privacy_scan : rien trouvé dans les {label}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
