extends SceneTree

## Tests sans écran du thème commun des menus (lot « présentation des menus », étape 1) : jetons et
## contrastes de `ui_theme.gd`, aide des boutons (`button_help.gd`) fidèle au plan des boutons §7.1,
## pictogrammes (`ui_icons.gd`), menu plein écran (`menu_view.gd`) avec l'accueil entier, la sélection,
## les éléments désactivés et la carte de détail, aucune couleur écrite en dur dans les vues des menus.
## Les hauteurs ne se vérifient pas ici (métriques de police fausses sans écran) : tests graphiques.
## Lancement : godot --headless --path engine --script res://tests/unit/test_menu_style.gd

const UiTheme := preload("res://scripts/ui_theme.gd")
const UiIcons := preload("res://scripts/ui_icons.gd")
const ButtonHelp := preload("res://scripts/button_help.gd")
const MenuView := preload("res://scripts/menu_view.gd")
const MenuModel := preload("res://scripts/menu_model.gd")
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


## Rapport de contraste WCAG de deux couleurs opaques.
static func _contrast(a: Color, b: Color) -> float:
	var lum := func(c: Color) -> float:
		var ch := func(v: float) -> float: return v / 12.92 if v <= 0.03928 else pow((v + 0.055) / 1.055, 2.4)
		return 0.2126 * ch.call(c.r) + 0.7152 * ch.call(c.g) + 0.0722 * ch.call(c.b)
	var la: float = lum.call(a)
	var lb: float = lum.call(b)
	return (maxf(la, lb) + 0.05) / (minf(la, lb) + 0.05)


func _test_theme() -> void:
	_check(_contrast(UiTheme.TEXT, UiTheme.VOID) >= 7.0, "texte sur fond : contraste %.1f ≥ 7" % _contrast(UiTheme.TEXT, UiTheme.VOID))
	for pair in [["secondaire", UiTheme.DIM], ["sélection", UiTheme.FOCUS], ["records", UiTheme.GOLD],
			["prêt", UiTheme.OK], ["recherche", UiTheme.WARN], ["erreur", UiTheme.DANGER]]:
		var c := _contrast(pair[1], UiTheme.SURFACE)
		_check(c >= 4.5, "%s sur carte : contraste %.1f ≥ 4,5" % [pair[0], c])
	_check(_contrast(UiTheme.DISABLED, UiTheme.VOID) >= 3.0, "désactivé encore lisible : contraste %.1f ≥ 3" % _contrast(UiTheme.DISABLED, UiTheme.VOID))
	var sizes := [UiTheme.TITLE_SIZE, UiTheme.ITEM_SIZE, UiTheme.DETAIL_SIZE, UiTheme.CARD_SIZE, UiTheme.HELP_SIZE,
		UiTheme.CHIP_SIZE, UiTheme.SMALL_SIZE]
	_check(sizes.all(func(s): return s >= 16), "aucune police sous 16 px : %s" % str(sizes))
	_check(UiTheme.TITLE_SIZE > UiTheme.ITEM_SIZE and UiTheme.ITEM_SIZE > UiTheme.DETAIL_SIZE, "hiérarchie titre > entrée > détail")
	var focus := UiTheme.row_style(true)
	_check(focus.border_color == UiTheme.FOCUS and focus.border_width_left >= 2 and focus.bg_color.a > 0.0,
		"sélection : bord et fond de la couleur de sélection")
	_check(UiTheme.row_style(false).bg_color.a == 0.0, "entrée non choisie : sans fond")


func _test_button_help() -> void:
	var main: Dictionary = ButtonHelp.entries("routes")[0]
	_check(main["keys"] == ["A"] and main["hold"] and main["main"] and main["text"] == "Valider",
		"valider en tête : A maintenu")
	var keys := {}
	for screen in ["home", "routes", "ready", "settings", "pause", "confirm", "summary"]:
		for e in ButtonHelp.entries(screen):
			for k in e["keys"]:
				keys[k] = true
	_check(keys.keys().all(func(k): return k in ["A", "+", "B", "Y"]),
		"seulement des boutons du boîtier droit, ni Z ni « − » seul (§7.1) : %s" % str(keys.keys()))
	var y := func(screen: String) -> String:
		for e in ButtonHelp.entries(screen):
			if e["keys"] == ["Y"]:
				return e["text"]
		return ""
	_check(y.call("home") == "" and y.call("pause") == "Reprendre" and y.call("confirm") == "Annuler"
		and y.call("routes") == "Retour", "Y selon l'écran : rien à l'accueil, reprendre en pause, annuler, retour")
	_check(ButtonHelp.text("routes") == "A maintenir : Valider · + A : Suivant · B : Précédent · Y : Retour · " + ButtonHelp.KEYBOARD,
		"aide en une ligne : %s" % ButtonHelp.text("routes"))


func _test_icons() -> void:
	_check(UiIcons.ITEM_ICONS.values().all(func(s): return s in UiIcons.SHAPES), "pictogrammes connus")
	var m = MenuModel.new()
	m.set_modes(["ride", "erg", "open_world"])
	var missing: Array = []
	for screen in [MenuModel.HOME, MenuModel.READY, MenuModel.PAUSE, MenuModel.CONFIRM]:
		for it in m._screens[screen]["items"]:
			if UiIcons.for_item(str(it["id"])) == "":
				missing.append(it["id"])
	_check(missing.is_empty(), "accueil, Prêt, pause, confirmation : un pictogramme par entrée %s" % str(missing))
	var canvas := Control.new()
	root.add_child(canvas)
	canvas.draw.connect(func() -> void:
		for i in range(UiIcons.SHAPES.size()):
			UiIcons.draw(canvas, UiIcons.SHAPES[i], Rect2(i * 32, 0, 28, 28), UiTheme.FOCUS))
	canvas.queue_redraw()
	canvas.free()


func _test_view() -> void:
	var f = MenuFlow.new()
	f.connect_done = true
	f.on_state({"session_state": "IDLE"})
	var v = MenuView.new()
	root.add_child(v)
	var state := {"session_state": "IDLE", "trainer_status": "MOCK", "input_status": "KEYBOARD"}
	v.update_display(f.state(), state, {}, false)
	var home: Array = f.state()["items"]
	_check(v.anchor_right == 1.0 and v.anchor_bottom == 1.0 and v.offset_left == 0.0 and v.offset_top == 0.0,
		"menu en plein écran")
	_check(v.items_text().split(" | ").size() == home.size() and v.more_label.text == "",
		"accueil entier avec les appareils : %d entrées sur %d" % [v.items_text().split(" | ").size(), home.size()])
	_check(v.devices.visible and v.button_bar.visible and not v.card.visible, "accueil : pastilles et bandeau, sans carte")
	var first: PanelContainer = v._item_panels[0]
	_check(first.get_meta("focused") and first.get_theme_stylebox("panel").border_color == UiTheme.FOCUS,
		"sélection encadrée en couleur de sélection")
	var items := [{"id": "a", "label": "Actif", "detail": "12,0 km"}, {"id": "b", "label": "Désactivé", "enabled": false, "detail": "à compiler"}]
	v.update_display({"screen": "routes", "title": "Parcours", "focus": 0, "items": items}, state, {}, false)
	var off: Label = v._item_panels[1].get_child(0).get_child(1)
	var detail: Label = v._item_panels[1].get_child(0).get_child(2)
	_check(off.get_theme_color("font_color") == UiTheme.DISABLED and detail.visible and detail.text == "à compiler",
		"désactivé en couleur atténuée, détail à droite")
	_check(v.items_text() == "[Actif — 12,0 km] | Désactivé — à compiler", "texte des entrées : %s" % v.items_text())
	_check(not v.devices.visible and not v.card.visible, "liste des parcours : ni pastilles ni carte")
	v.update_display({"screen": "ready", "title": "Prêt", "focus": 0, "items": items, "card": ["10,0 km · ↑ 120 m"]}, state, {}, false)
	_check(v.card.visible and v.card_label.text == "10,0 km · ↑ 120 m" and v.card_title.text == "Fiche du parcours",
		"écran Prêt : fiche du parcours dans la carte")
	v.free()
	# Pause : raison de la pause sous le titre (le HUD est caché pendant un menu).
	f.on_state({"session_state": "RUNNING"})
	f.on_state({"session_state": "PAUSED", "pause_reason": "trainer_lost"})
	_check(f.state()["screen"] == MenuModel.PAUSE and f.state()["status"] == MenuFlow.PAUSE_REASONS["trainer_lost"],
		"pause : raison affichée (%s)" % f.state()["status"])
	f.on_state({"session_state": "PAUSED", "pause_reason": "user"})
	_check(f.state()["status"] == "", "pause demandée : pas de ligne d'état")


func _test_no_literal_colors() -> void:
	var re := RegEx.create_from_string("Color\\(\\s*[0-9.]")
	var found: Array = []
	for path in ["res://scripts/menu_view.gd", "res://scripts/devices_view.gd", "res://scripts/summary_view.gd",
			"res://scripts/button_bar.gd"]:
		var src := FileAccess.get_file_as_string(path)
		if re.search(src) != null:
			found.append(path.get_file())
	_check(found.is_empty(), "vues des menus sans couleur écrite en dur (jetons de ui_theme.gd) %s" % str(found))


func _initialize() -> void:
	_test_theme()
	_test_button_help()
	_test_icons()
	_test_view()
	_test_no_literal_colors()
	print("test_menu_style : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
