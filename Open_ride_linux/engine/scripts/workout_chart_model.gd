extends RefCounted

## Courbes de la séance façon GoldenCheetah (lot O13) : modèle sans affichage, testé sans écran.
##
## Profil des watts cibles de toute la séance (polygones colorés par zone de Coggan, mêmes seuils
## que `erg_view.gd` et `openride-core summary`) et, par-dessus, les courbes de la puissance, de la
## fréquence cardiaque et de la cadence, échantillonnées à une valeur par seconde de séance.
## Le dessin est le lot O14 : il appelle `push()` à chaque trame `state` puis `geometry(w, h)`.
##
## - `set_workout(profile, ftp_w, duration_s)` : triplets du contrat `[durée_s, fraction début,
##   fraction fin]` (une case sans fraction est ignorée : pas de roue libre en ERG, lot O19) ; `set_workout_w(profile_w, duration_s)` : même
##   forme en watts absolus (`.erg` du lot O9), zones calculées avec `set_ftp()` ;
##   sans profil : parcours libre, fenêtre des 10 dernières minutes.
## - `push(t_s, power_w, hr_bpm, cadence_rpm, target_w)` : `t_s` = temps de séance (hors pauses).
##   Une trame dont le temps n'avance pas (pause) est ignorée. Valeur absente (`null`, FC ≤ 0) :
##   trou, jamais zéro. Coût O(1).
## - `geometry(w, h)` : recalculée au plus une fois par seconde de séance (ou si la taille ou le
##   lissage change), sinon le dernier résultat est rendu.
## Pas de class_name : charger par preload("res://scripts/workout_chart_model.gd").

const ErgView := preload("res://scripts/erg_view.gd")

const SERIES := ["power", "hr", "cadence", "target"]
const FREE_WINDOW_S := 600.0          # parcours libre : 10 dernières minutes
const MAX_DRAWN_POINTS := 1800        # au-delà, regroupement par 2, 4, 8…
const SMOOTHING_CHOICES := [0, 3, 10] # brut, 3 s, 10 s (moyenne glissante)
const HR_MIN := 60.0
const HR_MAX_DEFAULT := 190.0
const CADENCE_MAX := 140.0
const WATTS_ROUND := 50.0
## Moyennes par groupes de 2, 4… 64 secondes tenues à jour à chaque seconde : la géométrie d'une
## longue séance lit ces groupes au lieu de reparcourir chaque seconde (critère des 5 ms).
const LEVELS := [2, 4, 8, 16, 32, 64]

var ftp_w := 0.0
var duration_s := 0.0
## Segments du profil en watts : {t0, t1, w0, w1}.
var segments: Array = []
var has_profile := false
var smoothing_s := 0

## Valeurs brutes par seconde (NAN = trou), une entrée par seconde terminée, par série.
var _raw := {}
var _sums := {}
var _counts := {}
var _cur_sec := -1
var _last_t := -INF
var _max := {}
var _cache: Dictionary = {}
var _cache_key := ""
## Par série : {facteur: Array des moyennes de groupes complets} et accumulateurs du groupe en cours.
var _levels := {}
var _lsum := {}
var _lcnt := {}
var _lfill := {}


func _init() -> void:
	reset()


func reset() -> void:
	_raw = {}
	_sums = {}
	_counts = {}
	_max = {}
	_levels = {}
	_lsum = {}
	_lcnt = {}
	_lfill = {}
	for s in SERIES:
		_raw[s] = []   # Array (référence) : un tableau compact rangé dans un Dictionary serait copié
		_levels[s] = {}
		_lsum[s] = {}
		_lcnt[s] = {}
		_lfill[s] = {}
		for f in LEVELS:
			_levels[s][f] = []
			_lsum[s][f] = 0.0
			_lcnt[s][f] = 0
			_lfill[s][f] = 0
		_sums[s] = 0.0
		_counts[s] = 0
		_max[s] = 0.0
	_cur_sec = -1
	_last_t = -INF
	_cache = {}
	_cache_key = ""


func set_ftp(value_w: float) -> void:
	ftp_w = maxf(0.0, value_w)
	_cache_key = ""


## Profil du contrat (fractions de FTP).
func set_workout(profile: Array, ftp: float, total_s: float) -> void:
	set_ftp(ftp)
	_set_segments(profile, ftp, total_s)


## Profil en watts absolus (`.erg`, lot O9) ; les zones se calculent avec la FTP de `set_ftp()`.
func set_workout_w(profile_w: Array, total_s: float) -> void:
	_set_segments(profile_w, 1.0, total_s)


func clear_workout() -> void:
	segments = []
	has_profile = false
	duration_s = 0.0
	_cache_key = ""


func _set_segments(profile: Array, scale: float, total_s: float) -> void:
	segments = []
	var t := 0.0
	for item in profile:
		if typeof(item) != TYPE_ARRAY or item.size() < 3 or item[1] == null or item[2] == null:
			continue
		var dur := maxf(0.0, float(item[0]))
		if dur <= 0.0:
			continue
		segments.append({"t0": t, "t1": t + dur, "w0": float(item[1]) * scale, "w1": float(item[2]) * scale})
		t += dur
	duration_s = maxf(t, total_s)
	has_profile = not segments.is_empty()
	_cache_key = ""


func set_smoothing(seconds: int) -> void:
	smoothing_s = seconds if seconds in SMOOTHING_CHOICES else 0
	_cache_key = ""


# --- échantillonnage ------------------------------------------------------------------------

static func _valid(series: String, v: Variant) -> bool:
	if v == null:
		return false
	var f := float(v)
	if is_nan(f) or is_inf(f):
		return false
	if series == "hr":
		return f > 0.0
	return f >= 0.0


func push(t_s: float, power_w: Variant, hr_bpm: Variant, cadence_rpm: Variant, target_w: Variant) -> void:
	if t_s <= _last_t or t_s < 0.0:
		return   # pause (temps figé) ou trame en retard : rien n'est ajouté
	_last_t = t_s
	var sec := int(floor(t_s))
	if _cur_sec < 0:
		_cur_sec = sec
		for s in SERIES:
			for _i in range(sec):
				_append_raw(s, NAN)   # séance reprise en cours : trous jusqu'ici
	elif sec > _cur_sec:
		_close_second()
		for s in SERIES:
			for _i in range(sec - _cur_sec - 1):
				_append_raw(s, NAN)   # seconde sans trame : trou
		_cur_sec = sec
	var frame := {"power": power_w, "hr": hr_bpm, "cadence": cadence_rpm, "target": target_w}
	for s in SERIES:
		if _valid(s, frame[s]):
			_sums[s] += float(frame[s])
			_counts[s] += 1


func _close_second() -> void:
	for s in SERIES:
		var v := NAN
		if _counts[s] > 0:
			v = _sums[s] / float(_counts[s])
			_max[s] = maxf(_max[s], v)
		_append_raw(s, v)
		_sums[s] = 0.0
		_counts[s] = 0


func _append_raw(s: String, v: float) -> void:
	_raw[s].append(v)
	var sums: Dictionary = _lsum[s]
	var cnts: Dictionary = _lcnt[s]
	var fills: Dictionary = _lfill[s]
	for f in LEVELS:
		if not is_nan(v):
			sums[f] += v
			cnts[f] += 1
		fills[f] += 1
		if fills[f] == f:
			_levels[s][f].append(NAN if cnts[f] == 0 else sums[f] / float(cnts[f]))
			sums[f] = 0.0
			cnts[f] = 0
			fills[f] = 0


## Moyennes par groupes de `f` secondes à partir de `start` (multiple de `f`) jusqu'à `stop`,
## lues dans les groupes tenus à jour ; le dernier groupe incomplet est calculé ici.
func _grouped(series: String, f: int, start: int, stop: int) -> PackedFloat32Array:
	var full: Array = _levels[series][f]
	var g0 := start / f
	var g1 := mini(full.size(), stop / f)
	var out := PackedFloat32Array(full.slice(g0, g1)) if g0 < g1 else PackedFloat32Array()
	var tail_start := maxi(start, g1 * f)
	if tail_start < stop:
		var sum := 0.0
		var cnt := 0
		for i in range(tail_start, stop):
			var v := value_at(series, i)
			if not is_nan(v):
				sum += v
				cnt += 1
		out.append(NAN if cnt == 0 else sum / float(cnt))
	return out


## Nombre de points (secondes), seconde en cours comprise.
func point_count() -> int:
	return _raw["power"].size() + (1 if _cur_sec >= 0 else 0)


## Valeur brute de la seconde `i` (seconde en cours : moyenne partielle) ; NAN = trou.
func value_at(series: String, i: int) -> float:
	var arr: Array = _raw[series]
	if i >= 0 and i < arr.size():
		return arr[i]
	if i == arr.size() and _cur_sec >= 0 and _counts[series] > 0:
		return _sums[series] / float(_counts[series])
	return NAN


## Valeurs brutes de toute la séance (copie), seconde en cours comprise.
func values(series: String) -> PackedFloat32Array:
	var out := PackedFloat32Array(_raw[series])
	if _cur_sec >= 0:
		out.append(value_at(series, out.size()))
	return out


## Valeurs lissées (moyenne glissante des `seconds` dernières secondes, trous ignorés ; un trou
## reste un trou). `seconds` ≤ 1 : valeurs brutes.
func smoothed(series: String, seconds: int, from_i: int = 0, to_i: int = -1) -> PackedFloat32Array:
	var n := point_count()
	var stop := n if to_i < 0 else mini(to_i, n)
	var start := clampi(from_i, 0, stop)
	var first := start if seconds <= 1 else maxi(0, start - seconds + 1)
	var src := _slice(series, first, stop)
	if seconds <= 1:
		return src
	var out := PackedFloat32Array()
	out.resize(stop - start)
	var sum := 0.0
	var cnt := 0
	var offset := start - first
	for k in range(src.size()):
		var v := src[k]
		if not is_nan(v):
			sum += v
			cnt += 1
		if k >= seconds:
			var old := src[k - seconds]
			if not is_nan(old):
				sum -= old
				cnt -= 1
		if k >= offset:
			out[k - offset] = NAN if (is_nan(v) or cnt == 0) else sum / float(cnt)
	return out


## Valeurs brutes des secondes [a, b[, seconde en cours comprise, sans appel par élément.
func _slice(series: String, a: int, b: int) -> PackedFloat32Array:
	var arr: Array = _raw[series]
	var closed := mini(b, arr.size())
	var out := PackedFloat32Array(arr.slice(a, closed)) if a < closed else PackedFloat32Array()
	if b > arr.size() and a <= arr.size() and _cur_sec >= 0:
		out.append(value_at(series, arr.size()))
	return out


func current_values() -> Dictionary:
	var i := point_count() - 1
	var out := {}
	for s in SERIES:
		var v := value_at(s, i) if i >= 0 else NAN
		out[s] = null if is_nan(v) else v
	return out


# --- échelles --------------------------------------------------------------------------------

func target_max_w() -> float:
	var m := 0.0
	for seg in segments:
		m = maxf(m, maxf(float(seg["w0"]), float(seg["w1"])))
	return m


func scales() -> Dictionary:
	var power_max := maxf(_max["power"], value_at("power", point_count() - 1) if point_count() > 0 else 0.0)
	var target_max := maxf(target_max_w(), _max["target"])
	var w_top := maxf(maxf(1.5 * ftp_w, target_max * 1.1), power_max * 1.05)
	w_top = maxf(WATTS_ROUND, ceilf(w_top / WATTS_ROUND - 1e-6) * WATTS_ROUND)
	var hr_cur := value_at("hr", point_count() - 1) if point_count() > 0 else NAN
	var hr_top := maxf(HR_MAX_DEFAULT, maxf(_max["hr"], 0.0 if is_nan(hr_cur) else hr_cur))
	return {
		"watts": [0.0, w_top], "hr": [HR_MIN, ceilf(hr_top)], "cadence": [0.0, CADENCE_MAX],
		"watts_ticks": nice_ticks(0.0, w_top), "hr_ticks": nice_ticks(HR_MIN, ceilf(hr_top)),
		"cadence_ticks": nice_ticks(0.0, CADENCE_MAX),
	}


## Graduations « jolies » (pas de 1, 2 ou 5 × 10ⁿ) entre `lo` et `hi`, au plus `max_ticks` + 1.
static func nice_ticks(lo: float, hi: float, max_ticks: int = 5) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	if hi <= lo or max_ticks < 1:
		return out
	var raw := (hi - lo) / float(max_ticks)
	var mag := pow(10.0, floor(log(raw) / log(10.0)))
	var step := mag
	for m in [1.0, 2.0, 5.0, 10.0]:
		if m * mag >= raw - 1e-9:
			step = m * mag
			break
	var v := ceilf(lo / step - 1e-9) * step + 0.0   # + 0.0 : -0.0 devient 0.0 (Godot 4.7 compare les tableaux bit à bit)
	while v <= hi + 1e-6:
		out.append(v)
		v += step
	return out


static func zone_of_w(w: float, ftp: float) -> int:
	return ErgView.zone_of_frac(w / ftp) if ftp > 0.0 else -1


static func zone_color_w(w: float, ftp: float) -> Color:
	if ftp <= 0.0:
		return ErgView.NEUTRAL_COLOR
	return ErgView.zone_color(w / ftp)


# --- géométrie ---------------------------------------------------------------------------------

## Fenêtre de temps affichée [début, fin] en secondes de séance.
func time_window() -> Vector2:
	var elapsed := float(point_count())
	if has_profile:
		return Vector2(0.0, maxf(duration_s, elapsed))
	var end := maxf(FREE_WINDOW_S, elapsed)
	return Vector2(end - FREE_WINDOW_S, end)


## Facteur de regroupement (1, 2, 4…) pour dessiner au plus MAX_DRAWN_POINTS points.
static func group_factor(n: int) -> int:
	var f := 1
	while (n + f - 1) / f > MAX_DRAWN_POINTS:
		f *= 2
	return f


func geometry(w: float, h: float) -> Dictionary:
	var key := "%d|%.1f|%.1f|%d|%.1f|%d" % [point_count(), w, h, smoothing_s, ftp_w, segments.size()]
	if key == _cache_key:
		return _cache
	_cache_key = key
	_cache = _compute(w, h)
	return _cache


func _compute(w: float, h: float) -> Dictionary:
	var win := time_window()
	var span := maxf(1.0, win.y - win.x)
	var sc := scales()
	var w_top: float = sc["watts"][1]
	var hr_lo: float = sc["hr"][0]
	var hr_hi: float = sc["hr"][1]
	var out := {
		"size": Vector2(w, h), "window": win, "scales": sc,
		"profile": _profile_polygons(w, h, win, span, w_top),
		"cursor_x": clampf((float(point_count()) - win.x) / span, 0.0, 1.0) * w,
		"current": current_values(),
		"group": 1,
	}
	var start := maxi(0, int(floor(win.x)))
	var stop := point_count()
	var f := group_factor(maxi(0, stop - start))
	out["group"] = f
	var curves := {}
	var fast := f > 1 and smoothing_s <= 1 and start % f == 0 and f in LEVELS
	for s in ["power", "hr", "cadence"]:
		var vals := _grouped(s, f, start, stop) if fast else smoothed(s, smoothing_s, start, stop)
		var lo := 0.0
		var hi := w_top
		if s == "hr":
			lo = hr_lo
			hi = hr_hi
		elif s == "cadence":
			hi = CADENCE_MAX
		if fast:
			curves[s] = _polylines(vals, start, 1, w, h, win.x, span, lo, hi, f)
		else:
			curves[s] = _polylines(vals, start, f, w, h, win.x, span, lo, hi)
	out["curves"] = curves
	return out


## Polylignes coupées aux trous ; chaque point = moyenne d'un groupe de `f` valeurs, chaque
## valeur couvrant `per_value` secondes (1, ou la taille des groupes déjà moyennés).
static func _polylines(vals: PackedFloat32Array, start: int, f: int, w: float, h: float,
		t0: float, span: float, lo: float, hi: float, per_value: int = 1) -> Array:
	var lines: Array = []
	var cur := PackedVector2Array()
	var n := vals.size()
	var range_v := maxf(1e-6, hi - lo)
	var i := 0
	while i < n:
		var sum := 0.0
		var cnt := 0
		var j_end := mini(n, i + f)
		for j in range(i, j_end):
			var v := vals[j]
			if not is_nan(v):
				sum += v
				cnt += 1
		if cnt == 0:
			if cur.size() > 0:
				lines.append(cur)
				cur = PackedVector2Array()
		else:
			var t := float(start) + (float(i) + 0.5 * float(j_end - i)) * float(per_value)
			var x := (t - t0) / span * w
			var y := h - clampf((sum / float(cnt) - lo) / range_v, 0.0, 1.0) * h
			cur.append(Vector2(x, y))
		i = j_end
	if cur.size() > 0:
		lines.append(cur)
	return lines


## Polygones du profil cible : une marche par bloc, les rampes coupées aux seuils des zones pour
## que chaque morceau ait la couleur de sa zone.
func _profile_polygons(w: float, h: float, win: Vector2, span: float, w_top: float) -> Array:
	var out: Array = []
	for seg in segments:
		var t0: float = seg["t0"]
		var t1: float = seg["t1"]
		var w0: float = seg["w0"]
		var w1: float = seg["w1"]
		var cuts: Array = [0.0, 1.0]
		if ftp_w > 0.0 and w0 != w1:
			for pct in ErgView.ZONE_HIGH_PCT:
				var b := float(pct) / 100.0 * ftp_w
				var u := (b - w0) / (w1 - w0)
				if u > 0.0 and u < 1.0:
					cuts.append(u)
		cuts.sort()
		for k in range(cuts.size() - 1):
			var ua: float = cuts[k]
			var ub: float = cuts[k + 1]
			if ub - ua <= 1e-9:
				continue
			var wa := lerpf(w0, w1, ua)
			var wb := lerpf(w0, w1, ub)
			out.append(_poly(lerpf(t0, t1, ua), lerpf(t0, t1, ub), wa, wb, 0.5 * (wa + wb), w, h, win, span, w_top))
	return out


func _poly(ta: float, tb: float, wa: float, wb: float, mid_w: float, w: float, h: float,
		win: Vector2, span: float, w_top: float) -> Dictionary:
	var xa := (ta - win.x) / span * w
	var xb := (tb - win.x) / span * w
	var ya := h - clampf(wa / w_top, 0.0, 1.0) * h
	var yb := h - clampf(wb / w_top, 0.0, 1.0) * h
	return {
		"polygon": PackedVector2Array([Vector2(xa, h), Vector2(xa, ya), Vector2(xb, yb), Vector2(xb, h)]),
		"t0": ta, "t1": tb, "w0": wa, "w1": wb,
		"zone": zone_of_w(mid_w, ftp_w),
		"color": zone_color_w(mid_w, ftp_w),
	}
