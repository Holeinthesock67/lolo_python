extends RefCounted

## Fabrique des matériaux du mode Cyber-Rogue (lot R17 §4.2) : un seul matériau par jeton, sorte et
## préréglage, mis en cache. Aucune texture : tout vient des shaders de `res://scripts/rogue/`.
## Pas de class_name : preload("res://scripts/rogue/neon_materials.gd").

const Palette := preload("res://scripts/rogue/neon_palette.gd")

const EDGE_SHADER := preload("res://scripts/rogue/neon_edge.gdshader")
const GRID_SHADER := preload("res://scripts/rogue/neon_grid.gdshader")
const HOLOGRAM_SHADER := preload("res://scripts/rogue/hologram.gdshader")
const GLITCH_SHADER := preload("res://scripts/rogue/glitch.gdshader")
const WALL_SHADER := preload("res://scripts/rogue/energy_wall.gdshader")

static var _cache: Dictionary = {}


static func clear_cache() -> void:
	_cache.clear()


static func cache_size() -> int:
	return _cache.size()


static func _key(kind: String, token: String, preset: String, adapted: bool, extra: String) -> String:
	return "%s|%s|%s|%s|%s" % [kind, token, preset, str(adapted), extra]


static func _new(shader: Shader) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = shader
	return m


## Volume sombre à arêtes lumineuses (`width` : épaisseur de l'arête en pixels).
static func edge(token: String, width: float = 2.0, preset: String = "low", adapted: bool = false) -> ShaderMaterial:
	var key := _key("edge", token, preset, adapted, str(width))
	if not _cache.has(key):
		var m := _new(EDGE_SHADER)
		m.set_shader_parameter("body_color", Palette.body_color())
		m.set_shader_parameter("line_color", Palette.glow_color(token, preset, adapted))
		m.set_shader_parameter("width_px", width)
		_cache[key] = m
	return _cache[key]


## Panneau de verre teinté et translucide (portes, cartes) : sans balayage ni scintillement.
static func glass(token: String, alpha: float = 0.25, preset: String = "low", adapted: bool = false) -> ShaderMaterial:
	var key := _key("glass", token, preset, adapted, str(alpha))
	if not _cache.has(key):
		var m := _new(HOLOGRAM_SHADER)
		m.set_shader_parameter("tint", Palette.glow_color(token, preset, adapted))
		m.set_shader_parameter("base_alpha", alpha)
		m.set_shader_parameter("scan_strength", 0.0)
		m.set_shader_parameter("flicker", 0.0)
		_cache[key] = m
	return _cache[key]


## Hologramme : lignes de balayage fines et scintillement léger (HUD de R11, cartes, portes).
static func hologram(token: String, preset: String = "low", adapted: bool = false) -> ShaderMaterial:
	var key := _key("hologram", token, preset, adapted, "")
	if not _cache.has(key):
		var m := _new(HOLOGRAM_SHADER)
		m.set_shader_parameter("tint", Palette.glow_color(token, preset, adapted))
		_cache[key] = m
	return _cache[key]


## Mur de lumière translucide et ondulant (Firewall, traînées, mur du Puncheur).
static func wall(token: String, preset: String = "low", adapted: bool = false) -> ShaderMaterial:
	var key := _key("wall", token, preset, adapted, "")
	if not _cache.has(key):
		var m := _new(WALL_SHADER)
		m.set_shader_parameter("tint", Palette.glow_color(token, preset, adapted))
		_cache[key] = m
	return _cache[key]


## Grille infinie au sol (jeton `grid`), à poser sur un grand plan.
static func grid(preset: String = "low", adapted: bool = false) -> ShaderMaterial:
	var key := _key("grid", "grid", preset, adapted, "")
	if not _cache.has(key):
		var m := _new(GRID_SHADER)
		var c := Palette.color("grid", adapted)
		m.set_shader_parameter("line_color", Color(c.r, c.g, c.b, 1.0))
		m.set_shader_parameter("line_intensity", Palette.GRID_INTENSITY * Palette.INTENSITY.get(preset, 1.6))
		_cache[key] = m
	return _cache[key]


## Bandes décalées et couleurs séparées, à poser sur un `ColorRect` plein écran (`intensity` de 0 à 1).
static func glitch(intensity: float = 0.0) -> ShaderMaterial:
	var m := _new(GLITCH_SHADER)
	m.set_shader_parameter("intensity", clampf(intensity, 0.0, 1.0))
	return m
