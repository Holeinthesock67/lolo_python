extends RefCounted

## Réglages d'image (SRS §8, lots E1, L4 et E3) : caméra, ombres, SSAO, MSAA, brouillard, tronçons.
##
## Applique les réglages de quality_presets.gd sur la caméra, la lumière, l'environnement, le viewport
## et le streamer. La table interne d'E1 est supprimée au profit de quality_presets.gd.
## Pas de class_name (charger par preload).

const QualityPresets := preload("res://scripts/quality_presets.gd")
const WorldStreamer := preload("res://scripts/world_streamer.gd")

const DEFAULT_PRESET := QualityPresets.DEFAULT_PRESET

const CAMERA_NEAR_M := 0.1
const CAMERA_FAR_M := WorldStreamer.FAR_RADIUS_M

## Brouillard en profondeur : début et fin (m), avec et sans terrain.
const FOG_TERRAIN := {"begin": 3000.0, "end": WorldStreamer.FAR_RADIUS_M}
const FOG_FLAT := {"begin": 300.0, "end": 3000.0}
const FOG_COLOR := Color(0.70, 0.78, 0.86)


static func apply_preset(preset_name: String, camera: Camera3D, light: DirectionalLight3D,
		env: Environment, viewport: Viewport, streamer: Variant = null) -> void:
	var key := preset_name.strip_edges()
	var p: Dictionary = QualityPresets.preset(key)
	camera.near = CAMERA_NEAR_M
	camera.far = CAMERA_FAR_M
	light.shadow_enabled = true
	light.directional_shadow_max_distance = QualityPresets.shadow_distance_m(key)
	env.ssao_enabled = bool(p["ssao"])
	match int(p["msaa"]):
		2:
			viewport.msaa_3d = Viewport.MSAA_2X
		4:
			viewport.msaa_3d = Viewport.MSAA_4X
		_:
			viewport.msaa_3d = Viewport.MSAA_DISABLED
	env.volumetric_fog_enabled = bool(p["fog_volumetric"])

	if streamer != null:
		if "chunks_ahead" in streamer:
			streamer.chunks_ahead = int(p["chunks_ahead"])
		if "chunks_behind" in streamer:
			streamer.chunks_behind = int(p["chunks_behind"])
		if "vegetation_density_factor" in streamer:
			streamer.vegetation_density_factor = float(p["vegetation_density_factor"])


static func apply_fog(env: Environment, has_terrain: bool, horizon_color: Color = FOG_COLOR,
		theme_fog_density: float = 0.0) -> void:
	var fog: Dictionary = FOG_TERRAIN if has_terrain else FOG_FLAT
	env.fog_enabled = true
	env.fog_mode = Environment.FOG_MODE_DEPTH
	env.fog_light_color = horizon_color
	env.fog_density = 1.0
	env.fog_depth_begin = fog["begin"]
	env.fog_depth_end = fog["end"]
	env.fog_depth_curve = 1.0
	if env.volumetric_fog_enabled:
		env.volumetric_fog_density = theme_fog_density if theme_fog_density > 0.0 else 0.01
