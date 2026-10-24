extends RefCounted

## Modèle de vue du HUD de séance (Lot K2, SRS §8 « HUD de base », Contrat IPC v1 §3).
##
## Calcule les textes affichés (puissance, vitesse, cadence, cardio, braquet, pente, distance, temps),
## le profil d'altitude autour du cycliste et la prochaine montée, sans aucun nœud Godot.
## Le lot E3 n'a plus qu'à dessiner ce que ce modèle renvoie.
## Pas de class_name : charger par preload("res://scripts/hud_view_model.gd").
##
## Lissage : la puissance affichée est `power_3s` (moyenne sur 3 s calculée par le core) ; les autres
## valeurs sont affichées telles que reçues, le core les envoyant déjà filtrées à 30 Hz.
## Valeur absente, nulle ou non finie (NaN, infini) : « — ». Valeur négative là où elle n'a pas de sens
## (vitesse, cadence, puissance) : 0. Valeur hors des bornes plausibles ci-dessous : « — ».

const NO_VALUE := "—"

# Bornes plausibles de l'affichage (au-delà : « — »).
const MAX_POWER_W := 5000.0
const MAX_SPEED_KMH := 200.0
const MAX_CADENCE_RPM := 300.0
const MAX_HR_BPM := 300.0
const MAX_GRADE_PCT := 60.0
const MAX_DISTANCE_M := 1.0e8
const MAX_ELAPSED_S := 1.0e7

# Classes de pente du profil (pente réelle en %), bornes basses incluses.
const GRADE_DESCENT_BELOW := -2.0   # < −2 % : descent
const GRADE_CLIMB_FROM := 2.0       # [−2 ; 2[ : flat ; [2 ; 6[ : climb
const GRADE_STEEP_FROM := 6.0       # [6 ; 10] : steep
const GRADE_WALL_ABOVE := 10.0      # > 10 % : wall

# Détection des montées (next_climb) : pas d'analyse, pente de début de montée et replat toléré.
const CLIMB_STEP_M := 10.0
const CLIMB_START_PCT := 2.0
const CLIMB_MAX_DIP_M := 50.0

var _has_state: bool = false
var _state_time_s: float = 0.0
var _raw: Dictionary = {}
# Distance parcourue : le core envoie `s` cumulé (une boucle ne le remet pas à zéro) ; si `s` repart
# quand même en arrière de plus d'une demi-longueur sur une boucle, un tour est ajouté.
var _laps: int = 0
var _last_s: float = NAN


static func _finite(value: Variant) -> bool:
	if typeof(value) != TYPE_INT and typeof(value) != TYPE_FLOAT:
		return false
	return is_finite(float(value))


## Nombre fini dans [lo, hi] (négatif ramené à 0 si clamp_negative), sinon NAN.
static func _clean(value: Variant, hi: float, clamp_negative := true) -> float:
	if not _finite(value):
		return NAN
	var f := float(value)
	if clamp_negative and f < 0.0:
		f = 0.0
	if absf(f) > hi:
		return NAN
	return f


static func format_hms(seconds: float) -> String:
	if not is_finite(seconds) or seconds < 0.0 or seconds > MAX_ELAPSED_S:
		return NO_VALUE
	var sec := int(floor(seconds + 1e-6))
	return "%d:%02d:%02d" % [sec / 3600, (sec / 60) % 60, sec % 60]


## Pente avec signe et une décimale ; −0,04 s'affiche « 0.0 % » (pas de « -0.0 »).
static func format_grade(grade: float) -> String:
	if is_nan(grade):
		return NO_VALUE
	var r := snappedf(grade, 0.1)
	if absf(r) < 0.05:
		return "0.0 %"
	return ("+%.1f %%" if r > 0.0 else "%.1f %%") % r


static func grade_class(grade: float) -> String:
	if grade < GRADE_DESCENT_BELOW:
		return "descent"
	if grade < GRADE_CLIMB_FROM:
		return "flat"
	if grade < GRADE_STEEP_FROM:
		return "climb"
	if grade <= GRADE_WALL_ABOVE:
		return "steep"
	return "wall"


func reset() -> void:
	_has_state = false
	_state_time_s = 0.0
	_raw = {}
	_laps = 0
	_last_s = NAN


## Enregistre une trame `state` (contrat IPC §3) reçue à l'instant `now_s`.
func on_state(state: Dictionary, now_s: float) -> void:
	var length := _clean(state.get("route_length_m", null), MAX_DISTANCE_M)
	var s_now := _clean(state.get("s", null), MAX_DISTANCE_M)
	if not is_nan(s_now) and not is_nan(_last_s) and not is_nan(length) and length > 0.0 \
			and s_now < _last_s - length * 0.5:
		_laps += 1
	if not is_nan(s_now):
		_last_s = s_now
	var gears_total = state.get("gears_total", 24)
	var gear = state.get("gear", null)
	var hr := _clean(state.get("hr", null), MAX_HR_BPM)
	if hr == 0.0:
		hr = NAN
	_raw = {
		"power_w": _clean(state.get("power_3s", state.get("power", null)), MAX_POWER_W),
		"speed_kmh": _clean(float(state.get("v", NAN)) * 3.6 if _finite(state.get("v", null)) else NAN, MAX_SPEED_KMH),
		"cadence_rpm": _clean(state.get("cadence", null), MAX_CADENCE_RPM),
		"hr_bpm": hr,
		"gear": int(gear) if _finite(gear) else -1,
		"gears_total": int(gears_total) if _finite(gears_total) and int(gears_total) > 0 else 24,
		"grade_pct": _clean(state.get("grade", null), MAX_GRADE_PCT, false),
		"distance_m": NAN if is_nan(s_now) else s_now + _laps * (length if not is_nan(length) else 0.0),
		"elapsed_s": _clean(state.get("t", null), MAX_ELAPSED_S),
	}
	_has_state = true
	_state_time_s = now_s


## Textes et valeurs brutes du HUD à l'instant de rendu `now_s`. `age_s` : âge de la dernière trame.
func evaluate(now_s: float) -> Dictionary:
	var r := _raw
	if not _has_state:
		r = {"power_w": NAN, "speed_kmh": NAN, "cadence_rpm": NAN, "hr_bpm": NAN, "gear": -1,
			"gears_total": 24, "grade_pct": NAN, "distance_m": NAN, "elapsed_s": NAN}
	var out := r.duplicate()
	out["has_state"] = _has_state
	out["age_s"] = now_s - _state_time_s if _has_state else INF
	out["power_text"] = NO_VALUE if is_nan(r["power_w"]) else "%d W" % int(round(r["power_w"]))
	out["speed_text"] = NO_VALUE if is_nan(r["speed_kmh"]) else "%.1f km/h" % r["speed_kmh"]
	out["cadence_text"] = NO_VALUE if is_nan(r["cadence_rpm"]) else "%d rpm" % int(round(r["cadence_rpm"]))
	out["hr_text"] = NO_VALUE if is_nan(r["hr_bpm"]) else "%d bpm" % int(round(r["hr_bpm"]))
	var g: int = r["gear"]
	out["gear_text"] = "%d/%d" % [g, r["gears_total"]] if g >= 1 and g <= r["gears_total"] else NO_VALUE
	out["grade_text"] = format_grade(r["grade_pct"])
	out["distance_text"] = NO_VALUE if is_nan(r["distance_m"]) else "%.2f km" % (r["distance_m"] / 1000.0)
	out["elapsed_text"] = format_hms(r["elapsed_s"])
	return out


## Altitude et pente à une position déjà ramenée par wrap_s : même interpolation linéaire que
## route_data.sample(), sans le calcul de position (Catmull-Rom) inutile ici. Calcul en float 64 bits.
static func _alt_grade(route, pos: float) -> Array:
	var seg: Array = route._segment(pos)
	var i: int = seg[0]
	var u: float = seg[1]
	return [route.alt_m[i] + (route.alt_m[i + 1] - route.alt_m[i]) * u,
		route.grade_pct[i] + (route.grade_pct[i + 1] - route.grade_pct[i]) * u]


## Profil d'altitude de `behind_m` derrière à `ahead_m` devant la position `s`, sur `columns` colonnes.
## Boucle : la fenêtre traverse l'arrivée (positions ramenées par wrap_s). Parcours ouvert : la fenêtre
## est tronquée à [0, longueur], sans valeur inventée, et les colonnes couvrent la partie restante.
## Renvoie points (Vector2(distance relative en m, altitude en m)), s_abs (positions sur la route),
## alts (altitudes en float 64 bits), grades, grade_class, marker_index, alt_min, alt_max (marge de 5 %).
func profile(route, s: float, behind_m := 500.0, ahead_m := 4500.0, columns := 120) -> Dictionary:
	var out := {"points": PackedVector2Array(), "s_abs": PackedFloat64Array(), "alts": PackedFloat64Array(),
		"grades": PackedFloat64Array(), "grade_class": PackedStringArray(), "marker_index": -1,
		"alt_min": 0.0, "alt_max": 0.0, "from_m": 0.0, "to_m": 0.0}
	if route == null or route.n < 2 or columns < 2 or not is_finite(s):
		return out
	var here: float = route.wrap_s(s)
	var from_rel := -maxf(0.0, behind_m)
	var to_rel := maxf(0.0, ahead_m)
	if not route.is_loop():
		from_rel = maxf(from_rel, -here)
		to_rel = minf(to_rel, route.length_m - here)
	out["from_m"] = from_rel
	out["to_m"] = to_rel
	var span := to_rel - from_rel
	var step := span / float(columns - 1)
	var lo := INF
	var hi := -INF
	var best := INF
	for c in range(columns):
		var rel := from_rel + step * c
		var pos: float = route.wrap_s(here + rel)
		var ag := _alt_grade(route, pos)
		var alt: float = ag[0]
		var gr: float = ag[1]
		out["points"].append(Vector2(rel, alt))
		out["s_abs"].append(pos)
		out["alts"].append(alt)
		out["grades"].append(gr)
		out["grade_class"].append(grade_class(gr))
		lo = minf(lo, alt)
		hi = maxf(hi, alt)
		if absf(rel) < best:
			best = absf(rel)
			out["marker_index"] = c
	var margin := maxf(hi - lo, 1.0) * 0.05
	out["alt_min"] = lo - margin
	out["alt_max"] = hi + margin
	return out


## Prochaine montée devant `s` : au moins `min_length_m` de long et `min_grade_pct` de pente moyenne.
## Une montée commence quand la pente sur CLIMB_STEP_M atteint CLIMB_START_PCT et finit au premier replat
## (ou descente) de plus de CLIMB_MAX_DIP_M. Si `s` est dans une montée, renvoie ce qu'il en reste
## (start_m = 0, in_progress = vrai). Recherche jusqu'à la fin (parcours ouvert) ou sur un tour (boucle).
## Renvoie {start_m, length_m, avg_grade_pct, gain_m, in_progress} ou {} s'il n'y en a pas.
func next_climb(route, s: float, min_length_m := 300.0, min_grade_pct := 3.0) -> Dictionary:
	if route == null or route.n < 2 or not is_finite(s):
		return {}
	var here: float = route.wrap_s(s)
	var horizon: float = route.length_m if route.is_loop() else route.length_m - here
	var steps := int(floor(horizon / CLIMB_STEP_M))
	var start := -1.0
	var last_up := -1.0     # fin du dernier pas montant de la montée en cours
	var d := 0.0
	for k in range(steps + 1):
		d = minf(k * CLIMB_STEP_M, horizon)
		var d2 := minf(d + CLIMB_STEP_M, horizon)
		var ended := k == steps or d2 <= d
		var up := false
		if not ended:
			var a0: float = _alt_grade(route, route.wrap_s(here + d))[0]
			var a1: float = _alt_grade(route, route.wrap_s(here + d2))[0]
			up = (a1 - a0) / (d2 - d) * 100.0 >= CLIMB_START_PCT
		if up:
			if start < 0.0:
				start = d
			last_up = d2
		if start >= 0.0 and (ended or (not up and d - last_up >= CLIMB_MAX_DIP_M)):
			var res := _climb(route, here, start, last_up, min_length_m, min_grade_pct)
			if not res.is_empty():
				return res
			start = -1.0
			last_up = -1.0
		if ended:
			break
	return {}


func _climb(route, here: float, start: float, end: float, min_length_m: float, min_grade_pct: float) -> Dictionary:
	var length := end - start
	if length <= 0.0:
		return {}
	var a0: float = _alt_grade(route, route.wrap_s(here + start))[0]
	var a1: float = _alt_grade(route, route.wrap_s(here + end))[0]
	var avg := (a1 - a0) / length * 100.0
	if length < min_length_m or avg < min_grade_pct:
		return {}
	return {"start_m": start, "length_m": length, "avg_grade_pct": avg, "gain_m": a1 - a0,
		"in_progress": start == 0.0}
