import sys
import os
import math
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import pandas as pd
from PIL import Image, ImageTk, ImageGrab, ImageDraw
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

# Activer la netteté haute densité (DPI scaling) sous Windows
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# Theme de couleurs premium (Dark Mode)
THEME = {
    'bg_main': '#121214',      # Fond principal ultra-sombre
    'bg_panel': '#1e1e24',     # Fond de panneau sombre
    'bg_control': '#2a2a35',   # Fond de contrôle
    'fg_text': '#ffffff',      # Texte blanc
    'fg_muted': '#a0a0b0',     # Texte grisé
    'accent_x': '#ff9f1c',     # Orange néon pour l'axe X
    'accent_y': '#4cc9f0',     # Cyan néon pour l'axe Y
    'accent_curve': '#39ff14', # Vert néon pour la courbe
    'accent_reg': '#f72585',   # Rose néon pour la régression
    'btn_bg': '#3f3f4f',       # Fond bouton plat
    'btn_hover': '#5f5f7f',    # Hover bouton
    'btn_active': '#7f7f9f',   # Clic bouton
    'entry_bg': '#2a2a35',     # Entrée utilisateur
    'entry_fg': '#ffffff',
}

class DigitizerModel:
    def __init__(self):
        self.original_image = None
        self.display_image = None
        self.scale_factor = 1.0  # display_size / original_size
        self.pad_x = 0
        self.pad_y = 0
        
        # Repères de calibration (coordonnées en pixels sur l'image ORIGINALE)
        # Initialisés à None, seront positionnés à l'import de l'image
        self.calib_px = {
            'x1': None,  # (u, v) pour X_min
            'x2': None,  # (u, v) pour X_max
            'y1': None,  # (u, v) pour Y_min
            'y2': None,  # (u, v) pour Y_max
        }
        
        # Valeurs réelles associées aux repères de calibration
        self.calib_val = {
            'x1': 0.0,
            'x2': 10.0,
            'y1': 0.0,
            'y2': 10.0,
        }
        
        # Type d'échelle ("linear" ou "log")
        self.x_scale = "linear"
        self.y_scale = "linear"
        
        # Liste des points numérisés (tuples (u, v) sur l'image ORIGINALE)
        self.points = []
        
        # Modèle de régression sélectionné
        self.reg_type = "Aucune"
        self.poly_degree = 2

    def is_calibrated(self):
        """Vérifie si les repères sont correctement configurés et valides."""
        for key, pt in self.calib_px.items():
            if pt is None:
                return False
        
        # Vérification des divisions par zéro
        if self.calib_px['x1'][0] == self.calib_px['x2'][0]:
            return False
        if self.calib_px['y1'][1] == self.calib_px['y2'][1]:
            return False
            
        # En mode logarithmique, les valeurs réelles doivent être strictement positives
        if self.x_scale == "log":
            if self.calib_val['x1'] <= 0 or self.calib_val['x2'] <= 0:
                return False
        if self.y_scale == "log":
            if self.calib_val['y1'] <= 0 or self.calib_val['y2'] <= 0:
                return False
                
        return True

    def pixel_to_real(self, u, v):
        """Convertit les coordonnées pixels (image originale) en valeurs physiques réelles."""
        if not self.is_calibrated():
            return 0.0, 0.0
            
        u1, _ = self.calib_px['x1']
        u2, _ = self.calib_px['x2']
        _, v1 = self.calib_px['y1']
        _, v2 = self.calib_px['y2']
        
        x1, x2 = self.calib_val['x1'], self.calib_val['x2']
        y1, y2 = self.calib_val['y1'], self.calib_val['y2']
        
        # Calcul X
        if self.x_scale == "log":
            log_x1 = math.log10(x1)
            log_x2 = math.log10(x2)
            log_x = log_x1 + (u - u1) * (log_x2 - log_x1) / (u2 - u1)
            x = 10 ** log_x
        else:
            x = x1 + (u - u1) * (x2 - x1) / (u2 - u1)
            
        # Calcul Y
        if self.y_scale == "log":
            log_y1 = math.log10(y1)
            log_y2 = math.log10(y2)
            log_y = log_y1 + (v - v1) * (log_y2 - log_y1) / (v2 - v1)
            y = 10 ** log_y
        else:
            y = y1 + (v - v1) * (y2 - y1) / (v2 - v1)
            
        return x, y

    def real_to_pixel(self, x, y):
        """Convertit les coordonnées physiques réelles en pixels de l'image originale."""
        if not self.is_calibrated():
            return 0, 0
            
        u1, _ = self.calib_px['x1']
        u2, _ = self.calib_px['x2']
        _, v1 = self.calib_px['y1']
        _, v2 = self.calib_px['y2']
        
        x1, x2 = self.calib_val['x1'], self.calib_val['x2']
        y1, y2 = self.calib_val['y1'], self.calib_val['y2']
        
        # Inverse X
        if self.x_scale == "log":
            if x <= 0: return 0, 0
            log_x1 = math.log10(x1)
            log_x2 = math.log10(x2)
            log_x = math.log10(x)
            u = u1 + (log_x - log_x1) * (u2 - u1) / (log_x2 - log_x1)
        else:
            u = u1 + (x - x1) * (u2 - u1) / (x2 - x1)
            
        # Inverse Y
        if self.y_scale == "log":
            if y <= 0: return 0, 0
            log_y1 = math.log10(y1)
            log_y2 = math.log10(y2)
            log_y = math.log10(y)
            v = v1 + (log_y - log_y1) * (v2 - v1) / (log_y2 - log_y1)
        else:
            v = v1 + (y - y1) * (v2 - v1) / (y2 - y1)
            
        return int(round(u)), int(round(v))

    def get_real_points(self):
        """Renvoie la liste des points numérisés en coordonnées physiques réelles."""
        real_pts = []
        for u, v in self.points:
            x, y = self.pixel_to_real(u, v)
            real_pts.append((x, y))
        return real_pts

    def compute_regression(self):
        """Calcule la régression sélectionnée sur les points numérisés."""
        real_pts = self.get_real_points()
        if len(real_pts) < 2:
            return None, "Besoin d'au moins 2 points pour calculer une régression."
            
        # Séparer X et Y et trier par X pour un affichage continu
        x_raw, y_raw = zip(*real_pts)
        x = np.array(x_raw)
        y = np.array(y_raw)
        
        # Tri
        sort_idx = np.argsort(x)
        x_sorted = x[sort_idx]
        y_sorted = y[sort_idx]
        
        try:
            if self.reg_type == "Linéaire":
                a, b = np.polyfit(x_sorted, y_sorted, 1)
                y_pred = a * x_sorted + b
                
                # R²
                y_mean = np.mean(y_sorted)
                ss_tot = np.sum((y_sorted - y_mean)**2)
                ss_res = np.sum((y_sorted - y_pred)**2)
                r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 1.0
                
                eq = f"y = {a:.4e} * x {'+' if b >= 0 else '-'} {abs(b):.4e}"
                
                # Pour le tracé lisse
                x_fit = np.linspace(x_sorted[0], x_sorted[-1], 200)
                y_fit = a * x_fit + b
                
                return {
                    'type': 'Linéaire',
                    'eq': eq,
                    'r2': r2,
                    'x_fit': x_fit,
                    'y_fit': y_fit
                }, None
                
            elif self.reg_type == "Polynomiale":
                deg = self.poly_degree
                if len(x_sorted) <= deg:
                    return None, f"Besoin de plus de {deg} points pour un polynôme de degré {deg}."
                    
                coeffs = np.polyfit(x_sorted, y_sorted, deg)
                y_pred = np.polyval(coeffs, x_sorted)
                
                y_mean = np.mean(y_sorted)
                ss_tot = np.sum((y_sorted - y_mean)**2)
                ss_res = np.sum((y_sorted - y_pred)**2)
                r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 1.0
                
                terms = []
                for i, c in enumerate(coeffs):
                    power = deg - i
                    if power > 1:
                        terms.append(f"{c:.4e}*x^{power}")
                    elif power == 1:
                        terms.append(f"{c:.4e}*x")
                    else:
                        terms.append(f"{c:.4e}")
                eq = "y = " + " + ".join(terms).replace("+ -", "- ")
                
                x_fit = np.linspace(x_sorted[0], x_sorted[-1], 200)
                y_fit = np.polyval(coeffs, x_fit)
                
                return {
                    'type': f'Polynôme (Deg {deg})',
                    'eq': eq,
                    'r2': r2,
                    'x_fit': x_fit,
                    'y_fit': y_fit
                }, None
                
            elif self.reg_type == "Exponentielle":
                if np.any(y_sorted <= 0):
                    return None, "Erreur: Les valeurs Y doivent être strictement positives (> 0) pour un modèle exponentiel."
                    
                b, ln_a = np.polyfit(x_sorted, np.log(y_sorted), 1)
                a = np.exp(ln_a)
                
                y_pred = a * np.exp(b * x_sorted)
                y_mean = np.mean(y_sorted)
                ss_tot = np.sum((y_sorted - y_mean)**2)
                ss_res = np.sum((y_sorted - y_pred)**2)
                r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 1.0
                
                eq = f"y = {a:.4e} * e^({b:.4e} * x)"
                
                x_fit = np.linspace(x_sorted[0], x_sorted[-1], 200)
                y_fit = a * np.exp(b * x_fit)
                
                return {
                    'type': 'Exponentielle',
                    'eq': eq,
                    'r2': r2,
                    'x_fit': x_fit,
                    'y_fit': y_fit
                }, None
                
            elif self.reg_type == "Puissance":
                if np.any(x_sorted <= 0) or np.any(y_sorted <= 0):
                    return None, "Erreur: Les valeurs X et Y doivent être strictement positives (> 0) pour un modèle puissance."
                    
                b, ln_a = np.polyfit(np.log(x_sorted), np.log(y_sorted), 1)
                a = np.exp(ln_a)
                
                y_pred = a * (x_sorted**b)
                y_mean = np.mean(y_sorted)
                ss_tot = np.sum((y_sorted - y_mean)**2)
                ss_res = np.sum((y_sorted - y_pred)**2)
                r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 1.0
                
                eq = f"y = {a:.4e} * x^({b:.4e})"
                
                x_fit = np.linspace(x_sorted[0], x_sorted[-1], 200)
                y_fit = a * (x_fit**b)
                
                return {
                    'type': 'Puissance',
                    'eq': eq,
                    'r2': r2,
                    'x_fit': x_fit,
                    'y_fit': y_fit
                }, None
                
            elif self.reg_type == "Logarithmique":
                if np.any(x_sorted <= 0):
                    return None, "Erreur: Les valeurs X doivent être strictement positives (> 0) pour un modèle logarithmique."
                    
                a, b = np.polyfit(np.log(x_sorted), y_sorted, 1)
                
                y_pred = a * np.log(x_sorted) + b
                y_mean = np.mean(y_sorted)
                ss_tot = np.sum((y_sorted - y_mean)**2)
                ss_res = np.sum((y_sorted - y_pred)**2)
                r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 1.0
                
                eq = f"y = {a:.4e} * ln(x) {'+' if b >= 0 else '-'} {abs(b):.4e}"
                
                x_fit = np.linspace(x_sorted[0], x_sorted[-1], 200)
                y_fit = a * np.log(x_fit) + b
                
                return {
                    'type': 'Logarithmique',
                    'eq': eq,
                    'r2': r2,
                    'x_fit': x_fit,
                    'y_fit': y_fit
                }, None
                
        except Exception as e:
            return None, f"Erreur de calcul mathématique: {str(e)}"
            
        return None, "Modèle inconnu ou non supporté."


class DigitizerCanvas(tk.Canvas):
    def __init__(self, parent, model, app, **kwargs):
        super().__init__(parent, highlightthickness=0, **kwargs)
        self.model = model
        self.app = app
        self.configure(bg=THEME['bg_main'])
        
        self.image_id = None
        self.active_handle = None   # Repère de calibration ou point de courbe sélectionné
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        
        # Liaison d'événements souris
        self.bind("<Configure>", self.on_resize)
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Motion>", self.on_hover)
        
        # Clic droit pour supprimer en mode Edition
        self.bind("<Button-3>", self.on_right_click)

    def on_resize(self, event):
        """Redessine le canvas en cas de changement de taille de la fenêtre."""
        self.update_image_display()

    def update_image_display(self):
        """Redimensionne dynamiquement l'image originale pour l'intégrer au canvas."""
        if self.model.original_image is None:
            self.draw_placeholder()
            return
            
        # Dimensions actuelles du Canvas
        cw, ch = self.winfo_width(), self.winfo_height()
        if cw < 10 or ch < 10:
            return
            
        iw, ih = self.model.original_image.size
        
        # Calcul du facteur d'échelle optimal pour insérer l'image
        scale = min(cw / iw, ch / ih)
        self.model.scale_factor = scale
        
        nw, nh = int(iw * scale), int(ih * scale)
        if nw < 1 or nh < 1:
            return
            
        # Marges pour centrer l'image
        self.model.pad_x = (cw - nw) // 2
        self.model.pad_y = (ch - nh) // 2
        
        # Redimensionnement de l'image
        resized = self.model.original_image.resize((nw, nh), Image.Resampling.LANCZOS)
        self.model.display_image = ImageTk.PhotoImage(resized)
        
        # Dessin complet
        self.redraw()

    def draw_placeholder(self):
        """Dessine le texte d'aide si aucune image n'est chargée."""
        self.delete("all")
        self.image_id = None
        
        cw, ch = self.winfo_width(), self.winfo_height()
        self.create_text(
            cw // 2, ch // 2 - 20,
            text="Glissez-déposez une capture d'écran de courbe ici\nou utilisez Ctrl + V pour coller depuis votre Presse-papiers",
            fill=THEME['fg_muted'], font=("Segoe UI", 12), justify="center"
        )
        self.create_rectangle(
            20, 20, cw - 20, ch - 20,
            outline=THEME['fg_muted'], dash=(5, 5), width=2
        )

    def redraw(self):
        """Redessine l'image, les repères de calibration et les points numérisés."""
        self.delete("all")
        
        if self.model.display_image is None:
            return
            
        # 1. Dessiner l'image de fond
        self.image_id = self.create_image(
            self.model.pad_x, self.model.pad_y,
            anchor="nw", image=self.model.display_image
        )
        
        # 2. Dessiner les points numérisés de la courbe
        pts = self.model.points
        if len(pts) > 0:
            disp_pts = []
            for u, v in pts:
                # Conversion Pixel Original -> Pixel Canvas
                uc = u * self.model.scale_factor + self.model.pad_x
                vc = v * self.model.scale_factor + self.model.pad_y
                disp_pts.append((uc, vc))
                
            # Dessiner la courbe reliant les points
            if len(disp_pts) > 1:
                self.create_line(
                    disp_pts, fill=THEME['accent_curve'], width=2, tags="curve_line"
                )
                
            # Dessiner les points individuels
            for i, (uc, vc) in enumerate(disp_pts):
                self.create_oval(
                    uc - 4, vc - 4, uc + 4, vc + 4,
                    fill=THEME['accent_curve'], outline="white", width=1,
                    tags=f"curve_point_{i}"
                )
                
        # 3. Dessiner les repères de calibration
        if self.model.is_calibrated():
            self.draw_calibration_lines()

    def draw_calibration_lines(self):
        """Dessine les lignes et poignées des repères de calibration."""
        scale = self.model.scale_factor
        px = self.model.pad_x
        py = self.model.pad_y
        
        # 1. Repères Axe X (Verticaux, couleur Orange)
        ux1, vx1 = self.model.calib_px['x1']
        ux2, vx2 = self.model.calib_px['x2']
        
        cx1 = ux1 * scale + px
        cx2 = ux2 * scale + px
        
        # Lignes verticales
        self.create_line(cx1, py, cx1, py + self.model.display_image.height(), fill=THEME['accent_x'], dash=(3, 3), width=1.5)
        self.create_line(cx2, py, cx2, py + self.model.display_image.height(), fill=THEME['accent_x'], dash=(3, 3), width=1.5)
        
        # Poignées de déplacement
        cy_h1 = vx1 * scale + py
        cy_h2 = vx2 * scale + py
        
        self.create_rectangle(cx1 - 6, cy_h1 - 6, cx1 + 6, cy_h1 + 6, fill=THEME['accent_x'], outline="white", tags="handle_x1")
        self.create_text(cx1, cy_h1 - 15, text=f"X1={self.model.calib_val['x1']}", fill=THEME['accent_x'], font=("Segoe UI", 8, "bold"))
        
        self.create_rectangle(cx2 - 6, cy_h2 - 6, cx2 + 6, cy_h2 + 6, fill=THEME['accent_x'], outline="white", tags="handle_x2")
        self.create_text(cx2, cy_h2 - 15, text=f"X2={self.model.calib_val['x2']}", fill=THEME['accent_x'], font=("Segoe UI", 8, "bold"))
        
        # 2. Repères Axe Y (Horizontaux, couleur Cyan)
        uy1, vy1 = self.model.calib_px['y1']
        uy2, vy2 = self.model.calib_px['y2']
        
        cy1 = vy1 * scale + py
        cy2 = vy2 * scale + py
        
        # Lignes horizontales
        self.create_line(px, cy1, px + self.model.display_image.width(), cy1, fill=THEME['accent_y'], dash=(3, 3), width=1.5)
        self.create_line(px, cy2, px + self.model.display_image.width(), cy2, fill=THEME['accent_y'], dash=(3, 3), width=1.5)
        
        # Poignées
        cx_h1 = uy1 * scale + px
        cx_h2 = uy2 * scale + px
        
        self.create_rectangle(cx_h1 - 6, cy1 - 6, cx_h1 + 6, cy1 + 6, fill=THEME['accent_y'], outline="white", tags="handle_y1")
        self.create_text(cx_h1 + 25, cy1, text=f"Y1={self.model.calib_val['y1']}", fill=THEME['accent_y'], font=("Segoe UI", 8, "bold"))
        
        self.create_rectangle(cx_h2 - 6, cy2 - 6, cx_h2 + 6, cy2 + 6, fill=THEME['accent_y'], outline="white", tags="handle_y2")
        self.create_text(cx_h2 + 25, cy2, text=f"Y2={self.model.calib_val['y2']}", fill=THEME['accent_y'], font=("Segoe UI", 8, "bold"))

    def canvas_to_orig_pixel(self, cx, cy):
        """Traduit une coordonnée canvas (pixel écran) en coordonnées pixel de l'image originale."""
        if self.model.display_image is None:
            return 0, 0
        u = (cx - self.model.pad_x) / self.model.scale_factor
        v = (cy - self.model.pad_y) / self.model.scale_factor
        
        # Bloquer dans les limites de l'image
        iw, ih = self.model.original_image.size
        u = max(0, min(iw - 1, u))
        v = max(0, min(ih - 1, v))
        return int(round(u)), int(round(v))

    def on_press(self, event):
        if self.model.display_image is None:
            return
            
        cx, cy = event.x, event.y
        scale = self.model.scale_factor
        px = self.model.pad_x
        py = self.model.pad_y
        
        # 1. Vérifier si on clique sur une poignée de calibration
        if self.model.is_calibrated():
            handles = {
                'x1': self.model.calib_px['x1'],
                'x2': self.model.calib_px['x2'],
                'y1': self.model.calib_px['y1'],
                'y2': self.model.calib_px['y2']
            }
            for name, pt in handles.items():
                u, v = pt
                hx = u * scale + px
                hy = v * scale + py
                if abs(cx - hx) <= 10 and abs(cy - hy) <= 10:
                    self.active_handle = f"calib_{name}"
                    return
                    
        # 2. En mode "Edition", vérifier si on clique sur un point de la courbe pour le déplacer
        mode = self.app.get_trace_mode()
        if mode == "edition":
            for i, (u, v) in enumerate(self.model.points):
                hx = u * scale + px
                hy = v * scale + py
                if abs(cx - hx) <= 8 and abs(cy - hy) <= 8:
                    self.active_handle = f"point_{i}"
                    return
                    
        # 3. En mode "Manuel", un clic gauche ajoute un point de courbe
        if mode == "manuel":
            u, v = self.canvas_to_orig_pixel(cx, cy)
            self.model.points.append((u, v))
            self.redraw()
            self.app.update_data_views()
            
        # 4. En mode "Suivi Automatique", clic gauche lance l'algorithme
        elif mode == "auto":
            u, v = self.canvas_to_orig_pixel(cx, cy)
            self.run_auto_tracing(u, v)

    def on_drag(self, event):
        if self.model.display_image is None or self.active_handle is None:
            return
            
        cx, cy = event.x, event.y
        u, v = self.canvas_to_orig_pixel(cx, cy)
        
        # Glisser un repère de calibration
        if self.active_handle.startswith("calib_"):
            name = self.active_handle.split("_")[1]
            self.model.calib_px[name] = (u, v)
            self.redraw()
            self.app.update_data_views()
            
        # Glisser un point de courbe numérisé
        elif self.active_handle.startswith("point_"):
            idx = int(self.active_handle.split("_")[1])
            if 0 <= idx < len(self.model.points):
                self.model.points[idx] = (u, v)
                self.redraw()
                self.app.update_data_views()

    def on_release(self, event):
        self.active_handle = None
        self.app.update_data_views()

    def on_hover(self, event):
        """Gère la loupe de précision et la lecture des coordonnées sous le curseur."""
        if self.model.original_image is None:
            return
            
        cx, cy = event.x, event.y
        u, v = self.canvas_to_orig_pixel(cx, cy)
        
        # Mettre à jour l'affichage des coordonnées réelles dans la barre d'état
        if self.model.is_calibrated():
            rx, ry = self.model.pixel_to_real(u, v)
            self.app.status_var.set(f"Curseur: X = {rx:.4f}, Y = {ry:.4f}  (Pixel: {u}, {v})")
        else:
            self.app.status_var.set(f"Curseur: Pixel X = {u}, Y = {v}  (Calibration requise)")
            
        # Actualiser la loupe de zoom
        self.app.update_loupe(u, v)

    def on_right_click(self, event):
        """Permet de supprimer un point numérisé par clic droit en mode Edition."""
        if self.model.original_image is None or self.app.get_trace_mode() != "edition":
            return
            
        cx, cy = event.x, event.y
        scale = self.model.scale_factor
        px = self.model.pad_x
        py = self.model.pad_y
        
        for i, (u, v) in enumerate(self.model.points):
            hx = u * scale + px
            hy = v * scale + py
            if abs(cx - hx) <= 8 and abs(cy - hy) <= 8:
                del self.model.points[i]
                self.redraw()
                self.app.update_data_views()
                break

    def run_auto_tracing(self, u_start, v_start):
        """Algorithme de tracé automatique intelligent (suivi de couleur)."""
        img_arr = np.array(self.model.original_image)
        h_orig, w_orig, _ = img_arr.shape
        
        # Récupérer la couleur de la cible au point cliqué
        target_color = img_arr[v_start, u_start, :3].astype(float)
        
        # Tolérance de la couleur définie par le slider de l'app
        tol = self.app.get_auto_tolerance()
        
        # Paramètres de recherche
        step_x = 4  # Pas de pixels horizontaux
        w_y = 20    # Demi-hauteur de la fenêtre de recherche verticale (pixels)
        
        extracted_pts = [(u_start, v_start)]
        
        # 1. Tracé vers la droite
        v_prev = v_start
        for u in range(u_start + step_x, w_orig - 2, step_x):
            # Zone verticale de recherche
            v_min = max(0, v_prev - w_y)
            v_max = min(h_orig - 1, v_prev + w_y)
            
            best_v = None
            min_dist = 999999.0
            
            for v in range(v_min, v_max + 1):
                col = img_arr[v, u, :3].astype(float)
                dist = np.linalg.norm(col - target_color)
                if dist < min_dist:
                    min_dist = dist
                    best_v = v
                    
            if best_v is not None and min_dist <= tol:
                extracted_pts.append((u, best_v))
                v_prev = best_v
            else:
                break  # Arrêt si le fil est rompu ou dévie trop
                
        # 2. Tracé vers la gauche
        v_prev = v_start
        for u in range(u_start - step_x, 1, -step_x):
            v_min = max(0, v_prev - w_y)
            v_max = min(h_orig - 1, v_prev + w_y)
            
            best_v = None
            min_dist = 999999.0
            
            for v in range(v_min, v_max + 1):
                col = img_arr[v, u, :3].astype(float)
                dist = np.linalg.norm(col - target_color)
                if dist < min_dist:
                    min_dist = dist
                    best_v = v
                    
            if best_v is not None and min_dist <= tol:
                extracted_pts.insert(0, (u, best_v))
                v_prev = best_v
            else:
                break
                
        # Ajouter les points extraits à la liste des points globale
        # Pour éviter les doublons horizontaux serrés, on nettoie ou on ajoute simplement
        self.model.points.extend(extracted_pts)
        
        # Tri final de tous les points de la courbe par X croissant
        self.model.points = sorted(list(set(self.model.points)), key=lambda p: p[0])
        
        self.redraw()
        self.app.update_data_views()


class CurveDigitizerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CurveDigitizer Pro - Récupérateur & Régression de Courbes")
        self.geometry("1300x850")
        self.configure(bg=THEME['bg_main'])
        
        self.model = DigitizerModel()
        
        # Déclarer les variables TK
        self.status_var = tk.StringVar(value="Veuillez importer une capture d'écran pour commencer.")
        self.x_min_val = tk.StringVar(value="0.0")
        self.x_max_val = tk.StringVar(value="10.0")
        self.y_min_val = tk.StringVar(value="0.0")
        self.y_max_val = tk.StringVar(value="10.0")
        
        self.x_scale_var = tk.StringVar(value="linear")
        self.y_scale_var = tk.StringVar(value="linear")
        
        self.trace_mode_var = tk.StringVar(value="manuel")
        self.auto_tol_var = tk.DoubleVar(value=60.0)
        
        self.reg_type_var = tk.StringVar(value="Aucune")
        self.poly_deg_var = tk.IntVar(value=2)
        
        # Construction de l'UI
        self.setup_ui_layout()
        
        # Configuration des écoutes de variables pour mise à jour dynamique de la calibration
        self.x_min_val.trace_add("write", self.on_calib_inputs_changed)
        self.x_max_val.trace_add("write", self.on_calib_inputs_changed)
        self.y_min_val.trace_add("write", self.on_calib_inputs_changed)
        self.y_max_val.trace_add("write", self.on_calib_inputs_changed)
        
        self.x_scale_var.trace_add("write", self.on_scale_type_changed)
        self.y_scale_var.trace_add("write", self.on_scale_type_changed)
        
        self.reg_type_var.trace_add("write", self.on_regression_changed)
        self.poly_deg_var.trace_add("write", self.on_regression_changed)
        
        # Raccourci Presse-papiers Ctrl+V global
        self.bind("<Control-v>", self.on_clipboard_paste)
        self.bind("<Control-V>", self.on_clipboard_paste)

    def setup_ui_layout(self):
        """Conçoit la mise en page ergonomique et moderne avec Thème Sombre."""
        # Configurer le gestionnaire de grille principale
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, minsize=320, weight=0) # Volet gauche de contrôle
        self.columnconfigure(1, weight=1)              # Volet central (Image)
        self.columnconfigure(2, minsize=420, weight=0) # Volet droit (Graphiques & Tableau)
        
        # 1. PANNEAU DE CONTROLE GAUCHE
        left_frame = tk.Frame(self, bg=THEME['bg_panel'], padx=10, pady=10)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(5, 2), pady=5)
        self.build_left_control_panel(left_frame)
        
        # 2. CANVAS CENTRAL
        center_frame = tk.Frame(self, bg=THEME['bg_main'])
        center_frame.grid(row=0, column=1, sticky="nsew", padx=2, pady=5)
        
        center_title = tk.Label(center_frame, text="Capture d'écran active", fg=THEME['fg_text'], bg=THEME['bg_main'], font=("Segoe UI", 11, "bold"))
        center_title.pack(anchor="w", pady=(0, 5))
        
        self.canvas = DigitizerCanvas(center_frame, self.model, self)
        self.canvas.pack(fill="both", expand=True)
        
        # 3. PANNEAU DROIT (Analyses, Graphiques et Résultats)
        right_frame = tk.Frame(self, bg=THEME['bg_panel'], padx=10, pady=10)
        right_frame.grid(row=0, column=2, sticky="nsew", padx=(2, 5), pady=5)
        self.build_right_results_panel(right_frame)
        
        # 4. BARRE D'ETAT INFERIEURE
        status_bar = tk.Frame(self, bg=THEME['bg_main'], height=25, bd=1, relief="flat")
        status_bar.grid(row=1, column=0, columnspan=3, sticky="ew")
        status_label = tk.Label(status_bar, textvariable=self.status_var, fg=THEME['fg_muted'], bg=THEME['bg_main'], font=("Segoe UI", 9))
        status_label.pack(side="left", padx=10, pady=2)

    def build_left_control_panel(self, parent):
        parent.rowconfigure(0, weight=0) # Import
        parent.rowconfigure(1, weight=0) # Calibration
        parent.rowconfigure(2, weight=0) # Outils
        parent.rowconfigure(3, weight=1) # Loupe (prend l'espace disponible)
        
        # ------------------ SECTION IMPORT ------------------
        import_group = tk.LabelFrame(parent, text=" 1. Charger une Image ", fg="white", bg=THEME['bg_panel'], font=("Segoe UI", 10, "bold"), bd=1, padx=8, pady=8)
        import_group.pack(fill="x", pady=(0, 10))
        
        btn_open = tk.Button(
            import_group, text="Ouvrir un fichier image...", bg=THEME['btn_bg'], fg="white",
            relief="flat", activebackground=THEME['btn_active'], activeforeground="white",
            font=("Segoe UI", 9, "bold"), pady=6, command=self.import_image_dialog
        )
        btn_open.pack(fill="x", pady=2)
        
        btn_paste = tk.Button(
            import_group, text="Coller Presse-papiers (Ctrl+V)", bg=THEME['btn_bg'], fg=THEME['accent_x'],
            relief="flat", activebackground=THEME['btn_active'], activeforeground="white",
            font=("Segoe UI", 9, "bold"), pady=6, command=self.on_clipboard_paste
        )
        btn_paste.pack(fill="x", pady=(5, 2))
        
        # ------------------ SECTION CALIBRATION ------------------
        calib_group = tk.LabelFrame(parent, text=" 2. Calibration des échelles ", fg="white", bg=THEME['bg_panel'], font=("Segoe UI", 10, "bold"), bd=1, padx=8, pady=8)
        calib_group.pack(fill="x", pady=(0, 10))
        
        # Grille pour les valeurs Xmin, Xmax, Ymin, Ymax
        grid_frame = tk.Frame(calib_group, bg=THEME['bg_panel'])
        grid_frame.pack(fill="x", pady=2)
        
        # Ligne Xmin / Xmax
        tk.Label(grid_frame, text="X_min:", fg=THEME['accent_x'], bg=THEME['bg_panel'], font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", pady=2)
        ent_xmin = tk.Entry(grid_frame, textvariable=self.x_min_val, width=8, bg=THEME['entry_bg'], fg=THEME['entry_fg'], insertbackground="white", bd=1, relief="solid")
        ent_xmin.grid(row=0, column=1, padx=(5, 10), pady=2)
        
        tk.Label(grid_frame, text="X_max:", fg=THEME['accent_x'], bg=THEME['bg_panel'], font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", pady=2)
        ent_xmax = tk.Entry(grid_frame, textvariable=self.x_max_val, width=8, bg=THEME['entry_bg'], fg=THEME['entry_fg'], insertbackground="white", bd=1, relief="solid")
        ent_xmax.grid(row=0, column=3, padx=5, pady=2)
        
        # Ligne Ymin / Ymax
        tk.Label(grid_frame, text="Y_min:", fg=THEME['accent_y'], bg=THEME['bg_panel'], font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w", pady=6)
        ent_ymin = tk.Entry(grid_frame, textvariable=self.y_min_val, width=8, bg=THEME['entry_bg'], fg=THEME['entry_fg'], insertbackground="white", bd=1, relief="solid")
        ent_ymin.grid(row=1, column=1, padx=(5, 10), pady=6)
        
        tk.Label(grid_frame, text="Y_max:", fg=THEME['accent_y'], bg=THEME['bg_panel'], font=("Segoe UI", 9, "bold")).grid(row=1, column=2, sticky="w", pady=6)
        ent_ymax = tk.Entry(grid_frame, textvariable=self.y_max_val, width=8, bg=THEME['entry_bg'], fg=THEME['entry_fg'], insertbackground="white", bd=1, relief="solid")
        ent_ymax.grid(row=1, column=3, padx=5, pady=6)
        
        # Sélecteurs Log / Lin
        scale_frame = tk.Frame(calib_group, bg=THEME['bg_panel'])
        scale_frame.pack(fill="x", pady=5)
        
        tk.Label(scale_frame, text="Axe X :", fg="white", bg=THEME['bg_panel'], font=("Segoe UI", 9)).pack(side="left", padx=(0, 5))
        tk.Radiobutton(scale_frame, text="Lin", variable=self.x_scale_var, value="linear", fg="white", bg=THEME['bg_panel'], selectcolor=THEME['bg_control'], font=("Segoe UI", 8)).pack(side="left", padx=2)
        tk.Radiobutton(scale_frame, text="Log", variable=self.x_scale_var, value="log", fg="white", bg=THEME['bg_panel'], selectcolor=THEME['bg_control'], font=("Segoe UI", 8)).pack(side="left", padx=2)
        
        tk.Label(scale_frame, text="  |  Axe Y :", fg="white", bg=THEME['bg_panel'], font=("Segoe UI", 9)).pack(side="left", padx=5)
        tk.Radiobutton(scale_frame, text="Lin", variable=self.y_scale_var, value="linear", fg="white", bg=THEME['bg_panel'], selectcolor=THEME['bg_control'], font=("Segoe UI", 8)).pack(side="left", padx=2)
        tk.Radiobutton(scale_frame, text="Log", variable=self.y_scale_var, value="log", fg="white", bg=THEME['bg_panel'], selectcolor=THEME['bg_control'], font=("Segoe UI", 8)).pack(side="left", padx=2)
        
        self.calib_status_label = tk.Label(calib_group, text="ÉTAT: Non calibré", fg="#ff3333", bg=THEME['bg_panel'], font=("Segoe UI", 9, "bold"))
        self.calib_status_label.pack(fill="x", pady=(5, 0))

        # ------------------ SECTION NUMERISATION ------------------
        num_group = tk.LabelFrame(parent, text=" 3. Outils de Tracé ", fg="white", bg=THEME['bg_panel'], font=("Segoe UI", 10, "bold"), bd=1, padx=8, pady=8)
        num_group.pack(fill="x", pady=(0, 10))
        
        # Boutons de mode de tracé
        r1 = tk.Radiobutton(num_group, text="Tracé Manuel (Clic par clic)", variable=self.trace_mode_var, value="manuel", fg="white", bg=THEME['bg_panel'], selectcolor=THEME['bg_control'], font=("Segoe UI", 9))
        r1.pack(anchor="w", pady=2)
        
        r2 = tk.Radiobutton(num_group, text="Suivi Automatique (Intelligent)", variable=self.trace_mode_var, value="auto", fg="white", bg=THEME['bg_panel'], selectcolor=THEME['bg_control'], font=("Segoe UI", 9))
        r2.pack(anchor="w", pady=2)
        
        # Tolérance pour suivi automatique
        tol_frame = tk.Frame(num_group, bg=THEME['bg_panel'])
        tol_frame.pack(fill="x", padx=15, pady=(2, 5))
        tk.Label(tol_frame, text="Sensibilité (couleur) :", fg=THEME['fg_muted'], bg=THEME['bg_panel'], font=("Segoe UI", 8)).pack(side="left")
        tol_slider = tk.Scale(tol_frame, from_=10.0, to=150.0, orient="horizontal", variable=self.auto_tol_var, bg=THEME['bg_panel'], fg="white", highlightthickness=0, bd=0, troughcolor=THEME['bg_control'])
        tol_slider.pack(side="right", fill="x", expand=True, padx=(5, 0))
        
        r3 = tk.Radiobutton(num_group, text="Édition / Déplacement points", variable=self.trace_mode_var, value="edition", fg="white", bg=THEME['bg_panel'], selectcolor=THEME['bg_control'], font=("Segoe UI", 9))
        r3.pack(anchor="w", pady=2)
        
        tk.Label(num_group, text="Astuce: Clic-droit sur un point pour le supprimer (Editer).", fg=THEME['fg_muted'], bg=THEME['bg_panel'], font=("Segoe UI", 8, "italic")).pack(anchor="w", pady=(4, 0))

        # ------------------ LOUPE DE ZOOM DE PRECISION ------------------
        zoom_group = tk.LabelFrame(parent, text=" Loupe de précision ", fg="white", bg=THEME['bg_panel'], font=("Segoe UI", 10, "bold"), bd=1, padx=8, pady=8)
        zoom_group.pack(fill="both", expand=True, pady=(0, 5))
        
        # Canvas contenant l'image de la loupe
        self.zoom_canvas = tk.Canvas(zoom_group, width=150, height=150, bg=THEME['bg_control'], highlightthickness=1, highlightbackground="gray")
        self.zoom_canvas.pack(pady=5)
        self.draw_zoom_placeholder()

    def build_right_results_panel(self, parent):
        # Configurer l'espace vertical
        parent.rowconfigure(0, weight=1) # Graphique Matplotlib
        parent.rowconfigure(1, weight=0) # Tableau de Données (petit volet ou onglet)
        parent.rowconfigure(2, weight=0) # Régression
        parent.rowconfigure(3, weight=0) # Action Exports
        
        # ------------------ GRAPHIQUE MATPLOTLIB ------------------
        graph_group = tk.LabelFrame(parent, text=" Courbe Reconstituée (Matplotlib) ", fg="white", bg=THEME['bg_panel'], font=("Segoe UI", 10, "bold"), bd=1, padx=5, pady=5)
        graph_group.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        
        self.fig, self.ax = plt.subplots(figsize=(4, 3.5), facecolor=THEME['bg_panel'])
        self.ax.set_facecolor(THEME['bg_control'])
        self.ax.tick_params(colors='white', labelsize=8)
        self.ax.grid(True, color='gray', linestyle=':', alpha=0.5)
        self.ax.spines['bottom'].set_color('white')
        self.ax.spines['top'].set_color('white')
        self.ax.spines['left'].set_color('white')
        self.ax.spines['right'].set_color('white')
        
        self.chart_canvas = FigureCanvasTkAgg(self.fig, master=graph_group)
        self.chart_canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # ------------------ TABLEAU DES COORDONNEES ------------------
        table_group = tk.LabelFrame(parent, text=" Points Extraits ", fg="white", bg=THEME['bg_panel'], font=("Segoe UI", 10, "bold"), bd=1, padx=5, pady=5)
        table_group.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        
        # Creation du Treeview
        columns = ("id", "x", "y")
        self.tree = ttk.Treeview(table_group, columns=columns, show="headings", height=5)
        self.tree.heading("id", text="N°")
        self.tree.heading("x", text="Valeur X")
        self.tree.heading("y", text="Valeur Y")
        
        self.tree.column("id", width=40, anchor="center")
        self.tree.column("x", width=160, anchor="e")
        self.tree.column("y", width=160, anchor="e")
        
        # Scrollbar pour le tableau
        scrollbar = ttk.Scrollbar(table_group, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="x", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Personnaliser le style ttk du Treeview pour le mode sombre
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=THEME['bg_control'], fieldbackground=THEME['bg_control'], foreground="white", gridcolor="gray")
        style.configure("Treeview.Heading", background=THEME['btn_bg'], foreground="white")

        # ------------------ ANALYSE DE REGRESSION ------------------
        reg_group = tk.LabelFrame(parent, text=" Analyse de Régression Mathématique ", fg="white", bg=THEME['bg_panel'], font=("Segoe UI", 10, "bold"), bd=1, padx=8, pady=8)
        reg_group.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        
        top_reg = tk.Frame(reg_group, bg=THEME['bg_panel'])
        top_reg.pack(fill="x", pady=2)
        
        tk.Label(top_reg, text="Modèle de Fit :", fg="white", bg=THEME['bg_panel'], font=("Segoe UI", 9)).pack(side="left")
        
        models = ["Aucune", "Linéaire", "Polynomiale", "Exponentielle", "Puissance", "Logarithmique"]
        self.reg_combobox = ttk.Combobox(top_reg, values=models, textvariable=self.reg_type_var, state="readonly", width=15)
        self.reg_combobox.pack(side="left", padx=5)
        
        # Frame pour le degré polynomial (visible uniquement si Polynomiale est sélectionné)
        self.poly_deg_frame = tk.Frame(top_reg, bg=THEME['bg_panel'])
        tk.Label(self.poly_deg_frame, text="Deg :", fg="white", bg=THEME['bg_panel'], font=("Segoe UI", 9)).pack(side="left")
        spin = tk.Spinbox(self.poly_deg_frame, from_=2, to=5, width=3, textvariable=self.poly_deg_var, bg=THEME['entry_bg'], fg="white", buttonbackground=THEME['btn_bg'])
        spin.pack(side="left", padx=2)
        
        # Affichage de l'Équation et du R2
        info_frame = tk.Frame(reg_group, bg=THEME['bg_control'], padx=10, pady=8, bd=1, relief="solid")
        info_frame.pack(fill="x", pady=(8, 2))
        
        self.eq_label = tk.Label(info_frame, text="Équation : (En attente de points)", fg=THEME['accent_reg'], bg=THEME['bg_control'], font=("Consolas", 10, "bold"), wraplength=360, justify="left")
        self.eq_label.pack(anchor="w", pady=2)
        
        self.r2_label = tk.Label(info_frame, text="Coeff R²  : N/A", fg="white", bg=THEME['bg_control'], font=("Segoe UI", 10, "bold"))
        self.r2_label.pack(anchor="w", pady=2)
        
        # Bouton pour copier l'équation
        self.btn_copy_eq = tk.Button(
            reg_group, text="Copier l'Équation", bg=THEME['btn_bg'], fg="white",
            relief="flat", font=("Segoe UI", 8), pady=2, command=self.copy_equation_to_clipboard
        )
        self.btn_copy_eq.pack(anchor="e", pady=(5, 0))

        # ------------------ EXPORTS ------------------
        export_group = tk.Frame(parent, bg=THEME['bg_panel'])
        export_group.grid(row=3, column=0, sticky="ew")
        
        # Boutons d'export
        btn_copy = tk.Button(
            export_group, text="Copier Tableau (Excel)", bg=THEME['btn_bg'], fg="white",
            relief="flat", activebackground=THEME['btn_active'], activeforeground="white",
            font=("Segoe UI", 9, "bold"), pady=6, command=self.copy_table_to_clipboard
        )
        btn_copy.pack(side="left", fill="x", expand=True, padx=(0, 4))
        
        btn_save = tk.Button(
            export_group, text="Enregistrer CSV...", bg=THEME['btn_bg'], fg="white",
            relief="flat", activebackground=THEME['btn_active'], activeforeground="white",
            font=("Segoe UI", 9, "bold"), pady=6, command=self.export_csv_dialog
        )
        btn_save.pack(side="left", fill="x", expand=True, padx=2)
        
        btn_clear = tk.Button(
            export_group, text="Effacer Tout", bg="#d90429", fg="white",
            relief="flat", activebackground="#ef233c", activeforeground="white",
            font=("Segoe UI", 9, "bold"), pady=6, command=self.clear_all_points
        )
        btn_clear.pack(side="left", fill="x", expand=True, padx=(4, 0))

    # --- LOUPE ET ZOOM ---
    def draw_zoom_placeholder(self):
        self.zoom_canvas.delete("all")
        self.zoom_canvas.create_text(75, 75, text="Pas d'image", fill=THEME['fg_muted'], font=("Segoe UI", 9))

    def update_loupe(self, u_orig, v_orig):
        """Met à jour le panneau Loupe avec un agrandissement x5 autour du curseur."""
        if self.model.original_image is None:
            return
            
        iw, ih = self.model.original_image.size
        
        # Taille du cadre à copier (30x30 pixels)
        side = 30
        r = side // 2
        
        # Coordonnées du rectangle sur l'image originale
        x0, y0 = u_orig - r, v_orig - r
        x1, y1 = u_orig + r, v_orig + r
        
        # Recadrage avec padding noir si le curseur sort de l'image
        crop_box = (max(0, x0), max(0, y0), min(iw, x1), min(ih, y1))
        cropped = self.model.original_image.crop(crop_box)
        
        # Créer une image noire de 30x30 pour insérer la partie découpée
        pad_img = Image.new("RGB", (side, side), color=THEME['bg_control'])
        
        # Calculer le décalage pour insérer la partie découpée
        dx = max(0, -x0)
        dy = max(0, -y0)
        pad_img.paste(cropped, (dx, dy))
        
        # Dessiner les repères de calibration et les points numérisés sur l'image 30x30 avant grossissement
        draw_pad = ImageDraw.Draw(pad_img)
        
        # 1. Repères Axe X (Verticaux, couleur Orange)
        for name in ['x1', 'x2']:
            pt = self.model.calib_px[name]
            if pt is not None:
                ux, _ = pt
                u_rel = ux - x0
                if 0 <= u_rel < side:
                    draw_pad.line((u_rel, 0, u_rel, side), fill=THEME['accent_x'], width=1)
                    
        # 2. Repères Axe Y (Horizontaux, couleur Cyan)
        for name in ['y1', 'y2']:
            pt = self.model.calib_px[name]
            if pt is not None:
                _, vy = pt
                v_rel = vy - y0
                if 0 <= v_rel < side:
                    draw_pad.line((0, v_rel, side, v_rel), fill=THEME['accent_y'], width=1)
                    
        # 3. Points numérisés de la courbe (Verts)
        for u_pt, v_pt in self.model.points:
            u_rel = u_pt - x0
            v_rel = v_pt - y0
            if 0 <= u_rel < side and 0 <= v_rel < side:
                draw_pad.ellipse((u_rel - 1, v_rel - 1, u_rel + 1, v_rel + 1), fill=THEME['accent_curve'])
        
        # Agrandir l'image à 150x150 en conservant des pixels nets (NEAREST)
        zoomed = pad_img.resize((150, 150), Image.Resampling.NEAREST)
        
        # Dessiner le réticule central sur l'image zoomée
        draw = ImageDraw.Draw(zoomed)
        # Réticule rouge central
        draw.line((75, 0, 75, 150), fill="red", width=1)
        draw.line((0, 75, 150, 75), fill="red", width=1)
        
        # Afficher dans le Canvas
        self.zoom_photo = ImageTk.PhotoImage(zoomed)
        self.zoom_canvas.delete("all")
        self.zoom_canvas.create_image(0, 0, anchor="nw", image=self.zoom_photo)

    # --- EVENEMENTS ET ACTIONS ---
    def import_image_dialog(self):
        """Ouvre une boîte de dialogue pour importer un fichier image."""
        file_path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.webp *.gif"), ("Tous les fichiers", "*.*")]
        )
        if file_path:
            try:
                img = Image.open(file_path)
                self.load_image(img, os.path.basename(file_path))
            except Exception as e:
                messagebox.showerror("Erreur d'importation", f"Impossible d'ouvrir l'image :\n{str(e)}")

    def on_clipboard_paste(self, event=None):
        """Récupère et charge l'image directement depuis le presse-papiers."""
        try:
            img = ImageGrab.grabclipboard()
            if img is not None:
                if isinstance(img, list):
                    # Parfois grabclipboard renvoie une liste de chemins de fichiers copiés
                    if len(img) > 0 and os.path.exists(img[0]):
                        img = Image.open(img[0])
                if isinstance(img, Image.Image):
                    self.load_image(img, "Presse-papiers")
                else:
                    messagebox.showerror("Erreur", "Le presse-papiers ne contient pas de données image valides.")
            else:
                messagebox.showinfo("Presse-papiers vide", "Aucune image trouvée dans le presse-papiers.\nUtilisez Win+Shift+S ou la touche Imp.Écran pour copier une courbe d'abord.")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de coller l'image : {str(e)}")

    def load_image(self, img, source_name):
        """Initialise le modèle et le canvas avec la nouvelle image chargée."""
        # Convertir en RGB si nécessaire pour éviter les bugs de palette
        if img.mode != "RGB":
            img = img.convert("RGB")
            
        self.model.original_image = img
        iw, ih = img.size
        
        # Initialiser les repères de calibration à des positions par défaut
        # X1 (15%), X2 (85%), Y1 (85%), Y2 (15%)
        self.model.calib_px['x1'] = (int(iw * 0.15), int(ih * 0.5))
        self.model.calib_px['x2'] = (int(iw * 0.85), int(ih * 0.5))
        self.model.calib_px['y1'] = (int(iw * 0.5), int(ih * 0.85))
        self.model.calib_px['y2'] = (int(iw * 0.5), int(ih * 0.15))
        
        # Vider la liste des points numérisés
        self.model.points = []
        
        # Actualiser les vues
        self.canvas.update_image_display()
        self.update_data_views()
        self.status_var.set(f"Image chargée : {source_name} ({iw}x{ih} px). Ajustez les repères de calibration.")

    def on_calib_inputs_changed(self, *args):
        """Lit les saisies utilisateur pour les valeurs réelles et met à jour le modèle."""
        try:
            self.model.calib_val['x1'] = float(self.x_min_val.get())
            self.model.calib_val['x2'] = float(self.x_max_val.get())
            self.model.calib_val['y1'] = float(self.y_min_val.get())
            self.model.calib_val['y2'] = float(self.y_max_val.get())
            self.canvas.redraw()
            self.update_data_views()
        except ValueError:
            # Ignorer temporairement si l'utilisateur est en train de saisir un nombre incomplet (ex: "-")
            pass

    def on_scale_type_changed(self, *args):
        """Définit si les échelles X et Y sont linéaires ou logarithmiques."""
        self.model.x_scale = self.x_scale_var.get()
        self.model.y_scale = self.y_scale_var.get()
        self.canvas.redraw()
        self.update_data_views()

    def on_regression_changed(self, *args):
        """Gère le masquage/affichage dynamique des options de régression et relance le calcul."""
        sel_type = self.reg_type_var.get()
        self.model.reg_type = sel_type
        self.model.poly_degree = self.poly_deg_var.get()
        
        if sel_type == "Polynomiale":
            self.poly_deg_frame.pack(side="left", padx=5)
        else:
            self.poly_deg_frame.pack_forget()
            
        self.update_data_views()

    def get_trace_mode(self):
        return self.trace_mode_var.get()

    def get_auto_tolerance(self):
        return self.auto_tol_var.get()

    # --- MISE A JOUR DES DONNEES ET GRAPHIQUES ---
    def update_data_views(self):
        """Actualise le tableau, recalcule la régression et redessine le graphique Matplotlib."""
        if not self.model.is_calibrated():
            self.calib_status_label.config(text="ÉTAT: Non calibré", fg="#ff3333")
            return
        else:
            self.calib_status_label.config(text="ÉTAT: Calibré (Prêt)", fg="#39ff14")

        # 1. Mettre à jour le tableau des points
        # Vider le tableau
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        real_pts = self.model.get_real_points()
        for i, (rx, ry) in enumerate(real_pts):
            self.tree.insert("", "end", values=(i + 1, f"{rx:.6g}", f"{ry:.6g}"))

        # 2. Calculer la régression
        reg_data = None
        if len(self.model.points) >= 2 and self.model.reg_type != "Aucune":
            reg_data, err = self.model.compute_regression()
            if err:
                self.eq_label.config(text=err, fg="#ff3333")
                self.r2_label.config(text="Coeff R²  : N/A")
            elif reg_data:
                self.eq_label.config(text=f"Équation :\n{reg_data['eq']}", fg=THEME['accent_reg'])
                self.r2_label.config(text=f"Coeff R²  : {reg_data['r2']:.6f}")
        else:
            self.eq_label.config(text="Équation : (Sélectionnez un modèle)", fg=THEME['fg_muted'])
            self.r2_label.config(text="Coeff R²  : N/A")

        # 3. Mettre à jour le graphique Matplotlib
        self.ax.clear()
        self.ax.set_facecolor(THEME['bg_control'])
        self.ax.grid(True, color='gray', linestyle=':', alpha=0.5)
        
        # Appliquer les échelles de calibration (Lin / Log)
        if self.model.x_scale == "log":
            self.ax.set_xscale("log")
        else:
            self.ax.set_xscale("linear")
            
        if self.model.y_scale == "log":
            self.ax.set_yscale("log")
        else:
            self.ax.set_yscale("linear")
            
        # Dessiner la courbe numérisée si des points existent
        if len(real_pts) > 0:
            rx, ry = zip(*real_pts)
            self.ax.plot(rx, ry, color=THEME['accent_curve'], marker='o', markersize=4, linestyle='-', label="Points numérisés")
            
        # Dessiner le fit de régression si disponible
        if reg_data is not None:
            self.ax.plot(reg_data['x_fit'], reg_data['y_fit'], color=THEME['accent_reg'], linestyle='--', linewidth=2, label=reg_data['type'])
            
        self.ax.legend(facecolor=THEME['bg_panel'], edgecolor='white', labelcolor='white', fontsize=8)
        self.ax.set_xlabel("Axe X", color="white", fontsize=8)
        self.ax.set_ylabel("Axe Y", color="white", fontsize=8)
        
        # Ajuster les marges
        self.fig.tight_layout()
        self.chart_canvas.draw()

    # --- ACTIONS D'EXPORT ---
    def copy_equation_to_clipboard(self):
        """Copie l'équation de régression affichée dans le presse-papiers."""
        eq_text = self.eq_label.cget("text")
        if "Équation :" in eq_text and len(eq_text) > 12:
            clean_eq = eq_text.replace("Équation :\n", "")
            self.clipboard_clear()
            self.clipboard_append(clean_eq)
            self.update()
            self.status_var.set("Équation copiée dans le presse-papiers !")
        else:
            messagebox.showwarning("Copie impossible", "Aucune équation de régression disponible pour le moment.")

    def copy_table_to_clipboard(self):
        """Copie les données réelles formatées sous forme de table Excel."""
        real_pts = self.model.get_real_points()
        if len(real_pts) == 0:
            messagebox.showwarning("Copie impossible", "Le tableau est vide. Veuillez d'abord numériser des points.")
            return
            
        # Formater les colonnes séparées par des tabulations (\t) pour Excel
        lines = ["X\tY"]
        for x, y in real_pts:
            lines.append(f"{str(x).replace('.', ',')}\t{str(y).replace('.', ',')}") # Format compatible Excel FR (virgule)
            
        table_str = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(table_str)
        self.update()
        self.status_var.set(f"{len(real_pts)} points copiés (format Excel).")

    def export_csv_dialog(self):
        """Enregistre les données extraites au format CSV."""
        real_pts = self.model.get_real_points()
        if len(real_pts) == 0:
            messagebox.showwarning("Export impossible", "Aucun point de courbe à exporter.")
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("Fichiers CSV (*.csv)", "*.csv"), ("Tous les fichiers", "*.*")]
        )
        if file_path:
            try:
                # Créer un DataFrame pandas et l'enregistrer
                df = pd.DataFrame(real_pts, columns=["X", "Y"])
                df.to_csv(file_path, index=False, sep=";")
                self.status_var.set(f"Données enregistrées avec succès dans : {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Erreur de sauvegarde", f"Une erreur s'est produite lors de l'enregistrement :\n{str(e)}")

    def clear_all_points(self):
        """Efface tous les points numérisés de la courbe."""
        if len(self.model.points) == 0:
            return
        if messagebox.askyesno("Confirmer", "Voulez-vous vraiment effacer tous les points numérisés de cette courbe ?"):
            self.model.points = []
            self.canvas.redraw()
            self.update_data_views()
            self.status_var.set("Tous les points de la courbe ont été effacés.")


if __name__ == "__main__":
    app = CurveDigitizerApp()
    app.mainloop()
