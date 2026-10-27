shader_type spatial;
render_mode cull_disabled, diffuse_lambert, specular_disabled;

// Animaux du Lot P11 : animation par sommet à partir du temps global TIME.
// - UV.x : poids de l'aile (oiseaux, mode 0) ; battement autour de l'axe du corps.
// - UV.y : poids de la tête (bêtes au sol, mode 1) ; la tête descend brouter puis remonte.
// - INSTANCE_CUSTOM.x : phase de l'individu (0 à 1), pour que les animaux ne bougent pas ensemble.
// - INSTANCE_CUSTOM.y : 1 = tête levée (chevreuil aux aguets ou en fuite), 0 = broutage normal.
uniform int mode = 0;
uniform vec3 albedo : source_color = vec3(0.3, 0.3, 0.3);
uniform float flap_hz = 6.0;
uniform float graze_hz = 0.12;

void vertex() {
	float phase = INSTANCE_CUSTOM.x * 6.2831853;
	if (mode == 0) {
		float flap = sin(TIME * 6.2831853 * flap_hz + phase);
		VERTEX.y += UV.x * flap * 0.35 * abs(VERTEX.x) * 2.0;
	} else {
		float down = 0.5 + 0.5 * sin(TIME * 6.2831853 * graze_hz + phase);
		down = smoothstep(0.35, 0.9, down) * (1.0 - INSTANCE_CUSTOM.y);
		VERTEX.y -= UV.y * down * 0.45;
		VERTEX.z += UV.y * down * 0.12;
	}
}

void fragment() {
	ALBEDO = albedo;
}
