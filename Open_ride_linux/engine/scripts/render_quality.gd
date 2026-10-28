extends RefCounted

## Réglages d'image (SRS §8, lots E1, L4, E3, Y1 et Y13) : caméra, ombres, anticrénelage, filtrage,
## occlusion ambiante, glow, rendu des tons, brouillard, tronçons, rayon des tuiles lointaines.
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
## Voile de l'horizon des biomes (série U) : poussière et brume, mélangé à l'horizon selon `sky.haze` du biome.
const HAZE_COLOR := Color(0.86, 0.80, 0.68)
## Part du brouillard posée sur le ciel. Godot met 1 par défaut : en Forward+ (PC cible), le ciel entier
## prenait alors la couleur du brouillard et les nuages de P6 étaient invisibles (recette P16). À 0, le
## ciel reste dessiné ; le ciel nuageux raccorde son horizon à la couleur du brouillard (sky_clouds.gd).
const FOG_SKY_AFFECT := 0.0


## Rendu des tons et étalonnage communs à tous les préréglages (lot Y13, coût nul) : courbe « Filmic »
## (hautes lumières du ciel adoucies au lieu d'être coupées), exposition relevée pour compenser la courbe,
## contraste et saturation légèrement relevés. Choisi sur captures parmi Linear, Reinhard, Filmic et ACES.
const LOOK := {
	"tonemap": Environment.TONE_MAPPER_FILMIC,
	"exposure": 1.25,
	"white": 6.0,
	"contrast": 1.08,
	"saturation": 1.18,
}
## Glow des préréglages qui l'activent : léger, seulement sur ce qui dépasse le blanc (ciel, soleil).
const GLOW := {"intensity": 0.6, "strength": 1.0, "bloom": 0.0, "hdr_threshold": 1.0}

const AO_QUALITY := {
	"low": RenderingServer.ENV_SSAO_QUALITY_LOW,
	"medium": RenderingServer.ENV_SSAO_QUALITY_MEDIUM,
	"high": RenderingServer.ENV_SSAO_QUALITY_HIGH,
}
const SSIL_QUALITY := {
	"low": RenderingServer.ENV_SSIL_QUALITY_LOW,
	"medium": RenderingServer.ENV_SSIL_QUALITY_MEDIUM,
	"high": RenderingServer.ENV_SSIL_QUALITY_HIGH,
}
const SHADOW_FILTER := {
	"hard": RenderingServer.SHADOW_QUALITY_HARD,
	"very_low": RenderingServer.SHADOW_QUALITY_SOFT_VERY_LOW,
	"low": RenderingServer.SHADOW_QUALITY_SOFT_LOW,
	"medium": RenderingServer.SHADOW_QUALITY_SOFT_MEDIUM,
	"high": RenderingServer.SHADOW_QUALITY_SOFT_HIGH,
}
## Brume volumétrique par niveau (lot Y13, étape 3) : grille (cases en largeur et en hauteur d'écran),
## portée en m, densité minimale et anisotropie (le soleil éclaire la brume vers l'avant, rayons dans
## les trouées des arbres). Les densités des thèmes (0,0004 à 0,0012) ne se voient pas à ces portées :
## celle du thème ne l'emporte que si elle est plus forte. La brume prend la couleur de l'horizon.
const VOLUMETRIC := {
	"light": {"grid": 48, "length_m": 600.0, "density": 0.004, "anisotropy": 0.6},
	"full": {"grid": 64, "length_m": 1200.0, "density": 0.006, "anisotropy": 0.6},
}
const VOLUMETRIC_DEPTH := 64
const MSAA := {0: Viewport.MSAA_DISABLED, 2: Viewport.MSAA_2X, 4: Viewport.MSAA_4X, 8: Viewport.MSAA_8X}


static func apply_preset(preset_name: String, camera: Camera3D, light: DirectionalLight3D,
		env: Environment, viewport: Viewport, streamer: Variant = null) -> void:
	var key := preset_name.strip_edges()
	var p: Dictionary = QualityPresets.preset(key)
	camera.near = CAMERA_NEAR_M
	camera.far = camera_far_m(key)
	light.shadow_enabled = true
	light.directional_shadow_max_distance = QualityPresets.shadow_distance_m(key)
	# SSAO, SSIL et brouillard volumétrique n'existent qu'en Forward+ (sans RenderingDevice : Compatibility).
	var forward_plus := RenderingServer.get_rendering_device() != null
	apply_image(QualityPresets.image(key), light, env, viewport, forward_plus)

	if streamer != null:
		if "chunks_ahead" in streamer:
			streamer.chunks_ahead = int(p["chunks_ahead"])
		if "chunks_behind" in streamer:
			streamer.chunks_behind = int(p["chunks_behind"])
		if "vegetation_density_factor" in streamer:
			streamer.vegetation_density_factor = float(p["vegetation_density_factor"])
		if "far_radius_m" in streamer:
			streamer.far_radius_m = WorldStreamer.far_radius_for(QualityPresets.fog_end_m(key))
		if "quality_preset" in streamer:
			streamer.quality_preset = key   # biomes par tuile et textures de sol (lot U6)


## Qualité d'image (lot Y13) : anticrénelage, filtrage, occlusion ambiante, glow, ombres, LOD, et rendu
## des tons commun (LOOK). La résolution reste celle de l'écran : aucune mise à l'échelle 3D.
static func apply_image(img: Dictionary, light: DirectionalLight3D, env: Environment, viewport: Viewport,
		forward_plus: bool) -> void:
	viewport.msaa_3d = MSAA[int(img["msaa"])]
	viewport.screen_space_aa = Viewport.SCREEN_SPACE_AA_FXAA if bool(img["fxaa"]) else Viewport.SCREEN_SPACE_AA_DISABLED
	viewport.mesh_lod_threshold = float(img["mesh_lod_threshold"])
	viewport.scaling_3d_scale = 1.0

	var half := bool(img["ao_half_size"])
	var ssao := str(img["ssao"])
	env.ssao_enabled = forward_plus and AO_QUALITY.has(ssao)
	if env.ssao_enabled:
		RenderingServer.environment_set_ssao_quality(AO_QUALITY[ssao], half, 0.5, 2, 50.0, 300.0)
	var ssil := str(img["ssil"])
	env.ssil_enabled = forward_plus and SSIL_QUALITY.has(ssil)
	if env.ssil_enabled:
		RenderingServer.environment_set_ssil_quality(SSIL_QUALITY[ssil], half, 0.5, 4, 50.0, 300.0)

	var vol := str(img["fog_volumetric"])
	env.volumetric_fog_enabled = forward_plus and VOLUMETRIC.has(vol)
	if env.volumetric_fog_enabled:
		RenderingServer.environment_set_volumetric_fog_volume_size(int(VOLUMETRIC[vol]["grid"]), VOLUMETRIC_DEPTH)
		RenderingServer.environment_set_volumetric_fog_filter_active(true)
		env.volumetric_fog_length = VOLUMETRIC[vol]["length_m"]
		env.volumetric_fog_anisotropy = VOLUMETRIC[vol]["anisotropy"]

	env.glow_enabled = bool(img["glow"])
	env.glow_intensity = GLOW["intensity"]
	env.glow_strength = GLOW["strength"]
	env.glow_bloom = GLOW["bloom"]
	env.glow_hdr_threshold = GLOW["hdr_threshold"]
	env.glow_blend_mode = Environment.GLOW_BLEND_MODE_SOFTLIGHT

	env.tonemap_mode = LOOK["tonemap"]
	env.tonemap_exposure = LOOK["exposure"]
	env.tonemap_white = LOOK["white"]
	env.adjustment_enabled = true
	env.adjustment_contrast = LOOK["contrast"]
	env.adjustment_saturation = LOOK["saturation"]

	RenderingServer.directional_shadow_atlas_set_size(int(img["shadow_atlas"]), true)
	# Le filtre doux de Compatibility tire un bruit différent à chaque image (grain qui scintille) :
	# ombres dures sans RenderingDevice, comme pour SSAO et SSIL.
	RenderingServer.directional_soft_shadow_filter_set_quality(SHADOW_FILTER[str(img["shadow_filter"])] if forward_plus
		else RenderingServer.SHADOW_QUALITY_HARD)
	light.directional_shadow_mode = (DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS if int(img["shadow_splits"]) == 4
		else DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS)


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
		env.volumetric_fog_density = volumetric_density(preset_name, theme_fog_density)
		env.volumetric_fog_albedo = horizon_color


## Densité de la brume volumétrique : celle du niveau du préréglage, ou celle du thème si elle est plus forte.
static func volumetric_density(preset_name: String, theme_fog_density: float) -> float:
	var vol := str(QualityPresets.image(preset_name)["fog_volumetric"])
	return maxf(float(VOLUMETRIC[vol]["density"]), theme_fog_density) if VOLUMETRIC.has(vol) else 0.0


## Brume de la météo (Lot P17, `fog_boost` de weather_model.gd, 0 à 1) : rapproche le brouillard en
## profondeur posé par `apply_fog` (début et fin `base` en m). À `fog_boost` = 1, le brouillard
## commence à MIST_BEGIN_M et est plein à MIST_END_M ; 0 redonne `base`. La brume volumétrique, si elle
## est active, s'épaissit avec : densité `vol_base` × (1 + MIST_VOLUMETRIC_GAIN × `fog_boost`).
const MIST_BEGIN_M := 20.0
const MIST_END_M := 450.0
const MIST_VOLUMETRIC_GAIN := 3.0


static func weather_fog_range(base: Vector2, fog_boost: float) -> Vector2:
	var b := clampf(fog_boost, 0.0, 1.0)
	var end := lerpf(base.y, minf(base.y, MIST_END_M), b)
	var begin := minf(lerpf(base.x, MIST_BEGIN_M, b), end * 0.5) if b > 0.0 else base.x
	return Vector2(begin, end)


static func apply_weather_fog(env: Environment, base: Vector2, fog_boost: float, vol_base: float = 0.0) -> void:
	var r := weather_fog_range(base, fog_boost)
	env.fog_depth_begin = r.x
	env.fog_depth_end = r.y
	if env.volumetric_fog_enabled and vol_base > 0.0:
		env.volumetric_fog_density = vol_base * (1.0 + MIST_VOLUMETRIC_GAIN * clampf(fog_boost, 0.0, 1.0))
