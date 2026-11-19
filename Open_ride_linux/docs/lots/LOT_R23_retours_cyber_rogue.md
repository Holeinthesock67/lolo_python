# Lot R23 – Retours du Cyber-Rogue : chaque Z répond, surchauffe expliquée, vitesse et vue sur le vélo

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Retours du Cyber-Rogue : événements jamais perdus entre deux trames, chaque Z accepté ou refusé avec son, animation et raison, surchauffe et tendance de l'adrénaline affichées, vitesse toujours affichée, vue sur le vélo (contrat révision 1.17) | Python, GDScript | R22 | Moyenne | **Livré le 16 novembre** (PR #884), **version 2.0** |

## 1. Constat

Essai sur le vélo du 14 novembre (R22 noté 2/5) :

1. Z ne donne ni son ni animation : on ne sait pas s'il a marché.
2. L'adrénaline baisse sans explication.
3. La vue du joueur sur le vélo n'existe pas dans le mode.
4. La vitesse (braquet) engagée ne se voit pas assez.
5. Le guide vocal de l'essai partait du lancement sans compter les 6 min d'échauffement (corrigé à part, dans le guide de l'essai, hors dépôt).

## 2. Causes trouvées dans le code

- **Événements perdus.** Le core fait un pas toutes les 20 ms (50 Hz) et envoie la trame `state` toutes les 33 ms (30 Hz). L'objet `rogue` de la trame était celui du **dernier pas** seulement : les événements d'un pas sur deux ou trois (environ 40 %) n'arrivaient jamais à l'engine. Un Z accepté (`hit`) ou refusé (`z_refused`), une arche ratée, un Perfect Shift : ni son, ni texte, ni impact. Le contrat dit pourtant « événements de la dernière **trame** ».
- **Z sans réponse hors combat.** À l'échauffement (hors relique), au couloir une fois la porte prise et au retour au calme, Z court était ignoré sans rien dire. Un rocher touché sans être brisé (armure restante) et la relance des cartes réussie n'avaient pas d'événement non plus.
- **Un Z accepté n'avait pas de retour propre** : seulement le son `rogue_hit` (bas, sous la musique) et le choc sur l'ennemi, quand l'événement arrivait.
- **Surchauffe muette, règle contradictoire.** En endurance, au-dessus de 75 % de la FTP pendant 5 s, l'adrénaline fond de 2 par seconde et Z est refusé ; mais la consigne affichait « garde ≥ 70 % FTP », sans plafond. Pire, les phases 2 et 3 du boss d'endurance demandent jusqu'à 85 % de la FTP (plus de la moitié de leur longueur au-dessus de 75 %) : tenir la consigne faisait fondre l'adrénaline. Le banc l'a montré : le cycliste simulé, qui tient la cible, passait 161 s en surchauffe sur une run de 30 min.
- **Vitesse.** Elle n'apparaissait qu'en petit dans la ligne du panneau d'état (« Vitesse 06 … »), et disparaissait avec le panneau au couloir et à la relique.
- **Vues.** Les 3 vues du mode (derrière, haute, proche) sont toutes derrière le vélo.

## 3. Travail

Principe : une seule règle pour tous les appuis, sans cas particulier. **Chaque Z court d'une run produit exactement un retour** : `z_ok` (accepté, avec son action) ou `z_refused` (avec sa raison).

### 3.1 Core (contrat révision 1.17, ajouts compatibles)

- `rogue/mode.py` : les événements, `z_reason`, `z_action` et `shift_miss` s'accumulent entre deux trames ; la session les vide à l'envoi de chaque trame `state` (`take_frame`). Plus aucun événement perdu, chacun envoyé une seule fois.
- `rogue/run.py`, `rogue/combat.py` : événement `z_ok` et champ `z_action` (`strike`, `charges` (Diesel), `rock` (rocher brisé), `rock_chip` (armure entamée), `parry`, `purge`, `reroll`) ; Z sans effet à l'échauffement, au couloir sans choix et au retour au calme : `z_refused` avec `no_target`.
- Champ `adrenaline_trend` : `{rate_per_s, cause, overheat_in_s}` ; `cause` parmi `gain` (à la cible), `below` (sous la cible : stable), `overheat` (fond), `stopped` (arrêt), `full`, `none` (hors combat) ; `overheat_in_s` : secondes avant la surchauffe quand on est déjà au-dessus du seuil, sinon `null`.
- Seuil de surchauffe : le plus haut de 75 % et de la cible + 10 points (`overheat_margin` de `balance.toml`, `overheat_limit`). Une seule règle, jamais contraire à la consigne ; le bonus du châssis Endurant (+3 points) s'applique toujours.
- `target_pct.hi` en endurance : ce seuil ; la consigne devient une plage.

### 3.2 Engine

- `rogue_guide_model.gd` : retour pour chaque `z_ok` (« FRAPPE ! −6 % », « Charges : −N % », « Rocher brisé », « Rocher entamé », « Parade ! », « Vitesses débloquées », « Cartes relancées ») ; texte de `no_target` selon la phase (« Z sert en salle : première salle dans 4:12 ») ; bandeau de surchauffe permanent en rouge (« SURCHAUFFE : adrénaline −2/s, Z bloqué · descends sous 75 % FTP ») et alerte orange avant (« Au-dessus de 75 % FTP : surchauffe dans 3 s ») ; consigne en plage « 70–75 % FTP » en endurance.
- Jauge d'adrénaline : tendance écrite à côté (« +0,5/s », « −2/s surchauffe », « stable : sous la cible »).
- `rogue_hud_view.gd` : anneau qui s'ouvre au centre de l'écran à chaque Z (or si accepté, rouge si refusé) et pastille Z qui clignote ; pavé **VITESSE NN** toujours visible en bas à droite, dans toutes les phases, qui s'allume à chaque changement.
- Sons : `rogue_z_ok` (nouveau, net et court) à chaque Z accepté, en plus du son de l'action ; priorité de `rogue_refused` et `rogue_z_ok` relevée pour ne jamais être couverts.
- `rogue_scene.gd` : 4e vue « sur le vélo » (yeux à 1,4 m, avatar caché), ordre derrière, haute, proche, sur le vélo ; le nom de la vue s'affiche 1,5 s à chaque changement.

### 3.3 Cartes sans vitesse imposée (choix du propriétaire, 14 novembre)

Le propriétaire a trouvé la carte Overdrive incompréhensible (« pousser fort pendant 8 secondes est bien plus simple ; pourquoi imposer des vitesses ? », de même pour Soin). Une seule règle pour les cartes, comme pour les objets des salles : elles se déclenchent à la puissance ou à la cadence, jamais par une vitesse imposée.

| Carte | Avant | Depuis R23 |
| --- | --- | --- |
| Overdrive | vitesse 12 : +4 points de pente, dégâts ×2 pendant 8 s, puis retour forcé en 6 | au-dessus de 150 % de la FTP (`overdrive_power_frac`) : dégâts ×2 pendant 8 s, recharge 45 s ; pente inchangée, plus de retour forcé (`RunOutputs.force_gear` retiré) |
| Soin | vitesse 1 au-dessus de 95 rpm | au-dessus de 95 rpm et sous 60 % de la FTP (`heal_power_frac`) : +1 de bouclier par seconde |
| Maudit | vitesse 10 : dégâts ×1,35, Z sans effet | au-dessus de 100 % de la FTP (`cursed_power_frac`) : dégâts ×1,35, Z refusé (raison `cursed`) |
| Tremplin cinétique | en bas d'une descente, en vitesse 9 ou plus | en bas de chaque descente, quelle que soit la vitesse |

Les trois premières passent du type `gear` au type `module` ; `replaces_gear` reste `null` dans `loot`. Les textes de toutes les cartes et reliques sont réécrits en français simple (ce qu'il faut faire, ce que ça change, combien de temps). Clés retirées de `balance.toml` : `overdrive_grade_pts`, `overdrive_back_gear`, `cursed_gear`, `springboard_min_gear` (une surcharge `~/OpenRide/rogue_balance.toml` qui les contient est refusée avec « clé inconnue »).

### 3.4 Retours de l'essai des captures (14 novembre, midi)

Demandes du propriétaire en lisant la planche :

- **Watts partout** : « 150 % et 60 % de FTP demandent un calcul ; donne directement la puissance ». Textes des cartes calculés par le core pour la FTP du coureur (`cards.card_text`, arrondi à 5 W) ; consignes, plage d'endurance, surchauffe, pavé et sortie de Maudit écrits en watts par l'engine (`GuideModel.watts`, FTP de `hello_ack`) ; puissance du panneau d'état en watts.
- **Carte déclenchée** : événement `card_on` et champ `card_on` (révision 1.17) : Overdrive à son déclenchement, Soin et Maudit au passage de leur condition (au plus une annonce par carte toutes les 5 s, `card_on_rearm_s`) ; son `rogue_card_on`, anneau vert, message (« OVERDRIVE ! », « SOIN ACTIF », « MAUDIT ACTIF »).
- **Lancer l'action** : invite « Z : FRAPPE ! », « Z : PARADE ! », « Z : ROCHER ! », « Z : DÉBLOQUE ! » qui bat au centre de l'écran tant que Z agit (`z_call` du guide).
- **Savoir si l'attaque a porté** : en plus du son et de l'anneau or, éclair blanc et or de tout l'écran (0,25 s) pour une frappe, des charges, un rocher ou une parade.
- **Dégâts reçus** : bords rouges qui clignotent tant que le bouclier baisse, « TOUCHÉ ! Coup non paré » et « TOUCHÉ PAR LE FIREWALL ».
- **Règles** : bandeau défilant des règles pendant l'échauffement.

### 3.5 Essai sur le vélo du 15 novembre

- **Puissance impossible à tenir** : les consignes (gain d'adrénaline, surchauffe, parade, pavé) et les seuils des cartes étaient jugés sur la puissance brute du trainer (écart type de 60 à 90 W par minute en salle, variation d'une seconde à l'autre de 11 W en médiane, plus de 36 W une fois sur dix), alors que l'écran montre la moyenne de 3 s. Ils se jugent désormais sur cette moyenne affichée (`RunInputs.power_avg_w`, `CombatInputs.power_avg_w`), à `target_grace_w` (5 W, l'arrondi de l'affichage) près ; les dégâts par seconde, le W'bal et les postures gardent la puissance brute.
- Les « décrochages » du frein du journal étaient des arrêts de pédalage en fin de salle (cadence à 0, roue libre) : rien à corriger ici.
- **Boss final sans assez d'adrénaline** (choix du propriétaire : « elle se garde ») : l'adrénaline n'est plus remise à 0 à chaque salle ni à chaque phase du boss ; elle passe d'un combat au suivant. `adrenaline_start` (châssis Survolté) devient un plancher.
- **Attente dans le sas** (choix du propriétaire : « sas court, salles plus longues ») : couloirs de 45 s au lieu de 2 min (`calendars`), le temps gagné va aux salles (4,5 min en moyenne, 5 min au plus) et le reste au boss ; la durée de la run ne change pas. Le boss remplit le temps qui reste avant le retour au calme (`boss_fit_min` 0,75, `boss_fit_max` 1,6) : une salle finie en avance (carte Rouleau compresseur, rouleur plus fort que prévu) rallonge le boss au lieu de raccourcir la run. Un message `room` trop grand (salle de 5 min, phase de boss de 90 min : plus de 4 096 o, jeté par l'envoi) est maintenant coupé en parties (`Room.to_messages`, 3 500 o au plus), que l'engine réassemblait déjà.
- **« Je n'ai pas compris pourquoi la défaite »** : en salle, à 300 m de la fin d'une salle encore debout (et de la phase 3 du boss, la seule qui décide de la run), le guide dit « Fin de salle dans 200 m : ennemi encore à 60 % ». Au bilan, une phrase de cause et ce qu'il fallait faire (`summary.rogue.end_cause`, révision 1.17 : `boss_time`, `boss_shield`, `abandoned`), par exemple « Défaite : la phase 3 du boss s'est finie avec encore 42 % de PV au boss. » puis « À faire : tiens ta plage de watts, puis Z à chaque « Z : FRAPPE ! ». ». Plus de « fui » pour une salle qui a simplement atteint sa fin : « Boss : non vaincu », « Salles non gagnées / sautées ».
- **Bloqué sur le bilan** (Y sans effet sur l'écran de fin) : corrigé par la PR #901 (fil du vélodrome), commune à tous les modes ; R23 n'y touche pas pour éviter deux comportements.

## 4. Tests

- `core/tests/test_rogue_r23_retours.py` : aucun événement perdu à 50 Hz / 30 Hz, chaque Z donne un seul retour dans toutes les phases, actions de `z_ok`, tendance de l'adrénaline (gain, sous la cible, surchauffe, compte à rebours), plage de la consigne en endurance, schéma.
- `engine/tests/unit/test_rogue_guide_model.gd`, `test_rogue_hud_model.gd`, `test_rogue_sound_model.gd` : textes et sons des retours, tendance, surchauffe, vitesse, vue sur le vélo.
- `rogue_bout_en_bout` : un Z sans cible à l'échauffement, puis un seul retour par Z court dans les trames ; en endurance, 20 s trop fort dans la première salle : surchauffe annoncée, dite, finie.
- `rogue_bench.py` : nouveaux moments (Z refusé à l'échauffement, Z accepté, surchauffe proche, surchauffe, vue sur le vélo) et vérifications (pavé VITESSE, retour du Z, bandeau de surchauffe, vue).
- Captures low, medium et high (`engine/tests/rogue_galerie.py --objective endurance`).
- Essai du 15 novembre : adrénaline gardée d'une salle à l'autre, couloirs de 45 s et durée tenue pour toutes les durées et tous les objectifs, message `room` coupé sous 4 096 o, boss qui remplit le temps restant, cause de la défaite au bilan (`core/tests/test_rogue_r23_retours.py`) ; fin de salle annoncée, verdict du bilan, plus de « fui » (`engine/tests/unit/test_rogue_r23_retours.gd`). La recette du calendrier (`rogue_recette.py`) n'exige plus le boss à ± 1 min : une avance est rendue au boss, seul un retard de plus d'une minute est une faute ; la fin de run reste à ± 1 min.

## 5. Reste au propriétaire

- Validation des captures, puis essai sur le vélo (10 min, consignes calées après l'échauffement).

## Livraison

En revue le 14 novembre.
