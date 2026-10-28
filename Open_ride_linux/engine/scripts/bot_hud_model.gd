extends RefCounted

## Modèle de vue de l'encart des bots du HUD (lot T15, série T), sans aucun nœud. Pas de class_name :
## charger par preload("res://scripts/bot_hud_model.gd").
##
## Entrées : sortie de bots_view_model.view() (bots du plus loin devant au plus loin derrière, avec les
## champs de profil de la révision 1.4 quand le core les donne) et `race` = {bot_ahead, bot_behind,
## jerseys} de la trame `state` (bots_view_model.race()).
## `view(bots_view, race)` rend :
## - `rows` : une ligne par bot, [{name, detail, gap_text, color, wbal, jersey, dir}] : nom (suivi du
##   profil traduit quand il diffère du nom), FTP en W et en W/kg (`cp_w`, `mass_kg`), réserve W′ de 0 à 1
##   (`wbal`, −1 sans champ : jauge cachée), maillot porté (`sprint`, `kom` ou ""), et `dir` = "ahead" ou
##   "behind" pour les voisins immédiats (`bot_ahead`, `bot_behind` ; "" sinon, ou quand le champ vaut
##   `null`) : les voisins sont marqués sur leur propre ligne, sans ligne à part (lot X22) ;
## - `rider_index` : nombre de bots devant le cycliste (sa place dans la liste) ;
## - `jerseys_text` : porteurs des maillots de la séance, « Vert : toi · Pois : Grimpeur », "" sans
##   porteur ;
## - `visible` : vrai dès qu'il y a un bot.
## Un bot sans champ de profil (bot à puissance constante, fantôme, core sans T12) n'a que son nom, son
## maillot et son écart. Écarts au format des blocs segment : « +8,4 s », « −3,1 s ».
## `fit(view, height_px)` : lignes affichées dans la hauteur donnée, {first, count, jerseys}. Priorité :
## les deux lignes autour du cycliste (ses voisins), toujours ; puis la ligne des maillots ; puis d'autres
## lignes, en élargissant la fenêtre autour du cycliste.

const SegmentHudModel := preload("res://scripts/segment_hud_model.gd")
const RoadsideModel := preload("res://scripts/roadside_model.gd")

const PROFILE_NAMES := {"climber": "Grimpeur", "rouleur": "Rouleur", "sprinter": "Sprinteur", "diesel": "Diesel"}
const JERSEY_NAMES := {"sprint": "Vert", "kom": "Pois"}
const RIDER := "me"
const RIDER_NAME := "toi"
## Hauteurs (px) d'une ligne de bot, de la ligne des maillots, et marge du panneau ; lignes toujours
## affichées autour du cycliste.
const BOT_ROW := 30.0
const JERSEY_ROW := 24.0
const PADDING := 8.0
const MIN_ROWS := 2


static func profile_name(profile) -> String:
	return "" if profile == null else str(PROFILE_NAMES.get(str(profile), ""))


## « 248 W · 4,1 W/kg » ; « 248 W » sans masse ; "" sans `cp_w`.
static func ftp_text(cp_w, mass_kg) -> String:
	if not (cp_w is float or cp_w is int) or float(cp_w) <= 0.0:
		return ""
	var txt: String = "%d W" % int(round(float(cp_w)))
	if (mass_kg is float or mass_kg is int) and float(mass_kg) > 0.0:
		txt += " · " + RoadsideModel.format_dec(float(cp_w) / float(mass_kg), 1) + " W/kg"
	return txt


static func row(b: Dictionary, dir := "") -> Dictionary:
	var name := str(b.get("name", b.get("id", "")))
	var prof := profile_name(b.get("profile", null))
	if prof != "" and prof != name:
		name += " · " + prof
	var wbal = b.get("wbal_pct", null)
	var jersey = b.get("jersey", null)
	return {"name": name, "detail": ftp_text(b.get("cp_w", null), b.get("mass_kg", null)),
		"gap_text": SegmentHudModel.gap_text(float(b.get("gap_s", 0.0))), "color": b.get("color", Color.WHITE),
		"wbal": clampf(float(wbal) / 100.0, 0.0, 1.0) if (wbal is float or wbal is int) else -1.0,
		"jersey": str(jersey) if JERSEY_NAMES.has(str(jersey)) else "", "dir": dir}


static func _find(bots_view: Array, id) -> Dictionary:
	if id == null:
		return {}
	for b in bots_view:
		if str(b.get("id", "")) == str(id):
			return b
	return {}


static func jerseys_text(bots_view: Array, jerseys) -> String:
	if not (jerseys is Dictionary):
		return ""
	var parts: Array = []
	for kind in ["sprint", "kom"]:
		var holder = jerseys.get(kind, null)
		if holder == null or str(holder) == "":
			continue
		var who := RIDER_NAME
		if str(holder) != RIDER:
			who = str(_find(bots_view, holder).get("name", holder))
		parts.append("%s : %s" % [JERSEY_NAMES[kind], who])
	return " · ".join(parts)


static func view(bots_view: Array, race: Dictionary) -> Dictionary:
	var ahead = race.get("bot_ahead", null)
	var behind = race.get("bot_behind", null)
	var rows: Array = []
	var rider_index := 0
	for b in bots_view:
		var id := str(b.get("id", ""))
		var dir := "ahead" if ahead != null and id == str(ahead) else ("behind" if behind != null and id == str(behind) else "")
		rows.append(row(b, dir))
		if float(b.get("gap_s", 0.0)) > 0.0:
			rider_index += 1
	return {"rows": rows, "rider_index": rider_index,
		"jerseys_text": jerseys_text(bots_view, race.get("jerseys", null)), "visible": not bots_view.is_empty()}


## Lignes affichées dans `height_px` : {first, count, jerseys}. Les MIN_ROWS lignes autour du cycliste
## restent même sans place ; la ligne des maillots puis les autres lignes seulement si elles tiennent.
static func fit(v: Dictionary, height_px: float) -> Dictionary:
	var total: int = v.get("rows", []).size()
	var count: int = mini(MIN_ROWS, total)
	var jerseys: bool = str(v.get("jerseys_text", "")) != "" and height(count, true) <= height_px
	while count < total and height(count + 1, jerseys) <= height_px:
		count += 1
	return {"first": window_start(int(v.get("rider_index", 0)), count, total), "count": count, "jerseys": jerseys}


## Première ligne d'une fenêtre de `count` lignes autour du cycliste (une ligne de plus devant quand le
## compte est impair), dans la liste.
static func window_start(rider_index: int, count: int, total: int) -> int:
	return clampi(rider_index - int(ceil(count / 2.0)), 0, maxi(total - count, 0))


## Hauteur du panneau pour `n_rows` lignes de bots, avec ou sans la ligne des maillots.
static func height(n_rows: int, jerseys: bool) -> float:
	return PADDING + BOT_ROW * n_rows + (JERSEY_ROW if jerseys else 0.0)
