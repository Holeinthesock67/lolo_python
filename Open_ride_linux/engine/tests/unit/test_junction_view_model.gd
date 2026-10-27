extends SceneTree

## Panneau du carrefour (lot W12) : modèle sans affichage, flèches du clavier, placement sans recouvrement
## en 1 920 × 1 080 et 1 280 × 720, affichage des branches.
## Lancement : godot --headless --path engine --script res://tests/unit/test_junction_view_model.gd

const Model := preload("res://scripts/junction_view_model.gd")
const JunctionView := preload("res://scripts/junction_view.gd")
const Banner := preload("res://scripts/banner.gd")
const ErgView := preload("res://scripts/erg_view.gd")

var _checked := 0
var _failures := 0


func _check(ok: bool, what: String) -> void:
	_checked += 1
	if not ok:
		_failures += 1
		printerr("[ÉCHEC] ", what)
	else:
		print("[OK] ", what)


## Trame `open_world.next` : trois branches, de gauche à droite dans le désordre [droite, gauche, tout droit].
func _next(d_m: float, chosen: int = 2, locked: bool = false, default: int = 2) -> Dictionary:
	return {"id": "j42", "d_m": d_m, "default": default, "chosen": chosen, "locked": locked,
		"b": [[88.0, "m", -3.4], [-92.0, "c", 6.6], [4.0, "t", 0.4]]}


func _init() -> void:
	var m = Model.new()
	_check(not m.view()["visible"], "rien avant la première trame")
	m.update(_next(301.0))
	_check(not m.view()["visible"], "invisible à 301 m")
	m.update(_next(300.0))
	_check(m.view()["visible"], "visible à 300 m")
	m.update(_next(0.0))
	_check(m.view()["visible"], "encore visible au carrefour (0 m)")
	m.update(_next(-5.0))
	_check(not m.view()["visible"], "disparaît après le carrefour")
	m.update(null)
	_check(not m.view()["visible"], "next absent : caché")

	m.update(_next(240.4))
	var v: Dictionary = m.view()
	_check(v["distance_m"] == 240 and v["title"] == "Carrefour dans 240 m", "distance arrondie au mètre : " + v["title"])
	var order := []
	for b in v["branches"]:
		order.append(b["index"])
	_check(order == [1, 2, 0], "branches de gauche à droite par angle : %s" % str(order))
	var left: Dictionary = v["branches"][0]
	var straight: Dictionary = v["branches"][1]
	var right: Dictionary = v["branches"][2]
	_check(left["label"] == "piste cyclable" and straight["label"] == "route" and right["label"] == "petite route",
		"libellés des classes c, t, m")
	_check(left["arrow_deg"] == -90 and straight["arrow_deg"] == 0 and right["arrow_deg"] == 90, "flèches arrondies à 15° (-92 → -90, 4 → 0, 88 → 90)")
	_check(Model.round_arrow(8.0) == 15 and Model.round_arrow(7.0) == 0 and Model.round_arrow(-22.0) == -15, "arrondi à 15° : 8 → 15, 7 → 0, -22 → -15")
	_check(left["grade_pct"] == 7 and straight["grade_pct"] == 0 and right["grade_pct"] == -3, "pentes arrondies à 1 %% : %d, %d, %d" % [left["grade_pct"], straight["grade_pct"], right["grade_pct"]])
	_check(left["grade_text"] == "+7 %" and right["grade_text"] == "-3 %", "texte de pente avec signe")
	_check(left["grade_class"] == "steep" and right["grade_class"] == "descent", "pente colorée comme le profil du HUD")
	_check(straight["is_default"] and straight["is_chosen"] and not left["is_chosen"], "défaut et choix sur la branche 2")
	_check(not straight["greyed"] and not left["greyed"], "rien de grisé avant le verrouillage")
	for code in ["p", "s", "t", "m", "c", "k"]:
		_check(Model.class_label(code) != "", "libellé de la classe " + code)
	_check(Model.class_label("p") == "grande route" and Model.class_label("k") == "chemin revêtu" and Model.class_label("?") == "route", "libellés « grande route », « chemin revêtu », inconnu = route")

	# Verrouillage : branches non choisies grisées, plus de choix.
	m.update(_next(20.0, 0, true, 2))
	v = m.view()
	_check(v["locked"] and v["title"] == "Choix verrouillé", "verrouillage reflété")
	var greyed := 0
	for b in v["branches"]:
		if b["greyed"]:
			greyed += 1
	_check(greyed == 2 and v["branches"][2]["is_chosen"] and not v["branches"][2]["greyed"], "deux branches grisées, la choisie (0) non")
	_check(m.press(-1).is_empty() and m.press(1).is_empty(), "verrouillé : aucune commande")

	# Clavier : ← puis → depuis la branche par défaut (2, au milieu).
	m = Model.new()
	m.update(_next(200.0))
	var first: Dictionary = m.press(-1)
	_check(first == {"junction_id": "j42", "branch": 1}, "← : branche 1 (à gauche) : %s" % str(first))
	var second: Dictionary = m.press(1)
	_check(second == {"junction_id": "j42", "branch": 2}, "→ : retour à la branche 2 : %s" % str(second))
	m.update(_next(190.0, 2))
	_check(m.press(1) == {"junction_id": "j42", "branch": 0}, "→ depuis le milieu : branche 0 (à droite)")
	_check(m.press(1).is_empty(), "→ sur la dernière branche : rien")
	m.update(_next(180.0, 0))
	_check(m.press(1).is_empty() and m.press(-1)["branch"] == 2, "choix confirmé par le core, ← : branche 2")
	_check(Model.new().press(1).is_empty(), "sans carrefour : rien")
	m.update(_next(400.0))
	_check(m.press(-1).is_empty(), "carrefour à plus de 300 m : rien")
	# Nouveau carrefour : la demande en attente est oubliée.
	m.update(_next(100.0, 2))
	var pending: Dictionary = m.press(-1)
	var other := _next(250.0, 2)
	other["id"] = "j43"
	m.update(other)
	_check(m.chosen_index() == 2 and pending["branch"] == 1, "autre carrefour : choix du core")

	# Placement : pas de recouvrement avec les panneaux de mesures, le bandeau d'alerte, le bandeau ERG et le profil.
	for size in [Vector2(1920, 1080), Vector2(1280, 720)]:
		var rect := Model.layout_for(size, 130.0)
		var left_panel := Rect2(20.0, 20.0, 300.0, 320.0)
		var right_panel := Rect2(size.x - 320.0, 20.0, 300.0, 320.0)
		var banner := Rect2(Banner.MARGIN, 130.0 + Banner.MARGIN / 2.0, size.x - 2.0 * Banner.MARGIN, 40.0)
		var erg := Rect2(ErgView.SIDE_MARGIN, size.y - ErgView.BOTTOM_OFFSET - ErgView.PANEL_HEIGHT,
			size.x - 2.0 * ErgView.SIDE_MARGIN, ErgView.PANEL_HEIGHT)
		var profile := Rect2(40.0, size.y - 120.0, size.x - 80.0, 105.0)
		var center := Rect2(340.0, 20.0, size.x - 680.0, 110.0)
		var tag := "%dx%d" % [size.x, size.y]
		_check(not rect.intersects(left_panel) and not rect.intersects(right_panel), tag + " : hors des colonnes de mesures")
		_check(not rect.intersects(banner) and not rect.intersects(center), tag + " : hors du bandeau d'alerte et du panneau central")
		_check(not rect.intersects(erg) and not rect.intersects(profile), tag + " : hors du bandeau ERG et du profil")
		_check(Rect2(Vector2.ZERO, size).encloses(rect), tag + " : dans la fenêtre")

	# Affichage : quatre branches, attribution.
	var view = JunctionView.new()
	root.add_child(view)
	view.update_display(null, Vector2(1280, 720), 130.0)
	_check(not view.panel.visible and not view.attribution_label.visible, "hors monde ouvert : ni panneau ni attribution")
	view.update_display({"rev": 1, "next": null, "data": "cached"}, Vector2(1280, 720), 130.0)
	_check(view.attribution_label.visible and not view.panel.visible, "monde ouvert sans carrefour : attribution seule")
	_check(view.attribution_label.text == "© OpenStreetMap, OpenMapTiles, Copernicus", "texte de l'attribution")
	var four := _next(150.0)
	four["b"].append([-40.0, "p", 2.0])
	view.update_display({"rev": 1, "next": four, "data": "cached"}, Vector2(1280, 720), 130.0)
	_check(view.panel.visible and view.cells_row.get_child_count() == 4, "quatre branches affichées")
	_check(view.panel.position.y >= 130.0 + 56.0 and view.title_label.text == "Carrefour dans 150 m", "panneau sous le bandeau, titre")
	view.update_display({"rev": 1, "next": null, "data": "cached"}, Vector2(1280, 720), 130.0)
	_check(not view.panel.visible, "carrefour dépassé : panneau caché")
	view.queue_free()

	print("test_junction_view_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
