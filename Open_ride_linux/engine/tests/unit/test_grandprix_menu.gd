extends SceneTree

## Tests sans écran du menu du Grand Prix des objets (série GP, lot GP9) : entrée de l'accueil selon `modes`,
## écran Prêt du mode (réglages `grandprix.*` et niveau des bots modifiés en place, tours du circuit : le mode se
## court sur une boucle, lot GPL1, liste du mode sans la trace en ligne étiquetée), ligne « Objets » et écran des objets (list_mode_options,
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
	{"key": "bots.objective", "label": "Objectif des bots", "type": "choice", "value": "tempo", "choices": ["recovery", "endurance", "tempo", "threshold", "max"], "group": "ride", "applies": "next_session"},
	{"key": "grandprix.opponents", "label": "Grand Prix : adversaires", "type": "int", "value": 4, "min": 2, "max": 11, "step": 1, "unit": "", "group": "ride", "applies": "next_session"},
	{"key": "grandprix.laps", "label": "Grand Prix : tours du circuit", "type": "int", "value": 3, "min": 1, "max": 5, "step": 1, "unit": "", "group": "ride", "applies": "next_session"},
	{"key": "grandprix.chaos", "label": "Grand Prix : chaos", "type": "choice", "value": "normal", "choices": ["soft", "normal", "wild"], "group": "ride", "applies": "next_session"},
	{"key": "grandprix.box_every_m", "label": "Grand Prix : écart des boîtes", "type": "int", "value": 1500, "min": 500, "max": 3000, "step": 500, "unit": "m", "group": "ride", "applies": "next_session"}]}

## Lot GPL1 : « Longue », trace en ligne étiquetée « grandprix », reste un parcours libre (pas dans la liste du mode).
const ROUTES := [{"id": "long", "name": "Longue", "status": "ready", "length_m": 25000.0, "route_type": "point_to_point",
		"library": {"tags": ["grandprix"]}},
	{"id": "libre", "name": "Libre", "status": "ready", "length_m": 7000.0, "route_type": "loop"},
	{"id": "boucle", "name": "Boucle", "status": "ready", "length_m": 3000.0, "route_type": "loop", "library": {"tags": ["grandprix"]}},
	{"id": "grande", "name": "Grande boucle", "status": "ready", "length_m": 4000.0, "route_type": "loop",
		"library": {"tags": ["grandprix"]}}]


func _run() -> void:
	var old = MenuFlow.new()
	old.connect_done = true
	old.menu.set_modes(["ride", "erg", "survivor"])
	old.on_state({"session_state": "IDLE"})
	_check(not "grandprix" in _ids(old), "core sans « grandprix » dans modes : pas d'entrée")

	var f = MenuFlow.new()
	f.connect_done = true
	f.menu.set_modes(["ride", "erg", "survivor", "grandprix"])
	f.menu.set_mode_routes({"grandprix": "grandprix"})
	f.on_settings(SETTINGS.duplicate(true))
	f.set_routes(ROUTES.duplicate(true))
	f.on_state({"session_state": "IDLE"})
	_check("grandprix" in _ids(f), "modes avec « grandprix » : entrée Grand Prix des objets")
	_check(_item(f, "grandprix")["label"] == "Grand Prix des objets" and str(_item(f, "grandprix")["detail"]) != "",
		"libellé et explication")
	_check(_ids(f).find("grandprix") == _ids(f).find("survivor") + 1, "après le Dernier survivant")
	f.menu.focus_item("grandprix")
	var act: Dictionary = f.handle("A_LONG")
	_check(act == {"action": "sequence", "list": [{"action": "sequence", "list": [{"action": "select_workout", "workout_id": null},
		{"action": "list_mode_options", "mode": "grandprix"}]}, {"action": "select_route", "route_id": "boucle"}]},
		"entrée : SIM seulement, première boucle du mode, objets demandés au core (%s)" % str(act))
	_check(f.state()["screen"] == "ready", "écran Prêt sur la première boucle du mode")
	f.menu.focus_item("change_route")
	f.handle("A_LONG")
	_check(f.state()["screen"] == "routes" and "boucle" in _ids(f) and "grande" in _ids(f) and not "long" in _ids(f)
		and not "libre" in _ids(f), "liste du mode : les boucles étiquetées seulement (%s)" % str(_ids(f)))
	f.menu.focus_item("grande")
	act = f.handle("A_LONG")
	_check(act.get("action", "") == "select_route" and f.state()["screen"] == "ready", "parcours choisi : écran Prêt")
	_check(str(f.state()["title"]) == "Prêt : Grand Prix des objets — Grande boucle", "titre du mode (%s)" % f.state()["title"])
	_check(_ids(f) == ["start", "change_route", "set:grandprix.opponents", "set:grandprix.laps",
		"set:grandprix.chaos", "set:grandprix.box_every_m", "gp_items", "_gp_help"],
		"Lancer, parcours, réglages avec les tours (plus de distance en ligne), Objets, aide (%s)" % str(_ids(f)))
	_check(_item(f, "start")["label"] == "Lancer" and _item(f, "start")["detail"] == "3 tours, 12,0 km" and _item(f, "start")["enabled"],
		"Lancer : tours et longueur de la course (%s)" % _item(f, "start")["detail"])
	# Lot GP-niv : effort des bots en watts demandé au core, ligne « Bots » grisée en dernier (contrat 1.22)
	_check(f.wanted_bots_preview() == {"mode": "grandprix"}, "écran Prêt : bots_preview demandé (%s)" % str(f.wanted_bots_preview()))
	_check(f.wanted_bots_preview().is_empty(), "même course : pas de nouvelle demande")
	f.on_bots_preview({"type": "bots_preview", "v": 1, "request_cmd_id": 9, "mode": "grandprix", "objective": "tempo",
		"ftp_pct": 92.4, "power_w": 231, "duration_s": 540, "elo": {"rating": 1540, "races": 3}})
	_check(_ids(f)[1] == "intensity" and _item(f, "intensity")["enabled"]
		and _item(f, "intensity")["label"] == "Intensité : moyen"
		and _item(f, "intensity")["detail"] == "bots ≈ 231 W",
		"lot R1 : « Intensité du jour » sous Lancer, mot, watts, durée et cote (%s)" % str(_item(f, "intensity")))
	_check(MenuFlow.bots_info_row({"power_w": null}).is_empty(), "sans watts (parcours pas chargé) : pas de watts")
	_check(MenuFlow.duration_text(3900.0) == "1 h 05", "durée de plus d'une heure : 1 h 05")
	_check(MenuFlow.bots_info_row({"power_w": 180, "duration_s": 600, "objective": "endurance", "elo": null})
		== {"watts": "≈ 180 W", "cote": "", "duration": "≈ 10 min", "hold": "", "mine": ""}, "cote coupée : pas de cote")
	# Lot PP6b (contrat 1.37) : durée tenable et temps estimé pour toi, en mots
	var pp6b := {"power_w": 260, "duration_s": 1500, "hold_s": 720, "my_time_s": 1380, "elo": null}
	_check(MenuFlow.bots_info_row(pp6b)["hold"] == "environ 12 min" and MenuFlow.bots_info_row(pp6b)["mine"] == "environ 23 min",
		"PP6b : tu tiens environ 12 min, temps estimé environ 23 min (%s)" % str(MenuFlow.bots_info_row(pp6b)))
	_check(MenuFlow.hold_text({"hold_s": 2000, "duration_s": 1500}) == "jusqu'au bout", "PP6b : au-delà de la course : jusqu'au bout")
	_check(MenuFlow.hold_text({"hold_s": 40, "duration_s": 1500}) == "environ 40 s", "PP6b : moins d'une minute en secondes")
	_check(MenuFlow.hold_text({"duration_s": 1500}) == "", "PP6b : core plus ancien, rien")
	# Lot R1 : A sur la ligne change la dose (moyen → dur → facile → moyen), gardée dans `bots.objective`
	f.menu.focus_item("intensity")
	_check(str(f.state()["status"]).begins_with("Intensité du jour : A pour facile, moyen ou dur.")
		and str(f.state()["status"]).ends_with("Course estimée à ≈ 9 min. Ta cote : 1540."),
		"focus sur la ligne : aide en mots, durée de la course et cote (%s)" % f.state()["status"])
	f.on_bots_preview({"type": "bots_preview", "v": 1, "request_cmd_id": 11, "mode": "grandprix", "objective": "tempo",
		"ftp_pct": 86.6, "power_w": 217, "duration_s": 780, "elo": {"rating": 1500, "races": 0}, "hold_s": 7734, "my_time_s": 660})
	_check(str(f.state()["status"]).ends_with("Course ≈ 13 min : allure tenue jusqu'au bout, toi à fond ≈ 11 min. Cote : 1500."),
		"PP6b : ligne d'état courte avec durée tenable, temps à fond et cote (%s)" % f.state()["status"])
	act = f.handle("A_LONG")
	_check(act == {"action": "set_setting", "key": "bots.objective", "value": "max"}, "moyen → dur (%s)" % str(act))
	_check(_item(f, "intensity")["detail"] == "" and _item(f, "intensity")["label"] == "Intensité : dur", "dur : anciens watts effacés jusqu'à la réponse")
	_check(f.wanted_bots_preview() == {"mode": "grandprix"}, "dose changée : nouvelle demande bots_preview")
	f.on_bots_preview({"type": "bots_preview", "v": 1, "request_cmd_id": 10, "mode": "grandprix", "objective": "max",
		"ftp_pct": 115.5, "power_w": 289, "duration_s": 480, "elo": {"rating": 1540, "races": 3}})
	_check(_item(f, "intensity")["detail"] == "bots ≈ 289 W", "dur : nouveaux watts")
	_check(f.handle("A_LONG").get("value", "") == "endurance" and _item(f, "intensity")["label"].begins_with("Intensité : facile"),
		"dur → facile")
	_check(f.handle("A_LONG").get("value", "") == "tempo", "facile → moyen")
	_check(MenuFlow.next_intensity("recovery") == "endurance" and MenuFlow.next_intensity("threshold") == "max",
		"récupération → facile, seuil → dur")
	_check(_item(f, "set:grandprix.opponents")["label"] == "Adversaires" and _item(f, "set:grandprix.opponents")["detail"] == "4",
		"réglage : libellé court et valeur")
	_check(_item(f, "set:grandprix.chaos")["detail"] == "normal", "chaos en français")
	_check(str(_item(f, "set:grandprix.box_every_m")["detail"]).contains("1500") or str(_item(f, "set:grandprix.box_every_m")["detail"]).contains("1 500"),
		"écart des boîtes en mètres (%s)" % _item(f, "set:grandprix.box_every_m")["detail"])
	_check(_item(f, "gp_items")["label"] == "Objets : tous", "Objets : tous activés par défaut")

	# Réglage modifié en place puis enregistré (set_setting), repris dans la ligne Lancer
	f.menu.focus_item("set:grandprix.laps")
	act = f.handle("A_LONG")
	_check(act.is_empty() and bool(_item(f, "set:grandprix.laps").get("editing", false)), "A long : modification en place")
	f.handle("PLUS_SHORT")
	act = f.handle("A_LONG")
	_check(act == {"action": "set_setting", "key": "grandprix.laps", "value": 4}, "A long : set_setting envoyé (%s)" % str(act))
	_check(_item(f, "start")["detail"] == "4 tours, 16,0 km", "tours relus : 4 tours (%s)" % _item(f, "start")["detail"])
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

	# Aide du mode (lot GPH1) : résumé dans la carte de l'écran Prêt, écran « Aide Grand Prix » un sujet par ligne
	f.menu.focus_item("start")
	_check(str(f.card(f.state()).get("title", "")) != "Aide Grand Prix", "focus sur Lancer : fiche du parcours, pas l'aide")
	f.menu.focus_item("_gp_help")
	var card: Dictionary = f.card(f.state())
	_check(_item(f, "_gp_help")["label"] == "Comment ça marche ?" and card.get("title", "") == "Aide Grand Prix"
		and card.get("name", "") == "Le Grand Prix en bref", "« Comment ça marche ? » : résumé du mode dans la carte (%s)" % str(card))
	_check(" ".join(card.get("lines", [])).contains("A ou ← →") and " ".join(card.get("lines", [])).contains("Z"),
		"résumé : boîtes, Z, changement de voie")
	act = f.handle("A_LONG")
	_check(act.is_empty() and f.state()["screen"] == "gp_help", "A long : écran « Aide Grand Prix »")
	_check(_ids(f) == ["help:summary", "help:boxes", "help:lanes", "help:buttons", "help:hits"], "sujets de l'aide (%s)" % str(_ids(f)))
	f.menu.focus_item("help:lanes")
	card = f.card(f.state())
	_check(card.get("name", "") == "À quoi servent les voies" and " ".join(card.get("lines", [])).contains("abri"),
		"sujet des voies : son explication, abri compris")
	_check(f.handle("A_LONG").is_empty() and f.state()["screen"] == "gp_help", "un sujet ne fait rien")
	f.handle("Y_SHORT")
	_check(f.state()["screen"] == "ready", "Y : retour à l'écran Prêt")

	f.menu.focus_item("start")
	act = f.handle("A_LONG")
	_check(act == {"action": "start", "args": {"mode": "grandprix"}}, "start avec mode « grandprix », sans bots")
	f.on_error("bad_args", "Grand Prix : parcours trop court")
	_check(str(f.state()["status"]) == "× REFUSÉ · Départ impossible : le parcours est trop court pour cette course\nÀ faire : choisis un parcours plus long, ou baisse les adversaires ou l'écart"
		and f.state()["status_error"], "refus du core expliqué : pourquoi et quoi faire (lot RT4, %s)" % str(f.state()["status"]))

	# Parcours en ligne imposé à l'écran Prêt (le core n'en accepte pas) : Lancer grisé et conseil (lot GPL1)
	f.menu.set_world("long", "Longue")
	f.handle("MINUS_SHORT")
	_check(not _item(f, "start")["enabled"] and str(_item(f, "start")["detail"]) == "parcours en ligne",
		"parcours en ligne : Lancer grisé (%s)" % _item(f, "start")["detail"])
	_check(str(f.state().get("status", "")).contains("se court sur une boucle"), "conseil sur la ligne d'état (%s)" % f.state().get("status", ""))
	f.menu.set_world("boucle", "Boucle")
	f.handle("MINUS_SHORT")
	_check(_item(f, "start")["enabled"] and _item(f, "start")["detail"] == "4 tours, 12,0 km", "circuit : tours et longueur (%s)" % _item(f, "start")["detail"])

	f.menu.reset()
	_check(f.menu.mode == "free", "retour à l'accueil : le mode ne reste pas collé")

	_check(MenuFlow.grandprix_launch(3, {}) == {"enabled": true, "detail": "", "advice": ""}, "parcours inconnu : Lancer actif")
	_check(not "grandprix.distance_km" in MenuFlow.GRANDPRIX_KEYS, "plus de distance en ligne (lot GPL1)")
	_check(MenuFlow.grandprix_launch(1, {"length_m": 4000.0, "route_type": "loop"})["detail"] == "1 tour, 4,0 km", "un tour au singulier")
	_check(not MenuFlow.grandprix_launch(3, {"length_m": 25000.0, "route_type": "point_to_point"})["enabled"],
		"parcours en ligne : Lancer désactivé")
	_check(MenuFlow.mode_label("Grand Prix : écart des boîtes", MenuFlow.GP_PREFIX) == "Écart des boîtes", "libellé court")
	print("test_grandprix_menu : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
