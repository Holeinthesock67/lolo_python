extends SceneTree

## Tests unitaires sans écran de render_quality.gd (Lot E3 / SRS §8 et §11).
## Vérifie l'application des préréglages sur Camera3D, DirectionalLight3D, Environment, Viewport et Streamer.

const RenderQuality := preload("res://scripts/render_quality.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const WorldStreamer := preload("res://scripts/world_streamer.gd")

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
		_check(absf(cam.near - RenderQuality.CAMERA_NEAR_M) < 1e-3 and absf(cam.far - RenderQuality.CAMERA_FAR_M) < 1.0,
			"%s : cam.near/far conformes (near=%.3f, far=%.1f)" % [name, cam.near, cam.far])
		_check(light.shadow_enabled and absf(light.directional_shadow_max_distance - QualityPresets.shadow_distance_m(name)) < 1e-4,
			"%s : distance d'ombre = %.0f m" % [name, QualityPresets.shadow_distance_m(name)])
		_check(env.ssao_enabled == (bool(p["ssao"]) and fp),
			"%s : ssao_enabled = %s" % [name, str(p["ssao"])])
		var want_msaa = Viewport.MSAA_DISABLED
		if int(p["msaa"]) == 2:
			want_msaa = Viewport.MSAA_2X
		elif int(p["msaa"]) == 4:
			want_msaa = Viewport.MSAA_4X
		_check(vp.msaa_3d == want_msaa, "%s : msaa_3d conforme" % name)
		_check(env.volumetric_fog_enabled == (bool(p["fog_volumetric"]) and fp),
			"%s : volumetric_fog_enabled = %s" % [name, str(p["fog_volumetric"])])
		_check(streamer.chunks_ahead == int(p["chunks_ahead"]) and streamer.chunks_behind == int(p["chunks_behind"]),
			"%s : tronçons ahead=%d, behind=%d" % [name, p["chunks_ahead"], p["chunks_behind"]])
		_check(absf(streamer.vegetation_density_factor - float(p["vegetation_density_factor"])) < 1e-4,
			"%s : vegetation_density_factor = %.1f" % [name, p["vegetation_density_factor"]])

	# Préréglage inconnu donne low
	RenderQuality.apply_preset("inconnu_xyz", cam, light, env, vp, streamer)
	var p_low: Dictionary = QualityPresets.preset("low")
	_check(env.ssao_enabled == (bool(p_low["ssao"]) and fp) and light.directional_shadow_max_distance == QualityPresets.shadow_distance_m("low"),
		"préréglage inconnu replie sur low")

	vp.queue_free()


func _test_fog() -> void:
	var env := Environment.new()
	var horizon := Color(0.65, 0.75, 0.85)

	# Avec terrain, preset low (volumetric fog désactivé)
	env.volumetric_fog_enabled = false
	RenderQuality.apply_fog(env, true, horizon, 0.05)
	_check(env.fog_enabled and env.fog_mode == Environment.FOG_MODE_DEPTH,
		"brouillard activé en mode profondeur")
	_check(absf(env.fog_density - 1.0) < 1e-4, "fog_density = 1.0")
	_check(absf(env.fog_depth_begin - 3000.0) < 1e-4 and absf(env.fog_depth_end - WorldStreamer.FAR_RADIUS_M) < 1e-4,
		"brouillard terrain [3000, 12000] m")
	_check(env.fog_light_color == horizon, "couleur du brouillard = couleur d'horizon")

	# Sans terrain (sol plat)
	RenderQuality.apply_fog(env, false, horizon, 0.05)
	_check(absf(env.fog_depth_begin - 300.0) < 1e-4 and absf(env.fog_depth_end - 3000.0) < 1e-4,
		"brouillard sol plat [300, 3000] m")

	# Preset high (volumetric fog activé)
	env.volumetric_fog_enabled = true
	RenderQuality.apply_fog(env, true, horizon, 0.035)
	_check(env.volumetric_fog_enabled and absf(env.volumetric_fog_density - 0.035) < 1e-4,
		"brouillard volumétrique actif avec densité du thème")

	# Avant le chargement du parcours, la scène garde aussi un brouillard à pleine opacité (revue E2, R2).
	var scene: PackedScene = load("res://scenes/main.tscn")
	var main_node := scene.instantiate()
	var env_node := main_node.get_node("WorldEnvironment") as WorldEnvironment
	_check(absf(env_node.environment.fog_density - 1.0) < 1e-4, "main.tscn : fog_density = 1 avant le chargement du parcours")
	main_node.free()


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


func _init() -> void:
	_test_presets_application()
	_test_fog()
	_test_weather_fog()
	print("test_render_quality : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
