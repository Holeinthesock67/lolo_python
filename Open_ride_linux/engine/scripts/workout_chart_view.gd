extends Control

## Courbes de la séance à l'écran (Lot O14) : dessin de la géométrie de workout_chart_model.gd (O13),
## « comme GoldenCheetah » : profil des watts cibles coloré par zone, atténué, courbe de puissance en
## blanc épais et, en taille complète, fréquence cardiaque en rouge et cadence en bleu clair, avec la
## légende des valeurs courantes. Trois tailles (`mode`, réglage `[render] chart` du core) :
## - `hidden` : rien (en ERG, l'histogramme de N7 reste affiché) ;
## - `reduced` : profil cible et puissance, valeur courante en watts ;
## - `full` : cible, puissance, FC, cadence, graduations et légende.
## Une instance en ERG, dans le bandeau d'erg_view.gd à la place de l'histogramme (le profil cible du
## graphique joue ce rôle, curseur compris) ; une instance en SIM dans un panneau du HUD, qui montre
## les 10 dernières minutes sans profil. Les deux lisent le même modèle ; le dessin n'est redemandé
## que lorsqu'une nouvelle seconde de séance est arrivée (`refresh()`), jamais à chaque image.
## Ne décide rien. Pas de class_name : charger par preload("res://scripts/workout_chart_view.gd").

const UiTheme := preload("res://scripts/ui_theme.gd")
const MODES := ["hidden", "reduced", "full"]
const POWER_COLOR := UiTheme.POWER
const HR_COLOR := UiTheme.HEART_RATE
const CADENCE_COLOR := UiTheme.CADENCE
const BG_COLOR := UiTheme.CHART_BG
const GRID_COLOR := UiTheme.GRID
const TEXT_COLOR := UiTheme.CHART_TEXT
const PROFILE_ALPHA := 0.45          # profil atténué : les courbes passent devant
const POWER_WIDTH := 3.5
const CURVE_WIDTH := 2.0
const LEGEND_SIZE := 22
const AXIS_SIZE := 15
const FREERIDE_BAND := 5.0

## Modèle partagé (workout_chart_model.gd), donné par main.gd.
var model = null
var mode := "reduced"
var draw_count := 0       # nombre de dessins, pour les tests


func _init() -> void:
	name = "WorkoutChart"
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	custom_minimum_size = Vector2(0.0, 56.0)
	draw.connect(_on_draw)


func set_mode(value: String) -> void:
	mode = value if value in MODES else "reduced"
	queue_redraw()


## Une nouvelle seconde de séance (ou une nouvelle taille) : dessin redemandé.
func refresh() -> void:
	if is_visible_in_tree():
		queue_redraw()


## Texte de la légende : [{text, color}] de la valeur courante de chaque courbe affichée.
static func legend(current: Dictionary, chart_mode: String) -> Array:
	var out: Array = []
	var p = current.get("power", null)
	out.append({"text": "—" if p == null else "%d W" % int(round(float(p))), "color": POWER_COLOR})
	if chart_mode == "full":
		var h = current.get("hr", null)
		out.append({"text": "—" if h == null else "%d bpm" % int(round(float(h))), "color": HR_COLOR})
		var c = current.get("cadence", null)
		out.append({"text": "—" if c == null else "%d rpm" % int(round(float(c))), "color": CADENCE_COLOR})
	return out


func _on_draw() -> void:
	draw_count += 1
	if model == null or mode == "hidden":
		return
	var w := size.x
	var h := size.y
	if w < 8.0 or h < 8.0:
		return
	draw_rect(Rect2(0.0, 0.0, w, h), BG_COLOR)
	var geo: Dictionary = model.geometry(w, h)
	var sc: Dictionary = geo["scales"]
	var font := ThemeDB.fallback_font
	# Graduations de la puissance.
	var w_top: float = sc["watts"][1]
	for tick in sc["watts_ticks"]:
		var y := h - float(tick) / w_top * h
		draw_line(Vector2(0.0, y), Vector2(w, y), GRID_COLOR, 1.0)
		if mode == "full" and float(tick) > 0.0 and y > AXIS_SIZE:
			draw_string(font, Vector2(4.0, y - 2.0), "%d" % int(tick), HORIZONTAL_ALIGNMENT_LEFT, -1, AXIS_SIZE, TEXT_COLOR)
	# Profil des watts cibles, atténué ; roue libre : bande basse grise.
	for poly in geo["profile"]:
		var pts: PackedVector2Array = poly["polygon"]
		if pts.size() < 4 or absf(pts[3].x - pts[0].x) < 0.5:
			continue
		var color: Color = poly["color"]
		if int(poly["zone"]) < 0:
			draw_rect(Rect2(pts[0].x, h - FREERIDE_BAND, pts[3].x - pts[0].x, FREERIDE_BAND), color)
			continue
		if minf(pts[1].y, pts[2].y) >= h - 0.5:
			continue
		color.a = PROFILE_ALPHA
		draw_colored_polygon(pts, color)
	# Courbes : FC et cadence d'abord, puissance par-dessus.
	var curves: Dictionary = geo["curves"]
	if mode == "full":
		_draw_lines(curves.get("hr", []), HR_COLOR, CURVE_WIDTH)
		_draw_lines(curves.get("cadence", []), CADENCE_COLOR, CURVE_WIDTH)
	_draw_lines(curves.get("power", []), POWER_COLOR, POWER_WIDTH)
	# Curseur de position (profil connu).
	if model.has_profile:
		var cx: float = geo["cursor_x"]
		draw_line(Vector2(cx, 0.0), Vector2(cx, h), UiTheme.INK, 2.0)
	# Légende, alignée à droite, de gauche à droite : puissance, FC, cadence.
	var items := legend(geo["current"], mode)
	var widths: Array = []
	var total := 0.0
	for it in items:
		var tw := font.get_string_size(it["text"], HORIZONTAL_ALIGNMENT_LEFT, -1, LEGEND_SIZE).x
		widths.append(tw)
		total += tw + 18.0
	var x := w - total - 4.0
	for i in range(items.size()):
		draw_string_outline(font, Vector2(x, LEGEND_SIZE + 2.0), items[i]["text"], HORIZONTAL_ALIGNMENT_LEFT, -1, LEGEND_SIZE, 5, UiTheme.OUTLINE)
		draw_string(font, Vector2(x, LEGEND_SIZE + 2.0), items[i]["text"], HORIZONTAL_ALIGNMENT_LEFT, -1, LEGEND_SIZE, items[i]["color"])
		x += float(widths[i]) + 18.0


func _draw_lines(lines: Array, color: Color, width: float) -> void:
	for pts in lines:
		var p: PackedVector2Array = pts
		if p.size() >= 2:
			draw_polyline(p, color, width, true)
		elif p.size() == 1:
			draw_circle(p[0], width, color)
