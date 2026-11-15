extends SceneTree

## Tests sans écran du décor vivant à rebours (lot N23) : après un demi-tour (lot N17), la circulation
## (traffic_model.gd) et les cyclistes du décor (road_cyclists_model.gd) roulent sur le parcours retourné
## (route_mirror.gd, u = L - s) : de nouveaux véhicules et cyclistes viennent encore, ceux déjà là ne sautent pas,
## leurs poses sont celles du parcours, retournées. Jumeau de core/tests/test_decor_rebours.py.
## Lancement : godot --headless --path engine --script res://tests/unit/test_decor_rebours.gd

const TrafficModel := preload("res://scripts/traffic_model.gd")
const RoadCyclistsModel := preload("res://scripts/road_cyclists_model.gd")
const RouteMirror := preload("res://scripts/route_mirror.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")

const LENGTH_M := 30000.0
const DT := 0.1
const V_MPS := 8.3

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Route droite vers l'est, en montée de 3 % jusqu'à 10 km puis plate.
func _route():
	var ds := 10.0
	var n := int(LENGTH_M / ds) + 1
	var cols := {"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	var alt := 400.0
	for i in range(n):
		var s := i * ds
		var g := 3.0 if s < 10000.0 else 0.0
		cols["lat"].append(48.9)
		cols["lon"].append(7.1)
		cols["alt_m"].append(alt)
		alt += ds * g / 100.0
		cols["x"].append(s)
		cols["z"].append(0.0)
		cols["grade_pct"].append(g)
		cols["heading_deg"].append(90.0)
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": (n - 1) * ds, "type": "open"}
	d.merge(cols)
	var r = RouteDataScript.new()
	r.load_route_dict(d)
	return r


func _test_mirror(route) -> void:
	var back = RouteMirror.new(route)
	var ok := true
	for u in [0.0, 1234.5, 15000.0, LENGTH_M]:
		var a: Dictionary = back.sample(u)
		var b: Dictionary = route.sample(LENGTH_M - u)
		ok = ok and is_equal_approx(float(a["x"]), float(b["x"])) and is_equal_approx(float(a["z"]), float(b["z"])) \
			and is_equal_approx(float(a["y"]), float(b["y"])) and is_equal_approx(float(a["grade_pct"]), -float(b["grade_pct"])) \
			and is_equal_approx(float(a["heading_deg"]), fposmod(float(b["heading_deg"]) + 180.0, 360.0))
	_check(ok, "parcours retourné : même tracé, cap + 180°, pente opposée")
	_check(is_equal_approx(back.display_pitch(25000.0), -route.display_pitch(5000.0)) and route.display_pitch(5000.0) > 0.0,
		"tangage retourné : la montée de l'aller descend au retour")
	_check(is_equal_approx(RouteMirror.flip_s(LENGTH_M, RouteMirror.flip_s(LENGTH_M, 1500.0)), 1500.0), "u = L - s est sa propre réciproque")


## Aller de 1 à 15 km, demi-tour, retour jusqu'à 2 km ; retourne le nombre de véhicules tirés à l'aller et au retour.
func _traffic_out_and_back(route, rng_seed: int, out: Dictionary) -> void:
	var tm = TrafficModel.new()
	tm.configure(route, {"terrain": {"snow_line_m": 3000.0}}, [], 8, rng_seed)
	var s := 1000.0
	while s < 15000.0:
		tm.update(s, V_MPS, DT)
		s += V_MPS * DT
	var before := {}
	for v in tm.vehicles:
		before[str(v["id"])] = Vector3(float(v["s"]), float(v["dir"]), float(v["lateral"]))
	var fwd: int = tm.spawned_total
	var flipped: bool = tm.set_direction(-1)
	if not flipped or tm.set_direction(-1):
		out["flip_errors"] = int(out["flip_errors"]) + 1
	for v in tm.vehicles:   # mêmes places dans le repère du parcours
		var p: Vector3 = before[str(v["id"])]
		# Lot AS10 : celui qui doublait le cycliste vient en face ; il rejoint sa voie d'un coup, comme le cycliste
		var lat := -p.z
		if int(v["dir"]) == -1 and lat > tm.oncoming_lateral(str(v["kind"])):
			lat = tm.oncoming_lateral(str(v["kind"]))
		if not (is_equal_approx(tm.model_s(float(v["s"])), p.x) and -int(v["dir"]) == int(p.y)
				and is_equal_approx(float(v["lateral"]), lat)):
			out["jumps"] = int(out["jumps"]) + 1
	while s > 2000.0:
		var u: float = tm.model_s(s)
		tm.update(u, V_MPS, DT)
		for v in tm.vehicles:
			if absf(float(v["s"]) - u) < 20.0 and int(v["dir"]) == -1:
				out["met"] = int(out["met"]) + 1
				if float(v["lateral"]) >= 0.0:   # en face, sur sa droite à lui : la gauche du cycliste
					out["wrong_side"] = int(out["wrong_side"]) + 1
			if int(v["dir"]) == 1 and float(v["s"]) > u:
				out["ahead_same"] = int(out["ahead_same"]) + 1
		s -= V_MPS * DT
	out["fwd"] = int(out["fwd"]) + fwd
	out["back"] = int(out["back"]) + tm.spawned_total - fwd
	# Pose d'un véhicule en face à rebours : il roule vers les s croissants du parcours
	for v in tm.vehicles:
		if int(v["dir"]) == -1:
			var xf: Transform3D = tm.world_transform(v)
			var nose := -xf.basis.z   # avant vers -z local
			if nose.x <= 0.5:
				out["bad_pose"] = int(out["bad_pose"]) + 1


func _test_traffic(route) -> void:
	var out := {"flip_errors": 0, "fwd": 0, "back": 0, "jumps": 0, "met": 0, "wrong_side": 0, "ahead_same": 0, "bad_pose": 0}
	for sd in range(1, 9):
		_traffic_out_and_back(route, sd, out)
	print("circulation, 8 graines : %s" % str(out))
	_check(int(out["back"]) >= 5 and int(out["back"]) * 2 >= int(out["fwd"]),
		"véhicules tirés au retour comme à l'aller (%d contre %d ; aucun avant N23)" % [out["back"], out["fwd"]])
	_check(int(out["flip_errors"]) == 0, "demi-tour : le sens change une seule fois")
	_check(int(out["jumps"]) == 0, "au demi-tour, les véhicules déjà là restent à leur place")
	_check(int(out["met"]) > 0 and int(out["wrong_side"]) == 0, "véhicules croisés à rebours, tous de l'autre côté de l'axe")
	_check(int(out["bad_pose"]) == 0, "véhicule en face à rebours tourné vers l'est (sens du parcours)")
	var tm = TrafficModel.new()
	tm.configure(route, {}, [], 8, 3)
	tm.set_direction(-1)
	tm.set_direction(1)
	_check(tm.route == route and tm.base_route == route, "deux demi-tours : de nouveau le parcours dans son sens")


func _test_cyclists(route) -> void:
	var fwd := 0
	var back := 0
	var dirs := {}
	var kept_ok := true
	for sd in range(1, 5):
		var cm = RoadCyclistsModel.new()
		cm.configure(route, [{"start_s": 0.0, "summit_s": 10000.0}], [], 12, sd)
		var s := 1000.0
		while s < 12000.0:
			cm.update(s, V_MPS, DT)
			s += V_MPS * DT
		fwd += cm.spawned_total
		var before := {}
		for r in cm.riders():
			before[str(r["id"])] = Vector2(float(r["s"]), float(r["lateral"]))
		var n0: int = cm.spawned_total
		cm.set_direction(-1, s)
		for r in cm.riders():
			var p: Vector2 = before[str(r["id"])]
			kept_ok = kept_ok and is_equal_approx(cm.model_s(float(r["s"])), p.x) and is_equal_approx(-float(r["lateral"]), p.y)
		kept_ok = kept_ok and cm._climbs.is_empty()
		while s > 2000.0:
			var u: float = cm.model_s(s)
			cm.update(u, V_MPS, DT)
			for r in cm.riders():
				dirs[int(r["dir"])] = true
			s -= V_MPS * DT
		back += cm.spawned_total - n0
		cm.set_direction(1, s)
		kept_ok = kept_ok and cm.route == route and cm._climbs.size() == 1
	print("cyclistes du décor, 4 graines : %d à l'aller, %d au retour" % [fwd, back])
	_check(back >= 5, "cyclistes du décor tirés au retour (%d ; aucun avant N23)" % back)
	_check(dirs.has(1) and dirs.has(-1), "à rebours, des cyclistes devant dans son sens et d'autres en face")
	_check(kept_ok, "au demi-tour, les cyclistes déjà là restent à leur place ; montées vides à rebours, rendues à l'aller")


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var route = _route()
	_test_mirror(route)
	_test_traffic(route)
	_test_cyclists(route)
	print("test_decor_rebours : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
