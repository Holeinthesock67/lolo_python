# Plan de la série CT : mode « Course tactique » (version 5.0)

Étude du 29 octobre 2026 du document de conception « Triangle Tactique Unifié » proposé par le propriétaire, décisions du même jour au §9. Toute maquette sera soumise au propriétaire avant la moindre modification, et tout essai de performance se fera en `low`, `medium` et `high`.

Sources lues : `core/src/openride_core/physics.py`, `draft.py`, `bots.py` (ProfileBot, T12/T13), `rogue/wbal.py`, `powerups.py` (T6), `session.py` (pente envoyée, abri, ERG), `docs/contracts/ipc_v1.md` (révisions 1.4 et 1.5), `docs/SPECIFICATION_GENERALE.md` §6.1 et §7.1, `docs/lots/LOT_Y10_comportement_bots_core.md`, cahiers AS1 à AS7, `docs/2.0/GDD_CYBER_ROGUE.md`, `docs/spikes.md`. Chiffres calculés avec `physics.steady_speed` et `draft.draft_coefficient` du core actuel.

---

## 1. En bref

1. **Créer un nouveau mode « Course tactique »**, sans toucher aux règles du mode classique, et faire passer dans le classique uniquement ce qui reste réaliste : la réserve W′ du cycliste et des bots affichée, et les bots qui réagissent (Y10). Le mode classique garde ses records, son FIT et sa physique honnête ; le Cyber-Rogue reste un jeu solo contre des salles.
2. **Le core a déjà la moitié du socle** : W′bal de Skiba partagé par le joueur (série R) et les bots à profil (T12), avec le bot ramené à sa CP quand la réserve est vide ; `wbal_pct` des bots déjà dans le contrat 1.4 ; abri exponentiel avec plafond, placement latéral et groupes prévus par la série AS ; relais, attaques et réponses des bots prévus par Y10 ; carrefours et choix au Click dans le monde ouvert (W).
3. **Trois règles sont à ajuster fortement** : la bifurcation telle qu'écrite est physiquement impossible (le raccourci à 12 % est 2,6 fois plus lent, et les deux voies ne peuvent pas finir à la même altitude) ; la pénalité de virage punirait toutes les épingles de montée ; « aspiration doublée » casse le plafond de 55 %.
4. **Tout le mode est SIM seulement** : en ERG, le trainer impose la puissance, si bien qu'aucun pic ni aucune coupure ne sont possibles. Même règle que les bonus de la série T.
5. **La règle 3 (pacte de relais) recouvre les power-ups 4.0** : je recommande que la 4.0 livre le **catalogue d'effets** et que la 5.0 livre l'**économie** qui les paie, au lieu de deux systèmes parallèles.
6. **Sécurité** : jamais de résistance augmentée par une pénalité, des seuils indexés sur la FTP et pas en watts absolus, les relances toujours facultatives, pas de détection de pic pendant une coupure du trainer.

---

## 2. Ce que le core sait faire aujourd'hui

| Besoin du GDD | Dans le core aujourd'hui | Écart |
| --- | --- | --- |
| W′ du joueur et des bots, mêmes lois | `rogue/wbal.py` (Skiba 2015, recharge exacte) ; `ProfileBot` l'utilise et se ramène à sa CP à réserve vide ; CP et W′ estimés depuis l'historique (R16) | La W′ du joueur n'est calculée qu'en Cyber-Rogue ; en classique il n'y en a pas |
| Voir la W′ des bots | `bots[].wbal_pct` dans `state` (révision 1.4) | Pas d'affichage diégétique (couleur du vélo) |
| Bots qui suivent, lâchent, relaient | Stratégie par segment seulement (plat, montée, attaque si réserve, pic au sprint) | Y10 (relais 30 à 60 s, attaques, réponse aux attaques) n'est pas fait ; AS1 recoupe la partie abri de Y10 |
| Abri, zone de 0,5 à 1,5 m | Abri 1D : 0,40 à 0,3 m, 0,38 à 0,5 m, 0,34 à 1 m, 0,30 à 1,5 m, 0,20 à 3 m ; lissage 1 s ; plafond 0,45, porté à 0,55 dans un groupe par AS4 ; le fantôme n'abrite pas | AS2 ajoute `lane_m` et le placement automatique (2.0) |
| Ressenti de l'abri sur le trainer | En SIM, supplément de pente négatif (`grade_offset_pct`), borné, rampe de 4 %/s à la montée et 8 %/s à la descente | En ERG, vitesse seulement |
| Virages | La route a un cap (`heading_deg`), donc une courbure calculable | Aucun modèle de vitesse en virage |
| Bifurcations | Monde ouvert seulement (W) : `open_world.next`, `choose_branch`, A court/long et flèches | Parcours `.world` classiques linéaires |
| Revêtement rugueux | Série U (3.0) : Crr 2 à 3 fois le bitume, en supplément de pente sous le même plafond que le vent | — |
| Capacités | `powerups.py` (T6) : 3 bonus tirés au hasard, 15 s, Z court, vitesse virtuelle seulement, désactivés en ERG | Catalogue 4.0 à l'étude dans un autre fil |
| Boutons | Plan unique §7.1 : Z court action du mode, Z long action spéciale, A choix affiché, boîtier gauche non fiable | — |

Faits du trainer qui comptent pour ce GDD :
- En SIM, la vitesse du trainer met 7 à 8 s pour suivre une commande de pente (`spikes.md`). La puissance mesurée, elle, suit l'effort en environ une seconde : **une mécanique détectée sur la puissance est réactive, une mécanique qui passe par la résistance du trainer ne l'est pas.**
- En ERG, le trainer tient la cible : pédaler plus fort fait baisser la résistance. Un pic de +150 W ou une coupure à 0 W n'existent donc pas en ERG.
- Coupures du trainer (ATT 0x80, Control Point occupé, #540 et #542) : la puissance tombe à 0 puis remonte. Sans garde, cela ressemble exactement à « couper puis relancer sec ».

---

## 3. Règle par règle

### Règle 1 : symétrie de la surchauffe (W′ et Burnout)

**Verdict : à garder, en l'ajustant pour réutiliser le modèle existant.**

- **Garder** la symétrie : c'est déjà le principe de T12 (« le même modèle pour le joueur et les bots »). Une seule fonction, `wbal_step`, pour tout le monde.
- **Ajuster les seuils** : le GDD dit « se vide au-dessus de 105 % de la FTP, se recharge sous 85 % ». Deux seuils de plus créeraient une exception à côté de Skiba. Je recommande de garder Skiba tel quel : la réserve se vide au-dessus de la CP et se recharge sous la CP, d'autant plus vite qu'on est bas. La CP et la W′ viennent de R16 (estimées depuis l'historique) ou du réglage `[rogue]`, déjà dans le contrat.
- **Burnout** : 8 s de vitesse bridée à réserve vide, à garder, mais **bridé sur la puissance prise en compte, jamais sur la résistance du trainer**. Proposition : puissance prise en compte plafonnée à 70 % de la CP pendant 8 s, le cycliste peut continuer à pédaler sans à-coup sous les pieds. Pour les bots, même règle. Aujourd'hui un bot à réserve vide est simplement ramené à sa CP, il faudra l'aligner.
- **« Couper à 1 % évite la pénalité »** : à garder, c'est le geste tactique. Avec Skiba, il suffit de repasser sous la CP avant 0 %. Prévoir 0,5 s de tolérance, pour le retard de la puissance mesurée.
- **Lisibilité diégétique** (châssis du bleu au rouge clignotant) : excellente idée de jeu. Décision du 29 octobre : dans le nouveau mode, des effets **flashy et exagérés, façon cartoon** (vélo qui rougit et fume, étoiles du Burnout), avec leur propre charte (lot CT9) ; dans le classique, un signe discret et réaliste (posture, petite jauge en arc comme la jauge d'abri, choix C). **Maquettes à faire valider avant tout code.** Le clignotement reste lent (au plus 2 Hz, pas de flash plein écran), pour le confort visuel.
- **Le contre de 10 s sur un bot à 5 %** : il suppose que le bot décide de suivre ou de lâcher. C'est la « réponse » de Y10 (suivre si réserve au-dessus de 40 %) : il faut que la décision tienne compte de sa propre réserve, pour qu'un bot puisse « exploser » s'il suit à tort. Prévoir un taux d'erreur selon le profil et la difficulté (50 % par défaut).

### Règle 2 : tir à la corde du sillage et catapulte

**Verdict : à garder dans le nouveau mode, avec une zone plus large, une charge progressive et un déclencheur indexé sur la FTP.**

- **Zone de verrouillage de 0,5 à 1,5 m : trop étroite sur un home trainer.** Avec une inertie de 7 à 8 s côté résistance et une puissance lissée sur une seconde, tenir un écart à ± 0,5 m pendant 15 s demande une précision que même Zwift n'exige pas. Une différence de 0,1 m/s déplace l'écart d'un mètre en 10 s. Recommandation : charge **proportionnelle à l'abri reçu** (de 0,20 à 3 m jusqu'à 0,40 roue dans la roue), pleine en 15 s roue dans la roue et en environ 30 s à 3 m. Le geste reste « coller la roue », sans tout perdre pour un demi-mètre.
- **Déclencheur « +150 W en 1 s » : à indexer.** 150 W, c'est 75 % de la FTP d'un cycliste à 200 W et 40 % d'un cycliste à 380 W. Proposition : hausse d'au moins 50 % de la FTP sur 2 s, tenue au moins 1 s. La détection se fait sur la puissance mesurée, ignorée pendant 5 s après une coupure du trainer (#542).
- **Impulsion « gratuite » de 3 s** : à garder dans le nouveau mode, sous forme de puissance prise en compte majorée, comme le bonus « puissance » de T6. Ordre de grandeur : à 37 km/h, +10 % de vitesse pendant 3 s fait gagner 3 m, juste de quoi sortir de la roue et prendre l'abri d'un autre. Ne jamais l'appliquer en ERG ni dans les records sans bonus (T5).
- **Rétro-radar en tête** : à garder. Il ne demande qu'un champ de plus pour le bot qui suit et la charge de sa catapulte. Le HUD le place dans le bandeau des voisins (`bot_behind`, T16).
- **Parade « micro-coup de frein » de 2 s** : en physique 1D, couper 2 s fait seulement se rapprocher le suiveur. Avec la position latérale d'AS2 et le dépassement automatique, le suiveur plus rapide déborde et prend le vent : la parade fonctionne naturellement. Pour le joueur suiveur, il faut que la catapulte se vide quand il passe devant. **Dépend d'AS2.** Ne pas exiger « en virage » : n'importe où sur le plat suffit, et le virage ajoute une exigence sans gain.
- **« Changer de voie à une bifurcation »** : voir la règle 4, ça ne marche que là où il y a des bifurcations.

### Règle 3 : pacte de relais et marché de l'énergie

**Verdict : à garder, c'est l'idée la plus originale, mais en la rebranchant sur les power-ups de la 4.0 et sur les relais de Y10.**

- **Crédits gagnés en tête** : à garder. Mesure simple et juste : le travail aérodynamique fourni pour les autres, soit `(1 − α) × aéro × v` intégré quand au moins un coureur profite de votre abri. Un coureur seul loin devant ne gagne rien, sinon l'échappée solitaire deviendrait la stratégie dominante.
- **Seuil « 15 s en tête »** : à garder comme durée minimale d'un relais qui compte.
- **Cohésion d'échappée** (le bot suivant prend un relais de 20 s à 110 %) : c'est Y10 (relais de 30 à 60 s). Recommandation : une seule règle de relais, celle de Y10, avec un paramètre « relais appuyé » dans le nouveau mode, plutôt qu'une deuxième mécanique.
- **Jauge de capacités à 25, 50 et 100 %** : à garder, mais **les effets doivent venir du catalogue 4.0** (série TT de la 4.0 : un seul modèle d'effets décrit par des données dans `powerups.py`, vitesse virtuelle seulement, coupé en ERG ; accord des deux fils le 29 octobre). Correspondance proposée avec les noms et identifiants de la 4.0, encore à valider par le propriétaire :
  - Sillage furtif (25 %) : « Échappée » (`breakaway`, fusion de Burrito et Fantôme décidée le 29 octobre pour la 4.0 : pendant 20 s, pas d'abri pour les suiveurs et pas de réponse des bots ; refusée à moins de 400 m de l'arrivée) ;
  - Bouclier d'inertie (50 %) : sans équivalent dans la 4.0. Je propose « pas de Burnout et pas de perte en virage pendant 10 s », ajouté au même modèle de données, plutôt qu'un effet sur la masse ;
  - Overdrive aéro (100 %) : « Casque aéro » (`aero`, CdA × 0,75), sur 20 à 25 s au lieu de 15 s.
- **« Supprimer le hasard »** : compatible avec la 4.0 si les power-ups 4.0 sont gagnés au hasard en classique (comme T6) et achetés avec des crédits dans le nouveau mode. Même effet, deux façons de l'obtenir : aucune exception dans le moteur.
- **Boutons** : Z court déclenche la capacité la plus haute que la jauge peut payer, sous 100 % ; Z long déclenche l'Overdrive (100 %). Pas besoin d'A, qui reste aux vues et aux carrefours (§7.1, sans exception).

### Règle 4a : virages, Apex Boost et grip

**Verdict : à ajuster fortement, sinon à écarter.**

- **Le problème** : « pédaler à pleine puissance en plein virage serré fait perdre 15 % de vitesse ». Dans une épingle de montée (l'Alpe, le Ventoux), on roule à 10 ou 15 km/h à pleine puissance : la règle punirait toutes les ascensions. La vitesse critique d'une épingle (rayon de 10 m) est d'environ 25 à 32 km/h, celle d'un virage de 25 m de 40 à 50 km/h. **Le virage ne compte qu'en descente ou sur le plat rapide**, où l'on ne pédale de toute façon pas à fond.
- **Recommandation** : vitesse critique `√(μ g R)` calculée par le core depuis la courbure de la route, et effet seulement quand `v` dépasse cette vitesse. Au-dessus : la vitesse est ramenée à la vitesse critique (freinage automatique, comme Zwift), sans pénalité supplémentaire. Le bonus d'Apex (relance à la corde) n'existe que dans le nouveau mode, au plus un tous les 30 s.
- **« Couper 2 s puis pic au point de corde »** : faisable en SIM, la puissance mesurée répond en environ 1 s. Mais enchaîner une série d'épingles en descente, c'est enchaîner des sprints arrêtés : à limiter (voir §5).
- **Bots qui ratent leur trajectoire** : à garder dans le nouveau mode (chance d'erreur si réserve sous 20 %), affiché avec le `lane_m` d'AS2.

### Règle 4b : bifurcations asymétriques

**Verdict : idée à garder, chiffres à refaire, et seulement là où les bifurcations existent.**

- **Les chiffres du GDD ne tiennent pas.** Calcul avec la physique du core, à la CP de chaque profil de bot :

  | Profil | Voie A : 340 m à 12 %, Crr doublé | Voie B : 400 m à 2 % | Voie B abritée (α 0,30) |
  | --- | --- | --- | --- |
  | Grimpeur (240 W, 68 kg) | 126 s | 49 s | 46 s |
  | Rouleur (259 W, 80 kg) | 136 s | 50 s | 46 s |
  | Sprinteur (264 W, 88 kg) | 147 s | 51 s | 48 s |

  Le « raccourci » est 2,6 fois plus lent pour tout le monde. Et surtout, les deux voies partent et arrivent au même endroit, donc **elles montent du même dénivelé** : 340 m à 12 % font 41 m, qu'une voie à 2 % ne monte qu'en 2 km.
- **Recommandation** : la voie A monte le dénivelé commun d'un coup, la voie B le monte plus doucement sur une distance calculée par le core. Avec 41 m de dénivelé, chacun à sa CP, B abritée (α 0,30) :

  | Longueur de B (pente) | Grimpeur : A, B | Rouleur : A, B | Sprinteur : A, B |
  | --- | --- | --- | --- |
  | 500 m (8,2 %) | 126 s, 127 s | 136 s, 137 s | 147 s, 148 s |
  | 700 m (5,9 %) | 126 s, 136 s | 136 s, 145 s | 147 s, 155 s |
  | 900 m (4,6 %) | 126 s, 147 s | 136 s, 155 s | 147 s, 165 s |

  À effort égal, l'écart entre les deux voies change peu d'un profil à l'autre (4 à 5 s). **Ce qui sépare le grimpeur du sprinteur, c'est l'éclatement du groupe** : sur A, sans abri, ils arrivent à 21 s l'un de l'autre ; sur B, le groupe reste soudé dans les roues. La règle juste est donc : A un peu plus rapide (5 à 10 s, B de 600 à 700 m) mais sélective, B un peu plus lente mais qui garde le groupe. Les longueurs se règlent avec la simulation de calibrage de T13, comme les niveaux des bots.
- **« Aspiration doublée »** : écarter. Elle dépasse le plafond de 55 % (AS4, décision du 29 octobre). Remplacer par « abri × 1,25, plafond inchangé », ou plus simplement par une voie large où l'éventail tient (AS3).
- **Revêtement rugueux** : prendre la surface de la série U (3.0), même plafond que le vent. Si la 5.0 doit pouvoir partir avant U, un Crr par voie suffit.
- **Où** : les parcours `.world` classiques sont linéaires, sans bifurcation. Deux possibilités, à trancher par le propriétaire :
  1. **en monde ouvert** (W), les carrefours existent déjà, avec le choix au Click (A court, A long, flèches) : le nouveau mode marque certains carrefours « asymétriques » ;
  2. **des circuits générés** pour le mode, sans GPS, comme le Cyber-Rogue (`lat`, `lon` à `null`), avec des variantes de 300 m à 2,5 km. C'est le plus simple à équilibrer.

  Je recommande l'option 2 pour démarrer, puis l'option 1.
- **Boutons** : exactement ceux du monde ouvert (A court branche suivante, A long valider, flèches en complément, le boîtier gauche n'étant pas fiable). Flèches au sol en approche : à garder, maquette à soumettre.

---

## 4. Choix du mode

| Option | Pour | Contre |
| --- | --- | --- |
| **A. Nouveau mode « Course tactique », et le socle réaliste dans le classique** (recommandé) | Le classique reste honnête (records, FIT, physique) ; le mode peut tricher (catapulte, Burnout, crédits) ; une entrée de plus dans `hello_ack.config.modes` ; ce qui est réaliste (W′ visible, bots réactifs, AS) profite à tout le monde | Un mode de plus à maintenir |
| B. Tout dans le mode classique, désactivable | Pas de nouveau mode | Records et classements faussés, réglages en cascade, exceptions partout (contraire au principe « on évite les exceptions ») |
| C. Dans le Cyber-Rogue | Charte néon R17 et W′ déjà là, style diégétique cohérent | Le Rogue est solo contre des salles, sans peloton ni abri ; mélanger les deux brouillerait les deux modes |

Recommandation : **option A**. Le nouveau mode a sa propre charte, flashy et exagérée façon cartoon (décision 5 du §9, lot CT9). Il est SIM seulement : `set_ride_mode` y répond `busy`, comme pendant une run. Le fantôme y reste une simple référence (pas de W′, pas d'abri, décision du 25 octobre).

Ce qui va dans le classique, sans règle de jeu : W′ du cycliste calculée et affichée en option, W′ des bots lisible (déjà dans le contrat), bots réactifs (Y10), vitesse critique en virage (freinage automatique seulement).

---

## 5. Sécurité et ressenti sur le home trainer

- **Aucune pénalité ne passe par la résistance.** Burnout, dérive en virage et sillage perdu agissent sur la vitesse virtuelle. La pente envoyée garde ses rampes (4 %/s et 8 %/s) et son plafond.
- **Seuils en % de la FTP**, jamais en watts absolus (pic de catapulte, Apex).
- **Relances facultatives** : le mode doit pouvoir se finir à l'endurance. Un réglage « Intensité des relances » (douce, normale, forte) règle la hausse demandée.
- **Densité des sprints** : au plus une Apex toutes les 30 s et une catapulte toutes les 60 s ; avertissement au départ (« relances en danseuse : vérifiez la fixation du vélo »).
- **Coupures du trainer** : aucune détection de pic ou de coupure dans les 5 s qui suivent une reconnexion, ni pendant un segment suspendu (#542). Gros braquet et faible cadence au moment d'un pic : risque connu de Control Point occupé (#540), à mesurer pendant la recette.
- **ERG** : mode interdit. Le classique en ERG garde l'affichage de la W′ seulement.
- **Lisibilité** : clignotement d'au plus 2 Hz, pas de flash plein écran, couleurs doublées par une forme (arc, icône) pour les daltoniens.

---

## 6. Contrat IPC et HUD

Ajouts compatibles, révision à prendre à la fusion : la première libre (spécification générale §6.1, ordre des fusions), comme la série U (3.0) et le contrat TT1 de la 4.0.
- `modes` : valeur `"tactical"` ;
- `state.tactical` (nouveau mode seulement) : `wbal_pct` et `burnout_s` du cycliste, `sling_pct` (charge de la catapulte), `credits_pct` (jauge de capacités), `active` (capacité en cours, reste en s), `corner` (`v_crit_kmh`, `d_m`, `apex` dans la fenêtre), `leech` (id du bot qui charge dans votre roue, et sa charge) ;
- éléments de `bots` : `burnout` (booléen), `sling_pct` ; `wbal_pct` existe déjà ;
- variantes de route : reprendre la forme `open_world.next` (`b` = branches) plutôt qu'une nouvelle ;
- commande `start` : `{ "mode": "tactical", ... }` ou `start_tactical` sur le modèle de `start_run`.
Taille : moins de 300 octets de plus pour la trame la plus chargée, bien sous la limite de 4 096 octets ; à vérifier avec `ipc_budget`.

HUD : la W′ du cycliste (arc ou barre près de la puissance), la jauge de capacités, la catapulte sur la jauge en arc au-dessus du bot (réutiliser la jauge C de #566), le rétro-radar dans le bandeau `bot_behind`, la vitesse critique en approche de virage. **Toutes les maquettes passent par le propriétaire avant fusion** (règle du 29 octobre).

---

## 7. Découpage (série CT, version 5.0)

La lettre TT est prise par la série des power-ups de la 4.0 : la série de la Course tactique s'appelle CT. Cahiers dans `docs/lots/` (`00_INDEX.md`).

| Lot | Contenu | Où | Dépend de |
| --- | --- | --- | --- |
| CT0 | Simulateur d'équilibrage `tactical_sim` et rapport ; valeurs dans `tactical/balance.toml` | core | Y10, T13 |
| CT1 | Contrat (première révision libre), mode `tactical`, plan des boutons | docs | CT0, TT1 |
| CT2 | W′ du cycliste (option du classique, mode), Burnout symétrique à 70 % de la CP pendant 8 s | core | R2, R16, T12, CT1 |
| CT3 | Cerveau des bots : suivre ou lâcher, erreurs, relais appuyé | core | Y10, AS1, AS4, CT2 |
| CT4 | Catapulte : charge proportionnelle à l'abri, déclencheur en % de la FTP | core | AS2, CT2 |
| CT5 | Parade et rétro-radar | core | AS2, CT4 |
| CT6 | Crédits gagnés en tête, capacités payées (effets de la 4.0) | core | TT2 à TT5, Y10, CT1 |
| CT7 | Virages : vitesse critique et freinage automatique (classique), Apex (mode) | core | AS2, CT2 |
| CT8 | Circuits générés avec variantes asymétriques, puis carrefours du monde ouvert | core | CT0, CT1 ; W pour l'étape 2 |
| CT9 | Charte cartoon et maquettes, validées par le propriétaire avant tout code | docs | CT1 |
| CT10 | Effets cartoon dans l'engine, mesurés en `low`, `medium` et `high` | engine | CT9, CT2 à CT8 |
| CT11 | HUD, menus, pause et bilan | engine | CT9, CT10 |
| CT12 | Recette sur le vélo, étapes de 10 min | propriétaire | CT2 à CT11 |

Ordre : CT0, CT1, puis CT2, CT7 et CT9, puis CT3, CT4 et CT5, puis CT6 (après la 4.0), puis CT8, puis CT10 et CT11, puis CT12.

## 8. Dépendances avec les autres versions

- **2.0** : série AS (AS2 placement latéral, AS3 bordure, AS4 groupes et plafond de 55 %) ; Y10 (relais, attaques, réponses), qui recoupe AS1 pour l'abri entre bots, un seul des deux à faire ; T12 et T13 (bots à profil et calibrage) ; T5 (records avec et sans bonus) ; R2 et R16 (W′bal, estimation de CP et W′) ; R17 (charte néon) ; W (carrefours) ; Y16 (avatar).
- **3.0** : série U pour les revêtements des voies rugueuses (facultatif : un Crr par voie suffit pour démarrer).
- **4.0** : série TT (catalogue des power-ups, `docs/4.0/PLAN_SERIE_TT.md`), dont la 5.0 réutilise le modèle d'effets de TT2 ; test du boîtier gauche du Click avec l'appli Zwift, reporté à la 4.0, qui rendrait les flèches fiables pour les bifurcations.

---

## 9. Décisions du propriétaire (29 octobre)

1. Mode : option A, nouveau mode « Course tactique » et socle réaliste dans le classique (16 h 56).
2. Bifurcations : circuits générés d'abord, monde ouvert ensuite (16 h 59).
3. Capacités : effets repris du catalogue 4.0 (série TT), correspondance du §3, règle 3 (16 h 59).
4. Burnout : puissance prise en compte plafonnée à 70 % de la CP pendant 8 s (16 h 59).
5. Style : **flashy et exagéré, façon cartoon**, même s'il faut créer de nouveaux effets (16 h 59). Ce n'est donc ni le réaliste de Y16 ni le néon de R17 : il faut une charte propre au mode (lot CT9, sur le modèle de R17), avec des maquettes validées avant tout code et une mesure en low, medium et high. Les règles de confort restent : clignotement de 2 Hz au plus, pas de flash plein écran, couleur doublée par une forme.
