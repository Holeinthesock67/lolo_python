extends RefCounted

## Modèle de catalogue et conversion pour les menus (Lot N3, Contrat IPC v1.1).
##
## Transforme les listes de parcours et d'entraînements reçues du core
## en éléments au format de menu_model.set_items ({id, label, enabled, detail}),
## avec tri et textes adaptés, sans aucun nœud Godot.
## Pas de class_name : charger par preload("res://scripts/catalog_model.gd").

const NO_WORKOUT_ID := "_sim"
const SIM_WORKOUT_LABEL := "Rouler sans entraînement (SIM)"


static func _format_fr_km(length_m: float) -> String:
	var km := length_m / 1000.0
	return ("%.1f km" % km).replace(".", ",")


## Convertit une liste de parcours bruts IPC en éléments pour menu_model.set_items(ROUTES, ...) :
## - label : nom, longueur en km avec une décimale, « boucle » le cas échéant ;
## - enabled : vrai si 'ready' ou 'outdated', faux si 'to_compile' ou 'invalid' ;
## - detail : « à compiler », « à recompiler », ou message d'erreur court ;
## - tri : parcours prêts ('ready') d'abord puis par nom ; les autres par nom ensuite.
func route_items(raw_routes: Array) -> Array:
	var ready_list: Array = []
	var other_list: Array = []

	for item in raw_routes:
		if not (item is Dictionary):
			continue
		var r_id: String = str(item.get("id", ""))
		if r_id == "":
			continue
		var name: String = str(item.get("name", r_id))
		var status: String = str(item.get("status", "ready"))
		var length = item.get("length_m", null)
		var r_type = item.get("route_type", null)
		var err = item.get("error", null)

		# Formatage du label
		var parts: Array[String] = []
		if length != null:
			parts.append(_format_fr_km(float(length)))
		if str(r_type) == "loop":
			parts.append("boucle")

		var label := name
		if not parts.is_empty():
			label = "%s (%s)" % [name, ", ".join(parts)]

		# enabled et detail
		var enabled := (status == "ready" or status == "outdated")
		var detail := ""
		match status:
			"to_compile":
				detail = "à compiler"
			"outdated":
				detail = "à recompiler"
			"invalid":
				detail = str(err) if (err != null and str(err) != "") else "invalide"

		var entry := {
			"id": r_id,
			"label": label,
			"enabled": enabled,
			"detail": detail,
			"_name": name.to_lower(),
			"_status": status
		}

		if status == "ready":
			ready_list.append(entry)
		else:
			other_list.append(entry)

	# Tri : prêts par nom, autres par nom
	var sort_by_name = func(a: Dictionary, b: Dictionary) -> bool:
		return str(a["_name"]) < str(b["_name"])

	ready_list.sort_custom(sort_by_name)
	other_list.sort_custom(sort_by_name)

	var out: Array = []
	for e in ready_list:
		e.erase("_name")
		e.erase("_status")
		out.append(e)
	for e in other_list:
		e.erase("_name")
		e.erase("_status")
		out.append(e)

	return out


## Convertit une liste d'entraînements bruts IPC en éléments pour menu_model.set_items(WORKOUTS, ...) :
## - label : nom, durée en min ;
## - enabled : selectable (booléen) ;
## - detail : message d'erreur si invalide ;
## - tri : par durée croissante.
func workout_items(raw_workouts: Array) -> Array:
	var clean: Array = []

	for item in raw_workouts:
		if not (item is Dictionary):
			continue
		var w_id: String = str(item.get("id", ""))
		if w_id == "" or w_id == NO_WORKOUT_ID:
			continue
		var name: String = str(item.get("name", w_id))
		var duration_s = item.get("duration_s", 0)
		var dur_f := float(duration_s) if duration_s != null else 0.0
		var selectable = item.get("selectable", true)
		var err = item.get("error", null)

		var mins := int(round(dur_f / 60.0))
		var label := "%s (%d min)" % [name, mins] if mins > 0 else name
		var enabled := bool(selectable)
		var detail := str(err) if (err != null and str(err) != "") else ""

		clean.append({
			"id": w_id,
			"label": label,
			"enabled": enabled,
			"detail": detail,
			"_dur": dur_f,
			"_name": name.to_lower()
		})

	# Tri par durée
	clean.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		if a["_dur"] != b["_dur"]:
			return a["_dur"] < b["_dur"]
		return a["_name"] < b["_name"]
	)

	var out: Array = []
	for e in clean:
		e.erase("_dur")
		e.erase("_name")
		out.append(e)

	return out
