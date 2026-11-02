# Lot T13 – Équilibrage des bots à profil : niveau, calibrage par simulation et choix au menu

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| 2.0 série T : équilibrage des bots à profil (niveau 90, 100, 110 % ou libre, calibrage par simulation du parcours, profils au menu) | Python, GDScript | T12, O7 | Moyenne | Livré le 28 octobre (PR #488) |

## 1. Objectif

Régler les bots à profil de T12 sur ta FTP. Tu choisis un niveau (90, 100 ou 110 % de ta FTP, ou une valeur libre dans les réglages). Avant le départ, le core simule le parcours et ajuste la CP de chaque bot, pour qu'il finisse dans le même temps qu'un cycliste qui roulerait à ce niveau. Le profil décide **où** le bot est fort, le niveau décide **à quel point** (plan §3.4, question T-Q6 tranchée le 25 octobre).

## 2. À lire

1. `docs/2.0/PLAN_SERIE_T.md` §3.4 (équilibrage) et §6 (T-Q6, décisions du 27 octobre).
2. Cahier `LOT_T12_bots_profil.md` (profils, stratégies, `ProfileBot`).
3. Cahier `LOT_O7_affichage_bots.md` (choix des bots au menu, argument `bots` de `start`).
4. Code : `core/src/openride_core/bots.py`, `physics.py`, `settings.py` (réglages du menu), `session.py` ; `engine/scripts/menu_model.gd` et `menu_flow.gd` (écran des bots d'O7).

## 3. Prérequis

T12 livré ; O7 livré pour l'écran des bots.

## 4. Travail demandé

- **Calibrage** (`bots.py`, fonction pure `calibrate(profile, route, level_pct, rider)`) :
  - temps de référence : un cycliste de ta masse totale (`config.toml`) qui roule à `level_pct` % de ta FTP en puissance constante, sur le parcours entier (un tour pour une boucle), avec `physics.py` ;
  - le bot du profil, avec sa stratégie et sa réserve, est simulé sur le même parcours ; un facteur d'échelle de sa CP (et de son pic) est cherché par dichotomie jusqu'à un temps égal à 0,5 % près ;
  - pas de simulation de 50 Hz : le pas est de 0,5 s, pour moins de 0,5 s de calcul pour 4 bots sur 100 km ;
  - le résultat est gardé pour la séance ; CP et masse publiées dans `cp_w` et `mass_kg`.
- **Niveau** :
  - réglage `bots.level_pct` (entier, défaut 100, de 50 à 150 par pas de 5, libellé « Niveau des bots ») dans `settings.py`, donc dans l'écran « Réglages » ; c'est la valeur libre de T-Q6 ;
  - argument `bots` de `start` : `{ "kind": "profile", "profile": …, "level_pct": 90 }` facultatif, qui prend le pas sur le réglage pour ce bot.
- **Menu de l'engine** (écran des bots d'O7) : ajout des quatre profils, chacun avec trois niveaux (90, 100, 110 %), au plus 4 bots en tout comme aujourd'hui ; aucun nouveau bouton ni nouvelle action (plan de boutons commun inchangé).
- **Contrat :** le champ `level_pct` de l'élément `{kind: "profile"}` est un ajout compatible, dans la même révision que l'élément de T12.

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/bots.py`, `settings.py`, `session.py`, `docs/contracts/ipc_v1.md` et le schéma de `start`, `docs/SRS_v1.1.md` (réglage), `engine/scripts/menu_model.gd`, `menu_flow.gd` et leurs tests, `README.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Nouveau :** `core/tests/test_bots_calibration.py`.
- **Interdits :** `physics.py`, `rogue/wbal.py`.

## 6. Modifications de contrat autorisées

Le champ `level_pct` de l'élément `{ "kind": "profile" }` de l'argument `bots` de `start`.

## 7. Critères d'acceptation

1. `pytest -q` passe dans `core/` ; tests Godot sans écran verts (écran des bots).
2. Parcours de démonstration et parcours de synthèse (plat de 20 km, col de 10 km à 7 %) : chaque profil calibré à 100 % finit à 0,5 % près du temps du cycliste de référence.
3. Niveau 110 % : chaque bot finit plus vite qu'au niveau 100 %, dans un rapport proche de celui du cycliste de référence (à 1 % près).
4. Sur le col : le grimpeur calibré passe devant le diesel calibré dans la montée, alors que les deux finissent ensemble sur le parcours.
5. Réglage `bots.level_pct` hors bornes : `setting_invalid`.
6. Coût : calibrage de 4 bots sur 100 km sous 0,5 s sur le PC de développement.

## 8. Hors périmètre

- Équilibrage ressenti sur le vélo (recette T11).
- Bots du Cyber-Rogue (série R) et de la carrière (série V, lot V5).

## 9. Livraison (28 octobre 2026)

- **`calibrate(profile, route, level_pct, rider, segments, bike_mass_kg)`** dans `core/src/openride_core/bots.py`, fonction pure : temps de référence d'un `RefRider` (FTP et `PhysicsParams.from_config`, donc masse totale, CdA, Crr et rendement de `config.toml`) à `level_pct` % de sa FTP, puis échelle de la CP, de W′ et du pic du profil (`ProfileBot.set_scale`) cherchée sur son logarithme par une sécante gardée dans l'encadrement trouvé (dichotomie quand la sécante en sort). Départ au même W/kg que le cycliste. Tolérance de 0,2 % (sous les 0,5 % du cahier, pour couvrir le relevé du parcours), 12 essais au plus, échelle de 0,2 à 5. Sans vent.
- **Simulation** : `RouteProfile` relève la pente et l'altitude tous les 10 m une fois pour tous les bots ; `ride_time` avance au pas de 0,5 s avec les équations de `RiderPhysics.step` et de `wbal_step` écrites en ligne (`physics.py` et `rogue/wbal.py` inchangés), égalité vérifiée par un test contre le `step` du bot. 4 bots sur 100 km : 0,2 s.
- **Niveau** : section `[bots]` de `config.toml`, `level_pct` (défaut 100, 50 à 150, bornes dans `config.BOUNDS`), réglage « Niveau des bots » du groupe « Séance » (pas de 5) ; `level_pct` facultatif dans `{kind: "profile"}` de `start.bots`, gardé par le bot (`ProfileBot.level_pct`), hors bornes : `bot_invalid`. `calibrate_bots` calibre les bots de la séance dans `CoreSession._new_race` (un calcul par couple profil et niveau, durée au journal) ; les bots de `--bot-profile` prennent le réglage.
- **Menu de l'engine** : `BOT_CHOICES` de `menu_model.gd` gagne les quatre profils à 90, 100 et 110 % (« Grimpeur 90 % »…), dans le même cycle de A long sur l'écran Prêt, sans nouveau bouton.
- **Contrat** : une ligne dans l'historique de la révision 1.5 ; SRS : section `[bots]`.
- **Tests** : `core/tests/test_bots_calibration.py` (critères 2 à 6), `engine/tests/unit/test_menu_flow.gd` (profils au menu, argument de `start`).
- **Abri (lot AS1, 29 octobre)** : le calibrage reste calculé sans abri. En séance, un bot qui roule en groupe ou dans la roue du cycliste s'abrite : il peut donc finir plus tôt que le temps visé.
