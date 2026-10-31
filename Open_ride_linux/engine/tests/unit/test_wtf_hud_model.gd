extends SceneTree

## Tests sans écran de l'habillage du mode « What the fuck » (série WTF, lot WTF7) : objet `wtf` de la trame
## `state` (contrat 1.5) traduit en bandeau, carte, invite, Katamari et horloge (maquettes du 30 octobre).
## Lancement : godot --headless --path engine --script res://tests/unit/test_wtf_hud_model.gd

const WtfHudModel := preload("res://scripts/wtf/wtf_hud_model.gd")
const WtfView := preload("res://scripts/wtf/wtf_view.gd")
const SummaryViewModel := preload("res://scripts/summary_view_model.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _init() -> void:
	call_deferred("_run")


func _ev(ev: Dictionary) -> Dictionary:
	return WtfHudModel.view({"points": 120, "event": ev})


func _run() -> void:
	_check(not WtfHudModel.view(null)["visible"], "hors mode WTF : rien")
	var idle: Dictionary = WtfHudModel.view({"points": 0, "event": null, "next_s": 12})
	_check(idle["banner"]["text"] == "MODE WTF" and idle["banner"]["time"] == "prochain gag dans 12 s",
		"entre deux gags : compte à rebours")
	_check(idle["card"].is_empty() and idle["kata"].is_empty() and idle["clock"].is_empty(), "règles coupées : pas de carte")

	var moon := _ev({"id": "gravity", "left_s": 42.3, "planet": "moon", "hop_m": 1.2})
	_check(moon["banner"]["text"] == "GRAVITÉ : LA LUNE !" and moon["banner"]["time"] == "0:43", "Lune : nom et temps")
	_check(moon["banner"]["points"] == "120 pts", "points")
	_check(_ev({"id": "gravity", "left_s": 5, "planet": "jupiter"})["banner"]["color"] == WtfHudModel.ORANGE,
		"Jupiter en orange")
	var col := _ev({"id": "collapse", "left_s": 30, "gap_m": 60.0})
	_check(col["card"]["value"] == "60 m" and is_equal_approx(col["card"]["bar"], 0.5), "effondrement : écart et jauge")
	var cheese := _ev({"id": "cheese", "left_s": 30, "gap_m": 125.0, "squashed": true})
	_check(cheese["banner"]["text"] == "ÉCRASÉ !" and cheese["card"]["value"] == "125 / 250 m", "fromage : écrasé")
	var micro := _ev({"id": "micro", "left_s": 70, "kind": "sprint", "target": 375.0, "round": 2,
		"round_left_s": 12.0, "results": [true], "progress": 0.4})
	_check(micro["banner"]["text"] == "MICRO-DÉFI 2 / 3" and micro["banner"]["time"] == "0:12", "micro-défi : manche")
	_check(micro["card"]["value"] == "375 W pendant 5 s" and is_equal_approx(micro["card"]["bar"], 0.4), "sprint : cible")
	var steady := _ev({"id": "micro", "kind": "steady", "target": 0, "progress": 0.0})
	_check(steady["card"]["value"] == "fixe ta puissance…", "régulier : cible pas encore fixée")
	var eggs := _ev({"id": "eggs", "left_s": 200, "eggs": 4, "left_m": 1500})
	_check(eggs["banner"]["time"] == "1,5 km" and eggs["card"]["value"] == "4 / 6", "œufs : distance et œufs intacts")
	_check(_ev({"id": "camera", "left_s": 3, "view": "pigeon"})["banner"]["text"] == "CAMÉRA PIGEON !", "caméra pigeon")
	_check(_ev({"id": "tiny", "left_s": 3})["card"].is_empty(), "tout petit : pas de carte")

	var reveal := _ev({"id": "chef", "left_s": 50, "phase": "reveal", "dish": "souffle", "phase_left_s": 3.2})
	_check(reveal["banner"]["text"] == "SURPRISE DU CHEF : SOUFFLÉ !", "chef : plat révélé")
	_check(reveal["prompt"]["key"] == "Z" and reveal["prompt"]["time"] == "4 s", "invite Z le temps de la révélation")
	_check(reveal["card"].is_empty(), "pas de carte avant de manger")
	var arrive := _ev({"id": "chef", "phase": "arrive", "dish": null, "phase_left_s": 2.0})
	_check(arrive["banner"]["text"] == "LE CHEF ARRIVE…" and arrive["prompt"].is_empty(), "cloche : plat caché")
	var souffle := _ev({"id": "chef", "phase": "eat", "dish": "souffle", "phase_left_s": 30.0, "souffle": 0.85})
	_check(souffle["card"]["value"] == "85 %" and souffle["prompt"].is_empty(), "soufflé : hauteur, plus d'invite")
	var chili := _ev({"id": "chef", "phase": "eat", "dish": "chili", "burning": true})
	_check(chili["card"]["value"].begins_with("ÇA BRÛLE"), "piment : ça brûle")

	var amb: Dictionary = WtfHudModel.view({"points": 5, "event": null, "next_s": 3,
		"kata": {"size": 3.1, "count": 87, "last": "cow", "next": []}, "clock_h": 21.5, "fish": true})
	_check(amb["kata"]["title"] == "KATAMARI × 3,1" and amb["kata"]["line"] == "87 objets · dernier : une vache",
		"Katamari : taille et dernier objet")
	_check(WtfHudModel.view({"kata": {"size": 1.0, "count": 0, "last": null}})["kata"]["line"] == "0 objets",
		"Katamari vide : pas de dernier objet")
	_check(amb["clock"]["text"] == "21 h 30" and amb["clock"]["fish"], "horloge et poissons volants")

	var lines: Array = SummaryViewModel.new().wtf_lines({"points": 1480, "events": {"gravity": 2, "chef": 1},
		"kata_size": 3.1, "kata_count": 87})
	var labels: Array = lines.map(func(l): return l["label"])
	_check(labels == ["Mode WTF", "Gags joués", "Katamari", "Records"], "bilan : points, gags, Katamari, pas de records")
	_check(lines[0]["value"] == "1480 pts" and lines[1]["value"] == "Gravité × 2, Surprise du chef × 1"
		and lines[2]["value"] == "× 3,1, 87 objets", "bilan : valeurs")
	var plain: Array = SummaryViewModel.new().lines({"duration_s": 60.0, "wtf": {"points": 0, "events": {}}})
	_check(plain.any(func(l): return l["label"] == "Gags joués" and l["value"] == "aucun"), "bilan sans gag")

	var view = WtfView.new()
	root.add_child(view)
	view.update_view(reveal)
	var info: Dictionary = view.test_info()
	_check(info["visible"] and info["banner"] == "SURPRISE DU CHEF : SOUFFLÉ !", "vue : bandeau affiché")
	_check(info["prompt"].contains("NON MERCI, CHEF !") and info["card"] == "", "vue : invite, pas de carte")
	view.update_view(amb)
	info = view.test_info()
	_check(info["kata"] == "KATAMARI × 3,1" and info["clock"].contains("poissons"), "vue : Katamari et horloge")
	_check(info["kata_top"] == WtfView.SIDE_TOP and info["clock_top"] > info["kata_top"], "vue : sans gag, Katamari en haut")
	var with_card: Dictionary = amb.duplicate()
	with_card["card"] = {"title": "Œufs intacts", "value": "6 / 6", "bar": 1.0, "note": ""}
	view.update_view(with_card)
	info = view.test_info()
	_check(info["card"] == "Œufs intacts" and info["card_top"] == WtfView.SIDE_TOP and info["kata_top"] > info["card_top"]
		and info["clock_top"] > info["kata_top"], "vue : carte du gag à gauche, au-dessus du Katamari et de l'horloge")
	_check(info["kata_compact"], "vue : pendant un gag à carte, Katamari réduit à une ligne")
	var worst: Dictionary = WtfHudModel.view({"points": 5, "event": {"id": "gravity", "planet": "jupiter", "left_s": 30},
		"kata": {"size": 3.1, "count": 87, "last": "church"}, "clock_h": 21.5, "fish": true})
	view.update_view(worst)
	info = view.test_info()
	_check(info["stack_bottom"] > WtfView.SIDE_TOP and info["stack_bottom"] <= 720.0 * WtfView.STACK_MAX_FRAC,
		"vue : la pile de gauche s'arrête au-dessus du bas de l'écran (%d px sur 720)" % int(info["stack_bottom"]))
	view.update_view(reveal)
	_check(view.test_info()["prompt_top"] < 720.0 * 0.35, "vue : invite du chef sous le bandeau, pas sur le cycliste")
	view.update_view(amb)
	_check(not view.test_info()["kata_compact"], "vue : sans gag, Katamari complet")
	view.update_view(WtfHudModel.view(null))
	_check(not view.test_info()["visible"], "vue cachée hors mode WTF")
	view.queue_free()
	print("test_wtf_hud_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
