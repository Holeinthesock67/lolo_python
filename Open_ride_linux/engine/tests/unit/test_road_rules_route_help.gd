extends SceneTree

## Petits modèles sans test jusque-là (audit du 22/11, R12) :
## - road_rules.gd, jumelle de `draft.pass_window` du core : mêmes constantes et mêmes fenêtres sur trois cas
##   (valeurs relevées sur le core ; un écart de l'une des deux copies fait échouer ce test) ;
## - ridden_distance.gd (lot N17) : distance croissante après un demi-tour, tour de boucle, saut, nouvelle séance ;
## - route_help.gd (lot O22) : un élément par sujet, carte de chaque sujet, sujet inconnu vide.
## Lancement : godot --headless --path engine --script res://tests/unit/test_road_rules_route_help.gd

const RoadRules := preload("res://scripts/road_rules.gd")
const RiddenDistance := preload("res://scripts/ridden_distance.gd")
const RouteHelp := preload("res://scripts/route_help.gd")

var _failures := 0
var _checked := 0


func _init() -> void:
	_road_rules()
	_ridden_distance()
	_route_help()
	print("test_road_rules_route_help : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _near(a: float, b: float) -> bool:
	return absf(a - b) < 1e-4


func _road_rules() -> void:
	# core : draft.PASS_SAFETY_S, PASS_MARGIN_M, BIKE_LENGTH_M
	_check(RoadRules.PASS_SAFETY_S == 1.0 and RoadRules.PASS_MARGIN_M == 0.3 and RoadRules.BIKE_LENGTH_M == 1.7,
		"constantes égales à celles du core")
	# core : draft.pass_window(len_a, len_b, closing_mps, lateral_m, lateral_mps)
	var cases := [
		[[1.7, 1.7, 2.0, 0.8, 1.0], Vector2(-5.6, 3.6)],
		[[1.7, 4.5, 0.1, 1.5, 0.05], Vector2(-11.4, 10.9)],   # rapprochement et décalage sous leurs planchers
		[[1.7, 1.7, 5.0, -0.6, 2.0], Vector2(-8.5, 3.5)],     # décalage vers la gauche : même fenêtre
	]
	for c in cases:
		var a: Array = c[0]
		var w := RoadRules.pass_window(a[0], a[1], a[2], a[3], a[4])
		_check(_near(w.x, c[1].x) and _near(w.y, c[1].y), "pass_window%s = %s (core), lu %s" % [str(a), str(c[1]), str(w)])


func _ridden_distance() -> void:
	var d = RiddenDistance.new()
	_check(is_nan(d.push(NAN, 0.0)), "aucune position : distance inconnue")
	_check(d.push(100.0, 1.0) == 100.0, "première trame : distance = s")
	_check(d.push(130.0, 2.0) == 130.0, "en avançant : +Δs")
	_check(d.push(110.0, 3.0) == 150.0, "après un demi-tour (s décroît) : la distance croît encore")
	_check(d.push(NAN, 4.0) == 150.0, "trame sans position : distance inchangée")
	_check(d.push(2000.0, 5.0) == 2000.0, "saut de plus de RESET_JUMP_M : repart de s")
	_check(d.push(50.0, 1.0) == 50.0, "temps qui repart en arrière (nouvelle séance) : repart de s")
	var loop = RiddenDistance.new()
	loop.push(990.0, 1.0, 1000.0)
	_check(loop.push(10.0, 2.0, 1000.0) == 1010.0, "ligne d'une boucle franchie en avant : +20 m, pas un saut")
	_check(loop.push(995.0, 3.0, 1000.0) == 1025.0, "ligne franchie en arrière (demi-tour) : +15 m")
	loop.reset()
	_check(is_nan(loop.distance_m) and loop.push(5.0, 0.0) == 5.0, "reset : distance oubliée, repart de s")


func _route_help() -> void:
	var items := RouteHelp.items()
	_check(items.size() == RouteHelp.TOPICS.size() and items.size() > 0, "un élément par sujet")
	for it in items:
		var topic := str(it["id"]).trim_prefix("help:")
		var sheet := RouteHelp.sheet(topic)
		_check(str(it["id"]).begins_with("help:") and it["enabled"], "« %s » : id help:…, actif" % it["label"])
		_check(sheet.get("title") == RouteHelp.TITLE and sheet.get("name") == it["label"]
			and not (sheet.get("lines", []) as Array).is_empty(), "« %s » : carte titrée, avec des lignes" % it["label"])
	_check(RouteHelp.sheet("inconnu").is_empty(), "sujet inconnu : carte vide")
	var s := RouteHelp.sheet("choose")
	(s["lines"] as Array).clear()
	_check(not (RouteHelp.sheet("choose")["lines"] as Array).is_empty(), "la carte rendue est une copie")
