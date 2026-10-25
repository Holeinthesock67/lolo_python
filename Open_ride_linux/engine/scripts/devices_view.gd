extends VBoxContainer

## État des appareils dans les menus (Lot N6) : une ligne par appareil (trainer, boîtiers du Click,
## ceinture), couleur selon le niveau, puis la ligne « prêt à rouler ». Ne calcule rien : lit
## devices_view_model.gd (lot N5). Pas de class_name : charger par preload("res://scripts/devices_view.gd").

const DevicesViewModel := preload("res://scripts/devices_view_model.gd")

const FONT_SIZE := 20
const LEVEL_COLORS := {
	DevicesViewModel.LEVEL_OK: Color(0.55, 0.90, 0.55),
	DevicesViewModel.LEVEL_WARN: Color(1.0, 0.80, 0.30),
	DevicesViewModel.LEVEL_ERROR: Color(1.0, 0.45, 0.40),
	DevicesViewModel.LEVEL_OFF: Color(0.70, 0.72, 0.75),
}

var model = DevicesViewModel.new()
var _labels: Array[Label] = []
var ready_label: Label


func _init() -> void:
	add_theme_constant_override("separation", 2)
	ready_label = _label()


func _label() -> Label:
	var l := Label.new()
	l.add_theme_font_size_override("font_size", FONT_SIZE)
	l.clip_text = true
	add_child(l)
	return l


## Texte affiché, une ligne par appareil (tests graphiques).
func text() -> String:
	var parts: Array[String] = []
	for l in _labels:
		if l.visible:
			parts.append(l.text)
	if ready_label.text != "":
		parts.append(ready_label.text)
	return " | ".join(parts)


func update_display(state: Dictionary) -> void:
	var rows: Array = model.rows(state)
	while _labels.size() < rows.size():
		var l := _label()
		move_child(l, _labels.size())
		_labels.append(l)
	for i in range(_labels.size()):
		var l := _labels[i]
		l.visible = i < rows.size()
		if l.visible:
			var r: Dictionary = rows[i]
			l.text = "%s : %s" % [r.get("label", ""), r.get("status_text", "")]
			l.modulate = LEVEL_COLORS.get(r.get("level", ""), Color.WHITE)
	var ready: Dictionary = model.ready_to_ride(state)
	ready_label.text = str(ready.get("reason", ""))
	ready_label.modulate = LEVEL_COLORS[DevicesViewModel.LEVEL_OK if ready.get("ok", false) else DevicesViewModel.LEVEL_ERROR]
