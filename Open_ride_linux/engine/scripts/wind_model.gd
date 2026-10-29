extends RefCounted

## Modèle du vent de l'engine, sans aucun nœud (Lot P4, Contrat IPC v1 révision 1.3 §3, thème 1.2).
## Pas de class_name : charger par preload("res://scripts/wind_model.gd").
##
## Une seule valeur lissée pour tout le décor (arbres, nuages, sons, indicateur) :
## - `on_state(state, now_s)` lit l'objet `wind` de la trame (2 fois par seconde) ; sans `wind` depuis
##   `WIRE_TIMEOUT_S`, le vent du thème (`set_theme_wind`) sert de vent décoratif, sinon calme ;
## - `evaluate(now_s)` rend `{dir, strength, gust, phase}` : `dir` est la direction vers où souffle le
##   vent dans le repère de Godot (nord = −z, est = +x), `strength` de 0 à 1 (1 = 60 km/h), `gust` de
##   0 à 1, `phase` en secondes, continue (elle avance plus vite par vent fort, sans saut) ;
## - `apparent(rider_speed_mps, heading_deg)` : vent apparent (m/s) pour l'animation proche.
##
## Lissage du premier ordre : `DIR_TAU_S = 2.0` pour la direction, `STRENGTH_TAU_S = 0.5` pour la force
## et la rafale (90 % de la cible en 1,15 s, sans dépassement).

const MAX_SPEED_MPS := 60.0 / 3.6
const WIRE_TIMEOUT_S := 2.0
const DIR_TAU_S := 2.0
const STRENGTH_TAU_S := 0.5
const PHASE_RATE_MIN := 0.4      # vitesse d'avance de la phase par vent nul (s par s)
const PHASE_RATE_MAX := 2.0      # par vent de 60 km/h
const THEME_GUST_PERIOD_S := 23.0

var _theme_speed_mps: float = 0.0
var _theme_from_deg: float = 0.0
var _theme_gust: float = 0.0

var _wire_seen: bool = false
var _wire_at_s: float = -INF
var _wire_speed_mps: float = 0.0
var _wire_from_deg: float = 0.0
var _wire_gust: float = 0.0
var _wire_head_mps: float = 0.0

var _speed_mps: float = 0.0       # lissé
var _gust: float = 0.0            # lissé
var _from_deg: float = 0.0        # lissé (plus court chemin)
var _dir_ready: bool = false
var _phase: float = 0.0
var _last_eval_s: float = NAN
var _out := {"dir": Vector3.ZERO, "strength": 0.0, "gust": 0.0, "phase": 0.0}


static func _is_number(v: Variant) -> bool:
	return (typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT) and is_finite(float(v))


## Direction horizontale d'un cap (degrés depuis le nord, sens horaire) dans le repère de Godot.
static func heading_vector(heading_deg: float) -> Vector3:
	var a := deg_to_rad(heading_deg)
	return Vector3(sin(a), 0.0, -cos(a))


static func shortest_delta_deg(from_deg: float, to_deg: float) -> float:
	return fposmod(to_deg - from_deg + 180.0, 360.0) - 180.0


func reset() -> void:
	_wire_seen = false
	_wire_at_s = -INF
	_speed_mps = 0.0
	_gust = 0.0
	_dir_ready = false
	_phase = 0.0
	_last_eval_s = NAN


## Vent décoratif du thème 1.2 (`{speed_kmh, from_deg, gust_pct}`) ; dictionnaire vide : calme.
func set_theme_wind(theme_wind: Dictionary) -> void:
	_theme_speed_mps = maxf(float(theme_wind.get("speed_kmh", 0.0)), 0.0) / 3.6 \
		if _is_number(theme_wind.get("speed_kmh", 0.0)) else 0.0
	_theme_from_deg = float(theme_wind.get("from_deg", 0.0)) \
		if _is_number(theme_wind.get("from_deg", 0.0)) else 0.0
	_theme_gust = clampf(float(theme_wind.get("gust_pct", 0.0)) / 100.0, 0.0, 1.0) \
		if _is_number(theme_wind.get("gust_pct", 0.0)) else 0.0


func on_state(state: Dictionary, now_s: float) -> void:
	var w: Variant = state.get("wind", null)
	if typeof(w) != TYPE_DICTIONARY:
		return
	var wd: Dictionary = w
	if not (_is_number(wd.get("speed_mps")) and _is_number(wd.get("from_deg"))):
		return
	_wire_seen = true
	_wire_at_s = now_s
	_wire_speed_mps = maxf(float(wd["speed_mps"]), 0.0)
	_wire_from_deg = float(wd["from_deg"])
	_wire_gust = clampf(float(wd.get("gust", 0.0)), 0.0, 1.0) if _is_number(wd.get("gust", 0.0)) else 0.0
	_wire_head_mps = float(wd.get("head_mps", 0.0)) if _is_number(wd.get("head_mps", 0.0)) else 0.0


## Vrai tant que le core envoie le vent (dernier `wind` reçu il y a moins de `WIRE_TIMEOUT_S`).
func has_wire(now_s: float) -> bool:
	return _wire_seen and now_s - _wire_at_s <= WIRE_TIMEOUT_S


## Composante de face reçue du core (m/s), 0 sans vent du core.
func head_mps(now_s: float) -> float:
	return _wire_head_mps if has_wire(now_s) else 0.0


## Cibles du vent à l'instant `now_s` : [vitesse (m/s), provenance (degrés), rafale, souffle].
func _targets(now_s: float) -> Array:
	if has_wire(now_s):
		return [_wire_speed_mps, _wire_from_deg, _wire_gust, true]
	if _theme_speed_mps > 0.0:
		# Vent décoratif du thème : une rafale lente, de ± la moitié de gust_pct autour du vent de base.
		var g := 0.5 + 0.5 * sin(TAU * now_s / THEME_GUST_PERIOD_S)
		return [_theme_speed_mps * (1.0 + 0.5 * _theme_gust * (2.0 * g - 1.0)), _theme_from_deg, _theme_gust * g, true]
	return [0.0, _from_deg, 0.0, _speed_mps > 1e-3]   # le vent retombe doucement au calme


## Scène figée des tests graphiques (lot X20) : vent posé sur ses cibles à l'instant `now_s`, sans l'historique
## du lissage, et phase calculée depuis 0 ; deux passages figés au même instant voient le même vent.
func settle(now_s: float) -> void:
	var t := _targets(now_s)
	_speed_mps = float(t[0])
	_from_deg = fposmod(float(t[1]), 360.0)
	_gust = float(t[2])
	_dir_ready = true
	_phase = maxf(now_s, 0.0) * lerpf(PHASE_RATE_MIN, PHASE_RATE_MAX, clampf(_speed_mps / MAX_SPEED_MPS, 0.0, 1.0))
	_last_eval_s = now_s


func evaluate(now_s: float) -> Dictionary:
	var t := _targets(now_s)
	var target_speed: float = t[0]
	var target_from: float = t[1]
	var target_gust: float = t[2]
	var blowing: bool = t[3]

	var dt := 0.0 if is_nan(_last_eval_s) else clampf(now_s - _last_eval_s, 0.0, 1.0)
	_last_eval_s = now_s
	if not _dir_ready:
		_from_deg = target_from
		_dir_ready = true
	var k_strength := 1.0 - exp(-dt / STRENGTH_TAU_S)
	var k_dir := 1.0 - exp(-dt / DIR_TAU_S)
	_speed_mps += (target_speed - _speed_mps) * k_strength
	_gust += (target_gust - _gust) * k_strength
	_from_deg = fposmod(_from_deg + shortest_delta_deg(_from_deg, target_from) * k_dir, 360.0)

	var strength := clampf(_speed_mps / MAX_SPEED_MPS, 0.0, 1.0)
	_phase += dt * lerpf(PHASE_RATE_MIN, PHASE_RATE_MAX, strength)
	_out["dir"] = heading_vector(_from_deg + 180.0) if blowing else Vector3.ZERO
	_out["strength"] = strength
	_out["gust"] = _gust
	_out["phase"] = _phase
	return _out.duplicate()


## Vent apparent (m/s, repère de Godot) : vent lissé moins la vitesse du cycliste le long de son cap.
func apparent(rider_speed_mps: float, heading_deg: float) -> Vector3:
	var wind := heading_vector(_from_deg + 180.0) * _speed_mps
	return wind - heading_vector(heading_deg) * maxf(rider_speed_mps, 0.0)
