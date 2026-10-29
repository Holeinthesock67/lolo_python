# Lot WTF1 – Règles du mode WTF dans le core

Série WTF (mode « What the fuck », demande du propriétaire du 29 octobre 2026). Plan de la série : `docs/2.0/PLAN_SERIE_WTF.md`.

## 1. Objectif

Écrire en modules purs (aucune entrée-sortie dans la boucle) les treize règles du mode, chacune désactivable, et le chef d'orchestre qui les tire et combine leurs effets sous des bornes sûres.

## 2. À lire

`docs/2.0/PLAN_SERIE_WTF.md` §2 à §5 ; `core/src/openride_core/powerups.py` (module pur de même forme) ; `core/src/openride_core/physics.py`.

## 3. Travail demandé

- `core/src/openride_core/wtf/rules.py` : catalogue, fichier `~/OpenRide/wtf.toml` lu et écrit (remplacement atomique), erreurs lisibles.
- `core/src/openride_core/wtf/events.py` : gravité, monde à l'envers, route qui s'effondre, fromage, tempête, micro-défis, œufs, vélo minuscule, caméras.
- `core/src/openride_core/wtf/chef.py` : surprise du chef (phases, refus par Z court, chef vexé, cinq plats).
- `core/src/openride_core/wtf/mode.py` : `WtfMode` (tirage, règles permanentes, effets combinés, bornes, trame, journal, bilan).

## 4. Critères d'acceptation

1. Chaque règle a ses tests, positifs et négatifs ; toutes les règles coupées donnent une séance ordinaire.
2. Deux heures de séance aléatoire, toutes règles actives : supplément ressenti dans ± 3 points, pente envoyée entre − 6 % et + 10 %, trame `wtf` sous 1 200 octets.
3. Même graine, même séance.

## 5. Livraison

Livré le 29 octobre 2026 (branche `claude/project-thread-i6o5pd`) : paquet `wtf/` et `core/tests/test_wtf.py` (33 tests). Rien n'est encore branché sur la séance (lot WTF2).
