extends Panel

## Mini-carte du monde ouvert (lot W24) : dessine ce que `minimap_model.gd` décrit, en bas à gauche du HUD.
## Enfant du HUD ; ne reçoit pas la souris. Redessinée au plus toutes les `redraw_ms` (réglage de qualité).
## Pas de class_name (charger par preload).

const UiTheme := preload("res://scripts/ui_theme.gd")
const Model := preload("res://scripts/minimap_model.gd")

const WIDTH := 243.0          # largeur de la colonne gauche du HUD (hud_view.gd, COLUMN_W)
const MAP_H := 170.0          # hauteur de la carte quand la place le permet
const MAP_MIN_H := 96.0       # en dessous, la carte se cache plutôt que d'écraser la colonne gauche
const HEADER_H := 22.0
const LINE_H := 18.0
const PAD := 6.0
const FONT_SIZE := 13
const CAPTION_SIZE := 12

const AHEAD_COLOR := UiTheme.TEXT
const BEHIND_COLOR := UiTheme.DIM
const PREVIEW_COLOR := Color(UiTheme.DIM, 0.8)
const RIDER_COLOR := UiTheme.FOCUS
const GOAL_COLOR := UiTheme.GOLD
const JUNCTION_COLOR := UiTheme.GOLD
const SHADE := UiTheme.OUTLINE
const MAP_BG := UiTheme.CHART_BG

var map: Control
var header: Control
var lines_label: Label
var view := {"visible": false}
var redraw_ms := 100
var _last_draw_ms := -100000


func _init() -> void:
	name = "Minimap"
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := StyleBoxFlat.new()
	style.bg_color = UiTheme.PANEL_BG
	for corner in ["top_left", "top_right", "bottom_left", "bottom_right"]:
		style.set("corner_radius_" + corner, 8)
	add_theme_stylebox_override("panel", style)
	visible = false
	header = Control.new()
	header.mouse_filter = Control.MOUSE_FILTER_IGNORE
	header.draw.connect(_draw_header)
	add_child(header)
	map = Control.new()
	map.mouse_filter = Control.MOUSE_FILTER_IGNORE
	map.clip_contents = true
	map.draw.connect(_draw_map)
	add_child(map)
	lines_label = Label.new()
	lines_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	lines_label.add_theme_font_size_override("font_size", FONT_SIZE)
	lines_label.add_theme_color_override("font_color", UiTheme.TEXT)
	lines_label.add_theme_color_override("font_outline_color", SHADE)
	lines_label.add_theme_constant_override("outline_size", 3)
	lines_label.clip_text = true
	add_child(lines_label)


## Place la carte : bord gauche du HUD (`left_x`), bas à `bottom`, jamais au-dessus de `top_limit` (bas de la
## colonne gauche : vent, abri). Renvoie faux quand la place manque (carte cachée).
func place(left_x: float, top_limit: float, bottom: float, line_count: int) -> bool:
	var lines_h := LINE_H * float(line_count)
	var fixed := HEADER_H + lines_h + 2.0 * PAD
	var map_h := minf(MAP_H, bottom - top_limit - fixed)
	if map_h < MAP_MIN_H:
		return false
	var h := map_h + fixed
	position = Vector2(left_x, bottom - h)
	size = Vector2(WIDTH, h)
	header.position = Vector2(PAD, PAD)
	header.size = Vector2(WIDTH - 2.0 * PAD, HEADER_H)
	map.position = Vector2(PAD, PAD + HEADER_H)
	map.size = Vector2(WIDTH - 2.0 * PAD, map_h)
	lines_label.position = Vector2(PAD, PAD + HEADER_H + map_h)
	lines_label.size = Vector2(WIDTH - 2.0 * PAD, lines_h)
	lines_label.visible = line_count > 0
	return true


## Nouvelle vue (minimap_model.build) ; `force` redessine même avant `redraw_ms` (changement de place).
func show_view(v: Dictionary, force: bool = false) -> void:
	var now := Time.get_ticks_msec()
	if not force and now - _last_draw_ms < redraw_ms:
		return
	_last_draw_ms = now
	view = v
	lines_label.text = "\n".join(PackedStringArray(v.get("lines", [])))
	header.queue_redraw()
	map.queue_redraw()


## Texte de la carte pour les tests et les captures (widget « minimap » de main.gd).
func describe() -> String:
	var parts := ["Carte", str(view.get("scale", {}).get("text", ""))]
	parts.append_array(view.get("lines", []))
	return " · ".join(PackedStringArray(parts))


# --- dessin ------------------------------------------------------------------------------

func _font() -> Font:
	return get_theme_default_font()


func _draw_header() -> void:
	var font := _font()
	var w := header.size.x
	var base := HEADER_H * 0.5 + CAPTION_SIZE * 0.35
	header.draw_string(font, Vector2(0.0, base), "CARTE", HORIZONTAL_ALIGNMENT_LEFT, -1, CAPTION_SIZE, UiTheme.HUD_DIM)
	var sc: Dictionary = view.get("scale", {})
	if sc.is_empty():
		return
	# Barre d'échelle à droite, son texte devant elle : « 200 m |——| ».
	var half := map.size.x * 0.5
	var bar_px := float(sc["frac"]) * half
	var x1 := w
	var x0 := x1 - bar_px
	var y := HEADER_H * 0.5
	for c in [[SHADE, 4.0], [UiTheme.TEXT, 2.0]]:
		header.draw_line(Vector2(x0, y), Vector2(x1, y), c[0], c[1])
		header.draw_line(Vector2(x0, y - 4.0), Vector2(x0, y + 4.0), c[0], c[1])
		header.draw_line(Vector2(x1, y - 4.0), Vector2(x1, y + 4.0), c[0], c[1])
	header.draw_string(font, Vector2(x0 - 80.0 - 6.0, base), str(sc["text"]), HORIZONTAL_ALIGNMENT_RIGHT, 80.0,
		CAPTION_SIZE, UiTheme.TEXT)


func _to_px(p: Vector2) -> Vector2:
	var half := map.size * 0.5
	return half + Vector2(p.x * half.x, p.y * half.x)   # même échelle sur les deux axes (unité = demi-largeur)


func _draw_map() -> void:
	map.draw_rect(Rect2(Vector2.ZERO, map.size), MAP_BG)
	if not view.get("visible", false):
		return
	for pv in view.get("previews", []):
		_polyline(pv, PREVIEW_COLOR, 2.0)
	_dashed(view.get("behind", PackedVector2Array()), BEHIND_COLOR, 2.0, 6.0, 5.0)
	var ahead: PackedVector2Array = view.get("ahead", PackedVector2Array())
	_polyline(ahead, SHADE, 6.0)
	_polyline(ahead, AHEAD_COLOR, 3.5)
	var j: Dictionary = view.get("junction", {})
	if not j.is_empty():
		var c := _to_px(j["pos"])
		map.draw_arc(c, 7.0, 0.0, TAU, 20, SHADE, 4.0)
		map.draw_arc(c, 7.0, 0.0, TAU, 20, JUNCTION_COLOR, 2.0)
	_draw_goal(view.get("goal", {}))
	_draw_north(view.get("north", Vector2(0.0, -1.0)))
	_draw_rider(_to_px(view.get("rider", Model.RIDER)))


func _polyline(pts: PackedVector2Array, color: Color, width: float) -> void:
	if pts.size() < 2:
		return
	var px := PackedVector2Array()
	px.resize(pts.size())
	for i in pts.size():
		px[i] = _to_px(pts[i])
	map.draw_polyline(px, color, width, true)


## Pointillés le long de la ligne, réguliers d'un bout à l'autre (les points de la route sont à 10 m, moins
## d'un tiret : draw_dashed_line par segment ne donnerait qu'un trait plein).
func _dashed(pts: PackedVector2Array, color: Color, width: float, dash: float, gap: float) -> void:
	if pts.size() < 2:
		return
	var period := dash + gap
	var phase := 0.0
	var prev := _to_px(pts[0])
	for i in range(1, pts.size()):
		var cur := _to_px(pts[i])
		var seg := cur - prev
		var length := seg.length()
		var t := 0.0
		while t < length:
			var in_dash := phase < dash
			var left := (dash - phase) if in_dash else (period - phase)
			var step := minf(left, length - t)
			if in_dash:
				var a := prev + seg * (t / length)
				var b := prev + seg * ((t + step) / length)
				map.draw_line(a, b, SHADE, width + 2.0)
				map.draw_line(a, b, color, width)
			t += step
			phase = fmod(phase + step, period)
		prev = cur


func _draw_rider(c: Vector2) -> void:
	var tip := c + Vector2(0.0, -10.0)
	var tri := PackedVector2Array([tip, c + Vector2(7.0, 7.0), c + Vector2(0.0, 3.0), c + Vector2(-7.0, 7.0)])
	map.draw_colored_polygon(tri, RIDER_COLOR)
	tri.append(tip)
	map.draw_polyline(tri, SHADE, 1.5, true)


func _draw_north(dir: Vector2) -> void:
	var center := map.size * 0.5
	var r := minf(center.x, center.y) - 11.0
	var c := center + dir.normalized() * r
	map.draw_circle(c, 9.0, Color(SHADE, 0.6))
	var font := _font()
	map.draw_string(font, c + Vector2(-6.0, 5.0), "N", HORIZONTAL_ALIGNMENT_CENTER, 12.0, FONT_SIZE, UiTheme.TEXT)


func _draw_goal(g: Dictionary) -> void:
	if g.is_empty():
		return
	var c := _to_px(g["pos"])
	var d := 6.0
	var diamond := PackedVector2Array([c + Vector2(0, -d), c + Vector2(d, 0), c + Vector2(0, d), c + Vector2(-d, 0)])
	map.draw_colored_polygon(diamond, GOAL_COLOR)
	diamond.append(c + Vector2(0, -d))
	map.draw_polyline(diamond, SHADE, 1.5, true)
	# Libellé à côté du losange, du côté où il reste dans la carte.
	var font := _font()
	var label := str(g["label"])
	var tw := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, CAPTION_SIZE).x
	var x := c.x + 9.0 if c.x + 9.0 + tw < map.size.x - 2.0 else c.x - 9.0 - tw
	var y := clampf(c.y + 4.0, CAPTION_SIZE, map.size.y - 3.0)
	map.draw_string_outline(font, Vector2(x, y), label, HORIZONTAL_ALIGNMENT_LEFT, -1, CAPTION_SIZE, 3, SHADE)
	map.draw_string(font, Vector2(x, y), label, HORIZONTAL_ALIGNMENT_LEFT, -1, CAPTION_SIZE, GOAL_COLOR)
