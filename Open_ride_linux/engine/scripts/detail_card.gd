extends PanelContainer

## Carte de détail à droite des menus (lot « présentation des menus », étape 2) : en-tête, nom, tuiles des
## chiffres clés, graphique tracé par le code (profil d'altitude d'un parcours chargé, blocs d'un
## entraînement colorés par zone), lignes de texte. Affiche une fiche de menu_flow.card() :
## {title, name, tiles [{label, value, unit, gold}] (gold : valeur en or), lines, profile (HudViewModel.profile), blocks ([durée,
## début, fin]), curve (courbe de puissance de « Ma puissance », power_view_model.gd, lot PP3), fitness (courbe de forme,
## {ctl, atl, weeks, days}, lot FO1)} ; les clés absentes ne
## montrent rien. `body` reçoit d'autres contenus (bilan, menu_view).
## Couleurs et tailles du thème commun (ui_theme.gd). Pas de class_name : charger par
## preload("res://scripts/detail_card.gd").

const UiTheme := preload("res://scripts/ui_theme.gd")
const ErgView := preload("res://scripts/erg_view.gd")

## Tuiles affichées au plus (la carte garde sa largeur).
const MAX_TILES := 3
## Hauteur des blocs : la plus forte cible remplit le graphique, au moins 120 % de FTP.
const BLOCKS_MIN_TOP := 1.2
## Courbe de puissance (lot PP3) : hauteur, marge des watts à gauche, marge des durées en bas, échelle 5 s à 60 min.
const CURVE_H := 150.0
const CURVE_LEFT := 52.0
const CURVE_BOTTOM := 20.0
const CURVE_MIN_S := 5.0
const CURVE_MAX_S := 3600.0

var body: VBoxContainer
var title_label: Label
var name_label: Label
var tiles_box: HBoxContainer
var chart: Control
var lines_label: Label
var _tiles: Array[PanelContainer] = []
var _sheet: Dictionary = {}
var _shown_once := false


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


## Graphique affiché : "profile", "blocks", "curve" ou "" (tests).
func chart_kind() -> String:
	if not chart.visible:
		return ""
	if _has_curve():
		return "curve"
	if _has_fitness():
		return "fitness"
	return "profile" if _has_profile() else "blocks"


func update_display(sheet: Dictionary) -> void:
	if sheet == _sheet and _shown_once:   # même fiche : rien à reposer ni à redessiner
		return
	_shown_once = true
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
	chart.visible = _has_profile() or not sheet.get("blocks", []).is_empty() or _has_curve() or _has_fitness()
	chart.custom_minimum_size.y = CURVE_H if (_has_curve() or _has_fitness()) else UiTheme.CHART_H
	chart.queue_redraw()


func _has_curve() -> bool:
	var c = _sheet.get("curve", null)
	return c is Dictionary and c.get("m6", []) is Array and not c.get("m6", []).is_empty()


func _has_fitness() -> bool:
	var f = _sheet.get("fitness", null)
	return f is Dictionary and f.get("ctl", []) is Array and f.get("ctl", []).size() >= 2


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
	# Valeur clé (record) en or ; sinon couleur du texte.
	(row.get_child(0) as Label).add_theme_color_override("font_color", UiTheme.GOLD if tile.get("gold", false) else UiTheme.TEXT)
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
	if _has_curve():
		_draw_curve(w, h)
	elif _has_fitness():
		_draw_fitness(w, h)
	elif _has_profile():
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


## Abscisse d'une durée sur l'échelle logarithmique de 5 s à 60 min, marges des libellés comprises.
static func curve_x(seconds: float, w: float) -> float:
	var t := (log(maxf(seconds, CURVE_MIN_S)) - log(CURVE_MIN_S)) / (log(CURVE_MAX_S) - log(CURVE_MIN_S))
	return CURVE_LEFT + clampf(t, 0.0, 1.0) * (w - CURVE_LEFT - 8.0)


## Courbe de puissance (lot PP3) : points pleins reliés pour la période principale, points creux pour l'autre,
## FTP réglée en tirets ; graduations en watts à gauche, durées en bas. Les mots de la légende sont dans les
## lignes de la carte : la forme des points (plein, creux) et les libellés portent l'information, pas la couleur.
func _draw_curve(w: float, h: float) -> void:
	var c: Dictionary = _sheet["curve"]
	var font := ThemeDB.fallback_font
	var top := 0.0
	for key in ["m6", "w6"]:
		for p in c.get(key, []):
			if p[1] != null:
				top = maxf(top, float(p[1]))
	top = maxf(top, float(c.get("ftp_w", 0))) * 1.1
	if top <= 0.0:
		return
	var plot_h := h - CURVE_BOTTOM
	var y_of := func(watts: float) -> float: return plot_h - watts / top * (plot_h - 6.0)
	for gw in _grid_watts(top):
		var gy: float = y_of.call(float(gw))
		chart.draw_line(Vector2(CURVE_LEFT, gy), Vector2(w, gy), Color(UiTheme.LINE, 0.8), 1.0)
		chart.draw_string(font, Vector2(0, gy + 5), "%d W" % gw, HORIZONTAL_ALIGNMENT_LEFT, CURVE_LEFT - 4, 13, UiTheme.DIM)
	for tick in [[5, "5 s"], [60, "1 min"], [300, "5 min"], [1200, "20 min"], [3600, "60 min"]]:
		var tx := curve_x(float(tick[0]), w)
		chart.draw_line(Vector2(tx, plot_h), Vector2(tx, plot_h + 4), UiTheme.DIM, 1.0)
		chart.draw_string(font, Vector2(tx - 22, h - 4), tick[1], HORIZONTAL_ALIGNMENT_CENTER, 44, 13, UiTheme.DIM)
	var ftp := float(c.get("ftp_w", 0))
	if ftp > 0.0:
		var fy: float = y_of.call(ftp)
		chart.draw_dashed_line(Vector2(CURVE_LEFT, fy), Vector2(w, fy), UiTheme.GOLD, 1.5, 6.0)
	var main_key: String = str(c.get("focus", "m6"))
	var other_key: String = "w6" if main_key == "m6" else "m6"
	for key in [other_key, main_key]:
		var strong: bool = key == main_key
		var line := PackedVector2Array()
		for p in c.get(key, []):
			if p[1] == null:
				if line.size() >= 2 and strong:
					chart.draw_polyline(line, UiTheme.FOCUS, 2.5, true)
				line = PackedVector2Array()
				continue
			var pt := Vector2(curve_x(float(p[0]), w), y_of.call(float(p[1])))
			line.append(pt)
			if strong:
				chart.draw_circle(pt, 4.0, UiTheme.FOCUS)
			else:
				chart.draw_arc(pt, 4.5, 0.0, TAU, 16, UiTheme.TEXT, 1.5, true)
		if line.size() >= 2 and strong:
			chart.draw_polyline(line, UiTheme.FOCUS, 2.5, true)


## Courbe de forme (lot FO1) : condition en trait plein, fatigue en pointillé, chacune nommée en bout de trait ;
## sous l'axe, le nombre de séances de chaque semaine (« 0 » marque une semaine sans séance). Points de charge,
## graduations sans unité ; le mot et la forme du trait portent l'information, pas la couleur.
func _draw_fitness(w: float, h: float) -> void:
	var f: Dictionary = _sheet["fitness"]
	var font := ThemeDB.fallback_font
	var ctl: Array = f.get("ctl", [])
	var atl: Array = f.get("atl", [])
	var top := 10.0
	for v in ctl + atl:
		top = maxf(top, float(v))
	top *= 1.15
	var plot_h := h - CURVE_BOTTOM
	var right := w - 70.0   # place des noms en bout de trait
	var left := 34.0
	var y_of := func(v: float) -> float: return plot_h - v / top * (plot_h - 6.0)
	var step := 10 if top <= 60.0 else (20 if top <= 120.0 else 50)
	var g := step
	while g < top:
		var gy: float = y_of.call(float(g))
		chart.draw_line(Vector2(left, gy), Vector2(right, gy), Color(UiTheme.LINE, 0.8), 1.0)
		chart.draw_string(font, Vector2(0, gy + 5), str(g), HORIZONTAL_ALIGNMENT_LEFT, left - 4, 13, UiTheme.DIM)
		g += step
	var weeks: Array = f.get("weeks", [])
	for i in range(weeks.size()):
		var cx := left + (i + 0.5) / float(weeks.size()) * (right - left)
		chart.draw_string(font, Vector2(cx - 10, h - 4), str(int(weeks[i])), HORIZONTAL_ALIGNMENT_CENTER, 20, 13,
			UiTheme.TEXT if int(weeks[i]) == 0 else UiTheme.DIM)
	var lines := {"Condition": ctl, "Fatigue": atl}
	var ends: Array = []
	for key in lines:
		var arr: Array = lines[key]
		if arr.size() < 2:
			continue
		var pts := PackedVector2Array()
		for i in range(arr.size()):
			pts.append(Vector2(left + i / float(arr.size() - 1) * (right - left), y_of.call(float(arr[i]))))
		if key == "Condition":
			chart.draw_polyline(pts, UiTheme.FOCUS, 2.5, true)
		else:
			for i in range(pts.size() - 1):
				chart.draw_dashed_line(pts[i], pts[i + 1], UiTheme.TEXT, 1.5, 5.0)
		ends.append([key, pts[pts.size() - 1].y])
	if ends.size() == 2 and absf(ends[0][1] - ends[1][1]) < 14.0:   # noms qui se chevauchent : on les écarte
		var mid: float = (float(ends[0][1]) + float(ends[1][1])) / 2.0
		var up: int = 0 if float(ends[0][1]) <= float(ends[1][1]) else 1
		ends[up][1] = mid - 7.0
		ends[1 - up][1] = mid + 7.0
	for e in ends:
		chart.draw_string(font, Vector2(right + 4, clampf(e[1], 10.0, plot_h) + 5), e[0], HORIZONTAL_ALIGNMENT_LEFT,
			w - right - 4, 13, UiTheme.TEXT)


## Graduations rondes (100, 200 ou 250 W d'écart) sous le haut du graphique.
static func _grid_watts(top: float) -> Array:
	var step := 100 if top <= 700.0 else 250
	var out: Array = []
	var v := step
	while v < top:
		out.append(v)
		v += step
	return out


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
