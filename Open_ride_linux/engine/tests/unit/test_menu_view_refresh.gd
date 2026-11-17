extends SceneTree

## Tests sans écran : une mise à jour du menu sans changement ne repose rien (lag de la liste des parcours,
## essai du 15 novembre). Rangées et carte de détail inchangées gardent leurs libellés, un changement les refait.
## Lancement : godot --headless --path engine --script res://tests/unit/test_menu_view_refresh.gd

const MenuView := preload("res://scripts/menu_view.gd")
const CatalogModel := preload("res://scripts/catalog_model.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _route(i: int) -> Dictionary:
	return {"id": "col-%02d" % i, "name": "Col %d" % i, "status": "ready", "length_m": 15000.0,
		"stats": {"distance_m": 15000.0, "gain_m": 1200.0, "max_grade_pct": 11.2, "difficulty": 5, "duration_s": 5400.0},
		"library": {"description": "Un col.", "region": "Savoie", "tags": ["col"]}}


func _menu(focus: int, label0 := "Col 0") -> Dictionary:
	var items := []
	for i in range(30):
		items.append({"id": "col-%02d" % i, "label": label0 if i == 0 else "Col %d" % i, "detail": "15,0 km · ↑ 1 200 m"})
	return {"screen": "routes", "title": "Parcours", "focus": focus, "items": items,
		"card": CatalogModel.route_sheet(_route(focus))}


func _first_label(v) -> Label:
	return v._item_panels[0].get_child(0).get_child(1)


func _initialize() -> void:
	var v = MenuView.new()
	root.add_child(v)
	v.update_display(_menu(0), {}, {}, false)
	_check(_first_label(v).text == "Col 0", "première rangée affichée")
	_check(v.card.name_label.text == "Col 0", "fiche du parcours sous le focus")
	# Marques posées à la main : une mise à jour identique ne doit pas les effacer.
	_first_label(v).text = "marque"
	v.card.name_label.text = "marque"
	v.update_display(_menu(0), {}, {}, false)
	_check(_first_label(v).text == "marque", "rangée inchangée : rien n'est reposé")
	_check(v.card.name_label.text == "marque", "même fiche : carte non reposée")
	v.update_display(_menu(0, "Col zéro"), {}, {}, false)
	_check(_first_label(v).text == "Col zéro", "libellé changé : rangée refaite")
	v.update_display(_menu(1), {}, {}, false)
	_check(v.card.name_label.text == "Col 1", "focus déplacé : nouvelle fiche")
	var focused: PanelContainer = v._item_panels[1]
	_check(focused.get_meta("focused", false), "rangée du focus marquée")
	_check(not v._item_panels[0].get_meta("focused", true), "ancienne rangée du focus démarquée")
	v.update_display({"screen": "routes", "title": "Parcours", "focus": 0, "items": [], "card": {}}, {}, {}, false)
	_check(not v.card.visible, "fiche vide : carte cachée")
	print("test_menu_view_refresh : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
