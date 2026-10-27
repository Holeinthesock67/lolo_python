extends RefCounted

## Modèle de catalogue et conversion pour les menus (Lot N3, Contrat IPC v1.1).
##
## Transforme les listes de parcours et d'entraînements reçues du core
## en éléments au format de menu_model.set_items ({id, label, enabled, detail}),
## avec tri et textes adaptés, sans aucun nœud Godot.
## Pas de class_name : charger par preload("res://scripts/catalog_model.gd").

const NO_WORKOUT_ID := "_sim"
const SIM_WORKOUT_LABEL := "Rouler sans entraînement (SIM)"
## Tris de la bibliothèque (lot O12), dans l'ordre du cycle au Click : clé (celles de
## `openride-core library --sort`) et libellé. Croissants ; un parcours sans la valeur vient en dernier.
const ROUTE_SORTS := [["nom", "nom"], ["distance", "distance"], ["deniv", "dénivelé"],
	["difficulte", "difficulté"], ["duree", "durée estimée"]]


static func _format_fr_km(length_m: float) -> String:
	var km := length_m / 1000.0
	return ("%.1f km" % km).replace(".", ",")


static func _format_fr_duration(seconds: float) -> String:
	var mins := int(round(seconds / 60.0))
	return "%d min" % mins if mins < 60 else "%d h %02d" % [mins / 60, mins % 60]


## Étiquettes de la bibliothèque (`library.tags`, lot O15), sans doublon, triées.
static func route_tags(raw_routes: Array) -> Array:
	var tags: Array = []
	for item in raw_routes:
		if item is Dictionary and item.get("library") is Dictionary and item["library"].get("tags") is Array:
			for t in item["library"]["tags"]:
				if not str(t) in tags:
					tags.append(str(t))
	tags.sort()
	return tags


## Valeur de tri d'un parcours (ROUTE_SORTS) ; null si le parcours ne l'a pas (fiche absente).
static func _sort_value(item: Dictionary, key: String):
	var st: Dictionary = item["stats"] if item.get("stats") is Dictionary else {}
	match key:
		"distance":
			return item.get("length_m", null)
		"deniv":
			return st.get("gain_m", null)
		"difficulte":
			return st.get("difficulty", null)
		"duree":
			return st.get("duration_s", null)
	return null


## Fiche d'un parcours pour l'écran Prêt (lot O12) : lignes de texte depuis `stats` et `library` ;
## vide sans fiche. Durée estimée à la FTP du core (contrat 1.3).
static func route_card(item: Dictionary) -> Array:
	var out: Array = []
	var st = item.get("stats", null)
	if st is Dictionary:
		var parts: Array[String] = [_format_fr_km(float(st.get("distance_m", item.get("length_m", 0.0)))),
			"↑ %d m" % int(round(float(st.get("gain_m", 0.0)))),
			"pente max %s %%" % _format_fr_1(float(st.get("max_grade_pct", 0.0)))]
		if st.get("difficulty", null) != null:
			parts.append("difficulté %d / 5" % int(st["difficulty"]))
		if st.get("duration_s", null) != null:
			parts.append("≈ " + _format_fr_duration(float(st["duration_s"])))
		out.append(" · ".join(parts))
		var climb = st.get("main_climb", null)
		if climb is Dictionary:
			var cat := " (cat. %s)" % str(climb["category"]) if climb.get("category", null) != null else ""
			out.append("Montée principale : %s à %s %%, ↑ %d m%s" % [_format_fr_km(float(climb.get("length_m", 0.0))),
				_format_fr_1(float(climb.get("avg_grade_pct", 0.0))), int(round(float(climb.get("gain_m", 0.0)))), cat])
	var lib = item.get("library", null)
	if lib is Dictionary:
		var words: Array[String] = []
		if str(lib.get("region", "")) != "":
			words.append(str(lib["region"]))
		if lib.get("tags") is Array:
			for t in lib["tags"]:
				words.append(str(t))
		var head := ", ".join(words)
		var desc := str(lib.get("description", ""))
		var line := head + (" — " if head != "" and desc != "" else "") + desc
		if line != "":
			out.append(line)
	return out


static func _format_fr_1(val: float) -> String:
	return ("%.1f" % val).replace(".", ",")


## Convertit une liste de parcours bruts IPC en éléments pour menu_model.set_items(ROUTES, ...) :
## - label : nom, longueur en km avec une décimale, dénivelé (fiche du lot O12), « boucle » le cas échéant ;
## - enabled : vrai si 'ready' ou 'outdated', faux si 'to_compile' ou 'invalid' ;
## - detail : « à compiler », « à recompiler », ou message d'erreur court ; étiquettes d'un parcours prêt ;
## - tri : parcours prêts ('ready') d'abord puis les autres, chacun par `sort_key` (ROUTE_SORTS, nom
##   à égalité) ;
## - filtre : `tag` non vide garde les parcours qui portent cette étiquette.
func route_items(raw_routes: Array, sort_key := "nom", tag := "") -> Array:
	var ready_list: Array = []
	var other_list: Array = []

	for item in raw_routes:
		if not (item is Dictionary):
			continue
		var r_id: String = str(item.get("id", ""))
		if r_id == "":
			continue
		var tags: Array = []
		if item.get("library") is Dictionary and item["library"].get("tags") is Array:
			tags = item["library"]["tags"]
		if tag != "" and not tag in tags.map(func(t): return str(t)):
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
		if item.get("stats") is Dictionary and item["stats"].get("gain_m", null) != null:
			parts.append("↑ %d m" % int(round(float(item["stats"]["gain_m"]))))
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
			_:
				detail = ", ".join(PackedStringArray(tags.map(func(t): return str(t))))

		var entry := {
			"id": r_id,
			"label": label,
			"enabled": enabled,
			"detail": detail,
			"_name": name.to_lower(),
			"_status": status,
			"_key": _sort_value(item, sort_key),
		}

		if status == "ready":
			ready_list.append(entry)
		else:
			other_list.append(entry)

	# Tri : prêts puis autres, chacun par la clé choisie (absente : à la fin), puis par nom
	var sort_by_name = func(a: Dictionary, b: Dictionary) -> bool:
		if a["_key"] != b["_key"]:
			if a["_key"] == null or b["_key"] == null:
				return b["_key"] == null
			return float(a["_key"]) < float(b["_key"])
		return str(a["_name"]) < str(b["_name"])

	ready_list.sort_custom(sort_by_name)
	other_list.sort_custom(sort_by_name)

	var out: Array = []
	for e in ready_list + other_list:
		e.erase("_name")
		e.erase("_status")
		e.erase("_key")
		out.append(e)

	return out


## Convertit une liste d'entraînements bruts IPC en éléments pour menu_model.set_items(WORKOUTS, ...) :
## - label : nom, durée en min ;
## - enabled : selectable (booléen) ;
## - detail : message d'erreur si invalide ; « watts fixes » pour un fichier en watts absolus (`unit`,
##   .erg et .mrc, lot O12), avec la puissance maximale si `ftp_w` (FTP du core) est connue ;
## - tri : par durée croissante.
func workout_items(raw_workouts: Array, ftp_w := 0.0) -> Array:
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
		if detail == "" and str(item.get("unit", "ftp")) == "watts":
			detail = "watts fixes"
			var top := 0.0
			for b in (item.get("profile", []) if item.get("profile") is Array else []):
				if b is Array and b.size() >= 3:
					top = maxf(top, maxf(float(b[1]), float(b[2])))
			if ftp_w > 0.0 and top > 0.0:
				detail += ", jusqu'à %d W" % int(round(top * ftp_w))

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
