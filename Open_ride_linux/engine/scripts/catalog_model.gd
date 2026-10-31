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


## Fiche d'un parcours pour la carte de détail des menus (lot O12, mise en forme du lot « présentation
## des menus », étape 2) : nom, chiffres clés (`tiles`, valeur et unité séparées pour les mettre en
## valeur), lignes de texte (montée principale, difficulté et durée, bibliothèque). Depuis `stats` et
## `library` ; sans fiche calculée, seule la longueur. Durée estimée à la FTP du core (contrat 1.3).
## Le profil d'altitude n'est pas dans la liste : main.gd l'ajoute (`profile`) quand le parcours est chargé.
static func route_sheet(item: Dictionary) -> Dictionary:
	var tiles: Array = []
	var lines: Array = []
	var st = item.get("stats", null)
	var length = st.get("distance_m", item.get("length_m", null)) if st is Dictionary else item.get("length_m", null)
	if length != null:
		tiles.append(_tile("Distance", _format_fr_1(float(length) / 1000.0), "km"))
	if st is Dictionary:
		tiles.append(_tile("Dénivelé", "↑ %d" % int(round(float(st.get("gain_m", 0.0)))), "m"))
		tiles.append(_tile("Pente max", _format_fr_1(float(st.get("max_grade_pct", 0.0))), "%"))
		var climb = st.get("main_climb", null)
		if climb is Dictionary:
			var cat := " (cat. %s)" % str(climb["category"]) if climb.get("category", null) != null else ""
			lines.append("Montée principale : %s à %s %%, ↑ %d m%s" % [_format_fr_km(float(climb.get("length_m", 0.0))),
				_format_fr_1(float(climb.get("avg_grade_pct", 0.0))), int(round(float(climb.get("gain_m", 0.0)))), cat])
		var parts: Array[String] = []
		if st.get("difficulty", null) != null:
			parts.append("Difficulté %d / 5" % int(st["difficulty"]))
		if st.get("duration_s", null) != null:
			parts.append("durée ≈ " + _format_fr_duration(float(st["duration_s"])))
		if not parts.is_empty():
			lines.append(" · ".join(parts))
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
			lines.append(line)
	return {"title": "Parcours", "id": str(item.get("id", "")), "name": str(item.get("name", item.get("id", ""))),
		"tiles": tiles, "lines": lines}


## Fiche d'un entraînement pour la carte de détail (lot « présentation des menus », étape 2) : nom,
## durée, nombre de blocs, intensité maximale (en % de FTP, en watts pour un fichier en watts quand la
## FTP est connue), blocs du profil ([durée, début, fin] en fraction de FTP, contrat 1.1) à dessiner.
static func workout_sheet(item: Dictionary, ftp_w := 0.0) -> Dictionary:
	var tiles: Array = []
	var lines: Array = []
	var blocks: Array = item.get("profile", []) if item.get("profile") is Array else []
	var err = item.get("error", null)
	if err != null and str(err) != "":
		lines.append(str(err))
	else:
		tiles.append(_tile("Durée", _format_fr_duration(float(item.get("duration_s", 0.0))), ""))
		tiles.append(_tile("Blocs", str(int(item.get("block_count", blocks.size()))), ""))
		var top := 0.0
		for b in blocks:
			if b is Array and b.size() >= 3:
				top = maxf(top, maxf(float(b[1]) if b[1] != null else 0.0, float(b[2]) if b[2] != null else 0.0))
		var watts := str(item.get("unit", "ftp")) == "watts"
		if top > 0.0 and watts and ftp_w > 0.0:
			tiles.append(_tile("Puissance max", str(int(round(top * ftp_w))), "W"))
		elif top > 0.0:
			tiles.append(_tile("Intensité max", str(int(round(top * 100.0))), "% FTP"))
		if watts:
			lines.append("Fichier en watts fixes : cibles gardées quelle que soit la FTP")
		if item.get("profile_truncated", false):
			lines.append("Profil coupé : %d premiers blocs dessinés" % blocks.size())
	return {"title": "Entraînement", "id": str(item.get("id", "")), "name": str(item.get("name", item.get("id", ""))),
		"tiles": tiles, "lines": lines, "blocks": blocks}


## Test de FTP : mêmes blocs que le core (ftp_test.py : rampe de 20 W par minute depuis 100 W jusqu'au
## palier FTP / 0,75, puis retour au calme ; le test de 20 minutes est retiré au lot O19).
const FTP_REF_W := 250.0           # FTP de référence sans FTP connue (DEFAULT_PLAN_FTP_W du core)
const RAMP_START_W := 100.0
const RAMP_STEP_W := 20.0
const RAMP_STEP_S := 60.0
const RAMP_WARMUP_S := 300.0
const RAMP_COOLDOWN_S := 300.0
const RAMP_FACTOR := 0.75


## Blocs [durée, début, fin] de la rampe du test de FTP en fraction de la FTP (`kind` : `ramp`, seul test).
static func ftp_test_blocks(kind: String, ftp_w: float) -> Array:
	if kind != "ramp":
		return []
	var ref := ftp_w if ftp_w > 0.0 else FTP_REF_W
	var last_w := maxf(ref / RAMP_FACTOR, RAMP_START_W)
	var out: Array = [[RAMP_WARMUP_S, 0.6 * RAMP_START_W / ref, RAMP_START_W / ref]]
	var w := RAMP_START_W
	while w <= last_w:
		out.append([RAMP_STEP_S, w / ref, w / ref])
		w += RAMP_STEP_W
	out.append([RAMP_COOLDOWN_S, RAMP_START_W / ref, RAMP_START_W / ref])
	return out


static func blocks_duration(blocks: Array) -> float:
	var total := 0.0
	for b in blocks:
		total += float(b[0])
	return total


## Fiche d'un test de FTP (écran « Test de FTP ») : durée, FTP actuelle, part retenue, blocs, explication.
static func ftp_test_sheet(kind: String, name: String, how: String, ftp_w: float) -> Dictionary:
	var blocks := ftp_test_blocks(kind, ftp_w)
	return {"title": "Test de FTP", "name": name, "blocks": blocks, "lines": [how],
		"tiles": [_tile("Durée", _format_fr_duration(blocks_duration(blocks)), ""),
			_tile("FTP actuelle", str(int(round(ftp_w))) if ftp_w > 0.0 else "—", "W" if ftp_w > 0.0 else ""),
			_tile("Retenu", str(int(RAMP_FACTOR * 100.0)), "%")]}


## Fiche d'un plan de la liste (`plans.items`) ; `active` : plan en cours de la réponse (ou null).
static func plan_sheet(plan: Dictionary, active) -> Dictionary:
	var tiles: Array = [_tile("Semaines", str(int(plan.get("weeks", 0))), ""),
		_tile("Séances", str(int(plan.get("sessions", 0))), "")]
	var lines: Array = []
	if plan.get("error", null) != null:
		lines.append(str(plan["error"]))
	if active is Dictionary and str(active.get("id", "")) == str(plan.get("id", "")):
		tiles.append(_tile("Fait", str(int(round(float(active.get("done_pct", 0.0))))), "%"))
		lines.append("En cours : " + active_progress(active))
	return {"title": "Plan", "name": str(plan.get("name", plan.get("id", ""))), "tiles": tiles, "lines": lines}


## Fiche du plan en cours : semaine, part faite, séances faites.
static func active_plan_sheet(active: Dictionary) -> Dictionary:
	var week := "%s / %d" % [str(active["week"]) if active.get("week", null) != null else "–", int(active.get("weeks", 0))]
	return {"title": "Plan en cours", "name": str(active.get("name", "")), "lines": [active_progress(active)],
		"tiles": [_tile("Semaine", week, ""), _tile("Fait", str(int(round(float(active.get("done_pct", 0.0))))), "%"),
			_tile("Séances", "%d / %d" % [int(active.get("done", 0)), int(active.get("total", 0))], "")]}


static func active_progress(active: Dictionary) -> String:
	if active.get("finished", false):
		return "terminé, %d %% fait" % int(round(float(active.get("done_pct", 0.0))))
	return "semaine %s / %d, %d %% fait (%d / %d)" % [str(active["week"]) if active.get("week", null) != null else "–",
		int(active.get("weeks", 0)), int(round(float(active.get("done_pct", 0.0)))), int(active.get("done", 0)), int(active.get("total", 0))]


## Fiche de la séance du jour d'un plan : durée, TSS, date, retard ; `blocks` : profil de la séance si connu.
static func plan_day_sheet(day: Dictionary, blocks: Array) -> Dictionary:
	var tiles: Array = [_tile("Durée", _format_fr_duration(float(day.get("duration_s", 0.0))), "")]
	if day.get("tss", null) != null:
		tiles.append(_tile("TSS", str(int(round(float(day["tss"])))), ""))
	var lines: Array = [str(day.get("date", ""))]
	if day.get("late", false):
		lines.append("En retard : à rattraper")
	return {"title": "Séance du jour", "name": str(day.get("name", "")), "tiles": tiles, "lines": lines, "blocks": blocks}


## Fiche de la pause (lot N20 §4.3) : chiffres de la séance en cours. `elapsed_s` et `distance_m` NAN ou négatifs :
## tuile « — » ; `avg_w` < 0 : pas encore de mesure de puissance.
static func pause_sheet(elapsed_s: float, distance_m: float, avg_w: float) -> Dictionary:
	var has_t := is_finite(elapsed_s) and elapsed_s >= 0.0
	var has_d := is_finite(distance_m) and distance_m >= 0.0
	var h := int(elapsed_s) / 3600 if has_t else 0
	var time_text := "—"
	if has_t:
		time_text = "%d:%02d:%02d" % [h, (int(elapsed_s) / 60) % 60, int(elapsed_s) % 60] if h > 0 else "%d:%02d" % [int(elapsed_s) / 60, int(elapsed_s) % 60]
	return {"title": "Séance en cours", "name": "En pause",
		"tiles": [_tile("Durée", time_text, ""),
			_tile("Distance", _format_fr_1(distance_m / 1000.0) if has_d else "—", "km" if has_d else ""),
			_tile("Puissance moy.", str(int(round(avg_w))) if avg_w >= 0.0 else "—", "W" if avg_w >= 0.0 else "")]}


static func _tile(label: String, value: String, unit: String) -> Dictionary:
	return {"label": label, "value": value, "unit": unit}


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
