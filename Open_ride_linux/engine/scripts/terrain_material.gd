extends RefCounted

## Création et mise à jour du ShaderMaterial triplanaire du terrain (Lot E2, SRS §8.1).
## Pas de class_name : charger par preload("res://scripts/terrain_material.gd").

const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const TERRAIN_SHADER := preload("res://shaders/terrain.gdshader")


## Crée un nouveau ShaderMaterial configuré selon le thème et son dossier.
static func create_material(theme: Dictionary = {}, theme_dir: String = "") -> ShaderMaterial:
	var mat := ShaderMaterial.new()
	mat.shader = TERRAIN_SHADER
	apply_to_material(mat, theme, theme_dir)
	return mat


## Applique les paramètres du thème au ShaderMaterial donné.
static func apply_to_material(mat: ShaderMaterial, theme: Dictionary = {}, theme_dir: String = "") -> void:
	if mat == null or mat.shader == null:
		return

	var uniforms := ThemeRenderParams.terrain_uniforms(theme)

	mat.set_shader_parameter("grass_color", uniforms["grass_color"])
	mat.set_shader_parameter("grass_inv_scale", uniforms["grass_inv_scale"])
	mat.set_shader_parameter("rock_color", uniforms["rock_color"])
	mat.set_shader_parameter("rock_inv_scale", uniforms["rock_inv_scale"])
	mat.set_shader_parameter("snow_color", uniforms["snow_color"])
	mat.set_shader_parameter("snow_inv_scale", uniforms["snow_inv_scale"])
	mat.set_shader_parameter("slope_threshold_deg", uniforms["slope_threshold_deg"])
	mat.set_shader_parameter("snow_line_m", uniforms["snow_line_m"])
	mat.set_shader_parameter("blend_sharpness", uniforms["blend_sharpness"])
	# Constantes de la fonction de référence du lot L3 (le shader n'en recopie aucune).
	mat.set_shader_parameter("snow_melt_band_m", ThemeRenderParams.SNOW_MELT_BAND_M)
	mat.set_shader_parameter("steep_snow_start_deg", ThemeRenderParams.STEEP_SNOW_START_DEG)
	mat.set_shader_parameter("steep_snow_max_deg", ThemeRenderParams.STEEP_SNOW_MAX_DEG)
	mat.set_shader_parameter("min_slope_half_band_deg", ThemeRenderParams.MIN_SLOPE_HALF_BAND_DEG)
	mat.set_shader_parameter("max_slope_half_band_deg", ThemeRenderParams.MAX_SLOPE_HALF_BAND_DEG)

	var tex_grass: Texture2D = null
	var tex_rock: Texture2D = null
	var tex_snow: Texture2D = null

	if theme_dir != "":
		tex_grass = ThemeLoader.texture_for(theme, theme_dir, "terrain.grass")
		tex_rock = ThemeLoader.texture_for(theme, theme_dir, "terrain.rock")
		tex_snow = ThemeLoader.texture_for(theme, theme_dir, "terrain.snow")

	if tex_grass != null:
		mat.set_shader_parameter("grass_texture", tex_grass)
		mat.set_shader_parameter("has_grass_texture", true)
	else:
		mat.set_shader_parameter("has_grass_texture", false)

	if tex_rock != null:
		mat.set_shader_parameter("rock_texture", tex_rock)
		mat.set_shader_parameter("has_rock_texture", true)
	else:
		mat.set_shader_parameter("has_rock_texture", false)

	if tex_snow != null:
		mat.set_shader_parameter("snow_texture", tex_snow)
		mat.set_shader_parameter("has_snow_texture", true)
	else:
		mat.set_shader_parameter("has_snow_texture", false)
