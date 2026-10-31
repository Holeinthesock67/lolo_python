extends Control

## Écran d'attente du départ au pédalage (lot O36, demande du propriétaire du 31 octobre : « un écran de
## chargement avec une image sympa du type start your engine »). Dessiné par le code, sans texture : titre
## « START YOUR ENGINES », cinq feux de départ (allumés selon start_wait_model.gd), barre du pédalage,
## cadence mesurée, étape en cours et « Y : annuler ». Voile opaque tant que le décor se charge, plus léger
## pendant le pédalage pour voir la route du départ ; feux verts « GO ! » à l'ouverture du départ.
## Ne décide rien : affiche ce que `show_wait` et `show_go` lui donnent (main.gd).
## Pas de class_name : charger par preload("res://scripts/start_screen.gd").

const UiTheme := preload("res://scripts/ui_theme.gd")
const StartWaitModel := preload("res://scripts/start_wait_model.gd")

const BASE := Vector2(1280.0, 720.0)
const TITLE_SIZE := 64
const TEXT_SIZE := 28
const SMALL_SIZE := 20
const LIGHT_R := 34.0
const LIGHT_GAP := 104.0
const LIGHTS_Y := 330.0
const BAR_W := 520.0
const BAR_H := 14.0
const VEIL_LOADING := 0.94
const VEIL_PEDALLING := 0.55

var _wait = null          # objet start_wait de la dernière trame, null hors attente
var _cadence := 0.0
var _go_left_s := 0.0


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	visible = false


## Trame reçue pendant l'attente (`wait` : objet start_wait) ou hors attente (null).
func show_wait(wait, cadence_rpm: float) -> void:
	if wait == null and _wait != null:
		_wait = null
		visible = _go_left_s > 0.0
		queue_redraw()
		return
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
	if _go_left_s > 0.0:
		_go_left_s -= delta
		if _go_left_s <= 0.0:
			visible = false
		queue_redraw()


## Informations des tests visuels et unitaires.
func test_info() -> Dictionary:
	return {"visible": visible, "lights": StartWaitModel.lights(_wait), "go": _go_left_s > 0.0,
		"text": StartWaitModel.text(_wait)}


func _draw() -> void:
	var k := size / BASE if size.x > 0.0 and size.y > 0.0 else Vector2.ONE
	draw_set_transform(Vector2.ZERO, 0.0, k)
	var go := _go_left_s > 0.0
	var pedalling := go or (_wait is Dictionary and str(_wait.get("phase", "")) == "pedalage")
	draw_rect(Rect2(Vector2.ZERO, BASE), Color(UiTheme.VOID, VEIL_PEDALLING if pedalling else VEIL_LOADING))
	var font := ThemeDB.fallback_font
	# Bandes de damier en haut et en bas, comme une ligne de départ.
	for row in 2:
		for i in int(BASE.x / 20.0):
			if (i + row) % 2 == 0:
				draw_rect(Rect2(i * 20.0, 60.0 + row * 10.0, 20.0, 10.0), Color(UiTheme.TEXT, 0.5))
				draw_rect(Rect2(i * 20.0, 640.0 + row * 10.0, 20.0, 10.0), Color(UiTheme.TEXT, 0.5))
	_centered(font, StartWaitModel.TITLE, 190.0, TITLE_SIZE, UiTheme.GOLD if go else UiTheme.FOCUS)
	# Feux de départ sur leur portique.
	var n := StartWaitModel.LIGHTS
	var x0 := BASE.x * 0.5 - LIGHT_GAP * (n - 1) * 0.5
	draw_rect(Rect2(x0 - LIGHT_GAP * 0.5, LIGHTS_Y - LIGHT_R - 16.0, LIGHT_GAP * n, LIGHT_R * 2.0 + 32.0), UiTheme.NIGHT)
	var lit := StartWaitModel.lights(_wait)
	for i in n:
		var c := Vector2(x0 + i * LIGHT_GAP, LIGHTS_Y)
		var col: Color = UiTheme.OK if go else (UiTheme.DANGER if i < lit else UiTheme.LINE)
		if go or i < lit:
			draw_circle(c, LIGHT_R + 10.0, Color(col, 0.25))
		draw_circle(c, LIGHT_R, col)
	if go:
		_centered(font, "GO !", 470.0, TITLE_SIZE, UiTheme.OK)
		return
	# Barre du pédalage, cadence mesurée, étape et annulation.
	var bar := Rect2(BASE.x * 0.5 - BAR_W * 0.5, 410.0, BAR_W, BAR_H)
	draw_rect(bar, UiTheme.SURFACE)
	draw_rect(Rect2(bar.position, Vector2(BAR_W * StartWaitModel.progress(_wait), BAR_H)), UiTheme.FOCUS)
	var text := StartWaitModel.text(_wait)
	var cut := text.find("  (")
	_centered(font, text if cut < 0 else text.substr(0, cut), 480.0, TEXT_SIZE, UiTheme.TEXT)
	if pedalling:
		_centered(font, "Cadence : %d tr/min" % int(round(_cadence)), 530.0, TEXT_SIZE, UiTheme.GOLD)
	_centered(font, "Y : annuler", 600.0, SMALL_SIZE, UiTheme.DIM)


func _centered(font: Font, text: String, y: float, font_size: int, col: Color) -> void:
	var w := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	draw_string(font, Vector2(BASE.x * 0.5 - w * 0.5, y), text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, col)
