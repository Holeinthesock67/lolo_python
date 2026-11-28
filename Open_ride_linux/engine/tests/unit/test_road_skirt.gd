extends SceneTree

## Tests sans écran des talus des bords de la route (road_builder.gd build_skirt_arrays, 4 novembre 2026 : « la
## route lévite ») : une bande par bord, du bord extérieur du bas-côté jusqu'à SKIRT_DROP_M plus bas et
## SKIRT_OUT_M plus loin vers l'extérieur, à chaque coupe du tronçon.
## Sur un pont (22 novembre 2026, banc ea1_lac au relief ×2,5 : talus pendu sous le tablier d'un pont de 30 m) :
## pas de talus entre deux coupes posées sur le tablier (bridge_mesh.gd `cuts_on_deck`), ni pour un pont d'une
## autre route à côté ou au-dessus ; axe du tablier lu entre ses bouts seulement (`deck_axis_alt`).
## Lancement : godot --headless --path engine --script res://tests/unit/test_road_skirt.gd

const RoadBuilder := preload("res://scripts/road_builder.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const BridgeMesh := preload("res://scripts/bridge_mesh.gd")

var _failures := 0
var _checked := 0


func _init() -> void:
	var route = RouteDataScript.new()
	if not route.load_world_dir("res://demo/demo.world"):
		_check(false, "demo.world chargé : " + route.load_error)
	else:
		_test_skirt(route)
		_test_bridge(route)
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


## Pont le long de la route, de s0 à s1, décalé de `side` m à droite et de `dy` m en hauteur.
static func _bridge_on(route, s0: float, s1: float, side: float = 0.0, dy: float = 0.0) -> Dictionary:
	var pts := []
	var s := s0
	while s <= s1 + 1e-6:
		var smp: Dictionary = route.sample(s)
		var h := deg_to_rad(float(smp["heading_deg"]))
		pts.append([float(smp["x"]) + cos(h) * side, float(smp["z"]) + sin(h) * side, float(smp["alt_m"]) + dy])
		s += 10.0
	return {"id": "p", "kind": "bridge", "length_m": s1 - s0, "half_width_m": 3.0, "points": pts, "piers": []}


func _test_bridge(route) -> void:
	var road := RoadBuilder.build_chunk_arrays(route, 0)
	var cuts := (road[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() / RoadBuilder.VERTS_PER_SECTION
	var full := (cuts - 1) * 12
	var deck := BridgeMesh.cuts_on_deck(road, [_bridge_on(route, 200.0, 300.0)], route, RoadBuilder.VERTS_PER_SECTION)
	var on := 0
	var pairs := 0
	for c in range(deck.size()):
		on += deck[c]
		if c + 1 < deck.size() and deck[c] != 0 and deck[c + 1] != 0:
			pairs += 1
	# coupes tous les 2 m : de 200 à 300 m, 51 coupes (à une près aux bouts)
	_check(deck.size() == cuts and absi(on - 51) <= 1, "coupes sur un pont de 100 m : %d (51 attendues)" % on)
	var skirt := RoadBuilder.build_skirt_arrays(road, deck)
	var idx := (skirt[Mesh.ARRAY_INDEX] as PackedInt32Array).size()
	_check(idx == full - pairs * 12, "pas de talus sur le tablier (%d intervalles retirés, %d indices sur %d)" % [pairs, idx, full])
	_check((skirt[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() == cuts * 4, "talus gardé hors du pont (sommets inchangés)")
	var beside := BridgeMesh.cuts_on_deck(road, [_bridge_on(route, 200.0, 300.0, 8.0)], route, RoadBuilder.VERTS_PER_SECTION)
	var above := BridgeMesh.cuts_on_deck(road, [_bridge_on(route, 200.0, 300.0, 0.0, 6.0)], route, RoadBuilder.VERTS_PER_SECTION)
	var n_beside := 0
	var n_above := 0
	for c in range(cuts):
		n_beside += beside[c]
		n_above += above[c]
	_check(n_beside == 0 and n_above == 0, "pont d'une autre route à 8 m à côté ou 6 m au-dessus : talus gardé (%d, %d)" % [
		n_beside, n_above])
	var b := _bridge_on(route, 200.0, 300.0)
	var past: Dictionary = route.sample(310.0)
	var mid: Dictionary = route.sample(250.0)
	_check(is_nan(BridgeMesh.deck_axis_alt([b], float(past["x"]), float(past["z"]))),
		"10 m après le bout du pont : hors du tablier")
	_check(absf(BridgeMesh.deck_axis_alt([b], float(mid["x"]), float(mid["z"])) - float(mid["alt_m"])) < 0.5,
		"milieu du pont : altitude de l'axe du tablier")
	_check(RoadBuilder.build_skirt_arrays(road, PackedByteArray()).size() > 0 \
			and (RoadBuilder.build_skirt_arrays(road)[Mesh.ARRAY_INDEX] as PackedInt32Array).size() == full,
		"sans pont : talus complet")
