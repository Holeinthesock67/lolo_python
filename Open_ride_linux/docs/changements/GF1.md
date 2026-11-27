# GF1 : les bancs refusent un monde vide au lieu de rouler sur un autre parcours

- PR : à venir ; garde-fou 1 du fil « Fiabiliser les outils de banc » (27 novembre 2026) ; version : 6.0
- CHANGELOG (section « Corrigé ») :
  - Banc simulé : un `--world` vide ou un dossier `.world` absent arrête le banc en ENVIRONNEMENT (code 2),
    au lieu de rouler sans le dire sur le Col du lacet (banc pile à-coups du 27/11).
  - File des bancs : `{commun}`, dossier partagé par la fumée et les étapes d'une PR ; `{sortie}/..` refusé à
    la lecture de la file (c'était le dossier de l'étape seule, jamais celui de la fumée).
- SUIVI :
  - [ ] GF1 : sim_bench refuse un monde vide ou absent (code 2) ; file_bancs `{commun}`, `{sortie}/..` refusé.
