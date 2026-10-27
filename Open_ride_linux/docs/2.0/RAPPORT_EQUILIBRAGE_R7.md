# Rapport d'équilibrage du Cyber-Rogue (lot R7, 27 octobre 2026)

Mesuré avec `python -m openride_core.tools.rogue_sim --all-objectives --duration 45 --runs 200 --jobs 4 --sensitivity` sur la table livrée (empreinte `d3204a19`, graine 1). Le rapport complet se refait avec cette commande ; rien dans les règles n'a été changé.

## Cyclistes simulés

Ils suivent la cible de la salle avec le bruit de leur profil (Débutant 4 %, Moyen 2,5 %, Confirmé 1,5 %), réussissent leurs Perfect Shifts et leurs appuis sur Z selon leur taux (30/50 %, 60/75 %, 90/95 %), relancent de 10 % quand le mur est à moins de 40 m, s'accrochent par un pic de puissance avant une parade, tiennent la cadence des tunnels, prennent la meilleure carte de leur liste (relance une fois si aucune n'est bonne). Le Fatigué est le Moyen avec −15 % de puissance après 30 min. Le temps passe par pas de 1 s ; 200 runs de 45 min prennent 48 s sur un cœur.

## Résultats pour le profil Moyen (45 min)

| Mesure | Endurance | Seuil | VO2max | Cible |
| --- | --- | --- | --- | --- |
| Salles gagnées | 100 % | 92 % | 81 % | 60 à 80 % |
| Défaites par run | 0 | 0 | 0 | 0 à 1 (Débutant : au plus 2) |
| Relances par run | 1,3 | 0,9 | 1,1 | 1 à 2 |
| IF | 0,66 | 0,81 | 0,82 | 0,62 à 0,72 / 0,80 à 0,88 / 0,80 à 0,90 |
| Minutes au-delà de 1,10 FTP | — | — | 2,8 | au moins 8 |
| Boss battu | 100 % | 100 % | 100 % | 50 à 70 % |
| Écart Débutant / Confirmé | 0 pt | 2 pts | 3 pts | moins de 25 pts |

Le Fatigué perd le boss à chaque run (0 % de boss battu) : après 30 min à −15 %, il ne tient plus la cible du boss.

## Cibles manquées et valeurs proposées

1. **Salles gagnées trop nombreuses, boss toujours battu.** Un cycliste qui suit la cible gagne presque toujours : les PV de l'ennemi (0,9 × cible moyenne × durée) sont sous ce que la cible produit. `hp_factor` est la constante qui fait le plus bouger la mesure (Seuil : 92 % → 47 % à +20 %). Essai (60 runs, Moyen) : à 1,03 les salles gagnées passent à 95 % (endurance), 73 % (seuil), 55 % (VO2max) ; à 1,00 à 100, 91 et 72 %. **Proposition : `hp_factor` = 1,02 pour le seuil et le VO2max, 1,05 pour l'endurance**, ce qui demande un `hp_factor` par objectif (ou 1,03 partout et une cible de 55 à 95 %) ; à décider par le propriétaire. La cible reste atteignable parce que les salles non gagnées se terminent en fuite de l'ennemi, sans défaite.
2. **Boss : 100 % de victoires pour Moyen, insensible à ±20 % sur toutes les constantes.** Le boss se gagne en suivant sa cible ; ses PV ne passent pas par `hp_factor` et ses zones de parade sont toujours réussies (les cyclistes simulés appuient). **Écart de règle à signaler (R5/R6) :** lier les PV du boss à une constante propre (`boss_hp_factor`) avant de fixer le taux de 50 à 70 %.
3. **Défaites jamais atteintes.** Le Firewall ne punit que les retards ; un cycliste à la cible reste devant. Une défaite arrive seulement après une erreur (braquet haut sur un pavé : le mur rattrape les 140 m d'avance). Cible « 0 à 1 » tenue, mais sans pression : à revoir avec `start_gap_m` (150) et `max_gap_m` (400) après la correction du point 1.
4. **Minutes au-delà de 1,10 FTP (VO2max) : 2,8 au lieu de 8.** Le Puncheur 15 s à 1,06 FTP et le Sprinteur 8 s à 1,50 FTP ne donnent pas assez. Constantes qui bougent la mesure : `room_grade_max`, `pad_min_gear`, `room_min_s`. **Proposition : `fw_bump` du Puncheur de 1,06 à 1,15** (profil `room_profiles.puncheur.vo2max`) ; à vérifier avec `--objective vo2max` après le point 1.
5. **Relances (Seuil : 0,9).** Presque dans la cible ; elles dépendent surtout du nombre de couloirs (`room_spread_s`, `room_max_s`) et de l'or de départ. Pas de changement proposé.
6. **IF d'endurance (0,66)** est dans la cible ; **IF du seuil (0,81) et du VO2max (0,82)** aussi, mais ces deux valeurs montent avec le point 1.

## Limites

Les cyclistes ne se défendent pas au mieux (pas de cartes d'attaque choisies selon la salle, pas de relance préventive pour creuser l'écart) ; les taux de Perfect Shift et d'appuis sont ceux du cahier. La sensibilité à ±20 % est mesurée sur 12 runs par essai : elle classe les constantes, elle ne donne pas de valeurs exactes.
