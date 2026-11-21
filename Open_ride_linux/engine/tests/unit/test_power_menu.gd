extends SceneTree

## « Ma puissance » (série PP, lot PP3, contrat 1.29) : ligne de « Qui roule ? », courbe du message
## `power_curve` (6 mois et 6 semaines, mots « libre » et « ERG »), FTP estimée et sa proposition (confirmation,
## puis `set_setting` `rider.ftp_w`, puis courbe redemandée), test de rampe, évolution mois par mois, carte de
## détail avec la courbe. Valeurs fictives (FTP 250 W).
## Lancement : godot --headless --path engine --script res://tests/unit/test_power_menu.gd

const MenuFlow := preload("res://scripts/menu_flow.gd")
const MenuModel := preload("res://scripts/menu_model.gd")
const Power := preload("res://scripts/power_view_model.gd")
const Profiles := preload("res://scripts/profiles_view_model.gd")
const DetailCard := preload("res://scripts/detail_card.gd")

const HELLO := {"id": "cycliste-1", "name": "Cycliste 1", "type": "joueur", "count": 1}
const PROFILES := {"active": "cycliste-1", "items": [{"id": "cycliste-1", "name": "Cycliste 1", "type": "joueur",
	"level": 3, "last_ride": "2026-11-15"}], "trash": []}
const DURATIONS := [5, 15, 30, 60, 120, 180, 300, 480, 720, 1200, 1800, 2700, 3600]


func _pt(w: int, e: String, d: String, r, k = null) -> Dictionary:
	return {"w": w, "e": e, "d": d, "r": r, "k": k}


func _msg(proposal) -> Dictionary:
	var pts: Array = []
	var watts := [880, 720, 560, 430, 397, 349, 310, 286, 273, 262, 238, 232, 228]
	for i in range(DURATIONS.size()):
		var m6 := _pt(watts[i], "ERG" if DURATIONS[i] == 3600 else "libre", "2026-10-28", "demo",
			"seuil_3x15" if DURATIONS[i] == 3600 else null)
		var w6 = null if DURATIONS[i] >= 2700 else _pt(watts[i] - 10, "libre", "2026-11-15", "vosges")
		pts.append({"s": DURATIONS[i], "m6": m6, "w6": w6})
	return {"type": "power_curve", "v": 1, "request_cmd_id": 3, "profile_id": "cycliste-1", "ftp_set_w": 250,
		"sessions": {"m6": 9, "w6": 4}, "points": pts,
		"estimate": {"ftp_w": 249, "source": "best20", "date": "2026-11-15",
			"source_text": "meilleur effort libre de 20 min du 15 nov. (95 % de 262 W)"},
		"confidence": "Indicative", "reason": null, "proposal_w": proposal, "review": false, "delta_pct": -0.4,
		"monthly": [{"m": "2026-06", "ftp": null, "p5": null, "p20": null},
			{"m": "2026-11", "ftp": 249, "p5": 300, "p20": 262}],
		"warnings": ["L'estimation suppose des efforts à fond.", "Calibration du home trainer."]}


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
	var f = MenuFlow.new()
	f.connect_done = true
	f.on_state({"session_state": "IDLE"})
	f.on_hello_profile(HELLO)
	f.on_profiles(PROFILES)
	f.set_routes([{"id": "vosges", "name": "Vosges", "status": "ready", "length_m": 30000},
		{"id": "demo", "name": "Col du lacet", "status": "ready", "length_m": 10000}])
	f.menu.reset()
	f.menu.focus_item("profile")
	f.handle("A_LONG")
	_check(f.menu.current_screen() == Profiles.SCREEN and "power" in _ids(f.state()), "« Qui roule ? » : ligne « Ma puissance »")
	_check(_item(f.state(), "power")["detail"] == "courbe et FTP estimée de Cycliste 1", "détail de la ligne")
	f.menu.focus_item("power")
	_check(f.handle("A_LONG") == {"action": "list_power_curve"}, "Ma puissance : list_power_curve demandé")
	var st: Dictionary = f.state()
	_check(st["screen"] == Power.SCREEN and st["status"] == "Chargement…" and _ids(st) == ["none"], "en attente du core")
	f.on_power_curve(_msg(249))
	st = f.state()
	_check(st["title"] == "Ma puissance — Cycliste 1", "titre au nom du profil (%s)" % st["title"])
	var ids := _ids(st)
	_check(ids.slice(0, 4) == ["window", "accept", "ramp", "months"] and ids.size() == 17,
		"période, proposition, rampe, évolution, puis 13 durées (%s)" % str(ids))
	_check(_item(st, "accept")["label"] == "Utiliser 249 W comme FTP", "proposition en watts")
	var r5 := _item(st, "d:5")
	_check(r5["label"] == "5 s · 880 W · libre" and r5["detail"] == "28 oct. · Col du lacet",
		"durée : watts, date, séance, mot « libre » (%s | %s)" % [r5["label"], r5["detail"]])
	_check(_item(st, "d:3600")["label"] == "60 min · 228 W · ERG" and _item(st, "d:3600")["detail"] == "28 oct. · seuil 3x15",
		"séance ERG : le mot « ERG » et son entraînement")
	# carte : FTP réglée, FTP estimée et confiance en mots, courbe, source
	f.menu.focus_item("d:300")
	var card: Dictionary = f.card(f.state())
	_check(card["title"] == "MA PUISSANCE" and card["name"] == "6 derniers mois", "carte : titre et période")
	_check(card["tiles"][0]["value"] == "250" and card["tiles"][1]["label"] == "FTP estimée · Indicative"
		and card["tiles"][1]["value"] == "249", "tuiles : FTP réglée et estimée, confiance écrite")
	_check(card["curve"]["m6"].size() == 13 and card["curve"]["w6"][12][1] == null and card["curve"]["ftp_w"] == 250,
		"courbe des deux périodes et FTP réglée")
	_check(card["lines"][0].begins_with("Source : meilleur effort libre de 20 min"), "source en toutes lettres")
	_check("5 min : 310 W le 28 oct. (libre) sur 6 mois, 300 W le 15 nov. (libre) sur 6 semaines." in card["lines"],
		"ligne de la durée choisie (%s)" % str(card["lines"]))
	var dc = DetailCard.new()
	dc.update_display(card)
	_check(dc.chart_kind() == "curve", "la carte dessine la courbe")
	dc.free()
	# période des 6 dernières semaines
	f.menu.focus_item("window")
	f.handle("A_LONG")
	st = f.state()
	_check(_item(st, "window")["label"] == "Période : 6 semaines" and _item(st, "d:5")["label"] == "5 s · 870 W · libre"
		and _item(st, "d:3600")["label"] == "60 min · —", "6 dernières semaines : watts récents, trous signalés")
	_check(_item(st, "d:3600")["detail"] == "aucun effort à fond depuis 6 semaines", "trou de la courbe écrit en mots")
	_check("● 6 semaines   ○ 6 mois   - - FTP réglée" in f.card(st)["lines"], "légende écrite, à jour de la période")
	# proposition : confirmation, « Non » par défaut
	f.menu.focus_item("accept")
	f.handle("A_LONG")
	_check(f.menu.current_screen() == MenuModel.CONFIRM and f.state()["title"].begins_with("Utiliser 249 W comme FTP ?"),
		"confirmation demandée")
	_check(f.handle("A_LONG").is_empty() and f.menu.current_screen() == Power.SCREEN, "« Non » : rien n'est écrit")
	_check(f.take_power_refresh().is_empty(), "rien en attente après « Non »")
	f.menu.focus_item("accept")
	f.handle("A_LONG")
	f.handle("PLUS_SHORT")
	_check(f.handle("A_LONG") == {"action": "set_setting", "key": "rider.ftp_w", "value": 249},
		"« Oui » : réglage du joueur rider.ftp_w")
	_check(f.state()["status"] == "Enregistrement…", "attente du core")
	f.on_settings({"type": "settings", "items": [{"key": "rider.ftp_w", "value": 249}]})
	_check(f.take_power_refresh() == {"action": "list_power_curve"} and f.state()["status"] == "FTP enregistrée : 249 W",
		"FTP enregistrée, courbe redemandée")
	f.on_power_curve(_msg(null))
	_check(not ("accept" in _ids(f.state())), "plus de proposition quand la FTP réglée vaut l'estimation")
	# évolution et test de rampe
	f.menu.focus_item("months")
	f.handle("A_LONG")
	st = f.state()
	_check(st["screen"] == Power.MONTHS and st["items"][1]["label"] == "novembre 2026 · FTP 249 W"
		and st["items"][1]["detail"] == "5 min 300 W · 20 min 262 W" and st["items"][0]["label"] == "juin 2026 · FTP —",
		"évolution mois par mois (%s)" % str(st["items"]))
	f.handle("Y_SHORT")
	f.menu.focus_item("ramp")
	f.handle("A_LONG")
	_check(f.menu.current_screen() == "ftp_test", "« Faire un test de rampe » : écran du test de FTP")
	f.handle("Y_SHORT")
	# profil sans séance
	var empty := _msg(null)
	empty["sessions"] = {"m6": 0, "w6": 0}
	empty["estimate"] = null
	empty["confidence"] = "Pas assez de données"
	empty["reason"] = "aucun effort libre depuis 6 semaines"
	f.on_power_curve(empty)
	st = f.state()
	_check(_ids(st) == ["none", "ramp"] and st["items"][0]["label"] == "Roule une première séance pour voir ta courbe",
		"profil sans séance : message et test de rampe (%s)" % str(_ids(st)))
	_check(not f.card(st).has("curve") and f.card(st)["tiles"][1]["value"] == "—", "carte sans courbe")
	f.on_error("busy", "« Ma puissance » s'ouvre au menu")
	_check(f.state()["status_error"], "refus du core sur la ligne d'état")
	print("test_power_menu : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
