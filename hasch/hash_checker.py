import os
import sys
import hashlib
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk

# Configuration du thème de l'application
ctk.set_appearance_mode("System")  # Options: "System", "Dark", "Light"
ctk.set_default_color_theme("blue")  # Options: "blue", "green", "dark-blue"

class HashCalculator(threading.Thread):
    """
    Calcule MD5, SHA-1 et SHA-256 en arrière-plan (thread) par blocs de 1 Mo 
    pour éviter de saturer la RAM et de geler l'interface graphique.
    """
    def __init__(self, filepath, progress_callback, success_callback, error_callback):
        super().__init__()
        self.filepath = filepath
        self.progress_callback = progress_callback
        self.success_callback = success_callback
        self.error_callback = error_callback
        self._is_cancelled = False
        self.daemon = True  # Permet de fermer le thread si l'application s'arrête

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            total_size = os.path.getsize(self.filepath)
            
            md5_hash = hashlib.md5()
            sha1_hash = hashlib.sha1()
            sha256_hash = hashlib.sha256()
            
            bytes_read = 0
            chunk_size = 1024 * 1024  # Lecture par blocs de 1 Mo
            
            with open(self.filepath, 'rb') as f:
                while True:
                    if self._is_cancelled:
                        return
                    
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    
                    md5_hash.update(chunk)
                    sha1_hash.update(chunk)
                    sha256_hash.update(chunk)
                    
                    bytes_read += len(chunk)
                    if self.progress_callback:
                        self.progress_callback(bytes_read, total_size)
            
            if self._is_cancelled:
                return
                
            results = {
                'md5': md5_hash.hexdigest(),
                'sha1': sha1_hash.hexdigest(),
                'sha256': sha256_hash.hexdigest()
            }
            
            if self.success_callback:
                self.success_callback(results)
                
        except Exception as e:
            if self.error_callback:
                self.error_callback(str(e))


class HashCheckerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configuration de la fenêtre principale
        self.title("🛡️ Hash Guard - Vérificateur d'Intégrité")
        self.geometry("750x640")
        self.minimum_size = (750, 640)
        self.minsize(750, 640)
        
        # Centrer la fenêtre sur l'écran
        self.center_window()

        # Variables d'état
        self.selected_filepath = None
        self.calculated_hashes = {}
        self.calc_thread = None

        # Construction de l'interface
        self.create_widgets()
        
    def center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def create_widgets(self):
        # Configure le grid layout principal (1 colonne, plusieurs lignes)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)  # La zone centrale s'étire

        # ----------------- HEADER -----------------
        self.header_frame = ctk.CTkFrame(self, height=80, corner_radius=0, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=30, pady=(20, 10))
        self.header_frame.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self.header_frame, 
            text="🛡️ HASH GUARD", 
            font=ctk.CTkFont(family="Inter", size=24, weight="bold")
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        self.subtitle_label = ctk.CTkLabel(
            self.header_frame, 
            text="Vérifiez l'intégrité et la légitimité de vos executables téléchargés", 
            font=ctk.CTkFont(family="Inter", size=13),
            text_color="gray"
        )
        self.subtitle_label.grid(row=1, column=0, sticky="w", pady=(2, 0))
        
        # Bouton Theme (Sombre/Clair)
        self.theme_btn = ctk.CTkButton(
            self.header_frame,
            text="🌓",
            width=40,
            height=30,
            fg_color=("#E2E8F0", "#2B2D30"),
            hover_color=("#CBD5E1", "#3F4245"),
            text_color=("black", "white"),
            command=self.toggle_theme
        )
        self.theme_btn.grid(row=0, column=1, rowspan=2, sticky="e")

        # ----------------- ZONE DE SÉLECTION DE FICHIER -----------------
        self.file_frame = ctk.CTkFrame(self, corner_radius=12)
        self.file_frame.grid(row=1, column=0, sticky="nsew", padx=30, pady=10)
        self.file_frame.grid_columnconfigure(0, weight=1)
        
        # Label d'instruction
        self.select_prompt = ctk.CTkLabel(
            self.file_frame,
            text="Sélectionnez un fichier exécutable ou une archive pour commencer la vérification",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.select_prompt.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Bouton Parcourir
        self.browse_btn = ctk.CTkButton(
            self.file_frame,
            text="Parcourir les fichiers...",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=40,
            command=self.browse_file
        )
        self.browse_btn.grid(row=1, column=0, padx=20, pady=10)

        # Zone d'information sur le fichier (masquée par défaut ou vide)
        self.info_frame = ctk.CTkFrame(self.file_frame, fg_color=("#F1F5F9", "#202225"), corner_radius=8)
        self.info_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=10)
        self.info_frame.grid_columnconfigure(1, weight=1)

        self.lbl_file_name_title = ctk.CTkLabel(self.info_frame, text="Nom :", font=ctk.CTkFont(weight="bold"), text_color="gray")
        self.lbl_file_name_title.grid(row=0, column=0, sticky="w", padx=15, pady=(8, 4))
        
        self.lbl_file_name = ctk.CTkLabel(self.info_frame, text="Aucun fichier sélectionné", font=ctk.CTkFont(weight="normal"))
        self.lbl_file_name.grid(row=0, column=1, sticky="w", padx=5, pady=(8, 4))

        self.lbl_file_size_title = ctk.CTkLabel(self.info_frame, text="Taille :", font=ctk.CTkFont(weight="bold"), text_color="gray")
        self.lbl_file_size_title.grid(row=1, column=0, sticky="w", padx=15, pady=(4, 8))
        
        self.lbl_file_size = ctk.CTkLabel(self.info_frame, text="-", font=ctk.CTkFont(weight="normal"))
        self.lbl_file_size.grid(row=1, column=1, sticky="w", padx=5, pady=(4, 8))

        # Barre de progression du calcul de hash
        self.progress_bar = ctk.CTkProgressBar(self.file_frame)
        self.progress_bar.grid(row=3, column=0, sticky="ew", padx=20, pady=5)
        self.progress_bar.set(0)
        
        self.progress_label = ctk.CTkLabel(self.file_frame, text="En attente...", font=ctk.CTkFont(size=12), text_color="gray")
        self.progress_label.grid(row=4, column=0, pady=(0, 10))

        # ----------------- HASH VALUES DISPLAY -----------------
        self.hashes_frame = ctk.CTkFrame(self, corner_radius=12)
        self.hashes_frame.grid(row=2, column=0, sticky="ew", padx=30, pady=10)
        self.hashes_frame.grid_columnconfigure(1, weight=1)

        # SHA-256
        self.lbl_sha256 = ctk.CTkLabel(self.hashes_frame, text="SHA-256 :", font=ctk.CTkFont(weight="bold"))
        self.lbl_sha256.grid(row=0, column=0, padx=(15, 5), pady=8, sticky="w")
        self.entry_sha256 = ctk.CTkEntry(self.hashes_frame, font=ctk.CTkFont(family="Courier", size=12))
        self.entry_sha256.grid(row=0, column=1, padx=5, pady=8, sticky="ew")
        self.entry_sha256.configure(state="readonly")
        self.btn_copy_sha256 = ctk.CTkButton(self.hashes_frame, text="Copier", width=60, command=lambda: self.copy_to_clipboard(self.entry_sha256.get()))
        self.btn_copy_sha256.grid(row=0, column=2, padx=(5, 15), pady=8)

        # SHA-1
        self.lbl_sha1 = ctk.CTkLabel(self.hashes_frame, text="SHA-1 :", font=ctk.CTkFont(weight="bold"))
        self.lbl_sha1.grid(row=1, column=0, padx=(15, 5), pady=8, sticky="w")
        self.entry_sha1 = ctk.CTkEntry(self.hashes_frame, font=ctk.CTkFont(family="Courier", size=12))
        self.entry_sha1.grid(row=1, column=1, padx=5, pady=8, sticky="ew")
        self.entry_sha1.configure(state="readonly")
        self.btn_copy_sha1 = ctk.CTkButton(self.hashes_frame, text="Copier", width=60, command=lambda: self.copy_to_clipboard(self.entry_sha1.get()))
        self.btn_copy_sha1.grid(row=1, column=2, padx=(5, 15), pady=8)

        # MD5
        self.lbl_md5 = ctk.CTkLabel(self.hashes_frame, text="MD5 :", font=ctk.CTkFont(weight="bold"))
        self.lbl_md5.grid(row=2, column=0, padx=(15, 5), pady=8, sticky="w")
        self.entry_md5 = ctk.CTkEntry(self.hashes_frame, font=ctk.CTkFont(family="Courier", size=12))
        self.entry_md5.grid(row=2, column=1, padx=5, pady=8, sticky="ew")
        self.entry_md5.configure(state="readonly")
        self.btn_copy_md5 = ctk.CTkButton(self.hashes_frame, text="Copier", width=60, command=lambda: self.copy_to_clipboard(self.entry_md5.get()))
        self.btn_copy_md5.grid(row=2, column=2, padx=(5, 15), pady=8)

        # ----------------- ZONE DE COMPARAISON -----------------
        self.compare_frame = ctk.CTkFrame(self, corner_radius=12)
        self.compare_frame.grid(row=3, column=0, sticky="ew", padx=30, pady=10)
        self.compare_frame.grid_columnconfigure(0, weight=1)

        self.lbl_compare_title = ctk.CTkLabel(
            self.compare_frame,
            text="Coller le hash attendu (MD5, SHA-1 ou SHA-256) pour vérification :",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_compare_title.grid(row=0, column=0, columnspan=2, padx=15, pady=(12, 5), sticky="w")

        # Entry pour coller le hash officiel
        self.entry_official = ctk.CTkEntry(
            self.compare_frame, 
            placeholder_text="Collez le hash officiel ici...",
            font=ctk.CTkFont(family="Courier", size=12)
        )
        self.entry_official.grid(row=1, column=0, padx=(15, 5), pady=(5, 10), sticky="ew")
        self.entry_official.bind("<KeyRelease>", self.check_hash_match)

        self.btn_clear_compare = ctk.CTkButton(
            self.compare_frame, 
            text="Effacer", 
            width=60, 
            command=self.clear_compare_field
        )
        self.btn_clear_compare.grid(row=1, column=1, padx=(5, 15), pady=(5, 10))

        # Label d'indicateur de résultat de comparaison
        self.compare_result = ctk.CTkLabel(
            self.compare_frame,
            text="En attente de saisie...",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=38,
            corner_radius=6,
            fg_color=("#F1F5F9", "#2B2D30")
        )
        self.compare_result.grid(row=2, column=0, columnspan=2, padx=15, pady=(5, 15), sticky="ew")

        # ----------------- FOOTER ACTION BUTTONS -----------------
        self.footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.footer_frame.grid(row=4, column=0, sticky="ew", padx=30, pady=(10, 20))
        self.footer_frame.grid_columnconfigure(0, weight=1)

        self.btn_virustotal = ctk.CTkButton(
            self.footer_frame,
            text="🔍 Vérifier sur VirusTotal",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#0066CC",
            hover_color="#0052A3",
            height=40,
            command=self.open_virustotal,
            state="disabled"
        )
        self.btn_virustotal.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        self.btn_reset = ctk.CTkButton(
            self.footer_frame,
            text="🔄 Réinitialiser",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("#E2E8F0", "#475569"),
            hover_color=("#CBD5E1", "#334155"),
            text_color=("black", "white"),
            height=40,
            command=self.reset_all
        )
        self.btn_reset.grid(row=0, column=1, padx=(10, 0), sticky="ew")

    # ----------------- EVENEMENTS / LOGIQUE INTERFACE -----------------
    
    def toggle_theme(self):
        current = ctk.get_appearance_mode()
        if current == "Dark":
            ctk.set_appearance_mode("Light")
        else:
            ctk.set_appearance_mode("Dark")

    def browse_file(self):
        # Annuler un calcul en cours si existant
        if self.calc_thread and self.calc_thread.is_alive():
            self.calc_thread.cancel()

        file_path = filedialog.askopenfilename(
            title="Sélectionner un fichier",
            filetypes=[("Tous les fichiers", "*.*")]
        )
        
        if not file_path:
            return

        self.selected_filepath = file_path
        
        # Mettre à jour l'UI avec les infos du fichier
        filename = os.path.basename(file_path)
        size_bytes = os.path.getsize(file_path)
        size_formatted = self.format_size(size_bytes)

        self.lbl_file_name.configure(text=filename)
        self.lbl_file_size.configure(text=size_formatted)
        
        # Réinitialiser les champs de hashs
        self.clear_hash_entries()
        self.entry_official.delete(0, tk.END)
        self.compare_result.configure(
            text="Calcul des empreintes en cours...", 
            fg_color=("#F1F5F9", "#2B2D30"),
            text_color=("black", "white")
        )
        
        # Lancer le calcul en arrière-plan
        self.progress_bar.set(0)
        self.progress_label.configure(text="Initialisation...")
        
        self.calc_thread = HashCalculator(
            filepath=file_path,
            progress_callback=self.on_hash_progress,
            success_callback=self.on_hash_success,
            error_callback=self.on_hash_error
        )
        self.calc_thread.start()

    def format_size(self, bytes_size):
        for unit in ['Octets', 'Ko', 'Mo', 'Go', 'To']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.2f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.2f} To"

    def on_hash_progress(self, bytes_read, total_size):
        # Calcul du pourcentage de progression
        if total_size > 0:
            percentage = bytes_read / total_size
            self.progress_bar.set(percentage)
            pct_text = f"{percentage*100:.1f}%"
            read_mb = bytes_read / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            self.progress_label.configure(text=f"Lecture : {read_mb:.1f} Mo / {total_mb:.1f} Mo ({pct_text})")
        else:
            self.progress_bar.set(0)
            self.progress_label.configure(text="Lecture en cours...")
        
        # Forcer la mise à jour de l'interface tkinter
        self.update_idletasks()

    def on_hash_success(self, results):
        self.calculated_hashes = results
        
        # Mettre à jour les champs de hashs
        self.write_hash_entry(self.entry_sha256, results['sha256'])
        self.write_hash_entry(self.entry_sha1, results['sha1'])
        self.write_hash_entry(self.entry_md5, results['md5'])

        # Activer le bouton VirusTotal
        self.btn_virustotal.configure(state="normal")

        # Mettre à jour la barre de progression
        self.progress_bar.set(1.0)
        self.progress_label.configure(text="Calcul terminé avec succès !")

        # Relancer la comparaison si le champ officiel contient déjà du texte
        self.check_hash_match()

    def on_hash_error(self, error_msg):
        self.progress_label.configure(text="Erreur lors du calcul.")
        self.compare_result.configure(
            text=f"Erreur : {error_msg}",
            fg_color="#EF4444",
            text_color="white"
        )
        self.btn_virustotal.configure(state="disabled")

    def write_hash_entry(self, entry, value):
        entry.configure(state="normal")
        entry.delete(0, tk.END)
        entry.insert(0, value)
        entry.configure(state="readonly")

    def clear_hash_entries(self):
        for entry in [self.entry_sha256, self.entry_sha1, self.entry_md5]:
            entry.configure(state="normal")
            entry.delete(0, tk.END)
            entry.configure(state="readonly")
        self.calculated_hashes = {}
        self.btn_virustotal.configure(state="disabled")

    def clear_compare_field(self):
        self.entry_official.delete(0, tk.END)
        self.check_hash_match()

    def check_hash_match(self, event=None):
        official_hash = self.entry_official.get().strip().lower().replace(" ", "")
        
        if not official_hash:
            self.compare_result.configure(
                text="En attente de comparaison... Collez un hash attendu ci-dessus.",
                fg_color=("#F1F5F9", "#2B2D30"),
                text_color=("black", "white")
            )
            return

        if not self.calculated_hashes:
            self.compare_result.configure(
                text="Veuillez d'abord sélectionner un fichier à analyser.",
                fg_color=("#EAB308", "#CA8A04"), # Jaune / Orange
                text_color="white"
            )
            return

        # Comparer avec les 3 types de hash
        matches = False
        hash_type = ""
        
        if len(official_hash) == 64: # SHA-256 length
            matches = (official_hash == self.calculated_hashes.get('sha256'))
            hash_type = "SHA-256"
        elif len(official_hash) == 40: # SHA-1 length
            matches = (official_hash == self.calculated_hashes.get('sha1'))
            hash_type = "SHA-1"
        elif len(official_hash) == 32: # MD5 length
            matches = (official_hash == self.calculated_hashes.get('md5'))
            hash_type = "MD5"
        else:
            # Longueur inconnue ou invalide
            self.compare_result.configure(
                text="Format de hash invalide (MD5 = 32 car., SHA-1 = 40 car., SHA-256 = 64 car.)",
                fg_color=("#475569", "#64748B"), # Gris neutre
                text_color="white"
            )
            return

        if matches:
            self.compare_result.configure(
                text=f"✓ HASH CORRECT ({hash_type}) - Le fichier est intègre et identique à l'original !",
                fg_color="#10B981", # Vert émeraude
                text_color="white"
            )
        else:
            self.compare_result.configure(
                text=f"✗ HASH INCORRECT ({hash_type}) - Attention ! Le fichier a été modifié ou corrompu !",
                fg_color="#EF4444", # Rouge vif
                text_color="white"
            )

    def open_virustotal(self):
        sha256 = self.calculated_hashes.get('sha256')
        if sha256:
            url = f"https://www.virustotal.com/gui/file/{sha256}/detection"
            webbrowser.open(url)

    def copy_to_clipboard(self, text):
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            
            # Effet visuel temporaire pour confirmer la copie
            # On change temporairement le texte du bouton ou le statut
            self.progress_label.configure(text="Copié dans le presse-papiers !")
            self.after(2000, lambda: self.reset_progress_label_after_copy())

    def reset_progress_label_after_copy(self):
        if self.calculated_hashes:
            self.progress_label.configure(text="Calcul terminé avec succès !")
        else:
            self.progress_label.configure(text="En attente...")

    def reset_all(self):
        if self.calc_thread and self.calc_thread.is_alive():
            self.calc_thread.cancel()
            
        self.selected_filepath = None
        self.calculated_hashes = {}
        
        self.lbl_file_name.configure(text="Aucun fichier sélectionné")
        self.lbl_file_size.configure(text="-")
        
        self.progress_bar.set(0)
        self.progress_label.configure(text="Prêt")
        
        self.clear_hash_entries()
        self.entry_official.delete(0, tk.END)
        self.compare_result.configure(
            text="En attente de saisie...",
            fg_color=("#F1F5F9", "#2B2D30"),
            text_color=("black", "white")
        )


if __name__ == "__main__":
    app = HashCheckerApp()
    app.mainloop()
