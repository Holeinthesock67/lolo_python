extends SceneTree

## Tests sans écran des sons du mode « What the fuck » (série WTF, lot WTF7) : jingles rendus par
## wtf_sound_model.gd d'une trame `state` à l'autre, et leur synthèse (timbres `slide` et `noise`).
## Lancement : godot --headless --path engine --script res://tests/unit/test_wtf_sounds.gd

const M := preload("res://scripts/wtf/wtf_sound_model.gd")
const EventSounds := preload("res://scripts/event_sounds_model.gd")
const SoundPlayer := preload("res://scripts/sound_player.gd")

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


func _w(ev, points := 0, extra := {}) -> Dictionary:
	var out := {"points": points, "event": ev}
	out.merge(extra)
	return out


func _run() -> void:
	var m = M.new()
	_check(m.on_state(null).is_empty(), "hors mode WTF : rien")
	_check(m.on_state(_w({"id": "storm"})).is_empty(), "première trame du mode : rien, même avec un gag en cours")
	_check(m.on_state(_w({"id": "storm"})).is_empty(), "gag qui continue : rien")
	_check(m.on_state(_w(null, 100)) == ["wtf_win"], "fin d'un gag avec des points : arpège")
	_check(m.on_state(_w({"id": "gravity", "planet": "jupiter"}, 100)) == ["wtf_jupiter"], "Jupiter")
	_check(m.on_state(_w(null, 100)) == ["wtf_fail"], "fin d'un gag sans point : trombone triste")
	_check(m.on_state(_w({"id": "gravity", "planet": "moon"}, 100)) == ["wtf_moon"], "Lune")
	_check(m.on_state(_w({"id": "camera", "view": "snail"}, 150)) == ["wtf_win", "wtf_camera"],
		"un gag suit l'autre dans la même trame : fin puis début")

	var all_starts := {}
	for id in ["upside_down", "collapse", "cheese", "micro", "eggs", "tiny", "storm", "camera", "chef"]:
		var s = M.new()
		s.on_state(_w(null))
		var got: Array = s.on_state(_w({"id": id}))
		_check(got.size() == 1 and EventSounds.JINGLES.has(got[0]), "%s : un son de début connu (%s)" % [id, str(got)])
		all_starts[got[0]] = id
	_check(all_starts.size() == 9, "chaque gag a son propre son de début")

	m = M.new()
	m.on_state(_w({"id": "chef", "phase": "arrive"}))
	_check(m.on_state(_w({"id": "chef", "phase": "reveal", "dish": "chili"})) == ["wtf_cloche"], "le chef soulève sa cloche")
	_check(m.on_state(_w({"id": "chef", "phase": "eat", "dish": "chili"})).is_empty(), "le plat se mange : rien de plus")
	m = M.new()
	m.on_state(_w({"id": "eggs", "eggs": 6}))
	_check(m.on_state(_w({"id": "eggs", "eggs": 5})) == ["wtf_crack"], "œuf cassé")
	_check(m.on_state(_w({"id": "eggs", "eggs": 5})).is_empty(), "pas de nouvel œuf cassé : rien")
	m = M.new()
	m.on_state(_w({"id": "cheese", "squashed": false}))
	_check(m.on_state(_w({"id": "cheese", "squashed": true})) == ["wtf_splat"], "écrasé par le fromage")
	_check(m.on_state(_w({"id": "cheese", "squashed": true})).is_empty(), "toujours écrasé : un seul son")
	m = M.new()
	m.on_state(_w({"id": "micro", "results": []}))
	_check(m.on_state(_w({"id": "micro", "results": [true]})) == ["wtf_round_ok"], "manche gagnée")
	_check(m.on_state(_w({"id": "micro", "results": [true, false]})) == ["wtf_round_fail"], "manche perdue")

	m = M.new()
	m.on_state(_w(null, 0, {"kata": {"count": 3, "bonks": 0}, "attack": null, "fish": false}))
	_check(m.on_state(_w(null, 0, {"kata": {"count": 4, "bonks": 0}, "attack": null, "fish": false})) == ["wtf_pop"],
		"Katamari : objet ramassé")
	_check(m.on_state(_w(null, 0, {"kata": {"count": 4, "bonks": 1}, "attack": null, "fish": false})) == ["wtf_boing"],
		"Katamari : objet trop gros, boing")
	_check(m.on_state(_w(null, 0, {"kata": {"count": 4, "bonks": 1}, "attack": "b2", "fish": true})) == ["wtf_horn", "wtf_fish"],
		"mamie qui attaque et pluie de poissons")
	_check(m.on_state(_w({"id": "storm"}, 0, {"kata": {"count": 5, "bonks": 1}, "attack": "b2", "fish": true})).size()
		<= M.MAX_PER_FRAME, "au plus deux sons par trame")
	_check(m.on_state(_w({"id": "storm"}, 0, {"kata": {"count": 5, "bonks": 1}, "attack": "b2", "fish": true})).is_empty(),
		"attaque et poissons qui durent : un seul son")
	m.on_state(null)
	_check(m.on_state(_w({"id": "storm"})).is_empty(), "nouvelle séance WTF : rien à la première trame")

	# Synthèse des sons du mode : non bouclés, brefs, sans écrêtage (timbres slide et noise compris).
	var sp = SoundPlayer.new()
	var wtf_count := 0
	for jingle in EventSounds.JINGLES:
		if not str(jingle).begins_with("wtf_"):
			continue
		wtf_count += 1
		var wav: AudioStreamWAV = sp.stream(jingle)
		var peak := 0
		for i in range(0, wav.data.size(), 2):
			peak = maxi(peak, absi(wav.data.decode_s16(i)))
		_check(wav.loop_mode == AudioStreamWAV.LOOP_DISABLED and EventSounds.duration_s(jingle) < 1.6
			and peak > 20000 and peak < 32767, "%s : %.2f s, pic %d" % [jingle, EventSounds.duration_s(jingle), peak])
	_check(wtf_count == 22, "22 sons du mode WTF (%d)" % wtf_count)
	sp.free()

	print("test_wtf_sounds : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
