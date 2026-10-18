#!/usr/bin/env python3
import os
import shutil
import time
import json
import hashlib
import logging
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
from datetime import datetime
from PIL import Image, ExifTags
from geopy.geocoders import Nominatim

# --- Configuration ---
CACHE_FILE = "gps_cache.json"
LOG_FILENAME_FMT = "rapport_tri_%Y%m%d_%H%M%S.log"

# --- Gestion des erreurs Pillow ---
try:
    from PIL import UnidentifiedImageError
except ImportError:
    class UnidentifiedImageError(Exception):
        pass

# --- Fonctions Utilitaires ---

def setup_logging(log_file):
    """Configure le logging pour écrire dans la console et dans un fichier."""
    # Reset handlers existants
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def load_gps_cache():
    """Charge le cache GPS depuis le fichier JSON."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Erreur chargement cache GPS: {e}")
    return {}

def save_gps_cache(cache):
    """Sauvegarde le cache GPS dans le fichier JSON."""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Erreur sauvegarde cache GPS: {e}")

def calculate_file_hash(filepath, block_size=65536):
    """Calcule le hash MD5 d'un fichier pour détecter les doublons exacts."""
    md5 = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for block in iter(lambda: f.read(block_size), b''):
                md5.update(block)
        return md5.hexdigest()
    except Exception as e:
        logging.error(f"Erreur calcul hash {filepath}: {e}")
        return None

def convert_to_degrees(value):
    """Convertit coordonnées GPS (tuples ou float) en degrés décimaux."""
    if isinstance(value[0], tuple):
        d = value[0][0] / value[0][1]
        m = value[1][0] / value[1][1]
        s = value[2][0] / value[2][1]
    else:
        if len(value) == 3:
            d = float(value[0])
            m = float(value[1])
            s = float(value[2])
        else:
            return 0.0
    return d + (m / 60.0) + (s / 3600.0)

# --- Cœur du traitement ---

class PhotoOrganizer:
    def __init__(self, gps_cache):
        self.gps_cache = gps_cache
        self.geolocator = Nominatim(user_agent="photo_organizer_v3_premium")
        self.stats = {'processed': 0, 'copied': 0, 'skipped': 0, 'errors': 0}

    def get_location_name(self, lat, lon):
        """Récupère le nom du lieu (Cache ou API Nominatim)."""
        # Clé arrondie pour grouper les photos proches (précision ~11m)
        key = f"{lat:.4f},{lon:.4f}"
        
        if key in self.gps_cache:
            return self.gps_cache[key]

        try:
            logging.info(f"📍 Recherche API pour GPS: {key} (Pause anti-ban...)")
            time.sleep(1.1) # Pause respectueuse
            location = self.geolocator.reverse((lat, lon), language="fr", timeout=10, addressdetails=True)
            
            place_name = ""
            if location and location.raw and "address" in location.raw:
                add = location.raw["address"]
                # Ordre de préférence
                raw_name = (add.get("city") or add.get("town") or add.get("village") or 
                           add.get("municipality") or add.get("county") or add.get("state"))
                
                if raw_name:
                    # Nettoyage
                    s = raw_name.replace('-', '_').replace(' ', '_')
                    s_clean = "".join(c for c in s if c.isalnum() or c == '_')
                    s_norm = '_'.join(filter(None, s_clean.split('_')))
                    place_name = s_norm.capitalize()

            # Mise en cache (même si vide pour ne pas redemander)
            self.gps_cache[key] = place_name
            save_gps_cache(self.gps_cache) # Sauvegarde incrémentale
            return place_name

        except Exception as e:
            logging.error(f"Erreur API GPS: {e}")
            return ""

    def extract_metadata(self, file_path):
        metadata = {'lieu': ""}
        ext = os.path.splitext(file_path)[1].lower()
        
        # 1. Date par défaut = Modification
        metadata['date'] = datetime.fromtimestamp(os.path.getmtime(file_path))

        # 2. Si Image, tenter EXIF
        if ext in ['.jpg', '.jpeg', '.png', '.tiff', '.heic']:
            try:
                img = Image.open(file_path)
                exif_data = img._getexif()
                if exif_data:
                    exif = {ExifTags.TAGS.get(t, t): v for t, v in exif_data.items() if t in ExifTags.TAGS}
                    
                    # Date Prise de vue
                    date_str = exif.get("DateTimeOriginal") or exif.get("DateTime")
                    if date_str:
                        try:
                            fmt = "%Y:%m:%d %H:%M:%S"
                            if '.' in date_str: fmt += ".%f"
                            metadata['date'] = datetime.strptime(date_str, fmt)
                        except ValueError:
                            pass # On garde la date de modif

                    # GPS
                    gps_info = exif.get("GPSInfo")
                    if gps_info:
                        gps = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps_info.items()}
                        if "GPSLatitude" in gps and "GPSLongitude" in gps:
                            lat = convert_to_degrees(gps["GPSLatitude"])
                            if gps.get("GPSLatitudeRef") != "N": lat = -lat
                            lon = convert_to_degrees(gps["GPSLongitude"])
                            if gps.get("GPSLongitudeRef") != "E": lon = -lon
                            
                            metadata['lieu'] = self.get_location_name(lat, lon)
            except Exception as e:
                logging.warning(f"Erreur lecture EXIF {os.path.basename(file_path)}: {e}")

        return metadata

    def process_file(self, source_path, dest_root):
        try:
            self.stats['processed'] += 1
            meta = self.extract_metadata(source_path)
            
            # Structure Dossier
            date = meta['date']
            lieu = meta['lieu']
            year = date.strftime("%Y")
            month_folder = f"{year}_{date.strftime('%m')}"
            
            final_sub = f"{month_folder}_{lieu}" if lieu else month_folder
            target_dir = os.path.join(dest_root, year, month_folder, final_sub)
            os.makedirs(target_dir, exist_ok=True)

            # Nom fichier
            base_name = date.strftime(f"%Y%m%d_%H%M%S{'_' + lieu if lieu else ''}")
            ext = os.path.splitext(source_path)[1].lower()
            if not ext.startswith('.'): ext = '.' + ext
            
            target_name = base_name + ext
            target_path = os.path.join(target_dir, target_name)

            # Gestion Doublons
            if os.path.exists(target_path):
                # Vrai doublon ?
                src_hash = calculate_file_hash(source_path)
                tgt_hash = calculate_file_hash(target_path)
                
                if src_hash and tgt_hash and src_hash == tgt_hash:
                    logging.info(f"♻️ Doublon exact ignoré : {os.path.basename(source_path)}")
                    self.stats['skipped'] += 1
                    return
                
                # Faux doublon (contenu différent) -> Renommer
                counter = 1
                while os.path.exists(target_path):
                    target_name = f"{base_name}_{counter:02d}{ext}"
                    target_path = os.path.join(target_dir, target_name)
                    counter += 1

            # Copie
            shutil.copy2(source_path, target_path)
            logging.info(f"✅ Copié : {os.path.basename(source_path)} -> {os.path.relpath(target_path, dest_root)}")
            self.stats['copied'] += 1

        except Exception as e:
            logging.error(f"❌ Erreur critique sur {source_path}: {e}")
            self.stats['errors'] += 1

# --- Interface Graphique (GUI) ---

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Super Photo Organizer V3 🚀")
        self.geometry("600x500")
        
        # Variables
        self.src_var = tk.StringVar()
        self.dst_var = tk.StringVar()
        self.is_running = False

        self.setup_ui()
        
        # Redirection logging vers GUI
        self.log_queue = []
        self.after(100, self.update_logs)

    def setup_ui(self):
        # Frame Dossiers
        f_dirs = tk.LabelFrame(self, text="Configuration", padx=10, pady=10)
        f_dirs.pack(fill="x", padx=10, pady=5)

        tk.Label(f_dirs, text="Dossier Photos (Source):").grid(row=0, column=0, sticky="w")
        tk.Entry(f_dirs, textvariable=self.src_var, width=50).grid(row=0, column=1, padx=5)
        tk.Button(f_dirs, text="...", command=self.browse_src).grid(row=0, column=2)

        tk.Label(f_dirs, text="Dossier Trié (Dest):").grid(row=1, column=0, sticky="w")
        tk.Entry(f_dirs, textvariable=self.dst_var, width=50).grid(row=1, column=1, padx=5)
        tk.Button(f_dirs, text="...", command=self.browse_dst).grid(row=1, column=2)

        # Bouton Action
        self.btn_run = tk.Button(self, text="Démarrer le Tri 🎬", bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), command=self.start_thread)
        self.btn_run.pack(pady=10)

        # Logs
        tk.Label(self, text="Journal d'opérations :").pack(anchor="w", padx=10)
        self.txt_log = scrolledtext.ScrolledText(self, state='disabled', height=15)
        self.txt_log.pack(fill="both", expand=True, padx=10, pady=5)

    def browse_src(self):
        d = filedialog.askdirectory()
        if d: self.src_var.set(d)

    def browse_dst(self):
        d = filedialog.askdirectory()
        if d: self.dst_var.set(d)

    def log_gui(self, msg):
        self.log_queue.append(msg)

    def update_logs(self):
        while self.log_queue:
            msg = self.log_queue.pop(0)
            self.txt_log.config(state='normal')
            self.txt_log.insert(tk.END, msg + "\n")
            self.txt_log.see(tk.END)
            self.txt_log.config(state='disabled')
        self.after(100, self.update_logs)

    def start_thread(self):
        if self.is_running: return
        
        src = self.src_var.get()
        dst = self.dst_var.get()
        
        if not src or not os.path.exists(src):
            messagebox.showerror("Erreur", "Veuillez choisir un dossier source valide.")
            return
        if not dst:
            messagebox.showerror("Erreur", "Veuillez choisir un dossier destination.")
            return

        self.is_running = True
        self.btn_run.config(state="disabled", text="En cours...")
        
        # Thread séparé pour ne pas figer l'interface
        threading.Thread(target=self.run_process, args=(src, dst)).start()

    def run_process(self, src, dst):
        # Setup Logs
        log_file = datetime.now().strftime(LOG_FILENAME_FMT)
        setup_logging(log_file)
        
        # Handler custom pour envoyer les logs vers l'UI
        class GuiHandler(logging.Handler):
            def __init__(self, app):
                super().__init__()
                self.app = app
            def emit(self, record):
                msg = self.format(record)
                self.app.log_gui(msg)
        
        logging.getLogger().addHandler(GuiHandler(self))

        logging.info("=== Démarrage du Super Organisateur V3 ===")
        logging.info(f"Source: {src}")
        logging.info(f"Destination: {dst}")

        cache = load_gps_cache()
        organizer = PhotoOrganizer(cache)

        # Walk
        for root, dirs, files in os.walk(src):
            dirs[:] = [d for d in dirs if not d.startswith('.')] # Ignorer dossiers cachés
            
            for f in files:
                if f.startswith('.'): continue
                file_path = os.path.join(root, f)
                organizer.process_file(file_path, dst)

        # Final Report
        stats = organizer.stats
        logging.info("=== Terminé ! ===")
        logging.info(f"Total traités: {stats['processed']}")
        logging.info(f"Copiés avec succès: {stats['copied']}")
        logging.info(f"Ignorés (Doublons exacts): {stats['skipped']}")
        logging.info(f"Erreurs: {stats['errors']}")
        logging.info(f"Rapport complet sauvegardé dans: {log_file}")
        
        messagebox.showinfo("Terminé", "Le tri est terminé avec succès ! 🎉")
        
        self.is_running = False
        self.btn_run.config(state="normal", text="Démarrer le Tri 🎬")

if __name__ == "__main__":
    app = App()
    app.mainloop()
