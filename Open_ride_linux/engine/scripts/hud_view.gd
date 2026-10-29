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
## - Lot T15 : l'encart suit bot_hud_model.gd : une ligne par bot (pastille du maillot, nom et profil,
##   FTP en W et en W/kg, triangle des voisins immédiats, vers le haut devant, vers le bas derrière,
##   écart « +8,4 s », jauge de réserve W′), puis les porteurs des maillots. Colonne de droite empilée
##   sous le panneau de droite (`_layout_right_column`) : bloc segment, bloc bonus, encart des bots, qui
##   s'arrête au-dessus du profil d'altitude (ou du bandeau ERG). Lot X22 : blocs segment et bonus à la
##   hauteur de leur contenu ; quand la place manque, l'encart garde les deux lignes autour du cycliste
##   (ses voisins, avec maillot et W′), puis les maillots, puis les autres lignes.

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
const BLOCK_PAD := 4.0
## Profil d'altitude (SIM seulement : caché en ERG, où la pente n'agit pas sur le trainer) : depuis le
## 29/10, sous le panneau de droite et de sa largeur, en tête de la colonne de droite (avant : bandeau en
## bas de l'écran, sur toute la largeur). Hauteur, marge du bas de l'écran (bas de l'encart des bots).
const PROFILE_H := 57.0
const PROFILE_LABEL_W := 52.0   # colonne des altitudes haute et basse, à gauche des barres
const SCREEN_BOTTOM := 15.0
## Trois panneaux du haut (colonnes gauche et droite, bandeau central) : réduits deux fois de 10 %,
## polices comprises (300 de large jusqu'au 28/10, 270 le 28/10, 243 le 29/10) pour moins couvrir la
## route, et hauteur ajustée au contenu (_fit_top_panels). Marge à l'écran, largeur des colonnes,
## hauteurs de départ, marge intérieure, police minimale d'une valeur réduite pour tenir dans la colonne
## (« 152 W (98 %) »).
const TOP_MARGIN := 20.0
const COLUMN_W := 243.0
const COLUMN_H := 259.0
const CENTER_H := 89.0
const CENTER_PAD := 6.0
const COLUMN_PAD := 8.0
const METRIC_SEP := 10.0
const METRIC_MIN_FONT := 16
## Blocs sous les colonnes (vent, abri, encart des bots, segment, bonus) : construits sur BLOCK_W et
## réduits à l'affichage (scale) pour garder la largeur des colonnes, polices comprises.
const BLOCK_W := 300.0
const BLOCK_SCALE := COLUMN_W / BLOCK_W
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
## Teintes de texte des classes de pente (valeur de la pente du HUD, carrefours) : mêmes teintes que les
## barres du profil, éclaircies et opaques, pour au moins 4,5:1 sur un panneau au-dessus d'un ciel clair
## (lot X22 : 3,0 à 4,1:1 avec les couleurs des barres).
const GRADE_TEXT_COLORS := {
	"descent": UiTheme.GRADE_TEXT_DESCENT,
	"flat": UiTheme.GRADE_TEXT_FLAT,
	"climb": UiTheme.GRADE_TEXT_CLIMB,
	"steep": UiTheme.GRADE_TEXT_STEEP,
	"wall": UiTheme.GRADE_TEXT_WALL,
}

## Teintes du texte de la puissance et de la fréquence cardiaque par zone (Z1 en premier).
const ZONE_TEXT_COLORS := [UiTheme.ZONE_TEXT_1, UiTheme.ZONE_TEXT_2, UiTheme.ZONE_TEXT_3, UiTheme.ZONE_TEXT_4,
	UiTheme.ZONE_TEXT_5, UiTheme.ZONE_TEXT_6, UiTheme.ZONE_TEXT_7]

var vm := HudViewModel.new()
## FTP et FC max de la config de hello_ack (main.gd) : zones de la puissance et de la fréquence cardiaque.
var ftp_w := 0.0
var hr_max_bpm := 0.0

# Panneaux principaux
var panel_left: Panel
var panel_right: Panel
var panel_center: Panel
var _column_boxes: Array[VBoxContainer] = []   # contenus des colonnes gauche et droite
var _center_box: VBoxContainer

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
var bots_arrows: Array[Control] = []
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
	panel_left = _create_panel(Vector2(TOP_MARGIN, TOP_MARGIN), Vector2(COLUMN_W, COLUMN_H), false, false)
	var left_vbox := VBoxContainer.new()
	left_vbox.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT, Control.PRESET_MODE_KEEP_SIZE, int(COLUMN_PAD))
	_column_boxes.append(left_vbox)
	panel_left.add_child(left_vbox)

	power_val = _create_metric(left_vbox, "PUISSANCE (W)", HudViewModel.NO_VALUE)
	cadence_val = _create_metric(left_vbox, "CADENCE (RPM)", HudViewModel.NO_VALUE)
	hr_val = _create_metric(left_vbox, "CARDIO (BPM)", HudViewModel.NO_VALUE)
	# Cible ERG sous les mesures, affichée seulement en ERG (« roue libre » sur un bloc libre).
	target_val = _create_metric(left_vbox, "CIBLE ERG", HudViewModel.NO_VALUE, 32, 16)
	target_val.get_parent().visible = false

	# Panneau droit (haut) : Vitesse, Pente, Braquet, Distance, Temps
	panel_right = _create_panel(Vector2(-TOP_MARGIN - COLUMN_W, TOP_MARGIN), Vector2(COLUMN_W, COLUMN_H), true, false)
	var right_vbox := VBoxContainer.new()
	right_vbox.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT, Control.PRESET_MODE_KEEP_SIZE, int(COLUMN_PAD))
	_column_boxes.append(right_vbox)
	panel_right.add_child(right_vbox)

	speed_val = _create_metric(right_vbox, "VITESSE (KM/H)", HudViewModel.NO_VALUE)
	grade_val = _create_metric(right_vbox, "PENTE", HudViewModel.NO_VALUE)
	gear_val = _create_metric(right_vbox, "BRAQUET", HudViewModel.NO_VALUE, 26, 16)
	distance_val = _create_metric(right_vbox, "DISTANCE", HudViewModel.NO_VALUE, 26, 16)
	time_val = _create_metric(right_vbox, "TEMPS", HudViewModel.NO_VALUE, 26, 16)

	# Bandeau supérieur central : ERG, prochaine montée et ligne d'état de diagnostic
	var center_x := TOP_MARGIN + COLUMN_W + TOP_MARGIN
	panel_center = _create_panel(Vector2(center_x, TOP_MARGIN), Vector2(-2.0 * center_x, CENTER_H), false, false, true)
	var center_vbox := VBoxContainer.new()
	center_vbox.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT, Control.PRESET_MODE_KEEP_SIZE, int(CENTER_PAD))
	_center_box = center_vbox
	panel_center.add_child(center_vbox)

	climb_label = Label.new()
	climb_label.add_theme_font_size_override("font_size", 20)
	climb_label.text = ""
	climb_label.clip_text = true
	center_vbox.add_child(climb_label)

	erg_label = Label.new()
	erg_label.add_theme_font_size_override("font_size", 18)
	erg_label.text = ""
	erg_label.clip_text = true
	center_vbox.add_child(erg_label)

	# Ligne d'état de diagnostic : séance, raison de pause, trainer, entrée (affichée depuis le lot D).
	status_label = Label.new()
	status_label.add_theme_font_size_override("font_size", 14)
	status_label.text = "ÉTAT: en attente du core…"
	status_label.clip_text = true
	center_vbox.add_child(status_label)

	_build_wind_panel()
	_build_draft_label()

	# Profil d'altitude : sous le panneau de droite, de sa largeur (placé par _layout_right_column)
	profile_panel = Control.new()
	profile_panel.name = "ProfilePanel"
	profile_panel.anchor_left = 1.0
	profile_panel.anchor_right = 1.0
	profile_panel.offset_left = -TOP_MARGIN - COLUMN_W
	profile_panel.offset_right = -TOP_MARGIN
	_place(profile_panel, _right_column_top(), PROFILE_H)
	profile_panel.draw.connect(_on_profile_draw)
	add_child(profile_panel)
	_build_bots_panel()
	_build_segment_blocks()

	alt_min_label = Label.new()
	alt_min_label.add_theme_font_size_override("font_size", 14)
	alt_min_label.position = Vector2(5.0, PROFILE_H - 21.0)
	profile_panel.add_child(alt_min_label)

	alt_max_label = Label.new()
	alt_max_label.add_theme_font_size_override("font_size", 14)
	alt_max_label.position = Vector2(5.0, 1.0)
	profile_panel.add_child(alt_max_label)


## Indicateur du vent (Lot P16), sous le panneau de gauche (même largeur), caché tant qu'il n'y a
## pas de vent dans les trames du core.
func _build_wind_panel() -> void:
	panel_wind = _create_panel(Vector2(TOP_MARGIN, TOP_MARGIN + COLUMN_H + 10.0), Vector2(BLOCK_W, 132.0), false, false)
	_shrink_block(panel_wind, false)
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
	panel_bots = _create_panel(Vector2(-TOP_MARGIN - BLOCK_W, _right_column_top()), Vector2(BLOCK_W, 100.0), true, false)
	_shrink_block(panel_bots, true)
	panel_bots.name = "BotsPanel"
	panel_bots.visible = false
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
		bots_lines.append(_bots_label(Vector2(160.0, 26.0), 18))
		var arrow := Control.new()
		arrow.size = Vector2(16.0, 16.0)
		arrow.visible = false
		arrow.set_meta("dir", "ahead")
		arrow.draw.connect(func() -> void: _draw_neighbor_arrow(arrow))
		panel_bots.add_child(arrow)
		bots_arrows.append(arrow)
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
	arrow.draw_colored_polygon(pts, UiTheme.INK)   # teinte : modulate du nœud


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


## Haut des blocs de la colonne de droite : sous le panneau de droite.
func _right_column_top() -> float:
	return panel_right.offset_bottom + BLOCK_GAP


## Hauteur des trois panneaux du haut ajustée à leur contenu (pas de fond vide sous les lignes), puis
## vent et colonne de droite replacés dessous.
func _fit_top_panels() -> void:
	var left_h := _column_boxes[0].get_combined_minimum_size().y + 2.0 * COLUMN_PAD
	var right_h := _column_boxes[1].get_combined_minimum_size().y + 2.0 * COLUMN_PAD
	var center_h := _center_box.get_combined_minimum_size().y + 2.0 * CENTER_PAD
	if is_equal_approx(panel_left.size.y, left_h) and is_equal_approx(panel_right.offset_bottom - panel_right.offset_top, right_h) \
			and is_equal_approx(panel_center.offset_bottom - panel_center.offset_top, center_h):
		return
	panel_left.size.y = left_h
	_place(panel_right, TOP_MARGIN, right_h)
	_place(panel_center, TOP_MARGIN, center_h)
	panel_wind.position.y = TOP_MARGIN + left_h + DRAFT_GAP
	if draft_label.visible:
		draft_label.position.y = panel_wind.position.y + (panel_wind.size.y * BLOCK_SCALE + DRAFT_GAP if panel_wind.visible else 0.0)
	_layout_right_column()


## Colonne de droite : profil d'altitude (SIM), blocs segment et bonus visibles empilés, puis l'encart des
## bots jusqu'au bas de l'écran (ou au-dessus du bandeau ERG).
func _layout_right_column() -> void:
	var y := _right_column_top()
	if profile_panel != null and profile_panel.visible:
		_place(profile_panel, y, PROFILE_H)
		y += PROFILE_H + BLOCK_GAP
	for p in [panel_segment, panel_bonus]:
		if p != null and p.visible:
			var h: float = p.offset_bottom - p.offset_top
			_place(p, y, h)
			y += h * BLOCK_SCALE + BLOCK_GAP
	if panel_bots != null and panel_bots.visible:
		var bottom: float = _screen_height() - (ERG_RESERVE if _erg_active else SCREEN_BOTTOM)
		_layout_bots_panel(y, (bottom - y) / BLOCK_SCALE)


func _layout_bots_panel(top: float, avail: float) -> void:
	var v := _bots_hud
	var rows: Array = v["rows"]
	var shown_rows := BotHudModel.fit(v, avail)
	var first: int = shown_rows["first"]
	var n_rows: int = shown_rows["count"]
	var y := BotHudModel.PADDING / 2.0
	for i in range(bots_lines.size()):
		var shown := i < n_rows
		var r: Dictionary = rows[first + i] if shown else {}
		var jersey := str(r.get("jersey", ""))
		var wbal := float(r.get("wbal", -1.0))
		var dir := str(r.get("dir", ""))
		bots_lines[i].visible = shown
		bots_gaps[i].visible = shown
		bots_jerseys[i].visible = shown and jersey != ""
		bots_kom_dots[i].visible = jersey == "kom"
		bots_wbal_bg[i].visible = shown and wbal >= 0.0
		bots_arrows[i].visible = shown and dir != ""
		if not shown:
			continue
		var detail := str(r["detail"])
		bots_lines[i].text = str(r["name"]) + ("  " + detail if detail != "" else "")
		bots_lines[i].modulate = r["color"]
		bots_lines[i].position = Vector2(26.0, y)
		bots_gaps[i].text = str(r["gap_text"])
		bots_gaps[i].position = Vector2(210.0, y)
		bots_jerseys[i].position = Vector2(10.0, y + 4.0)
		bots_jerseys[i].color = JERSEY_COLORS.get(jersey, UiTheme.INK)
		bots_arrows[i].position = Vector2(193.0, y + 5.0)
		bots_arrows[i].modulate = r["color"]
		bots_arrows[i].set_meta("dir", dir)
		bots_arrows[i].queue_redraw()
		bots_wbal_bg[i].position = Vector2(26.0, y + 26.0)
		bots_wbal[i].size.x = bots_wbal_bg[i].size.x * maxf(wbal, 0.0)
		y += BotHudModel.BOT_ROW
	jerseys_label.visible = bool(shown_rows["jerseys"])
	if jerseys_label.visible:
		jerseys_label.text = str(v["jerseys_text"])
		jerseys_label.position = Vector2(10.0, y)
		y += BotHudModel.JERSEY_ROW
	_place(panel_bots, top, y + BotHudModel.PADDING / 2.0)


## Ligne de l'encart qui porte le voisin `dir` ("ahead" ou "behind"), null s'il n'est pas affiché (tests).
func neighbor_line(dir: String) -> Label:
	for i in range(bots_lines.size()):
		if bots_lines[i].visible and bots_arrows[i].visible and str(bots_arrows[i].get_meta("dir", "")) == dir:
			return bots_lines[i]
	return null


## Pastille « Abri 30 % » (Lot P17), même largeur que l'indicateur du vent.
func _build_draft_label() -> void:
	draft_label = Label.new()
	draft_label.name = "Draft"
	draft_label.position = panel_wind.position + Vector2(0.0, panel_wind.size.y * BLOCK_SCALE + DRAFT_GAP)
	draft_label.size = Vector2(panel_wind.size.x, 44.0)
	_shrink_block(draft_label, false)
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
	var top := _right_column_top()
	panel_segment = _create_panel(Vector2(-TOP_MARGIN - BLOCK_W, top), Vector2(BLOCK_W, 100.0), true, false)
	_shrink_block(panel_segment, true)
	panel_segment.name = "SegmentPanel"
	panel_segment.visible = false
	segment_title = _block_label(panel_segment, "SegmentTitle", Vector2(10.0, 4.0), 22)
	segment_main = _block_label(panel_segment, "SegmentMain", Vector2(10.0, 30.0), 36)
	segment_detail = _block_label(panel_segment, "SegmentDetail", Vector2(10.0, 70.0), 20)
	panel_bonus = _create_panel(Vector2(-TOP_MARGIN - BLOCK_W, top + 100.0 * BLOCK_SCALE + BLOCK_GAP), Vector2(BLOCK_W, 72.0), true, false)
	_shrink_block(panel_bonus, true)
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
		segment_detail.visible = segment_detail.text != ""
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
	_fit_block(panel_segment, [[segment_title, 20.0, 32.0], [segment_main, 40.0, 46.0], [segment_detail, 28.0, 28.0]])
	_fit_block(panel_bonus, [[bonus_held, 32.0, 36.0], [bonus_active, 26.0, 28.0], [bonus_bar, 8.0, 10.0]])
	_layout_right_column()


## Bloc à la hauteur de son contenu (lot X22) : lignes visibles empilées depuis le haut, `[nœud, pas,
## étendue]` : le pas mène à la ligne suivante (les boîtes des libellés se recouvrent, pas leurs chiffres),
## l'étendue va jusqu'au bas du texte plus la marge.
func _fit_block(p: Panel, lines: Array) -> void:
	var y := BLOCK_PAD
	var bottom := 0.0
	for line in lines:
		var c: Control = line[0]
		if not c.visible:
			continue
		c.position.y = y
		bottom = y + float(line[2])
		y += float(line[1])
	p.offset_bottom = p.offset_top + bottom


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
		var top := panel_wind.position.y + (panel_wind.size.y * BLOCK_SCALE + DRAFT_GAP if shown else 0.0)
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


## Bloc sous une colonne réduit à BLOCK_SCALE ; à droite, réduit vers le bord droit de l'écran.
func _shrink_block(c: Control, right: bool) -> void:
	c.scale = Vector2(BLOCK_SCALE, BLOCK_SCALE)
	if right:
		c.pivot_offset = Vector2(BLOCK_W, 0.0)


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
		val_size := 39, label_size := 20) -> Label:
	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", int(METRIC_SEP))
	parent.add_child(hbox)

	var lbl := Label.new()
	lbl.text = label_text
	lbl.add_theme_font_size_override("font_size", label_size)
	lbl.modulate = UiTheme.HUD_DIM
	hbox.add_child(lbl)

	var val := Label.new()
	val.text = default_val
	val.add_theme_font_size_override("font_size", val_size)
	val.set_meta("caption", lbl)   # libellé de la valeur (tests de lisibilité, lot X22)
	val.set_meta("font_max", val_size)
	hbox.add_child(val)

	return val


## Écrit la valeur d'une métrique des colonnes et réduit sa police, de 2 en 2 depuis sa taille de départ,
## jusqu'à ce que libellé et valeur tiennent dans la largeur de la colonne.
func _set_metric(val: Label, text: String) -> void:
	val.text = text
	var caption: Label = val.get_meta("caption")
	var avail := COLUMN_W - 2.0 * COLUMN_PAD - METRIC_SEP - caption.get_minimum_size().x
	var font := val.get_theme_font("font")
	var size: int = val.get_meta("font_max")
	while size > METRIC_MIN_FONT and font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x > avail:
		size -= 2
	val.add_theme_font_size_override("font_size", size)


## Teinte du texte d'une zone (0 = Z1), blanc sans zone.
func _zone_color(zone: int) -> Color:
	return ZONE_TEXT_COLORS[zone] if zone >= 0 and zone < ZONE_TEXT_COLORS.size() else Color.WHITE


## Met à jour les valeurs et le profil d'altitude.
func update_display(state: Dictionary, erg_eval: Dictionary, route: Variant = null, s: float = 0.0) -> void:
	_route = route
	_erg_active = state.get("erg") != null
	if profile_panel != null:
		profile_panel.visible = not _erg_active
	var now_s := Time.get_ticks_usec() / 1e6
	vm.on_state(state, now_s)
	var lines := HudViewModel.session_lines(state, erg_eval, ftp_w, hr_max_bpm)

	if power_val != null:
		_set_metric(power_val, lines["power_val"])
		power_val.modulate = _zone_color(int(lines["power_zone"]))
	if speed_val != null:
		_set_metric(speed_val, lines["speed_val"])
	if cadence_val != null:
		_set_metric(cadence_val, lines["cadence_val"])
	if hr_val != null:
		_set_metric(hr_val, lines["hr_val"])
		hr_val.modulate = _zone_color(int(lines["hr_zone"]))
	if distance_val != null:
		_set_metric(distance_val, lines["distance_val"])
	if time_val != null:
		_set_metric(time_val, lines["time_val"])
	if gear_val != null:
		# Braquet caché en ERG avec une cible : le trainer suit la puissance et ± règle l'intensité.
		_set_metric(gear_val, lines["gear_val"])
		gear_val.get_parent().visible = lines.get("gear_shown", true)

	if grade_val != null:
		_set_metric(grade_val, lines["grade_val"])
		var g_class: String = lines.get("grade_class", "flat")
		grade_val.modulate = GRADE_TEXT_COLORS.get(g_class, GRADE_TEXT_COLORS["flat"])

	if erg_label != null:
		erg_label.text = lines.get("erg", "")
		erg_label.visible = show_erg_line and lines.get("erg", "") != ""

	if target_val != null:
		# Même texte que la ligne de puissance du HUD d'origine (« 230 W » ou « roue libre »).
		var has_target: bool = lines["power"].contains("CIBLE ERG: ")
		_set_metric(target_val, lines["power"].get_slice("CIBLE ERG: ", 1) if has_target else HudViewModel.NO_VALUE)
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
	if climb_label != null:
		climb_label.visible = climb_label.text != ""   # ligne vide : pas de hauteur dans le bandeau
	_fit_top_panels()

	# Profil d'altitude (au plus 5 fois par seconde ou si s a avancé d'une colonne ~41 m)
	var col_step := 5000.0 / 120.0
	if route != null and (absf(s - _last_profile_s) >= col_step or now_s - _last_profile_time_s >= 0.20):
		_last_profile_s = s
		_last_profile_time_s = now_s
		_profile_data = vm.profile(route, s)
		if alt_min_label != null and alt_max_label != null:
			alt_min_label.text = "%.0f m" % float(_profile_data.get("alt_min", 0.0))
			alt_max_label.text = "%.0f m" % float(_profile_data.get("alt_max", 0.0))
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

	var x0 := PROFILE_LABEL_W
	var w: float = profile_panel.size.x - x0
	var h: float = profile_panel.size.y
	var cols := alts.size()
	if cols < 2:
		return

	# Fond du panneau profil
	profile_panel.draw_rect(Rect2(0, 0, x0 + w, h), UiTheme.CHART_BG)

	var col_w := w / float(cols)
	for i in range(cols):
		var norm_h := clampf((float(alts[i]) - alt_min) / alt_range, 0.05, 0.95)
		var bar_h := norm_h * h
		var bar_rect := Rect2(x0 + i * col_w, h - bar_h, col_w + 0.5, bar_h)
		var col_grade: String = classes[i] if i < classes.size() else "flat"
		var color: Color = GRADE_COLORS.get(col_grade, COLOR_FLAT)
		profile_panel.draw_rect(bar_rect, color)

	# Bots (lot O7) : un point coloré à la hauteur du profil, selon l'écart au cycliste.
	var from_m: float = float(_profile_data.get("from_m", 0.0))
	var to_m: float = float(_profile_data.get("to_m", 0.0))
	if to_m > from_m:
		for mark in BotsViewModel.profile_marks(_bots_view, from_m, to_m):
			var idx := clampi(int(round((float(mark["rel_m"]) - from_m) / (to_m - from_m) * float(cols - 1))), 0, cols - 1)
			var bx := x0 + (idx + 0.5) * col_w
			var by := h - clampf((float(alts[idx]) - alt_min) / alt_range, 0.05, 0.95) * h
			profile_panel.draw_circle(Vector2(bx, by), 5.0, UiTheme.INK_EDGE)
			profile_panel.draw_circle(Vector2(bx, by), 3.5, mark["color"])

	# Repère de position
	if marker_idx >= 0 and marker_idx < cols:
		var mx := x0 + (marker_idx + 0.5) * col_w
		var my := h - clampf((float(alts[marker_idx]) - alt_min) / alt_range, 0.05, 0.95) * h
		profile_panel.draw_circle(Vector2(mx, my), 6.0, UiTheme.INK)
		profile_panel.draw_circle(Vector2(mx, my), 3.0, UiTheme.INK_EDGE)
