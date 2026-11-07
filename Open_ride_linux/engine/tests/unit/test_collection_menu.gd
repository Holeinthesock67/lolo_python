extends SceneTree

## Collection de cartes au menu (série BC, lot BC5, maquettes BC3) : ligne « Collection » de l'accueil,
## première ouverture, album par familles, carte agrandie (gagnée, à gagner, de saison), `collection_seen`,
## « Voir la séance » vers le bilan de l'historique. Données synthétiques (dates fictives).
## Lancement : godot --headless --path engine --script res://tests/unit/test_collection_menu.gd

const MenuFlow := preload("res://scripts/menu_flow.gd")
const MenuModel := preload("res://scripts/menu_model.gd")
const Collection := preload("res://scripts/collection_view_model.gd")
const History := preload("res://scripts/history_view_model.gd")
const CollectionView := preload("res://scripts/collection_view.gd")

const CARDS := [
	{"id": "premiere_seance", "title": "Premier coup de pédale", "text": "La première séance est enregistrée.",
		"family": "seance", "rarity": "commune", "visual": "pedale"},
	{"id": "km_100", "title": "Cent bornes", "text": "Les cent premiers kilomètres sont au compteur.",
		"family": "distance", "rarity": "commune", "visual": "borne_100"},
	{"id": "km_1000", "title": "Mille bornes", "text": "Mille kilomètres cumulés.",
		"family": "distance", "rarity": "rare", "visual": "borne_1000"},
	{"id": "leve_tot", "title": "Lève-tôt", "text": "Une séance commencée avant 7 h.",
		"family": "heure", "rarity": "commune", "visual": "coq"},
	{"id": "halloween", "title": "Pédaleur citrouille", "text": "Une séance pendant la semaine d'Halloween.",
		"family": "saison", "rarity": "rare", "visual": "citrouille"},
]


static func _earned(id: String, date: String, edition = null) -> Dictionary:
	var c: Dictionary = {}
	for x in CARDS:
		if x["id"] == id:
			c = x.duplicate()
	c["key"] = id if edition == null else "%s:%d" % [id, edition]
	c["edition"] = edition
	c["journal"] = date + "_07-00-00.jsonl"
	c["date"] = date
	return c


static func _msg(first_time: bool) -> Dictionary:
	return {"type": "collection", "v": 1, "request_cmd_id": 3, "cards_count": CARDS.size(), "first_time": first_time,
		"cards": CARDS, "earned": [_earned("premiere_seance", "2026-09-02"), _earned("halloween", "2025-10-28", 2025),
			_earned("km_100", "2026-09-20"), _earned("halloween", "2026-10-29", 2026)],
		"remaining": [{"id": "km_1000", "value": 612.4, "target": 1000.0}, {"id": "leve_tot", "value": 0.0, "target": 1.0}],
		"new": ["km_100", "halloween:2026"]}


var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _ids(st: Dictionary) -> Array:
	return st["items"].map(func(it): return str(it["id"]))


func _item(st: Dictionary, id: String) -> Dictionary:
	for it in st["items"]:
		if str(it["id"]) == id:
			return it
	return {}


func _init() -> void:
	_test_model()
	_test_flow()
	_test_view()
	print("test_collection_menu : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _test_model() -> void:
	var m = Collection.new()
	_check(m.home_detail() == "", "accueil : rien avant la réponse du core")
	m.on_collection(_msg(false))
	_check(m.earned_count() == 3 and m.new_count() == 2, "3 cartes distinctes, 2 nouvelles (saison : une carte)")
	_check(m.home_detail() == "3 / 5 cartes · 2 nouvelles", "détail de l'accueil (%s)" % m.home_detail())
	m.first_time = true
	_check(m.home_detail() == "3 / 5 cartes", "avant la première ouverture : pas de « nouvelles »")
	m.first_time = false
	_check(Collection.number_text(1000.0) == "1 000" and Collection.number_text(612.4) == "612,4"
		and Collection.number_text(40000.0) == "40 000" and Collection.number_text(3.0) == "3", "nombres à la française")
	_check(Collection.date_text("2026-11-06") == "6 novembre 2026", "date en toutes lettres")
	var album: Dictionary = m.album("c:km_100")
	var names: Array = album["families"].map(func(f): return f["name"])
	_check(names == ["Séances", "Distance", "Heure"] and album["above"] == 0 and album["below"] == 1,
		"album : familles dans l'ordre du catalogue, trois à la fois (%s)" % str(names))
	var dist: Dictionary = album["families"][1]
	_check(dist["earned"] == 1 and dist["cards"].size() == 2 and dist["cards"][0]["focused"] and dist["cards"][0]["new"]
		and not dist["cards"][1]["earned"], "rangée Distance : 1 / 2, Cent bornes choisie et nouvelle, Mille bornes à gagner")
	_check(m.album("c:halloween")["above"] == 1, "la fenêtre suit la famille choisie")
	var keys: Array = m.open_card("c:km_100")
	_check(keys == ["km_100"] and not m.is_new("km_100") and m.new_count() == 1, "carte agrandie : notée vue")
	_check(m.open_card("c:km_100").is_empty(), "rouverte : rien à noter")
	var v: Dictionary = m.card_view()
	_check(v["title"] == "Cent bornes" and v["rarity_name"] == "Commune" and v["number"] == "n° 2 / 5"
		and v["lines"][0] == ["Gagnée le", "20 septembre 2026"] and m.card_items()[0]["id"] == "session",
		"carte gagnée : titre, rareté, numéro, date, « Voir la séance » (%s)" % str(v))
	m.open_card("c:km_1000")
	v = m.card_view()
	_check(not v["earned"] and v["lines"][0] == ["Avancement", "612,4 / 1 000 km"] and absf(v["bar"] - 0.6124) < 0.001
		and not m.card_items()[0].get("enabled", true), "carte à gagner : avancement en km, barre, pas de séance")
	_check(m.items()[2]["label"] == "Carte à gagner", "album : titre d'une carte à gagner caché")
	m.open_card("c:halloween")
	v = m.card_view()
	_check(v["title"] == "Pédaleur citrouille 2026" and v["lines"][1] == ["Éditions", "2025, 2026"] and v.has("note"),
		"carte de saison : dernière édition au titre, éditions gagnées, exclusive à sa période (%s)" % str(v["lines"]))
	_check(m.card_journal() == "2026-10-29_07-00-00.jsonl", "séance de la dernière édition")
	var first: Dictionary = m.first_view()
	_check(first["headline"] == "3 cartes déjà gagnées" and first["visuals"][0]["rarity"] == "rare"
		and first["visuals"].size() == 3, "première ouverture : nombre et visuels, les plus rares d'abord")
	_check(m.open_first().size() == 4 and m.new_keys.is_empty() and not m.first_time,
		"première ouverture : toutes les éditions gagnées notées vues")


func _test_flow() -> void:
	var f = MenuFlow.new()
	f.connect_done = true
	f.on_state({"session_state": "IDLE"})
	f.set_routes([{"id": "demo", "name": "Démo", "status": "ready", "length_m": 4000}])
	var st: Dictionary = f.state()
	_check("collection" in _ids(st) and _ids(st).find("collection") == _ids(st).find("history") + 1,
		"accueil : « Collection » après « Historique »")
	f.on_collection(_msg(true))   # réponse à list_collection du lancement : l'accueil seulement
	_check(_item(f.state(), "collection")["detail"] == "3 / 5 cartes" and f.state()["screen"] == MenuModel.HOME,
		"réponse hors de l'album : détail de l'accueil, pas de première ouverture")
	f.menu.focus_item("collection")
	_check(f.handle("A_LONG") == {"action": "list_collection"}, "Collection : list_collection demandé")
	st = f.state()
	_check(st["screen"] == Collection.SCREEN and st["status"] == "Chargement…" and st["collection"].is_empty(),
		"en attente de la réponse")
	var act: Dictionary = f.on_collection(_msg(true))
	st = f.state()
	_check(st["screen"] == Collection.FIRST and act.get("action") == "collection_seen" and act["keys"].size() == 4
		and st["collection"].get("kind") == "first", "première ouverture : écran unique, cartes passées notées vues")
	f.handle("A_LONG")   # Ouvrir la Collection
	st = f.state()
	_check(st["screen"] == Collection.SCREEN and st["status"] == "3 / 5 cartes" and st["collection"].get("kind") == "album"
		and _ids(st) == ["c:premiere_seance", "c:km_100", "c:km_1000", "c:leve_tot", "c:halloween"],
		"album : une carte par élément, sans nouvelle (%s | %s)" % [st["status"], str(_ids(st))])
	_check(f.on_collection(_msg(false)).is_empty() and f.state()["status"] == "3 / 5 cartes · 2 nouvelles",
		"réponse suivante : nouvelles comptées")
	f.handle("PLUS_SHORT")
	st = f.state()
	_check(st["collection"]["families"][1]["cards"][0]["focused"], "+ : carte suivante, vignette choisie")
	act = f.handle("A_LONG")
	st = f.state()
	_check(act == {"action": "collection_seen", "keys": ["km_100"]} and st["screen"] == Collection.CARD
		and st["title"] == "Cent bornes" and _ids(st) == ["session"], "A : carte agrandie, clé envoyée au core (%s)" % str(act))
	act = f.handle("A_LONG")
	_check(act == {"action": "history_session", "id": "2026-09-20_07-00-00.jsonl"} and f.state()["status"] == "Chargement de la séance…",
		"Voir la séance : bilan demandé")
	f.on_history_session({"type": "history_session", "id": "2026-09-20_07-00-00.jsonl", "summary": {"duration_s": 1800.0}})
	st = f.state()
	_check(st["screen"] == History.SESSION and f.shown_summary() == {"duration_s": 1800.0}, "bilan de la séance de la carte")
	f.handle("Y_SHORT")
	_check(f.state()["screen"] == Collection.CARD, "Y : retour à la carte")
	f.handle("A_LONG")
	f.on_error("bad_args", "Séance inconnue")
	_check(f.state()["status"] == "Échec : Séance inconnue" and f.state()["status_error"], "erreur sur la ligne d'état")
	f.handle("Y_SHORT")
	st = f.state()
	_check(st["screen"] == Collection.SCREEN and st["status"] == "3 / 5 cartes · 1 nouvelle", "Y : album, une nouvelle de moins")
	f.handle("Y_SHORT")
	st = f.state()
	_check(st["screen"] == MenuModel.HOME and _item(st, "collection")["detail"] == "3 / 5 cartes · 1 nouvelle",
		"accueil à jour")


func _test_view() -> void:
	var m = Collection.new()
	m.on_collection(_msg(false))
	var v = CollectionView.new()
	v.update_display(m.album("c:km_100"))
	var text: String = v.view_text()
	_check(v.visible and text.contains("Distance | 1 / 2 | [c:km_100] | c:km_1000") and text.contains("▼ 1 famille plus bas"),
		"vue de l'album : familles, vignettes, choix, familles cachées (%s)" % text)
	m.open_card("c:km_1000")
	v.update_display(m.card_view())
	text = v.view_text()
	_check(text.contains("Mille bornes | Rare | n° 3 / 5") and text.contains("Avancement | 612,4 / 1 000 km"),
		"vue de la carte (%s)" % text)
	v.update_display({})
	_check(not v.visible, "cachée hors de la collection")
	v.free()
