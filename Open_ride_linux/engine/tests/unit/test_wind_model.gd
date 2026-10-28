extends SceneTree

## Tests unitaires sans écran du modèle du vent `wind_model.gd` (Lot P4).
## Lancement : godot --headless --path engine --script res://tests/unit/test_wind_model.gd

const PerfBudget := preload("res://tests/perf_budget.gd")
const WindModel := preload("res://scripts/wind_model.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


static func _wind(speed_kmh: float, from_deg: float, head_mps := 0.0, gust := 0.0) -> Dictionary:
	return {"wind": {"speed_mps": speed_kmh / 3.6, "from_deg": from_deg, "head_mps": head_mps, "gust": gust}}


# Critère 5 : sans `wind` ni vent de thème, calme
func _test_calm() -> void:
	var m = WindModel.new()
	m.on_state({"session_state": "RUNNING"}, 0.0)
	var e: Dictionary = m.evaluate(0.0)
	e = m.evaluate(1.0)
	_check(e["strength"] == 0.0 and e["gust"] == 0.0 and e["dir"] == Vector3.ZERO,
		"sans wind ni thème : vent calme (strength %.3f)" % e["strength"])
	_check(not m.has_wire(1.0) and m.head_mps(1.0) == 0.0, "sans wind : has_wire faux, head_mps nul")


# Repère : vent du nord souffle vers le sud (+z) ; vent d'ouest vers l'est (+x)
func _test_direction() -> void:
	var m = WindModel.new()
	m.on_state(_wind(30.0, 0.0), 0.0)
	var e: Dictionary = m.evaluate(0.0)
	var d: Vector3 = e["dir"]
	_check(d.distance_to(Vector3(0, 0, 1)) < 1e-4, "vent du nord : dir = +z (vers le sud), reçu %s" % d)
	var m2 = WindModel.new()
	m2.on_state(_wind(30.0, 270.0), 0.0)
	var d2: Vector3 = m2.evaluate(0.0)["dir"]
	_check(d2.distance_to(Vector3(1, 0, 0)) < 1e-4, "vent d'ouest : dir = +x (vers l'est), reçu %s" % d2)
	# Direction lissée à 2 s : un virage de 90° du vent n'est pas immédiat, et passe par le plus court
	m.on_state(_wind(30.0, 350.0), 0.1)
	var e1: Dictionary = m.evaluate(0.1)
	var d1: Vector3 = e1["dir"]
	_check(d1.x > 0.0 and d1.x < 0.05, "passage par le nord (0 -> 350°) par le plus court chemin")


# Critère 4 : 0 à 40 km/h, 90 % en 1,2 s au plus, sans dépassement ; phase continue
func _test_strength_step_and_phase() -> void:
	var m = WindModel.new()
	m.on_state({}, 0.0)
	m.evaluate(0.0)
	var target := (40.0 / 3.6) / WindModel.MAX_SPEED_MPS
	var reached_at := -1.0
	var overshoot := false
	var prev_phase := 0.0
	var max_jump := 0.0
	var monotonic := true
	var t := 0.0
	while t < 3.0:
		t += 1.0 / 60.0
		if fmod(t, 0.5) < 1.0 / 60.0:
			m.on_state(_wind(40.0, 90.0), t)
		var e: Dictionary = m.evaluate(t)
		if t > 1.0 / 60.0 + 1e-6 and reached_at < 0.0 and e["strength"] >= 0.9 * target:
			reached_at = t
		overshoot = overshoot or e["strength"] > target + 1e-6
		max_jump = maxf(max_jump, float(e["phase"]) - prev_phase)
		monotonic = monotonic and float(e["phase"]) >= prev_phase
		prev_phase = float(e["phase"])
	# La première trame arrive à t ≈ 0,5 s : la montée se mesure depuis cette trame.
	_check(reached_at > 0.0 and reached_at - 0.5 <= 1.2,
		"0 -> 40 km/h : 90 %% atteint en %.2f s après la trame (≤ 1,2 s)" % (reached_at - 0.5))
	_check(not overshoot, "0 -> 40 km/h : pas de dépassement de la cible")
	_check(monotonic, "phase croissante sur toute la montée")
	_check(max_jump <= WindModel.PHASE_RATE_MAX / 60.0 + 1e-6,
		"phase continue : saut maximal %.4f s par image" % max_jump)


# Le vent du core expire après 2 s ; le vent du thème prend le relais
func _test_wire_timeout_and_theme() -> void:
	var m = WindModel.new()
	m.set_theme_wind({"speed_kmh": 12, "from_deg": 225, "gust_pct": 20})
	m.on_state(_wind(30.0, 0.0, 8.0), 0.0)
	_check(m.has_wire(1.9) and m.head_mps(1.9) == 8.0, "vent du core gardé 1,9 s après la trame")
	_check(not m.has_wire(2.1) and m.head_mps(2.1) == 0.0, "vent du core expiré après 2 s")
	var e: Dictionary
	for i in range(600):
		e = m.evaluate(2.1 + i * 0.05)
	var kmh := float(e["strength"]) * 60.0
	_check(kmh > 6.0 and kmh < 18.0, "vent du thème décoratif : %.1f km/h (12 ± 6)" % kmh)
	var d: Vector3 = e["dir"]
	_check(d.x > 0.6 and d.z < -0.6, "vent du thème du sud-ouest : souffle vers le nord-est, reçu %s" % d)


# Vent apparent : cycliste à 10 m/s plein nord, sans vent -> 10 m/s de face (+z)
func _test_apparent() -> void:
	var m = WindModel.new()
	m.evaluate(0.0)
	var a: Vector3 = m.apparent(10.0, 0.0)
	_check(a.distance_to(Vector3(0, 0, 10)) < 1e-4, "vent apparent sans vent : vitesse du cycliste, reçu %s" % a)
	var m2 = WindModel.new()
	for i in range(11):
		m2.on_state(_wind(36.0, 0.0), i * 0.5)
		m2.evaluate(i * 0.5)
	var a2: Vector3 = m2.apparent(10.0, 0.0)
	_check(absf(a2.z - 20.0) < 1e-3, "vent de face de 10 m/s + 10 m/s de vitesse : 20 m/s apparents (%.2f)" % a2.z)


# Critère 9 : coût de evaluate
func _test_cost() -> void:
	var m = WindModel.new()
	m.on_state(_wind(25.0, 300.0, 2.0, 0.4), 0.0)
	var st := {"t": 0.0}
	var cost := PerfBudget.frame_cost(func():
		m.evaluate(st["t"])
		st["t"] += 0.0167, 2000, 50)
	_check(PerfBudget.check("wind_evaluate", cost["median_ms"]), "evaluate : %.4f ms par appel" % cost["median_ms"])


func _init() -> void:
	_test_calm()
	_test_direction()
	_test_strength_step_and_phase()
	_test_wire_timeout_and_theme()
	_test_apparent()
	_test_cost()
	print("test_wind_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
