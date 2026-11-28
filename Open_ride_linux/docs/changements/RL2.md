# RL2 : relief IGN RGE ALTI en France pour le monde ouvert

- PR : #1073 (avec RL1) ; cahier : docs/lots/LOT_RL2_relief_ign_france.md ; version : 6.0
- CHANGELOG (section « Modifié ») :
  - Monde ouvert en France : relief au sol mesuré de l'IGN (pas de 5 m) ; ailleurs FABDEM, Copernicus en
    dernier repli.
  - 26/11 (banc multi-zones, zones françaises en DÉLAI : « Monde ouvert prêt » absent après 600 s) : les tuiles
    lointaines (maille de 50 m, jusqu'à 12 km) prenaient l'IGN, soit quelque 600 carrés de 1 km demandés un par un
    au départ. Elles prennent désormais FABDEM. Les carrés IGN des carrés proches se téléchargent en parallèle
    (6 à la fois), et après 5 échecs réseau de suite le service est coupé pour la séance, avec FABDEM en repli.
- SUIVI :
  - [ ] Monde ouvert au relief IGN en France, FABDEM ailleurs (lot RL2) ; essais RL3, parcours générés RL4.
