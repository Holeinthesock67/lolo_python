# BO1 : boucle du monde ouvert qui se figeait au passage au retour

- PR : #1084 ; cahier : aucun (défaut trouvé par le banc de la mini-carte, 25/11) ; version : 6.0
- CHANGELOG (section « Corrigé ») :
  - Monde ouvert, « Boucle de X km » : la route ne s'arrête plus vers 40 % de la boucle (pause « plus de route connue » sans fin, vue à Sevrier) ; le retour vise l'arête du départ, recalculée à chaque carrefour, et sans retour connu le générateur met le cap vers le départ au lieu de prendre une route au hasard.
  - Une route bloquée n'est plus republiée à chaque pas (plusieurs fois par seconde, l'engine relisait toute la route) ; elle repart d'elle-même si le graphe se complète.
- SUIVI :
  - [ ] BO1 : boucle du monde ouvert prolongée après 40 % (départ = arête du départ, repli cap vers le départ), route bloquée jamais republiée en boucle ; banc PC `ow_minicarte` en boucle de 10 km (cache séparé) à refaire.
