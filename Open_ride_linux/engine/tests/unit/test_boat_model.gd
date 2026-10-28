extends SceneTree

## Tests sans écran des bateaux du Lot P29 : maillages `boat_mesh.gd` (tailles, flottaison, faces), chemins
## et positions de `boat_model.gd` (lac avec une île, étang, ruisseau, canal, rivière, mer passée
## directement), comportement (voiliers qui gîtent sous le vent, petits bateaux rentrés par grand vent ou
## sous la pluie), budget, déterminisme, pause, tronçons, et affichage `boat_renderer.gd`.
## Lancement : godot --headless --path engine --script res://tests/unit/test_boat_model.gd

const BoatModel := preload("res://scripts/boat_model.gd")
const BoatRenderer := preload("res://scripts/boat_renderer.gd")
const BoatMesh := preload("res://scripts/boat_mesh.gd")
const SoundPlayer := preload("res://scripts/sound_player.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")

const CALM := {"dir": Vector3(1.0, 0.0, 0.0), "strength": 0.2, "gust": 0.0}
const CLEAR := {"rain": 0.0, "fog_boost": 0.0}
const LEVEL := 300.0

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _init() -> void:
	call_deferred("_run")


## Lac de 40 ha environ (contour irrégulier), île de 80 m au milieu.
func _lake(id: String, ox: float = 0.0) -> Dictionary:
	var outer := []
	for i in range(24):
		var a := TAU * i / 24.0
		var r := 360.0 + 25.0 * sin(3.0 * a)
		outer.append([ox + r * cos(a), r * 0.95 * sin(a)])
	var hole := [[ox - 40.0, -40.0], [ox + 40.0, -40.0], [ox + 40.0, 40.0], [ox - 40.0, 40.0]]
	return {"id": id, "kind": "lake", "level_y": LEVEL, "outer": outer, "holes": [hole]}


func _pond(id: String) -> Dictionary:
	return {"id": id, "kind": "pond", "level_y": LEVEL, "outer": [[0, 0], [60, 0], [60, 50], [0, 50]], "holes": []}


func _line(id: String, kind: String, width: float, length: float, z: float = 0.0) -> Dictionary:
	var pts := []
	for i in range(21):
		var x := -length * 0.5 + length * i / 20.0
		pts.append([x, z + 30.0 * sin(x / 300.0), LEVEL - 0.001 * x])
	return {"id": id, "kind": kind, "width_m": width, "points": pts}


func _sea() -> Dictionary:
	return {"id": "mer", "kind": "sea", "level_y": 0.0, "outer": [[-20000, -7000], [20000, -7000], [20000, 7000], [-20000, 7000]], "holes": []}


func _shape_of(a: Dictionary) -> Dictionary:
	var holes := []
	for h in a["holes"]:
		holes.append(BoatModel._ring(h))
	return {"outer": BoatModel._ring(a["outer"]), "holes": holes, "road": PackedVector2Array(), "margin": 0.0}


func _run() -> void:
	_test_meshes()

	# 1. Lac avec une île : voiliers, barques, pédalo, tous dans l'eau et écartés
	var lake := _lake("lac")
	var lake_paths := BoatModel.area_paths(lake)
	var kinds := {}
	for p in lake_paths:
		var k: String = p["boats"][0]["kind"]
		kinds[k] = int(kinds.get(k, 0)) + 1
	print("Lac de 40 ha : %s" % str(kinds))
	_check(int(kinds.get("sailboat", 0)) >= 3 and int(kinds.get("sailboat", 0)) <= 6 and int(kinds.get("rowboat", 0)) <= 3
		and int(kinds.get("rowboat", 0)) >= 1, "lac de 40 ha : %d voiliers, %d barques" % [int(kinds.get("sailboat", 0)), int(kinds.get("rowboat", 0))])
	var pedalos := 0
	var pedalo_ok := true
	for i in range(12):
		var a := _lake("lac%d" % i)
		for p in BoatModel.area_paths(a):
			if p["boats"][0]["kind"] == "pedalo":
				pedalos += 1
				pedalo_ok = pedalo_ok and BoatModel._shore_dist(_shape_of(a), p["centre"]) <= BoatModel.PEDALO_SHORE_M
	_check(pedalos >= 3 and pedalos <= 10 and pedalo_ok, "pédalos près du bord sur %d lacs sur 12" % pedalos)
	var shape := _shape_of(lake)
	var wet := true
	var apart := true
	var mi = BoatModel.new()
	mi.set_budget(64)
	mi.set_chunk(0, lake_paths)
	for step in range(240):
		mi.update(Vector3(0.0, LEVEL + 2.0, 0.0), 2.5, CALM, CLEAR)
		var pos := []
		for b in mi.boats:
			var o: Vector3 = (b["xform"] as Transform3D).origin
			wet = wet and BoatModel._shore_dist(shape, Vector2(o.x, o.z)) >= BoatModel.LOOP_MARGIN_M - 0.5 and absf(o.y - LEVEL) < 0.3
			for q in pos:
				apart = apart and Vector2(o.x, o.z).distance_to(q) >= BoatModel.SEPARATION_M
			pos.append(Vector2(o.x, o.z))
	_check(wet, "10 min : bateaux toujours sur l'eau, à %d m du bord et de l'île au moins" % int(BoatModel.LOOP_MARGIN_M))
	_check(apart, "jamais deux bateaux à moins de %d m" % int(BoatModel.SEPARATION_M))
	_check(BoatModel.area_paths(_pond("etang")).is_empty() and BoatModel.line_paths(_line("ru", "stream", 3.0, 800.0)).is_empty(),
		"étang de 0,3 ha et ruisseau : rien")
	var ponds := 0
	for i in range(30):
		ponds += BoatModel.area_paths({"id": "e%d" % i, "kind": "pond", "level_y": LEVEL,
			"outer": [[0, 0], [100, 0], [100, 80], [0, 80]], "holes": []}).size()
	_check(ponds >= 4 and ponds <= 18, "étang de 0,8 ha : une barque sur %d étangs sur 30" % ponds)
	var road := PackedVector2Array([Vector2(-500.0, 0.0), Vector2(500.0, 0.0)])
	var near_road := false
	for p in BoatModel.area_paths(lake, road):
		for j in range(BoatModel.LOOP_POINTS):
			var q := BoatModel._ellipse(p["centre"], p["radii"], p["angle"], TAU * j / BoatModel.LOOP_POINTS)
			near_road = near_road or absf(q.y) < BoatModel.ROAD_CLEAR_M
	_check(not near_road, "route qui traverse le lac : aucune boucle à moins de %d m" % int(BoatModel.ROAD_CLEAR_M))

	# 2. Canal et rivière
	var canal := BoatModel.line_paths(_line("canal", "canal", 15.0, 6000.0))
	var river := BoatModel.line_paths(_line("riv", "river", 12.0, 12000.0))
	_check(canal.size() == 1 and canal[0]["boats"][0]["kind"] == "barge" and river.size() == 1
		and river[0]["boats"][0]["kind"] in ["canoe", "kayak"], "canal de 15 m : péniches ; rivière de 12 m : canoës et kayaks")
	var dirs := {}
	var right_ok := true
	for j in range((canal[0]["boats"] as Array).size()):
		var b: Dictionary = canal[0]["boats"][j]
		dirs[b["dir"]] = true
		for t in [0.0, 300.0, 900.0]:
			var pl := BoatModel.place(canal[0], j, t)
			if pl.is_empty():
				continue
			var axis := BoatModel.place({"type": "line", "length": canal[0]["length"], "spacing": canal[0]["spacing"],
				"cum": canal[0]["cum"], "pts": canal[0]["pts"], "boats": [b.merged({"lateral": 0.0}, true)]}, 0, t)
			var f: Vector2 = pl["fwd"]
			var off: Vector3 = pl["pos"] - axis["pos"]
			right_ok = right_ok and absf(Vector2(off.x, off.z).dot(Vector2(-f.y, f.x)) - 15.0 * 0.25) < 0.01
	_check(dirs.size() == 2 and right_ok, "péniches dans les deux sens, chacune sur sa moitié droite (à 3,75 m de l'axe)")
	var down := []
	var up := []
	for b in river[0]["boats"]:
		(down if b["dir"] == 1 else up).append(float(b["speed"]))
	_check(not down.is_empty() and not up.is_empty() and down.min() > up.max(),
		"rivière : plus vite dans le sens du courant (%s contre %s m/s)" % [str(down), str(up)])
	_check(BoatModel.line_paths(_line("grand", "river", 40.0, 4000.0)).size() == 2 and BoatModel.line_paths(_line("c8", "canal", 8.0, 4000.0)).is_empty(),
		"grande rivière : péniches et canoës ; canal de 8 m : rien")

	# 3. Mer : voiliers près de la côte, ferry et cargo au large
	var sea := BoatModel.area_paths(_sea())
	var sea_kinds := {}
	var shore_ok := true
	var sshape := _shape_of(_sea())
	for p in sea:
		var k: String = p["boats"][0]["kind"]
		sea_kinds[k] = true
		if k == "sailboat":
			shore_ok = shore_ok and BoatModel._shore_dist(sshape, p["centre"]) <= BoatModel.SEA_SAIL_SHORE_M
		else:
			var mid: Vector3 = (p["pts"][0] + p["pts"][1]) * 0.5
			var d := BoatModel._shore_dist(sshape, Vector2(mid.x, mid.z))
			shore_ok = shore_ok and d >= BoatModel.SHIP_SHORE_M.x - 1.0 and float(p["length"]) >= BoatModel.SHIP_MIN_M - 1.0 \
				and float(p["length"]) <= BoatModel.SHIP_LEG_M + 1.0
	_check(sea_kinds.has("sailboat") and sea_kinds.has("ferry") and sea_kinds.has("cargo") and shore_ok,
		"mer : voiliers près de la côte, ferry et porte-conteneurs au large (%s)" % str(sea_kinds.keys()))
	var ms = BoatModel.new()
	ms.set_budget(16)
	ms.set_chunk(0, sea)
	var ferry_seen := 0.0
	var ferry_mid := Vector3.ZERO
	for p in sea:
		if p["boats"][0]["kind"] == "ferry":
			ferry_mid = (p["pts"][0] + p["pts"][1]) * 0.5 + Vector3(0.0, 2.0, 0.0)
			break
	for i in range(1800):
		ms.update(ferry_mid, 1.0, CALM, CLEAR)
		if ms.count("ferry") > 0:
			ferry_seen += 1.0
	_check(ferry_seen > 0.0 and ferry_seen < 1800.0, "30 min près de sa ligne : le ferry passe puis repart (%d s en vue)" % int(ferry_seen))

	# 4. Comportement : gîte, bôme sous le vent, grand vent, pluie
	var pl0 := {"pos": Vector3.ZERO, "fwd": Vector2(0.0, -1.0), "scale": 1.0}
	var beam := {"dir": Vector3(1.0, 0.0, 0.0), "strength": 0.1}
	var strong := {"dir": Vector3(1.0, 0.0, 0.0), "strength": 0.6}
	var p1 := BoatModel.pose("sailboat", pl0, 0.0, false, 0.0, beam)
	var p2 := BoatModel.pose("sailboat", pl0, 0.0, false, 0.0, strong)
	var p0 := BoatModel.pose("sailboat", pl0, 0.0, false, 0.0, {"dir": Vector3(1.0, 0.0, 0.0), "strength": 0.0})
	_check(absf(float(p2["roll"]) - float(p0["roll"])) > absf(float(p1["roll"]) - float(p0["roll"])) * 3.0 and float(p2["sail"]) > 0.5,
		"voilier vent de travers : bôme sous le vent (%.2f rad), gîte plus forte par vent fort" % float(p2["sail"]))
	var mixed = BoatModel.new()
	mixed.set_budget(64)
	mixed.set_chunk(0, lake_paths + canal + river)
	var cam := Vector3(0.0, LEVEL + 2.0, 0.0)
	mixed.update(cam, 0.1, CALM, CLEAR)
	var n_calm: int = mixed.boats.size()
	mixed.update(cam, 0.1, {"dir": Vector3.RIGHT, "strength": 0.9}, CLEAR)
	var storm_ok: bool = mixed.count("sailboat") + mixed.count("rowboat") + mixed.count("pedalo") == 0
	mixed.update(cam, 0.1, CALM, {"rain": 0.5, "fog_boost": 0.0})
	var rain_ok: bool = mixed.count("pedalo") + mixed.count("canoe") + mixed.count("kayak") == 0 and mixed.count("sailboat") > 0
	_check(n_calm > 0 and storm_ok and rain_ok, "grand vent : voiliers, barques et pédalos rentrés ; pluie : pédalos et canoës rentrés")

	# 5. Budget, plus proches, déterminisme, pause, tronçons
	var mb = BoatModel.new()
	mb.set_budget(3)
	mb.set_chunk(0, lake_paths)
	mb.set_chunk(1, BoatModel.area_paths(_lake("lac")))   # même lac vu par deux tronçons
	var mfull = BoatModel.new()
	mfull.set_budget(64)
	mfull.set_chunk(0, lake_paths)
	mb.update(cam, 0.1, CALM, CLEAR)
	mfull.update(cam, 0.1, CALM, CLEAR)
	var dists := []
	for b in mfull.boats:
		dists.append(float(b["dist"]))
	dists.sort()
	var kept := []
	for b in mb.boats:
		kept.append(float(b["dist"]))
	kept.sort()
	_check(mb.boats.size() == 3 and absf(kept[2] - dists[2]) < 0.01, "budget 3 : les 3 plus proches")
	var mdup = BoatModel.new()
	mdup.set_budget(64)
	mdup.set_chunk(0, lake_paths)
	mdup.set_chunk(1, BoatModel.area_paths(_lake("lac")))
	mdup.update(cam, 0.1, CALM, CLEAR)
	_check(mdup.boats.size() == mfull.boats.size(), "lac vu par deux tronçons : compté une fois (%d bateaux)" % mdup.boats.size())
	_check(str(BoatModel.area_paths(_lake("lac"))) == str(lake_paths) and str(BoatModel.area_paths(_lake("autre"))) != str(lake_paths),
		"déterministe : même lac, mêmes boucles ; autre lac, autres boucles")
	var before := str(mfull.boats)
	for i in range(20):
		mfull.update(cam, 0.1, CALM, CLEAR, true)
	_check(str(mfull.boats) == before, "pause : bateaux figés")
	mfull.remove_chunk(0)
	mfull.update(cam, 0.1, CALM, CLEAR)
	_check(mfull.boats.is_empty() and mfull.path_count() == 0, "tronçon retiré : bateaux retirés")

	# 6. Affichage et coût par image
	var sp = SoundPlayer.new()
	root.add_child(sp)
	var view = BoatRenderer.new()
	root.add_child(view)
	await process_frame
	var n0: int = view.get_child_count()
	var mv = BoatModel.new()
	mv.set_budget(16)
	mv.set_chunk(0, lake_paths + canal + river)
	view.setup(mv, sp)
	var match_ok := true
	var wake_ok := false
	var sail_ok := false
	var model_us := 0
	var view_us := 0
	var frames := 0
	var wind := {"dir": Vector3(0.6, 0.0, 0.8), "strength": 0.4}
	for i in range(3000):
		var t0 := Time.get_ticks_usec()
		mv.update(Vector3(-200.0 + 0.2 * i, LEVEL + 2.0, 100.0), 0.2, wind, CLEAR)
		var t1 := Time.get_ticks_usec()
		view.update()
		var t2 := Time.get_ticks_usec()
		model_us += t1 - t0
		view_us += t2 - t1
		frames += 1
		for kind in BoatModel.MAX_AT_ONCE:
			match_ok = match_ok and view.visible_count(kind) == mv.count(kind)
		for slot in view._slots["sailboat"]:
			if slot["root"].visible:
				wake_ok = wake_ok or (slot["wake"].visible and slot["wake"].scale.z > 10.0)
				sail_ok = sail_ok or absf(slot["sail"].rotation.y) > 0.2
	_check(match_ok, "affichage : un bateau affiché par bateau du modèle, de sa sorte")
	_check(wake_ok and sail_ok, "sillage derrière les voiliers, grand-voile tournée par le vent")
	_check(view._slots["barge"][0]["audio"].stream == sp.stream("barge_engine") and view._slots["ferry"][0]["audio"].stream == sp.stream("ship_horn")
		and view.get_child_count() == n0, "diesel des péniches et corne du ferry ; aucun nœud créé après le démarrage")
	var m_ms := model_us / 1000.0 / frames
	var v_ms := view_us / 1000.0 / frames
	print("Bateaux : modèle %.4f ms, affichage %.4f ms par image" % [m_ms, v_ms])
	_check(PerfBudget.check("boats_frame", m_ms), "modèle des bateaux en %.4f ms par image" % m_ms)
	_check(PerfBudget.check("boats_view_frame", v_ms), "affichage des bateaux en %.4f ms par image" % v_ms)
	view.queue_free()
	sp.queue_free()
	await process_frame
	print("test_boat_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)


func _test_meshes() -> void:
	var ok := true
	var faces_ok := true
	var report := []
	for kind in BoatMesh.KINDS:
		var mesh: ArrayMesh = BoatMesh.build(kind)
		var arr := mesh.surface_get_arrays(0)
		var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var normals: PackedVector3Array = arr[Mesh.ARRAY_NORMAL]
		var a := mesh.get_aabb()
		var size: Vector2 = BoatMesh.SIZE[kind]
		var tris := verts.size() / 3
		report.append("%s %d" % [kind, tris])
		ok = ok and tris <= (6000 if kind in ["ferry", "cargo"] else 2000) and absf(a.size.z - size.x) <= size.x * 0.06 \
			and a.size.x >= size.y * 0.95 and a.position.y < 0.0 and a.end.y > 0.0
		for t in range(0, verts.size(), 3):
			var fn := (verts[t + 1] - verts[t]).cross(verts[t + 2] - verts[t])
			if fn.length() > 1e-7 and fn.dot(normals[t] + normals[t + 1] + normals[t + 2]) > 0.0:
				faces_ok = false
	_check(ok, "maillages des bateaux à leur taille, flottaison à y = 0 (%s)" % ", ".join(report))
	_check(faces_ok, "faces orientées comme leurs normales")
	var w := BoatMesh.build("wake").get_aabb()
	_check(absf(w.end.z - 1.0) < 1e-4 and w.position.z >= -1e-4 and absf(w.position.y - 0.03) < 1e-4, "sillage de longueur 1 à plat sur l'eau")
	var cs: Array = BoatMesh.colors("sailboat", 5)
	_check(cs[0] == BoatMesh.SAILBOAT_PAINT[1], "couleurs reprises modulo leur palette")
