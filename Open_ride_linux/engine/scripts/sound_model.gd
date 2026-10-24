extends RefCounted

## Modèle sonore sans affichage : vent, roue libre et points d'intérêt spatialisés
## (Lot L5, SRS §8 « Audio », Contrat IPC v1 §3, Format .world v1 §8), sans aucun nœud Godot.
## Pas de class_name : charger par preload("res://scripts/sound_model.gd").
##
## Constantes de comportement :
## - `SILENCE_DB = -80.0` : volume de silence (à l'arrêt ou en pause).
## - `WIND_MAX_KMH = 60.0` : vitesse de plafonnement du volume et de la hauteur (`pitch`) du vent.
## - `WIND_MIN_MOVING_DB = -36.0`, `WIND_MAX_DB = 0.0` : plage de volume du vent en mouvement.
## - `WIND_PITCH_MIN = 0.8`, `WIND_PITCH_MAX = 1.3` : plage de hauteur (`pitch`) du vent.
## - `FREEWHEEL_MIN_KMH = 5.0` : vitesse minimale d'activation de la roue libre.
## - `FREEWHEEL_DELAY_S = 0.5` : durée minimale à 0 W (ou puissance absente) avant roue libre.
## - `FREEWHEEL_STOP_POWER_W = 10.0` : puissance au-dessus de laquelle la roue libre s'arrête.
## - `FREEWHEEL_ACTIVE_DB = -6.0` : volume cible de la roue libre active.
## - `HYSTERESIS_EXIT_FACTOR = 1.1` : un POI entre à `radius_m` et sort à `1,1 × radius_m`.
## - `SLEW_RATE_DB_PER_S = 12.0` : variation maximale de tout volume (12 dB/s, soit 1,2 dB pour 0,1 s).
## - `MAX_POI_SOURCES = 4` : nombre maximal de points d'intérêt audibles simultanément (les plus proches).

const SILENCE_DB := -80.0
const WIND_MAX_KMH := 60.0
const WIND_MIN_MOVING_DB := -36.0
const WIND_MAX_DB := 0.0
const WIND_PITCH_MIN := 0.8
const WIND_PITCH_MAX := 1.3

const FREEWHEEL_MIN_KMH := 5.0
const FREEWHEEL_DELAY_S := 0.5
const FREEWHEEL_STOP_POWER_W := 10.0
const FREEWHEEL_ACTIVE_DB := -6.0

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

var _pois: Array[Dictionary] = []
var _active_poi_ids: Dictionary = {}
var _pending_events: Array[Dictionary] = []

var _last_eval_s: float = NAN
var _wind_db: float = SILENCE_DB
var _freewheel_db: float = SILENCE_DB
var _poi_db: Dictionary = {}


static func _is_number(v: Variant) -> bool:
	return (typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT) and is_finite(float(v))


func reset() -> void:
	_has_state = false
	_speed_kmh = 0.0
	_paused = false
	_rider_pos = Vector3.ZERO
	_zero_power_since_s = NAN
	_freewheel_latch = false
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

	var p_raw = state.get("power", null)
	var has_power := _is_number(p_raw)
	var power_w := maxf(0.0, float(p_raw)) if has_power else 0.0

	if not has_power or power_w <= 0.0:
		if is_nan(_zero_power_since_s):
			_zero_power_since_s = now_s
		if (now_s - _zero_power_since_s) >= FREEWHEEL_DELAY_S - 1e-6 and _speed_kmh > FREEWHEEL_MIN_KMH and not _paused:
			_freewheel_latch = true
	elif power_w > FREEWHEEL_STOP_POWER_W:
		_zero_power_since_s = NAN
		_freewheel_latch = false
	else:
		# Entre 0 et 10 W : si la roue libre n'était pas déjà active, n'accumule pas le délai à 0 W
		if not _freewheel_latch:
			_zero_power_since_s = NAN

	if _paused or _speed_kmh <= FREEWHEEL_MIN_KMH:
		_freewheel_latch = false

	_update_poi_hysteresis()


static func _target_wind_db(speed_kmh: float, paused: bool) -> float:
	if paused or speed_kmh <= 0.0:
		return SILENCE_DB
	var ratio := clampf(speed_kmh / WIND_MAX_KMH, 0.0, 1.0)
	return lerpf(WIND_MIN_MOVING_DB, WIND_MAX_DB, ratio)


static func _target_wind_pitch(speed_kmh: float, paused: bool) -> float:
	if paused or speed_kmh <= 0.0:
		return WIND_PITCH_MIN
	var ratio := clampf(speed_kmh / WIND_MAX_KMH, 0.0, 1.0)
	return lerpf(WIND_PITCH_MIN, WIND_PITCH_MAX, ratio)


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

	var target_w_db := _target_wind_db(_speed_kmh, _paused)
	_wind_db = _slew(_wind_db, target_w_db, max_step)
	var wind_pitch := _target_wind_pitch(_speed_kmh, _paused)

	var fw_playing := _freewheel_latch and not _paused and _speed_kmh > FREEWHEEL_MIN_KMH
	var target_fw_db := FREEWHEEL_ACTIVE_DB if fw_playing else SILENCE_DB
	_freewheel_db = _slew(_freewheel_db, target_fw_db, max_step)

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
		},
		"freewheel": {
			"playing": fw_playing,
			"volume_db": _freewheel_db,
		},
		"pois": out_pois,
		"events": events_out,
	}
