# Série CH – Ligue d'hiver (mode championnat)

Cahier du mode, lot CH0 (21 novembre 2026). Rien n'est codé : ce document et les maquettes doivent être validés
par le propriétaire avant le premier lot de code (CH1).

Maquettes : `menus/ch0-ligue-hiver/` des fichiers du projet (hors dépôt), planche `planche_1280x720.png`.
FTP fictive de 250 W sur toutes les maquettes.

## 1. But

Passer la saison de home trainer sans perdre en physique, avec l'envie de faire un effort. La ligue donne le
rendez-vous de la semaine que Zwift obtient avec des humains : une manche par semaine contre les mêmes rivaux,
un classement qui bouge, un podium à la fin.

Repères du propriétaire : séance de 45 min, 1,5 séance par semaine, parfois 1 h 30 le dimanche. Une saison se
juge sur la régularité, y compris à effort modéré. Le fun ne se mesure pas (pas de question ni de note au bilan).

## 2. Décisions du propriétaire (21/11, 18 h 05 à 18 h 25)

| Point | Décision |
| --- | --- |
| Forme | Ligue d'hiver, classement aux points |
| Saison | 8 semaines ; plusieurs saisons dans un hiver |
| Rythme | Une manche par semaine |
| Résultats comptés | Les 6 meilleurs sur 8 : deux semaines jokers, sautées sans perte |
| Dureté | Bots calés sur la FTP pour environ 10 % de chances de gagner une manche (part juste à 12 : 8 %) ; la cote Elo (#941) tient ce réglage |
| Adversaires | 11 bots, les mêmes toute la saison, caractère fixe, nom, maillot, cote |
| Fin de saison | Podium et trophée, pas de divisions |
| Affichage | Une ligne à l'accueil ; classement à l'accueil et au bilan ; rien de plus pendant la course |
| Classique | Course de 1 h 30, facultative, à la date choisie par le joueur |

## 3. Réponses par défaut aux points ouverts (à confirmer avec les maquettes)

### 3.1 La manche

- **Durée : 45 min au plus, tout compris** : 10 min d'échauffement en ERG (règle déjà en place pour les courses,
  décision du 21/11), 25 à 30 min de course, 5 min de retour au calme en ERG léger, que l'on peut couper.
- **Modes existants à tour de rôle**, aucun mode nouveau. Le Cyber-Rogue n'entre pas dans la ligue : c'est une
  run en solo, sans adversaires classés. Calendrier type d'une saison (le parcours change d'une saison à l'autre) :

  | Semaine | Manche | Ce qui départage |
  | --- | --- | --- |
  | 1 | Course en tours, circuit vallonné | rouleurs |
  | 2 | Dernier survivant | sprint de survie |
  | 3 | Grand Prix des objets | tête et objets |
  | 4 | Vélodrome : course à l'élimination | placement, relances |
  | 5 | Course en ligne, arrivée en côte | grimpeurs |
  | 6 | Dernier survivant | sprint de survie |
  | 7 | Grand Prix des objets | tête et objets |
  | 8 | Finale : course en tours | tous |

- **Semaine** : du lundi au dimanche (semaine ISO, heure locale du PC). La manche de la semaine se court quand
  le joueur veut dans la semaine.
- **Un seul résultat par manche** : la première manche terminée compte. Une manche abandonnée avant l'arrivée
  peut être recourue tant que la semaine n'est pas finie (pas de « je la refais pour mieux faire »).
- **Semaine non courue** : 0 point, effacé par les 6 meilleurs résultats. Les bots, eux, courent la manche : leur
  résultat est simulé en temps accéléré (`bots_race`) le lundi suivant, pour que le classement avance.
- **Pause de saison** : pour un arrêt long (maladie, voyage), « Mettre la saison en pause » gèle le calendrier
  jusqu'à 4 semaines ; au-delà, la saison est close au classement du moment, sans trophée.

### 3.2 Les points

Barème par place, sur 12 coureurs. Toute arrivée rapporte des points, pour récompenser la régularité :

| Place | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | non courue |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Points | 25 | 20 | 16 | 13 | 11 | 10 | 9 | 8 | 7 | 6 | 5 | 4 | 0 |

- **Total de la saison** : somme des 6 meilleures manches, pour le joueur comme pour chaque bot.
- **Égalité** : plus de victoires, puis meilleure place à la finale.
- **Classique** : points du barème × 1,5 (37,5 pour une victoire), comptés **en plus** des 6 meilleures manches.
  Elle est facultative : la manquer ne coûte rien, la courir peut faire gagner des places. Les bots la courent
  aussi ; si le joueur ne l'a pas courue à la fin de la semaine 8, leur résultat est simulé à ce moment.

### 3.3 Les rivaux

- **11 bots fixes** tirés au début de la saison : 3 grimpeurs, 3 rouleurs, 3 sprinteurs, 2 diesels (profils de
  `bots.PROFILES`). Chaque bot a un nom fictif, un maillot (couleur **et** nom d'équipe écrit) et sa cote Elo.
  Ils restent les mêmes toute la saison ; une nouvelle saison en garde 8 et en remplace 3 (des têtes connues,
  un peu de neuf).
- **Dureté : 10 % de chances de victoire.** Le niveau des bots vient de la FTP du joueur et de sa cote Elo (#941) :
  le réglage vise une probabilité de victoire du joueur d'environ 10 % par manche, calculée par type de manche
  (CH2, banc de saisons simulées). Le haut du plateau est un peu plus fort que le joueur, le bas un peu plus
  faible : le joueur se bat pour des places tout le temps, pas seulement pour la victoire.
- **Intensité du jour (R1)** : la manche reste une course. La ligne « Intensité du jour » de l'écran Prêt (R1)
  s'affiche comme ailleurs ; le choix « facile » baisse les bots pour tout le monde et le résultat compte quand
  même, avec la mention « intensité facile » au classement de la manche. Pas d'exception de règle : c'est le
  même réglage que dans les autres modes.

### 3.4 Ce qui s'affiche

Peu d'ajouts, des mots écrits avant la couleur.

1. **Ligne d'accueil** (maquette 01), sous « Séance conseillée » : « Ligue d'hiver » à gauche ; à droite
   « 4e · manche 3/8 : Grand Prix, à courir cette semaine ». Quand la manche de la semaine est faite :
   « 4e · manche 3/8 faite · prochaine lundi ».
2. **Écran de la ligue** (maquette 02, ouvert par la ligne d'accueil) : classement général des 12 (place, nom,
   caractère, points, manches courues), la ligne du joueur encadrée et marquée « Toi » ; à gauche les actions
   « Courir la manche 3 : Grand Prix des objets », « Classique : choisir la date », « Calendrier »,
   « Mettre la saison en pause ».
3. **Bilan d'une manche** (maquette 03) : à la place du graphique de puissance, un encart « Ligue d'hiver »
   avec la place de la manche, les points gagnés, la place au général et le mouvement écrit (« gagne 2 places »),
   puis les cinq lignes autour du joueur au classement général.
4. **Fin de saison** (maquette 04) : podium des trois premiers et trophée écrit (« Trophée d'or », « d'argent »,
   « de bronze », ou « Trophée de régularité » pour 6 manches courues hors podium) ; le trophée rejoint la
   Collection (série BC). Action « Nouvelle saison ».
5. **Classique** (maquette 05) : choix de la date parmi les 8 semaines (jours proposés : samedis et dimanches),
   inscrite dans « Prochaine course » de la séance conseillée (`PLAN_SERIE_CO` §4, type « manche de
   championnat ») ; la séance conseillée évite une séance dure la veille (règle R2 existante).
6. **Pendant la course : rien de plus.** Pas de rappel de classement, pas de bandeau de points.

### 3.5 Lien avec la séance conseillée

La manche de la semaine non courue et la classique datée s'écrivent dans « Prochaine course » (CO3). Le conseil
garde ses règles ; la manche y apparaît comme une séance de jeu possible (« Lancer la manche 3 »). La ligue
ne force rien : on peut faire un entraînement ERG et courir la manche un autre jour.

## 4. Lots de code (après #939 Course, #941 Elo et R1)

Une branche et une PR par lot. Rangés dans la liste des lots en attente (`feuille-de-route/LOTS_EN_ATTENTE.md`
des fichiers du projet).

| Lot | Contenu | Vérification |
| --- | --- | --- |
| CH1 | Cœur de la saison, module pur `league.py` : calendrier de 8 manches, 11 rivaux fixes, barème, 6 meilleurs résultats, classique, pause, semaines non courues simulées ; saison dans `ligue.json` du profil, écriture sûre | Tests, saisons simulées |
| CH2 | Calibrage à 10 % de victoire depuis la FTP et la cote Elo, par type de manche | Banc de saisons simulées (modèle `elo_campagne`), pas d'essai vélo |
| CH3 | Lancer une manche : modes existants réglés pour 45 min (échauffement, course, retour au calme), résultat renvoyé à la saison ; révision IPC à réserver auprès du coordinateur (prochaine libre au 21/11 : 1.29) | Fumée + medium |
| CH4 | Écrans : ligne d'accueil, écran de la ligue, encart du bilan, podium et trophée | Captures low/medium/high validées |
| CH5 | Classique : choix de la date, course de 1 h 30, inscription dans la séance conseillée | Captures |

## 5. Hors série

- Pas de divisions, montées ni descentes.
- Pas de nouveau mode de course.
- Pas de mesure du fun, pas de question au bilan.
- Pas d'information de classement pendant la course.

## 6. Journal

- 21/11/2026 : cahier CH0 et maquettes 01 à 05, réponses par défaut du §3 à faire valider.
- 21/11/2026, 18 h 32 : maquettes 01 à 05 validées par le propriétaire (« Ok captures ») ; les réponses par défaut du §3 restent appliquées sauf correction.
- 21/11/2026, soir : CH1 codé (`league.py`, `docs/lots/LOT_CH1_saison_ligue.md`) ; la classique se court de la date choisie à la fin de la semaine 8 ; les pauses s'additionnent pour la limite de 4 semaines.
