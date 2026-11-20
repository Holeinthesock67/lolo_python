extends SceneTree

## Tests sans écran du menu du Grand Prix des objets (série GP, lot GP9) : entrée de l'accueil selon `modes`,
## écran Prêt du mode (réglages `grandprix.*` et niveau des bots modifiés en place, tours sur un circuit ou
## distance en ligne au plus le parcours, lot GP14), ligne « Objets » et écran des objets (list_mode_options,
## set_mode_option, réponse `mode_options`), `start` avec `mode` « grandprix » sans `bots`, retour à l'accueil.
## Lancement : godot --headless --path engine --script res://tests/unit/test_grandprix_menu.gd

const MenuFlow := preload("res://scripts/menu_flow.gd")
const GpItemsMenuModel := preload("res://scripts/grandprix/gp_items_menu_model.gd")

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
	{"key": "bots.level_pct", "label": "Niveau des bots", "type": "int", "value": 100, "min": 50, "max": 150, "step": 5, "unit": "%", "group": "ride", "applies": "next_session"},
	{"key": "bots.objective", "label": "Objectif des bots", "type": "choice", "value": "tempo", "choices": ["recovery", "endurance", "tempo", "threshold", "max"], "group": "ride", "applies": "next_session"},
	{"key": "grandprix.opponents", "label": "Grand Prix : adversaires", "type": "int", "value": 4, "min": 2, "max": 11, "step": 1, "unit": "", "group": "ride", "applies": "next_session"},
	{"key": "grandprix.laps", "label": "Grand Prix : tours du circuit", "type": "int", "value": 3, "min": 1, "max": 5, "step": 1, "unit": "", "group": "ride", "applies": "next_session"},
	{"key": "grandprix.distance_km", "label": "Grand Prix : distance en ligne", "type": "int", "value": 10, "min": 5, "max": 30, "step": 1, "unit": "km", "group": "ride", "applies": "next_session"},
	{"key": "grandprix.chaos", "label": "Grand Prix : chaos", "type": "choice", "value": "normal", "choices": ["soft", "normal", "wild"], "group": "ride", "applies": "next_session"},
	{"key": "grandprix.box_every_m", "label": "Grand Prix : écart des boîtes", "type": "int", "value": 1500, "min": 500, "max": 3000, "step": 500, "unit": "m", "group": "ride", "applies": "next_session"}]}

const ROUTES := [{"id": "long", "name": "Longue", "status": "ready", "length_m": 25000.0, "route_type": "point_to_point"},
	{"id": "court", "name": "Courte", "status": "ready", "length_m": 7000.0, "route_type": "point_to_point"},
	{"id": "mini", "name": "Mini", "status": "ready", "length_m": 3000.0, "route_type": "point_to_point"},
	{"id": "boucle", "name": "Boucle", "status": "ready", "length_m": 3000.0, "route_type": "loop"}]


func _run() -> void:
	var old = MenuFlow.new()
	old.connect_done = true
	old.menu.set_modes(["ride", "erg", "survivor"])
	old.on_state({"session_state": "IDLE"})
	_check(not "grandprix" in _ids(old), "core sans « grandprix » dans modes : pas d'entrée")

	var f = MenuFlow.new()
	f.connect_done = true
	f.menu.set_modes(["ride", "erg", "survivor", "grandprix"])
	f.on_settings(SETTINGS.duplicate(true))
	f.set_routes(ROUTES.duplicate(true))
	f.on_state({"session_state": "IDLE"})
	_check("grandprix" in _ids(f), "modes avec « grandprix » : entrée Grand Prix des objets")
	_check(_item(f, "grandprix")["label"] == "Grand Prix des objets" and str(_item(f, "grandprix")["detail"]) != "",
		"libellé et explication")
	_check(_ids(f).find("grandprix") == _ids(f).find("survivor") + 1, "après le Dernier survivant")
	f.menu.focus_item("grandprix")
	var act: Dictionary = f.handle("A_LONG")
	_check(act == {"action": "sequence", "list": [{"action": "select_workout", "workout_id": null},
		{"action": "list_mode_options", "mode": "grandprix"}]}, "entrée : SIM seulement et objets demandés au core")
	_check(f.state()["screen"] == "routes", "sans parcours choisi : la liste des parcours d'abord")
	f.menu.focus_item("long")
	act = f.handle("A_LONG")
	_check(act.get("action", "") == "select_route" and f.state()["screen"] == "ready", "parcours choisi : écran Prêt")
	_check(str(f.state()["title"]) == "Prêt : Grand Prix des objets — Longue", "titre du mode (%s)" % f.state()["title"])
	_check(_ids(f) == ["start", "change_route", "set:grandprix.opponents", "set:grandprix.distance_km", "set:bots.level_pct",
		"set:bots.objective", "set:grandprix.chaos", "set:grandprix.box_every_m", "gp_items"],
		"parcours en ligne : Lancer, parcours, réglages avec la distance, Objets (%s)" % str(_ids(f)))
	_check(_item(f, "start")["label"] == "Lancer" and _item(f, "start")["detail"] == "course de 10 km" and _item(f, "start")["enabled"],
		"Lancer : distance de la course")
	# Lot GP-niv : effort des bots en watts demandé au core, ligne « Bots » grisée en dernier (contrat 1.22)
	_check(f.wanted_bots_preview() == {"mode": "grandprix"}, "écran Prêt : bots_preview demandé (%s)" % str(f.wanted_bots_preview()))
	_check(f.wanted_bots_preview().is_empty(), "même course : pas de nouvelle demande")
	f.on_bots_preview({"type": "bots_preview", "v": 1, "request_cmd_id": 9, "mode": "grandprix", "objective": "tempo",
		"ftp_pct": 92.4, "power_w": 231, "duration_s": 540, "elo": {"rating": 1540, "races": 3}})
	_check(_ids(f)[-1] == "bots_info" and not _item(f, "bots_info")["enabled"]
		and _item(f, "bots_info")["detail"] == "≈ 231 W pendant ≈ 9 min (Tempo) · ta cote 1540",
		"ligne « Bots » : watts, durée, objectif et cote (%s)" % str(_item(f, "bots_info")))
	_check(MenuFlow.bots_info_text({"power_w": null}) == "", "sans watts (parcours pas chargé) : pas de ligne")
	_check(MenuFlow.duration_text(3900.0) == "1 h 05", "durée de plus d'une heure : 1 h 05")
	_check(MenuFlow.bots_info_text({"power_w": 180, "duration_s": 600, "objective": "endurance", "elo": null})
		== "≈ 180 W pendant ≈ 10 min (Endurance)", "cote coupée : pas de cote")
	_check(_item(f, "set:grandprix.opponents")["label"] == "Adversaires" and _item(f, "set:grandprix.opponents")["detail"] == "4",
		"réglage : libellé court et valeur")
	_check(_item(f, "set:grandprix.chaos")["detail"] == "normal", "chaos en français")
	_check(str(_item(f, "set:grandprix.box_every_m")["detail"]).contains("1500") or str(_item(f, "set:grandprix.box_every_m")["detail"]).contains("1 500"),
		"écart des boîtes en mètres (%s)" % _item(f, "set:grandprix.box_every_m")["detail"])
	_check(_item(f, "gp_items")["label"] == "Objets : tous", "Objets : tous activés par défaut")

	# Réglage modifié en place puis enregistré (set_setting), repris dans la ligne Lancer
	f.menu.focus_item("set:grandprix.distance_km")
	act = f.handle("A_LONG")
	_check(act.is_empty() and bool(_item(f, "set:grandprix.distance_km").get("editing", false)), "A long : modification en place")
	f.handle("PLUS_SHORT")
	act = f.handle("A_LONG")
	_check(act == {"action": "set_setting", "key": "grandprix.distance_km", "value": 11}, "A long : set_setting envoyé (%s)" % str(act))
	_check(_item(f, "start")["detail"] == "course de 11 km", "distance relue : 11 km")
	_check(f.wanted_bots_preview() == {"mode": "grandprix"}, "réglage de la course changé : bots_preview redemandé")
	f.menu.focus_item("set:grandprix.chaos")
	f.handle("A_LONG")
	f.handle("PLUS_SHORT")
	_check(str(_item(f, "set:grandprix.chaos")["detail"]).contains("fou"), "+ : chaos fou")
	f.handle("Y_SHORT")
	_check(_item(f, "set:grandprix.chaos")["detail"] == "normal", "Y : modification annulée")

	# Écran des objets : liste du core, une case par objet, bascule et « Tout activer »
	f.menu.focus_item("gp_items")
	act = f.handle("A_LONG")
	_check(act == {"action": "list_mode_options", "mode": "grandprix"} and f.state()["screen"] == GpItemsMenuModel.SCREEN,
		"Objets : écran des objets, liste redemandée")
	_check(_ids(f).size() == 14 and _ids(f)[0] == "item:gel" and _ids(f)[-1] == "all_on", "13 objets puis « Tout activer »")
	_check(not _item(f, "all_on")["enabled"], "tout activé : « Tout activer » grisé")
	f.menu.focus_item("item:storm")
	act = f.handle("A_LONG")
	_check(act == {"action": "set_mode_options", "mode": "grandprix", "list": [{"id": "storm", "on": false}]},
		"bascule : set_mode_option envoyé (%s)" % str(act))
	_check(_item(f, "item:storm")["label"] == "Nuage d'orage : non" and _item(f, "item:storm")["detail"] == "contre la tête",
		"objet coupé tout de suite, famille en clair")
	_check(str(f.state()["title"]) == "Grand Prix : 12 objets sur 13", "titre : objets actifs")
	var opts: Array = []
	for id in GpItemsMenuModel.GpItems.IDS:
		opts.append({"id": id, "label": GpItemsMenuModel.GpItems.label(id), "family": GpItemsMenuModel.GpItems.family(id),
			"on": not id in ["storm", "headwind"]})
	f.on_mode_options({"type": "mode_options", "v": 1, "mode": "grandprix", "options": opts})
	_check(_item(f, "item:headwind")["label"] == "Vent contraire : non", "réponse du core : elle fait foi")
	f.on_mode_options({"type": "mode_options", "v": 1, "mode": "wtf", "options": [{"id": "gravity", "label": "Gravité", "family": "event", "on": false}]})
	_check(_ids(f).size() == 14, "options du mode WTF : ignorées par l'écran des objets")
	f.menu.focus_item("all_on")
	act = f.handle("A_LONG")
	_check(act == {"action": "set_mode_options", "mode": "grandprix", "list": [{"id": "storm", "on": true}, {"id": "headwind", "on": true}]},
		"Tout activer : une commande par objet coupé")
	f.on_mode_options({"type": "mode_options", "v": 1, "mode": "grandprix", "options": opts})
	f.handle("Y_SHORT")
	_check(f.state()["screen"] == "ready" and _item(f, "gp_items")["label"] == "Objets : 11 sur 13",
		"retour à l'écran Prêt : ligne Objets à jour (%s)" % str(_item(f, "gp_items")))

	f.menu.focus_item("start")
	act = f.handle("A_LONG")
	_check(act == {"action": "start", "args": {"mode": "grandprix"}}, "start avec mode « grandprix », sans bots")
	f.on_error("bad_args", "Grand Prix : parcours trop court")
	_check(str(f.state()["status"]).begins_with("Échec : Grand Prix"), "refus du core sur la ligne d'état")

	# Parcours en ligne plus court que la distance : la course suit le parcours (lot GP14) ; circuit : tours
	f.menu.set_world("court", "Courte")
	f.handle("MINUS_SHORT")
	_check(_item(f, "start")["enabled"] and str(_item(f, "start")["detail"]) == "course de 7,0 km (tout le parcours)",
		"parcours en ligne plus court : course sur tout le parcours (%s)" % _item(f, "start")["detail"])
	_check(not f.state().has("status_error") or not f.state()["status_error"], "pas d'erreur sur la ligne d'état")
	f.menu.set_world("boucle", "Boucle")
	f.handle("MINUS_SHORT")
	_check("set:grandprix.laps" in _ids(f) and not "set:grandprix.distance_km" in _ids(f), "circuit : tours, pas de distance")
	_check(_item(f, "start")["enabled"] and _item(f, "start")["detail"] == "3 tours, 9,0 km", "circuit : tours et longueur (%s)" % _item(f, "start")["detail"])

	f.menu.reset()
	_check(f.menu.mode == "free", "retour à l'accueil : le mode ne reste pas collé")

	_check(MenuFlow.grandprix_launch(3, 10, {}) == {"enabled": true, "detail": "", "advice": ""}, "parcours inconnu : Lancer actif")
	_check(MenuFlow.grandprix_keys({}) == ["grandprix.opponents", "grandprix.laps", "grandprix.distance_km", "bots.level_pct",
		"bots.objective", "grandprix.chaos", "grandprix.box_every_m"], "parcours inconnu : tours et distance")
	_check(MenuFlow.grandprix_launch(1, 10, {"length_m": 4000.0, "route_type": "loop"})["detail"] == "1 tour, 4,0 km", "un tour au singulier")
	_check(not MenuFlow.grandprix_launch(3, 10, {"length_m": 800.0, "route_type": "point_to_point"})["enabled"],
		"parcours de moins de 1 km : Lancer désactivé")
	_check(MenuFlow.mode_label("Grand Prix : écart des boîtes", MenuFlow.GP_PREFIX) == "Écart des boîtes", "libellé court")
	print("test_grandprix_menu : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
