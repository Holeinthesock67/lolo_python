extends GPUParticles3D

## Lucioles des nuits douces (lot P35, 13 novembre : « ajoute des éléments lumineux pour ajouter de la vie ») :
## petits points vert-jaune qui s'allument et s'éteignent en flottant au ras de l'herbe autour du cycliste.
## Seulement la nuit (NightLights.current), hors hiver, sans pluie, et pas dans les biomes secs ou froids ;
## AMOUNT_BY_PRESET (aucune en `low`). Un seul nœud de particules (un appel de dessin), caché sinon.
## - `set_preset(name)` ; `update(cam_pos, season, rain, biome)` une fois par image.
## Pas de class_name : charger par preload("res://scripts/fireflies.gd").

const NightLights := preload("res://scripts/night_lights.gd")

const AMOUNT_BY_PRESET := {"low": 0, "medium": 60, "high": 120}
const SEASONS := ["spring", "summer", "wet", "none"]
const NO_BIOMES := ["polar", "tundra", "sand_desert", "rock_desert", "alpine", "volcanic"]
const AREA_M := Vector3(22.0, 1.2, 22.0)
const COLOR := Color(0.75, 1.0, 0.35)

var _amount := 0


func _init() -> void:
	name = "Fireflies"
	local_coords = false
	lifetime = 5.0
	preprocess = 5.0
	explosiveness = 0.0
	randomness = 1.0
	visibility_aabb = AABB(-AREA_M * 2.0, AREA_M * 4.0)
	cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var pm := ParticleProcessMaterial.new()
	pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	pm.emission_box_extents = AREA_M
	pm.gravity = Vector3.ZERO
	pm.direction = Vector3(0, 1, 0)
	pm.spread = 180.0
	pm.initial_velocity_min = 0.1
	pm.initial_velocity_max = 0.4
	pm.turbulence_enabled = true
	pm.turbulence_noise_strength = 0.6
	pm.turbulence_noise_scale = 3.0
	# Allumage et extinction lents : alpha 0 → 1 → 0 sur la vie de la luciole
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.25, 0.5, 0.75, 1.0])
	g.colors = PackedColorArray([Color(1, 1, 1, 0), Color(1, 1, 1, 1), Color(1, 1, 1, 0.15), Color(1, 1, 1, 1), Color(1, 1, 1, 0)])
	var gt := GradientTexture1D.new()
	gt.gradient = g
	pm.color_ramp = gt
	process_material = pm
	var dot := SphereMesh.new()
	dot.radius = 0.035
	dot.height = 0.07
	dot.radial_segments = 6
	dot.rings = 3
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.vertex_color_use_as_albedo = true
	m.vertex_color_is_srgb = true
	m.albedo_color = COLOR
	m.emission_enabled = true
	m.emission = COLOR
	m.emission_energy_multiplier = 3.0
	m.disable_fog = true
	dot.material = m
	draw_pass_1 = dot
	emitting = false
	visible = false


func set_preset(preset_name: String) -> void:
	_amount = int(AMOUNT_BY_PRESET.get(preset_name, 0))
	if _amount > 0:
		amount = _amount


static func wanted(night: float, season: String, rain: float, biome: String) -> bool:
	return night > 0.6 and season in SEASONS and rain < 0.1 and not biome in NO_BIOMES


func update(cam_pos: Vector3, season: String, rain: float, biome: String = "") -> void:
	var on := _amount > 0 and wanted(NightLights.current, season, rain, biome)
	if on != emitting:
		emitting = on
		visible = on
	if on:
		global_position = cam_pos + Vector3(0.0, -0.6, 0.0)
