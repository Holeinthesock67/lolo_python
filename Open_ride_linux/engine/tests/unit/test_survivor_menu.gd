extends SceneTree

## Tests sans écran du menu du mode « Dernier survivant » (série DS, lot DS7) : entrée de l'accueil selon `modes`,
## écran Prêt du mode (réglages `survivor.*` et niveau des bots modifiés en place, longueur de course, parcours
## trop court refusé), `start` avec `mode` « survivor » sans `bots`, refus du core affiché, retour à l'accueil.
## Lancement : godot --headless --path engine --script res://tests/unit/test_survivor_menu.gd

const MenuFlow := preload("res://scripts/menu_flow.gd")

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
	{"key": "survivor.opponents", "label": "Survivant : adversaires", "type": "int", "value": 4, "min": 2, "max": 4, "step": 1, "unit": "", "group": "ride", "applies": "next_session"},
	{"key": "survivor.spacing_km", "label": "Survivant : écart des arches", "type": "int", "value": 2, "min": 1, "max": 3, "step": 1, "unit": "km", "group": "ride", "applies": "next_session"},
	{"key": "bots.level_pct", "label": "Niveau des bots", "type": "int", "value": 100, "min": 50, "max": 150, "step": 5, "unit": "%", "group": "ride", "applies": "next_session"},
	{"key": "survivor.spread", "label": "Survivant : écart de niveau", "type": "choice", "value": "normal", "choices": ["tight", "normal", "wide"], "group": "ride", "applies": "next_session"},
	{"key": "survivor.after_out", "label": "Survivant : si éliminé", "type": "choice", "value": "ride", "choices": ["ride", "end"], "group": "ride", "applies": "next_session"}]}

const ROUTES := [{"id": "long", "name": "Longue", "status": "ready", "length_m": 25000.0, "route_type": "point_to_point"},
	{"id": "court", "name": "Courte", "status": "ready", "length_m": 5000.0, "route_type": "point_to_point"},
	{"id": "boucle", "name": "Boucle", "status": "ready", "length_m": 3000.0, "route_type": "loop"}]


func _run() -> void:
	var old = MenuFlow.new()
	old.connect_done = true
	old.menu.set_modes(["ride", "erg", "wtf"])
	old.on_state({"session_state": "IDLE"})
	_check(not "survivor" in _ids(old), "core sans « survivor » dans modes : pas d'entrée")

	var f = MenuFlow.new()
	f.connect_done = true
	f.menu.set_modes(["ride", "erg", "wtf", "survivor"])
	f.on_settings(SETTINGS.duplicate(true))   # const : lecture seule, le flux modifie les réglages en place
	f.set_routes(ROUTES.duplicate(true))
	f.on_state({"session_state": "IDLE"})
	_check("survivor" in _ids(f), "modes avec « survivor » : entrée Dernier survivant")
	_check(_item(f, "survivor")["label"] == "Dernier survivant" and str(_item(f, "survivor")["detail"]) != "", "libellé et explication")
	f.menu.focus_item("survivor")
	var act: Dictionary = f.handle("A_LONG")
	_check(act == {"action": "select_workout", "workout_id": null}, "entrée : séance sans entraînement ERG (SIM seulement)")
	_check(f.state()["screen"] == "routes", "sans parcours choisi : la liste des parcours d'abord")
	f.menu.focus_item("long")
	act = f.handle("A_LONG")
	_check(act.get("action", "") == "select_route" and f.state()["screen"] == "ready", "parcours choisi : écran Prêt")
	_check(str(f.state()["title"]).begins_with("Prêt : Dernier survivant"), "titre du mode")
	_check(_ids(f) == ["start", "change_route", "set:survivor.opponents", "set:survivor.spacing_km", "set:bots.level_pct",
		"set:survivor.spread", "set:survivor.after_out"], "Lancer, parcours, puis les cinq réglages (%s)" % str(_ids(f)))
	_check(_item(f, "start")["label"] == "Lancer" and _item(f, "start")["detail"] == "4 arches sur 8 km" and _item(f, "start")["enabled"],
		"Lancer : longueur de course")
	_check(_item(f, "set:survivor.opponents")["label"] == "Adversaires" and _item(f, "set:survivor.opponents")["detail"] == "4",
		"réglage : libellé court et valeur")
	_check(_item(f, "set:survivor.spread")["detail"] == "normal (± 8 %)", "écart de niveau en français")

	# Réglage modifié en place puis enregistré (set_setting), repris dans la longueur de course
	f.menu.focus_item("set:survivor.spacing_km")
	act = f.handle("A_LONG")
	_check(act.is_empty() and bool(_item(f, "set:survivor.spacing_km").get("editing", false)), "A long : modification en place")
	f.handle("PLUS_SHORT")
	_check(str(_item(f, "set:survivor.spacing_km")["detail"]).contains("3 km"), "+ : 3 km affiché")
	act = f.handle("A_LONG")
	_check(act == {"action": "set_setting", "key": "survivor.spacing_km", "value": 3}, "A long : set_setting envoyé")
	_check(_item(f, "start")["detail"] == "4 arches sur 12 km", "longueur de course relue : 12 km")
	f.menu.focus_item("set:survivor.after_out")
	f.handle("A_LONG")
	f.handle("PLUS_SHORT")
	f.handle("Y_SHORT")
	_check(_item(f, "set:survivor.after_out")["detail"] == "continuer à rouler", "Y : modification annulée")

	f.menu.focus_item("start")
	act = f.handle("A_LONG")
	_check(act == {"action": "start", "args": {"mode": "survivor"}}, "start avec mode « survivor », sans bots")
	f.on_error("bad_args", "Dernier survivant : parcours trop court")
	_check(str(f.state()["status"]).begins_with("Échec : Dernier survivant"), "refus du core sur la ligne d'état")

	# Parcours trop court : Lancer désactivé ; boucle : acceptée
	f.menu.set_world("court", "Courte")
	f.handle("MINUS_SHORT")
	_check(not _item(f, "start")["enabled"] and str(_item(f, "start")["detail"]).begins_with("parcours trop court : 5,0 km"),
		"parcours ouvert trop court : Lancer désactivé")
	_check(f.state()["status"].begins_with("Lancer grisé : 4 arches × 3 km = 12 km, parcours de 5,0 km.") and f.state()["status_error"],
		"ligne d'état : pourquoi Lancer est grisé et quoi changer (%s)" % f.state()["status"])
	f.menu.focus_item("set:survivor.opponents")
	_check(f.state()["status"].contains("A maintenu, puis − / +"), "focus sur un réglage : aide des touches avec l'explication")
	f.menu.set_world("boucle", "Boucle")
	f.handle("MINUS_SHORT")
	_check(_item(f, "start")["enabled"], "boucle : les arches continuent au tour suivant")

	f.menu.reset()
	_check(f.menu.mode == "free", "retour à l'accueil : le mode ne reste pas collé")

	_check(MenuFlow.survivor_launch(2, 1, {}) == {"enabled": true, "detail": "2 arches sur 2 km", "advice": ""}, "parcours inconnu : Lancer actif")
	var advice := MenuFlow.survivor_advice(4, 2, 5000.0)
	_check(advice == "Lancer grisé : 4 arches × 2 km = 8 km, parcours de 5,0 km. Baisse Adversaires ou Écart des arches (2 à 2 km, 4 à 1 km) ou change de parcours.",
		"explication du Lancer grisé : calcul et réglages qui tiennent (%s)" % advice)
	_check(MenuFlow.survivor_advice(2, 1, 1500.0).ends_with("Choisis un parcours plus long ou une boucle."), "parcours trop court pour tout réglage")
	_check(MenuFlow.survivor_label("Niveau des bots") == "Niveau des bots", "libellé sans préfixe gardé")
	print("test_survivor_menu : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
