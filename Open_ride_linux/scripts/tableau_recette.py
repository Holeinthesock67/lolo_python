#!/usr/bin/env python3
"""Tableau de la recette 1.0 (lot X30) : les 25 lignes d'O8 face au dernier rapport de l'outil qui les mesure.

    python3 scripts/tableau_recette.py [--json] [--out DOSSIER] [--home DOSSIER]

Lit la liste du cahier O8 (`docs/lots/LOT_O8_recette_1_0.md`, §4 : numéro, critère, ligne bloquante en
gras, groupe). La table `OUTILS` associe une ligne à l'outil qui la mesure et au dossier où il écrit ses
rapports (`~/OpenRide/<outil>/<date>_<heure>/`) ; pour chaque ligne, le dernier rapport de cet outil
donne le résultat :
- `guide.jsonl` : la ligne `verdict` (écrite par le guide des essais, lot X8) ;
- sinon `resume.json` (`ok`, ou l'étape nommée pour la recette du PC), `rapport.json` (`ok`),
  `resultats.json` (aucun échec) ou `resume_<mode>.txt` (recette d'installation).
Une ligne sans outil, ou dont l'outil n'écrit rien (contrôle d'un FIT, pente face à Garmin), est « à la
main » ; un outil sans rapport donne « à faire ».

Écrit `~/OpenRide/recette_1_0/tableau.html` : ligne, critère, dernier résultat (OK, ÉCHEC, à faire,
à la main), date, lien vers le rapport, case « vu par le propriétaire », note et PR de correction
(gardées dans la page, `localStorage`, et exportables en JSON). `--json` : le tableau sur la sortie
standard, pour les sessions qui corrigent. Rien n'est écrit dans le dépôt.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
O8 = ROOT / "docs" / "lots" / "LOT_O8_recette_1_0.md"
N_LINES = 25
STAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")
REPORT_FILES = ("rapport.html", "index.html", "resume.txt", "rapport.txt", "steps.txt")


@dataclass(frozen=True)
class Outil:
    nom: str                  # commande à lancer, telle qu'au protocole
    dossier: str | None       # sous-dossier de ~/OpenRide/ ; None : l'outil n'écrit rien
    etape: str | None = None  # étape de `resume.json` à lire (recette du PC)
    contient: str | None = None   # sous-dossier exigé dans le rapport (scénario du banc simulé)


# Ligne d'O8 → outil. Les lignes absentes sont « à la main ».
OUTILS: dict[int, Outil] = {
    1: Outil("python3 scripts/recette_install.py --mode docker", "recettes_install"),
    2: Outil("python3 scripts/recette_install.py --mode home", "recettes_install"),
    5: Outil("python -m openride_core.tools.boutons_click (gestes du plan commun)", "boutons_click"),
    6: Outil("python -m openride_core.tools.click_recette", "click_recette"),
    7: Outil("python -m openride_core.tools.fc_recette", "fc_recette"),
    10: Outil("python -m openride_core.tools.log_report --latence JOURNAL_CORE JOURNAL_ENGINE (n'écrit rien)", None),
    17: Outil("engine/tests/sim_bench.py --native --probe", "sim_bench"),
    18: Outil("engine/tests/sim_bench.py --native --scenario endurance", "sim_bench", contient="endurance"),
    19: Outil("python3 scripts/recette_pc.py (étape engine)", "recettes", etape="engine"),
    20: Outil("python3 engine/tests/menu_bench.py --out ~/OpenRide/menu_bench/<date>", "menu_bench"),
    21: Outil("openride-core fit-check FICHIER.fit (n'écrit rien)", None),
    22: Outil("openride-compiler compare-garmin PARCOURS.world (n'écrit rien)", None),
}


@dataclass
class Ligne:
    numero: int
    critere: str
    bloquante: bool
    groupe: str
    outil: str
    resultat: str             # OK, ÉCHEC, à faire, à la main
    date: str
    rapport: str              # chemin du rapport, vide sans rapport
    detail: str


def read_o8(path: Path = O8) -> list[dict]:
    """Lignes du §4 d'O8 : {"numero", "critere", "bloquante", "groupe"}."""
    text = path.read_text(encoding="utf-8")
    section = text.split("## 4.", 1)[1].split("\n## ", 1)[0]
    lines, groupe = [], ""
    for raw in section.splitlines():
        g = re.match(r"^\*\*([^*]+)\*\*\s*$", raw.strip())
        if g:
            groupe = g[1].strip()
            continue
        m = re.match(r"^(\d+)\. (.*)$", raw.strip())
        if not m:
            continue
        body = m[2]
        bold = body.startswith("**")
        critere = re.split(r"\s+Outils? (?:des lignes [^:]*)?:", body.replace("**", ""), maxsplit=1)[0].strip()
        lines.append({"numero": int(m[1]), "critere": critere, "bloquante": bold, "groupe": groupe})
    return lines


def _runs(folder: Path, contient: str | None) -> list[Path]:
    if not folder.is_dir():
        return []
    runs = [p for p in folder.iterdir() if p.is_dir() and STAMP_RE.match(p.name)]
    if contient:
        runs = [p for p in runs if (p / contient).is_dir()]
    return sorted(runs, key=lambda p: p.name)


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def verdict(run: Path, outil: Outil, numero: int) -> tuple[bool | None, str]:
    """(ok ou None si illisible, détail) d'un dossier de rapport."""
    if outil.etape:
        data = _json(run / "resume.json")
        if isinstance(data, dict):
            step = next((s for s in data.get("steps", []) if s.get("name") == outil.etape), None)
            if step is not None:
                return bool(step.get("ok")), f"étape {outil.etape} : {step.get('detail') or ''}".strip(" :")
    guide = run / "guide.jsonl"
    if guide.is_file():
        rows = [r for r in (_parse(line) for line in guide.read_text(encoding="utf-8", errors="replace").splitlines())
                if r and r.get("type") == "verdict"]
        if rows:
            return bool(rows[-1].get("ok")), str(rows[-1].get("texte", ""))
    for name in ("resume.json", "rapport.json"):
        data = _json(run / name)
        if isinstance(data, dict) and "ok" in data:
            return bool(data["ok"]), name
    data = _json(run / "resultats.json")
    if isinstance(data, list) and data:
        failed = sum(int(r.get("echecs", 0)) for r in data if isinstance(r, dict))
        return failed == 0, f"{len(data)} passage(s), {failed} échec(s)"
    mode = "docker" if numero == 1 else "home"
    resume = run / f"resume_{mode}.txt"
    if resume.is_file():
        text = resume.read_text(encoding="utf-8", errors="replace")
        return "installation neuve OK" in text and "ÉCHEC" not in text, resume.name
    return None, "rapport illisible"


def _parse(line: str):
    try:
        row = json.loads(line)
    except ValueError:
        return None
    return row if isinstance(row, dict) else None


def _report_file(run: Path, numero: int) -> Path:
    names = (f"resume_{'docker' if numero == 1 else 'home'}.txt",) + REPORT_FILES if numero in (1, 2) else REPORT_FILES
    return next((run / n for n in names if (run / n).is_file()), run)


def build(home: Path, o8: Path = O8) -> list[Ligne]:
    base = home / "OpenRide"
    out = []
    for item in read_o8(o8):
        n = item["numero"]
        outil = OUTILS.get(n)
        if outil is None or outil.dossier is None:
            out.append(Ligne(**item, outil=outil.nom if outil else "", resultat="à la main", date="", rapport="",
                             detail="aucun rapport écrit" if outil else "aucun outil"))
            continue
        runs = [r for r in _runs(base / outil.dossier, outil.contient)
                if n not in (1, 2) or (r / f"resume_{'docker' if n == 1 else 'home'}.txt").is_file()]
        if not runs:
            out.append(Ligne(**item, outil=outil.nom, resultat="à faire", date="", rapport="", detail="aucun rapport"))
            continue
        run = runs[-1]
        ok, detail = verdict(run, outil, n)
        when = datetime.strptime(run.name, "%Y-%m-%d_%H%M%S").strftime("%d/%m/%Y %H:%M")
        out.append(Ligne(**item, outil=outil.nom, resultat="à faire" if ok is None else "OK" if ok else "ÉCHEC",
                         date=when, rapport=str(_report_file(run, n)), detail=detail))
    return out


def render_html(lines: list[Ligne], made: datetime) -> str:
    rows = []
    for ln in lines:
        cls = {"OK": "ok", "ÉCHEC": "ko", "à faire": "todo"}.get(ln.resultat, "hand")
        link = (f'<a href="file://{html.escape(ln.rapport)}">rapport</a>' if ln.rapport else "")
        rows.append(
            f'<tr data-n="{ln.numero}"><td>{ln.numero}{" ●" if ln.bloquante else ""}</td>'
            f'<td>{html.escape(ln.critere)}<div class="tool">{html.escape(ln.outil)}</div></td>'
            f'<td class="{cls}">{html.escape(ln.resultat)}<div class="tool">{html.escape(ln.detail)}</div></td>'
            f'<td>{html.escape(ln.date)}</td><td>{link}</td>'
            f'<td><input type="checkbox" class="vu"></td><td><input class="note" placeholder="note"></td>'
            f'<td><input class="pr" placeholder="PR"></td></tr>')
    done = sum(ln.resultat == "OK" for ln in lines)
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Recette 1.0</title>
<style>body{{font:14px sans-serif;margin:16px;color:#1d211d;background:#fff}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #d9ddd9;padding:4px 6px;vertical-align:top}}th{{background:#eef1ee;text-align:left}}
.ok{{color:#1b6b2f;font-weight:bold}}.ko{{color:#b3261e;font-weight:bold}}.todo{{color:#8a5a00}}.hand{{color:#555}}
.tool{{color:#666;font-size:12px}}input.note{{width:100%}}input.pr{{width:5em}}</style></head><body>
<h1>Recette 1.0</h1><p>Tableau du {made:%d/%m/%Y %H:%M} : {done} ligne(s) OK sur {len(lines)} ; ● ligne bloquante.
Les cases, notes et PR restent dans ce navigateur. <button id="export">Exporter en JSON</button></p>
<table><tr><th>Ligne</th><th>Critère et outil</th><th>Dernier résultat</th><th>Date</th><th>Rapport</th>
<th>Vu</th><th>Note</th><th>PR</th></tr>
{"".join(rows)}
</table>
<script>
const KEY = "openride-recette-1-0";
let st = {{}};
try {{ st = JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{ st = {{}}; }}
function save() {{ try {{ localStorage.setItem(KEY, JSON.stringify(st)); }} catch (e) {{}} }}
document.querySelectorAll("tr[data-n]").forEach(tr => {{
  const n = tr.dataset.n, s = st[n] || {{}};
  const vu = tr.querySelector(".vu"), note = tr.querySelector(".note"), pr = tr.querySelector(".pr");
  vu.checked = !!s.vu; note.value = s.note || ""; pr.value = s.pr || "";
  const upd = () => {{ st[n] = {{vu: vu.checked, note: note.value, pr: pr.value}}; save(); }};
  vu.onchange = upd; note.oninput = upd; pr.oninput = upd;
}});
document.getElementById("export").onclick = () => {{
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(st, null, 2)], {{type: "application/json"}}));
  a.download = "recette_1_0_notes.json"; a.click();
}};
</script></body></html>
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Tableau de la recette 1.0 (lot X30).")
    ap.add_argument("--json", action="store_true", help="tableau en JSON sur la sortie standard")
    ap.add_argument("--home", type=Path, default=Path.home(), help="dossier personnel (défaut : ~)")
    ap.add_argument("--out", type=Path, help="dossier du tableau (défaut : ~/OpenRide/recette_1_0)")
    args = ap.parse_args(argv)
    lines = build(args.home)
    if args.json:
        print(json.dumps([asdict(ln) for ln in lines], ensure_ascii=False, indent=2))
        return 0
    out = args.out or args.home / "OpenRide" / "recette_1_0"
    out.mkdir(parents=True, exist_ok=True)
    (out / "tableau.html").write_text(render_html(lines, datetime.now()), encoding="utf-8")
    counts = {k: sum(ln.resultat == k for ln in lines) for k in ("OK", "ÉCHEC", "à faire", "à la main")}
    print(f"Recette 1.0 : {len(lines)} lignes ; " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    for ln in lines:
        if ln.resultat == "ÉCHEC":
            print(f"  ÉCHEC ligne {ln.numero} : {ln.critere[:70]} ({ln.rapport})")
    print(f"Tableau : {out / 'tableau.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
