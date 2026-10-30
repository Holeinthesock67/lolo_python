shader_type spatial;

// Objets du décor construits par code, habillés par le shader (lot Y8 étapes 3 et 4) : panneaux, poteaux et
// bornes du bord de route (lot P14, roadside_props.gd), éoliennes (lot P12, wind_turbines.gd).
// Une matière par pièce (`kind`), motifs en coordonnées de l'objet (mètres), sans texture, avec la couche
// commune surface_detail.gdshaderinc ; faux relief coupé en `low` (`relief` = 0) :
//   0 panneau : tôle peinte à coins arrondis, liseré blanc et rebord sur la face, dos en tôle galvanisée
//     renforcé de deux raidisseurs, rayures fines ;
//   1 poteaux : acier galvanisé (paillettes de zinc), traces de rouille et terre au pied, colliers ;
//   2 borne : socle de béton gris, fût de béton blanc (grain, coulures, salissures montant du sol), tête au-dessus
//     de `head_from_m` en peinture rouge un peu écaillée, filet noir à la jonction ;
//   3 mât d'éolienne : tronçons boulonnés, porte au pied, bas du mât en dégradé vert, coulures ;
//   4 nacelle : capot à panneaux et grilles d'aération ;
//   5 pale : bord d'attaque usé vers le bout, salissure.
// Dimensions de la pièce : UV2 (largeur, hauteur) pour les maillages construits par roadside_props.gd, sinon
// `size_m` ; les pièces sont centrées sur l'origine.
// La couleur de la pièce est `base_color` ; le texte des panneaux reste un Label3D posé devant la face.

#include "res://shaders/surface_detail.gdshaderinc"

uniform int kind = 0;
uniform vec3 base_color : source_color = vec3(0.9);
uniform vec3 size_m = vec3(1.0);          // dimensions du maillage (centré sur l'origine), avant l'échelle du nœud
uniform float relief = 1.0;
uniform float head_from_m = 0.58;         // borne : hauteur du bas de la tête peinte

// Position dans la pièce en mètres (échelle du nœud comprise) et dimensions réelles de la pièce
varying vec3 v_obj;
varying vec3 v_obj_normal;
varying vec3 v_extent;

void vertex() {
	vec3 scale = vec3(length(MODEL_MATRIX[0].xyz), length(MODEL_MATRIX[1].xyz), length(MODEL_MATRIX[2].xyz));
	v_obj = VERTEX * scale;
	v_obj_normal = NORMAL;
	v_extent = (UV2.x > 0.0 ? vec3(UV2, size_m.z) : size_m) * scale;
}

// Couleur écrite à l'œil (sRGB) vers l'espace linéaire du rendu, comme base_color (source_color)
vec3 lin(vec3 c) {
	return pow(c, vec3(2.2));
}

void fragment() {
	vec3 p = v_obj;
	vec3 col = base_color;
	float h = 0.0;
	float rough = 0.6;
	float metal = 0.0;
	// Hauteur au-dessus du bas de la pièce (poteaux et bornes reposent sur le sol)
	float ground = p.y + v_extent.y * 0.5;
	float fine = sd_visible(p.xy + p.zz, 0.01);
	if (kind == 0) {
		bool face = v_obj_normal.z > 0.5;
		bool back = v_obj_normal.z < -0.5;
		// Distance au bord de la plaque à coins arrondis (rayon 6 cm), négative dedans
		vec2 q = abs(p.xy) - (v_extent.xy * 0.5 - vec2(0.06));
		float d = length(max(q, vec2(0.0))) + min(max(q.x, q.y), 0.0) - 0.06;
		float border = step(-0.045, d);
		float rim = smoothstep(0.012, 0.0, abs(d + 0.012));
		if (face) {
			col = mix(col, lin(vec3(0.95, 0.95, 0.93)), border);
			h = rim * 0.003;
			rough = 0.35;   // film rétroréfléchissant
		} else {
			// Dos et tranches : tôle galvanisée
			// Dos et tranches : tôle galvanisée, deux raidisseurs horizontaux au dos
			col = lin(vec3(0.62, 0.63, 0.64)) * (0.92 + 0.12 * sd_noise(p.xy * 9.0));
			float rib = back ? smoothstep(0.03, 0.02, abs(abs(p.y) - v_extent.y * 0.25)) : 0.0;
			col *= 1.0 - 0.12 * rib;
			h = rib * 0.004;
			metal = back ? 0.6 : 0.4;
			rough = 0.5;
		}
		// Rayures et salissure légère, plus marquées en bas du panneau
		float scratch = smoothstep(0.85, 0.95, sd_noise(vec2(p.x * 60.0, p.y * 4.0))) * fine;
		col *= 1.0 - 0.15 * scratch;
		col *= 1.0 - 0.12 * (1.0 - smoothstep(-0.5, 0.5, p.y / v_extent.y * 2.0)) * sd_noise(p.xy * 3.0);
	} else if (kind == 1) {
		// Acier galvanisé : paillettes de zinc, rouille éparse, terre au pied (coordonnées de la pièce : les
		// poteaux d'un panneau ne sont pas centrés sur l'origine)
		vec2 spangle = sd_pebbles(vec2((p.x - p.z) * 40.0, p.y * 40.0));
		col = lin(vec3(0.60, 0.61, 0.62)) * (0.78 + 0.4 * spangle.y);
		float rust = smoothstep(0.7, 0.85, sd_noise(vec2(atan(p.z, p.x) * 2.0, p.y * 3.0)) * (1.0 - smoothstep(0.0, 1.2, ground)) + 0.25 * sd_noise(p.xy * 7.0));
		col = mix(col, lin(vec3(0.42, 0.24, 0.12)), rust * 0.7);
		col = mix(col, lin(vec3(0.30, 0.25, 0.18)), (1.0 - smoothstep(0.0, 0.25, ground)) * 0.8);
		metal = 0.7 * (1.0 - rust);
		rough = mix(0.45, 0.9, rust);
		h = spangle.x * 0.0005;
	} else if (kind == 2) {
		// Borne : béton blanc, grain, coulures verticales, salissure montant du sol
		float grain = sd_noise(p.xy * 40.0 + p.zz * 40.0);
		float streak = sd_noise(vec2((p.x + p.z) * 18.0, p.y * 1.5));
		col *= 0.9 + 0.1 * mix(0.5, grain, fine);
		col *= 1.0 - 0.14 * smoothstep(0.55, 0.8, streak);
		h = grain * 0.002 * fine;
		rough = 0.9;
		if (ground > head_from_m) {
			// Tête peinte en rouge, écaillée par endroits ; filet noir à la jonction avec le fût
			float chip = smoothstep(0.84, 0.87, sd_noise(p.xy * 45.0 + p.zz * 31.0)) * fine;
			col = mix(lin(vec3(0.78, 0.09, 0.07)) * (0.92 + 0.1 * grain), lin(vec3(0.86, 0.85, 0.82)), chip);
			col = mix(col, lin(vec3(0.05)), smoothstep(0.012, 0.006, ground - head_from_m));
			h = -chip * 0.001;
			rough = mix(0.4, 0.85, chip);
		} else if (ground < 0.06) {
			// Socle de béton brut, plus foncé
			col = lin(vec3(0.68, 0.67, 0.63)) * (0.85 + 0.2 * grain);
			rough = 0.95;
		}
		col = mix(col, lin(vec3(0.35, 0.32, 0.26)), (1.0 - smoothstep(0.0, 0.3, ground + 0.08 * sd_noise(p.xz * 12.0))) * 0.6);
	} else if (kind == 3) {
		// Mât : joints de tronçons tous les quarts de la hauteur, porte au pied (côté +z), dégradé vert au
		// pied, coulures sous les joints
		float sec = fract(ground / v_extent.y * 4.0);
		float seam = smoothstep(0.004, 0.0, min(sec, 1.0 - sec) * v_extent.y / 4.0 - 0.02);
		col *= 1.0 - 0.35 * seam;
		col = mix(col, lin(vec3(0.42, 0.55, 0.38)), (1.0 - smoothstep(0.0, 0.12 * v_extent.y, ground)) * 0.55);
		float drip = smoothstep(0.6, 0.85, sd_noise(vec2(atan(p.z, p.x) * 6.0, ground * 0.05))) * (1.0 - sec) * 0.18;
		col *= 1.0 - drip;
		bool door = v_obj_normal.z > 0.6 && abs(p.x) < 0.5 && ground > 0.3 && ground < 2.5;
		col = door ? lin(vec3(0.55, 0.57, 0.58)) : col;
		h = -seam * 0.01;
		rough = 0.5;
	} else if (kind == 4) {
		// Nacelle : panneaux du capot (joints tous les 2,5 m) et grilles d'aération sur l'arrière
		vec3 q = fract(p / 2.5);
		float joint = 1.0 - smoothstep(0.0, 0.01, min(min(q.x, 1.0 - q.x), min(q.z, 1.0 - q.z)));
		col *= 1.0 - 0.25 * joint;
		float grille = step(0.5, fract(p.y * 8.0)) * step(0.35 * v_extent.z, p.z) * step(abs(p.x), 0.3 * v_extent.x);
		col *= 1.0 - 0.3 * grille;
		rough = 0.45;
	} else {
		// Pale : bord d'attaque (côté +x) usé et sali vers le bout
		float wear = smoothstep(0.25 * v_extent.x, 0.5 * v_extent.x, p.x) * smoothstep(-0.1, 0.5, p.y / v_extent.y);
		col = mix(col, col * lin(vec3(0.8, 0.79, 0.76)), wear * 0.8);
		col *= 0.96 + 0.06 * sd_noise(p.xy * vec2(2.0, 0.2));
		rough = mix(0.35, 0.7, wear);
	}
	if (relief > 0.0) {
		NORMAL = sd_bump(NORMAL, VERTEX, h * relief);
	}
	ALBEDO = col;
	ROUGHNESS = rough;
	METALLIC = metal;
}
