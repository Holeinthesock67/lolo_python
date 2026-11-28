extends SceneTree

## Tests sans écran de loop_chunks.gd (revue E7-02 et E8-02) : numéro continu de la fenêtre au passage de la
## ligne dans les deux sens, numéro dans le tour, fin du dernier tronçon, parcours ouvert inchangé.
## Lancement : godot --headless --path engine --script res://tests/unit/test_loop_chunks.gd

const LoopChunks := preload("res://scripts/loop_chunks.gd")
const LoopRoute := preload("res://tests/loop_route.gd")
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


func _init() -> void:
	var route = LoopRoute.circle(101)   # 1 010 m : 26 tronçons de 40 m, le dernier de 10 m
	_check(route.is_loop() and is_equal_approx(route.length_m, 1010.0), "boucle de test : %.0f m" % route.length_m)
	var lc = LoopChunks.new(route, 40.0)
	_check(lc.is_loop() and lc.count() == 26, "26 tronçons par tour (%d)" % lc.count())
	# En avant : 24, 25, puis la ligne (0, 1) : numéros continus 26, 27, puis un tour complet
	var seq := []
	for k in [23, 24, 25, 0, 1, 2]:
		seq.append(lc.unwrap(k))
	_check(seq == [23, 24, 25, 26, 27, 28], "passage de la ligne en avant : %s" % str(seq))
	for k in range(3, 26):
		lc.unwrap(k)
	_check(lc.unwrap(0) == 52 and lc.key(52) == 0 and lc.key(51) == 25, "deuxième tour : 52, tronçon 0 du tour")
	# À rebours (demi-tour) : la ligne repassée vers l'arrière
	var back := []
	for k in [1, 0, 25, 24]:
		back.append(lc.unwrap(k))
	_check(back == [53, 52, 51, 50], "passage de la ligne à rebours : %s" % str(back))
	_check(lc.key(-1) == 25 and lc.key(-26) == 0, "numéro dans le tour des tronçons d'avant le départ")
	_check(lc.in_lap(1009.9) and not lc.in_lap(1010.0) and not lc.in_lap(1015.0) and lc.in_lap(0.0),
		"fin du dernier tronçon (au-delà de 1 010 m) hors du tour")
	# Parcours ouvert : rien ne change
	var open = RouteDataScript.new()
	open.load_route_dict({"version": "1.0", "ds_m": 10.0, "n": 3, "length_m": 20.0, "type": "open",
		"lat": [45.0, 45.0, 45.0], "lon": [6.0, 6.0, 6.0], "alt_m": [0.0, 0.0, 0.0], "x": [0.0, 0.0, 0.0],
		"z": [0.0, 10.0, 20.0], "grade_pct": [0.0, 0.0, 0.0], "heading_deg": [180.0, 180.0, 180.0]})
	var lo = LoopChunks.new(open, 40.0)
	_check(not lo.is_loop() and lo.unwrap(5) == 5 and lo.unwrap(0) == 0 and lo.key(-3) == -3 and lo.in_lap(1.0e6),
		"parcours ouvert : numéros d'origine")
	var none = LoopChunks.new()
	_check(not none.is_loop() and none.unwrap(7) == 7, "sans parcours : numéros d'origine")
	print("test_loop_chunks : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
