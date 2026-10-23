extends RefCounted

## Position affichée de la caméra le long de la route, à la cadence de rendu (SRS §8, lot D4).
##
## - Extrapolation : s_aff = s_dernier + v_dernier × (maintenant − t_reçu_dernier), bornée à 1 s.
## - Correction douce : à chaque trame, l'écart entre la position affichée et la position extrapolée
##   de la nouvelle trame est rattrapé linéairement en 150 ms, sans saut.
## - Pendant RUNNING la position ne recule jamais ; hors RUNNING elle se cale sur s sans extrapolation.
## - Boucle : les s reçus sont « déroulés » (passage de la longueur à 0) ; l'appelant applique wrap_s.
## Les temps sont en microsecondes de Time.get_ticks_usec(). Pas de class_name (charger par preload).

const MAX_EXTRAPOLATION_S := 1.0
const CORRECTION_S := 0.15

## Longueur de la boucle (0 si le parcours n'est pas une boucle) : sert à dérouler s.
var loop_length_m := 0.0
var displayed_s := 0.0

## Deux dernières trames reçues : {t_us, s, v}.
var last_frame: Dictionary = {}
var previous_frame: Dictionary = {}

var _running := false
var _offset := 0.0          # écart à rattraper au moment de la dernière trame
var _unwrap_m := 0.0        # tours de boucle ajoutés à s
var _has_frame := false


func reset() -> void:
	last_frame = {}
	previous_frame = {}
	displayed_s = 0.0
	_offset = 0.0
	_unwrap_m = 0.0
	_has_frame = false


func has_frame() -> bool:
	return _has_frame


## Enregistre une trame state : s et v du core, reçue à t_us (horloge locale).
func push_frame(t_us: int, s: float, v: float, running: bool) -> void:
	if loop_length_m > 0.0 and _has_frame:
		var raw_prev: float = float(last_frame["s"]) - _unwrap_m
		if s - raw_prev < -0.5 * loop_length_m:
			_unwrap_m += loop_length_m
		elif s - raw_prev > 0.5 * loop_length_m:
			_unwrap_m -= loop_length_m
	var s_abs := s + _unwrap_m
	previous_frame = last_frame
	last_frame = {"t_us": t_us, "s": s_abs, "v": v}
	_running = running
	if not running or not _has_frame:
		_offset = 0.0
		displayed_s = s_abs
	else:
		# Écart entre ce qui est affiché et la nouvelle référence, rattrapé en 150 ms.
		_offset = displayed_s - s_abs
	_has_frame = true


## Position extrapolée de la dernière trame à l'instant now_us, sans correction.
func extrapolated(now_us: int) -> float:
	if not _has_frame:
		return 0.0
	var age := clampf((now_us - int(last_frame["t_us"])) / 1e6, 0.0, MAX_EXTRAPOLATION_S)
	return float(last_frame["s"]) + float(last_frame["v"]) * age


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
	var since := (now_us - int(last_frame["t_us"])) / 1e6
	var k := clampf(1.0 - since / CORRECTION_S, 0.0, 1.0)
	var target := extrapolated(now_us) + _offset * k
	displayed_s = maxf(displayed_s, target)   # jamais de recul pendant RUNNING
	return displayed_s
