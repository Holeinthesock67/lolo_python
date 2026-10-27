# Lot T13 – Équilibrage des bots à profil : niveau, calibrage par simulation et choix au menu

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
