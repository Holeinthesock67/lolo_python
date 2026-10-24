extends CanvasLayer

## Vue du HUD de séance (Lot E3 §4.5, SRS §8 « HUD de base »).
##
## Affiche les métriques de séance avec lisibilité garantie à 2,5 m d'un écran 1080p :
## - Chiffres principaux >= 48 px, libellés >= 24 px.
## - Profil d'altitude en bas de l'écran sur 120 colonnes, coloré selon grade_class.
## - Prochaine montée ou montée en cours.
## - Fond semi-transparent, centre de l'écran dégagé (route visible à 50 m).
## - Ne calcule rien : s'appuie sur hud_view_model.gd.

const HudViewModel := preload("res://scripts/hud_view_model.gd")

const COLOR_DESCENT := Color(0.25, 0.60, 0.90, 0.85)
const COLOR_FLAT := Color(0.25, 0.75, 0.30, 0.85)
const COLOR_CLIMB := Color(0.95, 0.75, 0.20, 0.85)
const COLOR_STEEP := Color(0.95, 0.45, 0.10, 0.85)
const COLOR_WALL := Color(0.85, 0.15, 0.15, 0.85)

const GRADE_COLORS := {
	"descent": COLOR_DESCENT,
	"flat": COLOR_FLAT,
	"climb": COLOR_CLIMB,
	"steep": COLOR_STEEP,
	"wall": COLOR_WALL,
}

var vm := HudViewModel.new()

# Panneaux principaux
var panel_left: Panel
var panel_right: Panel
var panel_center: Panel

# Nœuds d'affichage
var power_val: Label
var cadence_val: Label
var hr_val: Label
var speed_val: Label
var grade_val: Label
var distance_val: Label
var time_val: Label
var gear_val: Label
var erg_label: Label
var climb_label: Label
var status_label: Label
var profile_panel: Control
var alt_min_label: Label
var alt_max_label: Label

# Données du profil d'altitude en cache
var _last_profile_s := -99999.0
var _last_profile_time_s := 0.0
var _profile_data: Dictionary = {}
var _route = null


func _init() -> void:
	_build_ui()


func _build_ui() -> void:
	if panel_left != null:
		return

	# Panneau gauche (haut) : Puissance, Cadence, Fréquence cardiaque
	panel_left = _create_panel(Vector2(20.0, 20.0), Vector2(300.0, 240.0), false, false)
	var left_vbox := VBoxContainer.new()
	left_vbox.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT, Control.PRESET_MODE_KEEP_SIZE, 10)
	panel_left.add_child(left_vbox)

	power_val = _create_metric(left_vbox, "PUISSANCE (W)", HudViewModel.NO_VALUE)
	cadence_val = _create_metric(left_vbox, "CADENCE (RPM)", HudViewModel.NO_VALUE)
	hr_val = _create_metric(left_vbox, "CARDIO (BPM)", HudViewModel.NO_VALUE)

	# Panneau droit (haut) : Vitesse, Pente, Braquet, Distance, Temps
	panel_right = _create_panel(Vector2(-320.0, 20.0), Vector2(300.0, 320.0), true, false)
	var right_vbox := VBoxContainer.new()
	right_vbox.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT, Control.PRESET_MODE_KEEP_SIZE, 10)
	panel_right.add_child(right_vbox)

	speed_val = _create_metric(right_vbox, "VITESSE (KM/H)", HudViewModel.NO_VALUE)
	grade_val = _create_metric(right_vbox, "PENTE", HudViewModel.NO_VALUE)
	gear_val = _create_metric(right_vbox, "BRAQUET", HudViewModel.NO_VALUE, 32, 20)
	distance_val = _create_metric(right_vbox, "DISTANCE", HudViewModel.NO_VALUE, 32, 20)
	time_val = _create_metric(right_vbox, "TEMPS", HudViewModel.NO_VALUE, 32, 20)

	# Bandeau supérieur central : ERG et Prochaine montée
	panel_center = _create_panel(Vector2(340.0, 20.0), Vector2(-680.0, 80.0), false, false, true)
	var center_vbox := VBoxContainer.new()
	center_vbox.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT, Control.PRESET_MODE_KEEP_SIZE, 8)
	panel_center.add_child(center_vbox)

	climb_label = Label.new()
	climb_label.add_theme_font_size_override("font_size", 24)
	climb_label.text = ""
	center_vbox.add_child(climb_label)

	erg_label = Label.new()
	erg_label.add_theme_font_size_override("font_size", 22)
	erg_label.text = ""
	center_vbox.add_child(erg_label)

	# Panneau inférieur : Profil d'altitude
	profile_panel = Control.new()
	profile_panel.name = "ProfilePanel"
	profile_panel.anchor_left = 0.0
	profile_panel.anchor_right = 1.0
	profile_panel.anchor_top = 1.0
	profile_panel.anchor_bottom = 1.0
	profile_panel.offset_left = 40.0
	profile_panel.offset_right = -40.0
	profile_panel.offset_top = -120.0
	profile_panel.offset_bottom = -15.0
	profile_panel.grow_vertical = Control.GROW_DIRECTION_BEGIN
	profile_panel.draw.connect(_on_profile_draw)
	add_child(profile_panel)

	alt_min_label = Label.new()
	alt_min_label.add_theme_font_size_override("font_size", 20)
	alt_min_label.position = Vector2(8.0, 80.0)
	profile_panel.add_child(alt_min_label)

	alt_max_label = Label.new()
	alt_max_label.add_theme_font_size_override("font_size", 20)
	alt_max_label.position = Vector2(8.0, 4.0)
	profile_panel.add_child(alt_max_label)


func _create_panel(pos: Vector2, size: Vector2, anchor_right := false, anchor_bottom := false, span_h := false) -> Panel:
	var p := Panel.new()
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.05, 0.07, 0.10, 0.70)
	style.corner_radius_top_left = 8
	style.corner_radius_top_right = 8
	style.corner_radius_bottom_left = 8
	style.corner_radius_bottom_right = 8
	p.add_theme_stylebox_override("panel", style)

	if span_h:
		p.anchor_left = 0.0
		p.anchor_right = 1.0
		p.offset_left = pos.x
		p.offset_right = size.x
		p.offset_top = pos.y
		p.offset_bottom = pos.y + size.y
	elif anchor_right:
		p.anchor_left = 1.0
		p.anchor_right = 1.0
		p.anchor_top = 0.0
		p.anchor_bottom = 0.0
		p.offset_left = pos.x
		p.offset_right = pos.x + size.x
		p.offset_top = pos.y
		p.offset_bottom = pos.y + size.y
	else:
		p.position = pos
		p.size = size

	add_child(p)
	return p


func _create_metric(parent: Control, label_text: String, default_val: String,
		val_size := 48, label_size := 24) -> Label:
	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 12)
	parent.add_child(hbox)

	var lbl := Label.new()
	lbl.text = label_text
	lbl.add_theme_font_size_override("font_size", label_size)
	lbl.modulate = Color(0.75, 0.80, 0.85)
	hbox.add_child(lbl)

	var val := Label.new()
	val.text = default_val
	val.add_theme_font_size_override("font_size", val_size)
	hbox.add_child(val)

	return val


## Met à jour les valeurs et le profil d'altitude.
func update_display(state: Dictionary, erg_eval: Dictionary, route: Variant = null, s: float = 0.0) -> void:
	_route = route
	var now_s := Time.get_ticks_usec() / 1e6
	vm.on_state(state, now_s)
	var lines := HudViewModel.session_lines(state, erg_eval)

	if power_val != null:
		power_val.text = lines["power_val"]
	if speed_val != null:
		speed_val.text = lines["speed_val"]
	if cadence_val != null:
		cadence_val.text = lines["cadence_val"]
	if hr_val != null:
		hr_val.text = lines["hr_val"]
	if distance_val != null:
		distance_val.text = lines["distance_val"]
	if time_val != null:
		time_val.text = lines["time_val"]
	if gear_val != null:
		gear_val.text = lines["gear_val"]

	if grade_val != null:
		grade_val.text = lines["grade_val"]
		var g_class: String = lines.get("grade_class", "flat")
		grade_val.modulate = GRADE_COLORS.get(g_class, COLOR_FLAT)

	if erg_label != null:
		erg_label.text = lines.get("erg", "")
		erg_label.visible = lines.get("erg", "") != ""

	# Prochaine montée (rafraîchie avec le profil)
	if route != null and climb_label != null:
		var climb: Dictionary = vm.next_climb(route, s)
		if climb.is_empty():
			climb_label.text = ""
		elif climb.get("in_progress", false):
			climb_label.text = "Montée en cours : reste %.1f km à %.1f %%" % [
				float(climb["length_m"]) / 1000.0, float(climb["avg_grade_pct"])]
		else:
			climb_label.text = "Prochaine montée : dans %.1f km (%.1f km à %.1f %%)" % [
				float(climb["start_m"]) / 1000.0, float(climb["length_m"]) / 1000.0, float(climb["avg_grade_pct"])]

	# Profil d'altitude (au plus 5 fois par seconde ou si s a avancé d'une colonne ~41 m)
	var col_step := 5000.0 / 120.0
	if route != null and (absf(s - _last_profile_s) >= col_step or now_s - _last_profile_time_s >= 0.20):
		_last_profile_s = s
		_last_profile_time_s = now_s
		_profile_data = vm.profile(route, s)
		if alt_min_label != null and alt_max_label != null:
			alt_min_label.text = "min %.0f m" % float(_profile_data.get("alt_min", 0.0))
			alt_max_label.text = "max %.0f m" % float(_profile_data.get("alt_max", 0.0))
		if profile_panel != null:
			profile_panel.queue_redraw()


func _on_profile_draw() -> void:
	if _profile_data.is_empty():
		return
	var alts: PackedFloat64Array = _profile_data.get("alts", PackedFloat64Array())
	var classes: PackedStringArray = _profile_data.get("grade_class", PackedStringArray())
	var marker_idx: int = int(_profile_data.get("marker_index", -1))
	var alt_min: float = float(_profile_data.get("alt_min", 0.0))
	var alt_max: float = float(_profile_data.get("alt_max", 1.0))
	var alt_range := maxf(alt_max - alt_min, 1.0)

	var w: float = profile_panel.size.x
	var h: float = profile_panel.size.y
	var cols := alts.size()
	if cols < 2:
		return

	# Fond du panneau profil
	profile_panel.draw_rect(Rect2(0, 0, w, h), Color(0.04, 0.06, 0.08, 0.65))

	var col_w := w / float(cols)
	for i in range(cols):
		var norm_h := clampf((float(alts[i]) - alt_min) / alt_range, 0.05, 0.95)
		var bar_h := norm_h * h
		var bar_rect := Rect2(i * col_w, h - bar_h, col_w + 0.5, bar_h)
		var col_grade: String = classes[i] if i < classes.size() else "flat"
		var color: Color = GRADE_COLORS.get(col_grade, COLOR_FLAT)
		profile_panel.draw_rect(bar_rect, color)

	# Repère de position
	if marker_idx >= 0 and marker_idx < cols:
		var mx := (marker_idx + 0.5) * col_w
		var my := h - clampf((float(alts[marker_idx]) - alt_min) / alt_range, 0.05, 0.95) * h
		profile_panel.draw_circle(Vector2(mx, my), 6.0, Color.WHITE)
		profile_panel.draw_circle(Vector2(mx, my), 3.0, Color.BLACK)
