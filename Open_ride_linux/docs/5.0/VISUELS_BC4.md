# Série BC (5.0) – Consignes des visuels pour Nano Banana (lot BC4)

7 novembre 2026. Fiche de commande des 42 visuels de la collection, pour l'IA d'images de Gemini (« Nano Banana »), demande du propriétaire du même jour. Plan : `docs/5.0/PLAN_SERIE_BC.md` §5 et §12 ; catalogue : `core/src/openride_core/data/collection.toml` (colonne `visual`).

## 1. Mode d'emploi

1. **Planche d'essai d'abord** : générer les 6 visuels marqués ★ au §4, les montrer côte à côte, faire valider le style. Ne commander les 36 autres qu'après.
2. Pour chaque visuel : coller le **bloc de style commun** (§2), puis la ligne **Sujet** de la carte (§4). Les consignes sont en anglais : l'IA d'images les suit mieux. Une image par message, pour garder le même style d'une carte à l'autre ; au besoin, joindre une image déjà validée en disant « same style as this image ».
3. Enregistrer chaque image sous le nom de la colonne `visual` : `coq.png`, `citrouille.png`… Le cadre de rareté, le titre, la ligne d'ambiance, la date et l'année d'une carte de saison sont dessinés par le jeu : **ils ne doivent pas être dans l'image**.
4. Si l'IA ajoute du texte, des chiffres ou un logo, régénérer (ou ajouter « absolutely no text, no letters, no numbers »).

## 2. Bloc de style commun (à coller à chaque fois)

```text
Circular badge illustration for a cycling video game collection card.
Style: flat cartoon vector art, bold clean outlines, soft cel shading, simple shapes,
bright saturated colors, friendly and playful, readable at small size (128 px).
Composition: one single subject, centered, filling a circle about 85 % of the image,
plain transparent background outside the circle, no frame, no border, no card edges.
Absolutely no text, no letters, no numbers, no logos, no brand names, no real people,
no flags. Square image, 1024 x 1024.
```

Couleur dominante selon la rareté (à ajouter après le bloc commun) :

| Rareté | Ligne à ajouter |
| --- | --- |
| commune | `Dominant palette: warm bronze and copper tones with one accent color.` |
| rare | `Dominant palette: cool silver and sky blue tones with one accent color.` |
| épique | `Dominant palette: rich gold and deep purple tones, subtle glow.` |
| légendaire | `Dominant palette: iridescent rainbow sheen, magical sparkles, strong glow.` |

## 3. Format attendu à la livraison

- PNG, fond transparent ; réduit à 512 × 512 par le script de contrôle de BC4 (l'IA livre souvent en 1024 × 1024 : c'est bien).
- Sujet centré, lisible en 128 px ; 200 Ko au plus après réduction.
- Si l'outil ne sait pas faire de fond transparent : demander `plain pure white background`, le détourage se fera au contrôle.

## 4. Consigne de chaque carte

★ = planche d'essai (une par rareté, une de saison, une d'heure).

| Visuel | Rareté | Carte | Sujet (à coller après le bloc commun) |
| --- | --- | --- | --- |
| `borne_100` | commune | Cent bornes | `Subject: a classic French roadside milestone (white stone with red top), a small bicycle leaning against it, sunny road.` |
| `borne_500` | commune | Cinq cents bornes | `Subject: a row of three roadside milestones along a winding country road seen from above, a tiny cyclist on the road.` |
| `borne_1000` | rare | Mille bornes | `Subject: a tall shiny roadside milestone with a laurel wreath around it, confetti in the air.` |
| `hexagone` | épique | Tour de France | `Subject: a stylized hexagon-shaped map of France made of roads, a bicycle wheel at its center, no flag.` |
| `globe` | légendaire | Tour de la Terre | `Subject: planet Earth with a cycling road wrapped around the equator and a tiny cyclist riding on it.` |
| `pedale` ★ | commune | Premier coup de pédale | `Subject: a close-up of a bicycle pedal and crank turning, small motion lines, a shoe about to clip in.` |
| `trainer_use` | rare | Habitué du home trainer | `Subject: a road bike mounted on an indoor smart trainer, a cozy room, a screen with a road in the background.` |
| `chrono_50` | commune | Demi-centaine | `Subject: a cycling stopwatch with a half-filled colored ring around it, a small road behind.` |
| `casque_romain` | épique | Centurion | `Subject: a cycling helmet styled like a Roman centurion helmet with a red crest.` |
| `sablier` | rare | Longue sortie | `Subject: an hourglass whose sand is made of tiny bicycle wheels, a long road in the background.` |
| `lacets` | rare | Mille mètres | `Subject: a mountain road with many hairpin bends climbing a green slope, a small cyclist on the switchbacks.` |
| `everest` ★ | épique | Toit du monde | `Subject: a snowy highest mountain peak with a bicycle planted on the summit like a flag pole, clouds below.` |
| `altimetre` | rare | Dix mille mètres | `Subject: a vintage altimeter gauge with a mountain silhouette on its dial and a bicycle needle.` |
| `panneau_hc` | rare | Hors catégorie | `Subject: a steep mountain pass road sign shape (blank, no writing) at the top of a brutal climb, rocky peaks.` |
| `calendrier_3` | commune | Semaine bien remplie | `Subject: a weekly calendar page with three days marked by small bicycle stickers (no numbers, no letters).` |
| `calendrier_4` | rare | Un mois sans lâcher | `Subject: a monthly calendar page whose four rows each have a glowing bicycle sticker (no numbers, no letters).` |
| `calendrier_12` | légendaire | Une saison entière | `Subject: a stack of calendar pages forming a staircase, each page with a bicycle sticker, a trophy on top.` |
| `sept_soleils` | épique | Sept jours sur sept | `Subject: seven small suns arranged in a ring around a bicycle wheel.` |
| `coq` ★ | commune | Lève-tôt | `Subject: a proud rooster perched on bicycle handlebars at sunrise, orange sky.` |
| `coq_dore` | rare | Chant du coq | `Subject: a golden rooster crowing on top of a bicycle saddle, sunrise rays behind.` |
| `sandwich` | commune | Pause de midi | `Subject: a baguette sandwich and a water bottle in a bicycle bottle cage, noon sun above.` |
| `hibou` | commune | Noctambule | `Subject: an owl wearing a cycling cap, riding a bicycle under a crescent moon and stars.` |
| `metronome` | rare | Métronome | `Subject: a metronome whose pendulum is a bicycle crank arm, rhythm lines around it.` |
| `rampe` | commune | Mesure de référence | `Subject: a staircase-shaped power bar chart made of glowing steps, a lightning bolt at the top step.` |
| `rampe_quatre` | rare | Suivi trimestriel | `Subject: four small staircase-shaped bar charts in a row, each a bit higher than the previous one.` |
| `maillot_pois` | rare | Maillot à pois | `Subject: a cycling jersey, white with red polka dots, floating on a hanger, mountain behind, no logo.` |
| `maillot_vert` | rare | Maillot vert | `Subject: a plain green cycling jersey floating on a hanger, speed lines behind, no logo.` |
| `chrono_or` | rare | Chasseur de records | `Subject: a golden stopwatch with a laurel wreath, a small finish line behind it.` |
| `grille_neon` | commune | Entrée dans la grille | `Subject: a cyclist entering a glowing neon grid tunnel, cyberpunk cyan and magenta.` |
| `boss_neon` | rare | Tombeur de boss | `Subject: a defeated giant neon robot head crumbling into pixels, a bicycle wheel shining in front.` |
| `canard` | commune | Grand n'importe quoi | `Subject: a yellow rubber duck wearing a cycling helmet riding a tiny bicycle, silly and joyful.` |
| `arche_finale` | épique | Dernier debout | `Subject: a single cyclist passing under a big inflatable finish arch, other bikes far behind, spotlight.` |
| `feu_artifice` | rare | Bonne résolution | `Subject: fireworks bursting above a bicycle wheel at midnight, festive.` |
| `coeur_tandem` | rare | Tandem de cœur | `Subject: a tandem bicycle with a big red heart floating above it.` |
| `oeuf_casque` | rare | Chasse aux œufs | `Subject: a painted spring egg wearing a tiny cycling helmet, sitting in grass with flowers.` |
| `soleil_haut` ★ | rare | Jour le plus long | `Subject: a big summer sun at its highest point above a long straight road, sunflowers on the side.` |
| `boucle_juillet` | épique | Grande Boucle | `Subject: a looping road forming a big circle through summer countryside, with a yellow cycling jersey floating above, no logo.` |
| `citrouille` ★ | rare | Pédaleur citrouille | `Subject: a smiling jack-o'-lantern pumpkin wearing a cycling helmet, riding a bicycle, bats in the night sky.` |
| `traineau` | rare | Tournée du père Noël | `Subject: a festive sleigh pulled by a bicycle instead of reindeer, gifts, snowflakes.` |
| `horloge_minuit` | rare | Dernier col de l'année | `Subject: a clock with both hands pointing to midnight on top of a snowy mountain pass, confetti.` |
| `bougie_1` | épique | Première année | `Subject: a birthday cupcake with one candle shaped like a bicycle, festive sparkles.` |
| `bougie_2` ★ | légendaire | Deux ans de route | `Subject: a birthday cake with two bicycle-shaped candles, magical sparkles, a road ribbon around the cake.` |

## 5. Contrôle avant de livrer

- Pas de texte, de chiffre, de logo, de drapeau ni de visage réel.
- Le sujet se reconnaît en petit (vignette de 128 px) et sur fond sombre comme sur fond clair.
- Le style est le même sur toute la planche (trait, ombres, saturation).
- Aucune donnée du cycliste dans les consignes : seulement le sujet de la carte.
