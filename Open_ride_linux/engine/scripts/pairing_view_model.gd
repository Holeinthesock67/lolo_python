extends RefCounted

## Écran « Appareils » du menu (Lot N13, contrat IPC révision 1.2), sans nœud : recherche des appareils,
## choix du trainer et de la ceinture, identification du boîtier « + » du Click, enregistrement.
## Oublier un appareil (lot O24, révision 1.5) : le trainer et la ceinture passent aussi par « aucun »
## dans leur cycle, « Oublier le Click » retire les deux boîtiers ; `pair_devices` reçoit alors "".
##
## Le core cherche et écrit (`scan_devices`, `identify_click_plus`, `pair_devices`) ; ce modèle garde le
## dernier `scan_results`, les choix en cours et une ligne d'état, et fabrique les éléments de l'écran.
## `handle(id)` renvoie l'action à exécuter par l'appelant (menu_flow.gd) :
##   {"action": "scan_devices"}, {"action": "identify_click_plus"},
##   {"action": "confirm_pair", "title": …, "args": {trainer, click_plus, click_minus, hr}},
##   {"action": "relaunch"} (nouvelle configuration prise au prochain lancement), {"action": "back"}.
## Pas de class_name : charger par preload("res://scripts/pairing_view_model.gd").

const SCREEN := "pairing"
const ROLES := ["trainer", "click_plus", "click_minus", "hr"]
## Choix « aucun » d'un rôle : l'appareil enregistré est oublié (lot O24).
const FORGET := ""

## Derniers appareils trouvés : [{role, name, address, rssi, configured}].
var items: Array = []
var scanning := false
var scanned := false
var identifying := false
## request_cmd_id attendu pour la fin de l'identification du « + » (0 : celui de n'importe quelle réponse).
var identify_cmd_id := 0
## Adresses choisies par rôle (null : rien de choisi, la valeur de config.toml reste ; FORGET : oublié).
var choice := {"trainer": null, "click_plus": null, "click_minus": null, "hr": null}
## Adresses déjà dans config.toml, d'après `configured` des éléments trouvés.
var configured := {"trainer": null, "click_plus": null, "click_minus": null, "hr": null}
var message := ""
## Le message est une erreur (affiché en couleur d'erreur).
var message_error := false
var saved := false
var _pair_failed := false


func reset() -> void:
	scanning = false
	identifying = false
	message = ""
	message_error = false
	saved = false


func _of_role(role: String) -> Array:
	return items.filter(func(it): return it is Dictionary and str(it.get("role", "")) == role)


func _name_of(address) -> String:
	if address == null or str(address) == FORGET:
		return ""
	for it in items:
		if it is Dictionary and str(it.get("address", "")) == str(address):
			var n := str(it.get("name", ""))
			return n if n != "" else str(address)
	return str(address)


## Message `scan_results` reçu (recherche en cours, terminée, ou fin de l'identification du « + »).
func on_scan_results(msg: Dictionary) -> void:
	message_error = false
	var raw = msg.get("items", [])
	items = raw if raw is Array else []
	var done := bool(msg.get("done", false))
	if done:
		scanned = true
	if identifying and done and (identify_cmd_id == 0 or int(msg.get("request_cmd_id", -1)) == identify_cmd_id):
		identifying = false
		var plus = msg.get("plus_address", null)
		if plus == null:
			message = "Aucun appui sur « + » reçu : réessayer"
		else:
			choice["click_plus"] = str(plus)
			choice["click_minus"] = null
			for it in _of_role("click"):
				if str(it.get("address", "")) != str(plus):
					choice["click_minus"] = str(it["address"])
					break
			message = "Boîtier « + » reconnu"
		return
	scanning = not done
	for role in ["trainer", "hr"]:
		var found := _of_role("trainer" if role == "trainer" else "hr_strap")
		for it in found:
			if bool(it.get("configured", false)):
				configured[role] = str(it["address"])
		if choice[role] == null and not found.is_empty():
			choice[role] = configured[role] if configured[role] != null else str(found[0]["address"])
	if done:
		message = "%d appareil(s) trouvé(s)" % items.size() if not items.is_empty() else "Aucun appareil trouvé"


## Erreur du core pendant l'écran (codes busy, scan_failed, pairing_failed).
func on_error(code: String, text: String) -> void:
	message_error = true
	match code:
		"scan_failed", "busy":
			scanning = false
			identifying = false
			message = text
		"pairing_failed":
			_pair_failed = true
			saved = false
			message = "Enregistrement refusé : " + text


## Accusé de `pair_devices` : enregistré, sauf si le core a répondu par une erreur avant.
func on_pair_acked() -> void:
	if not _pair_failed:
		saved = true
		message_error = false
		for role in ROLES:
			if choice[role] != null:
				configured[role] = choice[role]
		message = "Enregistré : relancer OpenRide pour utiliser ces appareils"


func changes() -> Dictionary:
	var out := {}
	for role in ROLES:
		out[role] = choice[role] if choice[role] != null and choice[role] != configured[role] else null
	return out


func has_changes() -> bool:
	return changes().values().any(func(v): return v != null)


func menu_items() -> Array:
	var out: Array = []
	out.append({"id": "scan", "label": "Recherche en cours…" if scanning else "Rechercher les appareils",
		"enabled": not scanning and not identifying})
	var trainers := _of_role("trainer")
	out.append({"id": "trainer", "label": "Trainer", "detail": _choice_text("trainer", "aucun"),
		"enabled": (not trainers.is_empty() or choice["trainer"] != null) and not scanning and not identifying})
	var clicks := _of_role("click")
	var click_label := "Click : identifier le bouton +"
	if identifying:
		click_label = "Appuyez sur « + » du Click…"
	elif choice["click_plus"] != null:
		click_label = "Click : + reconnu" + ("" if choice["click_minus"] == null else ", − trouvé")
	out.append({"id": "identify", "label": click_label, "enabled": not clicks.is_empty() and not identifying and not scanning})
	out.append({"id": "forget_click", "label": "Oublier le Click",
		"detail": "à l'enregistrement" if choice["click_plus"] == FORGET else "",
		"enabled": choice["click_plus"] != FORGET and not scanning and not identifying})
	var straps := _of_role("hr_strap")
	out.append({"id": "hr", "label": "Ceinture", "detail": _choice_text("hr", "aucune"),
		"enabled": (not straps.is_empty() or choice["hr"] != null) and not scanning and not identifying})
	out.append({"id": "save", "label": "Enregistrer", "enabled": has_changes() and not scanning and not identifying})
	if saved:
		out.append({"id": "relaunch", "label": "Relancer OpenRide maintenant"})
	out.append({"id": "back", "label": "Retour"})
	return out


## Texte du choix d'un rôle : nom de l'appareil, `none` (« aucun ») sans choix ni appareil, ou oubli.
func _choice_text(role: String, none: String) -> String:
	var c = choice[role]
	if c == null:
		return none
	if str(c) == FORGET:
		return none + (" (oublié)" if role == "trainer" else " (oubliée)") if configured[role] != FORGET else none
	return _name_of(c)


## Barres de force du signal (dBm) : 4 au-dessus de −55, 3 jusqu'à −65, 2 jusqu'à −75, 1 en dessous.
static func signal_bars(rssi) -> int:
	if rssi == null:
		return 0
	var r := float(rssi)
	return 4 if r >= -55.0 else (3 if r >= -65.0 else (2 if r >= -75.0 else 1))


## Fiche de l'élément sous le focus pour la carte de détail ({} : pas de carte) : appareil choisi (nom,
## signal, déjà enregistré ou non) pour Trainer et Ceinture, consigne pour le Click, ce qui sera écrit
## pour Enregistrer.
func sheet(item_id: String) -> Dictionary:
	if item_id in ["trainer", "hr"]:
		var scan_role := "trainer" if item_id == "trainer" else "hr_strap"
		var found := _of_role(scan_role)
		var address = choice[item_id]
		var dev := {}
		for it in found:
			if str(it.get("address", "")) == str(address):
				dev = it
		var lines: Array = []
		if address != null and str(address) == FORGET:
			lines.append("Enregistrer oublie l'appareil" + (" : OpenRide cherchera un trainer par son nom" if item_id == "trainer" else " : plus de ceinture cardio"))
		if not found.is_empty():
			var pl := "s" if found.size() > 1 else ""
			lines.append("%d appareil%s trouvé%s, puis « aucun » : valider pour passer au suivant" % [found.size(), pl, pl])
		else:
			lines.append("Aucun appareil trouvé : lancer la recherche")
		var tiles: Array = []
		if not dev.is_empty():
			tiles.append({"label": "Signal", "value": "%d / 4" % signal_bars(dev.get("rssi", null)), "unit": ""})
			tiles.append({"label": "Enregistré", "value": "oui" if str(address) == str(configured[item_id]) else "non", "unit": ""})
		return {"title": "Trainer" if item_id == "trainer" else "Ceinture cardio",
			"name": _name_of(address) if address != null else "", "tiles": tiles, "lines": lines}
	if item_id == "identify":
		return {"title": "Click", "name": "Reconnaître le boîtier +",
			"lines": ["Appuyez sur « + » du Click dans les 15 s : l'autre boîtier est déduit de la recherche"]}
	if item_id == "forget_click":
		return {"title": "Click", "name": "Oublier les deux boîtiers",
			"lines": ["Enregistrer retire les boîtiers « + » et « − » ; le clavier reste utilisable"]}
	if item_id == "save":
		return {"title": "Enregistrement", "name": "Changements à écrire",
			"lines": ["Écrits dans ~/OpenRide/config.toml ; relancer OpenRide ensuite"] if has_changes() else ["Rien à enregistrer"]}
	return {}


## Appareil suivant du rôle : les appareils trouvés, puis « aucun » (FORGET), puis le premier à nouveau.
func _cycle(role: String, scan_role: String) -> void:
	var options: Array = []
	for it in _of_role(scan_role):
		options.append(str(it["address"]))
	options.append(FORGET)
	var idx := options.find(str(choice[role])) if choice[role] != null else -1
	choice[role] = options[(idx + 1) % options.size()]


func handle(item_id: String) -> Dictionary:
	match item_id:
		"scan":
			scanning = true
			message = ""
			message_error = false
			return {"action": "scan_devices"}
		"trainer":
			_cycle("trainer", "trainer")
		"hr":
			_cycle("hr", "hr_strap")
		"forget_click":
			choice["click_plus"] = FORGET
			choice["click_minus"] = FORGET
		"identify":
			identifying = true
			identify_cmd_id = 0
			message = "Appuyez sur « + » du Click dans les 15 s"
			return {"action": "identify_click_plus"}
		"save":
			var c := changes()
			var parts: Array[String] = []
			if c["trainer"] != null:
				parts.append("l'oubli du trainer" if c["trainer"] == FORGET else "trainer " + _name_of(c["trainer"]))
			if c["click_plus"] == FORGET:
				parts.append("l'oubli du Click")
			elif c["click_plus"] != null or c["click_minus"] != null:
				parts.append("Click")
			if c["hr"] != null:
				parts.append("l'oubli de la ceinture" if c["hr"] == FORGET else "ceinture " + _name_of(c["hr"]))
			_pair_failed = false
			return {"action": "confirm_pair", "title": "Enregistrer %s ?" % ", ".join(parts), "args": c}
		"relaunch":
			return {"action": "relaunch"}
		"back":
			return {"action": "back"}
	return {}
