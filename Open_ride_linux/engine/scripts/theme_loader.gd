extends RefCounted

## Chargeur et validateur de thèmes visuels OpenRide (Lot I5, Format .world v1 §9).
##
## Même logique que `compiler/src/openride_compiler/theme.py` (Lot H7) :
## - fusion récursive avec `res://themes/default/theme.json` (source unique des valeurs par défaut) ;
## - erreurs (JSON mal formé, version non supportée, couleur mal formée, valeur hors bornes) ->
##   repli complet sur le thème `default` ;
## - avertissements (clé inconnue, texture absente ou non puissance de 2) -> repli de la texture
##   sur la couleur unie `color`.
## Thème 2.0 (lot U1, pack de biomes) : `default_biome`, `biomes`, `variants` et `surfaces` validés ici ;
## les clés 1.x gardent leur sens et servent de valeurs aux biomes qui ne les donnent pas (biome_model.gd).
## Pas de class_name : charger par preload("res://scripts/theme_loader.gd").

const BiomeIds := preload("res://scripts/biome_ids.gd")
const TextureLevels := preload("res://scripts/texture_levels.gd")

const DEFAULT_THEME_DIR := "res://themes/default"
const DEFAULT_THEME_PATH := "res://themes/default/theme.json"
## Textures 1.x du thème (terrain et route), comptées pour le budget de mémoire vidéo du lot P20.
const DECOR_TEXTURES: Array[String] = ["terrain.grass", "terrain.rock", "terrain.snow", "road.texture"]


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
	if not (s.begins_with("1.") or s.begins_with("2.")) or s.length() < 3:
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

	if data.has("texture_levels"):
		_validate_texture_levels(data["texture_levels"], errors)

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


## Niveaux de textures du pack (lot P20) : [{name, max_px puissance de 2, dir relatif au thème}], noms et
## côtés distincts.
static func _validate_texture_levels(v: Variant, errors: PackedStringArray) -> void:
	if typeof(v) != TYPE_ARRAY:
		errors.append("texture_levels : doit être un tableau")
		return
	var names := {}
	var sizes := {}
	for i in range((v as Array).size()):
		var l = v[i]
		var label := "texture_levels[%d]" % i
		if typeof(l) != TYPE_DICTIONARY:
			errors.append(label + " : doit être un objet")
			continue
		if typeof(l.get("name", null)) != TYPE_STRING or str(l["name"]) == "" or names.has(l["name"]):
			errors.append(label + ".name : chaîne non vide, distincte des autres niveaux")
		else:
			names[l["name"]] = true
		var px = l.get("max_px", null)
		if not _is_number(px) or float(px) != floorf(float(px)) or not _is_power_of_two(int(px)) or int(px) < 64 or int(px) > 8192 or sizes.has(int(px)):
			errors.append(label + ".max_px : puissance de 2 entre 64 et 8 192, distincte des autres niveaux")
		else:
			sizes[int(px)] = true
		var d = l.get("dir", null)
		if typeof(d) != TYPE_STRING or str(d).strip_edges() == "" or str(d).begins_with("/") or ".." in str(d).split("/"):
			errors.append(label + ".dir : dossier relatif au thème, sans « .. »")


## Clés du thème 2.0 absentes du thème par défaut tant qu'il est en 1.x.
const V2_KEYS := ["default_biome", "biomes", "variants", "surfaces"]


static func _is_v2(data: Dictionary) -> bool:
	return typeof(data.get("version", null)) == TYPE_STRING and str(data["version"]).begins_with("2.")


static func _check_color_key(d: Dictionary, key: String, label: String, errors: PackedStringArray) -> void:
	if d.has(key) and not _is_hex_color(d[key]):
		errors.append(label + "." + key + " : couleur hexadécimale #RRGGBB invalide")


static func _check_unit_key(d: Dictionary, key: String, label: String, errors: PackedStringArray) -> void:
	if d.has(key) and (not _is_number(d[key]) or float(d[key]) < 0.0 or float(d[key]) > 1.0):
		errors.append(label + "." + key + " : doit être dans [0, 1]")


static func _validate_biome(b: Variant, label: String, errors: PackedStringArray) -> void:
	if typeof(b) != TYPE_DICTIONARY:
		errors.append(label + " : doit être un objet")
		return
	var bd: Dictionary = b
	if typeof(bd.get("ground", null)) == TYPE_DICTIONARY:
		var g: Dictionary = bd["ground"]
		if g.has("layers"):
			if typeof(g["layers"]) != TYPE_ARRAY or (g["layers"] as Array).is_empty() or (g["layers"] as Array).size() > 3:
				errors.append(label + ".ground.layers : de 1 à 3 couches")
			else:
				var roles := []
				for layer in g["layers"]:
					if typeof(layer) != TYPE_DICTIONARY or not BiomeIds.GROUND_ROLES.has(layer.get("role", "")):
						errors.append(label + ".ground.layers : role flat, steep ou high obligatoire")
						continue
					if roles.has(layer["role"]):
						errors.append(label + ".ground.layers : role " + str(layer["role"]) + " en double")
					roles.append(layer["role"])
					_validate_surface_layer(layer, label + ".ground." + str(layer["role"]), errors)
					if not layer.has("color"):
						errors.append(label + ".ground." + str(layer["role"]) + ".color : obligatoire")
		if g.has("slope_threshold_deg") and (not _is_number(g["slope_threshold_deg"]) or float(g["slope_threshold_deg"]) < 0.0 or float(g["slope_threshold_deg"]) > 90.0):
			errors.append(label + ".ground.slope_threshold_deg : doit être dans [0, 90]")
		if g.has("high_line_m") and g["high_line_m"] != null and not _is_number(g["high_line_m"]):
			errors.append(label + ".ground.high_line_m : nombre ou null")
	elif bd.has("ground"):
		errors.append(label + ".ground : doit être un objet")
	if typeof(bd.get("vegetation", null)) == TYPE_DICTIONARY:
		var v: Dictionary = bd["vegetation"]
		if v.has("species"):
			if typeof(v["species"]) != TYPE_ARRAY:
				errors.append(label + ".vegetation.species : doit être un tableau")
			else:
				for sp in v["species"]:
					if typeof(sp) != TYPE_DICTIONARY or not BiomeIds.SPECIES.has(sp.get("kind", "")):
						errors.append(label + ".vegetation.species : espèce inconnue " + str(sp))
					elif not _is_number(sp.get("weight", null)) or float(sp["weight"]) <= 0.0:
						errors.append(label + ".vegetation.species : weight > 0 obligatoire")
		if v.has("max_density_per_ha") and (not _is_number(v["max_density_per_ha"]) or float(v["max_density_per_ha"]) < 0.0):
			errors.append(label + ".vegetation.max_density_per_ha : doit être >= 0")
		if v.has("treeline_m") and v["treeline_m"] != null and not _is_number(v["treeline_m"]):
			errors.append(label + ".vegetation.treeline_m : nombre ou null")
	if typeof(bd.get("water", null)) == TYPE_DICTIONARY:
		_check_color_key(bd["water"], "color", label + ".water", errors)
		_check_unit_key(bd["water"], "turbidity", label + ".water", errors)
	if typeof(bd.get("sky", null)) == TYPE_DICTIONARY:
		var sk: Dictionary = bd["sky"]
		_check_color_key(sk, "light_tint", label + ".sky", errors)
		_check_unit_key(sk, "haze", label + ".sky", errors)
		if sk.has("fog_density") and (not _is_number(sk["fog_density"]) or float(sk["fog_density"]) < 0.0):
			errors.append(label + ".sky.fog_density : doit être >= 0")
	if typeof(bd.get("seasons", null)) == TYPE_DICTIONARY:
		var se: Dictionary = bd["seasons"]
		if se.has("calendar") and not BiomeIds.CALENDARS.has(se["calendar"]):
			errors.append(label + ".seasons.calendar : four, wet_dry, polar ou none")


## Clés du thème 2.0 (Format .world v1 §9, lot U1).
static func _validate_v2(data: Dictionary, errors: PackedStringArray) -> void:
	if data.has("default_biome") and not BiomeIds.is_biome(data["default_biome"]):
		errors.append("default_biome : biome inconnu " + str(data["default_biome"]))
	if data.has("biomes"):
		if typeof(data["biomes"]) != TYPE_DICTIONARY:
			errors.append("biomes : doit être un objet")
		else:
			for id in data["biomes"].keys():
				if not BiomeIds.is_biome(id):
					errors.append("biomes : biome inconnu " + str(id))
				else:
					_validate_biome(data["biomes"][id], "biomes." + str(id), errors)
	if data.has("variants"):
		if typeof(data["variants"]) != TYPE_DICTIONARY:
			errors.append("variants : doit être un objet")
		else:
			for id in data["variants"].keys():
				if not (BiomeIds.GROUND_VARIANTS.has(id) or BiomeIds.ROOF_VARIANTS.has(id)):
					errors.append("variants : variante inconnue " + str(id))
					continue
				var va = data["variants"][id]
				if typeof(va) != TYPE_DICTIONARY:
					errors.append("variants." + str(id) + " : doit être un objet")
					continue
				_check_color_key(va, "rock_color", "variants." + str(id), errors)
				_check_color_key(va, "soil_color", "variants." + str(id), errors)
				for arr_key in ["walls", "roofs"]:
					if va.has(arr_key):
						if typeof(va[arr_key]) != TYPE_ARRAY:
							errors.append("variants." + str(id) + "." + arr_key + " : doit être un tableau")
						else:
							for item in va[arr_key]:
								if not _is_hex_color(item):
									errors.append("variants." + str(id) + "." + arr_key + " : couleur #RRGGBB invalide")
	if data.has("surfaces"):
		if typeof(data["surfaces"]) != TYPE_DICTIONARY:
			errors.append("surfaces : doit être un objet")
		else:
			for id in data["surfaces"].keys():
				if not BiomeIds.SURFACES.has(id):
					errors.append("surfaces : surface inconnue " + str(id))
				elif typeof(data["surfaces"][id]) != TYPE_DICTIONARY:
					errors.append("surfaces." + str(id) + " : doit être un objet")
				else:
					_check_color_key(data["surfaces"][id], "color", "surfaces." + str(id), errors)


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
		return {"theme": default_theme, "warnings": warnings, "errors": errors, "theme_dir": DEFAULT_THEME_DIR}

	var theme_file := theme_dir.path_join("theme.json")
	if not FileAccess.file_exists(theme_file):
		errors.append("theme.json absent dans " + theme_dir)
		print("[theme] erreur : ", errors[0], " ; repli sur default")
		return {"theme": default_theme, "warnings": warnings, "errors": errors, "theme_dir": DEFAULT_THEME_DIR}

	var text := FileAccess.get_file_as_string(theme_file)
	var json := JSON.new()
	var parse_err := json.parse(text)
	var data = json.data if parse_err == OK else null
	if typeof(data) != TYPE_DICTIONARY:
		errors.append("theme.json illisible ou non objet JSON dans " + theme_dir)
		print("[theme] erreur : ", errors[0], " ; repli sur default")
		return {"theme": default_theme, "warnings": warnings, "errors": errors, "theme_dir": DEFAULT_THEME_DIR}

	var dict_data: Dictionary = data
	_validate_schema(dict_data, errors)
	var reference := default_theme
	if _is_v2(dict_data):
		_validate_v2(dict_data, errors)
		reference = default_theme.duplicate()
		for key in V2_KEYS:
			if dict_data.has(key):
				reference[key] = dict_data[key]
	_warn_unknown_keys(dict_data, reference, "", warnings)

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

	if errors.is_empty() and _is_v2(dict_data) and typeof(dict_data.get("biomes", null)) == TYPE_DICTIONARY:
		for id in dict_data["biomes"].keys():
			var ground = dict_data["biomes"][id].get("ground", {})
			if typeof(ground) != TYPE_DICTIONARY or typeof(ground.get("layers", null)) != TYPE_ARRAY:
				continue
			for layer in ground["layers"]:
				for field in ["texture", "normal"]:
					if layer.has(field):
						_check_texture_field(theme_dir, "biomes.%s.ground.%s.%s" % [id, layer["role"], field], layer[field], warnings)

	if errors.size() > 0:
		print("[theme] thème invalide (", theme_dir, ") : ", errors[0], " ; repli sur default")
		return {"theme": default_theme, "warnings": warnings, "errors": errors, "theme_dir": DEFAULT_THEME_DIR}

	# Le pack de biomes du thème par défaut n'est jamais prêté à un autre thème : un thème 1.x décrit
	# tous les biomes, et un biome absent d'un thème 2.0 prend ses clés 1.x (Format .world v1 §9).
	var base := default_theme
	if ProjectSettings.globalize_path(theme_dir).simplify_path() != ProjectSettings.globalize_path(DEFAULT_THEME_DIR).simplify_path():
		base = without_biomes(default_theme)
	var merged := _deep_merge(base, dict_data)
	return {"theme": merged, "warnings": warnings, "errors": errors, "theme_dir": theme_dir}


## Thème sans ses clés 2.0 (`default_biome`, `biomes`, `variants`, `surfaces`).
static func without_biomes(theme: Dictionary) -> Dictionary:
	var out := theme.duplicate(true)
	for key in V2_KEYS:
		out.erase(key)
	return out


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
## `choice` : niveau des textures retenu par TextureLevels.choose (lot P20) : fichier cherché dans le dossier
## du niveau, puis des niveaux inférieurs, puis à la racine, et image réduite au côté du niveau ; px = 0 :
## couleurs unies (budget de mémoire vidéo). Vide : racine du thème, taille du fichier.
static func texture_for(theme: Dictionary, theme_dir: String, key_path: String, choice: Dictionary = {}) -> Texture2D:
	var s := texture_path(theme, key_path)
	if s == "" or (not choice.is_empty() and int(choice.get("px", 0)) <= 0):
		return null

	var full := TextureLevels.resolve(theme_dir, s, choice) if not choice.is_empty() else _resolve_tex_path(theme_dir, s)
	if full == "" or not FileAccess.file_exists(full):
		return null

	var info := _read_image_dimensions(full)
	if not bool(info.get("ok", false)):
		return null

	var img := Image.load_from_file(full)
	if img == null or img.is_empty():
		return null
	var px := int(choice.get("px", 0))
	if px > 0 and (img.get_width() > px or img.get_height() > px):
		if img.is_compressed():
			img.decompress()
		img.resize(mini(img.get_width(), px), mini(img.get_height(), px), Image.INTERPOLATE_LANCZOS)
	# Sans mipmaps, le filtrage anisotrope du shader n'a rien à lire : scintillement au loin
	# et lectures de texture coûteuses sur les tuiles lointaines.
	if not img.has_mipmaps():
		img.generate_mipmaps()
	return ImageTexture.create_from_image(img)


## Chemin relatif de la texture d'un matériau (ex. "terrain.grass" ou "road.texture") ; "" sans texture.
static func texture_path(theme: Dictionary, key_path: String) -> String:
	var cur: Variant = theme
	for p in key_path.split(".", false):
		if typeof(cur) == TYPE_DICTIONARY and (cur as Dictionary).has(p):
			cur = (cur as Dictionary)[p]
		else:
			return ""
	if typeof(cur) == TYPE_DICTIONARY:
		cur = (cur as Dictionary).get("texture", null)
	if cur == null or typeof(cur) != TYPE_STRING:
		return ""
	return (cur as String).strip_edges()


static func decor_texture_count(theme: Dictionary) -> int:
	var n := 0
	for k in DECOR_TEXTURES:
		if texture_path(theme, k) != "":
			n += 1
	return n
