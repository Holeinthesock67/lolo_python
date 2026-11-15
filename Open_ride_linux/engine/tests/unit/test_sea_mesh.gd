extends SceneTree

## Tests unitaires sans écran de la mer animée (lot U9) : maillage de la mer (île sans triangle), couleur
## d'après les biomes, anneau d'horizon, écume côté mer, plages drapées, distance au rivage, lecture de la
## couche `coast` par osm_layers.gd, branchement dans osm_streamer.gd (nœuds de mer, d'écume, de plage et
## d'horizon) et parcours sans mer sans aucun nœud de mer.
## Lancement : godot --headless --path engine --script res://tests/unit/test_sea_mesh.gd

const SeaMesh := preload("res://scripts/sea_mesh.gd")
const OsmLayers := preload("res://scripts/osm_layers.gd")
const OsmStreamer := preload("res://scripts/osm_streamer.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")

const TMP := "user://test_sea_mesh"

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _tri_centers(res: Dictionary) -> Array:
	var verts: PackedVector3Array = res["vertices"]
	var idx: PackedInt32Array = res["indices"]
	var out := []
	for t in range(0, idx.size(), 3):
		out.append((verts[idx[t]] + verts[idx[t + 1]] + verts[idx[t + 2]]) / 3.0)
	return out


func _all_up(res: Dictionary) -> bool:
	var verts: PackedVector3Array = res["vertices"]
	var idx: PackedInt32Array = res["indices"]
	for t in range(0, idx.size(), 3):
		var a := verts[idx[t]]
		var b := verts[idx[t + 1]]
		var c := verts[idx[t + 2]]
		if (b - a).cross(c - a).length_squared() < 1e-10:
			continue
		if Plane(a, b, c).normal.y < 0.5:
			return false
	return true


func _area_xz(res: Dictionary) -> float:
	var verts: PackedVector3Array = res["vertices"]
	var idx: PackedInt32Array = res["indices"]
	var area := 0.0
	for t in range(0, idx.size(), 3):
		var a := Vector2(verts[idx[t]].x, verts[idx[t]].z)
		var b := Vector2(verts[idx[t + 1]].x, verts[idx[t + 1]].z)
		var c := Vector2(verts[idx[t + 2]].x, verts[idx[t + 2]].z)
		area += 0.5 * absf((b - a).cross(c - a))
	return area


# Critère 2 : polygone de mer avec une île, aucun triangle sur l'île
func _test_sea_with_island() -> void:
	var sea := {"id": "sea_0", "kind": "sea", "level_y": 0.0,
		"outer": [[0.0, 0.0], [400.0, 0.0], [400.0, 400.0], [0.0, 400.0]],
		"holes": [[[150.0, 150.0], [150.0, 250.0], [250.0, 250.0], [250.0, 150.0]]]}
	var res := SeaMesh.build_sea([sea], func(_x: float, _z: float) -> Color: return Color(0.1, 0.5, 0.6))
	_check(int(res["built"]) == 1 and int(res["skipped"]) == 0, "mer avec île construite")
	var on_island := 0
	for c in _tri_centers(res):
		if c.x > 150.0 and c.x < 250.0 and c.z > 150.0 and c.z < 250.0:
			on_island += 1
	_check(on_island == 0, "aucun triangle sur l'île (%d)" % on_island)
	_check(absf(_area_xz(res) - (400.0 * 400.0 - 100.0 * 100.0)) < 1.0, "aire de la mer = carré moins l'île (%.1f m²)" % _area_xz(res))
	var y_ok := true
	for v in (res["vertices"] as PackedVector3Array):
		y_ok = y_ok and is_equal_approx(v.y, SeaMesh.SURFACE_OFFSET_M)
	_check(y_ok, "mer posée %.2f m au-dessus du niveau 0 (pas de scintillement avec le MNT)" % SeaMesh.SURFACE_OFFSET_M)
	_check(_all_up(res), "triangles de la mer vus du dessus")
	var cols: PackedColorArray = res["colors"]
	_check(cols.size() == (res["vertices"] as PackedVector3Array).size() and cols[0].is_equal_approx(Color(0.1, 0.5, 0.6)),
		"couleur de sommet de la mer donnée par color_at")


func _test_split_and_color() -> void:
	var areas := [{"kind": "lake"}, {"kind": "sea"}, {"kind": "pond"}]
	var split := SeaMesh.split_areas(areas)
	_check((split["sea"] as Array).size() == 1 and (split["inland"] as Array).size() == 2, "aires sea séparées des plans d'eau")
	var theme := {"biomes": {"coast": {"water": {"color": "#2a8a9a"}}}}
	_check(SeaMesh.sea_color(theme, null, 0.0, 0.0).is_equal_approx(Color("#2a8a9a")), "sans biome : couleur `water` du biome coast")
	_check(SeaMesh.sea_color({}, null, 0.0, 0.0).is_equal_approx(SeaMesh.DEFAULT_SEA_COLOR), "sans thème : couleur par défaut")
	_check(SeaMesh.sand_color({"biomes": {"coast": {"ground": {"layers": [{"role": "flat", "color": "#c2ae86"}]}}}}) == Color("#c2ae86"),
		"sable des plages : sol plat du biome coast")


func _test_horizon() -> void:
	var h := SeaMesh.build_horizon(-1.0, Color.BLUE)
	var verts: PackedVector3Array = h["vertices"]
	var min_r := INF
	var max_r := 0.0
	var y_ok := true
	for v in verts:
		var r := Vector2(v.x, v.z).length()
		min_r = minf(min_r, r)
		max_r = maxf(max_r, r)
		y_ok = y_ok and is_equal_approx(v.y, -1.0)
	_check(y_ok, "horizon à la hauteur demandée")
	_check(absf(min_r - SeaMesh.HORIZON_HOLE_M) < 1.0 and absf(max_r - SeaMesh.HORIZON_RADIUS_M) < 1.0,
		"anneau d'horizon de %.0f à %.0f m" % [min_r, max_r])
	_check(_all_up(h), "triangles de l'horizon vus du dessus")
	var inside := 0
	for c in _tri_centers(h):
		if Vector2(c.x, c.z).length() < SeaMesh.HORIZON_HOLE_M * 0.9:
			inside += 1
	_check(inside == 0, "trou central de l'horizon laissé aux aires sea")


# Écume : côté mer (à droite du sens des points), largeur selon le rivage
func _test_foam() -> void:
	# Côte parcourue du nord au sud (z croissant) : la mer est à l'ouest (x < 0), comme demo_biomes.py.
	var lines := [{"id": "c0", "shore": "sand", "points": [[0.0, 0.0], [0.0, 100.0], [0.0, 200.0]]},
		{"id": "c1", "shore": "cliff", "points": [[500.0, 0.0], [500.0, 200.0]]}]
	var f := SeaMesh.build_foam(lines, 0.0)
	_check(int(f["built"]) == 2, "deux rubans d'écume")
	var min_x0 := INF
	var max_x0 := -INF
	var min_x1 := INF
	for v in (f["vertices"] as PackedVector3Array):
		if v.x < 250.0:
			min_x0 = minf(min_x0, v.x)
			max_x0 = maxf(max_x0, v.x)
		else:
			min_x1 = minf(min_x1, v.x)
	_check(max_x0 <= 1e-4 and absf(min_x0 + SeaMesh.FOAM_WIDTH_M["sand"]) < 1e-3,
		"écume du sable côté mer, large de %.0f m (x de %.2f à %.2f)" % [SeaMesh.FOAM_WIDTH_M["sand"], min_x0, max_x0])
	_check(absf(min_x1 - (500.0 - SeaMesh.FOAM_WIDTH_M["cliff"])) < 1e-3 and SeaMesh.FOAM_WIDTH_M["cliff"] > SeaMesh.FOAM_WIDTH_M["sand"],
		"écume plus large au pied des falaises")
	var y_ok := true
	for v in (f["vertices"] as PackedVector3Array):
		y_ok = y_ok and v.y > SeaMesh.SURFACE_OFFSET_M
	_check(y_ok, "écume au-dessus de la mer")
	_check(_all_up(f), "triangles de l'écume vus du dessus")
	var uv: PackedVector2Array = f["uvs"]
	_check(uv[0] == Vector2(0.0, 0.0) and uv[1] == Vector2(0.0, 1.0) and is_equal_approx(uv[5].x, 200.0),
		"UV de l'écume : distance le long de la côte, 0 au rivage et 1 au large")
	var col: PackedColorArray = f["colors"]
	_check(is_equal_approx(col[0].r, 2.0 / 6.0), "part toujours couverte de la bande du sable : 2 m sur 6")


# Plages drapées sur le terrain, découpées à la maille de 10 m
func _test_beaches() -> void:
	var slope := func(x: float, z: float) -> float: return 0.05 * x + 0.02 * z
	var beach := {"id": "b0", "kind": "shingle", "outer": [[0.0, 0.0], [35.0, 0.0], [35.0, 25.0], [0.0, 25.0]], "holes": []}
	var res := SeaMesh.build_beaches([beach], slope, Color("#c2ae86"))
	_check(int(res["built"]) == 1, "plage construite")
	var err := 0.0
	for v in (res["vertices"] as PackedVector3Array):
		err = maxf(err, absf(v.y - (float(slope.call(v.x, v.z)) + SeaMesh.BEACH_ABOVE_M)))
	_check(err < 1e-3, "plage drapée sur le terrain, %.2f m au-dessus (écart %.4f m)" % [SeaMesh.BEACH_ABOVE_M, err])
	_check(absf(_area_xz(res) - 35.0 * 25.0) < 0.5, "aire de la plage gardée (%.1f m²)" % _area_xz(res))
	var max_span := 0.0
	var verts: PackedVector3Array = res["vertices"]
	var idx: PackedInt32Array = res["indices"]
	for t in range(0, idx.size(), 3):
		var lo := Vector2(INF, INF)
		var hi := Vector2(-INF, -INF)
		for k in 3:
			var q := Vector2(verts[idx[t + k]].x, verts[idx[t + k]].z)
			lo = Vector2(minf(lo.x, q.x), minf(lo.y, q.y))
			hi = Vector2(maxf(hi.x, q.x), maxf(hi.y, q.y))
		max_span = maxf(max_span, maxf(hi.x - lo.x, hi.y - lo.y))
	_check(max_span <= SeaMesh.BEACH_CELL_M + 1e-3, "triangles de plage dans une case de 10 m (%.2f m)" % max_span)
	_check((res["colors"] as PackedColorArray)[0].is_equal_approx(SeaMesh.BEACH_COLORS["shingle"]), "galets gris")
	_check(_all_up(res), "triangles de la plage vus du dessus")


func _test_shore_distance() -> void:
	var pls := SeaMesh.shore_polylines([{"id": "c", "shore": "rock", "points": [[0.0, 0.0], [0.0, 100.0]]}])
	_check(absf(SeaMesh.shore_distance(pls, -30.0, 50.0) - 30.0) < 1e-4, "distance au rivage : 30 m")
	_check(SeaMesh.shore_distance([], 0.0, 0.0) == INF, "sans rivage : INF")


func _write_json(path: String, data: Variant) -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(path.get_base_dir()))
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(JSON.stringify(data))
	f.close()


func _route() -> Variant:
	var d := {"version": "1.0", "ds_m": 10.0, "n": 201, "length_m": 2000.0, "type": "open",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(201):
		d["lat"].append(45.0)
		d["lon"].append(2.0)
		d["alt_m"].append(5.0)
		d["x"].append(0.0)
		d["z"].append(i * 10.0)
		d["grade_pct"].append(0.0)
		d["heading_deg"].append(180.0)
	var route = RouteDataScript.new()
	route.load_route_dict(d)
	return route


func _make_world(dir: String, sea: bool) -> void:
	var layers := {"terrain": {"present": false}, "water": {"present": true}}
	if sea:
		layers["coast"] = {"present": true, "version": "1.0", "lines_count": 1, "beaches_count": 1}
	_write_json(dir.path_join("manifest.json"), {"version": "1.0", "format_version": "1.6", "layers": layers})
	for k in 2:
		var areas := [{"id": "lake_%d" % k, "kind": "lake", "level_y": 4.0,
			"outer": [[40.0, k * 1000.0 + 100.0], [80.0, k * 1000.0 + 100.0], [80.0, k * 1000.0 + 200.0]], "holes": []}]
		if sea:
			areas.append({"id": "sea_%d" % k, "kind": "sea", "level_y": 0.0,
				"outer": [[-70.0, k * 1000.0], [-70.0, (k + 1) * 1000.0], [-370.0, (k + 1) * 1000.0], [-370.0, k * 1000.0]],
				"holes": []})
			_write_json(dir.path_join("coast/chunk_%d.json" % k), {"version": "1.0",
				"lines": [{"id": "c%d" % k, "shore": "sand", "points": [[-70.0, k * 1000.0], [-70.0, (k + 1) * 1000.0]]}],
				"beaches": [{"id": "b%d" % k, "kind": "sand", "holes": [],
					"outer": [[-70.0, k * 1000.0 + 100.0], [-40.0, k * 1000.0 + 100.0], [-40.0, k * 1000.0 + 300.0], [-70.0, k * 1000.0 + 300.0]]}]})
		_write_json(dir.path_join("water/chunk_%d.json" % k), {"version": "1.0", "lines": [], "areas": areas})


func _node_kinds(streamer) -> Dictionary:
	var out := {}
	for c in streamer.get_children():
		var n := str(c.name)
		for kind in ["osm_sea_foam", "osm_sea_", "osm_beach", "osm_water_areas", "sea_horizon"]:
			if n.begins_with(kind) and not (kind == "osm_sea_" and n.begins_with("osm_sea_foam")):
				out[kind] = int(out.get(kind, 0)) + 1
	return out


# Lecture de la couche coast, branchement dans osm_streamer.gd ; critère 4 : parcours sans mer, aucun nœud
func _test_streamer() -> void:
	var with_sea := TMP.path_join("mer.world")
	var no_sea := TMP.path_join("lac.world")
	_make_world(with_sea, true)
	_make_world(no_sea, false)
	var c := OsmLayers.load_chunk(with_sea, "coast", 0)
	_check(c["ok"] and (c["lines"] as Array).size() == 1 and (c["beaches"] as Array).size() == 1 and int(c["ignored"]) == 0,
		"couche coast lue : une ligne, une plage")
	_write_json(TMP.path_join("bad/coast/chunk_0.json"), {"version": "1.0",
		"lines": [{"id": "x", "shore": "lave", "points": [[0, 0], [1, 1]]}, {"id": "y", "shore": "rock", "points": [[0, 0]]}],
		"beaches": [{"id": "z", "kind": "boue", "outer": [[0, 0], [1, 0], [1, 1]], "holes": []}]})
	var bad := OsmLayers.load_chunk(TMP.path_join("bad"), "coast", 0)
	_check(bad["ok"] and (bad["items"] as Array).is_empty() and int(bad["ignored"]) == 3, "rivage, ligne ou plage invalides ignorés")
	_check(OsmLayers.layers_present({"layers": {"coast": {"present": true}}}) == ["coast"], "couche coast reconnue au manifeste")

	var route = _route()
	var streamer = OsmStreamer.new()
	root.add_child(streamer)
	streamer.set_world(route, with_sea)
	streamer.update_window(0.0, 2000.0)
	streamer.flush()
	var kinds := _node_kinds(streamer)
	_check(int(kinds.get("osm_sea_", 0)) == 2 and int(kinds.get("osm_sea_foam", 0)) == 2 and int(kinds.get("osm_beach", 0)) == 2
		and int(kinds.get("osm_water_areas", 0)) == 2, "mer, écume et plage dans chaque tronçon, lac à part (%s)" % str(kinds))
	_check(streamer.sea_horizon() != null and int(kinds.get("sea_horizon", 0)) == 1, "un anneau d'horizon pour tout le parcours")
	var mats_ok := true
	for ch in streamer.get_children():
		var n := str(ch.name)
		if n.begins_with("osm_water"):
			mats_ok = mats_ok and ch.material_override == streamer.water_material()
		elif n.begins_with("osm_sea") or n.begins_with("osm_beach") or n == "sea_horizon":
			mats_ok = mats_ok and ch.material_override is ShaderMaterial and ch.material_override != streamer.water_material()
	_check(mats_ok, "matériaux : eau pour le lac, shaders de mer, d'écume et de plage pour la côte")
	streamer.set_water_shimmer(true)
	var shimmer_ok := true
	for ch in streamer.get_children():
		if str(ch.name).begins_with("osm_sea_") and not str(ch.name).begins_with("osm_sea_foam"):
			shimmer_ok = shimmer_ok and ch.material_override != streamer.water_material()
	_check(shimmer_ok, "reflets de l'eau (P12) sans effet sur la mer")
	_check(absf(streamer.shore_distance(0.0, 500.0) - 70.0) < 1e-3, "distance au rivage depuis la route : 70 m")
	streamer.clear()
	_check(streamer.sea_horizon() == null and streamer.shore_distance(0.0, 500.0) == INF, "tout retiré au changement de parcours")

	streamer.set_world(route, no_sea)
	streamer.update_window(0.0, 2000.0)
	streamer.flush()
	kinds = _node_kinds(streamer)
	_check(not kinds.has("osm_sea_") and not kinds.has("osm_sea_foam") and not kinds.has("osm_beach")
		and not kinds.has("sea_horizon") and int(kinds.get("osm_water_areas", 0)) == 2,
		"parcours sans mer : aucun nœud de mer, d'écume, de plage ni d'horizon (%s)" % str(kinds))
	streamer.clear()
	streamer.free()


func _init() -> void:
	_test_sea_with_island()
	_test_split_and_color()
	_test_horizon()
	_test_foam()
	_test_beaches()
	_test_shore_distance()
	_test_streamer()
	print("test_sea_mesh : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
