extends RefCounted

## Réglages d'image (SRS §8, lots E1, L4, E3 et Y1) : caméra, ombres, SSAO, MSAA, brouillard, tronçons,
## rayon des tuiles lointaines.
##
## Applique les réglages de quality_presets.gd sur la caméra, la lumière, l'environnement, le viewport
## et le streamer. La table interne d'E1 est supprimée au profit de quality_presets.gd.
## Pas de class_name (charger par preload).

const QualityPresets := preload("res://scripts/quality_presets.gd")
const WorldStreamer := preload("res://scripts/world_streamer.gd")

const DEFAULT_PRESET := QualityPresets.DEFAULT_PRESET

const CAMERA_NEAR_M := 0.1
## Marge de `camera.far` au-delà de la fin du brouillard (lot Y1) : rien n'est coupé net avant d'être
## entièrement dans le brouillard. Le ciel n'est pas concerné (dessiné à l'infini).
const CAMERA_FAR_MARGIN := 0.03

## Brouillard en profondeur avec terrain (lot Y1) : opaque à `fog_end_m` du préréglage, début à 40 %
## de cette fin (1,6 / 2,4 / 3,6 km) pour que le relief proche et les villages restent nets.
const FOG_BEGIN_FRACTION := 0.4
## Sans terrain (sol plat) : début et fin fixes (m), la fin ne dépassant pas celle du préréglage.
const FOG_FLAT := {"begin": 300.0, "end": 3000.0}
const FOG_COLOR := Color(0.70, 0.78, 0.86)
## Part du brouillard posée sur le ciel. Godot met 1 par défaut : en Forward+ (PC cible), le ciel entier
## prenait alors la couleur du brouillard et les nuages de P6 étaient invisibles (recette P16). À 0, le
## ciel reste dessiné ; le ciel nuageux raccorde son horizon à la couleur du brouillard (sky_clouds.gd).
const FOG_SKY_AFFECT := 0.0


static func apply_preset(preset_name: String, camera: Camera3D, light: DirectionalLight3D,
		env: Environment, viewport: Viewport, streamer: Variant = null) -> void:
	var key := preset_name.strip_edges()
	var p: Dictionary = QualityPresets.preset(key)
	camera.near = CAMERA_NEAR_M
	camera.far = camera_far_m(key)
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
		if "far_radius_m" in streamer:
			streamer.far_radius_m = WorldStreamer.far_radius_for(QualityPresets.fog_end_m(key))


## Distance de vue de la caméra : fin du brouillard du préréglage plus CAMERA_FAR_MARGIN.
static func camera_far_m(preset_name: String) -> float:
	return QualityPresets.fog_end_m(preset_name) * (1.0 + CAMERA_FAR_MARGIN)


## Début et fin du brouillard de profondeur (m) pour le préréglage, avec ou sans terrain.
static func fog_range(preset_name: String, has_terrain: bool) -> Dictionary:
	var end_m := QualityPresets.fog_end_m(preset_name)
	if has_terrain:
		return {"begin": end_m * FOG_BEGIN_FRACTION, "end": end_m}
	var flat_end := minf(float(FOG_FLAT["end"]), end_m)
	return {"begin": minf(float(FOG_FLAT["begin"]), flat_end * FOG_BEGIN_FRACTION), "end": flat_end}


static func apply_fog(env: Environment, preset_name: String, has_terrain: bool,
		horizon_color: Color = FOG_COLOR, theme_fog_density: float = 0.0) -> void:
	var fog := fog_range(preset_name, has_terrain)
	env.fog_enabled = true
	env.fog_mode = Environment.FOG_MODE_DEPTH
	env.fog_light_color = horizon_color
	env.fog_density = 1.0
	env.fog_depth_begin = fog["begin"]
	env.fog_depth_end = fog["end"]
	env.fog_depth_curve = 1.0
	env.fog_sky_affect = FOG_SKY_AFFECT
	env.volumetric_fog_sky_affect = FOG_SKY_AFFECT
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
