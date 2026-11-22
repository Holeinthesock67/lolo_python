extends RefCounted

## Modèle de l'écran de fin de séance (Lot N4, Contrat IPC v1 §3 et §7, v1.1 §4.3).
##
## Calcule les textes, unités, arrondis et bilan par bloc en ERG,
## ainsi que l'écran de menu associé, sans aucun nœud Godot.
## Pas de class_name : charger par preload("res://scripts/summary_view_model.gd").

const SurvivorHudModel := preload("res://scripts/survivor/survivor_hud_model.gd")
const GpHudModel := preload("res://scripts/grandprix/gp_hud_model.gd")
const SegmentHudModel := preload("res://scripts/segment_hud_model.gd")
const TrackHudModel := preload("res://scripts/track/track_hud_model.gd")
const FeedbackModel := preload("res://scripts/feedback_model.gd")

const KEY_DURATION := "duration_s"
const KEY_DISTANCE := "distance_m"
const KEY_AVG_POWER := "avg_power_w"
const KEY_NP := "np_w"
const KEY_IF := "intensity_factor"
const KEY_TSS := "tss"
const KEY_ELEVATION_GAIN := "elevation_gain_m"
const KEY_AVG_CADENCE := "avg_cadence_rpm"
const KEY_AVG_HR := "avg_hr_bpm"
const KEY_MAX_POWER := "max_power_w"
const KEY_BLOCKS := "blocks"
const KEY_FIT_PATH := "fit_path"
const KEY_DRAFT_TIME := "draft_time_s"   # lot AS5 : temps dans la roue, énergie économisée à l'abri
const KEY_DRAFT_KJ := "draft_kj"
const KEY_POWER_PROFILE := "power_profile"   # lot N20 (révision 1.10) : courbe réduite du graphique du bilan
const KEY_FTP_TEST := "ftp_test"

## Avertissements du test de FTP (`summary.ftp_test.warnings`), comme `openride-core ftp-test` ; repris par
## l'Historique et le menu.
const FTP_WARNINGS := {"too_short": "test trop court", "erratic_cadence": "cadence erratique",
	"trainer_dropout": "coupure du trainer pendant l'effort", "paused": "pause pendant l'effort"}
## Tuiles du bilan en tuiles (lot N20) : six au plus, dans cet ordre.
const MAX_TILES := 6
## Records battus listés au plus dans le bilan (les suivants : « … et N autres records »).
const MAX_RECORD_LINES := 3

const COLOR_GREEN := "vert"
const COLOR_ORANGE := "orange"
const COLOR_RED := "rouge"
const COLOR_NEUTRAL := "neutre"   # bloc sans cible connue (ancien journal, cible absente)


static func _format_fr_float(val: float, decimals: int) -> String:
	var fmt := "%%.%df" % decimals
	return (fmt % val).replace(".", ",")


static func _format_fr_round(val: Variant) -> String:
	if val == null:
		return ""
	var f := float(val)
	return str(int(round(f)))


static func _format_hms(seconds: float) -> String:
	var total := int(round(maxf(seconds, 0.0)))
	var h := total / 3600
	var rem := total % 3600
	var m := rem / 60
	var s := rem % 60
	return "%d:%02d:%02d" % [h, m, s]


## Lignes du bilan formatées {label, value, unit} dans un ordre fixe.
## Une ligne est absente si le champ correspondant manque ou vaut null.
func lines(summary: Dictionary, _mode: String = "", _ftp_w: int = 0) -> Array:
	var out: Array = []

	# 1. Durée
	if summary.has(KEY_DURATION) and summary[KEY_DURATION] != null:
		out.append({
			"label": "Durée",
			"value": _format_hms(float(summary[KEY_DURATION])),
			"unit": ""
		})

	# 2. Distance (km, deux décimales)
	if summary.has(KEY_DISTANCE) and summary[KEY_DISTANCE] != null:
		var km := float(summary[KEY_DISTANCE]) / 1000.0
		out.append({
			"label": "Distance",
			"value": _format_fr_float(km, 2),
			"unit": "km"
		})

	# 3. Puissance moyenne
	if summary.has(KEY_AVG_POWER) and summary[KEY_AVG_POWER] != null:
		out.append({
			"label": "Puissance moyenne",
			"value": _format_fr_round(summary[KEY_AVG_POWER]),
			"unit": "W"
		})

	# 4. Puissance normalisée (NP)
	if summary.has(KEY_NP) and summary[KEY_NP] != null:
		out.append({
			"label": "Puissance normalisée",
			"value": _format_fr_round(summary[KEY_NP]),
			"unit": "W"
		})

	# 5. IF (Facteur d'intensité)
	var if_val = summary.get(KEY_IF, summary.get("if", null))
	if if_val != null:
		out.append({
			"label": "IF",
			"value": _format_fr_float(float(if_val), 2),
			"unit": ""
		})

	# 6. TSS
	if summary.has(KEY_TSS) and summary[KEY_TSS] != null:
		out.append({
			"label": "TSS",
			"value": _format_fr_round(summary[KEY_TSS]),
			"unit": ""
		})

	# 7. Dénivelé
	if summary.has(KEY_ELEVATION_GAIN) and summary[KEY_ELEVATION_GAIN] != null:
		out.append({
			"label": "Dénivelé",
			"value": _format_fr_round(summary[KEY_ELEVATION_GAIN]),
			"unit": "m"
		})

	# 8. Cadence
	var cad_val = summary.get(KEY_AVG_CADENCE, null)
	if cad_val == null and summary.get("cadence") is Dictionary:
		cad_val = summary["cadence"].get("avg", null)
	if cad_val != null:
		out.append({
			"label": "Cadence",
			"value": _format_fr_round(cad_val),
			"unit": "rpm"
		})

	# 9. FC moyenne
	var hr_val = summary.get(KEY_AVG_HR, null)
	if hr_val == null and summary.get("hr") is Dictionary:
		hr_val = summary["hr"].get("avg", null)
	if hr_val != null:
		out.append({
			"label": "FC moyenne",
			"value": _format_fr_round(hr_val),
			"unit": "bpm"
		})

	# 10. Puissance max
	var max_p = summary.get(KEY_MAX_POWER, null)
	if max_p != null:
		out.append({
			"label": "Puissance max",
			"value": _format_fr_round(max_p),
			"unit": "W"
		})

	# 11. Abri (lot AS5) : « 12 min dans la roue, 9 kJ économisés », seulement après un passage dans la roue
	var wheel_s = summary.get(KEY_DRAFT_TIME, null)
	if wheel_s != null and float(wheel_s) >= 1.0:
		var wheel_text := ("%d min" % int(round(float(wheel_s) / 60.0))) if float(wheel_s) >= 60.0 \
			else ("%d s" % int(round(float(wheel_s))))
		out.append({"label": "Dans la roue", "value": wheel_text, "unit": ""})
		if summary.get(KEY_DRAFT_KJ, null) != null:
			out.append({"label": "Énergie économisée", "value": _format_fr_round(summary[KEY_DRAFT_KJ]), "unit": "kJ"})

	if summary.get("rogue") is Dictionary:
		out.append_array(rogue_lines(summary["rogue"]))
	if summary.get("wtf") is Dictionary:
		out.append_array(wtf_lines(summary["wtf"]))
	if summary.get("survivor") is Dictionary:   # Dernier survivant (lot DS6) : place, vainqueur, arche par arche
		out.append_array(SurvivorHudModel.summary_lines(summary["survivor"]))
	if summary.get("gp") is Dictionary:   # Grand Prix des objets (lot GP8) : place, objets, temps par objet
		out.append_array(GpHudModel.summary_lines(summary["gp"]))
	if summary.get("track") is Dictionary:   # Épreuves de piste (lot VD9) : place, temps, tours, record
		out.append_array(TrackHudModel.summary_lines(summary["track"]))
	out.append_array(bots_lines(summary))

	return out


## Lignes « Bots » (lot GP-niv : cible visée et moyenne réelle des bots, face à ta puissance moyenne) et « Cote »
## (lot BOT-elo : cote après la course et son écart, place) ; [] sans ces champs (contrat 1.22).
static func bots_lines(summary: Dictionary) -> Array:
	var out: Array = []
	var be = summary.get("bots_effort")
	if be is Dictionary and be.get("target_w") != null:
		var text := "%s W visés" % _format_fr_round(be["target_w"])   # court : la colonne du bilan coupe à ~30 signes
		if be.get("bots_avg_w") != null:
			text += ", %s roulés" % _format_fr_round(be["bots_avg_w"])
		out.append({"label": "Bots", "value": text, "unit": ""})
	var elo = summary.get("elo")
	if elo is Dictionary and elo.get("after") != null:
		var d := int(elo.get("delta", 0))
		var place := int(elo.get("place", 0))
		out.append({"label": "Cote", "value": "%s (%s%d), %s sur %d" % [_format_fr_round(elo["after"]),
			"+" if d >= 0 else "−", absi(d), "1er" if place == 1 else "%de" % place, int(elo.get("of", 0))],
			"unit": ""})
	return out


# --- bilan en tuiles (lot N20, présentation des menus étape 4) ---------------------------------------

static func _num(summary: Dictionary, key: String) -> Variant:
	var v = summary.get(key, null)
	return float(v) if v is int or v is float else null


## Tuiles du bilan {label, value, unit, sub} : distance, durée, dénivelé, puissance moyenne (puissance
## normalisée en `sub`), fréquence cardiaque moyenne, cadence moyenne ; une tuile sans donnée est retirée.
func tiles(summary: Dictionary) -> Array:
	var out: Array = []
	var dist = _num(summary, KEY_DISTANCE)
	if dist != null:
		out.append({"label": "Distance", "value": _format_fr_float(dist / 1000.0, 2), "unit": "km", "sub": ""})
	var dur = _num(summary, KEY_DURATION)
	if dur != null:
		out.append({"label": "Durée", "value": _format_hms(dur), "unit": "", "sub": ""})
	var gain = _num(summary, KEY_ELEVATION_GAIN)
	if gain != null and gain >= 1.0:   # 0 m (ERG, piste plate) : rien à montrer
		out.append({"label": "Dénivelé", "value": _format_fr_round(gain), "unit": "m", "sub": ""})
	var avg = _num(summary, KEY_AVG_POWER)
	if avg != null:
		var np = _num(summary, KEY_NP)
		out.append({"label": "Puissance", "value": _format_fr_round(avg), "unit": "W",
			"sub": ("NP " + _format_fr_round(np)) if np != null else ""})
	var hr = _num(summary, KEY_AVG_HR)
	if hr == null and summary.get("hr") is Dictionary:
		hr = _num(summary["hr"], "avg")
	if hr != null:
		out.append({"label": "FC moyenne", "value": _format_fr_round(hr), "unit": "bpm", "sub": ""})
	var cad = _num(summary, KEY_AVG_CADENCE)
	if cad == null and summary.get("cadence") is Dictionary:
		cad = _num(summary["cadence"], "avg")
	if cad != null:
		out.append({"label": "Cadence", "value": _format_fr_round(cad), "unit": "rpm", "sub": ""})
	return out.slice(0, MAX_TILES)


## Ligne des chiffres qui ne sont pas en tuile : « IF 0,84 · TSS 62 · Puissance max 612 W · Dans la roue
## 12 min · 9 kJ économisés » ; "" sans aucun.
func more_line(summary: Dictionary) -> String:
	var parts: Array[String] = []
	var if_val = _num(summary, KEY_IF)
	if if_val == null:
		if_val = _num(summary, "if")
	if if_val != null:
		parts.append("IF " + _format_fr_float(if_val, 2))
	var tss = _num(summary, KEY_TSS)
	if tss != null:
		parts.append("TSS " + _format_fr_round(tss))
	var max_p = _num(summary, KEY_MAX_POWER)
	if max_p != null:
		parts.append("Puissance max %s W" % _format_fr_round(max_p))
	var wheel_s = _num(summary, KEY_DRAFT_TIME)
	if wheel_s != null and wheel_s >= 1.0:
		parts.append("Dans la roue " + (("%d min" % int(round(wheel_s / 60.0))) if wheel_s >= 60.0
			else ("%d s" % int(round(wheel_s)))))
		var kj = _num(summary, KEY_DRAFT_KJ)
		if kj != null:
			parts.append("%s kJ économisés" % _format_fr_round(kj))
	return " · ".join(parts)


## Lignes propres à un mode (Cyber-Rogue, WTF, Dernier survivant, Grand Prix), au format de lines() ; [] sinon.
func mode_lines(summary: Dictionary) -> Array:
	var out: Array = []
	if summary.get("rogue") is Dictionary:
		out.append_array(rogue_lines(summary["rogue"]))
	if summary.get("wtf") is Dictionary:
		out.append_array(wtf_lines(summary["wtf"]))
	if summary.get("survivor") is Dictionary:
		out.append_array(SurvivorHudModel.summary_lines(summary["survivor"]))
	if summary.get("gp") is Dictionary:
		out.append_array(GpHudModel.summary_lines(summary["gp"]))
	out.append_array(bots_lines(summary))   # lots GP-niv et BOT-elo
	return out


## Courbe du graphique du bilan (`summary.power_profile`, révision 1.10) : {power_w, target_w, step_s,
## max_w} (target_w : [] sans cible ; max_w : plus haute valeur, puissance ou cible) ; {} sans courbe
## (au moins deux points).
func power_chart(summary: Dictionary) -> Dictionary:
	var p = summary.get(KEY_POWER_PROFILE, null)
	if not (p is Dictionary) or not (p.get("power_w") is Array) or (p["power_w"] as Array).size() < 2:
		return {}
	var power: Array = []
	for w in p["power_w"]:
		power.append(maxf(float(w), 0.0) if (w is int or w is float) else 0.0)
	var target: Array = []
	if p.get("target_w") is Array and (p["target_w"] as Array).size() == power.size():
		for w in p["target_w"]:
			target.append(float(w) if (w is int or w is float) else null)
	var top := 0.0
	for w in power + target:
		if w != null:
			top = maxf(top, float(w))
	return {"power_w": power, "target_w": target, "step_s": int(p.get("step_s", 1)), "max_w": top}


## Records battus pendant la séance (`summary.segments.passes`, `pr` vrai), du dernier au premier (la vue
## en montre MAX_RECORD_LINES) : {name, time, before} ; `before` : ancien record (`pr_time_s`, révision 1.10) ou
## « premier temps ». names : identifiant du segment → nom (couche `segments` du parcours).
func records_beaten(summary: Dictionary, names: Dictionary = {}) -> Array:
	var segs = summary.get("segments", null)
	if not (segs is Dictionary) or not (segs.get("passes") is Array):
		return []
	var out: Array = []
	var passes: Array = segs["passes"]
	for i in range(passes.size() - 1, -1, -1):
		var p = passes[i]
		if not (p is Dictionary) or not bool(p.get("pr", false)):
			continue
		var sid := str(p.get("segment_id", ""))
		var prev = p.get("pr_time_s", null)
		out.append({"name": str(names.get(sid, sid)) + (" (bonus)" if bool(p.get("with_powerup", false)) else ""),
			"time": SegmentHudModel.time_text(float(p.get("time_s", 0.0)), true),
			"before": ("avant " + SegmentHudModel.time_text(float(prev), true)) if (prev is int or prev is float)
				else "premier temps"})
	return out


## Résultat du test de FTP (`summary.ftp_test`, lot O12) pour le bandeau du bilan : {value, before, delta,
## note, ok} (`value` "" sans FTP calculable, `note` : fiabilité ou avertissements) ; {} sans test.
func ftp_result(summary: Dictionary) -> Dictionary:
	var ftp = summary.get(KEY_FTP_TEST, null)
	if not (ftp is Dictionary):
		return {}
	var warnings: Array[String] = []
	for w in ftp.get("warnings", []):
		warnings.append(str(FTP_WARNINGS.get(str(w), w)))
	var out := {"value": "", "before": "", "delta": "", "ok": bool(ftp.get("reliable", false)),
		"note": ", ".join(warnings) if not warnings.is_empty() else "effort fiable"}
	var now = ftp.get("ftp_w", null)
	if not (now is int or now is float):
		out["note"] = "aucune FTP calculable" + ((" ; " + out["note"]) if not warnings.is_empty() else "")
		return out
	out["value"] = "%d W" % int(round(float(now)))
	var prev = ftp.get("previous_ftp_w", null)
	if prev is int or prev is float:
		out["before"] = "avant %d W" % int(round(float(prev)))
		var d := int(round(float(now))) - int(round(float(prev)))
		out["delta"] = ("+%d W" % d) if d >= 0 else ("−%d W" % -d)
	return out


## Noms des gags du bilan du mode WTF (`summary.wtf.events`), dans l'ordre des règles du core.
const WTF_EVENTS := [["gravity", "Gravité"], ["upside_down", "Monde à l'envers"], ["collapse", "Effondrement"],
	["cheese", "Fromage"], ["micro", "Micro-défis"], ["eggs", "Œufs"], ["tiny", "Tout petit"], ["storm", "Tempête"],
	["camera", "Caméras"], ["chef", "Surprise du chef"]]


## Lignes du bilan du mode « What the fuck » (lot WTF7, `summary.wtf`, maquette « Bilan » du 30 octobre) :
## points, gags joués, Katamari ; pas de records en mode WTF.
func wtf_lines(wtf: Dictionary) -> Array:
	var out: Array = [{"label": "Mode WTF", "value": "%d pts" % int(wtf.get("points", 0)), "unit": ""}]
	var events = wtf.get("events", {})
	var played: Array = []
	if events is Dictionary:
		for e in WTF_EVENTS:
			var n := int(events.get(e[0], 0))
			if n > 0:
				played.append("%s × %d" % [e[1], n])
	out.append({"label": "Gags joués", "value": ", ".join(played) if not played.is_empty() else "aucun", "unit": ""})
	if int(wtf.get("kata_count", 0)) > 0 or float(wtf.get("kata_size", 1.0)) > 1.0:
		out.append({"label": "Katamari", "value": "× %s, %d objets" % [_format_fr_float(float(wtf.get("kata_size", 1.0)), 1),
			int(wtf.get("kata_count", 0))], "unit": ""})
	out.append({"label": "Records", "value": "pas de records en mode WTF", "unit": ""})
	return out


const ROGUE_RESULTS := {"victory": "Victoire", "defeat": "Défaite", "abandoned": "Abandon"}
# Lot R23 : « non vaincu » et non « fui » : une salle ou une phase se finit au bout de sa distance, gagnée ou non.
const ROGUE_BOSS := {"won": "vaincu", "fled": "non vaincu", "not_reached": "non atteint"}
const ROGUE_OBJECTIVES := {"endurance": "Endurance", "threshold": "Seuil", "vo2max": "VO2max"}


## Titre du résultat, commun au bilan de tous les modes (lot RT2, fin commune) : les mêmes mots que le moment
## RÉSULTAT de la séance (feedback_model.gd). {tag, title, sub, tone, extra} ; tone parmi win (or), place (bleu),
## out (rouge), done (or), stop (neutre : séance arrêtée avant l'issue). `extra` : lignes ajoutées sous le titre
## par un autre écran (encart extensible : la ligue d'hiver, lot CH4, y mettra ses points de manche), dans l'ordre.
func result_card(summary: Dictionary, extra: Array = []) -> Dictionary:
	var card := _result_head(summary)
	card["tag"] = FeedbackModel.FAMILIES["resultat"]["tag"]
	card["extra"] = []
	for line in extra:
		if str(line) != "":
			card["extra"].append(str(line))
	return card


func _result_head(summary: Dictionary) -> Dictionary:
	var rogue = summary.get("rogue", null)
	if rogue is Dictionary:   # le verdict (lot R23) dit la cause et le conseil en dessous
		var res := str(rogue.get("result", ""))
		if res == "victory":
			return {"title": "VICTOIRE !", "sub": "Cyber-Rogue", "tone": "win"}
		return {"title": "RUN ARRÊTÉE" if res == "abandoned" else "DÉFAITE", "sub": "Cyber-Rogue",
			"tone": "stop" if res == "abandoned" else "out"}
	var tr = summary.get("track", null)
	if tr is Dictionary:
		var ev := str(tr.get("event", ""))
		var title := str(TrackHudModel.TITLES.get(ev, ev))
		if not bool(tr.get("finished", false)):
			return {"title": "ÉPREUVE NON FINIE", "sub": title, "tone": "stop"}
		return _place_head(tr.get("place", null), tr.get("of", null), title, "ÉPREUVE TERMINÉE")
	var sv = summary.get("survivor", null)
	if sv is Dictionary:
		var place = sv.get("place", null)
		if place == null:
			return {"title": "COURSE NON FINIE", "sub": "Dernier survivant", "tone": "stop"}
		if int(place) == 1:
			return {"title": "VICTOIRE !", "sub": "Dernier survivant · 1er sur %d" % int(sv.get("of", 0)), "tone": "win"}
		return {"title": "ÉLIMINÉ · %s sur %d" % [FeedbackModel.place_text(int(place)), int(sv.get("of", 0))],
			"sub": "Dernier survivant", "tone": "out"}
	var arr = summary.get("arrival", null)
	var gp = summary.get("gp", null)
	if gp is Dictionary:
		var name := "Course" if str(gp.get("mode", "")) == "race" else "Grand Prix des objets"
		if gp.get("finished", true) == false:   # absent : bilan d'avant la révision 1.27, fini à l'arrivée
			return {"title": "COURSE NON FINIE", "sub": name, "tone": "stop"}
		return _place_head(gp.get("place", null), gp.get("of", null), name, "ARRIVÉE")
	if arr is Dictionary and str(arr.get("kind", "")) == "workout":
		return {"title": "ENTRAÎNEMENT TERMINÉ", "sub": "Tous les blocs faits", "tone": "done"}
	if arr is Dictionary:
		var r := FeedbackModel.arrival_result(arr)
		if not r.is_empty():
			return {"title": r["title"], "sub": "Bout du parcours atteint" if str(arr.get("kind", "")) == "route" else r["sub"],
				"tone": r["tone"]}
	if summary.get(KEY_BLOCKS) is Array and not (summary[KEY_BLOCKS] as Array).is_empty():
		return {"title": "ENTRAÎNEMENT ARRÊTÉ", "sub": "Arrêté avant le dernier bloc", "tone": "stop"}
	return {"title": "SÉANCE TERMINÉE", "sub": "", "tone": "done"}


## « VICTOIRE ! » à la 1re place, « ARRIVÉE · 3e sur 8 » sinon, `alone` sans classement.
static func _place_head(place, of, sub: String, alone: String) -> Dictionary:
	if not (place is int or place is float) or not (of is int or of is float) or int(of) < 2:
		return {"title": alone, "sub": sub, "tone": "done"}
	var rr: Array = FeedbackModel.race_result(int(place), int(of))
	return {"title": rr[0], "sub": ("%s · 1er sur %d" % [sub, int(of)]) if int(place) == 1 else sub, "tone": rr[1]}


## Verdict du bilan (lot R23, essai du 15 novembre : « je n'ai pas compris pourquoi la défaite ») : en une phrase,
## le résultat et sa cause, puis ce qu'il fallait faire ; {} pour un bilan sans verdict (modes sans résultat).
## {text, tip, tone}, tone parmi "ok", "warn".
func verdict(summary: Dictionary) -> Dictionary:
	var rogue = summary.get("rogue", null)
	if not (rogue is Dictionary):
		return {}
	var result := str(rogue.get("result", ""))
	if result == "victory":
		return {"text": "Victoire : boss vaincu !", "tip": "", "tone": "ok"}
	var end = rogue.get("end_cause", null)
	var cause := str(end.get("cause", "")) if end is Dictionary else ""
	var phase = end.get("boss_phase", null) if end is Dictionary else null
	var pct = end.get("enemy_pct", null) if end is Dictionary else null
	if result == "abandoned" or cause == "abandoned":
		return {"text": "Run arrêtée avant la fin : pas de victoire possible.", "tip": "", "tone": "warn"}
	if cause == "boss_shield":
		return {"text": "Défaite : ton bouclier est tombé à zéro face au boss%s." % ((" (phase %d)" % int(phase)) if phase != null else ""),
			"tip": "À faire : Z à chaque « Z : PARADE ! », reste devant le Firewall.", "tone": "warn"}
	var left := (" avec encore %d %% de PV" % int(pct)) if pct != null else " avant ses PV"
	return {"text": "Défaite : la phase 3 du boss s'est finie%s au boss." % left,
		"tip": "À faire : tiens ta plage de watts, puis Z à chaque « Z : FRAPPE ! ».",
		"tone": "warn"}


## Lignes du bilan d'une run du Cyber-Rogue (lot R13, `summary.rogue`) : résultat, salles, boss, or, cartes,
## Perfect Shifts et déblocages.
func rogue_lines(rogue: Dictionary) -> Array:
	var out: Array = []
	var obj := str(ROGUE_OBJECTIVES.get(str(rogue.get("objective", "")), rogue.get("objective", "")))
	out.append({"label": "Cyber-Rogue", "value": "%s, %d min" % [obj, int(rogue.get("duration_min", 0))], "unit": ""})
	out.append({"label": "Résultat", "value": str(ROGUE_RESULTS.get(str(rogue.get("result", "")), "—")), "unit": ""})
	out.append({"label": "Salles gagnées", "value": "%d / %d" % [int(rogue.get("rooms_won", 0)), int(rogue.get("rooms_total", 0))], "unit": ""})
	out.append({"label": "Salles non gagnées / sautées", "value": "%d / %d" % [int(rogue.get("rooms_fled", 0)), int(rogue.get("rooms_skipped", 0))], "unit": ""})
	out.append({"label": "Boss", "value": str(ROGUE_BOSS.get(str(rogue.get("boss", "")), "—")), "unit": ""})
	out.append({"label": "Or", "value": str(int(rogue.get("gold", 0))), "unit": ""})
	out.append({"label": "Cartes", "value": str((rogue.get("cards", []) as Array).size()), "unit": ""})
	out.append({"label": "Perfect Shifts", "value": str(int(rogue.get("perfect_shifts", 0))), "unit": ""})
	var unlocks: Array = rogue.get("unlocks", [])
	if not unlocks.is_empty():
		out.append({"label": "Déblocages", "value": ", ".join(PackedStringArray(unlocks)), "unit": ""})
	return out


## En ERG, une ligne par bloc avec écart à la cible en W et en %, et couleur associée.
func blocks(summary: Dictionary) -> Array:
	var raw_blocks = summary.get(KEY_BLOCKS, null)
	if raw_blocks == null or not (raw_blocks is Array):
		return []

	var out: Array = []
	for i in range(raw_blocks.size()):
		var b = raw_blocks[i]
		var idx: int = i + 1
		var avg_raw = null
		var tgt_raw = null

		if b is Array:
			# Format triplet [index, puissance moyenne, cible moyenne ou null]
			if b.size() >= 3:
				idx = int(b[0]) if b[0] != null else idx
				avg_raw = b[1]
				tgt_raw = b[2]
			elif b.size() >= 2:
				avg_raw = b[0]
				tgt_raw = b[1]
		elif b is Dictionary:
			idx = int(b.get("block", b.get("index", i + 1)))
			avg_raw = b.get("avg_power_w", b.get("avg_w", null))
			tgt_raw = b.get("target_w", null)
		else:
			continue

		# Cible null (ancien journal) ou moyenne absente : pas d'écart, couleur neutre.
		if avg_raw == null or tgt_raw == null or float(tgt_raw) <= 0.0:
			out.append({
				"block": idx,
				"index": idx,
				"avg_power_w": float(avg_raw) if avg_raw != null else null,
				"target_w": float(tgt_raw) if tgt_raw != null else null,
				"delta_w": null,
				"delta_pct": null,
				"delta_w_text": "",
				"delta_pct_text": "",
				"color": COLOR_NEUTRAL,
				"couleur": COLOR_NEUTRAL,
			})
			continue

		var avg_w := float(avg_raw)
		var tgt_w := float(tgt_raw)
		var delta_w := avg_w - tgt_w
		var delta_pct := (delta_w / tgt_w) * 100.0

		var abs_pct := absf(delta_pct)
		var color := COLOR_GREEN
		if abs_pct > 10.0:
			color = COLOR_RED
		elif abs_pct > 5.0:
			color = COLOR_ORANGE

		var sign_w := "+" if delta_w >= 0.0 else ""
		var sign_pct := "+" if delta_pct >= 0.0 else ""

		out.append({
			"block": idx,
			"index": idx,
			"avg_power_w": avg_w,
			"target_w": tgt_w,
			"delta_w": delta_w,
			"delta_pct": delta_pct,
			"delta_w_text": "%s%d W" % [sign_w, int(round(delta_w))],
			"delta_pct_text": "%s%s %%" % [sign_pct, _format_fr_float(delta_pct, 1)],
			"color": color,
			"couleur": color,
		})

	return out


## Ligne d'enregistrement FIT : nom de fichier seul, ou "Séance non enregistrée".
func fit_line(summary: Dictionary) -> String:
	var path_val = summary.get(KEY_FIT_PATH, null)
	if path_val == null:
		return "Séance non enregistrée"
	var path_str := str(path_val).strip_edges()
	if path_str == "":
		return "Séance non enregistrée"

	# Extraction du nom seul (compatible séparateurs Unix / et Windows \)
	var norm := path_str.replace("\\", "/")
	var filename := norm.get_file()
	if filename == "":
		return "Séance non enregistrée"

	return "Séance enregistrée : %s" % filename


## Écran au format de menu_model.gd.
func menu_screen() -> Dictionary:
	return {
		"id": "summary",
		"title": "Fin de séance",
		"on_back": "",
		"items": [
			{"id": "replay", "label": "Rejouer", "enabled": true, "detail": "même parcours, même mode"},
			{"id": "new_session", "label": "Menu principal", "enabled": true, "detail": ""},
			{"id": "details", "label": "Voir le bilan détaillé", "enabled": true, "detail": ""},
			{"id": "quit", "label": "Quitter", "enabled": true, "detail": ""}
		]
	}


## Branche cet écran sur une instance de menu_model.gd.
func attach_to_menu(menu: RefCounted) -> void:
	if menu != null and menu.has_method("add_screen"):
		menu.add_screen(menu_screen())
	elif menu != null and "_screens" in menu:
		menu._screens["summary"] = menu_screen()


## Traite une action issue du menu de fin de séance selon les règles de K5.
func handle_action(item_id: String, menu: RefCounted) -> Dictionary:
	match item_id:
		"new_session":   # « Menu principal » (15 novembre : « Nouvelle séance » ne disait pas qu'il ramène à l'accueil)
			if menu != null and menu.has_method("reset"):
				menu.reset()
			return {"action": "new_session"}
		"replay":        # même parcours, même mode et mêmes choix : écran Prêt, l'accueil derrière lui
			if menu != null and menu.has_method("replay"):
				menu.replay()
			return {"action": "new_session"}
		"details":
			return {"action": "details"}
		"quit":
			if menu != null and menu.has_method("confirm"):
				menu.confirm("Quitter OpenRide ?", {"action": "quit"})
			elif menu != null and menu.has_method("_confirm"):
				menu._confirm("Quitter OpenRide ?", {"action": "quit"})
			return {}
	return {}
