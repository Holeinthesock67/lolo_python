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
	# SSAO et brouillard volumétrique n'existent qu'en Forward+ (sans RenderingDevice : Compatibility).
	var forward_plus := RenderingServer.get_rendering_device() != null
	env.ssao_enabled = bool(p["ssao"]) and forward_plus
	match int(p["msaa"]):
		2:
			viewport.msaa_3d = Viewport.MSAA_2X
		4:
			viewport.msaa_3d = Viewport.MSAA_4X
		_:
			viewport.msaa_3d = Viewport.MSAA_DISABLED
	env.volumetric_fog_enabled = bool(p["fog_volumetric"]) and forward_plus

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


## Brume de la météo (Lot P17, `fog_boost` de weather_model.gd, 0 à 1) : rapproche le brouillard en
## profondeur posé par `apply_fog` (début et fin `base` en m). À `fog_boost` = 1, le brouillard
## commence à MIST_BEGIN_M et est plein à MIST_END_M ; 0 redonne `base`.
const MIST_BEGIN_M := 20.0
const MIST_END_M := 450.0


static func weather_fog_range(base: Vector2, fog_boost: float) -> Vector2:
	var b := clampf(fog_boost, 0.0, 1.0)
	var end := lerpf(base.y, minf(base.y, MIST_END_M), b)
	var begin := minf(lerpf(base.x, MIST_BEGIN_M, b), end * 0.5) if b > 0.0 else base.x
	return Vector2(begin, end)


static func apply_weather_fog(env: Environment, base: Vector2, fog_boost: float) -> void:
	var r := weather_fog_range(base, fog_boost)
	env.fog_depth_begin = r.x
	env.fog_depth_end = r.y
