"""
AI Training Analysis Script - Arena of Life

Generates comprehensive HTML report with visualizations from training_stats.csv
Run: python analyze_training.py
Output: training_report.html
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server environments
from datetime import datetime
import os

# Configuration
CSV_FILE = "training_stats.csv"
OUTPUT_HTML = "training_report.html"
IMAGES_DIR = "analysis_plots"

# Create directory for plots
os.makedirs(IMAGES_DIR, exist_ok=True)

def load_data():
    """Load and parse training statistics CSV"""
    print("Chargement des donnees...")
    df = pd.read_csv(CSV_FILE)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    return df

def create_plot(title, filename):
    """Helper to create consistent plot styling"""
    plt.figure(figsize=(12, 6))
    plt.title(title, fontsize=16, fontweight='bold')
    plt.grid(True, alpha=0.3)
    return filename

def plot_loss_evolution(df):
    """Plot Loss over generations"""
    filename = f"{IMAGES_DIR}/loss_evolution.png"
    create_plot("Évolution de la Loss (Erreur d'apprentissage)", filename)
    
    plt.plot(df['Generation'], df['Loss'], color='#e74c3c', linewidth=1.5, alpha=0.7)
    # Moving average
    window = 50
    if len(df) >= window:
        ma = df['Loss'].rolling(window=window).mean()
        plt.plot(df['Generation'], ma, color='#c0392b', linewidth=2.5, label=f'Moyenne mobile ({window})')
        plt.legend()
    
    plt.xlabel('Génération', fontsize=12)
    plt.ylabel('Loss', fontsize=12)
    plt.tight_layout()
    plt.savefig(filename, dpi=100, bbox_inches='tight')
    plt.close()
    return filename

def plot_rewards_by_season(df):
    """Plot average rewards per season"""
    filename = f"{IMAGES_DIR}/rewards_by_season.png"
    create_plot("Récompenses moyennes par saison", filename)
    
    seasons = ['Spring', 'Summer', 'Autumn', 'Winter']
    colors = ['#2ecc71', '#f1c40f', '#e67e22', '#3498db']
    
    for season, color in zip(seasons, colors):
        season_data = df[df['Season'] == season]
        if len(season_data) > 0:
            plt.plot(season_data['Generation'], season_data['AvgReward'], 
                    label=season, color=color, linewidth=2, alpha=0.8)
    
    plt.xlabel('Génération', fontsize=12)
    plt.ylabel('Récompense Moyenne', fontsize=12)
    plt.legend(loc='best', fontsize=11)
    plt.tight_layout()
    plt.savefig(filename, dpi=100, bbox_inches='tight')
    plt.close()
    return filename

def plot_epsilon_decay(df):
    """Plot epsilon exploration rate"""
    filename = f"{IMAGES_DIR}/epsilon_decay.png"
    create_plot("Décroissance de l'Epsilon (Exploration → Exploitation)", filename)
    
    plt.plot(df['Generation'], df['Epsilon'], color='#9b59b6', linewidth=2)
    plt.axhline(y=0.05, color='red', linestyle='--', alpha=0.5, label='Cible (0.05)')
    
    plt.xlabel('Génération', fontsize=12)
    plt.ylabel('Epsilon', fontsize=12)
    plt.legend()
    plt.tight_layout()
    plt.savefig(filename, dpi=100, bbox_inches='tight')
    plt.close()
    return filename

def plot_kills_by_season(df):
    """Plot kills performance by season"""
    filename = f"{IMAGES_DIR}/kills_by_season.png"
    create_plot("Tueries (Prédateurs) par saison", filename)
    
    seasons = ['Spring', 'Summer', 'Autumn', 'Winter']
    colors = ['#2ecc71', '#f1c40f', '#e67e22', '#3498db']
    
    for season, color in zip(seasons, colors):
        season_data = df[df['Season'] == season]
        if len(season_data) > 0:
            plt.plot(season_data['Generation'], season_data['Kills'], 
                    label=season, color=color, linewidth=2, alpha=0.8, marker='o', markersize=3)
    
    plt.xlabel('Génération', fontsize=12)
    plt.ylabel('Nombre de Tueries', fontsize=12)
    plt.legend(loc='best', fontsize=11)
    plt.tight_layout()
    plt.savefig(filename, dpi=100, bbox_inches='tight')
    plt.close()
    return filename

def plot_cv_evolution(df):
    """Plot Coefficient of Variation"""
    filename = f"{IMAGES_DIR}/cv_evolution.png"
    create_plot("Coefficient de Variation (Diversité des stratégies)", filename)
    
    # Filter out 0.0 CV values for better visualization
    df_filtered = df[df['CV'] > 0]
    plt.plot(df_filtered['Generation'], df_filtered['CV'], color='#1abc9c', linewidth=1.5, alpha=0.7)
    
    plt.xlabel('Génération', fontsize=12)
    plt.ylabel('CV', fontsize=12)
    plt.tight_layout()
    plt.savefig(filename, dpi=100, bbox_inches='tight')
    plt.close()
    return filename

def plot_genhr_evolution(df):
    """Plot Generations per hour"""
    filename = f"{IMAGES_DIR}/genhr_evolution.png"
    create_plot("Générations par heure (Vitesse d'entraînement)", filename)
    
    df_filtered = df[df['Gen/h'] > 0]
    plt.plot(df_filtered['Generation'], df_filtered['Gen/h'], color='#34495e', linewidth=1.5, alpha=0.7)
    
    # Average line
    avg_genhr = df_filtered['Gen/h'].mean()
    plt.axhline(y=avg_genhr, color='#e74c3c', linestyle='--', 
                label=f'Moyenne: {avg_genhr:.1f} Gen/h', alpha=0.7)
    
    plt.xlabel('Génération', fontsize=12)
    plt.ylabel('Générations/heure', fontsize=12)
    plt.legend()
    plt.tight_layout()
    plt.savefig(filename, dpi=100, bbox_inches='tight')
    plt.close()
    return filename

def plot_class_survival(df):
    """Plot survival rates by agent class"""
    filename = f"{IMAGES_DIR}/class_survival.png"
    create_plot("Taux de survie par classe d'agent", filename)
    
    # Calculate survival rates (agents alive out of total 50)
    df['Warrior_Survival%'] = (df['Alive_War'] / 50) * 100
    df['Scout_Survival%'] = (df['Alive_Sco'] / 50) * 100
    df['Healer_Survival%'] = (df['Alive_Hea'] / 50) * 100
    
    plt.plot(df['Generation'], df['Warrior_Survival%'], label='Warrior', color='#e74c3c', linewidth=2, alpha=0.8)
    plt.plot(df['Generation'], df['Scout_Survival%'], label='Scout', color='#3498db', linewidth=2, alpha=0.8)
    plt.plot(df['Generation'], df['Healer_Survival%'], label='Healer', color='#2ecc71', linewidth=2, alpha=0.8)
    
    plt.xlabel('Génération', fontsize=12)
    plt.ylabel('Taux de survie (%)', fontsize=12)
    plt.legend(loc='best', fontsize=11)
    plt.ylim(0, 100)
    plt.tight_layout()
    plt.savefig(filename, dpi=100, bbox_inches='tight')
    plt.close()
    return filename

def plot_class_rewards(df):
    """Plot average rewards by agent class"""
    filename = f"{IMAGES_DIR}/class_rewards.png"
    create_plot("Récompenses moyennes par classe", filename)
    
    # Check if columns exist (for backward compatibility)
    if 'AvgReward_War' in df.columns:
        # Moving average for smoother visualization
        window = 50
        if len(df) >= window:
            df['War_Rew_MA'] = df['AvgReward_War'].rolling(window=window).mean()
            df['Sco_Rew_MA'] = df['AvgReward_Sco'].rolling(window=window).mean()
            df['Hea_Rew_MA'] = df['AvgReward_Hea'].rolling(window=window).mean()
            
            plt.plot(df['Generation'], df['War_Rew_MA'], label='Warrior', color='#e74c3c', linewidth=2.5)
            plt.plot(df['Generation'], df['Sco_Rew_MA'], label='Scout', color='#3498db', linewidth=2.5)
            plt.plot(df['Generation'], df['Hea_Rew_MA'], label='Healer', color='#2ecc71', linewidth=2.5)
        else:
            plt.plot(df['Generation'], df['AvgReward_War'], label='Warrior', color='#e74c3c', linewidth=1.5, alpha=0.7)
            plt.plot(df['Generation'], df['AvgReward_Sco'], label='Scout', color='#3498db', linewidth=1.5, alpha=0.7)
            plt.plot(df['Generation'], df['AvgReward_Hea'], label='Healer', color='#2ecc71', linewidth=1.5, alpha=0.7)
            
        plt.xlabel('Génération', fontsize=12)
        plt.ylabel('Récompense Moyenne', fontsize=12)
        plt.legend()
    else:
        plt.text(0.5, 0.5, "Données non disponibles pour les anciennes générations", 
                 horizontalalignment='center', verticalalignment='center', transform=plt.gca().transAxes)
    
    plt.tight_layout()
    plt.savefig(filename, dpi=100, bbox_inches='tight')
    plt.close()
    return filename

def plot_weapon_efficiency(df):
    """Plot kill efficiency by weapon type"""
    filename = f"{IMAGES_DIR}/weapon_efficiency.png"
    create_plot("Efficacité des armes (Tueries par type)", filename)
    
    # Moving average for smoother visualization
    window = 50
    if len(df) >= window:
        df['Sword_MA'] = df['Kills_Sword'].rolling(window=window).mean()
        df['Bow_MA'] = df['Kills_Bow'].rolling(window=window).mean()
        df['Wand_MA'] = df['Kills_Wand'].rolling(window=window).mean()
        
        plt.plot(df['Generation'], df['Sword_MA'], label='Épée (Warrior)', color='#c0392b', linewidth=2.5)
        plt.plot(df['Generation'], df['Bow_MA'], label='Arc (Scout)', color='#2980b9', linewidth=2.5)
        plt.plot(df['Generation'], df['Wand_MA'], label='Bâton (Healer)', color='#27ae60', linewidth=2.5)
    else:
        plt.plot(df['Generation'], df['Kills_Sword'], label='Épée (Warrior)', color='#c0392b', linewidth=1.5, alpha=0.7)
        plt.plot(df['Generation'], df['Kills_Bow'], label='Arc (Scout)', color='#2980b9', linewidth=1.5, alpha=0.7)
        plt.plot(df['Generation'], df['Kills_Wand'], label='Bâton (Healer)', color='#27ae60', linewidth=1.5, alpha=0.7)
    
    plt.xlabel('Génération', fontsize=12)
    plt.ylabel('Tueries (moyenne mobile)', fontsize=12)
    plt.legend(loc='best', fontsize=11)
    plt.tight_layout()
    plt.savefig(filename, dpi=100, bbox_inches='tight')
    plt.close()
    return filename

def plot_specific_rewards(df):
    """Plot specific rewards per class"""
    filename = f"{IMAGES_DIR}/specific_rewards.png"
    create_plot("Récompenses Spécifiques par Classe", filename)
    
    if 'AvgRew_Heal_Hea' in df.columns:
        # Moving average
        window = 50
        if len(df) >= window:
            df['Heal_MA'] = df['AvgRew_Heal_Hea'].rolling(window=window).mean()
            df['Combat_MA'] = df['AvgRew_Combat_War'].rolling(window=window).mean()
            df['Res_MA'] = df['AvgRew_Res_Sco'].rolling(window=window).mean()
            
            plt.plot(df['Generation'], df['Heal_MA'], label='Soin (Healer)', color='#2ecc71', linewidth=2.5)
            plt.plot(df['Generation'], df['Combat_MA'], label='Combat (Warrior)', color='#e74c3c', linewidth=2.5)
            plt.plot(df['Generation'], df['Res_MA'], label='Ressources (Scout)', color='#f1c40f', linewidth=2.5)
        else:
            plt.plot(df['Generation'], df['AvgRew_Heal_Hea'], label='Soin (Healer)', color='#2ecc71', alpha=0.7)
            plt.plot(df['Generation'], df['AvgRew_Combat_War'], label='Combat (Warrior)', color='#e74c3c', alpha=0.7)
            plt.plot(df['Generation'], df['AvgRew_Res_Sco'], label='Ressources (Scout)', color='#f1c40f', alpha=0.7)
            
        plt.xlabel('Génération', fontsize=12)
        plt.ylabel('Récompense Moyenne', fontsize=12)
        plt.legend(loc='best', fontsize=11)
    else:
        plt.text(0.5, 0.5, "Données non disponibles", ha='center', va='center')
        
    plt.tight_layout()
    plt.savefig(filename, dpi=100, bbox_inches='tight')
    plt.close()
    return filename

def plot_action_distribution(df):
    """Plot action distribution"""
    filename = f"{IMAGES_DIR}/action_distribution.png"
    create_plot("Distribution des Actions", filename)
    
    if 'Act_Move' in df.columns:
        # Stackplot
        generations = df['Generation']
        
        # Smooth data
        window = 50
        if len(df) >= window:
            move = df['Act_Move'].rolling(window=window).mean()
            attack = df['Act_Attack'].rolling(window=window).mean()
            wait = df['Act_Wait'].rolling(window=window).mean()
            shout = df['Act_Shout'].rolling(window=window).mean()
        else:
            move = df['Act_Move']
            attack = df['Act_Attack']
            wait = df['Act_Wait']
            shout = df['Act_Shout']
            
        plt.stackplot(generations, move, attack, wait, shout, 
                     labels=['Mouvement', 'Attaque', 'Attente/Craft', 'Cri (Comms)'],
                     colors=['#3498db', '#e74c3c', '#95a5a6', '#9b59b6'], alpha=0.8)
                     
        plt.xlabel('Génération', fontsize=12)
        plt.ylabel('Pourcentage (%)', fontsize=12)
        plt.legend(loc='upper left', fontsize=10)
        plt.ylim(0, 100)
    else:
        plt.text(0.5, 0.5, "Données non disponibles", ha='center', va='center')
        
    plt.tight_layout()
    plt.savefig(filename, dpi=100, bbox_inches='tight')
    plt.close()
    return filename

def plot_general_behavior(df):
    """Plot general agent behavior metrics"""
    filename = f"{IMAGES_DIR}/general_behavior.png"
    create_plot("Comportement général des agents", filename)
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    
    # Survival rate over time
    df['Total_Alive'] = df['Alive_War'] + df['Alive_Sco'] + df['Alive_Hea']
    df['Survival_Rate%'] = (df['Total_Alive'] / 50) * 100
    
    window = 50
    if len(df) >= window:
        survival_ma = df['Survival_Rate%'].rolling(window=window).mean()
        ax1.plot(df['Generation'], survival_ma, color='#9b59b6', linewidth=2.5, label=f'Moyenne mobile ({window})')
    ax1.plot(df['Generation'], df['Survival_Rate%'], color='#9b59b6', linewidth=1, alpha=0.4, label='Brut')
    ax1.set_ylabel('Taux de survie global (%)', fontsize=11)
    ax1.set_title('Taux de survie des agents', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='best')
    
    # Exploration vs Exploitation (based on Epsilon)
    ax2.fill_between(df['Generation'], 0, df['Epsilon']*100, alpha=0.3, color='#f39c12', label='Exploration')
    ax2.fill_between(df['Generation'], df['Epsilon']*100, 100, alpha=0.3, color='#16a085', label='Exploitation')
    ax2.plot(df['Generation'], df['Epsilon']*100, color='#e67e22', linewidth=2, label='Epsilon')
    ax2.set_xlabel('Génération', fontsize=11)
    ax2.set_ylabel('Pourcentage', fontsize=11)
    ax2.set_title('Exploration vs Exploitation', fontsize=13, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='best')
    ax2.set_ylim(0, 100)
    
    plt.tight_layout()
    plt.savefig(filename, dpi=100, bbox_inches='tight')
    plt.close()
    return filename

def calculate_metrics(df):
    """Calculate key metrics and anomalies"""
    metrics = {
        'total_generations': len(df),
        'max_generation': df['Generation'].max() if len(df) > 0 else 0,
        'current_epsilon': df['Epsilon'].iloc[-1],
        'current_loss': df['Loss'].iloc[-1],
        'loss_trend': 'Baisse ✅' if df['Loss'].iloc[-1] < df['Loss'].iloc[0] else 'Hausse ⚠️',
        'training_duration': (df['Timestamp'].iloc[-1] - df['Timestamp'].iloc[0]).total_seconds() / 3600,
    }
    
    # Season-specific metrics
    season_stats = {}
    for season in ['Spring', 'Summer', 'Autumn', 'Winter']:
        season_data = df[df['Season'] == season]
        if len(season_data) > 0:
            season_stats[season] = {
                'avg_reward': season_data['AvgReward'].mean(),
                'max_reward': season_data['MaxReward'].max(),
                'avg_kills': season_data['Kills'].mean(),
                'total_gens': len(season_data)
            }
    
    metrics['season_stats'] = season_stats
    
    # Class-specific metrics (NEW)
    class_stats = {
        'Warrior': {
            'avg_alive': df['Alive_War'].mean(),
            'survival_rate': (df['Alive_War'].mean() / 50) * 100,
            'total_kills': df['Kills_Sword'].sum(),
            'avg_kills': df['Kills_Sword'].mean(),
            'avg_reward': df['AvgReward_War'].mean() if 'AvgReward_War' in df.columns else 0,
        },
        'Scout': {
            'avg_alive': df['Alive_Sco'].mean(),
            'survival_rate': (df['Alive_Sco'].mean() / 50) * 100,
            'total_kills': df['Kills_Bow'].sum(),
            'avg_kills': df['Kills_Bow'].mean(),
            'avg_reward': df['AvgReward_Sco'].mean() if 'AvgReward_Sco' in df.columns else 0,
        },
        'Healer': {
            'avg_alive': df['Alive_Hea'].mean(),
            'survival_rate': (df['Alive_Hea'].mean() / 50) * 100,
            'total_kills': df['Kills_Wand'].sum(),
            'avg_kills': df['Kills_Wand'].mean(),
            'avg_reward': df['AvgReward_Hea'].mean() if 'AvgReward_Hea' in df.columns else 0,
        }
    }
    
    metrics['class_stats'] = class_stats
    
    # General behavior metrics (NEW)
    df['Total_Alive'] = df['Alive_War'] + df['Alive_Sco'] + df['Alive_Hea']
    metrics['avg_survival_rate'] = (df['Total_Alive'].mean() / 50) * 100
    metrics['exploration_rate'] = df['Epsilon'].mean() * 100
    
    # Anomaly detection
    anomalies = []
    
    # Check if loss is increasing (last 100 vs previous 100)
    if len(df) >= 200:
        recent_loss = df['Loss'].iloc[-100:].mean()
        prev_loss = df['Loss'].iloc[-200:-100].mean()
        if recent_loss > prev_loss * 1.1:
            anomalies.append("🔴 Loss en augmentation récente (possible régression)")
    
    # Check if Spring/Summer/Winter rewards are stagnant
    for season in ['Spring', 'Summer', 'Winter']:
        if season in season_stats and season_stats[season]['avg_reward'] < 150:
            anomalies.append(f"🟡 {season}: Récompenses faibles (< 150)")
    
    # Check if Autumn is dominating too much
    if 'Autumn' in season_stats:
        autumn_reward = season_stats['Autumn']['avg_reward']
        other_seasons = [s for s in season_stats if s != 'Autumn']
        if other_seasons:
            other_avg = sum(season_stats[s]['avg_reward'] for s in other_seasons) / len(other_seasons)
            if other_avg > 0 and autumn_reward > other_avg * 3:
                anomalies.append(f"🟠 Automne domine trop (x{autumn_reward/other_avg:.1f} les autres saisons)")
    
    if not anomalies:
        anomalies.append("🟢 Aucune anomalie détectée")
    
    metrics['anomalies'] = anomalies
    
    # Correlations
    # Helper to safely calculate correlation
    def get_corr(col1, col2):
        if col1 in df.columns and col2 in df.columns:
            return df[col1].corr(df[col2])
        return 0.0

    metrics['correlations'] = {
        'shout_reward': get_corr('Act_Shout', 'AvgReward'),
        'attack_reward': get_corr('Act_Attack', 'AvgReward'),
        'healer_impact': get_corr('AvgRew_Heal_Hea', 'Alive_War'),
        'healer_contribution': get_corr('AvgRew_Heal_Hea', 'AvgReward'),
        'warrior_contribution': get_corr('AvgRew_Combat_War', 'AvgReward'),
        'scout_contribution': get_corr('AvgRew_Res_Sco', 'AvgReward'),
        'scout_survival': get_corr('Act_Move', 'Alive_Sco'),
        'resources_reward': df['Total_Wood'].corr(df['AvgReward']) if 'Total_Wood' in df.columns else 0.0 # Simplified approximation
    }
    # Better resource correlation (sum of wood + iron)
    if 'Total_Wood' in df.columns and 'Total_Iron' in df.columns:
        df['Total_Res'] = df['Total_Wood'] + df['Total_Iron']
        metrics['correlations']['resources_reward'] = df['Total_Res'].corr(df['AvgReward'])

    return metrics

def plot_correlations(df):
    """Generate correlation plots"""
    plots = {}
    
    # 1. Correlation Heatmap
    filename_heatmap = f"{IMAGES_DIR}/correlation_heatmap.png"
    create_plot("Matrice de Corrélation", filename_heatmap)
    
    # Select relevant columns for heatmap
    cols = ['AvgReward', 'Loss', 'Kills', 'Act_Shout', 'Act_Attack', 'Act_Move']
    if 'AvgRew_Heal_Hea' in df.columns: cols.append('AvgRew_Heal_Hea')
    if 'AvgRew_Combat_War' in df.columns: cols.append('AvgRew_Combat_War')
    if 'AvgRew_Res_Sco' in df.columns: cols.append('AvgRew_Res_Sco')
    
    # Filter existing columns
    valid_cols = [c for c in cols if c in df.columns]
    corr_matrix = df[valid_cols].corr()
    
    plt.imshow(corr_matrix, cmap='coolwarm', interpolation='nearest')
    plt.colorbar()
    plt.xticks(range(len(valid_cols)), valid_cols, rotation=45, ha='right')
    plt.yticks(range(len(valid_cols)), valid_cols)
    
    # Add values
    for i in range(len(valid_cols)):
        for j in range(len(valid_cols)):
            plt.text(j, i, f"{corr_matrix.iloc[i, j]:.2f}", 
                     ha="center", va="center", color="black", fontsize=8)
            
    plt.tight_layout()
    plt.savefig(filename_heatmap, dpi=100, bbox_inches='tight')
    plt.close()
    plots['heatmap'] = filename_heatmap

    # 2. Scatter Plots
    def create_scatter(x_col, y_col, title, filename, color):
        if x_col not in df.columns or y_col not in df.columns:
            return None
            
        full_path = f"{IMAGES_DIR}/{filename}"
        create_plot(title, full_path)
        
        plt.scatter(df[x_col], df[y_col], alpha=0.5, color=color)
        
        # Trend line
        import numpy as np
        if len(df) > 1:
            z = np.polyfit(df[x_col], df[y_col], 1)
            p = np.poly1d(z)
            plt.plot(df[x_col], p(df[x_col]), "r--", alpha=0.8)
        
        plt.xlabel(x_col)
        plt.ylabel(y_col)
        plt.tight_layout()
        plt.savefig(full_path, dpi=100, bbox_inches='tight')
        plt.close()
        return full_path

    plots['shout_vs_reward'] = create_scatter('Act_Shout', 'AvgReward', 
                                            'Communication vs Récompense', 'corr_shout_reward.png', '#9b59b6')
                                            
    plots['healer_impact'] = create_scatter('AvgRew_Heal_Hea', 'Alive_War', 
                                          'Soin (Healer) vs Survie (Warrior)', 'corr_healer_warrior.png', '#2ecc71')
                                          
    plots['warrior_impact'] = create_scatter('AvgRew_Combat_War', 'AvgReward', 
                                           'Combat (Warrior) vs Récompense Globale', 'corr_warrior_reward.png', '#e74c3c')
                                           
    plots['scout_impact'] = create_scatter('AvgRew_Res_Sco', 'AvgReward', 
                                         'Ressources (Scout) vs Récompense Globale', 'corr_scout_reward.png', '#f1c40f')

    return plots

def generate_html_report(df, metrics, plot_files):
    """Generate comprehensive HTML report"""
    print("Generation du rapport HTML...")
    
    # Season stats HTML
    season_table = ""
    for season, stats in metrics['season_stats'].items():
        emoji = {'Spring': '🌿', 'Summer': '🔥', 'Autumn': '🍂', 'Winter': '❄️'}[season]
        season_table += f"""
        <tr>
            <td>{emoji} {season}</td>
            <td>{stats['avg_reward']:.1f}</td>
            <td>{stats['max_reward']:.1f}</td>
            <td>{stats['avg_kills']:.1f}</td>
            <td>{stats['total_gens']}</td>
        </tr>
        """
    
    # Class stats HTML (NEW)
    class_table = ""
    for class_name, stats in metrics['class_stats'].items():
        emoji = {'Warrior': '⚔️', 'Scout': '🏹', 'Healer': '🔮'}[class_name]
        class_table += f"""
        <tr>
            <td>{emoji} {class_name}</td>
            <td>{stats['avg_alive']:.1f}</td>
            <td>{stats['survival_rate']:.1f}%</td>
            <td>{stats['total_kills']}</td>
            <td>{stats['avg_kills']:.2f}</td>
            <td>{stats['avg_reward']:.2f}</td>
        </tr>
        """
        
    # Correlations HTML
    corr = metrics['correlations']
    def format_corr(val):
        color = "green" if val > 0.3 else "red" if val < -0.3 else "gray"
        return f"<span style='color:{color}; font-weight:bold'>{val:.2f}</span>"

    correlation_table = f"""
    <tr><td>🗣️ Communication -> Récompense</td><td>{format_corr(corr['shout_reward'])}</td></tr>
    <tr><td>⚔️ Combat -> Récompense</td><td>{format_corr(corr['attack_reward'])}</td></tr>
    <tr><td>🔮 Soin -> Survie Warrior</td><td>{format_corr(corr['healer_impact'])}</td></tr>
    <tr><td>🔮 Soin -> Récompense Globale</td><td>{format_corr(corr['healer_contribution'])}</td></tr>
    <tr><td>⚔️ Warrior Combat -> Récompense</td><td>{format_corr(corr['warrior_contribution'])}</td></tr>
    <tr><td>🏹 Scout Ressources -> Récompense</td><td>{format_corr(corr['scout_contribution'])}</td></tr>
    <tr><td>🏃 Scout Mouvement -> Survie</td><td>{format_corr(corr['scout_survival'])}</td></tr>
    <tr><td>🌲 Ressources -> Récompense</td><td>{format_corr(corr['resources_reward'])}</td></tr>
    """
    
    # Anomalies HTML
    anomalies_html = "<br>".join(metrics['anomalies'])
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Rapport d'Entraînement - Arena of Life AI</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                margin: 0;
                padding: 20px;
                color: #333;
            }}
            .container {{
                max-width: 1400px;
                margin: 0 auto;
                background: white;
                border-radius: 15px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                padding: 40px;
            }}
            h1 {{
                color: #2c3e50;
                text-align: center;
                font-size: 2.5em;
                margin-bottom: 10px;
            }}
            .timestamp {{
                text-align: center;
                color: #7f8c8d;
                margin-bottom: 30px;
                font-size: 0.95em;
            }}
            .metrics-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin: 30px 0;
            }}
            .metric-card {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            }}
            .metric-card h3 {{
                margin: 0 0 10px 0;
                font-size: 0.95em;
                opacity: 0.9;
            }}
            .metric-card .value {{
                font-size: 2em;
                font-weight: bold;
                margin: 0;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ecf0f1;
            }}
            th {{
                background: #34495e;
                color: white;
                font-weight: 600;
            }}
            tr:hover {{
                background: #f8f9fa;
            }}
            .plot {{
                margin: 30px 0;
                text-align: center;
            }}
            .plot img {{
                max-width: 100%;
                border-radius: 10px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            }}
            .anomalies {{
                background: #fff3cd;
                border-left: 5px solid #ffc107;
                padding: 20px;
                margin: 20px 0;
                border-radius: 5px;
            }}
            .anomalies h2 {{
                margin-top: 0;
                color: #856404;
            }}
            .section {{
                margin: 40px 0;
            }}
            .section h2 {{
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
            }}
            .grid-2 {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏆 Rapport d'Entraînement IA</h1>
            <div class="timestamp">
                Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}<br>
                Données: {metrics['total_generations']} générations sur {metrics['training_duration']:.1f} heures
            </div>
            
            <div class="metrics-grid">
                <div class="metric-card">
                    <h3>📊 Générations Totales</h3>
                    <p class="value">{metrics['total_generations']}</p>
                </div>
                <div class="metric-card">
                    <h3>🎯 Epsilon Actuel</h3>
                    <p class="value">{metrics['current_epsilon']:.3f}</p>
                </div>
                <div class="metric-card">
                    <h3>📉 Loss Actuelle</h3>
                    <p class="value">{metrics['current_loss']:.1f}</p>
                </div>
                <div class="metric-card">
                    <h3>📈 Tendance Loss</h3>
                    <p class="value" style="font-size: 1.5em;">{metrics['loss_trend']}</p>
                </div>
                <div class="metric-card">
                    <h3>🛡️ Survie Moyenne</h3>
                    <p class="value">{metrics['avg_survival_rate']:.1f}%</p>
                </div>
                <div class="metric-card">
                    <h3>🔍 Taux d'Exploration</h3>
                    <p class="value">{metrics['exploration_rate']:.1f}%</p>
                </div>
            </div>
            
            <div class="anomalies">
                <h2>⚠️ Alertes & Observations</h2>
                {anomalies_html}
            </div>

            <div class="section">
                <h2>🔗 Analyse des Corrélations (Facteurs de succès)</h2>
                <div class="grid-2">
                    <div>
                        <table>
                            <thead>
                                <tr>
                                    <th>Relation</th>
                                    <th>Corrélation (Pearson)</th>
                                </tr>
                            </thead>
                            <tbody>
                                {correlation_table}
                            </tbody>
                        </table>
                        <p><em>Note: 1.0 = Corrélation parfaite, 0.0 = Aucun lien, -1.0 = Corrélation inverse</em></p>
                    </div>
                    <div class="plot">
                        <img src="{plot_files['heatmap']}" alt="Heatmap Corrélation">
                    </div>
                </div>
                
                <div class="grid-2">
                    <div class="plot"><img src="{plot_files['shout_vs_reward']}" alt="Shout vs Reward"></div>
                    <div class="plot"><img src="{plot_files['healer_impact']}" alt="Healer Impact"></div>
                    <div class="plot"><img src="{plot_files['warrior_impact']}" alt="Warrior Impact"></div>
                    <div class="plot"><img src="{plot_files['scout_impact']}" alt="Scout Impact"></div>
                </div>
            </div>
            
            <div class="section">
                <h2>🤖 Statistiques par Classe d'Agent</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Classe</th>
                            <th>Agents Vivants (Moy.)</th>
                            <th>Taux de Survie</th>
                            <th>Tueries Totales</th>
                            <th>Tueries Moy. / Gen</th>
                            <th>Récompense Moy.</th>
                        </tr>
                    </thead>
                    <tbody>
                        {class_table}
                    </tbody>
                </table>
            </div>
            
            <div class="section">
                <h2>📊 Statistiques par Saison</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Saison</th>
                            <th>Récompense Moy.</th>
                            <th>Récompense Max</th>
                            <th>Tueries Moy.</th>
                            <th>Générations</th>
                        </tr>
                    </thead>
                    <tbody>
                        {season_table}
                    </tbody>
                </table>
            </div>
            
            <div class="section">
                <h2>📈 Graphiques d'Évolution</h2>
                
                <div class="plot">
                    <img src="{plot_files['general_behavior']}" alt="General Behavior">
                </div>
                
                <div class="plot">
                    <img src="{plot_files['class_survival']}" alt="Class Survival Rates">
                </div>

                <div class="plot">
                    <img src="{plot_files['class_rewards']}" alt="Class Rewards">
                </div>
                
                <div class="plot">
                    <img src="{plot_files['weapon_efficiency']}" alt="Weapon Kill Efficiency">
                </div>
                
                <div class="plot">
                    <img src="{plot_files['loss']}" alt="Loss Evolution">
                </div>
                
                <div class="plot">
                    <img src="{plot_files['rewards']}" alt="Rewards by Season">
                </div>
                
                <div class="plot">
                    <img src="{plot_files['epsilon']}" alt="Epsilon Decay">
                </div>
                
                <div class="plot">
                    <img src="{plot_files['kills']}" alt="Kills by Season">
                </div>
                
                <div class="plot">
                    <img src="{plot_files['cv']}" alt="CV Evolution">
                </div>
                
                <div class="plot">
                    <img src="{plot_files['genhr']}" alt="Generations per Hour">
                </div>

                <div class="plot">
                    <img src="{plot_files['specific_rewards']}" alt="Specific Rewards">
                </div>

                <div class="plot">
                    <img src="{plot_files['action_distribution']}" alt="Action Distribution">
                </div>
            </div>
            
            <div style="text-align: center; margin-top: 50px; color: #7f8c8d;">
                <p>🤖 Arena of Life - AI Training Monitor</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"[OK] Rapport genere: {OUTPUT_HTML}")

def main():
    """Main execution flow"""
    print("=" * 60)
    print("ARENA OF LIFE - AI TRAINING ANALYZER")
    print("=" * 60)
    
    # Load data
    df = load_data()
    print(f"[OK] {len(df)} generations chargees")
    
    # Generate plots
    print("\nGeneration des graphiques...")
    plot_files = {
        'general_behavior': plot_general_behavior(df),
        'class_survival': plot_class_survival(df),
        'class_rewards': plot_class_rewards(df),
        'weapon_efficiency': plot_weapon_efficiency(df),
        'loss': plot_loss_evolution(df),
        'rewards': plot_rewards_by_season(df),
        'epsilon': plot_epsilon_decay(df),
        'kills': plot_kills_by_season(df),
        'cv': plot_cv_evolution(df),
        'genhr': plot_genhr_evolution(df),
        'specific_rewards': plot_specific_rewards(df),
        'action_distribution': plot_action_distribution(df),
    }
    
    # Add correlation plots
    corr_plots = plot_correlations(df)
    plot_files.update(corr_plots)
    
    print("[OK] Graphiques crees")
    
    # Calculate metrics
    print("\nAnalyse des metriques...")
    metrics = calculate_metrics(df)
    print("[OK] Metriques calculees")
    
    # Generate HTML report
    print("\n" + "=" * 60)
    generate_html_report(df, metrics, plot_files)
    print("=" * 60)
    print(f"\n[SUCCESS] Analyse terminee ! Ouvrez '{OUTPUT_HTML}' dans votre navigateur.")
    
if __name__ == "__main__":
    main()
