extends SceneTree

## Tests unitaires sans écran de render_quality.gd (Lot E3 / SRS §8 et §11).
## Vérifie l'application des préréglages sur Camera3D, DirectionalLight3D, Environment, Viewport et Streamer.

const RenderQuality := preload("res://scripts/render_quality.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const WorldStreamer := preload("res://scripts/world_streamer.gd")
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


class DummyStreamer:
	var chunks_ahead: int = 0
	var chunks_behind: int = 0
	var vegetation_density_factor: float = 0.0
	var far_radius_m: float = 0.0


func _test_presets_application() -> void:
	var vp := SubViewport.new()
	root.add_child(vp)
	var cam := Camera3D.new()
	vp.add_child(cam)
	var light := DirectionalLight3D.new()
	vp.add_child(light)
	var env := Environment.new()
	var streamer := DummyStreamer.new()

	# Sans écran (ou en Compatibility), pas de RenderingDevice : SSAO et brouillard volumétrique restent éteints.
	var fp := RenderingServer.get_rendering_device() != null
	for name in ["low", "medium", "high"]:
		RenderQuality.apply_preset(name, cam, light, env, vp, streamer)
		var p: Dictionary = QualityPresets.preset(name)
		var fog_end := QualityPresets.fog_end_m(name)
		_check(absf(cam.near - RenderQuality.CAMERA_NEAR_M) < 1e-3
			and cam.far >= fog_end and cam.far <= fog_end * 1.05,
			"%s : cam.near/far conformes (near=%.3f, far=%.1f, brouillard opaque à %.0f m)" % [name, cam.near, cam.far, fog_end])
		_check(absf(streamer.far_radius_m - WorldStreamer.far_radius_for(fog_end)) < 1e-3,
			"%s : rayon des tuiles lointaines = %.0f m" % [name, streamer.far_radius_m])
		_check(light.shadow_enabled and absf(light.directional_shadow_max_distance - QualityPresets.shadow_distance_m(name)) < 1e-4,
			"%s : distance d'ombre = %.0f m" % [name, QualityPresets.shadow_distance_m(name)])
		var img: Dictionary = QualityPresets.image(name)
		_check(env.ssao_enabled == (str(img["ssao"]) != "off" and fp)
			and env.ssil_enabled == (str(img["ssil"]) != "off" and fp),
			"%s : SSAO %s, SSIL %s" % [name, img["ssao"], img["ssil"]])
		_check(vp.msaa_3d == RenderQuality.MSAA[int(img["msaa"])]
			and (vp.screen_space_aa == Viewport.SCREEN_SPACE_AA_FXAA) == bool(img["fxaa"]),
			"%s : MSAA %d×, FXAA %s" % [name, img["msaa"], str(img["fxaa"])])
		_check(absf(vp.mesh_lod_threshold - float(img["mesh_lod_threshold"])) < 1e-4,
			"%s : seuil LOD %.1f px" % [name, img["mesh_lod_threshold"]])
		_check(vp.scaling_3d_scale == 1.0, "%s : résolution native, sans mise à l'échelle 3D" % name)
		_check(env.glow_enabled == bool(img["glow"]) and env.tonemap_mode == RenderQuality.LOOK["tonemap"]
			and env.adjustment_enabled,
			"%s : glow %s, rendu des tons et étalonnage communs" % [name, str(img["glow"])])
		_check((light.directional_shadow_mode == DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS) == (int(img["shadow_splits"]) == 4),
			"%s : %d cascades d'ombre" % [name, img["shadow_splits"]])
		var vol := str(img["fog_volumetric"])
		_check(env.volumetric_fog_enabled == (fp and RenderQuality.VOLUMETRIC.has(vol)),
			"%s : brume volumétrique %s" % [name, vol])
		if env.volumetric_fog_enabled:
			_check(absf(env.volumetric_fog_length - float(RenderQuality.VOLUMETRIC[vol]["length_m"])) < 1e-3,
				"%s : portée de la brume %.0f m" % [name, RenderQuality.VOLUMETRIC[vol]["length_m"]])
		_check(streamer.chunks_ahead == int(p["chunks_ahead"]) and streamer.chunks_behind == int(p["chunks_behind"]),
			"%s : tronçons ahead=%d, behind=%d" % [name, p["chunks_ahead"], p["chunks_behind"]])
		_check(absf(streamer.vegetation_density_factor - float(p["vegetation_density_factor"])) < 1e-4,
			"%s : vegetation_density_factor = %.1f" % [name, p["vegetation_density_factor"]])

	# Préréglage inconnu donne low
	RenderQuality.apply_preset("inconnu_xyz", cam, light, env, vp, streamer)
	_check(env.ssao_enabled == (str(QualityPresets.image("low")["ssao"]) != "off" and fp) and light.directional_shadow_max_distance == QualityPresets.shadow_distance_m("low")
		and absf(cam.far - RenderQuality.camera_far_m("low")) < 1e-3,
		"préréglage inconnu replie sur low")

	vp.queue_free()


func _test_fog() -> void:
	var env := Environment.new()
	var horizon := Color(0.65, 0.75, 0.85)

	# Avec terrain (volumetric fog désactivé) : opaque à fog_end_m, début à 40 %.
	env.volumetric_fog_enabled = false
	for name in ["low", "medium", "high"]:
		var end_m := QualityPresets.fog_end_m(name)
		RenderQuality.apply_fog(env, name, true, horizon, 0.05)
		_check(absf(env.fog_depth_begin - end_m * RenderQuality.FOG_BEGIN_FRACTION) < 1e-3
			and absf(env.fog_depth_end - end_m) < 1e-3,
			"%s : brouillard terrain [%.0f, %.0f] m" % [name, env.fog_depth_begin, env.fog_depth_end])
	_check(env.fog_enabled and env.fog_mode == Environment.FOG_MODE_DEPTH,
		"brouillard activé en mode profondeur")
	_check(absf(env.fog_density - 1.0) < 1e-4, "fog_density = 1.0")
	_check(env.fog_light_color == horizon, "couleur du brouillard = couleur d'horizon")
	_check(env.fog_sky_affect == 0.0 and env.volumetric_fog_sky_affect == 0.0,
		"le brouillard ne recouvre pas le ciel (nuages visibles en Forward+, recette P16)")
	RenderQuality.apply_fog(env, "inconnu_xyz", true, horizon, 0.05)
	_check(absf(env.fog_depth_end - QualityPresets.fog_end_m("low")) < 1e-3, "brouillard : préréglage inconnu -> low")

	# Sans terrain (sol plat) : inchangé, la fin des préréglages étant plus lointaine.
	for name in ["low", "medium", "high"]:
		RenderQuality.apply_fog(env, name, false, horizon, 0.05)
		_check(absf(env.fog_depth_begin - 300.0) < 1e-4 and absf(env.fog_depth_end - 3000.0) < 1e-4,
			"%s : brouillard sol plat [300, 3000] m" % name)

	# Brume volumétrique (Y13 étape 3) : densité du niveau, ou du thème si elle est plus forte ; couleur d'horizon.
	env.volumetric_fog_enabled = true
	RenderQuality.apply_fog(env, "medium", true, horizon, 0.0008)
	_check(absf(env.volumetric_fog_density - float(RenderQuality.VOLUMETRIC["light"]["density"])) < 1e-6
		and env.volumetric_fog_albedo == horizon, "medium : brume légère (%.4f) couleur d'horizon" % env.volumetric_fog_density)
	RenderQuality.apply_fog(env, "high", true, horizon, 0.0008)
	_check(absf(env.volumetric_fog_density - float(RenderQuality.VOLUMETRIC["full"]["density"])) < 1e-6,
		"high : brume pleine (%.4f)" % env.volumetric_fog_density)
	RenderQuality.apply_fog(env, "high", true, horizon, 0.035)
	_check(absf(env.volumetric_fog_density - 0.035) < 1e-6, "high : un thème plus brumeux l'emporte (0,035)")
	_check(RenderQuality.volumetric_density("low", 0.035) == 0.0, "low : pas de brume volumétrique")

	# Avant le chargement du parcours, la scène garde aussi un brouillard à pleine opacité (revue E2, R2).
	var scene: PackedScene = load("res://scenes/main.tscn")
	var main_node := scene.instantiate()
	var env_node := main_node.get_node("WorldEnvironment") as WorldEnvironment
	_check(absf(env_node.environment.fog_density - 1.0) < 1e-4, "main.tscn : fog_density = 1 avant le chargement du parcours")
	main_node.free()


# Lot Y1 : les tuiles lointaines suivent la fin du brouillard plus une tuile, plafond 12 km.
func _test_far_tiles() -> void:
	var size: float = TerrainTiles.LEVELS["far"]["size"]
	_check(WorldStreamer.far_radius_for(4000.0) == 4000.0 + size and WorldStreamer.far_radius_for(9000.0) == WorldStreamer.FAR_RADIUS_M,
		"far_radius_for : fin du brouillard + %.0f m, plafond %.0f m" % [size, WorldStreamer.FAR_RADIUS_M])
	var streamer = WorldStreamer.new()
	var cam := Camera3D.new()
	var light := DirectionalLight3D.new()
	var env := Environment.new()
	var vp := SubViewport.new()
	root.add_child(vp)
	# Caméra à l'origine : la tuile (i, 0) commence à i × 5 000 m.
	for i in range(0, 4):
		streamer._far_index[Vector2i(i, 0)] = true
	for name in ["low", "medium", "high"]:
		RenderQuality.apply_preset(name, cam, light, env, vp, streamer)
		var limit := QualityPresets.fog_end_m(name) + size
		var window: Array = streamer.far_window(0.0, 0.0)
		var ok := true
		for i in range(0, 4):
			var dist := i * size
			var want := dist <= minf(limit, WorldStreamer.FAR_RADIUS_M)
			ok = ok and (window.has(Vector2i(i, 0)) == want)
		_check(ok, "%s : tuiles lointaines chargées jusqu'à %.0f m seulement (%d tuiles)" % [name, minf(limit, WorldStreamer.FAR_RADIUS_M), window.size()])
	_check(streamer.far_window(0.0, 0.0).size() == 3 and not streamer.far_window(0.0, 0.0).has(Vector2i(3, 0)),
		"high : la tuile à 15 km reste au-delà du plafond")
	streamer.far_radius_m = WorldStreamer.far_radius_for(QualityPresets.fog_end_m("low"))
	_check(streamer.far_window(0.0, 0.0).size() == 2, "low : tuiles à 0 et 5 km chargées, 10 km non")
	streamer.free()
	cam.free()
	light.free()
	vp.queue_free()


## Brume de la météo (Lot P17) : brouillard rapproché selon `fog_boost`, base rendue à 0.
func _test_weather_fog() -> void:
	var base := Vector2(3000.0, 12000.0)
	var none := RenderQuality.weather_fog_range(base, 0.0)
	var half := RenderQuality.weather_fog_range(base, 0.5)
	var full := RenderQuality.weather_fog_range(base, 1.0)
	_check(none == base, "brume nulle : brouillard d'origine (%.0f à %.0f m)" % [none.x, none.y])
	_check(half.y < base.y and half.y > full.y and half.x <= half.y * 0.5, "brume 0,5 : %.0f à %.0f m" % [half.x, half.y])
	_check(absf(full.y - RenderQuality.MIST_END_M) < 1e-3 and absf(full.x - RenderQuality.MIST_BEGIN_M) < 1e-3,
		"brume pleine : %.0f à %.0f m" % [full.x, full.y])
	var env := Environment.new()
	RenderQuality.apply_weather_fog(env, base, 1.0)
	_check(absf(env.fog_depth_end - RenderQuality.MIST_END_M) < 1e-3, "apply_weather_fog : fin du brouillard appliquée")
	env.volumetric_fog_enabled = true
	RenderQuality.apply_weather_fog(env, base, 0.5, 0.004)
	_check(absf(env.volumetric_fog_density - 0.004 * (1.0 + RenderQuality.MIST_VOLUMETRIC_GAIN * 0.5)) < 1e-6,
		"brume 0,5 : brume volumétrique épaissie (%.4f)" % env.volumetric_fog_density)
	RenderQuality.apply_weather_fog(env, base, 0.0, 0.004)
	_check(absf(env.volumetric_fog_density - 0.004) < 1e-6, "brume nulle : brume volumétrique d'origine")


func _init() -> void:
	_test_presets_application()
	_test_fog()
	_test_far_tiles()
	_test_weather_fog()
	print("test_render_quality : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
