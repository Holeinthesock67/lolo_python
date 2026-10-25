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
## Message de test autre que send_command (seulement avec --test-mode), traité par main.gd (captures d'écran).
signal test_message_received(msg: Dictionary)

const EngineArgs := preload("res://scripts/engine_args.gd")

const CONTRACT_VERSION := 1
const ENGINE_VERSION := "0.1.0"
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
var last_state_seq := -1
## Diagnostic (contrat §6) : trames sautées (trous de seq) et trames arrivées en retard, ignorées.
var seq_gap_count := 0
var late_state_count := 0
var invalid_datagram_count := 0

var _peer := PacketPeerUDP.new()
var _cmd_id_counter := 0
## Commandes en attente d'accusé : {cmd_id, name, args, first_us, last_us, sends}.
var _pending: Array[Dictionary] = []
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
	# Gestion des relances de listes (lot N3 : redemande après 1 s, 3 fois au plus)
	if not _pending_list_routes.is_empty():
		_pending_list_routes["timer"] = float(_pending_list_routes.get("timer", 0.0)) + delta
		if _pending_list_routes["timer"] >= 1.0:
			_pending_list_routes["timer"] = 0.0
			_pending_list_routes["retries"] = int(_pending_list_routes.get("retries", 0)) + 1
			if _pending_list_routes["retries"] <= 3:
				var cid := send_command("list_routes", {})
				_pending_list_routes["cmd_id"] = cid
			else:
				var err_msg := "Aucune réponse pour la liste des parcours après 3 tentatives"
				_pending_list_routes.clear()
				list_failed.emit("routes", err_msg)

	if not _pending_list_workouts.is_empty():
		_pending_list_workouts["timer"] = float(_pending_list_workouts.get("timer", 0.0)) + delta
		if _pending_list_workouts["timer"] >= 1.0:
			_pending_list_workouts["timer"] = 0.0
			_pending_list_workouts["retries"] = int(_pending_list_workouts.get("retries", 0)) + 1
			if _pending_list_workouts["retries"] <= 3:
				var cid := send_command("list_workouts", {})
				_pending_list_workouts["cmd_id"] = cid
			else:
				var err_msg := "Aucune réponse pour la liste des entraînements après 3 tentatives"
				_pending_list_workouts.clear()
				list_failed.emit("workouts", err_msg)

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
				_pending_list_routes.clear()
				var r_items: Array = json_obj.get("items", [])
				routes_received.emit(r_items, json_obj)
			"workouts":
				_pending_list_workouts.clear()
				var w_items: Array = json_obj.get("items", [])
				workouts_received.emit(w_items, json_obj)
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


## Demande la liste des parcours au core (lot N3, contrat v1.1).
func list_routes() -> int:
	var cmd_id := send_command("list_routes", {})
	_pending_list_routes = {"cmd_id": cmd_id, "retries": 0, "timer": 0.0}
	return cmd_id


## Demande la liste des entraînements au core (lot N3, contrat v1.1).
func list_workouts() -> int:
	var cmd_id := send_command("list_workouts", {})
	_pending_list_workouts = {"cmd_id": cmd_id, "retries": 0, "timer": 0.0}
	return cmd_id


func send_hello() -> void:
	_send_json({
		"type": "hello",
		"v": CONTRACT_VERSION,
		"engine_version": ENGINE_VERSION
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
