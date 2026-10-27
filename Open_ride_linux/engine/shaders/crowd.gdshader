shader_type spatial;
render_mode cull_disabled;

// Spectateurs du Lot P15 et passants du Lot P21 : animation par sommet à partir du temps global TIME.
// - UV.y : poids des bras ; ils se lèvent et s'agitent quand le spectateur encourage.
// - UV.x : poids du drapeau ; il s'agite, plus fort quand le spectateur encourage.
// - UV2.x : ±1 sur chaque jambe (patte du chien) ; UV2.y : 1 sur le bras qui salue (P21).
// - INSTANCE_CUSTOM.x : phase (0 à 1) ; INSTANCE_CUSTOM.y : 0 calme, 1 encourage ou salue
//   (crowd_renderer.gd) ; INSTANCE_CUSTOM.z : animation (passersby_model.gd ANIM) : 0 debout
//   (spectateur), 1 marche, 2 course, 3 assis, 4 jardinage, 5 sautille, 6 chien.
// - COLOR : couleur des vêtements (couleur d'instance du MultiMesh).
uniform vec3 skin : source_color = vec3(0.85, 0.68, 0.55);

void vertex() {
	float phase = INSTANCE_CUSTOM.x * 6.2831853;
	float excite = INSTANCE_CUSTOM.y;
	int anim = int(INSTANCE_CUSTOM.z + 0.5);
	if (anim == 0) {
		float wave = sin(TIME * 8.0 + phase);
		VERTEX.y += UV.y * excite * (0.45 + 0.12 * wave);
		VERTEX.x += UV.y * excite * 0.08 * wave * sign(VERTEX.x);
		VERTEX.y += UV.y * (1.0 - excite) * 0.02 * sin(TIME * 1.3 + phase);
		VERTEX.z += UV.x * sin(TIME * (3.0 + 5.0 * excite) + VERTEX.y * 3.0 + phase) * (0.05 + 0.15 * excite);
	} else {
		float waving_arm = UV.y * UV2.y * excite;
		if (anim == 1 || anim == 2 || anim == 6) {
			// Marche, course, trot : jambes en balancier depuis la hanche, bras en opposition
			float freq = anim == 2 ? 11.0 : (anim == 6 ? 9.0 : 6.5);
			float amp = anim == 2 ? 0.35 : 0.2;
			float hip = anim == 6 ? 0.34 : 0.9;
			float sw = sin(TIME * freq + phase);
			VERTEX.z += UV2.x * sw * amp * clamp((hip - VERTEX.y) / hip, 0.0, 1.0);
			VERTEX.z -= UV.y * (1.0 - UV2.y * excite) * sign(VERTEX.x) * sw * amp * 0.6 * clamp((1.43 - VERTEX.y) / 0.5, 0.0, 1.0);
			if (anim == 2) {
				VERTEX.y += abs(sw) * 0.05;
			}
		} else if (anim == 3) {
			// Assis : haut du corps abaissé, cuisses à l'horizontale vers l'avant
			if (abs(UV2.x) > 0.5) {
				VERTEX.z += min(0.9 - VERTEX.y, 0.45);
				VERTEX.y = VERTEX.y > 0.45 ? 0.45 + (VERTEX.y - 0.45) * 0.2 : VERTEX.y;
			} else {
				VERTEX.y -= 0.4;
			}
		} else if (anim == 4) {
			// Jardinage ou travail des champs : buste penché qui se relève un peu, en boucle
			float up = max(VERTEX.y - 0.9, 0.0);
			float lean = 0.55 + 0.25 * sin(TIME * 2.0 + phase);
			VERTEX.z += up * lean;
			VERTEX.y -= up * lean * 0.4;
		} else if (anim == 5) {
			// Enfant qui sautille
			VERTEX.y += abs(sin(TIME * 4.0 + phase)) * 0.12;
		}
		// Salut de la main
		float hand = sin(TIME * 9.0 + phase);
		VERTEX.y += waving_arm * (0.45 + 0.08 * hand);
		VERTEX.x += waving_arm * 0.1 * hand;
	}
}

void fragment() {
	// Le blanc des sommets « peau » (COLOR.a = 0) garde la couleur de peau
	ALBEDO = mix(skin, COLOR.rgb, step(0.5, COLOR.a));
}
