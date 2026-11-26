extends SceneTree

## Tests sans écran du préchauffage des tronçons OSM (lot AC2, fil « à-coups de main » du 21/11) : le triangle de
## chaque sorte a le format de sommets que produit son vrai constructeur (bâtiments, eau, mer, écume, plages,
## ponts), warm_up pose une sorte par matériau devant la caméra avec les ombres des vrais nœuds, puis l'enlève
## après WARM_FRAMES images.
## Lancement : godot --headless --path engine --script res://tests/unit/test_osm_warm.gd

const OsmStreamer := preload("res://scripts/osm_streamer.gd")
const BuildingMesh := preload("res://scripts/building_mesh.gd")
const WaterMesh := preload("res://scripts/water_mesh.gd")
const SeaMesh := preload("res://scripts/sea_mesh.gd")
const BridgeMesh := preload("res://scripts/bridge_mesh.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		print("[ÉCHEC] ", msg)


## Attributs présents (indices de Mesh.ARRAY_*) d'un tableau de surface.
static func _slots(arr: Array) -> Array:
	var out := []
	for i in range(arr.size()):
		if arr[i] != null:
			out.append(i)
	return out


func _real_arrays() -> Dictionary:
	var theme: Dictionary = ThemeLoader.new().load_named("default")["theme"]
	var building := {"id": "b", "outer": [[0.0, 0.0], [10.0, 0.0], [10.0, 8.0], [0.0, 8.0]], "holes": [],
		"base_y": 100.0, "height_m": 6.0, "roof": "flat", "hint": {"building": "yes", "colour": null}}
	var line := {"id": "w", "kind": "stream", "width_m": 3.0,
		"points": [[0.0, 0.0, 500.0], [0.0, -50.0, 500.0], [0.0, -100.0, 500.0]]}
	var lake := {"id": "l", "kind": "lake", "level_y": 10.0,
		"outer": [[0.0, 0.0], [40.0, 0.0], [40.0, 40.0], [0.0, 40.0]], "holes": []}
	var sea := {"id": "s", "kind": "sea", "level_y": 0.0,
		"outer": [[0.0, 0.0], [400.0, 0.0], [400.0, 400.0], [0.0, 400.0]], "holes": []}
	var shore := [{"id": "c0", "shore": "sand", "points": [[0.0, 0.0], [0.0, 100.0], [0.0, 200.0]]}]
	var beach := {"id": "p", "kind": "sand", "outer": [[0.0, 0.0], [35.0, 0.0], [35.0, 25.0], [0.0, 25.0]], "holes": []}
	var pts := []
	for i in range(13):
		pts.append([0.0, -10.0 * i, 100.0])
	var bridge := {"id": "br", "kind": "bridge", "length_m": 120.0, "half_width_m": 3.0, "points": pts,
		"piers": [[0.0, -40.0, 100.0, 68.5]]}
	var flat := func(_x: float, _z: float) -> float: return 0.0
	var blue := func(_x: float, _z: float) -> Color: return Color(0.1, 0.5, 0.6)
	return {
		"buildings": BuildingMesh.build([building], theme, OsmStreamer.SKIRT_M),
		"water_lines": WaterMesh.build_lines([line]),
		"water_areas": WaterMesh.build_areas([lake]),
		"sea": SeaMesh.build_sea([sea], blue),
		"sea_horizon": SeaMesh.build_horizon(-1.0, Color.BLUE),
		"sea_foam": SeaMesh.build_foam(shore, 0.0),
		"beach": SeaMesh.build_beaches([beach], flat, Color("#c2ae86")),
		"bridges": BridgeMesh.build([bridge]),
	}


func _test_formats() -> void:
	var real := _real_arrays()
	for kind in real:
		var arr := OsmStreamer._arrays_from_mesh_dict(real[kind])
		var warm_kind := "sea" if kind == "sea_horizon" else str(kind)
		_check(not arr.is_empty(), "%s : le vrai constructeur produit un maillage" % kind)
		_check(_slots(arr) == _slots(OsmStreamer.warm_arrays(warm_kind)),
			"%s : format du préchauffage = format du constructeur (%s / %s)" % [kind, _slots(arr),
				_slots(OsmStreamer.warm_arrays(warm_kind))])
	_check(OsmStreamer.WARM_FORMATS.size() == 7, "sept sortes de nœuds de tronçon préchauffées")


func _test_warm_up() -> void:
	var osm = OsmStreamer.new()
	root.add_child(osm)
	var cam := Camera3D.new()
	root.add_child(cam)
	_check(osm.warm_up(null) == 0 and not osm.is_warming(), "sans caméra : rien")
	_check(osm.warm_up(cam) == 7 and osm.is_warming(), "une sorte par matériau posée devant la caméra")
	var warm: Node3D = cam.get_node("OsmWarm")
	var ok := warm != null and warm.get_child_count() == 7
	for mi in (warm.get_children() if warm != null else []):
		var kind := str(mi.name).trim_prefix("warm_")
		ok = ok and (mi as MeshInstance3D).material_override == osm._material_for(kind)
		var shadow: bool = (mi as MeshInstance3D).cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		ok = ok and shadow == (kind == "buildings" or kind == "bridges")
	_check(ok, "matériau et ombres des vrais nœuds (bâtiments et ponts avec ombre)")
	for i in OsmStreamer.WARM_FRAMES - 1:
		osm.integrate(0)
	_check(osm.is_warming(), "encore là avant WARM_FRAMES images")
	osm.integrate(0)
	_check(not osm.is_warming(), "retiré après WARM_FRAMES images")
	_check(osm.warm_up(cam) == 7 and osm.warm_up(cam) == 7 and cam.get_children().filter(
		func(n): return not n.is_queued_for_deletion()).size() == 1, "nouveau préchauffage : l'ancien est retiré")
	osm.free()
	cam.free()


## Étapes du plan (banc rJ25J du 25/11) : une sorte par étape, donc par image ; chaque sorte garde ses propres
## WARM_FRAMES images, les autres restent posées tant que les leurs ne sont pas finies.
func _test_warm_steps() -> void:
	var osm = OsmStreamer.new()
	root.add_child(osm)
	var cam := Camera3D.new()
	root.add_child(cam)
	_check(osm.warm_steps(null).is_empty(), "étapes sans caméra : aucune")
	var steps: Array = osm.warm_steps(cam)
	_check(steps.size() == OsmStreamer.WARM_FORMATS.size(), "une étape par sorte (%d)" % steps.size())
	_check(str(steps[0][0]) == "osm buildings", "nom de l'étape : osm <sorte>")
	_check(int((steps[0][1] as Callable).call()) == 1, "une étape pose une seule sorte")
	var warm: Node3D = cam.get_node("OsmWarm")
	_check(warm.get_child_count() == 1 and warm.get_child(0).name == "warm_buildings", "la première : bâtiments seuls")
	var counts_ok := true
	for k in range(1, steps.size()):
		osm.integrate(0)   # une image entre deux étapes
		(steps[k][1] as Callable).call()
		var live := warm.get_children().filter(func(n): return not n.is_queued_for_deletion()).size()
		counts_ok = counts_ok and live == mini(k + 1, OsmStreamer.WARM_FRAMES)
	_check(counts_ok, "au plus WARM_FRAMES sortes en scène, la plus ancienne retirée au bout de ses images")
	var mi := warm.get_node_or_null("warm_bridges") as MeshInstance3D
	_check(mi != null and mi.material_override == osm._material_for("bridges")
		and mi.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_ON, "dernière sorte : matériau et ombre des ponts")
	for i in OsmStreamer.WARM_FRAMES:
		osm.integrate(0)
	_check(not osm.is_warming(), "tout retiré après les images de la dernière sorte")
	_check(osm.warm_up(cam, "inconnue") == 0 and not osm.is_warming(), "sorte inconnue : rien")
	osm.free()
	cam.free()


func _init() -> void:
	_test_formats()
	_test_warm_up()
	_test_warm_steps()
	print("test_osm_warm : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
