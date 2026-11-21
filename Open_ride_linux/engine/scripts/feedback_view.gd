extends Control

## Vue des retours et consignes communs (lot RT1) : affiche la sortie de feedback_model.gd view(), la même pour
## tous les modes (maquettes validées le 21 novembre 2026) :
## - zone de consigne en bas au centre (CONSIGNE_W de large, au-dessus du bandeau ERG et du graphique) : « À FAIRE »
##   et les boutons sur la première ligne, l'action en gros, puis « Objectif … · Pourquoi … » ;
## - bandeau du moment juste au-dessus : mot de la famille (« + BIEN », « ! ATTENTION »…) dans une pastille, titre
##   et détail, couleur de la famille ;
## - résultat au milieu de l'écran : « ★ RÉSULTAT », titre en grand, détail.
## Enfant du HUD : caché avec lui. Ne décide rien. Pas de class_name : preload("res://scripts/feedback_view.gd").

const UiTheme := preload("res://scripts/ui_theme.gd")

const CONSIGNE_W := 714.0
const BOTTOM_OFFSET := 146.0    # au-dessus du bandeau ERG (126 px + 15) et du graphique de puissance
const CONSIGNE_BG := Color(0.114, 0.165, 0.235, 0.92)
const CONSIGNE_KEY := Color(0.561, 0.827, 1.0)
const RESULT_W := 700.0
const RESULT_TOP_FRAC := 0.35

var _consigne: PanelContainer
var _c_key: Label
var _c_chips: HBoxContainer
var _c_action: Label
var _c_detail: Label
var _toast: PanelContainer
var _t_tag: Label
var _t_title: Label
var _t_sub: Label
var _result: PanelContainer
var _r_tag: Label
var _r_title: Label
var _r_sub: Label
var _chips_shown: Array = []


func _init() -> void:
	name = "FeedbackView"
	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)
	_build()


func _build() -> void:
	_consigne = _panel(CONSIGNE_BG, 12)
	_bottom_center(_consigne, CONSIGNE_W)
	_consigne.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_consigne.offset_bottom = -BOTTOM_OFFSET
	_consigne.offset_top = -BOTTOM_OFFSET - 92.0
	var col := _vbox(_consigne, 2)
	var head := HBoxContainer.new()
	head.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_c_key = _label(13, CONSIGNE_KEY)
	_c_key.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(_c_key)
	_c_chips = HBoxContainer.new()
	_c_chips.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_c_chips.add_theme_constant_override("separation", 6)
	head.add_child(_c_chips)
	col.add_child(head)
	_c_action = _label(24, UiTheme.INK)
	_c_action.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	col.add_child(_c_action)
	_c_detail = _label(15, Color(0.85, 0.89, 0.93))
	_c_detail.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	col.add_child(_c_detail)

	_toast = _panel(Color.WHITE, 12)
	_bottom_center(_toast, CONSIGNE_W)
	var row := HBoxContainer.new()
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_theme_constant_override("separation", 14)
	var tag_box := _panel(Color(0, 0, 0, 0.22), 8)
	tag_box.visible = true
	tag_box.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_t_tag = _label(17, UiTheme.INK)
	tag_box.add_child(_t_tag)
	row.add_child(tag_box)
	var tcol := _vbox(row, 0)
	tcol.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_t_title = _label(22, UiTheme.INK)
	_t_sub = _label(15, UiTheme.INK)
	tcol.add_child(_t_title)
	tcol.add_child(_t_sub)
	_toast.add_child(row)

	_result = _panel(Color.WHITE, 16)
	_result.anchor_left = 0.5
	_result.anchor_right = 0.5
	_result.anchor_top = RESULT_TOP_FRAC
	_result.anchor_bottom = RESULT_TOP_FRAC
	_result.offset_left = -RESULT_W / 2.0
	_result.offset_right = RESULT_W / 2.0
	var rcol := _vbox(_result, 4)
	_r_tag = _label(16, UiTheme.INK)
	_r_title = _label(50, UiTheme.INK)
	_r_sub = _label(20, UiTheme.INK)
	for l in [_r_tag, _r_title, _r_sub]:
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		rcol.add_child(l)

	for p in [_consigne, _toast, _result]:
		add_child(p)


## `view` : sortie de feedback_model.gd view().
func update_view(view: Dictionary) -> void:
	visible = bool(view.get("visible", false))
	if not visible:
		return
	var c: Dictionary = view.get("consigne", {})
	_consigne.visible = not c.is_empty()
	if _consigne.visible:
		_c_key.text = str(c.get("k", ""))
		_c_action.text = str(c.get("action", ""))
		_c_detail.text = str(c.get("detail", ""))
		_c_detail.visible = _c_detail.text != ""
		_set_chips(c.get("chips", []) if c.get("chips", []) is Array else [])
	var t: Dictionary = view.get("toast", {})
	_toast.visible = not t.is_empty()
	if _toast.visible:
		_set_fill(_toast, t.get("color", Color.DIM_GRAY))
		_t_tag.text = str(t.get("tag", ""))
		_t_title.text = str(t.get("title", ""))
		_t_sub.text = str(t.get("sub", ""))
		_t_sub.visible = _t_sub.text != ""
		# juste au-dessus de la consigne (ou à sa place sans consigne)
		var bottom := (_consigne.offset_top - 6.0) if _consigne.visible else -BOTTOM_OFFSET
		_toast.offset_bottom = bottom
		_toast.offset_top = bottom - 64.0
	var r: Dictionary = view.get("result", {})
	_result.visible = not r.is_empty()
	if _result.visible:
		_set_fill(_result, r.get("color", Color.DIM_GRAY))
		_r_tag.text = str(r.get("tag", ""))
		_r_title.text = str(r.get("title", ""))
		_r_sub.text = str(r.get("sub", ""))


## Textes affichés, pour les tests et les bancs.
func test_info() -> Dictionary:
	return {"visible": visible,
		"consigne_k": _c_key.text if visible and _consigne.visible else "",
		"consigne": _c_action.text if visible and _consigne.visible else "",
		"consigne_detail": _c_detail.text if visible and _consigne.visible else "",
		"chips": _chips_shown.duplicate() if visible and _consigne.visible else [],
		"toast": ("%s %s" % [_t_tag.text, _t_title.text]) if visible and _toast.visible else "",
		"result": _r_title.text if visible and _result.visible else ""}


func _set_chips(chips: Array) -> void:
	if chips == _chips_shown:
		return
	_chips_shown = chips.duplicate()
	for ch in _c_chips.get_children():
		_c_chips.remove_child(ch)
		ch.queue_free()
	for text in chips:
		var p := _panel(Color(0, 0, 0, 0.27), 7)
		var s := p.get_theme_stylebox("panel") as StyleBoxFlat
		s.border_color = CONSIGNE_KEY
		s.set_border_width_all(2)
		s.content_margin_top = 2
		s.content_margin_bottom = 2
		s.content_margin_left = 7
		s.content_margin_right = 7
		p.visible = true
		p.add_child(_label(13, CONSIGNE_KEY))
		(p.get_child(0) as Label).text = str(text)
		_c_chips.add_child(p)


static func _bottom_center(p: Control, w: float) -> void:
	p.anchor_left = 0.5
	p.anchor_right = 0.5
	p.anchor_top = 1.0
	p.anchor_bottom = 1.0
	p.offset_left = -w / 2.0
	p.offset_right = w / 2.0


static func _panel(fill: Color, radius: int) -> PanelContainer:
	var p := PanelContainer.new()
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var s := StyleBoxFlat.new()
	s.bg_color = fill
	s.set_corner_radius_all(radius)
	s.content_margin_left = 14
	s.content_margin_right = 14
	s.content_margin_top = 8
	s.content_margin_bottom = 9
	p.add_theme_stylebox_override("panel", s)
	p.visible = false
	return p


static func _set_fill(p: PanelContainer, fill: Color) -> void:
	var s := p.get_theme_stylebox("panel") as StyleBoxFlat
	if s != null and s.bg_color != fill:
		s.bg_color = fill


static func _vbox(parent: Control, sep: int) -> VBoxContainer:
	var v := VBoxContainer.new()
	v.mouse_filter = Control.MOUSE_FILTER_IGNORE
	v.add_theme_constant_override("separation", sep)
	parent.add_child(v)
	return v


static func _label(size: int, color: Color) -> Label:
	var l := Label.new()
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l
