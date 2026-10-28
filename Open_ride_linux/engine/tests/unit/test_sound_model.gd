extends SceneTree

## Tests unitaires sans écran du modèle sonore `sound_model.gd` (Lot L5, Lot P10 : vent dans l'air,
## roue libre à la cadence, rythme du cliquet, « clac » de reprise). Courbe de volume du vent revue par
## P10 (logarithmique en vitesse dans l'air) : les tests L5 vérifient sa forme, pas ses valeurs.
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
	_check(strictly_inc and pitches[0] >= SoundModel.WIND_PITCH_MIN and is_equal_approx(pitches[pitches.size() - 1], SoundModel.WIND_PITCH_MAX),
		"vent de 5 à 60 km/h : volume et pitch strictement croissants (%s)" % str(vols))

	sm.on_state(_state(80.0), Vector3.ZERO, 100.0)
	var e80: Dictionary = sm.evaluate(100.0)
	_check(is_equal_approx(e80["wind"]["volume_db"], vols[vols.size() - 1])
		and is_equal_approx(e80["wind"]["pitch"], SoundModel.WIND_PITCH_MAX),
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


func _wstate(speed_kmh: float, head_kmh: float, extra: Dictionary = {}) -> Dictionary:
	var st := _state(speed_kmh, 150.0)
	st["wind"] = {"speed_mps": absf(head_kmh) / 3.6, "from_deg": 0.0, "head_mps": head_kmh / 3.6, "gust": 0.0}
	st.merge(extra, true)
	return st


# Lot P10, critère 2 : vent selon la vitesse dans l'air
func _test_air_speed_wind() -> void:
	var a = SoundModel.new()
	a.on_state(_wstate(30.0, 15.0), Vector3.ZERO, 0.0)
	var with_head: float = a.evaluate(0.0)["wind"]["volume_db"]
	var b = SoundModel.new()
	b.on_state(_state(45.0), Vector3.ZERO, 0.0)
	var still_45: float = b.evaluate(0.0)["wind"]["volume_db"]
	_check(absf(with_head - still_45) <= 0.5,
		"30 km/h + 15 km/h de face (%.2f dB) = 45 km/h sans vent (%.2f dB) à 0,5 dB près" % [with_head, still_45])

	var c = SoundModel.new()
	c.on_state(_wstate(30.0, -30.0), Vector3.ZERO, 0.0)
	var tail: Dictionary = c.evaluate(0.0)
	_check(float(tail["wind"]["volume_db"]) <= SoundModel.WIND_MIN_MOVING_DB + 0.01
		and is_equal_approx(float(tail["wind"]["air_kmh"]), 0.0),
		"30 km/h avec 30 km/h de dos : vent quasi muet (%.1f dB)" % tail["wind"]["volume_db"])

	var d = SoundModel.new()
	d.on_state(_state(10.0), Vector3.ZERO, 0.0)
	var v10: float = d.evaluate(0.0)["wind"]["volume_db"]
	d.on_state(_state(50.0), Vector3.ZERO, 1.0)
	d.evaluate(1.0)
	d.on_state(_state(50.0), Vector3.ZERO, 10.0)
	var v50: float = d.evaluate(10.0)["wind"]["volume_db"]
	_check(v10 < -40.0 and v50 > -18.0 and v50 < -12.0, "10 km/h dans l'air : %.1f dB (à peine audible), 50 km/h : %.1f dB (retour de recette P16 : -15 dB environ)" % [v10, v50])

	# Rafale : ± 3 dB et ± 5 % de hauteur au plus ; sans objet wind depuis 2 s, retour au vent nul
	var e = SoundModel.new()
	var lo := INF
	var hi := -INF
	var p_lo := INF
	var p_hi := -INF
	for i in range(61):
		var t := 10.0 + i * 0.05
		var st := _wstate(30.0, 0.0)
		st["wind"]["gust"] = 1.0
		e.on_state(st, Vector3.ZERO, t)
		var ev: Dictionary = e.evaluate(t)
		lo = minf(lo, ev["wind"]["volume_db"])
		hi = maxf(hi, ev["wind"]["volume_db"])
		p_lo = minf(p_lo, ev["wind"]["pitch"])
		p_hi = maxf(p_hi, ev["wind"]["pitch"])
	var base := SoundModel._target_wind_db(30.0, 30.0, false)
	var base_p := SoundModel._target_wind_pitch(30.0, 30.0, false)
	_check(hi - base <= 3.01 and base - lo <= 3.01 and hi - lo > 2.0
		and p_hi <= base_p * 1.0501 and p_lo >= base_p * 0.9499,
		"rafale pleine : volume de %.1f à %.1f dB autour de %.1f dB, hauteur de %.3f à %.3f" % [lo, hi, base, p_lo, p_hi])
	e.on_state(_state(30.0), Vector3.ZERO, 12.5)
	e.on_state(_state(30.0), Vector3.ZERO, 15.5)
	_check(is_equal_approx(e.air_speed_kmh(15.5), 30.0), "plus d'objet wind depuis plus de 2 s : vitesse dans l'air = vitesse")


# Lot P10, critères 3 à 5 : roue libre à la cadence, rythme, « clac » de reprise
func _test_cadence_freewheel_and_clac() -> void:
	var sm = SoundModel.new()
	var st := _state(30.0, 150.0)
	st["cadence"] = 0.0
	sm.on_state(st, Vector3.ZERO, 0.0)
	sm.on_state(st, Vector3.ZERO, 0.6)
	var ev: Dictionary = sm.evaluate(0.6)
	_check(bool(ev["freewheel"]["playing"]), "cadence 0 et 150 W (capteur qui traîne) pendant 0,6 s : roue libre active")

	var st80 := _state(30.0, 150.0)
	st80["cadence"] = 80.0
	sm.on_state(st80, Vector3.ZERO, 0.7)
	var ev80: Dictionary = sm.evaluate(0.7)
	_check(not ev80["freewheel"]["playing"] and bool(ev80["freewheel"]["clac"]),
		"cadence 80 tr/min : roue libre inactive, un « clac » de reprise")
	var clacs := 0
	for i in range(50):
		sm.on_state(st80, Vector3.ZERO, 0.8 + i * 0.1)
		if bool(sm.evaluate(0.8 + i * 0.1)["freewheel"]["clac"]):
			clacs += 1
	_check(clacs == 0, "pédalage continu pendant 5 s : aucun « clac » (%d)" % clacs)

	var c36 := SoundModel.freewheel_clicks_per_s(36.0)
	var c18 := SoundModel.freewheel_clicks_per_s(18.0)
	_check(absf(c36 - 171.0) <= 171.0 * 0.02 and is_equal_approx(c18, c36 / 2.0),
		"rythme : %.1f coups/s à 36 km/h (171 ± 2 %%), %.1f à 18 km/h" % [c36, c18])

	# Roue libre puis pause : silence immédiat, pas de « clac » ; volume plus fort à haute vitesse
	var m = SoundModel.new()
	m.on_state(_state(40.0, 0.0), Vector3.ZERO, 0.0)
	m.on_state(_state(40.0, 0.0), Vector3.ZERO, 0.6)
	var fast: Dictionary = m.evaluate(10.0)
	m.on_state(_state(10.0, 0.0), Vector3.ZERO, 10.5)
	var slow: Dictionary = m.evaluate(20.0)
	_check(float(fast["freewheel"]["volume_db"]) > float(slow["freewheel"]["volume_db"])
		and float(fast["freewheel"]["clicks_per_s"]) > float(slow["freewheel"]["clicks_per_s"]),
		"roue libre : plus forte et plus rapide à 40 km/h (%.1f dB) qu'à 10 km/h (%.1f dB)" % [
			fast["freewheel"]["volume_db"], slow["freewheel"]["volume_db"]])
	m.on_state(_state(10.0, 0.0, true), Vector3.ZERO, 20.05)
	var ep: Dictionary = m.evaluate(20.05)
	m.on_state(_state(10.0, 200.0, true), Vector3.ZERO, 20.1)
	var ep2: Dictionary = m.evaluate(20.1)
	_check(is_equal_approx(float(ep["freewheel"]["volume_db"]), SoundModel.SILENCE_DB)
		and is_equal_approx(float(ep["wind"]["volume_db"]), SoundModel.SILENCE_DB)
		and not ep2["freewheel"]["clac"],
		"pause pendant la roue libre : silence immédiat (0,05 s), aucun « clac »")


func _test_wheel() -> void:
	var sm = SoundModel.new()
	sm.on_state(_state(50.0, 200.0), Vector3.ZERO, 0.0)
	_check(sm.evaluate(0.0)["wheel"]["kind"] == "none" and sm.evaluate(0.1)["wheel"]["volume_db"] <= -80.0, "roues ordinaires : silence")
	sm.set_wheel_kind("hum")
	var e: Dictionary = sm.evaluate(10.0)
	_check(e["wheel"]["kind"] == "hum" and absf(e["wheel"]["volume_db"] - SoundModel.WHEEL_MAX_DB) < 0.01, "roue lenticulaire à 50 km/h : ronronnement à %.1f dB" % e["wheel"]["volume_db"])
	_check(absf(e["wheel"]["pitch"] - SoundModel.WHEEL_PITCH_MAX) < 0.01, "hauteur maximale à 50 km/h")
	sm.on_state(_state(15.0, 200.0), Vector3.ZERO, 11.0)
	_check(sm.evaluate(40.0)["wheel"]["volume_db"] <= -80.0, "sous 20 km/h : silence")
	sm.set_wheel_kind("whistle")
	sm.on_state(_state(35.0, 200.0), Vector3.ZERO, 41.0)
	var w: Dictionary = sm.evaluate(80.0)
	_check(w["wheel"]["kind"] == "whistle" and w["wheel"]["volume_db"] > SoundModel.WHEEL_MIN_DB and w["wheel"]["volume_db"] < SoundModel.WHEEL_MAX_DB, "jantes hautes à 35 km/h : sifflement intermédiaire")
	sm.set_wheel_kind("inconnu")
	_check(sm.evaluate(120.0)["wheel"]["kind"] == "none", "type de roue inconnu : aucun son")


func _init() -> void:
	_test_wheel()
	_test_wind()
	_test_freewheel()
	_test_pois_hysteresis_and_cap()
	_test_slew_rate()
	_test_determinism()
	_test_air_speed_wind()
	_test_cadence_freewheel_and_clac()
	print("test_sound_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
