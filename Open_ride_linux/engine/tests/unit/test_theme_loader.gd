extends SceneTree

## Tests sans écran du chargeur de thèmes `theme_loader.gd` (Lot I5).
## Reprend tous les cas de `compiler/tests/test_theme.py` (Lot H7).
## Lancement : godot --headless --path engine --script res://tests/unit/test_theme_loader.gd

const ThemeLoader := preload("res://scripts/theme_loader.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _dicts_equal(a: Dictionary, b: Dictionary) -> bool:
	if a.size() != b.size():
		return false
	for k in a.keys():
		if not b.has(k):
			return false
		var va = a[k]
		var vb = b[k]
		if typeof(va) == TYPE_DICTIONARY and typeof(vb) == TYPE_DICTIONARY:
			if not _dicts_equal(va, vb):
				return false
		elif typeof(va) == TYPE_ARRAY and typeof(vb) == TYPE_ARRAY:
			var aa: Array = va
			var ab: Array = vb
			if aa.size() != ab.size():
				return false
			for i in range(aa.size()):
				if str(aa[i]) != str(ab[i]):
					return false
		elif typeof(va) in [TYPE_INT, TYPE_FLOAT] and typeof(vb) in [TYPE_INT, TYPE_FLOAT]:
			if absf(float(va) - float(vb)) > 1e-6:
				return false
		else:
			if va != vb:
				return false
	return true


func _write_theme(dir_path: String, content: String) -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(dir_path))
	var f := FileAccess.open(dir_path.path_join("theme.json"), FileAccess.WRITE)
	f.store_string(content)
	f.close()


func _write_png(file_path: String, w: int, h: int) -> void:
	var dir_path := file_path.get_base_dir()
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(dir_path))
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	img.fill(Color(0.4, 0.6, 0.3, 1.0))
	img.save_png(ProjectSettings.globalize_path(file_path))


func _init() -> void:
	var base_tmp := "user://test_themes_i5"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(base_tmp))

	# 1. Thème default embarqué
	var def_res := ThemeLoader.load_theme("res://themes/default")
	_check(def_res["errors"].size() == 0, "default: 0 erreur")
	_check(def_res["warnings"].size() == 0, "default: 0 avertissement")
	var default_theme: Dictionary = def_res["theme"]

	# 2. Thème minimal {"version": "1.0"} -> égal clé par clé au thème default
	var min_dir := base_tmp.path_join("minimal")
	_write_theme(min_dir, '{"version": "1.0"}\n')
	var min_res := ThemeLoader.load_theme(min_dir)
	_check(min_res["errors"].size() == 0, "minimal: 0 erreur")
	_check(min_res["warnings"].size() == 0, "minimal: 0 avertissement")
	_check(_dicts_equal(min_res["theme"], default_theme), "minimal: égal clé par clé à default")

	# 3. Thème complet avec texture PNG 4x4 valide
	var full_dir := base_tmp.path_join("complet")
	_write_png(full_dir.path_join("textures/grass.png"), 4, 4)
	_write_png(full_dir.path_join("textures/road.png"), 4, 4)
	var full_json := JSON.stringify({
		"version": "1.0",
		"name": "Alpes été",
		"terrain": {
			"grass": {"texture": "textures/grass.png", "color": "#6f9a4a", "scale_m": 6.0},
			"rock": {"texture": null, "color": "#9a9488", "scale_m": 12.0},
			"snow": {"texture": null, "color": "#f2f5f8", "scale_m": 8.0},
			"slope_threshold_deg": 22,
			"snow_line_m": 2200,
			"blend_sharpness": 4.0,
		},
		"road": {"texture": "textures/road.png", "color": "#4a4a4d", "width_m": 6.0},
		"buildings": {"walls": ["#d9c9a3"], "roofs": ["#a65a3a"]},
		"vegetation": {"treeline_m": 2000, "max_density_per_ha": 400},
		"sky": {"sun_elevation_deg": 40, "fog_density": 0.0008},
	})
	_write_theme(full_dir, full_json)
	var full_res := ThemeLoader.load_theme(full_dir)
	_check(full_res["errors"].size() == 0, "complet: 0 erreur")
	_check(full_res["warnings"].size() == 0, "complet: 0 avertissement")
	var tex_grass := ThemeLoader.texture_for(full_res["theme"], full_dir, "terrain.grass")
	_check(tex_grass != null and tex_grass.get_width() == 4 and tex_grass.get_height() == 4, "complet: texture 4x4 chargée")
	var tex_rock := ThemeLoader.texture_for(full_res["theme"], full_dir, "terrain.rock")
	_check(tex_rock == null, "complet: texture null -> null")

	# 4. Couleurs mal formées -> erreur + repli sur default
	var bad_colors := ["vert", "#12345", "#1234567", "#GGGGGG"]
	for idx in range(bad_colors.size()):
		var c_dir := base_tmp.path_join("bad_color_%d" % idx)
		_write_theme(c_dir, JSON.stringify({"version": "1.0", "road": {"color": bad_colors[idx]}}))
		var c_res := ThemeLoader.load_theme(c_dir)
		_check(c_res["errors"].size() > 0, "couleur invalide %s -> erreur" % bad_colors[idx])
		_check(_dicts_equal(c_res["theme"], default_theme), "couleur invalide -> repli default")

	# 5. Bornes numériques violées -> erreur + repli sur default
	var bad_payloads := [
		{"version": "1.0", "terrain": {"grass": {"scale_m": 0}}},
		{"version": "1.0", "terrain": {"grass": {"scale_m": -5}}},
		{"version": "1.0", "terrain": {"slope_threshold_deg": 120}},
		{"version": "1.0", "road": {"width_m": 0}},
		{"version": "1.0", "sky": {"fog_density": -0.1}},
	]
	for idx in range(bad_payloads.size()):
		var b_dir := base_tmp.path_join("bad_bounds_%d" % idx)
		_write_theme(b_dir, JSON.stringify(bad_payloads[idx]))
		var b_res := ThemeLoader.load_theme(b_dir)
		_check(b_res["errors"].size() > 0, "borne numérique %d -> erreur" % idx)
		_check(_dicts_equal(b_res["theme"], default_theme), "borne numérique %d -> repli default" % idx)

	# 6. Version majeure non supportée -> erreur
	var v2_dir := base_tmp.path_join("v2")
	_write_theme(v2_dir, '{"version": "2.0"}')
	var v2_res := ThemeLoader.load_theme(v2_dir)
	_check(v2_res["errors"].size() > 0, "version 2.0 -> erreur")

	# 7. JSON mal formé -> erreur + repli sur default
	var bad_json_dir := base_tmp.path_join("bad_json")
	_write_theme(bad_json_dir, "{json_invalide")
	var bj_res := ThemeLoader.load_theme(bad_json_dir)
	_check(bj_res["errors"].size() > 0, "JSON mal formé -> erreur")
	_check(_dicts_equal(bj_res["theme"], default_theme), "JSON mal formé -> repli default")

	# 8. Texture manquante -> avertissement (pas erreur), texture_for renvoie null
	var miss_dir := base_tmp.path_join("missing_tex")
	_write_theme(miss_dir, JSON.stringify({
		"version": "1.0",
		"terrain": {"grass": {"texture": "textures/absent.png", "color": "#6f9a4a"}},
	}))
	var miss_res := ThemeLoader.load_theme(miss_dir)
	_check(miss_res["errors"].size() == 0, "texture absente: 0 erreur")
	_check(miss_res["warnings"].size() == 1 and miss_res["warnings"][0].contains("absent.png"), "texture absente: 1 avertissement")
	_check(ThemeLoader.texture_for(miss_res["theme"], miss_dir, "terrain.grass") == null, "texture absente: texture_for -> null")

	# 9. Dimensions non puissances de 2 -> avertissement
	var npot_dir := base_tmp.path_join("npot_tex")
	_write_png(npot_dir.path_join("textures/bad.png"), 6, 6)
	_write_theme(npot_dir, JSON.stringify({"version": "1.0", "road": {"texture": "textures/bad.png"}}))
	var npot_res := ThemeLoader.load_theme(npot_dir)
	_check(npot_res["errors"].size() == 0, "texture 6x6: 0 erreur")
	_check(npot_res["warnings"].size() == 1 and npot_res["warnings"][0].contains("6x6"), "texture 6x6: avertissement 6x6")

	# 10. Clé inconnue -> avertissement
	var unk_dir := base_tmp.path_join("unknown_key")
	_write_theme(unk_dir, JSON.stringify({"version": "1.0", "custom_future_field": true}))
	var unk_res := ThemeLoader.load_theme(unk_dir)
	_check(unk_res["errors"].size() == 0, "clé inconnue: 0 erreur")
	_check(unk_res["warnings"].size() == 1 and unk_res["warnings"][0].contains("custom_future_field"), "clé inconnue: avertissement")

	# 11. load_named("inexistant") -> thème default avec avertissement, sans erreur
	var named_res := ThemeLoader.load_named("inexistant_theme_xyz")
	_check(named_res["errors"].size() == 0, "load_named inexistant: 0 erreur")
	_check(named_res["warnings"].size() == 1, "load_named inexistant: 1 avertissement")
	_check(_dicts_equal(named_res["theme"], default_theme), "load_named inexistant: renvoie default")

	print("test_theme_loader : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
