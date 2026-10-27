extends SceneTree

## Route d'un monde vivant lue par parties (lot W10, format §13) : même résultat que la route entière,
## remplacement à partir d'une partie, parties gardées, route invalide refusée.
## Lancement : godot --headless --path engine --script res://tests/unit/test_route_parts.gd

const RouteDataScript := preload("res://scripts/route_data.gd")
const COLUMNS := ["lat", "lon", "alt_m", "x", "z", "grade_pct", "heading_deg"]

var _checked := 0
var _failures := 0


func _check(ok: bool, what: String) -> void:
	_checked += 1
	if not ok:
		_failures += 1
		printerr("[ÉCHEC] ", what)
	else:
		print("[OK] ", what)


## Découpe une route entière en parties au bord partagé (même règle que `split_parts` du générateur).
func _split(route: Dictionary, part_m: float) -> Array:
	var ds: float = route["ds_m"]
	var n: int = route["n"]
	var s := []
	for i in range(n - 1):
		s.append(i * ds)
	s.append(float(route["length_m"]))
	var parts := []
	var k := 0
	while true:
		var lo := k * part_m
		var hi := (k + 1) * part_m
		var idx := []
		for i in range(n):
			if s[i] >= lo - 1e-6 and s[i] <= hi + 1e-6:
				idx.append(i)
		if idx.size() < 2:
			break
		var part := {"version": "1.0", "ds_m": ds, "n": idx.size(), "length_m": s[idx[-1]] - s[idx[0]],
			"type": "open", "s0_m": lo}
		for c in COLUMNS:
			var col := []
			for i in idx:
				col.append(route[c][i])
			part[c] = col
		parts.append(part)
		if s[idx[-1]] >= s[n - 1] - 1e-6:
			break
		k += 1
	return parts


## Route synthétique : pente sinusoïdale, virage doux, `length` mètres au pas de 10 m.
func _synthetic(length: float, alt0: float = 600.0) -> Dictionary:
	var n := int(ceil(length / 10.0)) + 1
	var route := {"version": "1.0", "ds_m": 10.0, "n": n, "length_m": length, "type": "open"}
	for c in COLUMNS:
		route[c] = []
	var x := 0.0
	var z := 0.0
	for i in range(n):
		var sm: float = minf(i * 10.0, length)
		var heading := 90.0 + 20.0 * sin(sm / 700.0)
		if i > 0:
			x += 10.0 * sin(deg_to_rad(heading))
			z -= 10.0 * cos(deg_to_rad(heading))
		route["lat"].append(45.0 + z * -9e-6)
		route["lon"].append(6.0 + x * 1.27e-5)
		route["alt_m"].append(alt0 + 8.0 * sin(sm / 300.0))
		route["x"].append(x)
		route["z"].append(z)
		route["grade_pct"].append(2.5 * cos(sm / 300.0))
		route["heading_deg"].append(fposmod(heading, 360.0))
	return route


func _write_json(path: String, obj: Variant) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(JSON.stringify(obj))
	f.close()


func _write_world(dir: String, parts: Array) -> void:
	_write_json(dir.path_join("manifest.json"), {"format": "openride-world", "format_version": "1.4", "live": true})
	for k in range(parts.size()):
		_write_json(dir.path_join("route").path_join("part_%d.json" % k), parts[k])


func _same_samples(a, b, length: float, what: String) -> void:
	var worst := 0.0
	var s := 0.0
	while s <= length + 5.0:
		var pa: Dictionary = a.sample(s)
		var pb: Dictionary = b.sample(s)
		for key in ["x", "y", "z", "lat", "lon", "alt_m", "grade_pct", "heading_deg"]:
			worst = maxf(worst, absf(float(pa[key]) - float(pb[key])))
		s += 13.7
	_check(worst < 1e-6, "%s : écart maximal %s" % [what, str(worst)])


func _remove_tree(path: String) -> void:
	var d := DirAccess.open(path)
	if d == null:
		return
	for sub in d.get_directories():
		_remove_tree(path.path_join(sub))
	for f in d.get_files():
		d.remove(f)
	DirAccess.remove_absolute(path)


func _init() -> void:
	var base := "user://w10_parts_%d" % OS.get_process_id()

	# 1. Les vecteurs de référence découpés en parties de 30 m donnent les mêmes valeurs.
	var doc = JSON.parse_string(FileAccess.get_file_as_string(
		ProjectSettings.globalize_path("res://").path_join("../docs/contracts/world/route_test_vectors.json").simplify_path()))
	for case in doc["cases"]:
		if case["route"]["type"] != "open":
			continue
		var whole = RouteDataScript.new()
		whole.load_route_dict(case["route"])
		var dir := base.path_join("vec")
		_write_world(dir, _split(case["route"], 30.0))
		var live = RouteDataScript.new()
		_check(live.load_live_dir(dir), "%s : parties chargées (%d)" % [case["name"], live.parts.size()])
		_check(absf(live.length_m - whole.length_m) < 1e-9, "%s : même longueur" % case["name"])
		_same_samples(live, whole, whole.length_m, case["name"] + " en parties")

	# 2. Route de 5 400 m en parties de 1 km ; remplacement à partir de la partie 3.
	var whole_a := _synthetic(5400.0)
	var parts_a := _split(whole_a, 1000.0)
	_check(parts_a.size() == 6, "5 400 m = 6 parties")
	var dir_a := base.path_join("a")
	_write_world(dir_a, parts_a)
	var live_a = RouteDataScript.new()
	_check(live_a.load_live_dir(dir_a) and live_a.live, "monde vivant chargé")
	var ref_a = RouteDataScript.new()
	ref_a.load_route_dict(whole_a)
	_same_samples(live_a, ref_a, 5400.0, "route de 5 400 m")
	_check(live_a.parts.size() == 6 and not live_a.is_loop(), "6 parties, route ouverte")

	var before: Array = live_a.parts.duplicate()
	var whole_b := _synthetic(7300.0)          # autre route : mêmes 3 premiers km, puis prolongée
	var parts_b := _split(whole_b, 1000.0)
	var mixed := parts_a.slice(0, 3) + parts_b.slice(3)
	_write_world(dir_a, mixed)
	var res := RouteDataScript.read_parts(dir_a, 3)
	_check(res["ok"] and res["parts"].size() == 5, "lecture des parties 3 à 7")
	var fresh = live_a.revised_from(3, res["parts"])
	_check(fresh != null and absf(fresh.length_m - 7300.0) < 1e-9, "route révisée : 7 300 m")
	_check(live_a.parts.size() == 6 and absf(live_a.length_m - 5400.0) < 1e-9, "l'ancienne route ne change pas")
	var kept := true
	for i in range(3):
		kept = kept and is_same(fresh.parts[i], before[i])
	_check(kept, "parties 0 à 2 : mêmes objets")
	_check(not is_same(fresh.parts[3], before[3]), "partie 3 relue")
	var ref_b = RouteDataScript.new()
	ref_b.load_route_dict(_synthetic(7300.0))
	_same_samples(fresh, ref_b, 7300.0, "route révisée")
	_check(live_a.reload_from_part(3) and absf(live_a.length_m - 7300.0) < 1e-9, "reload_from_part(3) en place")

	# 3. Parties incohérentes : l'ancienne route reste.
	var broken := parts_b.slice(0, 3)
	var gap: Dictionary = parts_b[4].duplicate(true)
	broken.append(gap)                           # s0_m = 4 000 après 3 000 : trou
	var length_before: float = live_a.length_m
	live_a.quiet_errors = true
	_check(not live_a.replace_parts(0, broken), "trou entre deux parties refusé")
	_check(absf(live_a.length_m - length_before) < 1e-9 and live_a.parts.size() == 8, "route inchangée après refus")
	var absent = RouteDataScript.new()
	absent.quiet_errors = true
	_check(not absent.load_live_dir(base.path_join("absent")), "dossier absent refusé")
	var plain := base.path_join("plain")
	_write_json(plain.path_join("manifest.json"), {"format": "openride-world", "format_version": "1.3"})
	var dead = RouteDataScript.new()
	dead.quiet_errors = true
	_check(not dead.load_live_dir(plain), "monde non vivant refusé")

	_remove_tree(base)
	print("test_route_parts : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
