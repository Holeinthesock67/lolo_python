extends SceneTree

## Rendu hors écran des forêts lointaines en imposteurs (lot Y5, shaders/tree_impostor.gdshader) : sur un sol
## plat, des bouquets de la forêt tempérée entre 1,5 km et la fin du brouillard du préréglage medium.
## Vérifie que des houppiers verts sont dessinés sur la ligne d'horizon, et que rien n'est dessiné plus près
## que le début des imposteurs ni au-delà de leur fin (distances coupées dans le shader, par instance).
## Variable FOREST_CAPTURE_DIR : y écrit les images (téléobjectif et champ du jeu), pour les captures à montrer.

const RenderExit := preload("res://tests/render/render_exit.gd")

const ForestImpostors := preload("res://scripts/forest_impostors.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const BiomeModel := preload("res://scripts/biome_model.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")

const W := 640
const H := 360
const GROUND_Y := 300.0
const SKY := Color(0.62, 0.74, 0.88)
const GROUND := Color(0.46, 0.36, 0.30)   # brun : jamais compté comme houppier

var _failures := 0
var _checked := 0


func _init() -> void:
	call_deferred("_run")


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _scene(forest: Node3D, fov: float) -> Array:
	var vp := SubViewport.new()
	vp.size = Vector2i(W, H)
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.own_world_3d = true
	root.add_child(vp)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = SKY
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.55, 0.6, 0.7)
	env.ambient_light_energy = 0.6
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	var we := WorldEnvironment.new()
	we.environment = env
	vp.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-40.0, 30.0, 0.0)
	sun.light_energy = 1.0
	vp.add_child(sun)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(30000.0, 30000.0)
	ground.mesh = plane
	var gm := StandardMaterial3D.new()
	gm.albedo_color = GROUND
	gm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	ground.material_override = gm
	ground.position = Vector3(0.0, GROUND_Y - TerrainTiles.FAR_DROP_M, 0.0)
	vp.add_child(ground)
	vp.add_child(forest)
	var cam := Camera3D.new()
	cam.fov = fov
	cam.far = 12000.0
	vp.add_child(cam)
	cam.look_at_from_position(Vector3(0.0, GROUND_Y + 3.0, 0.0), Vector3(0.0, GROUND_Y + 3.0 - 60.0, -3000.0))
	cam.current = true
	return [vp, cam]


## Pixels de la bande autour de l'horizon dont la couleur n'est ni celle du ciel ni celle du sol, et plus verte.
func _forest_pixels(img: Image, cam: Camera3D) -> int:
	var y_far := int(cam.unproject_position(Vector3(0.0, GROUND_Y, -5500.0)).y)
	var y_near := int(cam.unproject_position(Vector3(0.0, GROUND_Y, -1500.0)).y)
	var top := clampi(y_far - 40, 0, H - 1)
	var bottom := clampi(y_near + 2, 0, H - 1)
	var n := 0
	for y in range(top, bottom + 1):
		for x in range(W):
			var c := img.get_pixel(x, y)
			var sky_d := Vector3(c.r - SKY.r, c.g - SKY.g, c.b - SKY.b).length()
			if sky_d > 0.12 and c.g > c.b and c.g >= c.r * 0.95 and c.get_luminance() < 0.5:
				n += 1
	return n


func _run() -> void:
	var theme: Dictionary = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)["theme"]
	var forest = ForestImpostors.new()
	forest.biome_model = BiomeModel.new(theme, null)
	forest.biome_model.set_forced("temperate_forest")
	forest.set_preset("medium")
	var flat := TerrainTiles.flat_heights(GROUND_Y)
	for tx in [-1, 0]:
		for tz in [-2, -1]:
			forest.add_tile(forest.prepare_tile(tx, tz, flat, null, theme))
	print("Bouquets affichés : ", forest.get_count())
	var capture_dir := OS.get_environment("FOREST_CAPTURE_DIR")

	# 1. Téléobjectif (20°) : houppiers sur l'horizon
	var s: Array = _scene(forest, 20.0)
	var vp: SubViewport = s[0]
	var cam: Camera3D = s[1]
	for i in 8:
		await process_frame
	var img := vp.get_texture().get_image()
	var drawn := _forest_pixels(img, cam)
	_check(drawn > W * 4, "forêt dessinée sur l'horizon (%d pixels de houppiers)" % drawn)
	if capture_dir != "":
		img.save_png(capture_dir.path_join("foret_teleobjectif.png"))

	# 2. Champ du jeu (70°), pour la capture
	cam.fov = 70.0
	for i in 4:
		await process_frame
	if capture_dir != "":
		vp.get_texture().get_image().save_png(capture_dir.path_join("foret_champ_jeu.png"))

	# 3. Début des imposteurs au-delà de toute la forêt : rien n'est dessiné
	cam.fov = 20.0
	forest.get_material().set_shader_parameter("begin_m", 20000.0)
	for i in 4:
		await process_frame
	var none := _forest_pixels(vp.get_texture().get_image(), cam)
	_check(none < W / 8, "plus près que le début des imposteurs : aucun bouquet (%d pixels)" % none)
	forest.get_material().set_shader_parameter("begin_m", ForestImpostors.BEGIN_M)

	# 4. Fin avant le début (au-delà de la fin, plus rien) : aucun bouquet
	forest.get_material().set_shader_parameter("end_m", 1000.0)
	for i in 4:
		await process_frame
	var beyond := _forest_pixels(vp.get_texture().get_image(), cam)
	_check(beyond < W / 8, "au-delà de la fin des imposteurs : aucun bouquet (%d pixels)" % beyond)
	vp.queue_free()
	await process_frame
	await RenderExit.settle(self)   # sortie en ordre (render_exit.gd)
	print("test_forest_impostor_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
