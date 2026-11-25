extends RefCounted

## Jauge de réserve W′ des bots (lot RW), règle et dessin uniques, partagés par l'encart des bots de la session
## libre (bot_hud_model.gd, hud_view.gd) et par les listes des modes compétitifs : liste des coureurs du Dernier
## survivant, bande de course du Grand Prix et de la Course, liste du vélodrome. Pas de class_name :
## preload("res://scripts/bot_reserve.gd").
##
## Règle (celle du lot T15, inchangée) : réserve = `wbal_pct` du bot dans la trame `state`, ramenée de 0 à 1 ;
## sans champ (bot à puissance constante, fantôme, bot loin allégé par `bots.light_frame`), −1 : pas de barre.
## Le core n'envoie `wbal_pct` que pour les 5 bots les plus proches (`bots.FULL_FRAME_BOTS`) : la valeur n'est
## pas gardée d'une trame à l'autre (elle change), comme dans bots_view_model.gd.
## Dessin : trait fin bleu clair (`UiTheme.WBAL`) sous le nom, sur un fond discret ; une ligne de légende écrite
## (LEGEND) sous chaque liste de mode où une barre est visible, pour que le trait ne parle pas par sa couleur seule.

const UiTheme := preload("res://scripts/ui_theme.gd")

const COLOR := UiTheme.WBAL
const BG_DARK := UiTheme.TRACK               # fond de la barre sur un panneau sombre (HUD, DS, vélodrome)
const BG_LIGHT := UiTheme.WBAL_TRACK_LIGHT   # fond de la barre sur le papier clair du Grand Prix
const HEIGHT := 3.0
const LEGEND := "Trait bleu : réserve des bots"
## Pas de redessin pour moins de 1 % d'écart (12 lignes à chaque image, lot DS8).
const STEP := 0.01


## Réserve d'un bot de la trame, de 0 à 1 ; −1 sans `wbal_pct`.
static func fraction(b) -> float:
	if not b is Dictionary:
		return -1.0
	var w = b.get("wbal_pct", null)
	if not (w is float or w is int):
		return -1.0
	return clampf(float(w) / 100.0, 0.0, 1.0)


## id du bot -> réserve (0 à 1), pour les seuls bots de la trame qui portent `wbal_pct`.
static func by_id(bots) -> Dictionary:
	var out := {}
	if not bots is Array:
		return out
	for b in bots:
		if b is Dictionary and str(b.get("id", "")) != "":
			var f := fraction(b)
			if f >= 0.0:
				out[str(b["id"])] = f
	return out


## Vrai si une ligne au moins montre une barre (champ `wbal` ≥ 0) : la légende s'affiche alors.
static func any_shown(rows: Array) -> bool:
	for r in rows:
		if r is Dictionary and float(r.get("wbal", -1.0)) >= 0.0:
			return true
	return false


## Barre d'une ligne de liste (conteneurs) : hauteur fixe même sans réserve, pour que la liste ne bouge pas
## quand un bot entre ou sort des 5 plus proches.
static func make_bar(bg: Color = BG_DARK) -> Control:
	var bar := Control.new()
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	bar.custom_minimum_size = Vector2(0.0, HEIGHT)
	bar.set_meta("frac", -1.0)
	bar.set_meta("bg", bg)
	bar.draw.connect(func() -> void: draw_bar(bar))
	return bar


## Pose la réserve (−1 : rien dessiné) ; ne redessine que si elle a changé d'au moins STEP.
static func set_bar(bar: Control, frac: float) -> void:
	var old := float(bar.get_meta("frac", -1.0))
	var shown := frac >= 0.0
	if shown == (old >= 0.0) and (not shown or absf(frac - old) < STEP):
		return
	bar.set_meta("frac", frac if shown else -1.0)
	bar.queue_redraw()


static func draw_bar(bar: Control) -> void:
	var frac := float(bar.get_meta("frac", -1.0))
	if frac < 0.0:
		return
	bar.draw_rect(Rect2(Vector2.ZERO, Vector2(bar.size.x, HEIGHT)), bar.get_meta("bg", BG_DARK))
	if frac > 0.0:
		bar.draw_rect(Rect2(Vector2.ZERO, Vector2(bar.size.x * frac, HEIGHT)), COLOR)
