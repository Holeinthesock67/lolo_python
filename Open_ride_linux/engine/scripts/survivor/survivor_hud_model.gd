extends RefCounted

## HUD du mode « Dernier survivant » (série DS, lot DS6, contrat 1.5), sans aucun nœud, d'après les maquettes
## validées par le propriétaire le 31 octobre (lot DS4) :
## - bloc « SURVIVANT » sous la vitesse : distance à l'arche, « Arche 2 / 4 », barre d'approche, rang parmi
##   les coureurs encore en course, écart avec le dernier ; cadre rouge et « DERNIER » quand le cycliste l'est ;
## - liste des coureurs sous la puissance (MAX_LINES lignes au plus) : en course du premier au dernier sur la
##   route (cycliste « Toi » surligné, dernier marqué d'un point rouge, écart au cycliste en secondes), puis
##   les éliminés grisés et barrés avec leur arche, du plus récent au plus ancien ;
## - bandeaux : élimination d'un bot en bas de l'écran (BANNER_S secondes), cycliste éliminé (rouge) et
##   vainqueur (vert) au milieu (CENTER_S secondes) ; les messages `elimination` répétés par le core (trois
##   fois, à une seconde d'intervalle) ne comptent qu'une fois par (`arch`, `rider`) ;
## - jingles : `jingle_elim` à chaque élimination, `jingle_winner` quand le cycliste gagne
##   (event_sounds_model.gd JINGLES) ;
## - lignes du bilan (`summary.survivor`) : place, vainqueur, arche par arche.
## Objet `survivor` de `state` : {arch, arches, d_m, alive, last, gap_last_s, out, me_out, winner} ; noms des
## bots lus dans la liste `bots` de la même trame et gardés (un bot éliminé disparaît de la trame au bout de
## 10 s). Ne décide rien : le core arbitre les arches. Pas de class_name :
## preload("res://scripts/survivor/survivor_hud_model.gd").

const UiTheme := preload("res://scripts/ui_theme.gd")

const ME := "me"
const ME_NAME := "Toi"
const MAX_LINES := 12
const BANNER_S := 3.0
const CENTER_S := 6.0
const RED := Color(0.62, 0.08, 0.10, 0.92)
const GREEN := Color(0.13, 0.50, 0.24, 0.92)
const LAST_RED := Color(1.0, 0.25, 0.25)
const YELLOW := UiTheme.GOLD

var names := {}                 # id du bot -> nom (gardé après sa disparition de la trame)
var after_out := "ride"         # réglage survivor.after_out : texte du bandeau du cycliste éliminé
## FTP du cycliste (hello_ack, posée par main.gd) : puissance « hors de portée » au-delà de REACH_FTP × FTP.
var ftp_w := 0.0
const REACH_FTP := 1.5
const REACH_MAX_W := 600.0
const GAP_MIN_SPEED_MPS := 1.0   # vitesse plancher de l'écart estimé d'un bot loin (gaps.py MIN_SPEED_MPS)
var _seen := {}                 # "arche:coureur" des éliminations déjà affichées
var _bottom := {}               # bandeau du bas en cours : {title, sub, color, until}
var _center := {}               # bandeau du milieu en cours
var _arch_start_d := {}         # arche -> distance à l'arche quand elle est devenue la prochaine (barre)
var _arch_s := {}               # arche -> position sur la route (s cumulé), pour les portiques
var _total := 0                 # coureurs au départ, cycliste compris (lu dans la trame)


func reset() -> void:
	names.clear()
	_seen.clear()
	_bottom = {}
	_center = {}
	_arch_start_d.clear()
	_arch_s.clear()
	_total = 0


## Noms des bots de la trame (`bots` de `state`). Peloton (lot PL1) : un bot loin n'a son nom qu'une trame sur
## N (`bots.light_frame`) ; sans nom, le nom déjà connu reste (lot DS8).
func remember_names(bots) -> void:
	if not bots is Array:
		return
	for b in bots:
		if b is Dictionary and str(b.get("id", "")) != "" and b.has("name"):
			names[str(b["id"])] = str(b["name"])


func name_of(id: String) -> String:
	if id == ME:
		return ME_NAME
	return str(names.get(id, id))


## Message `elimination` du core ; rend les jingles à jouer ([] pour un doublon).
func on_elimination(msg: Dictionary, now_s: float) -> Array:
	var key := "%d:%s" % [int(msg.get("arch", 0)), str(msg.get("rider", ""))]
	if _seen.has(key):
		return []
	_seen[key] = true
	var rider := str(msg.get("rider", ""))
	var place := int(msg.get("place", 0))
	var alive := int(msg.get("alive", 0))
	var of := _total
	var gap = msg.get("gap_s", null)
	var gap_text := ("à %s s" % fr1(float(gap))) if gap != null else ""
	if str(msg.get("name", "")) != "" and rider != ME:
		names[rider] = str(msg["name"])
	var out := ["jingle_elim"]
	if rider == ME:
		_center = {"title": "ÉLIMINÉ · %s sur %d" % [place_text(place), of],
			"sub": "Bilan de la course" if after_out == "end" else "Tu continues à rouler : la course se finit sans toi",
			"color": RED, "until": now_s + CENTER_S}
		return out
	_bottom = {"title": "Éliminé : " + name_of(rider),
		"sub": "arche %d%s" % [int(msg.get("arch", 0)), (" · " + gap_text) if gap_text != "" else ""],
		"color": RED, "until": now_s + BANNER_S}
	if alive == 1 and not _center_is_me_out():
		# dernière arche passée : le cycliste encore en course a gagné
		_center = {"title": "DERNIER SURVIVANT !", "sub": "1er sur %d · %s éliminé %s" % [of, name_of(rider), gap_text],
			"color": GREEN, "until": now_s + CENTER_S * 2.0}
		_bottom = {}
		out.append("jingle_winner")
	return out


func _center_is_me_out() -> bool:
	return not _center.is_empty() and _center.get("color") == RED


## Vue du HUD pour la trame `state` (null ou sans `survivor` : rien).
func view(state, now_s: float) -> Dictionary:
	var sv = state.get("survivor", null) if state is Dictionary else null
	if not sv is Dictionary:
		return {"visible": false}
	remember_names(state.get("bots", null))
	var alive: Array = sv.get("alive", []) if sv.get("alive") is Array else []
	var arch := int(sv.get("arch", 1))
	var arches := int(sv.get("arches", 0))
	var d = sv.get("d_m", null)
	var me_out = sv.get("me_out", null)
	var winner = sv.get("winner", null)
	var last := str(sv.get("last", "")) if sv.get("last", null) != null else ""
	_total = alive.size() + (sv["out"].size() if sv.get("out") is Array else 0) + (1 if me_out != null else 0)
	var out := {"visible": true, "block": {}, "list": list_rows(sv, state.get("bots", null), _num(state.get("s", null), NAN), _num(state.get("v", null), 0.0)), "bottom": {}, "center": {}}
	if d != null and me_out == null and winner == null:
		var dm := float(d)
		if not _arch_start_d.has(arch) or dm > float(_arch_start_d[arch]):
			_arch_start_d[arch] = dm
		_arch_s[arch] = float(state.get("s", 0.0)) + dm
		var start_d: float = maxf(float(_arch_start_d[arch]), 1.0)
		var rank := alive.find(ME) + 1
		var danger := last == ME
		var gap = sv.get("gap_last_s", null)
		var last_line := ""
		if gap != null and alive.size() >= 2:
			if danger:
				last_line = "%s à %s s" % [name_of(str(alive[alive.size() - 2])), fr1(float(gap))]
			else:
				last_line = "Dernier : %s à %s s" % [name_of(last), fr1(float(gap))]
		var pw = state.get("power_3s", state.get("power", 0.0))   # puissance lissée sur 3 s : écart stable
		var ahead := ahead_lines(sv.get("ahead", null), float(pw) if (pw is float or pw is int) else 0.0)
		out["block"] = {"title": "SURVIVANT", "dist": "dans " + distance_text(dm), "arch": "Arche %d / %d" % [arch, arches],
			"bar": clampf(1.0 - dm / start_d, 0.0, 1.0), "rank": "%s sur %d en course" % [place_text(rank), alive.size()],
			"danger": danger, "danger_text": "DERNIER" if danger else "", "last": last_line,
			"ahead": ahead[0], "ahead_w": ahead[1]}
	if not _bottom.is_empty() and now_s < float(_bottom["until"]):
		out["bottom"] = _bottom
	if not _center.is_empty() and now_s < float(_center["until"]):
		out["center"] = _center
	return out


## Coureur juste devant (`ahead` de la trame, essai du 4 novembre) : [« Devant : Grimpeur à 4,2 s »,
## « 245 W (+50) pour le rejoindre » (d'ici l'arche)] ; au-delà de REACH_FTP × FTP (ou REACH_MAX_W sans FTP) :
## « hors de portée d'ici l'arche » ; sans puissance (il a passé l'arche) : seconde ligne vide. ["", ""] si personne.
func ahead_lines(ahead, power_w: float) -> Array:
	if not ahead is Dictionary or str(ahead.get("id", "")) == "":
		return ["", ""]
	var first := "Devant : %s à %s s" % [name_of(str(ahead["id"])), fr1(float(ahead.get("gap_s", 0.0)))]
	var need = ahead.get("catch_w", null)
	if not (need is float or need is int):
		return [first, ""]
	var reach := REACH_FTP * ftp_w if ftp_w > 0.0 else REACH_MAX_W
	if float(need) > reach:
		return [first, "hors de portée"]
	var delta := int(round(float(need) - power_w))
	return [first, "%d W (%s%d) pour le rejoindre" % [int(need), "+" if delta >= 0 else "−", absi(delta)]]


## Lignes de la liste des coureurs : [{name, detail, me, last, out}].
func list_rows(sv: Dictionary, bots, rider_s := NAN, rider_v := 0.0) -> Array:
	var gaps := {}
	if bots is Array:
		for b in bots:
			if not b is Dictionary:
				continue
			if b.get("gap_s") is float or b.get("gap_s") is int:
				gaps[str(b.get("id", ""))] = float(b["gap_s"])
			elif not is_nan(rider_s) and (b.get("s") is float or b.get("s") is int):
				# Peloton (lot PL1) : les bots loin n'ont plus `gap_s` ; écart estimé comme le repli du core
				# (gaps.py : distance ÷ vitesse, vitesse plancher 1 m/s), lot DS8.
				gaps[str(b.get("id", ""))] = (float(b["s"]) - rider_s) / maxf(rider_v, GAP_MIN_SPEED_MPS)
	var rows: Array = []
	var alive: Array = sv.get("alive", []) if sv.get("alive") is Array else []
	var last := str(sv.get("last", "")) if sv.get("last", null) != null else ""
	var winner = sv.get("winner", null)
	for id in alive:
		var rid := str(id)
		var detail := ""
		if winner != null and str(winner) == rid:
			detail = "vainqueur"
		elif rid == ME:
			detail = "dernier" if last == ME and alive.size() > 1 else ""
		elif gaps.has(rid):
			detail = signed_s(float(gaps[rid]))
		rows.append({"name": name_of(rid), "detail": detail, "me": rid == ME,
			"last": rid == last and alive.size() > 1 and winner == null, "out": false})
	var gone: Array = []
	if sv.get("out") is Array:
		for o in sv["out"]:
			if o is Array and o.size() >= 2:
				gone.append([int(o[1]), str(o[0])])
	if sv.get("me_out", null) != null:
		gone.append([int(sv["me_out"]), ME])
	gone.sort_custom(func(a: Array, b: Array) -> bool: return a[0] > b[0])
	for g in gone:
		rows.append({"name": name_of(g[1]), "detail": "arche %d" % g[0], "me": g[1] == ME, "last": false, "out": true})
	return rows.slice(0, MAX_LINES)


static func _num(x, fallback: float) -> float:
	return float(x) if (x is float or x is int) else fallback


## Position de l'arche `arch` sur la route (s cumulé), connue dès qu'elle est devenue la prochaine ; NAN sinon.
func arch_s(arch: int) -> float:
	return float(_arch_s.get(arch, NAN))


## Portiques d'élimination à dessiner (lot DS5) : la prochaine arche et celle qu'on vient de passer, [{s, lines}].
func arches_to_draw(state) -> Array:
	var sv = state.get("survivor", null) if state is Dictionary else null
	if not sv is Dictionary:
		return []
	var arch := int(sv.get("arch", 1))
	var arches := int(sv.get("arches", 0))
	var out: Array = []
	for k in [arch - 1, arch]:
		if k >= 1 and _arch_s.has(k):
			out.append({"s": float(_arch_s[k]), "arch": k,
				"lines": ["Élimination", "Arche %d sur %d · le dernier sort" % [k, arches]]})
	return out


## Lignes du bilan (`summary.survivor`), au format de summary_view_model.gd : [{label, value, unit}].
static func summary_lines(sv: Dictionary) -> Array:
	var of := int(sv.get("of", 0))
	var place = sv.get("place", null)
	var out: Array = [{"label": "Dernier survivant",
		"value": ("%s sur %d" % [place_text(int(place)), of]) if place != null else "course non finie", "unit": ""}]
	var winner = sv.get("winner", null)
	if winner != null:
		out.append({"label": "Vainqueur", "value": ME_NAME if str(winner) == ME else str(sv.get("winner_name", winner)), "unit": ""})
	var spacing := float(sv.get("spacing_km", 0.0))
	var elim: Array = sv.get("eliminated", []) if sv.get("eliminated") is Array else []
	for e in elim:
		if e is Array and e.size() >= 4:
			var who := ME_NAME if str(e[1]) == ME else str(e[2])
			# court : la colonne du bilan coupe au-delà d'une trentaine de caractères (captures du 3 novembre)
			var gap_text := (", à %s s" % fr1(float(e[3]))) if e[3] != null else ""
			out.append({"label": "Arche %d (%s km)" % [int(e[0]), fr1(int(e[0]) * spacing)], "value": who + gap_text, "unit": ""})
	out.append({"label": "Records", "value": "aucun dans ce mode", "unit": ""})
	return out


static func place_text(n: int) -> String:
	return "1er" if n == 1 else "%de" % n


static func fr1(v: float) -> String:
	return ("%.1f" % v).replace(".", ",")


static func signed_s(gap: float) -> String:
	if absf(gap) < 0.05:
		return "0,0 s"
	return ("+" if gap > 0.0 else "−") + fr1(absf(gap)) + " s"


static func distance_text(d_m: float) -> String:
	if d_m >= 1000.0:
		return ("%.2f km" % (d_m / 1000.0)).replace(".", ",")
	return "%d m" % int(round(d_m / 10.0) * 10.0)
