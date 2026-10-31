# Lot X48 – Blocs vélo encore ouverts : leur logique vérifiée sans vélo

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : blocs vélo encore ouverts (7q, 7ae, 7af, 7ac) vérifiés sans vélo : aucune consigne ERG sous 50 W, abri de 3 bots à 230–250 W, marque `recette_sans_velo` et séances du pré-vol | Python | X36, O19, AS1 | Petite | En PR (29 octobre) |

## 1. Objectif

Le propriétaire a fait cette demande le 29 octobre : « Pour tous les points ouverts, essaye de les couvrir par des tests automatisables. » Il a précisé ensuite : « Les tests de consigne et de résistance du home trainer sont à faire en manuel sur le vélo. »

La file des mesures du PC garde plusieurs blocs vélo : 7q (rafales de braquets, montre Garmin allumée), 7ae (ERG sans roue libre, lot O19), 7af (abri AS1 avec 3 bots) et 7ac (recette V10). Ce lot vérifie sans vélo tout ce que le core décide dans ces blocs. Il ne reste au vélo que le ressenti, la consigne et la résistance réelles du trainer.

## 2. Spécification

| # | Règle |
| --- | --- |
| X48-1 | `core/tests/test_recettes_velo_auto.py`, marque `recette_sans_velo`. Bloc 7ae : un entraînement bas (FTP 100 W, blocs de 10 à 40 %, FreeRide), avec le biais au minimum, une pause, une reprise, le bloc suivant et la fin, n'envoie au trainer aucune consigne sous 50 W. L'ERG libre à 50 W, avec le biais au minimum, et la cadence verrouillée, avec un cycliste qui cesse de pédaler 60 s, n'en envoient pas non plus. |
| X48-2 | Même fichier, bloc 7af : 3 bots à 230, 240 et 250 W et un cycliste à 240 W, départ groupé, 10 min sur le plat en temps accéléré. Chaque bot et le cycliste reçoivent l'abri (> 0,2). Le bot de 230 W du groupe finit plus loin qu'un bot de 230 W seul. L'abri reste sous le plafond de la SRS (0,45). |
| X48-3 | Les tests existants qui couvrent ces blocs prennent la marque `recette_sans_velo` : montre Garmin et rafale de braquets sur un Control Point occupé (7q), FreeRide à 50 W et ERG libre (7ae), abri derrière le cycliste (7af), recette V10 de bout en bout (7ac). |
| X48-4 | `scripts/pre_vol_seances.toml` ajoute les séances `garmin_braquets`, `erg_libre_50w`, `abri_as1` et `v10`, avec leurs tests Godot et leurs scénarios simulés. `test_pre_vol.py` vérifie que ces fichiers et ces scénarios existent. |

## 3. Reste au vélo

Consigne ERG et pente SIM réellement appliquées par le trainer, résistance ressentie, décrochages au-dessus de 450 W, pompage, montre Garmin réelle, densité des bots à juger, Garage au Click réel. Chaque bloc dure 10 min au plus et commence par `scripts/pre_vol.py --seance <bloc>`.

## 4. Critères d'acceptation

1. `pytest -m recette_sans_velo` passe, en moins d'une minute.
2. `scripts/pre_vol.py --liste` affiche les quatre nouvelles séances.
