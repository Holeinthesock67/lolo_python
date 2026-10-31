extends SceneTree

## Vitrine des biomes (série U) : pour chaque biome forcé, une route droite dans un paysage plat avec le sol (lot U6),
## la végétation (lot U7), les animaux (lot U12), les détails de sol (rochers, herbes hautes, termitières, lot U8), et
## l'atmosphère du biome (lot U10, atmosphere_model.gd : brouillard, voile et teinte de la lumière, air humide,
## brume de chaleur des déserts et de la savane hors `low`), tirés du thème par défaut 2.0 (lot U15) par biome_model.gd. Un étang à droite de la route (oasis des déserts, flamants),
## un bois, un pré, un champ et une prairie (zones OSM de la faune d'avant la série U). Sans core ni parcours ;
## captures comparables d'un biome à l'autre. La vue `faune` cadre le groupe d'animaux propre au biome.
##
##   xvfb-run -a $GODOT --path engine --rendering-driver opengl3 --rendering-method gl_compatibility \
##     --audio-driver Dummy --script res://tests/vitrine_biomes.gd -- --out DOSSIER \
##     [--biomes alpine,savanna] [--quality low,medium,high] [--size 1680x1050] \
##     [--compare REF] [--seuil-ssim 0.97] [--tolerance 10] [--max-saturated 5]
##
## Écrit DOSSIER/<biome>_<vue>_<préréglage>.png et DOSSIER/vitrine_biomes.csv (biome ; vue ; préréglage ;
## préréglage appliqué ;
## arbres ; triangles ; appels de dessin ; objets ; préparation des arbres en ms ; bêtes et oiseaux affichés ;
## espèces animales placées ; placement des animaux en ms ; rochers, herbes hautes et termitières affichés ;
## part de pixels saturés du sol en % ; luminance moyenne du sol ; brume de chaleur et humidité de l'atmosphère). Contrôles automatiques (vitrine_checks.gd) :
## exposition du sol (bas de l'image, sauf vue `faune`), et comparaison à des captures de référence avec
## --compare ; code de sortie 1 si l'un échoue. Les temps du processeur
## graphique se mesurent sur le PC cible, pas ici : le rendu logiciel de Xvfb ne dit rien de la GTX 1060.

const BiomeIds := preload("res://scripts/biome_ids.gd")
const BiomeModel := preload("res://scripts/biome_model.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const BiomeTextures := preload("res://scripts/biome_textures.gd")
const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const FaunaPlacer := preload("res://scripts/fauna_placer.gd")
const FaunaRenderer := preload("res://scripts/fauna_renderer.gd")
const GroundDetails := preload("res://scripts/ground_details.gd")
const VitrineChecks := preload("res://tests/vitrine_checks.gd")
const AtmosphereModel := preload("res://scripts/atmosphere_model.gd")
const HeatHazeShader := preload("res://shaders/heat_haze.gdshader")

const ROAD_WIDTH_M := 6.0
const GROUND_Y := 100.0
const SETTLE_FRAMES := 20

## Vues : position de la caméra, point visé, champ vertical (degrés). La route part de (0, 0) vers −z.
const VIEWS := {
	"route": [Vector3(1.2, GROUND_Y + 1.6, 0.0), Vector3(0.0, GROUND_Y + 0.8, -120.0), 70.0],
	"bord": [Vector3(4.0, GROUND_Y + 1.7, -20.0), Vector3(40.0, GROUND_Y + 3.0, -70.0), 60.0],
	"haut": [Vector3(-60.0, GROUND_Y + 45.0, 60.0), Vector3(0.0, GROUND_Y, -250.0), 60.0],
	"faune": [],   # calculée par _fauna_view
}
## Étang (x, z, largeur, profondeur) et zones OSM de la faune, à droite (+x) et à gauche de la route.
const POND := Rect2(45.0, -230.0, 90.0, 70.0)
const AREAS := [
	{"id": "bois", "kind": "wood", "outer": [[-340.0, -420.0], [-60.0, -420.0], [-60.0, -120.0], [-340.0, -120.0]], "holes": [], "density": 0.8},
	{"id": "pre", "kind": "meadow", "outer": [[15.0, -120.0], [140.0, -120.0], [140.0, -30.0], [15.0, -30.0]], "holes": []},
	{"id": "champ", "kind": "farmland", "outer": [[-160.0, -100.0], [-15.0, -100.0], [-15.0, -20.0], [-160.0, -20.0]], "holes": []},
	{"id": "prairie", "kind": "grassland", "outer": [[150.0, -700.0], [420.0, -700.0], [420.0, -350.0], [150.0, -350.0]], "holes": []},
]
## Recul de la caméra de la vue `faune` selon la taille des bêtes (m).
const FAUNA_VIEW_M := {"marmot": 6.0, "hare": 6.0, "heron": 9.0, "ibex": 14.0, "giraffe": 34.0, "zebra": 26.0, "flamingo": 9.0, "gull": 7.0}
const FAUNA_VIEW_DEFAULT_M := 20.0

var _out_dir := "user://vitrine_biomes"
var _presets: Array = ["low"]
var _biomes: Array = BiomeIds.BIOMES.duplicate()
var _size := Vector2i(1280, 720)
var _checks = VitrineChecks.new()


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	_checks.parse_args(args)
	for i in range(args.size() - 1):
		if args[i] == "--out":
			_out_dir = args[i + 1]
		elif args[i] == "--quality":
			_presets = Array(args[i + 1].split(","))
		elif args[i] == "--biomes":
			_biomes = Array(args[i + 1].split(","))
		elif args[i] == "--size":
			var wh := args[i + 1].split("x")
			_size = Vector2i(int(wh[0]), int(wh[1]))
	call_deferred("_run")


func _run() -> void:
	DirAccess.make_dir_recursive_absolute(_out_dir)
	var theme: Dictionary = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)["theme"]
	var csv := FileAccess.open(_out_dir.path_join("vitrine_biomes.csv"), FileAccess.WRITE)
	csv.store_line("biome;vue;préréglage;qualite_appliquee;arbres;triangles;appels_dessin;objets;preparation_arbres_ms;betes;oiseaux;especes;placement_faune_ms;rochers;herbes_hautes;termitieres;sol_sature_pct;sol_luminance;brume_chaleur;humidite")
	for preset in _presets:
		var applied := VitrineChecks.applied_quality(preset, "vitrine_biomes")
		for biome in _biomes:
			var model = BiomeModel.new(theme, null)
			if not model.set_forced(biome):
				printerr("[vitrine_biomes] biome inconnu : ", biome)
				continue
			var built := _build_world(theme, model, biome, preset)
			var vp: SubViewport = built["vp"]
			for view in VIEWS:
				var v: Array = VIEWS[view] if view != "faune" else built["fauna_view"]
				var cam: Camera3D = vp.get_node("Camera")
				cam.fov = v[2]
				cam.look_at_from_position(v[0], v[1])
				_place_heat_haze(vp, cam)
				var fauna: Node = vp.get_node("Fauna")
				for f in range(SETTLE_FRAMES):
					# Cycliste loin de tout : aucune bête ne fuit
					fauna.update(cam.position, Vector3(0.0, GROUND_Y, 5000.0), 3.0 + f * 0.05)
					await process_frame
				var n_animals := 0
				for sp in FaunaRenderer.GROUND_SPECIES:
					n_animals += fauna.visible_count(sp)
				var n_birds := 0
				for sp in FaunaRenderer.BIRD_SPECIES:
					n_birds += fauna.visible_count(sp)
				var path := _out_dir.path_join("%s_%s_%s.png" % [biome, view, preset])
				var img := vp.get_texture().get_image()
				img.save_png(path)
				# Sol : bas de l'image, route comprise ; la vue `faune` cadre une bête, parfois d'en dessous
				var expo: Dictionary = _checks.exposure(img, "%s_%s_%s" % [biome, view, preset]) if view != "faune" else {"saturated_pct": NAN, "luma": NAN}
				var rid := vp.get_viewport_rid()
				var vis := RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE
				var tris := RenderingServer.viewport_get_render_info(rid, vis, RenderingServer.VIEWPORT_RENDER_INFO_PRIMITIVES_IN_FRAME)
				var draws := RenderingServer.viewport_get_render_info(rid, vis, RenderingServer.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME)
				var objs := RenderingServer.viewport_get_render_info(rid, vis, RenderingServer.VIEWPORT_RENDER_INFO_OBJECTS_IN_FRAME)
				var details: Node = vp.get_node("GroundDetails")
				csv.store_line("%s;%s;%s;%s;%d;%d;%d;%d;%.1f;%d;%d;%s;%.1f;%d;%d;%d;%.2f;%.3f;%.2f;%.2f" % [biome, view, preset, applied, built["trees"], tris, draws, objs, built["prep_ms"],
					n_animals, n_birds, built["species"], built["fauna_ms"], details.get_positions("rock").size(),
					details.get_positions("grass").size(), details.get_positions("termite").size(), expo["saturated_pct"], expo["luma"],
					built["atmo"]["heat_haze"], built["atmo"]["humidity"]])
				print("[vitrine_biomes] %s : %d arbres, %d bêtes, %d oiseaux, %d triangles, %d appels de dessin" % [path, built["trees"], n_animals, n_birds, tris, draws])
			vp.queue_free()
			await process_frame
	csv.close()
	_checks.compare(_out_dir)
	quit(_checks.exit_code("vitrine_biomes"))


func _build_world(theme: Dictionary, model, biome: String, preset: String) -> Dictionary:
	var p: Dictionary = model.params(biome)
	var atmo := AtmosphereModel.params_at(model, {biome: 1.0}, AtmosphereModel.daylight_from_theme(theme),
		{"rain": 0.0, "snow": 0.0, "fog_boost": 0.0}, preset)
	var vp := SubViewport.new()
	vp.size = _size
	vp.own_world_3d = true
	vp.msaa_3d = Viewport.MSAA_4X
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(vp)
	var env := Environment.new()
	var sky_mat := ProceduralSkyMaterial.new()
	var tint: Color = atmo["light_tint"]
	var horizon: Color = atmo["horizon_color"]
	sky_mat.sky_horizon_color = horizon
	sky_mat.ground_horizon_color = horizon
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	env.sky.sky_material = sky_mat
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	RenderQuality.apply_fog(env, preset, true, horizon, float(atmo["fog_density"]), float(atmo["fog_end_factor"]))
	# Courbe Filmic (blanc 6) : sans elle, les sols clairs (neige, sable) saturent en blanc dans le rendu logiciel.
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_white = 6.0
	var we := WorldEnvironment.new()
	we.environment = env
	vp.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.basis = Basis.looking_at(-(atmo["sun_direction"] as Vector3), Vector3.UP)
	sun.light_color = tint
	sun.light_energy *= float(atmo["light_energy_factor"])
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = QualityPresets.shadow_distance_m(preset)
	vp.add_child(sun)

	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(3000.0, 3000.0)
	plane.subdivide_width = 60
	plane.subdivide_depth = 60
	ground.mesh = plane
	ground.position = Vector3(0.0, GROUND_Y - 0.02, -500.0)
	ground.material_override = BiomeTextures.new(model, ThemeLoader.DEFAULT_THEME_DIR, preset).tile_material("near", 0, 0)
	vp.add_child(ground)
	var road := MeshInstance3D.new()
	road.mesh = _road_mesh()
	road.position.y = GROUND_Y
	road.material_override = RoadBuilder.make_markings_material(RoadBuilder.ROAD_COLOR, ROAD_WIDTH_M)
	vp.add_child(road)

	var pond := MeshInstance3D.new()
	var pond_mesh := PlaneMesh.new()
	pond_mesh.size = POND.size
	pond.mesh = pond_mesh
	pond.position = Vector3(POND.get_center().x, GROUND_Y + 0.03, POND.get_center().y)
	var water_mat := StandardMaterial3D.new()
	water_mat.albedo_color = p["water"]["color"]
	water_mat.roughness = 0.08
	water_mat.metallic_specular = 0.8
	pond.material_override = water_mat
	vp.add_child(pond)

	var trees := TreeRenderer.new()
	vp.add_child(trees)
	trees.set_preset(preset)
	trees.biome_model = model
	trees.near_water = func(x: float, z: float) -> bool:
		var dx := maxf(maxf(POND.position.x - x, 0.0), x - POND.end.x)
		var dz := maxf(maxf(POND.position.y - z, 0.0), z - POND.end.y)
		return sqrt(dx * dx + dz * dz) <= 80.0
	TreeRenderer.apply_wind({"dir": Vector3(1.0, 0.0, 0.0), "strength": 0.3, "gust": 0.0, "phase": 0.0})
	var heights := PackedFloat32Array()
	heights.resize(101 * 101)
	heights.fill(GROUND_Y)
	var route := StraightRoute.new()
	var t0 := Time.get_ticks_usec()
	for tz in range(-2, 1):
		for tx in range(-1, 1):
			trees.add_tile(trees.prepare_tile(tx, tz, heights, route, theme,
				float(QualityPresets.preset(preset)["vegetation_density_factor"])))
	var prep_ms := (Time.get_ticks_usec() - t0) / 1000.0 / 6.0
	trees.enforce_budget(Vector3(0.0, GROUND_Y, 0.0))

	# Animaux : zones OSM et étang ci-dessus, deux tronçons de 1 km le long de la route
	var water := {"areas": [{"id": "etang", "kind": "pond", "level_y": GROUND_Y, "outer": [[POND.position.x, POND.position.y],
		[POND.end.x, POND.position.y], [POND.end.x, POND.end.y], [POND.position.x, POND.end.y]]}], "lines": []}
	var groups := []
	var f0 := Time.get_ticks_usec()
	for k in range(2):
		groups.append_array(FaunaPlacer.place_chunk(k, AREAS, [], route, theme.get("fauna", {}), {
			"height_at": func(_x: float, _z: float) -> float: return GROUND_Y,
			"water": water, "biome_model": model}))
	var fauna_ms := (Time.get_ticks_usec() - f0) / 1000.0 / 2.0
	var fauna := FaunaRenderer.new()
	fauna.name = "Fauna"
	vp.add_child(fauna)
	fauna.set_preset(preset)
	fauna.set_chunk(0, groups)
	var species := {}
	for g in groups:
		species[str(g.get("species", ""))] = true

	# Détails de sol : budgets du décor vivant, hors étang ; posés autour du début de la route
	var details := GroundDetails.new()
	details.name = "GroundDetails"
	vp.add_child(details)
	var living := QualityPresets.living(preset)
	details.configure({"rock": int(living["ground_rocks"]), "grass": int(living["ground_grass"]),
		"termite": int(living["ground_termites"])}, route, model, ROAD_WIDTH_M)
	details.exclusions = [PackedVector2Array([POND.position, Vector2(POND.end.x, POND.position.y), POND.end,
		Vector2(POND.position.x, POND.end.y)])]
	for i in range(400):
		details.update(60.0)
		if details.is_settled():
			break

	var cam := Camera3D.new()
	cam.name = "Camera"
	cam.far = RenderQuality.camera_far_m(preset)
	cam.current = true
	vp.add_child(cam)
	if float(atmo["heat_haze"]) > 0.0:
		var layer := CanvasLayer.new()
		var rect := ColorRect.new()
		rect.name = "HeatHaze"
		rect.set_anchors_preset(Control.PRESET_FULL_RECT)
		rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var mat := ShaderMaterial.new()
		mat.shader = HeatHazeShader
		mat.set_shader_parameter("strength", float(atmo["heat_haze"]))
		rect.material = mat
		layer.add_child(rect)
		vp.add_child(layer)
	return {"vp": vp, "atmo": atmo, "trees": trees.get_active_tree_count(), "prep_ms": prep_ms, "fauna_ms": fauna_ms,
		"species": ",".join(PackedStringArray(species.keys())), "fauna_view": _fauna_view(groups)}


## Brume de chaleur : bande centrée sur l'horizon de la vue (point lointain droit devant, à hauteur d'œil).
func _place_heat_haze(vp: SubViewport, cam: Camera3D) -> void:
	var rect: ColorRect = vp.find_child("HeatHaze", true, false)
	if rect == null:
		return
	var ahead := -cam.global_transform.basis.z
	ahead.y = 0.0
	var far_pt := cam.global_position + ahead.normalized() * 5000.0
	var y := cam.unproject_position(far_pt).y / float(_size.y) if not cam.is_position_behind(far_pt) else -1.0
	(rect.material as ShaderMaterial).set_shader_parameter("horizon_y", y)


## Vue `faune` : le premier groupe propre au biome (BIOME_GROUPS, troupeau de préférence), sinon le premier
## troupeau, vu depuis la route à FAUNA_VIEW_M de lui ; une bande d'oiseaux est vue d'en dessous.
func _fauna_view(groups: Array) -> Array:
	var best := {}
	var rank := 9
	for g in groups:
		var own := str(g["id"]).begins_with("c") and str(g.get("species", "bird")) != "bird"
		var t := str(g["type"])
		var r := 0 if own and t == "herd" else (1 if own else (2 if t == "herd" else (3 if t in ["deer", "hare"] else 9)))
		if r < rank:
			rank = r
			best = g
	if best.is_empty():
		return VIEWS["bord"]
	var t := str(best["type"])
	if t == "birds":
		var c: Vector3 = best["center"]
		return [Vector3(c.x * 0.5, GROUND_Y + 2.0, c.z + 30.0), c, 60.0]
	var target := Vector3.ZERO
	var pts := []
	if best.has("members") and t != "birds":
		for m in best["members"]:
			pts.append(m["pos"])
	else:
		pts.append(best["pos"])
	for q in pts:
		target += q
	target /= float(pts.size())
	var d := float(FAUNA_VIEW_M.get(str(best.get("species", "")), FAUNA_VIEW_DEFAULT_M))
	var toward_road := Vector3(-signf(target.x), 0.0, 0.35).normalized()
	var aim := target + Vector3(0.0, 0.8 if d < 10.0 else 1.5, 0.0)
	return [target + toward_road * d + Vector3(0.0, 1.6 if d < 10.0 else 3.0, 0.0), aim, 45.0 if d < 10.0 else 55.0]


## Ruban de route droit de 1 200 m (UV d'E1), le long de −z.
func _road_mesh() -> ArrayMesh:
	var half := ROAD_WIDTH_M * 0.5 + RoadBuilder.SHOULDER_WIDTH_M
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var step := 4.0
	for j in range(300):
		var s0 := j * step
		var s1 := s0 + step
		var quad := [[-half, s0, 0.0], [half, s1, 1.0], [half, s0, 1.0], [-half, s0, 0.0], [-half, s1, 0.0], [half, s1, 1.0]]
		for q in quad:
			st.set_normal(Vector3.UP)
			st.set_uv(Vector2(q[2], q[1] / RoadBuilder.V_REPEAT_M))
			st.add_vertex(Vector3(q[0], 0.0, -q[1]))
	st.generate_tangents()
	return st.commit()


## Route droite vers −z pour le couloir sans arbres de vegetation_placer.gd (mêmes champs que route_data.gd).
class StraightRoute:
	var n := 121
	var ds_m := 10.0
	var length_m := 1200.0
	var x := PackedFloat64Array()
	var z := PackedFloat64Array()
	var s := PackedFloat64Array()
	var alt_m := PackedFloat64Array()
	var relief_k := 1.0
	func _init() -> void:
		for i in range(n):
			x.append(0.0)
			z.append(-i * ds_m)
			s.append(i * ds_m)
			alt_m.append(GROUND_Y)
	func sample_point(d: float) -> Vector3:
		return Vector3(0.0, GROUND_Y, -d)
	func is_loop() -> bool:
		return false
	func display_y(alt: float) -> float:
		return alt
	func sample(s: float) -> Dictionary:
		return {"x": 0.0, "y": GROUND_Y, "z": -s, "heading_deg": 0.0}
