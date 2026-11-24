extends RefCounted

## Ligue d'hiver au menu (série CH, lot CH4a, maquettes CH0 01 à 03 validées le 21 novembre 2026) : ligne de
## l'accueil, écran de la ligue (actions à gauche, classement général à droite), écran Prêt d'une manche et lignes
## du bilan. Ne décide rien : lit le message `league` du core (révision 1.30, réponse à `league_status` et
## `league_new`) et `summary.league`. Mots écrits avant la couleur : la ligne du cycliste est « Toi », encadrée.
## Pas de class_name : charger par preload("res://scripts/league_view_model.gd").

const SCREEN := "league"
const SCREENS := [SCREEN]
const RUN_ID := "league_run"
const NEW_ID := "league_new"
const PALMARES_ID := "league_palmares"   # lot CH6 : saisons closes, fiche à droite au focus
const MONTHS := ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
## Comment la manche s'enregistre (fin de séance commune RT2 : après l'arrivée on roule encore, « A maintenu =
## bilan ») : écrit sur la fiche de la ligue et sur la ligne « Démarrer ».
const RECORD_HINT := "La manche compte au bilan : après l'arrivée, Y puis A maintenu."
const STYLES := {"climber": "grimpeur", "rouleur": "rouleur", "sprinter": "sprinteur", "diesel": "diesel"}

## Saison du dernier message `league` (null : pas de saison) ; `loaded` : un message est arrivé (sinon, core sans
## ligue : la ligne de l'accueil n'apparaît pas).
var season = null
## Palmarès (`history` du message `league`, révision 1.35, lot CH6) : saisons closes, la plus récente d'abord.
var history: Array = []
var loaded := false
var message := ""
## Jour de la semaine (0 dimanche … 6 samedi, comme Time) ; -1 : celui du système (tests : jour imposé).
var weekday := -1


func on_league(msg: Dictionary) -> void:
	loaded = true
	season = msg.get("season") if msg.get("season") is Dictionary else null
	history = (msg.get("history") as Array).duplicate() if msg.get("history") is Array else []
	message = ""


## Détail de la ligne « Ligue d'hiver » de l'accueil (maquette 01).
func home_detail() -> String:
	if not loaded:
		return ""
	if season == null:
		return "8 semaines contre 11 rivaux"
	return str(season.get("home_line", ""))


func _round() -> Dictionary:
	return season.get("round", {}) if season is Dictionary and season.get("round") is Dictionary else {}


## Éléments de l'écran de la ligue : courir la manche de la semaine (grisée et expliquée sinon), ou commencer une
## saison quand il n'y en a pas (ou qu'elle est finie).
func items() -> Array:
	var out := _run_items()
	if not history.is_empty():   # lot CH6 : palmarès dès qu'une saison est close
		out.append(_item(PALMARES_ID, "Palmarès", true,
			"%d saison%s close%s" % [history.size(), "s" if history.size() > 1 else "", "s" if history.size() > 1 else ""]))
	return out


func _run_items() -> Array:
	if season == null or season.get("closed") != null:
		var n := 1 if season == null else int(season.get("number", 0)) + 1
		return [_item(NEW_ID, "Commencer la saison %d" % n, true, "8 semaines, une manche par semaine")]
	var r := _round()
	var label := "Courir la manche %d : %s" % [int(r.get("index", 0)) + 1, str(r.get("short", ""))]
	var detail := ""
	if bool(season.get("paused", false)):
		detail = "saison en pause"
	elif bool(r.get("done", false)):   # libellé court : la ligne n'est pas coupée
		label = "Manche %d faite" % (int(r.get("index", 0)) + 1)
		detail = "prochaine lundi" if int(season.get("week", 1)) < int(season.get("weeks", 8)) else ""
	elif not bool(r.get("playable", false)):
		detail = "pas encore jouable dans cette version"
	return [_item(RUN_ID, label, bool(r.get("playable", false)), detail)]


static func _item(id: String, label: String, enabled := true, detail := "") -> Dictionary:
	return {"id": id, "label": label, "enabled": enabled, "detail": detail}


## Titre de l'écran : « Ligue d'hiver · saison 1 · semaine 3 sur 8 ».
func title() -> String:
	if season == null:
		return "Ligue d'hiver"
	return "Ligue d'hiver · saison %d · semaine %d sur %d" % [int(season.get("number", 1)), int(season.get("week", 1)),
		int(season.get("weeks", 8))]


static func ordinal(place: int) -> String:
	return "1er" if place == 1 else "%de" % place


static func _points(v) -> String:
	var f := float(v)
	return ("%d" % int(round(f)) if is_equal_approx(f, round(f)) else ("%.1f" % f).replace(".", ",")) + " pts"


## Lignes du tableau du classement (detail_card.gd, clé `table`) : place, nom (« Toi » pour le cycliste),
## caractère et équipe écrits, points, manches courues, couleur du maillot, ligne encadrée pour le cycliste.
static func table_rows(rows: Array, ftp_w: float, weeks := 8) -> Array:
	var out: Array = []
	for r in rows:
		if not (r is Dictionary):
			continue
		var me := bool(r.get("me", false))
		var style := ("FTP %d W" % int(round(ftp_w))) if me and ftp_w > 0.0 else ""
		if not me:   # caractère écrit ; l'équipe se lit à la pastille du maillot (la colonne est étroite)
			style = str(STYLES.get(str(r.get("style", "")).to_lower(), str(r.get("style", "")))).to_lower()
		out.append({"place": str(int(r.get("place", 0))), "name": "Toi" if me else str(r.get("name", "")),
			"style": style, "points": _points(r.get("points", 0)), "ran": "%d/%d" % [int(r.get("ran", 0)), weeks],
			"color": str(r.get("color", "")) if not me else "", "me": me})
	return out


## Fiche de droite de l'écran de la ligue (maquette 02) : classement général et lignes d'explication.
func sheet(ftp_w: float, focused := "") -> Dictionary:
	if focused == PALMARES_ID:
		return palmares_sheet()
	if season == null:
		return {"title": "Ligue d'hiver", "name": "Une saison de 8 semaines",
			"lines": ["Une manche par semaine, contre les mêmes 11 rivaux.",
				"Comptent : tes 6 meilleures manches sur 8.",
				"Fin de saison : podium et trophée."]}
	var done := 0
	for r in season.get("standings", []):
		if r is Dictionary and bool(r.get("me", false)):
			done = int(r.get("ran", 0))
	var r := _round()
	var lines: Array = []
	lines.append("Manche %d : %s, environ 27 min de course." % [int(r.get("index", 0)) + 1, str(r.get("title", ""))])
	if bool(r.get("open", false)):
		lines.append(_deadline())
	lines.append(RECORD_HINT)
	lines.append("Comptent : tes 6 meilleures manches sur 8.")
	lines.append("Classique : pas encore datée." if season.get("classic_day") == null
		else "Classique : le %s." % str(season["classic_day"]))
	return {"title": "Classement général · %d manche%s courue%s par toi" % [done, "s" if done > 1 else "", "s" if done > 1 else ""],
		"name": str(season.get("home_line", "")),
		"table": table_rows(season.get("standings", []), ftp_w, int(season.get("weeks", 8))), "lines": lines}


## Fiche du palmarès (lot CH6) : une ligne écrite par saison close, la plus récente d'abord.
func palmares_sheet() -> Dictionary:
	var lines: Array = []
	for h in history:
		if h is Dictionary:
			lines.append(palmares_line(h))
	return {"title": "Palmarès", "name": "Tes saisons de la ligue d'hiver", "lines": lines}


## Ligne d'une saison : « Saison 1 (23 nov. – 17 janv.) : 3e sur 12, 142 pts · Trophée de bronze · vainqueur
## Alain Asphalte, 188 pts » ; « tu as gagné la saison » quand le vainqueur est le cycliste.
static func palmares_line(h: Dictionary) -> String:
	var parts: Array = ["%s sur %d, %s" % [ordinal(int(h.get("place", 0))), int(h.get("of", 12)), _points(h.get("points", 0))]]
	if h.get("trophy") != null:
		parts.append(str(h["trophy"]))
	if bool(h.get("winner_me", false)):
		parts.append("tu as gagné la saison")
	else:
		parts.append("vainqueur %s, %s" % [str(h.get("winner", "")), _points(h.get("winner_points", 0))])
	if str(h.get("closed", "")) == "pause":
		parts.append("close après une longue pause")
	return "Saison %d (%s – %s) : %s" % [int(h.get("number", 0)), _short_date(str(h.get("start", ""))),
		_short_date(str(h.get("end", ""))), " · ".join(parts)]


static func _short_date(iso: String) -> String:
	var p := iso.split("-")
	if p.size() != 3:
		return iso
	return "%d %s %s" % [int(p[2]), MONTHS[clampi(int(p[1]) - 1, 0, 11)], p[0]]


## Mode de course de la manche de la semaine (`start.mode`, lot CH4c) : race, survivor, grandprix ou track.
func round_mode() -> String:
	return str(_round().get("mode", "race"))


## Terrain voulu par la manche (`round.terrain` du core) : boucle, arrivee_cote, grandprix ou piste.
func terrain() -> String:
	return str(_round().get("terrain", "boucle"))


## Raison écrite pour laquelle `route` ne convient pas au terrain de la manche ("" : il convient) ; `rmode` : mode du
## parcours ("track" pour un vélodrome, "" libre).
func route_problem(route: Dictionary, rmode := "") -> String:
	var loop := str(route.get("route_type", "")) == "loop"
	match terrain():
		"piste":
			return "" if rmode == "track" else "choisis le vélodrome (« Changer de parcours »)"
		"arrivee_cote":
			if rmode == "track" or loop:
				return "choisis un parcours en ligne (« Changer de parcours »)"
		"grandprix":
			if rmode == "track":
				return "choisis un parcours sur route (« Changer de parcours »)"
		_:
			if rmode == "track" or not loop:
				return "choisis une boucle (« Changer de parcours »)"
	return ""


## Ligne « Démarrer » de l'écran Prêt d'une manche sur `route` (entrée de la liste des parcours, `rmode` : son mode) :
## {enabled, detail} ; grisée et expliquée sur un parcours qui ne va pas au terrain, une manche courue ou pas jouable.
func ready(route: Dictionary, rmode := "") -> Dictionary:
	var r := _round()
	if season == null or r.is_empty():
		return {"enabled": false, "detail": "pas de saison en cours"}
	if bool(r.get("done", false)):
		return {"enabled": false, "detail": "manche déjà courue cette semaine"}
	if not bool(r.get("playable", false)):
		return {"enabled": false, "detail": "pas encore jouable dans cette version"}
	var why := route_problem(route, rmode)
	if why != "":
		return {"enabled": false, "detail": why}
	return {"enabled": true, "detail": ready_text()}


## Échéance de la manche ouverte : « À courir avant dimanche soir » et, en fin de semaine (saison commencée un
## samedi, par exemple), les jours qui restent écrits.
func _deadline() -> String:
	var wd := weekday if weekday >= 0 else int(Time.get_date_dict_from_system()["weekday"])
	var left := 1 if wd == 0 else 8 - wd   # jours restants, aujourd'hui compris (dimanche : 1)
	if left > 3:
		return "À courir avant dimanche soir."
	return "À courir avant dimanche soir : %s." % ("dernier jour" if left == 1 else "encore %d jours" % left)


## Boucle où courir la manche (`routes` : liste des parcours du core, `current` : parcours choisi,
## `mode_of` : mode d'un parcours, "" libre) : `current` si c'est une boucle, sinon la première boucle libre, sinon
## le premier circuit du Grand Prix (les parcours libres de départ sont en ligne) ; "" : aucune.
static func pick_loop(routes: Array, current: String, mode_of: Callable) -> String:
	if is_loop(routes, current):
		return current
	for m in ["", "grandprix"]:
		for r in routes:
			var id := str(r.get("id", "")) if r is Dictionary else ""
			if id != "" and str(mode_of.call(id)) == m and is_loop(routes, id):
				return id
	return ""


## Parcours où courir la manche selon son terrain (lot CH4c) : `current` s'il convient, sinon le premier qui
## convient, parcours libres d'abord, puis ceux du Grand Prix, puis les vélodromes (Grand Prix : boucles d'abord) ;
## "" : aucun.
func pick_route(routes: Array, current: String, mode_of: Callable) -> String:
	if _fits(routes, current, mode_of):
		return current
	# Grand Prix : une boucle d'abord (tours de la ligue, environ 27 min), un parcours en ligne sinon.
	for loop_only in ([true, false] if terrain() == "grandprix" else [false]):
		for m in ["", "grandprix", "track"]:
			for r in routes:
				var id := str(r.get("id", "")) if r is Dictionary else ""
				if id != "" and str(mode_of.call(id)) == m and _fits(routes, id, mode_of) \
						and (not loop_only or str(r.get("route_type", "")) == "loop"):
					return id
	return ""


func _fits(routes: Array, id: String, mode_of: Callable) -> bool:
	for r in routes:
		if r is Dictionary and str(r.get("id", "")) == id and id != "":
			return str(r.get("status", "ready")) == "ready" and route_problem(r, str(mode_of.call(id))) == ""
	return false


static func is_loop(routes: Array, id: String) -> bool:
	for r in routes:
		if r is Dictionary and str(r.get("id", "")) == id:
			return str(r.get("route_type", "")) == "loop" and str(r.get("status", "ready")) == "ready"
	return false


## Texte de la ligne « Démarrer » de l'écran Prêt d'une manche.
func ready_text() -> String:
	var r := _round()
	return "manche %d sur %d · environ 27 min · %s · comptée au bilan (Y puis A maintenu)" % [int(r.get("index", 0)) + 1,
		int(season.get("weeks", 8)) if season is Dictionary else 8, str(r.get("title", ""))]


## Lignes du bilan d'une manche (`summary.league`, maquette 03) : place et points, général et mouvement écrit,
## puis les lignes du classement autour du cycliste (« Toi » écrit) ; [] sans manche.
static func summary_lines(summary: Dictionary) -> Array:
	var lg = summary.get("league")
	if not (lg is Dictionary):
		return []
	var out: Array = []
	out.append({"label": "Ligue d'hiver", "value": "manche %d sur %d" % [int(lg.get("round", 1)), int(lg.get("of_rounds", 8))], "unit": ""})
	out.append({"label": "Manche", "value": "%s sur %d · +%d points" % [ordinal(int(lg.get("place", 0))),
		int(lg.get("of", 12)), int(lg.get("points", 0))], "unit": ""})
	out.append({"label": "Général", "value": "%s, %s" % [ordinal(int(lg.get("general_after", 0))), str(lg.get("moved", ""))], "unit": ""})
	if bool(lg.get("easy", false)):
		out.append({"label": "Intensité", "value": "facile (noté au classement)", "unit": ""})
	for row in lg.get("rows", []):
		if row is Dictionary:
			var me := bool(row.get("me", false))
			out.append({"label": "%s %s" % [str(int(row.get("place", 0))), "Toi" if me else str(row.get("name", ""))],
				"value": _points(row.get("points", 0)), "unit": ""})
	return out
