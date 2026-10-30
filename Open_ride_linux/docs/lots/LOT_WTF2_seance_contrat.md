# Lot WTF2 – Mode WTF branché dans la séance et contrat IPC

Série WTF (mode « What the fuck », demande du propriétaire du 29 octobre 2026). Plan de la série : `docs/2.0/PLAN_SERIE_WTF.md`.

## 1. Objectif

Lancer une séance en mode WTF depuis l'engine, appliquer les effets de `WtfMode` à la physique, à la pente envoyée et aux bots, et publier le champ `wtf`.

## 2. À lire

`docs/2.0/PLAN_SERIE_WTF.md` ; `core/src/openride_core/session.py` (`_step`, `_new_race`, `_handle_input`) ; `docs/contracts/ipc_v1.md` (révision 1.5).

## 3. Travail demandé

- Contrat, ajouts compatibles de la révision 1.5 (ligne au journal du contrat) : argument `mode: "wtf"` de `start` ; valeur `"wtf"` de `hello_ack.config.modes` ; objet facultatif `wtf` dans `state` (forme du plan §5) ; commandes `list_wtf_rules` et `set_wtf_rule` (`id`, `on`), message `wtf_rules` ; `summary.wtf` ; code `wtf_rule_invalid` ; schémas JSON.
- Séance : `WtfMode` créé au départ (FTP, paramètres physiques, graine), pas en `RUNNING` seulement ; pente du parcours et pente anticipée transformées ; supplément borné ajouté comme celui du vent ; `clamp_feel` avant la limitation de variation ; `physics_params` et `power` pour la physique ; puissance des bots × `bot_power_factor` ; abri × `draft` ; Z court relayé à `press` ; lignes `wtf` au journal ; mode refusé en ERG (`bad_args`) ; bonus et records coupés.
- Journal : en-tête de séance `mode = "wtf"` pour que l'historique et la reprise après plantage (N8) le reconnaissent.

## 4. Critères d'acceptation

1. Séance simulée de 30 min en mode WTF (`--trainer sim`) : pente envoyée toujours entre − 6 % et + 10 %, puissance du FIT identique à la puissance mesurée.
2. Chaque règle coupée par `set_wtf_rule` n'apparaît plus dans `wtf`.
3. Taille de la trame `state` avec quatre bots sous 4 096 octets.

## 5. Livraison

Livré le 29 octobre 2026 (branche `claude/project-thread-i6o5pd`, même PR que WTF1) :
- `start` avec `mode` = `wtf` crée `WtfMode` (règles de `wtf.toml`, costumes des bots) ; pas de segments, records ni bonus, bots calibrés comme en classique ;
- à chaque pas : pente du parcours et pente anticipée transformées, supplément ressenti borné ajouté après le vent et l'abri, pente bornée de − 6 % à + 10 % avant la limitation de variation ; masse, roulement et vent de la règle en cours ; puissance prise en compte × le facteur du plat (piment) ; mamies à l'attaque (`power_factor` des bots) ; abri derrière la baleine ;
- Z court relayé au chef ; `set_ride_mode` vers l'ERG refusé (`busy`) ; `wtf` dans `state`, `summary.wtf`, lignes `wtf_start`, `wtf` et `wtf_summary` au journal (pente du parcours gardée au journal) ;
- contrat 1.5 : `start.mode`, `modes` = `wtf`, `list_wtf_rules`, `set_wtf_rule`, `wtf_rules`, `wtf_rule_invalid`, schémas JSON ;
- `core/tests/test_wtf_session.py` (6 tests).

Limite connue : après un plantage du core, la reprise (N8) repart en séance ordinaire, sans les règles WTF.
