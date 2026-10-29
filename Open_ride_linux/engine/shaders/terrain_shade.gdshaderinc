// Couches de sol du terrain, communes au shader d'un thème (terrain.gdshader, lots E2, E3, L3, P6, Y11)
// et au shader multi-biome (terrain_biomes.gdshader, lot U6) : règle de pente et d'altitude de L3,
// décor procédural de l'herbe, de la roche et de la neige (Y11), facettes de la roche (E3), ombre des
// nuages (P6). Le décor est affine en la couleur de la couche : le shader multi-biome mélange d'abord les
// couleurs des biomes par couche, puis applique ce décor une seule fois (même résultat, coût d'un thème).

// Constantes de la fonction de référence (ThemeRenderParams, lot L3), remplies par terrain_material.gd :
// le shader ne recopie aucune valeur à la main.
uniform float snow_melt_band_m = 50.0;
uniform float steep_snow_start_deg = 44.0;
uniform float steep_snow_max_deg = 50.0;
uniform float min_slope_half_band_deg = 1.5;
uniform float max_slope_half_band_deg = 3.0;
uniform float roughness : hint_range(0.0, 1.0) = 1.0;

// Relief affiché (lots Q2 et Y15) : hauteurs étirées de relief_k autour de relief_origin_m. Roche et neige se
// décident sur le relief réel (pente et altitude ramenées à k = 1) : seule la géométrie est exagérée.
uniform float relief_k = 1.0;
uniform float relief_origin_m = 0.0;

// Décor du terrain (Lot E3 / SRS §8.1) : variation de l'herbe et facettes de la roche
uniform float rock_facet_strength : hint_range(0.0, 1.0) = 0.6;
uniform float detail_strength : hint_range(0.0, 1.0) = 1.0;

// Ombre des nuages (Lot P6, préréglage high seulement) : même bruit et même défilement que
// sky_clouds.gdshader (couche basse), projeté verticalement. Faux par défaut : rendu inchangé.
uniform bool cloud_shadow_enabled = false;
uniform float cloud_shadow_coverage = 0.0;
uniform vec2 cloud_shadow_offset = vec2(0.0);
uniform float cloud_shadow_altitude_m = 2000.0;
uniform float cloud_shadow_strength = 0.35;
uniform float cloud_shadow_scale_m = 2600.0;

// Herbe (Lot Y11, techniques H1 à H3, procédurales ; roche et neige suivent le même principe) : faux relief de brins (3 cm) et de mottes (30 cm)
// effacé quand il devient plus fin qu'un pixel, mouchetures de brins clairs et sombres de près,
// plaques d'herbe plus sèche ou plus verte (40 à 120 m), vagues de vent qui défilent dans le sens du
// vent du modèle P4 (mêmes paramètres globaux que tree_sway.gdshader). Réglé par `grass_relief` × `detail_strength`
// (0 : herbe d'avant Y11).
uniform float grass_relief : hint_range(0.0, 2.0) = 1.0;
uniform vec3 grass_dry_color : source_color = vec3(0.62, 0.6, 0.32);
global uniform vec3 wind_dir;
global uniform float wind_strength;
global uniform float wind_phase;
#include "res://shaders/surface_detail.gdshaderinc"

// Poids en dessous duquel une couche n'est pas échantillonnée (économie de lectures de texture).
const float MIN_LAYER_WEIGHT = 0.001;
const float SNOW_DRIFT_M = 1.5;           // taille des congères du faux relief de la neige (Lot Y11)

varying vec3 v_world_pos;
varying vec3 v_world_normal;

// Poids triplanaires YZ (axe x), XZ (axe y), XY (axe z)
vec3 triplanar_weights(vec3 n, float sharpness) {
	vec3 tri_p = pow(max(abs(n), vec3(1e-6)), vec3(max(sharpness, 0.01)));
	float tri_tot = tri_p.x + tri_p.y + tri_p.z;
	return tri_p / max(tri_tot, 1e-6);
}

vec4 sample_triplanar(sampler2D tex, vec3 pos, float inv_scale, vec3 weights) {
	vec2 uv_x = pos.zy * inv_scale;
	vec2 uv_y = pos.xz * inv_scale;
	vec2 uv_z = pos.xy * inv_scale;
	return texture(tex, uv_x) * weights.x + texture(tex, uv_y) * weights.y + texture(tex, uv_z) * weights.z;
}

// Poids (herbe, roche, neige) de la règle de L3 (SRS §8.1) pour une normale monde et une altitude
vec3 layer_weights(vec3 n, float alt, float slope_threshold, float snow_line, float sharpness) {
	// Pente et altitude réelles : la normale affichée a ses composantes horizontales multipliées par relief_k,
	// l'altitude affichée est étirée autour de relief_origin_m (n.y = cos(pente)).
	vec3 n_real = normalize(vec3(n.x, n.y * relief_k, n.z));
	float slope_deg = degrees(acos(clamp(n_real.y, -1.0, 1.0)));
	alt = relief_origin_m + (alt - relief_origin_m) / relief_k;

	// Demi-largeur de transition herbe/roche (lot L3, SRS §8.1)
	float half_band = clamp(12.0 / max(sharpness, 1.0), min_slope_half_band_deg, max_slope_half_band_deg);
	float t_rock = smoothstep(slope_threshold - half_band, slope_threshold + half_band, slope_deg);

	// Neige au-dessus de snow_line, fondue sur snow_melt_band_m, absente sur la roche raide
	float snow_alt = smoothstep(snow_line, snow_line + snow_melt_band_m, alt);
	float snow_slope = 1.0 - smoothstep(steep_snow_start_deg, steep_snow_max_deg, slope_deg);
	float w_snow = clamp(snow_alt * snow_slope, 0.0, 1.0);

	float rem = 1.0 - w_snow;
	return vec3(rem * (1.0 - t_rock), rem * t_rock, w_snow);
}

// Variation d'herbe à deux échelles (~8 m et ~60 m), bruits de surface_detail.gdshaderinc
float _grass_noise(vec3 pos) {
	float n8 = sd_noise(pos.xz / 8.0);
	float n60 = sd_noise(pos.xz / 60.0);
	return (n8 * 0.6 + n60 * 0.4) * 2.0 - 1.0;
}

// Densité des nuages au-dessus du point (copie de _fbm et _layer de sky_clouds.gdshader, 5 octaves)
float _cloud_density(vec2 p) {
	float sum = 0.0;
	float amp = 0.5;
	float norm = 0.0;
	mat2 rot = mat2(vec2(0.8, 0.6), vec2(-0.6, 0.8));
	vec2 q = p / cloud_shadow_scale_m;
	for (int i = 0; i < 5; i++) {
		sum += amp * sd_noise(q);
		norm += amp;
		q = rot * q * 2.03 + vec2(17.1, 9.2);
		amp *= 0.5;
	}
	float threshold = mix(0.72, 0.22, cloud_shadow_coverage);
	return smoothstep(threshold, threshold + 0.16, sum / norm);
}

// Couleur du sol à partir des couleurs de base des trois couches (`grass_c`, `rock_c`, `snow_c`, lues
// seulement quand leur poids dépasse MIN_LAYER_WEIGHT) et de leurs poids `w` ; écrit la normale de la
// vue dans `normal_out` (`vertex` : VERTEX, `view` : VIEW_MATRIX). `extra_h` : faux relief ajouté à
// celui des couches (m, positif ; rides et dunes du sable, lot U8 ; 0 pour le thème 1.x).
vec3 shade_layers(vec3 grass_c, vec3 rock_c, vec3 snow_c, vec3 w, vec3 n, vec3 tri_weights, float extra_h,
		vec3 vertex, mat4 view, out vec3 normal_out) {
	float w_grass = w.x;
	float w_rock = w.y;
	float w_snow = w.z;
	vec3 final_color = vec3(0.0);
	float grass_h = 0.0;
	if (w_grass > MIN_LAYER_WEIGHT) {
		vec3 c = grass_c;
		vec2 q = v_world_pos.xz;
		float relief = grass_relief * detail_strength;
		float gn = _grass_noise(v_world_pos);
		float grass_mod = 1.0 + gn * 0.08 * detail_strength;
		// Plaques plus sèches ou plus vertes (H2)
		float dry = smoothstep(0.45, 0.8, sd_noise(q / 120.0 + vec2(3.7, 1.9)) * 0.7 + sd_noise(q / 40.0) * 0.3) * relief;
		vec3 g = mix(c, c * 0.55 + grass_dry_color * 0.45, dry * 0.6);
		// Brins et mottes (H1) : relief et mouchetures, effacés au loin
		float vis_blade = sd_visible(q, 0.03) * relief;
		float vis_clump = sd_visible(q, 0.3) * relief;
		float blades = sd_noise(q / vec2(0.03, 0.012));
		float clumps = sd_noise(q / 0.3);
		grass_h = blades * 0.006 * vis_blade + clumps * 0.02 * vis_clump;
		g *= 1.0 + (blades - 0.5) * 0.35 * vis_blade + (clumps - 0.5) * 0.18 * vis_clump;
		// Vagues de vent (H3) : bandes claires de 6 m qui défilent dans le sens du vent
		vec2 wd = length(wind_dir.xz) > 1e-4 ? normalize(wind_dir.xz) : vec2(1.0, 0.0);
		vec2 wq = vec2(dot(q, wd) - wind_phase * (2.0 + 6.0 * wind_strength), dot(q, vec2(-wd.y, wd.x)) * 0.25);
		g *= 1.0 + (sd_noise(wq / 6.0) - 0.5) * 0.18 * wind_strength * relief;
		final_color += g * grass_mod * w_grass;
	}
	float rock_h = 0.0;
	if (w_rock > MIN_LAYER_WEIGHT) {
		vec3 c = rock_c;
		// Roche (Y11, même principe que l'herbe) : blocs de 60 cm et grain de 8 cm projetés sur les trois
		// plans, strates horizontales plus claires ou plus sombres
		float relief = grass_relief * detail_strength;
		vec3 p3 = v_world_pos;
		float blocks = sd_noise(p3.zy / 0.6) * tri_weights.x + sd_noise(p3.xz / 0.6) * tri_weights.y + sd_noise(p3.xy / 0.6) * tri_weights.z;
		float grit = sd_noise(p3.zy / 0.08) * tri_weights.x + sd_noise(p3.xz / 0.08) * tri_weights.y + sd_noise(p3.xy / 0.08) * tri_weights.z;
		float vis_blocks = sd_visible(p3.xz + p3.y, 0.6) * relief;
		float vis_grit = sd_visible(p3.xz + p3.y, 0.08) * relief;
		rock_h = blocks * 0.06 * vis_blocks + grit * 0.008 * vis_grit;
		// Strates effacées quand leur pas de 1,2 m devient plus fin qu'un pixel (moirage des versants au loin)
		float strata = (sd_noise(vec2(p3.y / 1.2, (p3.x + p3.z) / 40.0)) - 0.5) * sd_visible(vec2(p3.y, p3.x + p3.z), 1.2);
		final_color += c * (1.0 + (strata * 0.25 + (blocks - 0.5) * 0.15) * relief + (grit - 0.5) * 0.15 * vis_grit) * w_rock;
	}
	float snow_h = 0.0;
	if (w_snow > MIN_LAYER_WEIGHT) {
		vec3 c = snow_c;
		// Neige : congères douces de 1,5 m et grain de 15 cm, presque sans variation de teinte
		float relief = grass_relief * detail_strength;
		float drifts = sd_noise(v_world_pos.xz / SNOW_DRIFT_M);
		float crust = sd_noise(v_world_pos.xz / 0.15);
		snow_h = drifts * 0.04 * sd_visible(v_world_pos.xz, SNOW_DRIFT_M) * relief + crust * 0.004 * sd_visible(v_world_pos.xz, 0.15) * relief;
		final_color += c * (1.0 - (1.0 - drifts) * 0.04 * relief) * w_snow;
	}

	// Facettes de la roche (Lot E3 / SRS §8.1)
	vec3 flat_n = normalize(cross(dFdx(v_world_pos), dFdy(v_world_pos)));
	if (dot(flat_n, n) < 0.0) {
		flat_n = -flat_n;
	}
	vec3 rock_n = normalize(mix(n, flat_n, rock_facet_strength * detail_strength));
	// Normale du monde ramenée dans l'espace de la vue, celui de NORMAL
	normal_out = normalize((view * vec4(mix(n, rock_n, clamp(w_rock, 0.0, 1.0)), 0.0)).xyz);
	// Faux relief des trois couches (Y11) : une seule perturbation de la normale
	float surface_h = grass_h * w_grass + rock_h * w_rock + snow_h * w_snow + extra_h;
	if (surface_h > 0.0) {
		normal_out = sd_bump(normal_out, vertex, surface_h);
	}

	if (cloud_shadow_enabled && cloud_shadow_coverage > 0.0) {
		final_color *= 1.0 - cloud_shadow_strength * _cloud_density(v_world_pos.xz + cloud_shadow_offset);
	}
	return final_color;
}
