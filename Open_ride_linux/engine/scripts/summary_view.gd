extends VBoxContainer

## Bilan de fin de séance dans les menus (lot N6), présenté en tuiles (lot N20, présentation des menus
## étape 4) : bandeau du résultat du test de FTP, six tuiles de chiffres au plus (une tuile sans donnée est
## retirée), graphique de la puissance de la séance (`summary.power_profile`, trait blanc des courbes d'O14
## réduit, profil cible coloré par zone en ERG, ligne de la FTP), records battus en `GOLD` avec l'ancien
## temps, ligne des autres chiffres (IF, TSS, puissance max, abri), lignes propres au mode (Cyber-Rogue,
## WTF, Dernier survivant), fichier FIT et, sur demande (« Voir le bilan détaillé »), les blocs ERG avec leur
## couleur ; bloc « Progression » (lot V9). Ne calcule rien : lit summary_view_model.gd (lot N4). Dans la
## carte de détail du menu, élargie à UiTheme.SUMMARY_CARD_W ; `fit` réduit les polices tant que le bilan
## (détaillé compris) ne tient pas au-dessus du bandeau des boutons ; couleurs du thème commun
## (ui_theme.gd). Pas de class_name : charger par preload("res://scripts/summary_view.gd").

const SummaryViewModel := preload("res://scripts/summary_view_model.gd")
const UiTheme := preload("res://scripts/ui_theme.gd")
const ErgView := preload("res://scripts/erg_view.gd")
const WorkoutChartView := preload("res://scripts/workout_chart_view.gd")

const FONT_SIZE := UiTheme.CARD_SIZE
const BLOCK_FONT_SIZE := 20
const BLOCK_COLORS := {
	SummaryViewModel.COLOR_GREEN: UiTheme.OK,
	SummaryViewModel.COLOR_ORANGE: UiTheme.WARN,
	SummaryViewModel.COLOR_RED: UiTheme.DANGER,
	SummaryViewModel.COLOR_NEUTRAL: UiTheme.DIM,
}
const MAX_BLOCK_LINES := 4
## Tuiles sur trois colonnes ; lignes du mode et de la progression sur deux colonnes, remplies ligne par ligne.
const TILE_COLUMNS := 3
const COLUMNS := 2
const COLUMN_GAP := 24
const TILE_GAP := 8
## Plus petite police des lignes du bilan quand `fit` le compacte (celle des autres lignes suit, 2 de moins).
const MIN_FONT_SIZE := 16
const COMPACT_LEVELS := 3
const TILE_MARGIN_COMPACT := 2
## Chiffre d'une tuile : 6 points de plus que les lignes (28 à la taille normale, comme la carte de détail).
const TILE_VALUE_EXTRA := UiTheme.VALUE_SIZE - FONT_SIZE
## Écarts entre les lignes ; `fit` passe aux écarts serrés et au graphique bas quand la plus petite police ne
## suffit pas (bilan détaillé avec abri, blocs ERG et progression en 720p, lot AS5).
const ROW_SEP := 6
const ROW_SEP_TIGHT := 1
const BOX_SEP := 8
const PROGRESS_SEP := 3
const BOX_SEP_TIGHT := 2
const CHART_H := UiTheme.CHART_H
const CHART_H_TIGHT := 48
## Graphique : trait de la puissance et son contour (réduits de workout_chart_view.gd), cible atténuée.
const POWER_WIDTH := 2.5
const POWER_OUTLINE := 1.5
const TARGET_ALPHA := 0.55
## Bloc « Progression » (lot V9) : durée de l'animation de la barre d'expérience, hauteur de la barre.
const BAR_ANIM_S := 1.2
const BAR_H := 12

var model = SummaryViewModel.new()
var ftp_band: PanelContainer
var ftp_title: Label
var ftp_value: Label
var ftp_before: Label
var ftp_delta: Label
var ftp_note: Label
var tiles_grid: GridContainer
var _tiles: Array[PanelContainer] = []
var chart_box: VBoxContainer
var chart_label: Label
var chart_max: Label
var chart: Control
var records_box: VBoxContainer
var records_more: Label
var more_label: Label
var lines_grid: GridContainer
var fit_label: Label
var blocks_box: GridContainer
var progress_box: VBoxContainer
var progress_grid: GridContainer
var bar_label: Label
var bar: Control
var extras_label: Label
## Animation de la barre d'expérience (coupée par main.gd en qualité basse).
var animate := true
var _chart: Dictionary = {}
var _tile_style: StyleBoxFlat
var _tile_style_compact: StyleBoxFlat
var _ftp_w := 0.0
var _bar_from := 0.0
var _bar_to := 0.0
var _bar_pos := 0.0
var _bar_t := 1.0
var _bar_key := ""


func _init() -> void:
	_tile_style = UiTheme.tile_style()
	_tile_style_compact = UiTheme.tile_style()
	_tile_style_compact.content_margin_top = TILE_MARGIN_COMPACT
	_tile_style_compact.content_margin_bottom = TILE_MARGIN_COMPACT
	add_theme_constant_override("separation", BOX_SEP)
	_build_ftp_band()
	tiles_grid = GridContainer.new()
	tiles_grid.columns = TILE_COLUMNS
	tiles_grid.add_theme_constant_override("h_separation", TILE_GAP)
	tiles_grid.add_theme_constant_override("v_separation", TILE_GAP)
	add_child(tiles_grid)
	for i in range(SummaryViewModel.MAX_TILES):
		var t := _tile()
		tiles_grid.add_child(t)
		_tiles.append(t)
	_build_chart()
	records_box = VBoxContainer.new()
	records_box.add_theme_constant_override("separation", 0)
	add_child(records_box)
	records_box.add_child(UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.DIM, "Records battus"))
	for i in range(SummaryViewModel.MAX_RECORD_LINES):
		records_box.add_child(_record_row())
	records_more = UiTheme.label(BLOCK_FONT_SIZE, UiTheme.DIM)
	records_box.add_child(records_more)
	more_label = UiTheme.label(BLOCK_FONT_SIZE, UiTheme.DIM)
	more_label.clip_text = true
	more_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	add_child(more_label)
	lines_grid = _grid(ROW_SEP)
	add_child(lines_grid)
	fit_label = UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.DIM)
	fit_label.clip_text = true
	add_child(fit_label)
	blocks_box = GridContainer.new()
	blocks_box.columns = 1
	blocks_box.add_theme_constant_override("h_separation", COLUMN_GAP)
	blocks_box.add_theme_constant_override("v_separation", 0)
	add_child(blocks_box)
	progress_box = VBoxContainer.new()
	progress_box.add_theme_constant_override("separation", PROGRESS_SEP)
	progress_box.visible = false
	add_child(progress_box)
	progress_box.add_child(UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.DIM, "Progression"))
	progress_grid = _grid(PROGRESS_SEP)
	progress_box.add_child(progress_grid)
	bar_label = UiTheme.label(BLOCK_FONT_SIZE, UiTheme.DIM)
	bar_label.clip_text = true
	progress_box.add_child(bar_label)
	bar = Control.new()
	bar.custom_minimum_size.y = BAR_H
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	bar.draw.connect(_draw_bar)
	progress_box.add_child(bar)
	extras_label = UiTheme.label(BLOCK_FONT_SIZE, UiTheme.OK)
	extras_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	progress_box.add_child(extras_label)
	set_process(false)


## Bandeau du test de FTP : « Résultat du test de FTP », nouvelle FTP en `GOLD`, ancienne FTP en `DIM`, écart
## et fiabilité à droite.
func _build_ftp_band() -> void:
	ftp_band = PanelContainer.new()
	ftp_band.add_theme_stylebox_override("panel", UiTheme.band_style())
	ftp_band.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ftp_band.visible = false
	add_child(ftp_band)
	var row := HBoxContainer.new()
	ftp_band.add_child(row)
	var left := VBoxContainer.new()
	left.add_theme_constant_override("separation", 0)
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(left)
	ftp_title = UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.DIM, "Résultat du test de FTP")
	left.add_child(ftp_title)
	var value_row := HBoxContainer.new()
	value_row.add_theme_constant_override("separation", 10)
	left.add_child(value_row)
	ftp_value = UiTheme.label(UiTheme.VALUE_SIZE, UiTheme.GOLD)   # nouvelle FTP en or, ancienne en DIM (N19 §4.4)
	value_row.add_child(ftp_value)
	ftp_before = UiTheme.label(BLOCK_FONT_SIZE, UiTheme.DIM)
	ftp_before.size_flags_vertical = Control.SIZE_SHRINK_END
	value_row.add_child(ftp_before)
	var right := VBoxContainer.new()
	right.add_theme_constant_override("separation", 0)
	right.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_child(right)
	ftp_delta = UiTheme.label(BLOCK_FONT_SIZE, UiTheme.OK)
	ftp_delta.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	right.add_child(ftp_delta)
	ftp_note = UiTheme.label(BLOCK_FONT_SIZE, UiTheme.DIM)
	ftp_note.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	right.add_child(ftp_note)


func _build_chart() -> void:
	chart_box = VBoxContainer.new()
	chart_box.add_theme_constant_override("separation", 2)
	add_child(chart_box)
	var head := HBoxContainer.new()
	chart_box.add_child(head)
	chart_label = UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.DIM)
	chart_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(chart_label)
	chart_max = UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.DIM)
	head.add_child(chart_max)
	chart = Control.new()
	chart.custom_minimum_size.y = CHART_H
	chart.mouse_filter = Control.MOUSE_FILTER_IGNORE
	chart.draw.connect(_draw_chart)
	chart_box.add_child(chart)


## Tuile d'un chiffre (même forme que celles de detail_card.gd) : libellé, chiffre, unité, complément (NP).
func _tile() -> PanelContainer:
	var t := PanelContainer.new()
	t.add_theme_stylebox_override("panel", _tile_style)
	t.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	t.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 0)
	t.add_child(box)
	box.add_child(UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.DIM))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	box.add_child(row)
	row.add_child(UiTheme.label(UiTheme.VALUE_SIZE))
	for i in range(2):   # unité, complément
		var l := UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.DIM)
		l.size_flags_vertical = Control.SIZE_SHRINK_END
		row.add_child(l)
	return t


## Ligne d'un record battu : « ★ nom » à gauche, temps en `GOLD` puis ancien temps en `DIM` à droite.
func _record_row() -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	var name_l := UiTheme.label(FONT_SIZE, UiTheme.GOLD)
	name_l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	name_l.clip_text = true
	name_l.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	row.add_child(name_l)
	row.add_child(UiTheme.label(FONT_SIZE, UiTheme.GOLD))
	var before := UiTheme.label(BLOCK_FONT_SIZE, UiTheme.DIM)
	before.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(before)
	return row


## Réduit les polices de 2 en 2, depuis FONT_SIZE, jusqu'à ce que chaque ligne tienne dans sa colonne
## (width : largeur du bilan) et que `fits` (hauteur de la carte) réponde vrai, ou jusqu'à MIN_FONT_SIZE ;
## à MIN_FONT_SIZE, resserre les écarts et baisse le graphique, puis passe les paliers de `_set_compact`
## un à un tant que la carte ne tient toujours pas (bilan détaillé avec progression en 1280×720).
func fit(width: float, fits: Callable) -> void:
	_set_tight(false)
	_set_compact(0)
	var size := FONT_SIZE
	while true:
		_set_fonts(size)
		if _cells_fit(width) and fits.call():
			return
		if size <= MIN_FONT_SIZE:
			break
		size -= 2
	_set_tight(true)
	for level in range(1, COMPACT_LEVELS + 1):
		if fits.call():
			return
		_set_compact(level)


## Paliers après les écarts resserrés, dans l'ordre : 1 tuiles basses, 2 blocs ERG sur deux colonnes,
## 3 graphique de puissance caché (comme l'étape « courbe du bilan » du contrat, la courbe part la première).
func _set_compact(level: int) -> void:
	for t in _tiles:
		t.add_theme_stylebox_override("panel", _tile_style_compact if level >= 1 else _tile_style)
	blocks_box.columns = 2 if level >= 2 else 1
	chart_box.visible = not _chart.is_empty() and level < 3


func _set_tight(tight: bool) -> void:
	add_theme_constant_override("separation", BOX_SEP_TIGHT if tight else BOX_SEP)
	lines_grid.add_theme_constant_override("v_separation", ROW_SEP_TIGHT if tight else ROW_SEP)
	tiles_grid.add_theme_constant_override("v_separation", ROW_SEP_TIGHT if tight else TILE_GAP)
	progress_grid.add_theme_constant_override("v_separation", ROW_SEP_TIGHT if tight else PROGRESS_SEP)
	progress_box.add_theme_constant_override("separation", ROW_SEP_TIGHT if tight else PROGRESS_SEP)
	chart.custom_minimum_size.y = CHART_H_TIGHT if tight else CHART_H


func _set_fonts(size: int) -> void:
	var small: int = size - (FONT_SIZE - BLOCK_FONT_SIZE)
	for l in lines_grid.get_children():
		l.add_theme_font_size_override("font_size", size)
	for t in _tiles:
		var row := t.get_child(0).get_child(1) as HBoxContainer
		(row.get_child(0) as Label).add_theme_font_size_override("font_size", size + TILE_VALUE_EXTRA)
	ftp_value.add_theme_font_size_override("font_size", size + TILE_VALUE_EXTRA)
	for i in range(1, SummaryViewModel.MAX_RECORD_LINES + 1):
		var row := records_box.get_child(i) as HBoxContainer
		(row.get_child(0) as Label).add_theme_font_size_override("font_size", size)
		(row.get_child(1) as Label).add_theme_font_size_override("font_size", size)
		(row.get_child(2) as Label).add_theme_font_size_override("font_size", small)
	for l in [more_label, records_more, bar_label, extras_label, ftp_before, ftp_delta, ftp_note] \
			+ progress_grid.get_children() + blocks_box.get_children():
		l.add_theme_font_size_override("font_size", small)


func _cells_fit(width: float) -> bool:
	for g: GridContainer in [lines_grid, progress_grid]:
		var col: float = (width - COLUMN_GAP * (g.columns - 1)) / g.columns
		for l: Label in g.get_children():
			var font: Font = l.get_theme_font("font")
			if l.visible and font.get_string_size(l.text, HORIZONTAL_ALIGNMENT_LEFT, -1,
					l.get_theme_font_size("font_size")).x > col:
				return false
	return true


func _grid(v_sep: int) -> GridContainer:
	var g := GridContainer.new()
	g.columns = COLUMNS
	g.add_theme_constant_override("h_separation", COLUMN_GAP)
	g.add_theme_constant_override("v_separation", v_sep)
	return g


## Remplit une grille d'une cellule par ligne (cellules en trop cachées, ellipse si une ligne déborde de sa
## colonne). Une seule ligne occupe toute la largeur (« Bilan en cours de calcul… »).
func _fill(g: GridContainer, rows: Array[String], font_size: int) -> void:
	while g.get_child_count() < rows.size():
		var l := UiTheme.label(font_size)
		l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		l.clip_text = true
		l.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		g.add_child(l)
	g.columns = COLUMNS if rows.size() > 1 else 1
	for i in range(g.get_child_count()):
		var l: Label = g.get_child(i)
		l.visible = i < rows.size()
		l.text = rows[i] if l.visible else ""
	g.visible = not rows.is_empty()


static func _grid_text(g: GridContainer) -> String:
	var parts: Array[String] = []
	for l in g.get_children():
		if l.visible:
			parts.append(l.text)
	return " | ".join(parts)


static func _row_text(row: Container) -> String:
	var parts: Array[String] = []
	for c in row.get_children():
		var l := c as Label
		if l != null and l.visible and l.text != "":
			parts.append(l.text)
	return " ".join(parts)


## Bandeau FTP, tuiles, graphique, records, autres chiffres, lignes du mode puis blocs du bilan détaillé,
## « | » entre les parties (tests graphiques).
func text() -> String:
	var parts: Array[String] = []
	if ftp_band.visible:
		var ftp: Array[String] = []
		for t in [ftp_value.text, ftp_before.text, ftp_delta.text, ftp_note.text]:
			if t != "":
				ftp.append(t)
		parts.append("FTP " + " ".join(ftp))
	for t in _tiles:
		if t.visible:
			var box := t.get_child(0) as VBoxContainer
			parts.append((box.get_child(0) as Label).text + " " + _row_text(box.get_child(1) as Container))
	if chart_box.visible:
		parts.append(_row_text(chart_box.get_child(0) as Container))
	if records_box.visible:
		for i in range(1, SummaryViewModel.MAX_RECORD_LINES + 1):
			var row := records_box.get_child(i) as HBoxContainer
			if row.visible:
				parts.append(_row_text(row))
		if records_more.visible:
			parts.append(records_more.text)
	if more_label.visible:
		parts.append(more_label.text)
	if lines_grid.visible:
		parts.append(_grid_text(lines_grid))
	if blocks_box.visible:
		for l in blocks_box.get_children():
			parts.append(l.text)
	return " | ".join(parts)


## Graphique affiché : "power", "power_target" (avec le profil cible) ou "" (tests).
func chart_kind() -> String:
	if not chart_box.visible:
		return ""
	return "power_target" if not (_chart["target_w"] as Array).is_empty() else "power"


## summary : bilan (`state.summary` ou `history_session.summary`) ; ftp_w : FTP des réglages (ligne du
## graphique) ; names : identifiant → nom des segments (records battus).
func update_display(summary: Dictionary, details: bool, _mode := "", ftp_w := 0.0, names := {}) -> void:
	_ftp_w = float(ftp_w)
	_show_ftp(model.ftp_result(summary))
	var tiles: Array = model.tiles(summary)
	for i in range(_tiles.size()):
		_tiles[i].visible = i < tiles.size()
		if _tiles[i].visible:
			_set_tile(_tiles[i], tiles[i])
	tiles_grid.visible = not tiles.is_empty()
	_chart = model.power_chart(summary)
	chart_box.visible = not _chart.is_empty()
	if chart_box.visible:
		chart_label.text = "Puissance et cible" if not (_chart["target_w"] as Array).is_empty() else "Puissance"
		chart_max.text = ("max %s W" % SummaryViewModel._format_fr_round(summary["max_power_w"])) \
			if (summary.get("max_power_w") is int or summary.get("max_power_w") is float) else ""
		chart.queue_redraw()
	_show_records(model.records_beaten(summary, names))
	more_label.text = model.more_line(summary)
	more_label.visible = more_label.text != ""
	var rows: Array[String] = []
	for ln in model.mode_lines(summary):
		var unit := str(ln.get("unit", ""))
		rows.append("%s : %s%s" % [ln["label"], ln["value"], (" " + unit) if unit != "" else ""])
	if tiles.is_empty() and rows.is_empty():
		rows.append("Bilan en cours de calcul…")
	_fill(lines_grid, rows, FONT_SIZE)
	fit_label.text = model.fit_line(summary)
	for c in blocks_box.get_children():
		blocks_box.remove_child(c)   # hors de la mesure de `fit` dès maintenant
		c.queue_free()
	blocks_box.visible = details
	if not details:
		return
	var blks: Array = model.blocks(summary)
	if blks.is_empty():
		_block_line("Pas de blocs (séance sans entraînement)", SummaryViewModel.COLOR_NEUTRAL)
	for i in range(mini(blks.size(), MAX_BLOCK_LINES)):
		var b: Dictionary = blks[i]
		var avg = b.get("avg_power_w")
		var line := "Bloc %d : %s" % [int(b.get("index", i + 1)), "—" if avg == null else "%d W" % int(round(float(avg)))]
		if b.get("target_w") != null:
			line += " pour %d W (%s, %s)" % [int(round(float(b["target_w"]))), b.get("delta_w_text", ""), b.get("delta_pct_text", "")]
		else:
			line += ", sans cible"
		_block_line(line, str(b.get("color", SummaryViewModel.COLOR_NEUTRAL)))
	if blks.size() > MAX_BLOCK_LINES:
		_block_line("… et %d autres blocs" % (blks.size() - MAX_BLOCK_LINES), SummaryViewModel.COLOR_NEUTRAL)


func _show_ftp(res: Dictionary) -> void:
	ftp_band.visible = not res.is_empty()
	if res.is_empty():
		return
	ftp_value.text = str(res["value"]) if str(res["value"]) != "" else "—"
	ftp_before.text = str(res["before"])
	ftp_delta.text = str(res["delta"])
	ftp_delta.visible = ftp_delta.text != ""
	ftp_note.text = str(res["note"])
	ftp_note.add_theme_color_override("font_color", UiTheme.DIM if bool(res["ok"]) else UiTheme.WARN)


func _set_tile(t: PanelContainer, tile: Dictionary) -> void:
	var box := t.get_child(0) as VBoxContainer
	var row := box.get_child(1) as HBoxContainer
	(box.get_child(0) as Label).text = str(tile.get("label", ""))
	(row.get_child(0) as Label).text = str(tile.get("value", ""))
	for i in [1, 2]:   # unité, complément (NP) : cachés vides
		var l := row.get_child(i) as Label
		l.text = str(tile.get("unit" if i == 1 else "sub", ""))
		l.visible = l.text != ""


func _show_records(recs: Array) -> void:
	records_box.visible = not recs.is_empty()
	for i in range(SummaryViewModel.MAX_RECORD_LINES):
		var row := records_box.get_child(i + 1) as HBoxContainer
		row.visible = i < recs.size()
		if row.visible:
			(row.get_child(0) as Label).text = "★ " + str(recs[i]["name"])
			(row.get_child(1) as Label).text = str(recs[i]["time"])
			(row.get_child(2) as Label).text = str(recs[i]["before"])
	var more := recs.size() - SummaryViewModel.MAX_RECORD_LINES
	records_more.text = ("… et %d autres records" % more) if more > 1 else ("… et un autre record" if more == 1 else "")
	records_more.visible = more > 0


func _block_line(text: String, color: String) -> void:
	var l := UiTheme.label(BLOCK_FONT_SIZE, BLOCK_COLORS.get(color, UiTheme.TEXT), text)
	l.clip_text = true
	blocks_box.add_child(l)


## Courbe réduite : profil cible coloré par zone (ERG, avec une FTP connue), ligne de la FTP, puissance en
## blanc sur un contour sombre (mêmes couleurs que workout_chart_view.gd).
func _draw_chart() -> void:
	if _chart.is_empty():
		return
	var w := chart.size.x
	var h := chart.size.y
	chart.draw_rect(Rect2(0, 0, w, h), WorkoutChartView.BG_COLOR)
	var power: Array = _chart["power_w"]
	var target: Array = _chart["target_w"]
	var top := maxf(float(_chart["max_w"]), _ftp_w) * 1.1
	if top <= 0.0:
		return
	var n := power.size()
	var step := w / float(n - 1)
	if not target.is_empty():
		for i in range(n):
			var t = target[i]
			if t == null:
				continue
			var col: Color = ErgView.zone_color(float(t) / _ftp_w) if _ftp_w > 0.0 else ErgView.zone_color(null)
			var x0 := maxf(step * (i - 0.5), 0.0)
			var x1 := minf(step * (i + 0.5), w)
			var y := h - float(t) / top * h
			chart.draw_rect(Rect2(x0, y, x1 - x0, h - y), Color(col, TARGET_ALPHA))
	if _ftp_w > 0.0:
		var yf := h - _ftp_w / top * h
		chart.draw_dashed_line(Vector2(0, yf), Vector2(w, yf), WorkoutChartView.GRID_COLOR, 1.0, 6.0)
	var line := PackedVector2Array()
	for i in range(n):
		line.append(Vector2(step * i, h - 1.0 - float(power[i]) / top * (h - 2.0)))
	chart.draw_polyline(line, UiTheme.OUTLINE, POWER_WIDTH + 2.0 * POWER_OUTLINE, true)
	chart.draw_polyline(line, WorkoutChartView.POWER_COLOR, POWER_WIDTH, true)
	chart.draw_line(Vector2(0, h - 1), Vector2(w, h - 1), UiTheme.LINE, 1.0)


## Texte du bloc « Progression » en une ligne, « | » entre les parties (tests graphiques) ; "" sans bloc.
func progress_text() -> String:
	if not progress_box.visible:
		return ""
	var parts: Array[String] = [_grid_text(progress_grid)]
	if bar_label.visible:
		parts.append(bar_label.text)
	if extras_label.visible:
		parts.append(extras_label.text.replace("\n", " | "))
	return " | ".join(parts)


## Position affichée de la barre, 0 à 1 (tests).
func bar_position() -> float:
	return _bar_pos


## Bloc « Progression » de progress_view_model.gd view() ; {} : bloc caché, bilan de N4 seul.
func update_progress(view: Dictionary) -> void:
	progress_box.visible = not view.is_empty()
	if view.is_empty():
		_bar_key = ""
		return
	var rows: Array[String] = []
	for ln in view["lines"]:
		rows.append(("%s : %s" % [ln["label"], ln["value"]]) if str(ln["value"]) != "" else str(ln["label"]))
	_fill(progress_grid, rows, BLOCK_FONT_SIZE)
	var b: Dictionary = view.get("bar", {})
	bar_label.visible = not b.is_empty()
	bar.visible = not b.is_empty()
	if not b.is_empty():
		bar_label.text = str(b["text"])
		var key := "%s|%s|%s" % [b["text"], b["before"], b["after"]]
		if key != _bar_key:
			_bar_key = key
			_bar_from = float(b["before"])
			_bar_to = float(b["after"])
			_bar_t = 0.0 if animate else 1.0
			_bar_pos = _bar_from if animate else _bar_to
			set_process(animate)
			bar.queue_redraw()
	var extras: Array[String] = []
	if str(view.get("level_up", "")) != "":
		extras.append(str(view["level_up"]))
	extras.append_array(view.get("unlocked", []))
	extras.append_array(view.get("challenges", []))
	if str(view.get("more", "")) != "":
		extras.append(str(view["more"]))
	extras_label.text = "\n".join(extras)
	extras_label.visible = not extras.is_empty()


func _process(delta: float) -> void:
	_bar_t = minf(_bar_t + delta / BAR_ANIM_S, 1.0)
	var k := 1.0 - pow(1.0 - _bar_t, 3.0)   # ralentit en fin de course
	_bar_pos = lerpf(_bar_from, _bar_to, k)
	bar.queue_redraw()
	if _bar_t >= 1.0:
		_bar_pos = _bar_to
		set_process(false)


func _draw_bar() -> void:
	var w := bar.size.x
	bar.draw_rect(Rect2(0, 0, w, BAR_H), UiTheme.LINE)
	bar.draw_rect(Rect2(0, 0, w * _bar_pos, BAR_H), UiTheme.FOCUS)
