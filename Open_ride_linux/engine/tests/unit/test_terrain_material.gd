extends SceneTree

## Tests sans écran de l'instanciation du shader triplanaire et du matériau de terrain (Lot E2).
## Lancement : godot --headless --path engine --script res://tests/unit/test_terrain_material.gd

const TerrainMaterial := preload("res://scripts/terrain_material.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


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

	# 5. Attachement à un maillage de test et compilation sans erreur
	var mi := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.material = tex_mat
	mi.mesh = plane
	_check(mi.mesh.surface_get_material(0) == tex_mat, "matériau attaché avec succès à un maillage")
	mi.free()

	print("test_terrain_material : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
