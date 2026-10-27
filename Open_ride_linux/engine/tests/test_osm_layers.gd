extends SceneTree

## Tests sans écran de la lecture des couches OSM `osm_layers.gd` (Lot K4).
## Données produites par le vrai compilateur, sans réseau : engine/tests/make_osm_world.py.
## Lancement : godot --headless --path engine --script res://tests/test_osm_layers.gd -- <osm-test.world> <expected.json>

const OsmLayers := preload("res://scripts/osm_layers.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")

const TMP := "user://test_osm_layers_k4"

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _write(layer: String, k: int, text: String) -> void:
	var dir := ProjectSettings.globalize_path(TMP.path_join(layer))
	DirAccess.make_dir_recursive_absolute(dir)
	var f := FileAccess.open(TMP.path_join(layer).path_join("chunk_%d.json" % k), FileAccess.WRITE)
	f.store_string(text)
	f.close()


func _route(length: float, loop: bool):
	var n := int(ceil(length / 10.0)) + 1
	var d := {"version": "1.0", "ds_m": 10.0, "n": n, "length_m": length, "type": "loop" if loop else "open",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	var radius := length / TAU
	for i in range(n):
		var si := minf(i * 10.0, length)
		var ang := TAU * si / length
		d["lat"].append(45.0)
		d["lon"].append(6.0)
		d["alt_m"].append(100.0)
		d["x"].append(radius * sin(ang) if loop else 0.0)
		d["z"].append(radius * (1.0 - cos(ang)) if loop else -si)
		d["grade_pct"].append(0.0)
		d["heading_deg"].append(0.0)
	var route = RouteDataScript.new()
	route.load_route_dict(d)
	return route


func _test_compiled_world(world_dir: String, expected_path: String) -> void:
	var expected = JSON.parse_string(FileAccess.get_file_as_string(expected_path))
	var manifest = JSON.parse_string(FileAccess.get_file_as_string(world_dir.path_join("manifest.json")))
	if typeof(expected) != TYPE_DICTIONARY or typeof(manifest) != TYPE_DICTIONARY:
		_check(false, "données de test lisibles (%s, %s)" % [world_dir, expected_path])
		return
	var present := OsmLayers.layers_present(manifest)
	_check(present == ["terrain", "buildings", "vegetation", "poi", "water"], "layers_present : %s" % str(present))
	var route = RouteDataScript.new()
	route.load_world_dir(world_dir)
	var all_chunks: Array[int] = OsmLayers.chunks_for_window(0.0, route.length_m, route)
	for layer in OsmLayers.OSM_LAYERS:
		var totals := {}
		var ignored := 0
		var files: Dictionary = expected["files"][layer]
		var per_chunk_ok := true
		for k in all_chunks:
			var res: Dictionary = OsmLayers.load_chunk(world_dir, layer, k)
			if not files.has(str(k)):
				per_chunk_ok = per_chunk_ok and not res["ok"]   # pas de fichier pour ce tronçon
				continue
			per_chunk_ok = per_chunk_ok and res["ok"]
			ignored += int(res["ignored"])
			var counts: Dictionary = files[str(k)]
			for key in counts.keys():
				var got: int = (res.get(key, res["items"]) as Array).size() if layer == "water" else (res["items"] as Array).size()
				per_chunk_ok = per_chunk_ok and got == int(counts[key])
				totals[key] = int(totals.get(key, 0)) + got
		var man: Dictionary = expected["manifest"][layer]
		var match_manifest := true
		match layer:
			"buildings", "vegetation", "poi":
				var key: String = {"buildings": "buildings", "vegetation": "areas", "poi": "points"}[layer]
				match_manifest = int(totals.get(key, 0)) == int(man["count"])
			"water":
				match_manifest = int(totals.get("lines", 0)) == int(man["lines_count"]) \
					and int(totals.get("areas", 0)) == int(man["areas_count"])
		_check(per_chunk_ok and match_manifest and ignored == 0,
			"%s : éléments lus %s = comptes du compilateur %s, tronçon par tronçon" % [layer, str(totals), str(man)])


func _test_corrupted() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(TMP))
	var ring := "[[0, 0], [10, 0], [10, 10]]"
	var area := "{\"id\": \"w1\", \"kind\": \"wood\", \"outer\": %s, \"holes\": [], \"density\": %s}"
	_write("vegetation", 0, "{\"version\": \"1.0\", \"areas\": [")   # JSON invalide
	var r0: Dictionary = OsmLayers.load_chunk(TMP, "vegetation", 0)
	_check(not r0["ok"] and "JSON invalide" in r0["error"], "JSON invalide : ok = faux (%s)" % r0["error"])
	_write("vegetation", 1, "{\"version\": \"1.0\", \"areas\": [%s, %s]}" % [
		area % ["[[0, 0], [10, 0]]", "0.5"], area % [ring, "0.5"]])
	var r1: Dictionary = OsmLayers.load_chunk(TMP, "vegetation", 1)
	_check(r1["ok"] and r1["items"].size() == 1 and r1["ignored"] == 1, "anneau de 2 points : élément ignoré et compté")
	_write("vegetation", 2, "{\"version\": \"1.0\", \"areas\": [%s]}" % (area % [ring, "1.5"]))
	var r2: Dictionary = OsmLayers.load_chunk(TMP, "vegetation", 2)
	_check(r2["ok"] and r2["items"].is_empty() and r2["ignored"] == 1, "density 1,5 : élément ignoré et compté")
	_write("vegetation", 3, "{\"version\": \"1.0\", \"areas\": [%s]}" % (area % [ring, "0.5"]).replace("wood", "meadow"))
	var r3: Dictionary = OsmLayers.load_chunk(TMP, "vegetation", 3)
	_check(r3["ok"] and r3["items"].is_empty() and r3["ignored"] == 1, "kind inconnu : élément ignoré et compté")
	_write("vegetation", 4, "{\"version\": \"2.0\", \"areas\": [%s]}" % (area % [ring, "0.5"]))
	var r4: Dictionary = OsmLayers.load_chunk(TMP, "vegetation", 4)
	_check(not r4["ok"] and "2.0" in r4["error"], "version 2.0 refusée (%s)" % r4["error"])
	_write("vegetation", 5, "{\"version\": \"1.3\", \"futur\": true, \"areas\": [%s]}" % (area % [ring, "0.5"]).replace("\"density\"", "\"autre\": 1, \"density\""))
	var r5: Dictionary = OsmLayers.load_chunk(TMP, "vegetation", 5)
	_check(r5["ok"] and r5["items"].size() == 1, "version 1.3 et champs inconnus : acceptés")
	var r6: Dictionary = OsmLayers.load_chunk(TMP, "vegetation", 99)
	_check(not r6["ok"] and "absent" in r6["error"], "fichier absent : ok = faux, message")
	_write("buildings", 0, "{\"version\": \"1.0\", \"buildings\": [{\"id\": \"w1\", \"outer\": %s, \"holes\": [], \"base_y\": 10, \"height_m\": 0, \"roof\": \"flat\", \"hint\": {}}, {\"id\": \"w2\", \"outer\": %s, \"holes\": [[[1, 1], [2, 1]]], \"base_y\": 10, \"height_m\": 5, \"roof\": \"flat\", \"hint\": {}}, {\"id\": \"w3\", \"outer\": %s, \"holes\": [], \"base_y\": 10, \"height_m\": 5, \"roof\": \"flat\", \"hint\": {}}]}" % [ring, ring, ring])
	var r7: Dictionary = OsmLayers.load_chunk(TMP, "buildings", 0)
	_check(r7["ok"] and r7["items"].size() == 1 and r7["ignored"] == 2, "bâtiments : hauteur nulle et trou de 2 points ignorés")
	_write("water", 0, "{\"version\": \"1.0\", \"lines\": [{\"id\": \"w1\", \"kind\": \"river\", \"width_m\": 3, \"points\": [[0, 0, 1], [5, 5]]}], \"areas\": []}")
	var r8: Dictionary = OsmLayers.load_chunk(TMP, "water", 0)
	_check(r8["ok"] and r8["lines"].is_empty() and r8["ignored"] == 1, "eau : point de rivière sans altitude ignoré")
	_write("poi", 0, "{\"version\": \"1.0\"}")
	var r9: Dictionary = OsmLayers.load_chunk(TMP, "poi", 0)
	_check(not r9["ok"] and "points" in r9["error"], "liste absente : ok = faux (%s)" % r9["error"])
	_write("poi", 1, "[1, 2]")
	_check(not OsmLayers.load_chunk(TMP, "poi", 1)["ok"], "racine qui n'est pas un objet : ok = faux")
	var m2 := {"format_version": "2.0", "layers": {"buildings": {"present": true}}}
	_check(OsmLayers.layers_present(m2).is_empty(), "manifeste de version 2.0 : aucune couche")
	var m1 := {"format_version": "1.1", "layers": {"buildings": {"present": false}, "poi": {"present": true},
		"roads3d": {"present": true}}}
	_check(OsmLayers.layers_present(m1) == ["poi"], "couche absente et couche inconnue ignorées")


func _test_chunks_for_window() -> void:
	var open = _route(3500.0, false)
	_check(OsmLayers.chunks_for_window(-500.0, 900.0, open) == [0], "ouvert : fenêtre [−500 ; 900] → [0]")
	_check(OsmLayers.chunks_for_window(999.0, 1000.0, open) == [0, 1], "ouvert : [999 ; 1 000] → [0, 1]")
	_check(OsmLayers.chunks_for_window(2500.0, 8000.0, open) == [2, 3], "ouvert : [2 500 ; 8 000] → [2, 3] (fin à 3 500 m)")
	var exact = _route(3000.0, false)
	_check(OsmLayers.chunks_for_window(2500.0, 3000.0, exact) == [2, 3],
		"ouvert de 3 000 m : la fin est dans le tronçon 3 (comme le compilateur)")
	var loop = _route(3500.0, true)
	_check(OsmLayers.chunks_for_window(3200.0, 4600.0, loop) == [3, 0, 1], "boucle : [3 200 ; 4 600] traverse l'arrivée → [3, 0, 1]")
	_check(OsmLayers.chunks_for_window(-300.0, 500.0, loop) == [3, 0], "boucle : [−300 ; 500] → [3, 0]")
	_check(OsmLayers.chunks_for_window(7100.0, 7900.0, loop) == [0], "boucle, deuxième tour : [7 100 ; 7 900] → [0]")
	_check(OsmLayers.chunks_for_window(0.0, 9000.0, loop) == [0, 1, 2, 3], "boucle : fenêtre de plus d'un tour → tous")


func _test_performance() -> void:
	var items := []
	for i in range(200):
		var x := 15.0 * (i % 20)
		var z := 15.0 * (i / 20)
		items.append({"id": "w%d" % i, "outer": [[x, z], [x + 10.0, z], [x + 10.0, z + 8.0], [x + 4.0, z + 11.0], [x, z + 8.0]],
			"holes": [], "base_y": 1200.0 + i * 0.1, "height_m": 8.0, "roof": "flat", "hint": {"building": "house", "colour": null}})
	_write("buildings", 7, JSON.stringify({"version": "1.0", "buildings": items}))
	OsmLayers.load_chunk(TMP, "buildings", 7)
	var box := [0]   # les lambdas capturent par valeur : résultat rangé dans un tableau
	var best := PerfBudget.measure_ms(func(): box[0] = (OsmLayers.load_chunk(TMP, "buildings", 7)["items"] as Array).size(), 3, 0)
	var n: int = box[0]
	print("Mesure : tronçon de %d bâtiments lu en %.2f ms" % [n, best])
	_check(n == 200 and PerfBudget.check("osm_buildings_200", best),
		"200 bâtiments lus, temps dans le budget (%.2f ms)" % best)


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() < 2:
		printerr("[ÉCHEC] Usage : … --script res://tests/test_osm_layers.gd -- <osm-test.world> <expected.json>")
		print("test_osm_layers : 1 vérifications, 1 échecs")
		quit(1)
		return
	_test_compiled_world(args[0], args[1])
	_test_corrupted()
	_test_chunks_for_window()
	_test_performance()
	print("test_osm_layers : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
