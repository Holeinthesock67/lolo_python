extends SceneTree

## Tests sans écran de l'instanciation du shader triplanaire et du matériau de terrain (Lot E2).
## Lancement : godot --headless --path engine --script res://tests/unit/test_terrain_material.gd

const TerrainMaterial := preload("res://scripts/terrain_material.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Couleurs égales à un pas de quantification 8 bits près.
func _same(a: Color, b: Color) -> bool:
	return absf(a.r - b.r) <= 1.0 / 255.0 and absf(a.g - b.g) <= 1.0 / 255.0 and absf(a.b - b.b) <= 1.0 / 255.0


func _write_png(file_path: String, w: int, h: int) -> void:
	var dir_path := file_path.get_base_dir()
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(dir_path))
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	img.fill(Color(0.2, 0.7, 0.4, 1.0))
	img.save_png(ProjectSettings.globalize_path(file_path))


func _init() -> void:
	# 1. Matériau avec thème par défaut
	var default_mat: ShaderMaterial = TerrainMaterial.create_material()
	_check(default_mat != null, "matériau créé")
	_check(default_mat.shader != null, "shader assigné au matériau")

	var def_uniforms := ThemeRenderParams.terrain_uniforms({})
	_check(default_mat.get_shader_parameter("grass_color") == def_uniforms["grass_color"], "grass_color par défaut")
	_check(absf(float(default_mat.get_shader_parameter("grass_inv_scale")) - float(def_uniforms["grass_inv_scale"])) < 1e-6, "grass_inv_scale par défaut")
	_check(default_mat.get_shader_parameter("rock_color") == def_uniforms["rock_color"], "rock_color par défaut")
	_check(absf(float(default_mat.get_shader_parameter("rock_inv_scale")) - float(def_uniforms["rock_inv_scale"])) < 1e-6, "rock_inv_scale par défaut")
	_check(default_mat.get_shader_parameter("snow_color") == def_uniforms["snow_color"], "snow_color par défaut")
	_check(absf(float(default_mat.get_shader_parameter("snow_inv_scale")) - float(def_uniforms["snow_inv_scale"])) < 1e-6, "snow_inv_scale par défaut")
	_check(absf(float(default_mat.get_shader_parameter("slope_threshold_deg")) - 22.0) < 1e-6, "slope_threshold_deg par défaut = 22°")
	_check(absf(float(default_mat.get_shader_parameter("snow_line_m")) - 2200.0) < 1e-6, "snow_line_m par défaut = 2200 m")
	_check(absf(float(default_mat.get_shader_parameter("blend_sharpness")) - 4.0) < 1e-6, "blend_sharpness par défaut = 4.0")
	_check(bool(default_mat.get_shader_parameter("has_grass_texture")) == false, "has_grass_texture false sans texture")
	_check(bool(default_mat.get_shader_parameter("has_rock_texture")) == false, "has_rock_texture false sans texture")
	_check(bool(default_mat.get_shader_parameter("has_snow_texture")) == false, "has_snow_texture false sans texture")

	# 2. Thème personnalisé
	var custom_theme := {
		"terrain": {
			"grass": {"color": "#448822", "scale_m": 5.0},
			"rock": {"color": "#555555", "scale_m": 15.0},
			"snow": {"color": "#ffffff", "scale_m": 10.0},
			"slope_threshold_deg": 30.0,
			"snow_line_m": 2500.0,
			"blend_sharpness": 6.0,
		}
	}
	var custom_mat: ShaderMaterial = TerrainMaterial.create_material(custom_theme)
	_check(custom_mat.get_shader_parameter("grass_color") == Color.html("#448822"), "custom grass_color")
	_check(absf(float(custom_mat.get_shader_parameter("grass_inv_scale")) - 0.2) < 1e-6, "custom grass_inv_scale = 1/5")
	_check(custom_mat.get_shader_parameter("rock_color") == Color.html("#555555"), "custom rock_color")
	_check(absf(float(custom_mat.get_shader_parameter("rock_inv_scale")) - 1.0 / 15.0) < 1e-6, "custom rock_inv_scale = 1/15")
	_check(custom_mat.get_shader_parameter("snow_color") == Color.html("#ffffff"), "custom snow_color")
	_check(absf(float(custom_mat.get_shader_parameter("snow_inv_scale")) - 0.1) < 1e-6, "custom snow_inv_scale = 1/10")
	_check(absf(float(custom_mat.get_shader_parameter("slope_threshold_deg")) - 30.0) < 1e-6, "custom slope_threshold_deg = 30°")
	_check(absf(float(custom_mat.get_shader_parameter("snow_line_m")) - 2500.0) < 1e-6, "custom snow_line_m = 2500 m")
	_check(absf(float(custom_mat.get_shader_parameter("blend_sharpness")) - 6.0) < 1e-6, "custom blend_sharpness = 6.0")

	# 3. Thème avec texture réelle
	var tmp_dir := "user://test_terrain_mat"
	_write_png(tmp_dir.path_join("textures/grass.png"), 8, 8)
	var theme_with_tex := {
		"version": "1.0",
		"terrain": {
			"grass": {"texture": "textures/grass.png", "color": "#6f9a4a", "scale_m": 6.0},
			"rock": {"texture": null, "color": "#9a9488", "scale_m": 12.0},
			"snow": {"texture": null, "color": "#f2f5f8", "scale_m": 8.0},
		}
	}
	var tex_mat: ShaderMaterial = TerrainMaterial.create_material(theme_with_tex, tmp_dir)
	_check(bool(tex_mat.get_shader_parameter("has_grass_texture")) == true, "has_grass_texture true avec texture valide")
	_check(tex_mat.get_shader_parameter("grass_texture") is Texture2D, "grass_texture est une Texture2D")
	_check(bool(tex_mat.get_shader_parameter("has_rock_texture")) == false, "has_rock_texture false car texture null")
	_check(bool(tex_mat.get_shader_parameter("has_snow_texture")) == false, "has_snow_texture false car texture null")

	# 4. Mise à jour dynamique d'un matériau existant
	TerrainMaterial.apply_to_material(default_mat, custom_theme)
	_check(absf(float(default_mat.get_shader_parameter("slope_threshold_deg")) - 30.0) < 1e-6, "apply_to_material met à jour le matériau")

	# 5. Attachement à un maillage de test (sans écran, le shader n'est pas compilé : voir tests/render/)
	var mi := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.material = tex_mat
	mi.mesh = plane
	_check(mi.mesh.surface_get_material(0) == tex_mat, "matériau attaché à un maillage")
	mi.free()

	# 6. Constantes de la fonction de référence (L3) transmises au shader, sans copie à la main
	var l3 := {
		"snow_melt_band_m": ThemeRenderParams.SNOW_MELT_BAND_M,
		"steep_snow_start_deg": ThemeRenderParams.STEEP_SNOW_START_DEG,
		"steep_snow_max_deg": ThemeRenderParams.STEEP_SNOW_MAX_DEG,
		"min_slope_half_band_deg": ThemeRenderParams.MIN_SLOPE_HALF_BAND_DEG,
		"max_slope_half_band_deg": ThemeRenderParams.MAX_SLOPE_HALF_BAND_DEG,
	}
	var code: String = default_mat.shader.code
	for key in l3:
		_check(absf(float(default_mat.get_shader_parameter(key)) - float(l3[key])) < 1e-6, "%s = %s (L3)" % [key, l3[key]])
		_check(code.contains("uniform float %s" % key), "uniform %s déclaré dans le shader" % key)
	_check(code.contains("12.0 / max(blend_sharpness, 1.0)"), "demi-bande de pente : 12 / blend_sharpness, comme blend_weights")
	var frag := code.substr(code.find("void fragment()"))
	var literal_ok := true
	for lit in ["44.0", "50.0", "1.5", "3.0"]:
		if frag.contains(lit):
			literal_ok = false
	_check(literal_ok, "aucune constante de L3 écrite en dur dans fragment()")

	# 7. Route : la ligne médiane reste peinte sur une texture de thème
	var road_tex_color := Color(0.2, 0.25, 0.3)
	var road_img := Image.create(128, 128, false, Image.FORMAT_RGB8)
	road_img.fill(road_tex_color)
	var out_img := RoadBuilder.road_image(RoadBuilder.ROAD_COLOR, road_img)
	_check(_same(out_img.get_pixel(64, 10), RoadBuilder.LINE_COLOR), "ligne médiane peinte sur la texture de route")
	_check(_same(out_img.get_pixel(64, 100), road_tex_color), "pas de ligne sur la moitié basse (3 m vides)")
	_check(_same(out_img.get_pixel(20, 10), road_tex_color), "texture du thème conservée hors de la ligne")
	_check(_same(road_img.get_pixel(64, 10), road_tex_color), "image du thème non modifiée (copie)")
	_check(RoadBuilder.make_material(RoadBuilder.ROAD_COLOR, ImageTexture.create_from_image(road_img)).albedo_texture != null,
		"matériau de route créé avec une texture de thème")
	var plain_img := RoadBuilder.road_image(Color(0.4, 0.1, 0.1))
	_check(_same(plain_img.get_pixel(5, 5), Color(0.4, 0.1, 0.1)) and _same(plain_img.get_pixel(32, 5), RoadBuilder.LINE_COLOR),
		"sans texture : couleur du thème et ligne médiane")

	# 8. Tuiles de terrain sans couleur de sommet (le shader ne la lit pas)
	var flat_arrays := TerrainTiles.build_arrays(TerrainTiles.flat_heights(1000.0), "near")
	_check(flat_arrays[Mesh.ARRAY_COLOR] == null, "tuile sans ARRAY_COLOR")

	print("test_terrain_material : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
