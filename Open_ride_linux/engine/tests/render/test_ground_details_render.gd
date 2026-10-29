extends SceneTree

## Rendu hors écran du relief du sable (lot U8, terrain_biomes.gdshader), éclairé (le relief ne change que
## la normale), même principe que test_terrain_biomes_render.gd :
##   xvfb-run -a godot --path engine --rendering-driver opengl3 --rendering-method gl_compatibility \
##     --audio-driver Dummy --script res://tests/render/test_ground_details_render.gd
## 1. Prairie tempérée : image identique avec et sans le relief du sable (critère 3 : pas de rides hors du sable).
## 2. Désert de sable : le relief change l'image (rides et dunes visibles sous un soleil rasant).

const BiomeTextures := preload("res://scripts/biome_textures.gd")
const BiomeModel := preload("res://scripts/biome_model.gd")
const BiomeLayer := preload("res://scripts/biome_layer.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")

const SIZE := 128
const TILE_M := 1000.0

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


## Vue de 3/4 sur une tuile plate de `biome`, soleil rasant ; `relief` faux : biome_rule.w mis à 0 partout.
func _shot(theme: Dictionary, biome: String, relief: bool) -> Image:
	var model := BiomeModel.new(theme, BiomeLayer.new())
	model.set_forced(biome)
	var bt := BiomeTextures.new(model, "", "medium")
	if not relief:
		var rules: Array = bt.material.get_shader_parameter("biome_rule")
		var flat := []
		for r in rules:
			flat.append(Vector4(r.x, r.y, r.z, 0.0))
		bt.material.set_shader_parameter("biome_rule", flat)
	var vp := SubViewport.new()
	vp.size = Vector2i(SIZE, SIZE)
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.own_world_3d = true
	root.add_child(vp)
	var mi := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(TILE_M, TILE_M)
	mi.mesh = plane
	mi.position = Vector3(TILE_M / 2.0, 0.0, TILE_M / 2.0)
	mi.material_override = bt.tile_material("near", 0, 0)
	vp.add_child(mi)
	var sun := DirectionalLight3D.new()
	vp.add_child(sun)
	sun.rotation = Vector3(deg_to_rad(-12.0), deg_to_rad(-90.0), 0.0)
	var cam := Camera3D.new()
	vp.add_child(cam)
	cam.position = Vector3(500.0, 6.0, 520.0)
	cam.rotation = Vector3(deg_to_rad(-25.0), 0.0, 0.0)
	cam.current = true
	for i in 5:
		await process_frame
	var img := vp.get_texture().get_image()
	vp.queue_free()
	await process_frame
	return img


func _diff(a: Image, b: Image) -> float:
	var worst := 0.0
	for y in range(a.get_height()):
		for x in range(a.get_width()):
			var p := a.get_pixel(x, y)
			var q := b.get_pixel(x, y)
			worst = maxf(worst, maxf(maxf(absf(p.r - q.r), absf(p.g - q.g)), absf(p.b - q.b)))
	return worst


func _run() -> void:
	var theme: Dictionary = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)["theme"]
	var g_on := await _shot(theme, "temperate_grassland", true)
	var g_off := await _shot(theme, "temperate_grassland", false)
	_check(g_on.get_data() == g_off.get_data(), "prairie tempérée : image identique avec et sans le relief du sable (écart %.4f)" % _diff(g_on, g_off))
	var s_on := await _shot(theme, "sand_desert", true)
	var s_off := await _shot(theme, "sand_desert", false)
	var d := _diff(s_on, s_off)
	_check(d > 0.02, "désert de sable : le relief change l'image (écart au pire %.1f %%)" % (100.0 * d))
	print("test_ground_details_render : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
