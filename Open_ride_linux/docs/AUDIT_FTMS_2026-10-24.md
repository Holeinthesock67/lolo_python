# Audit FTMS du 24 octobre 2026

Comparaison du code BLE du core (`core/src/openride_core/ftms.py`, `ftms_driver.py`) à la spécification Bluetooth SIG Fitness Machine Service v1.0 (2017) et aux définitions des caractéristiques du GATT Specification Supplement (dépôt public du Bluetooth SIG). Tests : `core/tests/test_ftms_spec.py`.

Les formats binaires (UUID, drapeaux, opcodes, unités, résolutions, codes de résultat) étaient déjà conformes. Écarts trouvés, tous corrigés :

| # | Gravité | Article | Écart | Correction |
| --- | --- | --- | --- | --- |
| 1 | Élevée | §4.16.3, §4.16.4 | Commandes du Control Point enchaînées sans attendre la réponse 0x80 (risque d'erreur ATT 0xFE). | `ControlPoint.call` attend l'indication (1 s au plus). |
| 2 | Élevée | §4.16.3 | `release-trainer` écrit sans s'abonner aux indications (refus ATT 0xFD attendu). | Abonnement avant la première écriture. |
| 3 | Moyenne | §4.17 | Fitness Machine Status (0x2ADA) non écouté ; perte de contrôle (0xFF) vue en retard. | Abonnement ; 0xFF et Reset par un tiers : reprise du contrôle. |
| 4 | Moyenne | Supplément, Indoor Bike Data | Niveau de résistance sur 2 octets (XML d'origine) contre 1 octet (supplément actuel). | Taille déduite de la longueur de la trame. |
| 5 | Moyenne | §4.3, tableau 4.15 | ERG ou SIM envoyés même si Fitness Machine Feature ne les annonce pas. | Consigne non envoyée, avertissement au journal. |
| 6 | Faible | §4.14 | Pas minimal de puissance ignoré. | Consigne ERG arrondie au pas. |
| 7 | Faible | §4.9.1.10 | Énergie 0xFFFF (« Data Not Available ») prise pour une valeur. | Lue comme absente. |
| 8 | Faible | §4.19 | Trame partielle (« More Data ») effaçant la cardio du trainer. | Dernière valeur gardée. |
| 9 | Faible | §4.16 | Trainer sans Control Point : connexion en échec en boucle. | Mode mesures seules. |
| 10 | Faible | Tableaux 4.15, 4.20 | Valeur hors sint16 : exception à l'encodage. | Saturation. |

Non corrigé : chiffrement du Control Point laissé à BlueZ (appairer avec `bluetoothctl pair` si un trainer refuse les commandes) ; recherche du trainer par nom plutôt que par le service 0x1826 ; mode ERG ou SIM non annoncé signalé au journal seulement.

À faire sur le HomeTrainer : une séance avec un passage ERG puis SIM, puis `openride-core release-trainer`, sans ligne « Pas de réponse du Control Point » ni « refusée » dans `~/run_trainer.log`.
