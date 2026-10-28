# Lot T12 – Bots à profil : CP, W′, masse, pic sur 10 s et stratégie par segment

## 1. Objectif

Donner à chaque bot du mode classique un profil physiologique et une stratégie simple, pour qu'on puisse choisir comment le battre : le grimpeur attaque dans les montées, le sprinteur lance le sprint dans les 200 derniers mètres, le rouleur est fort sur le plat, le diesel roule régulier. Les profils et leurs valeurs sont ceux validés par le propriétaire le 27 octobre (plan §6).

## 2. À lire

1. `docs/2.0/PLAN_SERIE_T.md` §3.4 (bots à profil) et §6 (décisions du 27 octobre).
2. `docs/contracts/ipc_v1.md` révision 1.4 : champs des bots (`profile`, `cp_w`, `mass_kg`, `wbal_pct`, `jersey`, `gap_s`) ; argument `bots` de `start` (lot O7).
3. Cahiers `LOT_N9_bots_core.md`, `LOT_O7_affichage_bots.md`, `LOT_T7_branchement_seance.md` et `LOT_T14_points_maillots.md`.
4. Code : `core/src/openride_core/bots.py` (`ConstantPowerBot`, `bots_from_menu` d'O7), `core/src/openride_core/rogue/wbal.py` (modèle W′bal de R2), `physics.py`, `classic.py`, `segments.py`.

## 3. Prérequis

N9, R2, T2, T7 et T14 livrés. O7 pour l'argument `bots` de `start` (en cours de fusion le 27 octobre) : sans lui, seule l'option de ligne de commande est faite, et l'argument de `start` suit O7.

## 4. Travail demandé

- **Nouvelle classe `ProfileBot`** dans `bots.py`, même modèle physique que `ConstantPowerBot` (pente réelle, pas de braquet), mais puissance décidée à chaque pas par sa stratégie et limitée par sa réserve :
  - réserve W′bal calculée par `rogue/wbal.py` (`wbal_step`, sans bonus de cadence : `cadence_rpm` à 0), **un seul module pour le joueur et les bots** (plan §3.4) ;
  - au-dessus de la CP, la puissance demandée est ramenée à la CP quand la réserve est vide ;
  - `kind` reste `"constant"` dans la trame (le contrat 1.4 fixe `constant` ou `ghost`, et son exemple montre un bot à profil en `constant`), `to_dict()` ajoute `profile`, `cp_w`, `mass_kg` et `wbal_pct` (0 à 100) aux champs de N9.
- **Profils** (table de données dans `bots.py`, valeurs du 27 octobre, CP en W/kg) :

  | Profil (`profile`) | Nom affiché | Masse | CP | W′ | Pic |
  | --- | --- | --- | --- | --- | --- |
  | `climber` | Grimpeur | 60 kg | 4,0 W/kg | 15 kJ | — |
  | `rouleur` | Rouleur | 72 kg | 3,6 W/kg | 20 kJ | — |
  | `sprinter` | Sprinteur | 80 kg | 3,3 W/kg | 25 kJ | 12 W/kg sur 10 s |
  | `diesel` | Diesel | 75 kg | 3,8 W/kg | 10 kJ | — |

  Ces CP sont les valeurs de référence d'un bot au niveau 100 % ; le lot T13 les met à l'échelle de ta FTP (le profil change l'endroit où le bot est fort, pas son niveau global). Masses proposées par ce cahier (le plan donne « ≈ 60 kg » et « ≈ 80 kg ») ; elles sont modifiables dans la table.
- **Stratégies** (règles simples tirées des segments de la couche et de la réserve restante, sans intelligence artificielle ; fractions dans la table, modifiables) :
  - **Grimpeur :** 0,92 × CP sur le plat et en descente ; 1,10 × CP dans une montée tant que la réserve dépasse 20 % ; CP ensuite.
  - **Rouleur :** 1,00 × CP sur le plat ; 0,95 × CP en montée ; jamais au-dessus de la CP.
  - **Sprinteur :** 0,90 × CP hors sprint ; dans les 200 derniers mètres d'un sprint, son pic (12 W/kg × masse) pendant au plus 10 s, tant que la réserve le permet ; 0,88 × CP en montée.
  - **Diesel :** 1,00 × CP partout, ne monte jamais au-dessus.
  - Montée et sprint : d'après les segments de la couche `segments` du parcours (ceux que chronomètre `classic.py`) ; parcours sans couche : la règle « plat » partout.
- **Création :**
  - ligne de commande `openride-core run --bot-profile climber` (répétable ; au plus 4 bots en tout avec `--bot`), noms « Grimpeur », « Rouleur », « Sprinteur », « Diesel » (suffixe « 2 » pour un deuxième du même profil) ;
  - argument `bots` de `start` (O7) : nouvel élément `{ "kind": "profile", "profile": "climber" }`, compté dans les 4 bots ; profil inconnu : `error` `bot_invalid` et rien ne démarre.
- **Classement et maillots :** les bots à profil sont chronométrés et classés comme les bots à puissance constante (`classic.py`), et marquent des points de maillot (T14). Ils ne prennent pas de bonus.
- **Contrat :** l'élément `{kind: "profile", profile}` de l'argument `bots` est un ajout compatible ; il entre dans la révision ouverte (1.5 au 27 octobre) avec une ligne dans l'historique de `ipc_v1.md` et le schéma de `start`. Les champs de la trame existent depuis la révision 1.4.

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/bots.py`, `__main__.py` (`--bot-profile`), `session.py` (création des bots au départ), `docs/contracts/ipc_v1.md` et le schéma de `start`, `README.md` et `CLAUDE.md` (option citée), `docs/SUIVI_AVANCEMENT.md`.
- **Nouveau :** `core/tests/test_profile_bots.py`.
- **Lecture seule :** `physics.py`, `rogue/wbal.py` (une fonction manquante se signale), l'engine.

## 6. Modifications de contrat autorisées

L'élément `{ "kind": "profile", "profile": … }` de l'argument `bots` de `start`, et lui seul.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Montée de 5 km à 7 % : à CP égale en W/kg, le grimpeur y gagne du temps sur le diesel ; sur 10 km de plat, le rouleur devance le grimpeur.
3. Sprint de 400 m : le sprinteur dépasse 10 W/kg dans les 200 derniers mètres, pendant au plus 10 s, puis repasse sous sa CP ; sa réserve W′ descend et remonte ensuite.
4. Réserve vide : aucune puissance au-dessus de la CP tant que la réserve n'est pas remontée au-dessus de 0.
5. W′bal du bot identique, pas à pas, à `wbal_step` appelé avec la même puissance (un seul modèle).
6. Trame avec 4 bots à profil : `profile`, `cp_w`, `mass_kg`, `wbal_pct` présents et validés par le schéma 1.4 ; taille sous 4 096 octets (`ipc_budget`).
7. `start` avec un profil inconnu : `bot_invalid`, séance non démarrée.
8. Coût : 4 bots à profil ajoutent moins de 0,3 ms au pas de physique p99.

## 8. Hors périmètre

- Mise à l'échelle sur ta FTP et niveaux 90, 100, 110 % (T13).
- Choix des profils au menu de l'engine (T13) et HUD des bots (T15).
- Aspiration entre bots, bonus des bots.

## 9. Livraison (28 octobre 2026)

- **`ProfileBot`** dans `core/src/openride_core/bots.py`, sous-classe de `ConstantPowerBot` : table `PROFILES` (`BotProfile` : masse, CP en W/kg, W′, pic, fractions de la stratégie), réserve `wbal_step` de `rogue/wbal.py` avec une cadence de 0, puissance ramenée à la CP quand la réserve est vide, pic du sprinteur de 10 s au plus par passage de sprint (sprint et tour). Masse physique : masse du profil plus celle du vélo de `config.toml` (8 kg par défaut hors séance). Paramètre `scale` (CP, W′ et pic) préparé pour T13.
- **`kind`** reste `constant` dans la trame : le contrat 1.4 fixe `constant` ou `ghost` et son exemple montre un bot à profil en `constant` ; le champ `profile` le distingue (l'engine de T15 le colore d'après ce champ).
- **Segments** : `attach_segments` donne aux bots à profil les segments de la couche au départ de la séance (`CoreSession._new_race`).
- **Création** : `openride-core run --bot-profile climber` (répétable, au plus 4 bots en tout avec `--bot`, « Grimpeur 2 » pour un deuxième), élément `{kind: "profile", profile}` de `start.bots` (`bots_from_menu`), `bot_invalid` pour un profil inconnu ; contrat : une ligne dans l'historique de la révision 1.5.
- **Tests** : `core/tests/test_profile_bots.py` (critères 2 à 8).

