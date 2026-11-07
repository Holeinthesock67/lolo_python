extends RefCounted

## Écrans de la séance conseillée (série CO, lot CO5, contrat IPC révision 1.6), sans nœud, selon les
## maquettes validées par le propriétaire le 7 novembre (lot CO4, engine/tests/maquette_conseil.gd). Pas de
## class_name : charger par preload("res://scripts/coach_view_model.gd").
##
## Le calcul est celui du core (`openride-core coach --json`, message `coach`) ; ce modèle le met en forme :
## - ligne « Séance conseillée » de l'accueil (home_detail()) ;
## - SCREEN « Séance conseillée : besoin » : raison en ligne d'état, « Lancer l'entraînement » (ERG),
##   « Lancer la course » (séance de jeu calibrée, lot CO9), autre séance du même besoin, autre besoin,
##   montre (CO8), prochaine course, objectif et temps disponible (réglages du profil), détail du calcul ;
## - DETAIL : répartition du temps sur 4 semaines en regard de la cible, forme, profil, FTP, courses, règle ;
## - NEED : « Choisir un autre besoin » (get_coach {need}, règle CH) ;
## - RACE : « Ma prochaine course » (set_next_race, clear_next_race) ;
## - WATCH : « Suggestion de ma montre » recopiée de la montre Garmin (set_watch_advice, clear_watch_advice) ;
## - OTHER : l'entraînement conseillé et les autres du même besoin.
## Les champs de RACE et WATCH se modifient en place comme un réglage (settings_view_model.gd, clés KEY_PREFIX) ;
## commit() renvoie l'action interne `coach_set`, traitée par set_field().

const SCREEN := "coach"
const DETAIL := "coach_detail"
const NEED := "coach_need"
const RACE := "coach_race_date"
const WATCH := "coach_watch"
const OTHER := "coach_other"
const SCREENS := [SCREEN, DETAIL, NEED, RACE, WATCH, OTHER]
## Champs des saisies (RACE, WATCH), modifiés par l'écran de modification des réglages.
const KEY_PREFIX := "conseil."
## Réglages du profil montrés sur l'écran du conseil (lignes « set:clé »), libellés sans « Conseil : ».
const SETTING_KEYS := ["coach.objectif", "coach.temps_disponible_min"]
const SETTING_PREFIX := "Conseil : "
const LOADING := "Calcul du conseil…"
const OTHER_PREFIX := "w:"
const NEED_PREFIX := "need_"
## Besoins de « Choisir un autre besoin » (CHOSEN_NEEDS du core), dans l'ordre de l'écran.
const NEEDS := ["light", "intense", "anaerobic", "recovery", "ftp_test"]
## Libellé, zones et explication de chaque besoin (zones de data/coach.toml du core, [needs]).
const NEED_TEXTS := {
	"light": ["Aérobie léger", "Z1–Z2", "Zones Z1 et Z2, jusqu'à 75 % de la FTP."],
	"intense": ["Aérobie intense", "Z3–Z5", "Zones Z3 à Z5, de 75 à 120 % de la FTP."],
	"anaerobic": ["Anaérobie", "Z6–Z7", "Au-dessus de 120 % de la FTP."],
	"recovery": ["Récupération", "Z1", "Zone Z1, sous 55 % de la FTP."],
	"ftp_test": ["Test de FTP", "", "Test de 20 min ou rampe : la FTP sert à toutes les zones."],
	"rest": ["Repos", "", "Pas de vélo aujourd'hui."],
	"plan": ["Séance du plan", "", "La séance du jour du plan actif."]}
const OBJECTIVE_TEXTS := {"endurance": "endurance", "courses": "courses", "grimpeur": "grimpeur", "reprise": "reprise"}
const RACE_KINDS := ["course", "championnat"]
const RACE_KIND_TEXTS := {"course": "course", "championnat": "manche de championnat"}
const RACE_KIND_LABELS := {"survivor": "Dernier survivant", "rogue": "Cyber-Rogue", "bots": "course contre les bots"}
const CAUSE_TEXTS := {"light": "à court de fond", "intense": "lâché en montée", "anaerobic": "battu au sprint"}
## Types de la montre (section [watch] de data/coach.toml du core), dans l'ordre de l'écran.
const WATCH_TYPES := ["repos", "recuperation", "fond", "tempo", "seuil", "vo2max", "anaerobie", "sprint"]
const WATCH_TEXTS := {"repos": "repos", "recuperation": "récupération", "fond": "fond", "tempo": "tempo",
	"seuil": "seuil", "vo2max": "VO2 max", "anaerobie": "anaérobie", "sprint": "sprint"}
const DAYS := ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."]
## Champs des saisies : {nom: [libellé, type, min, max, pas]} ; une valeur 0 de durée ou de puissance : « aucune ».
const FIELDS := {
	"race_days": ["Date", "int", 0, 365, 1],
	"race_kind": ["Type", "choice"],
	"watch_type": ["Type", "choice"],
	"watch_min": ["Durée", "int", 0, 600, 5],
	"watch_w": ["Puissance cible", "int", 0, 1000, 5]}

## Dernier message `coach` ({} avant la première réponse).
var msg: Dictionary = {}
## Besoin choisi par « Autre besoin » ("" : le conseil du jour), renvoyé à chaque `get_coach`.
var chosen_need := ""
## Ligne d'état des écrans du conseil (calcul en cours, erreur du core).
var message := ""
## Valeurs des saisies de RACE et WATCH (jours à partir du jour du conseil pour la date).
var form := {"race_days": 7, "race_kind": "course", "watch_type": "fond", "watch_min": 0, "watch_w": 0}


func loaded() -> bool:
	return not msg.is_empty()


## Arguments de `get_coach` : le besoin choisi, sinon rien.
func request_args() -> Dictionary:
	return {"need": chosen_need} if chosen_need != "" else {}


## Action `get_coach` pour main.gd ; la ligne d'état attend la réponse.
func request() -> Dictionary:
	message = LOADING
	return command("get_coach", request_args())


static func command(name: String, args := {}) -> Dictionary:
	return {"action": "coach_command", "name": name, "args": args}


## Message `coach` du core : conseil affiché, saisies remises aux valeurs enregistrées.
func on_coach(m: Dictionary) -> void:
	msg = m
	message = ""
	var d := details()
	var race = d.get("next_race")
	if race is Dictionary:
		form["race_days"] = clampi(days_between(str(m.get("date", "")), str(race.get("date", ""))), 0, 365)
		form["race_kind"] = str(race.get("kind", "course"))
	var watch = d.get("watch")
	if watch is Dictionary:
		form["watch_type"] = str(watch.get("type", "fond"))
		form["watch_min"] = int(watch.get("duration_min")) if watch.get("duration_min") != null else 0
		form["watch_w"] = int(round(float(watch.get("target_w")))) if watch.get("target_w") != null else 0


func details() -> Dictionary:
	var d = msg.get("details", {})
	return d if d is Dictionary else {}


func need() -> String:
	return str(msg.get("need", ""))


## Besoin conseillé par le calcul du jour : le premier « autre besoin » quand un besoin a été choisi (règle CH).
func advised_need() -> String:
	if str(msg.get("rule", "")) == "CH":
		var alts = msg.get("alternatives", [])
		return str(alts[0]) if alts is Array and not alts.is_empty() else ""
	return need()


static func need_name(n: String) -> String:
	return str(NEED_TEXTS.get(n, [n])[0])


static func first_upper(text: String) -> String:
	return text.left(1).to_upper() + text.substr(1)


static func minutes(seconds) -> int:
	return int(round(float(seconds if seconds != null else 0) / 60.0))


func workout() -> Dictionary:
	var w = msg.get("workout")
	return w if w is Dictionary else {}


func route() -> Dictionary:
	var r = msg.get("route")
	return r if r is Dictionary else {}


func other_workouts() -> Array:
	var out: Array = []
	var raw = msg.get("other_workouts", [])
	for w in (raw if raw is Array else []):
		if w is Dictionary:
			out.append(w)
	return out


# --- accueil -------------------------------------------------------------------------------------

## Détail de la ligne « Séance conseillée » de l'accueil : besoin et durée ; "" avant la première réponse (pas de ligne).
func home_detail() -> String:
	if not loaded():
		return ""
	if need() == "rest":
		return "repos"
	return "%s · %d min" % [str(msg.get("need_label", need_name(need()))), minutes(msg.get("duration_s"))]


# --- écran du conseil ------------------------------------------------------------------------------

func title() -> String:
	if not loaded():
		return "Séance conseillée"
	return "Séance conseillée : " + str(msg.get("need_label", need_name(need())))


func status(screen: String) -> String:
	if message != "" or not loaded():
		return message if message != "" else LOADING
	match screen:
		SCREEN:
			return "Pourquoi : " + str(msg.get("reason", ""))
		DETAIL:
			return "Répartition du temps sur 4 semaines, en regard de ta cible (objectif %s)." \
				% str(OBJECTIVE_TEXTS.get(str(details().get("objective", "")), details().get("objective", "")))
		NEED:
			return "Le conseil du jour reste proposé en premier ; ton choix ne change rien au calcul."
		RACE:
			return "Deux jours avant : activation courte. Le lendemain : récupération."
		WATCH:
			return "Recopie l'entraînement du jour de ta montre Garmin. OpenRide ne se connecte pas à Garmin Connect."
		OTHER:
			return "Entraînements de ta bibliothèque pour le besoin du jour."
	return ""


## Libellé de la ligne qui lance l'entraînement, selon le besoin.
func workout_label() -> String:
	match need():
		"plan":
			return "Lancer la séance du plan"
		"ftp_test":
			return "Lancer le test de FTP"
	return "Lancer l'entraînement"


## Ligne « Lancer l'entraînement » utilisable : un entraînement proposé, la séance du plan ou le test de FTP.
func can_launch_workout() -> bool:
	return need() in ["plan", "ftp_test"] or not workout().is_empty()


func items(setting_rows: Array) -> Array:
	if not loaded():
		return [{"id": "none", "label": LOADING, "enabled": false}]
	var out: Array = []
	if need() == "rest":
		out.append({"id": "rest", "label": "Repos conseillé aujourd'hui", "enabled": false})
	else:
		var w := workout()
		var detail := "%d min" % minutes(w.get("duration_s")) if not w.is_empty() else "aucun dans ta bibliothèque"
		if need() in ["plan", "ftp_test"]:
			detail = "%d min" % minutes(msg.get("duration_s"))
		out.append({"id": "coach_workout", "label": workout_label(), "enabled": can_launch_workout(), "detail": detail})
		var r := route()
		if r.is_empty():
			out.append({"id": "coach_race", "label": "Lancer la course", "enabled": false,
				"detail": "aucun parcours adapté"})
		else:
			out.append({"id": "coach_race", "label": "Lancer le Dernier survivant" if str(r.get("mode", "")) == "survivor"
				else "Lancer la course", "detail": "%d min" % minutes(r.get("duration_s"))})
	var others := other_workouts().size()
	out.append({"id": "coach_other", "label": "Autre séance", "enabled": others > 0,
		"detail": "%d de plus" % others if others > 0 else "aucune"})
	out.append({"id": "coach_need", "label": "Autre besoin",
		"detail": need_name(chosen_need) if chosen_need != "" else ""})
	var watch = details().get("watch")
	out.append({"id": "coach_watch", "label": "Ma montre",
		"detail": str(WATCH_TEXTS.get(str(watch.get("type", "")), "")) if watch is Dictionary else "aucune"})
	var race = details().get("next_race")
	out.append({"id": "coach_race_date", "label": "Prochaine course",
		"detail": date_text(str(race.get("date", ""))) if race is Dictionary else "aucune"})
	for row in setting_rows:
		var e: Dictionary = row.duplicate()
		e["label"] = first_upper(str(e.get("label", "")).trim_prefix(SETTING_PREFIX))
		out.append(e)
	out.append({"id": "coach_detail", "label": "Détail du calcul"})
	return out


## Carte de l'écran du conseil : la course quand elle a le focus, sinon l'entraînement conseillé.
func sheet(focused: String) -> Dictionary:
	if not loaded():
		return {}
	if focused == "coach_race" and not route().is_empty():
		return route_sheet()
	return workout_sheet(workout())


func workout_sheet(w: Dictionary) -> Dictionary:
	var n := need()
	var lines: Array = [str(NEED_TEXTS.get(str(w.get("need", n)), ["", "", ""])[2]),
		"Règle %s · objectif %s." % [str(msg.get("rule", "")),
			str(OBJECTIVE_TEXTS.get(str(details().get("objective", "")), details().get("objective", "")))]]
	for note in msg.get("notes", []):
		lines.append(str(note))
	var r := route()
	if not r.is_empty():
		lines.append("À côté : « %s », %s." % ["Lancer le Dernier survivant" if str(r.get("mode", "")) == "survivor"
			else "Lancer la course", str(r.get("label", "")).to_lower()])
	if w.is_empty():
		var label := need_name(n)
		return {"title": "Séance conseillée", "name": label, "tiles": [
			{"label": "Durée", "value": str(minutes(msg.get("duration_s"))), "unit": "min"}], "lines": lines}
	var tiles: Array = [{"label": "Durée", "value": str(minutes(w.get("duration_s"))), "unit": "min"}]
	if w.get("tss_estimate") != null:
		tiles.append({"label": "TSS estimé", "value": str(int(round(float(w["tss_estimate"]))))})
	if w.get("dominant_zone") != null:
		tiles.append({"label": "Zone", "value": str(w["dominant_zone"]), "gold": true})
	return {"title": "Entraînement conseillé", "name": str(w.get("name", w.get("id", ""))), "tiles": tiles, "lines": lines}


func route_sheet() -> Dictionary:
	var r := route()
	var laps := int(r.get("laps", 1))
	var name := "%s · %d tour%s" % [str(r.get("route_name", r.get("route_id", ""))), laps, "s" if laps > 1 else ""]
	var bots: Dictionary = r.get("bots", {}) if r.get("bots") is Dictionary else {}
	var tiles: Array = []
	var lines: Array = [str(r.get("label", "")) + "."]
	if str(r.get("mode", "")) == "survivor" and r.get("survivor") is Dictionary:
		var s: Dictionary = r["survivor"]
		tiles.append({"label": "Adversaires", "value": str(int(s.get("opponents", 0)))})
		tiles.append({"label": "Arches", "value": str(int(s.get("spacing_km", 1))), "unit": "km"})
		lines.append("Réglages du Dernier survivant mis à %d adversaires," % int(s.get("opponents", 0)))
		lines.append("une arche tous les %d km." % int(s.get("spacing_km", 1)))
	else:
		tiles.append({"label": "Bots", "value": str(int(bots.get("count", 0)))})
		if int(bots.get("count", 0)) > 0:
			tiles.append({"label": "Niveau", "value": str(int(bots.get("level_pct", 0))), "unit": "%"})
	tiles.append({"label": "Dans le besoin", "value": str(int(r.get("ratio_pct", 0))), "unit": "%", "gold": true})
	lines.append("Simulée à tes valeurs : %d min dans les zones du besoin" % minutes(r.get("predicted_need_s")))
	lines.append("pour %d min avec l'entraînement." % minutes(r.get("reference_need_s")))
	lines.append("Difficulté de la pente : la tienne.")
	return {"title": "Course contre des bots" if str(r.get("mode", "")) == "ride" and int(bots.get("count", 0)) > 0
		else ("Dernier survivant" if str(r.get("mode", "")) == "survivor" else "Séance en jeu"),
		"name": name, "tiles": tiles, "lines": lines}


## Bots de l'argument `start` pour la course conseillée (mode « ride ») : bots à profil, avec leur tactique (lot Y10),
## quand le format en demande une, sinon bots à puissance constante au même % de la FTP (rouler dans les roues).
func race_bots(profiles: Array) -> Array:
	var b = route().get("bots", {})
	if not (b is Dictionary):
		return []
	var out: Array = []
	for i in range(int(b.get("count", 0))):
		if str(b.get("tactics", "none")) == "none":
			out.append({"kind": "constant", "ftp_pct": int(b.get("level_pct", 100))})
		else:
			out.append({"kind": "profile", "profile": profiles[i % profiles.size()], "level_pct": int(b.get("level_pct", 100))})
	return out


## Texte de l'écran Prêt de la course conseillée : format, tours, durée.
func race_ready_text() -> String:
	var r := route()
	var laps := int(r.get("laps", 1))
	return "%d tour%s, environ %d min" % [laps, "s" if laps > 1 else "", minutes(r.get("duration_s"))]


# --- détail du calcul ---------------------------------------------------------------------------------

func detail_items() -> Array:
	if not loaded():
		return [{"id": "none", "label": LOADING, "enabled": false}]
	var d := details()
	var sh: Dictionary = d.get("shares_pct", {}) if d.get("shares_pct") is Dictionary else {}
	var out: Array = []
	for n in ["light", "intense", "anaerobic"]:
		var pct := float(sh.get(n, 0.0))
		out.append({"id": "d_" + n, "label": str(NEED_TEXTS[n][0]).replace("Aérobie l", "L").replace("Aérobie i", "I"),
			"detail": "%d %%" % int(round(pct)), "bar": clampi(int(round(pct)), 0, 100)})
	out.append({"id": "d_form", "label": "Forme", "detail": "%+d" % int(round(float(d.get("form", 0.0))))})
	var hard = d.get("days_since_hard")
	out.append({"id": "d_hard", "label": "Séance dure", "detail": "il y a %d j" % int(hard) if hard != null else "aucune"})
	var weak = d.get("profile_weak")
	out.append({"id": "d_profile", "label": "Point faible du profil", "detail": need_name(str(weak)).to_lower() if weak != null else "aucun"})
	out.append({"id": "d_ftp", "label": "FTP", "detail": "%d W" % int(round(float(d.get("ftp_w", 0.0))))})
	var races: Array = d.get("races", []) if d.get("races") is Array else []
	out.append({"id": "d_races", "label": "Dernières courses", "detail": str(races.size()) if not races.is_empty() else "aucune"})
	out.append({"id": "d_rule", "label": "Règle", "detail": str(msg.get("rule", ""))})
	return out


## Carte du détail : le besoin qui a le focus (part, cible, retard), sinon le besoin du jour.
func detail_sheet(focused: String) -> Dictionary:
	if not loaded():
		return {}
	var d := details()
	var n := focused.substr(2) if focused.begins_with("d_") and focused.substr(2) in ["light", "intense", "anaerobic"] else advised_need()
	if not n in ["light", "intense", "anaerobic"]:
		n = "intense"
	var share := float((d.get("shares_pct", {}) as Dictionary).get(n, 0.0)) if d.get("shares_pct") is Dictionary else 0.0
	var target := float((d.get("targets_pct", {}) as Dictionary).get(n, 0.0)) if d.get("targets_pct") is Dictionary else 0.0
	var lines: Array = ["Le plus grand retard décide (règle R6)."]
	var last = (d.get("last_by_need", {}) as Dictionary).get(n) if d.get("last_by_need") is Dictionary else null
	lines.append("Dernière séance de ce type : %s." % (date_text(str(last)) if last != null else "aucune en 4 semaines"))
	lines.append("%d séance%s dure%s ces 7 derniers jours." % [int(d.get("hard_last_7d", 0)),
		"s" if int(d.get("hard_last_7d", 0)) > 1 else "", "s" if int(d.get("hard_last_7d", 0)) > 1 else ""])
	var races: Array = d.get("races", []) if d.get("races") is Array else []
	for race in races:
		if race is Dictionary:
			lines.append(race_text(race))
	return {"title": need_name(n), "name": "Zones " + str(NEED_TEXTS[n][1]).replace("–", " à "), "tiles": [
		{"label": "Part", "value": str(int(round(share))), "unit": "%"},
		{"label": "Cible", "value": str(int(round(target))), "unit": "%"},
		{"label": "Retard", "value": str(maxi(int(round(target - share)), 0)), "unit": "pts", "gold": true}], "lines": lines}


## « Course : 05/11 Dernier survivant, 3e, lâché en montée. »
static func race_text(race: Dictionary) -> String:
	var parts: Array = [str(race.get("date", "")).substr(8, 2) + "/" + str(race.get("date", "")).substr(5, 2),
		str(RACE_KIND_LABELS.get(str(race.get("kind", "")), race.get("kind", "")))]
	if race.get("place") != null:
		parts[1] += ", %d%s" % [int(race["place"]), "er" if int(race["place"]) == 1 else "e"]
	if race.get("cause") != null:
		parts[1] += ", " + str(CAUSE_TEXTS.get(str(race["cause"]), race["cause"]))
	return "Course : %s %s." % [parts[0], parts[1]]


# --- autre besoin -------------------------------------------------------------------------------------

func need_items() -> Array:
	var out: Array = []
	var advised := advised_need()
	for n in NEEDS:
		var detail := str(NEED_TEXTS[n][1])
		if n == advised:
			detail = "conseillé"
		elif n == chosen_need:
			detail = "choisi"
		out.append({"id": NEED_PREFIX + n, "label": need_name(n), "detail": detail})
	return out


func need_sheet(focused: String) -> Dictionary:
	var n := focused.trim_prefix(NEED_PREFIX)
	if not n in NEEDS:
		return {}
	return {"title": need_name(n), "name": str(NEED_TEXTS[n][2]), "tiles": [],
		"lines": ["Règle CH : le conseil du jour reste", "en première autre idée."]}


## A sur un besoin : besoin choisi (celui du conseil : retour au conseil du jour) et `get_coach`.
func choose_need(item_id: String) -> Dictionary:
	var n := item_id.trim_prefix(NEED_PREFIX)
	if not n in NEEDS:
		return {}
	chosen_need = "" if n == advised_need() else n
	return request()


# --- autre séance ---------------------------------------------------------------------------------------

func other_items() -> Array:
	var out: Array = []
	var all: Array = ([workout()] if not workout().is_empty() else []) + other_workouts()
	for w in all:
		var tss := " · TSS %d" % int(round(float(w["tss_estimate"]))) if w.get("tss_estimate") != null else ""
		out.append({"id": OTHER_PREFIX + str(w.get("id", "")), "label": str(w.get("name", w.get("id", ""))),
			"detail": "%d min%s" % [minutes(w.get("duration_s")), tss]})
	if out.is_empty():
		out.append({"id": "none", "label": "Aucun entraînement de ce besoin", "enabled": false})
	return out


func other_sheet(focused: String) -> Dictionary:
	for w in ([workout()] if not workout().is_empty() else []) + other_workouts():
		if OTHER_PREFIX + str(w.get("id", "")) == focused:
			return workout_sheet(w)
	return {}


# --- saisies : prochaine course et montre ----------------------------------------------------------

## Champ d'une saisie pour l'écran de modification ({key, label, type, value, …}).
func field(name: String) -> Dictionary:
	var f: Array = FIELDS[name]
	var it := {"key": KEY_PREFIX + name, "label": f[0], "type": f[1], "value": form[name], "base_date": str(msg.get("date", ""))}
	if f[1] == "int":
		it.merge({"min": f[2], "max": f[3], "step": f[4]})
	else:
		it["choices"] = (RACE_KINDS if name == "race_kind" else WATCH_TYPES).duplicate()
	return it


## Valeur d'un champ en texte (rangée et modification), `key` avec KEY_PREFIX ; `base_date` : jour du conseil.
static func format_edit(key: String, value, base_date: String) -> String:
	match key.trim_prefix(KEY_PREFIX):
		"race_days":
			var day := add_days(base_date, int(value))
			return date_text(day) + (" (aujourd'hui)" if int(value) == 0 else " (dans %d j)" % int(value))
		"race_kind":
			return str(RACE_KIND_TEXTS.get(str(value), value))
		"watch_type":
			return str(WATCH_TEXTS.get(str(value), value))
		"watch_min":
			return "%d min" % int(value) if int(value) > 0 else "aucune"
		"watch_w":
			return "%d W" % int(value) if int(value) > 0 else "aucune"
	return str(value)


func set_field(name: String, value) -> void:
	if form.has(name):
		form[name] = value


func _row(name: String, editing: Dictionary) -> Dictionary:
	var it := field(name)
	var mine: bool = str(editing.get("key", "")) == it["key"]
	var value = editing.get("value") if mine else it["value"]
	var out := {"id": "set:" + str(it["key"]), "label": it["label"], "detail": format_edit(str(it["key"]), value, str(it["base_date"]))}
	if mine:
		out["detail"] = "◀ %s ▶" % out["detail"]
		out["editing"] = true
	return out


func race_items(editing: Dictionary) -> Array:
	var saved = details().get("next_race")
	return [_row("race_days", editing), _row("race_kind", editing), {"id": "race_save", "label": "Enregistrer"},
		{"id": "race_clear", "label": "Effacer", "enabled": saved is Dictionary}]


func watch_items(editing: Dictionary) -> Array:
	var saved = details().get("watch")
	return [_row("watch_type", editing), _row("watch_min", editing), _row("watch_w", editing),
		{"id": "watch_save", "label": "Enregistrer"}, {"id": "watch_clear", "label": "Effacer", "enabled": saved is Dictionary}]


func race_sheet() -> Dictionary:
	var day := add_days(str(msg.get("date", "")), int(form["race_days"]))
	var n := int(form["race_days"])
	return {"title": "Course annoncée", "name": "Aujourd'hui" if n == 0 else "Dans %d jour%s" % [n, "s" if n > 1 else ""],
		"tiles": [{"label": "Activation", "value": date_text(add_days(day, -2)).substr(5)},
			{"label": "Récupération", "value": date_text(add_days(day, 1)).substr(5)}],
		"lines": ["Types : course ou manche de championnat.", "Gardée dans ton profil jusqu'à son jour."]}


func watch_sheet() -> Dictionary:
	var saved = details().get("watch")
	var name := first_upper(str(WATCH_TEXTS.get(str(form["watch_type"]), form["watch_type"])))
	if saved is Dictionary and str(saved.get("type", "")) == str(form["watch_type"]):
		name += " → " + need_name(str(saved.get("need", ""))).to_lower()
	var tiles: Array = [{"label": "Règle", "value": "RG"}]
	if int(form["watch_min"]) > 0:
		tiles.append({"label": "Durée", "value": str(int(form["watch_min"])), "unit": "min"})
	if int(form["watch_w"]) > 0:
		tiles.append({"label": "Cible", "value": str(int(form["watch_w"])), "unit": "W"})
	return {"title": "Ce que fera le conseil", "name": name, "tiles": tiles,
		"lines": ["Passe avant les autres règles, pour la journée.", "Une course hier ou dans 2 jours s'affiche",
			"en note, sans l'annuler."]}


## « Enregistrer » et « Effacer » des saisies : commande du core (réponse `coach`, conseil du jour recalculé avec
## la saisie : le besoin choisi est oublié, ces commandes n'en portent pas).
func save_race() -> Dictionary:
	chosen_need = ""
	message = "Enregistrement…"
	return command("set_next_race", {"date": add_days(str(msg.get("date", "")), int(form["race_days"])),
		"kind": str(form["race_kind"])})


func save_watch() -> Dictionary:
	chosen_need = ""
	message = "Enregistrement…"
	var args := {"type": str(form["watch_type"])}
	if int(form["watch_min"]) > 0:
		args["duration_min"] = maxi(int(form["watch_min"]), 5)
	if int(form["watch_w"]) > 0:
		args["target_w"] = int(form["watch_w"])
	return command("set_watch_advice", args)


func clear(name: String) -> Dictionary:
	chosen_need = ""
	message = "Effacement…"
	return command(name)


# --- dates ----------------------------------------------------------------------------------------------

static func _unix(day: String) -> int:
	return Time.get_unix_time_from_datetime_string(day + "T12:00:00") if day.length() == 10 else 0


static func add_days(day: String, n: int) -> String:
	if day.length() != 10:
		return ""
	return Time.get_date_string_from_unix_time(_unix(day) + n * 86400)


static func days_between(a: String, b: String) -> int:
	if a.length() != 10 or b.length() != 10:
		return 0
	return int(round((_unix(b) - _unix(a)) / 86400.0))


## « sam. 14/11 ».
static func date_text(day: String) -> String:
	if day.length() != 10:
		return day
	var d := Time.get_date_dict_from_unix_time(_unix(day))
	return "%s %s/%s" % [DAYS[int(d["weekday"])], day.substr(8, 2), day.substr(5, 2)]
