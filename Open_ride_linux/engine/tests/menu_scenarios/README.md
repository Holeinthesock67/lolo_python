# Scénarios du robot des menus

Un fichier JSON par scénario, joué par `engine/tests/menu_robot.py` (vrai core sur Bluetooth simulé, vrai engine en `--test-mode`, HOME temporaire). Chaque scénario est joué une fois par canal d'entrée de sa liste `canaux` :

| Canal | Chemin des entrées |
| --- | --- |
| `click` | Appui sur le Click simulé par le port de pilotage du Bluetooth simulé (`control_port`, `ble_sim.py`) : trame 0x23 du boîtier, vrai pilote et décodeur du core, relais `input` à l'engine |
| `clavier` | Appui puis relâchement d'une touche injectés dans Godot (`Input.parse_input_event`, `test_input.gd`) avec la vraie durée : `_unhandled_input`, `key_map.gd` |
| `souris` | Survol, clic gauche sur la ligne, clic droit et molette injectés dans `menu_view.gd` ; un bouton sans geste de souris (A court, Z, appuis longs) est joué au clavier et compté dans le rapport |

```bash
python3 engine/tests/menu_robot.py --list                          # scénarios et canaux
python3 engine/tests/menu_robot.py --check                         # valide les fichiers sans rien lancer
python3 engine/tests/menu_robot.py                                 # tout, rapport.html (~25 min)
python3 engine/tests/menu_robot.py --rapide                        # un canal par scénario (~10 min)
python3 engine/tests/menu_robot.py --scenario reglages --canal click --native   # fenêtre visible
```

## Un seul tableau bouton → action

`BOUTONS` dans `menu_robot.py` reprend la colonne « Menus » de la spécification générale §7.1, seule référence : pour chaque bouton et durée d'appui (`+ court`, `- long`, `B court`, `A long`, `Y court`, `Z court`, `gauche`, `haut`, `+ flou`…), le bouton du Click simulé, la touche (même durée), le geste de la souris et l'effet attendu dans un menu (`suivant`, `precedent`, `+5`, `-5`, `valider`, `retour`, `rien`). `SYNONYMES` reprend le tableau du clavier (`=`, `Pavé+`, `PageHaut`, `Maj+A`, `Entrée`, `Échap`, `Maj+Z`…). L'étape `tableau` vérifie l'effet de chaque bouton sur l'écran affiché, avec les règles de focus de `menu_model.gd` (saut des éléments désactivés, boucle, grand pas borné).

## Format

```json
{
  "description": "Ce que le scénario couvre (affiché dans le rapport).",
  "canaux": ["clavier", "click", "souris"],
  "preparation": {"entrainements": true},
  "etapes": [
    {"attendre_ecran": "home", "delai": 15},
    {"ouvrir": "settings"},
    {"ecran": "settings", "elements": ["devices", "group:rider"], "focus": "devices"},
    {"tableau": null, "retour_vers": "home"}
  ]
}
```

Écrans et éléments sont désignés par leurs **identifiants stables** (`menu_model.gd`, `menu_flow.gd`, `settings_view_model.gd`…), jamais par leur libellé : un libellé peut changer avec la présentation des menus sans casser les scénarios. Les textes (`texte`, `titre`) ne servent qu'aux valeurs affichées (« 265 W »).

**Préparation** (`preparation`, dans le HOME temporaire) : `entrainements` (`erg_court.zwo`), `plans` (`plan_banc.toml` et son entraînement), `imports` (un `.zwo` dans `~/Téléchargements`), `parcours` (copies du parcours `demo` sous d'autres noms), `profil` (contenu de `~/OpenRide/profile.json`), `config` (lignes ajoutées à `config.toml`), `click` (`"unilateral"` : boîtier « − » jamais annoncé).

**Actions** (une par étape) :

| Clé | Effet |
| --- | --- |
| `bouton` | Bouton du tableau joué sur le canal du scénario (`"A long"`, `"- court"`, `"Y"`) ; `n` : répétitions |
| `ouvrir` | Focus sur l'élément puis validation (A long ; à la souris : clic sur sa ligne) |
| `aller` | Focus sur l'élément par petits pas (+ ou −, le plus court) |
| `touche` | Touche du clavier, quel que soit le canal (`"Entrée"`, `"Maj+A"`, `"PageHaut"`) ; `duree` facultative |
| `click` | Bouton du Click simulé (`"A"`, `"Y"`, `"LEFT"`…), `duree` |
| `souris` | Geste de la souris (`left`, `right`, `wheel_up`, `wheel_down`, `move`), `element` facultatif |
| `commande` | Commande du contrat envoyée par l'engine (`pause`, `end_session` avec `args`) |
| `attendre`, `attendre_etat`, `attendre_ecran` | Pause en secondes ; état de séance du core (`RUNNING`, `PAUSED`, `FINISHED`) ; écran du menu |
| `tableau` | Liste de boutons (ou `null` : le tableau par défaut) vérifiés sur l'écran affiché ; `sauf`, `retour_vers` (Y court en dernier, écran attendu) |
| `capture` | Capture d'écran nommée, dans le rapport |
| `ecrire` | Fichier écrit dans le HOME temporaire (`contenu`) |

**Vérifications** (plusieurs par étape, attendues jusqu'à `delai` secondes) : `ecran`, `titre`, `titre_debut`, `focus`, `elements` (`"item:*"` : un élément qui commence par `item:`), `absents`, `actifs`, `inactifs`, `texte`, `pas_texte`, `edition` (réglage en cours de modification), `menu_visible`, `monde_ouvert`, `bandeau`, `statut` (ligne d'état), `aide` (aide des boutons), `config` (`{"rider.ftp_w": 265}` lu dans `config.toml`), `config_present`, `config_absent`, `fichier` (chemin sous le HOME), `journal_core`, `journal_engine` (expressions régulières), `action_menu`, `sortie_engine` (code de sortie attendu), `signaler` (information seule : élément présent ou non).

**Options** de toute étape : `note` (affichée), `canaux` (étape jouée seulement sur ces canaux), `delai`, `connu` (défaut connu et expliqué : ses échecs sont signalés sans compter ; quand l'étape repasse, le rapport demande de retirer `connu`).

Chaque échec joint au rapport une capture d'écran et l'état du menu (écran, titre, focus, éléments avec leurs identifiants).
