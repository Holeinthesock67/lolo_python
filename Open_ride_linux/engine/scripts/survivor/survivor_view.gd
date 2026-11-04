extends Control

## Affichage du mode « Dernier survivant » dans le HUD (série DS, lot DS6), d'après les maquettes validées le
## 31 octobre (lot DS4), dans le style des panneaux du HUD (fond sombre translucide, coins arrondis) :
## - bloc « SURVIVANT » dans la colonne de droite (place libre donnée par hud_view.free_right_top()) :
##   distance à l'arche en or, « Arche 2 / 4 », barre d'approche, rang, écart avec le dernier ; cadre rouge et
##   « DERNIER » en rouge quand le cycliste est dernier (pas de clignotement) ;
## - liste des coureurs à gauche, sous le vent : « Toi » sur fond or, point rouge devant le dernier, éliminés
##   grisés et barrés avec leur arche ;
## - bandeau d'élimination d'un bot en bas de l'écran, bandeaux du cycliste éliminé (rouge) et du vainqueur
##   (vert) au milieu.
## Ne décide rien : affiche la sortie de survivor_hud_model.gd view(). Enfant du HUD : caché avec lui quand un
## menu plein écran est ouvert. Pas de class_name : preload("res://scripts/survivor/survivor_view.gd").

const Model := preload("res://scripts/survivor/survivor_hud_model.gd")
const UiTheme := preload("res://scripts/ui_theme.gd")

const BLOCK_W := 243.0          # largeur des colonnes du HUD (hud_view.gd COLUMN_W)
const MARGIN := 20.0            # hud_view.gd TOP_MARGIN
const LIST_TOP := 330.0         # sous le vent et l'abri du panneau de gauche (comme wtf_view.gd)
const ROW_H := 22.0
const TITLE_SIZE := 13
const ARCH_SIZE := 24
const TEXT_SIZE := 17
const ROW_SIZE := 16
const BOTTOM_W := 420.0
const BOTTOM_OFFSET := 150.0    # au-dessus du profil d'altitude et du bandeau ERG
const CENTER_W := 640.0
const CENTER_TOP_FRAC := 0.62   # sous le cycliste, sans cacher la route devant lui

var right_top := 160.0          # haut du bloc, posé par main.gd (hud_view.free_right_top())
var _block: PanelContainer
var _block_title: Label
var _block_dist: Label
var _block_arch: Label
var _block_bar: ProgressBar
var _block_rank: Label
var _block_danger: Label
var _block_last: Label
var _block_ahead: Label
var _block_ahead_w: Label
var _list: PanelContainer
var _rows: Array = []           # [HBoxContainer, nom (RichTextLabel), détail (Label), fond (StyleBoxFlat)]
var _bottom: PanelContainer
var _bottom_title: Label
var _bottom_sub: Label
var _center: PanelContainer
var _center_title: Label
var _center_sub: Label


func _init() -> void:
	name = "SurvivorView"
	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)
	_build()


func _build() -> void:
	_block = _panel(UiTheme.PANEL_BG)
	_block.anchor_left = 1.0
	_block.anchor_right = 1.0
	_block.offset_left = -MARGIN - BLOCK_W
	_block.offset_right = -MARGIN
	var col := _vbox(_block)
	var head := HBoxContainer.new()
	_block_title = _label(TITLE_SIZE, UiTheme.DIM)
	_block_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_block_dist = _label(TITLE_SIZE + 2, UiTheme.GOLD)
	head.add_child(_block_title)
	head.add_child(_block_dist)
	col.add_child(head)
	_block_arch = _label(ARCH_SIZE, UiTheme.INK)
	_block_bar = _bar(UiTheme.GOLD)
	_block_rank = _label(TEXT_SIZE, UiTheme.INK)
	var last_row := HBoxContainer.new()
	last_row.add_theme_constant_override("separation", 8)
	_block_danger = _label(TEXT_SIZE, Model.LAST_RED)
	_block_last = _label(TITLE_SIZE + 1, UiTheme.DIM)
	_block_last.clip_text = true
	_block_last.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	last_row.add_child(_block_danger)
	last_row.add_child(_block_last)
	_block_ahead = _label(TITLE_SIZE + 1, UiTheme.INK)   # coureur devant et puissance pour le rejoindre (4 novembre)
	_block_ahead_w = _label(TITLE_SIZE + 1, UiTheme.GOLD)
	for l in [_block_ahead, _block_ahead_w]:
		l.clip_text = true
	for c in [_block_arch, _block_bar, _block_rank, last_row, _block_ahead, _block_ahead_w]:
		col.add_child(c)

	_list = _panel(UiTheme.PANEL_BG)
	_list.offset_left = MARGIN
	_list.offset_right = MARGIN + BLOCK_W
	_list.offset_top = LIST_TOP
	var lcol := _vbox(_list)
	lcol.add_theme_constant_override("separation", 1)
	for i in range(Model.MAX_LINES):
		var row := PanelContainer.new()
		row.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var bg := StyleBoxFlat.new()
		bg.bg_color = Color(0, 0, 0, 0)
		bg.set_corner_radius_all(3)
		bg.content_margin_left = 4
		bg.content_margin_right = 4
		row.add_theme_stylebox_override("panel", bg)
		var h := HBoxContainer.new()
		var n := RichTextLabel.new()
		n.bbcode_enabled = true
		n.fit_content = true
		n.scroll_active = false
		n.autowrap_mode = TextServer.AUTOWRAP_OFF
		n.mouse_filter = Control.MOUSE_FILTER_IGNORE
		n.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		n.custom_minimum_size = Vector2(0, ROW_H)
		n.add_theme_font_size_override("normal_font_size", ROW_SIZE)
		var d := _label(ROW_SIZE - 3, UiTheme.DIM)
		d.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		h.add_child(n)
		h.add_child(d)
		row.add_child(h)
		row.visible = false
		lcol.add_child(row)
		_rows.append([row, n, d, bg])

	_bottom = _panel(Model.RED)
	_bottom.anchor_left = 0.5
	_bottom.anchor_right = 0.5
	_bottom.anchor_top = 1.0
	_bottom.anchor_bottom = 1.0
	_bottom.offset_left = -BOTTOM_W / 2.0
	_bottom.offset_right = BOTTOM_W / 2.0
	_bottom.offset_top = -BOTTOM_OFFSET - 64.0
	_bottom.offset_bottom = -BOTTOM_OFFSET
	var bcol := _vbox(_bottom)
	_bottom_title = _label(22, UiTheme.INK)
	_bottom_sub = _label(14, UiTheme.INK)
	for l in [_bottom_title, _bottom_sub]:
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		bcol.add_child(l)

	_center = _panel(Model.RED)
	_center.anchor_left = 0.5
	_center.anchor_right = 0.5
	_center.anchor_top = CENTER_TOP_FRAC
	_center.anchor_bottom = CENTER_TOP_FRAC
	_center.offset_left = -CENTER_W / 2.0
	_center.offset_right = CENTER_W / 2.0
	var ccol := _vbox(_center)
	_center_title = _label(40, UiTheme.INK)
	_center_sub = _label(16, UiTheme.INK)
	for l in [_center_title, _center_sub]:
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		ccol.add_child(l)

	for p in [_block, _list, _bottom, _center]:
		add_child(p)


## `view` : sortie de survivor_hud_model.gd view().
func update_view(view: Dictionary) -> void:
	visible = bool(view.get("visible", false))
	if not visible:
		return
	var b: Dictionary = view.get("block", {})
	_block.visible = not b.is_empty()
	_block.offset_top = right_top
	if _block.visible:
		_block_title.text = str(b.get("title", ""))
		_block_dist.text = str(b.get("dist", ""))
		_block_arch.text = str(b.get("arch", ""))
		_block_bar.value = float(b.get("bar", 0.0))
		_block_rank.text = str(b.get("rank", ""))
		_block_danger.text = str(b.get("danger_text", ""))
		_block_danger.visible = _block_danger.text != ""
		_block_last.text = str(b.get("last", ""))
		_block_ahead.text = str(b.get("ahead", ""))
		_block_ahead.visible = _block_ahead.text != ""
		_block_ahead_w.text = str(b.get("ahead_w", ""))
		_block_ahead_w.visible = _block_ahead_w.text != ""
		var st := _block.get_theme_stylebox("panel") as StyleBoxFlat
		var danger := bool(b.get("danger", false))
		st.set_border_width_all(2 if danger else 0)
		st.border_color = Model.LAST_RED
	var rows: Array = view.get("list", [])
	_list.visible = not rows.is_empty()
	for i in range(_rows.size()):
		var r: Array = _rows[i]
		var shown := i < rows.size()
		(r[0] as Control).visible = shown
		if not shown:
			continue
		var it: Dictionary = rows[i]
		var name_text := str(it.get("name", ""))
		var bb := name_text
		if bool(it.get("out", false)):
			bb = "[color=#%s][s]%s[/s][/color]" % [UiTheme.DISABLED.to_html(false), name_text]
		elif bool(it.get("me", false)):
			bb = "[color=#111111][b]%s[/b][/color]" % name_text
		elif bool(it.get("last", false)):
			bb = "[color=#%s]● %s[/color]" % [Model.LAST_RED.to_html(false), name_text]
		(r[1] as RichTextLabel).text = bb
		var d := r[2] as Label
		d.text = str(it.get("detail", ""))
		d.add_theme_color_override("font_color", Color(0.07, 0.07, 0.07) if bool(it.get("me", false)) and not bool(it.get("out", false))
			else (Model.LAST_RED if bool(it.get("last", false)) else UiTheme.DIM))
		(r[3] as StyleBoxFlat).bg_color = Model.YELLOW if bool(it.get("me", false)) and not bool(it.get("out", false)) else Color(0, 0, 0, 0)
	var bo: Dictionary = view.get("bottom", {})
	_bottom.visible = not bo.is_empty()
	if _bottom.visible:
		_set_fill(_bottom, bo.get("color", Model.RED))
		_bottom_title.text = str(bo.get("title", ""))
		_bottom_sub.text = str(bo.get("sub", ""))
	var ce: Dictionary = view.get("center", {})
	_center.visible = not ce.is_empty()
	if _center.visible:
		_set_fill(_center, ce.get("color", Model.RED))
		_center_title.text = str(ce.get("title", ""))
		_center_sub.text = str(ce.get("sub", ""))


## Pour les tests graphiques et le banc des menus : textes affichés.
func test_info() -> Dictionary:
	var names: Array = []
	for r in _rows:
		if (r[0] as Control).visible:
			names.append((r[1] as RichTextLabel).get_parsed_text())
	return {"visible": visible, "block": _block_arch.text if visible and _block.visible else "",
		"rank": _block_rank.text if visible and _block.visible else "",
		"danger": _block_danger.text if visible and _block.visible and _block_danger.visible else "",
		"ahead": (_block_ahead.text + " · " + _block_ahead_w.text) if visible and _block.visible and _block_ahead.visible else "",
		"list": names, "bottom": _bottom_title.text if visible and _bottom.visible else "",
		"center": _center_title.text if visible and _center.visible else "", "block_top": _block.offset_top}


static func _style(fill: Color) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = fill
	s.set_corner_radius_all(8)
	s.content_margin_left = 12
	s.content_margin_right = 12
	s.content_margin_top = 8
	s.content_margin_bottom = 8
	return s


func _panel(fill: Color) -> PanelContainer:
	var p := PanelContainer.new()
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	p.add_theme_stylebox_override("panel", _style(fill))
	p.visible = false
	return p


func _set_fill(p: PanelContainer, fill: Color) -> void:
	var s := p.get_theme_stylebox("panel") as StyleBoxFlat
	if s != null and s.bg_color != fill:
		s.bg_color = fill


static func _vbox(parent: Control) -> VBoxContainer:
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 4)
	parent.add_child(v)
	return v


static func _label(size: int, color: Color) -> Label:
	var l := Label.new()
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


static func _bar(fill: Color) -> ProgressBar:
	var b := ProgressBar.new()
	b.min_value = 0.0
	b.max_value = 1.0
	b.step = 0.0
	b.show_percentage = false
	b.custom_minimum_size = Vector2(0, 6)
	var bg := StyleBoxFlat.new()
	bg.bg_color = UiTheme.TRACK
	bg.set_corner_radius_all(3)
	var fg := StyleBoxFlat.new()
	fg.bg_color = fill
	fg.set_corner_radius_all(3)
	b.add_theme_stylebox_override("background", bg)
	b.add_theme_stylebox_override("fill", fg)
	return b
