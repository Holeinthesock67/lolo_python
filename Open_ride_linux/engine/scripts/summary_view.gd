extends VBoxContainer

## Bilan de fin de séance dans les menus (Lot N6) : lignes du bilan, fichier FIT et, sur demande
## (« Voir le bilan détaillé »), les blocs ERG avec leur couleur. Ne calcule rien : lit
## summary_view_model.gd (lot N4). Une colonne dans la carte de détail du menu, couleurs du thème commun
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
## Bloc « Progression » (lot V9) : durée de l'animation de la barre d'expérience, hauteur de la barre.
const BAR_ANIM_S := 1.2
const BAR_H := 12

var model = SummaryViewModel.new()
var lines_label: Label
var fit_label: Label
var blocks_box: VBoxContainer
var progress_box: VBoxContainer
var progress_label: Label
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
	lines_label = UiTheme.label(FONT_SIZE)
	add_child(lines_label)
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
	progress_label = UiTheme.label(BLOCK_FONT_SIZE)
	progress_box.add_child(progress_label)
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


func text() -> String:
	return lines_label.text.replace("\n", " | ")


func update_display(summary: Dictionary, details: bool, mode := "", ftp_w := 0) -> void:
	var rows: Array[String] = []
	for ln in model.lines(summary, mode, ftp_w):
		var unit := str(ln.get("unit", ""))
		rows.append("%s : %s%s" % [ln["label"], ln["value"], (" " + unit) if unit != "" else ""])
	lines_label.text = "\n".join(rows) if not rows.is_empty() else "Bilan en cours de calcul…"
	fit_label.text = model.fit_line(summary)
	for c in blocks_box.get_children():
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
			line += ", roue libre"
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
	var parts: Array[String] = [progress_label.text.replace("\n", " | ")]
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
	progress_label.text = "\n".join(rows)
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
