extends Panel

## Affichage de l'entraînement ERG (Lot N7, SRS §6 et §13, sprint 4) : bandeau (nom, bloc i/n, type,
## cible biais compris, temps restant, cible suivante) et histogramme des blocs sur toute la largeur,
## bloc en cours mis en évidence et curseur de position. Caché en SIM (objet `erg` absent).
##
## Ne calcule pas l'état de l'entraînement : lit le résultat de `erg_view_model.gd` (lot I6) et l'objet
## `erg` de la trame. Le profil des blocs (durées et fractions de FTP) vient de l'élément `workouts` du
## contrat v1.1 (`profile`), donné par `set_profiles()` ; sans profil connu (core v1, liste pas encore
## reçue, profil coupé), l'histogramme se replie sur une bande de `block_count` cases égales.
## ERG d'une session libre (lot O18, `kind` = `free` ou `cadence`) : bandeau sans type de bloc ni bloc
## suivant, histogramme vide (pas de blocs).
## Pas de class_name : charger par preload("res://scripts/erg_view.gd").

const UiTheme := preload("res://scripts/ui_theme.gd")
const ErgViewModel := preload("res://scripts/erg_view_model.gd")

## Zones de Coggan, mêmes seuils que `openride-core summary` (session_summary.ZONES), en % de FTP.
const ZONE_HIGH_PCT := [55.0, 75.0, 90.0, 105.0, 120.0, 150.0]
const ZONE_COLORS := [
	UiTheme.ZONE_1,   # Z1 récupération
	UiTheme.ZONE_2,   # Z2 endurance
	UiTheme.ZONE_3,   # Z3 tempo
	UiTheme.ZONE_4,   # Z4 seuil
	UiTheme.ZONE_5,   # Z5 PMA
	UiTheme.ZONE_6,   # Z6 anaérobie
	UiTheme.ZONE_7,   # Z7 neuromusculaire
]
const FREERIDE_COLOR := UiTheme.FREERIDE
## Blocs autres que le bloc en cours : bien visibles du début à la fin, pour se préparer aux efforts
## (retour d'essai du 25 octobre) ; le bloc en cours garde son cadre et son curseur.
const DIM_ALPHA := 0.85
const PAST_DARKEN := 0.35      # blocs déjà faits, assombris

const BLOCK_TYPE_LABELS := {
	"warmup": "Échauffement",
	"steady": "Bloc stable",
	"interval_on": "Effort",
	"interval_off": "Récupération",
	"ramp": "Rampe",
	"cooldown": "Retour au calme",
	"freeride": "Roue libre",
}

const PANEL_HEIGHT := 140.0
const BOTTOM_OFFSET := 15.0    # en bas de l'écran : le profil d'altitude du HUD est caché en ERG (28/10)
const SIDE_MARGIN := 40.0

var title_label: Label
var target_label: Label
var remaining_label: Label
var next_label: Label
var histogram: Control
## Courbes de la séance (lot O14), à la place de l'histogramme quand le réglage `render.chart` n'est pas
## `hidden` ; le profil des blocs y est dessiné par workout_chart_model.gd.
var chart: Control = null

var ftp_w: float = 0.0
## Nom d'entraînement -> profil (liste de [durée_s, fraction début, fraction fin]).
var _profiles: Dictionary = {}
var _erg: Dictionary = {}
var _eval: Dictionary = {}
var _bars: Array = []


func _init() -> void:
	_build_ui()
	visible = false


func _build_ui() -> void:
	name = "ErgView"
	# Fond sombre sous la ligne des textes seulement ; le graphique en dessous garde son fond léger
	# (UiTheme.CHART_BG), pour voir la route à travers.
	add_theme_stylebox_override("panel", StyleBoxEmpty.new())
	anchor_left = 0.0
	anchor_right = 1.0
	anchor_top = 1.0
	anchor_bottom = 1.0
	offset_left = SIDE_MARGIN
	offset_right = -SIDE_MARGIN
	offset_bottom = -BOTTOM_OFFSET
	offset_top = -BOTTOM_OFFSET - PANEL_HEIGHT
	grow_vertical = Control.GROW_DIRECTION_BEGIN
	mouse_filter = Control.MOUSE_FILTER_IGNORE

	var vbox := VBoxContainer.new()
	vbox.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT, Control.PRESET_MODE_KEEP_SIZE, 0)
	vbox.add_theme_constant_override("separation", 4)
	add_child(vbox)

	var header := PanelContainer.new()
	header.name = "ErgHeader"
	header.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := StyleBoxFlat.new()
	style.bg_color = UiTheme.PANEL_BG
	style.set_corner_radius_all(8)
	style.set_content_margin_all(8)
	header.add_theme_stylebox_override("panel", style)
	vbox.add_child(header)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 24)
	header.add_child(row)
	title_label = _label(row, 24, true)
	target_label = _label(row, 36, false)
	remaining_label = _label(row, 36, false)
	next_label = _label(row, 22, false)
	next_label.modulate = UiTheme.HUD_DIM
	next_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	title_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER

	histogram = Control.new()
	histogram.name = "ErgHistogram"
	histogram.size_flags_vertical = Control.SIZE_EXPAND_FILL
	histogram.custom_minimum_size = Vector2(0.0, 56.0)
	histogram.mouse_filter = Control.MOUSE_FILTER_IGNORE
	histogram.draw.connect(_on_histogram_draw)
	vbox.add_child(histogram)


func _label(parent: Control, font_size: int, expand: bool) -> Label:
	var l := Label.new()
	l.add_theme_font_size_override("font_size", font_size)
	if expand:
		# Seul le titre peut être coupé : les chiffres (cible, temps restant) gardent leur largeur.
		l.clip_text = true
		l.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(l)
	return l


## Profils connus, à partir des éléments `workouts` du contrat v1.1 (`name`, `profile`, `profile_truncated`).
func set_profiles(items: Array) -> void:
	_profiles.clear()
	for item in items:
		if typeof(item) != TYPE_DICTIONARY or bool(item.get("profile_truncated", false)):
			continue
		var prof = item.get("profile", [])
		if typeof(prof) == TYPE_ARRAY and not (prof as Array).is_empty():
			_profiles[str(item.get("name", ""))] = prof


## Profil v1.1 d'un entraînement connu ([] sinon), pour le graphique des courbes.
func profile_of(workout_name: String) -> Array:
	return _profiles.get(workout_name, [])


## Installe la vue des courbes sous le bandeau ; l'histogramme se replie quand elle est affichée.
func set_chart(view: Control, mode: String) -> void:
	if chart == null:
		chart = view
		chart.size_flags_vertical = Control.SIZE_EXPAND_FILL
		histogram.get_parent().add_child(chart)
	chart.set_mode(mode)
	chart.visible = mode != "hidden"
	histogram.visible = mode == "hidden"


func has_profile(workout_name: String) -> bool:
	return _profiles.has(workout_name)


## Met à jour l'affichage : `erg` est l'objet de la trame (ou null), `erg_eval` le résultat de
## `erg_view_model.gd`. Rien n'est affiché sans `erg` (mode SIM).
func update_display(erg: Variant, erg_eval: Dictionary) -> void:
	var on := typeof(erg) == TYPE_DICTIONARY and not (erg as Dictionary).is_empty() and bool(erg_eval.get("visible", false))
	visible = on
	if not on:
		_erg = {}
		_eval = {}
		return
	_erg = erg
	_eval = erg_eval
	var lines := banner_lines(_erg, _eval)
	title_label.text = lines["title"]
	target_label.text = lines["target"]
	remaining_label.text = lines["remaining"]
	next_label.text = lines["next"]
	histogram.queue_redraw()


## Textes du bandeau (fonction pure, testée sans scène).
static func banner_lines(erg: Dictionary, erg_eval: Dictionary) -> Dictionary:
	if is_free(erg):
		var state: String = str(erg_eval.get("next_text", ""))
		if str(erg_eval.get("paused_text", "")) != "":
			state = "En pause" if state == "" else state + " (pause)"
		return {"title": str(erg_eval.get("title", "")), "target": str(erg_eval.get("target_text", "")),
			"remaining": "", "next": state}
	var b_type := str(erg.get("block_type", "steady"))
	var title := "%s · %s" % [erg_eval.get("title", ""), BLOCK_TYPE_LABELS.get(b_type, b_type)]
	var remaining := str(erg_eval.get("remaining_text", ""))
	if str(erg_eval.get("paused_text", "")) != "":
		remaining += " (pause)"
	var next := ""
	var next_w: Variant = erg.get("next_target_w", null)
	if int(erg.get("block_index", 1)) < int(erg.get("block_count", 1)):
		next = "Ensuite : " + ("roue libre" if next_w == null else "%d W" % int(round(float(next_w))))
	return {"title": title, "target": str(erg_eval.get("target_text", "")), "remaining": remaining, "next": next}


## ERG d'une session libre (lot O18) : pas de blocs.
static func is_free(erg: Dictionary) -> bool:
	return str(erg.get("kind", "workout")) in ["free", "cadence"]


## Zone de Coggan (0 à 6) d'une fraction de FTP.
static func zone_of_frac(frac: float) -> int:
	var pct := frac * 100.0
	for i in range(ZONE_HIGH_PCT.size()):
		if pct < ZONE_HIGH_PCT[i]:
			return i
	return ZONE_HIGH_PCT.size()


static func zone_color(frac: Variant) -> Color:
	if frac == null:
		return FREERIDE_COLOR
	return ZONE_COLORS[zone_of_frac(float(frac))]


## Blocs au format de `ErgViewModel.profile_bars` à partir d'un profil v1.1 ([durée, début, fin]).
static func profile_to_blocks(profile: Array) -> Array:
	var out: Array = []
	for t in profile:
		if typeof(t) != TYPE_ARRAY or (t as Array).size() < 3:
			continue
		var free: bool = t[1] == null
		out.append({"type": "freeride" if free else "steady", "duration_s": float(t[0]),
				"start_frac": null if free else float(t[1]), "end_frac": null if free else float(t[2])})
	return out


## Géométrie de l'histogramme (fonction pure) : barres `profile_bars` complétées de `color`, `current`,
## `past`, et `cursor_x`. Avec un profil dont le nombre de blocs correspond à `block_count`, les largeurs
## suivent les durées et le curseur est placé au temps écoulé ; sinon bande de cases égales.
static func layout(erg: Dictionary, erg_eval: Dictionary, profile: Variant, ftp: float, width: float, height: float) -> Dictionary:
	var idx := int(erg.get("block_index", 1))
	var count := maxi(1, int(erg.get("block_count", 1)))
	var progress := clampf(float(erg_eval.get("progress", 0.0)), 0.0, 1.0)
	var bars: Array = []
	var from_profile := false
	if typeof(profile) == TYPE_ARRAY and (profile as Array).size() == count:
		var blocks := profile_to_blocks(profile)
		if blocks.size() == count:
			bars = ErgViewModel.profile_bars(blocks, maxf(ftp, 1.0), width, height)
			from_profile = bars.size() == count
	if from_profile:
		for b in bars:
			var blk: Dictionary = blocks_frac(profile, int(b["index"]) - 1)
			b["color"] = zone_color(blk["mean"])
	else:
		bars = []
		var cur_frac: Variant = null
		if str(erg.get("block_type", "")) != "freeride" and ftp > 0.0:
			cur_frac = float(erg.get("target_w", 0.0)) / ftp
		for i in range(count):
			var x0 := width * float(i) / float(count)
			var x1 := width * float(i + 1) / float(count)
			var is_cur := i + 1 == idx
			var h := height * (0.8 if is_cur else 0.5)
			bars.append({"index": i + 1, "x0": x0, "x1": x1, "width": x1 - x0, "h0": h, "h1": h,
					"polygon": PackedVector2Array([Vector2(x0, height), Vector2(x0, height - h),
							Vector2(x1, height - h), Vector2(x1, height)]),
					"color": zone_color(cur_frac) if is_cur else FREERIDE_COLOR})
	var cursor_x := 0.0
	for b in bars:
		b["current"] = int(b["index"]) == idx
		b["past"] = int(b["index"]) < idx
		if b["current"]:
			cursor_x = float(b["x0"]) + progress * float(b["width"])
	return {"bars": bars, "cursor_x": cursor_x, "from_profile": from_profile}


static func blocks_frac(profile: Array, i: int) -> Dictionary:
	var t: Array = profile[i]
	if t[1] == null:
		return {"mean": null}
	return {"mean": (float(t[1]) + float(t[2] if t[2] != null else t[1])) / 2.0}


func _on_histogram_draw() -> void:
	if _erg.is_empty() or is_free(_erg):
		return
	var w := histogram.size.x
	var h := histogram.size.y
	var prof: Variant = _profiles.get(str(_erg.get("workout_name", "")), null)
	var lay := layout(_erg, _eval, prof, ftp_w, w, h)
	_bars = lay["bars"]
	histogram.draw_rect(Rect2(0, 0, w, h), UiTheme.CHART_BG)
	var cur: Dictionary = {}
	for b in _bars:
		var c: Color = b["color"]
		if b["past"]:
			c = c.darkened(PAST_DARKEN)
		if not b["current"]:
			c.a = DIM_ALPHA
		else:
			cur = b
		histogram.draw_colored_polygon(b["polygon"], c)
		histogram.draw_line(Vector2(b["x0"], 0.0), Vector2(b["x0"], h), UiTheme.SHADOW_LINE, 1.0)
	if not cur.is_empty():
		# Contour blanc du bloc en cours.
		var poly: PackedVector2Array = cur["polygon"]
		var outline := PackedVector2Array(poly)
		outline.append(poly[0])
		histogram.draw_polyline(outline, UiTheme.INK, 2.0)
	var cx: float = lay["cursor_x"]
	histogram.draw_line(Vector2(cx, 0.0), Vector2(cx, h), UiTheme.INK, 3.0)
	histogram.draw_circle(Vector2(cx, 4.0), 5.0, UiTheme.INK)
