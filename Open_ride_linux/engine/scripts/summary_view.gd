extends VBoxContainer

## Bilan de fin de séance dans les menus (Lot N6) : lignes du bilan, fichier FIT et, sur demande
## (« Voir le bilan détaillé »), les blocs ERG avec leur couleur. Ne calcule rien : lit
## summary_view_model.gd (lot N4). Pas de class_name : charger par preload("res://scripts/summary_view.gd").

const SummaryViewModel := preload("res://scripts/summary_view_model.gd")

const FONT_SIZE := 24
const BLOCK_FONT_SIZE := 20
const BLOCK_COLORS := {
	SummaryViewModel.COLOR_GREEN: Color(0.55, 0.90, 0.55),
	SummaryViewModel.COLOR_ORANGE: Color(1.0, 0.75, 0.30),
	SummaryViewModel.COLOR_RED: Color(1.0, 0.45, 0.40),
	SummaryViewModel.COLOR_NEUTRAL: Color(0.75, 0.77, 0.80),
}
const MAX_BLOCK_LINES := 4

var model = SummaryViewModel.new()
var lines_label: Label
var fit_label: Label
var blocks_box: VBoxContainer


func _init() -> void:
	add_theme_constant_override("separation", 4)
	lines_label = Label.new()
	lines_label.add_theme_font_size_override("font_size", FONT_SIZE)
	add_child(lines_label)
	fit_label = Label.new()
	fit_label.add_theme_font_size_override("font_size", BLOCK_FONT_SIZE)
	fit_label.modulate = Color(0.75, 0.80, 0.85)
	fit_label.clip_text = true
	add_child(fit_label)
	blocks_box = VBoxContainer.new()
	add_child(blocks_box)


func text() -> String:
	return lines_label.text.replace("\n", " | ")


func update_display(summary: Dictionary, details: bool, mode := "", ftp_w := 0) -> void:
	var rows: Array[String] = []
	for ln in model.lines(summary, mode, ftp_w):
		var unit := str(ln.get("unit", ""))
		rows.append("%s : %s%s" % [ln["label"], ln["value"], (" " + unit) if unit != "" else ""])
	# Deux colonnes : le bilan complet tient dans le panneau à 1280 × 720.
	var half := int(ceil(rows.size() / 2.0))
	var text_rows: Array[String] = []
	for i in range(half):
		var right := ("        " + rows[i + half]) if i + half < rows.size() else ""
		text_rows.append(rows[i] + right)
	lines_label.text = "\n".join(text_rows) if not rows.is_empty() else "Bilan en cours de calcul…"
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
	var l := Label.new()
	l.add_theme_font_size_override("font_size", BLOCK_FONT_SIZE)
	l.text = text
	l.clip_text = true
	l.modulate = BLOCK_COLORS.get(color, Color.WHITE)
	blocks_box.add_child(l)
