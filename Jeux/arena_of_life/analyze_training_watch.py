"""
AI Training Analysis Script - Arena of Life (WATCH MODE)

Surveille training_stats.csv et regénère automatiquement le rapport
Run: python analyze_training_watch.py
Output: training_report.html (mis à jour automatiquement)
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
from datetime import datetime
import os
import time
from pathlib import Path

# Import functions from the main analyzer
import sys
sys.path.append(os.path.dirname(__file__))

# Configuration
CSV_FILE = "training_stats.csv"
OUTPUT_HTML = "training_report.html"
IMAGES_DIR = "analysis_plots"
WATCH_INTERVAL = 900  # 15 minutes between checks

def get_file_modified_time(filepath):
    """Get last modification time of file"""
    try:
        return os.path.getmtime(filepath)
    except:
        return 0

def clear_screen():
    """Clear console screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def main_watch():
    """Watch mode - continuously monitor and regenerate report"""
    print("="*70)
    print("  ARENA OF LIFE - AI TRAINING ANALYZER (MODE SURVEILLANCE)")
    print("="*70)
    print(f"\nSurveillance active:")
    print(f"  - Fichier: {CSV_FILE}")
    print(f"  - Intervalle: {WATCH_INTERVAL} secondes")
    print(f"  - Rapport: {OUTPUT_HTML}")
    print("\nAppuyez sur Ctrl+C pour arrêter\n")
    print("="*70)
    
    last_modified = 0
    generation_count = 0
    
    try:
        while True:
            current_modified = get_file_modified_time(CSV_FILE)
            
            # Check if file has been modified
            if current_modified > last_modified:
                last_modified = current_modified
                generation_count += 1
                
                # Clear screen and show status
                clear_screen()
                print("="*70)
                print("  ARENA OF LIFE - AI TRAINING ANALYZER (MODE SURVEILLANCE)")
                print("="*70)
                print(f"\n⏰ {datetime.now().strftime('%H:%M:%S')} - Nouveau données détectées!")
                print(f"📊 Régénération #{generation_count} en cours...\n")
                
                try:
                    # Import and run the analyzer
                    from analyze_training import (
                        load_data, plot_loss_evolution, plot_rewards_by_season,
                        plot_epsilon_decay, plot_kills_by_season, plot_cv_evolution,
                        plot_genhr_evolution, plot_class_survival, plot_weapon_efficiency,
                        plot_general_behavior, plot_class_rewards, plot_specific_rewards, 
                        plot_action_distribution, plot_correlations, calculate_metrics, generate_html_report
                    )
                    
                    # Create plots directory
                    os.makedirs(IMAGES_DIR, exist_ok=True)
                    
                    # Load data
                    df = load_data()
                    print(f"   ✓ {len(df)} générations chargées")
                    
                    # Generate plots (silently)
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
                    
                    print(f"   ✓ Graphiques générés (incluant corrélations)")
                    
                    # Calculate metrics
                    metrics = calculate_metrics(df)
                    print(f"   ✓ Métriques calculées")
                    
                    # Generate HTML
                    generate_html_report(df, metrics, plot_files)
                    print(f"   ✓ Rapport HTML mis à jour")
                    
                    # Summary
                    print(f"\n📈 Statistiques actuelles:")
                    print(f"   • Génération Actuelle: {metrics['max_generation']} (Données: {metrics['total_generations']})")
                    print(f"   • Epsilon: {metrics['current_epsilon']:.3f}")
                    print(f"   • Loss: {metrics['current_loss']:.1f}")
                    print(f"   • Survie moyenne: {metrics['avg_survival_rate']:.1f}%")
                    
                    print(f"\n✅ Rapport mis à jour avec succès!")
                    
                except Exception as e:
                    print(f"\n❌ Erreur lors de la génération: {e}")
                
                print(f"\n{'='*70}")
                print(f"⏳ Prochaine vérification dans {WATCH_INTERVAL} secondes...")

                
            else:
                # Show waiting status
                print(f"\r⏳ En attente de nouvelles données... {datetime.now().strftime('%H:%M:%S')}", end='', flush=True)
            
            # Wait before next check
            time.sleep(WATCH_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n" + "="*70)
        print("👋 Surveillance arrêtée par l'utilisateur")
        print(f"📊 Total de régénérations: {generation_count}")
        print("="*70)

if __name__ == "__main__":
    main_watch()
