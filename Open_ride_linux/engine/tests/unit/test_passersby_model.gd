extends SceneTree

## Tests sans écran des passants `passersby_model.gd` et de leur affichage par `crowd_renderer.gd` en
## mode « passants » (Lot P21) : densité au village et en campagne, écart au bord, segments de marche,
## salut une fois par passage, sons espacés, budget, coût par image.
## Lancement : godot --headless --path engine --script res://tests/unit/test_passersby_model.gd

const PasserbyModel := preload("res://scripts/passersby_model.gd")
const CrowdRenderer := preload("res://scripts/crowd_renderer.gd")
const ClimbDetector := preload("res://scripts/climb_detector.gd")
const ClimbTest := preload("res://tests/unit/test_climb_detector.gd")

const HALF_ROAD := 3.0

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _flat(_s: float) -> float:
	return 0.0


## Col de 4 km (8 à 12 km), plat ailleurs.
func _col(s: float) -> float:
	return 7.0 if s >= 8000.0 and s < 12000.0 else 0.0


## Village : maisons de part et d'autre de la route (vers l'est, z = 0) de x0 à x1.
static func _village(x0: float, x1: float) -> Array:
	var out := []
	var x := x0
	while x <= x1:
		for z in [-40.0, 40.0]:
			out.append({"id": "b%d_%d" % [int(x), int(z)], "outer": [[x - 4.0, z - 4.0], [x + 4.0, z - 4.0], [x + 4.0, z + 4.0], [x - 4.0, z + 4.0]]})
		x += 20.0
	return out


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var route = ClimbTest.make_route(8000.0, Callable(self, "_flat"))
	var buildings := _village(1020.0, 1480.0)
	var pm = PasserbyModel.new()
	pm.configure(route, buildings, {}, 5)
	var in_village: Array = pm.people.filter(func(p): return float(p["s"]) >= 1000.0 and float(p["s"]) < 1500.0)
	var in_country: Array = pm.people.filter(func(p): return float(p["s"]) >= 2000.0 and float(p["s"]) < 7000.0)
	_check(in_village.size() >= 10 and in_village.size() <= 30, "village de 500 m : %d personnes (10 à 30)" % in_village.size())
	_check(in_country.size() >= 6 and in_country.size() <= 17, "campagne de 5 km : %d personnes (6 à 17)" % in_country.size())
	var village_ok := in_village.all(func(p): return bool(p["village"]))
	var country_roles := in_country.all(func(p): return ["walker", "dog_walker", "jogger", "farmer"].has(str(p["role"])))
	_check(village_ok and country_roles, "rôles selon le lieu (village, campagne)")
	var again = PasserbyModel.new()
	again.configure(route, buildings, {}, 5)
	_check(str(again.people) == str(pm.people), "même graine, même placement")
	var other = PasserbyModel.new()
	other.configure(route, buildings, {}, 6)
	_check(str(other.people) != str(pm.people), "autre graine, autre placement")

	# Écart au bord et segments de marche, à tout instant
	var too_close := 0
	var off_segment := 0
	for p in pm.people:
		for k in range(60):
			var t := k * 3.7
			var pos: Vector3 = PasserbyModel.position_at(p, t)
			if absf(pos.z) - HALF_ROAD < 1.0 - 0.01:
				too_close += 1
			if pos.x < float(p["s"]) - 0.01 or pos.x > float(p["s"]) + float(p["len"]) + 0.01:
				off_segment += 1
	var movers: Array = pm.people.filter(func(p): return float(p["len"]) > 0.0)
	_check(too_close == 0, "aucune personne à moins de 1 m du bord de la chaussée")
	_check(movers.size() > 0 and off_segment == 0, "%d marcheurs ou joggeurs, tous restent sur leur segment" % movers.size())
	var joggers: Array = pm.people.filter(func(p): return str(p["role"]) == "jogger")
	var oncoming: Array = joggers.filter(func(p): return float(p["dir"]) < 0.0)
	var heading_ok := true
	var yaw_ok := true
	for p in movers:
		for k in range(40):
			var t := k * 1.3
			var a: Vector3 = PasserbyModel.position_at(p, t)
			var b: Vector3 = PasserbyModel.position_at(p, t + 0.05)
			var motion := Vector3(b.x - a.x, 0.0, b.z - a.z)
			if motion.length() > 1e-3 and motion.x * PasserbyModel.heading_sign(p, t) <= 0.0:
				heading_ok = false   # route vers l'est : abscisse croissante = x croissant
	pm.visible(Vector3(1250.0, 1.5, 1.0), 1250.0, 20.0, 80)
	for e in pm.visible(Vector3(1250.0, 1.5, 1.0), 1250.0, 20.02, 80):
		var p: Dictionary = pm.people[int(e["i"])]
		if bool(e["moving"]) and not bool(e["wave"]):
			var a: Vector3 = PasserbyModel.position_at(p, 20.02)
			var b: Vector3 = PasserbyModel.position_at(p, 20.07)
			var facing := Vector3(sin(float(e["yaw"])), 0.0, cos(float(e["yaw"])))
			if (b - a).length() > 1e-3 and facing.dot(b - a) <= 0.0:
				yaw_ok = false
	_check(heading_ok and yaw_ok, "marcheurs tournés dans le sens de leur marche, demi-tour au bout du segment")
	_check(joggers.is_empty() or oncoming.size() * 2 >= joggers.size(), "joggeurs surtout en sens inverse (%d sur %d)" % [oncoming.size(), joggers.size()])

	# Eau : un étang au bord de la route côté +z dans le village
	var water := {"areas": [{"id": "l", "kind": "pond", "level_y": 0.0, "outer": [[1000.0, 3.5], [1500.0, 3.5], [1500.0, 30.0], [1000.0, 30.0]]}]}
	var wet = PasserbyModel.new()
	wet.configure(route, buildings, water, 5)
	var in_pond := 0
	for p in wet.people:
		for pt in p["path"] if float(p["len"]) > 0.0 else [p["pos"]]:
			var v: Vector3 = pt
			if v.x >= 1000.0 and v.x <= 1500.0 and v.z > 3.5 and v.z < 30.0:
				in_pond += 1
	var wet_village: Array = wet.people.filter(func(p): return float(p["s"]) >= 1000.0 and float(p["s"]) < 1500.0)
	_check(in_pond == 0 and wet_village.all(func(p): return int(p["side"]) == -1), "personne dans l'eau : toutes de l'autre côté")

	# Pas de passants dans la zone des spectateurs de P15
	var climb_route = ClimbTest.make_route(14000.0, Callable(self, "_col"))
	var zones := PasserbyModel.crowd_zones(ClimbDetector.detect(climb_route))
	var zm = PasserbyModel.new()
	zm.configure(climb_route, [], {}, 5, 6.0, zones)
	_check(zones.size() == 1 and zm.people.filter(func(p): return float(p["s"]) >= float(zones[0][0]) and float(p["s"]) <= float(zones[0][1])).is_empty(),
		"aucun passant dans le dernier kilomètre du col (zone des spectateurs)")

	# Passage du cycliste à 8 m/s dans le village : une partie salue, une seule fois
	var starts := {}
	var sounds := []
	var now := 0.0
	for pass_i in range(2):
		var s := 900.0
		while s < 1600.0:
			var rider := Vector3(s, 0.0, 1.0)
			var ev: Dictionary = pm.update(rider, s, now)
			if str(ev["sound"]) != "":
				var sp: Vector3 = ev["pos"]
				sounds.append([now, ev["sound"], Vector2(sp.x - rider.x, sp.z - rider.z).length()])
			for i in pm.states.keys():
				var st: Dictionary = pm.states[i]
				if is_equal_approx(float(st["wave_at"]), now):
					starts[[pass_i, i]] = int(starts.get([pass_i, i], 0)) + 1
			s += 0.4
			now += 0.05
		now += 30.0
	var near_ids := {}
	for p in pm.people:
		if float(p["s"]) >= 900.0 - PasserbyModel.JOG_LEN_M.y and float(p["s"]) < 1600.0:
			near_ids[p] = true
	var waved_first := 0
	var twice := 0
	for key in starts:
		if int(key[0]) == 0:
			waved_first += 1
		if int(starts[key]) > 1:
			twice += 1
	_check(waved_first > 0 and waved_first < near_ids.size(), "au passage, %d personnes sur %d saluent" % [waved_first, near_ids.size()])
	_check(twice == 0, "chacune une seule fois par passage")
	var gaps_ok := true
	var near_ok := true
	for j in range(sounds.size()):
		if j > 0 and float(sounds[j][0]) - float(sounds[j - 1][0]) < PasserbyModel.SOUND_GAP_S:
			gaps_ok = false
		if float(sounds[j][2]) > PasserbyModel.SOUND_M:
			near_ok = false
	_check(sounds.size() > 0 and gaps_ok and near_ok, "%d sons, jamais deux à moins de 20 s, aucun à plus de 30 m" % sounds.size())

	# Pendant un bip du Click : aucun son
	var quiet = PasserbyModel.new()
	quiet.configure(route, buildings, {}, 5)
	var n_quiet := 0
	var tq := 0.0
	var sq := 900.0
	while sq < 1600.0:
		if str(quiet.update(Vector3(sq, 0.0, 1.0), sq, tq, true)["sound"]) != "":
			n_quiet += 1
		sq += 0.4
		tq += 0.05
	_check(n_quiet == 0, "aucun son pendant un bip du Click")

	# Affichage : budget, plus proches, chiens et bancs
	var r = CrowdRenderer.new("passersby")
	root.add_child(r)
	r.setup_passersby(pm)
	r.set_preset("low")
	var cam := Vector3(1250.0, 1.5, 1.0)
	r.update_passersby(cam, 1250.0, 10.0, {"sound": "voice_bonjour", "pos": Vector3(1250.0, 0.0, 5.0)})
	var people_mm: MultiMesh = r.get_node("Passersby_people").multimesh
	var shown := people_mm.visible_instance_count
	var vis: Array = pm.visible(cam, 1250.0, 10.0, r.budget).duplicate()
	var farthest_kept := 0.0
	for e in vis:
		farthest_kept = maxf(farthest_kept, (e["pos"] as Vector3).distance_to(cam))
	var all_vis: Array = pm.visible(cam, 1250.0, 10.0, 1000)
	var closer_left_out := 0
	for e in all_vis.slice(vis.size()):
		if (e["pos"] as Vector3).distance_to(cam) < farthest_kept - 1e-3:
			closer_left_out += 1
	_check(r.budget == 24 and shown <= r.budget and shown == mini(r.budget, all_vis.size()) and closer_left_out == 0,
		"low : %d passants affichés sur %d (budget 24), les plus proches" % [shown, all_vis.size()])
	var vis_again: Array = pm.visible(cam, 1250.0, 10.0, r.budget)
	var dogs_expected := vis_again.filter(func(e): return int(e["dog"]) >= 0).size()
	var benches_expected := vis_again.filter(func(e): return str(pm.people[int(e["i"])]["role"]) == "sitter").size()
	_check(r.get_node("Passersby_dogs").multimesh.visible_instance_count == dogs_expected
		and r.get_node("Passersby_benches").multimesh.visible_instance_count == benches_expected,
		"chiens (%d) et bancs (%d) des personnes affichées" % [dogs_expected, benches_expected])
	_check(r.sounds_played == ["voice_bonjour"], "son du passant transmis au lecteur 3D")
	r.set_preset("high", false)
	r.update_passersby(cam, 1250.0, 11.0)
	_check(people_mm.visible_instance_count == 0, "décor vivant coupé : aucun passant")

	# Coût par image : 80 personnes sur 200 m (village dense, rôles du placement recopiés et décalés)
	var long_route = ClimbTest.make_route(4000.0, Callable(self, "_flat"))
	var big = PasserbyModel.new()
	big.configure(long_route, _village(1000.0, 3000.0), {}, 2)
	var base: Array = big.people.duplicate()
	big.people.clear()
	for j in range(80):
		var q: Dictionary = base[j % base.size()].duplicate(true)
		var shift := Vector3(1900.0 + j * 2.5 - float(q["s"]), 0.0, 0.0)
		q["s"] = 1900.0 + j * 2.5
		q["pos"] = (q["pos"] as Vector3) + shift
		var moved := PackedVector3Array()
		for pt in q["path"]:
			moved.append(pt + shift)
		q["path"] = moved
		big.people.append(q)
	var t0 := Time.get_ticks_usec()
	var frames := 0
	var seen := 0
	var sx := 1800.0
	var t_upd := 0
	while sx < 2200.0:
		var tu := Time.get_ticks_usec()
		big.update(Vector3(sx, 0.0, 1.0), sx, frames / 60.0)
		t_upd += Time.get_ticks_usec() - tu
		var v: Array = big.visible(Vector3(sx, 1.5, 1.0), sx, frames / 60.0, 80)
		seen = maxi(seen, v.size())
		sx += 0.13
		frames += 1
	var per_frame_ms := (Time.get_ticks_usec() - t0) / 1000.0 / frames
	var update_ms := t_upd / 1000.0 / frames
	print("Passants : %d affichés ; modèle %.3f ms par image, avec la sélection et l'animation %.3f ms" % [seen, update_ms, per_frame_ms])
	_check(seen == 80 and update_ms < 0.1, "80 passants : mise à jour du modèle en %.3f ms par image (< 0,1 ms)" % update_ms)
	_check(per_frame_ms < 0.2, "80 passants : modèle, sélection et animation en %.3f ms par image (< 0,2 ms)" % per_frame_ms)

	r.queue_free()
	await process_frame
	print("test_passersby_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
