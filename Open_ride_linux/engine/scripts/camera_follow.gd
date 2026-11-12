extends RefCounted

## Position affichée de la caméra le long de la route, à la cadence de rendu (SRS §8, lot D4).
##
## - Extrapolation : s_aff = s_dernier + v_dernier × (maintenant − t_reçu_dernier), bornée à 1 s.
## - Correction douce : à chaque trame, l'écart entre la position affichée et la position extrapolée
##   de la nouvelle trame est rattrapé linéairement en 150 ms, sans saut.
## - Pendant RUNNING la position ne recule jamais ; hors RUNNING elle se cale sur s sans extrapolation.
## - Sens (lot N17, champ `dir` de la trame) : à rebours, s décroît ; l'extrapolation suit le sens et la position ne
##   revient jamais en arrière dans ce sens. Le demi-tour se fait en pause : la position se cale sur la trame.
## - Boucle : les s reçus sont « déroulés » (passage de la longueur à 0) ; l'appelant applique wrap_s.
## - Écart à l'axe (lot AS2) : l'avatar suit `lane_m` du core (placement dans la roue, dépassements) sans
##   marche d'escalier entre deux trames (au plus LANE_FOLLOW_MPS), la caméra suit l'avatar avec un lissage de
##   LANE_SMOOTH_TAU_S ; sans `lane_m` (pas de bot), DEFAULT_LANE_M (RoadBuilder.RIDER_LATERAL_M, lot P32).
## Les temps sont en microsecondes de Time.get_ticks_usec(). Pas de class_name (charger par preload).

const MAX_EXTRAPOLATION_S := 1.0
const CORRECTION_S := 0.15
const PITCH_LOOKAHEAD_NOMINAL_M := 20.0
const PITCH_LOOKAHEAD_MIN_M := 15.0
const PITCH_LOOKAHEAD_MAX_M := 30.0
const PITCH_SMOOTH_TAU_S := 0.5
const DEFAULT_LANE_M := 1.2      # RoadBuilder.RIDER_LATERAL_M
const LANE_FOLLOW_MPS := 1.0     # un peu plus que les 0,8 m/s du core : l'avatar ne prend pas de retard
const LANE_SMOOTH_TAU_S := 0.5
const PITCH_MAX_DEG := 18.0   # 12° jusqu'au lot Y15 : avec le relief ×2, une pente de 16 % réelle reste suivie

## Longueur de la boucle (0 si le parcours n'est pas une boucle) : sert à dérouler s.
var loop_length_m := 0.0
var displayed_s := 0.0

## Deux dernières trames reçues : {t_us, s, v}.
var last_frame: Dictionary = {}
var previous_frame: Dictionary = {}
## Sens de la dernière trame : 1 dans le sens du parcours, -1 à rebours (lot N17).
var direction := 1

var _running := false
var _offset := 0.0          # écart à rattraper au moment de la dernière trame
var _unwrap_m := 0.0        # tours de boucle ajoutés à s
var _has_frame := false
var _current_pitch_deg := 0.0
var _last_pitch_time_us := -1
var _has_pitch := false
## Écart à l'axe affiché de l'avatar et de la caméra (lot AS2).
var lane_m := DEFAULT_LANE_M
var camera_lane_m := DEFAULT_LANE_M
var _last_lane_time_us := -1


func reset() -> void:
	last_frame = {}
	previous_frame = {}
	displayed_s = 0.0
	_offset = 0.0
	_unwrap_m = 0.0
	_current_pitch_deg = 0.0
	_last_pitch_time_us = -1
	_has_pitch = false
	_has_frame = false
	direction = 1
	lane_m = DEFAULT_LANE_M
	camera_lane_m = DEFAULT_LANE_M
	_last_lane_time_us = -1


func has_frame() -> bool:
	return _has_frame


## Enregistre une trame state : s et v du core, reçue à t_us (horloge locale) ; `dir` : sens (lot N17).
func push_frame(t_us: int, s: float, v: float, running: bool, dir := 1) -> void:
	dir = -1 if dir < 0 else 1
	var turned := dir != direction   # demi-tour : nouvelle référence, sans rattrapage dans l'ancien sens
	direction = dir
	if loop_length_m > 0.0 and _has_frame:
		var raw_prev: float = float(last_frame["s"]) - _unwrap_m
		if s - raw_prev < -0.5 * loop_length_m:
			_unwrap_m += loop_length_m
		elif s - raw_prev > 0.5 * loop_length_m:
			_unwrap_m -= loop_length_m
	var s_abs := s + _unwrap_m
	# Position montrée à t_us (et non displayed_s, calculée à l'image précédente) : sinon chaque trame ajoute le
	# chemin parcouru depuis cette image au retard, qui s'accumule quand une trame arrive avant chaque image
	# (~15 images/s en high : jusqu'à 4 m de retard sur le core, les bots semblaient traverser le cycliste).
	var shown := _ahead_of(displayed_s, _target(t_us)) if _has_frame and _running and not turned else displayed_s
	previous_frame = last_frame
	last_frame = {"t_us": t_us, "s": s_abs, "v": v}
	_running = running
	if not running or not _has_frame or turned:
		_offset = 0.0
		displayed_s = s_abs
	else:
		# Écart entre ce qui est montré maintenant et la nouvelle référence, rattrapé en 150 ms.
		_offset = shown - s_abs
	_has_frame = true


## Position extrapolée de la dernière trame à l'instant now_us, sans correction.
func extrapolated(now_us: int) -> float:
	if not _has_frame:
		return 0.0
	var age := clampf((now_us - int(last_frame["t_us"])) / 1e6, 0.0, MAX_EXTRAPOLATION_S)
	return float(last_frame["s"]) + direction * float(last_frame["v"]) * age


## Vrai quand l'extrapolation a atteint sa borne (core muet depuis plus d'1 s) : caméra figée.
func is_frozen(now_us: int) -> bool:
	return _has_frame and (now_us - int(last_frame["t_us"])) / 1e6 >= MAX_EXTRAPOLATION_S


## Calcule et renvoie la position affichée à l'instant now_us.
func update(now_us: int) -> float:
	if not _has_frame:
		return displayed_s
	if not _running:
		displayed_s = float(last_frame["s"])
		return displayed_s
	displayed_s = _ahead_of(displayed_s, _target(now_us))   # jamais de recul pendant RUNNING
	return displayed_s


## La plus avancée des deux positions dans le sens de la marche.
func _ahead_of(a: float, b: float) -> float:
	return maxf(a, b) if direction > 0 else minf(a, b)


## Position extrapolée de la dernière trame à now_us, plus l'écart qui reste à rattraper.
func _target(now_us: int) -> float:
	var since := (now_us - int(last_frame["t_us"])) / 1e6
	var k := clampf(1.0 - since / CORRECTION_S, 0.0, 1.0)
	return extrapolated(now_us) + _offset * k


## Inclinaison de la caméra vers la route devant (Lot Q2).
## Angle de la droite qui joint l'œil au point de la route situé 20 m devant (entre 15 et 30 m selon v),
## lissé avec une constante de temps de 0,5 s et borné à ±PITCH_MAX_DEG. Les points viennent de `sample_point`,
## donc à la hauteur affichée : l'angle suit le relief exagéré (`route.relief_k`, lots Q2 et Y15).
func pitch_deg(route, s: float, v: float, dt_s: float = -1.0) -> float:
	if route == null or route.n < 2:
		return 0.0
	var lookahead := clampf(PITCH_LOOKAHEAD_NOMINAL_M + (v - 8.0) * 0.75, PITCH_LOOKAHEAD_MIN_M, PITCH_LOOKAHEAD_MAX_M)
	var s_eye: float = route.wrap_s(s)
	var s_target: float = route.wrap_s(s + direction * lookahead)   # devant, dans le sens de la marche (lot N17)
	var eye_pos: Vector3 = route.sample_point(s_eye)
	var target_pos: Vector3 = route.sample_point(s_target)
	var dx := target_pos.x - eye_pos.x
	var dz := target_pos.z - eye_pos.z
	var dy := target_pos.y - eye_pos.y
	var dxz := sqrt(dx * dx + dz * dz)
	var raw_angle_rad := atan2(dy, dxz) if dxz > 1e-6 else 0.0
	var target_pitch_deg := clampf(rad_to_deg(raw_angle_rad), -PITCH_MAX_DEG, PITCH_MAX_DEG)

	var dt := dt_s
	if dt < 0.0:
		var now_us := Time.get_ticks_usec()
		if _last_pitch_time_us < 0:
			dt = 0.0
		else:
			dt = clampf((now_us - _last_pitch_time_us) / 1e6, 0.0, 1.0)
		_last_pitch_time_us = now_us

	if not _has_pitch:
		_has_pitch = true
		_current_pitch_deg = target_pitch_deg
	elif dt > 0.0:
		var alpha := 1.0 - exp(-dt / PITCH_SMOOTH_TAU_S)
		_current_pitch_deg = lerpf(_current_pitch_deg, target_pitch_deg, alpha)

	return clampf(_current_pitch_deg, -PITCH_MAX_DEG, PITCH_MAX_DEG)


## Avance l'écart à l'axe affiché vers `target` (champ `lane_m` de la dernière trame, lot AS2) : avatar au plus
## LANE_FOLLOW_MPS, caméra lissée sur LANE_SMOOTH_TAU_S derrière l'avatar. `dt_s` négatif : temps réel écoulé
## depuis l'appel précédent (`now_us`, comme pitch_deg), pour suivre le core même quand le rendu rame.
func update_lane(target: float, dt_s: float, now_us: int = -1) -> void:
	if dt_s < 0.0:
		dt_s = 0.0 if _last_lane_time_us < 0 else clampf((now_us - _last_lane_time_us) / 1e6, 0.0, 1.0)
		_last_lane_time_us = now_us
	if dt_s <= 0.0:
		return
	lane_m = move_toward(lane_m, target, LANE_FOLLOW_MPS * dt_s)
	camera_lane_m = lerpf(camera_lane_m, lane_m, 1.0 - exp(-dt_s / LANE_SMOOTH_TAU_S))
