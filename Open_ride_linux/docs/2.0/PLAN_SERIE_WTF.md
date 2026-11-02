# Plan de la série WTF : mode « What the fuck »

Demande du propriétaire du 29 octobre 2026 : un mode de jeu délirant où toutes les idées du brainstorm sont jouées, chacune **désactivable une à une**, plus une règle inventée, « la surprise du chef ». Toute maquette sera soumise au propriétaire avant le moindre code d'affichage, et tout essai de performance se fera en `low`, `medium` **et** `high`, captures à l'appui.

Sources lues : `core/src/openride_core/physics.py`, `powerups.py` (T6), `wind.py` (P2), `classic.py` (T7), `session.py` (pente envoyée, ERG, abri), `settings.py`, `docs/contracts/ipc_v1.md` (révisions 1.4 et 1.5), `docs/5.0/PLAN_SERIE_CT.md` (style cartoon, mode SIM seulement).

---

## 1. En bref

1. **Un mode à part**, « Mode WTF », lancé depuis le menu comme le Cyber-Rogue : le mode classique, ses records et sa physique honnête ne changent pas.
2. **Treize règles**, toutes actives par défaut, chacune coupée ou rallumée dans un écran du menu (fichier `~/OpenRide/wtf.toml`, écrit par le core seul).
3. **Deux familles** : les **événements** (un seul à la fois, de 30 s à 2 min 30, tirés au hasard toutes les 45 à 90 s, « en sac » : chaque gag actif sort une fois avant qu'un autre ne revienne) et les **règles permanentes** (toute la séance). Sans ce tirage, douze gags en même temps seraient illisibles.
4. **SIM seulement**, comme la Course tactique : en ERG le trainer impose la puissance et aucune règle n'aurait de sens.
5. **Sécurité de la résistance réelle** : supplément de pente ressenti borné à ± 3 points, pente envoyée bornée de − 6 % à + 10 %, puis la limitation de variation habituelle du core (2 %/s). Les seuils des défis sont indexés sur la FTP, jamais en watts absolus. Pas de détection d'à-coup pendant une coupure du trainer (#542).
6. **La puissance mesurée n'est jamais modifiée** : journal, FIT et bilan gardent les watts réels. Les effets ne touchent que la vitesse virtuelle et, pour quelques règles, la pente ressentie bornée.
7. **Pas de records** dans ce mode (la physique y est fausse exprès) ; les points WTF ont leur propre bilan.

## 2. Les treize règles

| Règle (`id`) | Famille | Durée | Ce qui se passe | Effet sur la physique virtuelle | Effet sur le trainer (SIM) |
| --- | --- | --- | --- | --- | --- |
| Gravité au choix (`gravity`) | Événement | 60 s | La Lune (g × 0,165, le vélo bondit toutes les 2 s, jusqu'à 3 m) ou Jupiter (g × 2,53) | Pente et roulement × g | Pente × g, bornée |
| Monde à l'envers (`upside_down`) | Événement | 45 s | Ciel en bas, descentes et montées échangées | Pente × − 1 | Pente × − 1, bornée |
| La route s'effondre (`collapse`) | Événement | 60 s | La route s'écroule 120 m derrière toi, à la vitesse que donneraient 60 % de la FTP sur la pente du moment ; rattrapé : chute (cartoon), sinon 150 points | Aucun | Aucun |
| Katamari à vélo (`katamari`) | Permanente | Séance | Objets semés sur la route (pomme, panneau, vache, voiture, maison, église) : ramassés si tu es assez gros, sinon « boing » ; la boule grossit jusqu'à × 6 | Masse + 10 kg par unité de taille, 50 kg au plus | + 0,4 point par unité, 2 points au plus |
| Peloton délirant (`peloton`) | Permanente | Séance | Les bots deviennent mamie en vélo hollandais, tracteur, baignoire à roulettes et une seule baleine volante ; toutes les 2,5 à 4 min une mamie attaque (× 1,3 pendant 20 s) | Abri derrière la baleine × 1,5, sous le plafond de 55 % de la série AS | Abri ressenti comme aujourd'hui |
| Fromage géant (`cheese`) | Événement | Jusqu'à 75 s | Après 3 s de descente à − 3 % ou plus, une meule part 60 m derrière toi et accélère ; 250 m d'avance : 150 points, rattrapé : écrasé 3 s | Aucun | Aucun |
| Micro-défis (`micro`) | Événement | 3 × 30 s | Trois défis tirés parmi cinq : cadence pile (± 3 rpm, 60 % du temps), sprint (150 % de la FTP pendant 5 s : saut du ravin), plafond (moins de 60 % de la FTP, 3 s de tolérance : le gâteau tient), régularité (± 10 % pendant 70 % du temps), moulinette (110 rpm pendant 10 s) ; 100 points par défi | Aucun | Aucun |
| Livraison d'œufs (`eggs`) | Événement | 1 km, 2 min 30 au plus | Six œufs : un écart de plus de 35 % de la FTP d'une seconde à l'autre en casse un (une casse toutes les 2 s au plus) ; 50 points par œuf livré | Aucun | Aucun |
| La cadence pilote le monde (`clock`) | Permanente | Séance | L'heure avance de 3 h par minute à 90 rpm (proportionnelle à la cadence) ; au-dessus de 100 rpm il pleut des poissons (arrêt sous 95) | Aucun | Aucun |
| Vélo minuscule (`tiny`) | Événement | 60 s | Échelle 1/40 : la route traverse une cuisine géante, une pente c'est le bord d'une assiette | Aucun | Aucun |
| Météo folle (`storm`) | Événement | 40 s | Tornade de vaches et vent de face de 22 km/h ; sous 50 % de la FTP le vent te repousse (jusqu'à 30 m, visuel) ; tenu : 100 points | Vent de face + 6 m/s | + 1,5 point |
| Caméras improbables (`camera`) | Événement | 30 s | Vue d'un pigeon qui te suit, d'un escargot au bord de la route ou de ta roue | Aucun | Aucun |
| Surprise du chef (`chef`) | Événement | 54 s | Voir §3 | Selon le plat | Selon le plat |

## 3. La règle inventée : la surprise du chef

Un chef en toque te rattrape en tandem (4 s), puis soulève sa cloche : le plat est montré 5 s, pendant lesquelles **Z court** le refuse (« Non merci, chef ! »). Un chef vexé revient la fois suivante avec le plat le plus piquant. Sinon le plat se mange pendant 45 s :

| Plat | Ce qui se passe | Points |
| --- | --- | --- |
| Spaghetti (`spaghetti`) | La route ondule de ± 1,5 point toutes les 8 s, à l'écran et sous les pieds | 50 |
| Gelée (`jelly`) | Route en gelée qui tremble et colle : roulement × 1,5, + 1 point ressenti | 50 |
| Bal musette (`musette`) | Un accordéoniste annonce une cadence (80, 95 puis 70 rpm, 15 s chacune) ; chaque seconde à ± 4 rpm fait danser la foule | 2 par seconde |
| Soufflé (`souffle`) | Un soufflé au fromage sur le guidon monte quand la puissance est régulière et retombe à chaque à-coup ; réussi au-dessus de 80 % | 120 si réussi |
| Piment (`chili`) | Vitesse virtuelle + 25 % pendant 25 s, puis « ça brûle » : − 15 % pendant 20 s | 50 |

Pourquoi cette règle : elle mélange l'effet de surprise du tirage, un choix tactique (refuser, au risque du piment) et des gestes que le home trainer mesure bien (cadence, régularité). Elle ne demande aucune nouvelle mesure.

## 4. Architecture

- **Core, modules purs** `core/src/openride_core/wtf/` (lot WTF1, livré) : `rules.py` (catalogue, fichier `wtf.toml`), `events.py` (événements), `chef.py` (surprise du chef), `mode.py` (`WtfMode` : tirage, règles permanentes, effets combinés et bornés, champ `wtf` proposé, lignes `wtf` du journal, bilan).
- **Séance** (lot WTF2, livré) : `WtfMode.step` à chaque pas en `RUNNING` ; pente transformée pour la physique et pour la pente envoyée (avant braquet, puis supplément borné, puis bornes du mode, puis limitation de variation habituelle) ; costumes et attaques appliqués aux bots ; abri de la baleine ; Z court relayé au mode.
- **Engine** (lots WTF3 à WTF7) : n'affiche que ce que le core envoie dans `wtf`. Style **cartoon, flashy et exagéré**, même famille que la charte CT9 de la Course tactique, pour ne pas créer un troisième style.

Boutons (plan unique §7.1 de la spécification) : rien de nouveau. Z court refuse le plat du chef ; les braquets restent sur + et − ; Y reste la pause.

## 5. Champ `wtf` proposé pour la trame `state` (contrat : lot WTF2)

Forme produite par `WtfMode.frame` (environ 300 octets avec quatre bots, sous 1 200 octets dans tous les essais) :

```json
{"points": 350,
 "event": {"id": "chef", "left_s": 41.2, "phase": "eat", "dish": "musette", "phase_left_s": 32.0, "tempo_rpm": 95.0},
 "kata": {"size": 2.31, "count": 42, "last": "cow", "next": [[35.2, "car"], [110.0, "apple"], [190.4, "house"]]},
 "skins": {"b1": "grandma", "b2": "tractor", "b3": "bathtub", "b4": "whale"}, "attack": null,
 "clock_h": 17.5, "fish": false}
```

`next_s` (secondes avant le prochain événement) remplace `event` quand aucun n'est en cours. Les clés d'une règle coupée sont absentes.

## 6. Lots

| Lot | Titre | Dépend de | Taille |
| --- | --- | --- | --- |
| [WTF1](../lots/LOT_WTF1_regles_core.md) | Règles du mode dans le core (modules purs, tests) | — | Moyenne, **livré** |
| [WTF2](../lots/LOT_WTF2_seance_contrat.md) | Branchement dans la séance et contrat IPC | WTF1 | Moyenne, **livré** |
| [WTF3](../lots/LOT_WTF3_menu_regles.md) | Entrée du menu et écran des treize interrupteurs | WTF2 | Petite |
| [WTF4](../lots/LOT_WTF4_maquettes.md) | Maquettes cartoon des gags, validées par le propriétaire | WTF1 | Moyenne |
| [WTF5](../lots/LOT_WTF5_gags_physiques.md) | Engine : gravité, monde à l'envers, route qui s'effondre, fromage, tempête | WTF2, WTF4 | Grande |
| [WTF6](../lots/LOT_WTF6_decor_bots_camera.md) | Engine : Katamari, peloton délirant, horloge et poissons, vélo minuscule, caméras | WTF2, WTF4 | Grande |
| [WTF7](../lots/LOT_WTF7_hud_chef.md) | Engine : HUD des défis et des œufs, surprise du chef, bilan, sons | WTF2, WTF4 | Moyenne |
| [WTF8](../lots/LOT_WTF8_recette.md) | Recette sur le vélo (étapes de 10 min) et banc `low`, `medium`, `high` | WTF3 à WTF7 | Petite |

Ordre : WTF1 ──► WTF2 ──► WTF3 ; WTF1 ──► WTF4 ; WTF2, WTF4 ──► WTF5, WTF6, WTF7 ──► WTF8.

## 7. Questions ouvertes (réponses par défaut appliquées en attendant)

1. **Version** : rangé avec la 2.0 (contrat 1.5, bots à profil). Le mode peut sortir plus tôt, rien ne dépend de la 3.0.
2. **Points et progression** : les points WTF ont leur bilan propre ; l'expérience de la série V compte la séance comme une séance libre (temps et distance), sans bonus de points WTF.
3. **Rythme** : un événement toutes les 45 à 90 s, premier à 20 s ; réglable dans `wtf.toml` (`[director]`), sans réglage au menu pour l'instant.
