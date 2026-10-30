shader_type sky;
render_mode use_debanding;

// Ciel avec nuages qui défilent au vent (Lot P6), en un seul passage, sans volume.
// Le dégradé est celui du ProceduralSkyMaterial de Godot 4.7 (zénith, horizon, sol, soleil, calculés
// sur les cosinus depuis 4.6, mêmes réglages qu'en 4.3 convertis comme le fait le moteur), avec les
// couleurs du ciel actuel : sans nuage (couverture 0), l'image est celle d'aujourd'hui.
// Nuages : bruit fractal 2D projeté sur un plan horizontal à `altitude_m` au-dessus de la caméra
// (ancré au monde : la caméra passe dessous),
// décalé de `cloud_offset` (mètres parcourus au vent, cumulés par sky_clouds.gd). `layered` ajoute
// une seconde couche plus haute qui va 1,6 fois plus vite. Fondu vers l'horizon pour cacher la
// répétition. Les paramètres globaux du vent de P5 font évoluer la forme des nuages par vent fort.
// Compatible avec les moteurs Compatibility et Forward+.

global uniform vec3 wind_dir;
global uniform float wind_strength;
global uniform float wind_gust;
global uniform float wind_phase;

// Dégradé (mêmes noms et valeurs que ProceduralSkyMaterial)
uniform vec4 sky_top_color : source_color = vec4(0.38, 0.65, 0.98, 1.0);
uniform vec4 sky_horizon_color : source_color = vec4(0.65, 0.75, 0.85, 1.0);
uniform float sky_curve : hint_range(0, 1) = 0.15;
uniform float sky_energy = 1.0;
uniform vec4 ground_bottom_color : source_color = vec4(0.2, 0.169, 0.133, 1.0);
uniform vec4 ground_horizon_color : source_color = vec4(0.6463, 0.6558, 0.6708, 1.0);
uniform float ground_curve : hint_range(0, 1) = 0.02;
uniform float ground_energy = 1.0;
uniform float sun_angle_max = 0.5235988;   // 30° en radians
uniform float sun_curve : hint_range(0, 1) = 0.15;
uniform float exposure : hint_range(0, 128) = 1.0;

// Nuages
uniform float coverage : hint_range(0, 1) = 0.0;
uniform vec4 cloud_color : source_color = vec4(0.957, 0.969, 0.984, 1.0);
uniform float altitude_m = 2000.0;
uniform vec2 cloud_offset = vec2(0.0);   // mètres (x, z), cumulés au vent
uniform bool layered = false;
uniform float cloud_scale_m = 2600.0;    // taille d'un motif de base
uniform int octaves = 5;

float _hash21(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float _val_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	float a = _hash21(i);
	float b = _hash21(i + vec2(1.0, 0.0));
	float c = _hash21(i + vec2(0.0, 1.0));
	float d = _hash21(i + vec2(1.0, 1.0));
	return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

// Bruit fractal normalisé dans [0, 1] ; les octaves tournent pour casser l'alignement de la grille.
float _fbm(vec2 p, int n) {
	float sum = 0.0;
	float amp = 0.5;
	float norm = 0.0;
	mat2 rot = mat2(vec2(0.8, 0.6), vec2(-0.6, 0.8));
	for (int i = 0; i < 6; i++) {
		if (i >= n) {
			break;
		}
		sum += amp * _val_noise(p);
		norm += amp;
		p = rot * p * 2.03 + vec2(17.1, 9.2);
		amp *= 0.5;
	}
	return sum / max(norm, 1e-4);
}

// Densité d'une couche (0 à 1) au point `p` du plan des nuages.
float _layer(vec2 p, float evolve) {
	float d = _fbm(p / cloud_scale_m + vec2(evolve, -evolve * 0.7), octaves);
	float threshold = mix(0.72, 0.22, coverage);
	return smoothstep(threshold, threshold + 0.16, d);
}

void sky() {
	float v_angle = clamp(EYEDIR.y, -1.0, 1.0);
	vec3 sky = mix(sky_top_color.rgb, sky_horizon_color.rgb, clamp(pow(1.0 - v_angle, 0.6 / sky_curve), 0.0, 1.0));
	sky *= sky_energy;

	// Nuages, avant le soleil : le disque solaire reste visible à travers une couche fine seulement
	float alpha = 0.0;
	if (coverage > 0.0 && EYEDIR.y > 0.0) {
		float evolve = wind_phase * 0.004 * (0.3 + wind_strength);
		float t = altitude_m / max(EYEDIR.y, 0.02);
		vec2 p = POSITION.xz + EYEDIR.xz * t + cloud_offset;
		alpha = _layer(p, evolve);
		if (layered) {
			float t2 = (altitude_m * 1.8) / max(EYEDIR.y, 0.02);
			vec2 p2 = POSITION.xz + EYEDIR.xz * t2 + cloud_offset * 1.6 + vec2(5000.0, -3100.0);
			alpha = max(alpha, _layer(p2 * 0.7, evolve * 1.3) * 0.75);
		}
		// Fondu vers l'horizon (la répétition et l'aliasing se voient près de l'horizon)
		alpha *= smoothstep(0.01, 0.14, EYEDIR.y) * (0.9 + 0.1 * (1.0 - wind_gust));
	}

	if (LIGHT0_ENABLED) {
		float sun_angle = dot(LIGHT0_DIRECTION, EYEDIR);
		float sun_size = cos(LIGHT0_SIZE);
		float sun_max = cos(sun_angle_max);
		vec3 sun_col = LIGHT0_COLOR * LIGHT0_ENERGY;
		if (sun_angle > sun_size) {
			sky = sun_col;
		} else if (sun_angle > sun_max) {
			float c2 = (sun_size - sun_angle) / (sun_size - sun_max);
			sky = mix(sky, sun_col, clamp(pow(1.0 - c2, 1.6 / pow(sun_curve, 1.4)), 0.0, 1.0));
		}
	}

	if (alpha > 0.0) {
		// Nuage plus sombre en son cœur, éclairé côté soleil
		float sun_side = LIGHT0_ENABLED ? clamp(dot(LIGHT0_DIRECTION, EYEDIR) * 0.5 + 0.5, 0.0, 1.0) : 0.5;
		vec3 cloud = cloud_color.rgb * mix(0.9, 1.0, sun_side) * mix(1.0, 0.88, alpha * alpha) * sky_energy;
		sky = mix(sky, cloud, alpha * 0.95);
	}

	vec3 ground = mix(ground_bottom_color.rgb, ground_horizon_color.rgb, clamp(pow(1.0 + v_angle, 0.6 / ground_curve), 0.0, 1.0));
	ground *= ground_energy;

	COLOR = mix(ground, sky, step(0.0, EYEDIR.y)) * exposure;
}
