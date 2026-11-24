extends SceneTree

## Tests sans écran des objets sur la route du monde ouvert (24/11, balade de Biarritz : herbe, maison et arbres sur
## la route, arbre dans la mer) :
## - bâtiment que l'axe de la route traverse retiré, façade d'une rue étroite gardée (osm_streamer.gd) ;
## - tronçon plus ancien refait quand la route réécrite passe sur un de ses bâtiments ;
## - arbres hors de la mer (îles gardées) et hors des branches non suivies des carrefours (tree_renderer.gd) ;
## - herbe : branche ajoutée à la grille de distance, sans relier la route et la branche (road_clearance.gd) ;
## - arbres d'une tuile du monde vivant : bâtiments et eau lus dans le fichier du carré lui-même (world_streamer.gd) ;
## - branches non suivies de tous les carrefours connus (live_world.gd branch_lines).
## Lancement : godot --headless --path engine --script res://tests/unit/test_monde_ouvert_obstacles.gd

const RouteDataScript := preload("res://scripts/route_data.gd")
const OsmStreamer := preload("res://scripts/osm_streamer.gd")
const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const RoadClearance := preload("res://scripts/road_clearance.gd")
const WorldStreamer := preload("res://scripts/world_streamer.gd")
const LiveWorld := preload("res://scripts/live_world.gd")

var _failures := 0
var _checked := 0


func _init() -> void:
	_test_buildings_on_route()
	_test_rewritten_route_redoes_old_chunk()
	_test_trees_out_of_water()
	_test_trees_off_branches()
	_test_clearance_branch()
	_test_live_tile_items()
	_test_branch_lines()
	print("test_monde_ouvert_obstacles : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Route vivante droite vers le nord (z décroissant) en x = `x0`, `length` m, points tous les 10 m.
func _route(length: float = 600.0, x0: float = 0.0) -> Variant:
	var ds := 10.0
	var n := int(length / ds) + 1
	var data := {"version": "1.0", "type": "open", "ds_m": ds, "n": n, "length_m": ds * (n - 1),
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		data["lat"].append(43.0)
		data["lon"].append(-1.5)
		data["alt_m"].append(20.0)
		data["x"].append(x0)
		data["z"].append(-i * ds)
		data["grade_pct"].append(0.0)
		data["heading_deg"].append(0.0)
	var r = RouteDataScript.new()
	r.load_route_dict(data)
	r.live = true
	return r


static func _box(cx: float, cz: float, w: float, d: float) -> Array:
	return [[cx - w / 2, cz - d / 2], [cx + w / 2, cz - d / 2], [cx + w / 2, cz + d / 2], [cx - w / 2, cz + d / 2]]


func _building(id: String, cx: float, cz: float, w: float = 8.0, d: float = 8.0) -> Dictionary:
	return {"id": id, "outer": _box(cx, cz, w, d), "holes": [], "base_y": 20.0, "height_m": 9.0}


func _test_buildings_on_route() -> void:
	var r = _route()
	var items := [
		_building("sur_la_route", 0.0, -200.0),          # l'axe le traverse
		_building("facade_rue", 6.5, -250.0, 8.0, 10.0),  # mur à 2,5 m de l'axe (rue étroite) : gardé
		_building("au_loin", 40.0, -300.0),
		_building("au_bord", 4.9, -350.0),                # mur à 0,9 m de l'axe : sur la voie du cycliste
	]
	var kept: Array = OsmStreamer.drop_buildings_on_route(items, r)
	var ids := kept.map(func(b): return b["id"])
	_check(not ids.has("sur_la_route"), "bâtiment traversé par l'axe de la route : retiré")
	_check(not ids.has("au_bord"), "bâtiment à 0,9 m de l'axe : retiré")
	_check(ids.has("facade_rue"), "façade d'une rue étroite (2,5 m de l'axe) : gardée")
	_check(ids.has("au_loin"), "bâtiment à 36 m : gardé")


func _test_rewritten_route_redoes_old_chunk() -> void:
	var s = OsmStreamer.new()
	# Tronçon 0 déjà chargé : un bâtiment à x = 60, loin de l'ancienne route (x = 0)
	s._shapes_by_chunk[0] = {"forests": [], "buildings": [OsmStreamer._shape(_box(60.0, -1500.0, 8.0, 8.0))], "waters": []}
	s._chunk_instances[0] = []
	s._shapes_by_chunk[1] = {"forests": [], "buildings": [OsmStreamer._shape(_box(200.0, -1500.0, 8.0, 8.0))], "waters": []}
	s._chunk_instances[1] = []
	var old_r = _route(2000.0, 0.0)
	_check(s.chunks_with_buildings_on(old_r, 1000.0, 2).is_empty(), "route qui ne touche aucun bâtiment : rien à refaire")
	var new_r = _route(2000.0, 60.0)   # route réécrite à partir de 1 000 m, qui passe sur le bâtiment du tronçon 0
	var redo: Dictionary = s.chunks_with_buildings_on(new_r, 1000.0, 2)
	_check(redo.has(0) and not redo.has(1), "route réécrite sur un bâtiment d'un tronçon plus ancien : ce tronçon est refait")
	_check(s.chunks_with_buildings_on(new_r, 1000.0, 0).is_empty(), "seuls les tronçons plus bas que la partie réécrite")
	s.free()


func _test_trees_out_of_water() -> void:
	var sea := {"id": "mer", "kind": "sea", "level_y": 0.0,
		"outer": [[0.0, 0.0], [500.0, 0.0], [500.0, 500.0], [0.0, 500.0]],
		"holes": [[[200.0, 200.0], [260.0, 200.0], [260.0, 260.0], [200.0, 260.0]]]}
	var trees := PackedVector4Array([
		Vector4(100.0, 0.0, 100.0, 1.0),   # dans la mer
		Vector4(230.0, 3.0, 230.0, 1.0),   # sur l'île
		Vector4(600.0, 5.0, 100.0, 1.0),   # à terre
	])
	var out: PackedVector4Array = TreeRenderer.exclude_water(trees, [sea])
	var xs := []
	for t in out:
		xs.append(int(t.x))
	_check(not xs.has(100), "arbre dans la mer : retiré")
	_check(xs.has(230), "arbre sur une île : gardé")
	_check(xs.has(600), "arbre à terre : gardé")
	_check(TreeRenderer.exclude_water(trees, []).size() == 3, "sans eau : rien de retiré")


func _test_trees_off_branches() -> void:
	var branch := PackedVector2Array([Vector2(0.0, 0.0), Vector2(100.0, 0.0), Vector2(100.0, 100.0)])
	var trees := PackedVector4Array([
		Vector4(50.0, 0.0, 1.0, 1.0),    # sur l'amorce
		Vector4(102.0, 0.0, 50.0, 1.0),  # sur le second segment
		Vector4(50.0, 0.0, 12.0, 1.0),   # à 12 m
	])
	var out: PackedVector4Array = TreeRenderer.exclude_lines(trees, [branch], 7.0)
	_check(out.size() == 1 and is_equal_approx(out[0].z, 12.0), "arbres sur une branche non suivie : retirés, à 12 m : gardé")


func _test_clearance_branch() -> void:
	var r = _route(300.0)
	var rc := RoadClearance.new(r)
	_check(rc.is_clear(50.0, -100.0, 4.0), "avant la branche : point à 50 m dégagé")
	rc.add_polyline(PackedVector2Array([Vector2(50.0, -50.0), Vector2(50.0, -150.0)]))
	_check(not rc.is_clear(50.0, -100.0, 4.0), "branche ajoutée : point sur la branche plus dégagé")
	# La fin de la route (0, −300) et le début de la branche (50, −50) ne sont pas reliés
	_check(rc.is_clear(25.0, -175.0, 4.0), "route et branche non reliées par un faux segment")


func _test_live_tile_items() -> void:
	var dir := OS.get_user_data_dir().path_join("test_monde_ouvert_obstacles")
	DirAccess.make_dir_recursive_absolute(dir.path_join("buildings"))
	DirAccess.make_dir_recursive_absolute(dir.path_join("water"))
	# Carré (1, 0) à 700 m de la route (x = 0) : plus loin que la marge de 100 m d'avant
	var b := FileAccess.open(dir.path_join("buildings/tile_1_0.json"), FileAccess.WRITE)
	b.store_string(JSON.stringify({"version": "1.0", "buildings": [
		{"id": "maison", "outer": [[700, 500], [710, 500], [710, 510], [700, 510]], "holes": [], "base_y": 20.0, "height_m": 8.0, "roof": "flat", "hint": {}}]}))
	b.close()
	var w := FileAccess.open(dir.path_join("water/tile_1_0.json"), FileAccess.WRITE)
	w.store_string(JSON.stringify({"version": "1.0", "lines": [], "areas": [
		{"id": "mer", "kind": "sea", "level_y": 0.0, "outer": [[0, 0], [1000, 0], [1000, 300], [0, 300]], "holes": []}]}))
	w.close()
	var ws = WorldStreamer.new()
	ws.world_dir = dir
	ws._manifest = {"layers": {"buildings": {"present": true}, "water": {"present": true}}}
	ws.route = _route(600.0)
	var got: Array = ws._get_buildings(Vector2i(1, 0))
	_check(got.size() == 1 and is_equal_approx(float(got[0]["outer"][0][0]), 1700.0),
		"monde vivant : bâtiments de la tuile lus dans son carré, en coordonnées de la séance")
	var waters: Array = ws._get_water_areas(Vector2i(1, 0))
	_check(waters.size() == 1 and str(waters[0]["kind"]) == "sea", "monde vivant : mer de la tuile lue pour les arbres")
	_check(ws._get_buildings(Vector2i(5, 5)).is_empty(), "carré absent : aucun bâtiment")
	ws.free()


func _test_branch_lines() -> void:
	var lw = LiveWorld.new()
	lw.junctions = [
		{"id": "j1", "s_m": 3000.0, "default": 0, "branches": [
			{"index": 0, "preview": {"x": [0, 0], "y": [0, 0], "z": [0, -10]}},
			{"index": 1, "preview": {"x": [0, 10], "y": [0, 0], "z": [0, 0]}}]},
		{"id": "j2", "s_m": 100.0, "chosen": 1, "branches": [
			{"index": 0, "preview": {"x": [5, 5], "y": [0, 0], "z": [0, 10]}},
			{"index": 1, "preview": {"x": [5, 15], "y": [0, 0], "z": [0, 0]}}]},
	]
	var keys := (lw.branch_lines() as Array).map(func(it): return it["key"])
	keys.sort()
	_check(keys == ["j1:1", "j2:0"], "branches non suivies de tous les carrefours, même au-delà de 1,5 km : %s" % [keys])
