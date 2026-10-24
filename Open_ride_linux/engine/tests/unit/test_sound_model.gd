extends SceneTree

## Tests unitaires sans écran du modèle sonore `sound_model.gd` (Lot L5).
## Lancement : godot --headless --path engine --script res://tests/unit/test_sound_model.gd

const SoundModel := preload("res://scripts/sound_model.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _state(speed_kmh: float, power_w: Variant = 150.0, paused: bool = false) -> Dictionary:
	return {
		"v": speed_kmh / 3.6,
		"power": power_w,
		"paused": paused,
		"session_state": "PAUSED" if paused else "RUNNING",
	}


# Critère 2 : Vent (silence à 0 km/h, croissant de 5 à 60 km/h, identique à 60 et 80 km/h, silence en pause)
func _test_wind() -> void:
	var sm = SoundModel.new()
	sm.on_state(_state(0.0), Vector3.ZERO, 0.0)
	var e0: Dictionary = sm.evaluate(0.0)
	_check(is_equal_approx(e0["wind"]["volume_db"], -80.0),
		"vent à 0 km/h : silence (-80 dB, obtenu %.1f dB)" % e0["wind"]["volume_db"])

	var speeds := [5.0, 15.0, 30.0, 45.0, 60.0]
	var vols: Array[float] = []
	var pitches: Array[float] = []
	for i in range(speeds.size()):
		var t := float((i + 1) * 10)
		sm.on_state(_state(speeds[i]), Vector3.ZERO, t)
		var ev: Dictionary = sm.evaluate(t)
		vols.append(float(ev["wind"]["volume_db"]))
		pitches.append(float(ev["wind"]["pitch"]))

	var strictly_inc := true
	for i in range(vols.size() - 1):
		if not (vols[i] < vols[i + 1] and pitches[i] < pitches[i + 1]):
			strictly_inc = false
	_check(strictly_inc and pitches[0] >= 0.8 and is_equal_approx(pitches[pitches.size() - 1], 1.3),
		"vent de 5 à 60 km/h : volume et pitch strictement croissants (%s)" % str(vols))

	sm.on_state(_state(80.0), Vector3.ZERO, 100.0)
	var e80: Dictionary = sm.evaluate(100.0)
	_check(is_equal_approx(e80["wind"]["volume_db"], vols[vols.size() - 1])
		and is_equal_approx(e80["wind"]["pitch"], 1.3),
		"vent à 60 et 80 km/h : volume (%.1f dB) et pitch (%.2f) identiques" % [
			e80["wind"]["volume_db"], e80["wind"]["pitch"]])

	sm.on_state(_state(40.0, 180.0, true), Vector3.ZERO, 120.0)
	var ep: Dictionary = sm.evaluate(120.0)
	_check(is_equal_approx(ep["wind"]["volume_db"], -80.0) and not ep["freewheel"]["playing"],
		"en pause : tout est silencieux (-80 dB)")


# Critère 3 : Roue libre (30 km/h, 200 W -> 0 W : rien avant 0,5 s, playing après, arrêt dès 15 W)
func _test_freewheel() -> void:
	var sm = SoundModel.new()
	sm.on_state(_state(30.0, 200.0), Vector3.ZERO, 0.0)
	var e_init: Dictionary = sm.evaluate(0.0)
	_check(not e_init["freewheel"]["playing"], "roue libre à 200 W : inactive")

	# Passage à 0 W à t = 1,0 s
	sm.on_state(_state(30.0, 0.0), Vector3.ZERO, 1.0)
	var e_before: Dictionary = sm.evaluate(1.4)
	_check(not e_before["freewheel"]["playing"], "roue libre après 0,4 s à 0 W (< 0,5 s) : inactive")

	sm.on_state(_state(30.0, 0.0), Vector3.ZERO, 1.55)
	var e_after: Dictionary = sm.evaluate(1.55)
	_check(bool(e_after["freewheel"]["playing"]), "roue libre après 0,55 s à 0 W (≥ 0,5 s) : active (playing = true)")

	# Remontée à 15 W (> 10 W) -> arrêt immédiat
	sm.on_state(_state(30.0, 15.0), Vector3.ZERO, 2.0)
	var e_stop: Dictionary = sm.evaluate(2.0)
	_check(not e_stop["freewheel"]["playing"], "roue libre dès 15 W (> 10 W) : arrêt immédiat")

	# Vitesse <= 5 km/h : pas de roue libre même après 1 s à 0 W
	sm.on_state(_state(4.0, 0.0), Vector3.ZERO, 3.0)
	sm.on_state(_state(4.0, 0.0), Vector3.ZERO, 4.0)
	var e_slow: Dictionary = sm.evaluate(4.0)
	_check(not e_slow["freewheel"]["playing"], "roue libre à 4 km/h (≤ 5 km/h) : inactive")


# Critère 4 : Points d'intérêt (hystérésis 300 m / 330 m, oscillation 299-320 m, max 4 plus proches)
func _test_pois_hysteresis_and_cap() -> void:
	var sm = SoundModel.new()
	sm.set_pois([
		{"id": "bell_1", "kind": "church_bell", "x": 0.0, "y": 0.0, "z": 0.0, "radius_m": 300.0},
		{"id": "unk_1", "kind": "inconnu_spatial", "x": 0.0, "y": 0.0, "z": 0.0, "radius_m": 500.0},
	])

	# Approche depuis 350 m -> 299 m
	sm.on_state(_state(25.0), Vector3(350.0, 0.0, 0.0), 0.0)
	var ev0: Dictionary = sm.evaluate(0.0)
	_check(ev0["pois"].is_empty() and ev0["events"].is_empty(), "POI à 350 m (> 300 m) : inaudible")

	sm.on_state(_state(25.0), Vector3(299.0, 0.0, 0.0), 1.0)
	var ev_in: Dictionary = sm.evaluate(1.0)
	_check(ev_in["pois"].size() == 1 and ev_in["events"].size() == 1
		and ev_in["events"][0]["type"] == "entered" and ev_in["events"][0]["id"] == "bell_1",
		"POI à 299 m (≤ 300 m) : un seul événement entered reçu")

	# Oscillation entre 299 et 320 m (sous 1,1 × 300 = 330 m) : aucun nouvel événement
	var osc_events := 0
	for x_pos in [310.0, 320.0, 299.0, 325.0, 305.0]:
		sm.on_state(_state(25.0), Vector3(x_pos, 0.0, 0.0), 2.0)
		var ev_osc: Dictionary = sm.evaluate(2.0)
		osc_events += (ev_osc["events"] as Array).size()
	_check(osc_events == 0, "oscillation entre 299 et 325 m (< 330 m) : 0 nouvel événement")

	# Éloignement à 340 m (> 330 m) -> un seul left
	sm.on_state(_state(25.0), Vector3(340.0, 0.0, 0.0), 3.0)
	var ev_out: Dictionary = sm.evaluate(3.0)
	_check(ev_out["pois"].is_empty() and ev_out["events"].size() == 1
		and ev_out["events"][0]["type"] == "left" and ev_out["events"][0]["id"] == "bell_1",
		"POI à 340 m (> 330 m) : un seul événement left reçu")

	# 6 points audibles -> 4 rendus, les plus proches d'abord
	var six := []
	var dists := [90.0, 20.0, 60.0, 10.0, 40.0, 75.0]
	for i in range(6):
		six.append({"id": "p_%d" % int(dists[i]), "kind": "river", "x": dists[i], "y": 0.0, "z": 0.0, "radius_m": 200.0})
	sm.set_pois(six)
	sm.on_state(_state(20.0), Vector3.ZERO, 10.0)
	var ev6: Dictionary = sm.evaluate(10.0)
	var got_ids := []
	for p in ev6["pois"]:
		got_ids.append(p["id"])
	_check(got_ids == ["p_10", "p_20", "p_40", "p_60"],
		"6 POI audibles : 4 rendus, les plus proches d'abord (%s)" % str(got_ids))


# Critère 5 : Lissage (entre deux évaluations espacées de 0,1 s, aucun volume ne varie de plus de 1,2 dB)
func _test_slew_rate() -> void:
	var sm = SoundModel.new()
	sm.set_pois([{"id": "bell", "kind": "church_bell", "x": 0.0, "y": 0.0, "z": 0.0, "radius_m": 300.0}])
	sm.on_state(_state(0.0, 200.0), Vector3(100.0, 0.0, 0.0), 0.0)
	var prev: Dictionary = sm.evaluate(0.0)

	# Saut brutal : vitesse 0 -> 60 km/h, puissance 0 W depuis > 0,5 s, puis pause
	var max_delta := 0.0
	for step in range(1, 30):
		var t := float(step) * 0.1
		var spd := 60.0 if step < 15 else 0.0
		var pwr := 0.0 if step < 15 else 250.0
		var pos := Vector3(10.0 if step < 15 else 290.0, 0.0, 0.0)
		sm.on_state(_state(spd, pwr), pos, t)
		var cur: Dictionary = sm.evaluate(t)
		var dw := absf(float(cur["wind"]["volume_db"]) - float(prev["wind"]["volume_db"]))
		var df := absf(float(cur["freewheel"]["volume_db"]) - float(prev["freewheel"]["volume_db"]))
		var dp := absf(float(cur["pois"][0]["volume_db"]) - float(prev["pois"][0]["volume_db"]))
		max_delta = maxf(max_delta, maxf(dw, maxf(df, dp)))
		prev = cur
	_check(max_delta <= 1.2 + 1e-4,
		"lissage à 12 dB/s : variation max sur un pas de 0,1 s = %.4f dB (≤ 1,2 dB)" % max_delta)


# Critère 6 : Déterminisme
func _test_determinism() -> void:
	var run_seq := func() -> Array:
		var m = SoundModel.new()
		m.set_pois([{"id": "c1", "kind": "church_bell", "x": 100.0, "y": 0.0, "z": 0.0, "radius_m": 150.0}])
		var snaps := []
		for i in range(10):
			var t := float(i) * 0.2
			m.on_state(_state(float(i * 6), 0.0 if i >= 3 else 180.0), Vector3(float(i * 20), 0.0, 0.0), t)
			snaps.append(m.evaluate(t))
		return snaps
	var a: Array = run_seq.call()
	var b: Array = run_seq.call()
	_check(str(a) == str(b), "déterminisme : la même suite de trames donne exactement la même suite de sorties")


func _init() -> void:
	_test_wind()
	_test_freewheel()
	_test_pois_hysteresis_and_cap()
	_test_slew_rate()
	_test_determinism()
	print("test_sound_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
