extends RefCounted

## Menu « Garage » sans affichage (lot V8, contrat IPC 1.4 §5) : écrans Vélo, Tenue et Avatar, fiche de
## chaque pièce, achat avec confirmation, réglages de l'avatar en brouillon (Enregistrer / Annuler), en-tête
## niveau, expérience et pièces, aperçu et conseil du parcours.
##
## - Données : `hello_ack.config.progression` (niveau, expérience, pièces, pièces choisies, avatar), le
##   message `garage` (une ligne par pièce du catalogue : état, niveau, prix, défi, masse, CdA, terrain,
##   `look`) et le message `progression` qui suit chaque réussite. Core sans `progression` : pas de Garage.
## - Pièces : listées par emplacement, de la plus basse à la plus haute en niveau. Valider une pièce
##   possédée envoie `equip` ; achetable : confirmation « Acheter … pour N pièces ? Solde après : M », puis
##   `buy` ; verrouillée ou déjà choisie : une ligne d'explication, rien n'est envoyé.
## - Avatar : une ligne par réglage (menu_flow.gd ouvre l'écran de modification commun, + / − pour changer,
##   appui long + pour valider) ; le brouillon n'est envoyé (`set_avatar`) que par « Enregistrer », et
##   « Annuler » rend les valeurs enregistrées. L'aperçu 3D montre le brouillon.
## - Aperçu : l'équipement choisi, avec la pièce sous le focus à la place de celle de son emplacement.
## - Conseil du parcours : même règle que le core (equipment.py advice), limitée aux pièces possédées :
##   cadre et roues du terrain du parcours (`routes[].terrain`), sinon la pièce « tout terrain ».
## Pas de class_name : charger par preload("res://scripts/garage_view_model.gd").

const AvatarModel := preload("res://scripts/avatar_model.gd")
const EquipmentMeshes := preload("res://scripts/equipment_meshes.gd")

const SCREEN := "garage"
const BIKE := "garage_bike"
const OUTFIT := "garage_outfit"
const AVATAR := "garage_avatar"
const SCREENS := [SCREEN, BIKE, OUTFIT, AVATAR]
## Préfixe des clés de l'écran de modification (settings_view_model.gd) : « garage.skin »…
const KEY_PREFIX := "garage."

const GROUPS := {BIKE: ["frame", "wheels"], OUTFIT: ["kit", "helmet", "socks", "glasses"]}
const SLOT_NAMES := {"frame": "Cadre", "wheels": "Roues", "helmet": "Casque", "kit": "Tenue",
	"socks": "Chaussettes", "glasses": "Lunettes"}
const TERRAIN_NAMES := {"flat": "plat", "rolling": "vallonné", "climb": "col", "all": "tout terrain"}
const ROUTE_TERRAIN_NAMES := {"flat": "plat", "rolling": "vallonné", "climb": "avec col"}
const HEIGHT_NAMES := {"S": "petite", "M": "moyenne", "L": "grande", "XL": "très grande"}
const BUILD_NAMES := {"slim": "fine", "medium": "moyenne", "strong": "forte"}

## Réglages de l'avatar dans l'ordre de l'écran : {clé, libellé, valeurs}. `values` : liste fermée (le
## réglage vaut l'une d'elles) ; sinon entier de 0 à `max`.
const AVATAR_FIELDS := [
	{"key": "height", "label": "Taille", "values": ["S", "M", "L", "XL"]},
	{"key": "build", "label": "Silhouette", "values": ["slim", "medium", "strong"]},
	{"key": "skin", "label": "Teint", "max": AvatarModel.SKIN_MAX},
	{"key": "hair", "label": "Coiffure", "max": AvatarModel.HAIR_MAX},
	{"key": "hair_color", "label": "Couleur des cheveux", "max": AvatarModel.HAIR_COLOR_MAX},
	{"key": "kit_primary", "label": "Couleur principale de la tenue", "max": AvatarModel.KIT_MAX},
	{"key": "kit_secondary", "label": "Couleur secondaire de la tenue", "max": AvatarModel.KIT_MAX},
	{"key": "number", "label": "Numéro de dossard", "max": AvatarModel.NUMBER_MAX},
]
## Textes des refus du core (codes fermés du contrat 1.4).
const ERROR_TEXTS := {
	"item_locked": "Pièce verrouillée : niveau ou défi à atteindre",
	"not_enough_coins": "Pas assez de pièces",
	"avatar_invalid": "Avatar refusé par le core",
	"busy": "Impossible pendant une séance",
	"bad_args": "Demande refusée par le core",
}

var enabled := false
var items: Array = []
var level := 1
var xp := 0
var xp_next_level := 0
var coins := 0
var equipped: Dictionary = {}
var saved_avatar: Dictionary = AvatarModel.DEFAULTS.duplicate()
var draft_avatar: Dictionary = AvatarModel.DEFAULTS.duplicate()
## Ligne d'état des écrans du Garage (refus, pièce déjà choisie, enregistré).
var message := ""


## `progression` de hello_ack.config (absente ou vide : pas de Garage).
func on_hello(progression) -> void:
	enabled = progression is Dictionary and not progression.is_empty()
	items = []
	message = ""
	if enabled:
		_take(progression)
		draft_avatar = saved_avatar.duplicate()


## Message `progression` (après equip, buy, set_avatar) : niveau, expérience, pièces, choix, avatar.
func on_progression(msg: Dictionary) -> void:
	if not enabled:
		return
	var dirty_before := is_dirty()
	_take(msg)
	if not dirty_before:
		draft_avatar = saved_avatar.duplicate()


func _take(src: Dictionary) -> void:
	level = int(src.get("level", level))
	xp = int(src.get("xp", xp))
	xp_next_level = int(src.get("xp_next_level", xp_next_level))
	coins = int(src.get("coins", coins))
	if src.get("equipped") is Dictionary:
		equipped = src["equipped"].duplicate()
	if src.get("avatar") is Dictionary:
		saved_avatar = AvatarModel.parse_settings(src["avatar"])


## Message `garage` complet (parties réunies par ipc_client.gd).
func on_garage(list: Array) -> void:
	items = list.filter(func(it): return it is Dictionary and str(it.get("id", "")) != "")


func item(item_id: String) -> Dictionary:
	for it in items:
		if str(it["id"]) == item_id:
			return it
	return {}


## Pièces d'un emplacement, de la plus basse à la plus haute en niveau (puis prix, puis identifiant).
func slot_items(slot: String) -> Array:
	var out := items.filter(func(it): return str(it.get("slot", "")) == slot)
	out.sort_custom(func(a, b):
		var ka := [int(a.get("level_required", 0)), int(a.get("price", 0)), str(a["id"])]
		var kb := [int(b.get("level_required", 0)), int(b.get("price", 0)), str(b["id"])]
		return ka < kb)
	return out


# --- écrans ---------------------------------------------------------------------------------------

## Éléments d'un écran du Garage : [{id, label, detail, enabled}].
func screen_items(screen: String) -> Array:
	match screen:
		SCREEN:
			return [
				{"id": "bike", "label": "Vélo : cadre et roues", "detail": _equipped_names(GROUPS[BIKE])},
				{"id": "outfit", "label": "Tenue, casque, chaussettes, lunettes", "detail": _equipped_names(GROUPS[OUTFIT])},
				{"id": "avatar", "label": "Avatar", "detail": _avatar_summary()}]
		BIKE, OUTFIT:
			var out := []
			for slot in GROUPS[screen]:
				for it in slot_items(slot):
					out.append({"id": "item:" + str(it["id"]), "label": "%s : %s" % [SLOT_NAMES[slot], it.get("name", it["id"])],
						"detail": state_text(it)})
			if out.is_empty():
				out.append({"id": "empty", "label": "Catalogue en cours de chargement…", "detail": "", "enabled": false})
			return out
		AVATAR:
			var out := []
			for f in AVATAR_FIELDS:
				out.append({"id": "field:" + str(f["key"]), "label": f["label"], "detail": format_field(str(f["key"]), draft_avatar[f["key"]])})
			out.append({"id": "save", "label": "Enregistrer", "detail": "", "enabled": is_dirty()})
			out.append({"id": "cancel", "label": "Annuler les changements", "detail": "", "enabled": is_dirty()})
			return out
	return []


func title(screen: String) -> String:
	match screen:
		SCREEN:
			return "Garage : niveau %d, %d pièces" % [level, coins]
		BIKE:
			return "Garage : vélo"
		OUTFIT:
			return "Garage : tenue"
		AVATAR:
			return "Garage : avatar"
	return "Garage"


func _equipped_names(slots: Array) -> String:
	var names: Array[String] = []
	for slot in slots:
		var it := item(str(equipped.get(slot, "")))
		if not it.is_empty():
			names.append(str(it.get("name", it["id"])))
	return ", ".join(names)


func _avatar_summary() -> String:
	return "taille %s · silhouette %s" % [HEIGHT_NAMES.get(draft_avatar["height"], "?"), BUILD_NAMES.get(draft_avatar["build"], "?")]


## Détail d'une ligne de pièce : « choisie », « possédée », « 150 pièces », « niveau 5 » ou « défi : … ».
func state_text(it: Dictionary) -> String:
	match str(it.get("state", "")):
		"equipped":
			return "choisie"
		"owned":
			return "possédée"
		"buyable":
			return "%d pièces" % int(it.get("price", 0))
	if it.get("challenge") != null and int(it.get("price", 0)) <= 0:
		return "défi : %s" % str(it["challenge"])
	if it.get("challenge") != null:
		return "niveau %d ou défi" % int(it.get("level_required", 0))
	return "niveau %d" % int(it.get("level_required", 0))


## Carte de détail de l'écran (detail_card.gd : title, name, tiles, lines), {} sans carte.
func sheet(screen: String, focused_id: String) -> Dictionary:
	if screen == SCREEN:
		var lines: Array = []
		if xp_next_level > 0:
			lines.append("Expérience %d / %d vers le niveau %d : %s" % [xp, xp_next_level, level + 1, bar(xp, xp_next_level)])
		if message != "":
			lines.append(message)
		return {"title": "Garage", "name": "Niveau %d" % level,
			"tiles": [_tile("Niveau", str(level), ""), _tile("Pièces", str(coins), ""),
				_tile("Expérience", str(xp), "/ %d" % xp_next_level if xp_next_level > 0 else "")],
			"lines": lines}
	if screen in GROUPS and focused_id.begins_with("item:"):
		return item_sheet(item(focused_id.substr(5)))
	if screen == AVATAR:
		return {"title": "Avatar", "name": "Ton cycliste",
			"lines": ["Taille %s, silhouette %s" % [HEIGHT_NAMES.get(draft_avatar["height"], "?"), BUILD_NAMES.get(draft_avatar["build"], "?")],
				"Rien n'est enregistré avant « Enregistrer »."] + ([message] if message != "" else [])}
	return {}


## Fiche d'une pièce : masse, CdA, niveau ou prix, terrain conseillé, défi.
func item_sheet(it: Dictionary) -> Dictionary:
	if it.is_empty():
		return {}
	var physical := str(it.get("slot", "")) in ["frame", "wheels"]
	var tiles: Array = []
	var lines: Array = []
	if physical:
		var mass := float(it.get("mass_delta_kg", 0.0))
		var cda := float(it.get("cda_delta_pct", 0.0))
		tiles.append(_tile("Masse", "=" if mass == 0.0 else signed(mass), "" if mass == 0.0 else "kg"))
		tiles.append(_tile("CdA", "=" if cda == 0.0 else signed(cda), "" if cda == 0.0 else "%"))
		lines.append("Conseillé : %s" % TERRAIN_NAMES.get(str(it.get("terrain", "all")), "tout terrain"))
	else:
		lines.append("Apparence seulement")
	tiles.append(_tile("Niveau", str(int(it.get("level_required", 0))), ""))
	var price := int(it.get("price", 0))
	if price > 0:
		tiles.append(_tile("Prix", str(price), "pièces"))
	var state := str(it.get("state", ""))
	lines.append("État : " + state_text(it) if state != "locked" else "Verrouillée : " + state_text(it))
	if it.get("challenge") != null and state != "buyable":
		lines.append("Défi : %s" % str(it["challenge"]))
	if message != "":
		lines.append(message)
	return {"title": SLOT_NAMES.get(str(it.get("slot", "")), ""), "name": str(it.get("name", it["id"])),
		"tiles": tiles.slice(0, 3), "lines": lines}


static func _tile(label: String, value: String, unit: String) -> Dictionary:
	return {"label": label, "value": value, "unit": unit}


## « −1,5 », « +0,5 » : signe typographique, virgule décimale, une décimale.
static func signed(x: float) -> String:
	var s := ("%.1f" % absf(x)).replace(".", ",")
	return ("+" if x > 0.0 else "−") + s


## Barre de dix cases pleines jusqu'à value / total.
static func bar(value: int, total: int) -> String:
	var n := clampi(int(round(10.0 * float(value) / float(maxi(total, 1)))), 0, 10)
	return "■".repeat(n) + "□".repeat(10 - n)


# --- pièces : validation et achat -----------------------------------------------------------

## Valider une ligne de pièce (« item:id »). Renvoie {} (message mis à jour), {"action": "equip", slot,
## item_id} ou {"action": "confirm_buy", title, item_id}.
func activate(item_id: String) -> Dictionary:
	var it := item(item_id.substr(5)) if item_id.begins_with("item:") else {}
	message = ""
	if it.is_empty():
		return {}
	match str(it.get("state", "")):
		"equipped":
			message = "« %s » est déjà choisie" % it.get("name", it["id"])
		"owned":
			return {"action": "equip", "slot": str(it["slot"]), "item_id": str(it["id"])}
		"buyable":
			var price := int(it.get("price", 0))
			if price > coins:
				message = ERROR_TEXTS["not_enough_coins"] + " : %d manquantes" % (price - coins)
			else:
				return {"action": "confirm_buy", "title": "Acheter %s pour %d pièces ? Solde après : %d" % [it.get("name", it["id"]), price, coins - price],
					"item_id": str(it["id"])}
		_:
			message = "Verrouillée : " + state_text(it)
	return {}


## Texte français d'un refus du core (`error.code` du contrat, ou ERROR_TEXTS) pour la ligne d'état.
func on_error(code: String, text: String) -> bool:
	if not ERROR_TEXTS.has(code):
		return false
	message = ERROR_TEXTS[code] if text == "" else "%s : %s" % [ERROR_TEXTS[code], text]
	return true


# --- avatar ---------------------------------------------------------------------------------------

func is_dirty() -> bool:
	for f in AVATAR_FIELDS:
		if draft_avatar[f["key"]] != saved_avatar[f["key"]]:
			return true
	return false


static func field(key: String) -> Dictionary:
	for f in AVATAR_FIELDS:
		if f["key"] == key:
			return f
	return {}


## Texte d'une valeur de réglage : « moyenne », « teint 4 / 8 », « n° 27 »…
static func format_field(key: String, value) -> String:
	match key:
		"height":
			return str(HEIGHT_NAMES.get(str(value), value))
		"build":
			return str(BUILD_NAMES.get(str(value), value))
		"number":
			return "aucun" if int(value) == 0 else "n° %d" % int(value)
		"hair":
			return "chauve" if int(value) == 0 else "coiffure %d / %d" % [int(value), AvatarModel.HAIR_MAX]
	var f := field(key)
	return "%d / %d" % [int(value) + 1, int(f.get("max", 0)) + 1]


## Élément de l'écran de modification (settings_view_model.gd begin_with) pour un réglage : indice dans la
## liste fermée ou entier ; `format` laisse settings_view_model.gd demander le texte à format_field().
func edit_item(key: String) -> Dictionary:
	var f := field(key)
	if f.is_empty():
		return {}
	var values: Array = f.get("values", [])
	var hi := values.size() - 1 if not values.is_empty() else int(f["max"])
	var cur: int = values.find(draft_avatar[key]) if not values.is_empty() else int(draft_avatar[key])
	return {"key": KEY_PREFIX + key, "label": f["label"], "type": "int", "value": maxi(cur, 0), "min": 0, "max": hi,
		"step": 1, "unit": "", "format": "garage"}


## Valeur validée dans l'écran de modification : met à jour le brouillon.
func set_field(key: String, value: int) -> void:
	var f := field(key)
	if f.is_empty():
		return
	var values: Array = f.get("values", [])
	draft_avatar[key] = values[clampi(value, 0, values.size() - 1)] if not values.is_empty() else clampi(value, 0, int(f["max"]))
	message = ""


## Texte d'une valeur de l'écran de modification (valeur brute : indice de la liste fermée ou entier).
static func format_edit(key: String, raw: int) -> String:
	var f := field(key.substr(KEY_PREFIX.length()))
	var values: Array = f.get("values", [])
	return format_field(str(f["key"]), values[clampi(raw, 0, values.size() - 1)] if not values.is_empty() else raw)


## « Enregistrer » : {"action": "set_avatar", avatar} (réglages de contrat, sans les seuils de danseuse).
func save() -> Dictionary:
	if not is_dirty():
		return {}
	var avatar := {}
	for f in AVATAR_FIELDS:
		avatar[f["key"]] = draft_avatar[f["key"]]
	message = ""
	return {"action": "set_avatar", "avatar": avatar}


## « Annuler » : rend les valeurs enregistrées.
func cancel() -> void:
	draft_avatar = saved_avatar.duplicate()
	message = "Changements annulés"


# --- aperçu 3D et conseil du parcours ----------------------------------------------------------

## `look` de chaque identifiant du catalogue.
func look_map() -> Dictionary:
	var out := {}
	for it in items:
		out[str(it["id"])] = it.get("look")
	return out


## Aperçu : {settings, looks}. La pièce sous le focus remplace celle de son emplacement.
func preview(screen: String, focused_id: String, edit: Dictionary = {}) -> Dictionary:
	var shown := equipped.duplicate()
	if screen in GROUPS and focused_id.begins_with("item:"):
		var it := item(focused_id.substr(5))
		if not it.is_empty():
			shown[str(it["slot"])] = str(it["id"])
	var settings := draft_avatar.duplicate()
	if str(edit.get("key", "")).begins_with(KEY_PREFIX):
		var key := str(edit["key"]).substr(KEY_PREFIX.length())
		var f := field(key)
		if not f.is_empty():
			var values: Array = f.get("values", [])
			settings[key] = values[clampi(int(edit["value"]), 0, values.size() - 1)] if not values.is_empty() else int(edit["value"])
	return {"settings": AvatarModel.parse_settings(settings), "looks": EquipmentMeshes.equip_looks(shown, look_map())}


## Conseil de l'écran Prêt, "" sans conseil : « Parcours vallonné : conseillé Polyvalent léger, Profilées »
## quand le cadre ou les roues choisis ne sont pas ceux du terrain (pièces possédées seulement).
func route_advice(terrain) -> String:
	if not enabled or not (terrain is String) or not ROUTE_TERRAIN_NAMES.has(terrain) or items.is_empty():
		return ""
	var names: Array[String] = []
	var differs := false
	for slot in ["frame", "wheels"]:
		var best := _advised(slot, terrain)
		if best.is_empty():
			continue
		names.append(str(best.get("name", best["id"])))
		if str(best["id"]) != str(equipped.get(slot, "")):
			differs = true
	if not differs or names.is_empty():
		return ""
	return "Parcours %s : conseillé %s" % [ROUTE_TERRAIN_NAMES[terrain], ", ".join(names)]


func _advised(slot: String, terrain: String) -> Dictionary:
	var owned := slot_items(slot).filter(func(it): return str(it.get("state", "")) in ["owned", "equipped"])
	for want in [terrain, "all"]:
		var matching := owned.filter(func(it): return str(it.get("terrain", "all")) == want)
		if not matching.is_empty():
			return matching[-1]
	return {}
