extends Control

## Menus au-dessus de la vue 3D (Lot N6, réécrit par le lot « présentation des menus », étape 1) : plein
## écran sur un voile sombre (le HUD de séance est caché pendant un menu, main.gd), titre et ligne d'état,
## liste des éléments avec pictogramme, sélection encadrée et marquée d'un repère, détail aligné à droite,
## carte de détail à droite (detail_card.gd : fiche du parcours ou de l'entraînement, bilan), pastilles des
## appareils (devices_view.gd) et bandeau des boutons (button_bar.gd) en bas. Couleurs, tailles et
## espacements du thème commun (ui_theme.gd). Ne décide rien : affiche menu_flow.gd.
## Souris : clic gauche sur un élément = le valider (A long), clic droit = retour (Y), molette = choisir ;
## main.gd reçoit ces gestes par les signaux ci-dessous.
## Pas de class_name : charger par preload("res://scripts/menu_view.gd").

const DevicesView := preload("res://scripts/devices_view.gd")
const SummaryView := preload("res://scripts/summary_view.gd")
const ButtonBar := preload("res://scripts/button_bar.gd")
const UiTheme := preload("res://scripts/ui_theme.gd")
const UiIcons := preload("res://scripts/ui_icons.gd")
const DetailCard := preload("res://scripts/detail_card.gd")
const GaragePreview := preload("res://scripts/garage_preview.gd")
const ButtonHelp := preload("res://scripts/button_help.gd")

## Éléments affichés à la fois ; au-delà, la fenêtre suit le focus. Un de moins quand les pastilles des
## appareils sont affichées (accueil, Prêt, connexion) : l'accueil tient en entier.
const MAX_VISIBLE_ITEMS := 10
const MAX_VISIBLE_WITH_DEVICES := 9
const DEVICES_SCREENS := ["home", "ready", "connect"]

signal item_clicked(item_id: String)
## Événement du Click joué à la souris : Y_SHORT (clic droit), MINUS_SHORT / PLUS_SHORT (molette).
signal mouse_event(event_name: String)

var title_label: Label
var status_label: Label
## Carte de détail (detail_card.gd) : fiche de menu_flow.card() ; le bilan (lot N4) y est ajouté.
var card   # detail_card.gd
var items_box: VBoxContainer
var more_label: Label
var devices: HBoxContainer
var summary: VBoxContainer
## Aperçu 3D du Garage (lot V8), dans la carte de détail.
var preview   # garage_preview.gd
var button_bar: PanelContainer
var _header: VBoxContainer
## Confirmation : petite carte centrée sur le voile (question, puis « Non » et « Oui » ; items_box y est déplacée).
var confirm_card: PanelContainer
var _confirm_question: Label
var _confirm_rows: VBoxContainer
var _left: VBoxContainer
var _body: HBoxContainer
var _item_panels: Array[PanelContainer] = []
var _focus_style := UiTheme.row_style(true)
var _plain_style := UiTheme.row_style(false)


func _init() -> void:
	name = "MenuView"
	visible = false
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	gui_input.connect(_on_gui_input)
	var root := VBoxContainer.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.add_theme_constant_override("separation", 0)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	var margins := MarginContainer.new()
	margins.size_flags_vertical = Control.SIZE_EXPAND_FILL
	margins.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for side in ["left", "right"]:
		margins.add_theme_constant_override("margin_" + side, UiTheme.MARGIN)
	margins.add_theme_constant_override("margin_top", UiTheme.TOP)
	margins.add_theme_constant_override("margin_bottom", UiTheme.GAP)
	root.add_child(margins)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", UiTheme.GAP)
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	margins.add_child(box)
	# En-tête : titre, ligne d'état, filet.
	var header := VBoxContainer.new()
	_header = header
	header.add_theme_constant_override("separation", 6)
	box.add_child(header)
	title_label = UiTheme.label(UiTheme.TITLE_SIZE)
	title_label.clip_text = true
	title_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	header.add_child(title_label)
	status_label = UiTheme.label(UiTheme.DETAIL_SIZE, UiTheme.DIM)
	status_label.clip_text = true
	status_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	header.add_child(status_label)
	var rule := ColorRect.new()
	rule.color = UiTheme.LINE
	rule.custom_minimum_size.y = 1
	header.add_child(rule)
	# Corps : liste à gauche, carte de détail à droite.
	var body := HBoxContainer.new()
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.add_theme_constant_override("separation", UiTheme.GAP + 16)
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(body)
	_body = body
	var left := VBoxContainer.new()
	_left = left
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.add_theme_constant_override("separation", 6)
	left.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.add_child(left)
	items_box = VBoxContainer.new()
	items_box.add_theme_constant_override("separation", UiTheme.ROW_GAP)
	left.add_child(items_box)
	more_label = UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.DIM)
	more_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	left.add_child(more_label)
	card = DetailCard.new()
	body.add_child(card)
	summary = SummaryView.new()
	card.body.add_child(summary)
	preview = GaragePreview.new()
	card.body.add_child(preview)
	devices = DevicesView.new()
	box.add_child(devices)
	_build_confirm_card()
	# Bandeau des boutons sur toute la largeur, collé en bas.
	button_bar = ButtonBar.new()
	button_bar.mouse_filter = Control.MOUSE_FILTER_PASS
	root.add_child(button_bar)


## Carte de la confirmation (lot N20, étape 4d) : centrée, étroite, question en TEXT ; construite une fois,
## cachée hors de l'écran « confirm ».
func _build_confirm_card() -> void:
	confirm_card = PanelContainer.new()
	confirm_card.name = "ConfirmCard"
	confirm_card.visible = false
	confirm_card.mouse_filter = Control.MOUSE_FILTER_PASS
	confirm_card.add_theme_stylebox_override("panel", UiTheme.card_style())
	confirm_card.custom_minimum_size.x = UiTheme.CONFIRM_W
	confirm_card.set_anchors_and_offsets_preset(Control.PRESET_CENTER, Control.PRESET_MODE_MINSIZE)
	confirm_card.grow_horizontal = Control.GROW_DIRECTION_BOTH
	confirm_card.grow_vertical = Control.GROW_DIRECTION_BOTH
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", UiTheme.GAP)
	v.mouse_filter = Control.MOUSE_FILTER_IGNORE
	confirm_card.add_child(v)
	_confirm_question = UiTheme.label(UiTheme.ITEM_SIZE)
	_confirm_question.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	v.add_child(_confirm_question)
	_confirm_rows = VBoxContainer.new()
	_confirm_rows.mouse_filter = Control.MOUSE_FILTER_IGNORE
	v.add_child(_confirm_rows)
	add_child(confirm_card)


## Écran de confirmation : l'en-tête et la carte de détail s'effacent, la liste « Non / Oui » passe dans la carte.
func _show_confirm(on: bool, question := "") -> void:
	confirm_card.visible = on
	_header.visible = not on
	_body.visible = not on
	var target: Control = _confirm_rows if on else _left
	if items_box.get_parent() != target:
		items_box.reparent(target, false)
		if not on:
			_left.move_child(items_box, 0)
	_confirm_question.text = question


## Voile sur la scène 3D : dégradé horizontal, plus dense sous la liste.
func _draw() -> void:
	var w := size.x
	var h := size.y
	draw_polygon(PackedVector2Array([Vector2.ZERO, Vector2(w, 0), Vector2(w, h), Vector2(0, h)]),
		PackedColorArray([UiTheme.VEIL_LEFT, UiTheme.VEIL_RIGHT, UiTheme.VEIL_RIGHT, UiTheme.VEIL_LEFT]))


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED:
		queue_redraw()


## Textes des éléments affichés, séparés par « | », focus entre crochets (tests graphiques).
func items_text() -> String:
	var parts: Array[String] = []
	for p in _item_panels:
		if p.visible:
			var t := _row_text(p)
			parts.append(("[%s]" % t) if p.get_meta("focused", false) else t)
	return " | ".join(parts)


## Rangées affichées (tests, banc des menus) : identifiant, texte, focus et rectangle (repère du canevas).
func test_rows() -> Array:
	var out: Array = []
	for p in _item_panels:
		if p.visible:
			out.append({"id": str(p.get_meta("item_id", "")), "text": _row_text(p), "focused": bool(p.get_meta("focused", false)),
				"rect": p.get_global_rect()})
	return out


## Rectangle (repère du canevas) de la rangée affichée de l'élément `item_id` ; vide s'il n'est pas affiché.
func item_rect(item_id: String) -> Rect2:
	for p in _item_panels:
		if p.visible and str(p.get_meta("item_id", "")) == item_id:
			return p.get_global_rect()
	return Rect2()


## Aide des boutons affichée, en une ligne (tests).
func hint_text() -> String:
	return button_bar.text()


## menu : état de menu_model.gd ; state : dernière trame ; summary_data : bilan (écran « summary »).
func update_display(menu: Dictionary, state: Dictionary, summary_data: Dictionary, show_details: bool) -> void:
	title_label.text = str(menu.get("title", ""))
	status_label.text = str(menu.get("status", ""))
	status_label.visible = status_label.text != ""
	status_label.add_theme_color_override("font_color", UiTheme.DANGER if menu.get("status_error", false) else UiTheme.DIM)
	var screen := str(menu.get("screen", ""))
	var sheet: Dictionary = menu.get("card", {})
	card.visible = not sheet.is_empty()
	card.update_display(sheet)
	summary.visible = screen == "summary"
	card.custom_minimum_size.x = UiTheme.SUMMARY_CARD_W if summary.visible else UiTheme.CARD_W
	var garage_preview: Dictionary = menu.get("preview", {})
	preview.visible = not garage_preview.is_empty()
	if preview.visible:
		preview.show_preview(garage_preview)
	_show_confirm(screen == "confirm", title_label.text)
	var items: Array = menu.get("items", [])
	var focus := int(menu.get("focus", -1))
	var max_items := MAX_VISIBLE_WITH_DEVICES if screen in DEVICES_SCREENS else MAX_VISIBLE_ITEMS
	var first := 0
	if items.size() > max_items and focus >= 0:
		first = clampi(focus - max_items / 2, 0, items.size() - max_items)
	var shown := mini(items.size() - first, max_items)
	while _item_panels.size() < shown:
		var p := _new_row()
		items_box.add_child(p)
		_item_panels.append(p)
	for i in range(_item_panels.size()):
		var p := _item_panels[i]
		p.visible = i < shown
		if p.visible:
			_set_row(p, items[first + i], first + i == focus)
	more_label.text = "%d / %d" % [focus + 1, items.size()] if items.size() > max_items else ""
	more_label.visible = more_label.text != ""   # vide, il prendrait une ligne au-dessus du bandeau des boutons
	devices.visible = screen in DEVICES_SCREENS
	# Aide toujours visible (sans elle, rien ne dit qu'il faut un appui long pour valider).
	button_bar.update_display(ButtonHelp.EDIT if menu.get("editing", false) or screen == "setting_edit" else screen)
	if summary.visible:
		summary.update_display(summary_data, show_details, str(state.get("mode", "")))
		summary.update_progress(menu.get("progress", {}))
		_fit_summary()
	if devices.visible:
		devices.update_display(state)


## Bilan compacté pour que la carte tienne entre l'en-tête et le bandeau des boutons (taille de base de
## l'écran, 1280 de large et au moins 720 de haut avec l'étirement canvas_items).
func _fit_summary() -> void:
	var screen_h := size.y if size.y > 0.0 else 720.0   # plein écran : hauteur de base de l'écran
	var avail := screen_h - UiTheme.TOP - _header.get_combined_minimum_size().y - 2 * UiTheme.GAP \
		- button_bar.get_combined_minimum_size().y
	var pad: float = card.get_theme_stylebox("panel").get_minimum_size().x
	summary.fit(UiTheme.SUMMARY_CARD_W - pad, func() -> bool: return card.get_combined_minimum_size().y <= avail)


## Entrée de liste : pictogramme, libellé, détail aligné à droite ; repère dessiné à gauche de la sélection.
func _new_row() -> PanelContainer:
	var p := PanelContainer.new()
	p.custom_minimum_size.y = UiTheme.ROW_H
	p.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	p.mouse_filter = Control.MOUSE_FILTER_PASS   # clic droit et molette remontent au panneau
	p.gui_input.connect(_on_item_input.bind(p))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 16)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	p.add_child(row)
	var icon := Control.new()
	icon.custom_minimum_size = Vector2(UiTheme.ICON, UiTheme.ICON)
	icon.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	icon.draw.connect(func() -> void:
		UiIcons.draw(icon, str(icon.get_meta("shape", "")), Rect2(Vector2.ZERO, icon.size),
			icon.get_meta("color", UiTheme.DIM), UiTheme.LINE_W))
	row.add_child(icon)
	var l := UiTheme.label(UiTheme.ITEM_SIZE)
	l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	l.size_flags_stretch_ratio = 1.6
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.clip_text = true
	l.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(l)
	var bar := Control.new()   # curseur d'un réglage en % (0 à 100), dessiné par le code
	bar.custom_minimum_size = Vector2(UiTheme.BAR_W, UiTheme.BAR_H)
	bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	bar.draw.connect(func() -> void:
		var fill := float(bar.get_meta("pct", 0)) / 100.0
		bar.draw_rect(Rect2(Vector2.ZERO, bar.size), UiTheme.LINE)
		bar.draw_rect(Rect2(Vector2.ZERO, Vector2(bar.size.x * fill, bar.size.y)), UiTheme.FOCUS if bar.get_meta("focused", false) else UiTheme.DIM))
	row.add_child(bar)
	var d := UiTheme.label(UiTheme.DETAIL_SIZE, UiTheme.DIM)
	d.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	d.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	d.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	d.clip_text = true
	d.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	d.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(d)
	p.draw.connect(func() -> void:
		if p.get_meta("focused", false):
			var y := p.size.y / 2.0
			p.draw_colored_polygon(PackedVector2Array([Vector2(-16, y - 12), Vector2(-6, y), Vector2(-16, y + 12)]), UiTheme.FOCUS))
	return p


func _set_row(p: PanelContainer, it: Dictionary, focused: bool) -> void:
	var row: HBoxContainer = p.get_child(0)
	var icon: Control = row.get_child(0)
	var l: Label = row.get_child(1)
	var bar: Control = row.get_child(2)
	var d: Label = row.get_child(3)
	var enabled: bool = it.get("enabled", true)
	var id := str(it.get("id", ""))
	l.text = str(it.get("label", ""))
	d.text = str(it.get("detail", ""))
	d.visible = d.text != ""
	p.set_meta("item_id", id)
	p.set_meta("focused", focused)
	p.add_theme_stylebox_override("panel", _focus_style if focused else _plain_style)
	var color: Color = UiTheme.FOCUS if focused else (UiTheme.DIM if enabled else UiTheme.DISABLED)
	l.add_theme_color_override("font_color", UiTheme.DANGER if id == "yes" and confirm_card.visible else
		(UiTheme.TEXT if (focused or enabled) else UiTheme.DISABLED))   # l'action qui perd des données, en DANGER
	d.add_theme_color_override("font_color", UiTheme.FOCUS if it.get("editing", false) else
		(UiTheme.TEXT if focused else (UiTheme.DIM if enabled else UiTheme.DISABLED)))
	bar.visible = it.has("bar")
	bar.set_meta("pct", int(it.get("bar", 0)))
	bar.set_meta("focused", focused)
	bar.queue_redraw()
	icon.set_meta("shape", UiIcons.for_item(id))
	icon.set_meta("color", color)
	icon.queue_redraw()
	p.queue_redraw()


## Libellé et détail d'une entrée, comme avant le lot : « libellé — détail ».
func _row_text(p: PanelContainer) -> String:
	var row: HBoxContainer = p.get_child(0)
	var l: Label = row.get_child(1)
	var d: Label = row.get_child(3)
	return l.text + ((" — " + d.text) if d.text != "" else "")


func _on_item_input(event: InputEvent, panel: PanelContainer) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		accept_event()
		item_clicked.emit(str(panel.get_meta("item_id", "")))


## Hors des éléments (ou non traité par eux) : clic droit et molette sur tout le menu.
func _on_gui_input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton and event.pressed):
		return
	match event.button_index:
		MOUSE_BUTTON_RIGHT:
			mouse_event.emit("Y_SHORT")
		MOUSE_BUTTON_WHEEL_UP:
			mouse_event.emit("MINUS_SHORT")
		MOUSE_BUTTON_WHEEL_DOWN:
			mouse_event.emit("PLUS_SHORT")
		_:
			return
	accept_event()
