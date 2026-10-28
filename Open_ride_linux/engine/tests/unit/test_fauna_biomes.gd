extends SceneTree

## Tests sans écran de la faune par biome (lot U12, série U) : espèces de chaque biome (fauna_placer.gd
## BIOME_SPECIES et BIOME_GROUPS), distances à la route, eau des oasis, densités mélangées, budgets d'affichage ;
## branchement du modèle de biome dans world_streamer.gd (lot U17, première partie : `--biome=`).
## Lancement : godot --headless --path engine --script res://tests/unit/test_fauna_biomes.gd

const BiomeIds := preload("res://scripts/biome_ids.gd")
const BiomeModel := preload("res://scripts/biome_model.gd")
const BiomeLayer := preload("res://scripts/biome_layer.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const FaunaPlacer := preload("res://scripts/fauna_placer.gd")
const FaunaBehaviour := preload("res://scripts/fauna_behaviour.gd")
const FaunaRenderer := preload("res://scripts/fauna_renderer.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const WorldStreamer := preload("res://scripts/world_streamer.gd")
const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const OsmStreamer := preload("res://scripts/osm_streamer.gd")

const CHUNKS := 6

var _failures := 0
var _checked := 0
var _theme: Dictionary


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Route droite le long de l'axe x, de 0 à 6 000 m (z = 0).
func _route():
	var n := 601
	var cols := {"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		cols["lat"].append(48.9)
		cols["lon"].append(7.1)
		cols["alt_m"].append(250.0)
		cols["x"].append(i * 10.0)
		cols["z"].append(0.0)
		cols["grade_pct"].append(0.0)
		cols["heading_deg"].append(90.0)
	var d := {"version": "1.0", "ds_m": 10.0, "n": n, "length_m": 6000.0, "type": "open"}
	d.merge(cols)
	var r = RouteDataScript.new()
	r.load_route_dict(d)
	return r


func _square(x0: float, z0: float, size: float) -> Array:
	return [[x0, z0], [x0 + size, z0], [x0 + size, z0 + size], [x0, z0 + size]]


func _flat(_x: float, _z: float) -> float:
	return 250.0


## Zones OSM d'un tronçon : un bois, un pré et un champ de chaque côté de la route.
func _areas(k: int) -> Array:
	var x0 := k * 1000.0
	return [
		{"id": "w%d" % k, "kind": "wood", "outer": _square(x0 + 100.0, 30.0, 250.0), "holes": [], "density": 0.8},
		{"id": "m%d" % k, "kind": "meadow", "outer": _square(x0 + 450.0, 15.0, 200.0), "holes": []},
		{"id": "f%d" % k, "kind": "farmland", "outer": _square(x0 + 400.0, -215.0, 200.0), "holes": []},
		{"id": "g%d" % k, "kind": "grassland", "outer": _square(x0 + 700.0, -180.0, 160.0), "holes": []},
	]


func _model(biome: String):
	var m = BiomeModel.new(_theme, null)
	if biome != "":
		m.set_forced(biome)
	return m


## Groupes des CHUNKS premiers tronçons, avec ou sans modèle de biome, et une eau facultative.
func _place(route, model, water: Dictionary = {}) -> Array:
	var out := []
	for k in range(CHUNKS):
		var ctx := {"height_at": Callable(self, "_flat"), "water": water}
		if model != null:
			ctx["biome_model"] = model
		out.append_array(FaunaPlacer.place_chunk(k, _areas(k), [], route, _theme["fauna"], ctx))
	return out


func _species(groups: Array) -> Dictionary:
	var out := {}
	for g in groups:
		var sp := str(g.get("species", ""))
		var n := (g["members"] as Array).size() if g.has("members") else 1
		out[sp] = int(out.get(sp, 0)) + n
	return out


## Positions au sol des bêtes et des oiseaux posés d'un groupe.
func _ground_points(g: Dictionary) -> Array:
	match str(g["type"]):
		"herd", "crows":
			var pts := []
			for m in g["members"]:
				pts.append(m["pos"])
			return pts
		"deer", "hare":
			return [g["pos"]]
	return []


func _init() -> void:
	_theme = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)["theme"]
	var route = _route()

	# 1. Prairie tempérée : faune identique à P11/P23/P24 (mêmes groupes, mêmes espèces)
	var plain := _place(route, null)
	var temperate := _place(route, _model("temperate_grassland"))
	_check(not plain.is_empty() and str(plain) == str(temperate), "prairie tempérée : faune identique à celle d'avant la série U (%d groupes)" % plain.size())
	var muted := _place(route, _model(""))
	_check(str(plain) == str(muted), "modèle sans couche ni forçage : faune d'avant la série U")

	# 2. Savane : zèbres et girafes, tous à plus de 150 m de la route ; ni chevreuil ni lièvre
	var sav := _place(route, _model("savanna"))
	var cs := _species(sav)
	var far_ok := true
	for g in sav:
		if str(g.get("species", "")) in ["zebra", "giraffe"]:
			for p in _ground_points(g):
				if absf((p as Vector3).z) < 150.0:
					far_ok = false
	_check(cs.has("zebra") and cs.has("giraffe"), "savane : zèbres et girafes %s" % str(cs))
	_check(far_ok, "savane : zèbres et girafes à plus de 150 m de la route")
	_check(not cs.has("deer") and not cs.has("hare"), "savane : ni chevreuil ni lièvre")

	# 3. Montagne, toundra, jungle, littoral, zone humide : espèces du biome
	var alp := _species(_place(route, _model("alpine")))
	_check(alp.has("ibex") and alp.has("marmot") and not alp.has("deer") and not alp.has("hare"), "montagne : bouquetins et marmottes %s" % str(alp))
	var tun := _species(_place(route, _model("tundra")))
	_check(tun.has("reindeer") and not tun.has("cow") and not tun.has("sheep") and not tun.has("horse"), "toundra : rennes, pas de bétail %s" % str(tun))
	var jun_groups := _place(route, _model("jungle"))
	var others := 0
	for g in jun_groups:
		if str(g["species"]) == "bird" and str(g["type"]) != "raptor":
			others += 1
	var jun := _species(jun_groups)
	_check(jun.has("parrot") and others == 0, "jungle : perroquets, et pour seuls autres oiseaux les rapaces %s" % str(jun))
	var coa := _species(_place(route, _model("coast")))
	_check(coa.has("gull"), "littoral : mouettes %s" % str(coa))

	# 4. Désert : troupeaux de dromadaires propres au biome seulement près d'une eau (oasis) ; le bétail des prés
	#    (irrigués) y devient aussi dromadaire
	var dry_groups := _place(route, _model("sand_desert"))
	var wild_drom := 0
	for g in dry_groups:
		if str(g.get("species", "")) == "dromedary" and str(g["id"]).begins_with("c"):
			wild_drom += 1
	var dry := _species(dry_groups)
	_check(wild_drom == 0 and not dry.has("cow") and not dry.has("deer") and not dry.has("hare"), "désert sans eau : aucun troupeau loin des prés, ni vache ni gibier %s" % str(dry))
	var oases := {"areas": [], "lines": []}
	for k in range(CHUNKS):
		oases["areas"].append({"id": "o%d" % k, "kind": "pond", "level_y": 249.0, "outer": _square(k * 1000.0 + 200.0, 60.0, 80.0)})
		oases["areas"].append({"id": "p%d" % k, "kind": "pond", "level_y": 249.0, "outer": _square(k * 1000.0 + 600.0, -140.0, 80.0)})
	var oasis := _place(route, _model("sand_desert"), oases)
	var near_ok := true
	var n_drom := 0
	var ex := FaunaPlacer._make_ctx({"water": oases}, null, Rect2())
	for g in oasis:
		if str(g.get("species", "")) == "dromedary" and str(g["id"]).begins_with("c"):
			for p in _ground_points(g):
				n_drom += 1
				if FaunaPlacer._water_dist(ex, p.x, p.z) > FaunaPlacer.WATER_NEAR_M + FaunaPlacer.BIOME_SPREAD_M:
					near_ok = false
	_check(n_drom > 0 and near_ok, "oasis : %d dromadaires, tous près de l'eau" % n_drom)
	var wet := _species(_place(route, _model("wetland"), oases))
	_check(wet.has("flamingo") and wet.has("heron"), "zone humide : flamants et hérons %s" % str(wet))

	# 5. Aucun animal sur la chaussée, dans tous les biomes
	var road_ok := true
	var total := 0
	for biome in BiomeIds.BIOMES:
		for g in _place(route, _model(biome), oases):
			for p in _ground_points(g):
				total += 1
				if absf((p as Vector3).z) < FaunaPlacer.MIN_ROAD_CLEARANCE_M:
					road_ok = false
	_check(total > 0 and road_ok, "16 biomes : %d bêtes et oiseaux posés, aucun à moins de %.0f m de l'axe" % [total, FaunaPlacer.MIN_ROAD_CLEARANCE_M])

	# 6. Même graine, même faune ; biomes mêlés : densités mélangées et espèces des deux biomes
	_check(str(_place(route, _model("savanna"))) == str(sav), "même graine, même savane")
	var mix = BiomeModel.new(_theme, null)
	var grid_a := []
	var grid_b := []
	for i in range(BiomeLayer.POINTS):
		grid_a.append(128)
		grid_b.append(127)
	for ix in range(CHUNKS + 1):
		for iz in [-1, 0]:
			mix.layer.put_tile("near", ix, iz, BiomeLayer.parse_tile({"biomes": ["savanna", "temperate_grassland"], "grid": 17,
				"weights": [grid_a, grid_b]}, PackedStringArray()))
	var dm := FaunaPlacer._biome_density(mix, mix.weights_at(500.0, 0.0))
	_check(absf(dm["deer"] - (0.7 * 128.0 + 0.1 * 127.0) / 255.0) < 1e-3, "densité mélangée : chevreuil %.3f (moyenne pondérée de 0,7 et 0,1)" % dm["deer"])
	var cm := _species(_place(route, mix))
	_check(cm.has("zebra") and (cm.has("cow") or cm.has("sheep") or cm.has("horse")), "savane et prairie mêlées : zèbres et bétail %s" % str(cm))

	# 7. Comportements : les mouettes s'envolent sans croasser ; marmottes et bouquetins réagissent comme lièvres et troupeaux
	var gulls := []
	for g in _place(route, _model("coast")):
		if str(g["type"]) == "crows" and str(g["species"]) == "gull":
			gulls.append(g)
	var b := FaunaBehaviour.new()
	b.setup(gulls)
	var caws := 0
	for g in gulls:
		b.update(g["pos"], 10.0)
		caws += b.events.size()
	_check(not gulls.is_empty() and caws == 0 and str(gulls[0]["state"]) == "flight", "mouettes : %d groupes s'envolent au passage, sans croassement" % gulls.size())

	# 8. Affichage : une espèce par MultiMesh, budgets de `low` respectés
	var r := FaunaRenderer.new()
	r.set_preset("low")
	var k := 0
	for biome in ["savanna", "alpine", "coast", "jungle", "wetland", "tundra"]:
		r.set_chunk(k, _place(route, _model(biome), oases))
		k += 1
	r.update(Vector3(500.0, 252.0, 0.0), Vector3(-9000.0, 250.0, 0.0), 1.0)
	var n_animals := 0
	var n_birds := 0
	for sp in FaunaRenderer.GROUND_SPECIES:
		n_animals += r.visible_count(sp)
	for sp in FaunaRenderer.BIRD_SPECIES:
		n_birds += r.visible_count(sp)
	_check(n_animals > 0 and n_animals <= r.budget_animals, "low : %d bêtes affichées (budget %d)" % [n_animals, r.budget_animals])
	_check(n_birds > 0 and n_birds <= r.budget_birds, "low : %d oiseaux affichés (budget %d)" % [n_birds, r.budget_birds])
	var kinds := 0
	for sp in FaunaRenderer.SPECIES:
		if r.visible_count(sp) > 0:
			kinds += 1
	_check(kinds >= 4, "low : %d espèces à l'écran" % kinds)
	r.free()

	# 9. world_streamer.gd : biome forcé transmis aux arbres et aux animaux, sol aux couleurs du biome ; « auto »
	#    sans couche biome : rendu d'avant la série U
	var ws = WorldStreamer.new()
	var trees = TreeRenderer.new()
	var osm = OsmStreamer.new()
	ws.tree_renderer = trees
	ws.osm_streamer = osm
	ws.set_theme(_theme)
	ws.forced_biome = "savanna"
	ws.set_world(route, "")
	var sand: Color = _model("savanna").params("savanna")["terrain"]["grass_color"]
	_check(trees.biome_model != null and osm.biome_model == trees.biome_model and ws.start_biome() == "savanna"
		and ws._ground_color.is_equal_approx(sand), "--biome=savanna : arbres et animaux suivent la savane, sol couleur sable")
	var tile_mat = ws._terrain_material_for("near:0:0")
	_check(ws.biome_textures != null and tile_mat is ShaderMaterial and (tile_mat as ShaderMaterial).shader.resource_path.ends_with("terrain_biomes.gdshader"),
		"--biome=savanna : tuiles de terrain au shader multi-biome (U6)")
	ws.forced_biome = "auto"
	ws.set_world(route, "")
	_check(trees.biome_model == null and osm.biome_model == null and ws.biome_textures == null
		and ws._terrain_material_for("near:0:0") == ws._terrain_material, "--biome=auto sans couche biome : arbres, animaux et sol d'avant la série U")
	ws.free()
	trees.free()
	osm.free()

	print("test_fauna_biomes : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
