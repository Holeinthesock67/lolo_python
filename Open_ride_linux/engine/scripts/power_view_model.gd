extends RefCounted

## Écran « Ma puissance » du profil (série PP, lot PP3, contrat IPC révision 1.29), sans nœud. Pas de
## class_name : charger par preload("res://scripts/power_view_model.gd").
##
## Les calculs sont ceux du core (message `power_curve`, outils `power_curve` et `ftp_estimate`) :
## - SCREEN « Ma puissance » (ligne de « Qui roule ? ») : période montrée (6 derniers mois ou 6 dernières
##   semaines, A pour changer), proposition « Utiliser 249 W comme FTP » (confirmation, puis `set_setting`
##   `rider.ftp_w` : rien n'est écrit sans ce geste), « Faire un test de rampe », « Évolution mois par mois »,
##   puis les 13 durées (meilleur effort, date, séance, et le mot « libre » ou « ERG ») ;
## - carte de détail : FTP réglée et FTP estimée avec sa confiance en mots, courbe des deux périodes (points
##   pleins : 6 mois ; points creux : 6 semaines), ligne de la FTP réglée, source de l'estimation et
##   avertissements ; tout en watts, et les mots portent l'information, jamais la couleur seule ;
## - MONTHS « Évolution mois par mois » : FTP du mois, meilleurs 5 et 20 min libres, sur 6 mois.
## Rien ne s'affiche pendant une séance (le core refuse `list_power_curve` en roulant).

const SCREEN := "power"
const MONTHS := "power_months"
const SCREENS := [SCREEN, MONTHS]
const ROW_PREFIX := "d:"
const LOADING := "Chargement…"
const WINDOWS := {"m6": "6 derniers mois", "w6": "6 dernières semaines"}
## Noms courts : libellés de la liste et légende de la carte (les longs seraient coupés à côté du détail).
const SHORT := {"m6": "6 mois", "w6": "6 semaines"}
const MONTH_NAMES := ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
const MONTH_FULL := ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
	"novembre", "décembre"]
const NO_DATA := "Roule une première séance pour voir ta courbe"

var loaded := false
var data: Dictionary = {}
## Période montrée : « m6 » (6 derniers mois) ou « w6 » (6 dernières semaines).
var window := "m6"
## Ligne d'état (chargement, FTP enregistrée, erreur).
var message := ""


## Remet l'écran en attente de `power_curve` (à chaque ouverture : une séance vient peut-être de finir).
func begin() -> void:
	loaded = false
	message = LOADING


func on_power_curve(msg: Dictionary) -> void:
	data = msg
	loaded = true
	if message == LOADING:
		message = ""


func toggle_window() -> void:
	window = "w6" if window == "m6" else "m6"


static func _num(x) -> bool:
	return typeof(x) in [TYPE_INT, TYPE_FLOAT]


static func duration_label(seconds: int) -> String:
	return "%d s" % seconds if seconds < 60 else "%d min" % (seconds / 60)


## « 12 oct. » depuis « 2026-10-12 ».
static func short_date(ymd: String) -> String:
	var p := ymd.split("-")
	if p.size() != 3 or not p[1].is_valid_int() or int(p[1]) < 1 or int(p[1]) > 12:
		return ymd
	return "%d %s" % [int(p[2]), MONTH_NAMES[int(p[1]) - 1]]


## « novembre 2026 » depuis « 2026-11 ».
static func month_text(ym: String) -> String:
	var p := ym.split("-")
	if p.size() != 2 or not p[1].is_valid_int() or int(p[1]) < 1 or int(p[1]) > 12:
		return ym
	return "%s %s" % [MONTH_FULL[int(p[1]) - 1], p[0]]


func has_data() -> bool:
	var s = data.get("sessions", {})
	return s is Dictionary and int(s.get("m6", 0)) > 0


func points() -> Array:
	var raw = data.get("points", [])
	return raw if raw is Array else []


func ftp_set_w() -> int:
	return int(data.get("ftp_set_w", 0)) if _num(data.get("ftp_set_w")) else 0


func proposal_w() -> int:
	return int(data["proposal_w"]) if _num(data.get("proposal_w")) else 0


func estimate() -> Dictionary:
	return data["estimate"] if data.get("estimate") is Dictionary else {}


## Nom lisible de la séance d'un point : entraînement ERG, sinon parcours (noms de la liste des parcours).
static func session_name(pt: Dictionary, names: Dictionary) -> String:
	var k = pt.get("k")
	if k is String and k != "":
		return str(k).replace("_", " ")
	var r = pt.get("r")
	if r is String and r != "":
		return str(names.get(r, r))
	return "séance"


func row(p: Dictionary, names: Dictionary) -> Dictionary:
	var s := int(p.get("s", 0))
	var pt = p.get(window)
	var id := ROW_PREFIX + str(s)
	if not (pt is Dictionary):
		return {"id": id, "label": "%s · —" % duration_label(s),
			"detail": "aucun effort à fond" + (" depuis 6 semaines" if window == "w6" else " depuis 6 mois")}
	# Le mot de l'effort dans le libellé : un détail trop long est coupé à droite, le mot doit rester lisible.
	return {"id": id, "label": "%s · %d W · %s" % [duration_label(s), int(pt.get("w", 0)), str(pt.get("e", ""))],
		"detail": "%s · %s" % [short_date(str(pt.get("d", ""))), session_name(pt, names)]}


func items(names: Dictionary) -> Array:
	if not loaded:
		return [{"id": "none", "label": LOADING, "enabled": false}]
	var out: Array = []
	if not has_data():
		out.append({"id": "none", "label": NO_DATA, "enabled": false})
		out.append({"id": "ramp", "label": "Faire un test de rampe", "detail": "la mesure la plus fiable de la FTP"})
		return out
	out.append({"id": "window", "label": "Période : " + SHORT[window], "detail": "A : changer"})
	if proposal_w() > 0:   # FTP réglée et confiance sont dans la carte : le libellé reste entier
		out.append({"id": "accept", "label": "Utiliser %d W comme FTP" % proposal_w(), "detail": ""})
	out.append({"id": "ramp", "label": "Faire un test de rampe", "detail": ""})
	out.append({"id": "months", "label": "Évolution par mois", "detail": ""})
	for p in points():
		if p is Dictionary:
			out.append(row(p, names))
	return out


## Question de la confirmation de la proposition.
func accept_question() -> String:
	return "Utiliser %d W comme FTP ? (FTP réglée aujourd'hui : %d W)" % [proposal_w(), ftp_set_w()]


## Action de la confirmation : menu_flow.gd la change en `set_setting` `rider.ftp_w` et attend la réponse.
func accept_action() -> Dictionary:
	return {"action": "power_accept", "value": proposal_w()}


func month_items() -> Array:
	var out: Array = []
	var raw = data.get("monthly", [])
	for m in (raw if raw is Array else []):
		if not (m is Dictionary):
			continue
		var ftp := "FTP %d W" % int(m["ftp"]) if _num(m.get("ftp")) else "FTP —"
		var parts: Array = []
		parts.append("5 min %s" % ("%d W" % int(m["p5"]) if _num(m.get("p5")) else "—"))
		parts.append("20 min %s" % ("%d W" % int(m["p20"]) if _num(m.get("p20")) else "—"))
		out.append({"id": "m:" + str(m.get("m", "")), "label": "%s · %s" % [month_text(str(m.get("m", ""))), ftp],
			"detail": " · ".join(parts)})
	if out.is_empty():
		out.append({"id": "none", "label": "Aucune séance sur 6 mois", "enabled": false})
	return out


## Courbe de la carte : [[secondes, watts ou null]] des deux périodes et FTP réglée.
func curve() -> Dictionary:
	var m6: Array = []
	var w6: Array = []
	for p in points():
		if not (p is Dictionary):
			continue
		var s := int(p.get("s", 0))
		m6.append([s, p["m6"].get("w") if p.get("m6") is Dictionary else null])
		w6.append([s, p["w6"].get("w") if p.get("w6") is Dictionary else null])
	return {"m6": m6, "w6": w6, "ftp_w": ftp_set_w(), "focus": window}


func card(focused: String, names: Dictionary) -> Dictionary:
	if not loaded:
		return {}
	var est := estimate()
	var conf := str(data.get("confidence", ""))
	var tiles: Array = [{"label": "FTP réglée", "value": str(ftp_set_w()), "unit": "W"}]
	if est.is_empty():
		tiles.append({"label": "FTP estimée", "value": "—", "unit": ""})
	else:
		tiles.append({"label": "FTP estimée · " + conf, "value": str(int(est.get("ftp_w", 0))), "unit": "W",
			"gold": proposal_w() > 0})
	var lines: Array = []
	if not has_data():
		lines.append(NO_DATA + ".")
	elif est.is_empty():
		lines.append("FTP estimée : %s (%s)." % [conf.to_lower(), str(data.get("reason", ""))])
	else:
		lines.append("Source : %s." % str(est.get("source_text", "")))
	if focused.begins_with(ROW_PREFIX):
		lines.append_array(_focused_lines(int(focused.substr(ROW_PREFIX.length())), names))
	lines.append("● %s   ○ %s   - - FTP réglée" % [SHORT[window], SHORT["w6" if window == "m6" else "m6"]])
	var warn = data.get("warnings", [])
	for w in (warn if warn is Array else []):
		lines.append(str(w))
	var sheet := {"title": "MA PUISSANCE", "name": WINDOWS[window], "tiles": tiles, "lines": lines}
	if has_data():
		sheet["curve"] = curve()
	return sheet


## Ligne de la durée choisie : « 60 min : 229 W le 12 sept. (ERG) sur 6 mois, 199 W sur 6 semaines ».
func _focused_lines(seconds: int, _names: Dictionary) -> Array:
	for p in points():
		if p is Dictionary and int(p.get("s", 0)) == seconds:
			var parts: Array = []
			for key in ["m6", "w6"]:
				var pt = p.get(key)
				var span := "6 mois" if key == "m6" else "6 semaines"
				if pt is Dictionary:
					parts.append("%d W le %s (%s) sur %s" % [int(pt.get("w", 0)), short_date(str(pt.get("d", ""))),
						str(pt.get("e", "")), span])
				else:
					parts.append("aucun effort à fond sur %s" % span)
			return ["%s : %s." % [duration_label(seconds), ", ".join(parts)]]
	return []
