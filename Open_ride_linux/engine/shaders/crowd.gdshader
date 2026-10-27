shader_type spatial;
render_mode cull_disabled;

// Spectateurs du Lot P15 : animation par sommet à partir du temps global TIME.
// - UV.y : poids des bras ; ils se lèvent et s'agitent quand le spectateur encourage.
// - UV.x : poids du drapeau ; il s'agite, plus fort quand le spectateur encourage.
// - INSTANCE_CUSTOM.x : phase (0 à 1) ; INSTANCE_CUSTOM.y : 0 calme, 1 encourage (crowd_renderer.gd).
// - COLOR : couleur des vêtements (couleur d'instance du MultiMesh).
uniform vec3 skin : source_color = vec3(0.85, 0.68, 0.55);

void vertex() {
	float phase = INSTANCE_CUSTOM.x * 6.2831853;
	float excite = INSTANCE_CUSTOM.y;
	float wave = sin(TIME * 8.0 + phase);
	VERTEX.y += UV.y * excite * (0.45 + 0.12 * wave);
	VERTEX.x += UV.y * excite * 0.08 * wave * sign(VERTEX.x);
	VERTEX.y += UV.y * (1.0 - excite) * 0.02 * sin(TIME * 1.3 + phase);
	VERTEX.z += UV.x * sin(TIME * (3.0 + 5.0 * excite) + VERTEX.y * 3.0 + phase) * (0.05 + 0.15 * excite);
}

void fragment() {
	// Le blanc des sommets « peau » (COLOR.a = 0) garde la couleur de peau
	ALBEDO = mix(skin, COLOR.rgb, step(0.5, COLOR.a));
}
