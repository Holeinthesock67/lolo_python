shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

// Terrain multi-biome (lot U6, série U, Format .world v1 §8 quater et §9) : jusqu'à 4 biomes par tuile
// (3 en `low`, décision U-Q4), chacun avec ses couches de sol (herbe = `flat`, roche = `steep`,
// neige = `high`) choisies par sa propre règle de pente et d'altitude (L3). Les couleurs des biomes sont
// mélangées couche par couche, puis le décor de terrain_shade.gdshaderinc est appliqué une seule fois.
// Textures : deux Texture2DArray pour tout le parcours (biome_textures.gd) ; carte A = couleur et
// rugosité (alpha), carte B = normale XY et occlusion (bleu). Une couche sans texture garde sa couleur unie.

const int MAX_BIOMES = 20;     // BiomeIds.BIOMES
// Emplacements de sol : un par biome, puis un par couple (paysage du lot U25, biome de base) dont le thème
// donne le sol (biome_textures.gd MAX_LANDSCAPE_SLOTS) ; `biome_index` d'une tuile désigne un emplacement.
const int MAX_LANDSCAPE_SLOTS = 16;
const int MAX_SLOTS = MAX_BIOMES + MAX_LANDSCAPE_SLOTS;
const int MAX_LAYERS = MAX_SLOTS * 3;   // biome_textures.gd MAX_LAYERS

// Par tuile : poids des 4 biomes (RGBA, grille 17 × 17 du format, filtrage linéaire), indice de chaque
// biome dans les tableaux (-1 : canal vide), rectangle de la tuile dans le monde (x, z, côté, côté)
uniform sampler2D biome_weights : filter_linear, repeat_disable;
uniform vec4 biome_index = vec4(0.0, -1.0, -1.0, -1.0);
uniform vec4 tile_rect = vec4(0.0, 0.0, 1000.0, 1000.0);
// Modulation des poids par un bruit de 20 à 80 m : casse les fondus réguliers entre biomes
uniform float blend_noise : hint_range(0.0, 1.0) = 0.6;

// Par biome : (seuil de pente en degrés, limite de la couche haute en m, netteté du mélange, force des
// rides et dunes du sable) et indices des couches (herbe, roche, neige, -)
uniform vec4 biome_rule[MAX_SLOTS];
uniform vec4 biome_layers[MAX_SLOTS];
// Par couche : (couleur unie, 1 / échelle en m) et (indice dans ground_a, indice dans ground_b, -, -) ; -1 : pas de texture
uniform vec4 layer_color[MAX_LAYERS];
uniform vec4 layer_maps[MAX_LAYERS];
uniform sampler2DArray ground_a : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray ground_b : filter_linear_mipmap_anisotropic, repeat_enable;
// Rides (0,3 m) et dunes (40 m) du sable (lot U8) : faux relief seulement, crêtes perpendiculaires au vent
// du thème (direction vers laquelle il souffle, x et z du monde)
uniform vec2 sand_wind_dir = vec2(1.0, 0.0);
const float RIPPLE_M = 0.3;
const float DUNE_M = 40.0;
const float DUNE_H_M = 1.2;
const float RIPPLE_H_M = 0.012;
// Fond marin (lot SM1) : reflets mouvants de la surface (caustiques) sur le sol de l'emplacement `caustic_slot`
// (biome `reef`, -1 : aucun), de pleine force jusqu'à CAUSTIC_NEAR_M de la caméra, éteints à CAUSTIC_FAR_M
// (au-delà, le motif fin scintillerait) ; ajoutés en émission : visibles quelle que soit la lumière.
global uniform float anim_time;
uniform int caustic_slot = -1;
const float CAUSTIC_NEAR_M = 25.0;
const float CAUSTIC_FAR_M = 70.0;
const float CAUSTIC_GAIN = 0.55;

// Réseau de lignes claires qui ondulent : deux interférences de sinus déformés, sans texture.
float caustic(vec2 p, float t) {
	vec2 a = p * 0.45 + vec2(t * 0.30, t * 0.20);
	float c1 = sin(a.x + sin(a.y * 1.3 + t * 0.7)) * sin(a.y * 1.1 + sin(a.x * 0.9 - t * 0.6));
	vec2 b = p * 0.71 - vec2(t * 0.25, -t * 0.15);
	float c2 = sin(b.x * 1.2 + sin(b.y + t * 0.5)) * sin(b.y * 0.8 + sin(b.x * 1.4 + t * 0.4));
	return pow(clamp(1.0 - abs(c1 * 0.6 + c2 * 0.4), 0.0, 1.0), 6.0);
}

#include "res://shaders/terrain_shade.gdshaderinc"
// layer_color : couleurs sRGB des couches (Vector4), converties en linéaire comme les textures `ground_a`.
#include "res://shaders/couleur_srgb.gdshaderinc"

void vertex() {
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

// Lue dans les boucles des biomes et des couches : dérivées passées à textureGrad (voir sample_triplanar).
vec4 sample_layer_a(float layer, vec3 pos, float inv_scale, vec3 tw, vec3 dpdx, vec3 dpdy) {
	vec3 p = pos * inv_scale;
	vec3 dx = dpdx * inv_scale;
	vec3 dy = dpdy * inv_scale;
	return textureGrad(ground_a, vec3(p.zy, layer), dx.zy, dy.zy) * tw.x
		+ textureGrad(ground_a, vec3(p.xz, layer), dx.xz, dy.xz) * tw.y
		+ textureGrad(ground_a, vec3(p.xy, layer), dx.xy, dy.xy) * tw.z;
}

// Normale monde d'une carte B par projection triplanaire (mélange « whiteout ») et occlusion dans .w
vec4 sample_layer_b(float layer, vec3 pos, float inv_scale, vec3 tw, vec3 n, vec3 dpdx, vec3 dpdy) {
	vec3 p = pos * inv_scale;
	vec3 dx = dpdx * inv_scale;
	vec3 dy = dpdy * inv_scale;
	vec4 bx = textureGrad(ground_b, vec3(p.zy, layer), dx.zy, dy.zy);
	vec4 by = textureGrad(ground_b, vec3(p.xz, layer), dx.xz, dy.xz);
	vec4 bz = textureGrad(ground_b, vec3(p.xy, layer), dx.xy, dy.xy);
	vec2 tx = bx.xy * 2.0 - 1.0;
	vec2 ty = by.xy * 2.0 - 1.0;
	vec2 tz = bz.xy * 2.0 - 1.0;
	vec3 nx = vec3(tx + n.zy, abs(sqrt(max(1.0 - dot(tx, tx), 0.0))) * n.x);
	vec3 ny = vec3(ty + n.xz, abs(sqrt(max(1.0 - dot(ty, ty), 0.0))) * n.y);
	vec3 nz = vec3(tz + n.xy, abs(sqrt(max(1.0 - dot(tz, tz), 0.0))) * n.z);
	vec3 wn = normalize(nx.zyx * tw.x + ny.xzy * tw.y + nz.xyz * tw.z);
	return vec4(wn, bx.z * tw.x + by.z * tw.y + bz.z * tw.z);
}

// Faux relief du sable au point : dunes dissymétriques (pente douce au vent, raide sous le vent, crêtes
// ondulées) et rides effacées quand elles deviennent plus fines qu'un pixel
float sand_relief(vec2 q) {
	vec2 wd = sand_wind_dir;
	vec2 pd = vec2(-wd.y, wd.x);
	float a = dot(q, wd);
	float c = dot(q, pd);
	float f = fract(a / DUNE_M + 0.25 * sin(c / 55.0) + 0.6 * sd_noise(q / 90.0));
	float dune = f < 0.75 ? f / 0.75 : (1.0 - f) / 0.25;
	float rp = a / RIPPLE_M + 0.8 * sin(c / 1.7) + 1.5 * sd_noise(q / 2.0);
	float ripple = (0.5 + 0.5 * sin(rp * TAU)) * sd_visible(vec2(a, c), RIPPLE_M);
	return dune * DUNE_H_M + ripple * RIPPLE_H_M;
}

void fragment() {
	vec3 n = normalize(v_world_normal);
	vec2 q = v_world_pos.xz;
	vec3 dpdx = dFdx(v_world_pos);   // hors des boucles : dérivées des textures lues dans les branches
	vec3 dpdy = dFdy(v_world_pos);

	// Poids des biomes au point : grille de la tuile (centres des texels = points de la grille)
	vec2 uv = ((q - tile_rect.xy) / tile_rect.zw * 16.0 + 0.5) / 17.0;
	vec4 wb = texture(biome_weights, uv);
	// Bruit propre à chaque biome (décalé par son indice, pas par son canal) : deux tuiles voisines qui
	// rangent leurs biomes dans des canaux différents donnent le même mélange à leur bord commun.
	vec4 nz = vec4(0.5);
	for (int k = 0; k < 4; k++) {
		if (biome_index[k] >= 0.0) {
			vec2 o = vec2(biome_index[k] * 7.31, biome_index[k] * 3.17);
			nz[k] = sd_noise(q / 29.0 + o) * 0.7 + sd_noise(q / 83.0 + o.yx) * 0.3;
		}
	}
	wb *= step(vec4(0.0), biome_index) * (1.0 + (nz - 0.5) * 2.0 * blend_noise);
	wb = max(wb, vec4(0.0));
	float wsum = wb.x + wb.y + wb.z + wb.w;
	wb = wsum > 1e-5 ? wb / wsum : vec4(1.0, 0.0, 0.0, 0.0);

	// Netteté triplanaire moyenne des biomes présents, puis règle de L3 de chaque biome
	float sharp = 0.0;
	for (int k = 0; k < 4; k++) {
		if (wb[k] > MIN_LAYER_WEIGHT) {
			sharp += wb[k] * biome_rule[int(biome_index[k])].z;
		}
	}
	vec3 tri_weights = triplanar_weights(n, sharp);

	vec3 col[3] = vec3[3](vec3(0.0), vec3(0.0), vec3(0.0));
	float sand = 0.0;
	vec3 w = vec3(0.0);
	vec3 n_maps = vec3(0.0);
	float w_maps = 0.0;
	float ao = 0.0;
	float rough = 0.0;
	for (int k = 0; k < 4; k++) {
		if (wb[k] <= MIN_LAYER_WEIGHT) {
			continue;
		}
		int b = int(biome_index[k]);
		vec4 rule = biome_rule[b];
		sand += rule.w * wb[k];
		vec3 lw = layer_weights(n, v_world_pos.y, rule.x, rule.y, rule.z) * wb[k];
		w += lw;
		for (int r = 0; r < 3; r++) {
			if (lw[r] <= MIN_LAYER_WEIGHT) {
				continue;
			}
			int l = int(biome_layers[b][r]);
			vec4 lc = layer_color[l];
			vec4 maps = layer_maps[l];
			vec4 a = maps.x >= 0.0 ? sample_layer_a(maps.x, v_world_pos, lc.w, tri_weights, dpdx, dpdy) : vec4(lineaire(lc.rgb), roughness);
			col[r] += a.rgb * lw[r];
			rough += a.a * lw[r];
			if (maps.y >= 0.0) {
				vec4 nb = sample_layer_b(maps.y, v_world_pos, lc.w, tri_weights, n, dpdx, dpdy);
				n_maps += (nb.xyz - n) * lw[r];
				ao += nb.w * lw[r];
				w_maps += lw[r];
			}
		}
	}
	vec3 grass_c = w.x > 0.0 ? col[0] / w.x : vec3(0.0);
	vec3 rock_c = w.y > 0.0 ? col[1] / w.y : vec3(0.0);
	vec3 snow_c = w.z > 0.0 ? col[2] / w.z : vec3(0.0);
	vec3 n_shade = w_maps > 0.0 ? normalize(n + n_maps) : n;

	vec3 normal_out;
	ALBEDO = shade_layers(grass_c, rock_c, snow_c, w, n_shade, tri_weights,
		sand * sand_relief(q), VERTEX, VIEW_MATRIX, normal_out);
	NORMAL = normal_out;
	ROUGHNESS = rough * (1.0 - 0.35 * season_ground_wet);   // sol détrempé (lot U13)
	if (w_maps > 0.0) {
		AO = 1.0 - w_maps + ao;
	}
	if (caustic_slot >= 0) {
		float uw = 0.0;
		for (int k = 0; k < 4; k++) {
			uw += int(biome_index[k]) == caustic_slot ? wb[k] : 0.0;
		}
		float fade = 1.0 - smoothstep(CAUSTIC_NEAR_M, CAUSTIC_FAR_M, length(VERTEX));
		if (uw * fade > 0.01) {
			// Plus forts sur les sols tournés vers la surface
			EMISSION = ALBEDO * caustic(q, anim_time) * CAUSTIC_GAIN * uw * fade * clamp(n.y, 0.0, 1.0);
		}
	}
}
