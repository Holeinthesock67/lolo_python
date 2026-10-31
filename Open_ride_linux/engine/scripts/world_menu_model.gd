extends RefCounted

## Menu « Monde ouvert » sans affichage (lot W11, plan §2.1) : globe → carte → cap et navigation →
## préchargement. `handle(événement)` prend les événements du menu (`menu_model.gd`, Click ou clavier) et
## renvoie l'action à faire : {} (rien), {action: "world_search" | "world_map" | "world_pin" |
## "start_open_world" | "close", ...}. Les réponses du core arrivent par `on_places`, `on_map`, `on_regions`,
## `on_status`. Pas de class_name (charger par preload).
##
## Touches : globe — gauche et droite (ou − et +) tournent, appui long sur + ou − incline, A valide le centre
## du globe, appui long sur A épingle la région sous le centre, Z (ou taper un nom) ouvre la recherche, Y ferme.
## Recherche (lot O31) — saisie partagée (text_entry.gd) : + et − changent de case, maintenus de ligne, Z
## écrit, Y efface (texte vide : retour), A maintenu passe aux résultats ; résultats — − et + choisissent,
## A valide, Z revient à la grille, Y quitte la recherche. Au clavier, on tape le nom et la liste garde la main. Carte — gauche, droite, − (nord) et + (sud) déplacent le curseur
## de 100 m (appui long : 500 m), accroché à la route la plus proche, A valide. Cap — − et + changent de ligne
## (cap, navigation, longueur), gauche et droite changent la valeur, A démarre. Y revient d'un écran.

const TextEntry := preload("res://scripts/text_entry.gd")
const QUERY_MAX := 40

const GLOBE := "globe"
const SEARCH := "search"
const MAP := "map"
const SETUP := "setup"
const LOADING := "loading"

const ROTATE_STEP_DEG := 10.0
const TILT_STEP_DEG := 10.0
const MAX_TILT_DEG := 80.0
const CURSOR_STEP_M := 100.0
const CURSOR_LONG_STEP_M := 500.0
const MAP_RADIUS_M := 8000.0
const HEADING_STEP_DEG := 15.0
const LOOP_STEP_KM := 5.0
const LOOP_MIN_KM := 5.0
const LOOP_MAX_KM := 200.0
const M_PER_DEG := 111320.0
const NAVS := ["ride", "destination", "loop"]
const NAV_LABELS := {"ride": "Balade", "destination": "Destination", "loop": "Boucle"}
const FIELDS := ["heading", "nav", "extra"]
const ATTRIBUTIONS := "© OpenStreetMap, OpenMapTiles, Copernicus, NASA, Natural Earth"

var state := GLOBE
## Centre du globe (degrés) et inclinaison.
var globe_lon := 6.0
var globe_lat := 45.0
## Recherche : texte saisi (`entry`, `query`), résultats (`places`), ligne choisie ; `typing` : la saisie a la
## main, sinon la liste des résultats ; `search_for_target` : la recherche choisit la destination.
var entry = TextEntry.new(QUERY_MAX, ["'"])
var query: String:
	get:
		return entry.text
	set(value):
		entry.text = value
var typing := true
var places: Array = []
var place_index := 0
var search_for_target := false
## Carte : centre demandé, routes reçues ({c, xz}), curseur en mètres depuis le centre (x est, z sud).
var map_lat := 0.0
var map_lon := 0.0
var roads: Array = []
var cursor := Vector2.ZERO
var map_ready := false
var _map_request := 0
## Cap et navigation.
var heading_deg := 0.0
var nav := "ride"
var loop_km := 30.0
var target: Variant = null
var field_index := 0
var seed_value := 0
## Régions du cache (`world_regions`) : {id, name, pinned, bbox}.
var regions: Array = []
## Préchargement (`world_status`).
var status: Dictionary = {}
var last_error := ""


func reset() -> void:
	state = GLOBE
	query = ""
	entry.cell = 0
	typing = true
	places = []
	place_index = 0
	search_for_target = false
	roads = []
	cursor = Vector2.ZERO
	map_ready = false
	nav = "ride"
	target = null
	field_index = 0
	status = {}
	last_error = ""


# --- événements ------------------------------------------------------------------------------

func handle(event: String) -> Dictionary:
	if event == "Y_SHORT" and state != SEARCH:
		return _back()
	match state:
		GLOBE:
			return _on_globe(event)
		SEARCH:
			return _on_search(event)
		MAP:
			return _on_map(event)
		SETUP:
			return _on_setup(event)
	return {}


func _back() -> Dictionary:
	match state:
		GLOBE:
			return {"action": "close"}
		SEARCH:
			state = SETUP if search_for_target else GLOBE
			search_for_target = false
		MAP:
			state = GLOBE
		SETUP:
			state = MAP
		LOADING:
			return {"action": "cancel_loading"}
	return {}


func _on_globe(event: String) -> Dictionary:
	match event:
		"LEFT_SHORT", "MINUS_SHORT":
			globe_lon = _wrap_lon(globe_lon - ROTATE_STEP_DEG)
		"RIGHT_SHORT", "PLUS_SHORT":
			globe_lon = _wrap_lon(globe_lon + ROTATE_STEP_DEG)
		"PLUS_LONG":
			globe_lat = clampf(globe_lat - TILT_STEP_DEG, -MAX_TILT_DEG, MAX_TILT_DEG)
		"MINUS_LONG":
			globe_lat = clampf(globe_lat + TILT_STEP_DEG, -MAX_TILT_DEG, MAX_TILT_DEG)
		"A_SHORT":
			return _open_map(globe_lat, globe_lon)
		"Z_SHORT":
			_open_search(false)
		"A_LONG":
			var r := region_at(globe_lat, globe_lon)
			if not r.is_empty():
				return {"action": "world_pin", "region_id": r["id"], "pinned": not bool(r.get("pinned", false))}
	return {}


func _open_search(for_target: bool) -> void:
	state = SEARCH
	search_for_target = for_target
	query = ""
	entry.cell = 0
	typing = true
	places = []
	place_index = 0


func _on_search(event: String) -> Dictionary:
	if typing:
		return _on_typing(event)
	match event:
		"Y_SHORT":
			return _back()
		"Z_SHORT":
			typing = true
		"MINUS_SHORT", "LEFT_SHORT":
			place_index = maxi(0, place_index - 1)
		"PLUS_SHORT", "RIGHT_SHORT":
			place_index = mini(maxi(0, places.size() - 1), place_index + 1)
		"A_SHORT", "A_LONG":
			if place_index < places.size():
				var p: Dictionary = places[place_index]
				if search_for_target:
					target = {"lat": float(p["lat"]), "lon": float(p["lon"])}
					search_for_target = false
					state = SETUP
					return {}
				globe_lat = float(p["lat"])
				globe_lon = float(p["lon"])
				return _open_map(globe_lat, globe_lon)
	return {}


## Saisie du nom au Click : comme le nom d'un profil (text_entry.gd) ; Valider passe aux résultats.
func _on_typing(event: String) -> Dictionary:
	match event:
		"PLUS_SHORT", "RIGHT_SHORT", "A_SHORT":
			entry.move(1)
		"MINUS_SHORT", "LEFT_SHORT":
			entry.move(-1)
		"PLUS_LONG", "MINUS_LONG":
			entry.move(TextEntry.GRID_COLUMNS * (1 if event == "PLUS_LONG" else -1))
		"Z_SHORT":
			match entry.press_cell(entry.cell_id()):
				TextEntry.VALIDATE:
					_show_results()
				"changed":
					return _search_action()
		"A_LONG":
			_show_results()
		"Y_SHORT":
			if entry.backspace():
				return _search_action()
			return _back()
	return {}


## Résultats : la liste prend la main s'il y en a.
func _show_results() -> void:
	if not places.is_empty():
		typing = false
		place_index = 0


func _on_map(event: String) -> Dictionary:
	var step := CURSOR_STEP_M
	match event:
		"LEFT_SHORT":
			cursor.x -= step
		"RIGHT_SHORT":
			cursor.x += step
		"MINUS_SHORT":
			cursor.y -= step
		"PLUS_SHORT":
			cursor.y += step
		"MINUS_LONG":
			cursor.y -= CURSOR_LONG_STEP_M
		"PLUS_LONG":
			cursor.y += CURSOR_LONG_STEP_M
		"A_SHORT", "A_LONG":
			if map_ready:
				state = SETUP
				field_index = 0
				return {}
	cursor = cursor.clamp(Vector2(-MAP_RADIUS_M, -MAP_RADIUS_M), Vector2(MAP_RADIUS_M, MAP_RADIUS_M))
	if event in ["LEFT_SHORT", "RIGHT_SHORT", "MINUS_SHORT", "PLUS_SHORT", "MINUS_LONG", "PLUS_LONG"]:
		cursor = snap_to_road(cursor)
	return {}


func _on_setup(event: String) -> Dictionary:
	match event:
		"MINUS_SHORT":
			field_index = (field_index + FIELDS.size() - 1) % FIELDS.size()
		"PLUS_SHORT":
			field_index = (field_index + 1) % FIELDS.size()
		"LEFT_SHORT":
			_change_field(-1)
		"RIGHT_SHORT":
			_change_field(1)
		"A_SHORT", "A_LONG":
			if nav == "destination" and target == null:
				_open_search(true)
				return {}
			return _start()
	return {}


func _change_field(direction: int) -> void:
	match FIELDS[field_index]:
		"heading":
			heading_deg = fposmod(heading_deg + direction * HEADING_STEP_DEG, 360.0)
		"nav":
			nav = NAVS[(NAVS.find(nav) + direction + NAVS.size()) % NAVS.size()]
		"extra":
			if nav == "loop":
				loop_km = clampf(loop_km + direction * LOOP_STEP_KM, LOOP_MIN_KM, LOOP_MAX_KM)
			elif nav == "destination":
				target = null           # nouvelle destination : A ouvre la recherche


## Saisie de texte (clavier) : sur le globe, ouvre la recherche ; en recherche, complète le nom.
func type_text(text: String) -> Dictionary:
	if state == GLOBE:
		_open_search(false)
	if state != SEARCH:
		return {}
	typing = false   # au clavier, la liste garde la main : − et + choisissent, A valide
	for ch in text:
		entry.type_text(ch)
	return _search_action()


func backspace() -> Dictionary:
	if state != SEARCH or not entry.backspace():
		return {}
	return _search_action()


func _search_action() -> Dictionary:
	if query.strip_edges().length() < 2:
		places = []
		return {}
	return {"action": "world_search", "query": query.strip_edges()}


func _open_map(lat: float, lon: float) -> Dictionary:
	state = MAP
	map_lat = lat
	map_lon = lon
	roads = []
	cursor = Vector2.ZERO
	map_ready = false
	return {"action": "world_map", "lat": lat, "lon": lon, "radius_m": MAP_RADIUS_M}


func _start() -> Dictionary:
	var lat := map_lat - cursor.y / M_PER_DEG
	var lon := map_lon + cursor.x / (M_PER_DEG * maxf(cos(deg_to_rad(map_lat)), 0.01))
	var args := {"lat": snappedf(lat, 1e-6), "lon": snappedf(lon, 1e-6), "heading_deg": int(heading_deg), "nav": nav,
		"seed": seed_value}
	if nav == "loop":
		args["loop_km"] = loop_km
	elif nav == "destination":
		args["target"] = target
	state = LOADING
	status = {}
	return {"action": "start_open_world", "args": args}


# --- réponses du core ------------------------------------------------------------------------

func on_places(items: Array) -> void:
	places = items
	place_index = 0


## Routes reçues (message `world_map` complet, parties déjà réunies).
func on_map(msg: Dictionary) -> void:
	if state != MAP:
		return
	roads = msg.get("roads", [])
	map_ready = true
	cursor = snap_to_road(Vector2.ZERO)


func on_regions(items: Array) -> void:
	regions = items


func on_status(msg: Dictionary) -> void:
	if state == LOADING:
		status = msg


## Le core a refusé le départ (`world_unavailable`, `bad_args`) : retour au réglage du cap avec le message.
func on_error(code: String, message: String) -> void:
	if state == LOADING:
		state = SETUP
		last_error = message if message != "" else code


## La séance est prête : le menu se ferme.
func is_loading() -> bool:
	return state == LOADING


# --- géométrie -------------------------------------------------------------------------------

static func _wrap_lon(lon: float) -> float:
	return fposmod(lon + 180.0, 360.0) - 180.0


## Point des routes le plus proche de `p` (mètres depuis le centre de la carte) ; `p` sans route.
func snap_to_road(p: Vector2) -> Vector2:
	var best := p
	var best_d := INF
	for road in roads:
		var xz: Array = road.get("xz", [])
		for i in range(0, xz.size() - 3, 2):
			var a := Vector2(xz[i], xz[i + 1])
			var b := Vector2(xz[i + 2], xz[i + 3])
			var q := Geometry2D.get_closest_point_to_segment(p, a, b)
			var d := p.distance_squared_to(q)
			if d < best_d:
				best_d = d
				best = q
	return best


## Région du cache dont la boîte [ouest, sud, est, nord] contient le point ; {} sinon.
func region_at(lat: float, lon: float) -> Dictionary:
	for r in regions:
		var b = r.get("bbox")
		if typeof(b) == TYPE_ARRAY and b.size() == 4 and b[0] <= lon and lon <= b[2] and b[1] <= lat and lat <= b[3]:
			return r
	return {}


## Latitude et longitude du curseur de la carte.
func cursor_latlon() -> Vector2:
	return Vector2(map_lat - cursor.y / M_PER_DEG,
		map_lon + cursor.x / (M_PER_DEG * maxf(cos(deg_to_rad(map_lat)), 0.01)))


## Ligne de l'écran de préchargement : « 12 Mo / 45 Mo », « 3 / 9 carrés » ou le message du générateur.
## Écran de l'aide des boutons (button_help.gd) : l'état, ou `search_results` quand la liste a la main.
func help_screen() -> String:
	return "search_results" if state == SEARCH and not typing else state


func loading_text() -> String:
	if status.is_empty():
		return "Préparation du monde…"
	var parts: Array = []
	var total = status.get("total_bytes")
	if total != null and float(total) > 0.0:
		parts.append("%.0f Mo / %.0f Mo" % [float(status.get("done_bytes", 0)) / 1e6, float(total) / 1e6])
	if int(status.get("squares_needed", 0)) > 0:
		parts.append("%d / %d carrés" % [int(status.get("squares_ready", 0)), int(status.get("squares_needed", 0))])
	var msg := str(status.get("message", ""))
	if msg != "":
		parts.append(msg)
	return " — ".join(parts) if not parts.is_empty() else "Préparation du monde…"


func loading_fraction() -> float:
	var total = status.get("total_bytes")
	if total != null and float(total) > 0.0:
		return clampf(float(status.get("done_bytes", 0)) / float(total), 0.0, 1.0)
	var need := int(status.get("squares_needed", 0))
	if need > 0:
		return clampf(float(status.get("squares_ready", 0)) / float(need), 0.0, 1.0)
	return 0.0
