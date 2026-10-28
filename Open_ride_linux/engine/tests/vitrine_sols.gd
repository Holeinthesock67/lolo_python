extends SceneTree

## Vitrine du sol multi-biome (lot U6) : pour chaque paire de biomes, deux tuiles proches de 1 km avec un
## relief de collines (de 240 à 420 m, pentes douces et quelques versants raides) ; la première tuile passe de son biome au mélange
## à 50 % sur ses 250 derniers mètres, la seconde du mélange à son biome. Vue aérienne oblique du bord commun,
## éclairée, avec le thème par défaut 2.0. Sans core ni parcours ; captures comparables d'une paire à l'autre.
##
##   xvfb-run -a $GODOT --path engine --rendering-driver opengl3 --rendering-method gl_compatibility \
##     --audio-driver Dummy --script res://tests/vitrine_sols.gd -- --out DOSSIER \
##     [--quality low,medium,high] [--size 1680x1050] [--compare REF] [--max-diff 3] [--max-saturated 5]
##
## Écrit DOSSIER/<biome1>__<biome2>_<préréglage>.png et DOSSIER/vitrine_sols.csv (paire ; préréglage ;
## triangles ; appels de dessin ; préparation du matériau en ms ; part de pixels saturés du sol en % ;
## luminance moyenne du sol). Contrôles automatiques (vitrine_checks.gd) : exposition du sol, et comparaison
## à des captures de référence avec --compare ; code de sortie 1 si l'un échoue.

const BiomeModel := preload("res://scripts/biome_model.gd")
const BiomeLayer := preload("res://scripts/biome_layer.gd")
const BiomeTextures := preload("res://scripts/biome_textures.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const RenderQuality := preload("res://scripts/render_quality.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const VitrineChecks := preload("res://tests/vitrine_checks.gd")

const PAIRS := [
	["temperate_grassland", "mediterranean"], ["farmland", "temperate_forest"], ["boreal_forest", "tundra"],
	["alpine", "polar"], ["steppe", "savanna"], ["sand_desert", "rock_desert"], ["jungle", "wetland"],
	["coast", "volcanic"],
]
const SETTLE_FRAMES := 12

var _out_dir := "user://vitrine_sols"
var _presets: Array = ["low"]
var _size := Vector2i(1280, 720)
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
			"--size":
				var wh: PackedStringArray = args[i + 1].split("x")
				_size = Vector2i(int(wh[0]), int(wh[1]))
	call_deferred("_run")


## Collines : altitude au point (x, z) du monde.
static func _height(x: float, z: float) -> float:
	return 330.0 + 70.0 * sin(x / 260.0) * cos(z / 300.0) + 14.0 * sin((x + 2.0 * z) / 150.0) + 4.0 * sin(x / 41.0 + z / 57.0)


func _tile_heights(ix: int) -> PackedFloat32Array:
	var h := PackedFloat32Array()
	h.resize(TerrainTiles.SAMPLES * TerrainTiles.SAMPLES)
	var cell: float = TerrainTiles.LEVELS["near"]["cell"]
	for j in range(TerrainTiles.SAMPLES):
		for i in range(TerrainTiles.SAMPLES):
			h[j * TerrainTiles.SAMPLES + i] = _height(ix * 1000.0 + i * cell, j * cell)
	return h


## Valeurs juste au-delà des bords (comme load_neighbour_edges) : normales continues d'une tuile à l'autre.
func _edges(ix: int) -> Dictionary:
	var cell: float = TerrainTiles.LEVELS["near"]["cell"]
	var out := {"west": PackedFloat32Array(), "east": PackedFloat32Array(), "north": PackedFloat32Array(), "south": PackedFloat32Array()}
	for k in range(TerrainTiles.SAMPLES):
		out["west"].append(_height(ix * 1000.0 - cell, k * cell))
		out["east"].append(_height((ix + 1) * 1000.0 + cell, k * cell))
		out["north"].append(_height(ix * 1000.0 + k * cell, -cell))
		out["south"].append(_height(ix * 1000.0 + k * cell, 1000.0 + cell))
	return out


func _grid(f: Callable) -> PackedFloat32Array:
	var g := PackedFloat32Array()
	g.resize(BiomeLayer.POINTS)
	for j in range(BiomeLayer.GRID):
		for i in range(BiomeLayer.GRID):
			g[j * BiomeLayer.GRID + i] = f.call(i)
	return g


func _tile(a: String, b: String, wa: Callable) -> Dictionary:
	var names: Array[String] = [a, b]
	var grids: Array[PackedFloat32Array] = [_grid(wa), _grid(func(i): return 1.0 - wa.call(i))]
	return {"biomes": names, "weights": grids, "variant": null}


func _run() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(_out_dir))
	var theme: Dictionary = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)["theme"]
	var csv := FileAccess.open(_out_dir.path_join("vitrine_sols.csv"), FileAccess.WRITE)
	csv.store_line("paire;preset;triangles;appels_dessin;materiau_ms;sol_sature_pct;sol_luminance")
	var meshes := []
	for ix in [0, 1]:
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, TerrainTiles.build_arrays(_tile_heights(ix), "near", _edges(ix)))
		meshes.append(mesh)
	for preset in _presets:
		for pair in PAIRS:
			var layer := BiomeLayer.new()
			layer.put_tile("near", 0, 0, _tile(pair[0], pair[1], func(i): return 1.0 if i <= 12 else 1.0 - float(i - 12) / 8.0))
			layer.put_tile("near", 1, 0, _tile(pair[0], pair[1], func(i): return 0.5 - float(i) / 8.0 if i < 4 else 0.0))
			var model := BiomeModel.new(theme, layer)
			var t0 := Time.get_ticks_usec()
			var bt := BiomeTextures.new(model, ThemeLoader.DEFAULT_THEME_DIR, preset)
			var mat_ms := (Time.get_ticks_usec() - t0) / 1000.0

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
			RenderQuality.apply_fog(env, preset, true, RenderQuality.FOG_COLOR, 0.0)
			env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
			env.tonemap_white = 6.0
			var we := WorldEnvironment.new()
			we.environment = env
			vp.add_child(we)
			var sun := DirectionalLight3D.new()
			sun.rotation = Vector3(deg_to_rad(-40.0), deg_to_rad(-30.0), 0.0)
			sun.shadow_enabled = true
			sun.directional_shadow_max_distance = QualityPresets.shadow_distance_m(preset)
			vp.add_child(sun)
			for ix in [0, 1]:
				var mi := MeshInstance3D.new()
				mi.mesh = meshes[ix]
				mi.position = TerrainTiles.tile_origin("near", ix, 0)
				mi.material_override = bt.tile_material("near", ix, 0)
				vp.add_child(mi)
			var cam := Camera3D.new()
			cam.fov = 60.0
			cam.far = 6000.0
			vp.add_child(cam)
			cam.look_at_from_position(Vector3(1000.0, 650.0, 1250.0), Vector3(1000.0, 330.0, 420.0))
			cam.current = true
			for i in SETTLE_FRAMES:
				await process_frame
			var name := "%s__%s_%s" % [pair[0], pair[1], preset]
			var img := vp.get_texture().get_image()
			img.save_png(_out_dir.path_join(name + ".png"))
			# Sol : toute l'image sous l'horizon de la vue aérienne
			var expo: Dictionary = _checks.exposure(img, name, Rect2(0.0, 0.3, 1.0, 0.7))
			var rid := vp.get_viewport_rid()
			var vis := RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE
			var tris := RenderingServer.viewport_get_render_info(rid, vis, RenderingServer.VIEWPORT_RENDER_INFO_PRIMITIVES_IN_FRAME)
			var draws := RenderingServer.viewport_get_render_info(rid, vis, RenderingServer.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME)
			csv.store_line("%s|%s;%s;%d;%d;%.1f;%.2f;%.3f" % [pair[0], pair[1], preset, tris, draws, mat_ms, expo["saturated_pct"], expo["luma"]])
			print("[vitrine_sols] %s : %d triangles, %d appels de dessin, matériau %.1f ms, sol saturé %.1f %%, luminance %.2f" % [name,
				tris, draws, mat_ms, expo["saturated_pct"], expo["luma"]])
			vp.queue_free()
			await process_frame
	csv.close()
	_checks.compare(_out_dir)
	quit(_checks.exit_code("vitrine_sols"))
