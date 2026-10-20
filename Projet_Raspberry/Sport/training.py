"""Indicateurs de charge et d'intensité, calculés à partir des données Garmin.

Utilisé par l'instantané du coach (report.py) et par coach_metrics.json (carnet).
"""
from datetime import date, timedelta

STATUS_FR = {"PRODUCTIVE": "Productif", "MAINTAINING": "Maintien", "RECOVERY": "Récupération",
             "UNPRODUCTIVE": "Improductif", "DETRAINING": "Désentraînement", "OVERREACHING": "Surmenage",
             "PEAKING": "Pic de forme", "STRAINED": "Sous tension", "NO_STATUS": "Pas de statut"}
ACWR_FR = {"OPTIMAL": "optimal", "LOW": "faible", "HIGH": "élevé", "VERY_HIGH": "très élevé", "NONE": "n/d"}
BALANCE_FR = {"BALANCED": "Équilibré", "AEROBIC_HIGH_SHORTAGE": "Déficit aérobie intense",
              "AEROBIC_LOW_SHORTAGE": "Déficit aérobie léger", "ANAEROBIC_SHORTAGE": "Déficit anaérobie",
              "AEROBIC_HIGH_FOCUS": "Accent aérobie intense", "AEROBIC_LOW_FOCUS": "Accent aérobie léger",
              "ANAEROBIC_FOCUS": "Accent anaérobie", "NO_DATA": "Pas de données"}
LABEL_FR = {"RECOVERY": "Récupération", "BASE": "Base", "AEROBIC_BASE": "Base aérobie", "UNKNOWN": "Non déterminé", "TEMPO": "Tempo", "LACTATE_THRESHOLD": "Seuil",
            "VO2MAX": "VO2max", "ANAEROBIC_CAPACITY": "Anaérobie", "SPEED": "Vitesse", "NO_BENEFIT": "Sans effet"}

INTENSE_LABELS = {"LACTATE_THRESHOLD", "VO2MAX", "ANAEROBIC_CAPACITY", "SPEED"}
ENDURANCE_TYPES = ("cycling", "biking", "ride", "running")  # supports possibles du 4×4 et de la sortie Z2
CROSSFIT_TYPES = ("indoor_cardio", "hiit", "crossfit")         # le CrossFit compte comme séance intense dans le programme


def fr(table, key):
    if not key:
        return "n/d"
    return table.get(key, key.replace("_", " ").capitalize())


def is_endurance(t):
    return bool(t) and any(k in t for k in ENDURANCE_TYPES)


def is_intense(a):
    """Séance intense au sens du programme (CrossFit, 4×4…). La musculation n'en fait pas partie."""
    if a["type"] == "strength_training":
        return False
    if a["type"] in CROSSFIT_TYPES and (a["duration_s"] or 0) >= 1800:
        return True   # la FC au poignet sous-estime le CrossFit : on suit le programme
    if a["te_label"] and a["te_label"] != "UNKNOWN":
        return a["te_label"] in INTENSE_LABELS   # l'étiquette Garmin prime (les zones FC ne sont pas adaptées à la natation)
    return (a["aerobic_te"] or 0) >= 4.0


def effect(a):
    if a["te_label"] is None and a["aerobic_te"] is None:
        return "n/d"
    te = f"aé {a['aerobic_te']:.1f}" if a["aerobic_te"] is not None else ""
    an = f" / an {a['anaerobic_te']:.1f}" if a["anaerobic_te"] is not None else ""
    lab = fr(LABEL_FR, a["te_label"]) if a["te_label"] else "Sans étiquette"
    return f"{lab} ({te}{an})".replace("( / ", "(")


def metrics(con, today=None):
    today = today or date.today()
    iso = date.isoformat
    m = {"date": iso(today)}

    # --- charge aiguë / chronique (Garmin) ---
    r = con.execute("SELECT * FROM daily WHERE acute_load IS NOT NULL AND day<=? ORDER BY day DESC LIMIT 1",
                    (iso(today),)).fetchone()
    if r:
        acwr = r["acwr"]
        m["load"] = dict(day=r["day"], acute=r["acute_load"], chronic=r["chronic_load"], acwr=acwr,
                         status=fr(ACWR_FR, r["acwr_status"]), training_status=fr(STATUS_FR, r["training_status"]),
                         signal=None if acwr is None else ("au-dessus de 1,3 : signal compté" if acwr > 1.3
                                                            else "sous 0,8 : sous-charge" if acwr < 0.8 else None))
    # --- répartition de la charge sur 4 semaines ---
    r = con.execute("SELECT * FROM daily WHERE load_aer_low IS NOT NULL AND day<=? ORDER BY day DESC LIMIT 1",
                    (iso(today),)).fetchone()
    if r:
        def part(v, lo, hi):
            state = None if v is None or lo is None or hi is None else ("sous la cible" if v < lo else
                                                                       "au-dessus de la cible" if v > hi else "dans la cible")
            return dict(value=v, min=lo, max=hi, state=state)
        m["balance"] = dict(day=r["day"], feedback=fr(BALANCE_FR, r["load_balance"]),
                            aer_low=part(r["load_aer_low"], r["load_aer_low_min"], r["load_aer_low_max"]),
                            aer_high=part(r["load_aer_high"], r["load_aer_high_min"], r["load_aer_high_max"]),
                            anaer=part(r["load_anaer"], r["load_anaer_min"], r["load_anaer_max"]))
    # --- FTP estimé par Garmin ---
    r = con.execute("SELECT day, ftp_w FROM daily WHERE ftp_w IS NOT NULL AND day<=? ORDER BY day DESC LIMIT 1",
                    (iso(today),)).fetchone()
    if r:
        w15 = [x[0] for x in con.execute("SELECT weight_kg FROM daily WHERE weight_kg IS NOT NULL AND day>? AND day<=?",
                                         (iso(today - timedelta(days=15)), iso(today)))]
        if not w15:
            last = con.execute("SELECT weight_kg FROM daily WHERE weight_kg IS NOT NULL AND day<=? ORDER BY day DESC LIMIT 1",
                               (iso(today),)).fetchone()
            w15 = [last[0]] if last else []
        wt = sum(w15) / len(w15) if w15 else None
        m["ftp"] = dict(day=r["day"], watts=r["ftp_w"], weight=wt, wkg=round(r["ftp_w"] / wt, 2) if wt else None)

    # --- minutes d'intensité OMS (7 derniers jours complets) ---
    rows = con.execute("SELECT im_moderate, im_vigorous FROM daily WHERE day>=? AND day<=?",
                       (iso(today - timedelta(days=7)), iso(today - timedelta(days=1)))).fetchall()
    mod = [x[0] for x in rows if x[0] is not None]
    vig = [x[1] for x in rows if x[1] is not None]
    if mod or vig:
        m["oms"] = dict(moderate=sum(mod), vigorous=sum(vig), total=sum(mod) + 2 * sum(vig), days=len(rows))
    return m


def _n(x, nd=0):
    return "n/d" if x is None else f"{x:.{nd}f}".replace(".", ",")


def section(m):
    """Section Markdown « Charge et intensité » de l'instantané."""
    L = ["", "## Charge et intensité (Garmin)"]
    ld = m.get("load")
    if ld:
        sig = f" → **{ld['signal']}**" if ld["signal"] else ""
        L.append(f"- Charge aiguë {_n(ld['acute'])} / chronique {_n(ld['chronic'])} → rapport **{_n(ld['acwr'], 2)}** "
                 f"({ld['status']}){sig} [au {ld['day']}]")
        L.append(f"- Statut d'entraînement Garmin : {ld['training_status']} (contexte seulement, pas un critère de décision)")
    else:
        L.append("- Charge aiguë/chronique : pas encore de données")
    b = m.get("balance")
    if b:
        def p(lbl, x):
            tgt = f" (cible {_n(x['min'])}–{_n(x['max'])}, {x['state']})" if x["state"] else ""
            return f"{lbl} {_n(x['value'])}{tgt}"
        L.append(f"- Répartition 4 semaines : {p('aérobie léger', b['aer_low'])} ; {p('aérobie intense', b['aer_high'])} ; "
                 f"{p('anaérobie', b['anaer'])} → {b['feedback']}")
        L.append("  (le 4×4 se pilote sur l'aérobie intense, comparée à la cible de l'onglet Réglages du carnet)")
    o = m.get("oms")
    if o:
        L.append(f"- Minutes d'intensité OMS (7 j) : {_n(o['total'])} (modérées {_n(o['moderate'])} + 2 × intenses {_n(o['vigorous'])}) ; "
                 "repère OMS 150–300")
    f = m.get("ftp")
    if f:
        L.append(f"- FTP estimé par Garmin : {_n(f['watts'])} W, soit {_n(f['wkg'], 2)} W/kg au poids moyen de {_n(f['weight'], 1)} kg "
                 f"[{f['day']}] (estimation : stagne sans effort maximal ; le test fait foi)")
    L.append("Zones = zones cardiaques réglées dans Garmin ; charges Garmin calculées sur la FC (musculation sous-estimée : voir RPE × durée du carnet).")
    return L
