
import torch
import os
import shutil
from datetime import datetime
from config.constants import SEASON_CYCLE, WEAPON_FISTS, WEAPON_SWORD, WEAPON_BOW, WEAPON_WAND

def reset_stats_keep_brain():
    print("=== ARENA OF LIFE : STATS RESET (KEEP BRAIN) ===")
    
    # Paths
    base_path = os.path.dirname(os.path.abspath(__file__))
    model_dir = os.path.join(base_path, "assets", "models")
    brain_path = os.path.join(model_dir, "arena_brain.pth")
    csv_path = os.path.join(base_path, "training_stats.csv")
    
    # 1. HANDLE CSV (Backup & Remove)
    if os.path.exists(csv_path):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_csv = os.path.join(base_path, f"training_stats_backup_{ts}.csv")
        try:
            shutil.move(csv_path, backup_csv)
            print(f"[OK] Archived CSV to: {os.path.basename(backup_csv)}")
        except Exception as e:
            print(f"[ERR] Failed to archive CSV: {e}")
    else:
        print("[INFO] No CSV found to reset.")

    # 1.5 CLEAR PATCH FLAGS (To allow Epsilon Boost to re-trigger)
    flag_files = ["patch_v2_applied.flag", "epsilon_boost_v1.flag", "epsilon_boost_v2.flag"]
    for fname in flag_files:
        fpath = os.path.join(base_path, "assets", fname)
        if os.path.exists(fpath):
            os.remove(fpath)
            print(f"[INFO] Cleared flag: {fname}")

    # 2. HANDLE BRAIN (Reset Metadata, Keep Weights)
    brain_files = [brain_path, os.path.join(model_dir, "arena_brain_backup.pth")]
    
    for b_path in brain_files:
        if os.path.exists(b_path):
            print(f"[INFO] Processing brain: {os.path.basename(b_path)}")
            try:
                # Load on CPU to be safe, save back effectively
                checkpoint = torch.load(b_path, map_location='cpu')
                
                # Reset Counters
                print(f" -> Current Gen: {checkpoint.get('generation', '?')}")
                print(" -> Resetting Generation and History...")
                checkpoint['generation'] = 0
                checkpoint['steps_done'] = 0
                
                # Reset Lists/Stats
                checkpoint['kill_history'] = []
                checkpoint['reward_history'] = []
                checkpoint['duration_history'] = []
                checkpoint['action_history'] = []
                checkpoint['gen_loss_history'] = []
                
                checkpoint['global_kills_by_type'] = {
                    WEAPON_FISTS: 0,
                    WEAPON_SWORD: 0,
                    WEAPON_BOW: 0,
                    WEAPON_WAND: 0
                }
                
                checkpoint['hall_of_fame'] = []
                
                # Reset Season/Cycle
                checkpoint['current_season'] = SEASON_CYCLE[0] # Spring
                checkpoint['auto_season_mode'] = True
                checkpoint['season_gens_counter'] = 0
                checkpoint['cycle_number'] = 1
                checkpoint['complete_cycle_performance'] = []
                
                # Save back
                print(f"[INFO] Saving reset {os.path.basename(b_path)}...")
                torch.save(checkpoint, b_path)
                print("[SUCCESS] Brain reset.")
                
            except Exception as e:
                print(f"[ERR] Failed to process {os.path.basename(b_path)}: {e}")
    else:
        print("[WARN] No brain file found! Starting fresh naturally.")

    # 3. CLEANUP CHECKPOINTS
    # Move old checkpoints to a backup folder to avoid loading them by mistake
    print("[INFO] Cleaning up old checkpoints...")
    bkp_dir = os.path.join(model_dir, "archived_checkpoints")
    if not os.path.exists(bkp_dir):
        os.makedirs(bkp_dir)
        
    for f in os.listdir(model_dir):
        if f.startswith("arena_brain_gen_") and f.endswith(".pth"):
            src = os.path.join(model_dir, f)
            dst = os.path.join(bkp_dir, f)
            shutil.move(src, dst)
            print(f" -> Moved {f} to archive")

    print("\n=== RESET COMPLETE ===")
    print("You can now restart the game.")

if __name__ == "__main__":
    reset_stats_keep_brain()
