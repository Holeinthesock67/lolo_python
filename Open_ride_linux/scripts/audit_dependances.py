#!/usr/bin/env python3
"""Audit des dépendances (lot X24) : vulnérabilités connues, actions GitHub en retard, paquets anciens.

    python3 scripts/audit_dependances.py [--out DOSSIER] [--hors-ligne] [--json]

- **Vulnérabilités** : `pip-audit -r constraints.txt` (extra `dev` du core) ; pour chaque paquet touché,
  l'identifiant de l'avis et la version corrigée.
- **Actions GitHub** : chaque `uses: propriétaire/action@<sha> # vN.x.y` (épinglage par SHA, lot SHA1) ou
  `@vN` des workflows comparé à la dernière version majeure publiée (étiquettes lues par
  `git ls-remote --tags`, sans jeton) ; une action épinglée dont l'étiquette `vN` a avancé depuis est
  signalée « à rafraîchir » (correctif de la même majeure, non compté en retard) ; sauté avec `--hors-ligne`.
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
# `@vN` ou `@<sha de 40 caractères> # vN…` : la majeure vient de l'étiquette ou du commentaire.
USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([\w.-]+/[\w.-]+)@(?:v(\d+)\b|([0-9a-f]{40})\s+#\s*v(\d+)\b)",
                     re.M)
TAG_RE = re.compile(r"refs/tags/v(\d+)(?:\.\d+)*$")


@dataclass
class Rapport:
    vulnerabilites: list[dict] = field(default_factory=list)   # {"paquet", "version", "id", "corrige"}
    actions: list[dict] = field(default_factory=list)          # {"action", "utilise", "derniere", "fichiers", "en_retard"}
    a_rafraichir: list[dict] = field(default_factory=list)     # {"action", "majeure", "epingle", "etiquette", "fichiers"}
    anciens: list[dict] = field(default_factory=list)          # {"paquet", "version", "publie", "jours"}
    sautes: list[str] = field(default_factory=list)
    # Éléments que l'audit n'a pas pu vérifier (revue de code vague 5, O1-10) : jamais comptés comme sains.
    non_verifies: list[str] = field(default_factory=list)


def read_constraints(path: Path = CONSTRAINTS) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*([A-Za-z0-9_.-]+)==([^\s#;]+)", line)
        if m:
            out[m[1]] = m[2]
    return out


def read_workflows(folder: Path = WORKFLOWS) -> dict[str, dict]:
    """{"actions/checkout": {"majeures": {5}, "fichiers": ["openride.yml"], "shas": {"<sha>": 5}}}."""
    found: dict[str, dict] = {}
    for wf in sorted(folder.glob("*.y*ml")):
        for m in USES_RE.finditer(wf.read_text(encoding="utf-8")):
            entry = found.setdefault(m[1], {"majeures": set(), "fichiers": [], "shas": {}})
            major = int(m[2] or m[4])
            entry["majeures"].add(major)
            if m[3]:
                entry["shas"][m[3]] = major
            if wf.name not in entry["fichiers"]:
                entry["fichiers"].append(wf.name)
    return found


def latest_major(ls_remote: str) -> int | None:
    """Plus grande version majeure des étiquettes `vN…` d'une sortie de `git ls-remote --tags`."""
    majors = [int(m[1]) for line in ls_remote.splitlines() if (m := TAG_RE.search(line.split("\t")[-1]))]
    return max(majors) if majors else None


def tag_sha(ls_remote: str, major: int) -> str | None:
    """SHA du commit visé par l'étiquette `vN` (forme déréférencée `^{}` prioritaire si l'étiquette est annotée)."""
    refs = {}
    for line in ls_remote.splitlines():
        sha, _, ref = line.partition("\t")
        refs[ref] = sha
    return refs.get(f"refs/tags/v{major}^{{}}") or refs.get(f"refs/tags/v{major}")


def stale_pins(used: dict[str, dict], tags: dict[str, str | None]) -> list[dict]:
    """Épinglages dont l'étiquette `vN` désigne aujourd'hui un autre commit (correctif à reprendre)."""
    rows = []
    for name, entry in sorted(used.items()):
        text = tags.get(name)
        for sha, major in sorted(entry.get("shas", {}).items()):
            current = tag_sha(text, major) if text else None
            if current and current != sha:
                rows.append({"action": name, "majeure": f"v{major}", "epingle": sha, "etiquette": current,
                             "fichiers": entry["fichiers"]})
    return rows


def compare_actions(used: dict[str, dict], latest: dict[str, int | None]) -> list[dict]:
    rows = []
    for name, entry in sorted(used.items()):
        last = latest.get(name)
        oldest = min(entry["majeures"])
        rows.append({"action": name, "utilise": f"v{oldest}", "derniere": f"v{last}" if last else "?",
                     "fichiers": entry["fichiers"], "en_retard": last is not None and oldest < last})
    return rows


def pip_audit_skipped(text: str) -> list[str]:
    """Paquets que pip-audit n'a pas pu auditer (entrée avec `skip_reason`), avec la raison."""
    data = json.loads(text)
    deps = data.get("dependencies", []) if isinstance(data, dict) else data
    return [f"{d.get('name', '?')} (pip-audit : {d['skip_reason']})" for d in deps if d.get("skip_reason")]


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


def fetch_tags(action: str) -> str | None:
    """Sortie de `git ls-remote --tags` du dépôt de l'action, None si illisible."""
    try:
        p = subprocess.run(["git", "ls-remote", "--tags", f"https://github.com/{action}"], capture_output=True,
                           text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return p.stdout if p.returncode == 0 else None


def fetch_latest(action: str) -> int | None:
    text = fetch_tags(action)
    return latest_major(text) if text is not None else None


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
        unknown = sum(1 for a in rep.actions if a["derniere"] == "?")
        lines.append(f"Actions GitHub : {len(rep.actions)}, {len(late)} en retard"
                     + (f", {unknown} non vérifiée{'s' if unknown > 1 else ''}" if unknown else ""))
        lines += [f"  {a['action']} : {a['utilise']} utilisée, {a['derniere']} publiée ({', '.join(a['fichiers'])})"
                  for a in late]
        if rep.a_rafraichir:
            lines.append(f"Épinglages à rafraîchir (étiquette avancée) : {len(rep.a_rafraichir)}")
            lines += [f"  {r['action']} {r['majeure']} : épinglée {r['epingle'][:12]}, étiquette sur {r['etiquette'][:12]}"
                      f" ({', '.join(r['fichiers'])})" for r in rep.a_rafraichir]
    if "anciens" not in rep.sautes:
        lines.append(f"Paquets publiés il y a plus de {OLD_DAYS} jours : {len(rep.anciens)}")
        lines += [f"  {o['paquet']} {o['version']} : publié le {o['publie']} ({o['jours']} jours)" for o in rep.anciens]
    if rep.non_verifies:
        lines.append(f"Non vérifiés : {len(rep.non_verifies)}")
        lines += [f"  {n}" for n in rep.non_verifies]
    if rep.sautes:
        lines.append("Sautés : " + ", ".join(rep.sautes))
    if rep.vulnerabilites:
        verdict = "vulnérabilité à corriger"
    elif any("pip-audit" in n for n in rep.non_verifies):
        verdict = "aucune vulnérabilité connue parmi les paquets audités (certains n'ont pas pu l'être)"
    else:
        verdict = "aucune vulnérabilité connue"
    lines += ["", "Verdict : " + verdict]
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
    rep.non_verifies += pip_audit_skipped(out)
    if offline:
        rep.sautes += ["actions", "anciens"]
    else:
        used = read_workflows(workflows)
        tags = {name: fetch_tags(name) for name in used}
        rep.actions = compare_actions(used, {name: latest_major(t) if t is not None else None
                                             for name, t in tags.items()})
        rep.a_rafraichir = stale_pins(used, tags)
        rep.non_verifies += [f"action {a['action']} (dernière version illisible)" for a in rep.actions
                             if a["derniere"] == "?"]
        published = {}
        for name, version in read_constraints(constraints).items():
            when = fetch_published(name, version)
            if when is not None:
                published[name] = (version, when)
            else:
                rep.non_verifies.append(f"âge de {name} {version} (PyPI illisible)")
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
