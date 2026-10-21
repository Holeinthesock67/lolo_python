class_name IpcClient
extends Node

## Client IPC UDP localhost pour OpenRide Engine (Contrat IPC v1).
## Écoute sur port 5005 (state, input, hello_ack, etc.) et émet vers 5006 (hello, heartbeat, cmd, bye).

signal state_received(state_dict: Dictionary)
signal input_event_received(event_name: String)
signal hello_ack_received(ack_dict: Dictionary)

const CONTRACT_VERSION := 1
const PORT_STATE := 5005
const PORT_COMMANDS := 5006
const SERVER_HOST := "127.0.0.1"

var _peer := PacketPeerUDP.new()
var _heartbeat_timer := 0.0
var _cmd_id_counter := 0
var last_state_seq := -1


func _ready() -> void:
	var err := _peer.bind(PORT_STATE, SERVER_HOST)
	if err != OK:
		push_error("Impossible d'attacher le port UDP " + str(PORT_STATE) + ": " + str(err))
	else:
		print("IpcClient attaché sur ", SERVER_HOST, ":", PORT_STATE)
		send_hello()


func _process(delta: float) -> void:
	_heartbeat_timer += delta
	if _heartbeat_timer >= 0.5: # 2 Hz
		_heartbeat_timer = 0.0
		send_heartbeat()
	
	_poll_incoming()


func _poll_incoming() -> void:
	while _peer.get_available_packet_count() > 0:
		var pkt := _peer.get_packet()
		var text := pkt.get_string_from_utf8()
		var json_obj = JSON.parse_string(text)
		if typeof(json_obj) != TYPE_DICTIONARY:
			continue
		
		var msg_type: String = json_obj.get("type", "")
		match msg_type:
			"state":
				var seq: int = int(json_obj.get("seq", 0))
				if seq > last_state_seq:
					last_state_seq = seq
					state_received.emit(json_obj)
			"input":
				var ev_name: String = json_obj.get("event", "")
				input_event_received.emit(ev_name)
			"hello_ack":
				hello_ack_received.emit(json_obj)


func _send_json(dict: Dictionary) -> void:
	var payload := JSON.stringify(dict).to_utf8_buffer()
	_peer.set_dest_address(SERVER_HOST, PORT_COMMANDS)
	_peer.put_packet(payload)


func send_hello() -> void:
	_send_json({
		"type": "hello",
		"v": CONTRACT_VERSION,
		"engine_version": "0.1.0"
	})


func send_heartbeat() -> void:
	_send_json({
		"type": "heartbeat",
		"v": CONTRACT_VERSION,
		"seq": Time.get_ticks_msec(),
		"fps": Performance.get_monitor(Performance.TIME_FPS)
	})


func send_command(cmd_name: String, args: Dictionary = {}) -> int:
	_cmd_id_counter += 1
	_send_json({
		"type": "cmd",
		"v": CONTRACT_VERSION,
		"cmd_id": _cmd_id_counter,
		"name": cmd_name,
		"args": args
	})
	return _cmd_id_counter


func _exit_tree() -> void:
	_send_json({
		"type": "bye",
		"v": CONTRACT_VERSION
	})
	_peer.close()
