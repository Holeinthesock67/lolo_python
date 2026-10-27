extends CanvasLayer

## Vue du HUD de séance (Lot E3 §4.5, SRS §8 « HUD de base »).
##
## Affiche les métriques de séance avec lisibilité garantie à 2,5 m d'un écran 1080p :
## - Chiffres principaux >= 48 px, libellés >= 24 px.
## - Profil d'altitude en bas de l'écran sur 120 colonnes, coloré selon grade_class.
## - Prochaine montée ou montée en cours.
## - Fond semi-transparent, centre de l'écran dégagé (route visible à 50 m).
## - Ne calcule rien : s'appuie sur hud_view_model.gd.
## - Lot P16 : indicateur du vent sous le panneau de gauche (`update_wind`, sortie de
##   wind_view_model.gd) : flèche d'où vient le vent par rapport à la route, « 18 km/h face »,
##   barres d'intensité et leur niveau, pastille verte, rouge ou grise du verdict ; caché sans vent.
##   Le coin supérieur droit sous le panneau de droite reste libre (blocs segment et bonus, série T).
## - Lot T9 : blocs « segment » (approche, chrono et écart au record, résultat) et « bonus » (réserve,
##   bonus actif et barre de temps) empilés sous le panneau de droite (`update_segment`, sortie de
##   segment_hud_model.gd) ; cachés sans champ `segment` ni `powerup`. Le bloc segment s'arrête au-dessus
##   du bandeau ERG en 720p ; le bloc bonus n'existe pas en ERG.
## - Lot P17 : « Abri 30 % » derrière un bot (`draft_text` de la même sortie), pastille bleue sous
##   l'indicateur du vent (à sa place quand il n'y a pas de vent) ; cachée sans abri.

const HudViewModel := preload("res://scripts/hud_view_model.gd")

const COLOR_DESCENT := Color(0.25, 0.60, 0.90, 0.85)
const COLOR_FLAT := Color(0.25, 0.75, 0.30, 0.85)
const COLOR_CLIMB := Color(0.95, 0.75, 0.20, 0.85)
const COLOR_STEEP := Color(0.95, 0.45, 0.10, 0.85)
const COLOR_WALL := Color(0.85, 0.15, 0.15, 0.85)

const WIND_TONES := {
	"good": Color(0.15, 0.62, 0.25, 0.95),
	"bad": Color(0.80, 0.18, 0.12, 0.95),
	"neutral": Color(0.45, 0.48, 0.52, 0.95),
}
const WIND_BAR_COLOR := Color(0.85, 0.90, 0.95)
const DRAFT_COLOR := Color(0.15, 0.42, 0.75, 0.95)
const DRAFT_GAP := 10.0
const WIND_BAR_OFF := Color(0.85, 0.90, 0.95, 0.18)
const SEGMENT_TONES := {"good": Color(0.35, 0.90, 0.45), "bad": Color(0.95, 0.40, 0.35), "": Color(0.92, 0.94, 0.96)}
const BONUS_COLOR := Color(0.62, 0.32, 0.92, 0.95)   # violet des arches de bonus (lot T8)
const BLOCK_GAP := 8.0

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
var target_val: Label
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
# Indicateur du vent (Lot P16)
var panel_wind: Panel
var wind_arrow: Control
var wind_speed_label: Label
var wind_bars: Control
var wind_level_label: Label
var wind_verdict_label: Label
var _wind_view: Dictionary = {}
# Abri derrière un bot (Lot P17)
var draft_label: Label
# Blocs segment et bonus (Lot T9)
var panel_segment: Panel
var segment_title: Label
var segment_main: Label
var segment_detail: Label
var panel_bonus: Panel
var bonus_held: Label
var bonus_active: Label
var bonus_bar: Control
var _bonus_fraction := 0.0

# Données du profil d'altitude en cache
var _last_profile_s := -99999.0
var _last_profile_time_s := 0.0
var _profile_data: Dictionary = {}
var _route = null
## Faux quand le bandeau ERG (erg_view.gd, lot N7) affiche l'entraînement : la ligne ERG du panneau
## central reste alors cachée.
var show_erg_line := true


func _init() -> void:
	_build_ui()


func _build_ui() -> void:
	if panel_left != null:
		return

	# Panneau gauche (haut) : Puissance, Cadence, Fréquence cardiaque
	panel_left = _create_panel(Vector2(20.0, 20.0), Vector2(300.0, 320.0), false, false)
	var left_vbox := VBoxContainer.new()
	left_vbox.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT, Control.PRESET_MODE_KEEP_SIZE, 10)
	panel_left.add_child(left_vbox)

	power_val = _create_metric(left_vbox, "PUISSANCE (W)", HudViewModel.NO_VALUE)
	cadence_val = _create_metric(left_vbox, "CADENCE (RPM)", HudViewModel.NO_VALUE)
	hr_val = _create_metric(left_vbox, "CARDIO (BPM)", HudViewModel.NO_VALUE)
	# Cible ERG sous les mesures, affichée seulement en ERG (« roue libre » sur un bloc libre).
	target_val = _create_metric(left_vbox, "CIBLE ERG", HudViewModel.NO_VALUE, 40, 20)
	target_val.get_parent().visible = false

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

	# Bandeau supérieur central : ERG, prochaine montée et ligne d'état de diagnostic
	panel_center = _create_panel(Vector2(340.0, 20.0), Vector2(-680.0, 110.0), false, false, true)
	var center_vbox := VBoxContainer.new()
	center_vbox.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT, Control.PRESET_MODE_KEEP_SIZE, 8)
	panel_center.add_child(center_vbox)

	climb_label = Label.new()
	climb_label.add_theme_font_size_override("font_size", 24)
	climb_label.text = ""
	climb_label.clip_text = true
	center_vbox.add_child(climb_label)

	erg_label = Label.new()
	erg_label.add_theme_font_size_override("font_size", 22)
	erg_label.text = ""
	erg_label.clip_text = true
	center_vbox.add_child(erg_label)

	# Ligne d'état de diagnostic : séance, raison de pause, trainer, entrée (affichée depuis le lot D).
	status_label = Label.new()
	status_label.add_theme_font_size_override("font_size", 18)
	status_label.text = "ÉTAT: en attente du core…"
	status_label.clip_text = true
	center_vbox.add_child(status_label)

	_build_wind_panel()
	_build_draft_label()
	_build_segment_blocks()

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


## Indicateur du vent (Lot P16), sous le panneau de gauche (même largeur), caché tant qu'il n'y a
## pas de vent dans les trames du core.
func _build_wind_panel() -> void:
	panel_wind = _create_panel(Vector2(20.0, 350.0), Vector2(300.0, 132.0), false, false)
	panel_wind.name = "WindPanel"
	panel_wind.visible = false
	wind_arrow = Control.new()
	wind_arrow.name = "WindArrow"
	wind_arrow.position = Vector2(10.0, 10.0)
	wind_arrow.size = Vector2(72.0, 72.0)
	wind_arrow.draw.connect(_on_wind_arrow_draw)
	panel_wind.add_child(wind_arrow)
	wind_speed_label = Label.new()
	wind_speed_label.name = "WindSpeed"
	wind_speed_label.position = Vector2(92.0, 6.0)
	wind_speed_label.size = Vector2(200.0, 40.0)
	wind_speed_label.add_theme_font_size_override("font_size", 30)
	wind_speed_label.clip_text = true
	panel_wind.add_child(wind_speed_label)
	wind_bars = Control.new()
	wind_bars.name = "WindBars"
	wind_bars.position = Vector2(94.0, 50.0)
	wind_bars.size = Vector2(70.0, 28.0)
	wind_bars.draw.connect(_on_wind_bars_draw)
	panel_wind.add_child(wind_bars)
	wind_level_label = Label.new()
	wind_level_label.name = "WindLevel"
	wind_level_label.position = Vector2(172.0, 48.0)
	wind_level_label.size = Vector2(120.0, 32.0)
	wind_level_label.add_theme_font_size_override("font_size", 22)
	wind_level_label.modulate = Color(0.75, 0.80, 0.85)
	wind_level_label.clip_text = true
	panel_wind.add_child(wind_level_label)
	wind_verdict_label = Label.new()
	wind_verdict_label.name = "WindVerdict"
	wind_verdict_label.position = Vector2(10.0, 88.0)
	wind_verdict_label.size = Vector2(280.0, 36.0)
	wind_verdict_label.add_theme_font_size_override("font_size", 24)
	wind_verdict_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	wind_verdict_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	var pill := StyleBoxFlat.new()
	pill.bg_color = WIND_TONES["neutral"]
	pill.set_corner_radius_all(18)
	wind_verdict_label.add_theme_stylebox_override("normal", pill)
	panel_wind.add_child(wind_verdict_label)


## Pastille « Abri 30 % » (Lot P17), même largeur que l'indicateur du vent.
func _build_draft_label() -> void:
	draft_label = Label.new()
	draft_label.name = "Draft"
	draft_label.position = panel_wind.position + Vector2(0.0, panel_wind.size.y + DRAFT_GAP)
	draft_label.size = Vector2(panel_wind.size.x, 44.0)
	draft_label.add_theme_font_size_override("font_size", 28)
	draft_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	draft_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	var pill := StyleBoxFlat.new()
	pill.bg_color = DRAFT_COLOR
	pill.set_corner_radius_all(22)
	draft_label.add_theme_stylebox_override("normal", pill)
	draft_label.visible = false
	add_child(draft_label)


## Blocs segment et bonus (Lot T9), sous le panneau de droite, même largeur, cachés au départ.
func _build_segment_blocks() -> void:
	var top := 20.0 + 320.0 + BLOCK_GAP
	panel_segment = _create_panel(Vector2(-320.0, top), Vector2(300.0, 100.0), true, false)
	panel_segment.name = "SegmentPanel"
	panel_segment.visible = false
	segment_title = _block_label(panel_segment, "SegmentTitle", Vector2(10.0, 4.0), 22)
	segment_main = _block_label(panel_segment, "SegmentMain", Vector2(10.0, 30.0), 36)
	segment_detail = _block_label(panel_segment, "SegmentDetail", Vector2(10.0, 70.0), 20)
	panel_bonus = _create_panel(Vector2(-320.0, top + 100.0 + BLOCK_GAP), Vector2(300.0, 72.0), true, false)
	panel_bonus.name = "BonusPanel"
	panel_bonus.visible = false
	bonus_held = _block_label(panel_bonus, "BonusHeld", Vector2(10.0, 4.0), 26)
	bonus_active = _block_label(panel_bonus, "BonusActive", Vector2(10.0, 36.0), 20)
	bonus_bar = Control.new()
	bonus_bar.name = "BonusBar"
	bonus_bar.position = Vector2(10.0, 62.0)
	bonus_bar.size = Vector2(280.0, 6.0)
	bonus_bar.draw.connect(_on_bonus_bar_draw)
	panel_bonus.add_child(bonus_bar)


func _block_label(parent: Control, node_name: String, pos: Vector2, font_size: int) -> Label:
	var l := Label.new()
	l.name = node_name
	l.position = pos
	l.size = Vector2(280.0, font_size * 1.3)
	l.add_theme_font_size_override("font_size", font_size)
	l.clip_text = true
	parent.add_child(l)
	return l


## Blocs segment et bonus (Lot T9) : `view` est la sortie de segment_hud_model.view().
func update_segment(view: Dictionary) -> void:
	_build_ui()
	var seg: Dictionary = view.get("segment", {})
	var mode := str(seg.get("mode", ""))
	panel_segment.visible = mode != ""
	if mode != "":
		segment_title.text = str(seg.get("title", ""))
		segment_main.text = str(seg.get("main", ""))
		segment_main.visible = segment_main.text != ""
		segment_detail.text = str(seg.get("detail", ""))
		segment_detail.modulate = SEGMENT_TONES.get(str(seg.get("tone", "")), SEGMENT_TONES[""])
		segment_main.modulate = SEGMENT_TONES["good"] if mode == "result" and str(seg.get("tone", "")) == "good" else SEGMENT_TONES[""]
	var pu: Dictionary = view.get("powerup", {})
	panel_bonus.visible = bool(pu.get("visible", false))
	if panel_bonus.visible:
		var held := str(pu.get("held_text", ""))
		var active := str(pu.get("active_text", ""))
		bonus_held.text = held if held != "" else active
		bonus_active.text = active if held != "" else ""
		bonus_active.visible = bonus_active.text != ""
		var fraction := float(pu.get("fraction", 0.0)) if active != "" else 0.0
		bonus_bar.visible = active != ""
		if absf(fraction - _bonus_fraction) > 0.005:
			_bonus_fraction = fraction
			bonus_bar.queue_redraw()


func _on_bonus_bar_draw() -> void:
	bonus_bar.draw_rect(Rect2(Vector2.ZERO, bonus_bar.size), Color(1, 1, 1, 0.15))
	bonus_bar.draw_rect(Rect2(Vector2.ZERO, Vector2(bonus_bar.size.x * _bonus_fraction, bonus_bar.size.y)), BONUS_COLOR)


## Indicateur du vent (Lot P16) et de l'abri (Lot P17) : `view` est la sortie de wind_view_model.view().
func update_wind(view: Dictionary) -> void:
	_build_ui()
	var shown := bool(view.get("visible", false)) and str(view.get("speed_text", "")) != ""
	panel_wind.visible = shown
	var draft := str(view.get("draft_text", ""))
	draft_label.visible = draft != ""
	if draft != "":
		draft_label.text = draft
		var top := panel_wind.position.y + (panel_wind.size.y + DRAFT_GAP if shown else 0.0)
		draft_label.position = Vector2(panel_wind.position.x, top)
	if not shown:
		_wind_view = {}
		return
	var changed: bool = view.get("arrow_deg") != _wind_view.get("arrow_deg") or view.get("level") != _wind_view.get("level")
	_wind_view = view.duplicate()
	var label := str(view.get("label", ""))
	wind_speed_label.text = (str(view["speed_text"]) + " " + label).strip_edges()
	wind_level_label.text = str(view.get("level_text", ""))
	wind_verdict_label.text = str(view.get("verdict_text", ""))
	var pill := wind_verdict_label.get_theme_stylebox("normal") as StyleBoxFlat
	if pill != null:
		pill.bg_color = WIND_TONES.get(str(view.get("tone", "neutral")), WIND_TONES["neutral"])
	if changed:
		wind_arrow.queue_redraw()
		wind_bars.queue_redraw()


## Flèche dans le sens où souffle le vent, vue du cycliste (route vers le haut) : vent de face, flèche
## vers le bas ; vent de droite, flèche vers la gauche.
func _on_wind_arrow_draw() -> void:
	var c := wind_arrow.size * 0.5
	wind_arrow.draw_circle(c, 34.0, Color(1, 1, 1, 0.10))
	if _wind_view.is_empty():
		return
	# arrow_deg : d'où vient le vent (0 = de face) ; la flèche pointe là où il va.
	var a := deg_to_rad(float(_wind_view.get("arrow_deg", 0.0)))
	var from_dir := Vector2(sin(a), -cos(a))       # direction d'où il vient, à l'écran (haut = devant)
	var to_dir := -from_dir
	var tip := c + to_dir * 28.0
	var tail := c - to_dir * 24.0
	var col: Color = WIND_TONES.get(str(_wind_view.get("tone", "neutral")), WIND_TONES["neutral"]).lightened(0.35)
	wind_arrow.draw_line(tail, tip - to_dir * 10.0, col, 7.0, true)
	var side := Vector2(-to_dir.y, to_dir.x)
	wind_arrow.draw_colored_polygon(PackedVector2Array([tip, tip - to_dir * 18.0 + side * 13.0,
		tip - to_dir * 18.0 - side * 13.0]), col)


## Barres d'intensité : une par niveau au-delà du calme (quatre en tout).
func _on_wind_bars_draw() -> void:
	var level := int(_wind_view.get("level", 0))
	var n := 4
	var w := wind_bars.size.x / float(n)
	for i in range(n):
		var h := wind_bars.size.y * float(i + 1) / float(n)
		var r := Rect2(i * w + 2.0, wind_bars.size.y - h, w - 4.0, h)
		wind_bars.draw_rect(r, WIND_BAR_COLOR if i < level else WIND_BAR_OFF)


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
		p.offset_right = pos.x + size.x   # size.x négatif : marge droite égale à la marge gauche
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
		erg_label.visible = show_erg_line and lines.get("erg", "") != ""

	if target_val != null:
		# Même texte que la ligne de puissance du HUD d'origine (« 230 W » ou « roue libre »).
		var has_target: bool = lines["power"].contains("CIBLE ERG: ")
		target_val.text = lines["power"].get_slice("CIBLE ERG: ", 1) if has_target else HudViewModel.NO_VALUE
		target_val.get_parent().visible = has_target

	if status_label != null:
		var pause = state.get("pause_reason", null)
		status_label.text = "ÉTAT: %s%s | TRAINER: %s | ENTRÉE: %s" % [
			state.get("session_state", "?"),
			(" (" + str(pause) + ")") if pause != null else "",
			state.get("trainer_status", "?"),
			state.get("input_status", "?")]

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
