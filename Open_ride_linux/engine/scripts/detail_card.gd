extends PanelContainer

## Carte de détail à droite des menus (lot « présentation des menus », étape 2) : en-tête, nom, tuiles des
## chiffres clés, graphique tracé par le code (profil d'altitude d'un parcours chargé, blocs d'un
## entraînement colorés par zone), lignes de texte. Affiche une fiche de menu_flow.card() :
## {title, name, tiles [{label, value, unit}], lines, profile (HudViewModel.profile), blocks ([durée,
## début, fin])} ; les clés absentes ne montrent rien. `body` reçoit d'autres contenus (bilan, menu_view).
## Couleurs et tailles du thème commun (ui_theme.gd). Pas de class_name : charger par
## preload("res://scripts/detail_card.gd").

const UiTheme := preload("res://scripts/ui_theme.gd")
const ErgView := preload("res://scripts/erg_view.gd")

## Tuiles affichées au plus (la carte garde sa largeur).
const MAX_TILES := 3
## Hauteur des blocs : la plus forte cible remplit le graphique, au moins 120 % de FTP.
const BLOCKS_MIN_TOP := 1.2

var body: VBoxContainer
var title_label: Label
var name_label: Label
var tiles_box: HBoxContainer
var chart: Control
var lines_label: Label
var _tiles: Array[PanelContainer] = []
var _sheet: Dictionary = {}


func _init() -> void:
	add_theme_stylebox_override("panel", UiTheme.card_style())
	custom_minimum_size.x = UiTheme.CARD_W
	size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	clip_contents = true
	mouse_filter = Control.MOUSE_FILTER_PASS
	body = VBoxContainer.new()
	body.add_theme_constant_override("separation", 8)
	add_child(body)
	title_label = UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.DIM)
	body.add_child(title_label)
	name_label = UiTheme.label(UiTheme.ITEM_SIZE)
	name_label.clip_text = true
	name_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	body.add_child(name_label)
	tiles_box = HBoxContainer.new()
	tiles_box.add_theme_constant_override("separation", 10)
	body.add_child(tiles_box)
	for i in range(MAX_TILES):
		var t := _tile()
		tiles_box.add_child(t)
		_tiles.append(t)
	chart = Control.new()
	chart.custom_minimum_size.y = UiTheme.CHART_H
	chart.mouse_filter = Control.MOUSE_FILTER_IGNORE
	chart.draw.connect(_draw_chart)
	body.add_child(chart)
	# Lignes en taille de pastille : la carte tient à côté des pastilles des appareils (écran Prêt).
	lines_label = UiTheme.label(UiTheme.CHIP_SIZE)
	lines_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.add_child(lines_label)


## Texte de la carte en une ligne, « | » entre les parties (tests graphiques).
func text() -> String:
	var parts: Array[String] = []
	for l in [title_label, name_label]:
		if l.visible:
			parts.append(l.text)
	for t in _tiles:
		if t.visible:
			parts.append(_tile_text(t))
	if lines_label.visible:
		parts.append(lines_label.text.replace("\n", " | "))
	return " | ".join(parts)


## Graphique affiché : "profile", "blocks" ou "" (tests).
func chart_kind() -> String:
	if not chart.visible:
		return ""
	return "profile" if _has_profile() else "blocks"


func update_display(sheet: Dictionary) -> void:
	_sheet = sheet
	title_label.text = str(sheet.get("title", ""))
	title_label.visible = title_label.text != ""
	name_label.text = str(sheet.get("name", ""))
	name_label.visible = name_label.text != ""
	var tiles: Array = sheet.get("tiles", [])
	for i in range(_tiles.size()):
		_tiles[i].visible = i < tiles.size()
		if _tiles[i].visible:
			_set_tile(_tiles[i], tiles[i])
	tiles_box.visible = not tiles.is_empty()
	var lines: Array = sheet.get("lines", [])
	lines_label.text = "\n".join(PackedStringArray(lines.map(func(l): return str(l))))
	lines_label.visible = not lines.is_empty()
	chart.visible = _has_profile() or not sheet.get("blocks", []).is_empty()
	chart.queue_redraw()


func _has_profile() -> bool:
	var p = _sheet.get("profile", null)
	return p is Dictionary and p.get("points", PackedVector2Array()).size() >= 2


func _tile() -> PanelContainer:
	var t := PanelContainer.new()
	t.add_theme_stylebox_override("panel", UiTheme.tile_style())
	t.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	t.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 0)
	t.add_child(box)
	box.add_child(UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.DIM))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	box.add_child(row)
	var v := UiTheme.label(UiTheme.VALUE_SIZE)
	row.add_child(v)
	var u := UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.DIM)
	u.size_flags_vertical = Control.SIZE_SHRINK_END
	row.add_child(u)
	return t


func _set_tile(t: PanelContainer, tile: Dictionary) -> void:
	var box: VBoxContainer = t.get_child(0)
	var row: HBoxContainer = box.get_child(1)
	(box.get_child(0) as Label).text = str(tile.get("label", ""))
	(row.get_child(0) as Label).text = str(tile.get("value", ""))
	(row.get_child(1) as Label).text = str(tile.get("unit", ""))


## « Distance 10,0 km ».
func _tile_text(t: PanelContainer) -> String:
	var box: VBoxContainer = t.get_child(0)
	var row: HBoxContainer = box.get_child(1)
	var unit := (row.get_child(1) as Label).text
	return "%s %s%s" % [(box.get_child(0) as Label).text, (row.get_child(0) as Label).text, (" " + unit) if unit != "" else ""]


func _draw_chart() -> void:
	var w := chart.size.x
	var h := chart.size.y
	chart.draw_line(Vector2(0, h - 1), Vector2(w, h - 1), UiTheme.LINE, 1.0)
	if _has_profile():
		_draw_profile(w, h)
	else:
		_draw_blocks(w, h)


## Altitude sur toute la longueur : aire teintée et trait de la couleur de sélection.
func _draw_profile(w: float, h: float) -> void:
	var p: Dictionary = _sheet["profile"]
	var pts: PackedVector2Array = p["points"]
	var x0 := pts[0].x
	var span := maxf(pts[pts.size() - 1].x - x0, 1.0)
	var lo := float(p.get("alt_min", 0.0))
	var rng := maxf(float(p.get("alt_max", 0.0)) - lo, 1.0)
	var line := PackedVector2Array()
	for q in pts:
		line.append(Vector2((q.x - x0) / span * w, h - 4.0 - (q.y - lo) / rng * (h - 8.0)))
	var area := line.duplicate()
	area.append(Vector2(w, h))
	area.append(Vector2(0, h))
	chart.draw_colored_polygon(area, Color(UiTheme.FOCUS, 0.16))
	chart.draw_polyline(line, UiTheme.FOCUS, 2.5, true)


## Blocs à leur durée et à leur cible (début et fin, rampes comprises), couleur de la zone de Coggan.
func _draw_blocks(w: float, h: float) -> void:
	var blocks: Array = _sheet.get("blocks", [])
	var total := 0.0
	var top := BLOCKS_MIN_TOP
	for b in blocks:
		total += float(b[0])
		for f in [b[1], b[2]]:
			if f != null:
				top = maxf(top, float(f))
	if total <= 0.0:
		return
	var x := 0.0
	for b in blocks:
		var bw := float(b[0]) / total * w
		var a := 0.5 if b[1] == null else float(b[1])
		var e := 0.5 if b[2] == null else float(b[2])
		var col := ErgView.zone_color(null if b[1] == null else (a + e) / 2.0)
		if bw >= 1.0 and maxf(a, e) > 0.0:   # polygone dégénéré : rien à tracer
			chart.draw_colored_polygon(PackedVector2Array([Vector2(x, h), Vector2(x, h - a / top * h),
				Vector2(x + bw - 1.0, h - e / top * h), Vector2(x + bw - 1.0, h)]), Color(col, 0.9))
		x += bw
