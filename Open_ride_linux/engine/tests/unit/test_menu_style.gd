extends SceneTree

## Tests sans écran du thème commun des menus (lot « présentation des menus », étape 1) : jetons et
## contrastes de `ui_theme.gd`, aide des boutons (`button_help.gd`) fidèle au plan des boutons §7.1,
## pictogrammes (`ui_icons.gd`), menu plein écran (`menu_view.gd`) avec l'accueil entier, la sélection,
## les éléments désactivés et la carte de détail, aucune couleur écrite en dur dans les vues des menus ;
## étape 2 : fiches de la carte (catalog_model.route_sheet, workout_sheet), carte selon l'écran
## (menu_flow.card), carte affichée (detail_card.gd : tuiles, graphique, lignes).
## Les hauteurs ne se vérifient pas ici (métriques de police fausses sans écran) : tests graphiques.
## Lancement : godot --headless --path engine --script res://tests/unit/test_menu_style.gd

const UiTheme := preload("res://scripts/ui_theme.gd")
const UiIcons := preload("res://scripts/ui_icons.gd")
const ButtonHelp := preload("res://scripts/button_help.gd")
const MenuView := preload("res://scripts/menu_view.gd")
const MenuModel := preload("res://scripts/menu_model.gd")
const MenuFlow := preload("res://scripts/menu_flow.gd")
const CatalogModel := preload("res://scripts/catalog_model.gd")
const DetailCard := preload("res://scripts/detail_card.gd")

const ROUTE := {"id": "col", "name": "Col", "length_m": 10000.0, "status": "ready", "stats": {"distance_m": 10000.0,
	"gain_m": 300.0, "max_grade_pct": 8.0, "duration_s": 1800.0, "difficulty": 2, "main_climb": {"length_m": 4000.0,
	"gain_m": 280.0, "avg_grade_pct": 7.0, "category": "3"}}, "library": {"description": "Court et raide.", "region": "Vosges", "tags": ["col"]}}
const SettingsViewModel := preload("res://scripts/settings_view_model.gd")
const BARE_ROUTE := {"id": "brut", "name": "Brut", "length_m": 5000.0, "status": "to_compile"}
const WORKOUT := {"id": "ss", "name": "Sweet spot", "duration_s": 3600, "block_count": 3, "selectable": true,
	"profile": [[600, 0.5, 0.75], [2400, 0.92, 0.92], [600, null, null]], "profile_truncated": false}

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
		UiTheme.CHIP_SIZE, UiTheme.SMALL_SIZE, UiTheme.VALUE_SIZE]
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
	var detail: Label = v._item_panels[1].get_child(0).get_child(3)
	_check(off.get_theme_color("font_color") == UiTheme.DISABLED and detail.visible and detail.text == "à compiler",
		"désactivé en couleur atténuée, détail à droite")
	_check(v.items_text() == "[Actif — 12,0 km] | Désactivé — à compiler", "texte des entrées : %s" % v.items_text())
	_check(not v.devices.visible and not v.card.visible, "liste des parcours : ni pastilles ni carte")
	v.update_display({"screen": "ready", "title": "Prêt", "focus": 0, "items": items, "card": CatalogModel.route_sheet(ROUTE)}, state, {}, false)
	_check(v.card.visible and v.card.text().begins_with("Parcours | Col | Distance 10,0 km") and not v.summary.visible,
		"écran Prêt : fiche du parcours dans la carte (%s)" % v.card.text())
	v.update_display({"screen": "summary", "title": "Fin de séance", "focus": 0, "items": items, "card": {"title": "Bilan de la séance"}},
		state, {"distance_m": 1000.0}, false)
	_check(v.card.visible and v.summary.visible and v.card.text() == "Bilan de la séance" and v.summary.get_parent() == v.card.body,
		"bilan dans la carte, sous son en-tête")
	v.free()
	# Pause : raison de la pause sous le titre (le HUD est caché pendant un menu).
	f.on_state({"session_state": "RUNNING"})
	f.on_state({"session_state": "PAUSED", "pause_reason": "trainer_lost"})
	_check(f.state()["screen"] == MenuModel.PAUSE and f.state()["status"] == MenuFlow.PAUSE_REASONS["trainer_lost"],
		"pause : raison affichée (%s)" % f.state()["status"])
	f.on_state({"session_state": "PAUSED", "pause_reason": "user"})
	_check(f.state()["status"] == "", "pause demandée : pas de ligne d'état")


## Étape 2 : chiffres clés et lignes des fiches, carte selon l'écran et le focus, graphique choisi.
func _test_cards() -> void:
	var tile_texts := func(sheet: Dictionary) -> Array:
		return sheet["tiles"].map(func(t): return ("%s %s %s" % [t["label"], t["value"], t["unit"]]).strip_edges())
	var r := CatalogModel.route_sheet(ROUTE)
	_check(tile_texts.call(r) == ["Distance 10,0 km", "Dénivelé ↑ 300 m", "Pente max 8,0 %"], "parcours : chiffres clés %s" % str(tile_texts.call(r)))
	_check(r["lines"] == ["Montée principale : 4,0 km à 7,0 %, ↑ 280 m (cat. 3)", "Difficulté 2 / 5 · durée ≈ 30 min",
		"Vosges, col — Court et raide."], "parcours : lignes %s" % str(r["lines"]))
	var bare := CatalogModel.route_sheet(BARE_ROUTE)
	_check(tile_texts.call(bare) == ["Distance 5,0 km"] and bare["lines"].is_empty() and bare["name"] == "Brut",
		"parcours sans fiche calculée : la longueur seule")
	var w := CatalogModel.workout_sheet(WORKOUT)
	_check(tile_texts.call(w) == ["Durée 1 h 00", "Blocs 3", "Intensité max 92 % FTP"] and w["blocks"].size() == 3,
		"entraînement : chiffres clés %s, blocs" % str(tile_texts.call(w)))
	var watts := CatalogModel.workout_sheet({"id": "e", "name": "Erg", "duration_s": 600, "block_count": 1, "unit": "watts",
		"profile": [[600, 0.8, 1.2]]}, 250.0)
	_check(tile_texts.call(watts)[2] == "Puissance max 300 W" and watts["lines"][0].begins_with("Fichier en watts fixes"),
		"entraînement en watts : puissance maximale en watts (%s)" % str(tile_texts.call(watts)))
	var bad := CatalogModel.workout_sheet({"id": "x", "name": "X", "error": "fichier illisible", "selectable": false, "profile": []})
	_check(bad["tiles"].is_empty() and bad["lines"] == ["fichier illisible"], "entraînement illisible : l'erreur seule")
	var f = MenuFlow.new()
	f.set_routes([ROUTE, BARE_ROUTE])
	f.set_workouts([WORKOUT])
	var on := func(screen: String, id: String) -> Dictionary:
		return f.card({"screen": screen, "focus": 0, "items": [{"id": id}]})
	_check(on.call(MenuModel.ROUTES, "brut").get("id") == "brut" and on.call(MenuModel.ROUTES, "col").get("id") == "col",
		"liste des parcours : fiche du parcours sous le focus")
	_check(on.call(MenuModel.ROUTES, MenuModel.SORT_ROUTES_ID).is_empty(), "liste des parcours : pas de carte sur « Trier par »")
	_check(on.call(MenuModel.WORKOUTS, "ss").get("blocks", []).size() == 3 and on.call(MenuModel.WORKOUTS, MenuModel.NO_WORKOUT_ID).is_empty(),
		"liste des entraînements : fiche avec blocs, rien sur « sans entraînement »")
	f.menu.set_world("col", "Col")
	_check(on.call(MenuModel.READY, "start").get("id") == "col", "écran Prêt : fiche du parcours choisi, pas du focus")
	_check(on.call(MenuFlow.SUMMARY, "new_session") == {"title": "Bilan de la séance"} and on.call(MenuModel.HOME, "ride").is_empty(),
		"bilan : en-tête seul ; accueil : pas de carte")
	f.builder.set_value("reps", 2)
	var create: Dictionary = on.call(MenuFlow.WORKOUT_CREATE, "save")
	_check(create["title"] == "Aperçu" and create["blocks"].size() == 6 and create["blocks"][1] == [240.0, 1.05, 1.05]
		and create["blocks"][5] == [600.0, 0.65, 0.45] and tile_texts.call(create) == ["Durée 34 min", "Blocs 6", "Intensité max 105 % FTP"],
		"création : aperçu des blocs du .zwo écrit par le core (%s)" % str(tile_texts.call(create)))
	var c = DetailCard.new()
	var profile := {"points": PackedVector2Array([Vector2(0, 100), Vector2(5000, 140), Vector2(10000, 120)]),
		"alt_min": 95.0, "alt_max": 145.0}
	c.update_display(r.merged({"profile": profile}))
	_check(c.chart_kind() == "profile" and c.tiles_box.visible and c.lines_label.visible, "carte : profil d'altitude du parcours chargé")
	c.update_display(r)
	_check(c.chart_kind() == "", "carte : pas de graphique sans parcours chargé")
	c.update_display(w)
	_check(c.chart_kind() == "blocks" and c.text() == "Entraînement | Sweet spot | Durée 1 h 00 | Blocs 3 | Intensité max 92 % FTP",
		"carte : blocs de l'entraînement (%s)" % c.text())
	c.update_display(bad)
	_check(c.chart_kind() == "" and not c.tiles_box.visible and c.text() == "Entraînement | X | fichier illisible",
		"carte : entraînement illisible, ni tuiles ni graphique")
	c.free()


## Étape 3 : rangées des réglages (valeur à droite, curseur, modification en place), carte, aide des boutons.
func _test_settings() -> void:
	var ftp := {"key": "rider.ftp_w", "label": "FTP", "group": "rider", "type": "int", "value": 250, "min": 50, "max": 600,
		"step": 5, "unit": "W", "applies": "next_session"}
	var vol := {"key": "sound.master_pct", "label": "Volume général", "group": "sound", "type": "int", "value": 80, "min": 0,
		"max": 100, "step": 10, "unit": "%", "applies": "now"}
	var quality := {"key": "render.quality", "label": "Qualité", "group": "display", "type": "choice", "value": "high",
		"choices": ["low", "medium", "high"], "applies": "now"}
	var s = SettingsViewModel.new()
	s.on_settings({"items": [ftp, vol, quality]})
	var rows: Array = s.menu_items("sound")
	_check(rows[0] == {"id": "set:sound.master_pct", "label": "Volume général", "detail": "80 %", "bar": 80},
		"réglage en % : libellé, valeur à droite, curseur (%s)" % str(rows[0]))
	_check(s.menu_items("rider")[0] == {"id": "set:rider.ftp_w", "label": "FTP", "detail": "250 W"} and not s.menu_items("rider")[0].has("bar"),
		"réglage en watts : pas de curseur")
	s.begin("sound.master_pct")
	s.step(1)
	rows = s.menu_items("sound")
	_check(rows[0]["detail"] == "◀ 90 % ▶" and rows[0]["bar"] == 90 and rows[0]["editing"], "rangée en cours de modification (%s)" % str(rows[0]))
	s.cancel()
	_check(s.menu_items("sound")[0]["detail"] == "80 %", "annulé : valeur d'avant")
	var sheet: Dictionary = s.sheet("sound.master_pct")
	_check(sheet["name"] == "Volume général" and sheet["tiles"].map(func(t): return t["label"]) == ["Valeur", "Plage", "Pas"]
		and sheet["lines"] == ["S'applique tout de suite"], "carte d'un réglage numérique (%s)" % str(sheet["lines"]))
	_check(s.sheet("render.quality")["lines"][0] == "Choix : low, medium, high" and s.sheet("absent").is_empty(), "carte d'un choix")
	_check(SettingsViewModel.crumb("sound") == "Réglages › Son", "fil d'Ariane du sous-écran")
	var edit := ButtonHelp.entries(ButtonHelp.EDIT)
	_check(edit[0]["hold"] and edit[0]["text"] == "Enregistrer" and edit.map(func(e): return e["keys"]).size() == 3
		and edit[-1]["keys"] == ["Y"] and edit[-1]["text"] == "Annuler", "aide en modification : enregistrer, régler, annuler")
	var v = MenuView.new()
	root.add_child(v)
	var items := SettingsViewModel.new()
	items.on_settings({"items": [vol]})
	v.update_display({"screen": "settings_group", "title": "Réglages › Son", "focus": 0, "items": items.menu_items("sound"),
		"card": items.sheet("sound.master_pct"), "editing": false}, {}, {}, false)
	var row: HBoxContainer = v._item_panels[0].get_child(0)
	_check(row.get_child(2).visible and row.get_child(3).text == "80 %" and v.button_bar.text().begins_with("A maintenir : Valider"),
		"vue : curseur et valeur à droite, aide de la liste")
	v.update_display({"screen": "settings_group", "title": "Réglages › Son", "focus": 0, "items": [{"id": "a", "label": "FTP",
		"detail": "◀ 250 W ▶", "editing": true}], "card": {}, "editing": true}, {}, {}, false)
	row = v._item_panels[0].get_child(0)
	_check(not row.get_child(2).visible and row.get_child(3).get_theme_color("font_color") == UiTheme.FOCUS
		and v.button_bar.text().begins_with("A maintenir : Enregistrer"), "vue : valeur en cours de réglage en couleur de sélection, aide mise à jour")
	v.free()


func _test_no_literal_colors() -> void:
	var re := RegEx.create_from_string("Color\\(\\s*[0-9.]")
	var found: Array = []
	for path in ["res://scripts/menu_view.gd", "res://scripts/devices_view.gd", "res://scripts/summary_view.gd",
			"res://scripts/button_bar.gd", "res://scripts/detail_card.gd"]:
		var src := FileAccess.get_file_as_string(path)
		if re.search(src) != null:
			found.append(path.get_file())
	_check(found.is_empty(), "vues des menus sans couleur écrite en dur (jetons de ui_theme.gd) %s" % str(found))


func _initialize() -> void:
	_test_theme()
	_test_button_help()
	_test_icons()
	_test_view()
	_test_cards()
	_test_settings()
	_test_no_literal_colors()
	print("test_menu_style : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
