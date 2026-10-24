extends RefCounted

## Réglages d'image (SRS §8, lot E1 §4.4) : caméra, ombres, SSAO, MSAA, brouillard.
##
## Préréglage `low` par défaut (PC cible, GTX 1060). `medium` et `high` sont provisoires.
## Le brouillard en profondeur masque la limite des tuiles lointaines ; sans couche terrain,
## il est plus dense et cache le bord du sol plat (format §10).
## Pas de class_name (charger par preload).

const WorldStreamer := preload("res://scripts/world_streamer.gd")

const DEFAULT_PRESET := "low"
const PRESET_LOW := {"shadow_max_distance_m": 150.0, "ssao": false, "msaa_3d": Viewport.MSAA_DISABLED}
const PRESET_MEDIUM := {"shadow_max_distance_m": 300.0, "ssao": false, "msaa_3d": Viewport.MSAA_2X}
const PRESET_HIGH := {"shadow_max_distance_m": 600.0, "ssao": true, "msaa_3d": Viewport.MSAA_4X}
const PRESETS := {"low": PRESET_LOW, "medium": PRESET_MEDIUM, "high": PRESET_HIGH}

const CAMERA_NEAR_M := 0.1
const CAMERA_FAR_M := WorldStreamer.FAR_RADIUS_M

## Brouillard en profondeur : début et fin (m), avec et sans terrain.
const FOG_TERRAIN := {"begin": 3000.0, "end": WorldStreamer.FAR_RADIUS_M}
const FOG_FLAT := {"begin": 300.0, "end": 3000.0}
const FOG_COLOR := Color(0.70, 0.78, 0.86)
const FOG_DEPTH_DENSITY := 1.0


static func apply_preset(preset_name: String, camera: Camera3D, light: DirectionalLight3D,
		env: Environment, viewport: Viewport) -> void:
	var preset: Dictionary = PRESETS.get(preset_name, PRESET_LOW)
	camera.near = CAMERA_NEAR_M
	camera.far = CAMERA_FAR_M
	light.shadow_enabled = true
	light.directional_shadow_max_distance = preset["shadow_max_distance_m"]
	env.ssao_enabled = preset["ssao"]
	viewport.msaa_3d = preset["msaa_3d"]


static func apply_fog(env: Environment, has_terrain: bool) -> void:
	var fog: Dictionary = FOG_TERRAIN if has_terrain else FOG_FLAT
	env.fog_enabled = true
	env.fog_mode = Environment.FOG_MODE_DEPTH
	env.fog_light_color = FOG_COLOR
	env.fog_depth_begin = fog["begin"]
	env.fog_depth_end = fog["end"]
	env.fog_depth_curve = 1.0
	# En mode profondeur, Godot 4.3 multiplie l'opacité par fog_density (0,01 par défaut) :
	# à 1, le brouillard couvre entièrement la limite du terrain (revue E2, R2 ; cahier E3 §4.2).
	env.fog_density = FOG_DEPTH_DENSITY
