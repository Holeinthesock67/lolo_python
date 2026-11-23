# Cadrage – Courbe de puissance sur 6 mois et FTP estimée, dans le profil

Date : 21 novembre 2026. Statut : **cadrage validé par le propriétaire le 21 novembre (§7 et §10)** ; copie de travail du cadrage, lots PP1 à PP8.
Lecture faite sur `main` (0bece20b). Nom de série proposé : **PP** (« profil de puissance »), libre dans l'index des lots.

## 1. Réponse courte

Oui aux trois demandes, et l'essentiel des données existe déjà.

1. **Courbe de puissance sur 6 mois** : faisable sans rien enregistrer de plus. Le jeu écrit déjà un relevé par seconde pour chaque séance.
2. **FTP estimée** : faisable. Deux briques existent déjà (test de rampe O10, estimation CP et W' R16). Il manque une estimation « au fil des séances », visible et expliquée.
3. **Dans le profil et reliée au profil** : c'est la pente naturelle. Chaque profil de joueur a déjà son dossier, ses séances, sa FTP et son cache de puissances. Il manque seulement l'écran.

Correction du 21/11 19 h 29 (propriétaire) : W' n'est plus utilisé en Cyber-Rogue. Le doc n'y rattache donc plus rien.

## 2. Ce que le jeu enregistre déjà

| Donnée | Où (hors dépôt) | Utile pour |
| --- | --- | --- |
| Journal de séance, un relevé par seconde : puissance, cadence, FC, `mode` (SIM, ERG, ROGUE), `target_w` (cible ERG) | `~/OpenRide/Profils/<id>/Activities/.journal/*.jsonl` | Courbe, tri ERG ou libre |
| En-tête du journal : `source` (`live`, `simulated`, `replay`), `ftp_w` du jour, `profile_id`, `workout_id` | même fichier | Écarter les séances simulées et rejouées |
| Pauses, coupures du trainer (`event`, `device`) | même fichier | Ne pas compter un effort « à cheval » sur une pause |
| Résultat d'un test de rampe (`ftp_test`) | même fichier | FTP mesurée, la plus fiable |
| FIT de chaque séance | `~/OpenRide/Profils/<id>/Activities/*.fit` | Secours si un journal manque |
| Cache des meilleures puissances sur 3, 5, 8, 12 et 20 min (lot R16) | `~/OpenRide/Profils/<id>/.cache/mmp.json` | Base à étendre |
| FTP, poids du profil (lot MJ4) | `~/OpenRide/Profils/<id>/profil.toml` | Comparaison FTP réglée / estimée |

Rien de tout cela n'est dans le dépôt, et rien n'y entrera : les tests utiliseront des séances fabriquées (modèle à 250 W).

### Ce qui manque

- La courbe complète : R16 ne garde que 5 durées, sur 90 jours, et ne sert qu'à W' pour Cyber-Rogue.
- Les durées courtes (5 s à 1 min) et longues (30 et 60 min).
- Le tri entre effort libre et effort imposé par l'ERG.
- La date et la séance de chaque record de durée.
- Un défaut du calcul actuel : les secondes de pause sont retirées puis les morceaux sont recollés. Un « meilleur 20 min » peut donc contenir une pause cachée. À corriger : une fenêtre ne traverse jamais une pause ni une coupure du trainer.
- Tout l'écran : rien n'est affiché au joueur aujourd'hui, et l'ancienne proposition de W' au départ de Cyber-Rogue disparaît avec la jauge W' (R25).

Point à vérifier sur le PC (non joignable ce soir) : le nombre réel de séances `live` des 6 derniers mois. Le jeu ne supprime aucun journal, donc l'historique est complet depuis le début du projet, mais pas plus ancien.

## 3. Algorithme proposé

### 3.1 Courbe

- **Durées** : 5 s, 15 s, 30 s, 1 min, 2 min, 3 min, 5 min, 8 min, 12 min, 20 min, 30 min, 45 min, 60 min (13 points, lisibles au menu ; les 5 durées de R16 sont incluses).
- **Par séance** : meilleure puissance moyenne de chaque durée, par sommes cumulées, sur des morceaux continus (coupés aux pauses, aux coupures du trainer et aux trous de plus de 2 s).
- **Séances gardées** : celles du profil en cours, `source = live` (le profil d'essai garde aussi ses séances simulées, comme aujourd'hui), jamais les rejeux.
- **Garde-fous** : relevé au-dessus de 2 000 W ou saut irréaliste écarté (pic de capteur) ; séance de moins de 5 min ignorée pour les durées longues seulement.
- **Fenêtres** : « 6 derniers mois » (courbe principale, 183 jours glissants) et « 6 dernières semaines » (forme du moment), tracées ensemble pour voir l'évolution.
- **Chaque point garde** : watts, date, séance, et le mot **« libre »** ou **« ERG »**.

### 3.2 Séances ERG : la règle proposée

En ERG, c'est la consigne qui fixe la puissance : l'effort est réel, mais il n'est pas forcément maximal.

- **Dans la courbe** : les séances ERG comptent (les watts ont bien été produits), avec le mot « ERG » sur le point.
- **Dans l'estimation de FTP** : elles ne comptent pas. Sinon l'estimation tourne en rond : une séance réglée à 100 % d'une FTP de 250 W « prouverait » une FTP de 250 W.
- **Exception** : le test de rampe, qui est en ERG mais fait pour aller au bout.

### 3.3 FTP estimée

Trois sources, de la plus fiable à la moins fiable. L'écran en montre une seule, avec sa source écrite en toutes lettres.

| Rang | Source | Formule | Existe ? |
| --- | --- | --- | --- |
| 1 | Test de rampe de moins de 6 semaines | 75 % de la meilleure minute | Oui (O10) |
| 2 | Puissance critique (CP) sur les efforts libres de 3 à 20 min | travail = CP × durée + W' | Oui (R16), à brancher sur la nouvelle courbe |
| 3 | Meilleur effort libre de 20 min | 95 % de la moyenne | À écrire (petit) |

- **Confiance en mots** : « Fiable », « Indicative », « Pas assez de données », avec la raison (« aucun effort libre de plus de 12 min depuis 6 semaines »).
- **Avertissement permanent** : l'estimation suppose des efforts à fond ; sans effort à fond, elle est trop basse.
- **Jamais d'écriture automatique** : le jeu propose « Utiliser 250 W comme FTP », le joueur accepte ou non (même règle que le test de rampe). Aucune proposition pendant qu'il roule : seulement au menu et sur le bilan de fin de séance.
- **Calibration** : la puissance vient du home trainer. Un changement de calibration décale toute la courbe ; le jeu ne peut pas le détecter. Une ligne d'aide le dit.

### 3.4 Coût de calcul

- Par séance d'une heure : 13 durées × 3 600 relevés, environ 50 000 additions, quelques dizaines de millisecondes en Python. Fait une seule fois par fichier, puis lu dans le cache du profil.
- Premier calcul sur 6 mois (ordre de grandeur 150 séances) : quelques secondes, à cause de la lecture des journaux. Ensuite instantané. R16 tient déjà « 200 séances en moins de 5 s avec le cache ».
- Jamais dans la boucle à 50 Hz : calcul à l'ouverture de l'écran et à la fin d'une séance. Aucun effet sur le GPU.

## 4. Écran proposé

Accès : accueil, ligne « Profil : … », puis nouvelle ligne **« Ma puissance »** (à côté de « Historique » et des records). Tout appartient au profil en cours ; changer de profil change la courbe.

Maquette (valeurs fictives, FTP 250 W) :

```
MA PUISSANCE — profil « Cycliste 1 »                 6 derniers mois | 6 dernières semaines

  W
 900 ┤●
 700 ┤ ●
 500 ┤   ●
 400 ┤     ●──○
 300 ┤          ●──●──○
 250 ┤- - - - - - - - - ●──●──●- - - - FTP réglée 250 W
 200 ┤                           ●──●
     └─┬───┬───┬───┬───┬───┬───┬───┬───┬──
      5 s 30 s 1 min 3 min 5 min 12  20  60 min
      ● 6 derniers mois    ○ 6 dernières semaines (quand elle est plus basse)

  Durée     Meilleur    Quand         Séance                Effort
  5 s       880 W       12 oct.       Grand Prix            libre
  1 min     430 W       3 nov.        Vélodrome             libre
  5 min     310 W       28 oct.       Col fictif            libre
  20 min    262 W       15 nov.       Route des Érables     libre
  60 min    228 W       9 nov.        Seuil 3 × 15          ERG

  FTP RÉGLÉE : 250 W          FTP ESTIMÉE : 249 W — Indicative
  Source : meilleur effort libre de 20 min du 15 nov. (95 % de 262 W)
  [ Utiliser 249 W comme FTP ]   [ Faire un test de rampe ]   [ Évolution mois par mois ]
```

- Tout en watts ; W/kg en seconde ligne seulement si le poids du profil est réglé.
- Mots écrits partout (« libre », « ERG », « Indicative ») ; la couleur ne porte jamais l'information seule.
- Sous-écran « Évolution » : FTP estimée et meilleurs 5 min et 20 min, mois par mois sur 6 mois.
- Sur le bilan de fin de séance : une ligne « Nouveau record sur 5 min : 310 W » quand un record tombe. Rien pendant la séance.
- Profil sans données : « Roule une première séance pour voir ta courbe », et le bouton du test de rampe.

## 5. Liens possibles (à décider, hors premier lot)

- **Bots et Elo** : l'intensité du jour (R1 de la stratégie des bots) et le calibrage BT1 lisent la FTP réglée. Si la FTP estimée s'écarte de plus de 5 %, le menu le signale ; rien ne change sans accord.
- **Cyber-Rogue** : aucun lien. La jauge W' y est supprimée (décision du 21/11, lot R25, PR #956) ; l'estimation de W' de R16 n'a donc plus d'usage en jeu. Son calcul de CP est repris pour la FTP estimée (§3.3), et son cache est remplacé par celui de la courbe.
- **Coach et plans** : même signal « ta FTP a peut-être changé » avant de démarrer un plan.
- **Ligue d'hiver** : catégorie proposée d'après le meilleur 20 min, à cadrer avec ce lot-là.

## 6. Découpage en lots

| Lot | Contenu | Langage | Contrat IPC | Taille |
| --- | --- | --- | --- | --- |
| **PP1** | Core : courbe à 13 durées par profil, fenêtres 6 mois et 6 semaines, tri libre / ERG, pauses respectées, cache version 2 ; outil `python -m openride_core.tools.power_curve` (texte et `--json`)  ; l'ancien cache de R16 (W' de Cyber-Rogue, plus utilisé depuis R25) est remplacé, et le code de proposition de W' devenu mort est retiré si R25 est fusionné. Tests sur séances fabriquées. | Python | aucun | Moyenne |
| **PP2** | Core : FTP estimée (3 sources, confiance, raison), évolution par mois, acceptation par le joueur via le chemin existant des réglages du profil. | Python | aucun | Petite |
| **PP3** | Contrat **1.29** : `list_power_curve` et réponse `power_curve` (13 points, FTP estimée, évolution), en une trame de moins de 4 096 octets. Écran « Ma puissance » dans le profil, scénario du banc des menus, captures low, medium et high. | Python + GDScript | 1.29 | Moyenne |
| **PP4** | Ligne « Nouveau record de durée » sur le bilan de fin de séance ; signal « FTP à revoir » au menu. | Python + GDScript | champ facultatif | Petite |
| **PP5** (option) | Liens bots, coach, ligue d'hiver (§5). | à cadrer | à cadrer | à cadrer |

PP1 et PP2 sont de la logique pure : fumée + medium, pas d'essai vélo. PP3 demande la validation des captures du menu avant fusion. Aucun de ces lots ne touche le monde ouvert ni la file de l'essai de dimanche.

## 7. Questions pour le propriétaire

1. Séances ERG : d'accord pour les montrer dans la courbe avec le mot « ERG », et les écarter de l'estimation de FTP ? **DÉCIDÉ : oui (propriétaire, 21/11 19 h 31).**
2. FTP estimée : simple proposition à accepter au menu (recommandé), ou mise à jour automatique ? **DÉCIDÉ : proposition à accepter au menu (propriétaire, 21/11 19 h 55).**
3. Place de l'écran : dans le profil, ligne « Ma puissance » (recommandé), ou dans « Historique » ? **DÉCIDÉ : dans le profil (propriétaire, 21/11 19 h 55).**
4. Les 13 durées conviennent-elles, ou faut-il en ajouter (10 s, 10 min, 90 min) ?
5. Quand lancer : après l'essai de dimanche et la file en cours (recommandé), ou PP1 tout de suite en parallèle (aucun fichier commun avec la file) ? **DÉCIDÉ : dimanche 22/11, après l'essai vélo (propriétaire, 21/11 19 h 55).**

## 8. Remue-méninges : à quoi sert la courbe, et comment l'exploiter

Idées en vrac, classées par usage. Rien n'est décidé ; la colonne « Effort » sert à choisir.

### 8.1 Se connaître (lecture seule)

| Idée | Ce que voit le joueur | Effort |
| --- | --- | --- |
| **Profil de cycliste** en un mot | « Tu es plutôt PUNCHEUR » (sprinteur, puncheur, grimpeur, rouleur), tiré du rapport entre 5 s, 1 min, 5 min et 20 min | Petit |
| **Point fort, point faible** | « Ton point fort : 1 min. À travailler : 20 min » | Petit |
| **Forme du moment** | Courbe des 6 dernières semaines sous celle des 6 mois : « Tu es à 96 % de ton meilleur niveau sur 5 min » | Inclus dans PP1 |
| **Records de durée** | Ligne « Nouveau record sur 5 min : 310 W » au bilan, et liste des records dans le profil | PP4 |
| **Record vieillissant** | « Ton meilleur 20 min date de 4 mois : il sortira de la courbe dans 2 mois » | Petit |

### 8.2 Régler le jeu à la bonne difficulté

| Idée | Effet | Effort |
| --- | --- | --- |
| **FTP toujours à jour** | Signal « ta FTP a peut-être changé » ; toutes les séances ERG et les plans suivent | PP2 |
| **Bots à ta mesure selon la durée** | Une course de 10 min se cale sur ton meilleur 10 min, une de 40 min sur ton 40 min, au lieu d'un seul pourcentage de FTP. Complète BT1 et l'Elo (#941) | Moyen |
| **Durée tenable annoncée** | Avant une course : « À ce niveau, tu tiens environ 12 min » | Petit |
| **Sprints et attaques** | Seuil d'attaque des boîtes « ! ATTAQUE » du Grand Prix calé sur ton 15 s et ton 1 min, pas sur un chiffre fixe | Moyen |
| **Élimination au vélodrome** | Rythme des tours calé sur ton 1 à 3 min | Petit |

### 8.3 Donner des objectifs

| Idée | Ce que voit le joueur | Effort |
| --- | --- | --- |
| **Défi « bats ton record »** | Au menu : « Défi du jour : 5 min au-dessus de 310 W ». Le jeu propose le parcours qui convient (une bosse de 5 min) | Moyen |
| **Fantôme de ton record** | Un bot roule à la puissance de ton meilleur effort sur la durée de la bosse ou du segment | Moyen (les fantômes existent) |
| **Trous de la courbe** | « Tu n'as aucun effort à fond de 8 à 12 min : essaie le col fictif » | Petit |
| **Trophées** | Maillot ou pièce débloqué à un palier (300 W sur 5 min), dans la progression existante | Petit |
| **Temps prévu sur un col** | Sur la fiche d'un parcours : « Temps estimé pour toi : 23 min », calculé depuis la courbe et non depuis la FTP seule | Petit |

### 8.4 Mieux s'entraîner

| Idée | Effet | Effort |
| --- | --- | --- |
| **Séance conseillée par le coach** | Le coach propose la séance qui travaille le point faible (« 4 × 4 min pour ton 5 min ») | Moyen (coach existant) |
| **Intervalles calés sur la courbe** | Un 30/30 réglé sur ton meilleur 1 min plutôt que sur un pourcentage de FTP, plus juste pour les efforts courts | Moyen |
| **Bilan de plan** | À la fin d'un plan de 6 semaines : courbe avant et après | Petit |
| **Test de rampe proposé au bon moment** | Seulement quand la FTP estimée s'écarte, pas à date fixe | Petit |

### 8.5 À éviter

- Afficher la courbe ou un record pendant la séance : contraire à la règle « pas de consigne en roulant ». Tout se passe au menu et au bilan.
- Changer la difficulté tout seul sans le dire : toujours une proposition, écrite en watts.
- Comparer avec d'autres personnes ou des tables « niveau mondial » : hors sujet pour un jeu local, et décourageant.
- Exporter la courbe hors du PC : elle reste dans le dossier du profil.

### 8.6 Ordre conseillé si tout plaît

1. PP1 à PP4 (courbe, FTP estimée, écran, records au bilan) : le socle.
2. Profil de cycliste, point fort et point faible, forme du moment : petits ajouts sur l'écran, très parlants.
3. Bots et courses calés sur la durée, temps prévu sur un parcours : là où la courbe change vraiment le jeu.
4. Défis, fantôme du record, conseil du coach : la motivation à long terme.

## 9. Faut-il des tests réguliers ? (réponse du 21/11)

Principe : **aucun test imposé**. La courbe se remplit avec les séances normales ; elle n'est juste que là où il existe un effort à fond récent.

- 5 s à 30 s : sprints du Grand Prix et du vélodrome.
- 1 à 3 min : élimination, attaques, bosses courtes.
- 5 à 12 min : cols, segments chronométrés, courses courtes.
- 20 à 60 min : courses longues ; zone le plus souvent vide.

L'écran signale les durées sans effort à fond depuis 6 semaines et propose un défi ou un parcours pour combler le trou (au menu seulement). Le test de rampe reste proposé quand la FTP estimée s'écarte de la FTP réglée, pas à date fixe.

## 10. Décisions du propriétaire (21/11) et lots qui en découlent

- Q1 : séances ERG dans la courbe avec le mot « ERG », écartées de la FTP estimée : **oui**.
- Q2 : FTP estimée en **proposition** à accepter au menu, jamais d'écriture automatique.
- Q3 : écran « Ma puissance » **dans le profil**.
- Q4 : **toutes les idées du remue-méninges (§8) sont retenues** (19 h 56). Les 13 durées sont gardées, faute de demande contraire.
- Q5 : PP1 lancé **dimanche 22/11 après l'essai vélo**.
- Cyber-Rogue : aucun lien (W' retiré, lot R25).

PP5 du §6 est remplacé par quatre lots, lancés dans cet ordre quand la file le permet, chacun avec son cahier avant le code :

| Lot | Idées du §8 | Dépend de | Taille |
| --- | --- | --- | --- |
| **PP5** Se connaître | Profil de cycliste en un mot, point fort et point faible, forme du moment en pourcentage, record vieillissant, trous de la courbe | PP3 | Petite |
| **PP6** Jeu à ta mesure | Bots calés sur ta durée de course, durée tenable annoncée, temps prévu pour toi sur un parcours, seuils d'attaque du Grand Prix et rythme de l'élimination calés sur tes efforts courts | PP1, Elo (#941), mode Course (#939), stratégie des bots R1 | Moyenne, à cadrer avec le fil des bots |
| **PP7** Objectifs | Défi « bats ton record » avec parcours proposé, fantôme de ton record, trophées par palier | PP3, PP5 | Moyenne |
| **PP8** Entraînement | Séance conseillée par le coach sur le point faible, intervalles calés sur la courbe, courbe avant et après un plan, test de rampe proposé au bon moment | PP2, PP5, coach (série CO) | Moyenne |

Lien avec la ligue d'hiver (série CH) : PP6 fournit le réglage des bots selon la durée de la manche ; à raccorder au cahier CH quand CH1 partira.
Les garde-fous du §8.5 restent : rien pendant la séance, aucune difficulté changée sans le dire, aucune comparaison avec d'autres personnes, rien n'est exporté hors du PC.

## 11. Remise à zéro des statistiques (lot RZ1, 23/11)

Quand le profil a une date de remise à zéro (`ProfileContext.stats_since`, lot RZ1), `power_curve.kept_sessions(found, sources, since)` écarte les séances commencées avant. Décision du propriétaire : « garder coach, FIT et mon Elo ». Le filtre vaut donc seulement pour ce qu'il voit comme ses statistiques :

| Lit seulement les séances d'après la remise à zéro | Lit toutes les séances |
| --- | --- |
| Courbe de « Ma puissance » (PP1, PP3) | FTP estimée, proposition et évolution mensuelle (PP2) |
| Records du bilan (PP4) | Signal « FTP à revoir » du bilan (PP4) |
| Profil « Se connaître » (PP5) | Coach (PP8) |
| Défi « bats ton record » (PP7) | Courbe des bots (PP6) et trophées de puissance (PP7b, triés par la progression) |

Juste après la remise à zéro, la courbe est vide et la première séance n'annonce aucun record, comme la toute première séance d'un profil. Tests : `core/tests/test_power_since.py`.
