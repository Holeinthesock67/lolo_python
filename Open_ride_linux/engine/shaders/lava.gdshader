shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_disabled, diffuse_burley, specular_schlick_ggx;

// Lave des paysages en feu (démo « Volcan en flammes », volcano_fx.gd) : coulées et lacs posés sur le terrain.
// Croûte noire qui se fend en plaques sur une lave orange à jaune qui coule ; tout est calculé ici, sans image.
// COLOR.a : 1 au cœur de la coulée ou du lac, 0 sur la rive (croûte figée, plus sombre, sans lueur).
// Coordonnées monde pour le motif (pas d'UV) : deux coulées voisines ne se répètent pas ; le courant glisse vers l'ouest.

uniform vec3 lava_color : source_color = vec3(1.0, 0.35, 0.06);
uniform vec3 lava_hot : source_color = vec3(1.0, 0.82, 0.3);
uniform vec3 crust_color : source_color = vec3(0.08, 0.06, 0.05);
uniform float flow_mps = 0.6;
uniform float energy = 3.0;

varying vec3 world_pos;

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

// Plaques de croûte : distance au bord de la cellule de Voronoï la plus proche (0 sur la fissure).
float cracks(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	float d1 = 8.0;
	float d2 = 8.0;
	for (int y = -1; y <= 1; y++) {
		for (int x = -1; x <= 1; x++) {
			vec2 g = vec2(float(x), float(y));
			vec2 o = vec2(hash(i + g), hash(i + g + 17.0));
			float d = length(g + o - f);
			if (d < d1) {
				d2 = d1;
				d1 = d;
			} else if (d < d2) {
				d2 = d;
			}
		}
	}
	return d2 - d1;
}

// Lave rapprochée de la caméra d'une part de sa distance (au plus `pull_max_m`) : posée sur un terrain dont les
// triangles s'écartent de la hauteur échantillonnée, elle ne s'enfonce pas par endroits (rubans hachés, r-volcan).
uniform float pull_share = 0.015;
uniform float pull_max_m = 3.0;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec3 view = (MODELVIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float d = length(view);
	view *= 1.0 - min(d * pull_share, pull_max_m) / max(d, 0.001);
	POSITION = PROJECTION_MATRIX * vec4(view, 1.0);
}

void fragment() {
	float core = COLOR.a;
	vec2 p = world_pos.xz * 0.22;
	// Courant : le motif glisse le long de la coulée (UV.x), le lac tourne lentement
	vec2 drift = vec2(-TIME * flow_mps * 0.22, 0.0);
	float n = noise(p * 1.7 + drift * 1.3 + vec2(TIME * 0.05));
	float c = cracks(p + drift + n * 0.6);
	float pulse = 0.75 + 0.25 * sin(TIME * 1.7 + n * 6.2831);
	// Fissures larges au cœur, croûte presque fermée sur la rive
	float open = mix(0.02, 0.32, core) * (0.7 + 0.6 * n);
	float molten = 1.0 - smoothstep(open * 0.4, open, c);
	molten = max(molten, core * smoothstep(0.55, 0.9, n) * 0.85);
	vec3 hot = mix(lava_color, lava_hot, smoothstep(0.4, 1.0, molten * pulse));
	vec3 crust = crust_color * (0.7 + 0.6 * noise(p * 4.0));
	// Croûte tiède : rouge sombre près des fissures
	vec3 warm = mix(crust, lava_color * 0.35, (1.0 - smoothstep(0.0, open * 2.5, c)) * core);
	ALBEDO = mix(warm, hot, molten);
	ROUGHNESS = mix(0.95, 0.4, molten);
	SPECULAR = 0.2;
	EMISSION = hot * molten * energy * pulse + lava_color * core * 0.25;
}
