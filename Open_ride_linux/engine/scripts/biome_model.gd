extends RefCounted

## Modèle de biome sans nœud ni affichage (lot U5, série U, Format .world v1 §8 quater et §9).
## Répond pour tout point du monde : quels biomes, avec quels poids, et quels paramètres de rendu
## (sol, végétation, eau, ciel, ambiance, faune, saisons). Les lots de rendu U6 à U14 s'appuient sur lui.
## - `weights_at(x, z)` : interpolation bilinéaire dans la grille 17 × 17 de la tuile proche (sinon
##   lointaine), somme ramenée à 1 ; sans couche biome, biome par défaut ;
## - `top_biomes(ix, iz, max_n)` : les `max_n` biomes les plus présents d'une tuile proche, renormalisés ;
## - forçage : `forced` (argument `--biome=`, puis `hello_ack.config.biome` avec le lot U16) remplace tous les poids ;
## - `params(biome, season, progress, variant)` : paramètres du thème 2.0, repli sur les clés 1.x ;
##   un thème 1.x donne donc à tous les biomes les paramètres d'aujourd'hui. Saisons : valeurs neutres
##   tant que P18 et le lot U13 ne sont pas là ;
## - `blend(weights, params_by_biome)` : mélange numérique des couleurs et des densités en un point.
## Pas de class_name : charger par preload("res://scripts/biome_model.gd").

const BiomeIds := preload("res://scripts/biome_ids.gd")
const BiomeLayer := preload("res://scripts/biome_layer.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")

const NEAR_M := 1000.0
const FAR_M := 5000.0
const CELLS := 16
const NO_HIGH_LINE_M := 100000.0
const DEFAULT_WATER_HEX := "#1f5261"   # water_mesh.gd WATER_COLOR
const DEFAULT_TURBIDITY := 0.3
const DEFAULT_SEASONS := {"calendar": "four", "offset_months": 0, "durations_months": [3, 3, 3, 3]}

var theme: Dictionary
var layer
var forced := ""
var _params_cache := {}
var _mutex := Mutex.new()   # params() appelé depuis les fils de préparation


func _init(theme_dict: Dictionary = {}, biome_layer = null) -> void:
	theme = theme_dict
	layer = biome_layer if biome_layer != null else BiomeLayer.new()


## Biome par défaut : manifeste du parcours s'il a une couche biome, sinon `default_biome` du thème.
func default_biome() -> String:
	if layer.present:
		return layer.default_biome
	var d = theme.get("default_biome", null)
	return d if BiomeIds.is_biome(d) else BiomeIds.DEFAULT_BIOME


## Force un biome sur tout le parcours ; "" ou "auto" rend la main aux données. Renvoie faux si inconnu.
func set_forced(id: String) -> bool:
	if id == "" or id == "auto":
		forced = ""
		return true
	if not BiomeIds.is_biome(id):
		return false
	forced = id
	return true


## Vrai quand le rendu doit suivre les biomes (couche présente ou forçage) ; faux = rendu d'avant la 3.0.
func active() -> bool:
	return forced != "" or layer.present


static func _bilinear(g: PackedFloat32Array, i0: int, j0: int, fu: float, fv: float) -> float:
	var p := j0 * 17 + i0
	var top := g[p] + (g[p + 1] - g[p]) * fu
	var bottom := g[p + 17] + (g[p + 18] - g[p + 17]) * fu
	return top + (bottom - top) * fv


## Poids de chaque biome au point (x, z) du monde, de somme 1.
func weights_at(x: float, z: float) -> Dictionary:
	if forced != "":
		return {forced: 1.0}
	if not layer.present:
		return {default_biome(): 1.0}
	var size := NEAR_M
	var ix := floori(x / NEAR_M)
	var iz := floori(z / NEAR_M)
	var t: Dictionary = layer.tile("near", ix, iz)
	if t.is_empty():
		size = FAR_M
		ix = floori(x / FAR_M)
		iz = floori(z / FAR_M)
		t = layer.tile("far", ix, iz)
		if t.is_empty():
			return {default_biome(): 1.0}
	var u := (x - ix * size) / size * CELLS
	var v := (z - iz * size) / size * CELLS
	var i0 := clampi(floori(u), 0, CELLS - 1)
	var j0 := clampi(floori(v), 0, CELLS - 1)
	var fu := clampf(u - i0, 0.0, 1.0)
	var fv := clampf(v - j0, 0.0, 1.0)
	var out := {}
	var total := 0.0
	var biomes: Array[String] = t["biomes"]
	var grids: Array[PackedFloat32Array] = t["weights"]
	for b in range(biomes.size()):
		var w := _bilinear(grids[b], i0, j0, fu, fv)
		if w > 0.0:
			out[biomes[b]] = w
			total += w
	if total <= 0.0:
		return {default_biome(): 1.0}
	for k in out.keys():
		out[k] = out[k] / total
	return out


## Les `max_n` biomes les plus présents de la tuile proche (ix, iz), parts renormalisées à 1
## (3 en `low`, 4 sinon : `QualityPresets.max_biomes`). Ordre décroissant des parts.
func top_biomes(ix: int, iz: int, max_n: int) -> Dictionary:
	if forced != "":
		return {forced: 1.0}
	var t: Dictionary = layer.tile("near", ix, iz) if layer.present else {}
	if t.is_empty():
		return {default_biome(): 1.0}
	var shares := []
	var biomes: Array[String] = t["biomes"]
	var grids: Array[PackedFloat32Array] = t["weights"]
	for b in range(biomes.size()):
		var s := 0.0
		for w in grids[b]:
			s += w
		if s > 0.0:
			shares.append([s, biomes[b]])
	shares.sort_custom(func(a, b): return a[0] > b[0] or (a[0] == b[0] and a[1] < b[1]))
	shares = shares.slice(0, maxi(max_n, 1))
	var total := 0.0
	for e in shares:
		total += e[0]
	var out := {}
	for e in shares:
		out[e[1]] = e[0] / total
	return out


func max_biomes(quality: String) -> int:
	return QualityPresets.max_biomes(quality)


static func _num(v: Variant) -> bool:
	return (typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT) and is_finite(float(v))


## Section `terrain` au format 1.x tirée de `ground` d'un biome (flat = herbe, steep = roche, high = neige).
func _terrain_dict(ground: Dictionary) -> Dictionary:
	var base: Dictionary = (theme.get("terrain", {}) as Dictionary).duplicate(true) if typeof(theme.get("terrain", null)) == TYPE_DICTIONARY else {}
	var names := {"flat": "grass", "steep": "rock", "high": "snow"}
	if typeof(ground.get("layers", null)) == TYPE_ARRAY:
		for l in ground["layers"]:
			if typeof(l) == TYPE_DICTIONARY and names.has(l.get("role", "")):
				base[names[l["role"]]] = l
	for key in ["slope_threshold_deg", "blend_sharpness"]:
		if _num(ground.get(key, null)):
			base[key] = ground[key]
	if ground.has("high_line_m"):
		base["snow_line_m"] = float(ground["high_line_m"]) if _num(ground["high_line_m"]) else NO_HIGH_LINE_M
	return base


## Section `terrain` au format 1.x du biome (pour TerrainMaterial tant que U6 n'est pas là, et pour les vitrines).
func terrain_theme(biome: String) -> Dictionary:
	var entry = theme.get("biomes", {}).get(biome, {}) if typeof(theme.get("biomes", null)) == TYPE_DICTIONARY else {}
	var ground = entry.get("ground", {}) if typeof(entry) == TYPE_DICTIONARY else {}
	return {"terrain": _terrain_dict(ground if typeof(ground) == TYPE_DICTIONARY else {})}


## Paramètres de rendu d'un biome pour une saison, l'avancée dans la saison (0 à 1) et une variante.
## Un biome absent du thème, ou une clé absente, prend la valeur 1.x du thème.
func params(biome: String, season: String = "", progress: float = 0.0, variant: Variant = null) -> Dictionary:
	var key := "%s|%s|%s" % [biome, season, str(variant)]
	_mutex.lock()
	var hit = _params_cache.get(key, null)
	_mutex.unlock()
	if hit != null:
		return hit
	var entry: Dictionary = {}
	if typeof(theme.get("biomes", null)) == TYPE_DICTIONARY and typeof(theme["biomes"].get(biome, null)) == TYPE_DICTIONARY:
		entry = theme["biomes"][biome]
	var ground: Dictionary = entry.get("ground", {}) if typeof(entry.get("ground", null)) == TYPE_DICTIONARY else {}
	var terrain := ThemeRenderParams.terrain_uniforms({"terrain": _terrain_dict(ground)})

	var veg_1x: Dictionary = theme.get("vegetation", {}) if typeof(theme.get("vegetation", null)) == TYPE_DICTIONARY else {}
	var veg_b: Dictionary = entry.get("vegetation", {}) if typeof(entry.get("vegetation", null)) == TYPE_DICTIONARY else {}
	var vegetation := {
		"species": (veg_b.get("species", []) as Array).duplicate(true) if typeof(veg_b.get("species", null)) == TYPE_ARRAY else [],
		# Faux : le biome ne donne pas d'espèces (thème 1.x ou biome absent) -> arbre d'avant la série U.
		"has_species": typeof(veg_b.get("species", null)) == TYPE_ARRAY,
		"max_density_per_ha": float(veg_b.get("max_density_per_ha", veg_1x.get("max_density_per_ha", 400.0))),
		"treeline_m": veg_b["treeline_m"] if veg_b.has("treeline_m") else veg_1x.get("treeline_m", 2000.0),
	}

	var water_b: Dictionary = entry.get("water", {}) if typeof(entry.get("water", null)) == TYPE_DICTIONARY else {}
	var water := {
		"color": ThemeRenderParams._color_or_default(water_b.get("color", null), DEFAULT_WATER_HEX),
		"turbidity": float(water_b.get("turbidity", DEFAULT_TURBIDITY)),
	}

	var sky_b: Dictionary = entry.get("sky", {}) if typeof(entry.get("sky", null)) == TYPE_DICTIONARY else {}
	var sky_theme := theme.duplicate()
	if sky_b.has("fog_density"):
		var s1: Dictionary = (theme.get("sky", {}) as Dictionary).duplicate() if typeof(theme.get("sky", null)) == TYPE_DICTIONARY else {}
		s1["fog_density"] = sky_b["fog_density"]
		sky_theme["sky"] = s1
	var sky := ThemeRenderParams.sky_params(sky_theme)
	sky["haze"] = float(sky_b.get("haze", 0.0))
	sky["light_tint"] = ThemeRenderParams._color_or_default(sky_b.get("light_tint", null), "#ffffff")

	var out := {
		"biome": biome,
		"terrain": terrain,
		"vegetation": vegetation,
		"water": water,
		"sky": sky,
		"ambience": (entry.get("ambience", theme.get("ambience", {})) as Dictionary).duplicate(true),
		"fauna": (entry.get("fauna", theme.get("fauna", {})) as Dictionary).duplicate(true),
		"seasons": (entry.get("seasons", DEFAULT_SEASONS) as Dictionary).duplicate(true),
		"season": season,
		"season_progress": clampf(progress, 0.0, 1.0),
		"variant": _variant_params(variant),
	}
	_mutex.lock()
	_params_cache[key] = out
	_mutex.unlock()
	return out


## Entrées `variants` du thème pour le couple {ground, roofs} d'une tuile ({} si aucune).
func _variant_params(variant: Variant) -> Dictionary:
	var out := {}
	if typeof(variant) != TYPE_DICTIONARY or typeof(theme.get("variants", null)) != TYPE_DICTIONARY:
		return out
	for part in ["ground", "roofs"]:
		var id = variant.get(part, null)
		if typeof(id) == TYPE_STRING and typeof(theme["variants"].get(id, null)) == TYPE_DICTIONARY:
			out[part] = {"id": id, "values": (theme["variants"][id] as Dictionary).duplicate(true)}
	return out


## Mélange en un point : couleurs et nombres pondérés par `weights` (somme 1), espèces cumulées
## (poids de l'espèce × poids du biome). `params_by_biome` : biome -> params(...).
static func blend(weights: Dictionary, params_by_biome: Dictionary) -> Dictionary:
	var colors := {"grass_color": Color(0, 0, 0, 0), "rock_color": Color(0, 0, 0, 0), "snow_color": Color(0, 0, 0, 0)}
	var nums := {"max_density_per_ha": 0.0, "fog_density": 0.0, "haze": 0.0, "turbidity": 0.0}
	var water := Color(0, 0, 0, 0)
	var tint := Color(0, 0, 0, 0)
	var species := {}
	for b in weights.keys():
		var w := float(weights[b])
		var p: Dictionary = params_by_biome[b]
		for c in colors.keys():
			colors[c] += p["terrain"][c] * w
		nums["max_density_per_ha"] += float(p["vegetation"]["max_density_per_ha"]) * w
		nums["fog_density"] += float(p["sky"]["fog_density"]) * w
		nums["haze"] += float(p["sky"]["haze"]) * w
		nums["turbidity"] += float(p["water"]["turbidity"]) * w
		water += p["water"]["color"] * w
		tint += p["sky"]["light_tint"] * w
		var sp_total := 0.0
		for sp in p["vegetation"]["species"]:
			sp_total += float(sp["weight"])
		for sp in p["vegetation"]["species"]:
			species[sp["kind"]] = float(species.get(sp["kind"], 0.0)) + float(sp["weight"]) / sp_total * w
	var out := nums.duplicate()
	for c in colors.keys():
		out[c] = colors[c]
	out["water_color"] = water
	out["light_tint"] = tint
	out["species"] = species
	return out
