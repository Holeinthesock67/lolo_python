import pandas as pd
import os

def analyze_survival(file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # Calculate Total Agents (Active + Deaths) assuming 50 max usually, but let's derive
    df['TotalAgents'] = df['ActiveAgents'] + df['Deaths']
    df['SurvivalRate'] = df['ActiveAgents'] / df['TotalAgents'] * 100

    # Last 50 generations
    last_50 = df.tail(50)
    
    print("--- General Survival Stats (Last 50 Gen) ---")
    print(f"Avg Survival Rate: {last_50['SurvivalRate'].mean():.2f}%")
    print(f"Avg Duration: {last_50['Duration'].mean():.2f}")
    print(f"Avg Deaths: {last_50['Deaths'].mean():.2f}")
    print(f"Avg Active Agents: {last_50['ActiveAgents'].mean():.2f}")

    print("\n--- Class Survival Stats (Last 50 Gen) ---")
    print(f"Avg Alive Warriors: {last_50['Alive_War'].mean():.2f}")
    print(f"Avg Alive Scouts: {last_50['Alive_Sco'].mean():.2f}")
    print(f"Avg Alive Healers: {last_50['Alive_Hea'].mean():.2f}")

    print("\n--- Season Analysis (Last 100 Gen) ---")
    last_100 = df.tail(100)
    season_stats = last_100.groupby('Season')[['SurvivalRate', 'Duration', 'Deaths', 'ActiveAgents']].mean()
    print(season_stats)

    print("\n--- Recent Trend (Last 10 Gen) ---")
    print(last_50[['Generation', 'Season', 'SurvivalRate', 'Duration', 'Deaths', 'ActiveAgents']].tail(10).to_string(index=False))

if __name__ == "__main__":
    analyze_survival(r"c:\Users\laure\lolo_python\Jeux\arena_of_life\training_stats.csv")
