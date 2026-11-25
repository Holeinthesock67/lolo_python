shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

// Terrain multi-biome (lot U6, série U, Format .world v1 §8 quater et §9) : jusqu'à 4 biomes par tuile
// (3 en `low`, décision U-Q4), chacun avec ses couches de sol (herbe = `flat`, roche = `steep`,
// neige = `high`) choisies par sa propre règle de pente et d'altitude (L3). Les couleurs des biomes sont
// mélangées couche par couche, puis le décor de terrain_shade.gdshaderinc est appliqué une seule fois.
// Textures : deux Texture2DArray pour tout le parcours (biome_textures.gd) ; carte A = couleur et
// rugosité (alpha), carte B = normale XY et occlusion (bleu). Une couche sans texture garde sa couleur unie.

const int MAX_BIOMES = 23;     // BiomeIds.BIOMES
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
const float CAUSTIC_GAIN = 0.32;

#include "res://shaders/terrain_shade.gdshaderinc"
// Trou dans le volume des tunnels proches (lot EA5)
#include "res://shaders/tunnel_cut.gdshaderinc"
// layer_color : couleurs sRGB des couches (Vector4), converties en linéaire comme les textures `ground_a`.
#include "res://shaders/couleur_srgb.gdshaderinc"

// Aspect des emplacements (lot U25-p2, biome_textures.gd `_fill_looks`, biome_model.gd `surface_look`) ; zéros : rien.
// Strates des parois (canyons) : (épaisseur d'une strate en m, force 0 à 1, première couleur, nombre de couleurs)
// dans `strata_color` (sRGB) ; elles teintent la couche `steep`, ondulent en grand et s'effacent quand une strate
// devient plus fine qu'un pixel.
const int MAX_STRATA_COLORS = 32;   // biome_textures.gd MAX_STRATA_COLORS
uniform vec4 slot_strata[MAX_SLOTS];
uniform vec4 strata_color[MAX_STRATA_COLORS];
// Gradins inondés (rizières) : (hauteur d'une marche en m, pente maximale en degrés, part des casiers en eau, -) sur la
// couche `flat` ; eau de `slot_water` (`water.color` du biome dans son paysage, sRGB), diguettes de la couche `steep` ;
// faux relief : chaque casier est plat (miroir du ciel), un mur à chaque marche.
uniform vec4 slot_terraces[MAX_SLOTS];
uniform vec4 slot_water[MAX_SLOTS];
// Cascades (fjords) : (densité 0 à 1, pente minimale en degrés, largeur en m, -) sur la couche `steep`, écume de
// `slot_foam` (sRGB) qui coule vers le bas, roche mouillée autour.
uniform vec4 slot_falls[MAX_SLOTS];
uniform vec4 slot_foam[MAX_SLOTS];
const float FALLS_CELL_M = 34.0;    // une cascade au plus par tranche de 34 m de paroi
const float DIKE_M = 0.8;           // largeur des diguettes
const float RICE_CELL_M = 180.0;    // une marche change d'état (eau ou riz) sur des portions de l'ordre de 180 m

float u25_hash(float x) {
	return fract(sin(x * 127.1 + 311.7) * 43758.5453);
}

// Pente réelle en degrés (relief affiché ramené à k = 1, comme layer_weights)
float real_slope_deg(vec3 n) {
	vec3 n_real = normalize(vec3(n.x, n.y * relief_k, n.z));
	return degrees(acos(clamp(n_real.y, -1.0, 1.0)));
}

// Facteur de teinte des strates pour la roche de l'emplacement (`base` : sa couleur unie, linéaire) ;
// `vis` : 1 de près, 0 quand une strate est plus fine qu'un pixel (teinte moyenne).
vec3 strata_tint(vec4 st, vec3 base, vec2 q, float y, float fw_y) {
	float band = st.x;
	float yy = y + (sd_noise(q / 260.0) - 0.5) * band * 3.0 + (sd_noise(q / 41.0) - 0.5) * band * 0.5;
	float t = yy / band;
	float i0 = floor(t);
	int off = int(st.z);
	int cnt = max(int(st.w), 1);
	vec3 c0 = strata_color[off + int(u25_hash(i0) * float(cnt)) % cnt].rgb;
	vec3 c1 = strata_color[off + int(u25_hash(i0 + 1.0) * float(cnt)) % cnt].rgb;
	vec3 c = mix(c0, c1, smoothstep(0.82, 1.0, fract(t)));
	vec3 avg = vec3(0.0);
	for (int i = 0; i < cnt; i++) {
		avg += strata_color[off + i].rgb;
	}
	avg /= float(cnt);
	float vis = 1.0 - smoothstep(0.25, 0.6, fw_y / band);
	vec3 target = lineaire(mix(avg, c, vis));
	return mix(vec3(1.0), target / max(base, vec3(0.02)), st.y);
}

// Gradins au point : (part d'eau, part de diguette, faux relief en m, -) ; `fw_q` : taille d'un pixel au sol (m).
vec4 terraces_at(vec4 te, vec3 n, vec2 q, float y, float fw_q) {
	float slope = real_slope_deg(n);
	float on = 1.0 - smoothstep(te.y - 3.0, te.y, slope);
	if (on <= 0.0) {
		return vec4(0.0);
	}
	float step_m = te.x;
	float yy = y + (sd_noise(q / 70.0) - 0.5) * step_m * 0.8;
	float t = yy / step_m;
	float f = fract(t);
	float tanv = max(tan(radians(slope)), 0.03);
	float spacing = step_m / tanv;                     // largeur d'un casier (m)
	float vis = 1.0 - smoothstep(0.25, 0.6, fw_q / spacing);
	float vis_dike = 1.0 - smoothstep(0.25, 0.6, fw_q / DIKE_M);
	float d_low = f * spacing;                         // distance au bord aval du casier (m)
	float d_high = (1.0 - f) * spacing;                // distance au mur amont
	float dike = max(1.0 - smoothstep(DIKE_M * 0.6, DIKE_M, d_low), 1.0 - smoothstep(DIKE_M * 0.4, DIKE_M * 0.7, d_high)) * vis_dike;
	// Chaque marche est en eau ou en riz sur de longues portions (bruit lent : pas de quadrillage ni de taches)
	float part = floor(sd_noise(q / RICE_CELL_M + vec2(floor(t) * 0.37, 0.0)) * 3.0);
	float wet = step(u25_hash(floor(t) * 3.7 + part * 11.3), te.z);
	float water = wet * (1.0 - dike) * vis;
	return vec4(water * on, dike * on, -f * step_m * vis * on, 0.0);
}

// Une rangée de cascades le long d'une paroi (`u` : coordonnée horizontale le long de la paroi, `y` : altitude) :
// (écume, roche mouillée).
vec2 falls_row(vec4 fa, float u, float y, float t, float fw) {
	float ci = floor(u / FALLS_CELL_M);
	if (u25_hash(ci * 1.91 + 5.3) > fa.x) {
		return vec2(0.0);
	}
	float width = fa.z * (0.6 + 0.8 * u25_hash(ci + 9.7));
	float center = (ci + 0.3 + 0.4 * u25_hash(ci + 3.1)) * FALLS_CELL_M + (sd_noise(vec2(ci * 2.3, y / 28.0)) - 0.5) * 5.0;
	float d = abs(u - center);
	// La cascade tombe d'un replat sur une partie de la paroi seulement
	float seg = smoothstep(0.38, 0.52, sd_noise(vec2(ci * 1.7 + 0.5, y / 140.0)));
	// Au loin, la cascade garde au moins un pixel de large, plus pâle d'autant (pas de fils qui scintillent)
	float half_w = max(width * 0.5, fw);
	float core = (1.0 - smoothstep(half_w * 0.7, half_w, d)) * seg * min(width * 0.5 / half_w, 1.0);
	float wet = (1.0 - smoothstep(width * 0.5, width * 1.8, d)) * seg;
	float flow = sd_noise(vec2(u / 0.7, (y + t * 7.0) / 2.6)) * 0.6 + sd_noise(vec2(u / 0.3, (y + t * 9.5) / 1.1)) * 0.4;
	return vec2(core * mix(0.65, 1.0, flow), wet);
}

// Cascades au point : (écume, roche mouillée) ; deux rangées projetées comme une texture triplanaire
// (le long de x sur une paroi tournée vers z, le long de z sur une paroi tournée vers x).
vec2 falls_at(vec4 fa, vec3 n, vec3 p, float t, float fw) {
	float on = smoothstep(fa.y, fa.y + 8.0, real_slope_deg(n));
	if (on <= 0.0) {
		return vec2(0.0);
	}
	float ax = abs(n.x);
	float az = abs(n.z);
	float wx = smoothstep(0.35, 0.65, az / max(ax + az, 1e-4));
	vec2 r = vec2(0.0);
	if (wx > 0.0) {
		r += falls_row(fa, p.x, p.y, t, fw) * wx;
	}
	if (wx < 1.0) {
		r += falls_row(fa, p.z + 1000.0, p.y, t, fw) * (1.0 - wx);
	}
	return r * on;
}


// Réseau de lignes claires qui ondulent : deux interférences de sinus déformés, sans texture.
float caustic(vec2 p, float t) {
	vec2 a = p * 0.45 + vec2(t * 0.30, t * 0.20);
	float c1 = sin(a.x + sin(a.y * 1.3 + t * 0.7)) * sin(a.y * 1.1 + sin(a.x * 0.9 - t * 0.6));
	vec2 b = p * 0.71 - vec2(t * 0.25, -t * 0.15);
	float c2 = sin(b.x * 1.2 + sin(b.y + t * 0.5)) * sin(b.y * 0.8 + sin(b.x * 1.4 + t * 0.4));
	return pow(clamp(1.0 - abs(c1 * 0.6 + c2 * 0.4), 0.0, 1.0), 6.0);
}


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
	float fw_y = fwidth(v_world_pos.y);           // strates et gradins (lot U25-p2), hors des branches
	float fw_q = max(length(dpdx.xz), length(dpdy.xz));
	float fw_p = max(length(dpdx), length(dpdy));   // taille d'un pixel sur une paroi (cascades)

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
	// Gradins et cascades (lot U25-p2) : parts, couleurs cumulées, faux relief
	float terr_water = 0.0;
	float terr_dike = 0.0;
	float terr_h = 0.0;
	vec3 water_c = vec3(0.0);
	vec3 dike_c = vec3(0.0);
	float falls_w = 0.0;
	float wet_w = 0.0;
	vec3 foam_c = vec3(0.0);
	for (int k = 0; k < 4; k++) {
		if (wb[k] <= MIN_LAYER_WEIGHT) {
			continue;
		}
		int b = int(biome_index[k]);
		vec4 rule = biome_rule[b];
		sand += rule.w * wb[k];
		vec3 lw = layer_weights(n, v_world_pos.y, rule.x, rule.y, rule.z) * wb[k];
		w += lw;
		vec4 st = slot_strata[b];
		vec3 strata_k = vec3(1.0);
		if (st.y > 0.0 && lw.y > MIN_LAYER_WEIGHT) {
			strata_k = strata_tint(st, lineaire(layer_color[int(biome_layers[b][1])].rgb), q, v_world_pos.y, fw_y);
		}
		vec4 te = slot_terraces[b];
		if (te.x > 0.0 && lw.x > MIN_LAYER_WEIGHT) {
			vec4 tr = terraces_at(te, n, q, v_world_pos.y, fw_q);
			terr_water += tr.x * lw.x;
			terr_dike += tr.y * lw.x;
			terr_h += tr.z * lw.x;
			water_c += lineaire(slot_water[b].rgb) * tr.x * lw.x;
			dike_c += lineaire(layer_color[int(biome_layers[b][1])].rgb) * tr.y * lw.x;
		}
		vec4 fa = slot_falls[b];
		if (fa.x > 0.0 && lw.y > MIN_LAYER_WEIGHT) {
			vec2 fr = falls_at(fa, n, v_world_pos, anim_time, fw_p);
			falls_w += fr.x * lw.y;
			wet_w += fr.y * lw.y;
			foam_c += lineaire(slot_foam[b].rgb) * fr.x * lw.y;
		}
		for (int r = 0; r < 3; r++) {
			if (lw[r] <= MIN_LAYER_WEIGHT) {
				continue;
			}
			int l = int(biome_layers[b][r]);
			vec4 lc = layer_color[l];
			vec4 maps = layer_maps[l];
			vec4 a = maps.x >= 0.0 ? sample_layer_a(maps.x, v_world_pos, lc.w, tri_weights, dpdx, dpdy) : vec4(lineaire(lc.rgb), roughness);
			col[r] += (r == 1 ? a.rgb * strata_k : a.rgb) * lw[r];
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
		sand * sand_relief(q) + terr_h, VERTEX, VIEW_MATRIX, normal_out);
	NORMAL = normal_out;
	ROUGHNESS = rough * (1.0 - 0.35 * season_ground_wet);   // sol détrempé (lot U13)
	// Gradins (eau lisse qui reflète le ciel, diguettes de terre) et cascades (roche mouillée, écume) : lot U25-p2
	if (terr_water + terr_dike > 0.001) {
		ALBEDO = mix(ALBEDO, dike_c / max(terr_dike, 1e-4), clamp(terr_dike, 0.0, 1.0));
		ALBEDO = mix(ALBEDO, water_c / max(terr_water, 1e-4), clamp(terr_water, 0.0, 1.0));
		ROUGHNESS = mix(ROUGHNESS, 0.06, clamp(terr_water, 0.0, 1.0));
	}
	if (wet_w + falls_w > 0.001) {
		ALBEDO *= 1.0 - 0.4 * clamp(wet_w, 0.0, 1.0);
		ALBEDO = mix(ALBEDO, foam_c / max(falls_w, 1e-4), clamp(falls_w, 0.0, 1.0));
		ROUGHNESS = mix(ROUGHNESS, 0.3, clamp(wet_w, 0.0, 1.0));
	}
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
	// Lot EA5 : terrain du volume d'un tunnel non dessiné, en dernier (dérivées calculées par tout le quad)
	if (tunnel_cut_inside(v_world_pos)) {
		discard;
	}
}
