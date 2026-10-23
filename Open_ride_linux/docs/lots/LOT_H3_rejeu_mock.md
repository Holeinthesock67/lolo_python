# Lot H3 – Rejeu d'une séance réelle dans le simulateur

## 1. Objectif

Permettre au `MockDriver` de rejouer une séance enregistrée (journal JSONL ou fichier FIT) : puissance, cadence et fréquence cardiaque suivent alors la vraie séance, seconde par seconde. On peut ainsi développer et déboguer avec des données réalistes, sans le vélo, comme le prévoit la SRS §12 (« rejeu d'un FIT ou d'un journal »).

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/SRS_v1.1.md` §9 (journal, FIT) et §12 (mode mock).
3. Code :
   - `core/src/openride_core/mock_driver.py` (`MockDriver`, `TrainerMetrics`) ;
   - `journal.py` (`read_journal`, champs de `Record`) ;
   - `fit_export.py` (`iter_records`, qui relit un FIT) ;
   - `config.py` (section `[drivers]`) et `session.py` (`build_driver`) ;
   - `__main__.py` (options de `run`).

## 3. Prérequis

Aucun. Partir de `main` à jour.

## 4. Travail demandé

### 4.1 Source de rejeu : `core/src/openride_core/replay.py` (nouveau)

```python
@dataclass(frozen=True)
class ReplaySample:
    t: float                 # secondes depuis le début du rejeu
    power_w: float
    cadence_rpm: float
    hr_bpm: int | None

def load_replay(path: Path) -> list[ReplaySample]: ...   # .jsonl ou .fit, d'après l'extension
```

- **JSONL :** lignes `kind == "record"` de `read_journal` ; `t` est le champ `t` ramené à 0 au premier enregistrement.
- **FIT :** messages `record` de `iter_records` ; `t` est tiré de `timestamp`, ramené à 0.
- Champs absents ou `None` : puissance et cadence à 0, FC à `None`.
- Fichier illisible, vide ou d'extension inconnue : `ReplayError` avec un message lisible.

### 4.2 `MockDriver`

- Nouveau paramètre facultatif `replay: list[ReplaySample] | None`.
- En mode SIM, `poll(t_session)` renvoie l'échantillon interpolé linéairement à `t_session` (puissance, cadence) ; FC prise à l'échantillon précédent.
- Au-delà du dernier échantillon : le rejeu recommence au début (`loop`), pour les longues sessions de développement.
- En mode ERG, le comportement actuel est conservé : la puissance suit la cible.
- Sans `replay`, le comportement est strictement inchangé (tous les tests existants passent).

### 4.3 Configuration et ligne de commande

- `config.toml`, section `[drivers]` : clé `mock_replay = ""` (chemin, vide par défaut), ajoutée à la dataclass correspondante de `config.py`.
- `openride-core run --replay CHEMIN` : force `trainer = "mock"` et renseigne `mock_replay`.
- `build_driver` (dans `session.py`) charge le rejeu quand `mock_replay` est renseigné ; une `ReplayError` est journalisée en ERROR et le core démarre avec le simulateur ordinaire (ne pas planter).

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/replay.py`, `core/tests/test_replay.py`.
- **Modifiés :** `mock_driver.py`, `config.py`, `session.py` (`build_driver` seulement), `__main__.py`, `README.md` (une ligne de commande), `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune. La clé `mock_replay` étend `config.toml` (SRS §11) : l'ajouter à l'exemple de la SRS, avec un commentaire.

## 7. Critères d'acceptation

1. `cd core && pytest -q` passe en entier.
2. Un journal synthétique de 120 s (puissance 100 → 300 W en rampe) est rejoué : à `t = 60,5 s`, la puissance vaut la valeur interpolée à 1 W près.
3. Le même contenu écrit en FIT par `write_fit` puis rejoué donne les mêmes puissances (à 1 W près) que le JSONL.
4. Après le dernier échantillon, le rejeu reprend au début.
5. En ERG, la puissance suit la cible, même avec un rejeu chargé.
6. Une séance `CoreSession` de 60 s en temps accéléré avec rejeu produit un journal dont les puissances suivent le fichier rejoué.
7. `openride-core run --replay inexistant.jsonl` journalise l'erreur et ne plante pas (test avec `CoreSession` et un faux chemin, sans lancer la boucle complète).

## 8. Hors périmètre

- Rejeu de la position ou de la pente (le parcours reste celui de la séance).
- Commande de vitesse de rejeu (accéléré, ralenti).


## 9. Livraison (23 octobre 2026)

Branche `lot-h3-rejeu-mock` (PR #13), fusionnée dans `main`. Les 7 critères d'acceptation du §7 sont tenus (8 tests dans `core/tests/test_replay.py`) :
- `replay.py` charge `.jsonl` et `.fit`, ramène `t` à 0 s, remplace puissance/cadence absentes par `0.0` et FC absente/0 par `None`, et lève `ReplayError` sur fichier introuvable, vide, illisible ou d'extension inconnue.
- `MockDriver` interpole linéairement puissance et cadence en SIM, conserve la FC de l'échantillon précédent, reboucle au-delà de la durée du rejeu et garde le comportement ERG inchangé.
- Clé `mock_replay = ""` dans `DriversConfig` (`config.py` et exemple de `docs/SRS_v1.1.md` §11), option `openride-core run --replay CHEMIN`, repli sans plantage dans `build_driver`.
- Aucun écart.
