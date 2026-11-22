extends SceneTree

## Tests unitaires sans écran des ponts dessinés (lot EA4) : maillage `bridge_mesh.gd` (tablier sous la chaussée,
## garde-corps des deux côtés, piles du tablier au pied, normales tournées vers l'extérieur et faces dans le sens
## de Godot), lecture de la couche `bridges` par `osm_layers.gd` (validation, monde vivant : coordonnées
## relatives au coin du carré) et relief exagéré (`osm_streamer.scale_bridges`).
## Lancement : godot --headless --path engine --script res://tests/unit/test_bridge_mesh.gd

const BridgeMesh := preload("res://scripts/bridge_mesh.gd")
const OsmLayers := preload("res://scripts/osm_layers.gd")
const OsmStreamer := preload("res://scripts/osm_streamer.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Pont droit de 120 m vers le nord (z décroissant), chaussée à 100 m, deux piles au-dessus d'un sol à 70 m.
func _bridge(piers: Array = [[0.0, -40.0, 100.0, 68.5], [0.0, -80.0, 100.0, 68.5]]) -> Dictionary:
	var pts := []
	for i in range(13):
		pts.append([0.0, -10.0 * i, 100.0])
	return {"id": "b0", "kind": "bridge", "length_m": 120.0, "half_width_m": 3.0, "points": pts, "piers": piers}


func _test_geometry() -> void:
	var m := BridgeMesh.build([_bridge()])
	var v: PackedVector3Array = m["vertices"]
	var nrm: PackedVector3Array = m["normals"]
	var idx: PackedInt32Array = m["indices"]
	_check(int(m["built"]) == 1 and int(m["piers"]) == 2, "un pont, deux piles (%d, %d)" % [m["built"], m["piers"]])
	_check(v.size() == nrm.size() and v.size() == (m["colors"] as PackedColorArray).size() and idx.size() % 3 == 0,
		"tableaux cohérents (%d sommets, %d indices)" % [v.size(), idx.size()])
	var lo := INF
	var hi := -INF
	var xmax := 0.0
	var deck_top_ok := true
	for p in v:
		lo = minf(lo, p.y)
		hi = maxf(hi, p.y)
		xmax = maxf(xmax, absf(p.x))
	# Sous la chaussée (|x| < 3,5 m, ruban de route et bas-côtés) : rien au-dessus de la route
	for p in v:
		if absf(p.x) < 3.5 and p.y > 100.0 - BridgeMesh.DECK_TOP_DROP_M + 1e-4:
			deck_top_ok = false
	_check(deck_top_ok, "rien du pont au-dessus de la chaussée (dessus du tablier %.2f m sous la route)" % BridgeMesh.DECK_TOP_DROP_M)
	_check(is_equal_approx(hi, 100.0 + BridgeMesh.PARAPET_H_M), "garde-corps à %.1f m au-dessus de la route (%.2f)" % [BridgeMesh.PARAPET_H_M, hi - 100.0])
	_check(is_equal_approx(xmax, 3.0 + BridgeMesh.DECK_EXTRA_M), "rive du tablier à %.1f m de l'axe (%.2f)" % [3.0 + BridgeMesh.DECK_EXTRA_M, xmax])
	_check(is_equal_approx(lo, 68.5), "pieds des piles à 68,5 m (%.2f)" % lo)
	# Garde-corps des deux côtés : sommets à la hauteur du garde-corps à gauche et à droite
	var left := false
	var right := false
	for p in v:
		if is_equal_approx(p.y, hi):
			left = left or p.x < -3.0
			right = right or p.x > 3.0
	_check(left and right, "garde-corps à gauche et à droite")
	# Regard libre entre la bordure et la main courante (montants exceptés) : aucun sommet dans cet intervalle
	var gap_free := true
	for p in v:
		if p.y > 100.0 + BridgeMesh.CURB_H_M + 0.01 and p.y < 100.0 + BridgeMesh.RAIL_TOP_M - BridgeMesh.RAIL_H_M - 0.01:
			gap_free = false
	_check(gap_free, "garde-corps ajouré : rien entre la bordure (%.1f m) et la main courante" % BridgeMesh.CURB_H_M)
	# Normales unitaires, faces dans le sens horaire vu de leur normale (face avant de Godot)
	var unit := true
	var winding := true
	for t in range(0, idx.size(), 3):
		var a := v[idx[t]]
		var b := v[idx[t + 1]]
		var c := v[idx[t + 2]]
		var n := nrm[idx[t]]
		unit = unit and absf(n.length() - 1.0) < 1e-4
		var cr := (b - a).cross(c - a)
		if cr.length() > 1e-6 and cr.normalized().dot(n) > -0.99:
			winding = false
	_check(unit, "normales unitaires")
	_check(winding, "triangles dans le sens horaire vu de l'extérieur (face avant de Godot)")
	# Dessous du tablier : normale vers le bas ; rive droite : normale vers la droite (+x pour un pont vers −z)
	var bottom_down := false
	var side_out := false
	for t in range(0, idx.size(), 3):
		var a := v[idx[t]]
		var n := nrm[idx[t]]
		if is_equal_approx(a.y, 100.0 - BridgeMesh.DECK_TOP_DROP_M - BridgeMesh.DECK_DEPTH_M) and n.y < -0.99:
			bottom_down = true
		if is_equal_approx(a.x, 3.0 + BridgeMesh.DECK_EXTRA_M) and n.x > 0.99:
			side_out = true
	_check(bottom_down and side_out, "dessous tourné vers le bas, rive tournée vers l'extérieur")


func _test_piers_and_invalid() -> void:
	var low := BridgeMesh.build([_bridge([[0.0, -40.0, 100.0, 99.0]])])   # sol juste sous le tablier : pas de pile
	_check(int(low["piers"]) == 0 and int(low["built"]) == 1, "pile ignorée quand le tablier touche presque le sol")
	var bad := BridgeMesh.build([{"id": "x", "points": [[0.0, 0.0, 1.0]], "piers": []}, 42])
	_check(int(bad["built"]) == 0 and int(bad["skipped"]) == 2 and (bad["vertices"] as PackedVector3Array).is_empty(),
		"pont d'un seul point et élément non objet ignorés")
	# Pont courbe : la rive suit l'axe (aucun sommet plus loin que la rive de l'axe le plus proche)
	var pts := []
	for i in range(19):
		var a := deg_to_rad(5.0 * i)
		pts.append([100.0 * sin(a), -100.0 * (1.0 - cos(a)), 50.0])
	var curve := BridgeMesh.build([{"id": "c", "kind": "bridge", "half_width_m": 3.0, "points": pts, "piers": []}])
	var far := 0.0
	for p in (curve["vertices"] as PackedVector3Array):
		var d := absf(Vector2(p.x, p.z + 100.0).length() - 100.0)
		far = maxf(far, d)
	_check(far < 3.0 + BridgeMesh.DECK_EXTRA_M + 0.05, "pont en courbe : rive à %.2f m de l'axe au plus" % far)


func _test_layer_reading() -> void:
	var dir := OS.get_temp_dir().path_join("openride_ea4_%d" % Time.get_ticks_usec())
	DirAccess.make_dir_recursive_absolute(dir.path_join("bridges"))
	var good := _bridge()
	var doc := {"version": "1.0", "bridges": [good, {"id": "", "kind": "bridge", "half_width_m": 3.0, "points": [], "piers": []},
		{"id": "t", "kind": "tunnel", "half_width_m": 3.0, "points": [[0, 0, 0], [0, -10, 0]], "piers": []}]}
	var f := FileAccess.open(dir.path_join("bridges/chunk_0.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(doc))
	f.close()
	var res := OsmLayers.load_chunk(dir, "bridges", 0)
	_check(res["ok"] and (res["items"] as Array).size() == 1 and int(res["ignored"]) == 2,
		"couche bridges : un pont valide, deux ignorés (%s)" % str(res.get("error", "")))
	_check(OsmLayers.layers_present({"layers": {"bridges": {"present": true}}}).has("bridges"), "couche bridges reconnue au manifeste")
	# Monde vivant : carré (2, -1), coordonnées relatives au coin rendues absolues (piles comprises)
	DirAccess.make_dir_recursive_absolute(dir.path_join("live/bridges"))
	f = FileAccess.open(dir.path_join("live/bridges/tile_2_-1.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify({"version": "1.0", "bridges": [_bridge()]}))
	f.close()
	var one := OsmLayers._load_file(dir.path_join("live/bridges/tile_2_-1.json"), "bridges", Vector2(2000.0, -1000.0))
	var b: Dictionary = one["items"][0]
	_check(is_equal_approx(float(b["points"][1][0]), 2000.0) and is_equal_approx(float(b["points"][1][1]), -1010.0)
		and is_equal_approx(float(b["piers"][0][1]), -1040.0) and is_equal_approx(float(b["piers"][0][3]), 68.5),
		"monde vivant : axe et piles ramenés au repère de la séance, altitudes gardées")


## Route vivante réduite (`chunk_bounds` : n, ds_m, x, z) : 200 m vers le nord depuis (2 000, −1 000).
class FakeLiveRoute:
	var live := true
	var n := 21
	var ds_m := 10.0
	var x := PackedFloat64Array()
	var z := PackedFloat64Array()

	func _init() -> void:
		for i in range(n):
			x.append(2000.0)
			z.append(-1000.0 - 10.0 * i)


## Ponts de la route d'un tronçon (22 novembre 2026, talus retirés sur un tablier) : monde vivant, tous les carrés
## autour du tronçon ; parcours compilé, tronçons voisins compris.
func _test_route_bridges() -> void:
	var dir := OS.get_temp_dir().path_join("openride_pont_sol_%d" % Time.get_ticks_usec())
	DirAccess.make_dir_recursive_absolute(dir.path_join("bridges"))
	var f := FileAccess.open(dir.path_join("bridges/tile_2_-1.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify({"version": "1.0", "bridges": [_bridge()]}))
	f.close()
	var live := OsmLayers.route_bridges(dir, FakeLiveRoute.new(), 0)
	_check(live.size() == 1 and is_equal_approx(float(live[0]["points"][2][1]), -1020.0),
		"monde vivant : pont du carré lu en coordonnées de la séance (%d)" % live.size())
	_check(absf(BridgeMesh.deck_axis_alt(live, 2001.0, -1050.0) - 100.0) < 1e-3
		and is_nan(BridgeMesh.deck_axis_alt(live, 2004.0, -1050.0)) and is_nan(BridgeMesh.deck_axis_alt(live, 2000.0, -1130.0)),
		"axe du tablier : à 1 m de l'axe oui ; à 4 m (demi-largeur 3 m) ou après le bout non")
	f = FileAccess.open(dir.path_join("bridges/chunk_1.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify({"version": "1.0", "bridges": [_bridge()]}))
	f.close()
	var compiled := FakeLiveRoute.new()
	compiled.live = false
	_check(OsmLayers.route_bridges(dir, compiled, 0).size() == 1 and OsmLayers.route_bridges(dir, compiled, 3).is_empty(),
		"parcours compilé : pont du tronçon voisin lu, rien au loin")


class FakeRoute:
	func display_y(y: float) -> float:
		return 2.0 * y


func _test_relief_scale() -> void:
	var scaled := OsmStreamer.scale_bridges([_bridge()], FakeRoute.new())
	var b: Dictionary = scaled[0]
	_check(is_equal_approx(float(b["points"][0][2]), 200.0) and is_equal_approx(float(b["piers"][0][2]), 200.0)
		and is_equal_approx(float(b["piers"][0][3]), 137.0), "relief exagéré : tablier et pied des piles passés par display_y")


func _test_performance() -> void:
	var items := []
	for k in range(20):
		var it := _bridge()
		for p in it["points"]:
			p[0] = float(p[0]) + 50.0 * k
		items.append(it)
	var t0 := Time.get_ticks_usec()
	var m := BridgeMesh.build(items)
	var ms := (Time.get_ticks_usec() - t0) / 1000.0
	var tris := (m["indices"] as PackedInt32Array).size() / 3
	_check(tris < 20 * 120 * 12, "20 ponts de 120 m : %d triangles (moins de 12 par mètre de pont, montants compris), %.1f ms" % [tris, ms])


func _init() -> void:
	_test_geometry()
	_test_piers_and_invalid()
	_test_layer_reading()
	_test_relief_scale()
	_test_route_bridges()
	_test_performance()
	print("test_bridge_mesh : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
