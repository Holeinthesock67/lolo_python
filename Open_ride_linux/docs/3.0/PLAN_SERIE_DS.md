# Plan de la série DS : mode « Dernier survivant »

Demande du propriétaire du 31 octobre 2026 : « un mode dernier survivant. Le joueur se bat contre les bots et le dernier arrivé aux diverses arches est éliminé. » C'est la course à l'élimination de la piste, transposée sur route : à chaque arche, le dernier coureur encore en course sort, jusqu'à ce qu'il n'en reste qu'un. Ce document est une étude ; aucun code n'est écrit. Toute maquette sera soumise au propriétaire avant le moindre code d'affichage, et tout essai de performance se fera en `low`, `medium` **et** `high`, captures à l'appui.

Sources lues : `core/src/openride_core/bots.py` (bots constants, fantôme, bots à profil T12 avec réserve W′, calibrage T13, au plus 4 bots plus le fantôme), `core/src/openride_core/classic.py` (T7), `core/src/openride_core/draft.py` (AS1), `core/src/openride_core/session.py` (commande `start`, `mode` `ride` ou `wtf`), `docs/contracts/ipc_v1.md` (liste `bots`, limite de 4 096 octets, `segment_result`), `docs/2.0/PLAN_SERIE_WTF.md`, `docs/5.0/PLAN_SERIE_CT.md`, `docs/4.0/PLAN_SERIE_TT.md`, cahiers AS1, AS4, Y10 et Y18.

---

## 1. En bref

1. **Un mode à part**, « Dernier survivant » (`survivor`), lancé depuis l'accueil du menu comme le Mode WTF : le classique ne change pas. Rien ne se lance en ligne de commande.
2. **Une arche tous les X km** (1, 2 ou 3 km au choix, 2 km par défaut), **autant d'arches que d'adversaires** : avec 4 bots, 4 arches, 8 km de course ; la dernière arche désigne le vainqueur.
3. **Élimination immédiate** : dès que l'avant-dernier coureur encore en course passe l'arche, le dernier est éliminé, sans attendre qu'il y arrive.
4. **Physique honnête** : mêmes bots à profil (T12, T13), même aspiration (AS1, puis AS4), pas de bonus, pas d'élastique qui ralentit les bots de tête. C'est l'abri qui fait la tactique : rester dans les roues, puis sortir avant l'arche.
5. **SIM seulement**, comme le Mode WTF et la Course tactique : en ERG le trainer impose la puissance et la course n'aurait plus de sens. Les braquets restent sur + et −.
6. **Éliminé, le joueur continue à rouler** (réglage par défaut) : la séance d'entraînement n'est pas coupée, la course continue entre les bots jusqu'au vainqueur, puis le bilan donne la place. Un réglage permet de terminer la séance à l'élimination.
7. **Pas de doublon** : le Mode WTF déforme la physique pour rire, la Course tactique (5.0) ajoute des capacités, le Burnout et les relais. Le dernier survivant n'ajoute qu'une règle de course, sur la physique du classique.

## 2. Règles

### 2.1 Départ et adversaires

- Départ groupé : les bots sont créés à la position du cycliste, comme aujourd'hui (`start.bots`, lot O7).
- **Adversaires** : 2 à 4 bots tant que le core en limite le nombre à 4 (`MAX_CONSTANT_BOTS`), puis jusqu'à 11 avec le peloton prévu après le lot Y18 (lot DS8). Le fantôme est exclu : il rejoue une séance passée, il ne peut ni réagir ni être éliminé de façon juste.
- **Composition** : le core compose lui-même le plateau à partir des réglages du mode. Les profils tournent dans l'ordre grimpeur, rouleur, sprinteur, diesel (T12), et les niveaux sont étalés autour du réglage existant « Niveau des bots » (`bots.level_pct`, 50 à 150 % de la FTP) selon l'écart choisi : serré ± 3 %, normal ± 8 % (défaut), large ± 15 %. Chaque bot est calibré au départ (T13). Sans écart, l'ordre des éliminations serait presque tiré au sort ; avec lui, il suit le niveau, sauf erreur tactique.

### 2.2 Arches

| Point | Règle proposée |
| --- | --- |
| Nombre | Une arche par adversaire : N bots, N arches. Après l'arche k, il reste N + 1 − k coureurs ; après la dernière, le vainqueur. |
| Espacement | Réglage « Écart entre arches » : 1, 2 ou 3 km, 2 km par défaut. Arche k à `s0 + k × écart`, `s0` étant la position au départ. |
| Calage sur le terrain | Sur un parcours compilé, une arche qui tombe à moins de 300 m d'une ligne de sprint ou d'un sommet (couche `segments`, T3) est posée sur cette ligne : l'arche coïncide avec un vrai enjeu du terrain et les portiques ne se doublent pas (fusion sous 25 m de `segment_markers`). Jamais avant 1 km après le départ. |
| Longueur du parcours | La course mesure N × écart. Le menu affiche « 4 arches, 8 km » et refuse un parcours trop court (sauf circuit, où les arches continuent au tour suivant, et monde ouvert, où elles suivent la distance roulée). Le reste du parcours après la dernière arche se roule librement. |
| Passage | Instant interpolé entre deux pas du core (50 Hz) à partir de `s` avant et après la ligne : la précision est bien meilleure que 20 ms. |
| Élimination | Quand tous les coureurs encore en course sauf un ont passé l'arche, le dernier est éliminé tout de suite, même s'il est loin derrière. |
| Égalité | Écart de passage sous 1 ms : le bot est éliminé plutôt que le joueur ; entre deux bots, celui du niveau le plus bas, puis l'identifiant le plus grand. Règle fixe, rejouable avec la même graine. |
| Pause | Une pause (bouton Y, coupure du trainer) fige tout le monde, comme aujourd'hui. Pas d'élimination pendant une pause. |

### 2.3 Éliminés

- **Bot éliminé** : il se range sur le bas-côté, ralentit à 15 km/h et disparaît au bout de 10 s ou hors champ. Il cesse tout de suite de compter dans l'abri (sinon le joueur pourrait profiter d'un coureur hors course) et dans les écarts.
- **Joueur éliminé** : bandeau « Éliminé, 4e sur 5 », son d'élimination. Réglage « Après élimination » : *continuer à rouler* (défaut : la séance continue, les bots encore en course restent visibles jusqu'au vainqueur, puis la route est libre) ou *terminer la séance* (bilan tout de suite). Dans les deux cas, journal et FIT gardent toute la séance.
- **Place** : éliminé à l'arche k avec N bots, le coureur finit (N + 2 − k)e sur N + 1. Le vainqueur est 1er.

### 2.4 Ce qui reste du classique

| Élément | Dans ce mode | Pourquoi |
| --- | --- | --- |
| Physique, abri (AS1, puis AS2 à AS7), vent | Identiques | Le mode n'ajoute qu'une règle de course |
| Bonus (T6) | Coupés | Les bots n'en ont pas (décision 4.0) ; course déséquilibrée sinon |
| Segments, records, maillots (T2 à T14) | Coupés | Une seule course à suivre à l'écran ; le haut droit du HUD sert aux arches |
| Journal, FIT, expérience (série V) | Comme une séance libre | Puissance et vitesse réelles |
| Difficulté (Q1) | Inchangée | Elle ne change que la pente ressentie, pas la course |
| Bilan | Place, arche de chaque élimination, écarts | Lot DS6 |

## 3. Bots : tactique de survie (lot DS3)

Les bots à profil roulent aujourd'hui selon leur stratégie par segment (T12) et prennent la roue du coureur devant (AS1). Pour une élimination, il leur faut une règle de plus, calculée dans le core :

- **Danger** : à moins de 400 m de l'arche, un bot parmi les deux derniers encore en course, ou à moins de 2 s du dernier, monte à sa puissance de sprint (de 120 à 150 % de sa CP selon le profil) tant que sa réserve W′ dépasse 10 %.
- **Économie** : un bot à plus de 5 s du dernier roule à 95 % de sa CP et reste dans les roues, pour garder sa réserve.
- **Hasard borné** : point de départ du sprint tiré entre 250 et 400 m (graine de la séance), pour que deux courses ne se ressemblent pas.
- Les attaques, la fatigue et le placement plus fins viendront avec Y10 (fin de projet) ; DS3 n'en dépend pas.

Il n'y a pas d'élastique : un bot ne ralentit jamais parce que le joueur est loin. La difficulté se règle par le niveau et l'écart de niveau.

## 4. Accès par les menus

Tout se règle dans le menu, sans ligne de commande (lot DS7) :

- Accueil : entrée « Dernier survivant », visible quand le core annonce le mode (comme « Mode WTF »).
- Écran du mode : parcours (liste habituelle, avec la longueur de course et la mention « trop court » quand il ne convient pas), puis les réglages ci-dessous, puis « Lancer ».

| Réglage (`survivor.*`, section `[survivor]` de `config.toml`) | Valeurs | Défaut |
| --- | --- | --- |
| Adversaires (`opponents`) | 2 à 4, puis 2 à 11 avec DS8 | 4 |
| Écart entre arches (`spacing_km`) | 1, 2, 3 | 2 |
| Niveau des bots (`bots.level_pct`, réglage existant) | 50 à 150 % de la FTP | inchangé |
| Écart de niveau (`spread`) | serré, normal, large | normal |
| Après élimination (`after_out`) | continuer, terminer | continuer |

Les réglages sont enregistrés par le core (commande `set_setting`, comme les autres réglages) et repris à la séance suivante.

## 5. HUD et sons (maquettes DS4, puis DS5 et DS6)

Style : celui du classique, et l'arche gonflable commune à tous les portiques (PR #560) avec un style à elle (bandes rouges et noires, bandeau « ÉLIMINATION »). Pas de charte cartoon : le mode garde la physique honnête et l'allure du classique.

- **Bloc en haut à droite** (libre puisque segments et bonus sont coupés) : « Arche 2 / 4 · 650 m » avec une barre de progression ; « 3e sur 4 en course » ; écart avec le dernier (« Dernier : Rouleur à 2,4 s ») ou, si le joueur est dernier, « DERNIER ! Rouleur à 1,2 s devant » en rouge clignotant doux (pas de flash plein écran).
- **Liste des coureurs** à gauche : survivants dans l'ordre de course, éliminés grisés avec leur arche ; une ligne par coureur, compacte jusqu'à 12.
- **À chaque élimination** : bandeau 3 s « Éliminé : Grimpeur (arche 2) », court jingle (famille des jingles de portique, T17 et #560), et le bot qui se range.
- **Joueur éliminé, vainqueur** : grand bandeau, puis bilan (place, arche par arche, écart au passage).

## 6. Champ `survivor` proposé (contrat : lot DS2)

Révision : la première libre à la fusion de DS2 (la 1.6 est réservée à la série U, la suivante à TT1). Ajouts compatibles :

- `start` : `mode` gagne la valeur `survivor` ; avec un entraînement ERG, un argument `bots`, un fantôme ou un parcours trop court (hors circuit et monde ouvert) : `bad_args`, rien ne démarre.
- `state.survivor`, dans chaque trame de la course :

```json
{"arch": 2, "arches": 4, "d_m": 650.0, "alive": ["b2", "me", "b4"], "last": "b4",
 "gap_last_s": 1.8, "out": [["b1", 1], ["b3", 1]], "me_out": null}
```

  `alive` dans l'ordre de course ; `out` = paires (bot, arche) ; `me_out` = arche de l'élimination du joueur ou `null`. Environ 150 octets avec 4 bots, environ 300 avec 11 : la trame la plus chargée reste sous la limite de 4 096 octets (à vérifier par `python -m openride_core.ipc_budget`). Chaque élément de `bots` gagne `out` (arche de l'élimination) quand le bot est éliminé.
- Message `elimination` : `v`, `arch`, `rider` (`me` ou id du bot), `name`, `place`, `gap_s` (retard sur l'avant-dernier), `alive` ; répété 3 fois à 1 s, comme `segment_result`.
- `summary.survivor` : `place`, `of`, `arches`, `spacing_km`, `eliminated` (liste `[arche, id, nom, écart]`), `winner`.

## 7. Performances (budgets GPU : low 6 ms, medium 12 ms, high 14 ms)

- **Arches** : seules la prochaine arche et celle qu'on vient de passer existent dans la scène (deux au plus). Une arche gonflable coûte quelques appels de dessin (mesure de #560 : jusqu'à + 36 appels pour toute une vitrine dense de portiques).
- **Bots** : le coût est celui du lot Y18 (bots dessinés comme l'avatar, LOD par distance et par préréglage). Le pire moment est le départ, quand tous les adversaires sont là ; il diminue à chaque élimination. Avec 4 bots, rien de nouveau ; avec 11 (DS8), c'est la mesure principale du lot, en `low`, `medium` et `high`, et la solution de repli est de réduire les distances de LOD (`BOT_LOD_M`).
- **HUD** : une liste de 12 lignes et un bloc, négligeables.
- **Core** : un passage d'arche se teste en O(N) par pas ; rien de mesurable à 50 Hz.
- Recette DS9 : banc au départ (pire cas) en `low`, `medium` et `high`, captures validées par le propriétaire avant fusion des lots d'affichage.

## 8. Lots

| Lot | Titre | Dépend de | Taille |
| --- | --- | --- | --- |
| [DS1](../lots/LOT_DS1_regles_core.md) | Règles du mode dans le core (arches, passages, éliminations, égalités, bilan) | T12, T13, AS1 | Moyenne |
| [DS2](../lots/LOT_DS2_seance_contrat.md) | Branchement dans la séance, réglages et contrat IPC | DS1 | Moyenne |
| [DS3](../lots/LOT_DS3_tactique_bots.md) | Tactique de survie des bots | DS1 | Moyenne |
| [DS4](../lots/LOT_DS4_maquettes.md) | Maquettes de l'arche, du HUD et du bilan, validées par le propriétaire | DS1 | Petite |
| [DS5](../lots/LOT_DS5_arches_bots_engine.md) | Engine : arche d'élimination, bots qui se rangent, sons | DS2, DS4 | Moyenne |
| [DS6](../lots/LOT_DS6_hud_bilan.md) | Engine : HUD de course, bandeaux et bilan | DS2, DS4 | Moyenne |
| [DS7](../lots/LOT_DS7_menu.md) | Menu : entrée « Dernier survivant » et écran de réglages | DS2 | Petite |
| [DS8](../lots/LOT_DS8_peloton_onze.md) | Jusqu'à 11 adversaires (après le peloton du lot Y18) | DS2, Y18 | Moyenne |
| [DS9](../lots/LOT_DS9_recette.md) | Recette sur le vélo (étapes de 10 min) et banc `low`, `medium`, `high` | DS3, DS5, DS6, DS7 | Petite |

Ordre : T12, T13, AS1 ──► DS1 ──► DS2, DS3, DS4 ; DS2, DS4 ──► DS5, DS6 ; DS2 ──► DS7 ; DS2, Y18 ──► DS8 ; DS3, DS5, DS6, DS7 ──► DS9.

Tous les prérequis de DS1 sont sur `main` (bots à profil, calibrage, abri entre bots) : DS1 à DS4 peuvent démarrer dès que le propriétaire le décide. Les lots DS ne touchent ni la série Q ni les règles du Mode WTF.

## 9. Questions ouvertes (réponses par défaut appliquées en attendant)

1. **Version** : rangé en **3.0** (première version après la 2.0, où sont les bots à profil et l'aspiration fine). Rien n'empêche de l'avancer : ses prérequis sont déjà livrés.
2. **Joueur éliminé** : continuer à rouler par défaut, terminer la séance en option.
3. **Arches** : une par adversaire, tous les 2 km par défaut (1 à 3 km au menu), calées sur une ligne de sprint ou un sommet à moins de 300 m.
4. **Bonus, segments, records et maillots** : coupés dans ce mode.
5. **Fantôme** : exclu du mode.
6. **Égalité** : le joueur l'emporte sur un bot.
7. **Variante possible plus tard** (pas dans la série) : « deux éliminés par arche » pour les grands pelotons, ou une arche tous les tours sur un circuit court, comme sur la piste.
