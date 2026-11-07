extends RefCounted

## HUD des épreuves de piste du vélodrome (série VD, lot VD9, contrat 1.7), sans aucun nœud, d'après les
## maquettes validées par le propriétaire le 7 novembre (lot VD8, dossier du projet `velodrome/vd8/`) :
## - bandeau de l'épreuve en haut au centre : nom de l'épreuve, ligne d'information (prochain sprint, derny,
##   élimination, relais) ; doré avec deux cloches au dernier tour (`bell`), rouge à l'élimination ;
## - bloc des tours sous la vitesse : « 23 / 40 », tours restants, barre ; ou « ENCORE EN COURSE », ou l'heure ;
## - liste à gauche sous la puissance : points, positions, ordre de course (dernier marqué en rouge, sortis
##   grisés et barrés), coureurs derrière le derny, équipes ; « Toi » ou « Ton équipe » surlignés ;
## - blocs du bas : anneau de la poursuite et écart, chrono des contre-la-montre et distance de l'heure ;
## - bloc du derny du keirin sous les tours ; bandeau du milieu : « DERNIER ! » (élimination), relais (américaine) ;
## - tableau d'affichage de la salle (`board_text`, Label3D de velodrome_hall.gd) : même contenu, 8 lignes au plus ;
## - sons : cloche du dernier tour, pistolet du départ, public qui monte au sprint (`sounds`).
## Objet `track` de `state` : {event, t_s, lap, laps, laps_to_go, bell, ranking, points, eliminated, finished}
## et les champs de chaque épreuve (contrat §3 « Objet `track` »). Ne décide rien : le core arbitre l'épreuve.
## Pas de class_name : preload("res://scripts/track/track_hud_model.gd").

const UiTheme := preload("res://scripts/ui_theme.gd")
const VelodromeHall := preload("res://scripts/velodrome_hall.gd")
const TrackNames := preload("res://scripts/track/track_names.gd")

const ME := "me"
const ME_NAME := "Toi"
const HOME := "home"
const MAX_LINES := 8
const PACER_ID := "derny"
const PACER_LANE_M := 0.3       # derny à la corde quand la trame n'a pas la place du cycliste
const BOARD_LINES := 8
const CROWD_LAPS := 1            # le public monte au dernier tour d'un sprint
const RED := Color(0.47, 0.08, 0.10, 0.93)
const GOLD_BG := Color(0.47, 0.31, 0.04, 0.93)
const BLUE_BG := Color(0.08, 0.24, 0.47, 0.93)
const LAST_RED := Color(1.0, 0.25, 0.25)
const TEAM_BLUE := Color(0.45, 0.65, 1.0)

const TITLES := TrackNames.EVENTS
const SUBS := {"scratch": "Scratch", "tempo": "Tempo", "elimination": "Élimination", "points": "Course aux points"}
const TEAM_NAMES := {"t2": "Équipe rouge", "t3": "Équipe verte", "t4": "Équipe jaune", "t5": "Équipe blanche",
	"t6": "Équipe noire"}

var names := {}                 # id du bot -> nom (gardé)
var _bell := false
var _started := false
var _crowd_key := ""
var _team := {}                 # coureurs vus dans `order` : ton équipe (épreuves par équipes)


func reset() -> void:
	names.clear()
	_bell = false
	_started = false
	_crowd_key = ""
	_team.clear()


func remember_names(bots) -> void:
	if not bots is Array:
		return
	for b in bots:
		if b is Dictionary and str(b.get("id", "")) != "":
			names[str(b["id"])] = str(b.get("name", b["id"]))


func name_of(id: String) -> String:
	if id == ME:
		return ME_NAME
	if id == HOME:
		return "Ton équipe"
	if TEAM_NAMES.has(id):
		return str(TEAM_NAMES[id])
	return str(names.get(id, id))


## Vue du HUD pour la trame `state` (sans `track` : rien).
func view(state) -> Dictionary:
	var tr = state.get("track", null) if state is Dictionary else null
	if not tr is Dictionary:
		return {"visible": false}
	remember_names(state.get("bots", null))
	var ev := str(tr.get("event", ""))
	var shown := ev
	if ev == "omnium":
		shown = str(tr.get("sub", "scratch"))
	var out := {"visible": true, "event": ev, "banner": banner(tr), "laps": laps_block(tr), "list": list_block(tr),
		"pursuit": {}, "chrono": {}, "pacer": {}, "center": {}}
	if ev in ["pursuit", "team_pursuit", "team_sprint"]:
		out["pursuit"] = pursuit_block(tr)
	elif ev in ["kilo", "500", "flying_200"]:
		out["chrono"] = chrono_block(tr)
	elif ev == "hour":
		out["chrono"] = hour_block(tr)
	if ev == "keirin":
		out["pacer"] = pacer_block(tr)
	if shown == "elimination":
		out["center"] = elimination_center(tr)
	elif ev == "madison":
		out["center"] = madison_center(tr)
	return out


## Bandeau de l'épreuve : {title, sub, bell, color}.
func banner(tr: Dictionary) -> Dictionary:
	var ev := str(tr.get("event", ""))
	var laps = tr.get("laps", null)
	var title := str(TITLES.get(ev, ev))
	if ev == "omnium":
		title = "Omnium · %s (%d / %d)" % [str(SUBS.get(str(tr.get("sub", "")), "")), int(tr.get("sub_index", 1)),
			int(tr.get("subs", 4))]
	elif laps != null and ev in ["scratch", "points", "tempo", "keirin", "madison"]:
		title += " · %d tours" % int(laps)
	var sub := ""
	var color := UiTheme.PANEL_BG
	var bell := bool(tr.get("bell", false)) and not bool(tr.get("finished", false))
	var shown := str(tr.get("sub", ev)) if ev == "omnium" else ev
	match shown:
		"points", "madison":
			var nxt = tr.get("next_sprint_lap", null)
			var lap := int(tr.get("lap", 1) if tr.get("lap", null) != null else 1)
			if nxt != null:
				var n := int(nxt) - lap
				sub = "Sprint dans %d tour%s · 5, 3, 2, 1 pts" % [n, "s" if n > 1 else ""] if n > 0 else "Sprint à ce tour · 5, 3, 2, 1 pts"
		"tempo":
			sub = "1 point au premier de chaque tour"
		"scratch":
			sub = "Premier sur la ligne"
		"keirin":
			var p = tr.get("pacer", null)
			sub = "Derny de 30 à 50 km/h, puis sprint" if p is Dictionary and bool(p.get("on", false)) else "Derny parti : sprint !"
		"elimination":
			color = RED
			sub = "Le dernier sort sur la ligne"
			if tr.get("to_elim_m", null) != null:
				sub += " · %s" % distance_text(float(tr["to_elim_m"]))
		"pursuit", "team_pursuit", "team_sprint":
			sub = "Départ arrêté · ligne A · adversaire en ligne B"
		"kilo", "500":
			sub = "Seul contre le chrono"
		"flying_200":
			sub = "Élan de 425 m, puis 200 m chronométrés" if not bool(tr.get("timed", false)) else "200 m chronométrés"
		"hour":
			var avg = tr.get("avg_kmh", null)
			sub = ("Moyenne %s km/h · projection %s km" % [fr1(float(avg)), fr2(float(avg))]) if avg != null else "60 minutes"
		"free":
			var last = tr.get("last_lap_s", null)
			sub = ("Dernier tour %s s" % fr2(float(last))) if last != null else "Tours illimités, temps au tour"
	if ev == "omnium" and bool(tr.get("neutral", false)):
		sub = "Tour neutralisé avant l'épreuve suivante"
	if ev == "madison":
		color = BLUE_BG
	if bell:
		sub = "DERNIER TOUR" if shown != "elimination" else "ÉLIMINATION À CE TOUR"
		color = GOLD_BG if shown != "elimination" else RED
	return {"title": title, "sub": sub, "bell": bell, "color": color}


## Bloc des tours : {label, value, extra, bar} ; vide sans tours.
func laps_block(tr: Dictionary) -> Dictionary:
	var ev := str(tr.get("event", ""))
	var lap = tr.get("lap", null)
	var laps = tr.get("laps", null)
	if ev == "hour":
		var left := float(tr.get("time_left_s", 0.0))
		return {"label": "TOURS", "value": str(int(lap) - 1 if lap != null else 0), "extra": clock_text(left) + " restant",
			"bar": clampf(1.0 - left / 3600.0, 0.0, 1.0)}
	if ev == "free":
		var best = tr.get("best_lap_s", null)
		return {"label": "TOURS", "value": str(int(lap) - 1 if lap != null else 0),
			"extra": ("meilleur %s s" % fr2(float(best))) if best != null else "", "bar": -1.0}
	var shown := str(tr.get("sub", ev)) if ev == "omnium" else ev
	if shown == "elimination":
		var alive := int(tr.get("alive", (tr.get("ranking", []) as Array).size() - (tr.get("eliminated", []) as Array).size()))
		var total := (tr.get("ranking", []) as Array).size()
		return {"label": "ENCORE EN COURSE", "value": str(alive), "extra": "%d sur %d" % [alive, total], "bar": -1.0}
	if lap == null or laps == null:
		return {}
	var to_go := int(tr.get("laps_to_go", 0) if tr.get("laps_to_go", null) != null else 0)
	var extra := "cloche" if bool(tr.get("bell", false)) else ("%d tour%s" % [to_go, "s" if to_go > 1 else ""])
	if ev in ["kilo", "500", "flying_200", "pursuit", "team_pursuit", "team_sprint"]:
		extra = distance_text(float(tr.get("to_go_m", 0.0))) if tr.get("to_go_m", null) != null else extra
	return {"label": "TOURS", "value": "%d / %d" % [int(lap), int(laps)], "extra": extra,
		"bar": clampf(float(lap) / maxf(float(laps), 1.0), 0.0, 1.0)}


## Liste de gauche : {title, rows [{pos, name, value, kind}]} ; kind : me, ok, danger, out, team.
func list_block(tr: Dictionary) -> Dictionary:
	var ev := str(tr.get("event", ""))
	var shown := str(tr.get("sub", ev)) if ev == "omnium" else ev
	var ranking: Array = tr.get("ranking", []) if tr.get("ranking") is Array else []
	var pts = tr.get("points", null)
	var out_ids: Array = tr.get("eliminated", []) if tr.get("eliminated") is Array else []
	if ev in ["kilo", "500", "flying_200", "hour", "free", "pursuit"]:
		return {}
	var title := "POSITIONS"
	if pts is Array:
		title = "ÉQUIPES · POINTS" if ev == "madison" else "POINTS"
	if shown == "elimination":
		title = "ORDRE DE COURSE"
	if ev == "keirin":
		var p = tr.get("pacer", null)
		if p is Dictionary and bool(p.get("on", false)):
			title = "DERRIÈRE LE DERNY"
	if ev in ["team_pursuit", "team_sprint"]:
		title = "TON ÉQUIPE"
		ranking = tr.get("order", []) if tr.get("order") is Array else []
		pts = null
		for id in ranking:
			_team[str(id)] = true
		var mine: Array = []
		for id in out_ids:
			if _team.has(str(id)) or str(id) == ME:
				mine.append(id)
		out_ids = mine     # les sortis de l'autre équipe ne sont pas dans la liste
	var rows: Array = []
	var racing: Array = []
	for id in ranking:
		if not out_ids.has(id):
			racing.append(str(id))
	var last := str(tr.get("last", "")) if tr.get("last", null) != null else ""
	for i in racing.size():
		var rid: String = racing[i]
		var value := ""
		if pts is Array and ranking.find(rid) < (pts as Array).size():
			value = str(int(pts[ranking.find(rid)]))
		var kind := "ok"
		if rid == ME or rid == HOME:
			kind = "me"
		elif shown == "elimination" and rid == last:
			kind = "danger"
		if shown == "elimination" and rid == ME and last == ME:
			value = "dernier"
		if ev in ["team_pursuit", "team_sprint"] and i == 0:
			value = "en tête"
		if title == "DERRIÈRE LE DERNY" and i == 0:
			value = "derny"
		rows.append({"pos": "%d." % (i + 1), "name": name_of(rid), "value": value, "kind": kind})
	var gone := out_ids.duplicate()
	gone.reverse()
	for id in gone:
		rows.append({"pos": "", "name": name_of(str(id)), "value": "", "kind": "out"})
	return {"title": title, "rows": rows.slice(0, MAX_LINES)}


## Poursuite : {gap_s, gap_text, good, me_frac, opp_frac, left} (anneau de 250 m, A en bas, B en haut).
func pursuit_block(tr: Dictionary) -> Dictionary:
	var d := float(tr.get("d_m", 0.0))
	var gap = tr.get("gap_m", null)
	var lap_m := 250.0
	var me_frac := fposmod(d / lap_m, 1.0)
	var opp_frac := fposmod((d - (float(gap) if gap != null else 0.0)) / lap_m + 0.5, 1.0)
	var gs = tr.get("gap_s", null)
	var text := "—"
	var good := true
	if gs != null:
		# avance du cycliste (gap > 0) : temps qu'il prend à l'adversaire, affiché « −0,84 s » en vert
		good = float(gs) >= 0.0
		text = ("−" if good else "+") + fr2(absf(float(gs))) + " s"
	return {"gap_text": text, "good": good, "me_frac": me_frac, "opp_frac": opp_frac,
		"left": "encore " + distance_text(float(tr.get("to_go_m", 0.0))), "has_opp": gap != null}


## Contre-la-montre : {label, big, line}.
func chrono_block(tr: Dictionary) -> Dictionary:
	var t = tr.get("time_s", null)
	var big := chrono_text(float(t)) if t != null else "—"
	var line := "passage %s" % distance_text(float(tr.get("d_m", 0.0)))
	if str(tr.get("event", "")) == "flying_200" and not bool(tr.get("timed", false)):
		big = "élan"
		line = "chrono dans %s" % distance_text(maxf(425.0 - float(tr.get("d_m", 0.0)), 0.0))
	return {"label": "CHRONO", "big": big, "line": line}


func hour_block(tr: Dictionary) -> Dictionary:
	var d := float(tr.get("d_m", 0.0))
	return {"label": "DISTANCE", "big": ("%.3f km" % (d / 1000.0)).replace(".", ","),
		"line": "temps restant %s" % clock_text(float(tr.get("time_left_s", 0.0)))}


## Derny du keirin : {on, text, speed} ; tours avant son départ lus dans les tours restants (il part à 3).
func pacer_block(tr: Dictionary) -> Dictionary:
	var p = tr.get("pacer", null)
	if not p is Dictionary:
		return {}
	if not bool(p.get("on", false)):
		return {"on": false, "text": "parti : sprint !", "speed": "", "hint": ""}
	var left := int(tr.get("laps_to_go", 3) if tr.get("laps_to_go", null) != null else 3) - 3
	return {"on": true, "text": "s'écarte dans %d tour%s" % [maxi(left, 0), "s" if left > 1 else ""],
		"speed": "%d km/h" % int(round(float(p.get("v", 0.0)) * 3.6)), "hint": "Ne le dépasse pas avant"}


func elimination_center(tr: Dictionary) -> Dictionary:
	if str(tr.get("last", "")) != ME or bool(tr.get("finished", false)):
		return {}
	var ranking: Array = tr.get("ranking", []) if tr.get("ranking") is Array else []
	var out_ids: Array = tr.get("eliminated", []) if tr.get("eliminated") is Array else []
	var racing: Array = []
	for id in ranking:
		if not out_ids.has(id):
			racing.append(str(id))
	var i := racing.find(ME)
	var sub := "Remonte un coureur avant la ligne"
	if i > 0:
		var g = tr.get("gap_last_s", null)
		sub = "Remonte %s avant la ligne%s" % [name_of(racing[i - 1]), (" (%s s)" % fr1(float(g))) if g != null else ""]
	return {"title": "DERNIER !", "sub": sub, "color": RED}


## Américaine : bandeau du relais quand le cycliste est au repos (son coéquipier court).
func madison_center(tr: Dictionary) -> Dictionary:
	var racers = tr.get("racers", null)
	if not racers is Dictionary or not racers.has(HOME) or str(racers[HOME]) == ME:
		return {}
	return {"title": "AU REPOS EN HAUT", "sub": "%s court · redescends à son passage pour le relais" % name_of(str(racers[HOME])),
		"color": BLUE_BG}


## Bots de la trame et, au keirin tant qu'il roule, le derny (`track.pacer`), à la place du cycliste sur la piste
## (le derny mène à la corde) ; sans derny : `state.bots` tel quel.
static func bots_with_pacer(state: Dictionary):
	var bots = state.get("bots", null)
	var tr = state.get("track", null)
	var p = tr.get("pacer", null) if tr is Dictionary else null
	if not p is Dictionary or not bool(p.get("on", false)):
		return bots
	var out: Array = (bots as Array).duplicate() if bots is Array else []
	out.append({"id": PACER_ID, "name": "Derny", "kind": "constant", "s": float(p.get("s", 0.0)), "v": float(p.get("v", 0.0)),
		"lane_m": float(state.get("lane_m", PACER_LANE_M)) if state.get("lane_m", null) != null else PACER_LANE_M})
	return out


## Texte du tableau d'affichage de la salle (Label3D) : nom de l'épreuve, tour, puis le classement.
func board_text(state) -> String:
	var tr = state.get("track", null) if state is Dictionary else null
	if not tr is Dictionary:
		return VelodromeHall.SCOREBOARD_IDLE
	var b := banner(tr)
	var lines: Array = [str(b["title"]).to_upper()]
	var lb := laps_block(tr)
	if not lb.is_empty():
		lines.append("%s %s" % [str(lb["label"]), str(lb["value"])])
	var lst := list_block(tr)
	for r in (lst.get("rows", []) as Array):
		if lines.size() >= BOARD_LINES:
			break
		if str(r["kind"]) != "out":
			lines.append(("%s %s %s" % [str(r["pos"]), str(r["name"]).to_upper(), str(r["value"])]).strip_edges())
	return "\n".join(lines)


## Sons à jouer pour cette trame (une fois chacun) : track_gun au départ, track_bell au dernier tour,
## track_crowd au dernier tour avant un sprint ou l'arrivée.
func sounds(state) -> Array:
	var tr = state.get("track", null) if state is Dictionary else null
	if not tr is Dictionary:
		_started = false
		_bell = false
		return []
	var out: Array = []
	if not _started:
		_started = true
		if float(tr.get("t_s", 0.0)) < 1.0:
			out.append("track_gun")
	var bell := bool(tr.get("bell", false))
	if bell and not _bell:
		out.append("track_bell")
	_bell = bell
	var lap = tr.get("lap", null)
	var key := ""
	if bell:
		key = "fin"
	elif tr.get("next_sprint_lap", null) != null and lap != null and int(tr["next_sprint_lap"]) - int(lap) < CROWD_LAPS:
		key = "sprint%d" % int(tr["next_sprint_lap"])
	if key != "" and key != _crowd_key:
		_crowd_key = key
		out.append("track_crowd")
	return out


## Lignes du bilan (`summary.track`), au format de summary_view_model.gd : [{label, value, unit}].
static func summary_lines(st: Dictionary) -> Array:
	var ev := str(st.get("event", ""))
	var out: Array = []
	var place = st.get("place", null)
	var of := int(st.get("of", 0))
	out.append({"label": str(TITLES.get(ev, ev)), "value": ("%s sur %d" % [place_text(int(place)), of]) if place != null and of > 1 else
		("terminé" if bool(st.get("finished", false)) else "non fini"), "unit": ""})
	if st.get("time_s", null) != null:
		out.append({"label": "Ton temps", "value": chrono_text(float(st["time_s"])), "unit": ""})
	if ev == "hour" and st.get("distance_m", null) != null:
		out.append({"label": "Distance", "value": ("%.3f" % (float(st["distance_m"]) / 1000.0)).replace(".", ","), "unit": "km"})
	var laps: Array = st.get("laps", []) if st.get("laps") is Array else []
	if not laps.is_empty():
		out.append({"label": "Tours", "value": str(laps.size()), "unit": ""})
	if st.get("best_lap_s", null) != null:
		var best := float(st["best_lap_s"])
		out.append({"label": "Meilleur tour", "value": "%s s (tour %d)" % [fr2(best), laps.find(best) + 1 if laps.has(best) else 0], "unit": ""})
	var rank = st.get("record_rank", null)
	if rank != null:
		out.append({"label": "Records de la piste", "value": "nouveau record !" if int(rank) == 1 else "%s temps" % place_text(int(rank)), "unit": ""})
	var ranking: Array = st.get("ranking", []) if st.get("ranking") is Array else []
	var nm: Dictionary = st.get("names", {}) if st.get("names") is Dictionary else {}
	if ranking.size() > 1:
		var w := str(ranking[0])
		out.append({"label": "Vainqueur", "value": ME_NAME if w == ME else ("Ton équipe" if w == HOME else str(nm.get(w, TEAM_NAMES.get(w, w)))), "unit": ""})
	return out


## Temps de chaque tour pour le tableau du bilan : [{lap, time, best}].
static func lap_rows(st: Dictionary) -> Array:
	var laps: Array = st.get("laps", []) if st.get("laps") is Array else []
	var best = st.get("best_lap_s", null)
	var rows: Array = []
	for i in laps.size():
		rows.append({"lap": i + 1, "time": fr2(float(laps[i])) if float(laps[i]) >= 0.0 else "—",
			"best": best != null and absf(float(laps[i]) - float(best)) < 0.0005})
	return rows


static func place_text(n: int) -> String:
	return "1er" if n == 1 else "%de" % n


static func fr1(v: float) -> String:
	return ("%.1f" % v).replace(".", ",")


static func fr2(v: float) -> String:
	return ("%.2f" % v).replace(".", ",")


static func chrono_text(t: float) -> String:
	var m := int(t / 60.0)
	var s := t - m * 60.0
	return ("%d:%06.3f" % [m, s]).replace(".", ",") if m > 0 else ("%.3f" % s).replace(".", ",")


static func clock_text(t: float) -> String:
	var m := int(t / 60.0)
	return "%d:%02d" % [m, int(t) % 60]


static func distance_text(d_m: float) -> String:
	if d_m >= 1000.0:
		return ("%.2f km" % (d_m / 1000.0)).replace(".", ",")
	return "%d m" % int(round(d_m / 10.0) * 10.0)
