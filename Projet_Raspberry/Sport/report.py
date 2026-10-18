"""Instantané Markdown pour le coach + exports CSV."""
import csv
import json

import exercises as ex_mod
import training
import statistics as st
from datetime import date, timedelta
from pathlib import Path


def _series(con, col, start, end):
    assert col.replace("_", "").isalnum()
    rows = con.execute(f"SELECT day, {col} v FROM daily WHERE day>=? AND day<=? AND {col} IS NOT NULL "
                       "ORDER BY day", (start, end)).fetchall()
    return [r["v"] for r in rows]


def exercise_label(key):
    """INCLINE_DUMBBELL_BENCH_PRESS -> Incline dumbbell bench press."""
    if not key:
        return "exercice non identifié"
    return key.replace("_", " ").capitalize()


def _mean(x):
    return sum(x) / len(x) if x else None


def _f(x, nd=0, unit=""):
    return "n/d" if x is None else f"{x:.{nd}f}{unit}"


def snapshot(con, today=None, k_sd=0.75):
    today = today or date.today()
    iso = lambda d: d.isoformat()
    w_start, b_end, b_start = iso(today - timedelta(days=6)), iso(today - timedelta(days=7)), iso(today - timedelta(days=34))
    L = [f"# Instantané coach – {iso(today)}", ""]
    last = con.execute("SELECT MAX(day) d FROM daily").fetchone()["d"]
    L.append(f"Dernières données Garmin : {last or 'aucune'}")

    # --- VFC : moyenne 7 j vs corridor de 28 j précédents ---
    L += ["", "## Récupération"]
    cur, base = _series(con, "hrv_last_night", w_start, iso(today)), _series(con, "hrv_last_night", b_start, b_end)
    if len(cur) >= 3 and len(base) >= 14:
        m, sd = st.mean(base), st.pstdev(base)
        lo, hi, c = m - k_sd * sd, m + k_sd * sd, st.mean(cur)
        verdict = ("sous le corridor (alerte de gradient si > 3 jours, à croiser avec le ressenti)" if c < lo else
                   "au-dessus du corridor (à surveiller aussi)" if c > hi else "dans le corridor")
        L.append(f"- VFC (rMSSD) moyenne 7 j : {c:.0f} ms ; corridor {lo:.0f}–{hi:.0f} ms (28 j, ±{k_sd} écart-type) → **{verdict}**")
    else:
        L.append(f"- VFC : données insuffisantes ({len(cur)} nuits récentes, {len(base)} en base de référence)")
    r_cur, r_base = _mean(_series(con, "resting_hr", w_start, iso(today))), _mean(_series(con, "resting_hr", b_start, b_end))
    L.append(f"- FC repos 7 j : {_f(r_cur)} bpm (référence 28 j : {_f(r_base)}, écart {_f(r_cur - r_base if r_cur and r_base else None, 1)})")
    sl = _series(con, "sleep_seconds", w_start, iso(today))
    ss = _series(con, "sleep_start_min", w_start, iso(today))
    L.append(f"- Sommeil 7 j : {_f(_mean(sl) / 3600 if sl else None, 1)} h/nuit ; régularité du coucher (écart-type) : "
             f"{_f(st.pstdev(ss) if len(ss) > 2 else None)} min ; score moyen {_f(_mean(_series(con, 'sleep_score', w_start, iso(today))))}")
    L.append(f"- Body Battery max (moy. 7 j) : {_f(_mean(_series(con, 'body_battery_high', w_start, iso(today))))} ; "
             f"Training Readiness (dernier) : {_f((_series(con, 'training_readiness', b_start, iso(today)) or [None])[-1])}")
    w15 = _series(con, "weight_kg", iso(today - timedelta(days=15)), iso(today))
    vo2 = _series(con, "vo2max", b_start, iso(today))
    L.append(f"- Poids moyen 15 j : {_f(_mean(w15), 1)} kg ({len(w15)} pesées, cible : 1 tous les 5 jours) ; VO2max Garmin : {_f(vo2[-1] if vo2 else None, 1)}")
    r28 = _mean(_series(con, "resting_hr", iso(today - timedelta(days=27)), iso(today)))
    L.append(f"- FC repos moyenne 28 j : {_f(r28, 1)} bpm")
    pas = _mean(_series(con, "steps", iso(today - timedelta(days=7)), iso(today - timedelta(days=1))))  # 7 jours complets
    L.append(f"- Pas/jour (7 derniers jours complets) : {_f(pas)} (objectif 7 000–8 000)")

    # --- activités ---
    L += ["", "## Activités des 7 derniers jours"]
    acts = con.execute("SELECT * FROM v_activity_weather WHERE day>=? ORDER BY start_local", (w_start,)).fetchall()
    if acts:
        L += ["| Date | Type | Durée | FC moy | P moy | PN | Charge | Effet Garmin | Météo |", "|---|---|---|---|---|---|---|---|---|"]
        for a in acts:
            meteo = f"{_f(a['temp_c'])}°C, {_f(a['humidity'])} %, vent {_f(a['wind_kmh'])} km/h" if a["temp_c"] is not None else "n/d"
            L.append(f"| {a['start_local'][:16]} | {a['type']} | {_f((a['duration_s'] or 0) / 60)} min | {_f(a['avg_hr'])} | "
                     f"{_f(a['avg_power'])} | {_f(a['norm_power'])} | {_f(a['training_load'])} | {training.effect(a)} | {meteo} |")
    else:
        L.append("Aucune activité.")
    t7 = con.execute("SELECT SUM(duration_s) s FROM v_activities WHERE day>=?", (w_start,)).fetchone()["s"] or 0
    t28 = con.execute("SELECT SUM(duration_s) s FROM v_activities WHERE day>=? AND day<=?", (b_start, b_end)).fetchone()["s"] or 0
    L.append(f"\nVolume 7 j : {t7 / 3600:.1f} h (moyenne hebdo des 28 j précédents : {t28 / 3600 / 4:.1f} h)")
    L += training.section(training.metrics(con, today))

    # --- musculation : détail des séries (Garmin) ---
    sess = con.execute(
        "SELECT a.activity_id, a.start_local, a.duration_s, a.avg_hr, "
        "  SUM(s.set_type='ACTIVE' AND s.reps>0) n_sets, "
        "  SUM(CASE WHEN s.set_type='ACTIVE' AND s.reps>0 THEN s.reps END) reps, "
        "  SUM(CASE WHEN s.set_type='ACTIVE' AND s.reps>0 THEN COALESCE(s.weight_kg,0)*s.reps END) tonnage, "
        "  SUM(s.set_type='ACTIVE' AND s.reps>0 AND (s.wkt_step IS NOT NULL OR s.probability>=99) AND COALESCE(s.category,'UNKNOWN')<>'UNKNOWN') n_conf "
        "FROM v_activities a LEFT JOIN strength_sets s ON s.activity_id=a.activity_id "
        "WHERE a.type='strength_training' AND a.day>=? AND a.day<=? GROUP BY a.activity_id ORDER BY a.start_local",
        (w_start, iso(today))).fetchall()
    if sess:
        L += ["", "## Musculation (7 derniers jours, détail Garmin)",
              "| Date | Durée | Séries | Répétitions | Tonnage (kg) | Séries confirmées | FC moy |", "|---|---|---|---|---|---|---|"]
        for r in sess:
            L.append(f"| {r['start_local'][:16]} | {_f((r['duration_s'] or 0) / 60)} min | {_f(r['n_sets'])} | {_f(r['reps'])} | "
                     f"{_f(r['tonnage'])} | {_f(r['n_conf'])}/{_f(r['n_sets'])} | {_f(r['avg_hr'])} |")
        rows = con.execute(
            "SELECT a.start_local, s.activity_id, s.category, s.exercise, s.reps, s.weight_kg, s.probability, s.wkt_step "
            "FROM strength_sets s JOIN v_activities a ON a.activity_id=s.activity_id "
            "WHERE s.set_type='ACTIVE' AND s.reps>0 AND a.day>=? AND a.day<=? ORDER BY a.start_local, s.set_idx",
            (w_start, iso(today))).fetchall()
        groups, auto = {}, 0
        for r in rows:
            if not ex_mod.confirmed(r["probability"], r["wkt_step"], r["category"]):
                auto += 1
                continue
            k = (r["start_local"][:10], ex_mod.label(r["category"], r["exercise"]))
            w = r["weight_kg"]
            groups.setdefault(k, []).append(f"{'PDC' if not w else format(w, 'g')}×{r['reps']}")
        if groups:
            L.append("\nDétail des séries confirmées (charge × répétitions, PDC = poids du corps) :")
            for (d, lab), sets in groups.items():
                L.append(f"- {d} · {lab} : {', '.join(sets)}")
        if auto:
            L.append(f"\n{auto} série(s) détectée(s) automatiquement par la montre, sans confirmation : exercice et charge "
                     "peu fiables, non détaillés. Utilise tes entraînements programmés (Séance A/B) pour un suivi exact.")

    # --- doublons ignorés (30 derniers jours) ---
    dups = con.execute("SELECT start_local, type, name, duration_s, avg_hr, avg_power FROM v_duplicates "
                       "WHERE day>=? ORDER BY start_local", (iso(today - timedelta(days=30)),)).fetchall()
    if dups:
        L += ["", "## Doublons ignorés (30 derniers jours)",
              "Activités enregistrées deux fois (montre + compteur). Le coach n'en compte qu'une ; "
              "supprime celles-ci dans Garmin Connect si tu veux que la charge Garmin soit juste aussi."]
        for d in dups:
            L.append(f"- {d['start_local'][:16]} · {d['type']} · {d['name'] or ''} · {_f((d['duration_s'] or 0) / 60)} min · "
                     f"FC {_f(d['avg_hr'])} · P {_f(d['avg_power'])}")

    # --- météo à venir ---
    L += ["", "## Météo à venir"]
    for w in con.execute("SELECT * FROM v_weather_daily WHERE day>=? ORDER BY day LIMIT 4", (iso(today),)):
        L.append(f"- {w['day']} : {_f(w['tmin'])}–{_f(w['tmax'])} °C, pluie {_f(w['precip_mm'], 1)} mm, vent max {_f(w['wind_max_kmh'])} km/h")
    return "\n".join(L) + "\n"


def export(con, out_dir, today=None):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "coach_snapshot.md").write_text(snapshot(con, today), encoding="utf-8")
    (out / "coach_metrics.json").write_text(json.dumps(training.metrics(con, today), ensure_ascii=False, indent=1),
                                            encoding="utf-8")
    for name, sql in [("daily", "SELECT * FROM daily ORDER BY day"),
                      ("activities", "SELECT * FROM v_activity_weather ORDER BY start_local"),
                      ("weather_daily", "SELECT * FROM v_weather_daily ORDER BY day")]:
        cur = con.execute(sql)
        with open(out / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([c[0] for c in cur.description])
            w.writerows(cur.fetchall())
    return out
