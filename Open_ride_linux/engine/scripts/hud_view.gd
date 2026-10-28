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
## - Lot O7 : encart des bots (`update_bots`, sortie de bots_view_model.view()) sous le panneau de
##   droite et points colorés des bots sur le profil d'altitude ; caché sans bot.
## - Lot T15 : l'encart suit bot_hud_model.gd : voisins immédiats (triangle vers le haut devant, vers le
##   bas derrière, nom, écart « +8,4 s »), puis une ligne par bot (pastille du maillot, nom et profil,
##   FTP en W et en W/kg, écart, jauge de réserve W′), puis les porteurs des maillots. Colonne de droite
##   empilée sous le panneau de droite (`_layout_right_column`) : bloc segment, bloc bonus, encart des
##   bots, qui s'arrête au-dessus du profil d'altitude (ou du bandeau ERG) ; les lignes de bots qui ne
##   tiennent pas sont cachées, les voisins restent.

const UiTheme := preload("res://scripts/ui_theme.gd")
const HudViewModel := preload("res://scripts/hud_view_model.gd")
const BotsViewModel := preload("res://scripts/bots_view_model.gd")
const BotHudModel := preload("res://scripts/bot_hud_model.gd")
const ErgView := preload("res://scripts/erg_view.gd")

const COLOR_DESCENT := UiTheme.GRADE_DESCENT
const COLOR_FLAT := UiTheme.GRADE_FLAT
const COLOR_CLIMB := UiTheme.GRADE_CLIMB
const COLOR_STEEP := UiTheme.GRADE_STEEP
const COLOR_WALL := UiTheme.GRADE_WALL

const WIND_TONES := {
	"good": UiTheme.WIND_GOOD,
	"bad": UiTheme.WIND_BAD,
	"neutral": UiTheme.WIND_NEUTRAL,
}
const WIND_BAR_COLOR := UiTheme.PALE
const DRAFT_COLOR := UiTheme.DRAFT
const DRAFT_GAP := 10.0
const WIND_BAR_OFF := UiTheme.WIND_BAR_OFF
const SEGMENT_TONES := {"good": UiTheme.SEGMENT_GOOD, "bad": UiTheme.SEGMENT_BAD, "": UiTheme.SEGMENT_NEUTRAL}
const BONUS_COLOR := UiTheme.BONUS   # violet des arches de bonus (lot T8)
const BLOCK_GAP := 8.0
## Haut de la colonne de droite (sous le panneau de droite) et réserve du bas : profil d'altitude, ou
## bandeau ERG au-dessus de lui.
const RIGHT_COLUMN_TOP := 20.0 + 320.0 + BLOCK_GAP
const PROFILE_RESERVE := 120.0
const ERG_RESERVE := ErgView.BOTTOM_OFFSET + ErgView.PANEL_HEIGHT
const JERSEY_COLORS := {"sprint": UiTheme.JERSEY_SPRINT, "kom": UiTheme.JERSEY_KOM}
const KOM_DOT := UiTheme.KOM_DOT
const WBAL_BG := UiTheme.TRACK
const WBAL_COLOR := UiTheme.WBAL

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
# Encart des bots (lots O7 et T15)
var panel_bots: Panel
var neighbor_labels: Array[Label] = []
var neighbor_gaps: Array[Label] = []
var neighbor_arrows: Array[Control] = []
var bots_lines: Array[Label] = []
var bots_gaps: Array[Label] = []
var bots_jerseys: Array[ColorRect] = []
var bots_kom_dots: Array[ColorRect] = []
var bots_wbal_bg: Array[ColorRect] = []
var bots_wbal: Array[ColorRect] = []
var jerseys_label: Label
var _bots_view: Array = []
var _bots_hud: Dictionary = {}
var _erg_active := false
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
	_build_bots_panel()
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
	# Haut à 4 px : le libellé de 30 px grandit à 43 px de haut, il s'arrête ainsi à 47 px, au-dessus
	# du niveau (50 px), à toutes les échelles de l'interface (chevauchement vu en 1024x600)
	wind_speed_label.position = Vector2(92.0, 4.0)
	wind_speed_label.size = Vector2(200.0, 43.0)
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
	wind_level_label.position = Vector2(172.0, 50.0)
	wind_level_label.size = Vector2(120.0, 32.0)
	wind_level_label.add_theme_font_size_override("font_size", 22)
	wind_level_label.modulate = UiTheme.HUD_DIM
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


## Encart des bots (lots O7 et T15), sous le panneau de droite (même largeur), caché tant qu'il n'y a pas
## de bot. Lignes placées par _layout_bots_panel().
func _build_bots_panel() -> void:
	panel_bots = _create_panel(Vector2(-320.0, RIGHT_COLUMN_TOP), Vector2(300.0, 100.0), true, false)
	panel_bots.name = "BotsPanel"
	panel_bots.visible = false
	for i in range(2):
		var arrow := Control.new()
		arrow.size = Vector2(16.0, 16.0)
		arrow.set_meta("dir", "ahead")
		arrow.draw.connect(func() -> void: _draw_neighbor_arrow(arrow))
		panel_bots.add_child(arrow)
		neighbor_arrows.append(arrow)
		neighbor_labels.append(_bots_label(Vector2(178.0, BotHudModel.NEIGHBOR_ROW), 18))
		var gap := _bots_label(Vector2(80.0, BotHudModel.NEIGHBOR_ROW), 18)
		gap.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		neighbor_gaps.append(gap)
	for i in range(BotsViewModel.MAX_LINES):
		var swatch := ColorRect.new()
		swatch.size = Vector2(10.0, 18.0)
		panel_bots.add_child(swatch)
		bots_jerseys.append(swatch)
		var dot := ColorRect.new()
		dot.size = Vector2(4.0, 4.0)
		dot.position = Vector2(3.0, 7.0)
		dot.color = KOM_DOT
		swatch.add_child(dot)
		bots_kom_dots.append(dot)
		bots_lines.append(_bots_label(Vector2(184.0, 26.0), 18))
		var gap := _bots_label(Vector2(80.0, 26.0), 18)
		gap.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		bots_gaps.append(gap)
		var bg := ColorRect.new()
		bg.size = Vector2(264.0, 3.0)
		bg.color = WBAL_BG
		panel_bots.add_child(bg)
		bots_wbal_bg.append(bg)
		var fill := ColorRect.new()
		fill.size = Vector2(0.0, 3.0)
		fill.color = WBAL_COLOR
		bg.add_child(fill)
		bots_wbal.append(fill)
	jerseys_label = _bots_label(Vector2(280.0, BotHudModel.JERSEY_ROW), 16)


func _bots_label(box_size: Vector2, font_size: int) -> Label:
	var l := Label.new()
	l.size = box_size
	l.add_theme_font_size_override("font_size", font_size)
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.clip_text = true
	l.visible = false
	panel_bots.add_child(l)
	return l


## Triangle plein vers le haut (voisin devant) ou vers le bas (voisin derrière).
func _draw_neighbor_arrow(arrow: Control) -> void:
	var w := arrow.size.x
	var h := arrow.size.y
	var pts := PackedVector2Array([Vector2(w / 2.0, 1.0), Vector2(w - 1.0, h - 2.0), Vector2(1.0, h - 2.0)])
	if str(arrow.get_meta("dir", "ahead")) == "behind":
		pts = PackedVector2Array([Vector2(1.0, 2.0), Vector2(w - 1.0, 2.0), Vector2(w / 2.0, h - 1.0)])
	arrow.draw_colored_polygon(pts, Color.WHITE)   # teinte : modulate du nœud


## Encart et repères du profil : `view` est la sortie de bots_view_model.view(), `race` celle de
## bots_view_model.race() (voisins et maillots).
func update_bots(view: Array, race: Dictionary = {}) -> void:
	_build_ui()
	_bots_view = view
	_bots_hud = BotHudModel.view(view, race)
	panel_bots.visible = bool(_bots_hud["visible"])
	_layout_right_column()
	if profile_panel != null:
		profile_panel.queue_redraw()


## Hauteur de l'écran en unités du HUD : au moins 720 (étirement canvas_items et expand, base 1280 × 720).
func _screen_height() -> float:
	return maxf(get_viewport().get_visible_rect().size.y, 720.0) if is_inside_tree() else 720.0


func _place(p: Control, top: float, h: float) -> void:
	p.offset_top = top
	p.offset_bottom = top + h


## Colonne de droite : blocs segment et bonus visibles empilés, puis l'encart des bots jusqu'au-dessus du
## profil d'altitude (ou du bandeau ERG).
func _layout_right_column() -> void:
	var y := RIGHT_COLUMN_TOP
	for p in [panel_segment, panel_bonus]:
		if p != null and p.visible:
			var h: float = p.offset_bottom - p.offset_top
			_place(p, y, h)
			y += h + BLOCK_GAP
	if panel_bots != null and panel_bots.visible:
		var bottom: float = _screen_height() - (ERG_RESERVE if _erg_active else PROFILE_RESERVE) - BLOCK_GAP
		_layout_bots_panel(y, bottom - y)


func _layout_bots_panel(top: float, avail: float) -> void:
	var v := _bots_hud
	var neighbors: Array = v["neighbors"]
	var rows: Array = v["rows"]
	var n_rows := BotHudModel.rows_that_fit(v, avail)
	var jerseys := str(v["jerseys_text"])
	var show_jerseys := jerseys != "" and BotHudModel.height(v, 0) <= avail
	var y := BotHudModel.PADDING / 2.0
	for i in range(neighbor_labels.size()):
		var shown := i < neighbors.size()
		neighbor_labels[i].visible = shown
		neighbor_gaps[i].visible = shown
		neighbor_arrows[i].visible = shown
		if not shown:
			continue
		var nb: Dictionary = neighbors[i]
		neighbor_labels[i].text = str(nb["name"])
		neighbor_labels[i].modulate = nb["color"]
		neighbor_labels[i].position = Vector2(32.0, y)
		neighbor_gaps[i].text = str(nb["gap_text"])
		neighbor_gaps[i].position = Vector2(210.0, y)
		neighbor_arrows[i].position = Vector2(10.0, y + 6.0)
		neighbor_arrows[i].modulate = nb["color"]
		neighbor_arrows[i].set_meta("dir", nb["dir"])
		neighbor_arrows[i].queue_redraw()
		y += BotHudModel.NEIGHBOR_ROW
	for i in range(bots_lines.size()):
		var shown := i < n_rows
		var r: Dictionary = rows[i] if shown else {}
		var jersey := str(r.get("jersey", ""))
		var wbal := float(r.get("wbal", -1.0))
		bots_lines[i].visible = shown
		bots_gaps[i].visible = shown
		bots_jerseys[i].visible = shown and jersey != ""
		bots_kom_dots[i].visible = jersey == "kom"
		bots_wbal_bg[i].visible = shown and wbal >= 0.0
		if not shown:
			continue
		var detail := str(r["detail"])
		bots_lines[i].text = str(r["name"]) + ("  " + detail if detail != "" else "")
		bots_lines[i].modulate = r["color"]
		bots_lines[i].position = Vector2(26.0, y)
		bots_gaps[i].text = str(r["gap_text"])
		bots_gaps[i].position = Vector2(210.0, y)
		bots_jerseys[i].position = Vector2(10.0, y + 4.0)
		bots_jerseys[i].color = JERSEY_COLORS.get(jersey, Color.WHITE)
		bots_wbal_bg[i].position = Vector2(26.0, y + 26.0)
		bots_wbal[i].size.x = bots_wbal_bg[i].size.x * maxf(wbal, 0.0)
		y += BotHudModel.BOT_ROW
	jerseys_label.visible = show_jerseys
	if show_jerseys:
		jerseys_label.text = jerseys
		jerseys_label.position = Vector2(10.0, y)
		y += BotHudModel.JERSEY_ROW
	_place(panel_bots, top, y + BotHudModel.PADDING / 2.0)


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
	_layout_right_column()


func _on_bonus_bar_draw() -> void:
	bonus_bar.draw_rect(Rect2(Vector2.ZERO, bonus_bar.size), UiTheme.TRACK)
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
	wind_arrow.draw_circle(c, 34.0, UiTheme.TRACK_SOFT)
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
	style.bg_color = UiTheme.PANEL_BG
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
	lbl.modulate = UiTheme.HUD_DIM
	hbox.add_child(lbl)

	var val := Label.new()
	val.text = default_val
	val.add_theme_font_size_override("font_size", val_size)
	hbox.add_child(val)

	return val


## Met à jour les valeurs et le profil d'altitude.
func update_display(state: Dictionary, erg_eval: Dictionary, route: Variant = null, s: float = 0.0) -> void:
	_route = route
	_erg_active = state.get("erg") != null
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
	profile_panel.draw_rect(Rect2(0, 0, w, h), UiTheme.CHART_BG)

	var col_w := w / float(cols)
	for i in range(cols):
		var norm_h := clampf((float(alts[i]) - alt_min) / alt_range, 0.05, 0.95)
		var bar_h := norm_h * h
		var bar_rect := Rect2(i * col_w, h - bar_h, col_w + 0.5, bar_h)
		var col_grade: String = classes[i] if i < classes.size() else "flat"
		var color: Color = GRADE_COLORS.get(col_grade, COLOR_FLAT)
		profile_panel.draw_rect(bar_rect, color)

	# Bots (lot O7) : un point coloré à la hauteur du profil, selon l'écart au cycliste.
	var from_m: float = float(_profile_data.get("from_m", 0.0))
	var to_m: float = float(_profile_data.get("to_m", 0.0))
	if to_m > from_m:
		for mark in BotsViewModel.profile_marks(_bots_view, from_m, to_m):
			var idx := clampi(int(round((float(mark["rel_m"]) - from_m) / (to_m - from_m) * float(cols - 1))), 0, cols - 1)
			var bx := (idx + 0.5) * col_w
			var by := h - clampf((float(alts[idx]) - alt_min) / alt_range, 0.05, 0.95) * h
			profile_panel.draw_circle(Vector2(bx, by), 5.0, Color.BLACK)
			profile_panel.draw_circle(Vector2(bx, by), 3.5, mark["color"])

	# Repère de position
	if marker_idx >= 0 and marker_idx < cols:
		var mx := (marker_idx + 0.5) * col_w
		var my := h - clampf((float(alts[marker_idx]) - alt_min) / alt_range, 0.05, 0.95) * h
		profile_panel.draw_circle(Vector2(mx, my), 6.0, Color.WHITE)
		profile_panel.draw_circle(Vector2(mx, my), 3.0, Color.BLACK)
