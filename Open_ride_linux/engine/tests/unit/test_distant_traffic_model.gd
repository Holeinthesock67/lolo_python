extends SceneTree

## Tests sans écran des véhicules lointains `distant_traffic_model.gd` (Lot P25) : routes voisines (ligne, sens,
## vitesse, écart à la route du parcours, budget, tronçons déchargés), tracteur au champ (contour, passes de
## 6 m, demi-tours), déterminisme, pause, coût ; affichage `distant_traffic_renderer.gd` (détail et boîtes).
## Lancement : godot --headless --path engine --script res://tests/unit/test_distant_traffic_model.gd

const Model := preload("res://scripts/distant_traffic_model.gd")
const Renderer := preload("res://scripts/distant_traffic_renderer.gd")
const VehicleMesh := preload("res://scripts/vehicle_mesh.gd")
const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const SoundPlayer := preload("res://scripts/sound_player.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")

const LENGTH_M := 3000.0

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Route droite vers l'est le long de z = 0, à plat.
func _route():
	var ds := 10.0
	var n := int(LENGTH_M / ds) + 1
	var cols := {"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		cols["lat"].append(48.9)
		cols["lon"].append(7.1)
		cols["alt_m"].append(300.0)
		cols["x"].append(i * ds)
		cols["z"].append(0.0)
		cols["grade_pct"].append(0.0)
		cols["heading_deg"].append(90.0)
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": (n - 1) * ds, "type": "open"}
	d.merge(cols)
	var r = RouteDataScript.new()
	r.load_route_dict(d)
	return r


## Morceau droit de (x0, z) à (x1, z), un point tous les 25 m, `[x, z, y]`.
func _road(id: String, kind: String, x0: float, x1: float, z: float, lanes: int, oneway: bool, kmh: float) -> Dictionary:
	var pts := []
	var x := x0
	while true:
		pts.append([x, z, 300.0])
		if (x1 > x0 and x >= x1) or (x1 < x0 and x <= x1):
			break
		x = move_toward(x, x1, 25.0)
	return {"id": id, "kind": kind, "lanes": lanes, "oneway": oneway, "speed_kmh": kmh, "points": pts}


## Couche `roads` par tronçon : secondaire à double sens à 100 m, autoroute à sens unique et 3 voies à 300 m
## (tracé vers l'est), piste à 200 m.
func _roads() -> Dictionary:
	var out := {}
	for k in range(3):
		out[k] = [
			_road("sec_%d" % k, "secondary", k * 1000.0, (k + 1) * 1000.0, 100.0, 2, false, 80.0),
			_road("a4_%d" % k, "motorway", k * 1000.0, (k + 1) * 1000.0, -300.0, 3, true, 130.0),
			_road("trk_%d" % k, "track", k * 1000.0, (k + 1) * 1000.0, 200.0, 1, false, 30.0),
		]
	return out


func _rect(id: String, kind: String, x0: float, z0: float, x1: float, z1: float) -> Dictionary:
	return {"id": id, "kind": kind, "density": 0.0, "outer": [[x0, z0], [x1, z0], [x1, z1], [x0, z1]]}


## Végétation : champs (rectangle de 3,6 ha en biais, champ en L) et un pré de même forme, par tronçon.
func _vegetation(field_ids: Array) -> Dictionary:
	var lshape := {"id": field_ids[1], "kind": "farmland", "density": 0.0,
		"outer": [[2100.0, -60.0], [2400.0, -60.0], [2400.0, -140.0], [2220.0, -140.0], [2220.0, -260.0], [2100.0, -260.0]]}
	var tilted := {"id": field_ids[0], "kind": "farmland", "density": 0.0, "outer": []}
	for c: Vector2 in [Vector2(-150.0, -60.0), Vector2(150.0, -60.0), Vector2(150.0, 60.0), Vector2(-150.0, 60.0)]:
		var p: Vector2 = c.rotated(0.4) + Vector2(1500.0, 200.0)
		tilted["outer"].append([p.x, p.y])
	return {0: [_rect("meadow_a", "meadow", 300.0, 150.0, 600.0, 270.0)], 1: [tilted], 2: [lshape]}


## Graine pour laquelle les deux champs ont un tracteur (une chance sur 3 chacun).
func _field_seed(route, field_ids: Array) -> int:
	for sd in range(1, 400):
		var plan := Model.prepare(route, {}, _vegetation(field_ids), sd)
		if (plan["slots"] as Array).size() == 2:
			return sd
	return -1


func _line_dist(p: Vector3, line: Dictionary) -> float:
	var pts: PackedVector3Array = line["pts"]
	var best := INF
	for i in range(pts.size() - 1):
		var a := Vector2(pts[i].x, pts[i].z)
		var b := Vector2(pts[i + 1].x, pts[i + 1].z)
		var q := Vector2(p.x, p.z)
		var t := clampf((q - a).dot(b - a) / maxf((b - a).length_squared(), 1e-6), 0.0, 1.0)
		best = minf(best, q.distance_to(a + (b - a) * t))
	return best


func _test_roads(route) -> void:
	var plan := Model.prepare(route, _roads(), {}, 5)
	var plan2 := Model.prepare(route, _roads(), {}, 5)
	_check(str(plan["slots"]) == str(plan2["slots"]) and (plan["slots"] as Array).size() > 0,
		"même graine, mêmes routes : même plan (%d places)" % (plan["slots"] as Array).size())
	var kinds_on_motorway := {}
	var per_line := {}
	for sl in plan["slots"]:
		var road_id: String = str(sl["id"]).split("_")[0]
		if road_id == "a4":
			kinds_on_motorway[sl["kind"]] = true
		per_line[sl["line"]] = int(per_line.get(sl["line"], 0)) + 1
	var spacing_ok := true
	for li in per_line:
		var line: Dictionary = plan["lines"][li]
		spacing_ok = spacing_ok and per_line[li] <= 3 * maxi(1, int(floor((float(line["len"]) - 2.0 * Model.END_TRIM_M) / Model.SPACING_M))) * 2
	_check(not kinds_on_motorway.has("tractor") and not kinds_on_motorway.has("bus") and spacing_ok,
		"autoroute sans tracteur ni bus (%s), un véhicule par voie et par 400 m au plus" % str(kinds_on_motorway.keys()))
	var m = Model.new()
	m.configure(plan, 24)
	for k in range(3):
		m.set_chunk_loaded(k, true)
	var dt := 1.0 / 30.0
	var prev := {}
	var on_line := true
	var heading_ok := true
	var speed_ok := true
	var gap_ok := true
	var max_n := 0
	var usec := 0
	var frames := 0
	var rider := Vector3(0.0, 300.0, 0.0)
	var sizes := {}
	var sel_usec := 0
	while rider.x < LENGTH_M:
		var t0 := Time.get_ticks_usec()
		var will_select: bool = m._clock + dt - m._select_at >= Model.SELECT_PERIOD_S
		m.update(rider, dt)
		usec += Time.get_ticks_usec() - t0
		if will_select:
			sel_usec += Time.get_ticks_usec() - t0
		frames += 1
		max_n = maxi(max_n, m.vehicles.size())
		var now := {}
		for v in m.vehicles:
			var id: String = v["id"]
			var road_id := id.split("_")[0]
			var xf: Transform3D = v["xform"]
			var slot: Dictionary = {}
			for sl in plan["slots"]:
				if sl["id"] == id:
					slot = sl
			var line: Dictionary = plan["lines"][slot["line"]]
			on_line = on_line and _line_dist(xf.origin, line) <= absf(float(slot["lane_off"])) + 0.05 \
				and absf(_line_dist(xf.origin, line) - absf(float(slot["lane_off"]))) < 0.05
			gap_ok = gap_ok and absf(xf.origin.z) >= 20.0
			var fwd := -xf.basis.z
			if road_id == "a4":
				heading_ok = heading_ok and fwd.x > 0.99
			now[id] = xf.origin
			now[id + "#d"] = float(v["dist_m"])
			if prev.has(id) and float(v["scale"]) >= 1.0 and float(v["dist_m"]) <= Model.DETAIL_M \
					and float(prev.get(id + "#d", INF)) <= Model.DETAIL_M - 20.0:
				var spd := Vector2(xf.origin.x - prev[id].x, xf.origin.z - prev[id].z).length() / dt * 3.6
				var layer: float = {"sec": 80.0, "a4": 130.0, "trk": 30.0}[road_id]
				var cap := float(Model.KIND_MAX_KMH.get(v["kind"], layer))
				var hi := minf(layer, cap)
				var ok_now := spd <= hi + 0.5 and spd >= minf(layer * (1.0 - Model.MAX_SLOWDOWN), cap) - 0.5
				speed_ok = speed_ok and ok_now
			sizes[v["kind"]] = true
		prev = now
		rider.x += 30.0 / 3.6 * dt
	_check(on_line, "véhicules sur leur ligne, à leur voie")
	_check(heading_ok, "autoroute à sens unique : tous dans le sens du tracé")
	_check(speed_ok, "vitesse de la couche moins 15 % au plus (plafond de la sorte), mesurée à moins de 400 m")
	_check(gap_ok, "aucun véhicule à moins de 20 m de la route du parcours")
	_check(max_n <= 24 and max_n >= 6, "jamais plus que le budget de 24 (%d au plus), sortes %s" % [max_n, str(sizes.keys())])
	var avg := usec / 1000.0 / frames
	print("dont tri des places : %.4f ms par image en moyenne" % (sel_usec / 1000.0 / frames))
	_check(PerfBudget.check("distant_traffic_frame", avg), "24 véhicules lointains mis à jour en %.4f ms par image" % avg)
	# Tronçon déchargé : rien dessus
	m.set_chunk_loaded(1, false)
	m.update(Vector3(1500.0, 300.0, 0.0), dt)
	var none_on_1 := true
	for v in m.vehicles:
		none_on_1 = none_on_1 and int(v["chunk"]) != 1
	_check(none_on_1 and not m.vehicles.is_empty(), "rien sur un tronçon déchargé (%d sur les autres)" % m.vehicles.size())
	m.set_budget(0)
	m.update(Vector3(1500.0, 300.0, 0.0), dt)
	_check(m.vehicles.is_empty(), "budget nul : aucun véhicule")
	# Pause : figés
	m.set_budget(12)
	m.set_chunk_loaded(1, true)
	m.update(Vector3(1500.0, 300.0, 0.0), dt)
	var before := str(m.vehicles)
	for i in range(30):
		m.update(Vector3(1500.0, 300.0, 0.0), dt, true)
	_check(str(m.vehicles) == before, "pause : véhicules figés")


func _test_fields(route) -> void:
	var ids := ["champ_b", "champ_l"]
	var sd := _field_seed(route, ids)
	_check(sd > 0, "graine trouvée pour un tracteur dans chacun des deux champs (%d)" % sd)
	if sd < 0:
		return
	var veg := _vegetation(ids)
	var plan := Model.prepare(route, {}, veg, sd)
	var m = Model.new()
	m.configure(plan, 12)
	for k in range(3):
		m.set_chunk_loaded(k, true)
	var rings := {1: VegetationPlacer._packed_ring(veg[1][0]["outer"]), 2: VegetationPlacer._packed_ring(veg[2][0]["outer"])}
	var inside := true
	var no_meadow := true
	var turns := 0
	var last_fwd := {}
	var path_ok := true
	for p in plan["paths"]:
		var pts: PackedVector3Array = p["pts"]
		var ring: PackedVector2Array = rings[1] if VegetationPlacer._in_ring(pts[0].x, pts[0].z, rings[1]) else rings[2]
		for q in pts:
			path_ok = path_ok and VegetationPlacer._in_ring(q.x, q.z, ring)
	_check(path_ok, "chemins des tracteurs dans le contour de leur champ (rectangle en biais, champ en L)")
	# Passes espacées de 6 m : écart entre les deux premières passes du rectangle
	var p0: PackedVector3Array = plan["paths"][0]["pts"]
	var a := Vector2(p0[0].x, p0[0].z)
	var b := Vector2(p0[1].x, p0[1].z)
	var ax := (b - a).normalized()
	var c := Vector2(p0[1 + Model.TURN_SEGMENTS].x, p0[1 + Model.TURN_SEGMENTS].z)
	var off := absf((c - a).dot(Vector2(-ax.y, ax.x)))
	_check(absf(off - Model.PASS_STEP_M) < 0.05, "décalage de %.2f m entre deux passes" % off)
	var dt := 0.5
	var t := 0.0
	var rider := Vector3(1500.0, 300.0, 0.0)
	while t < 1800.0:
		m.update(rider, dt)
		for v in m.vehicles:
			var o: Vector3 = (v["xform"] as Transform3D).origin
			no_meadow = no_meadow and not (o.x > 300.0 and o.x < 600.0 and o.z > 150.0 and o.z < 270.0)
			inside = inside and (VegetationPlacer._in_ring(o.x, o.z, rings[1]) or VegetationPlacer._in_ring(o.x, o.z, rings[2]))
			var fwd := -(v["xform"] as Transform3D).basis.z
			if last_fwd.has(v["id"]) and fwd.dot(last_fwd[v["id"]]) < -0.9:
				turns += 1
			if not last_fwd.has(v["id"]) or fmod(t, 30.0) < dt:
				last_fwd[v["id"]] = fwd
		t += dt
	_check(inside and no_meadow, "tracteurs toujours dans leur champ, aucun dans le pré")
	_check(turns >= 4, "demi-tours au bord du champ (%d en 30 min)" % turns)
	_check(plan["slots"][0]["kind"] == "tractor_plough", "tracteur et charrue")


func _test_renderer(route) -> void:
	var sp = SoundPlayer.new()
	root.add_child(sp)
	var rr = Renderer.new()
	root.add_child(rr)
	await process_frame
	var n0: int = rr.get_child_count()
	var m = Model.new()
	m.configure(Model.prepare(route, _roads(), {}, 5), 24)
	for k in range(3):
		m.set_chunk_loaded(k, true)
	rr.setup(m, sp)
	var rider := Vector3(500.0, 300.0, 0.0)
	var counts_ok := true
	var near := 0
	var far := 0
	for i in range(300):
		m.update(rider, 1.0 / 30.0)
		rr.update(rider)
		counts_ok = counts_ok and rr.visible_count() == m.vehicles.size()
		near = maxi(near, rr.visible_count() - rr.shown("far"))
		far = maxi(far, rr.shown("far"))
		rider.x += 1.0
	_check(counts_ok and near > 0 and far > 0, "affichage : carrosserie détaillée jusqu'à 400 m (%d), boîte au-delà (%d)" % [near, far])
	_check(rr.get_child_count() == n0, "aucun nœud créé après le démarrage")
	VehicleMesh.set_lights(1.0)
	var lit := float(VehicleMesh.material("car_a").get_shader_parameter("lights_on")) == 1.0 \
		and float(VehicleMesh.material("far").get_shader_parameter("lights_on")) == 1.0
	VehicleMesh.set_lights(0.0)
	_check(lit and float(VehicleMesh.material("truck").get_shader_parameter("lights_on")) == 0.0,
		"phares : un seul paramètre partagé par sorte, sans matériau par véhicule")
	rr.queue_free()
	sp.queue_free()
	await process_frame


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var route = _route()
	_test_roads(route)
	_test_fields(route)
	await _test_renderer(route)
	print("test_distant_traffic_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
