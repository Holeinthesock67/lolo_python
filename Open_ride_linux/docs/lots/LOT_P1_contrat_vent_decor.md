# Lot P1 – Contrat : vent, aspiration et décor vivant (IPC révision 1.3, thème 1.2, configuration `[wind]`)

## 1. Objectif

La série P anime le décor après la 1.0 (vent, nuages, météo, sons, animaux, objets mobiles, bord de route ; jour, nuit et saisons en 2.0) et rend le vent et l'aspiration **physiques**. Le core reste le maître : il calcule le vent et l'abri derrière un bot, et l'engine affiche ce qu'il reçoit (arbres, nuages, sons et indicateur du HUD suivent le même vent que les jambes). Ce lot fixe, **avant tout code**, les ajouts compatibles aux trois contrats concernés. C'est une décision du propriétaire, comme N1.

## 2. À lire

1. `docs/lots/00_INDEX.md` (paragraphe « Série P »), `docs/contracts/ipc_v1.md` §3 et §8, `docs/contracts/world_format_v1.md` §8 et §9, `docs/contracts/world/theme.schema.json`, `docs/contracts/world/poi.schema.json`.
2. `docs/SRS_v1.1.md` §5 (formule de la résistance, terme de vent et `alpha_draft`), §4.1 (paramètres SIM envoyés au trainer), §11 (configuration).
3. Code : `core/src/openride_core/physics.py` (`wind_mps`, `alpha_draft`), `core/src/openride_core/ftms.py` (champ vent de la commande 0x11), `engine/scripts/theme_render_params.gd`.

## 3. Prérequis

Version 1.0 publiée (lot O8). N9 n'est pas requis pour écrire le contrat, seulement pour P3.

## 4. Travail demandé

### Décisions du propriétaire (25 octobre 2026)

| # | Question | Décision |
| --- | --- | --- |
| 1 | Vent par défaut | Coupé (`mode = "off"`) dans les versions 1.x. En 2.0, activé par défaut d'après la météo locale (lecture au lancement, repli sans vent si le réseau manque) : demande d'assouplir la règle « hors ligne », à trancher en 2.0 |
| 2 | Ressenti en SIM | Supplément de pente (`feel = "grade"`) ; le champ vent du FTMS reste une option à essayer |
| 3 | Plafond du supplément | 4 points de pente, réglable dans la section « Réglages » du menu |
| 4 | ERG | Le vent et l'abri ne changent que la vitesse virtuelle, jamais la puissance demandée |
| 5 | Fréquence d'envoi du vent | 2 fois par seconde |
| 6 | Abri derrière le fantôme | Non : seuls les bots à puissance constante abritent |
| 7 | Éoliennes et drapeaux dans le format | Oui |

Les propositions ci-dessous sont ajustées à ces décisions.

Rédiger les ajouts, chacun avec sa ligne au journal des changements du document. Propositions de départ, à trancher par le propriétaire :

### 4.1 IPC révision 1.3 : champ `wind` de `state`

- Objet facultatif `wind`, absent quand le vent est désactivé (trames inchangées) : `{speed_mps, from_deg, head_mps, gust}`.
  - `speed_mps` : vitesse du vent au sol, rafale comprise (≥ 0) ;
  - `from_deg` : direction d'où vient le vent, en degrés dans le sens horaire depuis le nord (convention du cap de `world_format_v1.md` §3) ;
  - `head_mps` : composante de face le long du cap de la route à `s` (positive de face, négative de dos), celle qu'utilise la physique ;
  - `gust` : facteur de rafale de 0 à 1, pour l'animation (arbres, drapeaux, son).
- Ces quatre champs suffisent à l'indicateur du HUD demandé par le propriétaire le 25 octobre (vent favorable ou non, et son intensité) : le verdict vient du signe de `head_mps`, l'intensité de `speed_mps` (calcul dans `wind_view_model.gd`, lot P4). Aucun champ de plus.
- Envoyé **2 fois par seconde** (décision du propriétaire), dans une trame sur quinze environ (environ 70 octets) ; la physique du core utilise le vent exact à 50 Hz et l'engine lisse les valeurs reçues. Vérifier que la trame la plus chargée (ERG, `devices`, 5 bots, `wind`, `draft`) tient toujours dans 1 400 octets (à la livraison : `wind` jamais dans la trame qui porte `devices`, §9).

### 4.2 IPC révision 1.3 : champ `draft` de `state`

- Nombre facultatif `draft` de 0 à 0,45 : coefficient d'aspiration appliqué au cycliste (SRS §5), absent sans bot. Champ facultatif `draft_bot` : `id` du bot qui abrite, ou absent.

### 4.3 Configuration `[wind]` (SRS §11)

- `mode` = `"off"` (défaut : comportement actuel), `"fixed"`, `"gusty"`, `"theme"` ; `speed_kmh` (0 à 60), `from_deg` (0 à 360), `gust_pct` (0 à 100), `seed` (entier).
- `feel` = `"grade"` (défaut) ou `"ftms"` : en SIM, la résistance due au vent et à l'aspiration est transmise au trainer soit sous forme de **supplément de pente**, soit dans le champ vent de la commande FTMS 0x11. `"grade"` est le choix sûr (pente validée sur le trainer le 22 octobre) ; `"ftms"` reste à essayer sur le matériel.
- `max_grade_offset_pct` (défaut 4,0, bornes 0 à 8) : borne du supplément de pente, réglable dans la section « Réglages » du menu (écrite par les réglages du core, comme O3).
- En ERG, ni le vent ni l'aspiration ne changent la résistance (puissance imposée) ; seule la vitesse virtuelle change.

### 4.4 Thème 1.2 (`theme.schema.json`, `world_format_v1.md` §9)

Clés facultatives, toutes ignorées par un engine qui ne les connaît pas :
- `sky.clouds` : `{coverage, speed_factor, color, altitude_m}` ;
- `sky.time_of_day` : `{mode: "fixed" | "real" | "accelerated", hour, factor}` (utilisé en 2.0 par P7) ;
- `weather` : `{kind: "clear" | "mist" | "rain" | "snow", intensity, morning_mist}` ;
- `season` : `"spring" | "summer" | "autumn" | "winter"` (feuilles qui tombent, couleur des arbres ; utilisé en 2.0 par P18) ;
- `wind` : `{speed_kmh, from_deg, gust_pct}`, lu quand `[wind] mode = "theme"` ;
- `ambience` : `{volume, birds, insects}` ;
- `fauna` : `{birds, livestock, deer}` (densités de 0 à 1).
- Mettre à jour `engine/themes/default/theme.json` avec des valeurs d'été calmes.

### 4.5 Format `.world` : points d'intérêt

- Ajouter les sortes `wind_turbine` (OSM `power=generator` et `generator:source=wind`, avec `height_m` facultatif) et `flag` (OSM `man_made=flagpole`) à l'énumération de `poi.schema.json` (§8).

## 5. Fichiers concernés

- **Modifiés :** `docs/contracts/ipc_v1.md`, `docs/contracts/ipc/state.schema.json`, `docs/contracts/world_format_v1.md`, `docs/contracts/world/theme.schema.json`, `docs/contracts/world/poi.schema.json`, `engine/themes/default/theme.json`, `docs/SRS_v1.1.md` (§5 et §11), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** tout code.

## 6. Modifications de contrat autorisées

Ajouts compatibles décrits au §4, et seulement eux.

## 7. Critères d'acceptation

1. `(cd core && pytest -q)` passe, dont `core/tests/test_docs_coherence.py` (schémas valides, exemple `config.toml` de la SRS §11 cohérent ; si `[wind]` y figure avant P2, l'ajouter comme exception commentée jusqu'à P2).
2. Une trame `state` d'exemple avec `wind` et `draft` est valide pour le schéma ; la même sans ces champs aussi.
3. `openride-compiler theme-check engine/themes/default` accepte le thème mis à jour.
4. Le propriétaire a validé les choix du §4 (notés en tête du lot à la livraison).

## 8. Hors périmètre

- Vent de travers sur la physique (seule la composante de face compte), vent qui varie selon le relief.
- Aspiration entre bots, peloton.
- Météo réelle téléchargée (aucun réseau à l'exécution).

## 9. Livraison (26 octobre 2026)

Livré sur la branche `lot-p1-contrat-vent-decor`. Les décisions du propriétaire du 25 octobre sont notées en tête du §4 ; la série a été lancée le 26 octobre sans attendre la 1.0 (« Lance les lots O et P »).

- **Numéro de révision :** Q1 et N13 ayant pris la révision 1.2 de l'IPC, le vent et l'aspiration forment la **révision 1.3** (numérotation confirmée par le propriétaire le 26 octobre). Les plans de la 2.0 (séries R, T et V) passent en révision 1.4.
- **IPC :** objet `wind` (`speed_mps`, `from_deg`, `head_mps`, `gust`) et champs `draft` et `draft_bot` dans `state` (`ipc_v1.md` §3, `state.schema.json`), avec les arrondis d'envoi. Pour tenir dans 1 400 octets, `wind` n'est jamais dans la trame qui porte `devices` (le core le décale d'une trame) : avec ERG, 5 bots et l'aspiration, la trame qui porte `devices` fait environ 1 370 octets et celle qui porte `wind` environ 1 160 octets.
- **Configuration :** section `[wind]` décrite dans la SRS §11, hors de l'exemple `config.toml` tant que le core ne la lit pas (lot P2 l'y ajoute) ; SRS §5 complétée (composante de face, supplément de pente borné, ERG, fantôme sans abri).
- **Thème 1.2 :** `sky.clouds`, `sky.time_of_day`, `weather`, `season`, `wind`, `ambience` et `fauna` dans `theme.schema.json` et `world_format_v1.md` §9 ; `engine/themes/default/theme.json` passe en 1.2 avec un été calme (vent de 8 km/h d'ouest, 30 % de nuages).
- **Points d'intérêt :** `wind_turbine` (avec `height_m`) et `flag` dans `poi.schema.json` et `world_format_v1.md` §8 (format 1.2).
- **Tests :** `test_v1_3_wind_and_draft_are_optional_and_fit` (trames avec et sans les nouveaux champs, valeurs hors bornes refusées, deux trames les plus chargées) ; `openride-compiler theme-check engine/themes/default` accepte le thème.
