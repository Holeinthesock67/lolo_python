# Guide d'utilisation d'OpenRide

OpenRide est un simulateur de cyclisme indoor pour Linux. Il relie votre home trainer à un parcours en 3D : la pente de la route est envoyée au trainer, votre puissance fait avancer le vélo. Ce guide explique comment l'installer et rouler, sans avoir besoin de connaître le projet. Les commandes du terminal ne servent que pour l'installation et le dépannage.

## Quelques mots utiles

- **FTMS** : le protocole Bluetooth standard des home trainers connectés ; OpenRide s'en sert pour lire votre puissance et régler la résistance.
- **FTP** : la puissance (en watts) que vous pouvez tenir environ une heure. Les entraînements s'expriment souvent en pourcentage de la FTP ; réglez la vôtre dans **Réglages**.
- **SIM (Session libre)** : le trainer reproduit la pente de la route. **ERG (Session ERG)** : le trainer impose la puissance à produire, quelle que soit votre cadence ou la pente.
- **Braquet** : le rapport de pédalage virtuel, de 1 (très petit) à 24 (très grand). Le trainer n'a pas de vitesses : OpenRide en simule 24.
- **Bot** : un cycliste virtuel qui roule à puissance constante pour vous accompagner. **Fantôme** : rejoue votre dernière séance sur le même parcours. **Records du parcours** : vos meilleurs temps sur ce parcours.
- **HUD** : les informations affichées sur l'image pendant la séance.
- **Core** : le programme d'OpenRide qui parle au trainer et au Click ; la fenêtre 3D est un autre programme. Si le core plante, OpenRide le relance tout seul.
- **Journal** : le fichier texte où OpenRide note ce qu'il fait ; c'est ce que l'on joint à une demande d'aide (section 9).
- **FIT** : le format de fichier des séances des montres et compteurs Garmin.

## 1. Ce qu'il faut

- Un PC sous Ubuntu, avec Bluetooth et une carte graphique 3D (la GTX 1060 est la référence).
- Un home trainer compatible FTMS (le Bluetooth standard des trainers connectés). Il doit être déconnecté de Zwift et du téléphone avant de lancer OpenRide.
- Facultatif : un Zwift Click (une paire de boîtiers « + » et « − ») pour naviguer et changer de braquet sans toucher au clavier.
- Facultatif : une ceinture cardio Bluetooth. Certains trainers relaient aussi la fréquence cardiaque.

## 2. Installer et mettre à jour

Installation, une seule fois, depuis le dossier `Open_ride_linux/` du dépôt (après `sudo apt install python3-venv bluez` et le téléchargement de Godot 4.7.2, version standard, pas .NET) :

```bash
scripts/install.sh
```

Le script demande le chemin de Godot 4.7.2 et crée trois icônes dans le menu des applications : **OpenRide**, **OpenRide – Libérer le trainer** et **OpenRide – Mettre à jour**. Il peut être relancé sans risque.

Pour mettre à jour, cliquez sur l'icône **OpenRide – Mettre à jour**. La mise à jour est refusée s'il y a des modifications locales dans le dossier du dépôt ; vos parcours, séances et réglages (dans `~/OpenRide/`) ne sont jamais touchés.

## 3. Premier démarrage et appairage

Lancez OpenRide avec son icône. Au premier démarrage, il crée le dossier `~/OpenRide/` (parcours, entraînements, séances, réglages), installe les contenus de départ (les entraînements livrés, deux plans et quatre parcours de démonstration des biomes, sans rien télécharger) et ouvre l'écran **Connexion des appareils**.

1. Allumez le trainer (pédalez un peu pour le réveiller) et les boîtiers du Click.
2. L'écran cherche les appareils. Quand tout est relié, il passe seul au menu. Avec un seul boîtier du Click, ou sans Click, choisissez **Passer**.
3. Pour changer de matériel plus tard : **Réglages**, puis **Appareils : rechercher et appairer**. Appuyez sur le bouton « + » du Click quand l'écran le demande pour reconnaître ce boîtier. Valider **Trainer** ou **Ceinture** passe à l'appareil suivant, puis à « aucun » pour l'oublier ; **Oublier le Click** retire les deux boîtiers. Une ceinture choisie est utilisée dès le lancement suivant. Les appareils trouvés sont enregistrés dans `~/OpenRide/config.toml`, puis **Relancer OpenRide** prend en compte le nouveau matériel.

## 4. Rouler un parcours

**Ajouter un parcours.** Téléchargez la trace (par exemple depuis Garmin Connect), puis, en bas de la liste des parcours, choisissez **Ajouter un parcours** : l'écran **Importer une trace** liste les traces de Téléchargements, du Bureau et de `~/OpenRide/Import`, les plus récentes d'abord. Formats : `.gpx`, ou l'export de Garmin Connect tel quel (`.fit`, `.tcx`, `.fit.gz`, `.tcx.gz` ou `.zip`). Choisissez-en une : OpenRide la copie dans `~/OpenRide/GPX/` et la compile tout de suite, sans relancer. La ligne d'état compte les secondes (une à quelques minutes ; la première fois dans une région, l'altitude se télécharge), puis le parcours apparaît dans la liste, sous le focus. Une trace illisible affiche son erreur et n'est pas ajoutée. Une trace déposée à la main dans `~/OpenRide/GPX/` est compilée au démarrage suivant (une notification s'affiche). Pour que la fiche d'un parcours soit plus parlante, posez à côté de la trace un petit fichier du même nom en `.toml` (nom, description, région, étiquettes). Le menu le rappelle : en bas de la liste des parcours, la carte de **Ajouter un parcours** résume l'import, et **Comment ça marche ?** ouvre l'écran **Aide parcours** (choisir un parcours, ajouter une trace, fiche `.toml`, monde ouvert), dont chaque sujet s'explique dans la carte de droite.

**Packs de parcours.** **Réglages**, **Contenus**, **Pack « Cols célèbres »** construit seize montées célèbres (Alpe d'Huez, Ventoux, Teide, Vosges, Japon…) depuis OpenStreetMap : il faut le réseau, l'écran demande confirmation, montre l'avancement col par col, puis compile les parcours, qui arrivent dans la liste sans relancer. Un pack de parcours reçu en archive `.zip` (avec son `pack.toml`) s'installe du même écran quand il est dans Téléchargements, sur le Bureau ou dans `~/OpenRide/Import`.

**Lancer une séance.**

1. Au menu principal, **Parcours : …** ouvre la liste. Le tri et le filtre par étiquette sont en bas de la liste.
2. Choisissez **Session libre** (la pente de la route est jouée par le trainer) ou **Session ERG** (section 5).
3. L'écran **Prêt** montre la fiche du parcours (distance, dénivelé, montée principale, durée estimée). Il propose aussi **Bot : …** (un cycliste virtuel à puissance constante), **Fantôme de la dernière séance** et **Records du parcours**.
4. **Démarrer** lance la séance : le vélo avance dès que vous pédalez.

**Pendant la séance.** Le HUD montre puissance, cadence, fréquence cardiaque, vitesse, distance, pente et profil d'altitude (sous le panneau de droite, en SIM). La puissance prend la couleur de sa zone de FTP (Z1 à Z7) et la fréquence cardiaque celle de sa zone de FC (Z1 à Z5, d'après la **FC max** des réglages du cycliste). La touche **Y** du Click (ou `Y`, `Échap` au clavier) met en pause : l'écran de pause propose **Reprendre**, **Terminer et enregistrer**, **Abandonner** et le curseur de **Difficulté**.

**Fin de séance.** À l'arrivée d'un parcours ou avec **Terminer et enregistrer**, le bilan affiche la durée, la distance, les puissances (NP, IF, TSS) et les zones. La séance est enregistrée dans `~/OpenRide/Activities/` (section 8).

**Fin d'un entraînement.** Quand le dernier bloc d'un entraînement ERG (ou de la séance du jour d'un plan) est fini, la séance ne s'arrête pas : le trainer repasse en parcours libre et le bandeau du haut affiche « Entraînement « … » terminé : Y puis A maintenu pour terminer et enregistrer » tant que vous roulez. **Y** ouvre la pause directement sur **Terminer et enregistrer** (la ligne sous le titre le rappelle) ; **A maintenu** (Échap puis Entrée au clavier) affiche le bilan et enregistre la séance. Pour continuer à rouler, **Reprendre** ; l'invite disparaît si vous choisissez un autre mode sur la ligne **Mode** de la pause.

**Mode WTF (« What the fuck »).** **Mode WTF** à l'accueil ouvre la liste des treize règles absurdes : gravité de la Lune ou de Jupiter, monde à l'envers, route qui s'effondre derrière vous, fromage géant dans les descentes, Katamari, peloton déguisé, micro-défis, livraison d'œufs, horloge réglée par votre cadence, vélo minuscule, tornade de vaches, caméras improbables et **Surprise du chef**. Chaque ligne s'allume ou se coupe (A maintenu ou Entrée) ; **Tout allumer** les rallume toutes ; le choix est gardé dans `~/OpenRide/wtf.toml`. **Lancer une séance WTF** ouvre l'écran **Prêt** (parcours, bot, fantôme), puis **Démarrer**. Un gag à la fois, toutes les 45 à 90 s : le bandeau du haut donne son nom, le temps restant et vos points, la carte dessous ce qu'il faut faire. Quand le chef révèle son plat, **Z** court (touche `Z` au clavier) répond « Non merci, chef ! » dans les 5 secondes ; le chef vexé sert alors du piment la fois suivante. Le mode WTF se roule en SIM seulement : la pente ressentie reste entre −6 et +10 %, et la puissance enregistrée dans le FIT est toujours votre puissance mesurée. Pas de records ni de bonus ; le bilan donne les points, les gags joués et la taille du Katamari.

## 4 bis. Monde ouvert

Le **Monde ouvert** de l'accueil crée la route en roulant, d'après les cartes OpenStreetMap et le relief Copernicus, sans trace à préparer. Il faut Internet la première fois dans une région ; ensuite, la région est en cache (`~/OpenRide/Cache/monde/`, 5 Go au plus) et rien n'est retéléchargé au même endroit.

1. **Globe.** Faites-le tourner jusqu'à votre région (flèches, ou « + » et « − »), ou cherchez un lieu par son nom : au Click, Z ouvre une grille de lettres, la même que pour le nom d'un profil (+ et − changent de case, maintenus de ligne, Z écrit, Y efface, A maintenu montre les résultats, Z y revient à la grille) ; au clavier, tapez simplement le nom. La recherche porte sur la liste fournie avec OpenRide, puis OpenStreetMap si Internet répond. Les régions en cache sont surlignées. A maintenu épingle la région sous le centre : une région épinglée reste toujours dans le cache. A ouvre la carte autour du centre.
2. **Carte.** Le curseur reste accroché à la route la plus proche ; A pose le départ.
3. **Cap et navigation.** Choisissez le cap, puis **Balade** (le jeu garde le cap et préfère les petites routes), **Destination** (A cherche le lieu) ou **Boucle** (retour au départ après la longueur choisie). A démarre le préchargement.
4. **En roulant.** Un panneau annonce chaque carrefour : les flèches ou A choisissent la branche, A maintenu la valide, jusqu'à 30 m avant ; sinon la navigation choisit. Le monde ouvert marche aussi en ERG.
5. **Garder la balade.** **Terminer et enregistrer** écrit la route parcourue (au-delà de 500 m) en GPX dans `~/OpenRide/GPX/` : elle devient un parcours de la liste au démarrage suivant.

Chaque écran du globe explique ce qu'il fait, et le bandeau du bas donne les boutons du Click et les touches du clavier. Au clavier, les lettres tapées sur le globe ouvrent la recherche d'un lieu ; ensuite, Entrée valide (recherche, carte, cap) et Échap revient.

## 5. Entraînements ERG, plans et test de FTP

En mode **ERG**, le trainer impose la puissance visée à chaque instant ; la pente de la route ne compte plus.

**Choisir un entraînement.** **Session ERG** ouvre la liste de `~/OpenRide/Workouts/`. En bas de la liste : **Créer** un entraînement par intervalles, **Importer un fichier** `.zwo`, `.erg`, `.mrc` ou `.qwk` trouvé dans Téléchargements, sur le Bureau ou dans `~/OpenRide/Import`, et **Comment ça marche ?**, l'aide à l'écran qui reprend tout ce qui suit (un sujet par ligne, l'explication dans la carte de droite). Les entraînements livrés sont installés au premier démarrage ; sur une installation plus ancienne, **Réglages**, **Contenus**, **Contenus de départ** les ajoute (A maintenu), sans jamais remplacer un fichier existant.

**Ajouter un entraînement.** Quatre façons :

- **Créer** : échauffement, répétitions d'effort et de récupération (durée et % de la FTP), retour au calme, réglés au Click ; **Enregistrer et choisir** écrit un `.zwo` et le choisit. Les mêmes réglages ne font pas de doublon, et aucun entraînement n'est remplacé : un nom déjà pris reçoit `_2`, `_3`…
- **QWKcode de GoldenCheetah** : un fichier texte `.qwk`, une ligne par segment, `[Nx] durée@puissance[-puissance] [rdurée@puissance[-puissance]]`. Durée en `h`, `m` ou `s`, combinables (`1m30s`, `1.5m`) ; puissance en watts, ou en % de la FTP avec `%` (`50-75%`). Une ligne `#` avant le premier segment donne le nom ; `#` ailleurs commence un commentaire. Exemple :

  ```
  # Seuil 4 × 5 min
  10m@130-220
  5m@180
  4x 5m@280 r3m@140
  8x 30s@120% r30s@50%
  10m@130
  ```

  `10m@130-220` est une rampe de 130 à 220 W ; `4x 5m@280 r3m@140` fait 4 fois 5 min à 280 W puis 3 min à 140 W. Une erreur donne le numéro de la ligne. Enregistre le fichier dans Téléchargements, puis **Importer un fichier**.
- **Importer** : le fichier est vérifié, puis copié dans `~/OpenRide/Workouts/` ; un fichier déjà importé n'est pas recopié, un autre du même nom reçoit `_2`.
- **À la main** : un fichier posé directement dans `~/OpenRide/Workouts/` apparaît dans la liste. `.zwo` (Zwift) et `.mrc` : puissances en % de la FTP ; `.erg` : watts fixes ; `.qwk` : watts ou %. Un bloc `FreeRide` devient un palier à 50 W. Exemples dans `core/workouts/`.

**Pendant l'ERG.** Le bandeau du bas montre le bloc en cours, le temps restant, la cible et le bloc suivant. Les appuis courts sur « + » et « − » règlent l'intensité de ± 2 %, les appuis longs de ± 10 % ; **Z** passe au bloc suivant et **Y** met la séance en pause. Après le dernier bloc, le bandeau du haut invite à terminer : **Y** puis **A maintenu** (section 4, « Fin d'un entraînement »). Le détail est dans la section 6.

**Passer en ERG pendant une session libre.** Mettez en pause (**Y**) : la ligne **Mode** de l'écran de pause passe de **SIM** à **ERG** ou à **ERG cadence** (« + » ou « − » pour changer, A maintenu pour appliquer, Y pour annuler), puis **Reprendre**. En **ERG**, la ligne **Puissance cible** règle la puissance par pas de 5 W ; elle part de votre puissance des 3 dernières secondes, et « + » et « − » règlent ensuite l'intensité de ± 2 % en roulant. En **ERG cadence**, la ligne **Cadence cible** règle la cadence à tenir (elle part de votre cadence du moment) : tant que vous restez à ± 10 % de cette cadence, la puissance ne bouge pas ; si vous tournez plus vite, elle monte peu à peu, si vous tournez moins vite, elle baisse, entre 50 W et 150 % de votre FTP. En roulant, « + » et « − » changent la cadence cible de ± 2 % (appui long ± 10 %). Le bandeau dit si vous êtes dans la plage. Revenez en **SIM** de la même façon. Pas de bascule pendant un entraînement ni en Cyber-Rogue.

**Courbes de la séance.** Un graphique façon GoldenCheetah montre la cible, votre puissance, votre fréquence cardiaque et votre cadence. Sa taille se règle dans **Réglages**, **Graphisme**, **Courbes de la séance** : masquées, réduites (cible et puissance) ou complètes.

**Volume sonore.** Quatre curseurs dans **Réglages**, **Son**, de 0 (coupé) à 100 % par pas de 10, pris en compte tout de suite : **Volume général**, **Volume vent et roue libre**, **Volume de l'ambiance** (oiseaux, cloches, véhicules, foule) et **Volume bips et événements** (bips du Click, changement de bloc ERG). Détail des catégories : [AUDIO.md](AUDIO.md).

**Images par seconde.** **Réglages**, **Graphisme**, **Afficher les images/s** : oui affiche en haut à droite, pendant la séance, « 60 images/s · p99 17 ms » (images de la dernière seconde, et temps d'image que 99 % d'entre elles ne dépassent pas : une valeur haute signale des saccades).

**Jauge d'abri des bots.** **Réglages**, **Graphisme**, **Jauge d'abri des bots** : oui affiche un petit arc bleu au-dessus du bot qui t'abrite, rempli selon l'abri que tu reçois (le même pourcentage que la pastille « Abri » du HUD). Elle apparaît dans la roue d'un bot, dès que la pastille « Abri » apparaît (jusqu'à 15 m environ derrière lui), et disparaît quand tu en sors. En medium et high, le pourcentage s'affiche sous l'arc ; en high, l'arc a un léger halo. Coupée par défaut. Seuls les bots abritent : ni le fantôme, ni les cyclistes du décor, ni les véhicules.

**Plans d'entraînement.** L'accueil affiche **Séance du jour** quand un plan est en cours, sinon **Choisir un plan**. Un plan range des entraînements par semaine et par jour ; il garde en mémoire ce qui est fait et ce qui est en retard. Deux plans de départ (« Reprise 4 semaines » et « FTP 6 semaines ») font partie des contenus de départ (**Réglages**, **Contenus**). **Créer un plan**, en bas de la liste des plans, compose votre propre plan : **Jours** (oui ou non pour chaque jour, mardi, jeudi et samedi au départ), **Entraînements** (ceux de la bibliothèque et le test de FTP ; chaque choix prend le numéro suivant, un second choix le retire), **Durée** (automatique : les entraînements une fois chacun ; plus de semaines : la suite recommence, 12 semaines au plus), puis **Créer le plan**. La carte de droite montre les premières semaines. Le plan s'appelle « Mon plan » (puis « Mon plan 2 »…) et s'ouvre sur sa page : **Démarrer ce plan aujourd'hui** le lance.

**Test de FTP.** **Test de FTP** à l'accueil lance la rampe : paliers d'une minute, +20 W, jusqu'à ce que tu ne puisses plus suivre. Roulez-la de préférence sur une boucle, car un parcours avec arrivée termine la séance. Au bilan, **Accepter** écrit la nouvelle FTP dans la configuration ; **Garder** conserve l'ancienne.

## 6. Commandes du Click et du clavier

Chaque bouton garde le même type d'action partout : « + » et « − » déplacent ou dosent (un appui long fait un grand pas), **A** choisit, **Y** revient en arrière ou met en pause, **Z** fait l'action du mode. Un appui est court en dessous d'une demi-seconde et long à partir de 0,9 s ; entre les deux, il ne fait rien et l'écran le signale.

**Dans les menus**

| Action | Click |
| --- | --- |
| Élément suivant | « + » court, A court, flèche droite |
| Élément précédent | « − » court, flèche gauche |
| Sauter de cinq vers le bas | « + » long |
| Sauter de cinq vers le haut | « − » long |
| Valider | A long |
| Revenir (sur l'écran de pause : reprendre) | Y |

**Pendant la séance, en Session libre**

| Action | Click |
| --- | --- |
| Braquet plus un, moins un | « + » court, « − » court |
| Braquet plus dix, moins dix (de 1 à 24) | « + » long, « − » long |
| Pause et reprise | Y |
| Vue de caméra suivante, précédente | flèche haut (ou A court), flèche bas |
| Activer le bonus en réserve (mode classique) | Z |
| Noter un décrochage du trainer au journal | Z long |

**Pendant la séance, en ERG**

| Action | Click |
| --- | --- |
| Intensité plus ou moins 2 % | « + » court, « − » court |
| Intensité plus ou moins 10 % (de 80 à 120 %) | « + » long, « − » long |
| Bloc suivant | Z |
| Noter un décrochage du trainer au journal | Z long |
| Pause et reprise | Y |
| Entraînement fini : terminer et enregistrer | Y, puis A long |
| Vue de caméra suivante, précédente | flèche haut (ou A court), flèche bas |

**Z long** (ou `Maj+Z` au clavier) note un repère « décrochage » au journal quand vous sentez la résistance du trainer lâcher (sauf en Cyber-Rogue, où Z long joue la carte active). L'écran le confirme ; rien d'autre ne change. L'outil `decrochages` relit ces repères en face des chutes de puissance mesurées.

Un entraînement ERG n'a jamais de roue libre : la consigne ne descend pas sous 50 W, et un bloc « FreeRide » d'un fichier `.zwo` devient un palier à 50 W. En ERG d'une session libre (section 5), Z garde son rôle de la Session libre (bonus) ; en ERG cadence, « + » et « − » changent la cadence cible de ± 2 % (appui long ± 10 %).

**Au clavier**

Le clavier double le Click touche pour touche, en menu comme en séance, avec les mêmes durées d'appui. Les touches de la colonne de droite font l'appui long d'un coup, sans tenir la touche.

| Bouton du Click | Touche | Appui long aussi par |
| --- | --- | --- |
| « + » | `+` (ou `=`, `+` du pavé numérique) | `Page haut` |
| « − » ou B | `-` (ou `-` du pavé numérique) | `Page bas` |
| A | `A` | `Maj+A`, `Entrée` |
| Y | `Y` ou `Échap` | — |
| Z | `Z` | `Maj+Z` |
| Flèches | `Gauche`, `Droite`, `Haut`, `Bas` | — |

Les lettres se lisent comme imprimées sur la touche (AZERTY comme QWERTY). Les flèches haut et bas ne changent pas le braquet : en séance, elles changent la vue de caméra.

Le boîtier gauche porte « − » et les quatre flèches : gauche et droite choisissent l'élément précédent ou suivant (menus, couloirs et cartes du Cyber-Rogue, branches d'un carrefour), haut et bas changent de vue en séance. Il est redémarré tout seul environ une fois par minute et reste alors 4 s environ sans boutons ; le bouton **B** du boîtier droit fait aussi « − », et tout ce que fait le gauche existe aussi sur le boîtier droit ou au clavier. Chaque type d'appui a son bip, ce qui permet de savoir ce qui a été compris sans regarder l'écran.

## 7. Réglages, thèmes et sons

**Réglages** (menu principal) : **Appareils**, **Contenus** (contenus de départ : entraînements, plans et parcours de démonstration ; pack « Cols célèbres », construit depuis OpenStreetMap après confirmation ; archives de thèmes, de biomes ou de parcours trouvées dans Téléchargements, sur le Bureau ou dans `~/OpenRide/Import` ; thèmes installés et place libre ; état « installé », « en partie installé » ou « à installer » ; A maintenu installe ce qui manque, sans rien écraser), puis un sous-écran par thème. **Cycliste** : FTP, poids, FC max, poids du vélo. **Séance** : difficulté en SIM (part de la pente ressentie, de 0 à 100 %, aussi sur l'écran de pause, où elle est gardée pour la séance suivante), braquet de départ, bonus, niveau des bots, pilotage du trainer (« résistance calculée » par défaut : OpenRide calcule la force de la route et règle le frein du trainer, sans trou de résistance après un sprint ; « SIM du trainer » : le trainer simule lui-même la pente et l'élan). **Graphisme** : qualité graphique (low, medium ou high), thème, courbes de la séance, mode d'affichage, images/s, jauge d'abri des bots, vue de caméra, décor vivant et relief exagéré (100 % : relief réel, 250 % par défaut ; ces deux derniers s'appliquent au lancement suivant, et la ligne **Relancer OpenRide maintenant** apparaît quand l'un d'eux a changé). **Son** : les six volumes. **Vent** : vent (coupé, constant, en rafales ou celui du thème), force, direction (par 45°, avec le point cardinal), rafales, plafond et ressenti (par la pente, ou par le trainer, à l'essai). **Avancé** : télécharger les cartes du monde ouvert (« non » : hors ligne, cache seulement), place du cache du monde ouvert et des thèmes installés (en Go), progression et Garage (« non » : comme avant la 2.0, au lancement suivant). Pour changer une valeur, choisissez le réglage et maintenez A : la valeur s'écrit entre deux flèches (`◀ 75 % ▶`) ; + et B la règlent (appui long : cinq pas), A maintenu l'enregistre et Y annule. Les réglages sont écrits dans `~/OpenRide/config.toml` ; ceux qui touchent la séance en cours s'appliquent tout de suite, les autres à la séance suivante.

**Qualité graphique.** Trois préréglages : `low`, `medium`, `high`. Si l'image saccade, passez en `low`.

**Décor vivant.** Le paysage s'anime autour du parcours : pluie, neige légère ou brume selon le thème, rapaces, volées d'oiseaux et corneilles, troupeaux dans les prés, moutons sur les pentes, lièvres dans les champs, éoliennes et drapeaux qui suivent le vent, voitures, camions et motos sur la route, circulation sur les routes voisines et tracteurs aux champs, cyclistes seuls ou en groupe (certains doublent en disant « Salut ! »), avions de ligne, parapentes au-dessus des montées et montgolfières par vent faible, bateaux sur les lacs, les canaux et les rivières, spectateurs au sommet des cols et passants dans les villages. Les phares s'allument dans la brume, sous la pluie ou au soleil bas. En pause, les véhicules, les cyclistes, le ciel et les bateaux se figent ; les animaux et les oiseaux continuent. La quantité dépend de la qualité graphique (moins d'objets en `low`). Les routes voisines, les prés et les champs viennent des couches OpenStreetMap du parcours (format `.world` 1.5 : recompilez un parcours plus ancien pour les avoir). Pour tout couper et retrouver le rendu de la version 1.0 : **Réglages › Graphisme › Décor vivant** sur « non », puis **Relancer OpenRide maintenant**.

**Thèmes.** Un thème change l'apparence de la route, du terrain et du ciel. Pour en ajouter un, déposez son archive `.zip` (thème ou pack de textures des biomes) dans Téléchargements, sur le Bureau ou dans `~/OpenRide/Import`, puis **Réglages**, **Contenus** : l'archive y apparaît avec sa taille ; A maintenu l'installe. Le même écran liste les thèmes installés, avec leur taille et leur dernière utilisation, et la place libre sur le disque ; un thème se choisit ensuite dans **Réglages**, **Graphisme**. La bibliothèque est plafonnée à 5 Go (`[render] theme_library_gb`) : au-delà, l'installation retire le pack utilisé le moins récemment, jamais le thème choisi. Recette d'un pack de textures libres pour les biomes : [3.0/PACK_BIOMES_CC0.md](3.0/PACK_BIOMES_CC0.md). **Textures du décor** (dans **Réglages**, `[render] texture_level`) : « selon la qualité » par défaut ; un pack qui fournit plusieurs tailles d'images (`theme-pack`) donne alors 1 024 px en basse et moyenne qualité, 2 048 px en haute, sous un budget de mémoire vidéo ; « hautes » impose 2 048 px quelle que soit la qualité.

**Sons.** OpenRide génère lui-même les sons du parcours (vent, roue libre, cloches, rivières). Un fichier OGG déposé dans `~/OpenRide/Sounds/` sous le nom du son (`wind.ogg`, `freewheel.ogg`, `church_bell.ogg`, `river.ogg`, `livestock.ogg`, `village.ogg`) le remplace. En mode classique, un court jingle marque le sommet d'une montée, la fin d'un sprint, le passage sous une arche de bonus et la fin de la séance ; il se remplace de la même façon (`jingle_summit.ogg`, `jingle_summit_pr.ogg` pour un record, `jingle_sprint.ogg`, `jingle_sprint_pr.ogg`, `jingle_arch.ogg`, `jingle_finish.ogg`).

**Profils de joueurs.** Chaque cycliste a son profil : réglages du cycliste et de la séance (FTP, poids, FC max, difficulté, braquet de départ, bonus, niveau des bots, vent, vue de caméra, courbes, ceinture cardio), progression, Garage, records, plan et séances, dans `~/OpenRide/Profils/<profil>/`. Le reste (graphisme, affichage, volumes, trainer, Click) appartient au PC et reste dans `~/OpenRide/config.toml`. Au premier lancement de cette version, votre profil actuel devient « Cycliste 1 » (`Profils/principal/`) après une sauvegarde dans `~/OpenRide/Sauvegardes/` ; les séances simulées ou rejouées passent dans le profil d'essai. Avec au moins deux profils, l'écran **Qui roule ?** s'ouvre après la connexion des appareils : le dernier profil est présélectionné, A maintenu le choisit. La ligne **Profil** de l'accueil y ramène pour changer de profil sans relancer. **Nouveau profil** propose « Cycliste N » ; pour écrire un autre nom au Click, + et B passent à la lettre suivante ou précédente (maintenus : une ligne), Z écrit la lettre, Y efface, A maintenu valide ; au clavier, tapez le nom puis Entrée ; à la souris, cliquez les lettres puis « Valider ». **Gérer un profil** permet de le renommer ou de le supprimer (il part dans la corbeille) ; le profil en cours et le dernier profil ne se suppriment pas. En fin de liste, **Restaurer un profil supprimé** le remet parmi les profils, tant que son nom n'a pas été repris, et **Vider le profil d'essai** le remet à zéro, après confirmation. Pour ouvrir directement un profil : `openride --profil cycliste-2` (l'identifiant est le nom en minuscules, sans accents) ; `openride-core profil list` liste les profils.

**Derniers choix.** Chaque profil retrouve ses derniers choix au lancement suivant : le dernier parcours est déjà chargé, l'écran Prêt reprend le bot et le fantôme de la dernière séance, la liste des entraînements s'ouvre sur le dernier choisi et le globe du monde ouvert sur le dernier départ (A, A, A relance le même). Le Cyber-Rogue reprend l'objectif et la durée de la dernière run. Un parcours supprimé entre-temps est simplement oublié.

**Profil d'essai.** « Session simulée » roule sur le profil d'essai (`Profils/_essai/`), signalé par « PROFIL D'ESSAI » dans le titre et le bandeau « ESSAI » : ses séances, ses pièces et ses records ne touchent jamais votre profil. **Gérer un profil > Vider le profil d'essai** le remet à zéro.

## 8. Retrouver ses séances

Chaque séance est écrite dans `~/OpenRide/Activities/` au format FIT, un fichier par séance, nommé avec la date. Ces fichiers s'importent tels quels dans **Garmin Connect** (Importer des données) ou dans **GoldenCheetah**. Si le core plante pendant une séance, OpenRide le relance et la séance reprend en pause au même endroit. Après un arrêt brutal du PC, la séance interrompue est proposée au lancement suivant, en tête de l'accueil : **Enregistrer la séance** en fait un FIT, **Ne pas l'enregistrer** (confirmé) la laisse de côté sans la reproposer.

Pour relire les chiffres d'une séance : `openride-core summary` (dernier bilan) et `openride-core history` (cumul par semaine).

## 9. Dépannage

**Le trainer ne répond plus ou reste « réservé ».** Une autre application (Zwift, le téléphone) le tient peut-être, ou OpenRide s'est arrêté sans le rendre. Fermez l'autre application, puis cliquez sur l'icône **OpenRide – Libérer le trainer**. En terminal : `openride-core release-trainer`. Éteindre et rallumer le trainer règle aussi la plupart des cas. Si le trainer reste réservé malgré cela, débranchez-le quelques secondes, puis relancez OpenRide ; s'il ne se connecte toujours pas, joignez le journal à une demande d'aide (voir plus bas).

**Le Click ne répond plus.** Appuyez sur un bouton pour le réveiller. Sinon, déconnectez-le d'abord (`bluetoothctl disconnect` suivi de son adresse) puis rappuyez. Si le boîtier gauche (« − » et flèches) ne répond pas pendant quelques secondes, c'est son redémarrage : sans passage récent par l'application Zwift (moins de 24 heures), Zwift le verrouille environ une minute après la connexion et OpenRide le redémarre tout seul (environ 4 s sans boutons, puis il répond de nouveau) ; un appui fait pendant ces quelques secondes est perdu, **B** du boîtier droit fait « − » en attendant. Ce n'est pas une panne d'OpenRide. Pour le laisser muet à la place : `click_reset_locked = false` dans `[drivers]`.

**Écran noir, lent ou saccadé.** Passez la qualité graphique en `low` (**Réglages**). Vérifiez que le pilote de la carte graphique est installé. Les courbes de la séance en « masquées » libèrent aussi un peu de puissance.

**Un parcours n'apparaît pas.** Importez la trace par **Ajouter un parcours** (liste des parcours) : l'erreur éventuelle s'affiche sur la ligne d'état. Une trace déposée à la main dans `~/OpenRide/GPX/` n'est compilée qu'au lancement suivant ; un fichier illisible y est signalé.

**Une fenêtre d'erreur s'affiche au lancement.** Elle donne la cause (Godot introuvable, configuration invalide, port occupé, trainer réservé, plantages répétés) et le chemin du journal. Pour un réglage invalide, la fenêtre propose de **remettre la valeur par défaut** (ou de repartir d'un fichier neuf s'il est illisible) : répondez Oui, OpenRide garde une copie `config.toml.bak` (ou `profil.toml.bak`) et démarre.

**Que joindre à une demande d'aide.** Le dernier journal du lanceur dans `~/OpenRide/Logs/` (nom de la forme `openride_AAAA-MM-JJ_HH-MM-SS.log`) et, pour un problème de trainer ou de Click, le fichier `~/run_trainer.log`. Ces fichiers ne contiennent pas de mot de passe, mais relisez-les avant de les partager : ils peuvent citer les adresses Bluetooth de votre matériel.
