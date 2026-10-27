extends SceneTree

## Tests sans écran de la détection des montées `climb_detector.gd` (Lot P14).
## Lancement : godot --headless --path engine --script res://tests/unit/test_climb_detector.gd

const ClimbDetector := preload("res://scripts/climb_detector.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Route droite vers l'est dont la pente (en %) est donnée par `grade.call(s)`.
static func make_route(length_m: float, grade: Callable, type: String = "open"):
	var ds := 10.0
	var n := int(length_m / ds) + 1
	var cols := {"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	var alt := 300.0
	for i in range(n):
		var s := i * ds
		if i > 0:
			alt += float(grade.call(s - ds * 0.5)) / 100.0 * ds
		cols["lat"].append(48.9)
		cols["lon"].append(7.1)
		cols["alt_m"].append(alt)
		cols["x"].append(s)
		cols["z"].append(0.0)
		cols["grade_pct"].append(float(grade.call(s)))
		cols["heading_deg"].append(90.0)
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": (n - 1) * ds, "type": type}
	d.merge(cols)
	var r = RouteDataScript.new()
	r.load_route_dict(d)
	return r


func _col_and_bump(s: float) -> float:
	if s >= 2000.0 and s < 10000.0:
		return 7.0
	if s >= 13000.0 and s < 13400.0:
		return 5.0
	return 0.0


func _two_close(s: float) -> float:
	if s >= 1000.0 and s < 2500.0:
		return 6.0
	if s >= 2700.0 and s < 4200.0:
		return 6.0
	return 0.0


func _short_steep(s: float) -> float:
	return 9.0 if s >= 1000.0 and s < 2000.0 else 0.0


func _rolling(s: float) -> float:
	return 2.0 * sin(s / 300.0)


func _init() -> void:
	var r = make_route(16000.0, Callable(self, "_col_and_bump"))
	var climbs: Array = ClimbDetector.detect(r)
	_check(climbs.size() == 1, "col de 8 km à 7 %% et bosse de 400 m à 5 %% : une seule montée (%d)" % climbs.size())
	if climbs.size() >= 1:
		var c: Dictionary = climbs[0]
		_check(absf(float(c["summit_s"]) - 10000.0) <= 20.0, "sommet à ± 20 m (%.0f m)" % c["summit_s"])
		_check(absf(float(c["avg_grade_pct"]) - 7.0) <= 0.2, "pente moyenne 7,0 %% ± 0,2 (%.2f %%)" % c["avg_grade_pct"])
		_check(absf(float(c["length_m"]) - 8000.0) <= 40.0 and absf(float(c["max_km_grade_pct"]) - 7.0) <= 0.2
			and absf(float(c["summit_alt_m"]) - 860.0) <= 1.0,
			"longueur %.0f m, pente maximale par kilomètre %.2f %%, sommet à %.0f m" % [c["length_m"], c["max_km_grade_pct"], c["summit_alt_m"]])
	var r2 = make_route(6000.0, Callable(self, "_two_close"))
	var c2: Array = ClimbDetector.detect(r2)
	_check(c2.size() == 1 and absf(float(c2[0]["start_s"]) - 1000.0) <= 20.0 and absf(float(c2[0]["summit_s"]) - 4200.0) <= 20.0,
		"deux rampes séparées par 200 m de replat : fusionnées en une montée de 1 000 à 4 200 m")
	var c3: Array = ClimbDetector.detect(make_route(4000.0, Callable(self, "_short_steep")))
	_check(c3.size() == 1 and absf(float(c3[0]["gain_m"]) - 90.0) <= 1.0, "1 km à 9 % (90 m de dénivelé) : gardée")
	var c4: Array = ClimbDetector.detect(make_route(10000.0, Callable(self, "_rolling")))
	_check(c4.is_empty(), "parcours vallonné (bosses de 12 m) : aucune montée (%d)" % c4.size())
	print("test_climb_detector : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
