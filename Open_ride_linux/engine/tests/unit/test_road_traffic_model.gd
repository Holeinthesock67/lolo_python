extends SceneTree

## Tests sans écran de la circulation des routes voisines et des tracteurs des champs (Lot P25) :
## `road_traffic_model.gd` (chemins, voies, sens, vitesses, tracteurs qui hersent, budget, tri des plus
## proches, déterminisme, pause, retrait d'un tronçon, coût par image) et `road_traffic_renderer.gd`
## (MultiMesh par sorte, phares, aucun nœud créé après le démarrage).
## Lancement : godot --headless --path engine --script res://tests/unit/test_road_traffic_model.gd

const RoadTraffic := preload("res://scripts/road_traffic_model.gd")
const RoadTrafficRenderer := preload("res://scripts/road_traffic_renderer.gd")
const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")

const SLOPE := 0.04        # pente de la route secondaire
const SECONDARY_Z := 100.0
const FIELDS := 10

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Ligne droite de `from` à `to` (x, z), un point tous les 25 m, altitude `y0 + pente × x`.
static func _line(id: String, kind: String, from: Vector2, to: Vector2, lanes: int, oneway: bool, kmh: float, slope: float = 0.0) -> Dictionary:
	var pts := []
	var n := int(ceil(from.distance_to(to) / 25.0))
	for i in range(n + 1):
		var p := from.lerp(to, float(i) / n)
		pts.append([p.x, p.y, 300.0 + slope * p.x])
	return {"id": id, "kind": kind, "lanes": lanes, "oneway": oneway, "speed_kmh": kmh, "points": pts}


static func _lines() -> Array:
	return [
		_line("sec", "secondary", Vector2(0.0, SECONDARY_Z), Vector2(1500.0, SECONDARY_Z), 2, false, 80.0, SLOPE),
		_line("mw", "motorway", Vector2(0.0, 300.0), Vector2(1500.0, 300.0), 3, true, 130.0),
		_line("trk", "track", Vector2(0.0, -200.0), Vector2(800.0, -200.0), 1, false, 30.0),
		_line("short", "residential", Vector2(10.0, 50.0), Vector2(18.0, 50.0), 2, false, 50.0),
		_line("foot", "footway", Vector2(0.0, 60.0), Vector2(500.0, 60.0), 1, false, 5.0),
	]


## Champs : FIELDS grands champs cultivés, un petit, un pré (seuls les grands peuvent porter un tracteur).
static func _fields() -> Array:
	var out := []
	for i in range(FIELDS):
		var x0 := 1600.0 + 400.0 * i
		out.append({"id": "big_%d" % i, "kind": "farmland", "density": 0.0,
			"outer": [[x0, -400.0], [x0 + 300.0, -400.0], [x0 + 300.0, -600.0], [x0, -600.0]], "holes": []})
	out.append({"id": "small", "kind": "farmland", "density": 0.0,
		"outer": [[0.0, -700.0], [50.0, -700.0], [50.0, -750.0], [0.0, -750.0]], "holes": []})
	out.append({"id": "pre", "kind": "meadow", "density": 0.0,
		"outer": [[0.0, -800.0], [400.0, -800.0], [400.0, -1100.0], [0.0, -1100.0]], "holes": []})
	return out


static func _height(x: float, z: float) -> float:
	return 200.0 + 0.01 * x + 0.002 * z


func _model(budget: int):
	var m = RoadTraffic.new()
	m.set_budget(budget)
	m.set_chunk(0, RoadTraffic.road_paths(_lines()))
	m.set_chunk(1, RoadTraffic.field_paths(_fields(), _height))
	return m


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	# 1. Chemins
	var roads := RoadTraffic.road_paths(_lines())
	var by_id := {}
	for p in roads:
		by_id[p["id"]] = p
	_check(roads.size() == 3 and by_id.has("sec") and by_id.has("mw") and by_id.has("trk"),
		"routes : 3 chemins (une rue de 8 m et un chemin piéton écartés)")
	var sec: Dictionary = by_id["sec"]
	var n_sec := int(round((float(sec["length"]) + 450.0) / 450.0))
	_check((sec["cars"] as Array).size() == n_sec and absf(float(sec["length"]) - 1500.0 * sqrt(1.0 + SLOPE * SLOPE)) < 0.5,
		"route secondaire : %d véhicules, un tous les 450 m" % n_sec)
	var mw_ok := true
	for c in by_id["mw"]["cars"]:
		mw_ok = mw_ok and int(c["dir"]) == 1 and absf(float(c["lateral"])) <= RoadTraffic.LANE_M + 1e-4 and c["kind"] != "tractor"
	_check(mw_ok and (by_id["mw"]["cars"] as Array).size() >= 9, "autoroute à sens unique : un seul sens, trois voies, pas de tracteur")
	var trk_ok := true
	var trk_dir: int = by_id["trk"]["cars"][0]["dir"]
	for c in by_id["trk"]["cars"]:
		trk_ok = trk_ok and c["kind"] == "tractor" and int(c["dir"]) == trk_dir and float(c["lateral"]) == 0.0 \
			and float(c["speed"]) <= 30.0 / 3.6 + 1e-4
	_check(trk_ok, "piste à une voie : des tracteurs, un seul sens, au milieu, 30 km/h au plus")
	var lane_ok := true
	for p in roads:
		var speeds := {}
		for c in p["cars"]:
			var key := Vector2i(int(c["dir"]), int(round(float(c["lateral"]) * 10.0)))
			if speeds.has(key):
				lane_ok = lane_ok and is_equal_approx(float(speeds[key]), float(c["speed"]))
			speeds[key] = c["speed"]
			lane_ok = lane_ok and float(c["speed"]) <= float(RoadTraffic.TrafficModel.KINDS[c["kind"]]["kmh"].y) / 3.6 + 1e-4
	_check(lane_ok, "même vitesse pour tous les véhicules d'une voie, jamais plus que leur sorte")

	# 2. Champs
	var fields := RoadTraffic.field_paths(_fields(), _height)
	var inside := true
	var on_ground := true
	var ids := []
	for f in fields:
		ids.append(f["id"])
		var id: String = f["id"]
		var i := int(id.get_slice("_", 1))
		var x0 := 1600.0 + 400.0 * i
		for p in f["pts"]:
			inside = inside and p.x >= x0 and p.x <= x0 + 300.0 and p.z <= -400.0 and p.z >= -600.0
			on_ground = on_ground and absf(p.y - _height(p.x, p.z)) < 1e-3
		var cars: Array = f["cars"]
		inside = inside and cars.size() == 1 and cars[0]["kind"] == RoadTraffic.FIELD_KIND
	_check(fields.size() >= 1 and fields.size() < FIELDS and not ids.has("field:small") and not ids.has("field:pre"),
		"champs : %d grands champs sur %d avec leur tracteur (petit champ et pré écartés)" % [fields.size(), FIELDS])
	if fields.is_empty():
		print("test_road_traffic_model : %d vérifications, %d échecs" % [_checked, _failures])
		quit(1)
		return
	_check(inside and on_ground, "rangs du tracteur dans le champ, posés sur le sol")
	var rows := RoadTraffic.field_rows(PackedVector2Array([Vector2(0, 0), Vector2(300, 0), Vector2(300, 200), Vector2(0, 200)]), 0.0)
	_check(rows.size() == 2 * 14 and absf(rows[1].x - rows[0].x - (300.0 - 2.0 * RoadTraffic.FIELD_MARGIN_M)) < 0.01
		and absf(rows[2].y - rows[1].y - RoadTraffic.FIELD_ROW_M) < 0.01 and rows[2].x == rows[1].x,
		"rangs : 14 au plus, tous les %.0f m, en zigzag (%d points)" % [RoadTraffic.FIELD_ROW_M, rows.size()])
	var fp: Dictionary = fields[0]
	var p0: Dictionary = RoadTraffic.place(fp, 0, 0.0)
	var p1: Dictionary = RoadTraffic.place(fp, 0, 10.0)
	var back: Dictionary = RoadTraffic.place(fp, 0, 2.0 * float(fp["length"]) / RoadTraffic.FIELD_SPEED_MPS)
	_check(absf((p1["pos"] as Vector3).distance_to(p0["pos"]) - 22.0) < 3.0 and (back["pos"] as Vector3).distance_to(p0["pos"]) < 0.01,
		"tracteur à %.1f m/s, aller et retour sur ses rangs" % RoadTraffic.FIELD_SPEED_MPS)

	# 3. Circulation : 2 minutes à 30 images/s, caméra près de la route secondaire
	var m = _model(24)
	var cam := Vector3(700.0, 300.0, 140.0)
	var dt := 1.0 / 30.0
	var max_live := 0
	var far := 0
	var wrong_side := 0
	var overlap := 0
	var pitch_bad := 0
	var kinds := {}
	var eased := false
	var usec := 0
	var frames := 0
	var log := []
	for f in range(3600):
		var t0 := Time.get_ticks_usec()
		m.update(cam, dt)
		usec += Time.get_ticks_usec() - t0
		frames += 1
		var vs: Array = m.vehicles
		max_live = maxi(max_live, vs.size())
		if f % 300 == 0:
			log.append(str(vs))
		for v in vs:
			var tr: Transform3D = v["xform"]
			kinds[v["kind"]] = true
			if tr.origin.distance_to(cam) > RoadTraffic.RANGE_M + 1.0:
				far += 1
			var fwd := -tr.basis.z.normalized()
			eased = eased or tr.basis.get_scale().x < 0.99
			if absf(tr.origin.z - SECONDARY_Z) < 5.0:
				if (fwd.x > 0.0) != (tr.origin.z > SECONDARY_Z):
					wrong_side += 1
				if absf(fwd.y / Vector2(fwd.x, fwd.z).length() - SLOPE * signf(fwd.x)) > 1e-3:
					pitch_bad += 1
		for i in range(vs.size()):
			for j in range(i + 1, vs.size()):
				var a: Vector3 = (vs[i]["xform"] as Transform3D).origin
				var b: Vector3 = (vs[j]["xform"] as Transform3D).origin
				if Vector2(a.x - b.x, a.z - b.z).length() < 3.0:
					overlap += 1
	var avg := usec / 1000.0 / frames
	_check(max_live >= 5 and max_live <= 24 and far == 0, "budget 24 : jusqu'à %d véhicules, tous à moins de %.0f m" % [max_live, RoadTraffic.RANGE_M])
	_check(wrong_side == 0 and pitch_bad == 0, "route à double sens : chacun sur la voie de droite de son sens, penché comme la route")
	_check(overlap == 0, "jamais deux véhicules au même endroit")
	_check(kinds.size() >= 4 and eased, "sortes vues : %s ; véhicules qui grandissent au bout de la route" % str(kinds.keys()))
	_check(m.reselects >= 230 and m.reselects <= 250, "tri des plus proches toutes les %.1f s (%d tris)" % [RoadTraffic.RESELECT_S, m.reselects])
	print("Circulation lointaine : %.4f ms par image" % avg)
	_check(PerfBudget.check("road_traffic_frame", avg), "mise à jour en %.4f ms par image" % avg)

	# 4. Les plus proches gardés
	var all := []
	for k in m.paths:
		for path in m.paths[k]:
			for j in range((path["cars"] as Array).size()):
				var pl: Dictionary = RoadTraffic.place(path, j, m.clock_s)
				if not pl.is_empty():
					all.append((pl["pos"] as Vector3).distance_to(cam))
	all.sort()
	var small = _model(3)
	small.clock_s = m.clock_s
	small.update(cam, 0.0)
	var worst := 0.0
	for v in small.vehicles:
		worst = maxf(worst, (v["xform"] as Transform3D).origin.distance_to(cam))
	_check(small.vehicles.size() == 3 and absf(worst - float(all[2])) < 0.01, "budget 3 : les trois plus proches de la caméra")

	# 5. Déterminisme, pause, retrait, budget nul
	var m2 = _model(24)
	var log2 := []
	for f in range(3600):
		m2.update(cam, dt)
		if f % 300 == 0:
			log2.append(str(m2.vehicles))
	_check(log2 == log, "même routes, même horloge : même circulation")
	var before := str(m2.vehicles)
	for i in range(30):
		m2.update(cam, dt, true)
	_check(str(m2.vehicles) == before, "pause : circulation figée")
	m2.remove_chunk(0)
	m2.remove_chunk(1)
	m2.update(cam, dt)
	_check(m2.vehicles.is_empty() and m2.path_count() == 0, "tronçons retirés : plus de véhicule")
	var m0 = _model(0)
	m0.update(cam, dt)
	_check(m0.vehicles.is_empty(), "budget nul : aucun véhicule")

	# 6. Affichage
	var view = RoadTrafficRenderer.new()
	root.add_child(view)
	await process_frame
	var n0: int = view.get_child_count()
	view.setup(m)
	view.set_budget(24)
	var shown_ok := true
	var vusec := 0
	for f in range(300):
		m.update(cam, dt)
		var t1 := Time.get_ticks_usec()
		view.update()
		vusec += Time.get_ticks_usec() - t1
		var per := {}
		for v in m.vehicles:
			per[v["kind"]] = int(per.get(v["kind"], 0)) + 1
		for kind in RoadTrafficRenderer.KINDS:
			shown_ok = shown_ok and view.count_of(kind) == int(per.get(kind, 0))
	_check(shown_ok and view.visible_count() == m.vehicles.size(), "affichage : une case de MultiMesh par véhicule, de sa sorte")
	view.set_lights(true)
	var lit: bool = view.instance_custom().r == 1.0
	view.set_lights(false)
	_check(lit and view.instance_custom().r == 0.0, "phares dans les données d'instance")
	_check(view.get_child_count() == n0, "aucun nœud créé après le démarrage")
	var vavg := vusec / 1000.0 / 300.0
	_check(PerfBudget.check("road_traffic_view_frame", vavg), "affichage en %.4f ms par image" % vavg)
	view.queue_free()
	await process_frame
	print("test_road_traffic_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
