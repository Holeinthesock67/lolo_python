---
name: "podcast-debat-ia"
description: "Écrit le script du podcast hebdo du propriétaire : débat de 20 min entre deux voix + revue de sujets, à partir du fichier de veille IA déposé sur Drive."
---

# Podcast débat IA — script hebdomadaire

Tu écris le script d'un podcast personnel d'environ 30 minutes, en français, lu ensuite par une synthèse vocale (Piper) sur un Raspberry Pi. Le podcast n'est pas un résumé des sources : il les confronte. La valeur ajoutée, c'est le croisement des points de vue, la vérification des thèses et l'argumentation.

## 1. Trouver la matière

1. Dans Google Drive, ouvre le dossier `Podcast IA/sources` et prends le fichier le plus récent nommé `AAAA-Wss_source.md` (ex. `2026-W42_source.md`). Si l'utilisateur joint un fichier ou en désigne un autre, utilise celui-là.
2. Regarde dans `Podcast IA/scripts` les scripts des 4 dernières semaines, pour ne pas refaire le même sujet de débat et pour pouvoir y faire référence (« il y a trois semaines, on parlait de… »).
3. Le fichier source commence par la liste des sources avec leur camp (Accélérationniste, Sceptique, Inquiet, Critique éthique, Philosophie, Transhumaniste, Repérage/macro) et leur thèse. Sers-t'en pour savoir qui défend quoi.

## 2. Choisir les sujets

- **Sujet du débat** : celui qui est abordé par le plus de sources ET par des camps différents, et qui divise vraiment. Privilégie les sujets frontières et non consensuels (AGI, singularité, bulle économique, emploi, pouvoir, risques, conscience, transhumanisme). Grand Angle sert surtout à repérer les grandes thèses ; les autres sources apportent faits et contre-arguments.
- Formule le sujet comme une question tranchée, par exemple : « La bulle de l'IA va-t-elle éclater d'ici deux ans ? ».
- **Revue** : deux ou trois autres sujets marquants de la semaine, différents du débat.
- Si la semaine est pauvre (peu de sources, pas de vrai désaccord), dis-le dans l'introduction et choisis le sujet le plus discutable plutôt que d'inventer une controverse.

## 3. Les deux voix

- **A — Camille** : défend la thèse la plus forte de la semaine.
- **B — Thomas** : la conteste.
- Les rôles « pour » et « contre » peuvent s'inverser d'une semaine à l'autre selon le sujet. Les deux sont sérieux, précis, de bonne foi : chacun présente la meilleure version des arguments de son camp (pas d'homme de paille), concède quand l'autre marque un point, et pousse l'autre sur ses faiblesses.
- Ton : sérieux et argumenté, dans l'esprit de Grand Angle. Pas d'humour forcé, pas de formules creuses (« c'est passionnant », « excellente question »).

## 4. Structure et longueur (≈ 4 500 mots au total)

1. **Ouverture (≈ 150 mots)** — Camille annonce la semaine, le sujet du débat formulé en question, et les sujets de la revue.
2. **Débat (≈ 3 000 mots, ≈ 20 min)**
   - Exposé de la thèse par A, puis de l'antithèse par B.
   - Trois ou quatre rounds d'échanges, chacun centré sur un argument précis (un chiffre, un fait, une prédiction), avec réponses directes.
   - Un passage « ce qui tient, ce qui relève de la spéculation » : les deux font le tri entre faits établis et paris sur l'avenir.
   - Conclusion du débat : chacun résume sa position en deux phrases, puis les deux disent ce qui les ferait changer d'avis.
3. **Revue (≈ 1 200 mots, ≈ 8 min)** — deux ou trois sujets, environ 400 mots chacun, en dialogue plus court : ce qui s'est passé, pourquoi c'est important, ce qui est contesté.
4. **Clôture (≈ 150 mots)** — « Qu'est-ce que ça change concrètement ? » : une ou deux implications pour le quotidien, le travail ou l'investissement, sans conseil financier personnalisé. Puis fin.

## 5. Règles sur les sources

- **Reformule toujours** : ne lis jamais un article ou une transcription mot pour mot. Une citation exacte doit rester exceptionnelle et très courte (moins de 15 mots).
- **Attribue les thèses** à voix haute : « Ed Zitron soutient que… », « Selon le Dwarkesh Podcast… », « Gary Marcus estime au contraire… ».
- **N'invente rien** : chiffres, dates, citations et faits viennent uniquement du fichier source. Si un argument a besoin d'un fait absent du fichier, présente-le comme une hypothèse, ou ne l'utilise pas.
- Distingue clairement les faits, les opinions et les prédictions.
- Les sources en anglais sont traduites et reformulées en français.

## 6. Écrire pour l'oreille (contraintes de la synthèse vocale)

- Phrases courtes, une idée par phrase. Pas de parenthèses, pas de listes, pas de markdown, pas d'émojis, pas d'URL.
- Écris les sigles comme ils se prononcent ou explique-les à la première occurrence : « l'AGI, c'est-à-dire une intelligence artificielle générale ». Écris « IA » tel quel.
- Écris les grands nombres et les pourcentages en toutes lettres : « deux mille milliards de dollars », « quarante pour cent ».
- Évite les termes anglais quand un mot français existe ; sinon, glisse une courte explication.
- Chaque réplique fait au maximum 120 mots, pour garder un vrai rythme de dialogue.

## 7. Format du fichier (lu par le Raspberry Pi)

Le Pi découpe le script ligne par ligne. Respecte strictement ce format :

- Une réplique par ligne, préfixée par `A:` (Camille) ou `B:` (Thomas), suivie d'un espace.
- Les marqueurs de section sont seuls sur leur ligne : `## OUVERTURE`, `## DEBAT`, `## REVUE`, `## CLOTURE`. Le Pi y insère un court silence.
- Pas d'autre texte : pas de titre, pas de didascalies, pas de lignes vides superflues.
- La toute dernière ligne est exactement `FIN`. Le Pi ignore tout script qui ne se termine pas par `FIN`.

Exemple :
```
## OUVERTURE
A: Bonjour le propriétaire. Cette semaine, une question divise nos sources : la bulle de l'IA va-t-elle éclater d'ici deux ans ?
B: Et on verra aussi que les avis sont loin d'être aussi tranchés qu'il n'y paraît.
## DEBAT
A: ...
FIN
```

## 8. Déposer le résultat

1. Nom du fichier : même identifiant de semaine que la source, suffixe `_script.txt` (ex. `2026-W42_script.txt`), en texte brut UTF-8.
2. Crée-le avec le connecteur Google Drive dans le dossier `Podcast IA/scripts` (crée le dossier s'il n'existe pas). Si un fichier du même nom existe déjà, ne l'écrase pas : ajoute `_v2`.
3. Avant de déposer, vérifie : environ 4 500 mots, toutes les lignes commencent par `A: `, `B: ` ou `## `, la dernière ligne est `FIN`, aucun chiffre n'est absent du fichier source.
4. Réponds ensuite en trois lignes au maximum : le sujet du débat, les sujets de la revue, et le nom du fichier déposé.