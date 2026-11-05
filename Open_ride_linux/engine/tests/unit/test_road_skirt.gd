extends SceneTree

## Tests sans écran des talus des bords de la route (road_builder.gd build_skirt_arrays, 4 novembre 2026 : « la
## route lévite ») : une bande par bord, du bord extérieur du bas-côté jusqu'à SKIRT_DROP_M plus bas et
## SKIRT_OUT_M plus loin vers l'extérieur, à chaque coupe du tronçon.
## Lancement : godot --headless --path engine --script res://tests/unit/test_road_skirt.gd

const RoadBuilder := preload("res://scripts/road_builder.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")

var _failures := 0
var _checked := 0


func _init() -> void:
	var route = RouteDataScript.new()
	if not route.load_world_dir("res://demo/demo.world"):
		_check(false, "demo.world chargé : " + route.load_error)
	else:
		_test_skirt(route)
	print("test_road_skirt : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _test_skirt(route) -> void:
	var road := RoadBuilder.build_chunk_arrays(route, 0)
	var skirt := RoadBuilder.build_skirt_arrays(road)
	var rv: PackedVector3Array = road[Mesh.ARRAY_VERTEX]
	var sv: PackedVector3Array = skirt[Mesh.ARRAY_VERTEX]
	var cuts := rv.size() / RoadBuilder.VERTS_PER_SECTION
	_check(sv.size() == cuts * 4, "4 sommets de talus par coupe (%d coupes, %d sommets)" % [cuts, sv.size()])
	_check((skirt[Mesh.ARRAY_INDEX] as PackedInt32Array).size() == (cuts - 1) * 12, "deux bandes de deux triangles entre deux coupes")
	var bad := 0
	for c in range(cuts):
		var b := c * RoadBuilder.VERTS_PER_SECTION
		var tops := [rv[b], rv[b + RoadBuilder.VERTS_PER_SECTION - 1]]
		var centre := (rv[b + 2] + rv[b + 3]) * 0.5
		for side in range(2):
			var top: Vector3 = sv[c * 4 + side * 2]
			var bottom: Vector3 = sv[c * 4 + side * 2 + 1]
			var out := Vector2(bottom.x - top.x, bottom.z - top.z)
			var away := Vector2(top.x - centre.x, top.z - centre.z)
			if not top.is_equal_approx(tops[side]) or absf(top.y - bottom.y - RoadBuilder.SKIRT_DROP_M) > 1e-3 \
					or absf(out.length() - RoadBuilder.SKIRT_OUT_M) > 1e-3 or out.dot(away) <= 0.0:
				bad += 1
	_check(bad == 0, "talus : haut au bord du bas-côté, %.1f m plus bas, %.1f m vers l'extérieur (%d écarts)" % [
		RoadBuilder.SKIRT_DROP_M, RoadBuilder.SKIRT_OUT_M, bad])
