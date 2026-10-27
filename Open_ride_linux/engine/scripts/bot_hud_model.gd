extends RefCounted

## Modèle de vue de l'encart des bots du HUD (lot T15, série T), sans aucun nœud. Pas de class_name :
## charger par preload("res://scripts/bot_hud_model.gd").
##
## Entrées : sortie de bots_view_model.view() (bots du plus loin devant au plus loin derrière, avec les
## champs de profil de la révision 1.4 quand le core les donne) et `race` = {bot_ahead, bot_behind,
## jerseys} de la trame `state` (bots_view_model.race()).
## `view(bots_view, race)` rend :
## - `neighbors` : voisins immédiats, [{dir: "ahead" | "behind", name, gap_text, color}] ; une ligne
##   disparaît quand le champ vaut `null` ou que le bot n'est plus dans la liste ;
## - `rows` : une ligne par bot, [{name, detail, gap_text, color, wbal, jersey}] : nom (suivi du profil
##   traduit quand il diffère du nom), FTP en W et en W/kg (`cp_w`, `mass_kg`), réserve W′ de 0 à 1
##   (`wbal`, −1 sans champ : jauge cachée), maillot porté (`sprint`, `kom` ou "") ;
## - `jerseys_text` : porteurs des maillots de la séance, « Vert : toi · Pois : Grimpeur », "" sans
##   porteur ;
## - `visible` : vrai dès qu'il y a un bot.
## Un bot sans champ de profil (bot à puissance constante, fantôme, core sans T12) n'a que son nom, son
## maillot et son écart. Écarts au format des blocs segment : « +8,4 s », « −3,1 s ».
## `rows_that_fit(view, height_px)` : nombre de lignes de bots qui tiennent dans la hauteur donnée sous
## les voisins et la ligne des maillots (priorité : voisins, maillots, puis bots).

const SegmentHudModel := preload("res://scripts/segment_hud_model.gd")
const RoadsideModel := preload("res://scripts/roadside_model.gd")

const PROFILE_NAMES := {"climber": "Grimpeur", "rouleur": "Rouleur", "sprinter": "Sprinteur", "diesel": "Diesel"}
const JERSEY_NAMES := {"sprint": "Vert", "kom": "Pois"}
const RIDER := "me"
const RIDER_NAME := "toi"
## Hauteurs (px) d'une ligne de voisin, d'une ligne de bot, de la ligne des maillots, et marge du panneau.
const NEIGHBOR_ROW := 26.0
const BOT_ROW := 30.0
const JERSEY_ROW := 24.0
const PADDING := 12.0


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


static func row(b: Dictionary) -> Dictionary:
	var name := str(b.get("name", b.get("id", "")))
	var prof := profile_name(b.get("profile", null))
	if prof != "" and prof != name:
		name += " · " + prof
	var wbal = b.get("wbal_pct", null)
	var jersey = b.get("jersey", null)
	return {"name": name, "detail": ftp_text(b.get("cp_w", null), b.get("mass_kg", null)),
		"gap_text": SegmentHudModel.gap_text(float(b.get("gap_s", 0.0))), "color": b.get("color", Color.WHITE),
		"wbal": clampf(float(wbal) / 100.0, 0.0, 1.0) if (wbal is float or wbal is int) else -1.0,
		"jersey": str(jersey) if JERSEY_NAMES.has(str(jersey)) else ""}


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
	var neighbors: Array = []
	for pair in [["ahead", "bot_ahead"], ["behind", "bot_behind"]]:
		var b := _find(bots_view, race.get(pair[1], null))
		if not b.is_empty():
			neighbors.append({"dir": pair[0], "name": str(b.get("name", b.get("id", ""))),
				"gap_text": SegmentHudModel.gap_text(float(b.get("gap_s", 0.0))), "color": b.get("color", Color.WHITE)})
	var rows: Array = []
	for b in bots_view:
		rows.append(row(b))
	return {"neighbors": neighbors, "rows": rows, "jerseys_text": jerseys_text(bots_view, race.get("jerseys", null)),
		"visible": not bots_view.is_empty()}


## Lignes de bots affichables dans `height_px` (au moins 0, au plus toutes).
static func rows_that_fit(v: Dictionary, height_px: float) -> int:
	var used: float = PADDING + NEIGHBOR_ROW * v.get("neighbors", []).size()
	if str(v.get("jerseys_text", "")) != "":
		used += JERSEY_ROW
	var n: int = int(floor((height_px - used) / BOT_ROW))
	return clampi(n, 0, v.get("rows", []).size())


## Hauteur du panneau pour `n_rows` lignes de bots.
static func height(v: Dictionary, n_rows: int) -> float:
	var h: float = PADDING + NEIGHBOR_ROW * v.get("neighbors", []).size() + BOT_ROW * n_rows
	if str(v.get("jerseys_text", "")) != "":
		h += JERSEY_ROW
	return h
