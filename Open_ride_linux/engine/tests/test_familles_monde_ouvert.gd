extends SceneTree

## Même décor en monde ouvert que sur les circuits précalculés (demande du 13 novembre 2026 : « retrouver la même
## qualité globale que sur les circuits précalculés ») : sur chaque parcours donné, le décor du bord de route est
## préparé par la fonction de la séance (living_decor.gd `_prepare_job`) et chaque famille d'objets doit être là
## dès que ce qui la déclenche existe, avec la même règle pour un circuit et pour un monde ouvert :
##
##   $GODOT --headless --path engine --script res://tests/test_familles_monde_ouvert.gd -- DOSSIER.world [...]
##
## - bornes kilométriques : une par km entier du parcours ;
## - montées : panneaux de sommet, panneaux d'approche (montée de plus d'1 km) et spectateurs ;
## - couches du manifeste lues par le décor : bâtiments, plans d'eau et points d'intérêt présents dans le monde
##   le long de la route sont bien lus (en monde ouvert : carrés `tile_<ix>_<iz>.json`, constat du 20 novembre
##   2026 : ils ne l'étaient pas, ni passants de village ni noms de sommets) ;
## - passants : promeneurs sur tout parcours à l'air libre, passants de village dès qu'un bâtiment est lu.
## Le décompte par famille est affiché pour comparer les parcours entre eux. Code de sortie 1 si un contrôle échoue.

const RouteDataScript := preload("res://scripts/route_data.gd")
const OsmLayers := preload("res://scripts/osm_layers.gd")
const LivingDecor := preload("res://scripts/living_decor.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")

## Bâtiment « au bord de la route » : centre à moins de BUILDING_BY_ROAD_M de l'axe. Les passants de village
## (passersby_model.gd) naissent dans une case de 100 m dont le milieu est à moins de VILLAGE_M (60 m) d'un
## bâtiment : à 30 m de l'axe, un bâtiment est toujours à moins de 60 m du milieu d'une case.
const BUILDING_BY_ROAD_M := 30.0

var _failures := 0
var _checked := 0


func _init() -> void:
	var dirs := OS.get_cmdline_user_args()
	if dirs.is_empty():
		printerr("Usage : -- DOSSIER.world [DOSSIER.world ...]")
		quit(2)
		return
	for wd in dirs:
		_run(wd)
	print("test_familles_monde_ouvert : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


static func _manifest(wd: String) -> Dictionary:
	var f := FileAccess.open(wd.path_join("manifest.json"), FileAccess.READ)
	if f == null:
		return {}
	var doc = JSON.parse_string(f.get_as_text())
	return doc if typeof(doc) == TYPE_DICTIONARY else {}


## Éléments d'une couche à moins de `margin` de la route, lus fichier par fichier sans passer par load_chunk
## (contrôle indépendant de ce que lit le décor) : nombre d'éléments, tous fichiers du dossier de la couche.
static func _layer_items_near(wd: String, layer: String, route, margin: float) -> int:
	var dir := DirAccess.open(wd.path_join(layer))
	if dir == null:
		return 0
	var box := Rect2(route.x[0], route.z[0], 0.0, 0.0)
	for i in range(route.n):
		box = box.expand(Vector2(route.x[i], route.z[i]))
	box = box.grow(margin)
	var n := 0
	for name in dir.get_files():
		if not name.ends_with(".json"):
			continue
		var off := Vector2.ZERO
		if name.begins_with("tile_"):
			var parts := name.trim_prefix("tile_").trim_suffix(".json").split("_")
			off = Vector2(float(parts[0]), float(parts[1])) * OsmLayers.TILE_M
			if not box.intersects(Rect2(off, Vector2.ONE * OsmLayers.TILE_M)):
				continue
		var res := OsmLayers._load_file(wd.path_join(layer).path_join(name), layer, off)
		if res.get("ok", false):
			n += (res.get("items", []) as Array).size() + (res.get("lines", []) as Array).size() \
				+ (res.get("areas", []) as Array).size()
	return n


## Bâtiments au bord de la route, lus fichier par fichier (sans load_chunk) : centre de l'enveloppe à moins
## de BUILDING_BY_ROAD_M d'un point de l'axe.
static func _buildings_by_road(wd: String, route) -> int:
	var dir := DirAccess.open(wd.path_join("buildings"))
	if dir == null:
		return 0
	var axis := PackedVector2Array()
	for i in range(route.n):
		axis.append(Vector2(route.x[i], route.z[i]))
	var n := 0
	for name in dir.get_files():
		if not name.ends_with(".json"):
			continue
		var off := Vector2.ZERO
		if name.begins_with("tile_"):
			var parts := name.trim_prefix("tile_").trim_suffix(".json").split("_")
			off = Vector2(float(parts[0]), float(parts[1])) * OsmLayers.TILE_M
		var res := OsmLayers._load_file(wd.path_join("buildings").path_join(name), "buildings", off)
		for b in res.get("items", []):
			var outer = b.get("outer", [])
			if typeof(outer) != TYPE_ARRAY or (outer as Array).is_empty():
				continue
			var c := Vector2.ZERO
			for p in outer:
				c += Vector2(float(p[0]), float(p[1]))
			c /= float((outer as Array).size())
			for q in axis:
				if q.distance_to(c) < BUILDING_BY_ROAD_M:
					n += 1
					break
	return n


func _run(wd: String) -> void:
	var name := wd.get_file()
	var route = RouteDataScript.new()
	if not route.load_world_dir(wd):
		_check(false, "%s : parcours lisible" % name)
		return
	var manifest := _manifest(wd)
	var layers := OsmLayers.layers_present(manifest)
	var job := {"gen": 0, "route": route, "world_dir": wd, "layers": layers, "road_width_m": RoadBuilder.ROAD_WIDTH_M,
		"crowd_all_climbs": true, "biome_at": Callable(), "underwater": false, "result": {}}
	LivingDecor._prepare_job(job)
	var res: Dictionary = job["result"]
	var kinds := {}
	for it in res["items"]:
		kinds[it["kind"]] = int(kinds.get(it["kind"], 0)) + 1
	var climbs: Array = res["climbs"]
	var long_climbs := 0
	for c in climbs:
		long_climbs += 1 if float(c["summit_s"]) - float(c["start_s"]) > 1000.0 else 0
	var people: Array = res["passersby"].people
	var village := 0
	for p in people:
		village += 1 if p.get("village", false) else 0
	var spectators: int = (res["crowd"].spectators as Array).size()
	var pois: int = (res["pois"] as Array).size()
	var kind := "monde ouvert" if route.live else "circuit"
	print("%s (%s) : %.1f km, montées %d (dont %d de plus d'1 km), couches %s ; bornes %d, sommets %d, approches %d, spectateurs %d, passants %d (village %d), POI lus %d" % [
		name, kind, route.length_m / 1000.0, climbs.size(), long_climbs, ",".join(layers), int(kinds.get("km", 0)),
		int(kinds.get("summit", 0)), int(kinds.get("approach", 0)), spectators, people.size(), village, pois])
	var km_expected := int(floor((route.length_m - 1.0) / 1000.0))
	_check(int(kinds.get("km", 0)) >= km_expected,
		"%s : bornes kilométriques (%d pour %d km entiers)" % [name, int(kinds.get("km", 0)), km_expected])
	if not climbs.is_empty():
		_check(int(kinds.get("summit", 0)) > 0 and spectators > 0,
			"%s : %d montées → panneaux de sommet (%d) et spectateurs (%d)" % [name, climbs.size(), int(kinds.get("summit", 0)), spectators])
	if long_climbs > 0:
		_check(int(kinds.get("approach", 0)) > 0,
			"%s : %d montées de plus d'1 km → panneaux d'approche (%d)" % [name, long_climbs, int(kinds.get("approach", 0))])
	_check(people.size() > 0, "%s : parcours à l'air libre → promeneurs (%d)" % [name, people.size()])
	# Couches du monde le long de la route : le décor doit les lire, circuit comme monde ouvert.
	var buildings_near := _buildings_by_road(wd, route) if layers.has("buildings") else 0
	var poi_near := _layer_items_near(wd, "poi", route, OsmLayers.LIVE_MARGIN_M) if layers.has("poi") else 0
	if buildings_near > 0:
		_check(village > 0, "%s : %d bâtiments à moins de %d m de la route → passants de village (%d)" % [
			name, buildings_near, int(BUILDING_BY_ROAD_M), village])
	if poi_near > 0:
		_check(pois > 0, "%s : %d points d'intérêt près de la route → lus par le décor (%d)" % [name, poi_near, pois])
