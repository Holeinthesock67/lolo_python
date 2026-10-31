extends SceneTree

## Tests unitaires sans écran du modèle de catalogue (Lot N3).
## Lancement : godot --headless --path engine --script res://tests/unit/test_catalog_model.gd

const CatalogModel := preload("res://scripts/catalog_model.gd")
const MenuModel := preload("res://scripts/menu_model.gd")

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
	var nodes_before := Performance.get_monitor(Performance.OBJECT_NODE_COUNT)
	var cat = CatalogModel.new()

	# Lecture du fichier de test catalog_test.json
	var file := FileAccess.open("res://tests/data/catalog_test.json", FileAccess.READ)
	_check(file != null, "fichier catalog_test.json présent et lisible")
	var json_str := file.get_as_text()
	var test_data = JSON.parse_string(json_str)
	_check(test_data is Dictionary, "catalog_test.json est un dictionnaire JSON valide")

	var raw_routes: Array = test_data.get("routes", [])
	var raw_workouts: Array = test_data.get("workouts", [])

	# 1. Vérification de route_items : 4 éléments, 2 prêts en tête triés par nom, puis les autres
	var r_items: Array = cat.route_items(raw_routes)
	_check(r_items.size() == 4, "route_items renvoie exactement 4 éléments")
	_check(r_items[0]["id"] == "alpe_huez" and r_items[0]["enabled"] == true, "1er parcours : alpe_huez (prêt)")
	_check(r_items[1]["id"] == "galibier" and r_items[1]["enabled"] == true, "2e parcours : galibier (prêt)")
	_check(r_items[2]["id"] == "ventoux_gpx" and r_items[2]["enabled"] == false, "3e parcours : ventoux_gpx (désactivé)")
	_check(r_items[2]["detail"] == "à compiler", "3e parcours : detail 'à compiler'")
	_check(r_items[3]["id"] == "parcours_casse" and r_items[3]["enabled"] == false, "4e parcours : parcours_casse (désactivé)")
	_check(r_items[3]["detail"] == "manifest.json manquant", "4e parcours : detail 'manifest.json manquant'")

	# Vérification du format du label
	_check("13,8 km" in r_items[0]["label"], "alpe_huez : longueur formatée 13,8 km")
	_check("17,7 km" in r_items[1]["label"], "galibier : longueur formatée 17,7 km")

	# Test avec parcours en boucle
	var loop_routes = [{
		"id": "circuit",
		"name": "Circuit des Lacs",
		"status": "ready",
		"length_m": 8500.0,
		"route_type": "loop"
	}]
	var loop_items = cat.route_items(loop_routes)
	_check("boucle" in loop_items[0]["label"] and "8,5 km" in loop_items[0]["label"], "label avec longueur et mention 'boucle'")

	# 2. Branchement au MenuModel : focus jamais sur les deux derniers désactivés
	var menu = MenuModel.new()
	menu.set_items("routes", r_items)
	menu._open("routes")
	_check(menu.state()["focus"] == 0, "menu routes : focus initial sur index 0 (alpe_huez)")

	menu.handle("PLUS_SHORT")
	_check(menu.state()["focus"] == 1, "menu routes : avance sur index 1 (galibier)")

	menu.handle("PLUS_SHORT")
	_check(menu.state()["items"][menu.state()["focus"]]["id"] == "_add_route",
		"menu routes : saute les 2 désactivés jusqu'à « Ajouter un parcours » (lot O22)")
	menu.handle("PLUS_SHORT")
	menu.handle("PLUS_SHORT")
	_check(menu.state()["focus"] == 0, "menu routes : boucle sur index 0 après l'aide de fin de liste")

	menu.handle("MINUS_SHORT")
	menu.handle("MINUS_SHORT")
	menu.handle("MINUS_SHORT")
	_check(menu.state()["focus"] == 1, "menu routes : recule sur index 1 en sautant l'aide et les 2 désactivés")

	# 3. Vérification de workout_items : tri par durée croissante
	var w_items: Array = cat.workout_items(raw_workouts)
	_check(w_items.size() == 3, "workout_items renvoie 3 entraînements")
	_check(w_items[0]["id"] == "casse" and w_items[0]["enabled"] == false, "1er entraînement : cassé (0 min, désactivé)")
	_check(w_items[0]["detail"] == "balise <workout> absente", "1er entraînement : detail d'erreur présent")
	_check(w_items[1]["id"] == "recup" and "30 min" in w_items[1]["label"], "2e entraînement : recup (30 min)")
	_check(w_items[2]["id"] == "sweet_spot" and "60 min" in w_items[2]["label"], "3e entraînement : sweet_spot (60 min)")

	# 3b. Fiche de la pause (N20 §4.3) : chiffres de la séance en cours
	var ps: Dictionary = CatalogModel.pause_sheet(754.0, 5230.0, 187.4)
	var tv: Array = ps["tiles"].map(func(t): return "%s=%s%s" % [t["label"], t["value"], (" " + t["unit"]) if t["unit"] != "" else ""])
	_check(tv == ["Durée=12:34", "Distance=5,2 km", "Puissance moy.=187 W"], "fiche de la pause : %s" % str(tv))
	var ph: Dictionary = CatalogModel.pause_sheet(3725.0, 0.0, 0.0)
	_check(ph["tiles"][0]["value"] == "1:02:05" and ph["tiles"][2]["value"] == "0", "pause : heures affichées, 0 W gardé")
	var pn: Dictionary = CatalogModel.pause_sheet(NAN, NAN, -1.0)
	_check(pn["tiles"][0]["value"] == "—" and pn["tiles"][1]["unit"] == "" and pn["tiles"][2]["value"] == "—", "pause sans données : tuiles « — », sans unité seule")

	# 4. Performance : aucun nœud créé
	var nodes_after := Performance.get_monitor(Performance.OBJECT_NODE_COUNT)
	_check(nodes_after == nodes_before, "aucun nœud créé par catalog_model.gd (Performance.OBJECT_NODE_COUNT constant)")

	print("test_catalog_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
