extends Panel

## Menus au-dessus de la vue 3D (Lot N6) : titre, éléments avec un focus très visible, raison d'un
## élément désactivé (« à compiler »…), puis l'état des appareils (devices_view.gd) ou le bilan
## (summary_view.gd). Placé entre les panneaux latéraux du HUD d'E3, au-dessus du profil d'altitude ;
## mêmes tailles de police que le HUD (lisible à 2 m). Ne décide rien : affiche menu_flow.gd.
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
const HINT := "+ / − : choisir   ·   long + : valider   ·   long − : retour   ·   Y : pause"

var title_label: Label
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
		var focused := idx == focus
		p.add_theme_stylebox_override("panel", _focus_style if focused else _plain_style)
		l.modulate = FOCUS_TEXT if focused else (Color.WHITE if it.get("enabled", true) else DISABLED_TEXT)
	more_label.text = "%d / %d" % [focus + 1, items.size()] if items.size() > MAX_VISIBLE_ITEMS else ""
	var screen := str(menu.get("screen", ""))
	summary.visible = screen == "summary"
	devices.visible = screen in ["home", "ready"]
	hint_label.visible = not devices.visible   # à 1024 × 600, l'aide et les appareils ne tiennent pas ensemble
	if summary.visible:
		summary.update_display(summary_data, show_details, str(state.get("mode", "")))
	if devices.visible:
		devices.update_display(state)
