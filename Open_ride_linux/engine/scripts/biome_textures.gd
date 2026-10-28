extends RefCounted

## Sols multi-biomes du terrain (lot U6, série U, Format .world v1 §9, décision U-Q4).
## - À la construction : matériau de base du shader terrain_biomes.gdshader pour tout le parcours, avec
##   la règle de pente et d'altitude (L3) et les trois couches de sol (herbe = `flat`, roche = `steep`,
##   neige = `high`) des 16 biomes, tirées de BiomeModel.terrain_theme (repli sur le thème 1.x) ;
## - textures : deux Texture2DArray (carte A = couleur et rugosité dans l'alpha, carte B = normale XY et
##   occlusion dans le bleu), une couche par sol texturé des biomes présents (`layers.biome.shares` du
##   manifeste, biome forcé, sinon tous), mipmaps, compression en mémoire vidéo quand elle est disponible ;
##   sol sans texture : couleur unie (tableaux d'une couche 1 × 1 quand aucun sol n'est texturé) ;
## - côté des textures : QualityPresets.ground_texture_px (1 024 px en low et medium, 2 048 en high),
##   plafonné par la mémoire vidéo estimée (`estimate_bytes` : tailles décompressées, mipmaps comprises,
##   règle de P20) sous BUDGET_BYTES (1 Go, U-Q4) : un niveau plus bas, puis couleurs unies, avec une
##   ligne de journal (`log_line`) ;
## - `tile_material(level, ix, iz)` : copie du matériau de base avec la texture de poids 17 × 17 de la
##   tuile (RGBA = les 3 biomes les plus présents en low, 4 sinon) et l'indice de chaque biome.
## Pas de class_name : charger par preload("res://scripts/biome_textures.gd").

const BiomeIds := preload("res://scripts/biome_ids.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const TerrainMaterial := preload("res://scripts/terrain_material.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const SHADER := preload("res://shaders/terrain_biomes.gdshader")

const GRID := 17
const MAX_LAYERS := 48                 # 16 biomes × 3 couches (terrain_biomes.gdshader MAX_LAYERS)
const BUDGET_BYTES := 1 << 30          # textures de sol du parcours (U-Q4)
const LEVELS_PX: Array[int] = [2048, 1024]
const ROLES: Array[String] = ["grass", "rock", "snow"]
## Paramètres réglés en cours de route sur le matériau du thème (ombre des nuages de P6, décor d'E3 et
## d'Y11), recopiés sur les matériaux des tuiles par `sync_from`.
const SHARED_PARAMS: Array[String] = [
	"cloud_shadow_enabled", "cloud_shadow_coverage", "cloud_shadow_offset", "cloud_shadow_altitude_m",
	"cloud_shadow_strength", "cloud_shadow_scale_m", "detail_strength", "grass_relief", "rock_facet_strength",
]

var model
var quality := ""
var material: ShaderMaterial
var texture_px := 0                    # 0 : couleurs unies
var estimated_bytes := 0
var compressed := false
var layers: Array[Dictionary] = []     # {color, inv_scale, texture, normal, a, b}
var biome_layers := {}                 # biome -> [herbe, roche, neige] (indices dans `layers`)
var log_line := ""
var _tile_materials: Array[ShaderMaterial] = []
var _shared := {}


func _init(biome_model, theme_dir: String = "", quality_name: String = "") -> void:
	model = biome_model
	quality = quality_name
	_collect_layers()
	var used := _textured_layers(theme_dir)
	var want := QualityPresets.ground_texture_px(quality)
	var choice := choose_size(used["a"].size() + used["b"].size(), want)
	texture_px = int(choice["px"])
	estimated_bytes = int(choice["bytes"])
	log_line = "[biomes] sols : %d couches, %d cartes texturées, %s, %.0f Mo estimés (%s)" % [layers.size(),
		used["a"].size() + used["b"].size(), ("%d px" % texture_px) if texture_px > 0 else "couleurs unies",
		estimated_bytes / 1048576.0, choice["reason"]]
	print(log_line)
	material = ShaderMaterial.new()
	material.shader = SHADER
	TerrainMaterial.apply_shared(material)
	_fill_material(used if texture_px > 0 else {"a": [], "b": []})


## Mémoire vidéo estimée de `maps` cartes de `px` × `px` (RGBA8 décompressé, mipmaps comprises : × 4/3).
static func estimate_bytes(maps: int, px: int) -> int:
	return int(float(maps) * px * px * 4.0 * 4.0 / 3.0)


## Côté retenu pour `maps` cartes : celui du préréglage s'il tient sous BUDGET_BYTES, sinon le niveau
## inférieur, sinon 0 (couleurs unies). {px, bytes, reason}.
static func choose_size(maps: int, preset_px: int) -> Dictionary:
	if maps == 0:
		return {"px": 0, "bytes": 0, "reason": "aucune texture de sol"}
	for px in LEVELS_PX:
		if px > preset_px:
			continue
		var bytes := estimate_bytes(maps, px)
		if bytes <= BUDGET_BYTES:
			return {"px": px, "bytes": bytes, "reason": "préréglage" if px == preset_px else "budget de 1 Go"}
	return {"px": 0, "bytes": 0, "reason": "budget de 1 Go dépassé même à %d px" % LEVELS_PX[-1]}


## Biomes dont les textures sont chargées : biome forcé, sinon parts du manifeste (et biome par défaut), sinon tous.
func biomes_in_use() -> Array[String]:
	var out: Array[String] = []
	if model.forced != "":
		out.append(model.forced)
		return out
	if model.layer.present and not model.layer.shares.is_empty():
		for id in BiomeIds.BIOMES:
			if float(model.layer.shares.get(id, 0.0)) > 0.0 or id == model.default_biome():
				out.append(id)
		return out
	return BiomeIds.BIOMES.duplicate()


func _collect_layers() -> void:
	var index := {}
	for b in BiomeIds.BIOMES:
		var t: Dictionary = model.terrain_theme(b)["terrain"]
		var u := ThemeRenderParams.terrain_uniforms({"terrain": t})
		var ids: Array[int] = []
		for r in ROLES:
			var sub: Dictionary = t.get(r, {}) if typeof(t.get(r, null)) == TYPE_DICTIONARY else {}
			var entry := {"color": u[r + "_color"], "inv_scale": float(u[r + "_inv_scale"]),
				"texture": u[r + "_texture"], "normal": ThemeRenderParams._tex_or_null(sub.get("normal", null)),
				"a": -1, "b": -1}
			var key := "%s|%f|%s|%s" % [(entry["color"] as Color).to_html(), entry["inv_scale"], str(entry["texture"]), str(entry["normal"])]
			if not index.has(key):
				index[key] = layers.size()
				layers.append(entry)
			ids.append(int(index[key]))
		biome_layers[b] = {"layers": ids, "rule": Vector4(float(u["slope_threshold_deg"]), float(u["snow_line_m"]),
			float(u["blend_sharpness"]), 0.0)}


## Images à charger des biomes en usage : {"a": [[couche, chemin]], "b": [[couche, chemin]]}.
func _textured_layers(theme_dir: String) -> Dictionary:
	var out := {"a": [], "b": []}
	if theme_dir == "":
		return out
	var seen := {}
	for b in biomes_in_use():
		for l in biome_layers[b]["layers"]:
			if seen.has(l):
				continue
			seen[l] = true
			for m in [["a", "texture"], ["b", "normal"]]:
				var rel = layers[l][m[1]]
				if typeof(rel) != TYPE_STRING:
					continue
				var full := ThemeLoader._resolve_tex_path(theme_dir, rel)
				if full != "" and FileAccess.file_exists(full):
					out[m[0]].append([l, full])
				else:
					push_warning("[biomes] texture de sol absente : " + str(rel))
	return out


func _fill_material(used: Dictionary) -> void:
	var rules: Array[Vector4] = []
	var ids: Array[Vector4] = []
	for b in BiomeIds.BIOMES:
		var bl: Dictionary = biome_layers[b]
		rules.append(bl["rule"])
		ids.append(Vector4(bl["layers"][0], bl["layers"][1], bl["layers"][2], 0.0))
	material.set_shader_parameter("biome_rule", rules)
	material.set_shader_parameter("biome_layers", ids)
	var arrays := {"a": _make_array(used["a"], "a", false), "b": _make_array(used["b"], "b", true)}
	var colors: Array[Vector4] = []
	var maps: Array[Vector4] = []
	for i in range(MAX_LAYERS):
		var l: Dictionary = layers[mini(i, layers.size() - 1)]
		var c: Color = l["color"]
		colors.append(Vector4(c.r, c.g, c.b, l["inv_scale"]))
		maps.append(Vector4(l["a"], l["b"], 0.0, 0.0))
	material.set_shader_parameter("layer_color", colors)
	material.set_shader_parameter("layer_maps", maps)
	material.set_shader_parameter("ground_a", arrays["a"])
	material.set_shader_parameter("ground_b", arrays["b"])


## Tableau de textures d'une sorte de carte ; écrit l'indice de chaque couche dans layers[l][kind].
func _make_array(items: Array, kind: String, normal_map: bool) -> Texture2DArray:
	var images: Array[Image] = []
	for it in items:
		var img := Image.load_from_file(it[1])
		if img == null or img.is_empty():
			push_warning("[biomes] texture de sol illisible : " + str(it[1]))
			continue
		if img.is_compressed():
			img.decompress()
		img.convert(Image.FORMAT_RGBA8)
		if img.get_width() != texture_px or img.get_height() != texture_px:
			img.resize(texture_px, texture_px, Image.INTERPOLATE_LANCZOS)
		img.generate_mipmaps(normal_map)
		layers[it[0]][kind] = images.size()
		images.append(img)
	if images.is_empty():
		var blank := Image.create(1, 1, false, Image.FORMAT_RGBA8)
		blank.fill(Color(0.5, 0.5, 1.0, 1.0) if normal_map else Color(1, 1, 1, 1))
		images.append(blank)
	else:
		var ok := true
		for img in images:
			ok = ok and img.compress(Image.COMPRESS_BPTC, Image.COMPRESS_SOURCE_NORMAL if normal_map else Image.COMPRESS_SOURCE_GENERIC) == OK
		if not ok:
			for img in images:
				if img.is_compressed():
					img.decompress()
		compressed = ok
	var arr := Texture2DArray.new()
	arr.create_from_images(images)
	return arr


## Poids d'une tuile pour le shader : les `max_n` biomes les plus présents de la tuile (niveau `level`)
## en RGBA d'une image 17 × 17 (point (i, j) au pixel (i, j)), et leurs indices dans BiomeIds.BIOMES (-1 : vide).
static func tile_weights(biome_model, level: String, ix: int, iz: int, max_n: int) -> Dictionary:
	var img := Image.create(GRID, GRID, false, Image.FORMAT_RGBA8)
	var index := Vector4(-1.0, -1.0, -1.0, -1.0)
	var t: Dictionary = {}
	if biome_model.forced == "" and biome_model.layer.present:
		t = biome_model.layer.tile(level, ix, iz)
	if t.is_empty():
		var only: String = biome_model.forced if biome_model.forced != "" else biome_model.default_biome()
		index.x = BiomeIds.BIOMES.find(only)
		img.fill(Color(1.0, 0.0, 0.0, 0.0))
		return {"index": index, "image": img, "biomes": [only]}
	var biomes: Array[String] = t["biomes"]
	var grids: Array[PackedFloat32Array] = t["weights"]
	var order := []
	for b in range(biomes.size()):
		var s := 0.0
		for w in grids[b]:
			s += w
		if s > 0.0:
			order.append([s, b])
	order.sort_custom(func(a, b): return a[0] > b[0] or (a[0] == b[0] and biomes[a[1]] < biomes[b[1]]))
	order = order.slice(0, clampi(max_n, 1, 4))
	var names := []
	for k in range(order.size()):
		index[k] = BiomeIds.BIOMES.find(biomes[order[k][1]])
		names.append(biomes[order[k][1]])
	for j in range(GRID):
		for i in range(GRID):
			var p := j * GRID + i
			var c := Color(0.0, 0.0, 0.0, 0.0)
			for k in range(order.size()):
				c[k] = grids[order[k][1]][p]
			img.set_pixel(i, j, c)
	return {"index": index, "image": img, "biomes": names}


## Matériau d'une tuile de terrain (`level` : "near" ou "far").
func tile_material(level: String, ix: int, iz: int) -> ShaderMaterial:
	var mat := material.duplicate() as ShaderMaterial
	var tw := tile_weights(model, level, ix, iz, QualityPresets.max_biomes(quality))
	mat.set_shader_parameter("biome_weights", ImageTexture.create_from_image(tw["image"]))
	mat.set_shader_parameter("biome_index", tw["index"])
	var o := TerrainTiles.tile_origin(level, ix, iz)
	var size := float(TerrainTiles.LEVELS[level]["size"])
	mat.set_shader_parameter("tile_rect", Vector4(o.x, o.z, size, size))
	for key in _shared:
		mat.set_shader_parameter(key, _shared[key])
	_tile_materials.append(mat)
	return mat


## Oublie le matériau d'une tuile retirée de la scène.
func release(mat: Material) -> void:
	_tile_materials.erase(mat)


## Recopie sur le matériau de base et sur les tuiles les paramètres de SHARED_PARAMS qui ont changé sur
## `source` (matériau du thème, réglé par living_world.gd et les préréglages).
func sync_from(source: Material) -> void:
	if not (source is ShaderMaterial):
		return
	for key in SHARED_PARAMS:
		var v = (source as ShaderMaterial).get_shader_parameter(key)
		if v == null or (_shared.has(key) and _shared[key] == v):
			continue
		_shared[key] = v
		material.set_shader_parameter(key, v)
		for mat in _tile_materials:
			mat.set_shader_parameter(key, v)
