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
constat, 2 si l'appel est invalide. Les constats ne citent jamais la valeur trouvée (rang dans la liste, « valeur masquée »).

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

# Adresses Bluetooth fictives admises (tests, docs), comparées une fois écrites avec « : » en
# majuscules : familles de test à au moins trois octets fixes, ou adresses entières (RC18, O2-11).
# « AA » et « C1 » ne sont pas des préfixes de fabricant (bit « administré localement »).
TEST_MAC = re.compile(
    r"^(C1:1C:00:00:00:..|AA:00:00:00:00:..|BB:00:00:00:00:..|AA:BB:CC:..:..:..|C0:FF:EE:00:..:.."
    r"|5A:1A:00:00:00:..|D1:22:33:44:55:66|11:22:33:44:55:66|12:34:56:78:9A:BC|11:11:11:11:11:11"
    r"|00:00:00:00:00:00|FF:FF:FF:FF:FF:FF)$")
# Séparateur « : », « - » ou « _ » (forme des journaux BlueZ : dev_E4_5F_…), le même partout.
MAC = re.compile(r"(?<![0-9A-Fa-f])(?<![0-9A-Fa-f]{2}[:_-])"
                 r"[0-9A-Fa-f]{2}([:_-])(?:[0-9A-Fa-f]{2}\1){4}[0-9A-Fa-f]{2}"
                 r"(?![0-9A-Fa-f])(?![:_-][0-9A-Fa-f])")

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

# Coordonnées (RC18, O2-08) : paires « 48.12345, 7.12345 » dans les deux ordres (GeoJSON met la
# longitude d'abord), y compris à cheval sur deux lignes (tableau JSON indenté) et avec la
# virgule décimale (« 48,12345 ; 7,12345 ») ; clés « lat = … » et « lon = … » appariées sur
# quelques lignes (TOML, JSON indenté, attributs GPX sur deux lignes). Une seule décimale : admis.
COORD_PAIR = re.compile(r"(?<![\d.])(?=(-?\d{1,3}\.\d{2,})[ \t]*(?:[,;/]\s*|\s+)(-?\d{1,3}\.\d{2,})(?![\d.]))")
COORD_PAIR_COMMA = re.compile(
    r"(?<![\d,])(?=(-?\d{1,3},\d{2,})[ \t]*(?:[;/]\s*|,\s+|\s+)(-?\d{1,3},\d{2,})(?![\d,]))")
COORD_LAT = re.compile(r"\blat(?:itude)?\b[\"']?\s*[:=]\s*[\"']?(-?\d{1,2}[.,]\d+)", re.I)
COORD_LON = re.compile(r"\b(?:lon|lng|long|longitude)\b[\"']?\s*[:=]\s*[\"']?(-?\d{1,3}[.,]\d+)", re.I)
KEYED_WINDOW = 3   # lignes d'écart admises entre une latitude et sa longitude

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


class DenylistError(ValueError):
    """Ligne illisible dans la liste. Le message ne cite jamais la valeur : le journal de la CI
    est public et GitHub ne masque que les lignes entières du secret (RC18, O2-12)."""


def parse_denylist(text: str) -> Denylist:
    dl = Denylist()
    for no, raw in enumerate(text.splitlines(), 1):
        line = raw.split(" #", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("regex:"):
            try:
                dl.patterns.append(re.compile(line[6:].strip(), re.I))
            except re.error:
                raise DenylistError(f"ligne {no} de la liste : expression « regex: » invalide") from None
        elif line.startswith("zone:"):
            try:
                lat, lon, radius = (float(x) for x in line[5:].split(","))
            except ValueError:
                raise DenylistError(
                    f"ligne {no} de la liste : « zone: » attend « latitude, longitude, rayon_km »") from None
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


def mask(kind: str, index: int) -> str:
    """Rang de l'entrée dans la liste, sans lettre ni longueur du mot (RC18, O2-12)."""
    return f"{kind} n° {index} de la liste"


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


def _num(text: str) -> float:
    return float(text.replace(",", "."))


def _in_zone(lat: float, lon: float, dl: Denylist) -> bool:
    if abs(lat) > 90 or abs(lon) > 180:
        return False
    return any(distance_km(lat, lon, zl, zo) <= zr for zl, zo, zr in dl.zones)


def gps_lines(text: str, dl: Denylist) -> list[int]:
    """Numéros des lignes (à partir de 1) où commence une coordonnée dans une zone privée."""
    if not dl.zones:
        return []
    starts = [0] + [m.end() for m in re.finditer(r"\n", text)]

    def line_of(pos: int) -> int:
        lo, hi = 0, len(starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if starts[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    hits: set[int] = set()
    for rx in (COORD_PAIR, COORD_PAIR_COMMA):
        for m in rx.finditer(text):
            a, b = _num(m.group(1)), _num(m.group(2))
            if _in_zone(a, b, dl) or _in_zone(b, a, dl):
                hits.add(line_of(m.start()))
    lats = [(line_of(m.start()), _num(m.group(1))) for m in COORD_LAT.finditer(text)]
    lons = [(line_of(m.start()), _num(m.group(1))) for m in COORD_LON.finditer(text)]
    for la_no, lat in lats:
        for lo_no, lon in lons:
            if abs(la_no - lo_no) <= KEYED_WINDOW and _in_zone(lat, lon, dl):
                hits.add(min(la_no, lo_no))
    return sorted(hits)


def scan_text(where: str, text: str, dl: Denylist) -> list[Finding]:
    out: list[Finding] = []
    gps = set(gps_lines(text, dl))
    for no, line in enumerate(text.splitlines(), 1):
        loc = f"{where}:{no}"
        norm = normalize(line)
        for i, w in enumerate(dl.words, 1):
            if re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", norm):
                out.append(Finding(loc, "mot interdit", mask("mot", i)))
        for i, pat in enumerate(dl.patterns, 1):
            if pat.search(line):
                out.append(Finding(loc, "motif interdit", mask("motif", i)))
        for m in MAC.finditer(line):
            if not TEST_MAC.match(re.sub(r"[_-]", ":", m.group(0)).upper()):
                out.append(Finding(loc, "adresse Bluetooth réelle ?", "valeur masquée"))
        for label, pat in SECRETS:
            if pat.search(line):
                out.append(Finding(loc, label, "valeur masquée"))
        if no in gps:
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


NULL_SHA = re.compile(r"^0{7,40}$")


def commit_range(rng: str, root: Path) -> list[str]:
    """Plage « A..B » d'un envoi ou d'une PR. Si A est nul (branche nouvelle) ou inconnu
    (envoi forcé, historique réécrit), seuls les commits de B absents des autres branches
    distantes sont pris, et à défaut la seule tête B (RC18, O2-07)."""
    base, sep, head = rng.partition("..")
    if not sep:
        return git("rev-list", rng, cwd=root).split()
    head = head or "HEAD"
    known = subprocess.run(["git", "cat-file", "-e", f"{base}^{{commit}}"], cwd=root,
                           capture_output=True).returncode == 0 if base else False
    if known:
        return git("rev-list", f"{base}..{head}", cwd=root).split()
    print(f"privacy_scan : début de plage « {base or '(vide)'} » absent ; contrôle des commits "
          f"de {head} absents des autres branches", file=sys.stderr)
    others = [r for r in git("for-each-ref", "--format=%(refname)", "refs/remotes", cwd=root).split()
              if not r.endswith("/HEAD")]
    head_sha = git("rev-parse", f"{head}^{{commit}}", cwd=root).strip()
    others = [r for r in others if git("rev-parse", r, cwd=root).strip() != head_sha]
    shas = git("rev-list", head, "--not", *others, cwd=root).split() if others else []
    return shas or [head_sha]


def scan_commits(rng: str, root: Path, dl: Denylist) -> list[Finding]:
    """Auteur, committer et message de chaque commit, fusions comprises (une fusion faite sur
    le PC porte la configuration git du PC) ; lignes ajoutées des commits ordinaires. Le
    contenu apporté par une fusion est couvert par `--all` sur la tête (RC18, O2-07)."""
    out: list[Finding] = []
    for sha in commit_range(rng, root):
        short = sha[:9]
        parents = git("rev-list", "--parents", "-n", "1", sha, cwd=root).split()[1:]
        meta = git("show", "-s", "--format=%an%x00%ae%x00%cn%x00%ce%x00%B", sha, cwd=root)
        an, ae, cn, ce, msg = (meta.split("\0") + [""] * 5)[:5]
        for role, email in (("auteur", ae), ("committer", ce)):
            if not ALLOWED_EMAIL.match(email.strip()):
                out.append(Finding(f"commit {short}", f"adresse e-mail de l'{role}", "pas une adresse noreply"))
        out += scan_text(f"commit {short} (auteur et committer)", f"{an}\n{cn}", dl)
        out += scan_text(f"commit {short} (message)", msg, dl)
        if len(parents) > 1:
            continue
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
    try:
        dl = load_denylist(args.denylist)
    except DenylistError as exc:
        print(f"privacy_scan : {exc}", file=sys.stderr)
        return 2
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
