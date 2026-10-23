# Lot F – Entraînements ERG : lecteur `.zwo` et pilotage ERG dans le core

## 1. Objectif

Permettre de suivre un entraînement structuré au format `.zwo` (format ouvert de Zwift) :
- le core calcule la puissance cible bloc par bloc et la transmet au trainer en mode ERG ;
- le paysage continue de défiler.

Ce lot couvre la partie core du sprint 4 de la SRS. Les bips d'annonce et le bandeau d'entraînement à l'écran sont pour l'engine, plus tard.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/SRS_v1.1.md` :
   - §6 : ERG et `.zwo`, en entier ;
   - §4.1 : mode ERG du pilote ;
   - §4.4 : actions du Click en ERG ;
   - §9 : champs `mode` et `block` du journal.
3. `docs/contracts/ipc_v1.md` §3 (objet `erg`), §4 (`select_workout`, `skip_block`) et §6.
4. Code :
   - `core/src/openride_core/session.py` ;
   - `mock_driver.py` et `ftms_driver.py` (`set_target_power`) ;
   - `journal.py` (`Record.mode`, `Record.block`) ;
   - `config.py` (`rider.ftp_w`).

## 3. Prérequis

**Lot C livré.** Il modifie `session.py` et ajoute les tests de contrat qui valideront l'objet `erg`. Partir de `main` après la fusion de C.

## 4. Travail demandé

### 4.1 Lecteur `.zwo` : `core/src/openride_core/workout.py` (nouveau)

**Lecture :**
- XML avec `xml.etree.ElementTree` ;
- racine `workout_file`, qui contient `name`, `description` (facultatif) et `workout`, lequel contient les blocs ;
- noms de balises et d'attributs lus sans tenir compte de la casse.

**Blocs reconnus** (SRS §6). Les puissances sont des fractions de la FTP ; les durées sont en secondes.

| Balise | Attributs | Blocs produits (`type` du contrat) |
| --- | --- | --- |
| `Warmup` | `Duration`, `PowerLow`, `PowerHigh` | 1 bloc `warmup`, rampe de `PowerLow` à `PowerHigh` |
| `Cooldown` | `Duration`, `PowerLow`, `PowerHigh` | 1 bloc `cooldown`, rampe de `PowerLow` à `PowerHigh` (souvent descendante) |
| `Ramp` | `Duration`, `PowerLow`, `PowerHigh` | 1 bloc `ramp` |
| `SteadyState` | `Duration`, `Power` | 1 bloc `steady` |
| `IntervalsT` | `Repeat`, `OnDuration`, `OffDuration`, `OnPower`, `OffPower` | `Repeat` paires `interval_on` puis `interval_off` |
| `FreeRide` | `Duration` | 1 bloc `freeride`, sans cible |

**Cas particuliers :**
- **Balise ou attribut inconnu** (`textevent`, `Cadence`, `MaxEffort`, …) : ignoré avec un avertissement dans le journal du programme, une fois par nom.
- **Fichier invalide** (XML mal formé, bloc sans durée, puissance négative ou supérieure à 3, aucun bloc) : `WorkoutError` avec un message lisible. Rien ne plante.

**API :**

```python
@dataclass(frozen=True)
class Block:
    type: str            # warmup, steady, interval_on, interval_off, ramp, cooldown, freeride
    duration_s: float
    start_frac: float | None   # None pour freeride
    end_frac: float | None

@dataclass(frozen=True)
class Workout:
    id: str; name: str; blocks: tuple[Block, ...]
    @property
    def duration_s(self) -> float: ...

def load_workout(path: Path) -> Workout: ...
def list_workouts(directory: Path) -> list[WorkoutInfo]: ...   # id, nom, durée, profil, erreur éventuelle
```

`list_workouts` lit `~/OpenRide/Workouts/` (SRS §11). Un fichier invalide apparaît avec son erreur et n'est pas sélectionnable (SRS §6). Cette fonction prépare le futur menu : aucun message IPC ne l'expose encore (voir §7).

### 4.2 Contrôleur ERG : `ErgController` (dans `workout.py` ou un module dédié)

- **Entrée :** temps écoulé dans l'entraînement, appelé à chaque pas de 50 Hz ; FTP de la configuration ; biais.
- **Cible brute :** `ftp × fraction(t) × biais / 100`, arrondie au watt. Dans un bloc en rampe, la fraction varie linéairement de `start_frac` à `end_frac`.
- **Lissage :** à chaque **changement de bloc**, la cible passe de l'ancienne valeur à la nouvelle linéairement en 2 s (SRS §6). À l'intérieur d'une rampe, pas de lissage supplémentaire.
- **Biais :**
  - 100 % au départ ;
  - ± 2 points par appui court ;
  - borné à 80–120 %.
  - Le changement de biais s'applique immédiatement, sans lissage de 2 s.
- **Saut de bloc :** passe au début du bloc suivant, avec le lissage de 2 s. Au dernier bloc, il termine l'entraînement.
- **Pause ERG :**
  - le temps du bloc s'arrête ;
  - le trainer reçoit une pente de 0 % en mode SIM (SRS §4.4) ;
  - la physique et la séance continuent.
  - La reprise relance le bloc là où il s'était arrêté.
- **Bloc `freeride` :** pas de cible. Le core repasse en mode SIM, avec les braquets, le temps du bloc.
- **Fin de l'entraînement :** `mode` revient à `SIM`, `erg` devient `null`, et la séance continue en parcours libre. Un message est écrit dans le journal du programme.

**Objet `erg` du contrat §3**, recalculé à chaque trame :
- `workout_name` ;
- `block_index` et `block_count` (à partir de 1, après dépliage des intervalles) ;
- `block_type`, `block_remaining_s`, `block_total_s` ;
- `target_w` (cible lissée, biais inclus) ;
- `next_target_w` (début du bloc suivant ; `null` pour `freeride` ou à la fin) ;
- `bias_pct`, `paused`.

### 4.3 Intégration dans la session

**Commandes :**
- `select_workout` (`{ "workout_id": chaîne ou null }`), accepté en `IDLE` ou `READY` :
  - charge `~/OpenRide/Workouts/<workout_id>.zwo` (dossier pouvant être changé pour les tests) ;
  - `null` revient au SIM ;
  - en cas d'erreur, envoie `error` avec le code `workout_invalid`, et la séance reste en SIM.
- `start` : si un entraînement est choisi, `mode` vaut `ERG` et le contrôleur démarre.
- `skip_block` : saute le bloc, seulement en ERG.

**Pas de simulation** (`_step`), en ERG hors `freeride` et hors pause :
- appeler `driver.set_target_power(target_w)` ;
- ne pas envoyer de pente.
- Dans tous les autres cas, garder le chemin SIM actuel.
- La vitesse virtuelle continue d'utiliser la puissance mesurée et la pente du terrain (SRS §6).

**Actions du Click et du clavier en ERG** (SRS §4.4), à la place des braquets :
- appui court + / − : biais ± 2 % ;
- appui long + : bloc suivant ;
- appui long − : pause ou reprise ERG.
- Le relais des événements vers l'engine (bips) ne change pas.

**Journal :** `Record.mode` = `ERG` et `Record.block` = indice du bloc pendant l'entraînement.

**Pause de séance :** une pause (`user`, `engine_lost`, `trainer_lost`) arrête aussi le temps de l'entraînement.

### 4.4 Tests

- **`.zwo` de référence**, écrits par les tests :
  - un fichier complet : échauffement de 600 s de 0,5 à 0,75, `SteadyState` de 1 200 s à 0,95, `IntervalsT` 3 × (60 s à 1,2 / 60 s à 0,5), `FreeRide` de 120 s, retour au calme de 300 s de 0,7 à 0,4 ;
  - un fichier avec une balise inconnue `textevent` ;
  - trois fichiers invalides.
- **Session :** tests avec `MockDriver`, dont `target_power_w` permet de vérifier ce qui est envoyé.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/workout.py`, `core/tests/test_workout.py`.
- **Modifiés :**
  - `core/src/openride_core/session.py`, `config.py` (dossier des entraînements, s'il est rendu configurable) ;
  - `mock_driver.py`, seulement si nécessaire pour les tests ;
  - `core/tests/test_contract_ipc.py` (cas ERG ajoutés) ;
  - `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune. L'objet `erg` et les commandes existent déjà dans le contrat v1.

## 7. Critères d'acceptation

1. `pytest` passe en entier dans `core/`.
2. **Lecture du fichier de référence :**
   - 10 blocs : échauffement, palier, 6 blocs d'intervalles, roue libre, retour au calme ;
   - durée totale de 2 580 s ;
   - types et fractions exacts.
3. **Cibles** avec une FTP de 250 W et un biais de 100 :
   - `target_w` = 125 W à t = 0 ;
   - 156 W à t = 300 s (milieu de l'échauffement, fraction 0,625 → 156,25 W, arrondi) ;
   - 238 W en plein palier (0,95 → 237,5 W, arrondi au pair par la règle de Python, à documenter) ;
   - 300 W en intervalle « on ».
4. **Lissage :** au passage échauffement → palier, la cible va de 188 à 238 W en 2 s et vaut environ 213 W à 1 s, à 1 W près.
5. **Biais :** 5 appuis courts + donnent 110 % (cible du palier : 261 W). Au-delà de 120 %, le biais reste à 120 % (cible du palier : 285 W).
6. **Saut et pause :**
   - un appui long + au milieu du palier passe au premier intervalle, avec lissage ;
   - un appui long − arrête le temps du bloc et envoie une pente de 0 % ;
   - un second appui long − reprend au même temps restant, à 0,1 s près.
7. **Roue libre :** pendant `freeride`, la session repasse en SIM. Les braquets fonctionnent, `erg.block_type` = `freeride`, `target_w` reste à sa dernière valeur ou à 0 (à documenter), `next_target_w` vaut 175 W (début du retour au calme).
8. **Contrat :** les trames `state` en ERG valident `state.schema.json`, objet `erg` compris.
9. **Entrées invalides :** un `.zwo` invalide donne l'erreur `workout_invalid` sans arrêter le core ; `list_workouts` le liste avec son erreur.
10. **Journal :** sur un entraînement complet simulé en temps accéléré, il contient `mode` = `ERG` et des indices de bloc croissants.
11. **Essai manuel du propriétaire,** hors recette automatique : un `.zwo` standard s'exécute en entier sur le HomeTrainer et les cibles sont tenues (critère du sprint 4).

## 8. Hors périmètre

- Bandeau d'entraînement, bips à T − 3 s et histogramme des blocs dans l'engine : lot à rédiger. Les champs `erg` du contrat suffisent.
- Messages IPC pour lister les entraînements et les parcours dans un menu : à concevoir avec le lot G. Le contrat v1 n'en a pas encore.
- Autres formats d'entraînement.
