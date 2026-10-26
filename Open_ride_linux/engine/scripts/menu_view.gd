extends Panel

## Menus au-dessus de la vue 3D (Lot N6) : titre, éléments avec un focus très visible, raison d'un
## élément désactivé (« à compiler »…), puis l'état des appareils (devices_view.gd) ou le bilan
## (summary_view.gd). Placé entre les panneaux latéraux du HUD d'E3, au-dessus du profil d'altitude ;
## mêmes tailles de police que le HUD (lisible à 2 m). Ne décide rien : affiche menu_flow.gd.
## Souris : clic gauche sur un élément = le valider, clic droit = retour, molette = choisir ;
## main.gd reçoit ces gestes par les signaux ci-dessous.
## Pas de class_name : charger par preload("res://scripts/menu_view.gd").

const DevicesView := preload("res://scripts/devices_view.gd")
const SummaryView := preload("res://scripts/summary_view.gd")

const TITLE_SIZE := 36
const ITEM_SIZE := 30
const DETAIL_SIZE := 20
## Éléments affichés à la fois ; au-delà, la fenêtre suit le focus.
const MAX_VISIBLE_ITEMS := 5
const FOCUS_BG := Color(0.95, 0.75, 0.20, 0.95)
const FOCUS_TEXT := Color(0.05, 0.05, 0.05)
const DISABLED_TEXT := Color(0.60, 0.62, 0.65)
const HINT := "Click : + / − choisir · A ou + long valider · Z ou − long retour   ·   Clavier : ↑ ↓ Entrée Échap   ·   Souris"
const HINT_PAUSE := "Click : + / − choisir · A ou + long valider · Y reprendre   ·   Clavier : ↑ ↓ Entrée, Échap reprendre   ·   Souris"

signal item_clicked(item_id: String)
## Événement du Click joué à la souris : MINUS_LONG (clic droit), MINUS_SHORT / PLUS_SHORT (molette).
signal mouse_event(event_name: String)

var title_label: Label
var status_label: Label
var items_box: VBoxContainer
var more_label: Label
var hint_label: Label
var devices: VBoxContainer
var summary: VBoxContainer
var _item_panels: Array[PanelContainer] = []
var _focus_style := StyleBoxFlat.new()
var _plain_style := StyleBoxEmpty.new()


func _init() -> void:
	name = "MenuView"
	visible = false
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.05, 0.07, 0.10, 0.82)
	style.set_corner_radius_all(10)
	add_theme_stylebox_override("panel", style)
	_focus_style.bg_color = FOCUS_BG
	_focus_style.set_corner_radius_all(6)
	_focus_style.content_margin_left = 12
	_focus_style.content_margin_right = 12
	_plain_style.content_margin_left = 12
	_plain_style.content_margin_right = 12
	gui_input.connect(_on_gui_input)
	# Entre les panneaux latéraux (20–320 px de chaque bord) et sous le panneau central (bas à 130 px).
	anchor_right = 1.0
	anchor_bottom = 1.0
	offset_left = 340.0
	offset_right = -340.0
	offset_top = 150.0
	offset_bottom = -135.0
	var box := VBoxContainer.new()
	box.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT, Control.PRESET_MODE_MINSIZE, 16)
	box.add_theme_constant_override("separation", 6)
	add_child(box)
	title_label = Label.new()
	title_label.add_theme_font_size_override("font_size", TITLE_SIZE)
	title_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(title_label)
	status_label = Label.new()
	status_label.add_theme_font_size_override("font_size", DETAIL_SIZE)
	status_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	status_label.modulate = FOCUS_BG
	status_label.clip_text = true
	box.add_child(status_label)
	summary = SummaryView.new()
	box.add_child(summary)
	items_box = VBoxContainer.new()
	items_box.add_theme_constant_override("separation", 4)
	box.add_child(items_box)
	more_label = Label.new()
	more_label.add_theme_font_size_override("font_size", DETAIL_SIZE)
	more_label.modulate = DISABLED_TEXT
	box.add_child(more_label)
	var spacer := Control.new()
	spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	box.add_child(spacer)
	devices = DevicesView.new()
	box.add_child(devices)
	hint_label = Label.new()
	hint_label.add_theme_font_size_override("font_size", 16)
	hint_label.modulate = DISABLED_TEXT
	hint_label.text = HINT
	hint_label.clip_text = true
	hint_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(hint_label)


## Textes des éléments affichés, séparés par « | », focus entre crochets (tests graphiques).
func items_text() -> String:
	var parts: Array[String] = []
	for p in _item_panels:
		if p.visible:
			var l: Label = p.get_child(0)
			parts.append(("[%s]" % l.text) if p.get_theme_stylebox("panel") == _focus_style else l.text)
	return " | ".join(parts)


## menu : état de menu_model.gd ; state : dernière trame ; summary_data : bilan (écran « summary »).
func update_display(menu: Dictionary, state: Dictionary, summary_data: Dictionary, show_details: bool) -> void:
	title_label.text = str(menu.get("title", ""))
	status_label.text = str(menu.get("status", ""))
	status_label.visible = status_label.text != ""
	var items: Array = menu.get("items", [])
	var focus := int(menu.get("focus", -1))
	var first := 0
	if items.size() > MAX_VISIBLE_ITEMS and focus >= 0:
		first = clampi(focus - MAX_VISIBLE_ITEMS / 2, 0, items.size() - MAX_VISIBLE_ITEMS)
	var shown := mini(items.size() - first, MAX_VISIBLE_ITEMS)
	while _item_panels.size() < shown:
		var p := PanelContainer.new()
		var l := Label.new()
		l.add_theme_font_size_override("font_size", ITEM_SIZE)
		l.clip_text = true
		p.add_child(l)
		p.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
		p.mouse_filter = Control.MOUSE_FILTER_PASS   # clic droit et molette remontent au panneau
		p.gui_input.connect(_on_item_input.bind(p))
		items_box.add_child(p)
		_item_panels.append(p)
	for i in range(_item_panels.size()):
		var p := _item_panels[i]
		p.visible = i < shown
		if not p.visible:
			continue
		var idx := first + i
		var it: Dictionary = items[idx]
		var l: Label = p.get_child(0)
		var detail := str(it.get("detail", ""))
		l.text = str(it.get("label", "")) + ((" — " + detail) if detail != "" else "")
		p.set_meta("item_id", str(it.get("id", "")))
		var focused := idx == focus
		p.add_theme_stylebox_override("panel", _focus_style if focused else _plain_style)
		l.modulate = FOCUS_TEXT if focused else (Color.WHITE if it.get("enabled", true) else DISABLED_TEXT)
	more_label.text = "%d / %d" % [focus + 1, items.size()] if items.size() > MAX_VISIBLE_ITEMS else ""
	var screen := str(menu.get("screen", ""))
	summary.visible = screen == "summary"
	devices.visible = screen in ["home", "ready", "connect"]
	# Aide toujours visible (sans elle, rien ne dit qu'il faut un appui long pour valider) ; une ligne
	# coupée à la largeur du panneau, sous les appareils.
	hint_label.text = HINT_PAUSE if screen == "pause" else HINT
	if summary.visible:
		summary.update_display(summary_data, show_details, str(state.get("mode", "")))
	if devices.visible:
		devices.update_display(state)


func _on_item_input(event: InputEvent, panel: PanelContainer) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		accept_event()
		item_clicked.emit(str(panel.get_meta("item_id", "")))


## Hors des éléments (ou non traité par eux) : clic droit et molette sur tout le panneau.
func _on_gui_input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton and event.pressed):
		return
	match event.button_index:
		MOUSE_BUTTON_RIGHT:
			mouse_event.emit("MINUS_LONG")
		MOUSE_BUTTON_WHEEL_UP:
			mouse_event.emit("MINUS_SHORT")
		MOUSE_BUTTON_WHEEL_DOWN:
			mouse_event.emit("PLUS_SHORT")
		_:
			return
	accept_event()
