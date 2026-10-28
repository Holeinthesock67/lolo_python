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
