# Lot X56 – FIT prêt pour Garmin Connect et GoldenCheetah (import et export)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : FIT de séance avec les totaux affichés par Garmin Connect et GoldenCheetah, contrôle de compatibilité dans `fit-check`, import de FIT façon Garmin verrouillé par des tests (3.0, recette 1.0 ligne 21) | Python | H5, X11, M7 | Petite | **Livré le 7 novembre** (PR #745, branche `claude/project-thread-lveqg5`) ; protocole F1 validé par le propriétaire le 7 novembre |

## 1. Objectif

Ligne 21 de la recette 1.0, reportée en 3.0 le 1er novembre : un FIT de séance OpenRide s'importe sans erreur dans Garmin Connect et dans GoldenCheetah, et une sortie Garmin se compile en parcours. L'essai réel reste au propriétaire (5 min, ses fichiers ne quittent pas le PC) ; ce lot fait en cloud, avec des FIT fabriqués, tout ce qui peut faire échouer cet essai.

## 2. Constat (7 novembre)

- **Export** : le FIT d'OpenRide passe le SDK officiel de Garmin (lot H5) et `fit-check` (X11), mais la séance n'avait ni calories, ni travail, ni D+, ni puissance normalisée, ni cadence maximale ; Garmin Connect et GoldenCheetah affichent ces champs tels qu'ils sont dans `session` et `lap`, sans les recalculer, d'où des « 0 kcal » et un D+ vide. Avec des tours (Cyber-Rogue), les tours n'avaient ni FC ni cadence. `device_info` portait une version 0.1 sans nom d'appareil.
- **Lecteur de GoldenCheetah** (`src/FileIO/FitRideFile.cpp`, lu le 7 novembre) : en-tête de 12 ou 14 octets seulement, signature `.FIT` obligatoire, tour ou séance ignoré quand il finit avant le premier enregistrement, sport et sous-sport repris de `session`, positions absentes acceptées (séance sans GPS). Aucune de ces règles n'était contrôlée.
- **Import** (compilateur, lot M7) : `fit-tool` lisait déjà les variantes des montres Garmin, mais rien ne le verrouillait. Le SDK de Garmin en Python, lui, refuse les en-têtes à temps compressé : il sert au contrôle des FIT d'OpenRide, pas à l'import des sorties.

## 3. Travail fait

- **`fit_export.py`** : une seule fonction de totaux (`totals`) pour chaque tour et pour la séance : distance, vitesse maximale, puissance moyenne et maximale, **travail** (somme des puissances à 1 Hz, en J), **calories** (1 kJ ≈ 1 kcal au vélo, règle usuelle), **puissance normalisée** (moyenne glissante sur 30 s, à partir de 30 s de relevés), FC et **cadence** moyennes et maximales, **D+ et D-** (hystérésis de 1 m). `device_info` : appareil créateur, nom « OpenRide », version du jeu (`VERSION`, majeur.mineur). Le fabricant reste `development` : OpenRide ne se fait pas passer pour un appareil Garmin.
- **`fit-check`** : deux contrôles de plus. « Compatibilité Garmin Connect et GoldenCheetah » (ÉCHEC) : en-tête, `file_id` d'activité daté avec fabricant et produit, séance de vélo qui couvre les relevés, tours et séances datés, dans l'ordre et au nombre annoncé, heure locale de `activity`, positions dans le globe. « Totaux affichés » (ATTENTION) : calories, travail, cadence maximale, D+ et D- absents (cas des FIT d'avant ce lot).
- **Tests** (cloud, sans PC ni vélo) :
  - `core/tests/test_fit_garmin_gc.py` : totaux de la séance lus par le SDK Garmin, tours complets dont la somme fait la séance, séance sans FC ni GPS, NP et D+, sept défauts fabriqués refusés par le contrôle, en-têtes refusés par GoldenCheetah, avertissement pour un FIT d'avant la 3.0 ;
  - `compiler/tests/test_fit_garmin_like.py` : FIT écrits octet par octet comme ceux des montres (temps compressé, grand-boutiste, champs développeur, messages inconnus ou du fabricant, en-tête de 12 octets, positions invalides en tête, fichiers chaînés, CRC faux) : même trace que le fichier simple ; aller-retour d'une séance OpenRide recompilée en parcours.

## 4. Critères d'acceptation

1. Les tests ci-dessus passent en cloud (Python 3.14 en CI).
2. Aucun fichier d'activité réel dans le dépôt, aucune position proche du domicile (scanner X23).
3. Recette du propriétaire (protocole F1) : `fit-check` sans ÉCHEC sur le FIT d'une vraie séance enregistrée après la fusion, puis import sans erreur dans Garmin Connect et GoldenCheetah, calories, D+ et puissance normalisée affichés.

## 5. Livraison

Livré le 7 novembre : PR #745 fusionnée (critères 1 et 2), puis protocole F1 validé par le propriétaire le même jour (critère 3) sur le FIT d'une séance gravel de la démo des biomes enregistrée après la fusion :

- `fit-check` : tous les contrôles OK, y compris « compatibilité Garmin Connect et GoldenCheetah » et « totaux affichés » ;
- Garmin Connect : import sans erreur ; calories, travail, puissance normalisée (147 W, la même que dans le jeu), D+ et cadence maximale affichés ;
- GoldenCheetah : import sans erreur ; travail (90 kJ), D+ (42 m) et puissances cohérents.

Le fichier reste sur le PC du propriétaire, hors du dépôt. Ligne 21 de la recette 1.0 faite (cahier O8 §4).

## 6. Hors périmètre

- Training Effect et statut d'entraînement de Garmin Connect : Garmin ne les calcule que pour ses propres appareils ; se faire passer pour l'un d'eux est exclu.
- Envoi automatique vers Garmin Connect (aucun envoi en ligne, SRS §9).
- Import d'un FIT dans l'historique d'OpenRide (lot O28, 2.0).
