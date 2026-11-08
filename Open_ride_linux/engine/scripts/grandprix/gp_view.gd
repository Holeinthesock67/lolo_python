extends Control

## Affichage du « Grand Prix des objets » dans le HUD (série GP, lot GP8), d'après les maquettes GP6 validées
## le 7 novembre 2026, dans la charte cartoon CT9 (aplats papier, bord à l'encre épais, ombre portée décalée),
## comme l'habillage du mode WTF (wtf_view.gd) :
## - case d'objet en haut au centre, sous le panneau central du HUD : pastille de l'objet, badge « ×2 » des
##   charges, roulette pendant le tirage, invite « Z : Trois musettes » ; effets en cours dessous ;
## - place, tours et écart dans la colonne de droite (place libre donnée par hud_view.free_right_top()) ;
## - bande de course à gauche, sous le vent (12 lignes au plus) : « Toi » sur fond encre, objet tenu ou
##   pastille « touché » au bout de chaque ligne ;
## - trois traits de voie en bas au centre, avec l'aide des boutons ;
## - avertissement au-dessus des voies (pastille, texte, flèche), contour de 14 px aux bords de l'écran et
##   chevrons en bas pour un danger qui vient de derrière ; aucun flash plein écran.
## Le HUD de base (puissance, vitesse, profil) reste à sa place, comme dans les autres modes.
## Ne décide rien : affiche la sortie de gp_hud_model.gd view(). Enfant du HUD : caché avec lui quand un menu
## plein écran est ouvert. Pas de class_name : preload("res://scripts/grandprix/gp_view.gd").

const Model := preload("res://scripts/grandprix/gp_hud_model.gd")
const Items := preload("res://scripts/grandprix/gp_items.gd")

const INK := Items.INK
const PAPER := Items.PAPER
const BORDER := 4
const RADIUS := 16
const SHADOW := 5
const MARGIN := 20.0            # hud_view.gd TOP_MARGIN
const COLUMN_W := 243.0         # hud_view.gd COLUMN_W
const ITEM_TOP := 125.0         # sous le panneau central du HUD (comme le bandeau WTF)
const ITEM_SIZE := 92.0
const KEY_SIZE := 18
const FX_SIZE := 14
const STRIP_TOP := 330.0        # sous le vent et l'abri du panneau de gauche (comme la liste du Dernier survivant)
const ROW_H := 24.0
const ROW_SIZE := 16
const BADGE_R := 10.0
const PLACE_SIZE := 46
const OF_SIZE := 22
const GAP_SIZE := 16
const LANES_W := 270.0
const LANES_H := 34.0
const LANES_BOTTOM := 40.0      # bas de l'écran : voies, puis l'aide dessous
const HINT_SIZE := 13
const WARN_W := 520.0
const WARN_BOTTOM := 104.0      # au-dessus des voies
const WARN_SIZE := 24
const OUTLINE_PX := 14.0
const CHEVRON_STEP := 120.0

var right_top := 160.0          # haut du bloc de place, posé par main.gd (hud_view.free_right_top())
var _view: Dictionary = {}
var _item_box: Control
var _item_key: Label
var _fx_line: Label
var _place: PanelContainer
var _place_big: Label
var _place_of: Label
var _place_lap: Label
var _place_gap: Label
var _strip: PanelContainer
var _rows: Array = []           # [PanelContainer, place, nom, écart, pastille (Control), fond, {appliqué}]
var _lanes: Control
var _hint: Label
var _warn: PanelContainer
var _warn_badge: Control
var _warn_text: Label
var _warn_arrow: Control
var _outline: Control
var _font: Font


func _init() -> void:
	name = "GrandPrixView"
	visible = false
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)
	_font = ThemeDB.fallback_font
	_build()


func _build() -> void:
	# Contour de l'écran (sous tout le reste)
	_outline = _canvas(_draw_outline)
	_outline.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(_outline)

	# Case d'objet, en haut au centre
	_item_box = _canvas(_draw_item)
	_item_box.anchor_left = 0.5
	_item_box.anchor_right = 0.5
	_item_box.offset_left = -ITEM_SIZE / 2.0
	_item_box.offset_right = ITEM_SIZE / 2.0
	_item_box.offset_top = ITEM_TOP
	_item_box.offset_bottom = ITEM_TOP + ITEM_SIZE
	add_child(_item_box)
	_item_key = _outlined(KEY_SIZE)
	_item_key.anchor_left = 0.5
	_item_key.anchor_right = 0.5
	_item_key.offset_left = -200.0
	_item_key.offset_right = 200.0
	_item_key.offset_top = ITEM_TOP + ITEM_SIZE + 2.0
	_item_key.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(_item_key)
	_fx_line = _outlined(FX_SIZE)
	_fx_line.anchor_left = 0.5
	_fx_line.anchor_right = 0.5
	_fx_line.offset_left = -200.0
	_fx_line.offset_right = 200.0
	_fx_line.offset_top = ITEM_TOP + ITEM_SIZE + 4.0 + KEY_SIZE * 1.4
	_fx_line.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(_fx_line)

	# Place, tours, écart (colonne de droite)
	_place = _panel(PAPER)
	_place.anchor_left = 1.0
	_place.anchor_right = 1.0
	_place.offset_left = -MARGIN - COLUMN_W
	_place.offset_right = -MARGIN
	var pcol := VBoxContainer.new()
	pcol.add_theme_constant_override("separation", 0)
	_place.add_child(pcol)
	var prow := HBoxContainer.new()
	prow.add_theme_constant_override("separation", 10)
	_place_big = _label(PLACE_SIZE, INK)
	var side := VBoxContainer.new()
	side.add_theme_constant_override("separation", 0)
	side.alignment = BoxContainer.ALIGNMENT_CENTER
	_place_of = _label(OF_SIZE, INK)
	_place_lap = _label(GAP_SIZE, INK)
	side.add_child(_place_of)
	side.add_child(_place_lap)
	prow.add_child(_place_big)
	prow.add_child(side)
	pcol.add_child(prow)
	_place_gap = _label(GAP_SIZE, INK)
	_place_gap.clip_text = true
	pcol.add_child(_place_gap)
	add_child(_place)

	# Bande de course (gauche)
	_strip = _panel(PAPER)
	_strip.offset_left = MARGIN
	_strip.offset_right = MARGIN + COLUMN_W
	_strip.offset_top = STRIP_TOP
	var scol := VBoxContainer.new()
	scol.add_theme_constant_override("separation", 2)
	_strip.add_child(scol)
	for i in range(Model.MAX_ROWS):
		var row := PanelContainer.new()
		row.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var bg := StyleBoxFlat.new()
		bg.bg_color = Color(0, 0, 0, 0)
		bg.set_corner_radius_all(6)
		bg.content_margin_left = 6
		bg.content_margin_right = 4
		row.add_theme_stylebox_override("panel", bg)
		var h := HBoxContainer.new()
		h.add_theme_constant_override("separation", 6)
		var p := _label(ROW_SIZE, INK)
		p.custom_minimum_size = Vector2(18, ROW_H)
		var n := _label(ROW_SIZE, INK)
		n.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		n.clip_text = true
		var g := _label(ROW_SIZE - 3, INK)
		g.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		var badge := Control.new()
		badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
		badge.custom_minimum_size = Vector2(BADGE_R * 2.0 + 4.0, ROW_H)
		badge.set_meta("row", {})
		badge.draw.connect(_draw_row_badge.bind(badge))
		for c in [p, n, g, badge]:
			h.add_child(c)
		row.add_child(h)
		row.visible = false
		scol.add_child(row)
		_rows.append([row, p, n, g, badge, bg, {}])
	add_child(_strip)

	# Avertissement, au-dessus des voies
	_warn = _panel(PAPER)
	_warn.anchor_left = 0.5
	_warn.anchor_right = 0.5
	_warn.anchor_top = 1.0
	_warn.anchor_bottom = 1.0
	_warn.offset_left = -WARN_W / 2.0
	_warn.offset_right = WARN_W / 2.0
	_warn.offset_top = -WARN_BOTTOM - 62.0
	_warn.offset_bottom = -WARN_BOTTOM
	var wrow := HBoxContainer.new()
	wrow.add_theme_constant_override("separation", 14)
	_warn_badge = _canvas(_draw_warn_badge)
	_warn_badge.custom_minimum_size = Vector2(44, 44)
	_warn_text = _label(WARN_SIZE, INK)
	_warn_text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_warn_text.clip_text = true
	_warn_text.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_warn_arrow = _canvas(_draw_warn_arrow)
	_warn_arrow.custom_minimum_size = Vector2(40, 44)
	for c in [_warn_badge, _warn_text, _warn_arrow]:
		wrow.add_child(c)
	_warn.add_child(wrow)
	add_child(_warn)

	# Trois traits de voie et l'aide, en bas au centre
	_lanes = _canvas(_draw_lanes)
	_lanes.anchor_left = 0.5
	_lanes.anchor_right = 0.5
	_lanes.anchor_top = 1.0
	_lanes.anchor_bottom = 1.0
	_lanes.offset_left = -LANES_W / 2.0
	_lanes.offset_right = LANES_W / 2.0
	_lanes.offset_top = -LANES_BOTTOM - LANES_H
	_lanes.offset_bottom = -LANES_BOTTOM
	add_child(_lanes)
	_hint = _outlined(HINT_SIZE)
	_hint.anchor_left = 0.5
	_hint.anchor_right = 0.5
	_hint.anchor_top = 1.0
	_hint.anchor_bottom = 1.0
	_hint.offset_left = -LANES_W
	_hint.offset_right = LANES_W
	_hint.offset_top = -LANES_BOTTOM + 2.0
	_hint.offset_bottom = -LANES_BOTTOM + 22.0
	_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(_hint)


## `view` : sortie de gp_hud_model.gd view().
func update_view(view: Dictionary) -> void:
	var was := visible
	visible = bool(view.get("visible", false))
	if not visible:
		_view = {}
		return
	var changed := not was or _view.hash() != view.hash()
	_view = view
	if not changed:
		return
	var it: Dictionary = view.get("item", {})
	_item_key.text = str(it.get("key", ""))
	var fx_texts: Array = []
	for f in view.get("fx", []):
		fx_texts.append(str(f.get("text", "")))
	_fx_line.text = "  ·  ".join(PackedStringArray(fx_texts))
	_item_box.queue_redraw()

	var pl: Dictionary = view.get("place", {})
	_place.visible = not pl.is_empty()
	_place.offset_top = right_top
	if _place.visible:
		_place_big.text = str(pl.get("place", ""))
		_place_of.text = str(pl.get("of", ""))
		_place_lap.text = str(pl.get("lap", ""))
		_place_lap.visible = _place_lap.text != ""
		_place_gap.text = str(pl.get("gap", ""))
		_place_gap.visible = _place_gap.text != ""

	var rows: Array = view.get("strip", [])
	_strip.visible = not rows.is_empty()
	for i in range(_rows.size()):
		var r: Array = _rows[i]
		var shown := i < rows.size()
		(r[0] as Control).visible = shown
		if shown:
			_apply_row(r, rows[i])

	var w: Dictionary = view.get("warn", {})
	_warn.visible = not w.is_empty()
	if _warn.visible:
		_warn_text.text = str(w.get("text", ""))
		_warn_badge.queue_redraw()
		_warn_arrow.queue_redraw()
	_outline.queue_redraw()

	var ln: Dictionary = view.get("lanes", {})
	_lanes.visible = not ln.is_empty()
	_hint.visible = _lanes.visible
	_hint.text = str(ln.get("hint", ""))
	_lanes.queue_redraw()


## Ligne `r` de la bande d'après `it` (gp_hud_model.gd strip_rows) : seul ce qui a changé est reposé.
func _apply_row(r: Array, it: Dictionary) -> void:
	var done: Dictionary = r[6]
	var me := bool(it.get("me", false))
	var p := str(it.get("place", ""))
	if (r[1] as Label).text != p:
		(r[1] as Label).text = p
	var n := str(it.get("name", ""))
	if (r[2] as Label).text != n:
		(r[2] as Label).text = n
	var g := str(it.get("gap", ""))
	if (r[3] as Label).text != g:
		(r[3] as Label).text = g
	if done.get("me") != me:
		var fg := PAPER if me else INK
		for k in [1, 2, 3]:
			(r[k] as Label).add_theme_color_override("font_color", fg)
		(r[5] as StyleBoxFlat).bg_color = INK if me else Color(0, 0, 0, 0)
		done["me"] = me
	var badge := r[4] as Control
	var key := {"item": str(it.get("item", "")), "hit": bool(it.get("hit", false)), "boost": bool(it.get("boost", false))}
	if badge.get_meta("row", {}) != key:
		badge.set_meta("row", key)
		badge.queue_redraw()


func _draw_row_badge(badge: Control) -> void:
	var key: Dictionary = badge.get_meta("row", {})
	var c := Vector2(badge.size.x / 2.0, badge.size.y / 2.0)
	if bool(key.get("hit", false)):
		Items.draw_hit(badge, c, BADGE_R)
	elif str(key.get("item", "")) != "":
		Items.draw_badge(badge, c, BADGE_R, str(key["item"]))
	elif bool(key.get("boost", false)):
		Items.draw_badge(badge, c, BADGE_R, "star")


func _draw_item() -> void:
	var it: Dictionary = _view.get("item", {})
	var sz := _item_box.size
	var rect := Rect2(Vector2.ZERO, sz)
	_item_box.draw_rect(Rect2(rect.position + Vector2(SHADOW, SHADOW), rect.size), INK, true)
	_item_box.draw_rect(rect, PAPER, true)
	_item_box.draw_rect(rect, INK, false, BORDER)
	_dashed_rect(_item_box, rect.grow(-9.0), INK, 2.0, 8.0)
	if it.is_empty() or bool(it.get("empty", true)):
		return
	var kind := str(it.get("kind", ""))
	Items.draw_badge(_item_box, sz / 2.0, sz.x * 0.33, kind)
	var n := int(it.get("n", 0))
	if n >= 1:
		var bc := Vector2(sz.x - 6.0, sz.y - 6.0)
		_item_box.draw_circle(bc, 17.0, PAPER)
		_item_box.draw_arc(bc, 17.0, 0.0, TAU, 24, INK, 3.0, true)
		_item_box.draw_string(_font, bc + Vector2(-17.0, 7.0), "×%d" % n, HORIZONTAL_ALIGNMENT_CENTER, 34.0, 18, INK)


func _draw_lanes() -> void:
	var ln: Dictionary = _view.get("lanes", {})
	if ln.is_empty():
		return
	var sz := _lanes.size
	_lanes.draw_rect(Rect2(Vector2.ZERO, sz), Color(INK, 0.72), true)
	var lane := int(ln.get("lane", 1))
	var auto := bool(ln.get("auto", false))
	var slot := (sz.x - 24.0) / 3.0
	for i in range(3):
		var x := 12.0 + slot * i + 6.0
		var bar := Rect2(Vector2(x, sz.y - 14.0), Vector2(slot - 12.0, 8.0))
		var chosen := i == lane
		var fill := (Color(0.78, 0.78, 0.8) if auto else Color.WHITE) if chosen else Color(1, 1, 1, 0.3)
		_lanes.draw_rect(bar, fill, true)
		if chosen:
			_lanes.draw_rect(bar, INK, false, 2.0)
			var cx := bar.position.x + bar.size.x / 2.0
			_lanes.draw_polyline(PackedVector2Array([Vector2(cx - 8.0, 13.0), Vector2(cx, 5.0), Vector2(cx + 8.0, 13.0)]),
				fill, 3.0, true)


func _draw_warn_badge() -> void:
	var w: Dictionary = _view.get("warn", {})
	if not w.is_empty():
		Items.draw_badge(_warn_badge, _warn_badge.size / 2.0, 20.0, str(w.get("kind", "")))


func _draw_warn_arrow() -> void:
	var w: Dictionary = _view.get("warn", {})
	var dir := str(w.get("arrow", ""))
	if dir == "":
		return
	var c := _warn_arrow.size / 2.0
	var s := -1.0 if dir == "up" else 1.0
	var col: Color = w.get("color", Items.HOT)
	var shaft := PackedVector2Array([c + Vector2(-6, -16 * s), c + Vector2(6, -16 * s), c + Vector2(6, 2 * s),
		c + Vector2(14, 2 * s), c + Vector2(0, 18 * s), c + Vector2(-14, 2 * s), c + Vector2(-6, 2 * s)])
	if s < 0.0:
		shaft.reverse()
	_warn_arrow.draw_colored_polygon(shaft, col)
	var closed := shaft.duplicate()
	closed.append(shaft[0])
	_warn_arrow.draw_polyline(closed, INK, 3.0, true)


func _draw_outline() -> void:
	var w: Dictionary = _view.get("warn", {})
	if w.is_empty() or not bool(w.get("outline", false)):
		return
	var sz := _outline.size
	var col: Color = w.get("color", Items.HOT)
	col.a = 0.85
	var k := OUTLINE_PX
	_outline.draw_rect(Rect2(0, 0, sz.x, k), col, true)
	_outline.draw_rect(Rect2(0, sz.y - k, sz.x, k), col, true)
	_outline.draw_rect(Rect2(0, k, k, sz.y - 2.0 * k), col, true)
	_outline.draw_rect(Rect2(sz.x - k, k, k, sz.y - 2.0 * k), col, true)
	if bool(w.get("chevrons", false)):   # danger derrière : chevrons vers le bas, au bord bas
		var x := CHEVRON_STEP / 2.0
		while x < sz.x:
			_outline.draw_polyline(PackedVector2Array([Vector2(x - 12.0, sz.y - k - 10.0), Vector2(x, sz.y - k - 2.0),
				Vector2(x + 12.0, sz.y - k - 10.0)]), INK, 3.0, true)
			x += CHEVRON_STEP


static func _dashed_rect(ci: CanvasItem, r: Rect2, col: Color, width: float, dash: float) -> void:
	var corners := [r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)]
	for i in range(4):
		ci.draw_dashed_line(corners[i], corners[(i + 1) % 4], col, width, dash)


## Pour les tests graphiques et le banc des menus : textes affichés.
func test_info() -> Dictionary:
	var names: Array = []
	for r in _rows:
		if (r[0] as Control).visible:
			names.append((r[2] as Label).text)
	var it: Dictionary = _view.get("item", {})
	return {"visible": visible, "item": str(it.get("kind", "")) if visible else "",
		"key": _item_key.text if visible else "", "place": (_place_big.text + " " + _place_of.text) if visible and _place.visible else "",
		"gap": _place_gap.text if visible and _place.visible else "", "strip": names,
		"warn": _warn_text.text if visible and _warn.visible else "",
		"outline": visible and bool(_view.get("warn", {}).get("outline", false)),
		"hint": _hint.text if visible and _hint.visible else "", "place_top": _place.offset_top,
		"strip_bottom": _strip.offset_top + _strip.get_combined_minimum_size().y}


func _canvas(draw_fn: Callable) -> Control:
	var c := Control.new()
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	c.draw.connect(draw_fn)
	return c


static func _style(fill: Color) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = fill
	s.border_color = INK
	s.set_border_width_all(BORDER)
	s.set_corner_radius_all(RADIUS)
	s.shadow_color = INK
	s.shadow_size = 1   # ombre nette décalée (style cartoon des maquettes, comme wtf_view.gd)
	s.shadow_offset = Vector2(SHADOW, SHADOW)
	s.content_margin_left = 14
	s.content_margin_right = 14
	s.content_margin_top = 8
	s.content_margin_bottom = 8
	return s


func _panel(fill: Color) -> PanelContainer:
	var p := PanelContainer.new()
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	p.add_theme_stylebox_override("panel", _style(fill))
	p.visible = false
	return p


static func _label(size: int, color: Color) -> Label:
	var l := Label.new()
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


## Texte blanc bordé d'encre, lisible sur le ciel et la route (invite de la case d'objet, aide des voies).
static func _outlined(size: int) -> Label:
	var l := _label(size, Color.WHITE)
	l.add_theme_color_override("font_outline_color", INK)
	l.add_theme_constant_override("outline_size", 6)
	return l
