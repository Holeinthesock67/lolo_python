extends Label

## Compteur d'images par seconde du HUD (réglage « Afficher les images/s », `render.fps` de config.toml).
##
## Petit texte en haut à droite, au-dessus du panneau droit du HUD : « 60 images/s · p99 17 ms ».
## Les images/s comptent les images de la dernière seconde ; le p99 est le temps d'image que 99 % des
## images de cette seconde ne dépassent pas (saccades visibles même quand la moyenne est bonne).
## Le texte change une fois par seconde, pour rester lisible et ne rien coûter. Enfant du HUD : caché
## avec lui quand un menu plein écran est ouvert.
## Pas de class_name : charger par preload("res://scripts/fps_counter.gd").

const UiTheme := preload("res://scripts/ui_theme.gd")

const SETTING_KEY := "render.fps"
const MODES := ["off", "on"]
const PERIOD_S := 1.0
const WIDTH := 300.0
const HEIGHT := 20.0
const MARGIN_RIGHT := 20.0   # aligné sur le panneau droit du HUD (x = −320, largeur 300)

var _frames: Array[float] = []   # temps d'image (ms) depuis la dernière mise à jour
var _elapsed_s := 0.0


func _init() -> void:
	name = "FpsCounter"
	visible = false
	horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	add_theme_font_size_override("font_size", UiTheme.SMALL_SIZE)
	add_theme_color_override("font_color", UiTheme.TEXT)
	add_theme_color_override("font_outline_color", UiTheme.VOID)
	add_theme_constant_override("outline_size", 4)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	anchor_left = 1.0
	anchor_right = 1.0
	offset_left = -MARGIN_RIGHT - WIDTH
	offset_right = -MARGIN_RIGHT
	offset_top = 0.0
	offset_bottom = HEIGHT


## Applique le réglage (`off` ou `on`) ; une valeur inconnue coupe le compteur.
func set_mode(mode: String) -> void:
	var on := mode == "on"
	if on and not visible:
		_frames.clear()
		_elapsed_s = 0.0
		text = ""
	visible = on


## Une image de `delta` secondes ; met le texte à jour chaque seconde. Rien à faire si caché.
func add_frame(delta: float) -> void:
	if not visible:
		return
	_frames.append(delta * 1000.0)
	_elapsed_s += delta
	if _elapsed_s < PERIOD_S - 1e-6:   # tolérance : 60 × (1/60) ne fait pas tout à fait 1,0
		return
	text = format(_frames, _elapsed_s)
	_frames.clear()
	_elapsed_s = 0.0


## Texte affiché pour des temps d'image (ms) couvrant `elapsed_s` secondes.
static func format(frames_ms: Array, elapsed_s: float) -> String:
	if frames_ms.is_empty() or elapsed_s <= 0.0:
		return ""
	var sorted := frames_ms.duplicate()
	sorted.sort()
	var p99: float = sorted[mini(int(floor(sorted.size() * 0.99)), sorted.size() - 1)]
	return "%d images/s · p99 %d ms" % [int(round(frames_ms.size() / elapsed_s)), int(round(p99))]
