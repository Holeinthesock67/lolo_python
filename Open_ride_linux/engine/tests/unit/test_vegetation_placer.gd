extends SceneTree

## Tests sans écran du placement de la végétation `vegetation_placer.gd` (Lot K3).
## Lancement : godot --headless --path engine --script res://tests/unit/test_vegetation_placer.gd

const Placer := preload("res://scripts/vegetation_placer.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")

## Empreinte figée de la tuile de référence (_reference_tile) : à mettre à jour seulement si la
## méthode de placement change volontairement (le paysage changera aussi pour l'utilisateur).
const REFERENCE_COUNT := 2920
const REFERENCE_CHECKSUM := "c91d4a0d8de7dd7d"

var _failures := 0
var _checked := 0
var _theme := {}


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _flat(_x: float, _z: float) -> float:
	return 500.0


func _slope_x(x: float, _z: float) -> float:
	return 1990.0 + 0.1 * x


func _steep(x: float, _z: float) -> float:
	return 0.5 * x


func _gentle(x: float, _z: float) -> float:
	return 0.3 * x


func _rolling(x: float, z: float) -> float:
	return 800.0 + 20.0 * sin(x / 90.0) + 15.0 * cos(z / 70.0)


func _square(x0: float, z0: float, size: float) -> Array:
	return [[x0, z0], [x0 + size, z0], [x0 + size, z0 + size], [x0, z0 + size]]


func _area(id: String, kind: String, outer: Array, density: float, holes: Array = []) -> Dictionary:
	return {"id": id, "kind": kind, "outer": outer, "holes": holes, "density": density}


## Empreinte : nombre d'arbres et somme de contrôle sur les valeurs arrondies au millimètre.
func _checksum(trees: PackedVector4Array) -> String:
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	for t in trees:
		ctx.update(("%d,%d,%d,%d;" % [roundi(t.x * 1000.0), roundi(t.y * 1000.0), roundi(t.z * 1000.0),
			roundi(t.w * 1000.0)]).to_utf8_buffer())
	return ctx.finish().hex_encode().substr(0, 16)


func _reference_tile() -> PackedVector4Array:
	var p = Placer.new()
	var areas := [
		_area("w98765", "wood", [[100.0, 100.0], [380.0, 120.0], [420.0, 400.0], [150.0, 450.0]], 0.8,
			[_square(200.0, 200.0, 60.0)]),
		_area("w12", "scrub", _square(0.0, 0.0, 120.0), 1.0),
	]
	return p.place_tile(0, 0, 500.0, _rolling, null, _theme, areas)


func _test_determinism() -> void:
	var a := _reference_tile()
	var b := _reference_tile()
	var same := a.size() == b.size()
	if same:
		for i in range(a.size()):
			same = same and a[i] == b[i]
	_check(same and a.size() > 0, "déterminisme : deux appels identiques, %d arbres égaux élément par élément" % a.size())
	var sum := _checksum(a)
	print("Empreinte de la tuile de référence : %d arbres, %s" % [a.size(), sum])
	_check(a.size() == REFERENCE_COUNT and sum == REFERENCE_CHECKSUM,
		"empreinte figée de la tuile de référence (%d arbres, %s)" % [a.size(), sum])
	var p = Placer.new()
	var n1: PackedVector4Array = p.place_tile(3, -2, 500.0, _flat, null, _theme)
	var n2: PackedVector4Array = p.place_tile(3, -2, 500.0, _flat, null, _theme)
	_check(n1 == n2 and n1.size() > 0, "déterminisme du bruit (tuile 3, −2) : %d arbres" % n1.size())
	var scales_ok := true
	for t in a:
		scales_ok = scales_ok and t.w >= 0.7 and t.w <= 1.3
	_check(scales_ok, "échelles entre 0,7 et 1,3")
	# Une zone à cheval sur deux tuiles donne les mêmes arbres quel que soit le découpage.
	var big := [_area("w7", "wood", _square(400.0, 100.0, 200.0), 0.5)]
	var left: PackedVector4Array = p.place_tile(0, 0, 500.0, _flat, null, _theme, big)
	var right: PackedVector4Array = p.place_tile(1, 0, 500.0, _flat, null, _theme, big)
	var whole: PackedVector4Array = p.place_tile(0, 0, 1000.0, _flat, null, _theme, big)
	_check(left.size() + right.size() == whole.size() and whole.size() > 0,
		"zone à cheval sur deux tuiles : %d + %d = %d arbres" % [left.size(), right.size(), whole.size()])


func _test_density() -> void:
	var p = Placer.new()
	var max_d := float(_theme["vegetation"]["max_density_per_ha"])
	var one_ha := [_area("w1", "wood", _square(100.0, 100.0, 100.0), 1.0)]
	var n: int = p.place_tile(0, 0, 500.0, _flat, null, _theme, one_ha).size()
	_check(absf(n - max_d) <= 0.1 * max_d, "1 ha de forêt à densité 1 : %d arbres (%d ± 10 %%)" % [n, int(max_d)])
	var zero := [_area("w2", "wood", _square(100.0, 100.0, 100.0), 0.0)]
	_check(p.place_tile(0, 0, 500.0, _flat, null, _theme, zero).size() == 0, "densité 0 : aucun arbre")
	for kind in [["scrub", 0.4], ["orchard", 0.6]]:
		var k: int = p.place_tile(0, 0, 500.0, _flat, null, _theme,
			[_area("k" + kind[0], kind[0], _square(0.0, 0.0, 200.0), 1.0)]).size()
		var expected: float = 4.0 * max_d * kind[1]
		_check(absf(k - expected) <= 0.1 * expected, "%s : %d arbres sur 4 ha (%d attendus)" % [kind[0], k, int(expected)])
	_check(p.place_tile(0, 0, 500.0, _flat, null, _theme,
		[_area("x", "meadow", _square(0.0, 0.0, 200.0), 1.0)]).size() == 0, "kind inconnu : ignoré")
	var noise: int = p.place_tile(0, 0, 500.0, _flat, null, _theme).size()
	var noise_max := 25.0 * max_d * 0.5
	_check(noise > 0 and noise <= noise_max, "sans zone, bruit : %d arbres sur 25 ha (au plus %d)" % [noise, int(noise_max)])


func _test_exclusions() -> void:
	var p = Placer.new()
	var wood := [_area("w3", "wood", _square(0.0, 0.0, 500.0), 1.0)]
	# Limite des arbres : altitude 1 990 + 0,1·x, limite à 2 000 m donc x ≤ 100 m.
	var t: PackedVector4Array = p.place_tile(0, 0, 500.0, _slope_x, null, _theme, wood)
	var above := 0
	for tree in t:
		if tree.y > 2000.0:
			above += 1
	_check(t.size() > 0 and above == 0, "limite des arbres : %d arbres, aucun au-dessus de 2 000 m" % t.size())
	_check(p.place_tile(0, 0, 500.0, _steep, null, _theme, wood).size() == 0, "pente de 26,6° (> 22°) : aucun arbre")
	_check(p.place_tile(0, 0, 500.0, _gentle, null, _theme, wood).size() > 0, "pente de 16,7° : arbres posés")
	# Trou : carré de 100 m au milieu d'une zone de 300 m.
	var holed := [_area("w4", "wood", _square(100.0, 100.0, 300.0), 1.0, [_square(200.0, 200.0, 100.0)])]
	var h: PackedVector4Array = p.place_tile(0, 0, 500.0, _flat, null, _theme, holed)
	var in_hole := 0
	for tree in h:
		if tree.x > 200.0 and tree.x < 300.0 and tree.z > 200.0 and tree.z < 300.0:
			in_hole += 1
	var expected := 8.0 * float(_theme["vegetation"]["max_density_per_ha"])
	_check(in_hole == 0 and absf(h.size() - expected) <= 0.1 * expected,
		"trou : aucun arbre dedans, %d arbres sur 8 ha" % h.size())
	# Couloir de la route : parcours de démonstration (courbe), tuile autour de s = 1 500 m.
	var route = RouteDataScript.new()
	if not route.load_world_dir("res://demo/demo.world"):
		_check(false, "demo.world chargé : " + route.load_error)
		return
	var c: Vector3 = route.sample_point(1500.0)
	var tx := int(floor(c.x / 500.0))
	var tz := int(floor(c.z / 500.0))
	var all_wood := [_area("w5", "wood", _square(tx * 500.0, tz * 500.0, 500.0), 1.0)]
	var r: PackedVector4Array = p.place_tile(tx, tz, 500.0, _flat, route, _theme, all_wood)
	# Axe de la route échantillonné tous les 0,5 m (indépendamment du placeur).
	var axis := PackedVector2Array()
	var s := 0.0
	while s <= route.length_m:
		var q: Vector3 = route.sample_point(s)
		if q.x > tx * 500.0 - 20.0 and q.x < tx * 500.0 + 520.0 and q.z > tz * 500.0 - 20.0 and q.z < tz * 500.0 + 520.0:
			axis.append(Vector2(q.x, q.z))
		s += 0.5
	var corridor := float(_theme["road"]["width_m"]) * 0.5 + 4.0
	var min_d := INF
	var near := 0
	for tree in r:
		var dmin := INF
		for a in axis:
			dmin = minf(dmin, a.distance_to(Vector2(tree.x, tree.z)))
		min_d = minf(min_d, dmin)
		if dmin < corridor + 3.0:
			near += 1
	_check(axis.size() > 100 and r.size() > 0 and min_d >= corridor - 0.02,
		"couloir de la route : arbre le plus proche à %.2f m de l'axe (≥ %.1f m)" % [min_d, corridor])
	_check(near > 0, "couloir de la route : %d arbres entre %.0f et %.0f m (pas d'exclusion excessive)" % [near, corridor, corridor + 3.0])


func _test_performance() -> void:
	var p = Placer.new()
	var wood := [_area("w6", "wood", _square(0.0, 0.0, 500.0), 1.0)]
	p.place_tile(0, 0, 500.0, _rolling, null, _theme, wood)   # premier appel hors mesure
	# Temps mesuré à part (lot X2) : budget de 50 ms du cahier dans tests/perf_budgets.json.
	var box := [0]   # les lambdas capturent par valeur : résultat rangé dans un tableau
	var ms := PerfBudget.measure_ms(func(): box[0] = p.place_tile(0, 0, 500.0, _rolling, null, _theme, wood).size(), 3, 0)
	var n: int = box[0]
	print("Mesure : tuile de 500 m × 500 m à densité maximale (%d arbres) en %.1f ms" % [n, ms])
	_check(n > 0 and PerfBudget.check("vegetation_tile_max", ms),
		"tuile à densité maximale : %d arbres, temps dans le budget (%.1f ms)" % [n, ms])


func _init() -> void:
	var doc = JSON.parse_string(FileAccess.get_file_as_string("res://themes/default/theme.json"))
	_theme = doc if typeof(doc) == TYPE_DICTIONARY else {}
	_check(not _theme.is_empty(), "thème par défaut lu")
	_test_determinism()
	_test_density()
	_test_exclusions()
	_test_performance()
	print("test_vegetation_placer : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
