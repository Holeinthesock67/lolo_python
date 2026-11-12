extends Control

## Affichage des épreuves de piste dans le HUD (série VD, lot VD9), d'après les maquettes validées le 7 novembre
## (lot VD8), dans le style des panneaux du HUD (fond sombre translucide, coins arrondis) :
## - bandeau de l'épreuve en haut au centre, doré avec deux cloches au dernier tour ;
## - bloc des tours dans la colonne de droite (place libre donnée par hud_view.free_right_top()), et sous lui
##   le bloc du derny du keirin ;
## - liste de gauche sous la puissance (« Toi » sur fond or, dernier en rouge, sortis grisés et barrés) ;
## - en bas au centre : anneau de la poursuite et écart, ou grand chrono des contre-la-montre et de l'heure ;
## - bandeau du milieu : « DERNIER ! » à l'élimination, relais de l'américaine.
## Ne décide rien : affiche la sortie de track_hud_model.gd view(). Enfant du HUD : caché avec lui quand un
## menu plein écran est ouvert. Pas de class_name : preload("res://scripts/track/track_view.gd").

const Model := preload("res://scripts/track/track_hud_model.gd")
const UiTheme := preload("res://scripts/ui_theme.gd")

const BLOCK_W := 243.0          # largeur des colonnes du HUD (hud_view.gd COLUMN_W)
const MARGIN := 20.0            # hud_view.gd TOP_MARGIN
const LIST_TOP := 330.0         # sous le vent et l'abri du panneau de gauche (comme survivor_view.gd)
const ROW_H := 22.0
const ROW_SIZE := 16
const BANNER_W := 560.0
const BOTTOM_W := 540.0
const BOTTOM_OFFSET := 24.0
const CENTER_W := 640.0
const CENTER_TOP_FRAC := 0.62
const RING_W := 180.0
const RING_H := 92.0
const RING_COLOR := Color(0.78, 0.55, 0.27)
const GREEN := Color(0.35, 0.85, 0.45)

var right_top := 160.0          # haut du bloc des tours, posé par main.gd (hud_view.free_right_top())
var banner_top := 14.0          # haut du bandeau, posé par main.gd : sous le bandeau ERG de la séance libre
var _banner: PanelContainer
var _banner_title: Label
var _banner_sub: Label
var _bells: Array = []
var _laps: PanelContainer
var _laps_label: Label
var _laps_extra: Label
var _laps_value: Label
var _laps_bar: ProgressBar
var _pacer: PanelContainer
var _pacer_speed: Label
var _pacer_text: Label
var _pacer_hint: Label
var _list: PanelContainer
var _list_title: Label
var _rows: Array = []           # [ligne, place (Label), nom (RichTextLabel), valeur (Label), fond (StyleBoxFlat)]
var _pursuit: PanelContainer
var _ring: Control
var _gap_title: Label
var _gap: Label
var _gap_left: Label
var _chrono: PanelContainer
var _chrono_label: Label
var _chrono_big: Label
var _chrono_line: Label
var _center: PanelContainer
var _center_title: Label
var _center_sub: Label
var _ring_me := 0.0
var _ring_opp := 0.5
var _ring_has_opp := false


func _init() -> void:
	name = "TrackView"
	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)
	_build()


func _build() -> void:
	_banner = _panel(UiTheme.PANEL_BG)
	_banner.anchor_left = 0.5
	_banner.anchor_right = 0.5
	_banner.offset_left = -BANNER_W / 2.0
	_banner.offset_right = BANNER_W / 2.0
	_banner.offset_top = 14.0
	var brow := HBoxContainer.new()
	_banner.add_child(brow)
	var bcol := VBoxContainer.new()
	bcol.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_banner_title = _label(24, UiTheme.INK)
	_banner_sub = _label(16, UiTheme.DIM)
	for l in [_banner_title, _banner_sub]:
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		bcol.add_child(l)
	for k in 2:
		var b := Control.new()
		b.custom_minimum_size = Vector2(40, 44)
		b.mouse_filter = Control.MOUSE_FILTER_IGNORE
		b.draw.connect(_draw_bell.bind(b))
		_bells.append(b)
	brow.add_child(_bells[0])
	brow.add_child(bcol)
	brow.add_child(_bells[1])

	_laps = _right_panel()
	var lcol := _vbox(_laps)
	var head := HBoxContainer.new()
	_laps_label = _label(14, UiTheme.DIM)
	_laps_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_laps_extra = _label(16, UiTheme.GOLD)
	head.add_child(_laps_label)
	head.add_child(_laps_extra)
	lcol.add_child(head)
	_laps_value = _label(36, UiTheme.INK)
	_laps_bar = _bar(UiTheme.GOLD)
	lcol.add_child(_laps_value)
	lcol.add_child(_laps_bar)

	_pacer = _right_panel()
	var pcol := _vbox(_pacer)
	var phead := HBoxContainer.new()
	var pl := _label(14, UiTheme.DIM)
	pl.text = "DERNY"
	pl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_pacer_speed = _label(16, UiTheme.INK)
	phead.add_child(pl)
	phead.add_child(_pacer_speed)
	pcol.add_child(phead)
	_pacer_text = _label(20, UiTheme.GOLD)
	_pacer_hint = _label(14, UiTheme.DIM)
	pcol.add_child(_pacer_text)
	pcol.add_child(_pacer_hint)

	_list = _panel(UiTheme.PANEL_BG)
	_list.offset_left = MARGIN
	_list.offset_right = MARGIN + BLOCK_W
	_list.offset_top = LIST_TOP
	var rcol := _vbox(_list)
	rcol.add_theme_constant_override("separation", 1)
	_list_title = _label(14, UiTheme.DIM)
	rcol.add_child(_list_title)
	for i in range(Model.MAX_LINES):
		var row := PanelContainer.new()
		row.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var bg := StyleBoxFlat.new()
		bg.bg_color = Color(0, 0, 0, 0)
		bg.set_corner_radius_all(5)
		bg.content_margin_left = 4
		bg.content_margin_right = 4
		row.add_theme_stylebox_override("panel", bg)
		var h := HBoxContainer.new()
		var p := _label(ROW_SIZE - 1, UiTheme.DIM)
		p.custom_minimum_size = Vector2(28, 0)
		var n := RichTextLabel.new()
		n.bbcode_enabled = true
		n.fit_content = true
		n.scroll_active = false
		n.autowrap_mode = TextServer.AUTOWRAP_OFF
		n.mouse_filter = Control.MOUSE_FILTER_IGNORE
		n.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		n.custom_minimum_size = Vector2(0, ROW_H)
		n.add_theme_font_size_override("normal_font_size", ROW_SIZE)
		n.add_theme_font_size_override("bold_font_size", ROW_SIZE)
		var d := _label(ROW_SIZE - 1, UiTheme.INK)
		d.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		h.add_child(p)
		h.add_child(n)
		h.add_child(d)
		row.add_child(h)
		row.visible = false
		rcol.add_child(row)
		_rows.append([row, p, n, d, bg])

	_pursuit = _bottom_panel()
	var prow := HBoxContainer.new()
	prow.add_theme_constant_override("separation", 24)
	_pursuit.add_child(prow)
	_ring = Control.new()
	_ring.custom_minimum_size = Vector2(RING_W + 24.0, RING_H + 28.0)
	_ring.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ring.draw.connect(_draw_ring)
	prow.add_child(_ring)
	var gcol := VBoxContainer.new()
	gcol.alignment = BoxContainer.ALIGNMENT_CENTER
	_gap_title = _label(14, UiTheme.DIM)
	_gap_title.text = "ÉCART SUR LE BOT"
	_gap = _label(40, GREEN)
	_gap_left = _label(17, UiTheme.INK)
	for l in [_gap_title, _gap, _gap_left]:
		gcol.add_child(l)
	prow.add_child(gcol)

	_chrono = _bottom_panel()
	var ccol := _vbox(_chrono)
	_chrono_label = _label(15, UiTheme.DIM)
	_chrono_big = _label(48, UiTheme.INK)
	_chrono_line = _label(16, UiTheme.DIM)
	for l in [_chrono_label, _chrono_big, _chrono_line]:
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		ccol.add_child(l)

	_center = _panel(Model.RED)
	_center.anchor_left = 0.5
	_center.anchor_right = 0.5
	_center.anchor_top = CENTER_TOP_FRAC
	_center.anchor_bottom = CENTER_TOP_FRAC
	_center.offset_left = -CENTER_W / 2.0
	_center.offset_right = CENTER_W / 2.0
	var mcol := _vbox(_center)
	_center_title = _label(34, UiTheme.INK)
	_center_sub = _label(18, UiTheme.INK)
	for l in [_center_title, _center_sub]:
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		mcol.add_child(l)

	for p in [_banner, _laps, _pacer, _list, _pursuit, _chrono, _center]:
		add_child(p)


## `view` : sortie de track_hud_model.gd view().
func update_view(view: Dictionary) -> void:
	visible = bool(view.get("visible", false))
	if not visible:
		return
	var b: Dictionary = view.get("banner", {})
	_banner.visible = not b.is_empty()
	_banner.offset_top = banner_top
	if _banner.visible:
		_set_fill(_banner, b.get("color", UiTheme.PANEL_BG))
		_banner_title.text = str(b.get("title", ""))
		_banner_sub.text = str(b.get("sub", ""))
		_banner_sub.visible = _banner_sub.text != ""
		var bell := bool(b.get("bell", false))
		_banner_sub.add_theme_color_override("font_color", UiTheme.GOLD if bell else UiTheme.DIM)
		for x in _bells:
			(x as Control).modulate.a = 1.0 if bell else 0.0

	var l: Dictionary = view.get("laps", {})
	_laps.visible = not l.is_empty()
	_laps.offset_top = right_top
	if _laps.visible:
		_laps_label.text = str(l.get("label", ""))
		_laps_extra.text = str(l.get("extra", ""))
		_laps_value.text = str(l.get("value", ""))
		var bar := float(l.get("bar", -1.0))
		_laps_bar.visible = bar >= 0.0
		_laps_bar.value = maxf(bar, 0.0)

	var pc: Dictionary = view.get("pacer", {})
	_pacer.visible = not pc.is_empty()
	_pacer.offset_top = right_top + (_laps.get_combined_minimum_size().y + 10.0 if _laps.visible else 0.0)
	if _pacer.visible:
		_pacer_speed.text = str(pc.get("speed", ""))
		_pacer_text.text = str(pc.get("text", ""))
		_pacer_hint.text = str(pc.get("hint", ""))
		_pacer_hint.visible = _pacer_hint.text != ""

	var lst: Dictionary = view.get("list", {})
	var rows: Array = lst.get("rows", [])
	_list.visible = not rows.is_empty()
	_list_title.text = str(lst.get("title", ""))
	for i in range(_rows.size()):
		var r: Array = _rows[i]
		var shown := i < rows.size()
		(r[0] as Control).visible = shown
		if not shown:
			continue
		var it: Dictionary = rows[i]
		var kind := str(it.get("kind", "ok"))
		var color: Color = {"me": Color(0.12, 0.10, 0.04), "danger": Model.LAST_RED, "out": UiTheme.DISABLED,
			"team": Model.TEAM_BLUE}.get(kind, UiTheme.INK)
		var nm := str(it.get("name", ""))
		var bb := "[color=#%s]%s[/color]" % [color.to_html(false), nm]
		if kind == "out":
			bb = "[color=#%s][s]%s[/s][/color]" % [color.to_html(false), nm]
		elif kind == "me":
			bb = "[color=#%s]%s[/color]" % [color.to_html(false), nm]
		elif kind == "danger":
			bb = "[color=#%s]● %s[/color]" % [color.to_html(false), nm]
		(r[1] as Label).text = str(it.get("pos", ""))
		(r[1] as Label).add_theme_color_override("font_color", color)
		(r[2] as RichTextLabel).text = bb
		(r[3] as Label).text = str(it.get("value", ""))
		(r[3] as Label).add_theme_color_override("font_color", color)
		(r[4] as StyleBoxFlat).bg_color = Color(0.98, 0.78, 0.24, 0.94) if kind == "me" else Color(0, 0, 0, 0)

	var pu: Dictionary = view.get("pursuit", {})
	_pursuit.visible = not pu.is_empty()
	if _pursuit.visible:
		_gap.text = str(pu.get("gap_text", ""))
		_gap.add_theme_color_override("font_color", GREEN if bool(pu.get("good", true)) else Model.LAST_RED)
		_gap_left.text = str(pu.get("left", ""))
		_gap_title.visible = bool(pu.get("has_opp", false))
		_gap.visible = _gap_title.visible
		_ring_me = float(pu.get("me_frac", 0.0))
		_ring_opp = float(pu.get("opp_frac", 0.5))
		_ring_has_opp = bool(pu.get("has_opp", false))
		_ring.queue_redraw()

	var ch: Dictionary = view.get("chrono", {})
	_chrono.visible = not ch.is_empty()
	if _chrono.visible:
		_chrono_label.text = str(ch.get("label", ""))
		_chrono_big.text = str(ch.get("big", ""))
		_chrono_line.text = str(ch.get("line", ""))

	var ce: Dictionary = view.get("center", {})
	_center.visible = not ce.is_empty()
	if _center.visible:
		_set_fill(_center, ce.get("color", Model.RED))
		_center_title.text = str(ce.get("title", ""))
		_center_sub.text = str(ce.get("sub", ""))


## Cloche du dernier tour (maquette VD8) : dôme, corps, rebord et battant, en or.
func _draw_bell(b: Control) -> void:
	var c := b.size / 2.0
	var r := 13.0
	var col := UiTheme.GOLD
	b.draw_circle(c + Vector2(0, -r * 0.1), r, col)
	b.draw_rect(Rect2(c + Vector2(-r, -r * 0.1), Vector2(2.0 * r, r * 0.65)), col)
	b.draw_colored_polygon(PackedVector2Array([c + Vector2(-r * 1.25, r * 0.75), c + Vector2(r * 1.25, r * 0.75),
		c + Vector2(r, r * 0.45), c + Vector2(-r, r * 0.45)]), col)
	b.draw_circle(c + Vector2(0, r * 0.95), r * 0.28, col)


## Anneau de 250 m vu de haut (forme de stade), lignes de poursuite A en bas et B en haut, deux points.
func _draw_ring() -> void:
	var c := Vector2(12.0 + RING_W / 2.0, 14.0 + RING_H / 2.0)
	var rh := RING_H / 2.0
	var half := RING_W / 2.0 - rh
	var pts := PackedVector2Array()
	for i in 65:
		pts.append(c + ring_point(float(i) / 64.0, half, rh))
	_ring.draw_polyline(pts, RING_COLOR, 7.0, true)
	var font := get_theme_default_font()
	_ring.draw_string(font, c + Vector2(-4, rh + 14), "A", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, UiTheme.DIM)
	_ring.draw_string(font, c + Vector2(-4, -rh - 5), "B", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, UiTheme.DIM)
	if _ring_has_opp:
		_ring.draw_circle(c + ring_point(_ring_opp, half, rh), 8.0, Model.LAST_RED)
	_ring.draw_circle(c + ring_point(_ring_me, half, rh), 8.0, UiTheme.GOLD)


## Point d'un stade de demi-longueur droite `half` et de rayon `rh`, frac 0 au milieu du bas, sens antihoraire.
static func ring_point(frac: float, half: float, rh: float) -> Vector2:
	var straight := 2.0 * half
	var arc := PI * rh
	var d := fposmod(frac, 1.0) * (2.0 * straight + 2.0 * arc)
	if d < half:
		return Vector2(d, rh)
	d -= half
	if d < arc:
		var a := PI / 2.0 - d / rh
		return Vector2(half + rh * cos(a), rh * sin(a))
	d -= arc
	if d < straight:
		return Vector2(half - d, -rh)
	d -= straight
	if d < arc:
		var a2 := -PI / 2.0 - d / rh
		return Vector2(-half + rh * cos(a2), rh * sin(a2))
	d -= arc
	return Vector2(-half + d, rh)


## Pour les tests graphiques et le banc des menus : textes affichés.
func test_info() -> Dictionary:
	var names: Array = []
	for r in _rows:
		if (r[0] as Control).visible:
			names.append((r[2] as RichTextLabel).get_parsed_text())
	return {"visible": visible, "banner": _banner_title.text if visible and _banner.visible else "",
		"sub": _banner_sub.text if visible and _banner.visible else "",
		"bell": visible and _banner.visible and (_bells[0] as Control).modulate.a > 0.5,
		"laps": _laps_value.text if visible and _laps.visible else "",
		"list_title": _list_title.text if visible and _list.visible else "", "list": names,
		"pursuit": _gap.text if visible and _pursuit.visible else "",
		"chrono": _chrono_big.text if visible and _chrono.visible else "",
		"pacer": _pacer_text.text if visible and _pacer.visible else "",
		"center": _center_title.text if visible and _center.visible else "", "laps_top": _laps.offset_top}


func _right_panel() -> PanelContainer:
	var p := _panel(UiTheme.PANEL_BG)
	p.anchor_left = 1.0
	p.anchor_right = 1.0
	p.offset_left = -MARGIN - BLOCK_W
	p.offset_right = -MARGIN
	return p


func _bottom_panel() -> PanelContainer:
	var p := _panel(UiTheme.PANEL_BG)
	p.anchor_left = 0.5
	p.anchor_right = 0.5
	p.anchor_top = 1.0
	p.anchor_bottom = 1.0
	p.offset_left = -BOTTOM_W / 2.0
	p.offset_right = BOTTOM_W / 2.0
	p.grow_vertical = Control.GROW_DIRECTION_BEGIN
	p.offset_bottom = -BOTTOM_OFFSET
	p.offset_top = -BOTTOM_OFFSET
	return p


static func _style(fill: Color) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = fill
	s.set_corner_radius_all(10)
	s.content_margin_left = 14
	s.content_margin_right = 14
	s.content_margin_top = 8
	s.content_margin_bottom = 10
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
	b.custom_minimum_size = Vector2(0, 10)
	var bg := StyleBoxFlat.new()
	bg.bg_color = UiTheme.TRACK
	bg.set_corner_radius_all(5)
	var fg := StyleBoxFlat.new()
	fg.bg_color = fill
	fg.set_corner_radius_all(5)
	b.add_theme_stylebox_override("background", bg)
	b.add_theme_stylebox_override("fill", fg)
	return b
