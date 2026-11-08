extends SceneTree

## Rendu hors écran des saisons (lot P18, critère 4 du cahier) : un chêne (caduc) et un épicéa (persistant)
## dessinés par tree_sway.gdshader, puis une pente au-dessus de 1 000 m dessinée par terrain.gdshader, en été,
## en automne et en hiver (paramètres globaux posés par season_model.apply_globals).
## - été : image identique à celle des paramètres globaux par défaut (rendu d'aujourd'hui) ;
## - automne : feuillage du chêne majoritairement orangé (teinte moyenne) ;
## - hiver : feuillage du chêne absent, épicéa inchangé, terrain plus clair (neige plus bas).
## Variable SEASON_CAPTURE_DIR : y écrit les images, pour les captures à montrer.

const SeasonModel := preload("res://scripts/season_model.gd")
const TreeSpecies := preload("res://scripts/tree_species.gd")
const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const TerrainMaterial := preload("res://scripts/terrain_material.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")

const W := 320
const H := 240
const SKY := Color(0.62, 0.74, 0.88)

var _failures := 0
var _checked := 0
var _vp: SubViewport
var _oak: MeshInstance3D
var _spruce: MeshInstance3D
var _slope: MeshInstance3D
var _cam: Camera3D


func _init() -> void:
	call_deferred("_run")


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _tree(kind: String, x: float) -> MeshInstance3D:
	var built := TreeSpecies.build(kind)
	var mi := MeshInstance3D.new()
	mi.mesh = built["lod0"]
	var m := TreeRenderer.sway_material(false)
	m.set_shader_parameter("sway_height_m", float(built["height"]))
	m.set_shader_parameter("deciduous", TreeSpecies.is_deciduous(kind))
	mi.material_override = m
	mi.position = Vector3(x, 0.0, -30.0)
	_vp.add_child(mi)
	return mi


func _setup() -> void:
	_vp = SubViewport.new()
	_vp.size = Vector2i(W, H)
	_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	_vp.own_world_3d = true
	root.add_child(_vp)
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = SKY
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.55, 0.6, 0.7)
	env.ambient_light_energy = 0.6
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	var we := WorldEnvironment.new()
	we.environment = env
	_vp.add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-40.0, 30.0, 0.0)
	_vp.add_child(sun)
	_oak = _tree("oak", -7.0)
	_spruce = _tree("spruce", 7.0)
	# Pente douce entre 1 200 et 1 300 m (sous la limite de neige du thème, 2 200 m), loin derrière les arbres
	_slope = MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(400.0, 400.0)
	_slope.mesh = plane
	var theme: Dictionary = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)["theme"]
	_slope.material_override = TerrainMaterial.create_material(theme)
	_slope.visible = false
	_vp.add_child(_slope)
	_cam = Camera3D.new()
	_cam.fov = 50.0
	_vp.add_child(_cam)
	_cam.look_at_from_position(Vector3(0.0, 8.0, 0.0), Vector3(0.0, 8.0, -30.0))
	_cam.current = true


func _season(season: String, progress: float = 0.5) -> void:
	SeasonModel.apply_globals(SeasonModel.params(season, progress))


func _frame() -> Image:
	for i in 6:
		await process_frame
	return _vp.get_texture().get_image()


## Pixels de feuillage d'une moitié de l'image (ni ciel, ni écorce sombre) et leur teinte moyenne.
func _foliage(img: Image, left: bool) -> Dictionary:
	var n := 0
	var sum := Color(0, 0, 0)
	for y in range(0, H):
		for x in (range(0, W / 2) if left else range(W / 2, W)):
			var c := img.get_pixel(x, y)
			if Vector3(c.r - SKY.r, c.g - SKY.g, c.b - SKY.b).length() < 0.08:
				continue
			# Feuillage : vert (été) ou jaune à roux (automne), jamais l'écorce brune et sombre
			var leafy := (c.g > c.r and c.g > c.b) or (c.r > c.g * 1.15 and c.r > c.b * 1.6 and c.get_luminance() > 0.18)
			if leafy:
				n += 1
				sum += c
	return {"count": n, "mean": sum / maxf(n, 1)}


func _diff(a: Image, b: Image, left: bool) -> float:
	var d := 0.0
	for y in range(0, H):
		for x in (range(0, W / 2) if left else range(W / 2, W)):
			var ca := a.get_pixel(x, y)
			var cb := b.get_pixel(x, y)
			d += absf(ca.r - cb.r) + absf(ca.g - cb.g) + absf(ca.b - cb.b)
	return d / float(W / 2 * H)


func _save(img: Image, name: String) -> void:
	var dir := OS.get_environment("SEASON_CAPTURE_DIR")
	if dir != "":
		img.save_png(dir.path_join(name))


func _run() -> void:
	_setup()
	SeasonModel.apply_globals(SeasonModel.NEUTRAL)
	var base: Image = await _frame()
	_season("summer")
	var summer: Image = await _frame()
	_save(summer, "saison_ete.png")
	_check(_diff(base, summer, true) < 1e-4 and _diff(base, summer, false) < 1e-4, "été : image identique au rendu d'aujourd'hui")
	var f_summer := _foliage(summer, true)
	_check(f_summer["count"] > 2000, "été : feuillage du chêne dessiné (%d pixels)" % f_summer["count"])

	_season("autumn")
	var autumn: Image = await _frame()
	_save(autumn, "saison_automne.png")
	var f_autumn := _foliage(autumn, true)
	var m: Color = f_autumn["mean"]
	_check(m.r > m.g * 1.1 and m.g > m.b, "automne : chêne majoritairement orangé (teinte moyenne %.2f %.2f %.2f)" % [m.r, m.g, m.b])

	_season("winter")
	var winter: Image = await _frame()
	_save(winter, "saison_hiver.png")
	var f_winter := _foliage(winter, true)
	_check(f_winter["count"] < f_summer["count"] * 0.1, "hiver : feuillage du chêne absent (%d pixels contre %d l'été)" % [f_winter["count"], f_summer["count"]])
	_check(_diff(summer, winter, false) < 0.01, "hiver : épicéa inchangé (écart moyen %.4f)" % _diff(summer, winter, false))

	# Terrain à 1 250 m : neige seulement l'hiver
	_oak.visible = false
	_spruce.visible = false
	_slope.visible = true
	_slope.position = Vector3(0.0, 1250.0, -200.0)
	_cam.look_at_from_position(Vector3(0.0, 1290.0, 0.0), Vector3(0.0, 1250.0, -150.0))
	_season("summer")
	var t_summer: Image = await _frame()
	_season("winter")
	var t_winter: Image = await _frame()
	_save(t_winter, "saison_hiver_terrain.png")
	var lum_s := 0.0
	var lum_w := 0.0
	for y in range(H / 2, H):
		for x in range(W):
			lum_s += t_summer.get_pixel(x, y).get_luminance()
			lum_w += t_winter.get_pixel(x, y).get_luminance()
	_check(lum_w > lum_s * 1.3, "hiver : terrain à 1 250 m plus clair, sous la neige (%.3f contre %.3f)" % [lum_w / (W * H / 2), lum_s / (W * H / 2)])
	SeasonModel.apply_globals(SeasonModel.NEUTRAL)
	_vp.queue_free()
	await process_frame
	print("test_season_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
