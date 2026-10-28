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

Installation, une seule fois, depuis le dossier `Open_ride_linux/` du dépôt (après `sudo apt install python3-venv bluez` et le téléchargement de Godot 4.3, version standard, pas .NET) :

```bash
scripts/install.sh
```

Le script demande le chemin de Godot 4.3 et crée trois icônes dans le menu des applications : **OpenRide**, **OpenRide – Libérer le trainer** et **OpenRide – Mettre à jour**. Il peut être relancé sans risque.

Pour mettre à jour, cliquez sur l'icône **OpenRide – Mettre à jour**. La mise à jour est refusée s'il y a des modifications locales dans le dossier du dépôt ; vos parcours, séances et réglages (dans `~/OpenRide/`) ne sont jamais touchés.

## 3. Premier démarrage et appairage

Lancez OpenRide avec son icône. Au premier démarrage, il crée le dossier `~/OpenRide/` (parcours, entraînements, séances, réglages) et ouvre l'écran **Connexion des appareils**.

1. Allumez le trainer (pédalez un peu pour le réveiller) et les boîtiers du Click.
2. L'écran cherche les appareils. Quand tout est relié, il passe seul au menu. Avec un seul boîtier du Click, ou sans Click, choisissez **Passer**.
3. Pour changer de matériel plus tard : **Réglages**, puis **Appareils : rechercher et appairer**. Appuyez sur le bouton « + » du Click quand l'écran le demande pour reconnaître ce boîtier. Les appareils trouvés sont enregistrés dans `~/OpenRide/config.toml`, puis **Relancer OpenRide** prend en compte le nouveau matériel.

## 4. Rouler un parcours

**Ajouter un parcours.** Déposez une trace dans le dossier `~/OpenRide/GPX/` : un fichier `.gpx`, ou l'export de Garmin Connect tel quel (`.fit`, `.tcx`, `.fit.gz`, `.tcx.gz` ou `.zip`). OpenRide compile les nouvelles traces à chaque démarrage (une notification s'affiche) : fermez-le et relancez-le avec son icône, le parcours apparaît ensuite dans la liste. Pour que la fiche d'un parcours soit plus parlante, posez à côté de la trace un petit fichier du même nom en `.toml` (nom, description, région, étiquettes).

**Lancer une séance.**

1. Au menu principal, **Parcours : …** ouvre la liste. Le tri et le filtre par étiquette sont en bas de la liste.
2. Choisissez **Session libre** (la pente de la route est jouée par le trainer) ou **Session ERG** (section 5).
3. L'écran **Prêt** montre la fiche du parcours (distance, dénivelé, montée principale, durée estimée). Il propose aussi **Bot : …** (un cycliste virtuel à puissance constante), **Fantôme de la dernière séance** et **Records du parcours**.
4. **Démarrer** lance la séance : le vélo avance dès que vous pédalez.

**Pendant la séance.** Le HUD montre puissance, cadence, fréquence cardiaque, vitesse, distance, pente et profil d'altitude. La touche **Y** du Click (ou `Y`, `Échap` au clavier) met en pause : l'écran de pause propose **Reprendre**, **Terminer et enregistrer**, **Abandonner** et le curseur de **Difficulté**.

**Fin de séance.** À l'arrivée d'un parcours ou avec **Terminer et enregistrer**, le bilan affiche la durée, la distance, les puissances (NP, IF, TSS) et les zones. La séance est enregistrée dans `~/OpenRide/Activities/` (section 8).

## 5. Entraînements ERG, plans et test de FTP

En mode **ERG**, le trainer impose la puissance visée à chaque instant ; la pente de la route ne compte plus.

**Choisir un entraînement.** **Session ERG** ouvre la liste de `~/OpenRide/Workouts/`. En bas de la liste : **Créer** un entraînement par intervalles, ou **Importer un fichier** `.zwo`, `.erg` ou `.mrc` trouvé dans Téléchargements, sur le Bureau ou dans `~/OpenRide/Import`. Une première série d'entraînements s'installe avec `python -m openride_core.tools.workouts install` (depuis `core/`, environnement activé).

**Pendant l'ERG.** Le bandeau du bas montre le bloc en cours, le temps restant, la cible et le bloc suivant. Les appuis courts sur « + » et « − » règlent l'intensité de ± 2 %, les appuis longs de ± 10 % ; **Z** passe au bloc suivant et **Y** met la séance en pause. Le détail est dans la section 6.

**Courbes de la séance.** Un graphique façon GoldenCheetah montre la cible, votre puissance, votre fréquence cardiaque et votre cadence. Sa taille se règle dans **Réglages**, **Affichage**, **Courbes de la séance** : masquées, réduites (cible et puissance) ou complètes.

**Volume sonore.** Quatre curseurs dans **Réglages**, **Son**, de 0 (coupé) à 100 % par pas de 10, pris en compte tout de suite : **Volume général**, **Volume vent et roue libre**, **Volume de l'ambiance** (oiseaux, cloches, véhicules, foule) et **Volume bips et événements** (bips du Click, changement de bloc ERG). Détail des catégories : [AUDIO.md](AUDIO.md).

**Images par seconde.** **Réglages**, **Affichage**, **Afficher les images/s** : oui affiche en haut à droite, pendant la séance, « 60 images/s · p99 17 ms » (images de la dernière seconde, et temps d'image que 99 % d'entre elles ne dépassent pas : une valeur haute signale des saccades).

**Plans d'entraînement.** L'accueil affiche **Séance du jour** quand un plan est en cours, sinon **Choisir un plan**. Un plan range des entraînements par semaine et par jour ; il garde en mémoire ce qui est fait et ce qui est en retard. `openride-core plan install` copie deux plans de départ (« Reprise 4 semaines » et « FTP 6 semaines »).

**Test de FTP.** **Test de FTP** à l'accueil propose deux tests : la rampe (paliers d'une minute, +20 W, jusqu'à l'épuisement) et les 20 minutes. Roulez-les de préférence sur une boucle, car un parcours avec arrivée termine la séance. Au bilan, **Accepter** écrit la nouvelle FTP dans la configuration ; **Garder** conserve l'ancienne.

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
| Activer le bonus en réserve (mode classique) | Z |

**Pendant la séance, en ERG**

| Action | Click |
| --- | --- |
| Intensité plus ou moins 2 % | « + » court, « − » court |
| Intensité plus ou moins 10 % (de 80 à 120 %) | « + » long, « − » long |
| Bloc suivant | Z |
| Pause et reprise | Y |

Pendant un bloc de roue libre, « + » et « − » changent le braquet, comme en Session libre.

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

Les lettres se lisent comme imprimées sur la touche (AZERTY comme QWERTY). Les flèches haut et bas ne changent pas le braquet : elles serviront aux vues de caméra.

Le bouton **B** du boîtier droit fait aussi « − » : il sert quand le boîtier gauche ne répond plus (section 9). Chaque type d'appui a son bip, ce qui permet de savoir ce qui a été compris sans regarder l'écran.

## 7. Réglages, thèmes et sons

**Réglages** (menu principal) : **Appareils**, puis un sous-écran par thème. **Cycliste** : FTP, poids, poids du vélo. **Séance** : difficulté en SIM (part de la pente ressentie, de 0 à 100 %, aussi sur l'écran de pause), braquet de départ, bonus. **Affichage** : qualité graphique, thème, courbes de la séance, mode d'affichage, images/s. **Son** : les quatre volumes. **Vent** : vent, force, direction (par 45°, avec le point cardinal), rafales et plafond. Pour changer une valeur, choisissez le réglage et maintenez A : la valeur s'écrit entre deux flèches (`◀ 75 % ▶`) ; + et B la règlent (appui long : cinq pas), A maintenu l'enregistre et Y annule. Les réglages sont écrits dans `~/OpenRide/config.toml` ; ceux qui touchent la séance en cours s'appliquent tout de suite, les autres à la séance suivante.

**Qualité graphique.** Trois préréglages : `low`, `medium`, `high`. Si l'image saccade, passez en `low`.

**Décor vivant.** Le paysage s'anime autour du parcours : pluie, neige légère ou brume selon le thème, rapaces, volées d'oiseaux et corneilles, troupeaux dans les prés, moutons sur les pentes, lièvres dans les champs, éoliennes et drapeaux qui suivent le vent, voitures, camions et motos sur la route, circulation sur les routes voisines et tracteurs aux champs, cyclistes seuls ou en groupe (certains doublent en disant « Salut ! »), avions de ligne, parapentes au-dessus des montées et montgolfières par vent faible, bateaux sur les lacs, les canaux et les rivières, spectateurs au sommet des cols et passants dans les villages. Les phares s'allument dans la brume, sous la pluie ou au soleil bas. En pause, les véhicules, les cyclistes, le ciel et les bateaux se figent ; les animaux et les oiseaux continuent. La quantité dépend de la qualité graphique (moins d'objets en `low`). Les routes voisines, les prés et les champs viennent des couches OpenStreetMap du parcours (format `.world` 1.5 : recompilez un parcours plus ancien pour les avoir). Pour tout couper et retrouver le rendu de la version 1.0, écrivez dans `~/OpenRide/config.toml` :

```toml
[render]
living = false
```

**Thèmes.** Un thème change l'apparence de la route, du terrain et du ciel. Les thèmes ajoutés se placent dans `~/OpenRide/Themes/` avec `openride-compiler theme-install DOSSIER` (et `theme-list` pour voir ceux qui sont installés), puis se choisissent dans **Réglages**.

**Sons.** OpenRide génère lui-même les sons du parcours (vent, roue libre, cloches, rivières). Un fichier OGG déposé dans `~/OpenRide/Sounds/` sous le nom du son (`wind.ogg`, `freewheel.ogg`, `church_bell.ogg`, `river.ogg`, `livestock.ogg`, `village.ogg`) le remplace. En mode classique, un court jingle marque le sommet d'une montée, la fin d'un sprint, le passage sous une arche de bonus et la fin de la séance ; il se remplace de la même façon (`jingle_summit.ogg`, `jingle_summit_pr.ogg` pour un record, `jingle_sprint.ogg`, `jingle_sprint_pr.ogg`, `jingle_arch.ogg`, `jingle_finish.ogg`).

## 8. Retrouver ses séances

Chaque séance est écrite dans `~/OpenRide/Activities/` au format FIT, un fichier par séance, nommé avec la date. Ces fichiers s'importent tels quels dans **Garmin Connect** (Importer des données) ou dans **GoldenCheetah**. Si le core plante pendant une séance, OpenRide le relance et la séance reprend en pause au même endroit. Après un arrêt brutal du PC, `openride-core recover` transforme le dernier journal en FIT.

Pour relire les chiffres d'une séance : `openride-core summary` (dernier bilan) et `openride-core history` (cumul par semaine).

## 9. Dépannage

**Le trainer ne répond plus ou reste « réservé ».** Une autre application (Zwift, le téléphone) le tient peut-être, ou OpenRide s'est arrêté sans le rendre. Fermez l'autre application, puis cliquez sur l'icône **OpenRide – Libérer le trainer**. En terminal : `openride-core release-trainer`. Éteindre et rallumer le trainer règle aussi la plupart des cas. Si le trainer reste réservé malgré cela, débranchez-le quelques secondes, puis relancez OpenRide ; s'il ne se connecte toujours pas, joignez le journal à une demande d'aide (voir plus bas).

**Le Click ne répond plus.** Appuyez sur un bouton pour le réveiller. Sinon, déconnectez-le d'abord (`bluetoothctl disconnect` suivi de son adresse) puis rappuyez. Si seul le boîtier gauche (« − ») est muet, utilisez le bouton **B** du boîtier droit : sans passage récent par l'application Zwift (moins de 24 heures), le boîtier gauche cesse d'envoyer ses boutons environ une minute après la connexion. Ce n'est pas une panne d'OpenRide.

**Écran noir, lent ou saccadé.** Passez la qualité graphique en `low` (**Réglages**). Vérifiez que le pilote de la carte graphique est installé. Les courbes de la séance en « masquées » libèrent aussi un peu de puissance.

**Un parcours n'apparaît pas.** Vérifiez que le fichier est bien dans `~/OpenRide/GPX/` et relancez OpenRide : la compilation se fait au lancement. Un fichier illisible est signalé au lancement.

**Une fenêtre d'erreur s'affiche au lancement.** Elle donne la cause (Godot introuvable, configuration invalide, port occupé, trainer réservé, plantages répétés) et le chemin du journal.

**Que joindre à une demande d'aide.** Le dernier journal du lanceur dans `~/OpenRide/Logs/` (nom de la forme `openride_AAAA-MM-JJ_HH-MM-SS.log`) et, pour un problème de trainer ou de Click, le fichier `~/run_trainer.log`. Ces fichiers ne contiennent pas de mot de passe, mais relisez-les avant de les partager : ils peuvent citer les adresses Bluetooth de votre matériel.
