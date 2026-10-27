shader_type spatial;
render_mode cull_disabled;

// Spectateurs du Lot P15 et passants du Lot P21, personnages refaits par le Lot Y14 (people_mesh.gd) :
// animation par articulations (hanche, genou, épaule) à partir du temps global TIME.
// - INSTANCE_CUSTOM.x : phase (0 à 1) ; INSTANCE_CUSTOM.y : 0 calme, 1 encourage ou salue
//   (crowd_renderer.gd) ; INSTANCE_CUSTOM.z : animation (passersby_model.gd ANIM) : 0 debout
//   (spectateur), 1 marche, 2 course, 3 assis, 4 jardinage, 5 sautille, 6 chien, 7 coureur qui pédale,
//   8 vélo (pédalier et roues qui tournent) ; pour 7 et 8, INSTANCE_CUSTOM.y = cadence / 100 tr/min ;
//   INSTANCE_CUSTOM.w : tenue (people_mesh.gd outfit : peau + 4 × (cheveux + 6 × (pantalon + 6 × style))) ;
//   style : bit 1 cheveux longs, bit 2 haut à bande.
// - CUSTOM0.w : 1 cheveux longs (repliés sans le bit de style), 2 casque (aérations sombres).
// - Données de sommet (people_mesh.gd) : CUSTOM0.x zone, CUSTOM0.y tibia, CUSTOM0.z porte-drapeau ;
//   UV.y bras libre, UV.x poids du drapeau ; UV2.x ±1 par jambe (patte), UV2.y bras qui salue.
// - COLOR : couleur d'instance du MultiMesh, couleur du haut (ou de la robe du chien, du bois du banc).
uniform vec3 skin_tones[4];
uniform vec3 hair_colors[6];
uniform vec3 trouser_colors[6];
uniform vec3 shoe_color : source_color = vec3(0.12, 0.1, 0.09);
uniform vec3 pole_color : source_color = vec3(0.6, 0.5, 0.36);
uniform vec3 metal_color : source_color = vec3(0.7, 0.71, 0.73);
uniform vec4 joints = vec4(0.92, 0.5, 1.42, 0.235);   // hanche, genou, épaule (hauteurs), écart des épaules
uniform vec4 bike = vec4(0.3, 0.2, 0.17, 0.34);       // boîtier (hauteur, avance), manivelle, rayon des roues
uniform vec4 axles = vec4(0.34, 0.8, 0.34, -0.21);    // axe avant (hauteur, avance), axe arrière
const float ANKLE_Y = 0.08;
const float WHEEL_TURNS_PER_CRANK = 2.6;               // braquet moyen : tours de roue par tour de pédalier

// Angle du pédalier (radians) : cadence × temps, décalé par la phase
float crank_angle(float cadence, float phase) {
	return TIME * cadence * 100.0 / 60.0 * 6.2831853 + phase;
}

varying flat float v_region;
varying flat float v_outfit;
varying flat float v_extra;
varying flat float v_rider;
varying vec3 v_local;          // position du sommet avant animation (motifs du haut et du casque)

// Rotation de p autour de l'axe x passant par le pivot (angle positif : le bas part vers l'arrière, -z,
// le haut vers l'avant)
vec3 rot_x(vec3 p, vec3 pivot, float a) {
	vec3 d = p - pivot;
	return pivot + vec3(d.x, d.y * cos(a) - d.z * sin(a), d.y * sin(a) + d.z * cos(a));
}

// Rotation de p autour de l'axe z passant par le pivot (angle positif : le bas part vers +x)
vec3 rot_z(vec3 p, vec3 pivot, float a) {
	vec3 d = p - pivot;
	return pivot + vec3(d.x * cos(a) - d.y * sin(a), d.x * sin(a) + d.y * cos(a), d.z);
}

void vertex() {
	v_region = CUSTOM0.x;
	v_outfit = INSTANCE_CUSTOM.w;
	v_extra = CUSTOM0.w;
	v_local = VERTEX;
	float phase = INSTANCE_CUSTOM.x * 6.2831853;
	float excite = INSTANCE_CUSTOM.y;
	int anim = int(INSTANCE_CUSTOM.z + 0.5);
	v_rider = anim == 7 ? 1.0 : 0.0;
	// Cheveux longs repliés quand la tenue ne les a pas
	int style = (int(INSTANCE_CUSTOM.w + 0.5) / 144) % 4;
	if (int(CUSTOM0.w + 0.5) == 1 && (style & 1) == 0) {
		VERTEX = vec3(0.0, 1.6, 0.0);
	}
	float leg = UV2.x;                       // ±1 sur une jambe, 0 ailleurs
	float side = sign(VERTEX.x);
	bool is_leg = abs(leg) > 0.5;
	bool free_arm = UV.y > 0.5;
	bool holder = CUSTOM0.z > 0.5;
	bool waving = UV2.y > 0.5 && excite > 0.5 && anim < 7;
	vec3 p = VERTEX;
	vec3 n = NORMAL;

	// Angles des articulations selon l'animation
	float hip = 0.0;        // jambe autour de la hanche (positif : vers l'arrière)
	float knee = 0.0;       // tibia autour du genou (positif : plié vers l'arrière)
	float arm_swing = 0.0;  // bras autour de l'épaule, d'avant en arrière
	float arm_raise = 0.08; // bras écartés sur le côté (radians, symétriques)
	float bend = 0.0;       // buste penché vers l'avant autour de la hanche
	float lift = 0.0;       // corps entier soulevé (m)
	if (anim == 0) {
		float wave = sin(TIME * 8.0 + phase);
		arm_raise = mix(0.08 + 0.03 * sin(TIME * 1.3 + phase), 2.55 + 0.25 * wave, excite);
		lift = excite * 0.04 * max(0.0, sin(TIME * 8.0 + phase));
	} else if (anim == 1 || anim == 2) {
		float run = anim == 2 ? 1.0 : 0.0;
		float freq = mix(6.5, 11.0, run);
		float sw = sin(TIME * freq + phase);
		hip = leg * sw * mix(0.38, 0.7, run);
		knee = max(0.0, -leg * sw) * mix(0.5, 1.3, run) + run * 0.5;
		arm_swing = -side * sw * mix(0.35, 0.8, run);
		lift = abs(sw) * mix(0.015, 0.06, run);
		bend = run * 0.15;
	} else if (anim == 3) {
		hip = -1.5708;
		knee = 1.5708;
		lift = -(joints.x - 0.47);
		arm_swing = -0.5;
	} else if (anim == 4) {
		bend = 0.95 + 0.3 * sin(TIME * 2.0 + phase);
		arm_swing = -0.9 - 0.3 * sin(TIME * 2.0 + phase);
		knee = 0.25;
		hip = -0.2;
	} else if (anim == 5) {
		lift = abs(sin(TIME * 4.0 + phase)) * 0.12;
		arm_raise = 0.5;
	} else if (anim == 7) {
		// Coureur : pied sur la pédale (jambe à deux segments résolue au genou), buste penché, mains au cintre
		float c = crank_angle(excite, phase) + (leg < 0.0 ? 3.14159265 : 0.0);
		vec2 foot = vec2(bike.x, bike.y) + bike.z * vec2(cos(c), sin(c));   // (y, z) : en haut à 0, devant à π/2
		vec2 v = foot - vec2(joints.x, 0.0);
		float l1 = joints.x - joints.y;
		float l2 = joints.y - ANKLE_Y;
		float d = clamp(length(v), 0.1, l1 + l2 - 1e-3);
		float a_hip = acos(clamp((l1 * l1 + d * d - l2 * l2) / (2.0 * l1 * d), -1.0, 1.0));
		float a_knee = acos(clamp((l1 * l1 + l2 * l2 - d * d) / (2.0 * l1 * l2), -1.0, 1.0));
		hip = atan(-v.y, -v.x) - a_hip;
		knee = 3.14159265 - a_knee;
		bend = 0.8;
		arm_swing = -1.75;
		arm_raise = 0.0;
	}

	if (anim == 8) {
		// Vélo : pédalier autour du boîtier, roues autour de leur axe (manivelle droite construite vers le bas)
		int part = int(CUSTOM0.y + 0.5);
		float c = crank_angle(excite, phase);
		if (part == 1) {
			p = rot_x(p, vec3(0.0, bike.x, bike.y), c + 3.14159265);
		} else if (part == 2) {
			p = rot_x(p, vec3(0.0, axles.x, axles.y), c * WHEEL_TURNS_PER_CRANK);
		} else if (part == 3) {
			p = rot_x(p, vec3(0.0, axles.z, axles.w), c * WHEEL_TURNS_PER_CRANK);
		}
		VERTEX = p;
	} else if (anim == 6) {
		// Chien : pattes en diagonale autour de leur attache (avant et arrière)
		float sw = sin(TIME * 9.0 + phase);
		if (is_leg) {
			p = rot_x(p, vec3(0.0, 0.34, sign(VERTEX.z) * 0.2), leg * sw * 0.45);
		}
		VERTEX = p;
	} else {
		// Jambes : genou puis hanche
		if (is_leg) {
			vec3 knee_p = vec3(VERTEX.x, joints.y, 0.0);
			vec3 hip_p = vec3(VERTEX.x, joints.x, 0.0);
			if (CUSTOM0.y > 0.5) {
				p = rot_x(p, knee_p, knee);
				n = rot_x(n, vec3(0.0), knee);
			}
			p = rot_x(p, hip_p, hip);
			n = rot_x(n, vec3(0.0), hip);
		}
		// Bras : écartés sur le côté, puis balancés
		vec3 shoulder = vec3(side * joints.w, joints.z, 0.0);
		if (free_arm) {
			float raise = waving ? 2.6 + 0.2 * sin(TIME * 9.0 + phase) : arm_raise;
			p = rot_z(p, shoulder, side * raise);
			n = rot_z(n, vec3(0.0), side * raise);
			float swing = waving ? 0.0 : arm_swing;
			p = rot_x(p, shoulder, swing);
			n = rot_x(n, vec3(0.0), swing);
		}
		// Porte-drapeau : le bras levé et la hampe balancent quand il encourage ; la toile ondule
		if (holder) {
			float a = excite * 0.35 * sin(TIME * 5.0 + phase);
			p = rot_z(p, shoulder, a);
			p.x += UV.x * sin(TIME * (3.0 + 5.0 * excite) - UV.x * 4.0 + phase) * (0.06 + 0.12 * excite);
		}
		// Coureur : tête relevée pour regarder la route malgré le buste penché
		if (anim == 7 && VERTEX.y > 1.46) {
			p = rot_x(p, vec3(0.0, 1.47, 0.0), -0.65);
		}
		// Buste penché autour du bassin (tout ce qui n'est pas une jambe)
		if (!is_leg && bend != 0.0 && VERTEX.y > joints.x - 0.06) {
			vec3 pelvis = vec3(0.0, joints.x - 0.06, 0.0);
			p = rot_x(p, pelvis, bend);
			n = rot_x(n, vec3(0.0), bend);
		}
		p.y += lift;
		VERTEX = p;
		NORMAL = normalize(n);
	}
}

void fragment() {
	int region = int(v_region + 0.5);
	int o = int(v_outfit + 0.5);
	vec3 c = COLOR.rgb;
	int style = (o / 144) % 4;
	if (region == 0) {
		// Bande claire sur la poitrine (haut à bande, maillot du coureur), flancs sombres du maillot,
		// aérations du casque
		bool stripe = (style & 2) != 0 || v_rider > 0.5;
		float band = step(1.22, v_local.y) * step(v_local.y, 1.3) * (stripe ? 1.0 : 0.0) * (v_extra > 0.5 ? 0.0 : 1.0);
		c = mix(c, vec3(0.95), band * 0.85);
		if (v_rider > 0.5 && v_extra < 0.5 && abs(v_local.x) > 0.15 && v_local.y > 0.98) {
			c *= 0.35;
		}
		if (int(v_extra + 0.5) == 2 && v_local.y > 1.66 && fract(v_local.x * 22.0) < 0.35) {
			c *= 0.25;
		}
	} else if (region == 1) {
		c = skin_tones[o % 4];
	} else if (region == 2) {
		c = hair_colors[(o / 4) % 6];
	} else if (region == 3) {
		c = trouser_colors[(o / 24) % 6];
	} else if (region == 4) {
		c = shoe_color;
	} else if (region == 5) {
		c = pole_color;
	} else if (region == 6) {
		c = metal_color;
	}
	ALBEDO = c;
	ROUGHNESS = region == 1 ? 0.6 : (region == 6 ? 0.35 : 0.85);
	METALLIC = region == 6 ? 0.8 : 0.0;
}
