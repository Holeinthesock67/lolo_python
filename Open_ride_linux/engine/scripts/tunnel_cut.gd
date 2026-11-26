extends RefCounted

## Trou du terrain dans les tunnels (lot EA5) : le terrain n'est pas dessiné dans le volume du tube et de
## l'approche des portails (tunnel_mesh.gd), la colline au-dessus reste. Une seule règle pour tous les terrains
## proches (terrain.gdshader et terrain_biomes.gdshader, `tunnel_cut.gdshaderinc`).
##
## Registre des tronçons de découpe par tronçon de parcours ou carré chargé (osm_streamer.gd) ; à chaque image,
## les MAX_SEGMENTS tronçons les plus proches de la caméra sont écrits dans une petite texture globale
## (`tunnel_cut_data`, 3 texels RGBA float par tronçon), avec leur nombre (`tunnel_cut_count`) et la boîte qui les
## contient (`tunnel_cut_box`, test rapide du shader). Refait seulement si le registre change ou si la caméra a
## bougé de plus de MOVE_M. Variables statiques : un seul monde affiché à la fois. Pas de class_name.
##
## Le trou n'est compilé que dans la variante TUNNEL_CUT des shaders du terrain (`shader_for`) : seules les tuiles
## de terrain qui touchent un tunnel enregistré la reçoivent (`touches`, world_streamer.gd). Un `discard` fait
## exécuter tout le fragment dans les passes de profondeur et d'ombre : sur tout le terrain, il alourdissait chaque
## image et la compilation des shaders, même loin de tout tunnel.

const TunnelMesh := preload("res://scripts/tunnel_mesh.gd")

const MAX_SEGMENTS := 64
const MOVE_M := 4.0
const TILE_MARGIN_M := 2.0     # marge autour de la boîte d'un tronçon pour choisir la variante d'une tuile
const DEFINE := "#define TUNNEL_CUT\n"

static var _chunks: Dictionary = {}          # clé -> PackedFloat32Array (TunnelMesh.CUT_FLOATS par tronçon)
static var _dirty := true
static var _last_cam := Vector3(INF, INF, INF)
static var _texture: ImageTexture = null
static var _count := 0
static var _box := Vector4.ZERO
static var _version := 0                     # change à chaque modification du registre (variante des tuiles)
static var _variants: Dictionary = {}        # Shader de base -> variante TUNNEL_CUT


static func set_chunk(key, cut: PackedFloat32Array) -> void:
	if cut.is_empty():
		if _chunks.erase(key):
			_changed()
		return
	_chunks[key] = cut
	_changed()


static func remove_chunk(key) -> void:
	if _chunks.erase(key):
		_changed()


static func clear() -> void:
	if not _chunks.is_empty():
		_chunks.clear()
		_changed()


static func _changed() -> void:
	_dirty = true
	_version += 1


## Numéro du registre : change à chaque tronçon ajouté ou retiré (les tuiles revoient alors leur variante).
static func version() -> int:
	return _version


## Vrai si un tronçon enregistré (tous, pas seulement les MAX_SEGMENTS proches) touche le rectangle horizontal
## `rect` (x, z) d'une tuile de terrain.
static func touches(rect: Rect2) -> bool:
	for key in _chunks:
		var cut: PackedFloat32Array = _chunks[key]
		for s in range(0, cut.size(), TunnelMesh.CUT_FLOATS):
			var b := box_of(cut.slice(s, s + TunnelMesh.CUT_FLOATS))
			var r := Rect2(b.x, b.y, b.z - b.x, b.w - b.y).grow(TILE_MARGIN_M)
			if r.intersects(rect, true):
				return true
	return false


## Shader du terrain avec (`cut` vrai) ou sans le trou des tunnels : variante TUNNEL_CUT de `base`, faite une
## fois (même code, `#define TUNNEL_CUT` après la ligne `shader_type`).
static func shader_for(base: Shader, cut: bool) -> Shader:
	if base == null:
		return base
	for b in _variants:
		if _variants[b] == base:          # variante passée : on retrouve sa base
			base = b
			break
	if not cut:
		return base
	if not _variants.has(base):
		var code := base.code
		var eol := code.find("\n")
		var v := Shader.new()
		v.code = code.substr(0, eol + 1) + DEFINE + code.substr(eol + 1)
		_variants[base] = v
	return _variants[base]


## Vrai si `shader` est une variante TUNNEL_CUT.
static func is_variant(shader: Shader) -> bool:
	return shader != null and _variants.values().has(shader)


static func segment_count() -> int:
	var n := 0
	for key in _chunks:
		n += (_chunks[key] as PackedFloat32Array).size() / TunnelMesh.CUT_FLOATS
	return n


## Tronçons gardés pour la caméra en `cam` : les MAX_SEGMENTS plus proches (distance au segment horizontal).
static func select(cam: Vector3) -> PackedFloat32Array:
	var cands: Array = []
	for key in _chunks:
		var cut: PackedFloat32Array = _chunks[key]
		for s in range(0, cut.size(), TunnelMesh.CUT_FLOATS):
			var a := Vector2(cut[s], cut[s + 2])
			var b := Vector2(cut[s + 4], cut[s + 6])
			var d := Geometry2D.get_closest_point_to_segment(Vector2(cam.x, cam.z), a, b).distance_to(Vector2(cam.x, cam.z))
			cands.append([d, cut.slice(s, s + TunnelMesh.CUT_FLOATS)])
	cands.sort_custom(func(x, y): return x[0] < y[0])
	var out := PackedFloat32Array()
	for i in range(mini(cands.size(), MAX_SEGMENTS)):
		out.append_array(cands[i][1])
	return out


## Boîte horizontale (min x, min z, max x, max z) des tronçons, élargie de leur demi-largeur.
static func box_of(cut: PackedFloat32Array) -> Vector4:
	if cut.is_empty():
		return Vector4.ZERO
	var b := Vector4(INF, INF, -INF, -INF)
	for s in range(0, cut.size(), TunnelMesh.CUT_FLOATS):
		var m := cut[s + 8]
		for o in [0, 4]:
			b.x = minf(b.x, cut[s + o] - m)
			b.y = minf(b.y, cut[s + o + 2] - m)
			b.z = maxf(b.z, cut[s + o] + m)
			b.w = maxf(b.w, cut[s + o + 2] + m)
	return b


## Met à jour les paramètres globaux du shader pour la caméra en `cam`. Rend vrai s'ils ont été réécrits.
static func update(cam: Vector3) -> bool:
	if not _dirty and cam.distance_to(_last_cam) < MOVE_M:
		return false
	if not _dirty and _chunks.is_empty():
		return false
	_dirty = false
	_last_cam = cam
	var cut := select(cam)
	_count = cut.size() / TunnelMesh.CUT_FLOATS
	_box = box_of(cut)
	var data := PackedFloat32Array()
	data.resize(MAX_SEGMENTS * TunnelMesh.CUT_FLOATS)
	data.fill(0.0)
	for i in range(cut.size()):
		data[i] = cut[i]
	var img := Image.create_from_data(MAX_SEGMENTS * 3, 1, false, Image.FORMAT_RGBAF, data.to_byte_array())
	if _texture == null:
		_texture = ImageTexture.create_from_image(img)
	else:
		_texture.update(img)
	RenderingServer.global_shader_parameter_set("tunnel_cut_data", _texture)
	RenderingServer.global_shader_parameter_set("tunnel_cut_count", _count)
	RenderingServer.global_shader_parameter_set("tunnel_cut_box", _box)
	return true


static func active_count() -> int:
	return _count
