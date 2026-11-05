global uniform float anim_time;

// Corps de crowd.gdshader (les bots ont l'avatar du joueur depuis le lot Y18 : bots_view.gd).
// Spectateurs du Lot P15 et passants du Lot P21, personnages refaits par les lots Y14 et Y21
// (people_mesh.gd) : animation par articulations (hanche, genou, épaule, coude, cou) à partir du temps
// global anim_time (anim_clock.gd : figé avec le décor quand le core ne répond plus).
// - INSTANCE_CUSTOM.x : phase (partie décimale) ; INSTANCE_CUSTOM.y : 0 calme, 1 encourage ou salue
//   (crowd_renderer.gd) ; INSTANCE_CUSTOM.z % 10 : animation (passersby_model.gd ANIM) : 0 debout
//   (spectateur), 1 marche, 2 course, 3 assis, 4 jardinage, 5 sautille, 6 chien, 7 coureur qui pédale,
//   8 vélo (pédalier et roues qui tournent), 9 porteur de pancarte (debout, tout le corps tourné vers la
//   caméra, au plus SIGN_MAX_YAW, pour que la pancarte se lise de la route) ; pour 7 et 8, INSTANCE_CUSTOM.y = cadence / 100 tr/min ;
//   tenue répartie par people_mesh.gd instance_custom (entiers sous 2 048 par composante) : x = détail +
//   phase, z = animation + 10 × (bas + 3 × (coiffe + 3 × geste)), w = peau + 4 × (cheveux + 6 × (pantalon
//   + 6 × style)) ; détail : barbe, moustache, lunettes de soleil, queue de cheval, chignon, sac à dos,
//   écharpe de supporter (pièce EXTRA 8 + détail) ; style : bit 1 cheveux longs, bit 2 haut à bande, bit 4
//   veste ouverte à manches longues ; bas : pantalon, short, jupe ; coiffe : rien, casquette, chapeau.
// - Debout (animation 0) : le geste (GESTURE_* de people_mesh.gd) choisit la pose quand la personne
//   encourage (bras levés, applaudit, poing levé, porte-voix, photo au téléphone, sautille en
//   applaudissant, salue d'un bras, deux poings) et, `geste % 4`, l'attitude au calme (bras le long du
//   corps, croisés, mains sur les hanches, mains jointes) ; debout, assis ou sautillant, la tête suit la
//   caméra (le cycliste) quand elle passe à moins de HEAD_TRACK_M.
// - CUSTOM0.w : pièces montrées selon la tenue (1 cheveux longs, 3 casquette, 4 chapeau, 5 jupe,
//   6 téléphone, 9 à 15 détail : repliées dans la tête sinon), 2 casque (aérations sombres), 7 drapeau (motif), 8 pancarte
//   (bras et pancarte balancés ensemble).
// - Données de sommet (people_mesh.gd) : CUSTOM0.x zone, CUSTOM0.y tibia et avant-bras, CUSTOM0.z
//   porteur (bras levé, hampe, drapeau, pancarte) ; UV.y bras libre, UV.x poids du drapeau (et abscisse de
//   son motif) ; UV2.x ±1 par jambe (patte), UV2.y bras qui salue (ordonnée du motif sur le drapeau).
// - COLOR : couleur d'instance du MultiMesh, couleur du haut (ou de la robe du chien, du bois du banc).
uniform vec3 skin_tones[4];
uniform vec3 hair_colors[6];
uniform vec3 trouser_colors[6];
uniform vec3 flag_colors[6];
// Palettes posées en Vector3 sRGB (people_mesh.gd) ; teinte calculée en sRGB, convertie à l'écriture.
#include "res://shaders/couleur_srgb.gdshaderinc"
uniform vec3 shoe_color = vec3(0.12, 0.1, 0.09);
uniform vec3 pole_color = vec3(0.6, 0.5, 0.36);
uniform vec3 metal_color = vec3(0.7, 0.71, 0.73);
uniform vec3 straw_color = vec3(0.86, 0.76, 0.5);
uniform vec4 joints = vec4(0.92, 0.5, 1.42, 0.205);   // hanche, genou, épaule (hauteurs), écart des épaules
uniform vec2 elbow = vec2(1.14, 0.225);               // coude : hauteur, écart
uniform vec4 sign_rect = vec4(-0.43, 1.94, 0.43, 2.42); // pancarte : x min, y min, x max, y max
uniform vec4 bike = vec4(0.3, 0.2, 0.17, 0.34);       // boîtier (hauteur, avance), manivelle, rayon des roues
uniform vec4 axles = vec4(0.34, 0.8, 0.34, -0.21);    // axe avant (hauteur, avance), axe arrière
const float ANKLE_Y = 0.08;
const float WHEEL_TURNS_PER_CRANK = 2.6;               // braquet moyen : tours de roue par tour de pédalier
const float HEAD_TRACK_M = 40.0;                       // la tête suit la caméra en deçà
const float HEAD_MAX_YAW = 1.1;                        // rotation de la tête au plus (radians)
const float SIGN_MAX_YAW = 0.9;                        // rotation du porteur de pancarte au plus (radians)

// Angle du pédalier (radians) : cadence × temps, décalé par la phase
float crank_angle(float cadence, float phase) {
	return anim_time * cadence * 100.0 / 60.0 * 6.2831853 + phase;
}

varying flat float v_region;
varying flat float v_outfit;
varying flat float v_pose;
varying flat float v_flag;      // motif du drapeau (0 à 3)
varying flat float v_extra;
varying flat float v_rider;
varying float v_shin;
varying vec2 v_pattern;        // drapeau : (le long, de haut en bas), de 0 à 1
varying vec3 v_local;          // position du sommet avant animation (motifs du haut, du casque, de la pancarte)

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

// Rotation de p autour de l'axe y passant par le pivot (angle positif : l'avant, +z, part vers +x)
vec3 rot_y(vec3 p, vec3 pivot, float a) {
	vec3 d = p - pivot;
	return pivot + vec3(d.x * cos(a) + d.z * sin(a), d.y, -d.x * sin(a) + d.z * cos(a));
}

// Champs de la tenue (people_mesh.gd instance_custom) : apparence `o` (INSTANCE_CUSTOM.w), pose `q`
// (INSTANCE_CUSTOM.z / 10) et détail (partie entière de INSTANCE_CUSTOM.x)
int outfit_style(int o) { return (o / 144) % 8; }
int outfit_bottom(int q) { return q % 3; }
int outfit_hat(int q) { return (q / 3) % 3; }
int outfit_gesture(int q) { return (q / 9) % 8; }

// Pose d'un bras (côté `s` : ±1) : (écart sur le côté, balancement avant (négatif) ou arrière, rotation
// vers l'intérieur, flexion du coude), pour l'attitude au calme (`calm` = geste % 4) ou le geste.
vec4 calm_arm(int calm, float s, float t, float phase) {
	float idle = 0.03 * sin(t * 1.3 + phase);
	if (calm == 1) {
		return vec4(0.12, -0.28 - (s > 0.0 ? 0.08 : 0.0), 1.28, 1.95);    // bras croisés
	} else if (calm == 2) {
		return vec4(0.62, 0.12, 1.35, 1.25);                               // mains sur les hanches
	} else if (calm == 3) {
		return vec4(0.04, -0.3 + idle, 0.95, 0.95);                        // mains jointes devant
	}
	return vec4(0.08 + idle, 0.04 * s * sin(t * 0.9 + phase), 0.0, 0.18);   // bras le long du corps
}

vec4 cheer_arm(int g, float s, float t, float phase) {
	float wave = sin(t * 8.0 + phase);
	if (g == 1 || g == 5) {
		float clap = sin(t * 13.0 + phase);
		return vec4(0.18, -0.85, 0.75 + 0.3 * clap, 1.35);                 // applaudit
	} else if (g == 2) {
		if (s > 0.0) {
			return vec4(2.85, -0.12, 0.0, 0.5 + 0.7 * max(0.0, sin(t * 7.0 + phase)));   // poing levé
		}
		return vec4(0.12, -0.1, 0.0, 0.3);
	} else if (g == 3) {
		return vec4(0.32, -0.95, 1.05, 2.25);                              // mains en porte-voix
	} else if (g == 4) {
		return vec4(0.22, -1.2, 0.5, 1.5);                                 // photo au téléphone
	} else if (g == 6) {
		if (s > 0.0) {
			return vec4(2.45 + 0.3 * sin(t * 9.0 + phase), -0.2, 0.0, 0.35);  // salue d'un bras
		}
		return vec4(0.1, 0.0, 0.0, 0.2);
	} else if (g == 7) {
		return vec4(2.7, -0.15, 0.0, 0.55 + 0.75 * max(0.0, sin(t * 7.0 + phase + s * 1.5708)));   // deux poings
	}
	return vec4(2.55 + 0.25 * wave, -0.15, 0.0, 0.3 + 0.2 * wave);         // bras levés qui s'agitent
}

void vertex() {
	v_region = CUSTOM0.x;
	v_outfit = INSTANCE_CUSTOM.w;
	v_extra = CUSTOM0.w;
	v_local = VERTEX;
	v_shin = CUSTOM0.y;
	v_pattern = vec2(UV.x, UV2.y);
	float phase = fract(INSTANCE_CUSTOM.x) * 6.2831853;
	int detail = int(floor(INSTANCE_CUSTOM.x));
	float excite = INSTANCE_CUSTOM.y;
	int zq = int(INSTANCE_CUSTOM.z + 0.5);
	int anim = zq % 10;
	int q = zq / 10;
	int o = int(INSTANCE_CUSTOM.w + 0.5);
	v_pose = float(q);
	v_flag = floor(fract(INSTANCE_CUSTOM.x) * 3.999);
	int style = outfit_style(o);
	int gesture = outfit_gesture(q);
	int extra = int(CUSTOM0.w + 0.5);
	v_rider = anim == 7 ? 1.0 : 0.0;
	// Pièces de tenue repliées dans la tête quand la tenue (ou le geste) ne les montre pas
	bool hidden = (extra == 1 && (style & 1) == 0) || (extra == 3 && outfit_hat(q) != 1)
		|| (extra == 4 && outfit_hat(q) != 2) || (extra == 5 && outfit_bottom(q) != 2)
		|| (extra == 6 && !(anim == 0 && excite > 0.5 && gesture == 4))
		|| (extra >= 9 && extra <= 15 && detail != extra - 8);
	if (hidden) {
		VERTEX = vec3(0.0, 1.6, 0.0);
	}
	float leg = UV2.x;                       // ±1 sur une jambe, 0 ailleurs
	float side = sign(VERTEX.x);
	bool is_leg = abs(leg) > 0.5;
	bool free_arm = UV.y > 0.5;
	bool holder = CUSTOM0.z > 0.5;
	bool below_joint = CUSTOM0.y > 0.5;       // tibia ou avant-bras
	bool waving = UV2.y > 0.5 && excite > 0.5 && anim != 0 && anim < 7;
	vec3 p = VERTEX;
	vec3 n = NORMAL;

	// Angles des articulations selon l'animation
	float hip = 0.0;        // jambe autour de la hanche (positif : vers l'arrière)
	float knee = 0.0;       // tibia autour du genou (positif : plié vers l'arrière)
	float arm_swing = 0.0;  // bras autour de l'épaule, d'avant en arrière
	float arm_raise = 0.08; // bras écartés sur le côté (radians, symétriques)
	float arm_twist = 0.0;  // bras tourné vers l'intérieur autour de la verticale de l'épaule
	float arm_flex = 0.18;  // coude plié (avant-bras vers l'avant)
	float bend = 0.0;       // buste penché vers l'avant autour de la hanche
	float lift = 0.0;       // corps entier soulevé (m)
	bool track = false;     // tête qui suit la caméra
	if (anim == 0) {
		vec4 arm = mix(calm_arm(gesture % 4, side, anim_time, phase), cheer_arm(gesture, side, anim_time, phase), excite);
		arm_raise = arm.x;
		arm_swing = arm.y;
		arm_twist = arm.z;
		arm_flex = arm.w;
		float hop = gesture == 5 ? 0.09 : (gesture == 0 || gesture == 7 ? 0.04 : 0.0);
		lift = excite * hop * max(0.0, sin(anim_time * 8.0 + phase));
		bend = excite * (gesture == 3 ? 0.12 + 0.06 * sin(anim_time * 5.0 + phase) : 0.0);
		track = true;
	} else if (anim == 9) {
		lift = excite * 0.03 * max(0.0, sin(anim_time * 8.0 + phase));
		track = true;
	} else if (anim == 1 || anim == 2) {
		float run = anim == 2 ? 1.0 : 0.0;
		float freq = mix(6.5, 11.0, run);
		float sw = sin(anim_time * freq + phase);
		hip = leg * sw * mix(0.38, 0.7, run);
		knee = max(0.0, -leg * sw) * mix(0.5, 1.3, run) + run * 0.5;
		arm_swing = -side * sw * mix(0.35, 0.8, run);
		arm_flex = mix(0.3, 1.45, run);
		lift = abs(sw) * mix(0.015, 0.06, run);
		bend = run * 0.15;
	} else if (anim == 3) {
		hip = -1.5708;
		knee = 1.5708;
		lift = -(joints.x - 0.47);
		arm_swing = -0.35;
		arm_flex = 0.9;
		arm_twist = 0.35;
		track = true;
	} else if (anim == 4) {
		bend = 0.95 + 0.3 * sin(anim_time * 2.0 + phase);
		arm_swing = -0.9 - 0.3 * sin(anim_time * 2.0 + phase);
		arm_flex = 0.35;
		knee = 0.25;
		hip = -0.2;
	} else if (anim == 5) {
		lift = abs(sin(anim_time * 4.0 + phase)) * 0.12;
		arm_raise = 0.5;
		arm_flex = 0.5;
		track = true;
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
		arm_flex = 0.0;
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
		float sw = sin(anim_time * 9.0 + phase);
		if (is_leg) {
			p = rot_x(p, vec3(0.0, 0.34, sign(VERTEX.z) * 0.2), leg * sw * 0.45);
		}
		VERTEX = p;
	} else {
		// Jambes : genou puis hanche
		if (is_leg) {
			vec3 knee_p = vec3(VERTEX.x, joints.y, 0.0);
			vec3 hip_p = vec3(VERTEX.x, joints.x, 0.0);
			if (below_joint) {
				p = rot_x(p, knee_p, knee);
				n = rot_x(n, vec3(0.0), knee);
			}
			p = rot_x(p, hip_p, hip);
			n = rot_x(n, vec3(0.0), hip);
		}
		// Bras : coude plié, bras tourné vers l'intérieur, écarté sur le côté, puis balancé
		vec3 shoulder = vec3(side * joints.w, joints.z, 0.0);
		if (free_arm) {
			if (below_joint) {
				vec3 elbow_p = vec3(side * elbow.y, elbow.x, 0.0);
				p = rot_x(p, elbow_p, -arm_flex);
				n = rot_x(n, vec3(0.0), -arm_flex);
			}
			p = rot_y(p, shoulder, -side * arm_twist);
			n = rot_y(n, vec3(0.0), -side * arm_twist);
			float raise = waving ? 2.6 + 0.2 * sin(anim_time * 9.0 + phase) : arm_raise;
			p = rot_z(p, shoulder, side * raise);
			n = rot_z(n, vec3(0.0), side * raise);
			float swing = waving ? 0.0 : arm_swing;
			p = rot_x(p, shoulder, swing);
			n = rot_x(n, vec3(0.0), swing);
		}
		if (holder && extra == 8) {
			// Pancarte : bras et pancarte balancés ensemble autour du milieu des épaules quand il encourage
			float a = excite * 0.12 * sin(anim_time * 4.0 + phase);
			p = rot_z(p, vec3(0.0, joints.z, 0.0), a);
			n = rot_z(n, vec3(0.0), a);
			p.y += excite * 0.05 * max(0.0, sin(anim_time * 8.0 + phase));
		} else if (holder) {
			// Porte-drapeau : le bras levé et la hampe balancent quand il encourage ; la toile ondule
			float a = excite * 0.35 * sin(anim_time * 5.0 + phase);
			p = rot_z(p, shoulder, a);
			p.x += UV.x * sin(anim_time * (3.0 + 5.0 * excite) - UV.x * 4.0 + phase) * (0.06 + 0.12 * excite);
		}
		// Tête (cou, visage, cheveux, coiffe) tournée vers la caméra quand elle passe près ; porteur de
		// pancarte : tout le corps d'abord (au plus SIGN_MAX_YAW), la tête fait le reste
		bool head = !free_arm && !holder && VERTEX.y > 1.49 && extra != 14 && extra != 15;
		if (track && (head || anim == 9)) {
			vec3 cam = (inverse(MODEL_MATRIX) * vec4(CAMERA_POSITION_WORLD, 1.0)).xyz;
			float yaw = atan(cam.x, cam.z);
			float reach = smoothstep(HEAD_TRACK_M, HEAD_TRACK_M * 0.6, length(cam.xz)) * smoothstep(2.6, 1.8, abs(yaw));
			float body = anim == 9 ? clamp(yaw, -SIGN_MAX_YAW, SIGN_MAX_YAW) * reach : 0.0;
			float a = body + (head ? clamp(yaw - body, -HEAD_MAX_YAW, HEAD_MAX_YAW) * reach : 0.0);
			p = rot_y(p, vec3(0.0), a);
			n = rot_y(n, vec3(0.0), a);
		}
		// Au calme, debout : léger balancement du haut du corps d'une jambe sur l'autre
		if (anim == 0 && !is_leg && VERTEX.y > joints.x - 0.08) {
			float sway = (1.0 - excite) * 0.03 * sin(anim_time * 0.7 + phase * 1.7);
			p = rot_z(p, vec3(0.0, joints.x - 0.08, 0.0), sway);
			n = rot_z(n, vec3(0.0), sway);
		}
		// Coureur : tête relevée pour regarder la route malgré le buste penché
		if (anim == 7 && VERTEX.y > 1.46 && !free_arm) {
			p = rot_x(p, vec3(0.0, 1.47, 0.0), -0.65);
		}
		// Buste penché autour du bassin : tout ce qui n'est pas une jambe, bras et mains compris (les mains
		// pendent sous le bassin au repos)
		if (!is_leg && bend != 0.0 && (VERTEX.y > joints.x - 0.06 || free_arm || holder)) {
			vec3 pelvis = vec3(0.0, joints.x - 0.06, 0.0);
			p = rot_x(p, pelvis, bend);
			n = rot_x(n, vec3(0.0), bend);
		}
		p.y += lift;
		VERTEX = p;
		NORMAL = normalize(n);
	}
}

// Motif du drapeau (`pattern` tiré de la phase de la personne : 0 tricolore vertical, 1 deux bandes, 2 croix nordique, 3 à pois) en
// coordonnées (le long, de haut en bas) ; c1 couleur d'instance, c2 couleur d'appoint.
vec3 flag_pattern(int pattern, vec2 q, vec3 c1, vec3 c2) {
	if (pattern == 0) {
		return q.x < 0.333 ? c1 : (q.x < 0.667 ? vec3(0.95) : c2);
	} else if (pattern == 1) {
		return q.y < 0.5 ? c1 : c2;
	} else if (pattern == 2) {
		bool cross = abs(q.x - 0.36) < 0.07 || abs(q.y - 0.5) < 0.1;
		return cross ? c2 : c1;
	}
	vec2 cell = fract(q * vec2(5.0, 3.4)) - 0.5;
	return length(cell) < 0.28 ? vec3(0.85, 0.08, 0.1) : vec3(0.97);
}

void fragment() {
	int region = int(v_region + 0.5);
	int o = int(v_outfit + 0.5);
	int extra = int(v_extra + 0.5);
	vec3 c = COLOR.rgb;
	int style = outfit_style(o);
	int bottom = outfit_bottom(int(v_pose + 0.5));
	vec3 skin = skin_tones[o % 4];
	vec3 trousers = trouser_colors[(o / 24) % 6];
	if (region == 0) {
		if (extra == 7) {
			// Deuxième couleur prise plus loin dans la palette si elle ressemble trop à la première
			int k = (o / 24) % 6;
			vec3 c2 = flag_colors[k];
			if (length(c2 - c) < 0.35) {
				c2 = flag_colors[(k + 2) % 6];
			}
			c = flag_pattern(int(v_flag + 0.5), v_pattern, c, c2);
		} else {
			// Bande claire sur la poitrine (haut à bande, maillot du coureur), flancs sombres du maillot,
			// aérations du casque, veste ouverte sur un tee-shirt clair
			bool stripe = (style & 2) != 0 || v_rider > 0.5;
			float band = step(1.22, v_local.y) * step(v_local.y, 1.3) * (stripe ? 1.0 : 0.0) * (v_extra > 0.5 ? 0.0 : 1.0);
			c = mix(c, vec3(0.95), band * 0.85);
			if ((style & 4) != 0 && v_rider < 0.5 && extra == 0 && v_local.z > 0.0 && abs(v_local.x) < 0.05
					&& v_local.y > 0.98 && v_local.y < 1.47) {
				c = vec3(0.92, 0.92, 0.9);
			}
			if (v_rider > 0.5 && v_extra < 0.5 && abs(v_local.x) > 0.15 && v_local.y > 0.98) {
				c *= 0.35;
			}
			if (extra == 2 && v_local.y > 1.66 && fract(v_local.x * 22.0) < 0.35) {
				c *= 0.25;
			}
		}
	} else if (region == 1) {
		c = skin;
	} else if (region == 2) {
		c = hair_colors[(o / 4) % 6];
	} else if (region == 3) {
		// Short : mollets nus ; jupe : jambes nues sous la jupe
		c = (bottom != 0 && v_shin > 0.5 && v_rider < 0.5) ? skin : trousers;
	} else if (region == 4) {
		c = shoe_color;
	} else if (region == 5) {
		c = extra == 4 ? straw_color : pole_color;
	} else if (region == 6) {
		c = metal_color;
	} else if (region == 7) {
		// Pancarte : fond clair, bord à la couleur du haut, deux lignes de lettres
		vec2 q = (v_local.xy - sign_rect.xy) / (sign_rect.zw - sign_rect.xy);
		c = vec3(0.96, 0.95, 0.9);
		if (q.x < 0.04 || q.x > 0.96 || q.y < 0.06 || q.y > 0.94) {
			c = COLOR.rgb;
		} else {
			float line = q.y > 0.52 && q.y < 0.82 ? 1.0 : (q.y > 0.2 && q.y < 0.44 ? 2.0 : 0.0);
			float letter = fract(q.x * 7.0 + float(o % 3) * 0.37);
			bool ink = line > 0.0 && q.x > 0.1 && q.x < 0.9 && letter > 0.12 && letter < 0.82
				&& (fract(q.y * 18.0 + q.x * 3.0) < 0.75 || abs(letter - 0.47) < 0.12);
			if (ink) {
				c = line > 1.5 ? flag_colors[(o / 24) % 6] : COLOR.rgb;
				c = length(c - vec3(0.96)) < 0.2 ? vec3(0.1) : c;
			}
		}
	} else if (region == 8) {
		// Peau du bras, manche longue avec une veste
		c = ((style & 4) != 0 && v_rider < 0.5) ? COLOR.rgb : skin;
	} else if (region == 9) {
		// Accessoire : écharpe de supporter rayée (couleur du haut et d'appoint), sac à dos d'appoint
		int k = (o / 24) % 6;
		vec3 c2 = flag_colors[k];
		if (length(c2 - COLOR.rgb) < 0.35) {
			c2 = flag_colors[(k + 2) % 6];
		}
		c = extra == 15 ? (fract(v_local.y * 14.0) < 0.5 ? COLOR.rgb : c2) : c2 * 0.8;
	} else if (region == 10) {
		c = vec3(0.93, 0.92, 0.88);
	} else if (region == 11) {
		c = mix(skin, vec3(0.62, 0.25, 0.25), 0.45);
	}
	if (region == 1 && v_local.y > 1.6 && v_local.y < 1.635 && abs(v_local.x) > 0.035 && abs(v_local.x) < 0.075 && v_local.z > 0.05) {
		c = mix(c, vec3(0.85, 0.42, 0.4), 0.18);   // joues
	}
	// Ombre de contact vers le sol et sous les bras (personnages debout), sans toucher au drapeau ni à la pancarte
	float ao = 1.0;
	if (v_rider < 0.5 && region != 7 && extra != 7) {
		ao = mix(0.72, 1.0, smoothstep(0.02, 0.5, v_local.y));
		if (region == 0 && abs(v_local.x) > 0.13 && v_local.y > 1.0 && v_local.y < 1.36) {
			ao *= 0.88;
		}
	}
	ALBEDO = lineaire(c) * ao;
	bool cloth = region == 0 || region == 3 || region == 9 || (region == 8 && (style & 4) != 0);
	ROUGHNESS = (region == 1 || region == 8 || region == 11) ? 0.6 : (region == 6 ? 0.35 : (region == 2 ? 0.55 : 0.85));
	METALLIC = region == 6 ? 0.8 : 0.0;
	RIM = cloth ? 0.3 : 0.15;
	RIM_TINT = 0.5;
}
