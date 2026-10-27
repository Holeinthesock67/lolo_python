extends SceneTree

## Tests unitaires sans écran des paramètres de rendu tirés du thème `theme_render_params.gd` (Lot L3).
## Lancement : godot --headless --path engine --script res://tests/unit/test_theme_render_params.gd

const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")

var _failures := 0
var _checked := 0
var _default_theme := {}


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _normal_for_slope_deg(deg: float) -> Vector3:
	var r := deg_to_rad(deg)
	return Vector3(sin(r), cos(r), 0.0).normalized()


# Critère 2 : thème par défaut aux 4 points cardinaux de pente/altitude
func _test_default_corners() -> void:
	var p: Dictionary = ThemeRenderParams.terrain_uniforms(_default_theme)
	_check(is_equal_approx(p["grass_inv_scale"], 1.0 / 6.0)
		and is_equal_approx(p["rock_inv_scale"], 1.0 / 12.0)
		and is_equal_approx(p["snow_inv_scale"], 1.0 / 8.0)
		and is_equal_approx(p["cos_slope"], cos(deg_to_rad(22.0))),
		"terrain_uniforms : échelles inverses et cos_slope conformes au thème par défaut")

	var w_flat_1000 := ThemeRenderParams.blend_weights(_normal_for_slope_deg(0.0), 1000.0, p)
	_check(w_flat_1000.x >= 0.99, "sol plat à 1 000 m : herbe = %.4f (≥ 0,99)" % w_flat_1000.x)

	var w_30_1000 := ThemeRenderParams.blend_weights(_normal_for_slope_deg(30.0), 1000.0, p)
	_check(w_30_1000.y >= 0.99, "pente 30° à 1 000 m : roche = %.4f (≥ 0,99)" % w_30_1000.y)

	var w_flat_2400 := ThemeRenderParams.blend_weights(_normal_for_slope_deg(0.0), 2400.0, p)
	_check(w_flat_2400.z >= 0.99, "sol plat à 2 400 m : neige = %.4f (≥ 0,99)" % w_flat_2400.z)

	var w_60_2400 := ThemeRenderParams.blend_weights(_normal_for_slope_deg(60.0), 2400.0, p)
	_check(w_60_2400.y >= 0.99, "pente 60° à 2 400 m : roche = %.4f (≥ 0,99)" % w_60_2400.y)


# Critère 3 : continuité en pente (0 à 45° par pas de 0,5°) et en altitude (2 100 à 2 300 m par pas de 1 m)
func _test_continuity() -> void:
	var p: Dictionary = ThemeRenderParams.terrain_uniforms(_default_theme)
	var max_slope_jump := 0.0
	var prev_w := ThemeRenderParams.blend_weights(_normal_for_slope_deg(0.0), 1500.0, p)
	for step in range(1, 91):
		var deg := float(step) * 0.5
		var w := ThemeRenderParams.blend_weights(_normal_for_slope_deg(deg), 1500.0, p)
		var jump := maxf(maxf(absf(w.x - prev_w.x), absf(w.y - prev_w.y)), absf(w.z - prev_w.z))
		max_slope_jump = maxf(max_slope_jump, jump)
		prev_w = w
	_check(max_slope_jump <= 0.2,
		"continuité en pente (0 à 45° par pas de 0,5°) : saut max = %.4f (≤ 0,2)" % max_slope_jump)

	var max_alt_jump := 0.0
	prev_w = ThemeRenderParams.blend_weights(_normal_for_slope_deg(10.0), 2100.0, p)
	for alt in range(2101, 2301):
		var w := ThemeRenderParams.blend_weights(_normal_for_slope_deg(10.0), float(alt), p)
		var jump := maxf(maxf(absf(w.x - prev_w.x), absf(w.y - prev_w.y)), absf(w.z - prev_w.z))
		max_alt_jump = maxf(max_alt_jump, jump)
		prev_w = w
	_check(max_alt_jump <= 0.2,
		"continuité en altitude (2 100 à 2 300 m par pas de 1 m) : saut max = %.4f (≤ 0,2)" % max_alt_jump)


# Critère 4 : 1 000 normales et altitudes tirées à graine fixe -> poids dans [0, 1], somme = 1 ± 1e-5
func _test_1000_random_samples() -> void:
	var p: Dictionary = ThemeRenderParams.terrain_uniforms(_default_theme)
	var rng := RandomNumberGenerator.new()
	rng.seed = 20261024
	var blend_ok := true
	var tri_ok := true
	for _i in range(1000):
		var nx := rng.randf_range(-1.0, 1.0)
		var ny := rng.randf_range(0.01, 1.0)
		var nz := rng.randf_range(-1.0, 1.0)
		var n := Vector3(nx, ny, nz).normalized()
		var alt := rng.randf_range(0.0, 3500.0)
		var bw := ThemeRenderParams.blend_weights(n, alt, p)
		var b_sum := bw.x + bw.y + bw.z
		if bw.x < -1e-6 or bw.y < -1e-6 or bw.z < -1e-6 or bw.x > 1.0 + 1e-6 or bw.y > 1.0 + 1e-6 or bw.z > 1.0 + 1e-6 or absf(b_sum - 1.0) > 1e-5:
			blend_ok = false
		var tw := ThemeRenderParams.triplanar_weights(n, p["blend_sharpness"])
		var t_sum := tw.x + tw.y + tw.z
		if tw.x < 0.0 or tw.y < 0.0 or tw.z < 0.0 or tw.x > 1.0 + 1e-6 or tw.y > 1.0 + 1e-6 or tw.z > 1.0 + 1e-6 or absf(t_sum - 1.0) > 1e-5:
			tri_ok = false
	_check(blend_ok, "1 000 échantillons à graine fixe : blend_weights dans [0, 1] et somme = 1 ± 1e-5")
	_check(tri_ok, "1 000 échantillons à graine fixe : triplanar_weights dans [0, 1] et somme = 1 ± 1e-5")


# Critère 5 : thème minimal {"version": "1.0"} et déplacement du seuil de pente à 30°
func _test_minimal_theme_and_custom_slope() -> void:
	var minimal := {"version": "1.0"}
	var u_min := ThemeRenderParams.terrain_uniforms(minimal)
	var u_def := ThemeRenderParams.terrain_uniforms(_default_theme)
	var r_min := ThemeRenderParams.road_params(minimal)
	var r_def := ThemeRenderParams.road_params(_default_theme)
	var s_min := ThemeRenderParams.sky_params(minimal)
	var s_def := ThemeRenderParams.sky_params(_default_theme)
	_check(u_min["grass_color"] == u_def["grass_color"]
		and is_equal_approx(u_min["cos_slope"], u_def["cos_slope"])
		and is_equal_approx(u_min["snow_line_m"], u_def["snow_line_m"])
		and r_min == r_def and s_min == s_def,
		"thème réduit à {\"version\": \"1.0\"} : valeurs identiques au thème de référence")

	var custom := {"version": "1.0", "terrain": {"slope_threshold_deg": 30.0}}
	var u_30 := ThemeRenderParams.terrain_uniforms(custom)
	var w_at_25 := ThemeRenderParams.blend_weights(_normal_for_slope_deg(25.0), 1000.0, u_30)
	var w_at_30 := ThemeRenderParams.blend_weights(_normal_for_slope_deg(30.0), 1000.0, u_30)
	var w_at_35 := ThemeRenderParams.blend_weights(_normal_for_slope_deg(35.0), 1000.0, u_30)
	_check(w_at_25.x >= 0.99 and is_equal_approx(w_at_30.x, 0.5) and is_equal_approx(w_at_30.y, 0.5) and w_at_35.y >= 0.99,
		"seuil de pente à 30° : transition déplacée à 30° (herbe(25°)=%.2f, herbe(30°)=%.2f, roche(35°)=%.2f)" % [
			w_at_25.x, w_at_30.x, w_at_35.y])


# Critère 6 : sky_params (vecteur du soleil unitaire, élévation égale à sun_elevation_deg à 0,01° près)
func _test_sky_params() -> void:
	for elev in [-15.0, 0.0, 40.0, 72.5]:
		var sk := ThemeRenderParams.sky_params({"version": "1.0", "sky": {"sun_elevation_deg": elev, "fog_density": 0.0012}})
		var dir: Vector3 = sk["sun_direction"]
		var got_elev := rad_to_deg(asin(clampf(dir.y, -1.0, 1.0)))
		_check(is_equal_approx(dir.length(), 1.0) and absf(got_elev - elev) <= 0.01,
			"sky_params (sun_elevation_deg = %.1f°) : |dir| = %.5f, élévation = %.4f°" % [elev, dir.length(), got_elev])


# Lot P6, critère 3 : cloud_params (valeurs par défaut sans clé, bornes appliquées)
func _test_cloud_params() -> void:
	var none := ThemeRenderParams.cloud_params({"version": "1.0"})
	_check(is_equal_approx(none["coverage"], 0.3) and is_equal_approx(none["speed_factor"], 1.0)
		and is_equal_approx(none["altitude_m"], 2000.0) and none["color"] is Color,
		"cloud_params sans sky.clouds : couverture 0,3, facteur 1,0, 2 000 m")
	var col: Color = none["color"]
	_check(col.b > col.r and col.r > 0.9, "couleur par défaut : blanc légèrement bleuté")
	var out := ThemeRenderParams.cloud_params({"sky": {"clouds": {"coverage": 1.7, "speed_factor": -2,
		"altitude_m": 50000, "color": "pas une couleur"}}})
	_check(is_equal_approx(out["coverage"], 1.0) and is_equal_approx(out["speed_factor"], 0.0)
		and is_equal_approx(out["altitude_m"], ThemeRenderParams.MAX_CLOUD_ALTITUDE_M)
		and out["color"] == ThemeRenderParams.cloud_params({})["color"],
		"bornes : couverture 1,7 ramenée à 1, facteur négatif à 0, altitude bornée, couleur invalide remplacée")
	var low := ThemeRenderParams.cloud_params({"sky": {"clouds": {"coverage": -0.5, "altitude_m": 10}}})
	_check(is_equal_approx(low["coverage"], 0.0) and is_equal_approx(low["altitude_m"], ThemeRenderParams.MIN_CLOUD_ALTITUDE_M),
		"bornes basses : couverture 0, altitude minimale")
	var dflt := ThemeRenderParams.cloud_params(_default_theme)
	_check(is_equal_approx(dflt["coverage"], 0.3) and is_equal_approx(dflt["altitude_m"], 1500.0)
		and dflt["color"] == Color.html("#ffffff"), "thème par défaut 1.2 : valeurs de sky.clouds lues")


func _init() -> void:
	var tl = ThemeLoader.new()
	_default_theme = tl.load_named("default")["theme"]
	_test_default_corners()
	_test_continuity()
	_test_1000_random_samples()
	_test_minimal_theme_and_custom_slope()
	_test_sky_params()
	_test_cloud_params()
	print("test_theme_render_params : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
