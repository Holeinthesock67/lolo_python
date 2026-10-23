extends SceneTree

## Vérifie route_data.gd contre les vecteurs partagés docs/contracts/world/route_test_vectors.json.
## Lancement : godot --headless --path engine --script res://tests/test_route_vectors.gd [-- <vecteurs.json>]
## Code de sortie : 0 si tous les vecteurs passent, 1 sinon.

const RouteDataScript := preload("res://scripts/route_data.gd")


func _vectors_path() -> String:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		return args[0]
	return ProjectSettings.globalize_path("res://").path_join("../docs/contracts/world/route_test_vectors.json").simplify_path()


func _angle_diff(a: float, b: float) -> float:
	var d := fposmod(a - b, 360.0)
	return minf(d, 360.0 - d)


func _init() -> void:
	var path := _vectors_path()
	var doc = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(doc) != TYPE_DICTIONARY:
		printerr("Vecteurs illisibles : ", path)
		quit(1)
		return
	var tol: Dictionary = doc["tolerances"]
	var checked := 0
	var failures := 0
	for case in doc["cases"]:
		var route = RouteDataScript.new()
		if not route.load_route_dict(case["route"]):
			printerr("[", case["name"], "] chargement refusé : ", route.load_error)
			failures += 1
			continue
		for expected in case["samples"]:
			var got: Dictionary = route.sample(float(expected["s"]))
			var errs := []
			var dp := Vector3(got["x"] - expected["x"], got["y"] - expected["y"], got["z"] - expected["z"]).length()
			if dp > float(tol["position_m"]):
				errs.append("position écart %.6f m" % dp)
			if absf(got["grade_pct"] - expected["grade_pct"]) > float(tol["grade_pct"]):
				errs.append("pente %.6f au lieu de %.6f" % [got["grade_pct"], expected["grade_pct"]])
			if _angle_diff(got["heading_deg"], expected["heading_deg"]) > float(tol["heading_deg"]):
				errs.append("cap %.6f au lieu de %.6f" % [got["heading_deg"], expected["heading_deg"]])
			for key in ["lat", "lon"]:
				if absf(got[key] - expected[key]) > float(tol["latlon_deg"]):
					errs.append(key + " écart")
			if absf(got["alt_m"] - expected["alt_m"]) > float(tol["alt_m"]):
				errs.append("altitude écart")
			if absf(route.wrap_s(float(expected["s"])) - float(expected["wrapped_s"])) > 1e-9:
				errs.append("wrap différent")
			checked += 1
			if errs.size() > 0:
				failures += 1
				printerr("[", case["name"], "] s = ", expected["s"], " : ", ", ".join(errs))
	print("Vecteurs de route vérifiés : %d, échecs : %d" % [checked, failures])
	quit(1 if failures > 0 else 0)
