extends SceneTree

## Vitrine des paysages, partie 2 (lot U25-p2) : sol du shader multi-biome dans un relief fait pour chaque effet,
## avec et sans le paysage de la tuile (même relief, même lumière) :
## - `canyon` : désert de roche dans un canyon à deux étages de falaises (strates colorées des parois) ;
## - `rizieres` : cultures sur des collines de 5 à 20° (gradins inondés, diguettes) ;
## - `fjord` : forêt tempérée au pied de parois de 600 m (cascades).
## Sans core ni parcours ; vue fixe par scène. Le ciel et la mer des paysages (atmosphere_model.gd, sea_mesh.gd)
## ne sont pas dans cette vitrine : test_atmosphere_model.gd et test_sea_mesh.gd les vérifient, le parcours de
## démonstration « Tour des nouveaux paysages » les montre en jeu.
##
##   xvfb-run -a $GODOT --path engine --rendering-driver vulkan --rendering-method forward_plus \
##     --audio-driver Dummy --script res://tests/vitrine_paysages.gd -- --out DOSSIER \
##     [--scenes canyon,rizieres,fjord] [--quality low,medium,high] [--size 1680x1050] [--temps 0]
##
## Écrit DOSSIER/<scène>_<préréglage>.png (paysage) et DOSSIER/<scène>_sans_<préréglage>.png (même biome sans
## paysage), et DOSSIER/vitrine_paysages.csv (scène ; paysage ; préréglage ; préréglage appliqué ; triangles ;
## appels de dessin ; part de pixels saturés du sol en % ; luminance moyenne du sol). Contrôle automatique
## (vitrine_checks.gd) : exposition du sol ; code de sortie 1 s'il échoue. Les temps du processeur graphique se
## mesurent sur le PC cible.

const BiomeModel := preload("res://scripts/biome_model.gd")
const BiomeLayer := preload("res://scripts/biome_layer.gd")
const BiomeTextures := preload("res://scripts/biome_textures.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const VitrineChecks := preload("res://tests/vitrine_checks.gd")

## Scène : paysage, biome de la tuile, caméra (position, point visé), soleil (élévation, azimut en degrés).
const SCENES := {
	"canyon": {"landscape": "canyon", "biome": "rock_desert", "cam": [Vector3(820.0, 1475.0, 980.0), Vector3(470.0, 1260.0, 380.0)], "sun": [-35.0, -60.0]},
	"rizieres": {"landscape": "rizieres", "biome": "farmland", "cam": [Vector3(520.0, 395.0, 880.0), Vector3(470.0, 320.0, 640.0)], "sun": [-45.0, -30.0]},
	"fjord": {"landscape": "fjord", "biome": "temperate_forest", "cam": [Vector3(420.0, 70.0, 960.0), Vector3(820.0, 330.0, 420.0)], "sun": [-40.0, 150.0]},
}
const SETTLE_FRAMES := 12

var _out_dir := "user://vitrine_paysages"
var _presets: Array = ["low"]
var _scenes: Array = SCENES.keys()
var _size := Vector2i(1280, 720)
var _time := 0.0
var _checks = VitrineChecks.new()


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	_checks.parse_args(args)
	for i in range(args.size()):
		match args[i]:
			"--out":
				_out_dir = args[i + 1]
			"--quality":
				_presets = Array(args[i + 1].split(","))
			"--scenes":
				_scenes = Array(args[i + 1].split(","))
			"--size":
				var wh: PackedStringArray = args[i + 1].split("x")
				_size = Vector2i(int(wh[0]), int(wh[1]))
			"--temps":
				_time = float(args[i + 1])
	call_deferred("_run")


## Relief de chaque scène : altitude au point (x, z) de la tuile (0 à 1 000 m).
static func height(scene: String, x: float, z: float) -> float:
	match scene:
		"canyon":
			# Fond plat de 140 m, première falaise de 140 m, replat, seconde falaise de 40 m jusqu'au plateau
			var d := absf(x - (480.0 + 110.0 * sin(z / 230.0)))
			return 1200.0 + 140.0 * smoothstep(70.0, 115.0, d) + 22.0 * smoothstep(115.0, 200.0, d) \
				+ 40.0 * smoothstep(205.0, 235.0, d) + 3.0 * sin(x / 37.0 + z / 53.0)
		"rizieres":
			return 300.0 + 45.0 * sin(x / 170.0) * cos(z / 210.0) + 10.0 * sin((x + z) / 95.0)
		"fjord":
			# Fond de vallée à 20 m, parois de 600 m sur 250 m (jusqu'à 75°), de chaque côté
			var d := absf(x - 420.0 - 40.0 * sin(z / 300.0))
			var t := smoothstep(110.0, 360.0, d)
			return 20.0 + 640.0 * pow(t, 1.25) + 6.0 * sin(z / 47.0 + x / 61.0)
	return 0.0


func _tile_heights(scene: String) -> PackedFloat32Array:
	var h := PackedFloat32Array()
	h.resize(TerrainTiles.SAMPLES * TerrainTiles.SAMPLES)
	var cell: float = TerrainTiles.LEVELS["near"]["cell"]
	for j in range(TerrainTiles.SAMPLES):
		for i in range(TerrainTiles.SAMPLES):
			h[j * TerrainTiles.SAMPLES + i] = height(scene, i * cell, j * cell)
	return h


func _edges(scene: String) -> Dictionary:
	var cell: float = TerrainTiles.LEVELS["near"]["cell"]
	var out := {"west": PackedFloat32Array(), "east": PackedFloat32Array(), "north": PackedFloat32Array(), "south": PackedFloat32Array()}
	for k in range(TerrainTiles.SAMPLES):
		out["west"].append(height(scene, -cell, k * cell))
		out["east"].append(height(scene, 1000.0 + cell, k * cell))
		out["north"].append(height(scene, k * cell, -cell))
		out["south"].append(height(scene, k * cell, 1000.0 + cell))
	return out


func _tile(biome: String, landscape: String) -> Dictionary:
	var g := PackedFloat32Array()
	g.resize(BiomeLayer.POINTS)
	g.fill(1.0)
	var names: Array[String] = [biome]
	var grids: Array[PackedFloat32Array] = [g]
	var variant = {"ground": null, "roofs": null, "landscape": landscape} if landscape != "" else null
	return {"biomes": names, "weights": grids, "variant": variant}


func _run() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(_out_dir))
	RenderingServer.global_shader_parameter_set("anim_time", _time)
	var theme: Dictionary = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)["theme"]
	var csv := FileAccess.open(_out_dir.path_join("vitrine_paysages.csv"), FileAccess.WRITE)
	csv.store_line("scene;paysage;preset;qualite_appliquee;triangles;appels_dessin;sol_sature_pct;sol_luminance")
	for scene in _scenes:
		if not SCENES.has(scene):
			push_error("[vitrine_paysages] scène inconnue : " + str(scene))
			continue
		var sc: Dictionary = SCENES[scene]
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, TerrainTiles.build_arrays(_tile_heights(scene), "near", _edges(scene)))
		for preset in _presets:
			var applied := VitrineChecks.applied_quality(preset, "vitrine_paysages")
			for landscape in [sc["landscape"], ""]:
				var layer := BiomeLayer.new()
				layer.put_tile("near", 0, 0, _tile(sc["biome"], landscape))
				var bt := BiomeTextures.new(BiomeModel.new(theme, layer), ThemeLoader.DEFAULT_THEME_DIR, preset)
				var vp := SubViewport.new()
				vp.size = _size
				vp.own_world_3d = true
				vp.msaa_3d = Viewport.MSAA_4X
				vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
				root.add_child(vp)
				var env := Environment.new()
				var sky_mat := ProceduralSkyMaterial.new()
				sky_mat.sky_horizon_color = RenderQuality.FOG_COLOR
				sky_mat.ground_horizon_color = RenderQuality.FOG_COLOR
				sky_mat.ground_bottom_color = RenderQuality.FOG_COLOR
				env.background_mode = Environment.BG_SKY
				env.sky = Sky.new()
				env.sky.sky_material = sky_mat
				env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
				env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
				RenderQuality.apply_fog(env, preset, true, RenderQuality.FOG_COLOR, 0.0)
				env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
				env.tonemap_white = 6.0
				var we := WorldEnvironment.new()
				we.environment = env
				vp.add_child(we)
				var sun := DirectionalLight3D.new()
				sun.rotation = Vector3(deg_to_rad(float(sc["sun"][0])), deg_to_rad(float(sc["sun"][1])), 0.0)
				sun.shadow_enabled = true
				sun.directional_shadow_max_distance = QualityPresets.shadow_distance_m(preset)
				vp.add_child(sun)
				var mi := MeshInstance3D.new()
				mi.mesh = mesh
				mi.position = TerrainTiles.tile_origin("near", 0, 0)
				mi.material_override = bt.tile_material("near", 0, 0)
				vp.add_child(mi)
				var cam := Camera3D.new()
				cam.fov = 60.0
				cam.far = 6000.0
				vp.add_child(cam)
				cam.look_at_from_position(sc["cam"][0], sc["cam"][1])
				cam.current = true
				for i in SETTLE_FRAMES:
					await process_frame
				var name := "%s_%s%s" % [scene, "" if landscape != "" else "sans_", preset]
				var img := vp.get_texture().get_image()
				img.save_png(_out_dir.path_join(name + ".png"))
				var expo: Dictionary = _checks.exposure(img, name, Rect2(0.0, 0.3, 1.0, 0.7))
				var rid := vp.get_viewport_rid()
				var vis := RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE
				var tris := RenderingServer.viewport_get_render_info(rid, vis, RenderingServer.VIEWPORT_RENDER_INFO_PRIMITIVES_IN_FRAME)
				var draws := RenderingServer.viewport_get_render_info(rid, vis, RenderingServer.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME)
				csv.store_line("%s;%s;%s;%s;%d;%d;%.2f;%.3f" % [scene, landscape if landscape != "" else "-", preset, applied, tris, draws,
					expo["saturated_pct"], expo["luma"]])
				print("[vitrine_paysages] %s : %d triangles, %d appels de dessin, sol saturé %.1f %%, luminance %.2f" % [name,
					tris, draws, expo["saturated_pct"], expo["luma"]])
				vp.queue_free()
				await process_frame
	csv.close()
	quit(_checks.exit_code("vitrine_paysages"))
