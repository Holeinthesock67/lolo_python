extends SceneTree

## Tests unitaires de l'inclinaison de la caméra (camera_follow.gd, lot Q2).
##
## Critère 2 :
## - 0° sur le plat ;
## - pente constante 8 % : atan(0,08) ± 0,3° une fois le lissage établi ;
## - bornes à ±12° ;
## - variation lissée (pas de saut de plus de 1° par image à 60 images/s sur une marche 0 → 8 %).

const CameraFollowScript := preload("res://scripts/camera_follow.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")

var _failures := 0
var _checked := 0


func _init() -> void:
	_run()
	print("test_camera_pitch : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _make_route(grade_pct: float, length_m: float = 2000.0):
	var d := {"version": "1.0", "ds_m": 10.0, "n": 0, "length_m": 0.0, "type": "open",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	var n := int(length_m / 10.0) + 1
	for k in range(n):
		var s := k * 10.0
		d["lat"].append(45.0)
		d["lon"].append(6.0)
		d["alt_m"].append(500.0 + (grade_pct / 100.0) * s)
		d["x"].append(0.0)
		d["z"].append(-s)  # nord = -z
		d["grade_pct"].append(grade_pct)
		d["heading_deg"].append(0.0)
	d["n"] = n
	d["length_m"] = (n - 1) * 10.0
	var route = RouteDataScript.new()
	route.load_route_dict(d)
	return route


func _run() -> void:
	var follow = CameraFollowScript.new()

	# 1. Plat (pente 0 %) : angle = 0°
	var route_flat = _make_route(0.0)
	var p0: float = follow.pitch_deg(route_flat, 200.0, 8.0, 0.1)
	_check(absf(p0) < 0.001, "0° sur le plat : %.4f°" % p0)

	# 2. Marche 0 -> 8 % à 60 images/s (dt = 1/60 s) : variation lissée sans saut > 1° par image
	var route_8 = _make_route(8.0)
	var expected_8_deg := rad_to_deg(atan(0.08))  # ~4.5739°
	var dt_60fps := 1.0 / 60.0

	# Premier pas après le plat : le saut doit être < 1.0°
	var p1: float = follow.pitch_deg(route_8, 200.0, 8.0, dt_60fps)
	var jump := absf(p1 - p0)
	_check(jump < 1.0, "variation lissée : saut de %.3f° à la 1re image à 60 fps (< 1°)" % jump)

	# Simulation sur 3 secondes (180 trames) pour laisser le lissage s'établir (tau = 0.5 s)
	var max_frame_jump := jump
	var prev_p := p1
	for frame in range(180):
		var s_sim := 200.0 + frame * dt_60fps * 8.0
		var p: float = follow.pitch_deg(route_8, s_sim, 8.0, dt_60fps)
		max_frame_jump = maxf(max_frame_jump, absf(p - prev_p))
		prev_p = p

	_check(max_frame_jump < 1.0, "aucun saut supérieur à 1° sur toute la transition : max %.3f°" % max_frame_jump)
	_check(absf(prev_p - expected_8_deg) <= 0.3,
		"pente constante 8 %% après lissage : %.3f° (cible %.3f° ± 0.3°)" % [prev_p, expected_8_deg])

	# 3. Bornes à ±12° sur pentes extrêmes (+30 % et -30 %)
	follow.reset()
	var route_steep_up = _make_route(30.0)
	for _i in range(120):
		follow.pitch_deg(route_steep_up, 200.0, 8.0, 0.05)
	var p_up: float = follow.pitch_deg(route_steep_up, 200.0, 8.0, 0.05)
	_check(absf(p_up - 12.0) < 0.001, "borne haute à +12° : %.3f°" % p_up)

	follow.reset()
	var route_steep_down = _make_route(-30.0)
	for _i in range(120):
		follow.pitch_deg(route_steep_down, 200.0, 8.0, 0.05)
	var p_down: float = follow.pitch_deg(route_steep_down, 200.0, 8.0, 0.05)
	_check(absf(p_down - (-12.0)) < 0.001, "borne basse à -12° : %.3f°" % p_down)

	# 4. Route nulle gérée sans crash
	follow.reset()
	_check(follow.pitch_deg(null, 0.0, 0.0) == 0.0, "route nulle gérée sans crash")
