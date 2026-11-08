extends SceneTree

## Export des fonds d'ambiance pour l'écoute (lot U11) : dans le dossier donné après `--`, pour chaque biome du
## thème par défaut une scène de SCENE_S secondes (tous les fonds au niveau que leur donne AmbienceModel : 100 %
## du biome, été, midi, voisinage de `SCENES`, phrases d'oiseaux comprises), puis chaque fond de biome seul, à
## son niveau plein (fichiers `fond_<nom>.wav`). WAV mono 16 bits à AmbienceSynth.MIX_RATE.
## Chaque scène est ramenée au même niveau d'écoute (LISTEN_RMS_DB) ; `scenes.csv` donne les niveaux du jeu.
## godot --headless --path engine --script res://tests/ambience_export.gd -- DOSSIER

const AmbienceModel := preload("res://scripts/ambience_model.gd")
const AmbienceSynth := preload("res://scripts/ambience_synth.gd")

const SCENE_S := 20.0
const SOLO_S := 12.0
const LISTEN_RMS_DB := -20.0
## Voisinage de chaque scène (part de forêt et de bâti, eau, mer, altitude, vent) : un paysage plausible du biome.
const SCENES := {
	"temperate_grassland": {"forest_share": 0.2},
	"temperate_forest": {"forest_share": 0.8},
	"farmland": {"forest_share": 0.1, "built_share": 0.1},
	"boreal_forest": {"forest_share": 0.8, "wind_strength": 0.5},
	"alpine": {"forest_share": 0.3, "alt_m": 1600.0, "wind_strength": 0.4},
	"tundra": {"alt_m": 300.0, "wind_strength": 0.6},
	"polar": {"wind_strength": 0.6},
	"mediterranean": {"forest_share": 0.2, "built_share": 0.05},
	"steppe": {"wind_strength": 0.5},
	"savanna": {"forest_share": 0.1},
	"sand_desert": {"wind_strength": 0.6},
	"rock_desert": {"wind_strength": 0.4},
	"jungle": {"forest_share": 0.9},
	"wetland": {"forest_share": 0.2, "water_dist_m": 30.0, "water_kind": "stream"},
	"coast": {"sea_dist_m": 40.0, "wind_strength": 0.5, "built_share": 0.05},
	"volcanic": {"alt_m": 900.0, "wind_strength": 0.3},
}


func _init() -> void:
	call_deferred("_run")


func _save(path: String, buf: PackedFloat32Array) -> void:
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = AmbienceSynth.MIX_RATE
	wav.stereo = false
	wav.data = AmbienceSynth.pcm16(buf)
	wav.save_to_wav(path)


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.is_empty():
		printerr("dossier de sortie manquant (après --)")
		quit(2)
		return
	var out_dir := args[0]
	DirAccess.make_dir_recursive_absolute(out_dir)
	var theme: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://themes/default/theme.json"))
	var loops := {}
	for bed in AmbienceModel.BEDS:
		loops[bed] = AmbienceSynth.bed_samples(bed)
	var rate := AmbienceSynth.MIX_RATE
	var lines := ["biome;fonds audibles (dB)"]
	for biome in SCENES:
		var m = AmbienceModel.new()
		m.voices = 8   # qualité high
		m.set_theme(theme)
		var neigh := {"forest_share": 0.0, "built_share": 0.0, "water_dist_m": INF, "water_kind": "", "alt_m": 200.0,
			"solar_hour": 12.0, "rain": 0.0, "wind_strength": 0.2, "paused": false, "season": "summer",
			"sea_dist_m": INF, "biomes": {biome: 1.0}}
		neigh.merge(SCENES[biome], true)
		var vols := {}
		for i in range(1800):   # 30 s : niveaux établis
			vols = m.evaluate(neigh, i / 60.0)
		var n := int(SCENE_S * rate)
		var buf := PackedFloat32Array()
		buf.resize(n)
		var heard := []
		for bed in AmbienceModel.BEDS:
			var db := float(vols[bed])
			if db <= AmbienceModel.SILENCE_DB:
				continue
			heard.append("%s %.0f" % [bed, db])
			var loop: PackedFloat32Array = loops[bed]
			for i in range(n):
				var g := db
				if bed == "forest_birds":
					g += AmbienceModel.birds_phrase_db(float(i) / rate)
				buf[i] += loop[i % loop.size()] * pow(10.0, g / 20.0)
		# Écoute : chaque scène ramenée à LISTEN_RMS_DB (en jeu, les fonds sont bien plus bas, sous le vent et les
		# bips) ; les niveaux du jeu, eux, sont dans scenes.csv
		var e := 0.0
		var peak := 0.0
		for i in range(n):
			e += buf[i] * buf[i]
			peak = maxf(peak, absf(buf[i]))
		var gain := minf(pow(10.0, LISTEN_RMS_DB / 20.0) / maxf(sqrt(e / n), 1e-9), 0.95 / maxf(peak, 1e-9))
		for i in range(n):
			buf[i] *= gain
		_save(out_dir.path_join("scene_%s.wav" % biome), buf)
		lines.append("%s;%s" % [biome, ", ".join(heard)])
	for bed in AmbienceModel.BIOME_BEDS:
		var loop: PackedFloat32Array = loops[bed]
		var n := int(SOLO_S * rate)
		var buf := PackedFloat32Array()
		buf.resize(n)
		var peak := 0.0
		for i in range(loop.size()):
			peak = maxf(peak, absf(loop[i]))
		for i in range(n):
			buf[i] = loop[i % loop.size()] * 0.8 / maxf(peak, 1e-6)
		_save(out_dir.path_join("fond_%s.wav" % bed), buf)
	var f := FileAccess.open(out_dir.path_join("scenes.csv"), FileAccess.WRITE)
	f.store_string("\n".join(lines) + "\n")
	f.close()
	print("\n".join(lines))
	quit(0)
