extends VBoxContainer

## Bilan de fin de séance dans les menus (Lot N6) : lignes du bilan, fichier FIT et, sur demande
## (« Voir le bilan détaillé »), les blocs ERG avec leur couleur. Ne calcule rien : lit
## summary_view_model.gd (lot N4). Dans la carte de détail du menu, élargie à UiTheme.SUMMARY_CARD_W :
## chiffres du bilan et lignes de progression sur deux colonnes, et `fit` réduit les polices tant que le
## bilan (détaillé compris) ne tient pas au-dessus du bandeau des boutons ; couleurs du thème commun
## (ui_theme.gd). Pas de class_name : charger par preload("res://scripts/summary_view.gd").

const SummaryViewModel := preload("res://scripts/summary_view_model.gd")
const UiTheme := preload("res://scripts/ui_theme.gd")

const FONT_SIZE := UiTheme.CARD_SIZE
const BLOCK_FONT_SIZE := 20
const BLOCK_COLORS := {
	SummaryViewModel.COLOR_GREEN: UiTheme.OK,
	SummaryViewModel.COLOR_ORANGE: UiTheme.WARN,
	SummaryViewModel.COLOR_RED: UiTheme.DANGER,
	SummaryViewModel.COLOR_NEUTRAL: UiTheme.DIM,
}
const MAX_BLOCK_LINES := 4
## Chiffres du bilan et lignes de progression : deux colonnes, remplies ligne par ligne.
const COLUMNS := 2
const COLUMN_GAP := 24
## Plus petite police des lignes du bilan quand `fit` le compacte (celle des autres lignes suit, 2 de moins).
const MIN_FONT_SIZE := 16
## Bloc « Progression » (lot V9) : durée de l'animation de la barre d'expérience, hauteur de la barre.
const BAR_ANIM_S := 1.2
const BAR_H := 12

var model = SummaryViewModel.new()
var lines_grid: GridContainer
var fit_label: Label
var blocks_box: VBoxContainer
var progress_box: VBoxContainer
var progress_grid: GridContainer
var bar_label: Label
var bar: Control
var extras_label: Label
## Animation de la barre d'expérience (coupée par main.gd en qualité basse).
var animate := true
var _bar_from := 0.0
var _bar_to := 0.0
var _bar_pos := 0.0
var _bar_t := 1.0
var _bar_key := ""


func _init() -> void:
	add_theme_constant_override("separation", 4)
	lines_grid = _grid(6)
	add_child(lines_grid)
	fit_label = UiTheme.label(BLOCK_FONT_SIZE, UiTheme.DIM)
	fit_label.clip_text = true
	add_child(fit_label)
	blocks_box = VBoxContainer.new()
	add_child(blocks_box)
	progress_box = VBoxContainer.new()
	progress_box.add_theme_constant_override("separation", 3)
	progress_box.visible = false
	add_child(progress_box)
	progress_box.add_child(UiTheme.label(UiTheme.SMALL_SIZE, UiTheme.DIM, "Progression"))
	progress_grid = _grid(3)
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


## Réduit les polices de 2 en 2, depuis FONT_SIZE, jusqu'à ce que chaque ligne tienne dans sa colonne
## (width : largeur du bilan) et que `fits` (hauteur de la carte) réponde vrai, ou jusqu'à MIN_FONT_SIZE.
func fit(width: float, fits: Callable) -> void:
	var size := FONT_SIZE
	while true:
		_set_fonts(size)
		if size <= MIN_FONT_SIZE or (_cells_fit(width) and fits.call()):
			return
		size -= 2


func _set_fonts(size: int) -> void:
	var small: int = size - (FONT_SIZE - BLOCK_FONT_SIZE)
	for l in lines_grid.get_children():
		l.add_theme_font_size_override("font_size", size)
	for l in [fit_label, bar_label, extras_label] + progress_grid.get_children() + blocks_box.get_children():
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


static func _grid_text(g: GridContainer) -> String:
	var parts: Array[String] = []
	for l in g.get_children():
		if l.visible:
			parts.append(l.text)
	return " | ".join(parts)


## Chiffres du bilan puis lignes du bilan détaillé, « | » entre les lignes (tests graphiques).
func text() -> String:
	var parts: Array[String] = [_grid_text(lines_grid)]
	if blocks_box.visible:
		for l in blocks_box.get_children():
			parts.append(l.text)
	return " | ".join(parts)


func update_display(summary: Dictionary, details: bool, mode := "", ftp_w := 0) -> void:
	var rows: Array[String] = []
	for ln in model.lines(summary, mode, ftp_w):
		var unit := str(ln.get("unit", ""))
		rows.append("%s : %s%s" % [ln["label"], ln["value"], (" " + unit) if unit != "" else ""])
	if rows.is_empty():
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


func _block_line(text: String, color: String) -> void:
	var l := UiTheme.label(BLOCK_FONT_SIZE, BLOCK_COLORS.get(color, UiTheme.TEXT), text)
	l.clip_text = true
	blocks_box.add_child(l)


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
