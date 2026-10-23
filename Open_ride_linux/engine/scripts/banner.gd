extends Label

## Bandeau d'alerte en haut de l'écran : plusieurs messages peuvent être actifs, chacun sous une clé
## (core_lost, shutdown, error, route, command…), avec ou sans durée. Caché quand aucun n'est actif.
## Pas de class_name (script attaché dans main.tscn).

signal changed(text: String)

## clé -> {text, until_us} ; until_us = 0 pour un message sans échéance.
var _messages: Dictionary = {}
var _order: Array[String] = []


func _ready() -> void:
	visible = false


## Affiche (ou remplace) le message de la clé ; duration_s ≤ 0 : jusqu'à clear_message().
func show_message(key: String, msg: String, duration_s: float = 0.0) -> void:
	var until := 0
	if duration_s > 0.0:
		until = Time.get_ticks_usec() + int(duration_s * 1e6)
	if not _messages.has(key):
		_order.append(key)
	_messages[key] = {"text": msg, "until_us": until}
	_refresh()


func clear_message(key: String) -> void:
	if _messages.erase(key):
		_order.erase(key)
		_refresh()


func has_message(key: String) -> bool:
	return _messages.has(key)


## Vrai si le message de la clé a dépassé son échéance (ou n'existe pas).
func is_expired(key: String) -> bool:
	if not _messages.has(key):
		return true
	var until: int = _messages[key]["until_us"]
	return until > 0 and Time.get_ticks_usec() >= until


func _process(_delta: float) -> void:
	var now := Time.get_ticks_usec()
	var expired: Array[String] = []
	for key in _order:
		var until: int = _messages[key]["until_us"]
		if until > 0 and now >= until and not _messages[key].get("sticky", false):
			expired.append(key)
	for key in expired:
		clear_message(key)


## Garde le message après son échéance tant que sticky est vrai (erreur toujours d'actualité).
func set_sticky(key: String, sticky: bool) -> void:
	if _messages.has(key):
		_messages[key]["sticky"] = sticky


func _refresh() -> void:
	var lines: Array[String] = []
	for key in _order:
		lines.append(_messages[key]["text"])
	text = "\n".join(lines)
	visible = not lines.is_empty()
	changed.emit(text)
