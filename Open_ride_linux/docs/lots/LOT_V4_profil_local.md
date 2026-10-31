# Lot V4 – Profil local : choix, achats et avatar, lecture et écriture sûres, migration

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Profil local (`~/OpenRide/profile.json`) : choix, achats, avatar, écriture sûre, migration | Python | V2 | Petite | **Livré le 27 octobre** (PR #276, issue #240) ; branchement par V11 |

## 1. Objectif

Garder dans `~/OpenRide/profile.json` ce qui ne se recalcule pas depuis le journal : équipement choisi, achats, vies du mode Cyber-Rogue et réglages de l'avatar. L'expérience, le niveau, les défis et les pièces gagnées ne sont **pas** stockés comme vérité : ils se recalculent (V2, V3b). Le fichier s'écrit sans risque de corruption, se répare s'il est abîmé et porte un numéro de version pour les migrations.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_V.md` §2.3, §2.4 et §3 (risque 4).
2. Code : `core/src/openride_core/config.py` (`OPENRIDE_HOME`), `config_edit.py` (écriture sûre avec copie `.bak`, à imiter), `progression.py` (lot V2).
3. `LOT_T1_contrat_1_4.md` §4.4 (réglages de l'avatar et leurs bornes).

## 3. Prérequis

V2 fusionné (le profil vit à côté de son module ; aucune dépendance de calcul).

## 4. Travail demandé

### 4.1 Contenu (version 1)

```json
{
  "version": 1,
  "equipped": {"frame": "frame_allround", "wheels": "wheels_standard", "helmet": "...", "kit": "...", "socks": "...", "glasses": "..."},
  "purchases": [{"item_id": "frame_climber", "price": 150, "ts": 1761500000}],
  "lives": {"bought": 0, "used": 0, "spent": 0},
  "avatar": {"height": "M", "build": "medium", "skin": 2, "hair": 1, "hair_color": 3,
             "kit_primary": 4, "kit_secondary": 0, "number": 1}
}
```

Aucune donnée personnelle (pas de nom, de masse, de taille réelle) : le profil reste local et n'est jamais versionné ni copié dans les journaux.

### 4.2 Module `profile.py`

- `load_profile(path=PROFILE_PATH) -> Profile` : fichier absent → profil par défaut (rien n'est écrit tant qu'aucun choix n'est fait). Fichier illisible ou invalide → essai de `profile.json.bak`, sinon profil par défaut ; le fichier abîmé est gardé sous `profile.json.corrompu-AAAAMMJJ-HHMMSS` et un avertissement est journalisé.
- `save_profile(profile, path)` : fichier temporaire dans le même dossier, `fsync`, copie de l'ancien en `.bak`, puis `os.replace` (jamais de fichier à moitié écrit).
- **Migration :** sans `version` → version 1 (champs manquants complétés par défaut) ; version plus récente que celle du code → lecture seule (`ProfileTooNew` à l'écriture) pour ne pas effacer des données d'une version future.
- Choix : `equip(profile, slot, item_id, owned)` refuse une pièce non possédée (`owned` est fourni par l'appelant, V3/V3b) ou un emplacement inconnu ; `set_avatar(profile, avatar)` valide chaque champ contre les bornes du contrat (T1 §4.4) et refuse le tout au premier champ invalide.
- Achats : `record_purchase(profile, item_id, price, ts)` (refuse un achat en double) ; vies : `record_life_purchase(profile, price)` et `use_life(profile)` (refuse si aucune vie). Le contrôle du solde est fait par V3b.
- Équipement manquant au catalogue (pièce retirée d'une version à l'autre) : l'emplacement revient à la pièce par défaut au chargement, sans erreur.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/profile.py`, `core/tests/test_profile.py`.
- **Modifiés :** `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** `session.py`, l'IPC, l'engine.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Aller-retour écriture puis lecture identique ; profil absent → défauts, aucun fichier créé.
3. Fichier tronqué : lecture du `.bak` ; `.bak` absent aussi : défauts, fichier abîmé conservé sous son nouveau nom.
4. Écriture interrompue (exception simulée avant `os.replace`) : l'ancien fichier reste intact.
5. Profil sans `version` migré ; profil de version 2 lu mais non réécrit.
6. `equip` d'une pièce non possédée et `set_avatar` hors bornes refusés sans rien changer.

## 8. Hors périmètre

Calcul du solde (V3b), catalogue (V3), commandes du menu (T1, V11), affichage (V8).

## 9. Livraison (26 octobre 2026, issue #240)

- Code et tests : `profile.py`, `core/tests/test_profile.py` (20 tests).
- Identifiants par défaut de l'apparence (`helmet_route`, `kit_uni`, `socks_blanches`, `glasses_claires`) fixés ici ; le catalogue du lot V3 les reprend.
- `load_profile(path, known_items)` : le catalogue est passé par l'appelant (V3, V11) pour remettre à la pièce par défaut un emplacement dont la pièce a été retirée.
