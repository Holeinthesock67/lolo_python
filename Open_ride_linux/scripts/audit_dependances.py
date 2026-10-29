#!/usr/bin/env python3
"""Audit des dépendances (lot X24) : vulnérabilités connues, actions GitHub en retard, paquets anciens.

    python3 scripts/audit_dependances.py [--out DOSSIER] [--hors-ligne] [--json]

- **Vulnérabilités** : `pip-audit -r constraints.txt` (extra `dev` du core) ; pour chaque paquet touché,
  l'identifiant de l'avis et la version corrigée.
- **Actions GitHub** : chaque `uses: propriétaire/action@vN` des workflows comparé à la dernière version
  majeure publiée (étiquettes lues par `git ls-remote --tags`, sans jeton) ; sauté avec `--hors-ligne`.
- **Paquets anciens** : version de `constraints.txt` publiée sur PyPI il y a plus de 12 mois.

Sortie : `resume.txt` et `resume.json` dans `~/OpenRide/deps/<date>_<heure>/` (`--out` pour un autre
dossier). Code 0, 1 si une vulnérabilité est trouvée, 2 si `pip-audit` manque, 75 sans réseau (étape
« deps » de `recette_pc.py` sautée). Rien n'est mis à jour : les versions se changent à la main.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]          # Open_ride_linux/
REPO = PROJECT.parent
CONSTRAINTS = PROJECT / "constraints.txt"
WORKFLOWS = REPO / ".github" / "workflows"
DEFAULT_OUT = Path.home() / "OpenRide" / "deps"
OLD_DAYS = 365
EXIT_NO_NETWORK = 75
USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([\w.-]+/[\w.-]+)@v(\d+)\b", re.M)
TAG_RE = re.compile(r"refs/tags/v(\d+)(?:\.\d+)*$")


@dataclass
class Rapport:
    vulnerabilites: list[dict] = field(default_factory=list)   # {"paquet", "version", "id", "corrige"}
    actions: list[dict] = field(default_factory=list)          # {"action", "utilise", "derniere", "fichiers", "en_retard"}
    anciens: list[dict] = field(default_factory=list)          # {"paquet", "version", "publie", "jours"}
    sautes: list[str] = field(default_factory=list)


def read_constraints(path: Path = CONSTRAINTS) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*([A-Za-z0-9_.-]+)==([^\s#;]+)", line)
        if m:
            out[m[1]] = m[2]
    return out


def read_workflows(folder: Path = WORKFLOWS) -> dict[str, dict]:
    """{"actions/checkout": {"majeures": {5}, "fichiers": ["openride.yml"]}}."""
    found: dict[str, dict] = {}
    for wf in sorted(folder.glob("*.y*ml")):
        for m in USES_RE.finditer(wf.read_text(encoding="utf-8")):
            entry = found.setdefault(m[1], {"majeures": set(), "fichiers": []})
            entry["majeures"].add(int(m[2]))
            if wf.name not in entry["fichiers"]:
                entry["fichiers"].append(wf.name)
    return found


def latest_major(ls_remote: str) -> int | None:
    """Plus grande version majeure des étiquettes `vN…` d'une sortie de `git ls-remote --tags`."""
    majors = [int(m[1]) for line in ls_remote.splitlines() if (m := TAG_RE.search(line.split("\t")[-1]))]
    return max(majors) if majors else None


def compare_actions(used: dict[str, dict], latest: dict[str, int | None]) -> list[dict]:
    rows = []
    for name, entry in sorted(used.items()):
        last = latest.get(name)
        oldest = min(entry["majeures"])
        rows.append({"action": name, "utilise": f"v{oldest}", "derniere": f"v{last}" if last else "?",
                     "fichiers": entry["fichiers"], "en_retard": last is not None and oldest < last})
    return rows


def parse_pip_audit(text: str) -> list[dict]:
    """Avis de la sortie JSON de `pip-audit --format json`."""
    data = json.loads(text)
    deps = data.get("dependencies", []) if isinstance(data, dict) else data
    out = []
    for dep in deps:
        for v in dep.get("vulns", []):
            out.append({"paquet": dep["name"], "version": dep.get("version", "?"), "id": v.get("id", "?"),
                        "corrige": ", ".join(v.get("fix_versions") or []) or "aucune"})
    return out


def old_packages(published: dict[str, tuple[str, datetime]], now: datetime, days: int = OLD_DAYS) -> list[dict]:
    """Paquets dont la version fixée a été publiée il y a plus de `days` jours."""
    rows = []
    for name, (version, when) in sorted(published.items()):
        age = (now - when).days
        if age > days:
            rows.append({"paquet": name, "version": version, "publie": when.date().isoformat(), "jours": age})
    return rows


# --- accès au réseau ---------------------------------------------------------------------------------

def network_ok() -> bool:
    try:
        urllib.request.urlopen("https://pypi.org/simple/pip/", timeout=10).close()
        return True
    except (urllib.error.URLError, OSError):
        return False


def run_pip_audit(constraints: Path) -> tuple[int, str, str]:
    p = subprocess.run([sys.executable, "-m", "pip_audit", "-r", str(constraints), "--format", "json",
                        "--progress-spinner", "off"], capture_output=True, text=True, check=False)
    return p.returncode, p.stdout, p.stderr


def fetch_latest(action: str) -> int | None:
    try:
        p = subprocess.run(["git", "ls-remote", "--tags", f"https://github.com/{action}"], capture_output=True,
                           text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return latest_major(p.stdout) if p.returncode == 0 else None


def fetch_published(name: str, version: str) -> datetime | None:
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=20) as r:
            data = json.load(r)
    except (urllib.error.URLError, OSError, ValueError):
        return None
    times = [u.get("upload_time_iso_8601") for u in data.get("urls", []) if u.get("upload_time_iso_8601")]
    return min(datetime.fromisoformat(t.replace("Z", "+00:00")) for t in times) if times else None


# --- rapport ------------------------------------------------------------------------------------------

def format_report(rep: Rapport, when: datetime) -> str:
    lines = [f"Audit des dépendances du {when:%d/%m/%Y %H:%M}", ""]
    lines.append(f"Vulnérabilités connues : {len(rep.vulnerabilites)}")
    lines += [f"  {v['paquet']} {v['version']} : {v['id']}, corrigé en {v['corrige']}" for v in rep.vulnerabilites]
    late = [a for a in rep.actions if a["en_retard"]]
    if "actions" not in rep.sautes:
        lines.append(f"Actions GitHub : {len(rep.actions)}, {len(late)} en retard")
        lines += [f"  {a['action']} : {a['utilise']} utilisée, {a['derniere']} publiée ({', '.join(a['fichiers'])})"
                  for a in late]
    if "anciens" not in rep.sautes:
        lines.append(f"Paquets publiés il y a plus de {OLD_DAYS} jours : {len(rep.anciens)}")
        lines += [f"  {o['paquet']} {o['version']} : publié le {o['publie']} ({o['jours']} jours)" for o in rep.anciens]
    if rep.sautes:
        lines.append("Sautés : " + ", ".join(rep.sautes))
    lines += ["", "Verdict : " + ("vulnérabilité à corriger" if rep.vulnerabilites else "aucune vulnérabilité connue")]
    return "\n".join(lines)


def audit(offline: bool, constraints: Path = CONSTRAINTS, workflows: Path = WORKFLOWS) -> tuple[int, Rapport]:
    rep = Rapport()
    rc, out, err = run_pip_audit(constraints)
    if "No module named pip_audit" in err:
        print("audit_dependances : pip-audit absent ; installer l'extra dev du core (pip install -e 'core[dev]')")
        return 2, rep
    if rc not in (0, 1) or not out.strip():
        print(f"audit_dependances : pip-audit a échoué (code {rc}) : {err.strip()[-300:]}")
        return 2, rep
    rep.vulnerabilites = parse_pip_audit(out)
    if offline:
        rep.sautes += ["actions", "anciens"]
    else:
        used = read_workflows(workflows)
        rep.actions = compare_actions(used, {name: fetch_latest(name) for name in used})
        published = {}
        for name, version in read_constraints(constraints).items():
            when = fetch_published(name, version)
            if when is not None:
                published[name] = (version, when)
        rep.anciens = old_packages(published, datetime.now(timezone.utc))
    return (1 if rep.vulnerabilites else 0), rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Audit des dépendances (lot X24).")
    ap.add_argument("--out", type=Path, help=f"dossier du résumé (défaut : {DEFAULT_OUT}/<date>)")
    ap.add_argument("--hors-ligne", action="store_true", help="saute les actions GitHub et l'âge des paquets")
    ap.add_argument("--json", action="store_true", help="résumé JSON sur la sortie standard")
    args = ap.parse_args(argv)
    if not network_ok():
        print("audit_dependances : pas de réseau vers PyPI, audit sauté")
        return EXIT_NO_NETWORK
    now = datetime.now()
    rc, rep = audit(args.hors_ligne)
    if rc == 2:
        return rc
    out = args.out or DEFAULT_OUT / now.strftime("%Y-%m-%d_%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    text = format_report(rep, now)
    (out / "resume.txt").write_text(text + "\n", encoding="utf-8")
    data = {"date": now.isoformat(timespec="seconds"), "ok": rc == 0, **asdict(rep)}
    (out / "resume.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2) if args.json else text)
    print(f"Résumé : {out}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
