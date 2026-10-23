extends RefCounted

## Chargeur et validateur de thèmes visuels OpenRide (Lot I5, Format .world v1 §9).
##
## Même logique que `compiler/src/openride_compiler/theme.py` (Lot H7) :
## - fusion récursive avec `res://themes/default/theme.json` (source unique des valeurs par défaut) ;
## - erreurs (JSON mal formé, version non supportée, couleur mal formée, valeur hors bornes) ->
##   repli complet sur le thème `default` ;
## - avertissements (clé inconnue, texture absente ou non puissance de 2) -> repli de la texture
##   sur la couleur unie `color`.
## Pas de class_name : charger par preload("res://scripts/theme_loader.gd").

const DEFAULT_THEME_DIR := "res://themes/default"
const DEFAULT_THEME_PATH := "res://themes/default/theme.json"


static func _home_dir() -> String:
	var h := OS.get_environment("HOME")
	if h != "":
		return h
	var up := OS.get_environment("USERPROFILE")
	if up != "":
		return up
	return OS.get_system_dir(OS.SYSTEM_DIR_DOCUMENTS)


static func _themes_base_dir() -> String:
	var env := OS.get_environment("OPENRIDE_THEMES_DIR")
	if env != "":
		return env
	return _home_dir().path_join("OpenRide/Themes")


static func _load_default_dict() -> Dictionary:
	var text := FileAccess.get_file_as_string(DEFAULT_THEME_PATH)
	var parsed = JSON.parse_string(text)
	if typeof(parsed) == TYPE_DICTIONARY:
		return (parsed as Dictionary).duplicate(true)
	return {}


static func _is_number(v: Variant) -> bool:
	return typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT


static func _is_hex_color(v: Variant) -> bool:
	if typeof(v) != TYPE_STRING:
		return false
	var s: String = v
	if s.length() != 7 or not s.begins_with("#"):
		return false
	for i in range(1, 7):
		var c := s.unicode_at(i)
		var is_digit := c >= 48 and c <= 57
		var is_upper := c >= 65 and c <= 70
		var is_lower := c >= 97 and c <= 102
		if not (is_digit or is_upper or is_lower):
			return false
	return true


static func _is_valid_version(v: Variant) -> bool:
	if typeof(v) != TYPE_STRING:
		return false
	var s: String = v
	if not s.begins_with("1.") or s.length() < 3:
		return false
	for i in range(2, s.length()):
		var c := s.unicode_at(i)
		if c < 48 or c > 57:
			return false
	return true


static func _is_power_of_two(n: int) -> bool:
	return n > 0 and (n & (n - 1)) == 0


static func _u16_be(buf: PackedByteArray, offset: int) -> int:
	return (int(buf[offset]) << 8) | int(buf[offset + 1])


static func _u32_be(buf: PackedByteArray, offset: int) -> int:
	return (
		(int(buf[offset]) << 24)
		| (int(buf[offset + 1]) << 16)
		| (int(buf[offset + 2]) << 8)
		| int(buf[offset + 3])
	)


static func _read_image_dimensions(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {"ok": false}
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return {"ok": false}
	var length := f.get_length()
	var data := f.get_buffer(min(length, 65536))
	f.close()

	# PNG : 89 50 4E 47 0D 0A 1A 0A + len(4) + 'IHDR'(4) + width(4) + height(4)
	if data.size() >= 24:
		if (
			data[0] == 0x89 and data[1] == 0x50 and data[2] == 0x4E and data[3] == 0x47
			and data[4] == 0x0D and data[5] == 0x0A and data[6] == 0x1A and data[7] == 0x0A
			and data[12] == 0x49 and data[13] == 0x48 and data[14] == 0x44 and data[15] == 0x52
		):
			var w := _u32_be(data, 16)
			var h := _u32_be(data, 20)
			if w > 0 and h > 0:
				return {"ok": true, "format": "png", "width": w, "height": h}
			return {"ok": false}

	# JPEG : FF D8 ...
	if data.size() >= 4 and data[0] == 0xFF and data[1] == 0xD8:
		var idx := 2
		var n := data.size()
		var sof_markers := [0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF]
		while idx < n:
			while idx < n and data[idx] != 0xFF:
				idx += 1
			while idx < n and data[idx] == 0xFF:
				idx += 1
			if idx >= n:
				break
			var marker := int(data[idx])
			idx += 1
			if marker == 0xD8 or marker == 0xD9 or marker == 0x01 or (marker >= 0xD0 and marker <= 0xD7):
				continue
			if idx + 2 > n:
				return {"ok": false}
			var seg_len := _u16_be(data, idx)
			if seg_len < 2 or idx + seg_len > n:
				return {"ok": false}
			if marker in sof_markers:
				if seg_len < 7:
					return {"ok": false}
				var h := _u16_be(data, idx + 3)
				var w := _u16_be(data, idx + 5)
				if w > 0 and h > 0:
					return {"ok": true, "format": "jpeg", "width": w, "height": h}
				return {"ok": false}
			idx += seg_len

	return {"ok": false}


static func _warn_unknown_keys(
	data: Dictionary,
	reference: Dictionary,
	prefix: String,
	warnings: PackedStringArray
) -> void:
	for key in data.keys():
		var k_str := str(key)
		var path_key := (prefix + "." + k_str) if prefix != "" else k_str
		if not reference.has(key):
			warnings.append("clé inconnue ignorée : " + path_key)
			continue
		var val = data[key]
		var ref_val = reference[key]
		if typeof(val) == TYPE_DICTIONARY and typeof(ref_val) == TYPE_DICTIONARY:
			_warn_unknown_keys(val, ref_val, path_key, warnings)


static func _validate_surface_layer(
	layer: Variant,
	label: String,
	errors: PackedStringArray
) -> void:
	if typeof(layer) != TYPE_DICTIONARY:
		errors.append(label + " : doit être un objet")
		return
	var d: Dictionary = layer
	if d.has("texture") and d["texture"] != null and typeof(d["texture"]) != TYPE_STRING:
		errors.append(label + ".texture : doit être une chaîne ou null")
	if d.has("color") and not _is_hex_color(d["color"]):
		errors.append(label + ".color : couleur hexadécimale #RRGGBB invalide")
	if d.has("scale_m"):
		if not _is_number(d["scale_m"]) or float(d["scale_m"]) <= 0.0:
			errors.append(label + ".scale_m : doit être > 0")


static func _validate_schema(data: Dictionary, errors: PackedStringArray) -> void:
	if not data.has("version"):
		errors.append("<racine> : champ 'version' obligatoire absent")
	elif not _is_valid_version(data["version"]):
		errors.append("version : version non supportée " + str(data["version"]))

	if data.has("name"):
		if typeof(data["name"]) != TYPE_STRING or str(data["name"]).length() < 1:
			errors.append("name : doit être une chaîne non vide")

	if data.has("terrain"):
		if typeof(data["terrain"]) != TYPE_DICTIONARY:
			errors.append("terrain : doit être un objet")
		else:
			var t: Dictionary = data["terrain"]
			for s_name in ["grass", "rock", "snow"]:
				if t.has(s_name):
					_validate_surface_layer(t[s_name], "terrain." + s_name, errors)
			if t.has("slope_threshold_deg"):
				if not _is_number(t["slope_threshold_deg"]) or float(t["slope_threshold_deg"]) < 0.0 or float(t["slope_threshold_deg"]) > 90.0:
					errors.append("terrain.slope_threshold_deg : doit être dans [0, 90]")
			if t.has("snow_line_m") and not _is_number(t["snow_line_m"]):
				errors.append("terrain.snow_line_m : doit être un nombre")
			if t.has("blend_sharpness"):
				if not _is_number(t["blend_sharpness"]) or float(t["blend_sharpness"]) <= 0.0:
					errors.append("terrain.blend_sharpness : doit être > 0")

	if data.has("road"):
		if typeof(data["road"]) != TYPE_DICTIONARY:
			errors.append("road : doit être un objet")
		else:
			var r: Dictionary = data["road"]
			if r.has("texture") and r["texture"] != null and typeof(r["texture"]) != TYPE_STRING:
				errors.append("road.texture : doit être une chaîne ou null")
			if r.has("color") and not _is_hex_color(r["color"]):
				errors.append("road.color : couleur hexadécimale #RRGGBB invalide")
			if r.has("width_m"):
				if not _is_number(r["width_m"]) or float(r["width_m"]) <= 0.0:
					errors.append("road.width_m : doit être > 0")

	if data.has("buildings"):
		if typeof(data["buildings"]) != TYPE_DICTIONARY:
			errors.append("buildings : doit être un objet")
		else:
			var b: Dictionary = data["buildings"]
			for arr_key in ["walls", "roofs"]:
				if b.has(arr_key):
					if typeof(b[arr_key]) != TYPE_ARRAY:
						errors.append("buildings." + arr_key + " : doit être un tableau")
					else:
						for item in b[arr_key]:
							if not _is_hex_color(item):
								errors.append("buildings." + arr_key + " : couleur #RRGGBB invalide")

	if data.has("vegetation"):
		if typeof(data["vegetation"]) != TYPE_DICTIONARY:
			errors.append("vegetation : doit être un objet")
		else:
			var v: Dictionary = data["vegetation"]
			if v.has("treeline_m") and not _is_number(v["treeline_m"]):
				errors.append("vegetation.treeline_m : doit être un nombre")
			if v.has("max_density_per_ha"):
				if not _is_number(v["max_density_per_ha"]) or float(v["max_density_per_ha"]) < 0.0:
					errors.append("vegetation.max_density_per_ha : doit être >= 0")

	if data.has("sky"):
		if typeof(data["sky"]) != TYPE_DICTIONARY:
			errors.append("sky : doit être un objet")
		else:
			var sk: Dictionary = data["sky"]
			if sk.has("sun_elevation_deg"):
				if not _is_number(sk["sun_elevation_deg"]) or float(sk["sun_elevation_deg"]) < -90.0 or float(sk["sun_elevation_deg"]) > 90.0:
					errors.append("sky.sun_elevation_deg : doit être dans [-90, 90]")
			if sk.has("fog_density"):
				if not _is_number(sk["fog_density"]) or float(sk["fog_density"]) < 0.0:
					errors.append("sky.fog_density : doit être >= 0")


static func _resolve_tex_path(theme_dir: String, rel_path: String) -> String:
	var base := ProjectSettings.globalize_path(theme_dir).simplify_path()
	var full := base.path_join(rel_path).simplify_path()
	if not full.begins_with(base + "/") and full != base:
		return ""
	return full


static func _check_texture_field(
	theme_dir: String,
	field_name: String,
	tex_val: Variant,
	warnings: PackedStringArray
) -> void:
	if tex_val == null or typeof(tex_val) != TYPE_STRING:
		return
	var s: String = tex_val
	if s.strip_edges() == "":
		warnings.append(field_name + " : chemin de texture vide")
		return
	var full := _resolve_tex_path(theme_dir, s)
	if full == "":
		warnings.append(field_name + " : texture hors du dossier du thème (" + s + ")")
		return
	if not FileAccess.file_exists(full):
		warnings.append(field_name + " : fichier texture absent (" + s + "), repli sur la couleur unie")
		return
	var info := _read_image_dimensions(full)
	if not bool(info.get("ok", false)):
		warnings.append(field_name + " : fichier texture (" + s + ") n'est pas un PNG ou JPEG valide")
		return
	var w := int(info["width"])
	var h := int(info["height"])
	if not (_is_power_of_two(w) and _is_power_of_two(h)):
		warnings.append("%s : dimensions %dx%d non puissances de 2 (%s)" % [field_name, w, h, s])


static func _deep_merge(base: Dictionary, override: Dictionary) -> Dictionary:
	var out := base.duplicate(true)
	for key in override.keys():
		var val = override[key]
		if typeof(val) == TYPE_DICTIONARY and out.has(key) and typeof(out[key]) == TYPE_DICTIONARY:
			out[key] = _deep_merge(out[key], val)
		elif typeof(val) == TYPE_ARRAY or typeof(val) == TYPE_DICTIONARY:
			out[key] = val.duplicate(true)
		else:
			out[key] = val
	return out


## Charge et valide un dossier de thème.
## Renvoie {"theme": Dictionary complet, "warnings": PackedStringArray, "errors": PackedStringArray}.
static func load_theme(theme_dir: String) -> Dictionary:
	var default_theme := _load_default_dict()
	var warnings := PackedStringArray()
	var errors := PackedStringArray()

	if not DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(theme_dir)):
		errors.append("dossier de thème introuvable : " + theme_dir)
		print("[theme] erreur : ", errors[0], " ; repli sur default")
		return {"theme": default_theme, "warnings": warnings, "errors": errors}

	var theme_file := theme_dir.path_join("theme.json")
	if not FileAccess.file_exists(theme_file):
		errors.append("theme.json absent dans " + theme_dir)
		print("[theme] erreur : ", errors[0], " ; repli sur default")
		return {"theme": default_theme, "warnings": warnings, "errors": errors}

	var text := FileAccess.get_file_as_string(theme_file)
	var json := JSON.new()
	var parse_err := json.parse(text)
	var data = json.data if parse_err == OK else null
	if typeof(data) != TYPE_DICTIONARY:
		errors.append("theme.json illisible ou non objet JSON dans " + theme_dir)
		print("[theme] erreur : ", errors[0], " ; repli sur default")
		return {"theme": default_theme, "warnings": warnings, "errors": errors}

	var dict_data: Dictionary = data
	_validate_schema(dict_data, errors)
	_warn_unknown_keys(dict_data, default_theme, "", warnings)

	if dict_data.has("terrain") and typeof(dict_data["terrain"]) == TYPE_DICTIONARY:
		var t: Dictionary = dict_data["terrain"]
		for layer_name in ["grass", "rock", "snow"]:
			if t.has(layer_name) and typeof(t[layer_name]) == TYPE_DICTIONARY:
				var layer: Dictionary = t[layer_name]
				if layer.has("texture"):
					_check_texture_field(theme_dir, "terrain." + layer_name + ".texture", layer["texture"], warnings)

	if dict_data.has("road") and typeof(dict_data["road"]) == TYPE_DICTIONARY:
		var r: Dictionary = dict_data["road"]
		if r.has("texture"):
			_check_texture_field(theme_dir, "road.texture", r["texture"], warnings)

	if errors.size() > 0:
		print("[theme] thème invalide (", theme_dir, ") : ", errors[0], " ; repli sur default")
		return {"theme": default_theme, "warnings": warnings, "errors": errors}

	var merged := _deep_merge(default_theme, dict_data)
	return {"theme": merged, "warnings": warnings, "errors": errors}


## Charge un thème par son nom de configuration : ~/OpenRide/Themes/<name>/, sinon res://themes/default/.
static func load_named(name: String) -> Dictionary:
	var clean := name.strip_edges()
	if clean == "" or clean == "default":
		var user_default := _themes_base_dir().path_join("default")
		if DirAccess.dir_exists_absolute(user_default) and FileAccess.file_exists(user_default.path_join("theme.json")):
			return load_theme(user_default)
		return load_theme(DEFAULT_THEME_DIR)

	var candidate := _themes_base_dir().path_join(clean)
	if DirAccess.dir_exists_absolute(candidate):
		return load_theme(candidate)

	var res := load_theme(DEFAULT_THEME_DIR)
	var warnings: PackedStringArray = res["warnings"]
	warnings.append("thème introuvable : " + clean + " (" + candidate + "), repli sur default")
	res["warnings"] = warnings
	print("[theme] avertissement : ", warnings[warnings.size() - 1])
	return res


## Renvoie la Texture2D associée à un chemin de matériau (ex. "terrain.grass" ou "road.texture"),
## ou null si la texture est absente / null / invalide (l'appelant utilise alors la couleur unie).
static func texture_for(theme: Dictionary, theme_dir: String, key_path: String) -> Texture2D:
	var parts := key_path.split(".", false)
	var cur: Variant = theme
	for p in parts:
		if typeof(cur) == TYPE_DICTIONARY and (cur as Dictionary).has(p):
			cur = (cur as Dictionary)[p]
		else:
			return null

	var rel_tex: Variant = cur
	if typeof(cur) == TYPE_DICTIONARY:
		rel_tex = (cur as Dictionary).get("texture", null)

	if rel_tex == null or typeof(rel_tex) != TYPE_STRING:
		return null
	var s: String = rel_tex
	if s.strip_edges() == "":
		return null

	var full := _resolve_tex_path(theme_dir, s)
	if full == "" or not FileAccess.file_exists(full):
		return null

	var info := _read_image_dimensions(full)
	if not bool(info.get("ok", false)):
		return null

	var img := Image.load_from_file(full)
	if img == null or img.is_empty():
		return null
	return ImageTexture.create_from_image(img)
