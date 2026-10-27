extends SceneTree

## Tests unitaires sans écran des fonds d'ambiance `ambience_model.gd` (Lot P9).
## Lancement : godot --headless --path engine --script res://tests/unit/test_ambience_model.gd

const AmbienceModel := preload("res://scripts/ambience_model.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _neigh(forest: float, built: float, hour: float, extra: Dictionary = {}) -> Dictionary:
	var d := {"forest_share": forest, "built_share": built, "water_dist_m": INF, "water_kind": "",
		"alt_m": 300.0, "solar_hour": hour, "rain": 0.0, "wind_strength": 0.2, "paused": false}
	d.merge(extra, true)
	return d


func _loudest(vols: Dictionary) -> String:
	var best := ""
	var best_db := -1000.0
	for b in vols:
		if float(vols[b]) > best_db:
			best_db = float(vols[b])
			best = b
	return best


## Volumes stables après 30 s au même endroit.
func _settle(m, neigh: Dictionary, t0: float = 0.0) -> Dictionary:
	var v := {}
	for i in range(1800):
		v = m.evaluate(neigh, t0 + i / 60.0)
	return v


# Critère 2 : forêt, champ, eau, nuit
func _test_landscapes() -> void:
	var m = AmbienceModel.new()
	var forest := _settle(m, _neigh(0.8, 0.0, 12.0))
	_check(_loudest(forest) == "forest_birds", "forêt à 80 %%, jour : les oiseaux dominent (%s)" % _loudest(forest))
	m.reset()
	var field := _settle(m, _neigh(0.0, 0.0, 12.0))
	_check(_loudest(field) == "field_insects", "champ à midi : les insectes dominent (%s)" % _loudest(field))
	m.reset()
	var river := _settle(m, _neigh(0.0, 0.0, 12.0, {"water_dist_m": 20.0, "water_kind": "river"}))
	_check(float(river["water_flow"]) > -30.0, "rivière à 20 m : eau audible (%.1f dB)" % river["water_flow"])
	m.reset()
	var noon := float(AmbienceModel.new().targets(_neigh(0.8, 0.0, 12.0))["forest_birds"])
	var night := float(AmbienceModel.new().targets(_neigh(0.8, 0.0, 1.0))["forest_birds"])
	_check(night <= noon - 20.0, "nuit : oiseaux %.1f dB plus bas qu'à midi (≥ 20 dB)" % (noon - night))
	var t_night := AmbienceModel.new().targets(_neigh(0.0, 0.0, 1.0))
	_check(t_night["field_insects"] == AmbienceModel.SILENCE_DB, "insectes muets la nuit")
	var rainy := AmbienceModel.new().targets(_neigh(0.8, 0.0, 12.0, {"rain": 1.0}))
	_check(rainy["forest_birds"] < noon - 10.0 and rainy["rain"] > -20.0, "pluie : oiseaux plus bas, pluie audible")
	var high := AmbienceModel.new().targets(_neigh(0.0, 0.0, 12.0, {"alt_m": 2600.0, "wind_strength": 0.8}))
	_check(high["high_wind"] > -25.0 and high["high_wind"] > AmbienceModel.new().targets(_neigh(0.0, 0.0, 12.0))["high_wind"], "altitude : vent marqué (%.1f dB)" % high["high_wind"])
	var paused := m.evaluate(_neigh(0.8, 0.0, 12.0, {"paused": true}), 100.0)
	var all_silent := true
	for i in range(120):
		paused = m.evaluate(_neigh(0.8, 0.0, 12.0, {"paused": true}), 100.0 + i / 60.0)
	for b in paused:
		all_silent = all_silent and paused[b] == AmbienceModel.SILENCE_DB
	_check(all_silent, "en pause : tout au silence en 2 s")
	var themed = AmbienceModel.new()
	themed.set_theme({"ambience": {"volume": 0.0}})
	var t0 := themed.targets(_neigh(0.8, 0.5, 12.0, {"rain": 1.0, "water_dist_m": 5.0}))
	var none := true
	for b in t0:
		none = none and t0[b] == AmbienceModel.SILENCE_DB
	_check(none, "ambience.volume = 0 : tout muet")


# Critère 3 : jamais plus de `ambience_voices` fonds audibles
func _test_voices() -> void:
	for preset in ["low", "medium", "high"]:
		var m = AmbienceModel.new()
		m.voices = QualityPresets.living(preset)["ambience_voices"]
		var worst := 0
		var rich := _neigh(0.5, 0.4, 12.0, {"water_dist_m": 10.0, "water_kind": "river", "alt_m": 2400.0,
			"rain": 0.5, "wind_strength": 0.9})
		var t := 0.0
		for k in range(6):
			var n := rich if k % 2 == 0 else _neigh(0.9, 0.0, 12.0)
			for i in range(600):
				m.evaluate(n, t)
				t += 1.0 / 60.0
				worst = maxi(worst, m.audible_count())
		_check(worst <= m.voices, "%s : au plus %d fonds audibles (relevé %d)" % [preset, m.voices, worst])
	var two = AmbienceModel.new()
	two.voices = 2
	var most := 0
	for i in range(1200):
		two.evaluate(_neigh(0.5, 0.4, 12.0, {"water_dist_m": 10.0, "water_kind": "river", "rain": 0.5}), i / 60.0)
		most = maxi(most, two.audible_count())
	_check(most == 2, "2 voix pour 5 fonds possibles : 2 audibles (relevé %d)" % most)


# Critère 4 : passage brusque de la forêt au champ, pas plus de 3 dB en 0,5 s
func _test_smooth() -> void:
	var m = AmbienceModel.new()
	var hist: Array = []
	var t := 0.0
	for i in range(1800):
		hist.append(m.evaluate(_neigh(1.0, 0.0, 12.0), t))
		t += 1.0 / 60.0
	for i in range(1800):
		hist.append(m.evaluate(_neigh(0.0, 0.0, 12.0), t))
		t += 1.0 / 60.0
	var worst := 0.0
	for i in range(1800 - 30, hist.size() - 30):
		for b in AmbienceModel.BEDS:
			var a := float(hist[i][b])
			var c := float(hist[i + 30][b])
			if a > AmbienceModel.SILENCE_DB and c > AmbienceModel.SILENCE_DB:
				worst = maxf(worst, absf(c - a))
	_check(worst <= 3.0, "forêt puis champ : variation max %.2f dB en 0,5 s (≤ 3 dB)" % worst)
	_check(float(hist[-1]["field_insects"]) > float(hist[-1]["forest_birds"]), "au champ, les insectes l'emportent ensuite")


# Critère 6 : cloches
func _test_bells() -> void:
	_check(AmbienceModel.bell_strikes(14.99, 15.01) == 3, "3 coups à 15 h")
	_check(AmbienceModel.bell_strikes(11.95, 12.02) == 12 and AmbienceModel.bell_strikes(23.99, 0.01) == 12,
		"12 coups à midi et à minuit")
	var none := true
	var h := 15.01
	while h < 15.99:
		none = none and AmbienceModel.bell_strikes(h, h + 0.01) == 0
		h += 0.01
	_check(none, "aucun coup hors de l'heure pleine")
	_check(AmbienceModel.bell_strikes(15.5, 14.0) == 0 and AmbienceModel.bell_strikes(NAN, 15.0) == 0,
		"horloge qui recule ou première lecture : rien")


func _test_describe_and_cost() -> void:
	var rider := Vector2(0, 0)
	var forest := PackedVector2Array([Vector2(-200, -200), Vector2(200, -200), Vector2(200, 0), Vector2(-200, 0)])
	var house := PackedVector2Array([Vector2(30, 30), Vector2(45, 30), Vector2(45, 45), Vector2(30, 45)])
	var river := {"kind": "river", "points": PackedVector2Array([Vector2(-300, 40), Vector2(300, 40)])}
	var d := AmbienceModel.describe(rider, [forest], [house], [river])
	_check(d["forest_share"] > 0.4 and d["forest_share"] < 0.65, "moitié en forêt : part %.2f" % d["forest_share"])
	_check(d["built_share"] > 0.0 and d["built_share"] < 0.1, "une maison : part bâtie %.2f" % d["built_share"])
	_check(is_equal_approx(d["water_dist_m"], 40.0) and d["water_kind"] == "river", "rivière à 40 m")
	var empty := AmbienceModel.describe(rider, [], [], [])
	_check(empty["forest_share"] == 0.0 and empty["water_dist_m"] == INF, "rien autour : aucune forêt, pas d'eau")
	var m = AmbienceModel.new()
	var n := _neigh(0.5, 0.2, 12.0, {"water_dist_m": 30.0, "water_kind": "stream"})
	var t0 := Time.get_ticks_usec()
	for i in range(5000):
		m.evaluate(n, i / 60.0)
	var ms := (Time.get_ticks_usec() - t0) / 1000.0 / 5000.0
	_check(ms < 0.1, "evaluate : %.4f ms (< 0,1 ms)" % ms)


func _init() -> void:
	_test_landscapes()
	_test_voices()
	_test_smooth()
	_test_bells()
	_test_describe_and_cost()
	print("test_ambience_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
