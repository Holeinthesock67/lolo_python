extends SceneTree

## Tests unitaires sans écran des zones d'exclusion `exclusion_zones.gd` (lot HERBE1) : même réponse que le
## contour lui-même (petit, grand, concave, à cheval sur plusieurs cases larges, coordonnées négatives, contours
## qui se chevauchent, entrée `{points, rect}` d'osm_streamer), cases calculées à la demande, coût d'une place
## indépendant de la taille des contours.
## Lancement : godot --headless --path engine --script res://tests/unit/test_exclusion_zones.gd

const ExclusionZones := preload("res://scripts/exclusion_zones.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Contour en L (6 sommets), coin en (x0, z0), 300 m de côté : il déborde sur plusieurs cases larges.
static func _l_shape(x0: float, z0: float) -> PackedVector2Array:
	return PackedVector2Array([Vector2(x0, z0), Vector2(x0 + 300, z0), Vector2(x0 + 300, z0 + 100),
		Vector2(x0 + 100, z0 + 100), Vector2(x0 + 100, z0 + 300), Vector2(x0, z0 + 300)])


## Même contour, chaque côté coupé en `n` : beaucoup de sommets (contour découpé par les cases).
static func _subdivide(pts: PackedVector2Array, n: int) -> PackedVector2Array:
	var out := PackedVector2Array()
	for i in range(pts.size()):
		var a := pts[i]
		var b := pts[(i + 1) % pts.size()]
		for k in range(n):
			out.append(a.lerp(b, float(k) / n))
	return out


## Points tirés (déterministes) dans le rectangle `r`, à plus de `margin` m des bords des contours de référence.
static func _points(r: Rect2, n: int) -> PackedVector2Array:
	var out := PackedVector2Array()
	var rng := RandomNumberGenerator.new()
	rng.seed = 0x5EA
	for i in range(n):
		out.append(Vector2(rng.randf_range(r.position.x, r.end.x), rng.randf_range(r.position.y, r.end.y)))
	return out


static func _near_edge(p: Vector2, poly: PackedVector2Array, margin: float) -> bool:
	for i in range(poly.size()):
		var q := Geometry2D.get_closest_point_to_segment(p, poly[i], poly[(i + 1) % poly.size()])
		if p.distance_to(q) < margin:
			return true
	return false


func _test_same_answer() -> void:
	for origin in [Vector2(10, 20), Vector2(-700, -450)]:
		var l := _l_shape(origin.x, origin.y)
		var big := _subdivide(l, 400)   # 2 400 sommets : découpé par les cases
		for poly in [l, big]:
			var z := ExclusionZones.new([poly])
			var wrong := 0
			var tested := 0
			for p in _points(Rect2(origin - Vector2(50, 50), Vector2(400, 400)), 3000):
				if _near_edge(p, l, 0.05):
					continue
				tested += 1
				if z.contains(p.x, p.y) != Geometry2D.is_point_in_polygon(p, l):
					wrong += 1
			_check(wrong == 0, "L de %d sommets en %s : même réponse que le contour (%d points)" % [poly.size(), str(origin), tested])


func _test_overlap_and_dict() -> void:
	var a := _subdivide(PackedVector2Array([Vector2(0, 0), Vector2(100, 0), Vector2(100, 100), Vector2(0, 100)]), 30)
	var b := PackedVector2Array([Vector2(50, 50), Vector2(150, 50), Vector2(150, 150), Vector2(50, 150)])
	var z := ExclusionZones.new([{"points": a, "rect": Rect2(0, 0, 100, 100)}, b, PackedVector2Array([Vector2(1, 1)])])
	_check(z.size() == 2, "contour de moins de 3 sommets ignoré : 2 contours")
	_check(z.contains(75.0, 75.0), "dans les deux contours : exclu (pas d'annulation entre contours)")
	_check(z.contains(25.0, 25.0) and z.contains(125.0, 125.0), "dans un seul des deux : exclu")
	_check(not z.contains(125.0, 25.0) and not z.contains(-5.0, 50.0), "hors des deux : libre")
	_check(not ExclusionZones.new().contains(0.0, 0.0), "aucune zone : rien n'est exclu")


func _test_lazy_and_cost() -> void:
	var small := ExclusionZones.new([_l_shape(0, 0)])
	_check(small.cells_built() == 0, "aucune case calculée avant la première place")
	small.contains(50.0, 50.0)
	small.contains(51.0, 52.0)
	_check(small.cells_built() == 1, "deux places dans la même case : une case calculée")
	# Coût par place : contour de 24 000 sommets contre 6, mêmes places, cases déjà calculées
	var huge := ExclusionZones.new([_subdivide(_l_shape(0, 0), 4000)])
	var pts := _points(Rect2(-20, -20, 340, 340), 4000)
	for p in pts:
		small.contains(p.x, p.y)
		huge.contains(p.x, p.y)
	var t0 := Time.get_ticks_usec()
	for p in pts:
		small.contains(p.x, p.y)
	var t_small := Time.get_ticks_usec() - t0
	t0 = Time.get_ticks_usec()
	for p in pts:
		huge.contains(p.x, p.y)
	var t_huge := Time.get_ticks_usec() - t0
	_check(t_huge < 3 * t_small + 2000, "coût par place : %.2f µs avec 24 000 sommets, %.2f µs avec 6" % [
		float(t_huge) / pts.size(), float(t_small) / pts.size()])


func _init() -> void:
	_test_same_answer()
	_test_overlap_and_dict()
	_test_lazy_and_cost()
	print("test_exclusion_zones : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
