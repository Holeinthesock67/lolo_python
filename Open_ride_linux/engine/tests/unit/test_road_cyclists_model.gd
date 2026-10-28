extends SceneTree

## Tests sans écran des cyclistes du décor `road_cyclists_model.gd` (Lot P28) : 20 km de plaine puis 10 km de
## montée, nombre de groupes, écarts au cycliste et aux bots, groupes doublés et qui doublent, budget, pause,
## vitesse en pente, cadence ; affichage `road_cyclists_renderer.gd`.
## Lancement : godot --headless --path engine --script res://tests/unit/test_road_cyclists_model.gd

const Model := preload("res://scripts/road_cyclists_model.gd")
const Renderer := preload("res://scripts/road_cyclists_renderer.gd")
const SoundPlayer := preload("res://scripts/sound_player.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")

const FLAT_M := 20000.0
const LENGTH_M := 31000.0
const CLIMB_PCT := 6.0
const MIN_CENTRE_M := Model.MIN_GAP_M + 2.0 * Model.RIDER_HALF_WIDTH_M
const ALONGSIDE_M := 2.0     # longueur d'un vélo et demi : « à la même abscisse »

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Route droite vers l'est : 20 km de plaine, puis une montée régulière à 6 %, puis 1 km de plat.
func _route():
	var ds := 10.0
	var n := int(LENGTH_M / ds) + 1
	var cols := {"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		var s := i * ds
		var climbing := s >= FLAT_M and s < FLAT_M + 10000.0
		cols["lat"].append(48.9)
		cols["lon"].append(7.1)
		cols["alt_m"].append(200.0 + clampf(s - FLAT_M, 0.0, 10000.0) * CLIMB_PCT / 100.0)
		cols["x"].append(s)
		cols["z"].append(0.0)
		cols["grade_pct"].append(CLIMB_PCT if climbing else 0.0)
		cols["heading_deg"].append(90.0)
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": (n - 1) * ds, "type": "open"}
	d.merge(cols)
	var r = RouteDataScript.new()
	r.load_route_dict(d)
	return r


const CLIMBS := [{"start_s": FLAT_M, "summit_s": FLAT_M + 10000.0}]


class FakeTraffic:
	var vehicles: Array = []


## Séance : 30 km/h en plaine, 14 km/h en montée, un bot à 32 km/h parti 200 m derrière ; relevé des contrôles.
func _ride(route, budget: int, rng_seed: int, traffic = null) -> Dictionary:
	var m = Model.new()
	m.configure(route, CLIMBS, [], budget, rng_seed, 6.0, traffic)
	var dt := 1.0 / 30.0
	var s := 300.0
	var bot := 100.0
	var seen := {}
	var log := []
	var flat_groups := 0
	var climb_groups := 0
	var too_close := 0
	var bot_close := 0
	var max_riders := 0
	var cases := {}
	var salut := 0
	var max_kmh := 0.0
	while s < FLAT_M + 10000.0:
		var v := 30.0 / 3.6 if s < FLAT_M else 14.0 / 3.6
		bot += (32.0 if bot < FLAT_M else 15.0) / 3.6 * dt
		m.update(s, v, dt, false, [bot])
		if not m.last_event.is_empty():
			salut += 1
		max_riders = maxi(max_riders, m.rider_count())
		for g in m.groups:
			max_kmh = maxf(max_kmh, float(g["speed_mps"]) * 3.6)
			if not seen.has(g["id"]):
				seen[g["id"]] = true
				log.append([g["id"], g["case"], (g["members"] as Array).size()])
				cases[g["case"]] = int(cases.get(g["case"], 0)) + 1
				if float(g["s"]) < FLAT_M + (300.0 if g["case"] == "overtake" else 0.0) and s < FLAT_M:
					flat_groups += 1
				else:
					climb_groups += 1
		for r in m.riders():
			if absf(float(r["s"]) - s) < ALONGSIDE_M and absf(float(r["lateral"])) < MIN_CENTRE_M - 1e-3:
				too_close += 1
			if absf(float(r["s"]) - bot) < ALONGSIDE_M and absf(float(r["lateral"]) - Model.BOT_LATERAL_M) < MIN_CENTRE_M - 1e-3:
				bot_close += 1
		s += v * dt
	return {"flat": flat_groups, "climb": climb_groups, "log": log, "too_close": too_close, "bot_close": bot_close,
		"max_riders": max_riders, "passed": m.passed_total, "overtook": m.overtook_total, "cases": cases,
		"salut": salut, "max_kmh": max_kmh}


func _test_renderer(route) -> void:
	var sp = SoundPlayer.new()
	root.add_child(sp)
	var rr = Renderer.new()
	root.add_child(rr)
	await process_frame
	var n0: int = rr.get_child_count()
	var m = Model.new()
	m.configure(route, CLIMBS, [], 16, 3)
	rr.setup(m, sp)
	var s := 1000.0
	var match_ok := true
	var cadence_ok := true
	var max_shown := 0
	var usec := 0
	var frames := 0
	for i in range(30 * 240):
		var t0 := Time.get_ticks_usec()
		m.update(s, 30.0 / 3.6, 1.0 / 30.0)
		rr.update(1.0 / 30.0)
		usec += Time.get_ticks_usec() - t0
		frames += 1
		var rs: Array = m.riders()
		max_shown = maxi(max_shown, rr.visible_count())
		match_ok = match_ok and rr.visible_count() == mini(rs.size(), Renderer.MAX_CYCLISTS)
		for j in range(rr.visible_count()):
			var r: Dictionary = rs[j]
			match_ok = match_ok and rr.shown_transform(j).origin.is_equal_approx(
				m.world_transform(float(r["s"]), float(r["lateral"]), int(r["dir"])).origin)
			var want := Model.cadence_rpm(float(r["group"]["speed_mps"]))
			cadence_ok = cadence_ok and absf(rr.shown_cadence(j) - want) < 1e-3
		s += 30.0 / 3.6 / 30.0
	_check(match_ok and max_shown >= 2, "affichage : un coureur et un vélo par cycliste du modèle, à sa place (%d au plus)" % max_shown)
	_check(cadence_ok, "cadence de chaque cycliste affiché d'après sa vitesse")
	_check(rr.get_child_count() == n0, "aucun nœud créé après le démarrage")
	var avg := usec / 1000.0 / frames
	_check(PerfBudget.check("road_cyclists_frame", avg), "16 cyclistes au plus : modèle et affichage en %.4f ms par image" % avg)
	rr.queue_free()
	sp.queue_free()
	await process_frame


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var route = _route()
	var r: Dictionary = _ride(route, 16, 7)
	print("30 km : %d groupes en plaine, %d en montée, cas %s, %d doublés, %d qui doublent, %d « Salut ! », %.0f km/h au plus" % [
		r["flat"], r["climb"], str(r["cases"]), r["passed"], r["overtook"], r["salut"], r["max_kmh"]])
	_check(r["flat"] >= 15 and r["flat"] <= 30, "20 km de plaine : de 15 à 30 groupes (%d)" % r["flat"])
	_check(r["climb"] >= 20 and r["climb"] <= 40, "10 km de montée : de 20 à 40 groupes (%d)" % r["climb"])
	_check(r["too_close"] == 0, "aucun cycliste du décor à moins de 1,2 m latéralement du cycliste")
	_check(r["bot_close"] == 0, "aucun cycliste du décor à moins de 1,2 m latéralement d'un bot")
	_check(r["passed"] >= 1 and r["overtook"] >= 1, "groupes devant doublés (%d), groupes qui doublent (%d)" % [r["passed"], r["overtook"]])
	_check(r["max_riders"] <= 16, "jamais plus que le budget de 16 cyclistes (%d)" % r["max_riders"])
	_check(r["max_kmh"] <= Model.MAX_KMH + 0.01, "jamais plus de 70 km/h (%.1f)" % r["max_kmh"])
	var r2: Dictionary = _ride(route, 16, 7)
	_check(str(r2["log"]) == str(r["log"]), "même graine, même parcours : mêmes groupes")
	var r3: Dictionary = _ride(route, 16, 8)
	_check(str(r3["log"]) != str(r["log"]), "autre graine : autres groupes")
	var safe := true
	var salut := 0
	for sd in range(1, 7):
		var rs: Dictionary = _ride(route, 8, sd)
		salut += int(rs["salut"])
		safe = safe and rs["too_close"] == 0 and rs["bot_close"] == 0 and rs["max_riders"] <= 8
		if not safe:
			print("graine %d : %d trop près, %d près d'un bot, %d au plus" % [sd, rs["too_close"], rs["bot_close"], rs["max_riders"]])
	_check(safe, "6 autres graines, budget 8 : mêmes garanties")
	_check(salut >= 1, "un groupe qui double dit « Salut ! » de temps en temps (%d)" % salut)
	var r0: Dictionary = _ride(route, 0, 7)
	_check(r0["log"].is_empty(), "budget nul : aucun cycliste")
	var busy := FakeTraffic.new()
	busy.vehicles = [{"id": "v1"}]
	var rt: Dictionary = _ride(route, 16, 7, busy)
	_check(int(rt["cases"].get("oncoming", 0)) == 0 and int(r["cases"].get("oncoming", 0)) > 0,
		"pas de groupe en face pendant qu'un véhicule est sur la route")

	# Vitesse en pente (puissance constante) et cadence
	var p := Model.power_for(25.0 / 3.6)
	_check(absf(Model.speed_on_grade(p, 0.0) * 3.6 - 25.0) < 0.2, "puissance constante : 25 km/h sur le plat")
	var up := Model.speed_on_grade(Model.power_for(28.0 / 3.6), 6.0) * 3.6
	var down := Model.speed_on_grade(Model.power_for(35.0 / 3.6), -8.0) * 3.6
	_check(up >= Model.MIN_KMH and up < 16.0 and down > 45.0 and down <= Model.MAX_KMH, "montée à 6 %% : %.1f km/h ; descente à 8 %% : %.1f km/h" % [up, down])
	var rpm := Model.cadence_rpm(30.0 / 3.6)
	_check(rpm > 75.0 and rpm < 90.0 and Model.cadence_rpm(60.0 / 3.6) == 0.0, "cadence à 30 km/h en 50 × 17 : %.0f tr/min ; roue libre à 60 km/h" % rpm)

	# Pause : tout est figé
	var m = Model.new()
	m.configure(route, CLIMBS, [], 16, 7)
	var s := 1000.0
	while m.groups.is_empty() and s < FLAT_M:
		m.update(s, 8.0, 0.1)
		s += 0.8
	var before := str(m.groups)
	for i in range(50):
		m.update(s, 0.0, 0.1, true)
	_check(not m.groups.is_empty() and str(m.groups) == before, "pause : cyclistes figés")
	await _test_renderer(route)
	print("test_road_cyclists_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
