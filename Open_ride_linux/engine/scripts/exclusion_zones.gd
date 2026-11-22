extends RefCounted

## Zones sans décor posé au sol (lot HERBE1, 19/11) : bâtiments et plans d'eau (mer comprise) où l'herbe
## (grass_tufts.gd) et les détails de sol (ground_details.gd) ne posent rien. Pas de class_name : charger par
## preload("res://scripts/exclusion_zones.gd").
##
## Pourquoi : chaque place d'herbe testait TOUS les contours chargés, sommet par sommet. Avec la mer du monde
## ouvert (#907, aires `sea` d'un carré de 1 km, côte détaillée des tuiles vectorielles), une place coûtait plus
## d'une milliseconde et l'herbe faisait 20 à 35 ms par image (47 images de plus de 50 ms sur 114 en medium au
## banc w23_mer du 19/11).
##
## Comment : grille de cases de `CELL_M` mètres, calculée à la demande (première place tombée dans la case).
## Une case garde, pour chaque contour qui la touche, ses morceaux dans la case : le contour entier s'il est
## petit (au plus `SMALL_POINTS` sommets), sinon son découpage par le carré de la case
## (Geometry2D.intersect_polygons, règle pair-impair comme is_point_in_polygon). Le découpage d'un grand contour
## passe d'abord par une case large (`COARSE_M`, gardée elle aussi) : la case fine découpe des morceaux déjà
## petits. Résultat identique au test direct (au bord près, à la précision du découpage), coût par place
## indépendant de la taille des contours. Les contours sont rangés dans les cases larges que touche leur
## rectangle englobant (pas de parcours de tous les contours par case).
## - `contains(x, z)` : vrai dans au moins un contour (pair-impair par contour, comme avant).
## - `size()` : nombre de contours.
## - `cells_built()` : cases fines calculées (tests, sondes).

const CELL_M := 32.0
const COARSE_M := 256.0
const SMALL_POINTS := 48

var _polys: Array[PackedVector2Array] = []
var _rects: Array[Rect2] = []
var _coarse_index := {}     # Vector2i -> PackedInt32Array (contours dont le rectangle touche la case large)
var _coarse_pieces := {}    # Vector2i -> {indice de contour: Array[PackedVector2Array]} (grands contours découpés)
var _cells := {}            # Vector2i -> Array de groupes ; groupe = Array[PackedVector2Array] d'un même contour


## `shapes` : PackedVector2Array, ou dictionnaires `{points, rect}` (osm_streamer.gd `layer_shapes`).
func _init(shapes: Array = []) -> void:
	for s in shapes:
		var pts: PackedVector2Array
		var rect := Rect2()
		var has_rect := false
		if s is Dictionary:
			pts = s.get("points", PackedVector2Array())
			if s.has("rect"):
				rect = s["rect"]
				has_rect = true
		else:
			pts = s
		if pts.size() < 3:
			continue
		if not has_rect:
			rect = Rect2(pts[0], Vector2.ZERO)
			for p in pts:
				rect = rect.expand(p)
		var i := _polys.size()
		_polys.append(pts)
		_rects.append(rect)
		var c0 := _coarse_of(rect.position)
		var c1 := _coarse_of(rect.end)
		for cx in range(c0.x, c1.x + 1):
			for cz in range(c0.y, c1.y + 1):
				var key := Vector2i(cx, cz)
				var list: PackedInt32Array = _coarse_index.get(key, PackedInt32Array())
				list.append(i)
				_coarse_index[key] = list


func size() -> int:
	return _polys.size()


func cells_built() -> int:
	return _cells.size()


func contains(x: float, z: float) -> bool:
	if _polys.is_empty():
		return false
	var key := Vector2i(floori(x / CELL_M), floori(z / CELL_M))
	var groups: Variant = _cells.get(key)
	if groups == null:
		groups = _build_cell(key)
		_cells[key] = groups
	var p := Vector2(x, z)
	for group in groups:
		var inside := false
		for piece in group:
			if Geometry2D.is_point_in_polygon(p, piece):
				inside = not inside
		if inside:
			return true
	return false


static func _coarse_of(p: Vector2) -> Vector2i:
	return Vector2i(floori(p.x / COARSE_M), floori(p.y / COARSE_M))


static func _square(r: Rect2) -> PackedVector2Array:
	return PackedVector2Array([r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)])


## Morceaux du contour `i` dans le rectangle `r` (pair-impair : un point est dans le contour s'il est dans un
## nombre impair de morceaux ; un découpage sans trou n'en donne qu'un).
static func _clip(pieces: Array, r: Rect2) -> Array:
	var out: Array = []
	var sq := _square(r)
	for piece in pieces:
		for q in Geometry2D.intersect_polygons(sq, piece):
			if q.size() >= 3:
				out.append(q)
	return out


func _build_cell(key: Vector2i) -> Array:
	var cell := Rect2(Vector2(key) * CELL_M, Vector2(CELL_M, CELL_M))
	var ck := _coarse_of(cell.get_center())
	var groups: Array = []
	var list: PackedInt32Array = _coarse_index.get(ck, PackedInt32Array())
	for i in list:
		if not _rects[i].intersects(cell, true):
			continue
		var pts := _polys[i]
		if pts.size() <= SMALL_POINTS:
			groups.append([pts])
			continue
		var pieces: Array = _clip(_coarse(ck, i), cell)
		if not pieces.is_empty():
			groups.append(pieces)
	return groups


## Morceaux du grand contour `i` dans la case large `ck` (calculés une fois).
func _coarse(ck: Vector2i, i: int) -> Array:
	var per: Dictionary = _coarse_pieces.get(ck, {})
	if not per.has(i):
		var r := Rect2(Vector2(ck) * COARSE_M, Vector2(COARSE_M, COARSE_M))
		per[i] = _clip([_polys[i]], r)
		_coarse_pieces[ck] = per
	return per[i]
