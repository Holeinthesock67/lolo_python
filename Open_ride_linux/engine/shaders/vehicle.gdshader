shader_type spatial;
render_mode cull_disabled;

// Véhicules du Lot P25 (vehicle_mesh.gd), sans texture.
// - CUSTOM0.x : zone (vehicle_mesh.gd VEH_*) : 0 peinture, 1 vitre, 2 noir, 3 métal, 4 phare, 5 feu arrière,
//   6 clair, 7 seconde couleur.
// - `instanced` faux (véhicules proches, un matériau par véhicule) : peinture `paint`, feux `lights` ;
//   vrai (MultiMesh de la circulation lointaine) : peinture dans COLOR (couleur d'instance), feux dans
//   INSTANCE_CUSTOM.x.
// - `lights` (0 ou 1) : phares allumés (brume, pluie ou soleil bas), feux arrière plus vifs ; flamme du
//   brûleur d'une montgolfière, feux à éclats d'un avion ou d'un hélicoptère (Lot P26).
// Corps du shader dans vehicle.gdshaderinc, partagé avec vehicle_far.gdshader.
#include "res://shaders/vehicle.gdshaderinc"
