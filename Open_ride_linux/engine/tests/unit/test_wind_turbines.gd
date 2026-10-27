extends SceneTree

## Tests sans écran des éoliennes `wind_turbines.gd` (Lot P12) : vitesse du rotor, orientation de la
## nacelle, limite de 20 éoliennes, coût par image avec les drapeaux.
## Lancement : godot --headless --path engine --script res://tests/unit/test_wind_turbines.gd

const WindTurbines := preload("res://scripts/wind_turbines.gd")
const Flags := preload("res://scripts/flags.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _turbine(i: int, x: float, z: float) -> Dictionary:
	return {"id": "n%d" % i, "kind": "wind_turbine", "x": x, "y": 300.0, "z": z, "radius_m": 5000, "name": null, "height_m": 100.0}


## Direction vers où souffle le vent pour un vent venant de `from_deg` (convention de wind_model.gd).
func _dir(from_deg: float) -> Vector3:
	var a := deg_to_rad(from_deg + 180.0)
	return Vector3(sin(a), 0.0, -cos(a))


func _test_rotor() -> void:
	var rpms := []
	for kmh in [0.0, 9.0, 12.0, 30.0, 60.0]:
		rpms.append(WindTurbines.rotor_rpm(kmh / 60.0))
	_check(rpms[0] == 0.0 and rpms[1] == 0.0 and rpms[2] > 0.0 and rpms[2] < rpms[3] and rpms[3] < rpms[4]
		and is_equal_approx(rpms[4], 17.0),
		"rotor : arrêté sous 10 km/h, puis croissant jusqu'à 17 tr/min à 60 km/h (%s)" % str(rpms))
	var t = WindTurbines.new()
	root.add_child(t)
	t.set_points([_turbine(1, 0.0, -500.0)])
	var wind := {"dir": _dir(270.0), "strength": 0.5, "gust": 0.0}
	var a0: float = t.turbine_state(0)["rotor"]
	for i in range(60):
		t.update(wind, Vector3.ZERO, 1.0 / 60.0)
	var turned := fposmod(float(t.turbine_state(0)["rotor"]) - a0, TAU)
	_check(absf(turned - 11.0 * TAU / 60.0) < 1e-3, "vent de 30 km/h : rotor à 11 tr/min (%.4f rad en 1 s)" % turned)
	t.queue_free()


func _test_yaw() -> void:
	var t = WindTurbines.new()
	root.add_child(t)
	t.set_points([_turbine(1, 0.0, -500.0)])
	var west := {"dir": _dir(270.0), "strength": 0.4, "gust": 0.0}
	for i in range(1200):
		t.update(west, Vector3.ZERO, 0.1)
	var target_w := WindTurbines.facing_yaw(_dir(270.0))
	_check(absf(wrapf(float(t.turbine_state(0)["yaw"]) - target_w, -PI, PI)) < 0.01, "vent d'ouest établi : nacelle face au vent")
	# Rotor face à l'ouest : son axe -z local pointe vers d'où vient le vent
	var facing := Basis(Vector3.UP, float(t.turbine_state(0)["yaw"])) * Vector3(0.0, 0.0, -1.0)
	_check(facing.dot(-_dir(270.0)) > 0.999, "le rotor regarde d'où vient le vent (%s)" % str(facing))

	var north := {"dir": _dir(0.0), "strength": 0.4, "gust": 0.0}
	var target_n := WindTurbines.facing_yaw(_dir(0.0))
	var reached_at := -1.0
	var max_rate := 0.0
	var max_acc := 0.0
	var prev: float = t.turbine_state(0)["yaw"]
	var prev_rate := 0.0
	for i in range(1, 601):
		t.update(north, Vector3.ZERO, 0.1)
		var y: float = t.turbine_state(0)["yaw"]
		var rate := absf(wrapf(y - prev, -PI, PI)) / 0.1
		max_rate = maxf(max_rate, rate)
		if i > 1:
			max_acc = maxf(max_acc, absf(rate - prev_rate) / 0.1)
		prev_rate = rate
		prev = y
		if reached_at < 0.0 and absf(wrapf(y - target_n, -PI, PI)) < deg_to_rad(5.0):
			reached_at = i * 0.1
	_check(reached_at > 0.0 and reached_at <= 60.0, "vent qui tourne de 90° : nacelle face au vent (± 5°) en %.1f s (≤ 60 s)" % reached_at)
	_check(rad_to_deg(max_rate) <= WindTurbines.YAW_MAX_DEG_S + 0.01,
		"sans à-coup : au plus %.1f °/s (limite %.0f °/s)" % [rad_to_deg(max_rate), WindTurbines.YAW_MAX_DEG_S])
	t.queue_free()


func _test_limit_and_cost() -> void:
	var t = WindTurbines.new()
	root.add_child(t)
	var n0: int = t.get_child_count()
	var pts := []
	for i in range(35):
		pts.append(_turbine(i, float(i) * 300.0, -800.0))
	pts.append({"id": "v1", "kind": "village", "x": 0.0, "y": 300.0, "z": 0.0, "radius_m": 300, "name": null})
	t.set_points(pts)
	t.update({"dir": _dir(270.0), "strength": 0.5, "gust": 0.0}, Vector3.ZERO, 0.016)
	_check(t.active_count() == 20 and t.get_child_count() == n0, "35 éoliennes : 20 affichées, aucun nœud créé")
	var far_kept := false
	for s in t._slots:
		if s["root"].visible and (s["root"].position as Vector3).x > 19.0 * 300.0 + 1.0:
			far_kept = true
	_check(not far_kept, "ce sont les 20 plus proches de la caméra")

	var f = Flags.new()
	root.add_child(f)
	var fpts := []
	for i in range(30):
		fpts.append({"id": "f%d" % i, "kind": "flag", "x": float(i) * 40.0, "y": 300.0, "z": 20.0, "radius_m": 150, "name": null})
	f.set_points(fpts)
	var total := 0
	var frames := 300
	for i in range(frames):
		var w := {"dir": _dir(270.0 + i * 0.1), "strength": 0.5, "gust": 0.2, "phase": i / 60.0}
		t.update(w, Vector3(i * 0.2, 0.0, 0.0), 1.0 / 60.0)
		f.update(w, 1.0 / 60.0)
		total += t.last_update_usec + f.last_update_usec
	var avg := total / 1000.0 / frames
	print("20 éoliennes et 30 drapeaux : %.3f ms par image" % avg)
	_check(f.visible_count() == 30, "30 drapeaux affichés")
	_check(PerfBudget.check("turbines_flags_frame", avg), "mise à jour de 20 éoliennes et 30 drapeaux en %.3f ms par image" % avg)
	t.queue_free()
	f.queue_free()


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	_test_rotor()
	_test_yaw()
	_test_limit_and_cost()
	await process_frame   # nœuds libérés avant la sortie (sinon erreurs du serveur de rendu factice)
	print("test_wind_turbines : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
