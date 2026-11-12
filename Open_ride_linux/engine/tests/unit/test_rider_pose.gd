extends SceneTree

## Pose du cycliste dans les virages (rider_pose.gd, lot CY1). Parcours d'essai : carré de 300 m de côté, 3 points
## par coin (le coin et un point à 3 m de part et d'autre, comme un parcours dessiné à la main tel que
## « essai-vent-carre »), ré-échantillonné tous les 10 m avec le cap du compilateur (pipeline._heading : écart des
## voisins puis moyenne circulaire sur 3 points). Avant le lot, le vélo prenait ce cap : jusqu'à 29° de crabe.
## Lancement : godot --headless --path engine --script res://tests/unit/test_rider_pose.gd

const RouteDataScript := preload("res://scripts/route_data.gd")
const RiderPose := preload("res://scripts/rider_pose.gd")

const SIDE_M := 300.0
const LANE_M := 1.2

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _init() -> void:
	_run()
	print("test_rider_pose : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


static func _wrap(a: float) -> float:
	return fposmod(a + PI, TAU) - PI


## Carré parcouru dans le sens horaire vu du ciel (virages à droite), boucle ou tracé ouvert (sans le dernier côté).
func _square(loop: bool) -> Variant:
	var corners := [Vector2(0, 0), Vector2(SIDE_M, 0), Vector2(SIDE_M, SIDE_M), Vector2(0, SIDE_M)]
	var pts: Array[Vector2] = []
	for k in 4:
		var c: Vector2 = corners[k]
		pts.append(c + (corners[k - 1] - c).normalized() * 3.0)
		pts.append(c)
		pts.append(c + (corners[(k + 1) % 4] - c).normalized() * 3.0)
	if loop:
		pts.append(pts[0])
	else:
		pts = pts.slice(1, pts.size() - 2)
	var cum := PackedFloat64Array([0.0])
	for i in range(1, pts.size()):
		cum.append(cum[i - 1] + pts[i].distance_to(pts[i - 1]))
	var length: float = cum[cum.size() - 1]
	var n := int(length / 10.0) + 1
	if length - (n - 1) * 10.0 > 1e-3:
		n += 1
	var xs := PackedFloat64Array()
	var zs := PackedFloat64Array()
	var j := 0
	for i in n:
		var s := minf(i * 10.0, length)
		while j < cum.size() - 2 and cum[j + 1] < s:
			j += 1
		var u := (s - cum[j]) / (cum[j + 1] - cum[j])
		var p := pts[j].lerp(pts[j + 1], u)
		xs.append(p.x)
		zs.append(p.y)
	if loop:
		xs[n - 1] = xs[0]
		zs[n - 1] = zs[0]
	# Cap comme pipeline._heading : écart des voisins, puis moyenne circulaire sur 3 points.
	var m := n - 1 if loop else n
	var raw := PackedFloat64Array()
	for i in m:
		var a: int = (i - 1 + m) % m if loop else maxi(i - 1, 0)
		var b: int = (i + 1) % m if loop else mini(i + 1, n - 1)
		raw.append(atan2(xs[b] - xs[a], -(zs[b] - zs[a])))
	var hd: Array = []
	for i in m:
		var sx := 0.0
		var sy := 0.0
		for k in range(-1, 2):
			var q := i + k
			if loop:
				q = (q + m) % m
			elif q < 0 or q >= m:
				continue
			sx += sin(raw[q])
			sy += cos(raw[q])
		hd.append(fposmod(rad_to_deg(atan2(sx, sy)), 360.0))
	if loop:
		hd.append(hd[0])
	var d := {"version": "1.0", "ds_m": 10.0, "n": n, "length_m": length, "type": "loop" if loop else "open",
		"lat": [], "lon": [], "alt_m": [], "x": Array(xs), "z": Array(zs), "grade_pct": [], "heading_deg": hd}
	for i in n:
		d["lat"].append(48.9)
		d["lon"].append(7.1)
		d["alt_m"].append(200.0)
		d["grade_pct"].append(0.0)
	var route = RouteDataScript.new()
	_check(route.load_route_dict(d), "carré %s chargé (%d points, %.0f m)" % ["en boucle" if loop else "ouvert", n, length])
	return route


func _run() -> void:
	var route = _square(true)
	var corner_s := SIDE_M   # deuxième coin, à s ≈ 300 m
	var v := 30.0 / 3.6
	# 1. Crabe : écart entre le cap affiché et la direction réellement suivie par le vélo.
	var crab_old := 0.0
	var crab_new := 0.0
	var lane_gap := 0.0
	var jump_yaw := 0.0
	var jump_roll := 0.0
	var jump_pos := 0.0
	var roll_min := 0.0
	var prev: Dictionary = RiderPose.pose(route, corner_s - 40.0, LANE_M, v)
	var s := corner_s - 40.0 + 0.1
	while s < corner_s + 40.0:
		var cur: Dictionary = RiderPose.pose(route, s, LANE_M, v)
		var nxt: Dictionary = RiderPose.pose(route, s + 0.1, LANE_M, v)
		var moved := RiderPose.chord_heading(prev["pos"], nxt["pos"], cur["yaw"])
		crab_new = maxf(crab_new, absf(rad_to_deg(_wrap(float(cur["yaw"]) - moved))))
		var a := RiderPose.lane_point(route, s - 0.1, LANE_M)
		var b := RiderPose.lane_point(route, s + 0.1, LANE_M)
		var old_heading := deg_to_rad(route.sample_heading_deg(s))
		crab_old = maxf(crab_old, absf(rad_to_deg(_wrap(old_heading - RiderPose.chord_heading(a, b, old_heading)))))
		lane_gap = maxf(lane_gap, (cur["pos"] as Vector3).distance_to(RiderPose.lane_point(route, s, LANE_M)))
		jump_yaw = maxf(jump_yaw, absf(rad_to_deg(_wrap(float(cur["yaw"]) - float(prev["yaw"])))))
		jump_roll = maxf(jump_roll, absf(rad_to_deg(float(cur["roll"]) - float(prev["roll"]))))
		jump_pos = maxf(jump_pos, (cur["pos"] as Vector3).distance_to(prev["pos"]))
		roll_min = minf(roll_min, rad_to_deg(float(cur["roll"])))
		prev = cur
		s += 0.1
	_check(crab_old > 20.0, "ancien cap (colonne heading_deg) : crabe de %.1f° sur l'angle droit (défaut constaté)" % crab_old)
	_check(crab_new < 3.0, "pose CY1 : le vélo regarde où il va (crabe au plus %.1f°)" % crab_new)
	_check(lane_gap < 0.9, "trajectoire lissée : au plus %.2f m de la voie (coupe le virage, < 0,9 m)" % lane_gap)
	_check(jump_pos < 0.15 and jump_yaw < 2.0 and jump_roll < 1.5,
		"continue tous les 10 cm : position %.3f m, cap %.2f°, roulis %.2f°" % [jump_pos, jump_yaw, jump_roll])
	_check(roll_min < -20.0 and roll_min >= -RiderPose.LEAN_MAX_DEG - 0.01,
		"30 km/h dans l'angle droit à droite : penché à droite jusqu'à %.1f° (borné à %.0f°)" % [roll_min, RiderPose.LEAN_MAX_DEG])
	# 2. Ligne droite : rien ne change par rapport à la voie, vélo droit dans l'axe.
	var mid: Dictionary = RiderPose.pose(route, SIDE_M * 1.5, LANE_M, v)
	var lane := RiderPose.lane_point(route, SIDE_M * 1.5, LANE_M)
	_check((mid["pos"] as Vector3).distance_to(lane) < 0.01 and absf(rad_to_deg(float(mid["roll"]))) < 0.1
		and absf(rad_to_deg(_wrap(float(mid["yaw"]) - PI))) < 0.1,
		"ligne droite : dans la voie, cap 180°, roulis nul")
	# 3. Arrêté au milieu du virage : vélo droit.
	var stopped: Dictionary = RiderPose.pose(route, corner_s, LANE_M, 0.0)
	_check(absf(float(stopped["roll"])) < 1e-6, "arrêté dans le virage : roulis nul")
	# 4. Virage à gauche (même carré parcouru… vu d'un écart à gauche) : signe du roulis par la courbure.
	_check(RiderPose.lean_roll(v, -0.1) > 0.0 and RiderPose.lean_roll(v, 0.1) < 0.0,
		"virage à gauche penché à gauche (roulis > 0), à droite penché à droite")
	# 5. Piste relevée : à la vitesse de course, presque perpendiculaire au relèvement ; borné à ± 30° de la piste.
	var bank := deg_to_rad(42.0)
	var race := rad_to_deg(RiderPose.lean_roll(15.0, -1.0 / 25.0, bank))
	_check(absf(race - 42.5) < 0.5, "virage relevé de 42° à 54 km/h (R 25 m) : roulis %.1f° (équilibre 42,5°)" % race)
	_check(is_equal_approx(rad_to_deg(RiderPose.lean_roll(0.0, 0.0, bank)), 12.0),
		"arrêté sur 42° de relèvement : roulis 12° (relèvement − 30°)")
	# 6. Parcours ouvert : grille de départ tout droit derrière le départ, sans tassement aux bouts.
	var open_route = _square(false)
	var p0 := RiderPose.lane_point(open_route, 0.0, LANE_M)
	var h0 := deg_to_rad(open_route.sample_heading_deg(0.0))
	var fwd := Vector3(sin(h0), 0.0, -cos(h0))
	var behind: Dictionary = RiderPose.pose(open_route, -6.0, LANE_M, 0.0)
	_check((behind["pos"] as Vector3).distance_to(p0 - fwd * 6.0) < 0.01, "grille de départ : 6 m derrière le départ, dans l'axe")
	var start: Dictionary = RiderPose.pose(open_route, 0.0, LANE_M, 0.0)
	_check((start["pos"] as Vector3).distance_to(p0) < 0.01, "au départ : posé sur la ligne (pas d'avance de la moyenne)")
	var end_s: float = open_route.length_m
	var at_end: Dictionary = RiderPose.pose(open_route, end_s, LANE_M, 0.0)
	_check((at_end["pos"] as Vector3).distance_to(RiderPose.lane_point(open_route, end_s, LANE_M)) < 0.05,
		"à l'arrivée : posé sur la ligne (coin à 3 m derrière)")
	# 7 bis. Point rapide de route_data (sample_xyzh) : même point et même cap que sample().
	var worst := 0.0
	for r in [route, open_route]:
		for i in 400:
			var ps: float = -3.0 + i * 2.37
			var full: Dictionary = r.sample(ps)
			var fast: Vector4 = r.sample_xyzh(ps)
			worst = maxf(worst, Vector3(fast.x, fast.y, fast.z).distance_to(Vector3(full["x"], full["y"], full["z"])))
			worst = maxf(worst, absf(_wrap(fast.w - deg_to_rad(float(full["heading_deg"])))))
	_check(worst < 1e-3, "sample_xyzh = sample (écart au plus %.6f)" % worst)
	# 6 bis. Cap des caméras : lissé, par l'écart le plus court, repris tel quel après un saut.
	var cy := RiderPose.follow_yaw(NAN, 1.0, 1.0 / 60.0, 0.35)
	_check(is_equal_approx(cy, 1.0), "cap de caméra : repris tel quel au premier appel")
	var y := deg_to_rad(350.0) - TAU
	for i in 60:
		y = RiderPose.follow_yaw(y, deg_to_rad(20.0), 1.0 / 60.0, 0.35)
	_check(absf(rad_to_deg(_wrap(y - deg_to_rad(20.0)))) < 2.0 and absf(rad_to_deg(_wrap(y - deg_to_rad(350.0)))) > 25.0,
		"cap de caméra : de 350° vers 20° par le nord en 1 s (%.1f°)" % fposmod(rad_to_deg(y), 360.0))
	_check(is_equal_approx(RiderPose.follow_yaw(0.0, 2.5, 1.0 / 60.0, 0.35), 2.5), "cap de caméra : saut de plus de 90° repris tel quel")
	_check(RiderPose.follow_yaw(0.3, 0.5, 0.0, 0.35) == 0.3, "cap de caméra : pas nul, cap inchangé")
	# 7. Coût : une pose par image pour le joueur et jusqu'à 12 bots (peloton PL1).
	var t0 := Time.get_ticks_usec()
	for i in 1300:
		RiderPose.pose(route, 37.0 + i * 0.7, LANE_M, v)
	var us := float(Time.get_ticks_usec() - t0) / 1300.0
	print("[PERF] rider_pose : %.1f µs par pose, %.2f ms pour 13 cyclistes" % [us, us * 13.0 / 1000.0])
	_check(us * 13.0 < 2000.0, "13 poses par image en moins de 2 ms (%.2f ms)" % [us * 13.0 / 1000.0])
