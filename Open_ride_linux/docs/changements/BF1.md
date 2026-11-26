# BF1 : bancs d'à-coups séparés à froid et à chaud

- PR : à venir ; cahier : docs/lots/LOT_BF1_bancs_froid_chaud.md ; version : 6.0
- CHANGELOG (section « Modifié ») :
  - Banc simulé : à shaders froids (`--shaders froid`, premier lancement), le départ est jugé à 1 s (écran animé) au
    lieu de 150 ms, et le chargement est relevé à titre indicatif ; à chaud, 150 ms reste le critère. Une seule
    image de la séance entre 100 et 200 ms est tolérée.
- SUIVI :
  - [ ] BF1 : bancs d'à-coups froid / chaud, une image lente tolérée (perf_probe.hitch_checks).
