extends SceneTree

## Tests sans écran du modèle de l'écran « Appareils » `pairing_view_model.gd` (Lot N13 ; oublis du lot O24).
## Lancement : godot --headless --path engine --script res://tests/unit/test_pairing_view_model.gd

const PairingViewModel := preload("res://scripts/pairing_view_model.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _item(m, id: String) -> Dictionary:
	for it in m.menu_items():
		if it["id"] == id:
			return it
	return {}


const FOUND := [
	{"role": "trainer", "name": "HomeTrainer 0001", "address": "AA:00:00:00:00:01", "rssi": -50, "configured": true},
	{"role": "trainer", "name": "HomeTrainer 0002", "address": "AA:00:00:00:00:02", "rssi": -70, "configured": false},
	{"role": "hr_strap", "name": "Ceinture 1", "address": "BB:00:00:00:00:01", "rssi": -60, "configured": false},
	{"role": "click", "name": "Zwift Click", "address": "C1:1C:00:00:00:01", "rssi": -40, "configured": false},
]


func _init() -> void:
	var m = PairingViewModel.new()
	_check(_item(m, "save")["enabled"] == false and _item(m, "identify")["enabled"] == false,
			"rien trouvé : Enregistrer et Identifier inactifs")
	_check(m.handle("scan") == {"action": "scan_devices"} and m.scanning, "Rechercher : scan_devices")
	_check(_item(m, "scan")["label"] == "Recherche en cours…" and not _item(m, "scan")["enabled"], "recherche en cours affichée")
	m.on_scan_results({"done": false, "items": [], "plus_address": null})
	_check(m.scanning, "première réponse (done faux) : toujours en recherche")
	m.on_scan_results({"done": true, "items": FOUND, "plus_address": null})
	_check(not m.scanning and m.message == "4 appareil(s) trouvé(s)", "fin de recherche : %s" % m.message)
	_check(m.choice["trainer"] == "AA:00:00:00:00:01" and m.configured["trainer"] == "AA:00:00:00:00:01",
			"trainer déjà configuré choisi par défaut")
	_check(not m.has_changes() or m.changes()["trainer"] == null, "trainer inchangé : pas dans les changements")
	_check(m.choice["hr"] == "BB:00:00:00:00:01" and m.has_changes(), "ceinture trouvée : changement à enregistrer")
	m.handle("trainer")
	_check(m.choice["trainer"] == "AA:00:00:00:00:02", "valider Trainer : trainer suivant")
	m.handle("trainer")
	_check(m.choice["trainer"] == "" and _item(m, "trainer")["detail"] == "aucun (oublié)" and m.changes()["trainer"] == "",
			"puis « aucun » : le trainer enregistré sera oublié (lot O24)")
	m.handle("trainer")
	_check(m.choice["trainer"] == "AA:00:00:00:00:01", "et retour au premier (boucle)")
	m.handle("identify")
	_check(m.identifying and not _item(m, "identify")["enabled"] and not _item(m, "save")["enabled"],
			"identification en cours : boutons inactifs")
	m.on_scan_results({"done": true, "items": FOUND, "plus_address": null})
	_check(not m.identifying and "Aucun appui" in m.message, "pas d'appui sur + : message")
	m.handle("identify")
	m.on_scan_results({"done": true, "items": FOUND, "plus_address": "C1:1C:00:00:00:01"})
	_check(m.choice["click_plus"] == "C1:1C:00:00:00:01" and m.choice["click_minus"] == null,
			"un seul boîtier trouvé : + reconnu, − inconnu (unilatéral)")
	var save: Dictionary = m.handle("save")
	_check(save.get("action") == "confirm_pair" and save["args"]["click_plus"] == "C1:1C:00:00:00:01"
			and save["args"]["trainer"] == null and "ceinture Ceinture 1" in save["title"], "Enregistrer : %s" % str(save))
	m.on_error("pairing_failed", "refus")
	m.on_pair_acked()
	_check(not m.saved and _item(m, "relaunch").is_empty(), "erreur avant l'accusé : pas enregistré")
	m.handle("save")
	m.on_pair_acked()
	_check(m.saved and not _item(m, "relaunch").is_empty(), "accusé sans erreur : Relancer proposé")
	# Lot O24 : oublier la ceinture et le Click
	m.handle("hr")
	_check(m.choice["hr"] == "" and _item(m, "hr")["detail"] == "aucune (oubliée)", "Ceinture : « aucune » après la seule ceinture")
	m.handle("forget_click")
	_check(m.choice["click_plus"] == "" and m.choice["click_minus"] == "" and not _item(m, "forget_click")["enabled"],
			"Oublier le Click : les deux boîtiers")
	var forget: Dictionary = m.handle("save")
	_check(forget["args"]["hr"] == "" and forget["args"]["click_plus"] == "" and "l'oubli de la ceinture" in forget["title"]
			and "l'oubli du Click" in forget["title"], "Enregistrer les oublis : %s" % str(forget))
	m.on_pair_acked()
	_check(m.configured["hr"] == "" and _item(m, "hr")["detail"] == "aucune" and not m.has_changes(),
			"oubli enregistré : plus rien à écrire")
	m.handle("scan")
	_check(not _item(m, "forget_click")["enabled"] and not _item(m, "hr")["enabled"], "recherche : rôles inactifs")
	m.on_error("scan_failed", "Bluetooth éteint")
	_check(not m.scanning and m.message == "Bluetooth éteint", "scan_failed : recherche arrêtée et raison")
	_check(m.handle("back") == {"action": "back"} and m.handle("relaunch") == {"action": "relaunch"}, "Retour et Relancer")
	print("test_pairing_view_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
