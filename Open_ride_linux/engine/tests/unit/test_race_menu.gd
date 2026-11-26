extends SceneTree

## Tests sans écran du mode « Course » (course classique contre les bots, lot CR1, contrat 1.23) : entrée de
## l'accueil selon `modes`, écran Prêt (réglages `race.*` et niveau des bots, tours sur une boucle, jusqu'à
## l'arrivée en ligne), `start` avec `mode` « race » sans `bots`, HUD sans case d'objet avec le classement complet
## (bots loin compris) et bilan.
## Lancement : godot --headless --path engine --script res://tests/unit/test_race_menu.gd

const MenuFlow := preload("res://scripts/menu_flow.gd")
const GpHudModel := preload("res://scripts/grandprix/gp_hud_model.gd")

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
	call_deferred("_run")


func _ids(f) -> Array:
	return f.state()["items"].map(func(it): return it["id"])


func _item(f, id: String) -> Dictionary:
	for it in f.state()["items"]:
		if it["id"] == id:
			return it
	return {}


const SETTINGS := {"type": "settings", "v": 1, "items": [
	{"key": "race.opponents", "label": "Course : adversaires", "type": "int", "value": 7, "min": 2, "max": 11, "step": 1, "unit": "", "group": "ride", "applies": "next_session"},
	{"key": "race.laps", "label": "Course : tours de la boucle", "type": "int", "value": 3, "min": 1, "max": 10, "step": 1, "unit": "", "group": "ride", "applies": "next_session"},
	{"key": "bots.objective", "label": "Objectif des bots", "type": "choice", "value": "tempo", "choices": ["recovery", "endurance", "tempo", "threshold", "max"], "group": "ride", "applies": "next_session"}]}

const ROUTES := [{"id": "long", "name": "Longue", "status": "ready", "length_m": 25000.0, "route_type": "point_to_point"},
	{"id": "mini", "name": "Mini", "status": "ready", "length_m": 800.0, "route_type": "point_to_point"},
	{"id": "boucle", "name": "Boucle", "status": "ready", "length_m": 3000.0, "route_type": "loop"}]


func _run() -> void:
	var old = MenuFlow.new()
	old.connect_done = true
	old.menu.set_modes(["ride", "erg", "grandprix"])
	old.on_state({"session_state": "IDLE"})
	_check(not "race" in _ids(old), "core sans « race » dans modes : pas d'entrée")

	var f = MenuFlow.new()
	f.connect_done = true
	f.menu.set_modes(["ride", "erg", "survivor", "grandprix", "race", "track"])
	f.on_settings(SETTINGS.duplicate(true))
	f.set_routes(ROUTES.duplicate(true))
	f.on_state({"session_state": "IDLE"})
	_check("race" in _ids(f) and _item(f, "race")["label"] == "Course", "entrée « Course » à l'accueil")
	_check(str(_item(f, "race")["detail"]).contains("sans objets"), "explication : sans objets")
	_check(_ids(f).find("race") == _ids(f).find("grandprix") + 1, "après le Grand Prix des objets")
	f.menu.focus_item("race")
	var act: Dictionary = f.handle("A_LONG")
	_check(act == {"action": "select_workout", "workout_id": null}, "entrée : SIM seulement (%s)" % str(act))
	_check(f.state()["screen"] == "routes", "sans parcours choisi : la liste des parcours d'abord")
	_check("long" in _ids(f) and "boucle" in _ids(f), "tous les parcours libres proposés")
	f.menu.focus_item("long")
	act = f.handle("A_LONG")
	_check(act.get("action", "") == "select_route" and f.state()["screen"] == "ready", "parcours choisi : écran Prêt")
	_check(str(f.state()["title"]) == "Prêt : Course — Longue", "titre du mode (%s)" % f.state()["title"])
	_check(_ids(f) == ["start", "change_route", "set:race.opponents"],
		"en ligne : pas de tours, pas de ligne Objets (%s)" % str(_ids(f)))
	_check(_item(f, "start")["detail"] == "25,0 km en ligne", "Lancer : jusqu'à l'arrivée (%s)" % _item(f, "start")["detail"])
	# Cote Elo et effort des bots en watts (contrat 1.22) : ligne « Intensité » (lot R1) comme au Grand Prix
	_check(f.wanted_bots_preview() == {"mode": "race"}, "écran Prêt : bots_preview demandé (%s)" % str(f.wanted_bots_preview()))
	f.on_bots_preview({"type": "bots_preview", "v": 1, "request_cmd_id": 9, "mode": "race", "objective": "tempo",
		"ftp_pct": 90.0, "power_w": 225, "duration_s": 2400, "elo": {"rating": 1520, "races": 2}})
	_check(_ids(f)[1] == "intensity" and _item(f, "intensity")["label"] == "Intensité : moyen"
		and _item(f, "intensity")["detail"] == "bots ≈ 225 W", "lot R1 : ligne « Intensité » sous Lancer (%s)" % str(_item(f, "intensity")))
	f.menu.focus_item("intensity")
	_check(str(f.state()["status"]).ends_with("Course estimée à ≈ 40 min. Ta cote : 1520."), "durée et cote dans la ligne d'état")
	_check(f.handle("A_LONG") == {"action": "set_setting", "key": "bots.objective", "value": "max"}, "Course : moyen → dur")
	_check(_item(f, "set:race.opponents")["label"] == "Adversaires" and _item(f, "set:race.opponents")["detail"] == "7",
		"réglage : libellé court et valeur")
	f.menu.focus_item("set:race.opponents")
	f.handle("A_LONG")
	f.handle("PLUS_SHORT")
	act = f.handle("A_LONG")
	_check(act == {"action": "set_setting", "key": "race.opponents", "value": 8}, "adversaires : set_setting (%s)" % str(act))
	_check(f.wanted_bots_preview() == {"mode": "race"}, "adversaires changés : bots_preview redemandé")
	_check(f.wanted_bots_preview().is_empty(), "même course : pas de nouvelle demande")
	f.menu.focus_item("start")
	act = f.handle("A_LONG")
	_check(act == {"action": "start", "args": {"mode": "race"}}, "start avec mode « race », sans bots (%s)" % str(act))

	f.menu.set_world("boucle", "Boucle")
	f.handle("MINUS_SHORT")
	_check("set:race.laps" in _ids(f), "boucle : réglage des tours")
	_check(_item(f, "start")["detail"] == "3 tours, 9,0 km", "boucle : tours et longueur (%s)" % _item(f, "start")["detail"])
	_check(not MenuFlow.race_launch(3, {"length_m": 800.0, "route_type": "point_to_point"})["enabled"],
		"parcours de moins de 1 km : Lancer grisé")
	_check(MenuFlow.race_keys({}) == ["race.opponents", "race.laps"], "parcours inconnu : tours")
	f.menu.reset()
	_check(f.menu.mode == "free", "retour à l'accueil : le mode ne reste pas collé")

	# HUD : classement complet sans case d'objet ; bots loin (sans gap_s) rangés par leur position
	var hud = GpHudModel.new()
	var bots := []
	for i in range(11):
		var b := {"id": "bot%d" % (i + 1), "kind": "constant", "s": 1000.0 + 400.0 - i * 80.0, "name": "Bot %d" % (i + 1)}
		if i >= 4 and i <= 7:
			b["gap_s"] = (1000.0 - b["s"]) / -10.0
		bots.append(b)
	var gp := {"mode": "race", "place": 6, "of": 12, "gap_s": 4.2, "held": null, "n": 0, "roll_s": 0.0, "lane": 1,
		"auto": true, "fx": [], "warn": null, "obj": [], "boxes": [], "pick": false, "lap": [2, 3]}
	var v: Dictionary = hud.view({"gp": gp, "bots": bots, "s": 1000.0, "v": 10.0}, 1.0)
	_check(v["visible"] and v.get("race", false), "Course : HUD visible, marqué course")
	_check(v["item"].is_empty() and v["lanes"].is_empty() and v["warn"].is_empty() and v["fx"].is_empty(),
		"Course : ni case d'objet, ni voies, ni menace")
	_check(v["strip"].size() == 12, "classement complet : 12 coureurs, bots loin compris (%d)" % v["strip"].size())
	_check(v["strip"][0]["name"] == "Bot 1" and v["strip"][5]["me"] and v["strip"][11]["name"] == "Bot 11",
		"ordre de la course, toi à ta place")
	_check(str(v["strip"][11]["gap"]).begins_with("+"), "écart estimé pour un bot loin derrière (%s)" % v["strip"][11]["gap"])
	_check(v["place"]["place"] == "6e" and v["place"]["lap"] == "tour 2 / 3", "place et tours")
	gp.erase("mode")
	_check(not hud.view({"gp": gp, "bots": bots, "s": 1000.0, "v": 10.0}, 1.0).get("race", false), "Grand Prix : HUD habituel")

	var lines: Array = GpHudModel.summary_lines({"mode": "race", "place": 2, "of": 8, "launched": {}, "received": {},
		"dodged": 0, "gained_s": {}, "lost_s": {}, "laps": 3})
	_check(lines.size() == 2 and lines[0]["label"] == "Course" and lines[0]["value"] == "2e sur 8" and lines[1]["value"] == "3 tours",
		"bilan : place et format, sans ligne d'objets (%s)" % str(lines))
	lines = GpHudModel.summary_lines({"mode": "race", "place": 1, "of": 4, "launched": {}, "received": {},
		"dodged": 0, "gained_s": {}, "lost_s": {}, "distance_km": 12.4})
	_check(lines[1]["value"] == "12,4 km", "bilan en ligne : distance")
	print("test_race_menu : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
