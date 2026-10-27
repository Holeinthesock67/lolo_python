# Lot P3 – Aspiration derrière les bots

## 1. Objectif

Rouler dans la roue d'un bot doit soulager, comme dehors. La SRS §5 prévoit un coefficient d'aspiration `alpha_draft` de 0 à 0,45 selon la distance derrière un bot, et `physics.py` l'accepte déjà, mais personne ne le calcule. Ce lot le calcule à partir des bots de N9, l'applique à la vitesse virtuelle et à la résistance ressentie en SIM (même voie que le vent de P2), et le publie dans `draft` (contrat v1.3 du lot P1).

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_P1_contrat_vent_decor.md` §4.2, `docs/lots/LOT_P2_vent_physique_core.md`, `docs/lots/LOT_N9_bots_core.md`.
2. `docs/SRS_v1.1.md` §5.
3. Code : `core/src/openride_core/bots.py` (N9), `core/src/openride_core/wind.py` (P2), `core/src/openride_core/physics.py`, `core/src/openride_core/session.py`.

## 3. Prérequis

P2 et N9 livrés. Version 1.0 publiée.

## 4. Travail demandé

Compromis réalisme et performance demandé par le propriétaire (25 octobre) : le calcul reste en une dimension (position `s` le long de la route, quelques bots), donc coûte moins de 0,02 ms par pas de 50 Hz, mais la courbe et les effets de groupe suivent les mesures publiées en soufflerie et en simulation numérique (Blocken et coll., 2013 à 2018) plutôt qu'une simple droite.

- Nouveau module pur `draft.py` :
  - `draft_coefficient(gap_m) -> float` : courbe exponentielle `α = α_max × exp(−(gap − gap_min) / L)` à partir de `gap_min` = 0,3 m (roue dans la roue), avec `α_max` = 0,40 et `L` = 4 m, coupée à 0 au-delà de 15 m et devant le bot ; on garde un abri résiduel de quelques pour cent jusqu'à 10 m, comme dans les mesures, au lieu d'un arrêt net ; constantes en tête du module, citées dans la SRS §5 (qui fixe le plafond de 0,45) ;
  - **effet de file :** derrière plusieurs bots en file (écart de moins de 3 m entre eux), l'abri grandit avec le rang : × 1,00 derrière un bot, × 1,12 derrière deux, × 1,18 derrière trois ou plus, plafonné à 0,45 ;
  - **poussée vers l'avant :** un bot suivi de près par le cycliste (moins de 1 m) gagne 2 à 3 % de résistance aérodynamique en moins (constante `PUSH_FROM_BEHIND`), ce qui rend les relais crédibles ; facultatif, désactivable ;
  - **vent de travers :** l'abri baisse avec l'angle du vent apparent (P2), jusqu'à − 50 % à 45° de travers, faute de pouvoir se placer en éventail sur une route à une dimension ; vent nul ou de face : aucun effet ;
  - `best_draft(rider_s, bots, route, wind) -> (alpha, bot_id)` : le bot (ou la file) qui abrite le plus, devant le cycliste sur le parcours (boucles et aller-retour comme `route.py`) ;
  - le fantôme n'abrite pas (décision du propriétaire du 25 octobre) : seuls les bots à puissance constante comptent.
- Vent : l'abri multiplie le terme aérodynamique complet `(1 − α)`, vent compris (SRS §5) ; l'abri compte donc davantage à grande vitesse et presque plus en côte raide, sans règle particulière.
- Ressenti en SIM : même calcul que P2 (`ΔF` total vent et aspiration, borné, avec les `PhysicsParams` courants à chaque pas), pas de deuxième voie.
- Lissage : `alpha` suit sa cible avec une constante de temps de 1 s, pour éviter un à-coup de résistance en entrant ou en sortant de la roue.
- Trame `state` : `draft` et `draft_bot` quand il y a au moins un bot.
- Journal : `draft` en champ facultatif à 1 Hz ; bilan (`summary`) : temps passé à l'abri (`draft_time_s`), facultatif.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/draft.py`, `core/tests/test_draft.py`.
- **Modifiés :** `core/src/openride_core/session.py`, `core/src/openride_core/recorder.py`, `core/src/openride_core/tools/session_summary.py`, `docs/SRS_v1.1.md` (§5, courbe), `CLAUDE.md` (module), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** l'engine, `bots.py` (sauf accès en lecture déjà public), le contrat.

## 6. Modifications de contrat autorisées

Aucune (P1).

## 7. Critères d'acceptation

1. `(cd core && pytest -q)` passe en entier.
2. `draft_coefficient` : environ 0,38 à 0,5 m, environ 0,13 à 5 m, entre 0,02 et 0,05 à 10 m, 0 au-delà de 15 m et devant le bot ; décroissance strictement monotone.
3. File de trois bots serrés : abri plus grand que derrière un seul, jamais au-dessus de 0,45. Vent de travers à 45° : abri réduit de moitié ; vent de face : inchangé.
4. Coût : `best_draft` avec 5 bots sous 0,02 ms par appel (mesure sur 50 000 appels dans le test).
5. Bot à 250 W, cycliste à 250 W collé dans sa roue : vitesse d'équilibre plus haute que seul ; à 200 W derrière lui, il ne se fait pas distancer sur le plat (séance simulée de 10 min, `MockDriver`).
6. Sans bot : `draft` absent, comportement identique à P2.
7. Sortie de la roue : `alpha` passe de 0,40 à 0 en 3 s au plus, sans saut de plus de 0,05 par pas de 50 Hz.
8. Boucle : bot à s = 50 m, cycliste à s = longueur − 2 m : abri trouvé.
9. ERG : aucune incidence sur la commande au trainer.

**Sur le vélo (le propriétaire) :** se placer derrière un bot à 220 W : soulagement perceptible et progressif en SIM.

## 8. Hors périmètre

- Indicateur « Abri » à l'écran (modèle dans P4, affichage dans P17).
- Aspiration entre bots, placement latéral (éventail), bots qui réagissent au cycliste ou prennent des relais.
