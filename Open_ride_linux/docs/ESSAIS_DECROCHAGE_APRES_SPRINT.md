# Essais du décrochage après sprint (31 octobre et 1er novembre 2026)

Ce document regroupe les essais vélo du 31/10 et du 1/11 sur le décrochage après sprint, et les décisions prises.
Les données brutes (journaux, `trainer_steps`, grilles) restent sur le PC, hors du dépôt.

## Le problème

Après un sprint de plus de 400 W en mode SIM, le trainer lâche sa résistance pendant quelques secondes. On a 0 W, ou presque, alors que le cycliste pédale encore. Le propriétaire ressent alors un « décrochage ».

Un autre symptôme est apparu : la cadence bloque vers 100 tr/min pendant 2 à 7 s.

## 1. Frein d'élan, #618 puis #686 (31/10) : ABANDONNÉ

L'idée était de maintenir une pente minimale (3 ou 6 %) pendant 4 à 8 s après le sprint.

Grille 7bk-bis : 2 sprints de 10 s au-dessus de 400 W par passe, notés de 1 à 5 (5 = aucun décrochage).

| Réglage | Note |
|---|---|
| 3 % pendant 4 s, 6 s et 8 s | 1, 1, 2 |
| 6 % pendant 4 s, 6 s et 8 s | 3, 3, 3 |
| Frein coupé | 3 |
| 6 % pendant 8 s, détection d'arrêt resserrée | 3 |
| **Appli du fabricant, mode résistance 32 %** | **5** |

Le frein ne fait jamais mieux que le frein coupé, et il ne tient jamais 8 s.

Décisions du propriétaire :
- #618 n'est pas fusionnée (31/10) ;
- l'option de menu #686 est abandonnée et fermée (1/11, 10h22).

## 2. Nouvelle approche : piloter le trainer en résistance ou en puissance (#683, #684)

Dans les deux modes, c'est le core qui calcule la force à la place du trainer en SIM :
- `control = "resistance"` : niveau de résistance FTMS ;
- `control = "power"` : consigne ERG égale à force × vitesse.

### 7rc1, étalonnage (1/11, de 9h37 à 9h53, #683 d458394b)

- Bloc à 70 puis 85 tr/min. Le propriétaire a abandonné au palier 6/8 (85 tr/min, 50 %).
- Bloc à 100 tr/min, avec un plafond de 300 W choisi par le propriétaire. Le garde-fou a coupé à 25 % (313 W).
- **Loi mesurée : F ≈ 0,036 × niveau (%) × vitesse du volant (km/h).** Le rapport F / (niveau × v) va de 0,0355 à 0,0363 sur tous les paliers. Le N/% apparent passe de 0,93 à 25 km/h à 1,22 à 35 km/h.
- Le trainer accepte le niveau en sint16. Il annonce une plage de 0 à 10 au pas de 0,1, et accuse réception en 200 à 800 ms.
- Volant : environ 0,355 km/h par tr/min avec le braquet du propriétaire (34 dents, Zwift Cog).
- Le réglage noté 5 (32 % dans l'appli du fabricant) correspond à environ 29 à 33 N.

### 7rc2 bloc 1 (1/11, de 10h06 à 10h14, #684 97bc229b, trace_ftms, profil réel)

| Passe | Note | Remarques |
|---|---|---|
| SIM1 | 3,5 | Frein lâché au sprint 1 (0 W à 115 tr/min). Plateau à 100 tr/min pendant 7 s au sprint 2. |
| PWR1 | 4 | « Frein un peu trop long ou en retard », « léger décrochage ». **Pas de plateau à 100 tr/min** (114 et 116 tr/min). |

Pour PWR1, deux défauts expliquent le ressenti :
- après le sprint, la consigne ERG reste haute pendant 3 à 6 s, parce qu'elle suit le volant encore lancé ;
- un creux d'environ 2 s apparaît vers +9 à +10 s, parce que la vitesse du volant lue est fausse (4,9 km/h à 71 tr/min).

### Corrections (#684 de17726b)

- Mode résistance : niveau = F / (k × v), avec k = 0,036 (`resistance_n_per_pct_kmh`), appris en roulant.
- Mode power : vitesse = cadence × `flywheel_kmh_per_rpm` (0,355), appris en roulant. La consigne baisse avec la cadence quand le cycliste relâche.

## 3. Prochaine séance, au choix du propriétaire (1/11)

Une seule séance de 9 sprints sur #684 de17726b : **R100, puis PWR2, puis SIM2**, avec 3 sprints par passe et une note par passe. Elle dure environ 19 min, dont 9 min 45 de passes.

On ajoutera une variante R70 ou R130 seulement si R100 est nettement trop dur ou trop mou.

Les fusions viendront ensuite : #683, puis #684 repointée sur main, après validation du propriétaire.

## 4. Ce qui reste vrai pour le mode SIM

- En SIM (0x11), OpenRide n'envoie pas le poids : le trainer prend le sien. Les modes résistance et puissance prennent la masse du profil.
- En sprint SIM, la force réelle (puissance / vitesse du volant) atteint environ 74 N à 39 km/h, contre environ 27 N pour la route à plat dans le modèle d'OpenRide : le trainer ajoute l'inertie qu'il simule à l'accélération, et la rend après le sprint (la phase à 0 W).
- Le plateau de cadence à 100 tr/min n'apparaît qu'en SIM (aucun en PWR1) ; cause non établie.

## 5. Séance de 9 sprints (1er novembre, #684 de17726b) et choix de la suite

| Passe | Note | Remarques |
|---|---|---|
| R100 | 3, 3,5, 4 | Aucun lâcher, aucun 0 W ; passe sous 100 W environ 9 s après la relâche ; 500 W en 2,6 à 3,5 s. k appris : 0,037 à 0,042. |
| PWR2 | 2,5 | Consigne plus lente que PWR1 (500 W en 6 s), au-dessus de la puissance mesurée ; une fois 20 s à 0 W. |
| SIM2 | 3 | Lâcher du frein sur 4 sprints sur 5 (200 à 352 W après 819 à 945 W), 5 à 14 s à 0 W. |

Ressenti du propriétaire : « ça ne change pas grand-chose, ça repousse le décrochage à des puissances plus élevées ». Lecture : sans inertie, le mode résistance supprime le trou d'après le sprint mais allège la relance (sur la route, accélérer 84 kg à 1 m/s² demande 84 N, plus que l'air à 45 km/h). Choix du propriétaire (1er novembre) : le mode « power » est retiré, et le mode résistance ajoute l'inertie m × a quand le volant accélère, jamais rendue au ralentissement (`resistance_inertia_pct`), à essayer à 50 et 100 %.

## 6. Inertie (7rc3) et choix final (1er novembre)

- Premier essai à 100 % : variations de résistance, dues au bruit de la vitesse du volant (±1 à 2,75 m/s² d'une trame à l'autre à 12–22 km/h) ; corrigé (lissage 1 s, seuil 0,4 m/s², rien sous 20 km/h, variation bornée à 60 N/s, k gelé).
- R-I50 : 3,5, « non linéarité de résistance dans phase de sprint (devient plus dur pendant le sprint) puis parfois résistance en retard », décrochage sauf au dernier sprint.
- Le propriétaire juge les essais manuels trop longs et demande de conclure sur l'ensemble des journaux. Bilan : seul le mode résistance sans inertie supprime le lâcher de façon mesurable (aucun 0 W sur ses sprints, contre 4 sprints sur 5 en SIM), avec des notes de 3 à 4.
- **Choix du propriétaire : résistance calculée sans inertie par défaut pour la 1.0**, SIM au menu (« Pilotage du trainer »).

## 7. Résistance calculée trop légère à basse vitesse (2 novembre) et correctif (5 novembre)

Essai du 2 novembre vers 19 h (AS #649, résistance calculée, plat, braquet 24/24) : pédalage dans le vide, 21 à 31 W à 70-84 tr/min, quand la route en demandait environ 180 W au volant. Le SIM du trainer est redevenu le défaut (1.0.2).

Ce que dit le journal du core (aucune ligne « FTMS ~ mesures », trace par seconde coupée) : k appris tombé de 0,036 à 0,0147 en 3 min. Le frein donnait donc bien moins de force que la loi de l'étalonnage 7rc1 au niveau envoyé, et la correction ne pouvait pas compenser : elle était coupée sous 30 W, c'est-à-dire justement pendant le défaut.

Correctif (lot RC4) :
- k se corrige aussi sous 30 W (seuil ramené à 5 W, volant libre écarté) ;
- frein sans effet (force mesurée sous 35 % de la force visée pendant 8 s, volant ≥ 15 km/h, niveau ≥ 5 %) : contrôle repris et niveau renvoyé, deux fois au plus, puis SIM du trainer jusqu'à la fin de la séance. Journal : lignes `ftms` `resistance_weak` et `resistance_fallback` ;
- en résistance calculée, la ligne « FTMS ~ mesures » (puissance, cadence, vitesse du volant, niveau, force visée et mesurée, k) est toujours écrite, avec ou sans `trace_ftms`.

Reste à établir sur le vélo : si la reprise du contrôle suffit (trainer resté dans un autre état) ou si le frein répond mal aux petits niveaux (zone morte sous 10 %, hors de l'étalonnage). La recette du soir le tranche en 10 min.

## 8. Recette RC4 (7 novembre) et correctif du pompage à basse cadence (lot RC5)

Recette vélo de 10 min sur #718 : 4/5 (« pas de trou, sprints beaucoup mieux, on monte moins haut en puissance mais beaucoup plus réaliste »), mais quelques pompages à faible cadence. Journal : k entre 0,034 et 0,048 la plupart du temps, puis tombé au plancher (0,0072) entre 520 et 557 s avec deux `resistance_weak` au niveau 10 (le maximum de la plage 0 à 10, donc 100 %). Pompage sous 60 tr/min : 66↔262 W à 61–76 s et 30↔305 W à 513–577 s, en cycles de 3 à 5 s.

Causes trouvées dans le code :
- k était corrigé même quand le niveau envoyé était déjà au maximum. Le niveau ne pouvait plus monter, et k baissait à chaque mesure jusqu'au plancher (un intégrateur saturé). Le frein restait ensuite au maximum trop longtemps, d'où les pics à 305 W ;
- le niveau suivait la vitesse instantanée du volant (F / (k × v)). Au point mort du pédalage, le volant ralentit et le niveau montait. Le trainer l'appliquait 200 à 800 ms plus tard, donc pendant la poussée suivante. À niveau fixe, le frein donne F ∝ v, ce qui stabilise le volant : la compensation en 1/v annulait cet amortissement, et le défaut grossit quand la cadence baisse.

Correctif (lot RC5) :
- k est gelé quand le niveau envoyé est à 95 % ou plus, et pendant 1 s après chaque changement de niveau (le temps que le trainer l'applique) ;
- le niveau est calculé sur la vitesse du volant lissée sur 1,5 s, soit plus qu'un tour de pédalier à 40 tr/min ;
- le niveau ne monte pas plus vite que 20 % de la plage par seconde. La baisse reste immédiate.

Recette vélo : 10 min, dont 3 min à 40–50 tr/min sur le plat et 2 min en montée à basse cadence.
