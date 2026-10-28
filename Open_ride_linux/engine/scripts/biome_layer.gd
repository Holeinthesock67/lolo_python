extends RefCounted

## Lecture de la couche `biome` d'un parcours (Format .world v1 §8 quater, depuis 1.6, lot U5).
## Tuiles `biome/near/tile_<ix>_<iz>.json` (1 000 m) et `biome/far/tile_<ix>_<iz>.json` (5 000 m),
## mêmes indices que le terrain. Validation légère, cache par tuile ; une tuile absente ou invalide
## vaut `{}` (l'appelant prend alors le biome par défaut).
## Une tuile chargée : {"biomes": Array[String], "weights": Array[PackedFloat32Array] (poids / 255),
## "variant": Dictionary ou null}.
## Pas de class_name : charger par preload("res://scripts/biome_layer.gd").

const BiomeIds := preload("res://scripts/biome_ids.gd")

const GRID := 17
const POINTS := GRID * GRID
const LEVELS := {
	"near": {"dir": "near", "size_m": 1000.0},
	"far": {"dir": "far", "size_m": 5000.0},
}

var world_dir := ""
var present := false
var default_biome := BiomeIds.DEFAULT_BIOME
var _cache := {}
var _mutex := Mutex.new()   # tuiles lues depuis les fils de préparation (arbres, faune)
var warnings := PackedStringArray()


## `manifest` : manifeste du parcours ; sans `layers.biome.present`, la couche est muette.
func _init(dir: String = "", manifest: Dictionary = {}) -> void:
	world_dir = dir
	var layer = manifest.get("layers", {}).get("biome", {}) if typeof(manifest.get("layers", null)) == TYPE_DICTIONARY else {}
	if typeof(layer) == TYPE_DICTIONARY:
		present = bool(layer.get("present", false)) and dir != ""
		if BiomeIds.is_biome(layer.get("default_biome", null)):
			default_biome = layer["default_biome"]


static func tile_path(dir: String, level: String, ix: int, iz: int) -> String:
	return dir.path_join("biome").path_join(LEVELS[level]["dir"]).path_join("tile_%d_%d.json" % [ix, iz])


## Contrôle d'une tuile lue en JSON ; renvoie la tuile prête à l'emploi, ou {} et une ligne dans `errors`.
static func parse_tile(data: Variant, errors: PackedStringArray) -> Dictionary:
	if typeof(data) != TYPE_DICTIONARY:
		errors.append("tuile de biome : objet JSON attendu")
		return {}
	var biomes = data.get("biomes", null)
	var weights = data.get("weights", null)
	if typeof(biomes) != TYPE_ARRAY or (biomes as Array).is_empty() or (biomes as Array).size() > 4:
		errors.append("tuile de biome : de 1 à 4 biomes")
		return {}
	for id in biomes:
		if not BiomeIds.is_biome(id):
			errors.append("tuile de biome : biome inconnu " + str(id))
			return {}
	if int(data.get("grid", 0)) != GRID or typeof(weights) != TYPE_ARRAY or (weights as Array).size() != (biomes as Array).size():
		errors.append("tuile de biome : une grille 17 × 17 par biome")
		return {}
	var grids: Array[PackedFloat32Array] = []
	var sums := PackedInt32Array()
	sums.resize(POINTS)
	for grid in weights:
		if typeof(grid) != TYPE_ARRAY or (grid as Array).size() != POINTS:
			errors.append("tuile de biome : 289 poids par biome")
			return {}
		var g := PackedFloat32Array()
		g.resize(POINTS)
		for p in range(POINTS):
			var w := int(grid[p])
			sums[p] += w
			g[p] = float(w) / 255.0
		grids.append(g)
	for p in range(POINTS):
		if sums[p] != 255:
			errors.append("tuile de biome : somme %d au point %d au lieu de 255" % [sums[p], p])
			return {}
	var biome_names: Array[String] = []
	for id in biomes:
		biome_names.append(str(id))
	var variant = data.get("variant", null)
	return {"biomes": biome_names, "weights": grids, "variant": variant if typeof(variant) == TYPE_DICTIONARY else null}


## Tuile `(ix, iz)` du niveau `near` ou `far`, en cache ; {} si absente ou invalide.
func tile(level: String, ix: int, iz: int) -> Dictionary:
	var key := Vector3i(ix, iz, 0 if level == "near" else 1)
	_mutex.lock()
	if _cache.has(key):
		var cached: Dictionary = _cache[key]
		_mutex.unlock()
		return cached
	var out := {}
	if present:
		var path := tile_path(world_dir, level, ix, iz)
		if FileAccess.file_exists(path):
			var errors := PackedStringArray()
			out = parse_tile(JSON.parse_string(FileAccess.get_file_as_string(path)), errors)
			for e in errors:
				warnings.append(path.get_file() + " : " + e)
				print("[biome] ", path.get_file(), " ignorée : ", e)
	_cache[key] = out
	_mutex.unlock()
	return out


## Injecte une tuile déjà construite (tests, parcours générés en mémoire).
func put_tile(level: String, ix: int, iz: int, t: Dictionary) -> void:
	present = true
	_mutex.lock()
	_cache[Vector3i(ix, iz, 0 if level == "near" else 1)] = t
	_mutex.unlock()
