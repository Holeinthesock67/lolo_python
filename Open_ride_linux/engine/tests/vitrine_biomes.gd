extends SceneTree

## Vitrine des biomes (série U) : pour chaque biome forcé, une route droite dans un paysage plat avec le sol,
## la végétation (lot U7), le brouillard et la teinte de la lumière du biome, tirés du thème par défaut 2.0
## (lot U15) par biome_model.gd. Sans core ni parcours ; captures comparables d'un biome à l'autre.
##
##   xvfb-run -a $GODOT --path engine --rendering-driver opengl3 --rendering-method gl_compatibility \
##     --audio-driver Dummy --script res://tests/vitrine_biomes.gd -- --out DOSSIER \
##     [--biomes alpine,savanna] [--quality low,medium,high] [--size 1680x1050]
##
## Écrit DOSSIER/<biome>_<vue>_<préréglage>.png et DOSSIER/vitrine_biomes.csv (biome ; vue ; préréglage ;
## arbres ; triangles ; appels de dessin ; objets ; préparation des arbres en ms). Les temps du processeur
## graphique se mesurent sur le PC cible, pas ici : le rendu logiciel de Xvfb ne dit rien de la GTX 1060.

const BiomeIds := preload("res://scripts/biome_ids.gd")
const BiomeModel := preload("res://scripts/biome_model.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const TerrainMaterial := preload("res://scripts/terrain_material.gd")
const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")

const ROAD_WIDTH_M := 6.0
const GROUND_Y := 100.0
const SETTLE_FRAMES := 20

## Vues : position de la caméra, point visé, champ vertical (degrés). La route part de (0, 0) vers −z.
const VIEWS := {
	"route": [Vector3(1.2, GROUND_Y + 1.6, 0.0), Vector3(0.0, GROUND_Y + 0.8, -120.0), 70.0],
	"bord": [Vector3(4.0, GROUND_Y + 1.7, -20.0), Vector3(40.0, GROUND_Y + 3.0, -70.0), 60.0],
	"haut": [Vector3(-60.0, GROUND_Y + 45.0, 60.0), Vector3(0.0, GROUND_Y, -250.0), 60.0],
}

var _out_dir := "user://vitrine_biomes"
var _presets: Array = ["low"]
var _biomes: Array = BiomeIds.BIOMES.duplicate()
var _size := Vector2i(1280, 720)


func _init() -> void:
	var args := OS.get_cmdline_user_args()
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
	csv.store_line("biome;vue;préréglage;arbres;triangles;appels_dessin;objets;preparation_arbres_ms")
	for preset in _presets:
		for biome in _biomes:
			var model = BiomeModel.new(theme, null)
			if not model.set_forced(biome):
				printerr("[vitrine_biomes] biome inconnu : ", biome)
				continue
			var built := _build_world(theme, model, biome, preset)
			var vp: SubViewport = built["vp"]
			for view in VIEWS:
				var v: Array = VIEWS[view]
				var cam: Camera3D = vp.get_node("Camera")
				cam.fov = v[2]
				cam.look_at_from_position(v[0], v[1])
				for f in range(SETTLE_FRAMES):
					await process_frame
				var path := _out_dir.path_join("%s_%s_%s.png" % [biome, view, preset])
				vp.get_texture().get_image().save_png(path)
				var rid := vp.get_viewport_rid()
				var vis := RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE
				var tris := RenderingServer.viewport_get_render_info(rid, vis, RenderingServer.VIEWPORT_RENDER_INFO_PRIMITIVES_IN_FRAME)
				var draws := RenderingServer.viewport_get_render_info(rid, vis, RenderingServer.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME)
				var objs := RenderingServer.viewport_get_render_info(rid, vis, RenderingServer.VIEWPORT_RENDER_INFO_OBJECTS_IN_FRAME)
				csv.store_line("%s;%s;%s;%d;%d;%d;%d;%.1f" % [biome, view, preset, built["trees"], tris, draws, objs, built["prep_ms"]])
				print("[vitrine_biomes] %s : %d arbres, %d triangles, %d appels de dessin" % [path, built["trees"], tris, draws])
			vp.queue_free()
			await process_frame
	csv.close()
	quit(0)


func _build_world(theme: Dictionary, model, biome: String, preset: String) -> Dictionary:
	var p: Dictionary = model.params(biome)
	var vp := SubViewport.new()
	vp.size = _size
	vp.own_world_3d = true
	vp.msaa_3d = Viewport.MSAA_4X
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(vp)
	var env := Environment.new()
	var sky_mat := ProceduralSkyMaterial.new()
	var haze: float = p["sky"]["haze"]
	var tint: Color = p["sky"]["light_tint"]
	var horizon := RenderQuality.FOG_COLOR.lerp(Color(0.86, 0.80, 0.68), haze * 0.6) * tint
	sky_mat.sky_horizon_color = horizon
	sky_mat.ground_horizon_color = horizon
	env.background_mode = Environment.BG_SKY
	env.sky = Sky.new()
	env.sky.sky_material = sky_mat
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	RenderQuality.apply_fog(env, preset, true, horizon, float(p["sky"]["fog_density"]))
	# Courbe Filmic (blanc 6) : sans elle, les sols clairs (neige, sable) saturent en blanc dans le rendu logiciel.
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_white = 6.0
	var we := WorldEnvironment.new()
	we.environment = env
	vp.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.basis = Basis.looking_at(-(p["sky"]["sun_direction"] as Vector3), Vector3.UP)
	sun.light_color = tint
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
	ground.material_override = TerrainMaterial.create_material(model.terrain_theme(biome))
	vp.add_child(ground)
	var road := MeshInstance3D.new()
	road.mesh = _road_mesh()
	road.position.y = GROUND_Y
	road.material_override = RoadBuilder.make_markings_material(RoadBuilder.ROAD_COLOR, ROAD_WIDTH_M)
	vp.add_child(road)

	var trees := TreeRenderer.new()
	vp.add_child(trees)
	trees.set_preset(preset)
	trees.biome_model = model
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

	var cam := Camera3D.new()
	cam.name = "Camera"
	cam.far = RenderQuality.camera_far_m(preset)
	cam.current = true
	vp.add_child(cam)
	return {"vp": vp, "trees": trees.get_active_tree_count(), "prep_ms": prep_ms}


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
	func sample(s: float) -> Dictionary:
		return {"x": 0.0, "y": GROUND_Y, "z": -s, "heading_deg": 0.0}
