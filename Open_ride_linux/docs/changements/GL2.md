# GL2 : détecteur de gel du fil principal de l'engine

- PR : à venir ; cahier : docs/lots/LOT_GL2_detecteur_gel_fil_principal.md ; version : 2.0
- CHANGELOG (section « Ajouté ») :
  - Le journal de l'engine signale tout gel de l'image de plus d'une seconde (lignes `[gel]`), avec l'étape en
    cours et sa durée ; `[perf-rendu]` donne le vrai temps d'image au lieu d'un temps plafonné à 150 ms.
- SUIVI :
  - [ ] GL2 : gels du fil principal nommés dans le journal (banc `gl2_biarritz` à faire sur le PC).
