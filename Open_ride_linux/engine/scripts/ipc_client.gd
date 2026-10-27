extends Node

## Client IPC UDP localhost pour OpenRide Engine (Contrat IPC v1).
## Écoute sur le port d'état (5005 par défaut : state, input, hello_ack, error, shutdown) et émet
## vers le port de commandes (5006 par défaut : hello, heartbeat, cmd, bye). Ports lus par engine_args.gd.

signal state_received(state_dict: Dictionary)
signal input_event_received(event_name: String)
signal hello_ack_received(ack_dict: Dictionary)
signal error_received(code: String, message: String)
signal shutdown_received
signal core_lost
signal core_returned
signal command_acked(cmd_name: String, cmd_id: int)
signal command_failed(cmd_name: String)
## Listes v1.1 (routes et workouts, lot N3)
signal routes_received(items: Array, msg: Dictionary)
signal workouts_received(items: Array, msg: Dictionary)
signal list_failed(list_name: String, error_message: String)
## Résultat d'une recherche d'appareils ou de l'identification du « + » (lot N13, contrat v1.2).
signal scan_results_received(msg: Dictionary)
## Réglages du menu (lots O3 et O4, contrat v1.3), réponse à list_settings ou set_setting.
signal settings_received(msg: Dictionary)
## Message de test autre que send_command (seulement avec --test-mode), traité par main.gd (captures d'écran).
signal test_message_received(msg: Dictionary)

const EngineArgs := preload("res://scripts/engine_args.gd")

const CONTRACT_VERSION := 1
## Révision du contrat annoncée dans hello (champ facultatif rev, révision 1.3).
const CONTRACT_REV := "1.3"
## Version de l'engine, lue dans project.godot (source unique : fichier VERSION, lot O2).
var engine_version: String = str(ProjectSettings.get_setting("application/config/version", "0.0.0"))
const SERVER_HOST := "127.0.0.1"
const HELLO_PERIOD_S := 1.0
const CMD_RESEND_US := 200_000        # contrat §4 : renvoi toutes les 200 ms
const CMD_TIMEOUT_US := 3_000_000     # contrat §4 : abandon après 3 s
const CORE_TIMEOUT_US := 1_000_000    # contrat §6 : core injoignable après 1 s sans state

var state_port: int = EngineArgs.DEFAULT_STATE_PORT
var cmd_port: int = EngineArgs.DEFAULT_CMD_PORT
var test_mode := false

## Configuration reçue dans hello_ack (ftp_w, gears_total, theme) ; vide tant que le core n'a pas répondu.
var core_config: Dictionary = {}
var core_version: String = ""
## Révision du contrat annoncée par le core (vide : core antérieur à la révision 1.3).
var core_rev: String = ""
var last_state_seq := -1
## Diagnostic (contrat §6) : trames sautées (trous de seq) et trames arrivées en retard, ignorées.
var seq_gap_count := 0
var late_state_count := 0
var invalid_datagram_count := 0

var _peer := PacketPeerUDP.new()
var _cmd_id_counter := 0
## Commandes en attente d'accusé : {cmd_id, name, args, first_us, last_us, sends}.
var _pending: Array[Dictionary] = []
## Relance des listes v1.1 (contrat §4) : une seconde sans réponse complète, 3 fois au plus.
const LIST_RETRY_S := 1.0
const LIST_MAX_RETRIES := 3
var _pending_list_routes: Dictionary = {}
var _pending_list_workouts: Dictionary = {}
var _hello_acked := false
var _hello_timer := 0.0
var _last_state_us := 0
var _core_reachable := true
var _hb_thread: Thread
var _hb_stop := false
var _bound := false


func _ready() -> void:
	var cfg := EngineArgs.current()
	state_port = cfg["state_port"]
	cmd_port = cfg["cmd_port"]
	test_mode = cfg["test_mode"]
	var err := _peer.bind(state_port, SERVER_HOST)
	if err != OK:
		# Contrat §2 : port occupé, arrêt avec un message explicite.
		printerr("Port UDP %d indisponible (code %d) : un autre engine tourne-t-il déjà ? "
				% [state_port, err] + "Choisir un autre port avec -- --ipc-state-port=N.")
		get_tree().quit(1)
		return
	_bound = true
	print("IpcClient attaché sur ", SERVER_HOST, ":", state_port, ", commandes vers le port ", cmd_port)
	_last_state_us = Time.get_ticks_usec()
	send_hello()
	# Heartbeat dans un fil séparé : il prouve que le programme est vivant même si le rendu
	# saccade ou se bloque (fenêtre masquée, vsync…). Socket propre à ce fil.
	_hb_thread = Thread.new()
	_hb_thread.start(_heartbeat_loop)


func _heartbeat_loop() -> void:
	var sock := PacketPeerUDP.new()
	sock.set_dest_address(SERVER_HOST, cmd_port)
	var seq := 0
	while not _hb_stop:
		seq += 1
		var payload := JSON.stringify({
			"type": "heartbeat",
			"v": CONTRACT_VERSION,
			"seq": seq,
			"fps": Engine.get_frames_per_second()
		}).to_utf8_buffer()
		sock.put_packet(payload)
		OS.delay_msec(500)
	sock.close()


## Ligne de journal pour les tests sans écran (format « [test] clé=valeur »), seulement avec --test-mode.
func test_log(text: String) -> void:
	if test_mode:
		print("[test] ", text)


func is_core_reachable() -> bool:
	return _core_reachable


func is_hello_acked() -> bool:
	return _hello_acked


func pending_count() -> int:
	return _pending.size()


func _process(delta: float) -> void:
	if not _bound:
		return
	# Diagnostic : un gel de l'engine (rendu bloqué, fenêtre masquée…) coupe les heartbeats.
	if delta > 0.4:
		print("[diag] gel de l'engine : image de %.2f s (FPS moyen %d)" % [delta, Engine.get_frames_per_second()])
	_poll_incoming()
	var now := Time.get_ticks_usec()
	# Contrat §6 : plus de state depuis 1 s, core injoignable ; hello toutes les secondes.
	if _core_reachable and now - _last_state_us > CORE_TIMEOUT_US:
		_core_reachable = false
		if _hello_acked:
			_hello_acked = false
			_hello_timer = HELLO_PERIOD_S   # hello dès maintenant ; sinon le rythme en cours continue
		# Un core relancé repart de seq = 0 : on accepte de nouveau toutes les trames.
		last_state_seq = -1
		print("Core non joignable (aucune trame depuis %.1f s)" % ((now - _last_state_us) / 1e6))
		test_log("core_lost age_ms=%d" % ((now - _last_state_us) / 1000))
		core_lost.emit()
	# Contrat §5 : hello répété chaque seconde jusqu'au hello_ack.
	if not _hello_acked:
		_hello_timer += delta
		if _hello_timer >= HELLO_PERIOD_S:
			_hello_timer = 0.0
			send_hello()
	# Relances des listes (lot N3, contrat v1.1 §4) : sans réponse complète une seconde après la demande
	# ou après la dernière partie reçue, nouvelle demande avec un nouveau cmd_id, 3 fois au plus.
	_tick_list(_pending_list_routes, "list_routes", "routes",
		"Aucune réponse pour la liste des parcours après 3 tentatives", delta)
	_tick_list(_pending_list_workouts, "list_workouts", "workouts",
		"Aucune réponse pour la liste des entraînements après 3 tentatives", delta)

	_resend_pending(now)


func _poll_incoming() -> void:
	while _peer.get_available_packet_count() > 0:
		var pkt := _peer.get_packet()
		var json_obj = JSON.parse_string(pkt.get_string_from_utf8())
		if typeof(json_obj) != TYPE_DICTIONARY:
			invalid_datagram_count += 1
			print("[diag] datagramme illisible ignoré (total %d)" % invalid_datagram_count)
			continue
		var msg_type := str(json_obj.get("type", ""))
		match msg_type:
			"state":
				_on_state(json_obj)
			"input":
				input_event_received.emit(str(json_obj.get("event", "")))
			"hello_ack":
				_hello_acked = true
				var cfg = json_obj.get("config", {})
				core_config = cfg if typeof(cfg) == TYPE_DICTIONARY else {}
				core_version = str(json_obj.get("core_version", ""))
				var rev = json_obj.get("rev", "")
				core_rev = rev if typeof(rev) == TYPE_STRING else ""
				if core_rev != CONTRACT_REV:
					# Même version majeure : compatible, les champs inconnus sont ignorés (contrat §8).
					print("Révisions du contrat différentes : core %s, engine %s"
						% [core_rev if core_rev != "" else "avant 1.3", CONTRACT_REV])
				print("hello_ack reçu : core ", core_version, ", configuration ", core_config)
				test_log("hello_ack config=%s" % JSON.stringify(core_config))
				hello_ack_received.emit(json_obj)
			"error":
				var code := str(json_obj.get("code", ""))
				var message := str(json_obj.get("message", ""))
				print("Erreur du core : ", code, " : ", message)
				error_received.emit(code, message)
			"shutdown":
				print("Le core s'est arrêté ; retour à l'attente.")
				test_log("shutdown")
				_hello_acked = false
				_hello_timer = HELLO_PERIOD_S   # hello dès l'image suivante, puis chaque seconde
				last_state_seq = -1
				shutdown_received.emit()
			"routes":
				_on_list_part(_pending_list_routes, "routes", json_obj)
			"workouts":
				_on_list_part(_pending_list_workouts, "workouts", json_obj)
			"scan_results":
				scan_results_received.emit(json_obj)
			"settings":
				settings_received.emit(json_obj)
			"_test":
				if test_mode:
					_on_test_message(json_obj)


func _on_state(msg: Dictionary) -> void:
	var seq := int(msg.get("seq", 0))
	if seq <= last_state_seq:
		# Contrat §3 et §6 : seule la trame au seq le plus élevé compte.
		late_state_count += 1
		test_log("state_late seq=%d late=%d" % [seq, late_state_count])
		return
	if last_state_seq >= 0 and seq > last_state_seq + 1:
		seq_gap_count += seq - last_state_seq - 1
	last_state_seq = seq
	_last_state_us = Time.get_ticks_usec()
	if not _core_reachable:
		_core_reachable = true
		print("Core de nouveau joignable.")
		test_log("core_returned")
		core_returned.emit()
	_ack_pending(int(msg.get("last_cmd_id", 0)))
	state_received.emit(msg)


## Messages de test (type « _test », seulement avec --test-mode) : permettent au faux core de
## déclencher une commande sans clavier, ou une capture d'écran (action « screenshot », traitée par
## main.gd, tests graphiques de tests/visual_check.py). Hors mode test, ce type inconnu est ignoré (contrat §1).
func _on_test_message(msg: Dictionary) -> void:
	if str(msg.get("action", "")) == "send_command":
		var args = msg.get("args", {})
		send_command(str(msg.get("name", "")), args if typeof(args) == TYPE_DICTIONARY else {})
	else:
		test_message_received.emit(msg)


func _send_json(dict: Dictionary) -> void:
	var payload := JSON.stringify(dict).to_utf8_buffer()
	_peer.set_dest_address(SERVER_HOST, cmd_port)
	var err := _peer.put_packet(payload)
	if err != OK:
		print("[diag] envoi UDP en échec (code ", err, ") : ", dict.get("type", "?"))


## Demande la liste des parcours au core (lot N3, contrat v1.1). Réponse : signal routes_received.
func list_routes() -> int:
	var cmd_id := send_command("list_routes", {})
	_reset_list_request(_pending_list_routes, cmd_id)
	return cmd_id


## Demande la liste des entraînements au core (lot N3, contrat v1.1). Réponse : signal workouts_received.
func list_workouts() -> int:
	var cmd_id := send_command("list_workouts", {})
	_reset_list_request(_pending_list_workouts, cmd_id)
	return cmd_id


## Modifie la difficulté du trainer pendant la séance (lot Q1, contrat v1.2).
func send_set_difficulty(pct: int) -> int:
	return send_command("set_difficulty", {"pct": pct})


## Appairage depuis le menu (lot N13, contrat v1.2) : recherche, identification du « + », enregistrement.
func scan_devices(timeout_s: float = 8.0) -> int:
	return send_command("scan_devices", {"timeout_s": timeout_s})


func identify_click_plus() -> int:
	return send_command("identify_click_plus", {})


func pair_devices(args: Dictionary) -> int:
	return send_command("pair_devices", args)


## Réglages du menu (lots O3 et O4, contrat v1.3).
func list_settings() -> int:
	return send_command("list_settings", {})


func set_setting(key: String, value) -> int:
	return send_command("set_setting", {"key": key, "value": value})


## Demande en cours : {cmd_id (dernier envoyé), cmd_ids, retries, timer, answers}. `answers` range les parties
## reçues par request_cmd_id : {request_cmd_id: {parts, got: {part: items}, truncated}}. Le dictionnaire est
## modifié sur place (pas réaffecté) pour que les références gardées par _process restent valables.
static func _reset_list_request(req: Dictionary, cmd_id: int) -> void:
	req.clear()
	req.merge({"cmd_id": cmd_id, "cmd_ids": [cmd_id], "retries": 0, "timer": 0.0, "answers": {}})


func _tick_list(req: Dictionary, cmd_name: String, list_name: String, error_message: String, delta: float) -> void:
	if req.is_empty():
		return
	req["timer"] = float(req.get("timer", 0.0)) + delta
	if req["timer"] < LIST_RETRY_S:
		return
	req["timer"] = 0.0
	req["retries"] = int(req.get("retries", 0)) + 1
	if req["retries"] > LIST_MAX_RETRIES:
		req.clear()
		list_failed.emit(list_name, error_message)
		return
	var cid := send_command(cmd_name, {})
	req["cmd_id"] = cid
	if not req.has("cmd_ids"):
		req["cmd_ids"] = []
	req["cmd_ids"].append(cid)


## Une partie de `routes` ou `workouts` : rangée sous son request_cmd_id ; liste émise quand toutes les
## parties d'une même réponse sont là. Une réponse à une demande qui n'est plus en cours est ignorée.
func _on_list_part(req: Dictionary, list_name: String, msg: Dictionary) -> void:
	if req.is_empty():
		return
	var rid := int(msg.get("request_cmd_id", -1))
	if not rid in req.get("cmd_ids", [req.get("cmd_id", -1)]):
		return
	var parts := maxi(1, int(msg.get("parts", 1)))
	var part := int(msg.get("part", 1))
	if part < 1 or part > parts:
		return
	if not req.has("answers"):
		req["answers"] = {}
	var answers: Dictionary = req["answers"]
	if not answers.has(rid) or int(answers[rid]["parts"]) != parts:
		answers[rid] = {"parts": parts, "got": {}, "truncated": false}
	var answer: Dictionary = answers[rid]
	var raw_items = msg.get("items", [])
	answer["got"][part] = raw_items if raw_items is Array else []
	answer["truncated"] = bool(answer["truncated"]) or bool(msg.get("truncated", false))
	req["timer"] = 0.0   # une seconde de plus pour la partie suivante
	if answer["got"].size() < parts:
		return
	var items: Array = []
	for i in range(1, parts + 1):
		items.append_array(answer["got"][i])
	var whole := {"type": list_name, "request_cmd_id": rid, "parts": parts, "items": items,
		"truncated": answer["truncated"]}
	req.clear()
	if list_name == "routes":
		routes_received.emit(items, whole)
	else:
		workouts_received.emit(items, whole)


func send_hello() -> void:
	_send_json({
		"type": "hello",
		"v": CONTRACT_VERSION,
		"rev": CONTRACT_REV,
		"engine_version": engine_version
	})


## Envoie une commande avec accusé (contrat §4) : renvoi toutes les 200 ms jusqu'à ce qu'un state
## porte last_cmd_id ≥ cmd_id, abandon après 3 s (signal command_failed). Renvoie le cmd_id.
func send_command(cmd_name: String, args: Dictionary = {}) -> int:
	_cmd_id_counter += 1
	var now := Time.get_ticks_usec()
	var cmd := {"cmd_id": _cmd_id_counter, "name": cmd_name, "args": args,
			"first_us": now, "last_us": now, "sends": 1}
	_pending.append(cmd)
	_send_cmd(cmd)
	test_log("cmd_sent name=%s id=%d" % [cmd_name, _cmd_id_counter])
	return _cmd_id_counter


func _send_cmd(cmd: Dictionary) -> void:
	_send_json({
		"type": "cmd",
		"v": CONTRACT_VERSION,
		"cmd_id": cmd["cmd_id"],
		"name": cmd["name"],
		"args": cmd["args"]
	})


func _ack_pending(last_cmd_id: int) -> void:
	var kept: Array[Dictionary] = []
	for cmd in _pending:
		if int(cmd["cmd_id"]) <= last_cmd_id:
			test_log("cmd_acked name=%s id=%d sends=%d" % [cmd["name"], cmd["cmd_id"], cmd["sends"]])
			command_acked.emit(cmd["name"], cmd["cmd_id"])
		else:
			kept.append(cmd)
	_pending = kept


func _resend_pending(now: int) -> void:
	var kept: Array[Dictionary] = []
	for cmd in _pending:
		if now - int(cmd["first_us"]) >= CMD_TIMEOUT_US:
			# Un appui abandonné n'est pas rejoué : la commande est simplement oubliée.
			print("Commande « %s » (id %d) abandonnée : aucun accusé du core en 3 s" % [cmd["name"], cmd["cmd_id"]])
			test_log("cmd_failed name=%s id=%d after_ms=%d sends=%d"
					% [cmd["name"], cmd["cmd_id"], (now - int(cmd["first_us"])) / 1000, cmd["sends"]])
			command_failed.emit(cmd["name"])
			continue
		if now - int(cmd["last_us"]) >= CMD_RESEND_US:
			cmd["last_us"] = now
			cmd["sends"] = int(cmd["sends"]) + 1
			_send_cmd(cmd)
		kept.append(cmd)
	_pending = kept


func _exit_tree() -> void:
	if not _bound:
		return
	_hb_stop = true
	if _hb_thread:
		_hb_thread.wait_to_finish()
	_send_json({
		"type": "bye",
		"v": CONTRACT_VERSION
	})
	_peer.close()
