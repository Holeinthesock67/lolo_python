extends SceneTree

## Tests sans écran des refus expliqués (lot RT4) : refusal_model.gd (départ refusé par le core, appui sans effet
## en séance, bonus refusé, trainer perdu), l'aide de l'attente du départ (start_wait_model.gd `hint`) et le
## bandeau commun « × REFUSÉ » de feedback_model.gd. Chaque refus dit pourquoi ET quoi faire, en mots.
## Lancement : godot --headless --path engine --script res://tests/unit/test_refusal_model.gd

const Refusal := preload("res://scripts/refusal_model.gd")
const Feedback := preload("res://scripts/feedback_model.gd")
const StartWait := preload("res://scripts/start_wait_model.gd")
const MenuFlow := preload("res://scripts/menu_flow.gd")
const MenuModel := preload("res://scripts/menu_model.gd")

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


func _st(extra := {}, session := "RUNNING") -> Dictionary:
	var s := {"session_state": session, "s": 100.0, "trainer_status": "CONNECTED"}
	s.merge(extra, true)
	return s


func _run() -> void:
	# --- Départ refusé : toujours un pourquoi et un quoi faire ---------------------------------------------
	var cases := [
		["bad_args", "Le Grand Prix des objets se joue sans entraînement ERG.", "sans entraînement ERG"],
		["bad_args", "Les épreuves de piste se courent sur un vélodrome.", "vélodrome"],
		["bad_args", "Dernier survivant : parcours trop court : 8 km de course", "trop court"],
		["bad_args", "Grand Prix des objets : le monde ouvert n'a pas de distance de course", "parcours de la liste"],
		["bad_args", "Grand Prix des objets : chaos : 'x' refusé (calme, normal)", "hors bornes"],
		["bot_invalid", "Bots refusés : aucune séance passée sur le parcours « vosges » pour le fantôme", "fantôme"],
		["bot_invalid", "Bots refusés : liste de 4 bots au plus attendue", "bots choisis"],
		["plan_invalid", "Aucune séance du plan à faire aujourd'hui.", "plan"],
		["workout_invalid", "Entraînement « x » invalide : ligne 3", "entraînement"],
		["busy", "Une trace est déjà en cours de compilation.", "autre action"],
		["world_unavailable", "Aucune route à moins de 2 km.", "route"],
	]
	for c in cases:
		var r: Dictionary = Refusal.launch(str(c[0]), str(c[1]))
		_check(str(r["why"]).find(str(c[2])) >= 0 and str(r["todo"]) != "",
			"départ refusé %s : pourquoi « %s », quoi faire « %s »" % [c[0], r["why"], r["todo"]])
	var unknown: Dictionary = Refusal.launch("bad_args", "Mode inconnu.")
	_check(unknown["why"] == "mode inconnu" and unknown["todo"] == Refusal.LAUNCH_FALLBACK_TODO,
		"refus inconnu : texte du core gardé, quoi faire générique (%s)" % str(unknown))
	_check(Refusal.launch("", "")["why"] != "", "refus sans texte : un pourquoi quand même")
	var line := Refusal.launch_text("plan_invalid", "Aucune séance du plan à faire aujourd'hui.")
	_check(line.begins_with("× REFUSÉ · Départ impossible : ") and line.find("\nÀ faire : ") > 0,
		"ligne de l'écran Prêt : mot écrit en tête, deux lignes (%s)" % line)

	# Écran Prêt de la séance libre : un entraînement refusé ne laissait aucune trace
	var f = MenuFlow.new()
	f.connect_done = true
	f.menu.open_screen(MenuModel.READY)
	f.session_state = "READY"
	_check(f.explains_error("plan_invalid") and f.explains_error("bad_args") and not f.explains_error("scan_failed"),
		"écran Prêt : refus du départ expliqué, sans bandeau technique par-dessus")
	f.on_error("workout_invalid", "Entraînement « x » invalide : ligne 3")
	var st: Dictionary = f.state()
	_check(str(st["status"]).begins_with("× REFUSÉ · Départ impossible : l'entraînement choisi est illisible")
		and st["status_error"], "séance libre : entraînement refusé expliqué sur l'écran Prêt (%s)" % str(st["status"]))
	f.on_error("plan_invalid", "Aucune séance du plan à faire aujourd'hui.")
	_check(str(f.state()["status"]).find("À faire : choisis « Session libre »") > 0, "plan du jour absent : quoi faire")

	# --- Appui sans effet en séance -------------------------------------------------------------------
	var gp_empty := _st({"gp": {"held": null, "roll_s": 0.0}})
	var m: Dictionary = Refusal.press("Z_SHORT", gp_empty)
	_check(m.get("family") == "refus" and m["title"] == "Z refusé : aucun objet" and str(m["sub"]).find("« + BONUS »") >= 0,
		"Grand Prix, Z sans objet : refus et quoi faire (%s)" % str(m))
	m = Refusal.press("Z_SHORT", _st({"gp": {"held": null, "roll_s": 1.2}}))
	_check(m.get("title") == "Z refusé : tirage en cours", "Grand Prix, Z pendant le tirage")
	_check(Refusal.press("Z_SHORT", _st({"gp": {"held": "gel", "n": 1, "roll_s": 0.0}})).is_empty(), "Grand Prix, objet en réserve : Z utile")
	_check(Refusal.press("A_SHORT", gp_empty).is_empty(), "autre bouton : rien")
	_check(Refusal.press("Z_SHORT", gp_empty, true).is_empty(), "Cyber-Rogue : ses propres refus")
	_check(Refusal.press("Z_SHORT", gp_empty, false, true).is_empty(), "menu affiché : rien")
	_check(Refusal.press("Z_SHORT", _st({"gp": {"held": null}}, "PAUSED")).is_empty(), "hors RUNNING : rien")
	_check(Refusal.press("Z_SHORT", _st({"wtf": {"points": 0}})).is_empty(), "mode WTF : ses propres retours")
	_check(Refusal.press("Z_SHORT", _st({"erg": {"kind": "workout"}})).is_empty(), "entraînement ERG : Z passe le bloc")
	_check(Refusal.press("Z_SHORT", _st({"erg": {}})).is_empty(), "ERG sans kind : entraînement (contrat)")
	m = Refusal.press("Z_SHORT", _st({"track": {"event": "scratch"}}))
	_check(m.get("title") == "Z sans effet sur la piste" and str(m["sub"]) != "", "piste : Z sans effet, quoi faire")
	m = Refusal.press("Z_SHORT", _st({"survivor": {"alive": 4}}))
	_check(m.get("title") == "Z sans effet au Dernier survivant", "Dernier survivant : Z sans effet")
	m = Refusal.press("Z_SHORT", _st({"powerup": {"held": null, "active": null}}))
	_check(m.get("title") == "Z refusé : aucun bonus en réserve" and str(m["sub"]).find("arche") >= 0, "séance libre : pas de bonus")
	m = Refusal.press("Z_SHORT", _st({"powerup": {"held": null, "active": "aero", "remaining_s": 8.0}}))
	_check(m.get("title") == "Z refusé : un bonus est déjà en cours", "séance libre : bonus déjà en cours")
	_check(Refusal.press("Z_SHORT", _st({"powerup": {"held": "aero", "active": null}})).is_empty(), "bonus en réserve : Z utile (le core juge)")
	_check(Refusal.press("Z_SHORT", _st({"powerup": {"held": null, "active": null, "refused": {"kind": "anvil", "reason": "no_bots"}}})).is_empty(),
		"refus du core en cours : pas de second bandeau")
	_check(Refusal.press("Z_SHORT", _st()).is_empty(), "séance libre sans bonus : rien à dire")

	# --- Bonus refusé par le core, trainer perdu : une fois chacun ----------------------------------------
	var r = Refusal.new()
	var refused := _st({"powerup": {"held": "anvil", "active": null, "refused": {"kind": "anvil", "reason": "no_bots"}}})
	var out: Array = r.on_state(refused)
	_check(out.size() == 1 and out[0]["family"] == "refus" and out[0]["title"] == "Enclume refusée : il faut des bots"
		and str(out[0]["sub"]).begins_with("Gardé en réserve · ajoute des bots"), "bonus refusé : raison du core et quoi faire (%s)" % str(out))
	_check(r.on_state(refused).is_empty(), "même refus sur la trame suivante : une seule fois")
	r.on_state(_st({"powerup": {"held": "anvil", "active": null}}))
	_check(r.on_state(refused).size() == 1, "nouveau refus après la fin du premier : annoncé de nouveau")
	out = r.on_state(_st({"powerup": {"held": "aero", "refused": {"kind": "aero", "reason": "erg"}}}))
	_check(out.size() == 1 and str(out[0]["sub"]).find("repasse en SIM") >= 0, "bonus refusé en ERG : quoi faire")
	var r2 = Refusal.new()
	_check(r2.on_state(_st({"trainer_status": "LOST"}, "IDLE")).is_empty(), "hors séance : trainer absent sans bandeau")
	out = r2.on_state(_st({"trainer_status": "LOST"}, "PAUSED"))
	_check(out.size() == 1 and out[0]["family"] == "attention" and out[0]["title"] == "Trainer perdu : reconnexion en cours"
		and str(out[0]["sub"]).find("pédaler") >= 0, "trainer perdu en séance : quoi faire (%s)" % str(out))
	_check(r2.on_state(_st({"trainer_status": "LOST"}, "PAUSED")).is_empty(), "trainer perdu : une fois par perte")
	r2.on_state(_st())
	_check(r2.on_state(_st({"trainer_status": "LOST"})).size() == 1, "nouvelle perte : annoncée de nouveau")

	# --- Bandeau commun : mot écrit, couleur grise, son de la famille -------------------------------------
	var fb = Feedback.new()
	var sounds: Array = fb.push_all([Refusal.press("Z_SHORT", gp_empty)], 10.0)
	var toast: Dictionary = fb.view(gp_empty, 10.5)["toast"]
	_check(sounds == ["fb_refus"] and toast["tag"] == "× REFUSÉ" and toast["title"] == "Z refusé : aucun objet",
		"bandeau « × REFUSÉ » et son fb_refus (%s, %s)" % [str(sounds), str(toast)])

	# --- Attente du départ qui dure -----------------------------------------------------------------------
	_check(StartWait.hint({"phase": "trainer"}, 3.0) == "", "trainer attendu 3 s : pas encore d'aide")
	_check(StartWait.hint({"phase": "trainer"}, 9.0).begins_with("À faire : allume le trainer"), "trainer muet 9 s : quoi faire")
	_check(StartWait.hint({"phase": "decor"}, 25.0).begins_with("Décor long à charger"), "décor long : patienter ou annuler")
	_check(StartWait.hint({"phase": "pedalage"}, 60.0) == "" and StartWait.hint(null, 60.0) == "", "pédalage, hors attente : rien")

	print("test_refusal_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
