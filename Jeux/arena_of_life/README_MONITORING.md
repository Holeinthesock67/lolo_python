# 📊 Outil de Monitoring IA - Guide d'Utilisation

## 🚀 Utilisation Rapide

### Lancer l'analyse
```bash
python analyze_training.py
```

### Résultat
Le script génère automatiquement :
- ✅ **`training_report.html`** : Rapport complet avec graphiques
- ✅ **`analysis_plots/`** : Dossier contenant 6 graphiques PNG

## 📈 Graphiques Générés

1. **Loss Evolution** - Erreur d'apprentissage (doit descendre)
2. **Rewards by Season** - Performance par saison
3. **Epsilon Decay** - Progression exploration → exploitation
4. **Kills by Season** - Efficacité de combat
5. **CV Evolution** - Diversité des stratégies
6. **Generations/Hour** - Vitesse d'entraînement

## 🔍 Métriques Analysées

- **Générations totales** et durée d'entraînement
- **Epsilon actuel** et tendance
- **Loss actuelle** et évolution
- **Statistiques par saison** (récompenses moyennes, max, tueries)
- **Détection d'anomalies automatique**

## ⚠️ Alertes Automatiques

Le script détecte automatiquement :
- 🔴 Loss en augmentation (régression possible)
- 🟡 Récompenses faibles sur Spring/Summer/Winter
- 🟠 Automne qui domine trop les autres saisons
- 🟢 Aucune anomalie détectée

## 📊 Comment Surveiller l'Entraînement

### Option 1 : Manuel
Lancez le script quand vous voulez vérifier la progression :
```bash
python analyze_training.py
```

### Option 2 : Automatique (Planification Windows)
**Créer une tâche planifiée** qui lance le script toutes les heures :

1. Ouvrir **Planificateur de tâches** Windows
2. Créer une nouvelle tâche
3. Déclencheur : Toutes les heures
4. Action : `python C:\Users\laure\lolo_python\Jeux\arena_of_life\analyze_training.py`

### Option 3 : Surveillance Continue
Créer un script batch qui boucle :
```batch
@echo off
:loop
python analyze_training.py
timeout /t 3600
goto loop
```

## 🎯 Quand Agir ?

### Continuer l'entraînement si :
- ✅ Loss continue de baisser
- ✅ Epsilon > 0.10 (encore en exploration)
- ✅ Amélioration visible sur Spring/Summer/Winter

### Intervenir si :
- ⚠️ Loss remonte pendant plus de 500 générations
- ⚠️ Aucune amélioration après 2000+ générations
- ⚠️ Automne domine trop (>5x les autres saisons)

## 📁 Fichiers Générés

```
arena_of_life/
├── training_stats.csv          # Données brutes
├── analyze_training.py         # Script d'analyse
├── training_report.html        # Rapport (OUVRIR DANS NAVIGATEUR)
└── analysis_plots/             # Graphiques PNG
    ├── loss_evolution.png
    ├── rewards_by_season.png
    ├── epsilon_decay.png
    ├── kills_by_season.png
    ├── cv_evolution.png
    └── genhr_evolution.png
```

## 🛠️ Dépendances Requises

Le script utilise :
- `pandas` - Manipulation de données
- `matplotlib` - Génération de graphiques

Si manquant, installer avec :
```bash
pip install pandas matplotlib
```

## 💡 Astuces

- **Comparer les rapports** : Renommez `training_report.html` avant de relancer pour garder l'historique
- **Partager** : Le rapport HTML est autonome, vous pouvez l'envoyer par email
- **Personnaliser** : Éditez `analyze_training.py` pour ajouter vos propres métriques
