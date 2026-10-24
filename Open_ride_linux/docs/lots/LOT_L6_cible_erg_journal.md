# Lot L6 – Cible ERG dans le journal de séance

## 1. Objectif

Le bilan `openride-core summary` (lot K7) sait calculer l'écart entre puissance et cible par bloc ERG, mais le journal v1 n'enregistre pas la cible : l'écart est signalé « indisponible ». Ce lot ajoute la cible au journal, pour que le bilan d'une séance ERG soit complet, et pour préparer le futur fantôme d'une séance (SRS §14).

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_F_erg_zwo.md` (livraison : lissage de la cible sur 2 s, biais ± 2 %, pause ERG), `docs/lots/LOT_K7_bilan_seance.md`.
2. `docs/SRS_v1.1.md` §6 (ERG) et §9 (journal continu : liste des champs).
3. Code : `core/src/openride_core/journal.py` (`Record`), `core/src/openride_core/session.py` (écriture de `Record` à 1 Hz, cible ERG envoyée), `core/src/openride_core/recorder.py`, `core/src/openride_core/fit_export.py` (lecture du journal), `core/src/openride_core/tools/session_summary.py` (lecture de `target_w`), `core/src/openride_core/replay.py`.
4. Tests : `core/tests/test_journal_fit.py`, `test_session_summary.py`, `test_drivers_session.py`, `test_replay.py`.

## 3. Prérequis

Aucun. Partir de `main` à jour.

## 4. Travail demandé

- `Record` gagne `target_w: float | None = None` : la cible ERG **réellement envoyée** au trainer à cet instant (après lissage et biais), arrondie au watt ; `None` en SIM et en pause ERG.
- `session.py` remplit ce champ ; rien d'autre ne change dans la boucle (aucune entrée-sortie ajoutée).
- **Compatibilité :** un journal v1 sans `target_w` se relit comme avant (`recover`, `summary`, `replay`, `log_report`) ; un lecteur ignore toujours les champs inconnus.
- `summary` affiche alors, par bloc, la cible moyenne et l'écart (déjà prévu par K7 : vérifier, compléter si besoin, sans changer les clés JSON).
- Le FIT est inchangé (aucun champ standard de `record` ne porte la cible) ; le rapport le rappelle.

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/journal.py`, `core/src/openride_core/session.py`, `core/src/openride_core/tools/session_summary.py` (si besoin), tests correspondants, `docs/SRS_v1.1.md` §9 (liste des champs), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `fit_export.py` (lecture seule), contrat IPC.

## 6. Modifications de contrat autorisées

`docs/SRS_v1.1.md` §9 : ajouter « cible ERG » à la liste des champs du journal, en précisant qu'elle est absente des journaux antérieurs au 24 octobre 2026.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Séance simulée de 2 min (`MockDriver`, temps accéléré, un `.zwo` de deux blocs à 150 et 250 W) : chaque ligne `record` en ERG a `target_w` ; en SIM ou en pause, `target_w` est `null` ; les valeurs tendent vers 150 puis 250 W (lissage sur 2 s compris).
3. `summary --json` sur ce journal : `erg.target_available` vaut `true`, cible moyenne de chaque bloc à ± 5 W de la consigne du `.zwo`.
4. Un journal v1 enregistré avant ce lot (fichier de test existant) donne exactement le même bilan qu'avant.
5. `recover` produit un FIT identique à celui d'avant le lot pour un même journal (hors horodatage de création).

## 8. Hors périmètre

- Champs de développeur FIT ou message `workout` dans le FIT.
- Affichage de la cible dans l'engine (F2).

## 9. Livraison (24 octobre 2026, PR #69)

- `core/src/openride_core/journal.py` et `session.py` : champ `Record.target_w` écrit à 1 Hz en mode ERG actif (`None` en SIM/FreeRide/pause).
- `core/src/openride_core/tools/session_summary.py` : moyenne de cible et écart signé par bloc ERG (`openride-core summary`).
- Tests de non-régression et rétrocompatibilité des anciens journaux validés.
- Intégration continue GitHub Actions verte.
