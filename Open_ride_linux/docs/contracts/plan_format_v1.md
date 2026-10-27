# Format des plans d'entraînement, version 1 (lot O11)

Rédigé le 26 octobre 2026. Un plan est un fichier TOML `~/OpenRide/Plans/<id>.toml` ; `<id>` est
le nom du fichier sans extension (minuscules, chiffres, `-` et `_`). Lu par
`core/src/openride_core/plans.py` ; plans de référence dans `core/plans/`.

## 1. Contenu

```toml
[plan]
name = "Construire sa FTP en 6 semaines"   # obligatoire
description = "..."                         # facultatif
days_per_week = 3                           # obligatoire, 1 à 7 (indicatif)

[[week]]                                    # une table par semaine, dans l'ordre
focus = "Endurance"                         # facultatif
days = [
  { day = "mardi",  workout = "endurance_45" },
  { day = "jeudi",  workout = "sweet_spot_3x10" },
  { day = "samedi", workout = "ftp_test:ramp" },
]
```

- `workout` : identifiant d'un entraînement de la bibliothèque `~/OpenRide/Workouts/` (nom du
  fichier `.zwo`, `.erg` ou `.mrc` sans extension, mêmes règles que `--workout`), ou
  `ftp_test:ramp` / `ftp_test:20min` (tests de FTP du lot O10 ; refusés tant que ce lot manque).
- `day` : `lundi` à `dimanche` (plan au calendrier) ou `jour1` à `jour7` (plan sans calendrier) ;
  les deux formes ne se mélangent pas dans un plan ; un jour au plus une fois par semaine.

Un plan est **invalide** si une de ces règles n'est pas tenue ou si un entraînement cité est
absent ou invalide : il est listé avec son erreur et ne peut pas être démarré.

## 2. Dates

- Plan au calendrier : la semaine 1 est la semaine du lundi au dimanche qui contient la date de
  début ; les séances de la semaine 1 placées avant la date de début ne comptent pas.
- Plan sans calendrier : `jourN` de la semaine `s` tombe à la date de début + 7 × (s − 1) + (N − 1) jours.

## 3. Plan actif

`~/OpenRide/plan_state.toml`, écrit par `openride-core plan start ID [--date AAAA-MM-JJ]`,
effacé par `plan stop` :

```toml
[active]
plan = "ftp_6_semaines"
start = "2026-11-02"
```

## 4. Suivi

Une séance prévue est faite si une séance de l'historique (`openride-core history`) du même jour,
ou des 3 jours suivants (rattrapage), porte le même entraînement (`workout_id` de l'en-tête du
journal) et a duré au moins 80 % de la durée prévue. Pendant un plan actif, l'en-tête du journal
d'une séance qui réalise une séance prévue porte `plan` = `{"id", "week", "day"}` (champ facultatif
du journal, `core/src/openride_core/journal.py`).

## 5. Journal des changements

| Version | Date | Changement |
| --- | --- | --- |
| 1 | 26 octobre 2026 | Première version (lot O11) |
