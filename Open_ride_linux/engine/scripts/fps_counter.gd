extends Label

## Compteur d'images par seconde du HUD (réglage « Afficher les images/s », `render.fps` de config.toml).
##
## Petit texte en haut à droite, au-dessus du panneau droit du HUD : « 60 images/s · p99 17 ms ».
## Les images/s comptent les images de la dernière seconde ; le p99 est le temps d'image que 99 % des
## images de cette seconde ne dépassent pas (saccades visibles même quand la moyenne est bonne).
## Quand le garde-fou de charge (lot Y6) a coupé des effets, la ligne finit par « · allégé : SSIL ».
## Choix `detail`, réservé aux essais : ajoute les temps CPU et GPU moyens du rendu de la vue
## (« · CPU 4.2 ms · GPU 10.8 ms », mêmes mesures que perf_probe.gd), mesurés seulement dans ce choix.
## Le texte change une fois par seconde, pour rester lisible et ne rien coûter. Enfant du HUD : caché
## avec lui quand un menu plein écran est ouvert.
## Pas de class_name : charger par preload("res://scripts/fps_counter.gd").

const UiTheme := preload("res://scripts/ui_theme.gd")

const SETTING_KEY := "render.fps"
const MODES := ["off", "on", "detail"]
const PERIOD_S := 1.0
const WIDTH := 600.0      # ligne détaillée : dépasse à gauche du panneau droit, dans la bande du haut
const HEIGHT := 20.0
const MARGIN_RIGHT := 20.0   # aligné sur le panneau droit du HUD (x = −320, largeur 300)

var _frames: Array[float] = []   # temps d'image (ms) depuis la dernière mise à jour
var _elapsed_s := 0.0
var _detail := false
var _cpu_sum := 0.0
var _gpu_sum := 0.0
var _viewport_rid := RID()
## Vrai quand la sonde de performance (perf_probe.gd) ou le garde-fou de charge (load_guard.gd) mesurent
## aussi : la mesure du RenderingServer reste alors active en quittant le choix `detail`.
var measure_kept := false
## Effets coupés par le garde-fou de charge (« SSIL, SSAO »), ajoutés à la fin de la ligne ; vide : rien.
var shed := ""


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


## Applique le réglage (`off`, `on` ou `detail`) ; une valeur inconnue coupe le compteur.
func set_mode(mode: String) -> void:
	var on := mode == "on" or mode == "detail"
	var detail := mode == "detail"
	if (on and not visible) or detail != _detail:
		_frames.clear()
		_elapsed_s = 0.0
		_cpu_sum = 0.0
		_gpu_sum = 0.0
		text = ""
	if detail != _detail:
		_detail = detail
		_measure(detail or measure_kept)
	visible = on


## Mesure des temps CPU et GPU de la vue par le RenderingServer (coupée hors du choix `detail`).
func _measure(on: bool) -> void:
	if not is_inside_tree():
		return
	_viewport_rid = get_viewport().get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(_viewport_rid, on)


## Une image de `delta` secondes ; met le texte à jour chaque seconde. Rien à faire si caché.
func add_frame(delta: float) -> void:
	if not visible:
		return
	_frames.append(delta * 1000.0)
	_elapsed_s += delta
	if _detail and _viewport_rid.is_valid():
		_cpu_sum += RenderingServer.viewport_get_measured_render_time_cpu(_viewport_rid) \
			+ RenderingServer.get_frame_setup_time_cpu()
		_gpu_sum += RenderingServer.viewport_get_measured_render_time_gpu(_viewport_rid)
	if _elapsed_s < PERIOD_S - 1e-6:   # tolérance : 60 × (1/60) ne fait pas tout à fait 1,0
		return
	text = format(_frames, _elapsed_s)
	if _detail and not _frames.is_empty():
		text += format_detail(_cpu_sum / _frames.size(), _gpu_sum / _frames.size())
		_measure(true)   # la sonde de performance a pu couper la mesure en se fermant
	if shed != "" and text != "":
		text += format_shed(shed)
	_frames.clear()
	_elapsed_s = 0.0
	_cpu_sum = 0.0
	_gpu_sum = 0.0


## Texte affiché pour des temps d'image (ms) couvrant `elapsed_s` secondes.
static func format(frames_ms: Array, elapsed_s: float) -> String:
	if frames_ms.is_empty() or elapsed_s <= 0.0:
		return ""
	var sorted := frames_ms.duplicate()
	sorted.sort()
	var p99: float = sorted[mini(int(floor(sorted.size() * 0.99)), sorted.size() - 1)]
	return "%d images/s · p99 %d ms" % [int(round(frames_ms.size() / elapsed_s)), int(round(p99))]


## Suite du texte quand le garde-fou de charge a coupé des effets.
static func format_shed(names: String) -> String:
	return " · allégé : " + names


## Suite du texte du choix `detail` : temps CPU et GPU moyens (ms) du rendu de la vue.
static func format_detail(cpu_ms: float, gpu_ms: float) -> String:
	return " · CPU %.1f ms · GPU %.1f ms" % [cpu_ms, gpu_ms]
