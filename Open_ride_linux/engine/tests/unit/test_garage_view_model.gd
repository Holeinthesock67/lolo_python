extends SceneTree

## Tests sans écran du menu « Garage » (lot V8) : modèle (garage_view_model.gd), déroulé dans les menus
## (menu_flow.gd) et aperçu 3D (garage_preview.gd).
## Lancement : godot --headless --path engine --script res://tests/unit/test_garage_view_model.gd

const GarageViewModel := preload("res://scripts/garage_view_model.gd")
const MenuFlow := preload("res://scripts/menu_flow.gd")
const GaragePreview := preload("res://scripts/garage_preview.gd")

const PROGRESSION := {"level": 9, "xp": 1200, "xp_next_level": 1500, "coins": 190,
	"equipped": {"frame": "f_all", "wheels": "w_std", "helmet": "h_road", "kit": "k_plain", "socks": "s_white", "glasses": "g_clear"},
	"avatar": {"height": "M", "build": "medium", "skin": 3, "hair": 2, "hair_color": 1, "kit_primary": 4,
		"kit_secondary": 11, "number": 27, "standing_grade_pct": 8.0, "standing_power_pct": 150.0}}


func _it(id: String, slot: String, name: String, state: String, level: int, price: int, extra := {}) -> Dictionary:
	var d := {"id": id, "slot": slot, "name": name, "state": state, "level_required": level, "price": price,
		"challenge": null, "mass_delta_kg": 0.0, "cda_delta_pct": 0.0, "terrain": "all", "look": id}
	d.merge(extra, true)
	return d


func _garage() -> Array:
	return [
		_it("f_climb", "frame", "Grimpeur", "buyable", 5, 150, {"mass_delta_kg": -1.5, "terrain": "climb", "look": "frame_light"}),
		_it("f_all", "frame", "Polyvalent", "equipped", 1, 0),
		_it("f_aero", "frame", "Profilé", "locked", 12, 400, {"cda_delta_pct": -4.0, "terrain": "flat", "look": "frame_aero"}),
		_it("f_tour", "frame", "Randonneur", "locked", 20, 0, {"challenge": "Tour du lac"}),
		_it("w_std", "wheels", "Standard", "equipped", 1, 0, {"look": "wheels_spoked"}),
		_it("w_deep", "wheels", "Profilées", "owned", 4, 90, {"terrain": "flat", "look": "wheels_deep", "cda_delta_pct": -1.0}),
		_it("k_plain", "kit", "Unie", "equipped", 1, 0, {"look": "kit_plain"}),
		_it("k_polka", "kit", "À pois", "buyable", 6, 400, {"look": "kit_polka"}),
		_it("h_road", "helmet", "Route", "equipped", 1, 0, {"look": "helmet_road"}),
		_it("s_white", "socks", "Blanches", "equipped", 1, 0, {"look": "socks_white"}),
		_it("g_clear", "glasses", "Claires", "equipped", 1, 0, {"look": "glasses_clear"}),
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


func _vm():
	var vm = GarageViewModel.new()
	vm.on_hello(PROGRESSION)
	vm.on_garage(_garage())
	return vm


func _test_model() -> void:
	var off = GarageViewModel.new()
	off.on_hello(null)
	_check(not off.enabled and off.route_advice("climb") == "", "sans progression : pas de Garage, pas de conseil")
	var vm = _vm()
	_check(vm.enabled and vm.level == 9 and vm.coins == 190, "en-tête : niveau %d, %d pièces" % [vm.level, vm.coins])
	_check(vm.title(GarageViewModel.SCREEN) == "Garage : niveau 9, 190 pièces", "titre avec niveau et solde")
	var ids: Array = vm.screen_items(GarageViewModel.BIKE).map(func(it): return it["id"])
	_check(ids == ["item:f_all", "item:f_climb", "item:f_aero", "item:f_tour", "item:w_std", "item:w_deep"],
		"vélo : cadres puis roues, par niveau : %s" % str(ids))
	var details: Array = vm.screen_items(GarageViewModel.BIKE).map(func(it): return it["detail"])
	_check(details == ["choisie", "150 pièces", "niveau 12", "défi : Tour du lac", "choisie", "possédée"], "états : %s" % str(details))
	_check(vm.screen_items(GarageViewModel.OUTFIT).size() == 5, "tenue : tenues, casque, chaussettes, lunettes")
	var sheet: Dictionary = vm.sheet(GarageViewModel.BIKE, "item:f_climb")
	_check(sheet["name"] == "Grimpeur" and sheet["tiles"][0]["value"] == "−1,5" and sheet["tiles"][1]["value"] == "=",
		"fiche : −1,5 kg, CdA = : %s" % str(sheet["tiles"]))
	_check("Conseillé : col" in sheet["lines"], "fiche : terrain conseillé")
	_check(vm.sheet(GarageViewModel.OUTFIT, "item:k_polka")["lines"][0] == "Apparence seulement", "fiche d'une tenue : apparence seulement")
	var head: Dictionary = vm.sheet(GarageViewModel.SCREEN, "bike")
	_check(head["name"] == "Niveau 9" and "1200 / 1500" in head["lines"][0] and "■■■■■■■■□□" in head["lines"][0], "barre d'expérience vers le niveau suivant")
	# Achat avec confirmation
	var buy: Dictionary = vm.activate("item:f_climb")
	_check(buy["action"] == "confirm_buy" and buy["title"] == "Acheter Grimpeur pour 150 pièces ? Solde après : 40", "achat : « %s »" % buy.get("title", ""))
	var poor = _vm()
	poor.coins = 100
	poor.activate("item:f_climb")
	_check("Pas assez de pièces" in poor.message and "50 manquantes" in poor.message, "solde insuffisant : %s" % poor.message)
	vm.activate("item:f_aero")
	_check(vm.message == "Verrouillée : niveau 12", "pièce verrouillée : %s" % vm.message)
	vm.activate("item:f_tour")
	_check(vm.message == "Verrouillée : défi : Tour du lac", "pièce de défi : %s" % vm.message)
	vm.activate("item:f_all")
	_check("déjà choisie" in vm.message, "pièce déjà choisie : %s" % vm.message)
	var eq: Dictionary = vm.activate("item:w_deep")
	_check(eq == {"action": "equip", "slot": "wheels", "item_id": "w_deep"} and vm.message == "", "pièce possédée : equip")
	_check(vm.on_error("item_locked", "x") and "verrouillée" in vm.message and vm.on_error("not_enough_coins", "") and vm.message == "Pas assez de pièces", "refus du core lisibles")
	_check(not vm.on_error("autre_code", ""), "autre code d'erreur : ignoré")
	# Progression : solde et pièces choisies
	var p := PROGRESSION.duplicate(true)
	p["coins"] = 40
	p["equipped"]["wheels"] = "w_deep"
	vm.on_progression(p)
	_check(vm.coins == 40 and vm.equipped["wheels"] == "w_deep", "message progression : solde et choix à jour")


func _test_avatar() -> void:
	var vm = _vm()
	_check(not vm.is_dirty() and vm.save().is_empty(), "avatar propre : rien à enregistrer")
	var it: Dictionary = vm.edit_item("height")
	_check(it["type"] == "int" and it["max"] == 3 and it["value"] == 1 and it["key"] == "garage.height", "réglage de taille : indice dans la liste fermée")
	_check(GarageViewModel.format_edit("garage.height", 3) == "très grande", "texte d'une taille")
	vm.set_field("height", 3)
	vm.set_field("skin", 6)
	vm.set_field("number", 5000)
	_check(vm.draft_avatar["height"] == "XL" and vm.draft_avatar["skin"] == 6 and vm.draft_avatar["number"] == 999, "brouillon : valeurs bornées")
	_check(vm.is_dirty() and vm.screen_items(GarageViewModel.AVATAR).filter(func(i): return i["id"] == "save")[0]["enabled"], "Enregistrer actif après un changement")
	var act: Dictionary = vm.save()
	_check(act["action"] == "set_avatar" and act["avatar"]["height"] == "XL" and not act["avatar"].has("standing_grade_pct") and act["avatar"].size() == 8,
		"set_avatar : les 8 réglages du contrat, sans les seuils de danseuse")
	vm.cancel()
	_check(not vm.is_dirty() and vm.draft_avatar["height"] == "M" and vm.draft_avatar["number"] == 27, "Annuler rend les valeurs enregistrées")
	vm.set_field("skin", 0)
	var p := PROGRESSION.duplicate(true)
	p["coins"] = 1
	vm.on_progression(p)
	_check(vm.draft_avatar["skin"] == 0, "un message progression ne détruit pas un brouillon en cours")


func _test_preview_and_advice() -> void:
	var vm = _vm()
	var pv: Dictionary = vm.preview(GarageViewModel.BIKE, "item:f_climb")
	_check(pv["looks"]["frame"] == "frame_light" and pv["looks"]["wheels"] == "wheels_spoked", "aperçu : le cadre sous le focus remplace le cadre choisi")
	pv = vm.preview(GarageViewModel.AVATAR, "", {"key": "garage.skin", "value": 6})
	_check(pv["settings"]["skin"] == 6 and pv["settings"]["number"] == 27, "aperçu : la valeur en cours de modification")
	_check(vm.route_advice("rolling") == "", "terrain sans pièce dédiée : les pièces tout terrain choisies suffisent")
	_check(vm.route_advice("flat") == "Parcours plat : conseillé Polyvalent, Profilées", "plat : %s" % vm.route_advice("flat"))
	vm.equipped["wheels"] = "w_deep"
	vm.items = _garage().map(func(i): return i.duplicate())
	for i in vm.items:
		if i["id"] == "w_deep":
			i["state"] = "equipped"
		if i["id"] == "w_std":
			i["state"] = "owned"
	_check(vm.route_advice("flat") == "", "tout est déjà au conseil : pas de ligne")
	_check(vm.route_advice(null) == "" and vm.route_advice("inconnu") == "", "sans terrain connu : pas de conseil")


func _ids(f) -> Array:
	return f.state()["items"].map(func(it): return it["id"])


func _test_flow() -> void:
	var f = MenuFlow.new()
	f.connect_done = true
	f.on_state({"session_state": "IDLE"})
	_check(not ("garage" in _ids(f)), "accueil sans progression : pas de Garage")
	f.on_hello_progression(PROGRESSION)
	f.on_garage(_garage())
	var home := _ids(f)
	_check("garage" in home and home.find("garage") == home.find("settings") - 1, "accueil : « Garage » avant « Réglages » : %s" % str(home))
	_check(f.menu.focus_item("garage"), "focus sur Garage")
	var act: Dictionary = f.handle("A_LONG")
	_check(act == {"action": "list_garage"} and f.state()["screen"] == "garage", "Garage ouvert, catalogue demandé")
	_check(f.state()["card"]["name"] == "Niveau 9" and f.state()["preview"]["looks"]["frame"] == "frame_round", "carte d'en-tête et aperçu de l'équipement choisi")
	_check(_ids(f) == ["bike", "outfit", "avatar"], "écran Garage : vélo, tenue, avatar")
	f.handle("A_LONG")   # Vélo
	_check(f.state()["screen"] == "garage_bike" and f.state()["card"]["name"] == "Polyvalent", "vélo : fiche de la première pièce")
	_check(f.state()["preview"]["looks"]["frame"] == "frame_round", "aperçu sur la pièce choisie")
	f.handle("PLUS_SHORT")   # Grimpeur
	_check(f.state()["card"]["name"] == "Grimpeur" and f.state()["preview"]["looks"]["frame"] == "frame_light", "le focus change la fiche et l'aperçu")
	act = f.handle("A_LONG")   # achat : confirmation
	_check(f.state()["screen"] == "confirm" and "Solde après : 40" in f.state()["title"] and act.is_empty(), "achat : confirmation")
	f.handle("PLUS_SHORT")   # Oui
	act = f.handle("A_LONG")
	_check(act == {"action": "buy", "item_id": "f_climb"} and f.state()["screen"] == "garage_bike", "Oui : buy, retour à la liste")
	# réponse du core : pièce possédée puis choisie
	var items := _garage()
	items[0]["state"] = "owned"
	f.on_garage(items)
	_check(f.state()["items"][1]["detail"] == "possédée", "après l'achat : possédée")
	act = f.handle("A_LONG")
	_check(act == {"action": "equip", "slot": "frame", "item_id": "f_climb"}, "pièce possédée : equip")
	f.handle("Y_SHORT")
	f.handle("PLUS_SHORT")
	f.handle("PLUS_SHORT")
	_check(_ids(f)[f.state()["focus"]] == "avatar", "focus sur Avatar")
	f.handle("A_LONG")
	_check(f.state()["screen"] == "garage_avatar" and f.state()["items"].size() == 10, "avatar : 8 réglages, enregistrer, annuler")
	f.handle("A_LONG")   # Taille : écran de modification commun
	_check(f.state()["screen"] == "setting_edit" and f.state()["items"][0]["label"] == "moyenne", "modification : valeur actuelle")
	_check(f.state()["card"]["title"] == "Avatar" and not f.state()["preview"].is_empty(), "modification : carte et aperçu")
	f.handle("PLUS_SHORT")
	_check(f.state()["items"][0]["label"] == "grande" and f.state()["preview"]["settings"]["height"] == "L", "+ : taille suivante, aperçu à jour")
	f.handle("A_LONG")   # valider
	_check(f.state()["screen"] == "garage_avatar" and f.state()["items"][0]["detail"] == "grande", "valeur validée dans le brouillon")
	_check(f.state()["items"][8]["enabled"], "Enregistrer actif")
	f.menu.focus_item("save")
	act = f.handle("A_LONG")
	_check(act["action"] == "set_avatar" and act["avatar"]["height"] == "L", "Enregistrer : set_avatar")
	var p := PROGRESSION.duplicate(true)
	p["avatar"]["height"] = "L"
	f.on_progression(p)
	_check(f.state()["status"] == "Enregistré" and not f.garage.is_dirty(), "progression reçue : enregistré")
	# refus du core affiché sur la ligne d'état
	f.on_error("busy", "séance en cours")
	_check("séance" in f.state()["status"], "refus busy : ligne d'état : %s" % f.state()["status"])
	# conseil du parcours sur l'écran Prêt
	f.set_routes([{"id": "plat", "name": "Plat", "length_m": 20000.0, "status": "ready", "terrain": "flat"}])
	f.menu.reset()
	f.menu.set_world("plat", "Plat")
	f.menu.open_screen("ready")
	_check("conseillé" in f.state()["status"], "écran Prêt : conseil du parcours : %s" % f.state()["status"])
	# pendant une séance, aucun menu
	f.on_state({"session_state": "RUNNING"})
	_check(not f.is_visible(), "séance en cours : Garage inaccessible")


func _test_preview() -> void:
	var prev = GaragePreview.new()
	root.add_child(prev)
	var vm = _vm()
	prev.show_preview(vm.preview(GarageViewModel.BIKE, "item:f_aero"))
	var info: Dictionary = prev.test_info()
	_check(info["looks"]["frame"] == "frame_aero" and info["triangles"] > 1000 and info["visible"], "aperçu 3D : cadre aéro, %d triangles" % info["triangles"])
	prev.visible = true
	prev._process(0.5)
	_check(prev.test_info()["angle"] > 0.3, "l'aperçu tourne")
	prev.show_preview({})
	_check(prev.test_info()["looks"]["frame"] == "frame_aero", "aperçu vide : rien ne change")
	prev.free()


func _init() -> void:
	_test_model()
	_test_avatar()
	_test_preview_and_advice()
	_test_flow()
	_test_preview()
	print("test_garage_view_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
