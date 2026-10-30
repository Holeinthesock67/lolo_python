extends RefCounted

## Modèle sonore sans affichage : vent, roue libre et points d'intérêt spatialisés
## (Lot L5, revu par le Lot P10 ; SRS §8 « Audio », Contrat IPC v1 §3, Format .world v1 §8), sans aucun nœud Godot.
## Pas de class_name : charger par preload("res://scripts/sound_model.gd").
##
## Constantes de comportement :
## - `SILENCE_DB = -80.0` : volume de silence (à l'arrêt ou en pause, sans lissage en pause).
## - Vent (Lot P10, baissé après la recette P16) : il suit la vitesse dans l'air `va = v + wind.head_mps`
##   (bornée à 0), selon `WIND_MAX_DB + 20 × WIND_LOG_K × log10(va / WIND_MAX_KMH)` dB, entre
##   `WIND_MIN_MOVING_DB = -60.0` et `WIND_MAX_DB = -12.0` (plafond à `WIND_MAX_KMH = 60.0` km/h dans
##   l'air) : à 10 km/h, -43 dB, à peine audible ; à 30 km/h, -24 dB ; à 50 km/h, -15 dB. Hauteur
##   (`pitch`) de `WIND_PITCH_MIN = 0.85` à `WIND_PITCH_MAX = 1.15`, linéaire en `va`. La rafale
##   `wind.gust` (0 à 1) module le volume de
##   ± `GUST_DB = 3.0` dB et la hauteur de ± `GUST_PITCH = 0.05`, sur une période de `GUST_PERIOD_S`.
##   Sans objet `wind` depuis `WIND_TIMEOUT_S = 2.0` s (2 envois par seconde), vent coupé.
## - `FREEWHEEL_MIN_KMH = 5.0` : vitesse minimale d'activation de la roue libre.
## - `FREEWHEEL_DELAY_S = 0.5` : durée minimale sans pédaler avant roue libre. Avec un champ `cadence`
##   numérique, c'est la cadence qui décide (0 tr/min : roue libre possible, au-dessus de
##   `FREEWHEEL_STOP_CADENCE_RPM = 20.0` : reprise), car un capteur de puissance traîne ; sans
##   cadence, la puissance (0 W ou absente : roue libre possible, au-dessus de
##   `FREEWHEEL_STOP_POWER_W = 10.0` : reprise), comme en L5.
## - Cliquetis : `clicks_per_s = v / WHEEL_CIRCUMFERENCE_M × ENGAGEMENT_POINTS` (roue de 2,1 m,
##   36 points : 171 coups par seconde à 36 km/h) ; volume de `FREEWHEEL_MIN_DB = -24.0` à 5 km/h à
##   `FREEWHEEL_MAX_DB = -16.0` à `FREEWHEEL_LOUD_KMH = 40.0` km/h (baissé après la recette P16).
## - Reprise du pédalage pendant la roue libre : `freewheel.clac` vrai pour une seule évaluation.
## - Roues (lot V7) : `set_wheel_kind("hum" | "whistle" | "none")` (equipment_meshes.gd wheel_sound). Un
##   ronronnement grave (roue lenticulaire) ou un sifflement léger (jantes hautes) naît à `WHEEL_MIN_KMH = 20.0`
##   à `WHEEL_MIN_DB = -40.0` et monte à `WHEEL_MAX_DB = -26.0` à `WHEEL_LOUD_KMH = 50.0` km/h ; hauteur de
##   `WHEEL_PITCH_MIN = 0.8` à `WHEEL_PITCH_MAX = 1.3`, linéaire en vitesse. Silence en pause et sans roue sonore.
## - Gravier (lot U22, option « gravel ») : `set_surface("paved" | "compacted" | "gravel" | "dirt")` (surface
##   effective sous le cycliste, world_streamer.surface_at). Crissement de `GRAVEL_MIN_DB = -36.0` à
##   `GRAVEL_MIN_KMH = 5.0` km/h jusqu'à `GRAVEL_MAX_DB = -18.0` à `GRAVEL_LOUD_KMH = 35.0` km/h, `COMPACTED_DB = -6.0`
##   dB plus bas sur `compacted` ; hauteur de `GRAVEL_PITCH_MIN = 0.8` à `GRAVEL_PITCH_MAX = 1.25`. Silence sur
##   le bitume, à l'arrêt et en pause ; changement de surface adouci par `SLEW_RATE_DB_PER_S`.
## - `HYSTERESIS_EXIT_FACTOR = 1.1` : un POI entre à `radius_m` et sort à `1,1 × radius_m`.
## - `SLEW_RATE_DB_PER_S = 12.0` : variation maximale de tout volume (12 dB/s, soit 1,2 dB pour 0,1 s).
## - `MAX_POI_SOURCES = 4` : nombre maximal de points d'intérêt audibles simultanément (les plus proches).

const SILENCE_DB := -80.0
const WIND_MAX_KMH := 60.0
const WIND_LOG_K := 2.0
const WIND_MIN_MOVING_DB := -60.0
const WIND_MAX_DB := -12.0
const WIND_PITCH_MIN := 0.85
const WIND_PITCH_MAX := 1.15
const GUST_DB := 3.0
const GUST_PITCH := 0.05
const GUST_PERIOD_S := 3.0
const WIND_TIMEOUT_S := 2.0

const FREEWHEEL_MIN_KMH := 5.0
const FREEWHEEL_DELAY_S := 0.5
const FREEWHEEL_STOP_POWER_W := 10.0
const FREEWHEEL_STOP_CADENCE_RPM := 20.0
const FREEWHEEL_MIN_DB := -24.0
const FREEWHEEL_MAX_DB := -16.0
const FREEWHEEL_LOUD_KMH := 40.0
const WHEEL_CIRCUMFERENCE_M := 2.1
const ENGAGEMENT_POINTS := 36

const WHEEL_MIN_KMH := 20.0
const WHEEL_LOUD_KMH := 50.0
const WHEEL_MIN_DB := -40.0
const WHEEL_MAX_DB := -26.0
const WHEEL_PITCH_MIN := 0.8
const WHEEL_PITCH_MAX := 1.3

const GRAVEL_SURFACES := ["compacted", "gravel", "dirt"]
const GRAVEL_MIN_KMH := 5.0
const GRAVEL_LOUD_KMH := 35.0
const GRAVEL_MIN_DB := -36.0
const GRAVEL_MAX_DB := -18.0
const COMPACTED_DB := -6.0
const GRAVEL_PITCH_MIN := 0.8
const GRAVEL_PITCH_MAX := 1.25

const HYSTERESIS_EXIT_FACTOR := 1.1
const SLEW_RATE_DB_PER_S := 12.0
const MAX_POI_SOURCES := 4
const POI_MIN_DB := -30.0
const POI_MAX_DB := 0.0

const KNOWN_POI_KINDS := ["church_bell", "river", "livestock", "village", "viewpoint"]

var _has_state: bool = false
var _speed_kmh: float = 0.0
var _paused: bool = false
var _rider_pos: Vector3 = Vector3.ZERO
var _zero_power_since_s: float = NAN
var _freewheel_latch: bool = false
var _clac_pending: bool = false
var _head_mps: float = 0.0
var _gust: float = 0.0
var _wind_at_s: float = NAN

var _pois: Array[Dictionary] = []
var _active_poi_ids: Dictionary = {}
var _pending_events: Array[Dictionary] = []

var _last_eval_s: float = NAN
var _wind_db: float = SILENCE_DB
var _freewheel_db: float = SILENCE_DB
var _poi_db: Dictionary = {}
var _wheel_kind := "none"
var _wheel_db: float = SILENCE_DB
var _surface := "paved"
var _gravel_db: float = SILENCE_DB


static func _is_number(v: Variant) -> bool:
	return (typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT) and is_finite(float(v))


func reset() -> void:
	_has_state = false
	_speed_kmh = 0.0
	_paused = false
	_rider_pos = Vector3.ZERO
	_zero_power_since_s = NAN
	_freewheel_latch = false
	_clac_pending = false
	_head_mps = 0.0
	_gust = 0.0
	_wind_at_s = NAN
	_active_poi_ids.clear()
	_pending_events.clear()
	_last_eval_s = NAN
	_wind_db = SILENCE_DB
	_freewheel_db = SILENCE_DB
	_poi_db.clear()


## Définit la liste des points d'intérêt du tronçon courant (`kind` inconnu ou élément invalide ignoré).
func set_pois(points: Array) -> void:
	_pois.clear()
	var valid_ids := {}
	for item in points:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var d: Dictionary = item
		var id_raw = d.get("id", null)
		if typeof(id_raw) != TYPE_STRING or (id_raw as String).is_empty():
			continue
		var kind := str(d.get("kind", ""))
		if not (kind in KNOWN_POI_KINDS):
			continue
		if not (_is_number(d.get("x", null)) and _is_number(d.get("y", null)) and _is_number(d.get("z", null)) and _is_number(d.get("radius_m", null))):
			continue
		var radius_m := float(d["radius_m"])
		if radius_m <= 0.0:
			continue
		var pid := str(id_raw)
		valid_ids[pid] = true
		_pois.append({
			"id": pid,
			"kind": kind,
			"position": Vector3(float(d["x"]), float(d["y"]), float(d["z"])),
			"radius_m": radius_m,
		})
	for old_id in _active_poi_ids.keys():
		if not valid_ids.has(old_id):
			_active_poi_ids.erase(old_id)
			_poi_db.erase(old_id)


func _update_poi_hysteresis() -> void:
	for p in _pois:
		var pid: String = p["id"]
		var kind: String = p["kind"]
		var pos: Vector3 = p["position"]
		var radius_m: float = p["radius_m"]
		var dist := _rider_pos.distance_to(pos)
		if _active_poi_ids.has(pid):
			if dist > HYSTERESIS_EXIT_FACTOR * radius_m:
				_active_poi_ids.erase(pid)
				_pending_events.append({"type": "left", "id": pid, "kind": kind})
		else:
			if dist <= radius_m:
				_active_poi_ids[pid] = true
				_pending_events.append({"type": "entered", "id": pid, "kind": kind})


## Enregistre une trame `state`, la position 3D du cycliste et l'instant `now_s`.
func on_state(state: Dictionary, rider_pos: Vector3, now_s: float) -> void:
	_has_state = true
	_rider_pos = rider_pos

	var paused_flag := bool(state.get("paused", false)) or str(state.get("session_state", "")) == "PAUSED"
	if typeof(state.get("erg", null)) == TYPE_DICTIONARY:
		paused_flag = paused_flag or bool((state["erg"] as Dictionary).get("paused", false))
	_paused = paused_flag

	var v_kmh := 0.0
	if _is_number(state.get("speed_kmh", null)):
		v_kmh = maxf(0.0, float(state["speed_kmh"]))
	elif _is_number(state.get("v", null)):
		v_kmh = maxf(0.0, float(state["v"]) * 3.6)
	_speed_kmh = v_kmh

	var w_raw = state.get("wind", null)
	if typeof(w_raw) == TYPE_DICTIONARY:
		var wd: Dictionary = w_raw
		_head_mps = float(wd["head_mps"]) if _is_number(wd.get("head_mps", null)) else 0.0
		_gust = clampf(float(wd["gust"]), 0.0, 1.0) if _is_number(wd.get("gust", null)) else 0.0
		_wind_at_s = now_s

	# Pédalage : la cadence décide si elle est présente, sinon la puissance (L5).
	var c_raw = state.get("cadence", null)
	var idle := false
	var pedalling := false
	if _is_number(c_raw):
		var cad := maxf(0.0, float(c_raw))
		idle = cad <= 0.0
		pedalling = cad > FREEWHEEL_STOP_CADENCE_RPM
	else:
		var p_raw = state.get("power", null)
		var has_power := _is_number(p_raw)
		var power_w := maxf(0.0, float(p_raw)) if has_power else 0.0
		idle = not has_power or power_w <= 0.0
		pedalling = power_w > FREEWHEEL_STOP_POWER_W

	if idle:
		if is_nan(_zero_power_since_s):
			_zero_power_since_s = now_s
		if (now_s - _zero_power_since_s) >= FREEWHEEL_DELAY_S - 1e-6 and _speed_kmh > FREEWHEEL_MIN_KMH and not _paused:
			_freewheel_latch = true
	elif pedalling:
		_zero_power_since_s = NAN
		if _freewheel_latch and not _paused:
			_clac_pending = true
		_freewheel_latch = false
	else:
		# Entre les deux seuils : si la roue libre n'était pas déjà active, n'accumule pas le délai
		if not _freewheel_latch:
			_zero_power_since_s = NAN

	if _paused or _speed_kmh <= FREEWHEEL_MIN_KMH:
		_freewheel_latch = false

	_update_poi_hysteresis()


## Vitesse dans l'air (km/h) : vitesse du cycliste plus composante de face du vent reçu, bornée à 0.
func air_speed_kmh(now_s: float) -> float:
	var head := _head_mps if not is_nan(_wind_at_s) and now_s - _wind_at_s <= WIND_TIMEOUT_S else 0.0
	return maxf(0.0, _speed_kmh + head * 3.6)


func _gust_now(now_s: float) -> float:
	if is_nan(_wind_at_s) or now_s - _wind_at_s > WIND_TIMEOUT_S:
		return 0.0
	return _gust * sin(TAU * now_s / GUST_PERIOD_S)


## Volume du vent (dB) à la vitesse du cycliste `speed_kmh` et à la vitesse dans l'air `air_kmh`.
static func _target_wind_db(speed_kmh: float, air_kmh: float, paused: bool) -> float:
	if paused or speed_kmh <= 0.0:
		return SILENCE_DB
	if air_kmh <= 0.0:
		return WIND_MIN_MOVING_DB
	var db := WIND_MAX_DB + 20.0 * WIND_LOG_K * log(minf(air_kmh, WIND_MAX_KMH) / WIND_MAX_KMH) / log(10.0)
	return clampf(db, WIND_MIN_MOVING_DB, WIND_MAX_DB)


static func _target_wind_pitch(speed_kmh: float, air_kmh: float, paused: bool) -> float:
	if paused or speed_kmh <= 0.0:
		return WIND_PITCH_MIN
	var ratio := clampf(air_kmh / WIND_MAX_KMH, 0.0, 1.0)
	return lerpf(WIND_PITCH_MIN, WIND_PITCH_MAX, ratio)


## Coups de cliquet par seconde de la roue libre à `speed_kmh`.
static func freewheel_clicks_per_s(speed_kmh: float) -> float:
	return maxf(0.0, speed_kmh) / 3.6 / WHEEL_CIRCUMFERENCE_M * float(ENGAGEMENT_POINTS)


static func _target_poi_db(dist: float, radius_m: float, paused: bool) -> float:
	if paused:
		return SILENCE_DB
	var exit_r := HYSTERESIS_EXIT_FACTOR * radius_m
	if dist > exit_r:
		return SILENCE_DB
	var t := 1.0 - clampf(dist / maxf(exit_r, 1e-3), 0.0, 1.0)
	return lerpf(POI_MIN_DB, POI_MAX_DB, t)


static func _slew(current_db: float, target_db: float, max_step_db: float) -> float:
	if is_inf(max_step_db):
		return target_db
	return move_toward(current_db, target_db, max_step_db)


func set_wheel_kind(kind: String) -> void:
	_wheel_kind = kind if kind in ["hum", "whistle"] else "none"


func set_surface(surface: String) -> void:
	_surface = surface if surface in GRAVEL_SURFACES else "paved"


## Volume cible du crissement des pneus (SILENCE_DB sur le bitume, sous GRAVEL_MIN_KMH ou en pause).
static func _target_gravel_db(surface: String, speed_kmh: float, paused: bool) -> float:
	if paused or not (surface in GRAVEL_SURFACES) or speed_kmh < GRAVEL_MIN_KMH:
		return SILENCE_DB
	var t := clampf((speed_kmh - GRAVEL_MIN_KMH) / (GRAVEL_LOUD_KMH - GRAVEL_MIN_KMH), 0.0, 1.0)
	return lerpf(GRAVEL_MIN_DB, GRAVEL_MAX_DB, t) + (COMPACTED_DB if surface == "compacted" else 0.0)


## Volume cible de la roue sonore (SILENCE_DB sans roue sonore, à l'arrêt ou en pause).
static func _target_wheel_db(kind: String, speed_kmh: float, paused: bool) -> float:
	if paused or kind == "none" or speed_kmh < WHEEL_MIN_KMH:
		return SILENCE_DB
	var t := clampf((speed_kmh - WHEEL_MIN_KMH) / (WHEEL_LOUD_KMH - WHEEL_MIN_KMH), 0.0, 1.0)
	return lerpf(WHEEL_MIN_DB, WHEEL_MAX_DB, t)


## Évalue les paramètres sonores à l'instant `now_s`.
func evaluate(now_s: float) -> Dictionary:
	if not is_nan(_zero_power_since_s) and (now_s - _zero_power_since_s) >= FREEWHEEL_DELAY_S - 1e-6 and _speed_kmh > FREEWHEEL_MIN_KMH and not _paused:
		_freewheel_latch = true
	if _paused or _speed_kmh <= FREEWHEEL_MIN_KMH:
		_freewheel_latch = false

	var max_step := INF
	if not is_nan(_last_eval_s):
		var dt := maxf(0.0, now_s - _last_eval_s)
		max_step = SLEW_RATE_DB_PER_S * dt
	_last_eval_s = now_s

	var air_kmh := air_speed_kmh(now_s)
	var g := _gust_now(now_s)
	var target_w_db := _target_wind_db(_speed_kmh, air_kmh, _paused)
	if target_w_db > SILENCE_DB:
		target_w_db = minf(target_w_db + GUST_DB * g, WIND_MAX_DB)
	# En pause : silence immédiat, sans lissage
	_wind_db = SILENCE_DB if _paused else _slew(_wind_db, target_w_db, max_step)
	var wind_pitch := _target_wind_pitch(_speed_kmh, air_kmh, _paused) * (1.0 + GUST_PITCH * g)

	var fw_playing := _freewheel_latch and not _paused and _speed_kmh > FREEWHEEL_MIN_KMH
	var target_fw_db := SILENCE_DB
	if fw_playing:
		var loud := clampf((_speed_kmh - FREEWHEEL_MIN_KMH) / (FREEWHEEL_LOUD_KMH - FREEWHEEL_MIN_KMH), 0.0, 1.0)
		target_fw_db = lerpf(FREEWHEEL_MIN_DB, FREEWHEEL_MAX_DB, loud)
	_freewheel_db = SILENCE_DB if _paused else _slew(_freewheel_db, target_fw_db, max_step)
	_wheel_db = SILENCE_DB if _paused else _slew(_wheel_db, _target_wheel_db(_wheel_kind, _speed_kmh, _paused), max_step)
	_gravel_db = SILENCE_DB if _paused else _slew(_gravel_db, _target_gravel_db(_surface, _speed_kmh, _paused), max_step)
	var clac := _clac_pending and not _paused
	_clac_pending = false

	var active_candidates: Array[Dictionary] = []
	for p in _pois:
		var pid: String = p["id"]
		if not _active_poi_ids.has(pid):
			_poi_db[pid] = _slew(float(_poi_db.get(pid, SILENCE_DB)), SILENCE_DB, max_step)
			continue
		var pos: Vector3 = p["position"]
		var radius_m: float = p["radius_m"]
		var dist := _rider_pos.distance_to(pos)
		var t_db := _target_poi_db(dist, radius_m, _paused)
		var prev_db := float(_poi_db.get(pid, t_db if is_inf(max_step) else SILENCE_DB))
		var cur_db := _slew(prev_db, t_db, max_step)
		_poi_db[pid] = cur_db
		active_candidates.append({
			"id": pid,
			"kind": p["kind"],
			"volume_db": cur_db,
			"position": pos,
			"_dist": dist,
		})

	active_candidates.sort_custom(func(a, b):
		if not is_equal_approx(a["_dist"], b["_dist"]):
			return a["_dist"] < b["_dist"]
		return str(a["id"]) < str(b["id"])
	)

	var out_pois := []
	var count := mini(MAX_POI_SOURCES, active_candidates.size())
	for i in range(count):
		var c := active_candidates[i]
		out_pois.append({
			"id": c["id"],
			"kind": c["kind"],
			"volume_db": c["volume_db"],
			"position": c["position"],
		})

	var events_out := _pending_events.duplicate(true)
	_pending_events.clear()

	return {
		"wind": {
			"volume_db": _wind_db,
			"pitch": wind_pitch,
			"air_kmh": air_kmh,
		},
		"freewheel": {
			"playing": fw_playing,
			"volume_db": _freewheel_db,
			"clicks_per_s": freewheel_clicks_per_s(_speed_kmh) if fw_playing else 0.0,
			"clac": clac,
		},
		"wheel": {
			"kind": _wheel_kind,
			"volume_db": _wheel_db,
			"pitch": lerpf(WHEEL_PITCH_MIN, WHEEL_PITCH_MAX, clampf(_speed_kmh / WHEEL_LOUD_KMH, 0.0, 1.0)),
		},
		"gravel": {
			"surface": _surface,
			"volume_db": _gravel_db,
			"pitch": lerpf(GRAVEL_PITCH_MIN, GRAVEL_PITCH_MAX, clampf(_speed_kmh / GRAVEL_LOUD_KMH, 0.0, 1.0)),
		},
		"pois": out_pois,
		"events": events_out,
	}
