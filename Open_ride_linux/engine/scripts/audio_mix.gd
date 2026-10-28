extends RefCounted

## Volumes du menu Réglages (section `[audio]` de config.toml, réglages `audio.*` du message `settings`).
##
## Catégories de volume (noms fixés pour tous les lots qui ajoutent des sons, voir docs/AUDIO.md) ;
## chaque catégorie est un bus audio envoyé au bus Master (volume général) :
## - `Ride` : vent dans les oreilles, roue libre, « clac » de reprise (sound_player.gd) ;
## - `Ambience` : fonds d'ambiance, cloches, points sonores (sound_player.gd), véhicules
##   (traffic_renderer.gd), foule et passants (crowd_renderer.gd) ;
## - `Events` : bips d'appui du Click, bip de changement de bloc ERG, consignes d'essai (main.gd),
##   et plus tard les jingles d'événements (sommet de col, arche, fin de sprint, fin de séance) ;
## - réservés au mode Cyber-Rogue (lot R18) : `RogueSfx` (`audio.rogue_sfx_pct`) et `RogueMusic`
##   (`audio.rogue_music_pct`), créés par ce lot sur le même modèle.
## Chaque lecteur prend son bus par `bus(groupe)`, qui crée les bus à la première demande.
## Un volume va de 0 (bus coupé) à 100 % (niveau d'origine) ; la courbe est quadratique
## (50 % ≈ −12 dB), plus proche de l'oreille qu'une échelle linéaire d'amplitude.
## Pas de class_name : charger par preload("res://scripts/audio_mix.gd").

const MASTER := &"Master"
const RIDE := &"Ride"
const AMBIENCE := &"Ambience"
const EVENTS := &"Events"
## Clé du réglage (message `settings`) -> bus réglé.
const SETTING_BUSES := {
	"audio.master_pct": MASTER,
	"audio.ride_pct": RIDE,
	"audio.ambience_pct": AMBIENCE,
	"audio.events_pct": EVENTS,
}


## Crée les bus manquants (sans effet s'ils existent déjà).
static func ensure_buses() -> void:
	for b in [RIDE, AMBIENCE, EVENTS]:
		if AudioServer.get_bus_index(b) >= 0:
			continue
		AudioServer.add_bus()
		var i := AudioServer.bus_count - 1
		AudioServer.set_bus_name(i, b)
		AudioServer.set_bus_send(i, MASTER)


## Nom du bus d'un groupe (RIDE, AMBIENCE ou EVENTS), bus créés au besoin.
static func bus(group: StringName) -> StringName:
	ensure_buses()
	return group


## Gain en dB d'un volume en % (0 : silence, coupé par `apply`).
static func pct_to_db(pct: int) -> float:
	var x := clampf(pct / 100.0, 0.0, 1.0)
	return linear_to_db(x * x) if x > 0.0 else -80.0


## Volume en % d'un bus (lecture, tests).
static func volume_pct(bus_name: StringName) -> int:
	var i := AudioServer.get_bus_index(bus_name)
	if i < 0 or AudioServer.is_bus_mute(i):
		return 0
	return int(round(sqrt(db_to_linear(AudioServer.get_bus_volume_db(i))) * 100.0))


## Règle un bus à `pct` % ; 0 coupe le bus.
static func set_volume(bus_name: StringName, pct: int) -> void:
	ensure_buses()
	var i := AudioServer.get_bus_index(bus_name)
	if i < 0:
		return
	pct = clampi(pct, 0, 100)
	AudioServer.set_bus_mute(i, pct == 0)
	AudioServer.set_bus_volume_db(i, pct_to_db(pct))


## Applique les volumes présents dans la liste `settings` (éléments {key, value}) ; renvoie le nombre
## de bus réglés.
static func apply_settings(items: Array) -> int:
	var n := 0
	for it in items:
		if not it is Dictionary or not SETTING_BUSES.has(str(it.get("key", ""))):
			continue
		var v = it.get("value")
		if v is int or v is float:
			set_volume(SETTING_BUSES[str(it["key"])], int(v))
			n += 1
	return n
