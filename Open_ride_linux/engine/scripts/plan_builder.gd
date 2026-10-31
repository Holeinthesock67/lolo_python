extends RefCounted

## Plan maison composé dans le menu (lot O30, contrat IPC révision 1.5, commande `create_plan`), sans nœud.
##
## « Plans d'entraînement › Créer un plan » : jours de la semaine (oui / non), entraînements de la
## bibliothèque et test de FTP numérotés dans l'ordre du choix, durée (automatique, ou plus de semaines :
## la suite recommence), puis « Créer le plan ». Le core écrit `~/OpenRide/Plans/mon-plan.toml` (nom
## « Mon plan », « Mon plan 2 »…) et répond `plans` avec `created` ; menu_flow.gd ouvre alors le plan, à
## démarrer comme les autres. Mêmes règles que plans.create_from_library (core) pour l'aperçu.
## Pas de class_name : charger par preload("res://scripts/plan_builder.gd").

const SCREEN := "plan_create"
const DAYS_SCREEN := "plan_create_days"
const WORKOUTS_SCREEN := "plan_create_workouts"
const WEEKS_SCREEN := "plan_create_weeks"
const SCREENS := [SCREEN, DAYS_SCREEN, WORKOUTS_SCREEN, WEEKS_SCREEN]
const DAYS := ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
const DEFAULT_DAYS := ["mardi", "jeudi", "samedi"]
const MAX_WORKOUTS := 42
const MAX_WEEKS := 12
const FTP_TEST := "ftp_test:ramp"
const FTP_TEST_LABEL := "Test de FTP (rampe)"
## Semaines montrées dans la carte d'aperçu ; les suivantes sont résumées sur une ligne.
const PREVIEW_WEEKS := 4

## Jours choisis, dans l'ordre de la semaine.
var days: Array = []
## Entraînements choisis, dans l'ordre du choix (identifiants de `workouts`, ou FTP_TEST).
var workouts: Array = []
## Semaines voulues ; 0 : automatique (autant qu'il en faut).
var weeks := 0


func _init() -> void:
	reset()


func reset() -> void:
	days = DEFAULT_DAYS.duplicate()
	workouts = []
	weeks = 0


static func short_day(day: String) -> String:
	return day.substr(0, 3)


func needed_weeks() -> int:
	if days.is_empty() or workouts.is_empty():
		return 0
	return ceili(float(workouts.size()) / days.size())


func week_count() -> int:
	return weeks if weeks > 0 else needed_weeks()


func session_count() -> int:
	return weeks * days.size() if weeks > 0 else workouts.size()


func can_create() -> bool:
	return not days.is_empty() and not workouts.is_empty()


## Une durée choisie devenue trop courte (plus d'entraînements, moins de jours) repasse en automatique.
func _keep_weeks() -> void:
	if weeks > 0 and weeks < needed_weeks():
		weeks = 0


func toggle_day(day: String) -> void:
	if not day in DAYS:
		return
	if day in days:
		days.erase(day)
	else:
		days.append(day)
		days.sort_custom(func(a, b): return DAYS.find(a) < DAYS.find(b))
	_keep_weeks()


## Ajoute un entraînement en fin de suite, ou le retire (les suivants remontent) ; faux au-delà de 42.
func toggle_workout(id: String) -> bool:
	if id in workouts:
		workouts.erase(id)
	elif workouts.size() >= MAX_WORKOUTS:
		return false
	else:
		workouts.append(id)
	_keep_weeks()
	return true


func set_weeks(n: int) -> void:
	weeks = n if n >= needed_weeks() and n <= MAX_WEEKS else 0


## Suite des séances, semaine par semaine : [[jour, entraînement], …] par semaine.
func schedule() -> Array:
	var out: Array = []
	var total := session_count()
	for i in range(0, total, maxi(days.size(), 1)):
		var week: Array = []
		for k in range(days.size()):
			if i + k < total:
				week.append([days[k], workouts[(i + k) % workouts.size()]])
		out.append(week)
	return out


static func _plural(n: int, word: String) -> String:
	return "%d %s%s" % [n, word, "s" if n > 1 else ""]


func days_text() -> String:
	if days.is_empty():
		return "aucun"
	var names: Array[String] = []
	for d in days:
		names.append(short_day(d))
	return ", ".join(names)


func weeks_text() -> String:
	if workouts.is_empty():
		return "automatique"
	if weeks == 0:
		return "automatique : " + _plural(needed_weeks(), "semaine")
	return _plural(weeks, "semaine")


## Écran « Créer un plan ».
func menu_items() -> Array:
	var create := {"id": "create", "label": "Créer le plan", "enabled": can_create()}
	if can_create():
		create["detail"] = _plural(session_count(), "séance")   # les semaines sont sur la ligne Durée
	return [
		{"id": "days", "label": "Jours", "detail": days_text()},
		{"id": "workouts", "label": "Entraînements",
			"detail": "aucun" if workouts.is_empty() else "%d choisi%s" % [workouts.size(), "s" if workouts.size() > 1 else ""]},
		{"id": "weeks", "label": "Durée", "detail": weeks_text(), "enabled": not workouts.is_empty()},
		create,
	]


func day_items() -> Array:
	var out: Array = []
	for d in DAYS:
		out.append({"id": "day:" + d, "label": str(d).capitalize(), "detail": "oui" if d in days else "non"})
	return out


## Entraînements à choisir : le test de FTP puis la bibliothèque (`raw` : éléments du message `workouts`) ;
## un entraînement choisi porte son rang dans la suite.
func workout_items(raw: Array) -> Array:
	var out: Array = [_workout_item(FTP_TEST, FTP_TEST_LABEL, true)]
	for w in raw:
		if w is Dictionary and str(w.get("id", "")) != "":
			out.append(_workout_item(str(w["id"]), str(w.get("name", w["id"])), bool(w.get("selectable", true))))
	return out


func _workout_item(id: String, label: String, enabled: bool) -> Dictionary:
	var rank := workouts.find(id)
	return {"id": "workout:" + id, "label": label, "enabled": enabled or rank >= 0,
		"detail": "n° %d" % (rank + 1) if rank >= 0 else ""}


func week_items() -> Array:
	var need := needed_weeks()
	var out: Array = [{"id": "weeks:0", "label": "Automatique", "detail": _plural(need, "semaine")
		+ (", choisi" if weeks == 0 else "")}]
	for n in range(maxi(need, 1), MAX_WEEKS + 1):
		var detail := _plural(n * days.size(), "séance")
		if n > need:
			detail += ", la suite recommence"
		out.append({"id": "weeks:%d" % n, "label": _plural(n, "semaine"),
			"detail": detail + (", choisi" if weeks == n else "")})
	return out


## Choix d'une ligne d'un des écrans : {"push": écran}, {"back": true} (durée choisie), ou l'action
## `create_plan` pour main.gd ; {} sinon.
func handle(screen: String, item_id: String) -> Dictionary:
	if screen == SCREEN:
		match item_id:
			"days":
				return {"push": DAYS_SCREEN}
			"workouts":
				return {"push": WORKOUTS_SCREEN}
			"weeks":
				return {"push": WEEKS_SCREEN}
			"create":
				return action() if can_create() else {}
	elif item_id.begins_with("day:"):
		toggle_day(item_id.substr(4))
	elif item_id.begins_with("workout:"):
		toggle_workout(item_id.substr(8))
	elif item_id.begins_with("weeks:"):
		set_weeks(int(item_id.substr(6)))
		return {"back": true}
	return {}


func action() -> Dictionary:
	return {"action": "create_plan", "workouts": workouts.duplicate(), "days": days.duplicate(),
		"weeks": null if weeks == 0 else weeks}


## Nom que le core donnera au plan : « Mon plan », sinon « Mon plan 2 »… (identifiants des plans présents).
static func plan_name(existing_ids: Array) -> String:
	var n := 1
	while ("mon-plan" if n == 1 else "mon-plan-%d" % n) in existing_ids:
		n += 1
	return "Mon plan" if n == 1 else "Mon plan %d" % n


## Carte d'aperçu : les premières semaines (jour et entraînement), puis le reste en une ligne.
func sheet(names: Dictionary, name := "Mon plan") -> Dictionary:
	var lines: Array = []
	if not can_create():
		lines.append("Choisir au moins un jour et un entraînement")
	var plan := schedule()
	for w in range(mini(plan.size(), PREVIEW_WEEKS)):
		var parts: Array[String] = []
		for entry in plan[w]:
			parts.append("%s %s" % [short_day(entry[0]), str(names.get(entry[1], entry[1]))])
		lines.append("S%d : %s" % [w + 1, ", ".join(parts)])
	if plan.size() > PREVIEW_WEEKS:
		lines.append("… jusqu'à la semaine %d" % plan.size())
	lines.append("Le plan se démarre ensuite depuis sa page")
	return {"title": "Aperçu", "name": name, "lines": lines}


## Noms affichés des entraînements (aperçu) d'après la liste `workouts`.
static func names_of(raw: Array) -> Dictionary:
	var out := {FTP_TEST: FTP_TEST_LABEL}
	for w in raw:
		if w is Dictionary and str(w.get("id", "")) != "":
			out[str(w["id"])] = str(w.get("name", w["id"]))
	return out
