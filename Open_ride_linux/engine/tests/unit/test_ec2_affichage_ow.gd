extends SceneTree

## Revue de code EC2 (affichage du monde ouvert) : l'ancien décor n'est retiré qu'une fois le nouveau prêt, et une
## révision de la route ne refait que ce qui change. Constats E5-01, E5-03, E5-04, E5-05, E7-01, E7-10, E8-01, E8-03.
## Sans écran (maillages sans rendu).
## Lancement : godot --headless --path engine --script res://tests/unit/test_ec2_affichage_ow.gd

const LiveWorld := preload("res://scripts/live_world.gd")
const WorldStreamer := preload("res://scripts/world_streamer.gd")
const OsmStreamer := preload("res://scripts/osm_streamer.gd")
const OsmLayers := preload("res://scripts/osm_layers.gd")
const GrassTufts := preload("res://scripts/grass_tufts.gd")
const RouteRevision := preload("res://scripts/route_revision.gd")
const AtmosphereModel := preload("res://scripts/atmosphere_model.gd")

## Départ de la route dans son carré : 800 m (cas du constat E5-03).
const X0 := 800.0

var _checked := 0
var _failures := 0


func _check(ok: bool, what: String) -> void:
	_checked += 1
	if not ok:
		_failures += 1
		printerr("[ÉCHEC] ", what)
	else:
		print("[OK] ", what)


func _write_json(path: String, obj: Variant) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(JSON.stringify(obj))
	f.close()


func _remove_tree(path: String) -> void:
	var d := DirAccess.open(path)
	if d == null:
		return
	for sub in d.get_directories():
		_remove_tree(path.path_join(sub))
	for f in d.get_files():
		d.remove(f)
	DirAccess.remove_absolute(path)


## Partie k d'une route droite vers l'est qui part de x = X0, z = 0.
func _part(k: int, length: float) -> Dictionary:
	var lo := 1000.0 * k
	var hi := minf(1000.0 * (k + 1), length)
	var part := {"version": "1.0", "ds_m": 10.0, "length_m": hi - lo, "type": "open", "s0_m": lo,
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	var s := lo
	while s <= hi + 1e-6:
		part["lat"].append(45.0)
		part["lon"].append(6.0 + s * 1.27e-5)
		part["alt_m"].append(600.0)
		part["x"].append(X0 + s)
		part["z"].append(0.0)
		part["grade_pct"].append(0.0)
		part["heading_deg"].append(90.0)
		s += 10.0
	part["n"] = part["x"].size()
	return part


func _publish(dir: String, length: float, rev: int, changed_from: int, first_part: int) -> void:
	for k in range(first_part, int(ceil(length / 1000.0))):
		_write_json(dir.path_join("route").path_join("part_%d.json" % k), _part(k, length))
	_write_json(dir.path_join("junctions.json"), {"version": "1.0", "revision": rev, "junctions": []})
	_write_json(dir.path_join("live.json"), {"version": "1.0", "revision": rev,
		"route": {"parts": int(ceil(length / 1000.0)), "length_m": length, "changed_from_part": changed_from},
		"tiles": {"near": [], "far": []}, "layer_tiles": [], "status": "ok"})


## Un bâtiment au milieu du carré (ix, 0), au bord de la route.
func _write_building(dir: String, ix: int) -> void:
	var b := {"id": "w%d" % ix, "outer": [[500.0, 40.0], [520.0, 40.0], [520.0, 60.0], [500.0, 60.0]], "holes": [],
		"base_y": 600.0, "height_m": 6.0, "roof": "flat", "hint": {"building": "house", "colour": null}}
	_write_json(dir.path_join("buildings").path_join("tile_%d_0.json" % ix), {"version": "1.0", "buildings": [b]})


func _buildings_of(osm, k: int) -> int:
	var shapes: Dictionary = osm._shapes_by_chunk.get(k, {})
	return (shapes.get("buildings", []) as Array).size()


func _init() -> void:
	var base := "user://ec2_ow_%d" % OS.get_process_id()
	var dir := base.path_join("ow-test.world")
	_write_json(dir.path_join("manifest.json"), {"format": "openride-world", "format_version": "1.4", "live": true,
		"layers": {"buildings": {"present": true}}})
	for ix in [0, 1, 2, 4, 5]:   # carré 3 absent : pas encore produit par le générateur (E5-05)
		_write_building(dir, ix)
	_publish(dir, 2500.0, 1, 0, 0)
	var lw = LiveWorld.new()
	_check(lw.open(dir), "monde vivant ouvert")
	var route_a = lw.route

	_test_road_kept(dir, lw)
	_test_same_span(route_a, lw.route)
	_test_osm(dir, route_a)
	_test_marks(dir, lw.route)
	_test_grass(route_a, lw.route)
	_test_atmosphere_cache()

	lw.close()
	_remove_tree(base)
	print("test_ec2_affichage_ow : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _test_same_span(route_a, route_b) -> void:
	_check(not is_same(route_a, route_b) and RouteRevision.same_span(route_a, route_b, 2000.0, 2040.0),
		"route révisée : tronçon réécrit mais identique gardé")
	_check(not RouteRevision.same_span(route_a, route_b, 2480.0, 2520.0), "tronçon qui dépasse l'ancienne fin : à refaire")
	_check(not RouteRevision.same_span(null, route_a, 0.0, 40.0), "pas d'ancienne route : à refaire")


## E5-01 : le ruban du kilomètre réécrit reste affiché jusqu'à son remplaçant.
func _test_road_kept(dir: String, lw) -> void:
	var st = WorldStreamer.new()
	root.add_child(st)
	st.set_world(lw.route, dir)
	st.osm_streamer = null
	st.update_window(1500.0, 0.0, Vector3(X0 + 1500.0, 1.4, 0.0))
	st.flush()
	var old_2 = st._instances.get("road:2", null)
	_check(old_2 != null and st._instances.has("road:1"), "tronçons 1 et 2 affichés")
	_publish(dir, 4500.0, 2, 2, 2)
	lw.on_open_world({"rev": 2})
	var upd: Dictionary = lw.wait_poll()
	_check(upd.has("route") and int(upd.get("from_part", -1)) == 2, "révision 2 : route changée depuis la partie 2")
	st.swap_route(upd["route"], int(upd["from_part"]))
	_check(is_same(st._instances.get("road:2", null), old_2), "tronçon 2 encore affiché après la révision (pas de trou)")
	_check(st.stale_keys("road").has("road:2"), "tronçon 2 noté à refaire")
	st.update_window(1500.0, 0.0, Vector3(X0 + 1500.0, 1.4, 0.0))
	st.flush()
	_check(st._instances.has("road:2") and not is_same(st._instances["road:2"], old_2), "tronçon 2 remplacé une fois prêt")
	_check(st.stale_keys("road").is_empty(), "plus rien à refaire")
	st.clear()
	st.queue_free()


## E5-03, E5-05, E5-01 côté OSM.
func _test_osm(dir: String, route_a) -> void:
	var osm = OsmStreamer.new()
	root.add_child(osm)
	osm.set_world(route_a, dir)
	# Carré 2 (x de 2 000 à 3 000 m) confié au tronçon 0 (boîte élargie de 300 m) : le cycliste y roule encore en
	# s = 2 100 (x = 2 900), alors que la fenêtre (1 tronçon derrière) ne garde plus le tronçon 0.
	_check(OsmLayers.chunk_tiles(route_a, 0).has(Vector2i(2, 0)), "(carré 2 confié au tronçon 0)")
	osm.update_window(1100.0, 2500.0)
	osm.flush()
	_check(not osm._chunk_instances.has(0), "(sans caméra : tronçon 0 hors de la fenêtre, libéré)")
	osm.update_window(1100.0, 2500.0, Vector2(X0 + 2100.0, 0.0))
	osm.flush()
	_check(osm._chunk_instances.has(0) and _buildings_of(osm, 0) >= 3,
		"caméra dans le carré 2 : tronçon 0 gardé, bâtiments du carré affichés (%d)" % _buildings_of(osm, 0))
	_check(osm._chunk_instances.has(1) and _buildings_of(osm, 1) == 0, "tronçon 1 construit sans le carré 3 (absent)")
	# E5-05 : le carré 3 arrive ; le tronçon 1, déjà construit, est refait, ses nœuds gardés jusque-là.
	_write_building(dir, 3)
	var nodes_1: Array = osm._chunk_instances[1]
	osm.swap_route(route_a, route_a.parts.size(), [Vector2i(3, 0)])
	_check(osm.stale_chunk_keys().has(1) and is_same(osm._chunk_instances[1], nodes_1),
		"carré 3 arrivé : tronçon 1 à refaire, anciens nœuds gardés")
	_check(not osm.stale_chunk_keys().has(0), "tronçon 0 (carrés 0 à 2) : gardé tel quel")
	osm.update_window(1100.0, 2500.0, Vector2(X0 + 2100.0, 0.0))
	osm.flush()
	_check(_buildings_of(osm, 1) == 1, "tronçon 1 refait avec le bâtiment du carré 3 (%d)" % _buildings_of(osm, 1))
	# E5-01 : révision depuis le tronçon 1 : nœuds gardés jusqu'à l'intégration des nouveaux.
	nodes_1 = osm._chunk_instances[1]
	osm.swap_route(route_a, 1)
	_check(is_same(osm._chunk_instances.get(1), nodes_1), "révision : tronçon 1 encore affiché")
	osm.update_window(1100.0, 2500.0, Vector2(X0 + 2100.0, 0.0))
	osm.flush()
	_check(osm._chunk_instances.has(1) and not is_same(osm._chunk_instances[1], nodes_1) and osm.stale_chunk_keys().is_empty(),
		"tronçon 1 remplacé une fois prêt")
	osm.clear()
	osm.queue_free()


## E5-04 et E7-10 : tuiles déjà affichées sous la route nouvelle, ou voisines d'une tuile proche arrivée.
func _test_marks(dir: String, route_b) -> void:
	var st = WorldStreamer.new()
	root.add_child(st)
	st.set_world(route_b, dir)
	st.osm_streamer = null
	for key in ["far:0:0", "far:1:0", "far:3:0", "near:3:0", "near:0:0", "near:6:0", "near:9:0"]:
		var mi := MeshInstance3D.new()
		st.add_child(mi)
		st._instances[key] = mi
	st._mark_under_new_road(2000.0)   # x de 2 800 à 5 300 m
	var far: Array = st.stale_keys("far")
	var near: Array = st.stale_keys("near")
	_check(far.has("far:0:0") and far.has("far:1:0") and not far.has("far:3:0"),
		"route nouvelle : tuiles lointaines traversées à refaire (%s)" % str(far))
	_check(near.has("near:3:0") and not near.has("near:0:0"), "route nouvelle : tuile proche traversée à refaire (%s)" % str(near))
	st._stale_near.clear()
	st._mark_arrived_near([Vector2i(7, 0)])
	_check(st.stale_keys("far") == ["far:1:0"], "tuile proche arrivée : tuile lointaine qui la contient à refaire")
	_check(st.stale_keys("near") == ["near:6:0"], "tuile proche arrivée : voisine affichée à refaire (raccord)")
	_check(st._instances.size() == 7, "rien retiré en attendant")
	st.clear()
	st.queue_free()


## E7-01 : herbe gardée sur les tronçons dont la route ne change pas.
func _test_grass(route_a, route_b) -> void:
	var g = GrassTufts.new()
	root.add_child(g)
	g.configure(2000, route_a)
	var cam_s := 2380.0   # fenêtre jusqu'au bout de la route de 2 500 m
	for i in range(400):
		g.update(cam_s)
	var before: PackedInt64Array = g._slot_chunk.duplicate()
	var children := g.get_child_count()
	var visible_before: int = g._visible_count
	g.retarget(route_b, null)
	var kept := 0
	var reset := 0
	for i in range(before.size()):
		var k: int = before[i]
		if (k + 1) * GrassTufts.CHUNK_M <= 2500.0:
			if g._slot_chunk[i] == k:
				kept += 1
		elif g._slot_chunk[i] == GrassTufts.NO_CHUNK:
			reset += 1
	var beyond := 0
	for k in before:
		if (k + 1) * GrassTufts.CHUNK_M > 2500.0:
			beyond += 1
	_check(kept == before.size() - beyond and kept > 0, "herbe : tronçons sur la même route gardés (%d)" % kept)
	_check(reset == beyond and beyond > 0, "herbe : tronçons au bout de l'ancienne route refaits (%d)" % reset)
	_check(g.get_child_count() == children and g._visible_count > 0 and g._visible_count <= visible_before,
		"herbe : rien de recréé, touffes gardées affichées (%d sur %d)" % [g._visible_count, visible_before])
	g.update(cam_s)
	_check(g._slot_chunk == before, "herbe : même fenêtre de tronçons après la mise à jour")
	g.queue_free()


## E8-03 : poids des biomes lus après le début du changement oubliés, les autres gardés.
func _test_atmosphere_cache() -> void:
	var m = AtmosphereModel.new(null, func(s: float) -> Vector2: return Vector2(s, 0.0))
	m._cache = {0: {}, 50: {}, 99: {}, 100: {}, 400: {}}
	m.set_positions(func(s: float) -> Vector2: return Vector2(-s, 0.0), 1000.0)
	_check(m._cache.keys() == [0, 50, 99], "atmosphère : cache gardé avant 1 000 m, oublié après (%s)" % str(m._cache.keys()))
	_check(m.pos_at.call(10.0) == Vector2(-10.0, 0.0), "atmosphère : positions lues sur la nouvelle route")
