# NV2 : ville néon, ciel, lumière et brume

- PR : #1089 ; cahier : docs/lots/LOT_NV2_ciel_lumiere_ville_neon.md ; version : 6.0
- CHANGELOG (section « Ajouté ») :
  - Paysage « ville néon » : ciel rose et orange avec un grand soleil bas, lumière rasante et brume rose au départ, puis nuit violette étoilée après une dizaine de minutes. Ce paysage impose sa lumière, quelle que soit l'heure choisie. Rien ne change ailleurs.
- SUIVI :
  - [ ] **Ville néon : ciel, lumière, brume** (lot NV2, 26 novembre) : `neon_fx.gd`, `atmosphere_view.gd` (`set_neon`), `sky_clouds.gdshader` (`neon_level`) ; image par défaut inchangée au pixel près ; banc PC à faire.
- Correctif du 27 novembre (banc PC de la Lagune, temps d'image p99 de 25,8 à 28,2 ms pour 25) : la nuit tombe par 96 paliers (`NeonFx.NIGHT_STEPS`) au lieu de changer à chaque image ; le ciel, le brouillard et la lumière étaient reposés 4 fois par seconde pendant 8 minutes (1 910 fois), ils le sont 97 fois. Étapes de sonde ajoutées pour attribuer le décor vivant (`decor_meteo`, `decor_faune`, `decor_cyclistes`, `decor_trafic`, `decor_ciel_bateaux`, `decor_foule`, `decor_passants`) et le mobilier de rue (`rue`).
