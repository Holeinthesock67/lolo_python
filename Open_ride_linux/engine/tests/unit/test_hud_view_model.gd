extends SceneTree

## Tests sans écran du modèle de vue du HUD `hud_view_model.gd` (Lot K2).
## Lancement : godot --headless --path engine --script res://tests/unit/test_hud_view_model.gd

const HudViewModel := preload("res://scripts/hud_view_model.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const ErgViewModel := preload("res://scripts/erg_view_model.gd")
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


## Parcours synthétique : altitudes données tous les ds_m ; ligne droite (ouvert) ou cercle (boucle).
func _make_route(alts: Array, ds: float, loop := false):
	var n := alts.size()
	var length := (n - 1) * ds
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": length, "type": "loop" if loop else "open",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	var radius := length / TAU
	for i in range(n):
		var px := i * ds
		var pz := 0.0
		var heading := 90.0
		if loop:
			var ang := TAU * i / float(n - 1)
			px = radius * sin(ang)
			pz = radius * (1.0 - cos(ang))
			heading = fposmod(90.0 - rad_to_deg(ang), 360.0)
		var j := mini(i, n - 2)
		d["lat"].append(45.0)
		d["lon"].append(6.0)
		d["alt_m"].append(float(alts[i]))
		d["x"].append(px)
		d["z"].append(pz)
		d["grade_pct"].append((float(alts[j + 1]) - float(alts[j])) / ds * 100.0)
		d["heading_deg"].append(heading)
	var route = RouteDataScript.new()
	if not route.load_route_dict(d):
		printerr("parcours synthétique refusé : ", route.load_error)
	return route


## Plat sur flat1 m, montée de climb_m à grade %, puis plat sur flat2 m (pas de 10 m).
func _climb_alts(flat1: float, climb_m: float, grade: float, flat2: float) -> Array:
	var alts := []
	var total := flat1 + climb_m + flat2
	var k := 0
	while k * 10.0 <= total + 1e-6:
		var x := k * 10.0
		alts.append(500.0 + clampf(x - flat1, 0.0, climb_m) * grade / 100.0)
		k += 1
	return alts


func _test_texts() -> void:
	var cases := [
		# [nom, trame, clé, texte attendu]
		["puissance 3 s", {"power_3s": 245.3, "power": 260}, "power_text", "245 W"],
		["puissance nulle", {"power_3s": 0}, "power_text", "0 W"],
		["puissance négative", {"power_3s": -12.0}, "power_text", "0 W"],
		["puissance NaN", {"power_3s": NAN}, "power_text", "—"],
		["puissance très grande", {"power_3s": 1.0e12}, "power_text", "—"],
		["puissance absente, repli sur power", {"power": 180.4}, "power_text", "180 W"],
		["vitesse", {"v": 4.62}, "speed_text", "16.6 km/h"],
		["vitesse négative", {"v": -1.0}, "speed_text", "0.0 km/h"],
		["vitesse infinie", {"v": INF}, "speed_text", "—"],
		["cadence", {"cadence": 79.4}, "cadence_text", "79 rpm"],
		["cadence nulle (null)", {"cadence": null}, "cadence_text", "—"],
		["cardio", {"hr": 151}, "hr_text", "151 bpm"],
		["cardio null", {"hr": null}, "hr_text", "—"],
		["cardio à 0", {"hr": 0}, "hr_text", "—"],
		["braquet", {"gear": 12, "gears_total": 24}, "gear_text", "12/24"],
		["braquet hors bornes", {"gear": 0, "gears_total": 24}, "gear_text", "—"],
		["braquet au-delà du total", {"gear": 30, "gears_total": 24}, "gear_text", "—"],
		["pente positive", {"grade": 7.84}, "grade_text", "+7.8 %"],
		["pente négative", {"grade": -3.21}, "grade_text", "-3.2 %"],
		["pente presque nulle", {"grade": -0.04}, "grade_text", "0.0 %"],
		["pente aberrante", {"grade": 250.0}, "grade_text", "—"],
		["distance", {"s": 12873.4}, "distance_text", "12.87 km"],
		["distance nulle", {"s": 0.0}, "distance_text", "0.00 km"],
		["temps", {"t": 3725.9}, "elapsed_text", "1:02:05"],
		["temps nul", {"t": 0}, "elapsed_text", "0:00:00"],
		["temps négatif", {"t": -5.0}, "elapsed_text", "0:00:00"],
		["temps NaN", {"t": NAN}, "elapsed_text", "—"],
	]
	var text_keys := ["power_text", "speed_text", "cadence_text", "hr_text", "gear_text", "grade_text",
		"distance_text", "elapsed_text"]
	for case in cases:
		var vm = HudViewModel.new()
		vm.on_state(case[1], 10.0)
		var out: Dictionary = vm.evaluate(10.5)
		_check(out[case[2]] == case[3], "texte %s : « %s » (attendu « %s »)" % [case[0], out[case[2]], case[3]])
		var empty := false
		for k in text_keys:
			empty = empty or str(out[k]) == ""
		if empty:
			_check(false, "texte %s : un texte est vide" % case[0])
	var vm0 = HudViewModel.new()
	var none: Dictionary = vm0.evaluate(1.0)
	var all_dash := true
	for k in text_keys:
		all_dash = all_dash and none[k] == "—"
	_check(all_dash and not none["has_state"], "avant toute trame : tous les textes valent « — »")
	var vm1 = HudViewModel.new()
	vm1.on_state({"power_3s": 200, "t": 12.0}, 5.0)
	var e1: Dictionary = vm1.evaluate(5.25)
	_check(absf(e1["age_s"] - 0.25) < 1e-9 and e1["power_w"] == 200.0, "champs bruts et âge de la trame")


func _test_distance_on_loop() -> void:
	var vm = HudViewModel.new()
	vm.on_state({"s": 1900.0, "route_length_m": 2000.0}, 0.0)
	vm.on_state({"s": 100.0, "route_length_m": 2000.0}, 1.0)
	_check(vm.evaluate(1.0)["distance_text"] == "2.10 km", "boucle : s ramené à 100 m après 1 900 m → 2,10 km parcourus")
	vm.on_state({"s": 4100.0, "route_length_m": 2000.0}, 2.0)
	var vm2 = HudViewModel.new()
	vm2.on_state({"s": 4100.0, "route_length_m": 2000.0}, 0.0)
	_check(vm2.evaluate(0.0)["distance_text"] == "4.10 km", "boucle : s cumulé par le core (2 tours) → 4,10 km")


func _test_grade_classes() -> void:
	var expect := {-5.0: "descent", -2.0: "flat", 0.0: "flat", 1.99: "flat", 2.0: "climb", 5.9: "climb",
		6.0: "steep", 10.0: "steep", 10.1: "wall"}
	var ok := true
	for g in expect.keys():
		ok = ok and HudViewModel.grade_class(g) == expect[g]
	_check(ok, "classes de pente : seuils −2, 2, 6 et 10 %")


func _test_profile_open() -> void:
	var route = RouteDataScript.new()
	if not route.load_world_dir("res://demo/demo.world"):
		_check(false, "demo.world chargé : " + route.load_error)
		return
	var vm = HudViewModel.new()
	for s in [0.0, 2500.0, route.length_m - 50.0]:
		var p: Dictionary = vm.profile(route, s)
		var pts: PackedVector2Array = p["points"]
		var max_err := 0.0
		for c in range(pts.size()):
			var expected: float = route.sample(s + pts[c].x)["alt_m"]
			max_err = maxf(max_err, absf(p["alts"][c] - expected))
			max_err = maxf(max_err, absf(pts[c].y - expected))
		_check(pts.size() == 120 and max_err <= 0.01,
			"profil ouvert à s = %.0f : 120 colonnes, altitudes = route.sample à %.4f m près" % [s, max_err])
		var expect_from := maxf(-500.0, -s)
		var expect_to := minf(4500.0, route.length_m - s)
		_check(absf(pts[0].x - expect_from) < 1e-6 and absf(pts[pts.size() - 1].x - expect_to) < 1e-6,
			"profil ouvert à s = %.0f : fenêtre [%.0f ; %.0f] m (tronquée aux extrémités)" % [s, expect_from, expect_to])
		var smin := INF
		var smax := -INF
		for v in p["s_abs"]:
			smin = minf(smin, v)
			smax = maxf(smax, v)
		_check(smin >= 0.0 and smax <= route.length_m, "profil ouvert à s = %.0f : aucune position hors du parcours" % s)
		var m: int = p["marker_index"]
		var step := (expect_to - expect_from) / 119.0
		_check(m >= 0 and absf(pts[m].x) <= step * 0.5 + 1e-6, "profil ouvert à s = %.0f : repère en colonne %d" % [s, m])
		var lo := INF
		var hi := -INF
		for a in p["alts"]:
			lo = minf(lo, a)
			hi = maxf(hi, a)
		var margin := maxf(hi - lo, 1.0) * 0.05
		_check(absf(p["alt_min"] - (lo - margin)) < 1e-6 and absf(p["alt_max"] - (hi + margin)) < 1e-6,
			"profil ouvert à s = %.0f : alt_min et alt_max avec marge de 5 %%" % s)
	# Mesure : 100 appels sur 120 colonnes.
	var avg_ms := PerfBudget.measure_ms(func():
		for i in range(100):
			vm.profile(route, 25.0 * i), 3, 1) / 100.0
	print("Mesure : profile (120 colonnes) en %.3f ms par appel" % avg_ms)
	_check(PerfBudget.check("hud_profile_120", avg_ms), "profile dans le budget (%.3f ms)" % avg_ms)


func _test_profile_loop() -> void:
	# Boucle de 2 000 m : montée régulière puis descente, pour que l'arrivée soit à la même altitude.
	var alts := []
	for i in range(201):
		var x := i * 10.0
		alts.append(300.0 + (x * 0.04 if x <= 1000.0 else (2000.0 - x) * 0.04))
	var route = _make_route(alts, 10.0, true)
	var vm = HudViewModel.new()
	var p: Dictionary = vm.profile(route, 1900.0, 500.0, 1000.0, 151)
	var pts: PackedVector2Array = p["points"]
	var step := 1500.0 / 150.0
	var max_jump := 0.0
	var crossed := false
	for c in range(1, pts.size()):
		max_jump = maxf(max_jump, absf(p["alts"][c] - p["alts"][c - 1]))
		crossed = crossed or p["s_abs"][c] < p["s_abs"][c - 1]
	_check(crossed and max_jump <= step * 0.04 + 1e-6,
		"profil sur boucle : fenêtre traverse l'arrivée sans saut (écart max %.3f m pour %.0f m)" % [max_jump, step])
	var max_err := 0.0
	for c in range(pts.size()):
		max_err = maxf(max_err, absf(p["alts"][c] - route.sample(1900.0 + pts[c].x)["alt_m"]))
	_check(absf(pts[0].x + 500.0) < 1e-6 and absf(pts[pts.size() - 1].x - 1000.0) < 1e-6 and max_err <= 0.01,
		"profil sur boucle : fenêtre complète [−500 ; 1 000] m, altitudes exactes")
	var classes: PackedStringArray = p["grade_class"]
	_check(classes[0] == "descent" and classes[classes.size() - 1] == "climb",
		"profil sur boucle : classes de pente par colonne (descente avant l'arrivée, montée après)")


func _test_next_climb() -> void:
	var route = _make_route(_climb_alts(1000.0, 800.0, 7.0, 1200.0), 10.0)
	var vm = HudViewModel.new()
	var c: Dictionary = vm.next_climb(route, 0.0)
	_check(not c.is_empty() and absf(c["start_m"] - 1000.0) <= 20.0 and absf(c["length_m"] - 800.0) <= 20.0
		and absf(c["avg_grade_pct"] - 7.0) <= 0.3,
		"prochaine montée depuis 0 : début %.0f m, longueur %.0f m, pente %.2f %%" % [
			c.get("start_m", -1.0), c.get("length_m", -1.0), c.get("avg_grade_pct", -1.0)])
	_check(not c.is_empty() and absf(c["gain_m"] - 56.0) <= 1.5 and not c["in_progress"],
		"prochaine montée : dénivelé %.1f m (56 attendus)" % c.get("gain_m", -1.0))
	var c2: Dictionary = vm.next_climb(route, 600.0)
	_check(not c2.is_empty() and absf(c2["start_m"] - 400.0) <= 20.0, "prochaine montée depuis 600 m : à %.0f m" % c2.get("start_m", -1.0))
	var c3: Dictionary = vm.next_climb(route, 1400.0)
	_check(not c3.is_empty() and c3["in_progress"] and absf(c3["length_m"] - 400.0) <= 20.0,
		"dans la montée à 1 400 m : reste %.0f m" % c3.get("length_m", -1.0))
	_check(vm.next_climb(route, 2000.0).is_empty(), "après la montée d'un parcours ouvert : aucune")
	var flat = _make_route(_climb_alts(1000.0, 0.0, 0.0, 1000.0), 10.0)
	_check(vm.next_climb(flat, 0.0).is_empty(), "parcours plat : aucune montée")
	var short = _make_route(_climb_alts(500.0, 200.0, 8.0, 500.0), 10.0)
	_check(vm.next_climb(short, 0.0).is_empty(), "montée de 200 m (< 300 m) : ignorée")
	var gentle = _make_route(_climb_alts(500.0, 800.0, 2.5, 500.0), 10.0)
	_check(vm.next_climb(gentle, 0.0).is_empty(), "montée à 2,5 % (< 3 %) : ignorée")
	# Boucle : montée de 400 m à 6 % placée juste après l'arrivée, cherchée depuis 1 500 m.
	var alts := []
	for i in range(201):
		var x := i * 10.0
		var a := 0.0
		if x <= 400.0:
			a = x * 0.06
		elif x <= 1600.0:
			a = 24.0 - (x - 400.0) * 0.02
		alts.append(100.0 + a)
	var loop = _make_route(alts, 10.0, true)
	var c4: Dictionary = vm.next_climb(loop, 1500.0)
	_check(not c4.is_empty() and absf(c4["start_m"] - 500.0) <= 20.0 and absf(c4["length_m"] - 400.0) <= 20.0,
		"boucle : montée trouvée après l'arrivée, à %.0f m" % c4.get("start_m", -1.0))


## Lignes du HUD de séance (main.gd) : SIM, ERG, palier à 50 W (lot O19), fréquence cardiaque.
func _test_session_lines() -> void:
	var sim := {"power": 251.6, "power_3s": 245.3, "v": 10.0, "cadence": 88, "hr": 151, "gear": 9,
		"gears_total": 24, "grade": 4.25, "grade_sent": 2.1, "s": 1234.0, "mode": "SIM", "erg": null}
	var no_erg: Dictionary = ErgViewModel.new().update(null, 0.0)
	var l: Dictionary = HudViewModel.session_lines(sim, no_erg)
	_check(l["power"] == "PUISSANCE: 252 W (3s: 245 W)", "SIM : puissance (%s)" % l["power"])
	_check(l["speed"] == "VITESSE: 36.0 km/h  [Braquet: 9/24]", "SIM : braquet (%s)" % l["speed"])
	_check(l["hr"] == "FC: 151 bpm", "fréquence cardiaque affichée (%s)" % l["hr"])
	_check(l["grade"] == "PENTE: 4.3 %  (envoyée au trainer: 2.1 %)" or l["grade"] == "PENTE: 4.2 %  (envoyée au trainer: 2.1 %)",
		"SIM : pente envoyée (%s)" % l["grade"])
	_check(l["distance"] == "DISTANCE: 1.23 km" and l["erg"] == "", "SIM : distance, pas de ligne ERG")
	sim["gear"] = 10
	_check(HudViewModel.session_lines(sim, no_erg)["speed"].contains("Braquet: 10/24"),
		"changement de braquet repris à la trame suivante")
	for hr in [null, 0, -3, NAN]:
		sim["hr"] = hr
		_check(HudViewModel.session_lines(sim, no_erg)["hr"] == "FC: —", "FC %s : « — »" % str(hr))

	var erg := {"workout_name": "Sweet spot 3x10", "block_index": 3, "block_count": 7, "block_type": "interval_on",
		"block_remaining_s": 512.0, "block_total_s": 600.0, "target_w": 238, "next_target_w": 125,
		"bias_pct": 100, "paused": false}
	var st := sim.duplicate()
	st["mode"] = "ERG"
	st["erg"] = erg
	var vm = ErgViewModel.new()
	l = HudViewModel.session_lines(st, vm.update(erg, 0.0))
	_check(l["power"].ends_with("|  CIBLE ERG: 238 W"), "ERG : cible envoyée au trainer (%s)" % l["power"])
	_check(l["speed"].contains("± = intensité en ERG"), "ERG : ± règle l'intensité (%s)" % l["speed"])
	_check(l["grade"].ends_with("(trainer en ERG)"), "ERG : pas de pente envoyée (%s)" % l["grade"])
	_check(not l["gear_shown"], "ERG : braquet sans effet, caché dans le HUD")
	_check(l["erg"].begins_with("ERG: Sweet spot 3x10 — Bloc 3 / 7  |  reste 8:32"), "ERG : ligne du bloc (%s)" % l["erg"])
	var erg2 := erg.duplicate()
	erg2["bias_pct"] = 105
	erg2["target_w"] = 250
	l = HudViewModel.session_lines(st, vm.update(erg2, 0.1))
	_check(l["power"].ends_with("CIBLE ERG: 250 W (105 %)"), "ERG : biais rafraîchi (%s)" % l["power"])
	var floor_erg := erg.duplicate()          # FreeRide d'un .zwo : palier ERG à 50 W (lot O19)
	floor_erg["target_w"] = 50
	floor_erg["bias_pct"] = 100
	l = HudViewModel.session_lines(st.merged({"erg": floor_erg}, true), ErgViewModel.new().update(floor_erg, 0.0))
	_check(l["power"].ends_with("CIBLE ERG: 50 W") and l["speed"].ends_with("± = intensité en ERG]"),
		"palier à 50 W : ERG comme les autres blocs (%s / %s)" % [l["power"], l["speed"]])
	_check(not l["gear_shown"], "palier à 50 W : braquet caché, pas de roue libre")
	_check(HudViewModel.session_lines(sim, no_erg)["gear_shown"], "SIM : braquet affiché")


func _test_zones() -> void:
	# Puissance : zones de Coggan (Z1 = 0 … Z7 = 6) ; FC : Z1 à Z5 en % de la FC max ; -1 sans référence.
	_check(HudViewModel.power_zone(100.0, 250.0) == 0 and HudViewModel.power_zone(248.0, 250.0) == 3
		and HudViewModel.power_zone(330.0, 250.0) == 5 and HudViewModel.power_zone(450.0, 250.0) == 6,
		"zones de puissance (40, 99, 132, 180 % de FTP)")
	_check(HudViewModel.power_zone(137.5, 250.0) == 1, "55 % de FTP : Z2 (borne basse incluse)")
	_check(HudViewModel.power_zone(NAN, 250.0) == -1 and HudViewModel.power_zone(200.0, 0.0) == -1,
		"puissance sans mesure ou sans FTP : pas de zone")
	_check(HudViewModel.hr_zone(100.0, 185.0) == 0 and HudViewModel.hr_zone(120.0, 185.0) == 1
		and HudViewModel.hr_zone(142.0, 185.0) == 2 and HudViewModel.hr_zone(160.0, 185.0) == 3
		and HudViewModel.hr_zone(176.0, 185.0) == 4, "zones de FC (54, 65, 77, 86, 95 % de la FC max)")
	_check(HudViewModel.hr_zone(0.0, 185.0) == -1 and HudViewModel.hr_zone(NAN, 185.0) == -1
		and HudViewModel.hr_zone(150.0, 0.0) == -1, "FC absente ou FC max inconnue : pas de zone")
	var l := HudViewModel.session_lines({"power_3s": 248.0, "hr": 142}, {"visible": false}, 250.0, 185.0)
	_check(l["power_zone"] == 3 and l["hr_zone"] == 2, "lignes du HUD : zones de la puissance 3 s et de la FC")
	_check(HudViewModel.session_lines({"power_3s": 248.0, "hr": 142}, {"visible": false})["power_zone"] == -1,
		"lignes du HUD sans FTP : pas de zone")


func _test_difficulty() -> void:
	# La difficulté se règle et se lit dans le menu Réglages (et l'écran de pause), pas dans le HUD
	# permanent (demande du propriétaire du 27 octobre) : aucune sortie du HUD n'en porte le texte.
	for pct in [30, 50, 100]:
		var vm := HudViewModel.new()
		vm.on_state({"difficulty_pct": pct}, 2.0)
		var eval := vm.evaluate(2.5)
		var lines := HudViewModel.session_lines({"difficulty_pct": pct}, {})
		for out in [eval, lines]:
			_check(not out.has("difficulty_text") and not out.has("difficulty_visible"),
				"difficulté à %d %% : absente du HUD" % pct)


func _test_controls_help() -> void:
	var sim: String = HudViewModel.controls_text(false)
	var erg: String = HudViewModel.controls_text(true)
	_check(sim.contains("Y = pause") and sim.contains("braquet") and not sim.contains("intensité"),
		"rappel en séance libre : Y = pause, + / − = braquet")
	_check(erg.contains("Y = pause") and erg.contains("intensité") and erg.contains("Z = bloc suivant")
		and not erg.contains("pause ERG"), "rappel en ERG : Y = pause, intensité, Z = bloc suivant, plus de pause ERG")
	_check(not sim.contains("P = pause") and not erg.contains("P = pause"), "rappel : plus de touche P")
	_check(HudViewModel.unclear_press_text("PLUS_UNCLEAR", true).contains("A long pour valider")
		and HudViewModel.unclear_press_text("MINUS_UNCLEAR", true).contains("précédent")
		and HudViewModel.unclear_press_text("PLUS_UNCLEAR", false).contains("braquet"),
		"appui ambigu expliqué : pas et A long dans les menus, braquet en séance")


func _init() -> void:
	_test_controls_help()
	_test_texts()
	_test_session_lines()
	_test_distance_on_loop()
	_test_grade_classes()
	_test_profile_open()
	_test_profile_loop()
	_test_next_climb()
	_test_zones()
	_test_difficulty()
	print("test_hud_view_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
