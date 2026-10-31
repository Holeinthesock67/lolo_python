extends SceneTree

## Historique dans le menu (lot O28) : ligne « Historique » de l'accueil, séances du message `history`,
## cumul par semaine, tests de FTP, bilan d'une séance passée (`history_session`) dans le panneau du bilan.
## Lancement : godot --headless --path engine --script res://tests/unit/test_history_menu.gd

const MenuFlow := preload("res://scripts/menu_flow.gd")
const MenuModel := preload("res://scripts/menu_model.gd")
const History := preload("res://scripts/history_view_model.gd")

const SESSION_A := {"id": "2026-10-30_18-05_vosges.fit", "date": "2026-10-30 18:05", "route": "vosges",
	"duration_s": 3725.0, "distance_m": 32412.0, "elevation_gain_m": 410.0, "avg_power_w": 190.0, "np_w": 208.6,
	"if": 0.83, "tss": 71.4, "status": "ok", "workout": null}
const SESSION_B := {"id": "2026-10-29_07-00_demo.jsonl", "date": "2026-10-29 07:00", "route": "demo",
	"duration_s": 1500.0, "distance_m": 9000.0, "elevation_gain_m": 20.0, "avg_power_w": 150.0, "np_w": 152.0,
	"if": 0.61, "tss": 15.5, "status": "recover", "workout": "sweet_spot"}
const MSG := {"type": "history", "v": 1, "request_cmd_id": 4, "sessions": [SESSION_A, SESSION_B],
	"truncated": false, "unreadable": 1,
	"weeks": [{"week": "2026-W44", "start_date": "2026-10-26", "count": 2, "duration_s": 5225.0,
		"distance_m": 41412.0, "elevation_gain_m": 430.0, "tss": 86.9}],
	"ftp_tests": [{"date": "2026-10-12 10:21", "ftp_w": 236, "previous_ftp_w": 200, "warnings": ["paused"],
		"reliable": true}]}
const SUMMARY := {"duration_s": 3725.0, "distance_m": 32412.0, "avg_power_w": 190.0, "fit_path": "/x/a.fit",
	"np_w": 208.6, "intensity_factor": 0.83, "tss": 71.4, "elevation_gain_m": 410.0}

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
	f.set_routes([{"id": "vosges", "name": "Vosges", "status": "ready", "length_m": 30000}])
	_check("history" in _ids(f.state()), "accueil : ligne « Historique »")
	f.menu.focus_item("history")
	_check(f.handle("A_LONG") == {"action": "list_history"}, "Historique : list_history demandé")
	var st: Dictionary = f.state()
	_check(st["screen"] == History.SCREEN and st["status"] == "Chargement…" and _ids(st) == ["none"],
		"en attente de la réponse")
	f.on_history(MSG)
	st = f.state()
	_check(_ids(st) == ["weeks", "ftp", "s:" + SESSION_A["id"], "s:" + SESSION_B["id"], "unreadable"],
		"semaines, tests de FTP, séances de la plus récente à la plus ancienne, fichier illisible (%s)" % str(_ids(st)))
	var a := _item(st, "s:" + SESSION_A["id"])
	_check(a["label"] == "30/10/2026 18:05 · Vosges" and a["detail"] == "1 h 02 · 32,4 km · NP 209 W · TSS 71",
		"séance : date, nom du parcours ; durée, distance, NP, TSS (%s | %s)" % [a["label"], a["detail"]])
	_check(_item(st, "s:" + SESSION_B["id"])["detail"] == "25 min · 9,0 km · NP 152 W · TSS 16 · sans fichier FIT",
		"séance sans FIT signalée")
	_check(_item(st, "ftp")["detail"] == "dernier : 236 W le 12/10/2026", "dernier test de FTP")
	_check(_item(st, "unreadable")["label"] == "1 fichier illisible ignoré", "fichiers illisibles comptés")
	f.menu.focus_item("weeks")
	f.handle("A_LONG")
	st = f.state()
	_check(st["screen"] == History.WEEKS and st["items"][0]["label"] == "Semaine du 26/10/2026 · 2 séances"
		and st["items"][0]["detail"] == "1 h 27 · 41,4 km · 430 m · TSS 87", "cumul par semaine (%s)" % str(st["items"][0]))
	f.handle("Y_SHORT")
	f.menu.focus_item("ftp")
	f.handle("A_LONG")
	st = f.state()
	_check(st["screen"] == History.FTP and st["items"][0]["label"] == "12/10/2026 10:21 · FTP 236 W"
		and st["items"][0]["detail"] == "FTP d'avant 200 W · pause pendant l'effort", "tests de FTP")
	f.handle("Y_SHORT")
	f.menu.focus_item("s:" + SESSION_A["id"])
	_check(f.handle("A_LONG") == {"action": "history_session", "id": SESSION_A["id"]}, "A : bilan demandé")
	f.on_history_session({"type": "history_session", "id": "autre.fit", "summary": SUMMARY})
	_check(f.state()["screen"] == History.SCREEN, "réponse pour une autre séance ignorée")
	f.on_history_session({"type": "history_session", "id": SESSION_A["id"], "summary": SUMMARY})
	st = f.state()
	_check(st["screen"] == History.SESSION and st["title"] == "Séance du 30/10/2026 18:05 · Vosges"
		and f.shown_summary() == SUMMARY and st["card"].get("title", "") == "Bilan de la séance",
		"bilan dans le panneau du bilan de fin de séance")
	f.handle("A_LONG")
	_check(f.show_details, "Voir le bilan détaillé")
	f.menu.focus_item("back")
	f.handle("A_LONG")
	_check(f.state()["screen"] == History.SCREEN and f.shown_summary() == f.summary, "retour à l'historique")
	f.menu.focus_item("s:" + SESSION_B["id"])
	f.handle("A_LONG")
	f.on_error("bad_args", "Séance inconnue")
	_check(f.state()["status"] == "Échec : Séance inconnue" and f.state()["status_error"], "erreur sur la ligne d'état")
	f.on_history({"type": "history", "sessions": [], "weeks": [], "ftp_tests": [], "unreadable": 0, "truncated": false})
	st = f.state()
	_check(_ids(st) == ["weeks", "ftp", "none"] and not st["items"][0]["enabled"] and not st["items"][1]["enabled"],
		"historique vide : rien à ouvrir")
	print("test_history_menu : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
