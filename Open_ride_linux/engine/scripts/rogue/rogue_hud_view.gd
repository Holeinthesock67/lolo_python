extends Node3D

## Vue du HUD du Cyber-Rogue. Lot R11 : hologramme au-dessus de la roue ; lot R22 (lisibilité, maquettes validées
## le 12 novembre) : tout passe en surimpression à l'écran, hors du centre.
## - en haut à gauche, l'état : phase ou salle, distance ou compte à rebours, jauges (ennemi, bouclier,
##   adrénaline avec son seuil de 50, réserve W'), vitesse engagée, % de FTP, cadence, posture, étapes à venir ;
## - en haut à droite, le Firewall en secondes (vert, orange, rouge) ou la consigne de puissance ;
## - en bas, la consigne du moment et les boutons utiles ;
## - au centre haut, les retours des appuis (Z refusé et sa raison, verdict des arches), quelques secondes ;
## - à droite, la légende d'un objet la première fois qu'il apparaît ;
## - le bandeau « Salle manquée » et le grésillement rouge (R11) ;
## - lot R23 : anneau au centre à chaque Z court (or : accepté, rouge : refusé), pavé VITESSE en bas à droite dans
##   toutes les phases (s'allume à chaque changement), tendance de l'adrénaline sous sa jauge, nom de la vue.
## Ne calcule rien : elle dessine les valeurs de rogue_hud_model.gd (clé `guide` : rogue_guide_model.gd).

const Palette := preload("res://scripts/rogue/neon_palette.gd")
const UiTheme := preload("res://scripts/ui_theme.gd")

const BANNER_S := 3.0
const GLITCH_S := 0.5
const TOAST_S := 2.5
const LEGEND_S := 9.0
const BANNER_TEXT := "Salle manquée −10 or"
const PANEL_W := 400.0
const SIDE_W := 300.0
const LEGEND_W := 330.0
const PULSE_S := 0.45               # anneau du Z (lot R23)
const GEAR_FLASH_S := 0.6
const VIEW_NAME_S := 1.5


## Anneau qui s'ouvre au centre de l'écran à chaque Z court (lot R23) : or si accepté, rouge si refusé.
class ZPulse extends Control:
	var left_s := 0.0
	var color := Color.WHITE

	func _init() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		set_anchors_preset(Control.PRESET_FULL_RECT)

	func fire(c: Color) -> void:
		color = c
		left_s = PULSE_S
		queue_redraw()

	func tick(delta: float) -> void:
		if left_s <= 0.0:
			return
		left_s = maxf(left_s - delta, 0.0)
		queue_redraw()

	func _draw() -> void:
		if left_s <= 0.0:
			return
		var u := 1.0 - left_s / PULSE_S                 # 0 → 1 pendant l'anneau
		var c := size * Vector2(0.5, 0.68)             # sous le retour écrit, sur la route devant la roue
		var r := lerpf(36.0, minf(size.x, size.y) * 0.2, u)
		var col := Color(color, 0.9 * (1.0 - u))
		draw_arc(c, r, 0.0, TAU, 64, col, lerpf(14.0, 3.0, u), true)
		draw_arc(c, r * 0.72, 0.0, TAU, 48, Color(col, col.a * 0.5), lerpf(6.0, 1.5, u), true)


## Jauge horizontale : fond, remplissage, trait du seuil (adrénaline) et bord rouge quand elle est basse.
class GaugeBar extends Control:
	var frac := 0.0
	var color := Color.WHITE
	var mark := -1.0
	var warn := false

	func _init() -> void:
		custom_minimum_size = Vector2(150, 14)
		size_flags_horizontal = Control.SIZE_EXPAND_FILL
		size_flags_vertical = Control.SIZE_SHRINK_CENTER
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func set_values(f: float, c: Color, m: float, w: bool) -> void:
		if is_equal_approx(f, frac) and c == color and is_equal_approx(m, mark) and w == warn:
			return
		frac = clampf(f, 0.0, 1.0)
		color = c
		mark = m
		warn = w
		queue_redraw()

	func _draw() -> void:
		var r := Rect2(Vector2.ZERO, size)
		draw_rect(r, Color(1, 1, 1, 0.12))
		if frac > 0.0:
			draw_rect(Rect2(Vector2.ZERO, Vector2(size.x * frac, size.y)), color)
		if mark >= 0.0:
			draw_rect(Rect2(Vector2(size.x * mark - 1.5, -4.0), Vector2(3.0, size.y + 8.0)), Color.WHITE)
		if warn:
			draw_rect(r, Color(1.0, 0.23, 0.36), false, 2.0)


var preset := "low"
var adapted := false
var holo: Label                     # ligne de route : vitesse, % FTP, cadence, posture (nom gardé du lot R11)
var gauges: Label                   # étapes à venir (nom gardé du lot R11)
var banner: Label
var phase_label: Label              # titre du panneau : phase ou salle
var title_right: Label
var countdown: Label
var countdown_sub: Label
var countdown_row: HBoxContainer
var panel: PanelContainer
var bars := {}                      # nom -> [GaugeBar, Label de valeur]
var side_panel: PanelContainer
var side_title: Label
var side_big: Label
var side_sub: Label
var hint_panel: PanelContainer
var hint_label: Label
var keys_row: HBoxContainer
var toast_panel: PanelContainer
var toast_title: Label
var toast_sub: Label
var legend_panel: PanelContainer
var legend_title: Label
var legend_text: Label
var glitch_rect: ColorRect
var banner_left_s := 0.0
var glitch_left_s := 0.0
var toast_left_s := 0.0
var legend_left_s := 0.0
var _toasts: Array = []
var _layer: CanvasLayer
var _keys_key := ""
var z_pulse: ZPulse                 # lot R23
var gear_panel: PanelContainer
var gear_value: Label
var gear_title: Label
var gear_flash_s := 0.0
var _gear_shown := -1
var adr_trend_label: Label
var view_label: Label
var view_left_s := 0.0


func _ready() -> void:
	_layer = CanvasLayer.new()
	_layer.layer = 5
	add_child(_layer)
	glitch_rect = ColorRect.new()
	glitch_rect.color = Palette.color("danger", adapted)
	glitch_rect.color.a = 0.0
	glitch_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	glitch_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	_layer.add_child(glitch_rect)
	_build_panel()
	_build_side()
	_build_hint()
	_build_toast()
	_build_legend()
	_build_gear()
	z_pulse = ZPulse.new()
	z_pulse.name = "ZPulse"
	_layer.add_child(z_pulse)
	view_label = _lbl(26, UiTheme.TEXT)
	view_label.name = "ViewName"
	view_label.set_anchors_preset(Control.PRESET_CENTER)
	view_label.grow_horizontal = Control.GROW_DIRECTION_BOTH
	view_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	view_label.add_theme_constant_override("outline_size", 6)
	view_label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.8))
	view_label.visible = false
	_layer.add_child(view_label)
	banner = Label.new()
	banner.text = BANNER_TEXT
	banner.visible = false
	banner.add_theme_font_size_override("font_size", 36)
	banner.add_theme_color_override("font_color", Palette.color("danger", adapted))
	banner.add_theme_constant_override("outline_size", 8)
	banner.add_theme_color_override("font_outline_color", Palette.color("void", false))
	banner.set_anchors_preset(Control.PRESET_CENTER_TOP)
	banner.grow_horizontal = Control.GROW_DIRECTION_BOTH
	banner.position = Vector2(0.0, 170.0)
	banner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_layer.add_child(banner)
	set_style(preset, adapted)


static func _box_style(edge: Color) -> StyleBoxFlat:
	var st := StyleBoxFlat.new()
	st.bg_color = Color(0.04, 0.05, 0.16, 0.80)
	st.border_color = edge
	st.set_border_width_all(2)
	st.set_corner_radius_all(12)
	st.content_margin_left = 14
	st.content_margin_right = 14
	st.content_margin_top = 8
	st.content_margin_bottom = 10
	st.shadow_color = Color(edge, 0.25)
	st.shadow_size = 6
	return st


func _lbl(size: int, color: Color = UiTheme.TEXT, text: String = "") -> Label:
	var l := UiTheme.label(size, color, text)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


func _build_panel() -> void:
	panel = PanelContainer.new()
	panel.name = "StatePanel"
	panel.position = Vector2(16, 14)
	panel.custom_minimum_size = Vector2(PANEL_W, 0)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_layer.add_child(panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 5)
	panel.add_child(box)
	var row := HBoxContainer.new()
	box.add_child(row)
	phase_label = _lbl(20)
	phase_label.name = "PhaseLabel"
	phase_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(phase_label)
	title_right = _lbl(17, UiTheme.DIM)
	row.add_child(title_right)
	countdown_row = HBoxContainer.new()
	countdown_row.add_theme_constant_override("separation", 12)
	box.add_child(countdown_row)
	countdown = _lbl(42)
	countdown_row.add_child(countdown)
	countdown_sub = _lbl(17, UiTheme.DIM)
	countdown_sub.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	countdown_row.add_child(countdown_sub)
	for spec in [["enemy", "Ennemi"], ["shield", "Bouclier"], ["adrenaline", "Adrénaline"], ["wbal", "Réserve W'"]]:
		var r := HBoxContainer.new()
		r.add_theme_constant_override("separation", 8)
		box.add_child(r)
		var name := _lbl(16, UiTheme.TEXT, spec[1])
		name.custom_minimum_size = Vector2(96, 0)
		r.add_child(name)
		var g := GaugeBar.new()
		r.add_child(g)
		var val := _lbl(16)
		val.custom_minimum_size = Vector2(70, 0)
		val.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		r.add_child(val)
		bars[spec[0]] = [g, val, r]
		if spec[0] == "adrenaline":   # lot R23 : la tendance (monte, stable, fond) sous la jauge
			adr_trend_label = _lbl(15, UiTheme.DIM)
			adr_trend_label.name = "AdrenalineTrend"
			adr_trend_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
			box.add_child(adr_trend_label)
	holo = _lbl(19)
	holo.name = "Hologram"
	box.add_child(holo)
	gauges = _lbl(16, UiTheme.DIM)
	gauges.name = "Gauges"
	gauges.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	gauges.custom_minimum_size = Vector2(PANEL_W - 30, 0)
	box.add_child(gauges)


func _build_side() -> void:
	side_panel = PanelContainer.new()
	side_panel.name = "SidePanel"
	side_panel.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	side_panel.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	side_panel.offset_right = -16
	side_panel.offset_top = 14
	side_panel.custom_minimum_size = Vector2(SIDE_W, 0)
	side_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_layer.add_child(side_panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 2)
	side_panel.add_child(box)
	side_title = _lbl(16, UiTheme.DIM)
	box.add_child(side_title)
	side_big = _lbl(32)
	box.add_child(side_big)
	side_sub = _lbl(16)
	box.add_child(side_sub)


func _build_hint() -> void:
	var col := VBoxContainer.new()
	col.name = "HintBar"
	col.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	col.offset_top = -104
	col.offset_bottom = -12
	col.alignment = BoxContainer.ALIGNMENT_END
	col.add_theme_constant_override("separation", 8)
	col.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_layer.add_child(col)
	hint_panel = PanelContainer.new()
	hint_panel.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	hint_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	col.add_child(hint_panel)
	hint_label = _lbl(24)
	hint_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint_panel.add_child(hint_label)
	keys_row = HBoxContainer.new()
	keys_row.alignment = BoxContainer.ALIGNMENT_CENTER
	keys_row.add_theme_constant_override("separation", 12)
	keys_row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	col.add_child(keys_row)


func _build_toast() -> void:
	toast_panel = PanelContainer.new()
	toast_panel.name = "Toast"
	toast_panel.set_anchors_preset(Control.PRESET_CENTER_TOP)
	toast_panel.grow_horizontal = Control.GROW_DIRECTION_BOTH
	toast_panel.offset_top = 290
	toast_panel.visible = false
	toast_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_layer.add_child(toast_panel)
	var box := VBoxContainer.new()
	box.alignment = BoxContainer.ALIGNMENT_CENTER
	toast_panel.add_child(box)
	toast_title = _lbl(32)
	toast_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(toast_title)
	toast_sub = _lbl(18)
	toast_sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	toast_sub.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	toast_sub.custom_minimum_size = Vector2(480, 0)
	box.add_child(toast_sub)


func _build_legend() -> void:
	legend_panel = PanelContainer.new()
	legend_panel.name = "Legend"
	legend_panel.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	legend_panel.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	legend_panel.offset_right = -16
	legend_panel.offset_top = 150
	legend_panel.custom_minimum_size = Vector2(LEGEND_W, 0)
	legend_panel.visible = false
	legend_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_layer.add_child(legend_panel)
	var box := VBoxContainer.new()
	legend_panel.add_child(box)
	legend_title = _lbl(19, UiTheme.GOLD)
	box.add_child(legend_title)
	legend_text = _lbl(16)
	legend_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	legend_text.custom_minimum_size = Vector2(LEGEND_W - 30, 0)
	box.add_child(legend_text)


## Pavé VITESSE (lot R23) : en bas à droite, au-dessus des boutons, visible dans toutes les phases.
func _build_gear() -> void:
	gear_panel = PanelContainer.new()
	gear_panel.name = "GearPanel"
	gear_panel.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	gear_panel.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	gear_panel.grow_vertical = Control.GROW_DIRECTION_BEGIN
	gear_panel.offset_right = -16
	gear_panel.offset_bottom = -116
	gear_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_layer.add_child(gear_panel)
	var box := VBoxContainer.new()
	box.alignment = BoxContainer.ALIGNMENT_CENTER
	box.add_theme_constant_override("separation", 0)
	gear_panel.add_child(box)
	gear_title = _lbl(15, UiTheme.DIM, "VITESSE")
	gear_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(gear_title)
	gear_value = _lbl(52, UiTheme.TEXT, "06")
	gear_value.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(gear_value)


## Anneau du Z court de la trame (« ok » ou « refused », lot R23).
func pulse(kind: String) -> void:
	if z_pulse == null or kind == "":
		return
	z_pulse.fire(UiTheme.GOLD if kind == "ok" else UiTheme.DANGER)


## Nom de la vue, 1,5 s au centre, à chaque changement (lot R23).
func show_view_name(text: String) -> void:
	if view_label == null:
		return
	view_label.text = "Vue : %s" % text
	view_left_s = VIEW_NAME_S


func set_style(new_preset: String, new_adapted: bool) -> void:
	preset = new_preset
	adapted = new_adapted
	if panel == null:
		return
	panel.add_theme_stylebox_override("panel", _box_style(Color(Palette.color("player", adapted), 0.55)))
	gear_panel.add_theme_stylebox_override("panel", _box_style(Color(Palette.color("player", adapted), 0.55)))
	hint_panel.add_theme_stylebox_override("panel", _box_style(Color(1, 1, 1, 0.25)))
	legend_panel.add_theme_stylebox_override("panel", _box_style(Palette.color("gold", adapted)))


func _tone(t: String) -> Color:
	match t:
		"ok":
			return UiTheme.OK
		"warn":
			return UiTheme.WARN
		"danger":
			return UiTheme.DANGER
	return UiTheme.FOCUS


## Affiche les valeurs du modèle. `bike_pos` : gardé pour l'appelant (le HUD n'est plus posé sur le vélo).
func apply(values: Dictionary, bike_pos: Vector3, delta: float) -> void:
	if panel == null:
		return
	visible = bool(values.get("active", false)) and not bool(values.get("paused", false))
	_layer.visible = visible
	if not visible:
		return
	position = bike_pos
	var g: Dictionary = values.get("guide", {})
	var phase := str(values.get("phase", ""))
	var choosing: bool = not (values.get("corridor", {}) as Dictionary).is_empty()
	# Couloir et relique : l'écran des cartes occupe le haut ; le panneau d'état se retire (R11 : il transparaissait).
	panel.visible = bool(g.get("panel", true)) and not choosing
	phase_label.visible = panel.visible
	holo.visible = panel.visible
	gauges.visible = panel.visible and not (g.get("next_lines", []) as Array).is_empty()
	phase_label.text = str(g.get("title", ""))
	title_right.text = str(g.get("title_right", ""))
	countdown.text = str(g.get("countdown", ""))
	countdown_sub.text = str(g.get("countdown_label", ""))
	countdown_row.visible = countdown.text != ""
	var fight := phase in ["ROOM", "BOSS", "RECOVERY"]
	_bar("enemy", fight and bool(values.get("has_enemy", false)), float(values.get("enemy_pct", 0.0)) / 100.0,
		"danger", "%d %%" % int(roundf(float(values.get("enemy_pct", 0.0)))), -1.0, false)
	_bar("shield", fight, float(values.get("shield_frac", 0.0)), "parry", str(values.get("shield_text", "")), -1.0,
		float(values.get("shield_frac", 1.0)) < 0.25)
	_bar("adrenaline", fight, float(values.get("adrenaline_frac", 0.0)), "gold", str(values.get("adrenaline_text", "")),
		float(values.get("adrenaline_z_mark", 0.5)), false)
	_bar("wbal", phase != "CORRIDOR", float(values.get("wbal_pct", 0.0)) / 100.0, "energy",
		"%d %%" % int(roundf(float(values.get("wbal_pct", 0.0)))), -1.0, bool(values.get("wbal_low", false)))
	holo.text = "Vitesse %s   %s FTP   %s rpm   %s" % [values.get("gear_text", ""), values.get("power_pct_text", ""),
		values.get("cadence_text", ""), values.get("posture_text", "")]
	holo.modulate = Palette.color(str(values.get("posture_token", "neutral")), adapted)
	var trend := str(g.get("adr_trend", ""))
	adr_trend_label.text = trend
	adr_trend_label.visible = fight and trend != ""
	adr_trend_label.add_theme_color_override("font_color", UiTheme.DANGER if bool(values.get("overheat", false)) else UiTheme.DIM)
	var gear := int(values.get("gear", 1))
	if gear != _gear_shown:
		if _gear_shown >= 0:
			gear_flash_s = GEAR_FLASH_S
		_gear_shown = gear
		gear_value.text = "%02d" % gear
	gauges.text = "\n".join(g.get("next_lines", []))
	_side(g, choosing)
	_hint(g)
	_tick(delta)


## Retours des appuis et légende nouvelle de la trame (rogue_guide_model.gd : take_toasts, take_legend).
func push_feedback(toasts: Array, legend: Array) -> void:
	_toasts.append_array(toasts)
	if legend.size() == 2 and legend_title != null:
		legend_title.text = str(legend[0])
		legend_text.text = str(legend[1])
		legend_left_s = LEGEND_S


func _bar(key: String, show: bool, frac: float, token: String, text: String, mark: float, warn: bool) -> void:
	var b: Array = bars[key]
	(b[2] as Control).visible = show
	if show:
		(b[0] as GaugeBar).set_values(frac, Palette.color(token, adapted), mark, warn)
		(b[1] as Label).text = text


func _side(g: Dictionary, choosing: bool) -> void:
	var fw: Dictionary = g.get("fw", {})
	var cons: Dictionary = g.get("consigne", {})
	if not fw.is_empty() and not choosing:
		side_panel.visible = true
		var c := _tone({"ok": "ok", "warn": "warn", "danger": "danger"}.get(str(fw.get("level", "ok")), "ok"))
		side_title.text = "Firewall derrière toi"
		side_big.text = str(fw.get("text", ""))
		side_big.add_theme_color_override("font_color", c)
		side_sub.text = str(fw.get("sub", ""))
		side_panel.add_theme_stylebox_override("panel", _box_style(c))
	elif not cons.is_empty() and not choosing:
		side_panel.visible = true
		var c2 := _tone("ok" if bool(cons.get("ok", false)) else "warn")
		side_title.text = "Consigne"
		side_big.text = str(cons.get("big", ""))
		side_big.add_theme_color_override("font_color", c2)
		side_sub.text = str(cons.get("sub", ""))
		side_panel.add_theme_stylebox_override("panel", _box_style(Color(Palette.color("player", adapted), 0.55)))
	else:
		side_panel.visible = false


func _hint(g: Dictionary) -> void:
	hint_label.text = str(g.get("hint", ""))
	hint_panel.visible = hint_label.text != ""
	var tone := str(g.get("tone", "info"))
	hint_panel.add_theme_stylebox_override("panel", _box_style(Color(1, 1, 1, 0.25) if tone == "info" else _tone(tone)))
	var keys: Array = g.get("keys", [])
	var key := str(keys.hash())
	if key == _keys_key:
		return
	_keys_key = key
	for c in keys_row.get_children():
		keys_row.remove_child(c)
		c.queue_free()
	for k in keys:
		var chip := PanelContainer.new()
		var on: bool = str(k[2]) == "on"
		chip.add_theme_stylebox_override("panel", UiTheme.chip_style(Palette.color("gold", adapted) if on else UiTheme.LINE))
		chip.modulate.a = 0.5 if str(k[2]) == "off" else 1.0
		chip.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 6)
		chip.add_child(row)
		var cap := PanelContainer.new()
		# Une seule couleur pour l'action à faire : le cadre or du bouton ; la touche garde son bord neutre (R22).
		cap.add_theme_stylebox_override("panel", UiTheme.keycap_style(false))
		cap.add_child(_lbl(16, UiTheme.TEXT, str(k[0])))
		row.add_child(cap)
		row.add_child(_lbl(16, UiTheme.TEXT, str(k[1])))
		keys_row.add_child(chip)


## Événements à montrer : « room_skipped » affiche le bandeau 3 s et grésille en rouge 0,5 s.
func show_events(events: Array) -> void:
	if banner == null:
		return
	if "room_skipped" in events:
		banner_left_s = BANNER_S
		glitch_left_s = GLITCH_S
		banner.visible = true


func _tick(delta: float) -> void:
	banner_left_s = maxf(banner_left_s - delta, 0.0)
	glitch_left_s = maxf(glitch_left_s - delta, 0.0)
	banner.visible = banner_left_s > 0.0
	# Un seul éclair rouge de 0,25 s dans la demi-seconde : bien sous le plafond de 3 éclairs par seconde.
	var lit := glitch_left_s > 0.0 and int(glitch_left_s * 4.0) % 2 == 1
	glitch_rect.color.a = 0.35 if lit else 0.0
	toast_left_s = maxf(toast_left_s - delta, 0.0)
	# Retour d'un Z (lot R23) : il passe tout de suite, devant les retours en attente.
	var urgent := -1
	for i in _toasts.size():
		if bool(_toasts[i].get("now", false)):
			urgent = i
	if urgent >= 0:
		var u: Dictionary = _toasts[urgent]
		_toasts = _toasts.filter(func(t): return not bool(t.get("now", false)))
		_toasts.push_front(u)
		toast_left_s = 0.0
	if toast_left_s <= 0.0 and not _toasts.is_empty():
		var t: Dictionary = _toasts.pop_front()
		if _toasts.size() > 2:          # pas de file sans fin : seuls les retours récents comptent
			_toasts = _toasts.slice(_toasts.size() - 2)
		var c := _tone(str(t.get("tone", "info")))
		toast_title.text = str(t.get("title", ""))
		toast_title.add_theme_color_override("font_color", c)
		toast_sub.text = str(t.get("sub", ""))
		toast_sub.visible = toast_sub.text != ""
		toast_panel.add_theme_stylebox_override("panel", _box_style(c))
		toast_left_s = TOAST_S
	toast_panel.visible = toast_left_s > 0.0
	z_pulse.tick(delta)
	gear_flash_s = maxf(gear_flash_s - delta, 0.0)
	var lit_gear := gear_flash_s > 0.0
	gear_value.add_theme_color_override("font_color", UiTheme.GOLD if lit_gear else UiTheme.TEXT)
	gear_panel.scale = Vector2.ONE * (1.0 + 0.12 * gear_flash_s / GEAR_FLASH_S)
	gear_panel.pivot_offset = gear_panel.size * 0.5
	view_left_s = maxf(view_left_s - delta, 0.0)
	view_label.visible = view_left_s > 0.0
	legend_left_s = maxf(legend_left_s - delta, 0.0)
	legend_panel.visible = legend_left_s > 0.0 and panel.visible   # jamais sur les cartes du couloir
