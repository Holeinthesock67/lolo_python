extends SceneTree

## Tests sans écran des parcours propres à un mode (lot GP13, demande du propriétaire du 15 novembre) : table du core
## (`hello_ack.config.mode_routes`), parcours d'un mode absents de la liste générale, liste du mode ouverte depuis son
## écran Prêt, Grand Prix et Vélodrome entrés par l'accueil sur leur dernier parcours (sinon le premier), retour au
## dernier parcours libre pour une séance hors de ces modes, `select_route` envoyé au core par menu_flow.gd.
## Lancement : godot --headless --path engine --script res://tests/unit/test_mode_routes.gd

const MenuFlow := preload("res://scripts/menu_flow.gd")
const MenuModel := preload("res://scripts/menu_model.gd")
const CatalogModel := preload("res://scripts/catalog_model.gd")

const TABLE := {"track": "velodrome", "grandprix": "grandprix"}
const TRACK := {"events": {"free": {"opponents": [5, [0, 5]]}}}
const ROUTES := [
	{"id": "alpe", "name": "Alpe d'Huez", "status": "ready", "length_m": 14000.0, "route_type": "point_to_point"},
	{"id": "demo", "name": "Col du lacet", "status": "ready", "length_m": 5000.0, "route_type": "point_to_point"},
	{"id": "demo-circuit", "name": "Circuit des Prés", "status": "ready", "length_m": 3000.0, "route_type": "loop",
		"library": {"tags": ["grandprix"]}},
	{"id": "vignes", "name": "Route des Vignes", "status": "ready", "length_m": 5000.0, "route_type": "loop",
		"library": {"tags": ["grandprix"]}},
	# Lot GPL1 : trace en ligne étiquetée « grandprix » : un parcours de mode est une boucle, elle reste libre
	{"id": "ligne", "name": "Ligne étiquetée", "status": "ready", "length_m": 6000.0, "route_type": "point_to_point",
		"library": {"tags": ["grandprix"]}},
	{"id": "velodrome-250", "name": "Vélodrome 250 m", "status": "ready", "length_m": 250.0, "route_type": "loop",
		"library": {"tags": ["velodrome"]}}]

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


func _flow(last := {}):
	var f = MenuFlow.new()
	f.connect_done = true
	f.menu.set_modes(["ride", "erg", "survivor", "grandprix", "track"])
	f.menu.set_mode_routes(TABLE)
	f.menu.set_track_events(TRACK)
	f.menu.set_last_choices(last)
	f.set_routes(ROUTES.duplicate(true))
	f.on_state({"session_state": "IDLE"})
	return f


func _press(f, id: String) -> Dictionary:
	_check(f.menu.focus_item(id), "élément %s présent" % id)
	return f.handle("A_LONG")


## Action `select_route` d'une action simple ou d'une suite d'actions ("" sans elle).
func _route_of(act: Dictionary) -> String:
	if act.get("action", "") == "select_route":
		return str(act["route_id"])
	for a in act.get("list", []):
		if a.get("action", "") == "select_route":
			return str(a["route_id"])
	return ""


func _run() -> void:
	# Catalogue : parcours de chaque mode et parcours libres
	var by_mode: Dictionary = CatalogModel.mode_route_ids(ROUTES, TABLE)
	_check(by_mode == {"track": ["velodrome-250"], "grandprix": ["demo-circuit", "vignes"]}, "parcours des modes (%s)" % str(by_mode))
	_check(CatalogModel.routes_of_mode(ROUTES, by_mode, "").map(func(r): return r["id"]) == ["alpe", "demo", "ligne"],
		"parcours libres, dont la trace en ligne étiquetée (lot GPL1)")
	_check(CatalogModel.routes_of_mode(ROUTES, by_mode, "grandprix").map(func(r): return r["id"]) == ["demo-circuit", "vignes"],
		"parcours du Grand Prix")
	_check(CatalogModel.tag_label("grandprix") == "Grand Prix", "étiquette « Grand Prix »")
	var c: Dictionary = CatalogModel.route_sheet({"id": "gp", "name": "Course", "length_m": 5000.0,
		"library": {"region": null, "tags": ["grandprix"], "description": null}})
	_check(c["lines"].has("Grand Prix") and not str(c["lines"]).contains("<null>"),
		"fiche sans description : « Grand Prix », jamais « <null> » (%s)" % str(c["lines"]))

	# Liste générale : ni la piste ni les parcours du Grand Prix
	var f = _flow({"route_id": "alpe"})
	f.menu.set_world("alpe", "Alpe d'Huez")
	_check(f.state()["items"][0]["label"] == "Parcours : Alpe d'Huez", "accueil : dernier parcours libre")
	_check("track" in _ids(f) and "grandprix" in _ids(f), "Vélodrome et Grand Prix à l'accueil")
	_press(f, "world")
	var listed: Array = _ids(f)
	_check(listed.has("alpe") and listed.has("demo") and listed.has("ligne") and not listed.has("demo-circuit") and not listed.has("vignes")
		and not listed.has("velodrome-250"), "liste générale sans les parcours des modes (%s)" % str(listed))
	f.handle("B_SHORT")

	# Grand Prix : premier parcours du mode, sa liste seulement
	f.menu.open_screen(MenuModel.HOME)
	var act: Dictionary = _press(f, "grandprix")
	_check(_route_of(act) == "demo-circuit" and f.menu.world_id == "demo-circuit", "Grand Prix : premier parcours du mode (%s)" % str(act))
	_check(f.state()["screen"] == MenuModel.READY and str(f.state()["title"]).ends_with("Circuit des Prés"), "écran Prêt du Grand Prix")
	_press(f, "change_route")
	listed = _ids(f)
	_check(listed.has("demo-circuit") and listed.has("vignes") and not listed.has("alpe") and not listed.has("velodrome-250")
		and not listed.has("ligne"),
		"liste du Grand Prix seulement (%s)" % str(listed))
	act = _press(f, "vignes")
	_check(_route_of(act) == "vignes" and f.state()["screen"] == MenuModel.READY, "autre parcours du Grand Prix")
	_check(f.state()["items"].size() > 0 and f.menu.free_world_name == "Alpe d'Huez", "le parcours libre reste l'Alpe d'Huez")

	# Retour à la session libre : dernier parcours libre renvoyé au core
	f.menu.reset()
	_check(f.state()["items"][0]["label"] == "Parcours : Alpe d'Huez", "accueil après le Grand Prix : parcours libre")
	act = _press(f, "ride")
	_check(_route_of(act) == "alpe" and f.menu.world_id == "alpe" and f.state()["screen"] == MenuModel.READY,
		"session libre : retour à l'Alpe d'Huez (%s)" % str(act))
	f.menu.reset()
	_check(_ids(f).has("track"), "retour à l'accueil")

	# Vélodrome à l'accueil
	act = _press(f, "track")
	_check(_route_of(act) == "velodrome-250" and f.menu.is_track(), "Vélodrome : piste choisie, écran du vélodrome (%s)" % str(act))
	_press(f, "change_route")
	_check(_ids(f).has("velodrome-250") and not _ids(f).has("alpe") and not _ids(f).has("demo-circuit"), "liste des pistes seulement")
	f.handle("B_SHORT")

	# Dernier parcours de chaque mode (last_choices.mode_routes)
	var g = _flow({"route_id": "demo", "mode_routes": {"grandprix": "vignes"}})
	act = _press(g, "grandprix")
	_check(_route_of(act) == "vignes", "Grand Prix : dernier parcours du mode (%s)" % str(act))
	g.menu.reset()
	_check(g.state()["items"][0]["label"] == "Parcours : à choisir", "sans parcours libre connu : à choisir")
	_press(g, "ride")
	_check(g.state()["screen"] == MenuModel.ROUTES and not _ids(g).has("vignes"), "session libre sans parcours libre : liste générale")
	act = _press(g, "demo")
	_check(_route_of(act) == "demo" and g.state()["screen"] == MenuModel.READY, "parcours libre choisi")

	# Mode sans parcours installé
	var h = MenuFlow.new()
	h.connect_done = true
	h.menu.set_modes(["ride", "erg", "grandprix"])
	h.menu.set_mode_routes(TABLE)
	h.set_routes([ROUTES[0]])
	h.on_state({"session_state": "IDLE"})
	h.menu.set_world("alpe", "Alpe d'Huez")
	_press(h, "grandprix")
	_check(h.state()["screen"] == MenuModel.ROUTES and _ids(h)[0] == "empty" and h.state()["items"][0]["label"] == "Aucun parcours pour ce mode",
		"Grand Prix sans parcours : liste vide expliquée (%s)" % str(h.state()["items"]))

	# Core sans table (ancien core) : rien ne change
	var o = MenuFlow.new()
	o.connect_done = true
	o.menu.set_modes(["ride", "erg", "grandprix"])
	o.set_routes(ROUTES.duplicate(true))
	o.on_state({"session_state": "IDLE"})
	o.menu.set_world("alpe", "Alpe d'Huez")
	act = _press(o, "grandprix")
	_check(_route_of(act) == "" and o.menu.world_id == "alpe", "sans table : le Grand Prix garde le parcours en cours")

	print("test_mode_routes : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
