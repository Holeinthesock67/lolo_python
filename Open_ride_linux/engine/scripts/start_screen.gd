extends Control

## Écran d'attente du départ au pédalage (lot O36, demande du propriétaire du 31 octobre : « un écran de
## chargement avec une image sympa du type start your engine ») ; habillage « Retransmission » de la 3.0
## (demande du 4 novembre : plus stylé, moins basique ; maquette A choisie). Dessiné par le code, sans
## texture ni police ajoutée (police par défaut de Godot, grasse et penchée par FontVariation) :
## - bandeau penché du titre « START YOUR ENGINES » avec traits de vitesse et reflet qui le balaie ;
## - portique de cinq boîtiers à deux lampes (allumés selon start_wait_model.gd), halo qui respire ;
## - pastilles des trois étapes (décor, trainer, pédalage), texte de l'étape en cours ;
## - carte du parcours qui va être roulé (nom, distance, dénivelé, profil), absente sans parcours ;
## - anneau de cadence qui se remplit pendant le pédalage, cadence lissée au centre ; touche « Y annuler ».
## Pendant le chargement du décor et la connexion du trainer, l'écran est figé (aucune animation, redessiné
## seulement à chaque trame du core) pour laisser toute l'image au chargement ; les animations ne tournent
## qu'au pédalage et au « GO ! ». Styles des cadres créés une fois (`_styles`).
## Voile opaque tant que le décor se charge, plus léger pendant le pédalage pour voir la route du départ ;
## au « GO ! », sans voile ni bandeau : feux verts, flash bref et « GO ! » penché (le rappel des commandes et
## le texte du segment restent lisibles autour).
## Ne décide rien : affiche ce que `show_wait`, `show_go` et `set_route` lui donnent (main.gd).
## Pas de class_name : charger par preload("res://scripts/start_screen.gd").

const UiTheme := preload("res://scripts/ui_theme.gd")
const StartWaitModel := preload("res://scripts/start_wait_model.gd")

const BASE := Vector2(1280.0, 720.0)
const VEIL_LOADING := 0.94
const VEIL_PEDALLING := 0.5
# Bandeau du titre (parallélogramme penché).
const TITLE_SIZE := 62
const TAG_SIZE := 18
const BAND_TOP := 58.0
const BAND_BOTTOM := 148.0
const BAND_LEFT := 170.0
const BAND_RIGHT := 1110.0
const BAND_SLANT := 40.0
const SHEEN_PERIOD_S := 3.5
# Portique : cinq boîtiers à deux lampes.
const HOUSING_GAP := 140.0
const HOUSING_W := 92.0
const HOUSING_H := 190.0
const GANTRY_Y := 200.0
const GANTRY_Y_GO := 150.0
const LAMP_R := 30.0
const BREATH_PERIOD_S := 1.6
# Étapes, texte, carte du parcours, anneau de cadence.
const STEP_W := 160.0
const STEP_H := 40.0
const STEP_Y := 420.0
const STEP_GAP := 190.0
const TEXT_SIZE := 26
const SMALL_SIZE := 18
const CARD := Rect2(48.0, 540.0, 420.0, 140.0)
const RING_C := Vector2(1130.0, 600.0)
const RING_R := 68.0
const RING_W := 14.0
const CADENCE_SMOOTH := 8.0   # 1/s : la cadence affichée rejoint la mesure en ~0,3 s
const GO_SIZE := 132
const GO_FLASH_S := 0.2

var _wait = null          # objet start_wait de la dernière trame, null hors attente
var _cadence := 0.0
var _cadence_shown := 0.0
var _go_left_s := 0.0
var _t := 0.0
var _route := {}          # carte du parcours (StartWaitModel.route_card), {} sans parcours
var _font: Font = null
var _title_font: FontVariation = null
var _tag_font: FontVariation = null
var _bold_font: FontVariation = null
var _styles := {}         # StyleBoxFlat des cadres, par couleurs, rayon et épaisseur


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false
	_font = ThemeDB.fallback_font
	_title_font = FontVariation.new()
	_title_font.base_font = _font
	_title_font.variation_embolden = 1.0
	_title_font.variation_transform = Transform2D(Vector2(1.0, 0.0), Vector2(0.22, 1.0), Vector2.ZERO)
	_tag_font = FontVariation.new()
	_tag_font.base_font = _font
	_tag_font.variation_embolden = 0.6
	_tag_font.spacing_glyph = 6
	_bold_font = FontVariation.new()
	_bold_font.base_font = _font
	_bold_font.variation_embolden = 0.6


## Parcours qui va être roulé (StartWaitModel.route_card) ; {} : pas de carte.
func set_route(card: Dictionary) -> void:
	_route = card
	queue_redraw()


## Trame reçue pendant l'attente (`wait` : objet start_wait) ou hors attente (null).
func show_wait(wait, cadence_rpm: float) -> void:
	if wait == null and _wait != null:
		_wait = null
		visible = _go_left_s > 0.0
		queue_redraw()
		return
	if wait != null and _wait == null:
		_cadence_shown = cadence_rpm
	_wait = wait
	_cadence = cadence_rpm
	if wait != null:
		_go_left_s = 0.0
		visible = true
		queue_redraw()


## Départ ouvert : feux verts pendant GO_S.
func show_go() -> void:
	_go_left_s = StartWaitModel.GO_S
	_wait = null
	visible = true
	queue_redraw()


func _process(delta: float) -> void:
	if not visible:
		return
	if _go_left_s <= 0.0 and not _animated():
		return   # chargement : écran figé, redessiné par show_wait seulement
	_t += delta
	_cadence_shown = lerpf(_cadence_shown, _cadence, clampf(delta * CADENCE_SMOOTH, 0.0, 1.0))
	if _go_left_s > 0.0:
		_go_left_s -= delta
		if _go_left_s <= 0.0:
			visible = false
	queue_redraw()


## Vrai au pédalage : seule étape de l'attente où l'écran s'anime.
func _animated() -> bool:
	return _wait is Dictionary and str(_wait.get("phase", "")) == "pedalage"


## Informations des tests visuels et unitaires.
func test_info() -> Dictionary:
	return {"visible": visible, "lights": StartWaitModel.lights(_wait), "go": _go_left_s > 0.0,
		"text": StartWaitModel.text(_wait), "steps": StartWaitModel.steps(_wait),
		"route": str(_route.get("name", "")), "route_line": str(_route.get("line", "")), "animated": _animated()}


func _draw() -> void:
	var k := size / BASE if size.x > 0.0 and size.y > 0.0 else Vector2.ONE
	draw_set_transform(Vector2.ZERO, 0.0, k)
	if _font == null:
		return
	if _go_left_s > 0.0:
		_draw_go()
		return
	var pedalling := _wait is Dictionary and str(_wait.get("phase", "")) == "pedalage"
	draw_rect(Rect2(Vector2.ZERO, BASE), Color(UiTheme.VOID, VEIL_PEDALLING if pedalling else VEIL_LOADING))
	_draw_title()
	_draw_gantry(GANTRY_Y, StartWaitModel.lights(_wait), false)
	_draw_steps()
	var text := StartWaitModel.text(_wait)
	var cut := text.find("  (")
	_centered(_font, text if cut < 0 else text.substr(0, cut), 500.0, TEXT_SIZE, UiTheme.TEXT)
	_draw_route_card()
	_draw_cadence_ring(pedalling)
	_draw_keycap(Vector2(560.0, 642.0), "Y", "annuler")


# --- Bandeau du titre --------------------------------------------------------------------------

func _draw_title() -> void:
	var band := PackedVector2Array([Vector2(BAND_LEFT + BAND_SLANT, BAND_TOP), Vector2(BAND_RIGHT, BAND_TOP),
		Vector2(BAND_RIGHT - BAND_SLANT, BAND_BOTTOM), Vector2(BAND_LEFT, BAND_BOTTOM)])
	draw_colored_polygon(band, Color(UiTheme.NIGHT, 0.92))
	draw_colored_polygon(PackedVector2Array([Vector2(BAND_LEFT, BAND_BOTTOM), Vector2(BAND_RIGHT - BAND_SLANT, BAND_BOTTOM),
		Vector2(BAND_RIGHT - BAND_SLANT - 4.0, BAND_BOTTOM + 8.0), Vector2(BAND_LEFT - 4.0, BAND_BOTTOM + 8.0)]), UiTheme.FOCUS)
	# Reflet qui balaie le bandeau : bande claire penchée, coupée aux bords du bandeau.
	var f := fmod(_t, SHEEN_PERIOD_S) / SHEEN_PERIOD_S
	var x := lerpf(BAND_LEFT - 80.0, BAND_RIGHT + 40.0, f)
	var x0 := clampf(x, BAND_LEFT + BAND_SLANT, BAND_RIGHT - BAND_SLANT)
	var x1 := clampf(x + 60.0, BAND_LEFT + BAND_SLANT, BAND_RIGHT - BAND_SLANT)
	if x1 > x0:
		draw_colored_polygon(PackedVector2Array([Vector2(x0, BAND_TOP), Vector2(x1, BAND_TOP),
			Vector2(x1 - BAND_SLANT, BAND_BOTTOM), Vector2(x0 - BAND_SLANT, BAND_BOTTOM)]), Color(UiTheme.FOCUS, 0.07))
	# Traits de vitesse à gauche du bandeau.
	for i in 3:
		var y := 78.0 + i * 22.0
		draw_colored_polygon(PackedVector2Array([Vector2(60.0 + i * 30.0, y), Vector2(190.0, y), Vector2(185.0, y + 10.0),
			Vector2(55.0 + i * 30.0, y + 10.0)]), Color(UiTheme.FOCUS, 0.8 - i * 0.25))
	_centered(_title_font, StartWaitModel.TITLE, 128.0, TITLE_SIZE, UiTheme.TEXT)
	_centered(_tag_font, StartWaitModel.TAG, 46.0, TAG_SIZE, UiTheme.GOLD)


# --- Portique des feux -------------------------------------------------------------------------

func _draw_gantry(top: float, lit: int, go: bool) -> void:
	var n := StartWaitModel.LIGHTS
	var x0 := BASE.x * 0.5 - HOUSING_GAP * (n - 1) * 0.5
	var bar := Rect2(x0 - HOUSING_GAP * 0.5 - 20.0, top - 22.0, HOUSING_GAP * n + 40.0, 18.0)
	draw_rect(bar, UiTheme.START_GANTRY)
	draw_rect(Rect2(bar.position.x, top - 6.0, bar.size.x, 3.0), UiTheme.LINE)
	var breath := 0.75 + 0.25 * sin(_t * TAU / BREATH_PERIOD_S)
	for i in n:
		var x := x0 + i * HOUSING_GAP
		_rounded(Rect2(x - HOUSING_W * 0.5, top, HOUSING_W, HOUSING_H), UiTheme.START_HOUSING, UiTheme.LINE, 10, 2)
		for j in 2:
			var c := Vector2(x, top + 50.0 + j * 90.0)
			var on := go or i < lit
			var col: Color = UiTheme.OK if go else UiTheme.DANGER
			if on:
				_glow(c, LAMP_R, col, 1.0 if go else breath)
			draw_circle(c, LAMP_R, col if on else UiTheme.START_LAMP_OFF)
			if on:
				draw_circle(c + Vector2(-9.0, -10.0), 8.0, UiTheme.START_LAMP_SHINE)
			draw_arc(c, LAMP_R + 6.0, PI * 1.08, PI * 1.92, 16, UiTheme.START_HOOD, 8.0, true)


## Halo : disques concentriques de moins en moins opaques.
func _glow(c: Vector2, r: float, col: Color, strength: float) -> void:
	for i in range(4, 0, -1):
		draw_circle(c, r + i * 7.0, Color(col, strength * 0.16 * (5 - i) / 4.0))


# --- Étapes, carte du parcours, anneau de cadence ---------------------------------------------

func _draw_steps() -> void:
	var steps := StartWaitModel.steps(_wait)
	for i in steps.size():
		var st: String = steps[i]["state"]
		var r := Rect2(BASE.x * 0.5 + (i - 1) * STEP_GAP - STEP_W * 0.5, STEP_Y, STEP_W, STEP_H)
		var edge: Color = UiTheme.OK if st == "done" else (UiTheme.FOCUS if st == "current" else UiTheme.LINE)
		var fill := Color(UiTheme.FOCUS, 0.16) if st == "current" else Color(UiTheme.SURFACE, 0.9)
		_rounded(r, fill, edge, int(STEP_H * 0.5), 2)
		var dot := r.position + Vector2(31.0, STEP_H * 0.5)
		if st == "done":
			draw_polyline(PackedVector2Array([dot + Vector2(-9.0, 1.0), dot + Vector2(-2.0, 8.0), dot + Vector2(11.0, -7.0)]),
				UiTheme.OK, 3.0, true)
		else:
			draw_circle(dot, 6.0, UiTheme.FOCUS if st == "current" else UiTheme.LINE)
		var col: Color = UiTheme.TEXT if st == "done" else (UiTheme.FOCUS if st == "current" else UiTheme.DIM)
		var w := _bold_font.get_string_size(steps[i]["label"], HORIZONTAL_ALIGNMENT_LEFT, -1, 19).x
		draw_string(_bold_font, Vector2(r.position.x + 98.0 - w * 0.5, r.position.y + 27.0), steps[i]["label"],
			HORIZONTAL_ALIGNMENT_LEFT, -1, 19, col)


func _draw_route_card() -> void:
	if _route.is_empty():
		return
	_rounded(CARD, Color(UiTheme.NIGHT, 0.9), UiTheme.LINE, 10, 2)
	var x := CARD.position.x + 22.0
	draw_string(_tag_font, Vector2(x, CARD.position.y + 30.0), "PARCOURS", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, UiTheme.DIM)
	draw_string(_bold_font, Vector2(x, CARD.position.y + 62.0), str(_route.get("name", "")), HORIZONTAL_ALIGNMENT_LEFT, 250.0, 24, UiTheme.TEXT)
	draw_string(_font, Vector2(x, CARD.position.y + 90.0), str(_route.get("line", "")), HORIZONTAL_ALIGNMENT_LEFT, 250.0, SMALL_SIZE, UiTheme.GOLD)
	var h: PackedFloat32Array = _route.get("heights", PackedFloat32Array())
	if h.size() < 2:
		return
	var box := Rect2(CARD.position.x + 292.0, CARD.position.y + 34.0, 108.0, 86.0)
	var line := PackedVector2Array()
	for i in h.size():
		line.append(box.position + Vector2(box.size.x * i / float(h.size() - 1), box.size.y * (1.0 - h[i])))
	var area := line.duplicate()
	area.append(box.end)
	area.append(Vector2(box.position.x, box.end.y))
	draw_colored_polygon(area, Color(UiTheme.FOCUS, 0.18))
	draw_polyline(line, UiTheme.FOCUS, 2.5, true)
	_glow(line[0], 6.0, UiTheme.GOLD, 0.6)
	draw_circle(line[0], 6.0, UiTheme.GOLD)


func _draw_cadence_ring(pedalling: bool) -> void:
	draw_arc(RING_C, RING_R, 0.0, TAU, 64, UiTheme.LINE, RING_W, true)
	var p := StartWaitModel.progress(_wait)
	if p > 0.0:
		draw_arc(RING_C, RING_R, -PI * 0.5, -PI * 0.5 + TAU * p, maxi(8, int(64 * p)), UiTheme.FOCUS, RING_W, true)
	var shown := int(round(_cadence_shown)) if pedalling else -1
	_centered_at(_title_font, str(shown) if shown >= 0 else "—", RING_C + Vector2(0.0, 14.0), 44,
		UiTheme.GOLD if shown >= 0 else UiTheme.DIM)
	_centered_at(_font, "tr/min", RING_C + Vector2(0.0, 38.0), 16, UiTheme.DIM)
	var target := int(_wait.get("cadence_rpm", 0)) if _wait is Dictionary else 0
	if target > 0:
		var label := "seuil %d" % target
		var w := _font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, SMALL_SIZE).x
		draw_string(_font, Vector2(RING_C.x - RING_R - 28.0 - w, RING_C.y + 6.0), label, HORIZONTAL_ALIGNMENT_LEFT, -1,
			SMALL_SIZE, UiTheme.DIM)


func _draw_keycap(pos: Vector2, letter: String, label: String) -> void:
	_rounded(Rect2(pos, Vector2(36.0, 36.0)), UiTheme.KEYCAP, UiTheme.KEYCAP_EDGE, 6, 2)
	_centered_at(_bold_font, letter, pos + Vector2(18.0, 26.0), 20, UiTheme.TEXT)
	draw_string(_font, pos + Vector2(48.0, 26.0), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 20, UiTheme.DIM)


# --- GO ! --------------------------------------------------------------------------------------

func _draw_go() -> void:
	var elapsed := StartWaitModel.GO_S - _go_left_s
	if elapsed < GO_FLASH_S:
		draw_rect(Rect2(Vector2.ZERO, BASE), Color(UiTheme.OK, 0.25 * (1.0 - elapsed / GO_FLASH_S)))
	_draw_gantry(GANTRY_Y_GO, StartWaitModel.LIGHTS, true)
	for i in 3:
		var y := 430.0 + i * 34.0
		var col := Color(UiTheme.OK, 0.7 - i * 0.2)
		draw_colored_polygon(PackedVector2Array([Vector2(260.0 + i * 40.0, y), Vector2(440.0, y), Vector2(434.0, y + 12.0),
			Vector2(254.0 + i * 40.0, y + 12.0)]), col)
		draw_colored_polygon(PackedVector2Array([Vector2(1020.0 - i * 40.0, y), Vector2(840.0, y), Vector2(846.0, y + 12.0),
			Vector2(1026.0 - i * 40.0, y + 12.0)]), col)
	var w := _title_font.get_string_size("GO !", HORIZONTAL_ALIGNMENT_LEFT, -1, GO_SIZE).x
	var pos := Vector2(BASE.x * 0.5 - w * 0.5, 520.0)
	draw_string_outline(_title_font, pos, "GO !", HORIZONTAL_ALIGNMENT_LEFT, -1, GO_SIZE, 10, UiTheme.VOID)
	draw_string(_title_font, pos, "GO !", HORIZONTAL_ALIGNMENT_LEFT, -1, GO_SIZE, UiTheme.OK)


# --- Aides de dessin ---------------------------------------------------------------------------

func _rounded(r: Rect2, fill: Color, edge: Color, radius: int, width: int) -> void:
	var key := "%s|%s|%d|%d" % [fill.to_html(), edge.to_html(), radius, width]
	var sb: StyleBoxFlat = _styles.get(key, null)
	if sb == null:
		sb = StyleBoxFlat.new()
		sb.bg_color = fill
		sb.border_color = edge
		sb.set_border_width_all(width)
		sb.set_corner_radius_all(radius)
		sb.anti_aliasing = true
		_styles[key] = sb
	draw_style_box(sb, r)


func _centered(font: Font, text: String, y: float, font_size: int, col: Color) -> void:
	_centered_at(font, text, Vector2(BASE.x * 0.5, y), font_size, col)


func _centered_at(font: Font, text: String, at: Vector2, font_size: int, col: Color) -> void:
	var w := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	draw_string(font, Vector2(at.x - w * 0.5, at.y), text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, col)
