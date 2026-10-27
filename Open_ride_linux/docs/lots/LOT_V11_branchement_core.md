# Lot V11 – Core : progression branchée dans la séance et commandes du Garage

## 1. Objectif

Le plan V ne prévoyait aucun lot pour brancher les modules purs (V2, V3, V3b, V4) dans la séance et répondre aux messages du contrat V1. Ce lot le fait : équipement appliqué à la vitesse virtuelle, équipement noté au journal, `progression` dans `hello_ack`, bilan `xp_result` en fin de séance, commandes `list_garage`, `equip`, `buy` et `set_avatar`.

## 2. À lire

1. `LOT_V1_contrat_progression.md` et le contrat livré (`docs/contracts/ipc_v1.md`, révision de V1).
2. Code : `session.py`, `ipc_server.py`, `ipc_lists.py` (réponses en parties), `journal.py`, `recorder.py`, `progression.py`, `equipment.py`, `coins.py`, `profile.py`.

## 3. Prérequis

V1 validé par le propriétaire ; V2, V3, V3b et V4 fusionnés ; de préférence après P2 (le vent utilise le CdA courant).

## 4. Travail demandé

- **Démarrage :** profil chargé, progression recalculée hors de la boucle à 50 Hz (fil séparé ou au lancement, moins de 2 s pour 500 séances ; un cache `~/.cache/openride/progression.json` indexé par nom, taille et date des journaux est permis) ; `hello_ack.config.progression` rempli.
- **Physique :** `PhysicsParams` de la séance = `apply_equipment(PhysicsParams.from_config(cfg), equipped, catalogue)` en SIM et en ERG ; résistance au trainer inchangée (la pente envoyée ne dépend pas de l'équipement, sauf le supplément de vent et d'aspiration de la série P, qui suit le CdA courant comme prévu par le plan).
- **Journal :** l'en-tête gagne `loadout` (identifiants du cadre et des roues, et leurs deltas de masse et de CdA) et `ftp_w` (FTP de la séance, pour que les pièces gagnées à l'effort ne changent pas quand la FTP change, V-Q10) ; ajouts compatibles.
- **Fin de séance :** à `FINISHED`, calcul des gains de la séance (V2, V3b), du temps gagné par l'équipement (V3), des déblocages et des défis, puis envoi de `xp_result` selon le contrat. La séance enregistrée est ajoutée au cache.
- **Commandes :** `list_garage` (réponse `garage` en parties, comme `routes`), `equip`, `buy`, `set_avatar` hors séance seulement (`busy` sinon), profil écrit par `save_profile`, puis message `progression`. Refus avec les codes du contrat.
- **Liste des parcours :** champ `terrain` de chaque élément de `routes` (`route_terrain` de V3 sur la longueur et le dénivelé du parcours).
- **Options :** `[progression] enabled = true` dans `config.toml` ; à `false`, aucun effet d'équipement et pas de `progression` (tout se coupe).

## 5. Fichiers concernés

`session.py`, `ipc_server.py`, `ipc_lists.py`, `journal.py`, `recorder.py`, `config.py`, leurs tests, `fake_core.py` de l'engine (messages de démonstration), `README.md`, `docs/SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Aucune au-delà de V1. Journal : champs facultatifs `loadout` et `ftp_w` de l'en-tête.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/` ; trames validées par les schémas de V1.
2. Séance simulée de 10 min sur le plat à 250 W avec Contre-la-montre + Lenticulaire : vitesse virtuelle plus haute qu'avec l'équipement de départ, pente envoyée au trainer identique à chaque pas.
3. `buy` puis `equip` hors séance : profil écrit, message `progression` reçu avec le nouveau solde ; pendant `RUNNING` : `busy`.
4. Séance de 6 min : `xp_result` reçu avec `eligible` vrai ; de 4 min : `eligible` faux, `reason` `too_short`.
5. `[progression] enabled = false` : trames et physique identiques à aujourd'hui.

## 8. Hors périmètre

Événements des séries T et R (V5), affichage (V6 à V9).
