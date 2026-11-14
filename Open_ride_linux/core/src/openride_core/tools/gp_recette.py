"""Recette du Grand Prix des objets (lot GP11) : bilan des journaux des courses jouées sur le vélo.

    python -m openride_core.tools.gp_recette                       # courses du jour (profil en cours)
    python -m openride_core.tools.gp_recette --dernieres 3         # les trois dernières courses
    python -m openride_core.tools.gp_recette JOURNAL.jsonl [...]   # journaux nommés
    python -m openride_core.tools.gp_recette ... --json            # même bilan en JSON

Chaque étape de la recette (`docs/RECETTE_SERIE_GP.md`) dure 10 minutes au plus ; ce bilan cumule les
courses des étapes déjà faites et dit ce qu'il reste à voir. Il lit les lignes du journal de séance :
`gp_start` (format, adversaires, objets joués), `gp` (boîte, objet utilisé, coup reçu, parade, vol),
`gp_summary` (place, esquives) et les échantillons `record` à 1 Hz (pente envoyée `grade_sent`,
supplément de vent et d'abri `wind_grade_pct`).

Contrôles :
- **couverture** (cahier GP11 §3) : chaque objet joué a été utilisé au moins une fois par le cycliste, et
  chaque objet qui peut toucher quelqu'un (effet sur la cible, éclaboussure ou vol, d'après la table des
  objets) a été subi au moins une fois ; un objet coupé dans toutes les courses est « non joué » ;
- **pente envoyée lisse** (critère 1) : autour de chaque coup subi (de `AVANT_S` s avant à `APRES_S` s
  après), la plus forte variation d'une seconde à l'autre de la pente envoyée ne dépasse pas celle du
  reste de la course (99e centile) de plus de `MARGE_PENTE_PCT` point, avec un plancher de
  `PLANCHER_PENTE_PCT` ; celle du supplément de vent et d'abri, seul canal par lequel un objet peut se
  ressentir (plan GP §7), ne dépasse pas `PAS_SUPPLEMENT_PCT` point par seconde ;
- **format** : au moins une course sur circuit et une course en ligne (cahier GP11 §3).

Le ressenti sous les pieds, la lisibilité et l'esquive au Click et au clavier restent à cocher par le
cycliste dans la recette : le journal ne note pas les changements de voie.

Code de sortie : 0 si tous les contrôles passent, 1 sinon, 2 si aucune course n'est lisible.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from ..grandprix import items as gp_items
from ..journal import read_journal

ME = "me"
AVANT_S = 1.0                # fenêtre d'un coup subi : 1 s avant …
APRES_S = 6.0                # … à 6 s après (glissade, relance, plus long effet à durée : 6 s)
MARGE_PENTE_PCT = 0.3        # pente envoyée : marge sur le 99e centile du reste de la course
PLANCHER_PENTE_PCT = 0.5     # pente envoyée : variation toujours admise (point par seconde)
PAS_SUPPLEMENT_PCT = 0.5     # supplément de vent et d'abri : « quelques dixièmes de point » (plan GP §7)


@dataclass
class Course:
    """Une course lue dans un journal."""
    path: str
    debut: dict
    fin: dict | None = None
    gp: list[dict] = field(default_factory=list)
    echantillons: list[tuple[float, float | None, float | None]] = field(default_factory=list)

    @property
    def circuit(self) -> bool:
        return self.debut.get("laps") is not None

    def format(self) -> str:
        if self.circuit:
            return f"circuit, {self.debut['laps']} tour(s)"
        return f"en ligne, {self.debut.get('length_m', 0.0) / 1000.0:.1f} km"


@dataclass
class Coup:
    """Coup subi par le cycliste et pente envoyée autour."""
    ts: float
    item: str
    pas_pente: float | None       # plus forte variation d'une seconde à l'autre dans la fenêtre
    pas_supplement: float | None
    seuil_pente: float | None
    ok: bool


@dataclass
class Ligne:
    """Couverture d'un objet sur toutes les courses lues."""
    item: str
    label: str
    joue: bool = False
    utilise: int = 0
    a_subir: bool = False
    subi: int = 0
    pare: int = 0

    @property
    def ok(self) -> bool:
        return not self.joue or (self.utilise > 0 and (not self.a_subir or self.subi > 0))


def lire(path: Path) -> list[Course]:
    """Courses du Grand Prix d'un journal (une séance n'en a qu'une, mais rien ne l'impose ici)."""
    courses: list[Course] = []
    for line in read_journal(path):
        kind = line.get("kind")
        if kind == "gp_start":
            courses.append(Course(str(path), line))
        elif not courses:
            continue
        elif kind == "gp":
            courses[-1].gp.append(line)
        elif kind == "gp_summary":
            courses[-1].fin = line
        elif kind == "record" and "ts" in line:
            courses[-1].echantillons.append((float(line["ts"]), line.get("grade_sent"), line.get("wind_grade_pct")))
    return courses


def _a_subir(spec: gp_items.ItemSpec) -> bool:
    return bool(spec.hit_fx or spec.splash_fx or spec.steal_m)


def couverture(courses: Iterable[Course], table: gp_items.ItemTable = gp_items.DEFAULT_TABLE) -> list[Ligne]:
    lignes = {i: Ligne(i, gp_items.LABELS[i], a_subir=_a_subir(table.items[i])) for i in gp_items.ITEM_IDS}
    for c in courses:
        for i in c.debut.get("items", ()):
            if i in lignes:
                lignes[i].joue = True
        dernier: dict[str, str] = {}   # dernier objet utilisé par chaque coureur (le vol vient de lui)
        for e in c.gp:
            ev, rider, item = e.get("event"), e.get("rider"), e.get("item")
            if ev == "use":
                dernier[rider] = item
                if rider == ME and item in lignes:
                    lignes[item].utilise += 1
            elif ev == "hit" and rider == ME and item in lignes:
                lignes[item].subi += 1
            elif ev == "parry" and rider == ME and item in lignes:
                lignes[item].pare += 1
            elif ev == "steal" and e.get("target") == ME and dernier.get(rider) in lignes:
                lignes[dernier[rider]].subi += 1
    return list(lignes.values())


def _pas(serie: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Variation par seconde entre deux échantillons voisins, datée par le second."""
    out = []
    for (t0, v0), (t1, v1) in zip(serie, serie[1:]):
        dt = t1 - t0
        if dt > 0:
            out.append((t1, abs(v1 - v0) / max(dt, 1.0)))
    return out


def _centile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(int(q * len(s)), len(s) - 1)]


def coups(c: Course) -> list[Coup]:
    """Coups subis par le cycliste et pente envoyée autour de chacun."""
    hits = [(float(e["ts"]), e.get("item", "?")) for e in c.gp
            if e.get("event") == "hit" and e.get("rider") == ME and "ts" in e]
    pente = _pas([(t, float(g)) for t, g, _ in c.echantillons if g is not None])
    supp = _pas([(t, float(w)) for t, _, w in c.echantillons if w is not None])

    def dans(t: float) -> bool:
        return any(h - AVANT_S <= t <= h + APRES_S for h, _ in hits)

    reste = [p for t, p in pente if not dans(t)]
    seuil = max(_centile(reste, 0.99) + MARGE_PENTE_PCT, PLANCHER_PENTE_PCT) if pente else None
    out = []
    for h, item in hits:
        fen_p = [p for t, p in pente if h - AVANT_S <= t <= h + APRES_S]
        fen_s = [p for t, p in supp if h - AVANT_S <= t <= h + APRES_S]
        pp = max(fen_p) if fen_p else None
        ps = max(fen_s) if fen_s else None
        ok = (pp is None or seuil is None or pp <= seuil) and (ps is None or ps <= PAS_SUPPLEMENT_PCT)
        out.append(Coup(h, item, None if pp is None else round(pp, 2), None if ps is None else round(ps, 2),
                        None if seuil is None else round(seuil, 2), ok))
    return out


def bilan(courses: list[Course]) -> dict[str, Any]:
    lignes = couverture(courses)
    par_course = []
    for c in courses:
        cs = coups(c)
        fin = c.fin or {}
        par_course.append({"journal": c.path, "format": c.format(), "circuit": c.circuit,
                           "adversaires": c.debut.get("opponents"), "chaos": c.debut.get("chaos"),
                           "objets_joues": len(c.debut.get("items", ())),
                           "place": fin.get("place"), "sur": fin.get("of"), "esquives": fin.get("dodged"),
                           "terminee": c.fin is not None, "coups": [asdict(k) for k in cs],
                           "pente_ok": all(k.ok for k in cs), "sans_pente": not c.echantillons})
    formats = {"circuit": any(c.circuit for c in courses), "en_ligne": any(not c.circuit for c in courses)}
    manque_util = [l.item for l in lignes if l.joue and l.utilise == 0]
    manque_subi = [l.item for l in lignes if l.joue and l.a_subir and l.subi == 0]
    non_joues = [l.item for l in lignes if not l.joue]
    ok = (bool(courses) and not manque_util and not manque_subi and all(formats.values())
          and all(p["pente_ok"] for p in par_course))
    return {"courses": par_course, "formats": formats,
            "objets": [{**asdict(l), "ok": l.ok} for l in lignes],
            "a_utiliser": manque_util, "a_subir": manque_subi, "non_joues": non_joues, "ok": ok}


def texte(b: dict[str, Any]) -> str:
    out = ["Recette du Grand Prix des objets (lot GP11)", ""]
    for p in b["courses"]:
        place = f"{p['place']}e sur {p['sur']}" if p["place"] else "non terminée"
        out.append(f"- {Path(p['journal']).name} : {p['format']}, {p['adversaires']} adversaire(s), chaos "
                   f"{p['chaos']}, {p['objets_joues']} objet(s) joué(s) ; {place}, {p['esquives'] or 0} esquive(s)")
        if p["sans_pente"]:
            out.append("    pente envoyée absente du journal : contrôle de lissage impossible")
        for k in p["coups"]:
            if not k["ok"]:
                out.append(f"    À-COUP ? {k['item']} à {datetime.fromtimestamp(k['ts']):%H:%M:%S} : pente "
                           f"{k['pas_pente']} pt/s (seuil {k['seuil_pente']}), supplément {k['pas_supplement']} "
                           f"pt/s (seuil {PAS_SUPPLEMENT_PCT})")
        n = len(p["coups"])
        if n and p["pente_ok"]:
            out.append(f"    pente envoyée lisse autour des {n} coup(s) subi(s)")
    out += ["", f"{'Objet':<24} {'joué':<5} {'utilisé':>8} {'subi':>6} {'paré':>6}  état"]
    for o in b["objets"]:
        subi = str(o["subi"]) if o["a_subir"] else "-"
        etat = "non joué" if not o["joue"] else ("OK" if o["ok"] else "à voir")
        out.append(f"{o['label']:<24} {'oui' if o['joue'] else 'non':<5} {o['utilise']:>8} {subi:>6} "
                   f"{o['pare']:>6}  {etat}")
    out.append("")
    if not b["formats"]["circuit"]:
        out.append("Reste à faire : une course sur circuit.")
    if not b["formats"]["en_ligne"]:
        out.append("Reste à faire : une course en ligne.")
    if b["a_utiliser"]:
        out.append("Reste à utiliser : " + ", ".join(gp_items.LABELS[i] for i in b["a_utiliser"]) + ".")
    if b["a_subir"]:
        out.append("Reste à subir : " + ", ".join(gp_items.LABELS[i] for i in b["a_subir"]) + ".")
    if b["non_joues"]:
        out.append("Non joués (coupés dans toutes les courses) : "
                   + ", ".join(gp_items.LABELS[i] for i in b["non_joues"]) + ".")
    out.append("Bilan : " + ("tous les contrôles passent." if b["ok"] else "contrôles incomplets ou en échec."))
    out.append("À cocher par le cycliste : ressenti sous les pieds, lisibilité, esquive au Click et au clavier.")
    return "\n".join(out)


def journaux_gp(dossier: Path) -> list[Path]:
    """Journaux du dossier qui contiennent une course du Grand Prix, du plus ancien au plus récent."""
    files = sorted(dossier.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    return [f for f in files if '"gp_start"' in f.read_text(encoding="utf-8", errors="replace")]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m openride_core.tools.gp_recette", description=__doc__.split("\n")[0])
    ap.add_argument("journaux", nargs="*", type=Path, help="journaux de séance (.jsonl)")
    ap.add_argument("--dernieres", type=int, metavar="N", help="les N dernières courses du profil en cours")
    ap.add_argument("--dossier", type=Path, help="dossier des journaux (défaut : celui du profil en cours)")
    ap.add_argument("--json", action="store_true", help="bilan en JSON")
    args = ap.parse_args(argv)
    paths = list(args.journaux)
    if not paths:
        dossier = args.dossier
        if dossier is None:
            from .. import profiles
            dossier = profiles.current().journal_dir
        found = journaux_gp(dossier) if dossier.is_dir() else []
        if args.dernieres:
            paths = found[-args.dernieres:]
        else:
            today = date.today()
            paths = [f for f in found if date.fromtimestamp(f.stat().st_mtime) == today]
    courses: list[Course] = []
    for p in paths:
        try:
            courses += lire(p)
        except OSError as exc:
            print(f"journal illisible : {p} ({exc})", file=sys.stderr)
    if not courses:
        print("Aucune course du Grand Prix des objets dans les journaux lus.", file=sys.stderr)
        return 2
    b = bilan(courses)
    print(json.dumps(b, ensure_ascii=False, indent=1) if args.json else texte(b))
    return 0 if b["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
