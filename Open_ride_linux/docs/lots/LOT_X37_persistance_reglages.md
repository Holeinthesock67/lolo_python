# Lot X37 – Persistance de tous les réglages

## 1. Objectif

Le 28 octobre, la difficulté réglée depuis l'écran de pause ne survivait pas à un redémarrage, et aucun test ne l'a vu. Ce lot vérifie que **chaque** réglage de la liste `settings` survit à un redémarrage complet (core et engine), qu'il soit changé depuis les Réglages ou depuis la pause.

## 2. À lire

`core/src/openride_core/settings.py` (liste des réglages, écriture de `config.toml`), `core/tests/test_settings.py`, le banc des menus réécrit par le fil « Tester automatiquement les menus au clic et clavier » (étapes `relancer` et `config`, scénarios `engine/tests/menu_scenarios/`).

## 3. Travail demandé

- **Test core** `core/tests/test_settings_persistance.py` : pour chaque réglage de la liste (lue, pas recopiée) : valeur différente de la valeur par défaut choisie selon son type (bornes, choix), `set_setting` par l'IPC, arrêt du core, relance sur le même HOME, `list_settings` : la valeur est relue ; même chose pour la difficulté depuis la pause (`set_difficulty`). Un réglage ajouté plus tard est couvert sans retouche.
- **Scénario du banc des menus** `engine/tests/menu_scenarios/persistance.json` : changer au Click quatre réglages de groupes différents et la difficulté de la pause, relancer, vérifier à l'écran et dans `config.toml`.

## 4. Fichiers

- **Nouveaux :** `core/tests/test_settings_persistance.py`, `engine/tests/menu_scenarios/persistance.json` (après la PR du banc des menus).
- **Modifiés :** `docs/OUTILS_DE_TEST.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 5. Critères d'acceptation

1. Le test couvre tous les réglages ; un réglage volontairement non écrit dans `config.toml` le fait échouer en le nommant.
2. Le scénario du banc passe sous Xvfb.

## 6. Hors périmètre

Mémoriser le dernier parcours ou entraînement choisi (question posée au propriétaire).

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x37`).

- **`core/tests/test_settings_persistance.py`** (3 tests) :
  - pour chaque élément de `list_settings`, une autre valeur permise (choix suivant, ou un pas de plus, un de moins en butée) est envoyée par `set_setting` ; un nouveau `CoreSession` relit le même `config.toml` (`config.load`) ; `list_settings` doit rendre toutes les valeurs. La liste vient du core, pas du test : un réglage ajouté est couvert sans retouche (seul `render.theme` est sauté quand aucun pack n'est installé, car il n'a qu'un choix) ;
  - difficulté réglée depuis la pause (`set_difficulty`, séance en pause) relue après relance, dans `difficulty_pct` et dans la liste ;
  - critère 1 : une écriture de `config.toml` qui oublie `audio.events_pct` fait échouer le contrôle avec ce nom.
- **Scénario du banc des menus** `engine/tests/menu_scenarios/persistance.json` :
  - difficulté de la pause 50 → 40 % pendant une séance abandonnée ;
  - puis, dans quatre sous-écrans des Réglages : FTP + 5 W, niveau des bots − 5 %, volume général − 10 %, force du vent + 5 km/h ;
  - `relancer`, puis chaque valeur relue dans `config.toml` et à l'écran.
- **Mesuré au cloud sous Xvfb** : voies clavier OK en 66 s, Click simulé OK en 68 s, souris OK en 37 s.
