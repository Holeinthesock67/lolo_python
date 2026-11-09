extends RefCounted

## Distance parcourue pendant la séance, déduite des positions `s` des trames `state` (lot N17).
##
## Sans demi-tour, c'est `s` (plus les tours d'une boucle si le core ramène `s` sur le tour). Après un demi-tour
## depuis la pause, `s` décroît (champ `dir` de la révision 1.9) et la distance parcourue continue de croître,
## comme celle du journal et du FIT : chaque trame ajoute |Δs|. Une nouvelle séance (temps qui repart en
## arrière) ou un saut de plus de RESET_JUMP_M (autre parcours, reprise) repart de `s`.
## Utilisé par le HUD (hud_view_model.gd) et la fiche de la pause (menu_flow.gd). Pas de class_name : charger
## par preload("res://scripts/ridden_distance.gd").

const RESET_JUMP_M := 500.0   # plus que le chemin de quelques secondes sans trame à 80 km/h

var distance_m := NAN
var _last_s := NAN
var _last_t := NAN


func reset() -> void:
	distance_m = NAN
	_last_s = NAN
	_last_t = NAN


## Trame reçue : position `s` (m), temps de séance `t` (s, NAN s'il manque), longueur d'une boucle (0 sinon).
## Renvoie la distance parcourue (NAN tant qu'aucune position n'est connue).
func push(s: float, t: float = NAN, loop_length_m: float = 0.0) -> float:
	if is_nan(s):
		return distance_m
	var new_session := not is_nan(t) and not is_nan(_last_t) and t + 1.0 < _last_t
	if is_nan(_last_s) or new_session:
		distance_m = s
	else:
		var ds := s - _last_s
		if loop_length_m > 0.0:   # passage de la ligne d'une boucle ramenée sur le tour, dans un sens ou l'autre
			if ds < -0.5 * loop_length_m:
				ds += loop_length_m
			elif ds > 0.5 * loop_length_m:
				ds -= loop_length_m
		distance_m = s if absf(ds) > RESET_JUMP_M else distance_m + absf(ds)
	_last_s = s
	if not is_nan(t):
		_last_t = t
	return distance_m
