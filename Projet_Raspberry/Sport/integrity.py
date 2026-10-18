"""Rapport d'intégrité des données (HTML autonome, sans dépendance).

Répond à trois questions :
  1. Qu'est-ce qui manque ?      -> couverture par indicateur + calendrier jour par jour
  2. Qu'est-ce qui est suspect ? -> valeurs hors plage physiologique, sauts de poids
  3. La collecte marche-t-elle ? -> réponses Garmin vides, météo incomplète, doublons
"""
import html
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import exercises as ex_mod

METRICS = [  # (colonne, libellé, unité, min plausible, max plausible)
    ("resting_hr", "FC de repos", "bpm", 30, 90),
    ("hrv_last_night", "VFC nocturne", "ms", 10, 200),
    ("sleep_seconds", "Sommeil", "h", 3 * 3600, 12 * 3600),
    ("body_battery_high", "Body Battery max", "", 1, 100),
    ("stress_avg", "Stress moyen", "", 1, 100),
    ("steps", "Pas", "", 300, 60000),
    ("training_readiness", "Training Readiness", "", 1, 100),
    ("vo2max", "VO2max", "", 25, 80),
    ("weight_kg", "Poids", "kg", 50, 150),
]
DAILY_EXPECTED = {"resting_hr", "hrv_last_night", "sleep_seconds", "body_battery_high", "stress_avg", "steps", "training_readiness"}

CSS = """
:root{--bg:#F3F5F4;--surface:#FFF;--ink:#16282E;--muted:#5C6E73;--line:#D9E1E0;--accent:#1F4E5F;--accent-soft:#E2ECEE;
--good:#2E7D57;--good-soft:#E3F2EA;--warn:#B26A00;--warn-soft:#FBEFD9;--bad:#B3392F;--bad-soft:#F8E3E0;--empty:#E6EBEA}
@media (prefers-color-scheme:dark){:root{--bg:#0F181B;--surface:#172429;--ink:#E4ECEC;--muted:#93A6AA;--line:#2A3A3F;--accent:#7FB8C9;
--accent-soft:#1E3239;--good:#6CC79A;--good-soft:#173328;--warn:#E9B25A;--warn-soft:#352A16;--bad:#EF8A7F;--bad-soft:#3A1F1C;--empty:#22323A;color-scheme:dark}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:24px 16px 48px;display:grid;gap:16px}
h1{font-size:26px;margin:0}h2{font-size:18px;margin:0}.muted{color:var(--muted);font-size:13px;margin:0}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px;display:grid;gap:12px;min-width:0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}
.tile{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.tile .v{font:600 24px ui-monospace,Menlo,Consolas,monospace}.tile .l{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
table{border-collapse:collapse;width:100%;font-size:14px;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.4px}
td.n{font-family:ui-monospace,Menlo,Consolas,monospace;text-align:right}
.tbl{overflow-x:auto}.pill{font-size:12px;font-weight:600;padding:2px 8px;border-radius:999px;white-space:nowrap}
.good{background:var(--good-soft);color:var(--good)}.warn{background:var(--warn-soft);color:var(--warn)}.bad{background:var(--bad-soft);color:var(--bad)}
.info{background:var(--accent-soft);color:var(--accent)}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--muted)}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:-1px}
.cal{overflow-x:auto}.cal svg{display:block}
"""


TYPES = {"cycling": "Vélo", "road_biking": "Vélo route", "indoor_cycling": "Home trainer", "virtual_ride": "Home trainer (virtuel)",
         "mountain_biking": "VTT", "e_bike_fitness": "VAE", "strength_training": "Musculation", "lap_swimming": "Natation piscine",
         "open_water_swimming": "Natation eau libre", "running": "Course à pied", "walking": "Marche", "indoor_cardio": "Cardio en salle (CrossFit)",
         "hiit": "HIIT", "hiking": "Randonnée"}


SOURCES = {"stats": "Résumé du jour (FC repos, pas, stress, Body Battery)", "hrv": "VFC nocturne", "sleep": "Sommeil",
           "readiness": "Training Readiness", "maxmetrics": "VO2max", "exercise_sets": "Séries de musculation (par séance)"}


def _type(t):
    return TYPES.get(t, t)


def _esc(x):
    return html.escape(str(x if x is not None else ""))


def _fmt(v, nd=0):
    if v is None:
        return "–"
    return f"{v:,.{nd}f}".replace(",", " ").replace(".", ",")


def _pill(pct):
    if pct is None:
        return '<span class="pill info">–</span>'
    cls = "good" if pct >= 90 else "warn" if pct >= 60 else "bad"
    return f'<span class="pill {cls}">{_fmt(pct)} %</span>'


def _days(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def build(con, out_path, today=None):
    today = today or date.today()
    rows = {r["day"]: dict(r) for r in con.execute("SELECT * FROM daily ORDER BY day")}
    if not rows:
        Path(out_path).write_text("<p>Aucune donnée.</p>", encoding="utf-8")
        return out_path
    first = date.fromisoformat(min(rows))
    last = min(date.fromisoformat(max(rows)), today)
    all_days = [d.isoformat() for d in _days(first, last)]
    yesterday = (today - timedelta(days=1)).isoformat()

    # ---------- couverture et valeurs suspectes ----------
    def cov(col, n):
        win = [d for d in all_days if d <= yesterday][-n:]
        if not win:
            return None
        return 100 * sum(1 for d in win if rows.get(d, {}).get(col) is not None) / len(win)

    suspects = []
    for col, label, unit, lo, hi in METRICS:
        for d in all_days:
            if d > yesterday:  # journée en cours : incomplète par nature
                continue
            v = rows.get(d, {}).get(col)
            if col == "steps" and v is not None and v < lo:
                suspects.append((d, label, _fmt(v), "très peu de pas : montre peu ou pas portée ce jour-là"))
                continue
            if v is not None and not (lo <= v <= hi):
                shown = v / 3600 if col == "sleep_seconds" else v
                suspects.append((d, label, _fmt(shown, 1), f"hors plage plausible ({_fmt(lo / 3600 if col == 'sleep_seconds' else lo)}–{_fmt(hi / 3600 if col == 'sleep_seconds' else hi)} {unit})"))
    w = [(d, rows[d]["weight_kg"]) for d in all_days if rows.get(d, {}).get("weight_kg") is not None]
    for (d0, v0), (d1, v1) in zip(w, w[1:]):
        gap = (date.fromisoformat(d1) - date.fromisoformat(d0)).days
        if gap <= 3 and abs(v1 - v0) > 1.5:
            suspects.append((d1, "Poids", _fmt(v1, 1), f"saut de {_fmt(v1 - v0, 1)} kg en {gap} j (pesée à vérifier)"))
    suspects.sort()
    bad_cells = {(d, lbl) for d, lbl, *_ in suspects}

    summary = []
    for col, label, unit, lo, hi in METRICS:
        vals = [d for d in all_days if rows.get(d, {}).get(col) is not None]
        summary.append((label, cov(col, 30), cov(col, 90), len(vals), vals[-1] if vals else None,
                        sum(1 for s in suspects if s[1] == label), col in DAILY_EXPECTED))

    # trous récents (90 j) sur les indicateurs quotidiens clés
    gaps = []
    recent = [d for d in all_days if d <= yesterday][-90:]
    for col, label, *_ in METRICS[:3]:
        run = []
        for d in recent + ["fin"]:
            if d != "fin" and rows.get(d, {}).get(col) is None:
                run.append(d)
            else:
                if len(run) >= 2:
                    gaps.append((run[0], run[-1], len(run), label))
                run = []
    gaps.sort()

    # ---------- calendrier de couverture (SVG) ----------
    cell, gapx, labw, rowh = 3, 0, 150, 16
    width = labw + len(all_days) * cell + 10
    height = 24 + len(METRICS) * rowh
    parts = [f'<svg width="{width}" height="{height}" role="img" aria-label="Couverture jour par jour">']
    for i, d in enumerate(all_days):
        if d.endswith("-01") or i == 0:
            x = labw + i * cell
            parts.append(f'<line x1="{x}" x2="{x}" y1="14" y2="{height}" stroke="var(--line)" stroke-width="1"/>')
            parts.append(f'<text x="{x + 2}" y="11" font-size="10" fill="var(--muted)">{d[:7]}</text>')
    for r, (col, label, *_rest) in enumerate(METRICS):
        y = 20 + r * rowh
        parts.append(f'<text x="0" y="{y + 9}" font-size="11" fill="var(--ink)">{_esc(label)}</text>')
        for i, d in enumerate(all_days):
            v = rows.get(d, {}).get(col)
            color = "var(--bad)" if (d, label) in bad_cells else "var(--accent)" if v is not None else "var(--empty)"
            parts.append(f'<rect x="{labw + i * cell}" y="{y}" width="{cell}" height="{rowh - 4}" fill="{color}"><title>{d} · {_esc(label)} : {"–" if v is None else _esc(round(v, 1))}</title></rect>')
    parts.append("</svg>")
    calendar = "".join(parts)

    # ---------- activités ----------
    by_type = con.execute("SELECT type, COUNT(*) n, ROUND(SUM(duration_s)/3600.0,1) h FROM v_activities GROUP BY type ORDER BY n DESC").fetchall()
    dups = con.execute("SELECT * FROM v_duplicates ORDER BY start_local").fetchall()
    no_hr = con.execute("SELECT * FROM v_activities WHERE avg_hr IS NULL ORDER BY start_local DESC LIMIT 15").fetchall()
    bike_no_p = con.execute("SELECT * FROM v_activities WHERE type IN ('cycling','road_biking','indoor_cycling','virtual_ride') "
                            "AND avg_power IS NULL AND duration_s > 1200 ORDER BY start_local DESC LIMIT 15").fetchall()
    short = con.execute("SELECT * FROM v_activities WHERE duration_s < 300 ORDER BY start_local DESC LIMIT 15").fetchall()
    no_wx = con.execute("SELECT * FROM v_activity_weather WHERE temp_c IS NULL ORDER BY start_local DESC LIMIT 15").fetchall()
    n_act = con.execute("SELECT COUNT(*) FROM activities").fetchone()[0]

    # ---------- musculation ----------
    st_total = con.execute("SELECT COUNT(*) FROM v_activities WHERE type='strength_training'").fetchone()[0]
    st_detail = con.execute("SELECT COUNT(*) FROM strength_fetched f JOIN v_activities a USING(activity_id) WHERE f.n_sets>0").fetchone()[0]
    st_empty = con.execute("SELECT COUNT(*) FROM strength_fetched f JOIN v_activities a USING(activity_id) WHERE f.n_sets=0").fetchone()[0]
    st_todo = st_total - st_detail - st_empty
    st_rows = con.execute(
        "SELECT s.category, s.exercise, s.activity_id, a.day, s.weight_kg, s.probability, s.wkt_step "
        "FROM strength_sets s JOIN v_activities a ON a.activity_id=s.activity_id WHERE s.set_type='ACTIVE' AND s.reps>0").fetchall()
    agg = {}
    for r in st_rows:
        k = ex_mod.label(r["category"], r["exercise"])
        g = agg.setdefault(k, {"acts": set(), "sets": 0, "conf": 0, "last": "", "wmax": None, "no_w": 0})
        g["acts"].add(r["activity_id"]); g["sets"] += 1; g["last"] = max(g["last"], r["day"])
        g["conf"] += 1 if ex_mod.confirmed(r["probability"], r["wkt_step"], r["category"]) else 0
        if r["weight_kg"]:
            g["wmax"] = max(g["wmax"] or 0, r["weight_kg"])
        else:
            g["no_w"] += 1
    st_ex = sorted(agg.items(), key=lambda kv: (kv[1]["last"], len(kv[1]["acts"])), reverse=True)
    st_conf_pct = 100 * sum(g["conf"] for g in agg.values()) / max(1, sum(g["sets"] for g in agg.values()))
    st_unknown = con.execute("SELECT COUNT(*) FROM strength_sets WHERE set_type='ACTIVE' AND reps>0 AND (category IS NULL OR category='UNKNOWN')").fetchone()[0]

    # ---------- météo ----------
    wx = {r[0]: (r[1], r[2]) for r in con.execute("SELECT substr(ts,1,10), COUNT(*), MAX(source) FROM weather_hourly GROUP BY substr(ts,1,10)")}
    wx_missing = [d for d in all_days if d not in wx]
    wx_partial = [(d, wx[d][0]) for d in all_days if d in wx and wx[d][0] < 24]
    wx_future = sorted(d for d in wx if d > today.isoformat())

    # ---------- collecte Garmin ----------
    raw = con.execute("SELECT endpoint, COUNT(*) n, MAX(fetched_at) last FROM raw_garmin GROUP BY endpoint").fetchall()
    empty = {}
    for ep, payload in con.execute("SELECT endpoint, payload FROM raw_garmin"):
        try:
            p = json.loads(payload)
        except (TypeError, ValueError):
            p = None
        is_empty = (p in (None, {}, [])) or (isinstance(p, dict) and not any(v not in (None, [], {}) for k, v in p.items() if k not in ("userProfileId", "displayName", "userProfilePK", "calendarDate")))
        if ep == "sleep" and isinstance(p, dict):
            is_empty = not (p.get("dailySleepDTO") or {}).get("sleepTimeSeconds")
        if ep == "stats" and isinstance(p, dict):
            is_empty = p.get("totalSteps") is None and p.get("restingHeartRate") is None
        empty[ep] = empty.get(ep, 0) + (1 if is_empty else 0)
    last_fetch = max((r["last"] for r in raw if r["last"]), default=None)

    # ---------- page ----------
    def table(head, body, empty_msg):
        if not body:
            return f'<p class="muted">{empty_msg}</p>'
        return ('<div class="tbl"><table><thead><tr>' + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead><tbody>"
                + "".join("<tr>" + "".join(c for c in r) + "</tr>" for r in body) + "</tbody></table></div>")

    def act_rows(lst):
        return [(f"<td>{_esc(a['start_local'][:16])}</td>", f"<td>{_esc(_type(a['type']))}</td>", f"<td>{_esc(a['name'])}</td>",
                 f'<td class="n">{_fmt((a["duration_s"] or 0) / 60)} min</td>', f'<td class="n">{_fmt(a["avg_hr"])}</td>',
                 f'<td class="n">{_fmt(a["avg_power"])}</td>') for a in lst]
    act_head = ["Début", "Type", "Nom", "Durée", "FC moy", "P moy"]

    core30 = [s[1] for s in summary if s[6] and s[1] is not None]
    H = [f"<!doctype html><html lang='fr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
         f"<title>Intégrité des données</title><style>{CSS}</style></head><body><div class='wrap'>",
         f"<header><h1>Intégrité des données du coach</h1><p class='muted'>Période {first.isoformat()} → {last.isoformat()} · "
         f"généré le {datetime.now().strftime('%Y-%m-%d %H:%M')} · dernière collecte Garmin : {_esc((last_fetch or '–').replace('T', ' '))}</p></header>",
         "<div class='tiles'>",
         f"<div class='tile'><div class='l'>Jours couverts</div><div class='v'>{len(all_days)}</div></div>",
         f"<div class='tile'><div class='l'>Couverture 30 j (moy.)</div><div class='v'>{_fmt(sum(core30) / len(core30) if core30 else None)} %</div></div>",
         f"<div class='tile'><div class='l'>Valeurs suspectes</div><div class='v'>{len(suspects)}</div></div>",
         f"<div class='tile'><div class='l'>Activités (doublons)</div><div class='v'>{n_act - len(dups)} <small style='font-size:14px'>({len(dups)})</small></div></div>",
         f"<div class='tile'><div class='l'>Jours sans météo</div><div class='v'>{len(wx_missing)}</div></div>",
         "</div>"]

    H.append("<section class='card'><h2>Couverture par indicateur</h2>"
             "<p class='muted'>Part des jours qui ont une valeur, hors aujourd'hui. Les indicateurs quotidiens devraient être proches de 100 % ; "
             "poids et VO2max sont ponctuels par nature.</p>")
    H.append(table(["Indicateur", "30 j", "90 j", "Jours avec valeur", "Dernière valeur", "Suspectes"],
                   [(f"<td>{_esc(l)}{'' if q else ' <span class=muted>(ponctuel)</span>'}</td>",
                     f"<td>{_pill(c30) if q else '–'}</td>", f"<td>{_pill(c90) if q else '–'}</td>", f'<td class="n">{n}</td>',
                     f"<td>{_esc(lastd or '–')}</td>", f'<td class="n">{s}</td>') for l, c30, c90, n, lastd, s, q in summary], ""))
    H.append("</section>")

    H.append("<section class='card'><h2>Calendrier de couverture</h2>"
             "<div class='legend'><span><i style='background:var(--accent)'></i>valeur présente</span>"
             "<span><i style='background:var(--empty)'></i>absente</span><span><i style='background:var(--bad)'></i>suspecte</span></div>"
             f"<div class='cal'>{calendar}</div><p class='muted'>Survole une case pour voir la date et la valeur.</p></section>")

    H.append("<section class='card'><h2>Valeurs suspectes</h2>")
    H.append(table(["Date", "Indicateur", "Valeur", "Motif"],
                   [(f"<td>{d}</td>", f"<td>{_esc(l)}</td>", f'<td class="n">{v}</td>', f"<td>{_esc(m)}</td>") for d, l, v, m in suspects[-40:]],
                   "Aucune valeur hors plage."))
    H.append("</section>")

    H.append("<section class='card'><h2>Trous récents (90 jours)</h2><p class='muted'>Deux jours consécutifs ou plus sans FC de repos, VFC ou sommeil : "
             "montre non portée la nuit, batterie vide ou synchronisation manquée.</p>")
    H.append(table(["Du", "Au", "Jours", "Indicateur"],
                   [(f"<td>{a}</td>", f"<td>{b}</td>", f'<td class="n">{n}</td>', f"<td>{_esc(l)}</td>") for a, b, n, l in gaps], "Aucun trou de 2 jours ou plus."))
    H.append("</section>")

    H.append("<section class='card'><h2>Activités</h2>")
    H.append(table(["Type", "Nombre", "Heures"], [(f"<td>{_esc(_type(r['type']))}</td>", f'<td class="n">{r["n"]}</td>', f'<td class="n">{_fmt(r["h"], 1)}</td>') for r in by_type], ""))
    H.append("<h2 style='font-size:16px'>Doublons écartés</h2><p class='muted'>Même sortie enregistrée par deux appareils. "
             "Le coach n'en compte qu'une ; à supprimer dans Garmin Connect pour que la charge Garmin soit juste.</p>")
    H.append(table(act_head, act_rows(dups), "Aucun doublon."))
    H.append("<h2 style='font-size:16px'>Sorties vélo de plus de 20 min sans puissance</h2>")
    H.append(table(act_head, act_rows(bike_no_p), "Aucune."))
    H.append("<h2 style='font-size:16px'>Activités sans FC (15 dernières)</h2>")
    H.append(table(act_head, act_rows(no_hr), "Aucune."))
    H.append("<h2 style='font-size:16px'>Activités de moins de 5 min (15 dernières)</h2>")
    H.append(table(act_head, act_rows(short), "Aucune."))
    H.append("<h2 style='font-size:16px'>Activités sans météo associée</h2>")
    H.append(table(act_head, act_rows(no_wx), "Toutes les activités ont leur météo."))
    H.append("</section>")

    H.append("<section class='card'><h2>Musculation : détail des séries</h2>"
             f"<p class='muted'>{st_total} séances de musculation : {st_detail} avec le détail des séries, "
             f"{st_empty} sans détail (séance enregistrée sans exercices), {st_todo} pas encore lues "
             f"(lues au fil des synchronisations). Séries sans exercice identifié : {st_unknown}.</p>")
    H.append(f"<p class='muted'>Séries confirmées (entraînement programmé, ou exercice corrigé dans Garmin Connect) : "
             f"{_fmt(st_conf_pct)} %. Les autres sont devinées par la montre en séance libre : exercice et charge peu fiables.</p>")
    H.append(table(["Exercice", "Séances", "Séries", "Confirmées", "Dernière", "Charge max", "Sans charge"],
                   [(f"<td>{_esc(k)}</td>", f'<td class="n">{len(g["acts"])}</td>', f'<td class="n">{g["sets"]}</td>',
                     f"<td>{_pill(100 * g['conf'] / g['sets'])}</td>", f"<td>{_esc(g['last'])}</td>",
                     f'<td class="n">{_fmt(g["wmax"], 1)}</td>', f'<td class="n">{g["no_w"]}</td>') for k, g in st_ex],
                   "Aucune série lue pour l'instant : elles arrivent au prochain sync."))
    H.append("<p class='muted'>« Séries sans charge » : normal pour les exercices au poids du corps (tractions, pompes, relevés) ; "
             "pour les autres, la charge n'a pas été saisie sur la montre ou dans Garmin Connect.</p></section>")
    H.append("<section class='card'><h2>Météo</h2>")
    H.append(f"<p class='muted'>{len(all_days) - len(wx_missing)} jours sur {len(all_days)} couverts ; "
             f"{len(wx_partial)} jours incomplets (moins de 24 heures) ; prévisions jusqu'au {wx_future[-1] if wx_future else '–'}.</p>")
    H.append(table(["Jour manquant"], [(f"<td>{d}</td>",) for d in wx_missing[-20:]], "Aucun jour manquant."))
    H.append(table(["Jour incomplet", "Heures"], [(f"<td>{d}</td>", f'<td class="n">{n}</td>') for d, n in wx_partial[-20:]], ""))
    H.append("</section>")

    H.append("<section class='card'><h2>Collecte Garmin</h2><p class='muted'>Une réponse vide signifie que Garmin n'avait rien pour ce jour "
             "(montre non portée, ou fonction absente de l'appareil utilisé à cette date), pas une erreur du script.</p>")
    H.append(table(["Source", "Jours interrogés", "Réponses vides", "Dernière collecte"],
                   [(f"<td>{_esc(SOURCES.get(r['endpoint'], r['endpoint']))}</td>", f'<td class="n">{r["n"]}</td>', f'<td class="n">{empty.get(r["endpoint"], 0)}</td>',
                     f"<td>{_esc((r['last'] or '').replace('T', ' '))}</td>") for r in raw], "Aucune collecte enregistrée."))
    H.append("</section></div></body></html>")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("".join(H), encoding="utf-8")
    return out_path
