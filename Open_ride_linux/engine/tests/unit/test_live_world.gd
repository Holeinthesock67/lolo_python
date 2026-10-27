extends SceneTree

## Monde vivant côté engine (lot W10) : révisions, carrefours et amorces, carrés de couches relatifs au
## coin de tuile, recentrage de l'origine, ruban des amorces. Sans écran.
## Lancement : godot --headless --path engine --script res://tests/unit/test_live_world.gd

const LiveWorld := preload("res://scripts/live_world.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const OsmLayers := preload("res://scripts/osm_layers.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")

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


## Partie k d'une route droite vers l'est (x = s, z = 0), 10 m de pas, `length` mètres connus.
func _part(k: int, length: float, alt0: float = 600.0) -> Dictionary:
	var lo := 1000.0 * k
	var hi := minf(1000.0 * (k + 1), length)
	var part := {"version": "1.0", "ds_m": 10.0, "length_m": hi - lo, "type": "open", "s0_m": lo,
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	var s := lo
	while s <= hi + 1e-6:
		part["lat"].append(45.0)
		part["lon"].append(6.0 + s * 1.27e-5)
		part["alt_m"].append(alt0 + s * 0.01)
		part["x"].append(s)
		part["z"].append(0.0)
		part["grade_pct"].append(1.0)
		part["heading_deg"].append(90.0)
		s += 10.0
	part["n"] = part["x"].size()
	return part


func _junction(id: String, s_m: float, chosen: int) -> Dictionary:
	var branches := []
	for i in range(3):
		branches.append({"index": i, "heading_deg": 90.0 + 30.0 * (i - 1), "angle_deg": 30.0 * (i - 1), "road_class": "t",
			"grade_pct_500m": 0.0, "dead_end": false,
			"preview": {"x": [s_m, s_m + 10.0], "y": [606.0, 606.0], "z": [0.0, 10.0 * (i - 1)]}})
	return {"id": id, "s_m": s_m, "x": s_m, "z": 0.0, "lock_s_m": s_m - 30.0, "default": 1, "chosen": chosen,
		"locked": false, "branches": branches}


func _publish(dir: String, length: float, rev: int, changed_from: int, junctions: Array, first_part: int = 0) -> void:
	var parts := int(ceil(length / 1000.0))
	for k in range(first_part, parts):
		_write_json(dir.path_join("route").path_join("part_%d.json" % k), _part(k, length))
	_write_json(dir.path_join("junctions.json"), {"version": "1.0", "revision": rev, "junctions": junctions})
	_write_json(dir.path_join("live.json"), {"version": "1.0", "revision": rev,
		"route": {"parts": parts, "length_m": length, "changed_from_part": changed_from},
		"tiles": {"near": [], "far": []}, "layer_tiles": [], "status": "ok"})


func _init() -> void:
	var base := "user://w10_live_%d" % OS.get_process_id()
	var dir := base.path_join("ow-test.world")
	_write_json(dir.path_join("manifest.json"), {"format": "openride-world", "format_version": "1.4", "live": true,
		"layers": {}, "grid": {"near_m": 1000, "far_m": 5000, "e0": 0, "n0": 0}})
	_publish(dir, 2000.0, 1, 0, [_junction("jA", 500.0, 1), _junction("jB", 1800.0, 0)])

	# --- ouverture et révisions ---
	var lw = LiveWorld.new()
	_check(lw.open(dir), "séance ouverte")
	_check(lw.revision == 1 and absf(lw.route.length_m - 2000.0) < 1e-9, "révision 1, 2 000 m")
	var route_1 = lw.route
	var part_0 = lw.route.parts[0]
	_publish(dir, 3500.0, 2, 1, [_junction("jA", 500.0, 1), _junction("jB", 1800.0, 0)], 1)
	lw.on_open_world({"rev": 2, "next": null, "data": "cached"})
	_check(lw.is_loading(), "lecture lancée en tâche de fond")
	var done := lw.wait_poll()
	_check(done.get("revision", 0) == 2 and int(done.get("from_part", -1)) == 1, "révision 2 appliquée depuis la partie 1")
	_check(absf(lw.route.length_m - 3500.0) < 1e-9 and absf(route_1.length_m - 2000.0) < 1e-9,
		"nouvelle route de 3 500 m, l'ancienne intacte")
	_check(is_same(lw.route.parts[0], part_0), "partie 0 gardée (même objet)")
	_check(absf(lw.route.sample(2750.0)["x"] - 2750.0) < 1e-6, "route prolongée lisible")

	# Même révision annoncée deux fois, ou plus ancienne : rien à faire.
	lw.on_open_world({"rev": 2})
	lw.on_open_world({"rev": 1})
	_check(not lw.is_loading(), "révision déjà connue : pas de relecture")

	# Révisions manquées : tout est relu.
	_publish(dir, 3600.0, 3, 3, [_junction("jA", 500.0, 1)], 3)
	_publish(dir, 4200.0, 5, 3, [_junction("jA", 500.0, 2)], 3)
	lw.on_open_world({"rev": 5})
	done = lw.wait_poll()
	_check(done.get("revision", 0) == 5 and int(done["from_part"]) == 0, "révisions manquées : relecture depuis la partie 0")
	_check(absf(lw.route.length_m - 4200.0) < 1e-9, "route de 4 200 m")

	# Annonce en avance sur le disque : attend.
	lw.on_open_world({"rev": 7})
	_check(not lw.is_loading() and lw.revision == 5, "révision pas encore sur le disque : attente")

	# Partie corrompue : l'ancienne route reste, pas de nouvelle tentative pour cette révision.
	_write_json(dir.path_join("route").path_join("part_4.json"), {"n": 1})
	_write_json(dir.path_join("live.json"), {"version": "1.0", "revision": 7,
		"route": {"parts": 5, "length_m": 4600.0, "changed_from_part": 4}})
	lw.on_open_world({"rev": 7})
	done = lw.wait_poll()
	_check(done.has("error") and lw.revision == 5 and absf(lw.route.length_m - 4200.0) < 1e-9, "partie illisible : route gardée")
	lw.on_open_world({"rev": 7})
	_check(not lw.is_loading(), "pas de nouvelle tentative pour la révision en échec")

	# --- amorces ---
	var pv: Array = lw.previews(0.0)     # carrefours : jA (chosen 2) à 500 m ; jB retiré par la révision 5
	_check(pv.size() == 2, "jA : deux amorces (branche suivie exclue), %d" % pv.size())
	var branches := []
	for p in pv:
		branches.append(p["branch"])
	_check(not branches.has(2) and branches.has(0) and branches.has(1), "branches 0 et 1, pas la 2 choisie")
	_check(lw.previews(600.0).is_empty(), "carrefour dépassé : plus d'amorce")
	lw.junctions = [_junction("jFar", 3000.0, 0)]
	_check(lw.previews(0.0).is_empty() and lw.previews(1600.0).size() == 2, "amorces seulement à moins de 1 500 m")

	# --- recentrage ---
	_check(LiveWorld.recenter_target(9000.0, 0.0, Vector2.ZERO, 10000.0) == Vector2.ZERO, "à 9 km : pas de recentrage")
	var t := LiveWorld.recenter_target(10400.0, -2300.0, Vector2.ZERO, 10000.0)
	_check(t == Vector2(10000.0, -2000.0), "à 10,4 km : origine au kilomètre le plus proche %s" % str(t))
	var cam_x := 60000.123456
	var cam_z := -3000.987654
	var err_without := absf(float(Vector2(cam_x, cam_z).x) - cam_x)
	var lw2 = LiveWorld.new()
	lw2.recenter_m = 10000.0
	var shift := lw2.track_camera(cam_x, cam_z)
	_check(fmod(shift.x, 1000.0) == 0.0 and fmod(shift.y, 1000.0) == 0.0 and shift != Vector2.ZERO, "déplacement multiple de 1 000 m")
	var r := LiveWorld.to_render(cam_x, cam_z, lw2.render_offset)
	var back_x := float(r.x) + float(lw2.render_offset.x)
	_check(absf(r.x - (cam_x - lw2.render_offset.x)) < 1e-3 and absf(back_x - cam_x) < 1e-3, "retour au repère du monde à moins de 1 mm")
	_check(absf(r.x) < 1000.0 and err_without > 0.0, "valeur de rendu petite (%f), erreur 32 bits sans recentrage %f" % [r.x, err_without])
	var pos32 := Vector3(60000.123456, 0.0, 0.0).x      # sans recentrage : 4 mm d'écart en 32 bits
	_check(absf(pos32 - 60000.123456) > 0.001 and absf(r.x - (cam_x - lw2.render_offset.x)) < 0.001, "erreur 32 bits à 60 km : sans recentrage > 1 mm, avec < 1 mm")
	_check(lw2.track_camera(cam_x + 500.0, cam_z) == Vector2.ZERO, "dans le rayon : plus de déplacement")

	# --- couches par carré, coordonnées relatives au coin de tuile ---
	var layers_dir := base.path_join("layers.world")
	_publish(layers_dir, 3000.0, 1, 0, [])
	_write_json(layers_dir.path_join("manifest.json"), {"format": "openride-world", "format_version": "1.4", "live": true})
	var building := {"id": "w1", "outer": [[12.0, -340.5], [20.5, -340.5], [20.5, -332.0], [12.0, -332.0]], "holes": [],
		"base_y": 600.0, "height_m": 6.0, "roof": "flat", "hint": {"building": "house", "colour": null}}
	var live_route = RouteDataScript.new()
	live_route.load_live_dir(layers_dir)
	# Route droite vers l'est (z = 0). Carré (1, 0) : coin en (1 000, 0). Il est confié au premier tronçon
	# qui le touche, ici le tronçon 0 (sa boîte, élargie de 300 m, va jusqu'à x = 1 300).
	_write_json(layers_dir.path_join("buildings").path_join("tile_1_0.json"), {"version": "1.0", "buildings": [building]})
	var res0 := OsmLayers.load_chunk(layers_dir, "buildings", 0, live_route)
	var res1 := OsmLayers.load_chunk(layers_dir, "buildings", 1, live_route)
	var res2 := OsmLayers.load_chunk(layers_dir, "buildings", 2, live_route)
	_check(res0["ok"] and res0["items"].size() == 1, "carré lu pour le tronçon 0")
	if res0["items"].size() == 1:
		var p0: Array = res0["items"][0]["outer"][0]
		_check(absf(p0[0] - 1012.0) < 1e-9 and absf(p0[1] - (-340.5)) < 1e-9, "position absolue = coin de tuile + relative (%s)" % str(p0))
		_check(absf(float(res0["items"][0]["base_y"]) - 600.0) < 1e-9, "altitude inchangée")
	var total: int = res0["items"].size() + res1["items"].size() + res2["items"].size()
	_check(total == 1, "un carré n'est affiché que par un seul tronçon (%d)" % total)
	var again := OsmLayers.load_chunk(layers_dir, "buildings", 0, live_route)
	_check(again["items"].size() == 1 and again["items"][0]["outer"][0][0] == 1012.0, "relecture : mêmes coordonnées (aucune accumulation)")
	_check(OsmLayers.load_chunk(layers_dir, "water", 1, live_route)["ok"], "couche absente : aucun carré, pas d'erreur")
	var compiled := OsmLayers.load_chunk(layers_dir, "buildings", 0)
	_check(not compiled["ok"], "sans route vivante : lecture de chunk_<k>.json comme avant")

	# --- ruban des amorces ---
	var xs := []
	var ys := []
	var zs := []
	for i in range(51):
		xs.append(1000.0 + i * 10.0)
		ys.append(600.0)
		zs.append(0.0)
	var arrays := RoadBuilder.build_polyline_arrays(xs, ys, zs, 6.0, 100.0)
	var colors: PackedColorArray = arrays[Mesh.ARRAY_COLOR]
	var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	_check(verts.size() == 102 and colors.size() == 102, "51 coupes de deux sommets")
	_check(colors[0].a == 1.0 and colors[80].a == 1.0 and colors[101].a == 0.0, "alpha 1 puis 0 sur les 100 derniers mètres")
	_check(absf(colors[2 * 45].a - 0.5) < 1e-6, "alpha 0,5 à 50 m de la fin")
	_check(absf(verts[0].z - (-3.0)) < 1e-6 and absf(verts[1].z - 3.0) < 1e-6, "largeur 6 m, gauche puis droite")
	_check(RoadBuilder.build_polyline_arrays([1.0], [0.0], [0.0], 6.0, 10.0).is_empty(), "un seul point : rien")

	lw.close()
	_remove_tree(base)
	print("test_live_world : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
