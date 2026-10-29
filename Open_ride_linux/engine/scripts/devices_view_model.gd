extends RefCounted

## Modèle de vue de l'état des appareils et de leurs alertes (Lot N5, SRS §4.2, Contrat IPC v1.1 §3).
##
## Calcule les lignes d'état des appareils (trainer, Click, cardio) avec repli v1,
## les alertes lors des transitions (coupures, batterie faible, perte de ceinture),
## et vérifie si le système est prêt à rouler, sans aucun nœud Godot.
## Pas de class_name : charger par preload("res://scripts/devices_view_model.gd").

const LEVEL_OK := "ok"
const LEVEL_WARN := "warn"
const LEVEL_ERROR := "error"
const LEVEL_OFF := "off"


## Valeur du contrat qui peut valoir null : dictionnaire vide, liste vide ou texte vide à la place.
static func _dict(v) -> Dictionary:
	return v if v is Dictionary else {}


static func _arr(v) -> Array:
	return v if v is Array else []


static func _text(v) -> String:
	return "" if v == null else str(v)


const TRAINER_BUSY_TEXT := "Trainer piloté par un autre appareil (montre ?) : consignes en attente"


## Vrai quand le core signale un Control Point occupé (`devices.trainer.busy`, révision 1.5) :
## un autre appareil (montre Garmin…) pilote le trainer, la liaison est gardée.
static func trainer_busy(state: Dictionary) -> bool:
	return _dict(_dict(state.get("devices")).get("trainer")).get("busy", false) == true


## Formate les lignes d'état des appareils à partir d'une trame state.
## Renvoie une liste de dictionnaires : {id, label, status_text, level}.
func rows(state: Dictionary) -> Array:
	var out: Array = []
	var devices = state.get("devices", null)

	if devices is Dictionary and not devices.is_empty():
		# 1. Trainer
		var trainer: Dictionary = _dict(devices.get("trainer"))
		var t_status: String = str(trainer.get("status", state.get("trainer_status", "LOST")))
		var t_name: String = _text(trainer.get("name")).strip_edges()
		var t_label := "Trainer" if t_name == "" else ("Trainer %s" % t_name)
		var t_text := "connecté"
		var t_level := LEVEL_OK

		match t_status:
			"CONNECTED":
				t_text = "connecté"
				t_level = LEVEL_OK
			"MOCK":
				t_text = "connecté"
				t_level = LEVEL_OK
			"RECONNECTING", "SEARCHING":
				t_text = "recherche…"
				t_level = LEVEL_WARN
			"LOST":
				t_text = "perdu"
				t_level = LEVEL_ERROR
			_:
				t_text = "déconnecté"
				t_level = LEVEL_OFF

		out.append({
			"id": "trainer",
			"label": t_label,
			"status_text": t_text,
			"level": t_level
		})

		# 2. Click (liste de boîtiers)
		var clicks = devices.get("click", [])
		if clicks is Array:
			for c in clicks:
				if not (c is Dictionary):
					continue
				var side: String = str(c.get("side", "single"))
				var c_status: String = str(c.get("status", "LOST"))
				var bat = c.get("battery_pct", null)

				var side_label := ""
				match side:
					"plus":
						side_label = "+"
					"minus":
						side_label = "−"
					"single":
						side_label = ""

				var c_label := "Click" if side_label == "" else ("Click %s" % side_label)
				var c_text := ""
				var c_level := LEVEL_OK

				match c_status:
					"CONNECTED":
						if bat != null:
							c_text = "connecté, batterie %d %%" % int(bat)
							var b_int := int(bat)
							if b_int < 10:
								c_level = LEVEL_ERROR
							elif b_int < 20:
								c_level = LEVEL_WARN
							else:
								c_level = LEVEL_OK
						else:
							c_text = "connecté"
							c_level = LEVEL_OK
					"SEARCHING":
						c_text = "recherche…"
						c_level = LEVEL_WARN
					"LOST":
						c_text = "perdu"
						c_level = LEVEL_ERROR
					_:
						c_text = "déconnecté"
						c_level = LEVEL_OFF

				out.append({
					"id": "click_%s" % side,
					"label": c_label,
					"status_text": c_text,
					"level": c_level
				})

		# 3. Cardio
		var hr: Dictionary = _dict(devices.get("hr"))
		var hr_status: String = str(hr.get("status", "NONE"))
		var hr_source = hr.get("source", null)
		var hr_text := "absente"
		var hr_level := LEVEL_OFF

		match hr_status:
			"CONNECTED":
				if str(hr_source) == "strap":
					hr_text = "ceinture"
					hr_level = LEVEL_OK
				elif str(hr_source) == "trainer":
					hr_text = "par le trainer"
					hr_level = LEVEL_OK
				else:
					hr_text = "connecté"
					hr_level = LEVEL_OK
			"SEARCHING":
				hr_text = "recherche…"
				hr_level = LEVEL_WARN
			"LOST":
				hr_text = "perdue"
				hr_level = LEVEL_ERROR
			_: # "NONE" ou absent
				hr_text = "absente"
				hr_level = LEVEL_OFF

		out.append({
			"id": "hr",
			"label": "Cardio",
			"status_text": hr_text,
			"level": hr_level
		})

	else:
		# Repli contrat v1 sans l'objet devices
		var t_status: String = str(state.get("trainer_status", "LOST"))
		var t_text := "connecté"
		var t_level := LEVEL_OK
		match t_status:
			"CONNECTED", "MOCK":
				t_text = "connecté"
				t_level = LEVEL_OK
			"RECONNECTING":
				t_text = "recherche…"
				t_level = LEVEL_WARN
			"LOST":
				t_text = "perdu"
				t_level = LEVEL_ERROR
			_:
				t_text = "déconnecté"
				t_level = LEVEL_OFF

		out.append({
			"id": "trainer",
			"label": "Trainer",
			"status_text": t_text,
			"level": t_level
		})

		var inp_status: String = str(state.get("input_status", "KEYBOARD"))
		var inp_text := "connecté"
		var inp_level := LEVEL_OK
		match inp_status:
			"CONNECTED":
				inp_text = "connecté"
				inp_level = LEVEL_OK
			"KEYBOARD":
				inp_text = "clavier seul"
				inp_level = LEVEL_OK
			"LOST":
				inp_text = "perdu"
				inp_level = LEVEL_ERROR
			_:
				inp_text = "déconnecté"
				inp_level = LEVEL_OFF

		out.append({
			"id": "input",
			"label": "Commandes",
			"status_text": inp_text,
			"level": inp_level
		})

	return out


## Détecte les alertes à afficher une seule fois lors du passage d'un état à l'autre.
func alerts(prev_state: Dictionary, state: Dictionary) -> Array:
	if prev_state.is_empty():
		return []

	var out: Array = []
	var prev_dev: Dictionary = _dict(prev_state.get("devices"))
	var curr_dev: Dictionary = _dict(state.get("devices"))

	if curr_dev.is_empty() or prev_dev.is_empty():
		return []

	# 1. Vérification des boîtiers Click
	var prev_clicks: Array = _arr(prev_dev.get("click"))
	var curr_clicks: Array = _arr(curr_dev.get("click"))

	var prev_click_map := {}
	for c in prev_clicks:
		if c is Dictionary and c.has("side"):
			prev_click_map[str(c["side"])] = c

	for c in curr_clicks:
		if not (c is Dictionary) or not c.has("side"):
			continue
		var side: String = str(c["side"])
		var side_label := "+" if side == "plus" else ("−" if side == "minus" else "")
		var label := "Click" if side_label == "" else ("Click %s" % side_label)

		var cur_status: String = str(c.get("status", ""))
		var prev_c: Dictionary = _dict(prev_click_map.get(side))
		var prv_status: String = str(prev_c.get("status", ""))

		# Perte / Reconnexion
		if prv_status != "LOST" and cur_status == "LOST":
			out.append({
				"id": "click_%s_lost" % side,
				"text": "%s perdu" % label,
				"level": LEVEL_ERROR
			})
		elif prv_status == "LOST" and cur_status == "CONNECTED":
			out.append({
				"id": "click_%s_connected" % side,
				"text": "%s reconnecté" % label,
				"level": LEVEL_OK
			})

		# Seuils de batterie (sous 20 %, sous 10 %)
		var cur_bat = c.get("battery_pct", null)
		var prv_bat = prev_c.get("battery_pct", null)
		if cur_bat != null and prv_bat != null:
			var cb := int(cur_bat)
			var pb := int(prv_bat)

			# Passage sous 20 %
			if pb >= 20 and cb < 20 and cb >= 10:
				out.append({
					"id": "click_%s_bat_low" % side,
					"text": "Batterie %s faible (< 20 %%)" % label,
					"level": LEVEL_WARN
				})
			# Passage sous 10 %
			elif pb >= 10 and cb < 10:
				out.append({
					"id": "click_%s_bat_crit" % side,
					"text": "Batterie %s critique (< 10 %%)" % label,
					"level": LEVEL_ERROR
				})

	# 2. Ceinture cardio perdue (passage de strap à trainer ou status LOST)
	var prev_hr: Dictionary = _dict(prev_dev.get("hr"))
	var curr_hr: Dictionary = _dict(curr_dev.get("hr"))
	var prv_hr_source: String = str(prev_hr.get("source", ""))
	var cur_hr_source: String = str(curr_hr.get("source", ""))
	var prv_hr_status: String = str(prev_hr.get("status", ""))
	var cur_hr_status: String = str(curr_hr.get("status", ""))

	if prv_hr_source == "strap" and prv_hr_status == "CONNECTED":
		if cur_hr_status == "LOST" or cur_hr_source == "trainer":
			out.append({
				"id": "hr_lost",
				"text": "Ceinture cardio perdue",
				"level": LEVEL_WARN
			})

	return out


## Détermine si la séance peut démarrer : {ok, reason}.
func ready_to_ride(state: Dictionary) -> Dictionary:
	var devices = state.get("devices", null)
	var trainer_status := ""
	var has_click := false

	if devices is Dictionary and not devices.is_empty():
		var t: Dictionary = _dict(devices.get("trainer"))
		trainer_status = str(t.get("status", state.get("trainer_status", "LOST")))

		var clicks = devices.get("click", [])
		if clicks is Array:
			for c in clicks:
				if c is Dictionary and str(c.get("status", "")) == "CONNECTED":
					has_click = true
					break
	else:
		trainer_status = str(state.get("trainer_status", "LOST"))
		var inp: String = str(state.get("input_status", "KEYBOARD"))
		has_click = (inp == "CONNECTED")

	if trainer_status != "CONNECTED" and trainer_status != "MOCK":
		return {
			"ok": false,
			"reason": "Trainer non connecté" if trainer_status != "LOST" else "Trainer perdu"
		}

	if not has_click:
		return {
			"ok": true,
			"reason": "Click absent : clavier seul"
		}

	return {
		"ok": true,
		"reason": ""
	}


## Écran de connexion au démarrage (lot N13) : {all_ok, trainer_ok, missing, unilateral}.
## `all_ok` : trainer relié, tous les boîtiers du Click listés reliés et ceinture reliée si elle est
## configurée (statut autre que NONE). `missing` : noms des appareils pas encore reliés, pour « Passer ».
## `unilateral` : un seul des deux boîtiers du Click relié (le bouton « Passer » le dit).
## Sans objet `devices` (core v1) : trainer_status et input_status.
func connection(state: Dictionary) -> Dictionary:
	var missing: Array[String] = []
	var devices = state.get("devices", null)
	var trainer_ok := false
	var clicks_up := 0
	var clicks_total := 0
	if devices is Dictionary and not devices.is_empty():
		var t: Dictionary = _dict(devices.get("trainer"))
		trainer_ok = str(t.get("status", state.get("trainer_status", ""))) in ["CONNECTED", "MOCK"]
		for c in _arr(devices.get("click")):
			if not c is Dictionary:
				continue
			clicks_total += 1
			if str(c.get("status", "")) == "CONNECTED":
				clicks_up += 1
			else:
				match str(c.get("side", "single")):
					"plus":
						missing.append("Click +")
					"minus":
						missing.append("Click −")
					_:
						missing.append("Click")
		var hr_status := str(_dict(devices.get("hr")).get("status", "NONE"))
		if not hr_status in ["NONE", "CONNECTED"]:
			missing.append("ceinture")
	else:
		trainer_ok = str(state.get("trainer_status", "")) in ["CONNECTED", "MOCK"]
		var inp := str(state.get("input_status", "KEYBOARD"))
		if inp in ["SEARCHING", "LOST"]:
			missing.append("Click")
	if not trainer_ok:
		missing.push_front("trainer")
	return {"all_ok": missing.is_empty(), "trainer_ok": trainer_ok, "missing": missing,
		"unilateral": clicks_total >= 2 and clicks_up == 1}
