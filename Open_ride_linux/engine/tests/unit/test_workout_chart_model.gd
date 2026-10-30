extends SceneTree

## Tests unitaires sans écran du modèle des courbes de la séance (workout_chart_model.gd, lot O13).
## Lancement : godot --headless --path engine --script res://tests/unit/test_workout_chart_model.gd

const PerfBudget := preload("res://tests/perf_budget.gd")
const ChartModel := preload("res://scripts/workout_chart_model.gd")
const ErgView := preload("res://scripts/erg_view.gd")

## sweet_spot_3x10.zwo tel que le core l'envoie (triplets du contrat v1.1).
const SWEET_SPOT := [
	[600, 0.50, 0.75],
	[600, 0.90, 0.90], [300, 0.55, 0.55],
	[600, 0.90, 0.90], [300, 0.55, 0.55],
	[600, 0.90, 0.90], [300, 0.55, 0.55],
	[300, 0.60, 0.45],
]

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _near(a: float, b: float, eps: float = 0.01) -> bool:
	return absf(a - b) <= eps


func _init() -> void:
	var nodes_before := Performance.get_monitor(Performance.OBJECT_NODE_COUNT)
	_test_sampling()
	_test_pause()
	_test_profile()
	_test_long_session()
	_test_smoothing()
	_test_free_ride()
	_test_ticks()
	var nodes_after := Performance.get_monitor(Performance.OBJECT_NODE_COUNT)
	_check(nodes_after == nodes_before, "aucun nœud créé")
	print("test_workout_chart_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)


## Critère 2 : 90 trames à 30 Hz donnent 3 points, moyennes de leur seconde ; trous.
func _test_sampling() -> void:
	var m = ChartModel.new()
	for k in range(90):
		var sec := k / 30
		var power := 100.0 + 100.0 * sec + float(k % 2) * 10.0   # moyenne 105, 205, 305
		var hr: Variant = 0 if sec == 1 else 140
		var cad: Variant = null if sec == 2 else 90.0
		m.push(k / 30.0, power, hr, cad, 200.0)
	_check(m.point_count() == 3, "90 trames à 30 Hz : 3 points (%d)" % m.point_count())
	var p: PackedFloat32Array = m.values("power")
	_check(p.size() == 3 and _near(p[0], 105.0) and _near(p[1], 205.0) and _near(p[2], 305.0),
		"chaque point est la moyenne de sa seconde (%s)" % str(p))
	var hr_v: PackedFloat32Array = m.values("hr")
	_check(_near(hr_v[0], 140.0) and is_nan(hr_v[1]) and _near(hr_v[2], 140.0), "FC à 0 : trou, pas zéro")
	var cad_v: PackedFloat32Array = m.values("cadence")
	_check(_near(cad_v[1], 90.0) and is_nan(cad_v[2]), "cadence null : trou")
	var g: Dictionary = m.geometry(300.0, 100.0)
	_check(g["curves"]["hr"].size() == 2, "courbe de FC coupée en deux au trou")
	_check(g["curves"]["power"].size() == 1 and g["curves"]["power"][0].size() == 3, "courbe de puissance : 3 points")
	var cur: Dictionary = m.current_values()
	_check(_near(float(cur["power"]), 305.0) and cur["cadence"] == null, "valeurs courantes de la dernière seconde")
	m.reset()
	_check(m.point_count() == 0 and m.values("power").is_empty(), "reset vide les séries")


## Critère 3 : pause de 20 s, aucun point ajouté, curseur figé.
func _test_pause() -> void:
	var m = ChartModel.new()
	m.set_workout(SWEET_SPOT, 250.0, 3600.0)
	for k in range(300):
		m.push(k / 30.0, 200.0, 130, 85.0, 200.0)
	var before := m.point_count()
	var cursor_before: float = m.geometry(800.0, 200.0)["cursor_x"]
	for _k in range(600):   # 20 s de trames en pause : temps de séance figé à 9,966 s
		m.push(299 / 30.0, 0.0, 120, 0.0, null)
	_check(m.point_count() == before, "pause : aucun point ajouté (%d)" % m.point_count())
	_check(_near(m.geometry(800.0, 200.0)["cursor_x"], cursor_before), "pause : curseur figé")
	m.push(10.0, 210.0, 131, 86.0, 200.0)
	_check(m.point_count() == before + 1, "reprise : la séance avance de nouveau")
	m.push(13.2, 210.0, 131, 86.0, 200.0)
	var p: PackedFloat32Array = m.values("power")
	_check(p.size() == 14 and is_nan(p[11]) and is_nan(p[12]), "secondes sans trame : trous")


## Critère 4 : profil sweet_spot_3x10 à FTP 250 W.
func _test_profile() -> void:
	var m = ChartModel.new()
	m.set_workout(SWEET_SPOT, 250.0, 3600.0)
	_check(_near(m.duration_s, 3600.0), "durée du profil : 3 600 s")
	var sc: Dictionary = m.scales()
	_check(_near(sc["watts"][1], 400.0), "échelle des watts : 400 W (%s)" % str(sc["watts"]))
	_check(_near(sc["hr"][0], 60.0) and _near(sc["hr"][1], 190.0) and _near(sc["cadence"][1], 140.0),
		"échelles FC 60–190 et cadence 0–140")
	var g: Dictionary = m.geometry(3600.0, 400.0)   # 1 px par seconde, 1 px par watt
	var polys: Array = g["profile"]
	# Échauffement 125 → 187,5 W coupé au seuil Z1/Z2 (137,5 W) ; retour au calme 150 → 112,5 W aussi.
	_check(polys.size() == 10, "8 blocs, 2 rampes coupées à un seuil de zone : 10 polygones (%d)" % polys.size())
	var warm_a: Dictionary = polys[0]
	var warm_b: Dictionary = polys[1]
	_check(_near(warm_a["t1"], 120.0, 0.5) and warm_a["zone"] == 0 and warm_b["zone"] == 1,
		"échauffement : Z1 jusqu'à 137,5 W (120 s), puis Z2")
	var pa: PackedVector2Array = warm_a["polygon"]
	_check(_near(pa[1].y, 400.0 - 125.0, 0.1) and _near(pa[2].y, 400.0 - 137.5, 0.1), "rampe : hauteurs de début et de fin")
	var work: Dictionary = polys[2]
	var pw: PackedVector2Array = work["polygon"]
	_check(_near(work["t0"], 600.0) and _near(work["t1"], 1200.0) and _near(pw[1].y, 175.0) and _near(pw[2].y, 175.0),
		"bloc à 90 % : marche de 225 W de 600 à 1 200 s")
	_check(work["zone"] == 3 and work["color"] == ErgView.ZONE_COLORS[3], "225 W à FTP 250 : zone 4 (seuil), couleur juste")
	_check(polys[3]["zone"] == 1 and polys[3]["color"] == ErgView.ZONE_COLORS[1], "récupération à 55 % : zone 2")
	var cool_a: Dictionary = polys[8]
	var cool_b: Dictionary = polys[9]
	_check(cool_a["zone"] == 1 and cool_b["zone"] == 0 and _near(cool_b["t1"], 3600.0), "retour au calme : Z2 puis Z1, fin à 3 600 s")
	m.set_ftp(200.0)
	m.set_workout_w([[60, 150, 150], [60, null, null]], 120.0)
	var gw: Dictionary = m.geometry(120.0, 400.0)
	_check(gw["profile"].size() == 1, "profil en watts (.erg) : case sans cible ignorée (pas de roue libre, lot O19)")
	var nf = ChartModel.new()
	nf.set_workout_w([[60, 150, 150]], 60.0)
	var gn: Dictionary = nf.geometry(60.0, 400.0)
	_check(gn["profile"][0]["zone"] == -1 and gn["profile"][0]["color"] == ErgView.NEUTRAL_COLOR, "sans FTP connue : gris neutre")
	_check(gw["profile"][0]["zone"] == 2, "150 W à FTP 200 (75 %) : zone 3")


## Critère 5 : 2 h de séance, au plus 1 800 points par courbe, géométrie en moins de 5 ms.
func _test_long_session() -> void:
	var m = ChartModel.new()
	m.set_workout([[7200, 0.7, 0.7]], 250.0, 7200.0)
	for s in range(7200):
		m.push(float(s), 175.0 + float(s % 30), 140 + s % 5, 90.0, 175.0)
	_check(m.point_count() == 7200, "2 h : 7 200 points bruts")
	var t0 := Time.get_ticks_usec()
	var g: Dictionary = m.geometry(1600.0, 300.0)
	var dt_ms := (Time.get_ticks_usec() - t0) / 1000.0
	var drawn := 0
	for line in g["curves"]["power"]:
		drawn += line.size()
	_check(drawn <= ChartModel.MAX_DRAWN_POINTS and g["group"] == 4, "au plus 1 800 points dessinés (%d, groupes de %d)" % [drawn, g["group"]])
	_check(PerfBudget.check("workout_chart_geometry", dt_ms), "géométrie de 2 h de courbes en %.2f ms" % dt_ms)
	var w_top: float = g["scales"]["watts"][1]
	var slow: Array = ChartModel._polylines(m.smoothed("power", 0, 0, 7200), 0, 4, 1600.0, 300.0, 0.0, 7200.0, 0.0, w_top)
	var fast: PackedVector2Array = g["curves"]["power"][0]
	_check(slow.size() == 1 and slow[0].size() == fast.size() and slow[0][0].distance_to(fast[0]) < 0.01
		and slow[0][1799].distance_to(fast[1799]) < 0.01 and slow[0][900].distance_to(fast[900]) < 0.01,
		"groupes tenus à jour : mêmes points que le calcul seconde par seconde")
	var t1 := Time.get_ticks_usec()
	m.geometry(1600.0, 300.0)
	_check(PerfBudget.check("workout_chart_cached", (Time.get_ticks_usec() - t1) / 1000.0), "même seconde : géométrie en cache")
	_check(ChartModel.group_factor(1800) == 1 and ChartModel.group_factor(1801) == 2 and ChartModel.group_factor(3600) == 2,
		"facteur de regroupement")
	var t2 := Time.get_ticks_usec()
	for k in range(3000):
		m.push(7200.0 + k / 30.0, 200.0, 140, 90.0, 175.0)
	_check(PerfBudget.check("workout_chart_push", (Time.get_ticks_usec() - t2) / 3000.0 / 1000.0), "push en temps constant")


## Critère 6 : lissage 10 s sur une marche de 100 à 300 W.
func _test_smoothing() -> void:
	var m = ChartModel.new()
	for s in range(40):
		m.push(float(s), 100.0 if s < 20 else 300.0, 120, 80.0, null)
	var raw: PackedFloat32Array = m.smoothed("power", 0)
	var s10: PackedFloat32Array = m.smoothed("power", 10)
	_check(_near(raw[20], 300.0) and _near(s10[19], 100.0), "avant la marche : 100 W")
	_check(_near(s10[20], 120.0) and _near(s10[24], 200.0) and _near(s10[29], 300.0),
		"lissage 10 s : 120, 200 puis 300 W (%.1f, %.1f, %.1f)" % [s10[20], s10[24], s10[29]])
	var s3: PackedFloat32Array = m.smoothed("power", 3)
	_check(_near(s3[21], 700.0 / 3.0), "lissage 3 s")
	_check(_near(m.values("power")[20], 300.0), "valeurs brutes inchangées")
	var part: PackedFloat32Array = m.smoothed("power", 10, 25, 30)
	_check(part.size() == 5 and _near(part[0], s10[25]), "lissage d'une fenêtre : mêmes valeurs")
	m.set_smoothing(10)
	_check(m.smoothing_s == 10, "lissage choisi : 10 s")
	m.set_smoothing(7)
	_check(m.smoothing_s == 0, "lissage inconnu : brut")


## Parcours libre : fenêtre des 10 dernières minutes.
func _test_free_ride() -> void:
	var m = ChartModel.new()
	m.set_ftp(250.0)
	for s in range(900):
		m.push(float(s), 200.0, 130, 90.0, null)
	var win: Vector2 = m.time_window()
	_check(not m.has_profile and _near(win.x, 300.0) and _near(win.y, 900.0), "sans profil : 10 dernières minutes")
	var g: Dictionary = m.geometry(600.0, 100.0)
	_check(g["profile"].is_empty() and g["curves"]["power"][0].size() == 600, "600 points dans la fenêtre")
	_check(_near(g["cursor_x"], 600.0), "curseur au bord droit")
	m.push(900.0, 700.0, 205, 90.0, null)
	m.push(901.0, 700.0, 205, 90.0, null)
	var sc: Dictionary = m.scales()
	_check(_near(sc["watts"][1], 750.0) and _near(sc["hr"][1], 205.0), "échelles suivent la puissance et la FC maximales")


func _test_ticks() -> void:
	var t: PackedFloat32Array = ChartModel.nice_ticks(0.0, 400.0)
	_check(t == PackedFloat32Array([0.0, 100.0, 200.0, 300.0, 400.0]), "graduations des watts : 0 à 400 par 100 (%s)" % str(t))
	var c: PackedFloat32Array = ChartModel.nice_ticks(0.0, 140.0)
	_check(c == PackedFloat32Array([0.0, 50.0, 100.0]), "graduations de la cadence par 50 (%s)" % str(c))
	var h: PackedFloat32Array = ChartModel.nice_ticks(60.0, 190.0)
	_check(_near(h[0], 100.0) or _near(h[0], 60.0), "graduations de la FC (%s)" % str(h))
