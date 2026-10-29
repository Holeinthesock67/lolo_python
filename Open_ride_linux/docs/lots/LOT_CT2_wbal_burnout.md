# Lot CT2 – Réserve W′ du cycliste et Burnout symétrique

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`.

## 1. Objectif

Calculer la réserve W′ du cycliste pendant la séance avec le modèle de Skiba déjà utilisé par le Cyber-Rogue et les bots à profil, l'afficher en option dans le mode classique, et appliquer dans la Course tactique le Burnout décidé le 29 octobre : puissance prise en compte plafonnée à 70 % de la CP pendant 8 s quand la réserve tombe à 0, pour le cycliste comme pour les bots.

## 2. À lire

1. `docs/5.0/PLAN_SERIE_CT.md` (décisions du propriétaire du 29 octobre), `docs/SPECIFICATION_GENERALE.md` §6.1 et §7.1, `docs/contracts/ipc_v1.md`.
2. Cahiers `LOT_R2_wbal_postures.md`, `LOT_R16_estimation_cp_wprime.md`, `LOT_T12_bots_profil.md` ; code `rogue/wbal.py`, `tools/estimate_cp.py`, `bots.py` (`ProfileBot.step`), `session.py`, `classic.py`.

## 3. Prérequis

R2, R16 et T12 livrés ; CT1 fusionné.

## 4. Travail demandé

- Module pur `tactical/surchauffe.py` : `wbal_step` de `rogue/wbal.py` sans copie ; état Burnout (`burnout_s` qui décompte 8 s), plafond de la puissance prise en compte à `burnout_cap_pct` × CP (70 %, `balance.toml`).
- **Seuils** : ceux de Skiba (vidange au-dessus de la CP, recharge sous la CP), et non 105 % et 85 % de la FTP. CP et W′ : réglage `[rogue]` sinon estimation de R16.
- **Tolérance** : le Burnout ne se déclenche que si la réserve reste à 0 pendant 0,5 s (retard de la puissance mesurée).
- **Jamais sur la résistance** : la pente envoyée au trainer, ses rampes et ses bornes ne changent pas ; seule la vitesse virtuelle est bridée.
- **Bots** : `ProfileBot` reçoit la même règle dans le mode (aujourd'hui ramené à sa CP à réserve vide ; inchangé dans le classique).
- **Classique** : réglage `ride.show_wbal` (coupé par défaut) qui envoie `wbal_pct` du cycliste dans la trame ; aucun Burnout.
- **Coupures** : réserve figée pendant un segment suspendu (#542) ; la puissance à 0 d'une coupure ne recharge pas la réserve.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/tactical/surchauffe.py`, `core/tests/test_tactical_surchauffe.py`.
- **Modifiés :** `bots.py`, `session.py`, `classic.py`, `settings.py` (réglage), ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.
- **Interdits :** l'engine, `physics.py`.

## 6. Modifications de contrat autorisées

Aucune : les champs viennent du lot CT1. Le réglage `ride.show_wbal` passe par `settings` (révision 1.3).

## 7. Critères d'acceptation

1. `pytest -q` passe ; résultats identiques à `rogue/wbal.py` pour les mêmes entrées.
2. 30 s à 150 % de la CP avec W′ = 20 kJ et CP = 250 W : réserve vide vers 53 s, Burnout de 8 s, puissance prise en compte ≤ 175 W pendant ce temps.
3. Repasser sous la CP à 1 % de réserve : pas de Burnout.
4. La pente envoyée est la même avec et sans Burnout (test sur le pilote simulé).
5. Coupure simulée pendant 10 s : réserve inchangée.

## 8. Hors périmètre

Affichage (CT10, CT11) ; réaction des bots à la réserve des autres (CT3).
