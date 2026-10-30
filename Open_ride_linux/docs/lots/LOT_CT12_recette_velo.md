# Lot CT12 – Recette de la Course tactique sur le vélo

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`.

## 1. Objectif

Vérifier sur le HomeTrainer et le Click que le mode est jouable, sûr et amusant.

## 2. À lire

1. `docs/5.0/PLAN_SERIE_CT.md` (décisions du propriétaire du 29 octobre), `docs/SPECIFICATION_GENERALE.md` §6.1 et §7.1, `docs/contracts/ipc_v1.md`.
2. `docs/PROTOCOLE_TEST_2026-10-26.md` (format des recettes), plan `docs/5.0/PLAN_SERIE_CT.md` §5 (sécurité).

## 3. Prérequis

CT2 à CT11 livrés.

## 4. Travail demandé

Étapes de 10 min au plus, chacune avec son relevé :
1. W′ et Burnout : vider sa réserve, sentir que le trainer ne change pas, voir le Burnout.
2. Catapulte : charger dans la roue d'un rouleur, déclencher en intensité normale.
3. Parade : décrocher un bot qui charge dans la roue.
4. Virages et Apex sur un circuit en descente.
5. Variantes : prendre A puis B, regarder le groupe.
6. Coupures : vérifier qu'une coupure du trainer ne déclenche rien.
Avis du propriétaire sur la difficulté, les effets et le confort ; mesures en `low`, `medium` et `high` séquencées par la file des mesures du PC.

## 5. Fichiers concernés

- **Nouveaux :** `docs/RECETTE_CT12.md`.
- **Modifiés :** ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Les six étapes faites, relevés écrits dans `RECETTE_CT12.md`.
2. Aucun à-coup de résistance attribué au mode ; aucune fausse détection après une coupure.

## 8. Hors périmètre

Équilibrage fin (nouvelle version de `balance.toml` si besoin).
