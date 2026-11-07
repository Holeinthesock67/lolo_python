extends RefCounted

## Écrans de la collection de cartes (série BC, lot BC5, contrat IPC révision 1.6), sans nœud. Pas de
## class_name : charger par preload("res://scripts/collection_view_model.gd").
##
## Maquettes validées par le propriétaire le 7 novembre (lot BC3). Les calculs sont ceux du core (message
## `collection`, réponse à `list_collection`) :
## - ligne « Collection » de l'accueil : « 17 / 42 cartes », « · 2 nouvelles » s'il y en a ;
## - FIRST, première ouverture (`first_time`) : « n cartes déjà gagnées par vos séances passées », puis
##   l'album ; les cartes déjà gagnées sont notées vues (`collection_seen`), sans point « nouvelle » ;
## - SCREEN « Collection » (album) : une rangée par famille, une vignette par carte du catalogue (gagnée :
##   visuel et cadre de sa rareté ; à gagner : silhouette grise ; nouvelle : point orange) ;
## - CARD : la carte agrandie (titre, rareté, n° x / 42, ligne d'ambiance ; gagnée : date et « Voir la
##   séance » ; à gagner : avancement ; de saison : éditions gagnées). L'ouvrir envoie `collection_seen`.
## Les rangées de l'album sont les éléments du menu (un par carte, dans l'ordre du catalogue) : + et −
## passent d'une carte à la suivante, A l'agrandit, Y revient. La vue (collection_view.gd) dessine les
## vignettes à partir de album().

const SCREEN := "collection"
const CARD := "collection_card"
const FIRST := "collection_first"
const SCREENS := [SCREEN, CARD, FIRST]
const CARD_PREFIX := "c:"
const LOADING := "Chargement…"
## Familles du catalogue (core/src/openride_core/collection.py, FAMILIES), dans l'ordre de l'album.
const FAMILY_NAMES := {"distance": "Distance", "seance": "Séances", "denivele": "Dénivelé",
	"regularite": "Régularité", "heure": "Heure", "entrainement": "Entraînement", "modes": "Modes de jeu",
	"saison": "Saisons", "anniversaire": "Anniversaires"}
const RARITY_NAMES := {"commune": "Commune", "rare": "Rare", "epique": "Épique", "legendaire": "Légendaire"}
## Rangées de l'album visibles à la fois (maquette BC3 : trois familles).
const FAMILIES_SHOWN := 3
## Unité de l'avancement d'une carte à gagner, selon sa famille (les autres comptent des séances,
## des semaines ou des jours, dits par la ligne d'ambiance).
const UNITS := {"distance": " km", "denivele": " m", "anniversaire": " jours"}
const MONTHS := ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
	"octobre", "novembre", "décembre"]

var loaded := false
var first_time := false
var cards_count := 0
## Cartes du catalogue, dans l'ordre ({id, title, text, family, rarity, visual}).
var cards: Array = []
## Cartes gagnées, dans l'ordre chronologique (forme card_line : {id, key, edition, …, journal, date}).
var earned: Array = []
## Carte à gagner -> {value, target}.
var remaining: Dictionary = {}
## Clés des cartes gagnées pas encore vues.
var new_keys: Array = []
## Carte agrandie (écran CARD).
var card_id := ""
## Ligne d'état des écrans de la collection (chargement, erreur du core).
var message := ""


## Remet l'écran en attente de la réponse à `list_collection` (à chaque ouverture : une séance vient
## peut-être de finir).
func begin() -> void:
	loaded = false
	message = LOADING


func on_collection(msg: Dictionary) -> void:
	cards = _dicts(msg.get("cards"))
	earned = _dicts(msg.get("earned"))
	remaining = {}
	for r in _dicts(msg.get("remaining")):
		remaining[str(r.get("id", ""))] = r
	new_keys = []
	var raw_new = msg.get("new")
	if raw_new is Array:
		for k in raw_new:
			new_keys.append(str(k))
	first_time = bool(msg.get("first_time", false))
	cards_count = int(msg.get("cards_count", cards.size()))
	loaded = true
	message = ""


static func _dicts(raw) -> Array:
	var out: Array = []
	if raw is Array:
		for x in raw:
			if x is Dictionary:
				out.append(x)
	return out


func _card(id: String) -> Dictionary:
	var i := _index(id)
	return cards[i] if i >= 0 else {}


func _index(id: String) -> int:
	for i in range(cards.size()):
		if str(cards[i].get("id", "")) == id:
			return i
	return -1


## Éditions gagnées d'une carte (une seule, sauf une carte de saison gagnée plusieurs années).
func editions(id: String) -> Array:
	return earned.filter(func(e): return str(e.get("id", "")) == id)


func is_earned(id: String) -> bool:
	return not editions(id).is_empty()


func is_new(id: String) -> bool:
	for e in editions(id):
		if str(e.get("key", "")) in new_keys:
			return true
	return false


## Cartes distinctes gagnées (une carte de saison compte une fois, quelle que soit l'année).
func earned_count() -> int:
	var ids := {}
	for e in earned:
		ids[str(e.get("id", ""))] = true
	return ids.size()


func new_count() -> int:
	var ids := {}
	for e in earned:
		if str(e.get("key", "")) in new_keys:
			ids[str(e.get("id", ""))] = true
	return ids.size()


## Détail de la ligne « Collection » de l'accueil ("" avant la première réponse du core).
func home_detail() -> String:
	if not loaded:
		return ""
	var text := "%d / %d cartes" % [earned_count(), cards_count]
	var n := 0 if first_time else new_count()   # avant la première ouverture : pas de « nouvelles »
	if n > 0:
		text += " · %d nouvelle%s" % [n, "s" if n > 1 else ""]
	return text


## Ligne d'état de l'album : total et nouvelles.
func album_status() -> String:
	if not loaded:
		return message
	var text := "%d / %d cartes" % [earned_count(), cards_count]
	var n := new_count()
	if n > 0:
		text += " · %d nouvelle%s" % [n, "s" if n > 1 else ""]
	return text


## Éléments de l'album : une carte par élément, dans l'ordre du catalogue.
func items() -> Array:
	if not loaded:
		return [{"id": "none", "label": LOADING, "enabled": false}]
	if cards.is_empty():
		return [{"id": "none", "label": "Aucune carte au catalogue", "enabled": false}]
	var out: Array = []
	for c in cards:
		var id := str(c.get("id", ""))
		var on := is_earned(id)
		out.append({"id": CARD_PREFIX + id, "label": str(c.get("title", id)) if on else "Carte à gagner",
			"detail": str(FAMILY_NAMES.get(str(c.get("family", "")), ""))})
	return out


## Album dessiné par collection_view.gd : familles visibles autour de la carte choisie, vignettes, et
## nombre de familles au-dessus et au-dessous. `focus_id` : élément choisi du menu ("c:<id>").
func album(focus_id: String) -> Dictionary:
	var fams: Array = []
	var by_family := {}
	for c in cards:
		var fam := str(c.get("family", ""))
		if not by_family.has(fam):
			by_family[fam] = {"id": fam, "name": str(FAMILY_NAMES.get(fam, fam)), "cards": [], "earned": 0}
			fams.append(by_family[fam])
		var id := str(c.get("id", ""))
		var on := is_earned(id)
		by_family[fam]["cards"].append({"id": CARD_PREFIX + id, "visual": str(c.get("visual", "")),
			"rarity": str(c.get("rarity", "")), "earned": on, "new": is_new(id),
			"focused": CARD_PREFIX + id == focus_id})
		if on:
			by_family[fam]["earned"] += 1
	var focus_fam := 0
	for i in range(fams.size()):
		for t in fams[i]["cards"]:
			if t["focused"]:
				focus_fam = i
	var first := clampi(focus_fam - 1, 0, maxi(fams.size() - FAMILIES_SHOWN, 0))
	var last := mini(first + FAMILIES_SHOWN, fams.size())
	return {"kind": "album", "families": fams.slice(first, last), "above": first, "below": fams.size() - last}


## A sur une carte de l'album : ouvre la carte ; renvoie les clés à noter vues ([] si aucune).
func open_card(item_id: String) -> Array:
	if not item_id.begins_with(CARD_PREFIX):
		return []
	card_id = item_id.substr(CARD_PREFIX.length())
	return mark_seen(card_id)


## Note vues les éditions nouvelles de la carte `id` (le point « nouvelle » disparaît tout de suite) ;
## renvoie leurs clés pour `collection_seen`.
func mark_seen(id: String) -> Array:
	var keys: Array = []
	for e in editions(id):
		var k := str(e.get("key", ""))
		if k in new_keys:
			keys.append(k)
			new_keys.erase(k)
	return keys


## Première ouverture : toutes les cartes déjà gagnées passent pour vues (pas de point sur les cartes des
## séances d'avant la série) ; renvoie toutes les clés gagnées (le fichier des cartes vues est créé même
## sans carte : la première ouverture n'est montrée qu'une fois).
func open_first() -> Array:
	first_time = false
	new_keys = []
	var keys: Array = []
	for e in earned:
		keys.append(str(e.get("key", "")))
	return keys


static func date_text(iso: String) -> String:
	var p := iso.split("-")
	if p.size() != 3 or not p[1].is_valid_int() or int(p[1]) < 1 or int(p[1]) > 12:
		return iso
	return "%d %s %s" % [int(p[2]), MONTHS[int(p[1]) - 1], p[0]]


## Nombre avec séparateur des milliers à la française (« 1 000 », « 612,5 »).
static func number_text(x: float) -> String:
	var whole := int(floor(absf(x) + 0.0001))
	var frac := absf(x) - whole
	var s := str(whole)
	var out := ""
	while s.length() > 3:
		out = " " + s.substr(s.length() - 3) + out
		s = s.substr(0, s.length() - 3)
	out = ("-" if x < 0 else "") + s + out
	if frac >= 0.05:
		out += "," + str(int(round(frac * 10.0)) % 10)
	return out


## Fiche de la carte agrandie, dessinée par collection_view.gd.
func card_view() -> Dictionary:
	var c := _card(card_id)
	if c.is_empty():
		return {}
	var eds := editions(card_id)
	var fam := str(c.get("family", ""))
	var seasonal := fam == "saison"
	var title := str(c.get("title", card_id))
	var v := {"kind": "card", "visual": str(c.get("visual", "")), "rarity": str(c.get("rarity", "")),
		"rarity_name": str(RARITY_NAMES.get(str(c.get("rarity", "")), "")), "earned": not eds.is_empty(),
		"title": title, "text": str(c.get("text", "")), "number": "n° %d / %d" % [_index(card_id) + 1, cards_count],
		"lines": [], "bar": -1.0}
	if not eds.is_empty():
		var last: Dictionary = eds[eds.size() - 1]
		if seasonal and last.get("edition") != null:
			v["title"] = "%s %d" % [title, int(last["edition"])]
		v["lines"].append(["Gagnée le", date_text(str(last.get("date", "")))])
		if seasonal:
			var years: Array = eds.map(func(e): return str(int(e.get("edition", 0))) if e.get("edition") != null else "")
			v["lines"].append(["Éditions", ", ".join(years.filter(func(y): return y != ""))])
	else:
		var r: Dictionary = remaining.get(card_id, {})
		if not r.is_empty() and float(r.get("target", 0.0)) > 0.0:
			var unit := str(UNITS.get(fam, ""))
			v["lines"].append(["Avancement", "%s / %s%s" % [number_text(float(r.get("value", 0.0))),
				number_text(float(r.get("target", 0.0))), unit]])
			v["bar"] = clampf(float(r.get("value", 0.0)) / float(r["target"]), 0.0, 1.0)
		else:
			v["lines"].append(["", "Pas encore gagnée"])
	if seasonal:
		v["note"] = "Exclusive à sa période : une édition par année, elle ne se rattrape pas après."
	return v


## Séance de la carte agrandie (dernière édition), "" si aucune.
func card_journal() -> String:
	var eds := editions(card_id)
	return str(eds[eds.size() - 1].get("journal", "")) if not eds.is_empty() else ""


func card_title() -> String:
	var v := card_view()
	return str(v.get("title", "Carte"))


## Éléments de la carte agrandie : « Voir la séance » pour une carte gagnée, sinon une ligne grisée.
func card_items() -> Array:
	if card_journal() != "":
		return [{"id": "session", "label": "Voir la séance"}]
	return [{"id": "none", "label": "Pas encore gagnée" if not is_earned(card_id) else "Séance introuvable",
		"enabled": false}]


## Première ouverture, dessinée par collection_view.gd : nombre de cartes déjà gagnées et jusqu'à cinq
## visuels (les plus rares d'abord).
func first_view() -> Dictionary:
	var seen := {}
	var shown: Array = []
	for rarity in ["legendaire", "epique", "rare", "commune"]:
		for e in earned:
			var id := str(e.get("id", ""))
			if str(e.get("rarity", "")) == rarity and not seen.has(id) and shown.size() < 5:
				seen[id] = true
				shown.append({"visual": str(e.get("visual", "")), "rarity": rarity})
	var n := earned_count()
	var headline := "Aucune carte gagnée pour l'instant" if n == 0 else \
		"%d carte%s déjà gagnée%s" % [n, "s" if n > 1 else "", "s" if n > 1 else ""]
	var sub := "Chaque séance peut en débloquer une." if n == 0 else \
		"par vos séances passées. Chaque nouvelle séance peut en débloquer d'autres."
	return {"kind": "first", "headline": headline, "text": sub, "visuals": shown}


static func first_items() -> Array:
	return [{"id": "open", "label": "Ouvrir la Collection"}]
